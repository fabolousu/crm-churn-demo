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
      response=$(curl -s -w "%{http_code}" -H "x-vercel-protection-bypass: $VERCEL_AUTOMATION_BYPASS_SECRET" -o response.json "$url")
    else
      response=$(curl -s -w "%{http_code}" -o response.json "$url")
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
if ! grep -q 'id="root"' response.json; then
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
status=$(python3 -c "import json, sys; print(json.load(sys.stdin).get('status'))" < response.json)
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
total=$(python3 -c "import json, sys; print(json.load(sys.stdin).get('total'))" < response.json)
items_len=$(python3 -c "import json, sys; print(len(json.load(sys.stdin).get('items')))" < response.json)

if [ "$total" -gt 0 ] && [ "$items_len" -eq 1 ]; then
  echo "PASS: /api/pipeline?limit=1"
else
  echo "FAIL: Invalid pipeline response. Total: $total, Items length: $items_len"
  exit 1
fi

echo "All smoke tests passed."
rm response.json
