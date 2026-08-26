#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${RUNFILES_DIR:-}" ]]; then
  PKG="${RUNFILES_DIR}/_main/qubership-apihub-ui"
  [[ -d "$PKG" ]] || PKG="${RUNFILES_DIR}/qubership_apihub_monorepo/qubership-apihub-ui"
  [[ -d "$PKG" ]] || PKG="$ROOT"
else
  PKG="$ROOT"
fi
test -f "${PKG}/package.json"
test -f "${PKG}/Dockerfile.local"
echo "apihub-ui image contract OK"
