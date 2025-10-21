#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${REGISTRY:-localhost}"
TAG="${TAG:-latest}"
BUILDER="${BUILDER:-podman}"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]
Options:
    -r, --registry REGISTRY    Registry (default: localhost)
    -t, --tag TAG              Tag (default: latest)
    -b, --builder BUILDER      podman or docker (default: podman)
    -s, --slurm-only           Build Slurm only
    -f, --flux-only            Build Flux only
    -h, --help                 Show help
EOF
    exit 0
}

BUILD_SLURM=true
BUILD_FLUX=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -b|--builder)
            BUILDER="$2"
            shift 2
            ;;
        -s|--slurm-only)
            BUILD_SLURM=true
            BUILD_FLUX=false
            shift
            ;;
        -f|--flux-only)
            BUILD_SLURM=false
            BUILD_FLUX=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if ! command -v "$BUILDER" &> /dev/null; then
    echo "Error: $BUILDER not found"
    exit 1
fi

echo "Building MCP servers (registry: $REGISTRY, tag: $TAG)"

if [ "$BUILD_SLURM" = true ]; then
    echo "Building Slurm MCP Server..."
    cd "${SCRIPT_DIR}/slurm"
    $BUILDER build -t "${REGISTRY}/slurm-mcp-server:${TAG}" -f Containerfile .
    cd "${SCRIPT_DIR}"
fi

if [ "$BUILD_FLUX" = true ]; then
    echo "Building Flux MCP Server..."
    cd "${SCRIPT_DIR}/flux"
    $BUILDER build -t "${REGISTRY}/flux-mcp-server:${TAG}" -f Containerfile .
    cd "${SCRIPT_DIR}"
fi

echo "Build complete!"
[ "$BUILD_SLURM" = true ] && echo "  - ${REGISTRY}/slurm-mcp-server:${TAG}"
[ "$BUILD_FLUX" = true ] && echo "  - ${REGISTRY}/flux-mcp-server:${TAG}"

