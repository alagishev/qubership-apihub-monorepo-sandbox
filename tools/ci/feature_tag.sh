#!/usr/bin/env bash
# Compute Docker/feature image tag for CI (mirrors qubership-apihub-ci/docker-ci tag rules).
set -euo pipefail

if [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
  echo "pull-${GITHUB_EVENT_NUMBER}-merge"
  exit 0
fi

REF="${GITHUB_REF_NAME:-${GITHUB_REF##*/}}"
case "$REF" in
  develop) echo "dev" ;;
  release) echo "next" ;;
  *)
    echo "$REF" | sed 's/\//-/g'
    ;;
esac
