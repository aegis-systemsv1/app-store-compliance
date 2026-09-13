#!/usr/bin/env python3
"""AEGIS portfolio compliance audit.

Runs the underlying App Store Compliance Guard across multiple apps, parses findings,
applies time-bounded human classifications, tracks store/account readiness, and emits
human and machine-readable release evidence without weakening the underlying rules.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

SUMMARY_RE = re.compile(r"Summary\. critical=(\d+) high=(\d+) medium=(\d+)")
FINDING_RE = re.compile(r"^\s*\[(CRITICAL|HIGH|MEDIUM)\]\s+(\S+)\s+(.*)$")
FIX_RE = re.compile(r"^\s*fix\.\s+(.*)$")
CLASSIFICATIONS = {"REAL", "FALSE_POSITIVE", "STORE_TASK", "OWNER_LEGAL", "DEFERRED"}
SEVERITY_RANK = {"critical": 3, "high": 2, "medium": 1}


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise SystemExit(f"File not found: {path}")
        return {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return data


def load_config(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data.get("apps"), list):
        raise SystemExit("Config must contain an 'apps' array")
    return data


def resolve_guard(cli_guard: str | None) -> Path:
    candidates: list[Path] = []
    if cli_guard:
        candidates.append(Path(cli_guard).expanduser())
    env_guard = os.environ.get("APP_STORE_COMPLIANCE_GUARD")
    if env_guard:
        candidates.append(Path(env_guard).expanduser())
    here = Path(__file__).resolve()
    candidates.extend([
        here.parent.parent / "agent-os" / "hooks" / "app-store-compliance-guard.sh",
        Path.home() / ".claude" / "hooks" / "app-store-compliance-guard.sh",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("Compliance guard not found. Pass --guard or set APP_STORE_COMPLIANCE_GUARD.")


def resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(raw)))
    return ((base_dir / path) if not path.is_absolute() else path).resolve()


def parse_guard_findings(output: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in output.splitlines():
        match = FINDING_RE.match(line)
        if match:
            severity, finding_id, title = match.groups()
            current = {
                "id": finding_id,
                "severity": severity.lower(),
                "title": title.strip(),
                "fix": "",
                "classification": "UNREVIEWED",
                "classification_active": False,
                "classification_reason": None,
                "classification_expires": None,
                "classification_evidence": [],
            }
            findings.append(current)
            continue
        fix = FIX_RE.match(line)
        if fix and current is not None:
            current["fix"] = fix.group(1).strip()
    return findings


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def load_classifications(app: dict[str, Any], app_path: Path, config_dir: Path) -> tuple[dict[str, dict[str, Any]], str | None]:
    raw = app.get("classifications")
    if raw:
        path = resolve_path(str(raw), config_dir)
    else:
        path = app_path / ".app-store-compliance" / "findings.json"
    if not path.is_file():
        return {}, None

    data = load_json(path)
    entries = data.get("findings", [])
    if not isinstance(entries, list):
        raise SystemExit(f"'findings' must be an array in {path}")

    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            raise SystemExit(f"Every classification requires an id in {path}")
        fid = str(entry["id"])
        if fid in result:
            raise SystemExit(f"Duplicate classification for {fid} in {path}")
        result[fid] = entry
    return result, str(path)


def apply_classifications(findings: list[dict[str, Any]], classifications: dict[str, dict[str, Any]], today: dt.date) -> dict[str, int]:
    counts = {
        "false_positive": 0,
        "store_task": 0,
        "owner_legal": 0,
        "deferred": 0,
        "expired": 0,
        "invalid": 0,
        "unreviewed": 0,
    }

    for finding in findings:
        entry = classifications.get(finding["id"])
        if not entry:
            counts["unreviewed"] += 1
            continue

        classification = str(entry.get("classification", "")).upper()
        reason = str(entry.get("reason", "")).strip()
        expires = parse_date(entry.get("expires"))
        evidence = entry.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list):
            evidence = []

        valid = classification in CLASSIFICATIONS and bool(reason)
        if classification in {"FALSE_POSITIVE", "DEFERRED"} and expires is None:
            valid = False
        if expires and expires < today:
            finding["classification"] = "EXPIRED"
            finding["classification_reason"] = reason
            finding["classification_expires"] = expires.isoformat()
            finding["classification_evidence"] = evidence
            counts["expired"] += 1
            continue
        if not valid:
            finding["classification"] = "INVALID"
            finding["classification_reason"] = reason or "missing reason or required expiry"
            counts["invalid"] += 1
            continue

        finding["classification"] = classification
        finding["classification_active"] = True
        finding["classification_reason"] = reason
        finding["classification_expires"] = expires.isoformat() if expires else None
        finding["classification_evidence"] = evidence
        if classification == "FALSE_POSITIVE":
            counts["false_positive"] += 1
        elif classification == "STORE_TASK":
            counts["store_task"] += 1
        elif classification == "OWNER_LEGAL":
            counts["owner_legal"] += 1
        elif classification == "DEFERRED":
            counts["deferred"] += 1
    return counts


def finding_blocks_code(f: dict[str, Any]) -> bool:
    if f.get("classification_active") and f.get("classification") in {"FALSE_POSITIVE", "STORE_TASK", "OWNER_LEGAL", "DEFERRED"}:
        return False
    return f["severity"] in {"critical", "high", "medium"}


def summarize_effective(findings: list[dict[str, Any]]) -> dict[str, int]:
    effective = {"critical": 0, "high": 0, "medium": 0}
    for f in findings:
        if finding_blocks_code(f):
            effective[f["severity"]] += 1
    return effective


def summarize_owner_blockers(findings: list[dict[str, Any]]) -> dict[str, int]:
    out = {"store_task": 0, "owner_legal": 0, "deferred": 0}
    for f in findings:
        if not f.get("classification_active"):
            continue
        c = f.get("classification")
        if c == "STORE_TASK": out["store_task"] += 1
        elif c == "OWNER_LEGAL": out["owner_legal"] += 1
        elif c == "DEFERRED": out["deferred"] += 1
    return out


def evaluate_store_readiness(app: dict[str, Any]) -> dict[str, Any]:
    readiness = app.get("store_readiness", {})
    if not isinstance(readiness, dict) or not readiness:
        return {"status": "NOT_TRACKED", "complete": 0, "total": 0, "missing": []}
    missing = [str(k) for k, v in readiness.items() if v is not True]
    complete = len(readiness) - len(missing)
    return {
        "status": "PASS" if not missing else "OWNER_ACTION",
        "complete": complete,
        "total": len(readiness),
        "missing": missing,
    }


def app_verdict(effective: dict[str, int], owners: dict[str, int], readiness: dict[str, Any], error: str | None = None) -> str:
    if error:
        return "ERROR"
    if effective["critical"]:
        return "BLOCKED"
    if owners["store_task"] or owners["owner_legal"] or readiness["status"] == "OWNER_ACTION":
        return "OWNER_ACTION"
    if effective["high"] or owners["deferred"]:
        return "REVIEW"
    return "PASS"


def empty_error(name: str, path: str, message: str) -> dict[str, Any]:
    return {
        "name": name, "path": path, "raw_counts": {"critical": 0, "high": 0, "medium": 0},
        "effective_counts": {"critical": 0, "high": 0, "medium": 0}, "findings": [],
        "owner_blockers": {"store_task": 0, "owner_legal": 0, "deferred": 0},
        "store_readiness": {"status": "NOT_TRACKED", "complete": 0, "total": 0, "missing": []},
        "verdict": "ERROR", "error": message, "output": ""
    }


def run_app(guard: Path, app: dict[str, Any], base_dir: Path, today: dt.date) -> dict[str, Any]:
    name = str(app.get("name") or "Unnamed app")
    raw_path = str(app.get("path") or "").strip()
    if not raw_path:
        return empty_error(name, "", "missing app path")
    path = resolve_path(raw_path, base_dir)
    if not path.is_dir():
        return empty_error(name, str(path), "app path not found")

    env = os.environ.copy()
    env.pop("APP_STORE_GUARD_OK", None)
    proc = subprocess.run(["bash", str(guard), str(path)], text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env=env, check=False)
    output = proc.stdout or ""
    summary_match = SUMMARY_RE.search(output)
    if not summary_match:
        result = empty_error(name, str(path), f"guard produced no parseable summary (exit {proc.returncode})")
        result["output"] = output
        return result

    raw_counts = dict(zip(("critical", "high", "medium"), (int(v) for v in summary_match.groups())))
    findings = parse_guard_findings(output)
    classifications, classification_file = load_classifications(app, path, base_dir)
    classification_counts = apply_classifications(findings, classifications, today)
    effective = summarize_effective(findings)
    owners = summarize_owner_blockers(findings)
    readiness = evaluate_store_readiness(app)
    error = None

    # If parsing and guard totals disagree, do not silently trust a greener interpretation.
    parsed_raw = {sev: sum(1 for f in findings if f["severity"] == sev) for sev in ("critical", "high", "medium")}
    if parsed_raw != raw_counts:
        error = f"finding parse mismatch: guard={raw_counts} parsed={parsed_raw}"

    return {
        "name": name,
        "path": str(path),
        "platforms": app.get("platforms", []),
        "regions": app.get("regions", []),
        "classification_file": classification_file,
        "classification_counts": classification_counts,
        "raw_counts": raw_counts,
        "effective_counts": effective,
        "owner_blockers": owners,
        "store_readiness": readiness,
        "guard_exit": proc.returncode,
        "verdict": app_verdict(effective, owners, readiness, error),
        "error": error,
        "findings": findings,
        "output": output,
    }


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-") or "app"


def serializable_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {**summary, "results": [{k: v for k, v in r.items() if k != "output"} for r in summary["results"]]}


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# {summary['portfolio']} compliance report",
        "",
        f"Generated: {summary['generated_at_utc']}",
        f"Final verdict: **{summary['overall_verdict']}**",
        "",
        "| App | Verdict | Critical | High | Medium | Store/account |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for r in summary["results"]:
        e = r["effective_counts"]
        sr = r["store_readiness"]
        store = sr["status"] if sr["total"] == 0 else f"{sr['status']} ({sr['complete']}/{sr['total']})"
        lines.append(f"| {r['name']} | {r['verdict']} | {e['critical']} | {e['high']} | {e['medium']} | {store} |")
    lines += ["", "## Findings", ""]
    for r in summary["results"]:
        lines.append(f"### {r['name']}")
        if r.get("error"):
            lines.append(f"- ERROR: {r['error']}")
        if not r["findings"]:
            lines.append("- No guard findings.")
        for f in r["findings"]:
            classification = f["classification"]
            expiry = f"; expires {f['classification_expires']}" if f.get("classification_expires") else ""
            lines.append(f"- **{f['severity'].upper()} {f['id']}**: {f['title']}  ")
            lines.append(f"  Classification: `{classification}`{expiry}.  ")
            if f.get("classification_reason"):
                lines.append(f"  Reason: {f['classification_reason']}  ")
            if f.get("fix"):
                lines.append(f"  Fix: {f['fix']}")
        missing = r["store_readiness"].get("missing", [])
        if missing:
            lines.append("- Store/account actions: " + ", ".join(missing))
        lines.append("")
    lines += [
        "## Interpretation",
        "",
        "- `FALSE_POSITIVE` only stops blocking while its documented waiver is valid and unexpired.",
        "- `STORE_TASK` and `OWNER_LEGAL` remain visible owner actions and prevent a final PASS.",
        "- `DEFERRED` is time-bounded and keeps the portfolio in REVIEW, not PASS.",
        "- Expired or invalid classifications become active findings again.",
    ]
    return "\n".join(lines) + "\n"


def build_sarif(summary: dict[str, Any]) -> dict[str, Any]:
    results = []
    rules: dict[str, dict[str, Any]] = {}
    level_map = {"critical": "error", "high": "warning", "medium": "note"}
    for app in summary["results"]:
        for f in app["findings"]:
            if f.get("classification_active") and f.get("classification") == "FALSE_POSITIVE":
                continue
            rid = f["id"]
            rules.setdefault(rid, {"id": rid, "name": rid, "shortDescription": {"text": f["title"]}})
            message = f"{app['name']}: {f['title']}"
            if f.get("classification") not in {"UNREVIEWED", "REAL"}:
                message += f" [{f['classification']}]"
            results.append({"ruleId": rid, "level": level_map[f["severity"]], "message": {"text": message}})
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "AEGIS App Store Compliance", "rules": list(rules.values())}},
            "results": results,
        }],
    }


def write_evidence(evidence_dir: Path, summary: dict[str, Any], sarif_path: Path | None = None) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for result in summary["results"]:
        slug = safe_filename(result["name"])
        (evidence_dir / f"{slug}-guard.txt").write_text(result.get("output", ""), encoding="utf-8")
        (evidence_dir / f"{slug}-findings.json").write_text(
            json.dumps(result.get("findings", []), indent=2) + "\n", encoding="utf-8")
    serial = serializable_summary(summary)
    (evidence_dir / "portfolio-summary.json").write_text(json.dumps(serial, indent=2) + "\n", encoding="utf-8")
    (evidence_dir / "SUMMARY.md").write_text(render_markdown(summary), encoding="utf-8")
    target = sarif_path or (evidence_dir / "compliance.sarif")
    target.write_text(json.dumps(build_sarif(summary), indent=2) + "\n", encoding="utf-8")


def print_table(results: list[dict[str, Any]]) -> None:
    headers = ("APP", "VERDICT", "CRIT", "HIGH", "MED", "OWNER", "STORE")
    rows = []
    for r in results:
        e, o, s = r["effective_counts"], r["owner_blockers"], r["store_readiness"]
        rows.append((r["name"], r["verdict"], str(e["critical"]), str(e["high"]), str(e["medium"]),
                     str(o["store_task"] + o["owner_legal"]), s["status"]))
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]
    def line(row: tuple[str, ...]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(row)))
    print(line(headers)); print(line(tuple("-" * w for w in widths)))
    for row in rows: print(line(row))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit multiple iOS/Android apps with evidence and release governance")
    parser.add_argument("--config", required=True, help="portfolio JSON configuration")
    parser.add_argument("--guard", help="path to app-store-compliance-guard.sh")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--evidence-dir", help="write release evidence bundle")
    parser.add_argument("--sarif", help="write SARIF output to this path")
    parser.add_argument("--today", help="override date for deterministic testing (YYYY-MM-DD)")
    parser.add_argument("--fail-on", choices=("critical", "high", "owner", "never"), default="critical")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    guard = resolve_guard(args.guard)
    today = parse_date(args.today) if args.today else dt.datetime.now(dt.timezone.utc).date()
    if today is None:
        raise SystemExit("--today must be YYYY-MM-DD")
    results = [run_app(guard, app, config_path.parent, today) for app in config["apps"]]

    totals = {
        "critical": sum(r["effective_counts"]["critical"] for r in results),
        "high": sum(r["effective_counts"]["high"] for r in results),
        "medium": sum(r["effective_counts"]["medium"] for r in results),
        "owner_actions": sum(r["owner_blockers"]["store_task"] + r["owner_blockers"]["owner_legal"] for r in results),
        "deferred": sum(r["owner_blockers"]["deferred"] for r in results),
        "store_readiness_missing": sum(len(r["store_readiness"].get("missing", [])) for r in results),
        "errors": sum(1 for r in results if r["verdict"] == "ERROR"),
    }
    overall = (
        "ERROR" if totals["errors"] else
        "BLOCKED" if totals["critical"] else
        "OWNER_ACTION" if totals["owner_actions"] or totals["store_readiness_missing"] else
        "REVIEW" if totals["high"] or totals["deferred"] else
        "PASS"
    )
    summary = {
        "schema_version": 2,
        "portfolio": config.get("portfolio_name", "Mobile app portfolio"),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "evaluation_date": today.isoformat(),
        "guard": str(guard),
        "overall_verdict": overall,
        "totals": totals,
        "results": results,
    }

    sarif_path = Path(args.sarif).expanduser().resolve() if args.sarif else None
    if args.evidence_dir:
        write_evidence(Path(args.evidence_dir).expanduser().resolve(), summary, sarif_path)
    elif sarif_path:
        sarif_path.parent.mkdir(parents=True, exist_ok=True)
        sarif_path.write_text(json.dumps(build_sarif(summary), indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(serializable_summary(summary), indent=2))
    else:
        print(f"== AEGIS Portfolio Compliance Audit ==\nPortfolio. {summary['portfolio']}\n")
        print_table(results)
        print(f"\nOverall. {overall}  critical={totals['critical']} high={totals['high']} medium={totals['medium']} owner_actions={totals['owner_actions']} deferred={totals['deferred']} store_missing={totals['store_readiness_missing']} errors={totals['errors']}")
        for r in results:
            if r.get("error"): print(f"ERROR {r['name']}: {r['error']}")

    if args.fail_on == "never": return 0
    if totals["errors"]: return 3
    if totals["critical"]: return 2
    if args.fail_on == "high" and totals["high"]: return 1
    if args.fail_on == "owner" and (totals["owner_actions"] or totals["store_readiness_missing"]): return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
