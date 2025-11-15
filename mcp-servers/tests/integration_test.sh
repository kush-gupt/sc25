#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-hpc-mcp}"
PORT="${PORT:-5000}"

pretty_print_sse_json() {
  python -c '
import json
import sys

payload = sys.stdin.read().strip()

def emit(obj):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(0)

if not payload:
    sys.exit("No data returned from server")

try:
    emit(json.loads(payload))
except json.JSONDecodeError:
    pass

for raw in payload.splitlines():
    line = raw.strip()
    if not line or line.startswith(":"):
        continue
    if line.startswith("data:"):
        line = line[5:].strip()
    if not line:
        continue
    try:
        emit(json.loads(line))
    except json.JSONDecodeError:
        continue

sys.exit("No JSON payload found in response")
' || return 1
}

if ! kubectl get svc hpc-mcp-server -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "Service hpc-mcp-server not found in namespace $NAMESPACE" >&2
  exit 1
fi

echo "Checking /health endpoint..."
PF_LOG=$(mktemp)
kubectl port-forward -n "$NAMESPACE" svc/hpc-mcp-server "$PORT:$PORT" >"$PF_LOG" 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true; rm -f "$PF_LOG"' EXIT
sleep 4

curl -fsS "http://127.0.0.1:${PORT}/health" | jq .

echo "Requesting tools/list..."
ACCEPT_HEADER="application/json, text/event-stream"

cat <<REQ | curl -fsS \
  -H 'Content-Type: application/json' \
  -H "Accept: ${ACCEPT_HEADER}" \
  -d @- "http://127.0.0.1:${PORT}/messages" | pretty_print_sse_json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
REQ

echo "Listing Flux MiniClusters..."
cat <<REQ | curl -fsS \
  -H 'Content-Type: application/json' \
  -H "Accept: ${ACCEPT_HEADER}" \
  -d @- "http://127.0.0.1:${PORT}/messages" | pretty_print_sse_json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "flux_list_miniclusters",
    "arguments": {}
  }
}
REQ

echo "Integration test completed successfully"
