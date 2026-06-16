#!/usr/bin/env bash
# verify.sh — run after Railway deploy to confirm agentmemory is healthy
# Usage: AGENTMEMORY_URL=https://<proxy-domain> AGENTMEMORY_SECRET=<token> ./verify.sh
set -euo pipefail

URL="${AGENTMEMORY_URL:-http://localhost:3111}"
SECRET="${AGENTMEMORY_SECRET:-}"

pass() { echo "✅ $1"; }
fail() { echo "❌ $1"; exit 1; }

echo "=== agentmemory verify ==="
echo "URL: $URL"
echo ""

# 1. Health check
status=$(curl -sf -o /dev/null -w "%{http_code}" \
  ${SECRET:+-H "Authorization: Bearer $SECRET"} \
  "$URL/agentmemory/health" 2>/dev/null || echo "000")
[ "$status" = "200" ] && pass "health ($status)" || fail "health returned $status (expected 200)"

# 2. Livez (alternate path)
status=$(curl -sf -o /dev/null -w "%{http_code}" \
  ${SECRET:+-H "Authorization: Bearer $SECRET"} \
  "$URL/agentmemory/livez" 2>/dev/null || echo "000")
[ "$status" = "200" ] && pass "livez ($status)" || echo "⚠️  livez returned $status (optional path, non-fatal)"

# 3. List memories (proves engine is running + data loaded)
echo ""
echo "--- memory list (top 5) ---"
curl -sf \
  ${SECRET:+-H "Authorization: Bearer $SECRET"} \
  "$URL/agentmemory/list?limit=5" 2>/dev/null \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('memories', data.get('items', []))
print(f'count in response: {len(items)}')
for m in items[:3]:
    text = m.get('content','') or m.get('text','') or str(m)
    print(f'  - {str(text)[:80]}')
" 2>/dev/null || echo "⚠️  /list not available or returned non-JSON"

echo ""
pass "verify complete — if all ✅, agentmemory is live and reachable"
