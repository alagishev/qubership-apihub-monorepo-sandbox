#!/usr/bin/env python3
"""Map changed file paths to monorepo module IDs using tools/modules.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def load_modules(root: Path) -> dict:
    path = root / "tools" / "modules.yaml"
    if yaml is None or not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("modules", {})


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    modules = load_modules(root)
    paths = sys.stdin.read().splitlines()
    matched: set[str] = set()
    for line in paths:
        line = line.strip()
        if not line:
            continue
        for mod_id, cfg in modules.items():
            prefix = cfg.get("path", "")
            if prefix and (line == prefix or line.startswith(prefix + "/")):
                matched.add(mod_id)
    for mod_id in sorted(matched):
        print(mod_id)


if __name__ == "__main__":
    main()
