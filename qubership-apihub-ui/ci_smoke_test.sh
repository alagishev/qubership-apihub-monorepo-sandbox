#!/usr/bin/env bash
set -euo pipefail
PKG_JSON="${1:-}"
if [[ -z "$PKG_JSON" || ! -f "$PKG_JSON" ]]; then
  echo "package.json not found (arg='$PKG_JSON')" >&2
  exit 1
fi
NAME="$(sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$PKG_JSON" | head -n1)"
test -n "$NAME"
echo "apihub-ui package smoke OK ($NAME)"
