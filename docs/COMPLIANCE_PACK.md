# Compliance Pack

AEGIS owns compliance requirement definitions: jurisdiction, regulator,
status (current law, future commencement, proposed, or guidance), effective
dates, applicability conditions, required evidence, and source citations.
A consuming system -- ShipSure, or any other schema-conformant consumer --
imports a specific, versioned export of this catalogue, independently
inspects an application, and computes its own release-readiness result.
AEGIS never computes a consumer's release-readiness result itself, and no
field in an exported pack is an instruction a consumer must obey; see
`release_blocking_policy` below.

## Files

- `data/compliance-pack-schema.json` -- the schema (JSON Schema draft-07) a
  pack conforms to.
- `data/compliance-pack-requirements.json` -- the authored source catalogue.
  Add or edit a requirement here.
- `scripts/export-compliance-pack.py` -- validates the catalogue and writes a
  versioned pack to `compliance-pack/exports/compliance-pack-v{version}.json`,
  stamped with the real git commit, tag (if any), export timestamp, and the
  repository's licence/attribution block.
- `scripts/validate-compliance-pack.py` -- validates the authored catalogue,
  or any already-exported pack file, independently of the export step.
- `scripts/export-compliance-pack-test.sh` -- the test gauntlet.

## How a human adds or updates a requirement

1. Edit `data/compliance-pack-requirements.json`. Give the requirement a
   stable `requirement_id` (never reused for a different requirement later
   -- a superseding requirement gets a new id). Fill every field the schema
   requires.
2. Classify `evidence_method` honestly:
   - `AUTOMATED` -- every evidence item is machine-checkable.
   - `HYBRID` -- at least one evidence item is machine-checkable and at
     least one genuinely needs an owner's evidence. (`scripts/validate.py`
     enforces that a `HYBRID` requirement actually has both kinds of
     evidence item, not just the label.)
   - `OWNER_EVIDENCE` -- no evidence item here is machine-checkable; a
     consumer must require an explicit owner attestation and must never
     treat the absence of a finding as a pass.
3. Set `status` honestly: `CURRENT_LAW` (already in force),
   `ENACTED_FUTURE_COMMENCEMENT` (passed, not yet in force -- requires a real
   `effective_date`), `PROPOSED_CONSULTATION` (not yet law), or
   `GUIDANCE_GOOD_PRACTICE` (not a legal instrument at all). A consumer must
   never let a `PROPOSED_CONSULTATION` or `GUIDANCE_GOOD_PRACTICE`
   requirement, or a future-dated `ENACTED_FUTURE_COMMENCEMENT`
   requirement, block a release -- that rule lives in the consumer's own
   code (see `release_blocking_policy` below), not in this catalogue.
4. Cite a real, retrievable primary source (`legislation.source_url`). Never
   fabricate a URL. If you cannot verify a citation with confidence, say so
   in the requirement's own evidence/description text rather than inventing
   one.
5. Run `python3 scripts/validate.py` (or
   `python3 scripts/validate-compliance-pack.py`) and fix anything it flags.
6. Run `python3 scripts/export-compliance-pack.py` to produce a new versioned
   export. Commit both the catalogue edit and the new export file together.

## `release_blocking_policy` is not an instruction

Every requirement carries a `release_blocking_policy` value
(`blocking_once_current_and_effective` or `advisory_only`). This is
descriptive metadata about AEGIS's own assessment of the requirement's
normal severity -- it is **not** authority a consumer may act on directly.
A conformant consumer must independently derive actual blocking behaviour
from `status` + `effective_date` + its own current date, every time, and
must never let this field alone force a blocking result on a requirement
that is `PROPOSED_CONSULTATION`, `GUIDANCE_GOOD_PRACTICE`, or not yet
`effective_date`. This is deliberate: a malformed or even malicious pack
entry claiming "always blocking" on a proposed requirement must have zero
effect on a correctly-implemented consumer.

## Versioning and identity

`pack_version` is an author-controlled, informational label. A consumer
should compute its **own** content hash of an imported pack for identity
and pinning purposes, never trust a hash asserted inside the pack. Each
export is also stamped with the real git `commit` (and `tag`, if the export
was made from a tagged commit) it was produced from, so provenance is
independently verifiable from the AEGIS repository's own history.

## Scope boundary

This catalogue and its exporter are additive to AEGIS. They do not change,
replace, or weaken any existing rejection-pattern detection, regulatory
deadline tracking, portfolio-register generation, or store-readiness
tracking already in this repository. The `PORTFOLIO_COMPLIANCE_REGISTER.md`
files generated for individual portfolio apps are a separate, pre-existing
AEGIS output and are untouched by this feature.

## Licence

The whole repository, including this catalogue and its exported packs, is
licensed under the OpenRoots Agent License 2.3 -- see `LICENSE` and
`NOTICE`. Every exported pack carries a `source.license` and
`source.license_origin` field recording this; a consumer must preserve that
attribution wherever it renders a requirement from this pack and must not
copy this repository's detection/implementation code into its own codebase
under a different licence.

## Pack schema 1.1.0: app-store platform policy and platforms

Version 1.1.0 of the schema (`pack_schema_version: "1.1.0"`) is a strict superset of 1.0.0, so a 1.0.0 pack still
validates. It adds what store submission requirements need:

- `status` gains `PLATFORM_POLICY_CURRENT` (an Apple or Google policy enforced at submission/review now) and
  `PLATFORM_POLICY_FUTURE` (announced with a fixed `effective_date`, required). A store policy is never labelled as
  law. A consumer applies the same date logic to `PLATFORM_POLICY_FUTURE` as to `ENACTED_FUTURE_COMMENCEMENT`.
- `applies_to_platforms` (optional): one or more of `web`, `ios`, `android`, `macos`, `windows`. Absent means the
  requirement is platform-agnostic. A consumer must treat a requirement whose platforms are all outside a product's
  selected platforms as not applicable, and must never evaluate a platform-agnostic requirement more than once per product.
- `store` (optional): `APPLE_APP_STORE` (platforms within ios/macos) or `GOOGLE_PLAY` (android). Grouping only.
- `submission_category` (optional): one of `CODE_AND_BUILD`, `PRIVACY_AND_DATA`, `PERMISSIONS`, `AUTHENTICATION`,
  `PAYMENTS`, `CONTENT_AND_SAFETY`, `STORE_LISTING`, `REVIEWER_ACCESS`, `LEGAL_AND_OWNER_DECLARATIONS`, `SUBMISSION_ASSETS`.
- `source_reference` (optional): the official rule identifier (an App Review Guidelines section, a Play policy name).
- `universal_for_platforms` (optional boolean): true when every product released on those platforms must satisfy the
  requirement, with no feature condition. A consumer may then treat it as applicable as soon as the owner selects one of
  those platforms; otherwise applicability stays an owner decision.

For `AUTOMATED` evidence items in store requirements, `note` starts with `SIGNAL: ` and names the deterministic
repository signal (file and key or pattern) a consumer can inspect. AEGIS describes the signal; the consumer decides
whether and how it checks it.

The store requirements were authored on 2026-10-04 from first-party sources only (developer.apple.com,
support.google.com/googleplay, developer.android.com, play.google). The gap analysis behind them, including what was
corrected from older AEGIS prose and what was left out because it could not be verified, is in
`docs/GAP-ANALYSIS-2026-10-STORES.md`. The catalogue's `skipped_unverified` lists the excluded items.

Apple and Google change these rules often. Re-verify against the cited sources and bump `last_verified_date`,
`requirement_version` and `change_history` when a rule changes; a consumer is expected to warn when the newest
`last_verified_date` for a store is old.
