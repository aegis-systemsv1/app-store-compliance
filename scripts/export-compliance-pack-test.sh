#!/usr/bin/env bash
# Test gauntlet for export-compliance-pack.py / validate-compliance-pack.py /
# the compliance-pack-requirements validation in validate.py.
set -uo pipefail
cd "$(dirname "$0")/.."
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fails=0
check() { # name, expected-regex, haystack-file
  if grep -qE "$2" "$3"; then echo "PASS $1"; else echo "FAIL $1 (wanted /$2/)"; fails=$((fails+1)); fi
}
ncheck() {
  if grep -qE "$2" "$3"; then echo "FAIL $1 (must NOT match /$2/)"; fails=$((fails+1)); else echo "PASS $1"; fi
}
expect_exit() { # name, expected-code, actual-code
  if [ "$2" -eq "$3" ]; then echo "PASS $1"; else echo "FAIL $1 (wanted exit $2, got $3)"; fails=$((fails+1)); fi
}

# --- 1. The real authored catalogue validates clean, every requirement, schema-conformant ---
python3 scripts/validate-compliance-pack.py > "$T/validate_real.txt" 2>&1
rc=$?
expect_exit "real catalogue validates with exit 0" 0 "$rc"
check "real catalogue reports all 12 requirements" "12 requirements, 0 errors" "$T/validate_real.txt"

# --- 2. A minimal, valid fixture exports and validates (roundtrip) ---
cat > "$T/good.json" <<'JSON'
{
  "catalogue_version": "9.9.9",
  "catalogue_description": "test fixture",
  "catalogue_items_covered": ["thing_a"],
  "requirements": [
    {
      "requirement_id": "TEST-GOOD-001",
      "jurisdiction": "AU",
      "regulator": "Test Regulator",
      "legislation": {
        "title": "Test Act 2026",
        "source_url": "https://example.invalid/test-act",
        "source_retrieved_date": "2026-10-02"
      },
      "description": "A fixture requirement for the export test gauntlet.",
      "status": "CURRENT_LAW",
      "effective_date": null,
      "applicability_conditions": ["always, for this fixture"],
      "evidence_method": "AUTOMATED",
      "evidence_requirements": [
        {
          "evidence_id": "fixture-evidence",
          "description": "A fixture evidence item.",
          "method": "AUTOMATED",
          "covers_catalogue_items": ["thing_a"]
        }
      ],
      "severity": "low",
      "release_blocking_policy": "advisory_only",
      "requirement_version": 1,
      "last_verified_date": "2026-10-02",
      "change_history": [
        {"requirement_version": 1, "changed_at": "2026-10-02", "change": "fixture", "pack_version_introduced": "9.9.9"}
      ]
    }
  ]
}
JSON

COMPLIANCE_REQUIREMENTS_FILE="$T/good.json" python3 scripts/export-compliance-pack.py --out "$T/exported-good.json" > "$T/export_good.txt" 2>&1
rc=$?
expect_exit "valid fixture exports with exit 0" 0 "$rc"
check "export reports 1 requirement" "1 requirements" "$T/export_good.txt"

test -f "$T/exported-good.json"
expect_exit "export actually wrote a file" 0 $?

python3 scripts/validate-compliance-pack.py "$T/exported-good.json" > "$T/validate_exported.txt" 2>&1
rc=$?
expect_exit "exported pack independently re-validates" 0 "$rc"

# --- 3. Attribution / licence block survives export ---
check "exported pack carries the OpenRoots licence" '"license": "OpenRoots Agent License 2.3"' "$T/exported-good.json"
check "exported pack carries licence_origin attribution" "Mirza Iqbal" "$T/exported-good.json"
check "exported pack carries a real commit sha, not a placeholder" '"commit": "[0-9a-f]{40}"' "$T/exported-good.json"

# --- 4. A malformed requirement fails the whole export, no partial pack ---
cat > "$T/bad.json" <<'JSON'
{
  "catalogue_version": "9.9.9",
  "catalogue_items_covered": [],
  "requirements": [
    {
      "requirement_id": "TEST-BAD-001",
      "jurisdiction": "AU",
      "regulator": "Test Regulator",
      "legislation": {"title": "Test Act 2026", "source_url": "https://example.invalid/x", "source_retrieved_date": "2026-10-02"},
      "description": "Missing evidence_method and evidence_requirements on purpose.",
      "status": "NOT_A_REAL_STATUS",
      "applicability_conditions": ["always"],
      "severity": "low",
      "release_blocking_policy": "advisory_only",
      "requirement_version": 1,
      "last_verified_date": "2026-10-02",
      "change_history": [{"requirement_version": 1, "changed_at": "2026-10-02", "change": "fixture", "pack_version_introduced": "9.9.9"}]
    }
  ]
}
JSON

COMPLIANCE_REQUIREMENTS_FILE="$T/bad.json" python3 scripts/export-compliance-pack.py --out "$T/exported-bad.json" > "$T/export_bad.txt" 2>&1
rc=$?
expect_exit "malformed requirement fails the export" 1 "$rc"
check "export names the invalid status" "invalid status" "$T/export_bad.txt"
check "export names the missing evidence_method" "missing required field 'evidence_method'" "$T/export_bad.txt"
test ! -f "$T/exported-bad.json"
expect_exit "no partial pack file was written on failure" 0 $?

# --- 5. HYBRID must have both an AUTOMATED and an OWNER_EVIDENCE evidence item ---
cat > "$T/bad_hybrid.json" <<'JSON'
{
  "catalogue_version": "9.9.9",
  "catalogue_items_covered": ["x"],
  "requirements": [
    {
      "requirement_id": "TEST-HYBRID-001",
      "jurisdiction": "AU",
      "regulator": "Test Regulator",
      "legislation": {"title": "Test Act 2026", "source_url": "https://example.invalid/x", "source_retrieved_date": "2026-10-02"},
      "description": "HYBRID with only automated evidence, which is invalid.",
      "status": "CURRENT_LAW",
      "applicability_conditions": ["always"],
      "evidence_method": "HYBRID",
      "evidence_requirements": [
        {"evidence_id": "e1", "description": "automated only", "method": "AUTOMATED", "covers_catalogue_items": ["x"]}
      ],
      "severity": "low",
      "release_blocking_policy": "advisory_only",
      "requirement_version": 1,
      "last_verified_date": "2026-10-02",
      "change_history": [{"requirement_version": 1, "changed_at": "2026-10-02", "change": "fixture", "pack_version_introduced": "9.9.9"}]
    }
  ]
}
JSON
COMPLIANCE_REQUIREMENTS_FILE="$T/bad_hybrid.json" python3 scripts/validate-compliance-pack.py "$T/bad_hybrid.json" > "$T/validate_hybrid.txt" 2>&1
rc=$?
expect_exit "HYBRID missing an OWNER_EVIDENCE item fails validation" 1 "$rc"
check "names the HYBRID inconsistency" "classified HYBRID but does not have both" "$T/validate_hybrid.txt"

# --- 6. OWNER_EVIDENCE must never be satisfied by absence of a finding alone ---
# (This is a documentation/behavioural invariant enforced on the consuming side,
#  not something this exporter can test in isolation -- confirmed by inspection
#  that evidence_method=OWNER_EVIDENCE requirements carry no AUTOMATED-only path.)
python3 -c "
import json
pack = json.load(open('compliance-pack/exports/compliance-pack-v1.0.0.json'))
owner_only = [r for r in pack['requirements'] if r['evidence_method'] == 'OWNER_EVIDENCE']
bad = [r['requirement_id'] for r in owner_only if any(e['method'] == 'AUTOMATED' for e in r['evidence_requirements'])]
assert not bad, f'OWNER_EVIDENCE requirement has an AUTOMATED-only path: {bad}'
print('PASS OWNER_EVIDENCE requirements never gate on empty filesystem evidence')
" >> "$T/owner_evidence.txt" 2>&1
rc=$?
cat "$T/owner_evidence.txt"
expect_exit "no OWNER_EVIDENCE requirement is secretly automated" 0 "$rc"

# --- 7. Catalogue items cross-check: every declared item must have real coverage ---
cat > "$T/missing_coverage.json" <<'JSON'
{
  "catalogue_version": "9.9.9",
  "catalogue_items_covered": ["covered_thing", "uncovered_thing"],
  "requirements": [
    {
      "requirement_id": "TEST-COVERAGE-001",
      "jurisdiction": "AU",
      "regulator": "Test Regulator",
      "legislation": {"title": "Test Act 2026", "source_url": "https://example.invalid/x", "source_retrieved_date": "2026-10-02"},
      "description": "Only covers one of the two declared items.",
      "status": "CURRENT_LAW",
      "applicability_conditions": ["always"],
      "evidence_method": "AUTOMATED",
      "evidence_requirements": [
        {"evidence_id": "e1", "description": "covers one item", "method": "AUTOMATED", "covers_catalogue_items": ["covered_thing"]}
      ],
      "severity": "low",
      "release_blocking_policy": "advisory_only",
      "requirement_version": 1,
      "last_verified_date": "2026-10-02",
      "change_history": [{"requirement_version": 1, "changed_at": "2026-10-02", "change": "fixture", "pack_version_introduced": "9.9.9"}]
    }
  ]
}
JSON
COMPLIANCE_REQUIREMENTS_FILE="$T/missing_coverage.json" python3 scripts/validate-compliance-pack.py "$T/missing_coverage.json" > "$T/validate_coverage.txt" 2>&1
rc=$?
expect_exit "an uncovered declared catalogue item fails validation" 1 "$rc"
check "names the uncovered item" "uncovered_thing" "$T/validate_coverage.txt"

echo "----"
if [ "$fails" -eq 0 ]; then echo "export-compliance-pack-test: ALL PASS"; else echo "export-compliance-pack-test: $fails FAIL"; exit 1; fi
