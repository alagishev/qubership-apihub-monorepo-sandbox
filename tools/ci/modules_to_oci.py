#!/usr/bin/env python3
"""Map module IDs to oci_push Bazel targets from tools/modules.yaml."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "tools" / "modules.yaml"
    raw = sys.argv[1] if len(sys.argv) > 1 else "[]"
    try:
        module_ids = json.loads(raw)
    except json.JSONDecodeError:
        module_ids = []

    targets: list[str] = []
    if yaml and path.exists():
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        modules = data.get("modules", {})
        for mod_id in module_ids:
            cfg = modules.get(mod_id, {})
            push = cfg.get("oci_push")
            if push:
                targets.append(push)

    print(json.dumps(sorted(set(targets))))


if __name__ == "__main__":
    main()
