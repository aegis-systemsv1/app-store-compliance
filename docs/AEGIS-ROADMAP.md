# AEGIS App Store Compliance Roadmap

Status: proposed enhancement plan for the AEGIS-maintained distribution.

The upstream project remains the policy and rule foundation. AEGIS enhancements should improve release governance without weakening or silently changing upstream compliance rules.

## Phase 1 — Portfolio compliance

Goal: audit several mobile apps as one release portfolio.

Deliverables:

- `scripts/portfolio-audit.py`
- YAML/JSON portfolio configuration
- per-app guard invocation
- consolidated Critical / High / Medium findings
- consolidated owner/store/legal blockers
- exit non-zero if any app has a critical finding
- Markdown and JSON reports

Example:

```yaml
apps:
  - name: Selayra
    path: ~/SELAYRA
    regions: [AU, US, EU]
  - name: DwellVerify
    path: ~/DwellVerify
    regions: [AU, US, EU]
  - name: Dishly
    path: ~/dishly
    regions: [AU, US, EU]
  - name: Kintra
    path: ~/KINTRA
    regions: [AU, US, EU]
```

## Phase 2 — Evidence and classification

Goal: every finding carries evidence instead of only a regex result.

Add:

- exact matched file
- exact matched line/string where safe
- scanner that produced the finding
- classification: `REAL`, `FALSE_POSITIVE`, `STORE_TASK`, `OWNER_LEGAL`, `DEFERRED`
- reviewer note
- proof/evidence reference
- completion date

Persist classifications in a repository-local file so known false positives do not need to be rediscovered on every audit.

Suggested format:

```yaml
findings:
  BOTH-PLACEHOLDER:
    classification: FALSE_POSITIVE
    reason: Open Collective URL in package-lock.json
    reviewed_at: 2026-09-13
    expires: 2027-03-13
```

Suppressions must expire. A stale waiver should become visible again automatically.

## Phase 3 — Region profiles

Goal: only surface regulatory requirements relevant to where the app will actually ship.

Profiles:

- Australia
- United States
- European Union
- United Kingdom
- Canada
- Singapore
- Brazil
- South Korea
- India
- China

A project can select one or more regions. Global Apple/Google requirements always remain active.

## Phase 4 — Release evidence bundle

Goal: generate a release-signoff package.

Output:

```text
release-evidence/
  SUMMARY.md
  compliance.json
  privacy-data-map.md
  store-readiness.md
  account-readiness.md
  regulatory-deadlines.md
  physical-device-qa.md
  signed-builds.md
  unresolved-findings.md
```

The bundle must clearly distinguish automated proof from human assertions.

## Phase 5 — CI integration

Goal: turn compliance failures into normal CI feedback.

Add:

- JSON output
- SARIF output for GitHub code scanning annotations
- GitHub Actions workflow example
- PR summary comment
- changed-files/diff-aware mode
- baseline comparison against main

Rules:

- new Critical findings fail CI
- resolved Critical findings are highlighted
- existing accepted false positives remain visible but do not fail CI until their waiver expires

## Phase 6 — Store readiness tracker

Goal: cover the work source scanners cannot prove.

Track:

- Apple Developer Program status
- Apple agreements/attachments
- App Store Connect app record
- App privacy answers
- age rating
- encryption declaration
- review/demo account
- Google Play developer verification
- package registration
- organisation / D-U-N-S requirement
- Data Safety form
- Health declaration
- location declaration
- subscription products
- RevenueCat production configuration
- signed builds
- physical-device QA

## Phase 7 — Metadata and screenshot validation

Extend the metadata engine to verify:

- app name limits
- subtitle limits
- keyword stuffing
- future-functionality claims
- unsupported claims
- platform references
- screenshot dimensions
- required device families
- screenshots that show the app in use rather than only splash/login screens
- consistent privacy/subscription wording

## Phase 8 — Policy-source trust model

Goal: make source quality explicit.

Priority:

1. legislation / regulator / Apple / Google primary source
2. official developer documentation
3. official support pages
4. reliable secondary reporting
5. community reports only as implementation evidence, never sole authority for a rule

Each rule should store source type and last verification date.

## Phase 9 — Automatic policy freshness

Add scheduled monitoring that:

- checks upstream Apple/Google policy pages
- re-verifies citation integrity
- detects changed policy text where feasible
- produces a review queue rather than silently changing compliance rules

No external policy change becomes an enforced blocking rule without review and source evidence.

## Phase 10 — Release readiness scorecard

Human-friendly final output:

```text
CODE COMPLIANCE        PASS
PRIVACY                PASS
APPLE STORE FORMS      PASS
GOOGLE STORE FORMS     PASS
ACCOUNT READINESS      PASS
SIGNED BUILDS          PASS
PHYSICAL QA            PASS
REGULATORY DEADLINES   PASS

FINAL VERDICT          READY TO SUBMIT
```

The scorecard must never show READY while a critical finding remains.

## Design principles

1. Do not weaken upstream rules to obtain a green result.
2. Do not hide uncertainty.
3. Automated checks and human evidence are different things.
4. A false positive must be evidenced, classified, and time-bounded.
5. Privacy declarations must match runtime behaviour.
6. Minimise permissions rather than merely documenting unnecessary access.
7. No AI agent may bypass critical blockers without an explicit human override.
8. Overrides must be visible in the final report.
9. Preserve the upstream licence and attribution.
10. Store policy changes require re-verification before release.
