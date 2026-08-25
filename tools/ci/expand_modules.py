#!/usr/bin/env python3
"""Expand module list with transitive dependents from tools/modules.yaml.

`dependents` on a module means consumers that must rebuild when it changes
(e.g. commons-go.dependents = [backend, linter, agents-backend]).
"""

from __future__ import annotations

import json
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


def expand(modules_cfg: dict, seeds: set[str]) -> list[str]:
    result = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop(0)
        cfg = modules_cfg.get(current, {})
        for dep in cfg.get("dependents", []) or []:
            if dep not in result:
                result.add(dep)
                queue.append(dep)
    return sorted(result)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    modules_cfg = load_modules(root)
    raw = sys.argv[1] if len(sys.argv) > 1 else "[]"
    try:
        seeds = set(json.loads(raw))
    except json.JSONDecodeError:
        seeds = set()
    print(json.dumps(expand(modules_cfg, seeds)))


if __name__ == "__main__":
    main()
