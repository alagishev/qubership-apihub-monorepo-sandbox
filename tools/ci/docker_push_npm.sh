#!/usr/bin/env bash
# Build and push npm service images using production Dockerfile.local flow.
# Usage: tools/ci/docker_push_npm.sh <module_id> <image_repo> <tag>
# Modules: build-task-consumer | ui
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

MODULE="${1:?module id}"
IMAGE="${2:?image repository}"
TAG="${3:?tag}"

case "$MODULE" in
  build-task-consumer)
    PKG="qubership-apihub-build-task-consumer"
    echo "Building $PKG (nest)..."
    pnpm --filter "@netcracker/qubership-apihub-build-task-consumer..." run build
    echo "Docker build+push $IMAGE:$TAG"
    docker build -f "$PKG/Dockerfile.local" -t "$IMAGE:$TAG" "$PKG"
    docker push "$IMAGE:$TAG"
    ;;
  ui)
    PKG="qubership-apihub-ui"
    echo "Building $PKG (lerna)..."
    pnpm --filter "@netcracker/qubership-apihub-ui..." run build
    echo "Docker build+push $IMAGE:$TAG"
    docker build -f "$PKG/Dockerfile.local" -t "$IMAGE:$TAG" "$PKG"
    docker push "$IMAGE:$TAG"
    ;;
  *)
    echo "Unknown npm image module: $MODULE" >&2
    exit 1
    ;;
esac
