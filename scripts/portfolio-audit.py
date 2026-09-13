#!/usr/bin/env python3
"""Run the App Store Compliance Guard across a portfolio of mobile apps.

The portfolio runner does not replace the underlying guard. It orchestrates it,
keeps each app's raw evidence, and produces one release-level summary.
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


def load_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Config not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")

    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise SystemExit("Config must be an object containing an 'apps' array")
    return data


def resolve_guard(cli_guard: str | None) -> Path:
    candidates: list[Path] = []
    if cli_guard:
        candidates.append(Path(cli_guard).expanduser())
    env_guard = os.environ.get("APP_STORE_COMPLIANCE_GUARD")
    if env_guard:
        candidates.append(Path(env_guard).expanduser())

    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parent.parent / "agent-os" / "hooks" / "app-store-compliance-guard.sh",
            Path.home() / ".claude" / "hooks" / "app-store-compliance-guard.sh",
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit(
        "Compliance guard not found. Pass --guard or set APP_STORE_COMPLIANCE_GUARD."
    )


def verdict(critical: int, high: int, error: str | None = None) -> str:
    if error:
        return "ERROR"
    if critical:
        return "BLOCKED"
    if high:
        return "REVIEW"
    return "PASS"


def run_app(guard: Path, app: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    name = str(app.get("name") or "Unnamed app")
    raw_path = str(app.get("path") or "").strip()
    if not raw_path:
        return {"name": name, "path": "", "critical": 0, "high": 0, "medium": 0,
                "verdict": "ERROR", "error": "missing app path", "output": ""}

    path = Path(os.path.expandvars(os.path.expanduser(raw_path)))
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()

    if not path.is_dir():
        return {"name": name, "path": str(path), "critical": 0, "high": 0, "medium": 0,
                "verdict": "ERROR", "error": "app path not found", "output": ""}

    env = os.environ.copy()
    # Portfolio audits must report the true guard result. Never inherit a local bypass.
    env.pop("APP_STORE_GUARD_OK", None)

    proc = subprocess.run(
        ["bash", str(guard), str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        check=False,
    )
    output = proc.stdout or ""
    match = SUMMARY_RE.search(output)
    if not match:
        return {
            "name": name,
            "path": str(path),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "verdict": "ERROR",
            "error": f"guard produced no parseable summary (exit {proc.returncode})",
            "output": output,
        }

    critical, high, medium = (int(v) for v in match.groups())
    return {
        "name": name,
        "path": str(path),
        "platforms": app.get("platforms", []),
        "regions": app.get("regions", []),
        "critical": critical,
        "high": high,
        "medium": medium,
        "guard_exit": proc.returncode,
        "verdict": verdict(critical, high),
        "error": None,
        "output": output,
    }


def print_table(results: list[dict[str, Any]]) -> None:
    headers = ("APP", "VERDICT", "CRIT", "HIGH", "MED")
    rows = [
        (r["name"], r["verdict"], str(r["critical"]), str(r["high"]), str(r["medium"]))
        for r in results
    ]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]

    def line(row: tuple[str, ...]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(row)))

    print(line(headers))
    print(line(tuple("-" * w for w in widths)))
    for row in rows:
        print(line(row))


def safe_filename(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-")
    return value or "app"


def write_evidence(evidence_dir: Path, summary: dict[str, Any]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for result in summary["results"]:
        (evidence_dir / f"{safe_filename(result['name'])}.txt").write_text(
            result.get("output", ""), encoding="utf-8"
        )

    serializable = {
        **summary,
        "results": [{k: v for k, v in r.items() if k != "output"} for r in summary["results"]],
    }
    (evidence_dir / "portfolio-summary.json").write_text(
        json.dumps(serializable, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit multiple iOS/Android apps with one command")
    parser.add_argument("--config", required=True, help="portfolio JSON configuration")
    parser.add_argument("--guard", help="path to app-store-compliance-guard.sh")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--evidence-dir", help="write raw per-app output and summary JSON")
    parser.add_argument(
        "--fail-on",
        choices=("critical", "high", "never"),
        default="critical",
        help="process exit threshold (default: critical)",
    )
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)
    guard = resolve_guard(args.guard)
    results = [run_app(guard, app, config_path.parent) for app in config["apps"]]

    totals = {
        "critical": sum(r["critical"] for r in results),
        "high": sum(r["high"] for r in results),
        "medium": sum(r["medium"] for r in results),
        "errors": sum(1 for r in results if r["verdict"] == "ERROR"),
    }
    overall = (
        "ERROR" if totals["errors"] else
        "BLOCKED" if totals["critical"] else
        "REVIEW" if totals["high"] else
        "PASS"
    )
    summary = {
        "schema_version": 1,
        "portfolio": config.get("portfolio_name", "Mobile app portfolio"),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "guard": str(guard),
        "overall_verdict": overall,
        "totals": totals,
        "results": results,
    }

    if args.evidence_dir:
        write_evidence(Path(args.evidence_dir).expanduser().resolve(), summary)

    if args.json:
        printable = {
            **summary,
            "results": [{k: v for k, v in r.items() if k != "output"} for r in results],
        }
        print(json.dumps(printable, indent=2))
    else:
        print(f"== AEGIS Portfolio Compliance Audit ==\nPortfolio. {summary['portfolio']}\n")
        print_table(results)
        print(
            f"\nOverall. {overall}  critical={totals['critical']} high={totals['high']} "
            f"medium={totals['medium']} errors={totals['errors']}"
        )
        for r in results:
            if r.get("error"):
                print(f"ERROR {r['name']}: {r['error']}")

    if args.fail_on == "never":
        return 0
    if totals["errors"]:
        return 3
    if totals["critical"]:
        return 2
    if args.fail_on == "high" and totals["high"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
