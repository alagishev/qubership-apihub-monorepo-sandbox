#!/usr/bin/env bash
# Run Gazelle for Go packages (Linux / Git Bash / WSL).
# Avoids `bazel run //:gazelle-*` Windows launcher issues and full-repo indexing hangs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TARGET="${1:-all}"

bazel build --config=go-only //:gazelle_bin
GAZELLE="$(find -L bazel-bin -name 'gazelle_bin' -o -name 'gazelle_bin.exe' 2>/dev/null | head -1)"
if [[ -z "$GAZELLE" ]]; then
  echo "gazelle_bin not found under bazel-bin" >&2
  exit 1
fi

run_one() {
  local prefix="$1"
  local path="$2"
  echo "==> gazelle update $path"
  "$GAZELLE" update \
    -index=lazy \
    -repo_root="$ROOT" \
    -go_prefix="$prefix" \
    -go_naming_convention=import \
    -external=external \
    "$path"
}

case "$TARGET" in
  commons-go|commons)
    run_one "github.com/Netcracker/qubership-apihub-commons-go" "qubership-apihub-commons-go"
    ;;
  backend)
    run_one "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service" \
      "qubership-apihub-backend/qubership-apihub-service"
    ;;
  linter)
    run_one "github.com/Netcracker/qubership-api-linter-service" \
      "qubership-api-linter-service/qubership-api-linter-service"
    ;;
  agents|agents-backend)
    run_one "github.com/Netcracker/qubership-apihub-agents-backend" \
      "qubership-apihub-agents-backend/qubership-apihub-agents-backend"
    ;;
  all)
    run_one "github.com/Netcracker/qubership-apihub-commons-go" "qubership-apihub-commons-go"
    run_one "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service" \
      "qubership-apihub-backend/qubership-apihub-service"
    run_one "github.com/Netcracker/qubership-api-linter-service" \
      "qubership-api-linter-service/qubership-api-linter-service"
    run_one "github.com/Netcracker/qubership-apihub-agents-backend" \
      "qubership-apihub-agents-backend/qubership-apihub-agents-backend"
    ;;
  *)
    echo "Usage: $0 [all|commons-go|backend|linter|agents-backend]" >&2
    exit 2
    ;;
esac

# Fill any deps Gazelle cannot resolve (e.g. renamed olric module path).
python3 "$ROOT/tools/bazel/sync_go_build_deps.py"
echo "Done. Try: bazel build --config=go-only //qubership-apihub-backend/qubership-apihub-service:qubership-apihub-service"
