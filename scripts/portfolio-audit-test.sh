#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d 2>/dev/null || mktemp -d -t portfolio-audit)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/clean-app" "$TMP/blocked-app"

cat > "$TMP/fake-guard.sh" <<'EOF'
#!/usr/bin/env bash
set -u
if [ "${APP_STORE_GUARD_OK:-0}" = "1" ]; then
  echo "Summary. critical=0 high=0 medium=0"
  exit 0
fi
case "$(basename "$1")" in
  clean-app)
    echo "Summary. critical=0 high=1 medium=2"
    exit 0
    ;;
  blocked-app)
    echo "Summary. critical=2 high=0 medium=1"
    exit 2
    ;;
  *)
    echo "unexpected path"
    exit 9
    ;;
esac
EOF
chmod +x "$TMP/fake-guard.sh"

cat > "$TMP/portfolio.json" <<EOF
{
  "portfolio_name": "Test Portfolio",
  "apps": [
    {"name": "Clean-ish", "path": "$TMP/clean-app"},
    {"name": "Blocked", "path": "$TMP/blocked-app"}
  ]
}
EOF

# The runner must remove an inherited local bypass rather than silently green the audit.
APP_STORE_GUARD_OK=1 python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/portfolio.json" \
  --guard "$TMP/fake-guard.sh" \
  --fail-on never \
  --json > "$TMP/result.json"

python3 - "$TMP/result.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    data = json.load(fh)

assert data["portfolio"] == "Test Portfolio"
assert data["overall_verdict"] == "BLOCKED"
assert data["totals"] == {"critical": 2, "high": 1, "medium": 3, "errors": 0}
assert data["results"][0]["verdict"] == "REVIEW"
assert data["results"][1]["verdict"] == "BLOCKED"
PY

mkdir "$TMP/evidence"
python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/portfolio.json" \
  --guard "$TMP/fake-guard.sh" \
  --fail-on never \
  --evidence-dir "$TMP/evidence" >/dev/null

test -f "$TMP/evidence/Clean-ish.txt"
test -f "$TMP/evidence/Blocked.txt"
test -f "$TMP/evidence/portfolio-summary.json"

cat > "$TMP/missing.json" <<EOF
{"apps":[{"name":"Missing","path":"$TMP/does-not-exist"}]}
EOF
set +e
python3 "$ROOT/scripts/portfolio-audit.py" \
  --config "$TMP/missing.json" \
  --guard "$TMP/fake-guard.sh" >/dev/null
status=$?
set -e
[ "$status" -eq 3 ] || { echo "expected missing app to exit 3, got $status"; exit 1; }

echo "portfolio-audit tests passed"
