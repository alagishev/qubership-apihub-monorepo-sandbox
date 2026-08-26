#!/usr/bin/env bash
# Contract check: image build inputs exist (real push is tools/ci/docker_push_npm.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${RUNFILES_DIR:-}" ]]; then
  PKG="${RUNFILES_DIR}/_main/qubership-apihub-build-task-consumer"
  [[ -d "$PKG" ]] || PKG="${RUNFILES_DIR}/qubership_apihub_monorepo/qubership-apihub-build-task-consumer"
  [[ -d "$PKG" ]] || PKG="$ROOT"
else
  PKG="$ROOT"
fi
test -f "${PKG}/package.json"
test -f "${PKG}/Dockerfile.local"
echo "build-task-consumer image contract OK"
