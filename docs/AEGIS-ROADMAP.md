# AEGIS App Store Compliance Roadmap

Status: **AEGIS release-governance redesign implemented.**

The upstream project remains the policy and rule foundation. AEGIS enhancements improve release governance without weakening or silently changing upstream compliance rules.

## Delivered

### 1. Portfolio compliance

Implemented in `scripts/portfolio-audit.py`.

- multi-app configuration
- per-app guard execution
- consolidated Critical / High / Medium counts
- portfolio verdict
- JSON output
- configurable CI thresholds
- inherited guard bypass stripped from child runs
- test coverage in `scripts/portfolio-audit-test.sh`

### 2. Evidence and classification

Implemented.

Each parsed finding carries:

- finding id
- severity
- title
- recommended fix
- classification
- classification reason
- classification expiry
- human evidence references

Supported classifications:

- `REAL`
- `FALSE_POSITIVE`
- `STORE_TASK`
- `OWNER_LEGAL`
- `DEFERRED`

False-positive and deferred classifications must expire. Invalid or expired classifications automatically become active findings again.

### 3. Region metadata

Portfolio configuration records intended release regions per app. Existing regulatory monitors remain the source of region-specific legal deadlines. AEGIS does not silently convert an unreviewed policy change into a blocking rule.

### 4. Release evidence bundle

Implemented with `--evidence-dir`.

Output includes:

```text
release-evidence/
  SUMMARY.md
  portfolio-summary.json
  compliance.sarif
  <App>-guard.txt
  <App>-findings.json
```

The bundle distinguishes raw scanner output from reviewed human classifications.

### 5. CI and SARIF

Implemented.

- JSON output
- SARIF 2.1.0 output
- CI threshold controls
- portfolio test suite wired into repository CI
- active false positives omitted from SARIF annotations while remaining in the evidence record

### 6. Store and account readiness

Implemented as `store_readiness` in the portfolio configuration.

It can track, per app:

- Apple Developer Program status
- Apple agreements and attachments
- App Store Connect app record
- app privacy answers
- age rating
- encryption declaration
- review/demo account
- Google developer verification
- package registration
- organisation / D-U-N-S requirement where applicable
- Data Safety
- health/location declarations
- subscription products
- RevenueCat production configuration
- signed builds
- physical-device QA

Any tracked item not set to literal `true` remains an owner action and prevents a final PASS.

### 7. Metadata validation

Existing `scripts/metadata-audit.py` remains the dedicated metadata engine and continues to cover store-copy risks. It is intentionally not duplicated inside the portfolio orchestrator.

### 8. Policy-source trust model

Existing citation verification and policy monitors remain authoritative. Source priority is:

1. legislation / regulator / Apple / Google primary source
2. official developer documentation
3. official support pages
4. reliable secondary reporting
5. community reports only as implementation evidence, never sole authority for a rule

### 9. Automatic policy freshness

Existing Apple, Google, privacy, AI-policy, security and regulatory monitors continue to provide freshness checks. Policy changes enter a review queue rather than silently becoming new blocking rules.

### 10. Release readiness scorecard

Implemented in the portfolio table and generated `SUMMARY.md`.

Verdicts:

```text
PASS
REVIEW
OWNER_ACTION
BLOCKED
ERROR
```

`PASS` is only possible when there is no active Critical or High code finding, no owner/store/legal blocker, no active deferral, and every tracked store-readiness item is complete.

## Safety invariants

1. Do not weaken upstream rules to obtain a green result.
2. Do not hide uncertainty.
3. Automated checks and human evidence are different things.
4. A false positive must be evidenced, classified, and time-bounded.
5. Privacy declarations must match runtime behaviour.
6. Minimise permissions rather than merely documenting unnecessary access.
7. A local `APP_STORE_GUARD_OK` setting must not silently green a portfolio audit.
8. Owner/store/legal work must stay visible even when it is not a code defect.
9. Expired waivers become active automatically.
10. Preserve the upstream licence and attribution.
11. Useful product capability must not be removed merely to silence a scanner.
12. A parser mismatch between raw guard counts and parsed findings fails closed as an audit error.
