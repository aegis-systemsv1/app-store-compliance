#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d 2>/dev/null || mktemp -d -t portfolio-audit)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/review-app/.app-store-compliance" "$TMP/blocked-app"

cat > "$TMP/fake-guard.sh" <<'EOF'
#!/usr/bin/env bash
set -u
if [ "${APP_STORE_GUARD_OK:-0}" = "1" ]; then
  echo "Summary. critical=0 high=0 medium=0"
  exit 0
fi
case "$(basename "$1")" in
  review-app)
    cat <<'OUT'
  [HIGH]     BOTH-PLACEHOLDER  Placeholder content found
      fix. Replace placeholder content.
  [MEDIUM]   GOOGLE-12-TESTER-RULE  Verify the closed testing requirement
      fix. Verify Play Console account requirements.
Summary. critical=0 high=1 medium=1
OUT
    exit 0
    ;;
  blocked-app)
    cat <<'OUT'
  [CRITICAL] APPLE-PRIVACY-MANIFEST-MISSING  Privacy manifest missing
      fix. Add a valid privacy manifest.
Summary. critical=1 high=0 medium=0
OUT
    exit 2
    ;;
  *) echo "unexpected path"; exit 9 ;;
esac
EOF
chmod +x "$TMP/fake-guard.sh"

cat > "$TMP/review-app/.app-store-compliance/findings.json" <<'EOF'
{
  "schema_version": 1,
  "findings": [
    {
      "id": "BOTH-PLACEHOLDER",
      "classification": "FALSE_POSITIVE",
      "reason": "Dependency metadata only",
      "reviewed_at": "2026-09-13",
      "expires": "2027-01-01",
      "evidence": ["package-lock.json"]
    },
    {
      "id": "GOOGLE-12-TESTER-RULE",
      "classification": "OWNER_LEGAL",
      "reason": "Account eligibility must be checked in Play Console",
      "reviewed_at": "2026-09-13"
    }
  ]
}
EOF

cat > "$TMP/portfolio.json" <<EOF
{
  "portfolio_name": "Test Portfolio",
  "apps": [
    {
      "name": "Review App",
      "path": "$TMP/review-app",
      "regions": ["AU", "US"],
      "store_readiness": {
        "apple_agreements": true,
        "privacy_answers": false
      }
    },
    {"name": "Blocked", "path": "$TMP/blocked-app"}
  ]
}
EOF

APP_STORE_GUARD_OK=1 python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/portfolio.json" --guard "$TMP/fake-guard.sh" \
  --today 2026-09-13 --fail-on never --json > "$TMP/result.json"

python3 - "$TMP/result.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh: data = json.load(fh)
assert data["schema_version"] == 2
assert data["overall_verdict"] == "BLOCKED"
review, blocked = data["results"]
assert review["raw_counts"] == {"critical": 0, "high": 1, "medium": 1}
assert review["effective_counts"] == {"critical": 0, "high": 0, "medium": 0}
assert review["classification_counts"]["false_positive"] == 1
assert review["owner_blockers"]["owner_legal"] == 1
assert review["store_readiness"]["missing"] == ["privacy_answers"]
assert review["verdict"] == "OWNER_ACTION"
assert blocked["effective_counts"]["critical"] == 1
assert blocked["verdict"] == "BLOCKED"
PY

mkdir "$TMP/evidence"
python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/portfolio.json" --guard "$TMP/fake-guard.sh" \
  --today 2026-09-13 --fail-on never --evidence-dir "$TMP/evidence" >/dev/null

test -f "$TMP/evidence/Review-App-guard.txt"
test -f "$TMP/evidence/Review-App-findings.json"
test -f "$TMP/evidence/portfolio-summary.json"
test -f "$TMP/evidence/SUMMARY.md"
test -f "$TMP/evidence/compliance.sarif"
python3 - "$TMP/evidence/compliance.sarif" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh: data = json.load(fh)
results = data["runs"][0]["results"]
ids = {r["ruleId"] for r in results}
assert "BOTH-PLACEHOLDER" not in ids
assert "GOOGLE-12-TESTER-RULE" in ids
assert "APPLE-PRIVACY-MANIFEST-MISSING" in ids
PY

# Expired false positives must become active again.
python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/portfolio.json" --guard "$TMP/fake-guard.sh" \
  --today 2027-02-01 --fail-on never --json > "$TMP/expired.json"
python3 - "$TMP/expired.json" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh: data = json.load(fh)
r = data["results"][0]
assert r["effective_counts"]["high"] == 1
assert r["classification_counts"]["expired"] == 1
PY

cat > "$TMP/missing.json" <<EOF
{"apps":[{"name":"Missing","path":"$TMP/does-not-exist"}]}
EOF
set +e
python3 "$ROOT/scripts/portfolio-audit.py" --config "$TMP/missing.json" --guard "$TMP/fake-guard.sh" >/dev/null
status=$?
set -e
[ "$status" -eq 3 ] || { echo "expected missing app to exit 3, got $status"; exit 1; }

echo "portfolio-audit tests passed"
