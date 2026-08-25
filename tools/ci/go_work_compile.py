#!/usr/bin/env python3
"""Compile Go packages for affected modules using go.work (cascade compile check)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# go.work module directories (repo-relative).
GO_MODULE_DIRS: dict[str, str] = {
    "commons-go": "qubership-apihub-commons-go",
    "backend": "qubership-apihub-backend/qubership-apihub-service",
    "linter": "qubership-api-linter-service/qubership-api-linter-service",
    "agents-backend": "qubership-apihub-agents-backend/qubership-apihub-agents-backend",
}


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    raw = sys.argv[1] if len(sys.argv) > 1 else "[]"
    try:
        module_ids = json.loads(raw)
    except json.JSONDecodeError:
        module_ids = []

    if yaml is None:
        print("pyyaml required", file=sys.stderr)
        sys.exit(1)

    with (root / "tools" / "modules.yaml").open(encoding="utf-8") as f:
        modules_cfg = (yaml.safe_load(f) or {}).get("modules", {})

    to_compile: list[str] = []
    for mod_id in module_ids:
        kind = modules_cfg.get(mod_id, {}).get("kind", "")
        if not kind.startswith("go"):
            continue
        rel = GO_MODULE_DIRS.get(mod_id)
        if not rel:
            continue
        # commons-go is covered by Bazel tests; compile only service modules here.
        if mod_id == "commons-go":
            continue
        to_compile.append(rel)

    for rel in sorted(set(to_compile)):
        path = root / rel
        if not (path / "go.mod").exists():
            print(f"skip {rel}: no go.mod", file=sys.stderr)
            continue
        print(f"go build ./... ({rel})")
        subprocess.run(
            ["go", "build", "./..."],
            cwd=path,
            check=True,
        )


if __name__ == "__main__":
    main()
