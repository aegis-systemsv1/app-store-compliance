# AEGIS Portfolio Audit

The portfolio audit runs the existing App Store Compliance Guard across multiple apps and produces one release-level result.

It is designed for teams or owners managing more than one iOS or Android product. It does **not** weaken or replace the underlying guard.

## Why this exists

Running each app manually makes it easy to lose track of which product is actually ready to ship. The portfolio runner gives you one view of:

- critical rejection blockers
- high-priority review items
- medium warnings
- missing or broken app paths
- raw evidence for each app
- a machine-readable summary for CI or release governance

## Configure your apps

Copy the template:

```bash
cp templates/portfolio.example.json portfolio.json
```

Edit each local app path. Paths may use `~` and environment variables.

Example:

```json
{
  "portfolio_name": "My Apps",
  "apps": [
    {
      "name": "Example App",
      "path": "~/ExampleApp",
      "platforms": ["ios", "android"],
      "regions": ["AU", "US"]
    }
  ]
}
```

`platforms` and `regions` are recorded as portfolio metadata. The underlying guard still detects the actual project platforms from the source tree.

## Run the audit

From this repository:

```bash
python3 scripts/portfolio-audit.py --config portfolio.json
```

The runner automatically finds the repository guard. If the skill is installed separately, you can point at it explicitly:

```bash
python3 scripts/portfolio-audit.py \
  --config portfolio.json \
  --guard ~/.claude/hooks/app-store-compliance-guard.sh
```

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `PASS` | No critical or high findings from the code guard |
| `REVIEW` | No critical findings, but one or more high findings require review |
| `BLOCKED` | At least one critical rejection risk exists |
| `ERROR` | An app path is missing or the guard did not produce a valid result |

A `PASS` is a code-guard result only. Store-console declarations, signed-device QA, legal/account agreements and other human validation may still remain.

## Evidence bundle

To keep the raw audit output for every app:

```bash
python3 scripts/portfolio-audit.py \
  --config portfolio.json \
  --evidence-dir compliance-evidence
```

This writes:

```text
compliance-evidence/
  Example-App.txt
  portfolio-summary.json
```

The text files contain the exact guard output. `portfolio-summary.json` contains the consolidated counts and verdicts without duplicating the raw logs.

Do not commit evidence bundles if they expose local paths or other information you do not want in source control.

## JSON / CI mode

```bash
python3 scripts/portfolio-audit.py --config portfolio.json --json
```

Exit behavior defaults to the same safety principle as the guard:

- exit `2` when any critical finding exists
- exit `3` when an app could not be audited correctly
- exit `0` when there are no criticals

To make high findings fail CI too:

```bash
python3 scripts/portfolio-audit.py --config portfolio.json --fail-on high
```

To collect results without failing the calling process:

```bash
python3 scripts/portfolio-audit.py --config portfolio.json --fail-on never
```

`--fail-on never` changes only the portfolio runner's process exit. It does not hide findings or set the underlying guard bypass.

## Safety rule

The runner deliberately removes `APP_STORE_GUARD_OK` from the child process environment. A machine that previously used a local guard override therefore cannot silently turn a portfolio audit green.

False positives should be investigated and classified. Do not delete useful product capability merely to make a scan quiet.

## Recommended AEGIS release flow

1. Run the portfolio audit.
2. Resolve all criticals.
3. Investigate every high finding and record whether it is a true issue, false positive, store-console task or owner action.
4. Complete account/store readiness and regulatory deadline checks.
5. Run real-device QA.
6. Capture the evidence bundle for the release candidate.
7. Submit only when the product, store, account and proof gates are all clear.
