# AEGIS Portfolio Audit

The AEGIS portfolio audit runs the existing App Store Compliance Guard across multiple apps and produces one release-level result without weakening the underlying rules.

It adds the governance layer the raw scanner cannot provide on its own: reviewed classifications, expiry dates, owner/store actions, store readiness, evidence bundles and SARIF output.

## What it tracks

For every app the audit records:

- raw Critical / High / Medium guard findings
- effective findings after valid human classification
- false positives with evidence and expiry
- owner/legal actions
- store-console actions
- deferred items with expiry
- store and account readiness
- region metadata
- raw guard output
- machine-readable JSON
- SARIF for CI/code-scanning systems
- a human-readable release summary

## Configure your portfolio

Copy the template:

```bash
cp templates/portfolio.example.json portfolio.json
```

Paths may use `~` and environment variables.

```json
{
  "portfolio_name": "My Apps",
  "apps": [
    {
      "name": "Example App",
      "path": "~/ExampleApp",
      "platforms": ["ios", "android"],
      "regions": ["AU", "US"],
      "store_readiness": {
        "apple_developer_program": true,
        "apple_agreements": true,
        "apple_privacy_answers": false,
        "google_developer_verification": true,
        "google_data_safety": false,
        "physical_device_qa": false
      }
    }
  ]
}
```

An empty `store_readiness` object means the release checklist is not yet being tracked. Once keys are added, every value other than literal `true` remains an owner action.

## Run

```bash
python3 scripts/portfolio-audit.py --config portfolio.json
```

To use the installed Claude hook explicitly:

```bash
python3 scripts/portfolio-audit.py \
  --config portfolio.json \
  --guard ~/.claude/hooks/app-store-compliance-guard.sh
```

## Finding classifications

Each app may keep a repository-local file at:

```text
.app-store-compliance/findings.json
```

or specify a different path with `"classifications": "..."` in the portfolio config.

Copy the example:

```bash
mkdir -p .app-store-compliance
cp templates/findings-classification.example.json .app-store-compliance/findings.json
```

Supported classifications:

| Classification | Effect |
| --- | --- |
| `REAL` | Finding remains active at its original severity |
| `FALSE_POSITIVE` | Does not block while the documented classification is valid and unexpired |
| `STORE_TASK` | Removed from code-defect counts but remains an owner/store action and prevents PASS |
| `OWNER_LEGAL` | Removed from code-defect counts but remains an owner/legal action and prevents PASS |
| `DEFERRED` | Time-bounded deferral; prevents PASS and keeps the app in REVIEW |

`FALSE_POSITIVE` and `DEFERRED` **must** have a valid `expires` date. Every classification requires a reason. Expired or invalid classifications become active findings again.

Example:

```json
{
  "schema_version": 1,
  "findings": [
    {
      "id": "BOTH-PLACEHOLDER",
      "classification": "FALSE_POSITIVE",
      "reason": "Only a dependency funding URL matched; no user-visible placeholder content exists.",
      "reviewed_at": "2026-09-13",
      "expires": "2027-03-13",
      "evidence": ["package-lock.json"]
    }
  ]
}
```

This is deliberately not a silent suppression system. Every waived item stays in the report.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `PASS` | No active critical/high findings, no owner/store blockers, no deferred items, and tracked store readiness is complete |
| `REVIEW` | High findings or deferred items remain |
| `OWNER_ACTION` | Store/account/legal work remains even though code may be clean |
| `BLOCKED` | At least one active critical finding remains |
| `ERROR` | The app could not be audited safely |

The system will not report PASS merely because a regex was suppressed.

## Evidence bundle

```bash
python3 scripts/portfolio-audit.py \
  --config portfolio.json \
  --evidence-dir compliance-evidence
```

Output:

```text
compliance-evidence/
  SUMMARY.md
  portfolio-summary.json
  compliance.sarif
  Example-App-guard.txt
  Example-App-findings.json
```

`SUMMARY.md` is the human release scorecard. `portfolio-summary.json` is the structured evidence record. `compliance.sarif` can be consumed by systems that understand SARIF 2.1.0.

Do not commit evidence bundles if they contain local machine paths or information you do not want in source control.

## JSON and CI

```bash
python3 scripts/portfolio-audit.py --config portfolio.json --json
```

Exit codes:

- `0`: threshold not breached
- `1`: high threshold breached when `--fail-on high`
- `2`: active critical finding
- `3`: audit error
- `4`: owner/store threshold breached when `--fail-on owner`

Examples:

```bash
python3 scripts/portfolio-audit.py --config portfolio.json --fail-on high
python3 scripts/portfolio-audit.py --config portfolio.json --fail-on owner
python3 scripts/portfolio-audit.py --config portfolio.json --fail-on never
```

`--fail-on never` changes process exit only. It never hides a finding and never sets `APP_STORE_GUARD_OK`.

## SARIF only

```bash
python3 scripts/portfolio-audit.py \
  --config portfolio.json \
  --sarif compliance.sarif
```

Valid active false positives are omitted from SARIF annotations but remain present in the JSON and Markdown evidence bundle. Owner/store/deferred findings remain visible.

## Safety properties

The runner deliberately strips inherited `APP_STORE_GUARD_OK` before launching the underlying guard. A machine that once used a local override therefore cannot silently green a portfolio audit.

The audit also fails closed if the parsed finding list disagrees with the guard's own summary counts. This prevents a parser change from producing a falsely cleaner result.

Useful app capability must not be removed merely to silence a scanner. Investigate the match, fix a real problem, or classify the evidence correctly.

## Recommended release flow

1. Run the portfolio audit.
2. Fix active Critical findings.
3. Review High findings.
4. Record any proven false positive with evidence and an expiry date.
5. Complete owner/legal and store-console actions.
6. Complete store/account readiness.
7. Run physical-device QA and signed-build validation.
8. Generate the evidence bundle.
9. Submit only when the final portfolio verdict is PASS.
