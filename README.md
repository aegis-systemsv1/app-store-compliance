<div align="center">

# AEGIS App Store Compliance

### Pre-submission safety checks for iOS and Android

Catch rejection risks before Apple or Google does.

[![Apple](https://img.shields.io/badge/Apple-App%20Store-black?logo=apple)](https://developer.apple.com/app-store/review/guidelines/)
[![Google Play](https://img.shields.io/badge/Google-Play-414141?logo=googleplay)](https://play.google/developer-content-policy/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-ready-5A67D8)](#install-for-claude-code)
[![AEGIS](https://img.shields.io/badge/AEGIS-enhanced-0A84FF)](#what-aegis-adds)
[![License](https://img.shields.io/badge/license-OpenRoots%20ORA%202.3-blue)](LICENSE)

**Audit. Explain. Block. Prove.**

</div>

---

## What this is

AEGIS App Store Compliance is an enhanced distribution of the original **App Store Compliance Playbook** by [mjmirza](https://github.com/mjmirza/app-store-compliance).

It is designed to answer one question before every release:

> **What can still get this app rejected, delayed, or blocked from submission?**

It combines:

- source-code scanning
- Apple App Store policy checks
- Google Play policy checks
- privacy and permission checks
- subscription and payment checks
- metadata checks
- account/program readiness checks
- regulatory deadline tracking
- citation verification
- pre-submission blocking hooks for AI coding agents

The original project remains the foundation. AEGIS adds a clearer operating model, portfolio readiness, evidence-driven closeout, and a path toward repeatable release governance across multiple apps.

---

## Why AEGIS exists

A mobile app can be technically finished and still be nowhere near ready to submit.

Common blockers include:

- missing privacy manifests
- incorrect App Store privacy answers
- Google Data Safety mismatches
- unnecessary permissions
- weak account deletion
- unfinished subscription flows
- invalid deep links
- staging URLs in release builds
- developer account agreements not accepted
- package names not registered
- age-rating forms not completed
- store billing requirements missed
- regulatory deadlines that code scanning cannot see

AEGIS treats those as part of engineering, not paperwork left for the last day.

---

## What AEGIS adds

The upstream playbook is already strong. This redesign adds a more operational release model around it.

### 1. Portfolio mode

Track several apps at once instead of auditing one repository in isolation.

Target output:

| App | Critical | High | Store tasks | Owner tasks | Submission state |
|---|---:|---:|---:|---:|---|
| App A | 0 | 2 | 3 | 1 | HOLD |
| App B | 0 | 0 | 1 | 0 | READY |

### 2. Evidence-first findings

Every finding should identify:

- severity
- rule ID
- exact file/string that triggered it
- whether it is REAL, FALSE POSITIVE, STORE TASK, OWNER/LEGAL TASK, or DEFERRED
- concrete fix
- verification evidence

### 3. Release-gate model

AEGIS separates readiness into five gates:

1. **Code** — the build itself is compliant
2. **Privacy** — declarations match runtime behaviour
3. **Store** — App Store Connect / Play Console are complete
4. **Account** — developer accounts, agreements and registrations are valid
5. **Proof** — signed builds and physical-device QA are complete

An app is not considered ready until every applicable gate is green.

### 4. Human validation queue

Some checks cannot be proven from source code. AEGIS keeps these visible instead of pretending they are complete.

Examples:

- Apple Developer Program membership status
- D-U-N-S / organisation account state
- App Store agreements
- Play package registration
- production RevenueCat credentials
- final age rating answers
- physical-device QA

### 5. Safer AI-agent behaviour

The guard is designed to stop an AI coding agent from confidently saying an app is ready while a critical rejection risk still exists.

---

## Fast start

Run a one-time audit:

```bash
bash agent-os/hooks/app-store-compliance-guard.sh /path/to/app
```

Run citation verification:

```bash
python3 scripts/verify-citations.py --files docs/ data/ references/ scripts/
```

Run the release audit:

```bash
python3 scripts/release-audit.py /path/to/app
```

Run supporting audits:

```bash
python3 scripts/accessibility-audit.py /path/to/app
python3 scripts/monitor-security.py --dir /path/to/app
python3 scripts/monitor-privacy.py --dir /path/to/app
python3 scripts/monitor-android.py --dir /path/to/app
python3 scripts/monitor-ai-policy.py --dir /path/to/app
python3 scripts/monitor-regulatory.py --project /path/to/app
```

---

## Install for Claude Code

Clone the repository:

```bash
git clone https://github.com/aegis-systemsv1/app-store-compliance.git ~/repositories/app-store-compliance
```

Install the skill:

```bash
mkdir -p ~/.claude/skills/app-store-compliance
cp agent-os/skill/SKILL.md ~/.claude/skills/app-store-compliance/
cp -R docs data references templates scripts ~/.claude/skills/app-store-compliance/
```

Install the guard:

```bash
mkdir -p ~/.claude/hooks
cp agent-os/hooks/app-store-compliance-guard.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/app-store-compliance-guard.sh
```

Then register it as a Claude Code `PreToolUse` hook for Bash commands so release/submission commands are checked before they run.

The guard is intended to catch submission paths including:

- `fastlane`
- `eas submit`
- `gradle bundleRelease`
- `xcodebuild archive`
- `xcrun altool`
- `bundletool`

---

## Recommended standing instruction for AI agents

```text
For any iOS or Android work, follow the current Apple App Store Review Guidelines and Google Play policies.

Before any release or submission:
- run the App Store Compliance audit
- identify the exact source evidence for every finding
- classify each finding as REAL, FALSE POSITIVE, STORE TASK, OWNER/LEGAL TASK, or DEFERRED
- never claim an app is ready while a critical rejection risk remains
- never bypass the guard merely to obtain a green result
- ensure privacy declarations match actual runtime behaviour
- keep account/program readiness separate from code readiness
- require signed-build and physical-device proof before final submission readiness
```

---

## Submission readiness model

AEGIS recommends maintaining this state for every app:

```text
CODE COMPLIANCE:       PASS / FAIL
PRIVACY POLICY:        READY / BLOCKED
APPLE PRIVACY LABELS:  READY / BLOCKED
GOOGLE DATA SAFETY:    READY / BLOCKED
AGE RATING:            READY / BLOCKED
BILLING:               READY / BLOCKED
ACCOUNT READINESS:     READY / BLOCKED
SIGNED BUILD:          READY / BLOCKED
PHYSICAL QA:           READY / BLOCKED
FINAL VERDICT:         READY / HOLD
```

A green code scan alone is not a submission approval.

---

## Severity model

### CRITICAL

Likely to block submission or create a serious privacy/policy failure.

Examples:

- release build points to localhost/staging by mistake
- required privacy manifest missing
- undeclared sensitive data collection
- prohibited permission use
- broken account deletion

### HIGH

Strong rejection or delay risk that should be resolved before submission.

### MEDIUM

Needs review, often metadata, accessibility, upcoming policy, or quality-related.

---

## False positives are handled explicitly

AEGIS should not "fix" code simply because a regex matched.

For each finding, trace the exact source first.

Examples that may be false positives:

- `example.com` inside tests
- Open Collective URLs in lockfiles
- a blocked permission name in a deny-list
- subscription cancellation copy that actually sends users to Apple/Google subscription management
- localhost contained only in test code

The correct outcome may be **FALSE POSITIVE**, with evidence.

---

## Regulatory deadline awareness

The project includes dated regulatory and platform requirements that may block distribution independently of the app code.

Run:

```bash
python3 scripts/generate-timeline.py
```

and review:

- `docs/PRE-SUBMISSION-CHECKLIST.md`
- `docs/EU-REGULATORY-2026.md`
- `docs/GLOBAL-REGULATORY-2026.md`
- `docs/PLATFORM-MECHANICS-2026.md`

Do not assume a passed code audit means developer-account or regional legal readiness.

---

## Citation integrity

Compliance rules must be traceable to real sources.

```bash
python3 scripts/verify-citations.py --files docs/ data/ references/ scripts/
```

The verifier distinguishes genuine sources, bot-blocked sources, known examples and unreachable sources rather than treating HTTP status alone as proof.

---

## Project structure

```text
agent-os/
  hooks/          pre-submission guard
  skill/          AI-agent skill

data/             structured rejection patterns and deadlines

docs/             Apple, Google, privacy, security and regulatory guidance

references/       structured policy slices loaded by agents

scripts/          monitors, release audit, citation verifier, metadata audit

templates/        reusable submission/compliance templates
```

---

## AEGIS development direction

Planned enhancements are documented in [`docs/AEGIS-ROADMAP.md`](docs/AEGIS-ROADMAP.md).

Priority areas:

- multi-app portfolio audit command
- machine-readable JSON/SARIF output
- policy-region profiles
- evidence bundles for release sign-off
- diff-aware audits for pull requests
- CI annotations
- waiver/suppression records with expiry dates
- store-account readiness tracking
- signed-build proof tracking
- release readiness scorecard

---

## Upstream attribution

This repository is derived from:

**App Store Compliance Playbook**  
Original author: **Mirza Iqbal / mjmirza**  
Upstream: https://github.com/mjmirza/app-store-compliance

AEGIS Systems maintains this enhanced distribution for its own mobile-app governance and release workflow.

The original copyright, licence and notice must be retained.

---

## Licence

This repository remains under the **OpenRoots Agent License 2.3** inherited from the upstream project.

See:

- [`LICENSE`](LICENSE)
- [`NOTICE`](NOTICE)

The current licence states that the Root tier is free for individuals and organisations at or below the stated annual revenue threshold, with different terms above that threshold. AI training rights are handled separately by the licence.

Do not remove or replace the upstream copyright or licence notices.

---

## Important note

This tool helps identify technical, store-policy and regulatory readiness issues. It is not a substitute for legal advice, and store policies can change after a release of this repository.

Always re-check current Apple and Google requirements before final submission.
