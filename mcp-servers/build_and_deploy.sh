#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-hpc-local}"

# Check cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Error: Cluster '${CLUSTER_NAME}' not found. Run: ../bootstrap/setup_local_cluster.sh"
    exit 1
fi

# Check deployments
SLURM_READY=false
FLUX_READY=false

kubectl get namespace slurm >/dev/null 2>&1 && \
    kubectl get pod slurm-controller-0 -n slurm >/dev/null 2>&1 && SLURM_READY=true

kubectl get namespace flux-operator >/dev/null 2>&1 && \
    kubectl get pods -n flux-operator -l job-name=flux-sample 2>/dev/null | grep -q flux-sample && FLUX_READY=true

if [ "$SLURM_READY" = false ] && [ "$FLUX_READY" = false ]; then
    echo "Error: Neither Slurm nor Flux found. Run: ../bootstrap/setup_local_cluster.sh"
    exit 1
fi

echo "Found: $([ "$SLURM_READY" = true ] && echo "Slurm")$([ "$SLURM_READY" = true ] && [ "$FLUX_READY" = true ] && echo " + ")$([ "$FLUX_READY" = true ] && echo "Flux")"

# Build images
echo "Building images..."
"${SCRIPT_DIR}/build.sh"

# Load images
echo "Loading images into kind..."
[ "$SLURM_READY" = true ] && podman save localhost/slurm-mcp-server:latest | kind load image-archive /dev/stdin --name "${CLUSTER_NAME}"
[ "$FLUX_READY" = true ] && podman save localhost/flux-mcp-server:latest | kind load image-archive /dev/stdin --name "${CLUSTER_NAME}"

# Deploy
echo "Deploying MCP servers..."
if [ "$SLURM_READY" = true ]; then
    kubectl get svc slurm-restapi -n slurm >/dev/null 2>&1 || echo "Warning: slurm-restapi service not found"
    kubectl apply -k "${PROJECT_ROOT}/manifests/slurm-mcp-server/overlays/local"
    kubectl wait --for=condition=Ready pod -l app=slurm-mcp-server -n slurm --timeout=60s 2>/dev/null || true
fi

if [ "$FLUX_READY" = true ]; then
    kubectl apply -k "${PROJECT_ROOT}/manifests/flux-mcp-server/overlays/local"
    kubectl wait --for=condition=Ready pod -l app=flux-mcp-server -n flux-operator --timeout=60s 2>/dev/null || true
fi

# Verify
echo "Deployment complete!"
[ "$SLURM_READY" = true ] && kubectl get pods,svc -n slurm -l app=slurm-mcp-server
[ "$FLUX_READY" = true ] && kubectl get pods,svc -n flux-operator -l app=flux-mcp-server

echo ""
echo "Run tests: cd ../tests && ./integration_test.sh"

