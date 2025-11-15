#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-hpc-local}"
KUSTOMIZE_PATH="${PROJECT_ROOT}/manifests/hpc-mcp-server/overlays/local"

if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Error: kind cluster '${CLUSTER_NAME}' not found. Run ../bootstrap/setup_local_cluster.sh" >&2
    exit 1
fi

echo "Building unified MCP server image..."
"${SCRIPT_DIR}/build.sh"

IMAGE="localhost/hpc-mcp-server:latest"

echo "Loading image into kind..."
TMP_IMAGE_FILE="$(mktemp)"
trap 'rm -f "$TMP_IMAGE_FILE"' EXIT
podman save "$IMAGE" -o "$TMP_IMAGE_FILE"
kind load image-archive "$TMP_IMAGE_FILE" --name "${CLUSTER_NAME}"

if [ ! -d "$KUSTOMIZE_PATH" ]; then
    echo "Error: missing kustomize overlay at $KUSTOMIZE_PATH" >&2
    exit 1
fi

echo "Deploying unified MCP server..."
kubectl apply -k "$KUSTOMIZE_PATH"

kubectl wait --for=condition=Ready pod -l app=hpc-mcp-server -n hpc-mcp --timeout=120s 2>/dev/null || true

kubectl get pods,svc -n hpc-mcp -l app=hpc-mcp-server

echo "Deployment complete. Use kubectl port-forward -n hpc-mcp svc/hpc-mcp-server 5000:5000"
