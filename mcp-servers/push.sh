#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${REGISTRY:-quay.io/YOUR_ORG}"
TAG="${TAG:-latest}"
BUILDER="${BUILDER:-podman}"
ALSO_TAG_LATEST=false

usage() {
    cat <<USAGE
Usage: $0 [OPTIONS]
  -r, --registry REGISTRY    Destination registry (required)
  -t, --tag TAG              Image tag (default: latest)
  -b, --builder BUILDER      Container builder (podman|docker)
  -l, --also-tag-latest      Also push :latest alongside TAG
  -h, --help                 Show help
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
        -l|--also-tag-latest)
            ALSO_TAG_LATEST=true; shift ;;
        -h|--help)
            usage ;;
        *)
            echo "Unknown option: $1" >&2
            usage ;;
    esac
done

if [[ "$REGISTRY" == *"YOUR_ORG"* ]]; then
    echo "Error: specify a valid registry via --registry" >&2
    exit 1
fi

IMAGE="${REGISTRY}/hpc-mcp-server:${TAG}"

if ! command -v "$BUILDER" >/dev/null 2>&1; then
    echo "Error: builder '$BUILDER' not found" >&2
    exit 1
fi

if ! $BUILDER images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE}$"; then
    echo "Local image $IMAGE not found, building first"
    REGISTRY="$REGISTRY" TAG="$TAG" "$SCRIPT_DIR/build.sh"
fi

$BUILDER push "$IMAGE"

if $ALSO_TAG_LATEST && [[ "$TAG" != "latest" ]]; then
    $BUILDER tag "$IMAGE" "${REGISTRY}/hpc-mcp-server:latest"
    $BUILDER push "${REGISTRY}/hpc-mcp-server:latest"
fi

echo "Pushed $IMAGE"
