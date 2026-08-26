#!/usr/bin/env bash
# Compute Docker/feature image tag for CI (mirrors qubership-apihub-ci/docker-ci tag rules).
set -euo pipefail

# Prefer caller-provided tag (CI sets FEATURE_TAG for pull_request).
if [[ -n "${FEATURE_TAG:-}" ]]; then
  echo "$FEATURE_TAG"
  exit 0
fi

if [[ "${GITHUB_EVENT_NAME:-}" == "pull_request" ]]; then
  # github.event.number must be exported as GITHUB_EVENT_NUMBER by the workflow.
  echo "pull-${GITHUB_EVENT_NUMBER:?GITHUB_EVENT_NUMBER required for pull_request}-merge"
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
