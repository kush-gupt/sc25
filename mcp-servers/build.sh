#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${REGISTRY:-localhost}"
TAG="${TAG:-latest}"
BUILDER="${BUILDER:-podman}"
IMAGE_NAME=""

usage() {
    cat <<USAGE
Usage: $0 [OPTIONS]
  -r, --registry REGISTRY    Target registry (default: localhost)
  -t, --tag TAG              Image tag (default: latest)
  -b, --builder BUILDER      Container builder (podman|docker)
  -h, --help                 Show this help
USAGE
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r|--registry)
            REGISTRY="$2"; shift 2 ;;
        -t|--tag)
            TAG="$2"; shift 2 ;;
        -b|--builder)
            BUILDER="$2"; shift 2 ;;
        -h|--help)
            usage ;;
        *)
            echo "Unknown option: $1" >&2
            usage ;;
    esac
done

IMAGE_NAME="${REGISTRY}/hpc-mcp-server:${TAG}"

if ! command -v "$BUILDER" >/dev/null 2>&1; then
    echo "Error: builder '$BUILDER' not found" >&2
    exit 1
fi

pushd "${SCRIPT_DIR}/hpc_mcp_server" >/dev/null
$BUILDER build -t "$IMAGE_NAME" -f Containerfile .
popd >/dev/null

echo "Built $IMAGE_NAME"
