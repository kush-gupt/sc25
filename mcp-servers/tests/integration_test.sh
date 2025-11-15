#!/bin/bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-hpc-mcp}"
PORT="${PORT:-5000}"

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
ACCEPT_HEADER="application/json"

cat <<REQ | curl -fsS \
  -H 'Content-Type: application/json' \
  -H "Accept: ${ACCEPT_HEADER}" \
  -d @- "http://127.0.0.1:${PORT}/messages" | jq .
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
  -d @- "http://127.0.0.1:${PORT}/messages" | jq .
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
