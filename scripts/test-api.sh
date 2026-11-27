#!/usr/bin/env bash
# Smoke-test the deployed API: happy path, error handling, CORS preflight, unknown route.
# Each run stores two new items in the table (the two 201 cases).
#
# Usage:
#   export API_URL="https://<api-id>.execute-api.us-west-2.amazonaws.com/prod"
#   ./scripts/test-api.sh
set -uo pipefail

API_URL="${API_URL:?Set API_URL first, e.g. export API_URL=https://<api-id>.execute-api.us-west-2.amazonaws.com/prod}"
FAILED=0

check() {
  local name="$1" expected="$2"
  shift 2
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' "$@")
  if [[ "$status" == "$expected" ]]; then
    printf 'PASS  %-16s %s\n' "$name" "$status"
  else
    printf 'FAIL  %-16s %s (expected %s)\n' "$name" "$status" "$expected"
    FAILED=1
  fi
}

JSON=(-H "Content-Type: application/json")

check "valid POST"     201 -X POST "$API_URL/submit" "${JSON[@]}" -d '{"name": "Mo", "module": "AWS"}'
check "decimal number" 201 -X POST "$API_URL/submit" "${JSON[@]}" -d '{"name": "Mo", "score": 9.5}'
check "bad JSON"       400 -X POST "$API_URL/submit" "${JSON[@]}" -d '{name: Mo}'
check "empty body"     400 -X POST "$API_URL/submit"
check "CORS preflight" 200 -X OPTIONS "$API_URL/submit" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type"
check "unknown route"  403 -X POST "$API_URL/does-not-exist"

exit "$FAILED"
