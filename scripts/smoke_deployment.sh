#!/usr/bin/env bash
set -e

# Usage: ./scripts/smoke_deployment.sh <base-url>

BASE_URL=$1

if [ -z "$BASE_URL" ]; then
  echo "Usage: ./scripts/smoke_deployment.sh <base-url>"
  exit 1
fi

# Remove trailing slash
BASE_URL=${BASE_URL%/}

# Response files live in a per-invocation directory; never touch caller files.
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# The bypass secret is only ever sent to this project's own Vercel hosts. A deployment
# status can carry an attacker-supplied URL, so validate it (scheme, credentials,
# query, fragment, hostname) before the first request.
if [ -n "$VERCEL_AUTOMATION_BYPASS_SECRET" ]; then
  if ! python3 "$SCRIPT_DIR/validate_deployment_url.py" "$BASE_URL" >/dev/null; then
    echo "FAIL: refusing to send the bypass secret to an unapproved URL: $BASE_URL"
    exit 1
  fi
fi

echo "Testing $BASE_URL..."

# Helper to run curl with retries
run_curl() {
  local url=$1
  local max_attempts=3
  local attempt=1
  
  while [ $attempt -le $max_attempts ]; do
    echo "Attempt $attempt: GET $url"
    
    # Check if bypass secret is set
    if [ -n "$VERCEL_AUTOMATION_BYPASS_SECRET" ]; then
      response=$(curl -sS --globoff --max-time 20 -w "%{http_code}" -H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET" -o "$TMP_DIR/response.json" "$url") || response="000"
    else
      response=$(curl -sS --globoff --max-time 20 -w "%{http_code}" -o "$TMP_DIR/response.json" "$url") || response="000"
    fi
    
    if [ "$response" -eq 200 ]; then
      return 0
    fi
    
    echo "Attempt $attempt failed with status $response"
    sleep 2
    attempt=$((attempt+1))
  done
  
  return 1
}

# 1. GET /
echo "Checking /"
if ! run_curl "$BASE_URL/"; then
  echo "FAIL: GET / failed"
  exit 1
fi
if ! grep -q 'id="root"' "$TMP_DIR/response.json"; then
  echo "FAIL: Root page does not contain id='root'"
  exit 1
fi
echo "PASS: /"

# 2. GET /api/health
echo "Checking /api/health"
if ! run_curl "$BASE_URL/api/health"; then
  echo "FAIL: GET /api/health failed"
  exit 1
fi
# Use python3 to verify JSON status
status=$(python3 -c "import json, sys; print(json.load(sys.stdin).get('status'))" < "$TMP_DIR/response.json")
echo "Status: $status"
if [[ "$status" != "ok" && "$status" != "degraded" ]]; then
  echo "FAIL: Invalid status: $status"
  exit 1
fi
echo "PASS: /api/health"

# 3. GET /api/pipeline?limit=1
echo "Checking /api/pipeline?limit=1"
if ! run_curl "$BASE_URL/api/pipeline?limit=1"; then
  echo "FAIL: GET /api/pipeline?limit=1 failed"
  exit 1
fi
total=$(python3 -c "import json, sys; print(json.load(sys.stdin).get('total'))" < "$TMP_DIR/response.json")
items_len=$(python3 -c "import json, sys; print(len(json.load(sys.stdin).get('items')))" < "$TMP_DIR/response.json")

if [ "$total" -gt 0 ] && [ "$items_len" -eq 1 ]; then
  echo "PASS: /api/pipeline?limit=1"
else
  echo "FAIL: Invalid pipeline response. Total: $total, Items length: $items_len"
  exit 1
fi

echo "All smoke tests passed."
