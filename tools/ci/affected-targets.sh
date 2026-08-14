#!/usr/bin/env bash
# Print affected Bazel test targets (one per line) for local pre-push.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="${1:-origin/main}"
HEAD="${2:-HEAD}"
JSON="$(bash "$ROOT/tools/ci/detect-affected.sh" "$BASE" "$HEAD")"
echo "$JSON" | jq -r '.bazel_targets[]'
