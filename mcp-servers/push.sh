#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGISTRY="${REGISTRY:-quay.io/YOUR_ORG}"
TAG="${TAG:-latest}"
BUILDER="${BUILDER:-podman}"

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]
Options:
    -r, --registry REGISTRY    Registry (required, default: quay.io/YOUR_ORG)
    -t, --tag TAG              Tag (default: latest)
    -b, --builder BUILDER      podman or docker (default: podman)
    -s, --slurm-only           Push Slurm only
    -f, --flux-only            Push Flux only
    -l, --also-tag-latest      Also tag as 'latest'
    -h, --help                 Show help
EOF
    exit 0
}

PUSH_SLURM=true
PUSH_FLUX=true
ALSO_TAG_LATEST=false

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
            PUSH_SLURM=true
            PUSH_FLUX=false
            shift
            ;;
        -f|--flux-only)
            PUSH_SLURM=false
            PUSH_FLUX=true
            shift
            ;;
        -l|--also-tag-latest)
            ALSO_TAG_LATEST=true
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

if [[ "$REGISTRY" == *"YOUR_ORG"* ]]; then
    echo "Error: Set a valid registry: ./push.sh --registry quay.io/myorg"
    exit 1
fi

echo "Pushing to $REGISTRY (tag: $TAG)"

push_image() {
    local NAME=$1
    local IMG="${REGISTRY}/${NAME}:${TAG}"
    
    # Build if missing
    if ! $BUILDER images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${REGISTRY}/${NAME}:${TAG}$"; then
        echo "Building missing image: $IMG"
        cd "${SCRIPT_DIR}/$(echo $NAME | cut -d- -f1)"
        $BUILDER build -t "$IMG" -f Containerfile .
        cd "${SCRIPT_DIR}"
    fi
    
    echo "Pushing $IMG..."
    $BUILDER push "$IMG"
    
    # Also push as latest if requested
    if [ "$ALSO_TAG_LATEST" = true ] && [ "$TAG" != "latest" ]; then
        $BUILDER tag "$IMG" "${REGISTRY}/${NAME}:latest"
        $BUILDER push "${REGISTRY}/${NAME}:latest"
    fi
}

[ "$PUSH_SLURM" = true ] && push_image "slurm-mcp-server"
[ "$PUSH_FLUX" = true ] && push_image "flux-mcp-server"

echo "Push complete!"

