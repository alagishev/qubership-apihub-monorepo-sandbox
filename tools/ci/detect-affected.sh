#!/usr/bin/env bash
# Detect affected Bazel targets and monorepo modules for CI.
# Usage: tools/ci/detect-affected.sh [base_sha] [head_sha]
# Outputs JSON to stdout: { "bazel_targets", "modules", "feature_tag", "oci_push_targets" }
#
# Primary strategy: git path → tools/modules.yaml (+ dependents).
# Optional: if bazel-diff and bazel are on PATH, refine bazel_targets via hash diff.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BASE_SHA="${1:-$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD origin/develop 2>/dev/null || echo "")}"
HEAD_SHA="${2:-HEAD}"

ALL_MODULES='["commons-go","api-diff","api-processor","build-task-consumer","ui","backend","linter","agents-backend"]'
ALL_OCI='["//qubership-apihub-backend:push","//qubership-api-linter-service:push","//qubership-apihub-agents-backend:push"]'

if [[ -z "$BASE_SHA" ]]; then
  jq -n \
    --argjson bazel_targets '["//..."]' \
    --argjson modules "$ALL_MODULES" \
    --argjson oci_push_targets "$ALL_OCI" \
    --arg feature_tag "dev" \
    '{bazel_targets: $bazel_targets, modules: $modules, feature_tag: $feature_tag, oci_push_targets: $oci_push_targets}'
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

BAZEL_TARGETS='[]'
OCI_PUSH='[]'
MODULES='[]'

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

# Expand module dependents from modules.yaml
if [[ -f "$ROOT/tools/ci/expand_modules.py" ]]; then
  EXPANDED=$(python3 "$ROOT/tools/ci/expand_modules.py" "$MODULES" 2>/dev/null || echo "$MODULES")
  [[ -n "$EXPANDED" ]] && MODULES="$EXPANDED"
fi

# Map modules → bazel package globs + oci_push targets
if [[ -f "$ROOT/tools/ci/modules_to_targets.py" ]]; then
  MAPPED=$(python3 "$ROOT/tools/ci/modules_to_targets.py" "$MODULES" 2>/dev/null || echo '{"bazel_targets":[],"oci_push_targets":[]}')
  BAZEL_TARGETS=$(echo "$MAPPED" | jq -c '.bazel_targets')
  OCI_PUSH=$(echo "$MAPPED" | jq -c '.oci_push_targets')
elif [[ -f "$ROOT/tools/ci/modules_to_oci.py" ]]; then
  OCI_PUSH=$(python3 "$ROOT/tools/ci/modules_to_oci.py" "$MODULES" 2>/dev/null || echo '[]')
fi

# Optional bazel-diff refinement when both tools are available
if command -v bazel >/dev/null 2>&1 && command -v bazel-diff >/dev/null 2>&1 && [[ -f "$ROOT/MODULE.bazel" ]]; then
  HASH_DIR=$(mktemp -d)
  trap 'rm -rf "$HASH_DIR"' EXIT
  bazel-diff generate-hashes -w "$ROOT" -b "$BASE_SHA" -o "$HASH_DIR/starting.json" 2>/dev/null || true
  bazel-diff generate-hashes -w "$ROOT" -b "$HEAD_SHA" -o "$HASH_DIR/final.json" 2>/dev/null || true
  if [[ -f "$HASH_DIR/starting.json" && -f "$HASH_DIR/final.json" ]]; then
    IMPACTED=$(bazel-diff get-impacted-targets -sh "$HASH_DIR/starting.json" -fh "$HASH_DIR/final.json" 2>/dev/null || echo "")
    if [[ -n "$IMPACTED" ]]; then
      BAZEL_TARGETS=$(echo "$IMPACTED" | jq -R -s 'split("\n") | map(select(length > 0))')
    fi
  fi
fi

# No module hit (e.g. only root CI/docs) → skip product builds; still emit empty lists
# If CI/tooling changed, callers may still want a smoke test — leave targets empty.

jq -n \
  --argjson bazel_targets "$BAZEL_TARGETS" \
  --argjson modules "$MODULES" \
  --argjson oci_push_targets "$OCI_PUSH" \
  --arg feature_tag "$FEATURE_TAG" \
  '{bazel_targets: $bazel_targets, modules: $modules, feature_tag: $feature_tag, oci_push_targets: $oci_push_targets}'
