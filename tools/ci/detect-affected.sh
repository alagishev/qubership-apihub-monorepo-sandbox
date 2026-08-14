#!/usr/bin/env bash
# Detect affected Bazel targets and monorepo modules for CI.
# Usage: tools/ci/detect-affected.sh [base_sha] [head_sha]
# Outputs JSON to stdout: { "bazel_targets", "modules", "feature_tag", "oci_push_targets" }

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BASE_SHA="${1:-$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD origin/develop 2>/dev/null || echo "")}"
HEAD_SHA="${2:-HEAD}"

if [[ -z "$BASE_SHA" ]]; then
  echo '{"bazel_targets":["//..."],"modules":["commons-go","api-diff","api-processor","build-task-consumer","ui","backend","linter","agents-backend"],"feature_tag":"dev","oci_push_targets":["//qubership-apihub-backend:push","//qubership-api-linter-service:push","//qubership-apihub-agents-backend:push","//qubership-apihub-build-task-consumer:push","//qubership-apihub-ui:push"]}' >&1
  exit 0
fi

FEATURE_TAG="${FEATURE_TAG:-}"
if [[ -z "$FEATURE_TAG" ]]; then
  if [[ -n "${GITHUB_HEAD_REF:-}" ]]; then
    FEATURE_TAG="$(echo "$GITHUB_HEAD_REF" | sed 's/\//-/g')"
  elif [[ -n "${GITHUB_REF_NAME:-}" ]]; then
    FEATURE_TAG="$(echo "$GITHUB_REF_NAME" | sed 's/\//-/g')"
  else
    FEATURE_TAG="local-$(git rev-parse --short HEAD)"
  fi
fi

BAZEL_TARGETS='["//..."]'
OCI_PUSH='[]'
MODULES='[]'

if command -v bazel >/dev/null 2>&1 && [[ -f "$ROOT/MODULE.bazel" ]]; then
  HASH_DIR=$(mktemp -d)
  trap 'rm -rf "$HASH_DIR"' EXIT

  if command -v bazel-diff >/dev/null 2>&1; then
    bazel-diff generate-hashes -w "$ROOT" -b "$BASE_SHA" -o "$HASH_DIR/starting.json" 2>/dev/null || true
    bazel-diff generate-hashes -w "$ROOT" -b "$HEAD_SHA" -o "$HASH_DIR/final.json" 2>/dev/null || true
    if [[ -f "$HASH_DIR/starting.json" && -f "$HASH_DIR/final.json" ]]; then
      IMPACTED=$(bazel-diff get-impacted-targets -sh "$HASH_DIR/starting.json" -fh "$HASH_DIR/final.json" 2>/dev/null || echo "")
      if [[ -n "$IMPACTED" ]]; then
        TARGET_LIST=$(echo "$IMPACTED" | jq -R -s 'split("\n") | map(select(length > 0))')
        BAZEL_TARGETS="$TARGET_LIST"
      fi
    fi
  fi

  # Map changed paths to modules via git diff when bazel-diff unavailable
  if [[ "$BAZEL_TARGETS" == '["//..."]' ]]; then
    CHANGED_PATHS=$(git diff --name-only "$BASE_SHA" "$HEAD_SHA" 2>/dev/null || echo "")
    if [[ -n "$CHANGED_PATHS" ]]; then
      MODULE_IDS=()
      while IFS= read -r mod; do
        [[ -n "$mod" ]] && MODULE_IDS+=("$mod")
      done < <(python3 "$ROOT/tools/ci/map_paths_to_modules.py" <<< "$CHANGED_PATHS" 2>/dev/null || true)
      if [[ ${#MODULE_IDS[@]} -gt 0 ]]; then
        MODULES=$(printf '%s\n' "${MODULE_IDS[@]}" | jq -R . | jq -s .)
      fi
    fi
  fi
fi

# Expand module dependents from modules.yaml
if command -v python3 >/dev/null 2>&1 && [[ -f "$ROOT/tools/ci/expand_modules.py" ]]; then
  EXPANDED=$(python3 "$ROOT/tools/ci/expand_modules.py" "$MODULES" 2>/dev/null || echo "$MODULES")
  [[ -n "$EXPANDED" ]] && MODULES="$EXPANDED"
fi

# Build oci_push target list from modules
if command -v python3 >/dev/null 2>&1 && [[ -f "$ROOT/tools/ci/modules_to_oci.py" ]]; then
  OCI_PUSH=$(python3 "$ROOT/tools/ci/modules_to_oci.py" "$MODULES" 2>/dev/null || echo '[]')
fi

jq -n \
  --argjson bazel_targets "$BAZEL_TARGETS" \
  --argjson modules "$MODULES" \
  --argjson oci_push_targets "$OCI_PUSH" \
  --arg feature_tag "$FEATURE_TAG" \
  '{bazel_targets: $bazel_targets, modules: $modules, feature_tag: $feature_tag, oci_push_targets: $oci_push_targets}'
