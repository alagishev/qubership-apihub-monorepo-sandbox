#!/usr/bin/env python3
"""Compute which monorepo modules to release and which versions to assign."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[\w-]+)(?:\([^)]+\))?(?P<breaking>!)?:\s*"
)
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
GLOBAL_TAG_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def classify_bump(message: str) -> str:
    first = message.strip().splitlines()[0] if message.strip() else ""
    lowered = first.lower()
    if lowered.startswith("breaking"):
        return "major"
    match = CONVENTIONAL_RE.match(lowered)
    if match:
        if match.group("breaking"):
            return "major"
        if match.group("type") == "feat":
            return "minor"
        return "patch"
    if lowered.startswith("feat!"):
        return "major"
    if lowered.startswith("feat"):
        return "minor"
    return "patch"


def highest_bump(levels: Iterable[str]) -> str:
    found = list(levels)
    if "major" in found:
        return "major"
    if "minor" in found:
        return "minor"
    return "patch"


def expand_dependants(modules_cfg: dict, seeds: set[str]) -> set[str]:
    result = set(seeds)
    queue = list(seeds)
    while queue:
        current = queue.pop(0)
        for dep in modules_cfg.get(current, {}).get("dependents", []) or []:
            if dep not in result:
                result.add(dep)
                queue.append(dep)
    return result


def parse_semver(version: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(version.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(previous: str | None, level: str) -> str:
    if previous is None:
        if level == "major":
            return "1.0.0"
        if level == "minor":
            return "0.1.0"
        return "0.0.1"
    major, minor, patch = parse_semver(previous)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def version_from_module_tag(tag: str, prefix: str) -> str:
    if not tag.startswith(prefix):
        raise ValueError(f"Tag {tag} does not start with {prefix}")
    return tag[len(prefix) :]


def latest_matching_tag(tags: Iterable[str], prefix: str) -> str | None:
    matching: list[tuple[tuple[int, int, int], str]] = []
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        try:
            matching.append((parse_semver(version_from_module_tag(tag, prefix)), tag))
        except ValueError:
            continue
    if not matching:
        return None
    matching.sort(key=lambda item: item[0])
    return matching[-1][1]


def latest_global_tag(tags: Iterable[str]) -> str | None:
    matching: list[tuple[tuple[int, int, int], str]] = []
    for tag in tags:
        if not GLOBAL_TAG_RE.match(tag):
            continue
        matching.append((parse_semver(tag), tag))
    if not matching:
        return None
    matching.sort(key=lambda item: item[0])
    return matching[-1][1]


def topological_release_order(modules_cfg: dict, selected: Iterable[str]) -> list[str]:
    selected_set = set(selected)
    remaining = set(selected_set)
    ordered: list[str] = []
    while remaining:
        ready = []
        for module_id in remaining:
            upstreams = [
                other
                for other in remaining
                if module_id in (modules_cfg.get(other, {}).get("dependents") or [])
            ]
            if not upstreams:
                ready.append(module_id)
        if not ready:
            ready = sorted(remaining)
        ready.sort()
        current = ready[0]
        ordered.append(current)
        remaining.remove(current)
    return ordered


class GitRepo:
    def __init__(self, root: Path):
        self.root = root

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
            )
        return result.stdout

    def tags(self) -> list[str]:
        output = self._run("tag", "--list")
        return [line.strip() for line in output.splitlines() if line.strip()]

    def path_has_changes(self, previous_tag: str | None, module_path: str) -> bool:
        if previous_tag is None:
            return True
        output = self._run("diff", "--name-only", previous_tag, "HEAD", "--", module_path)
        return bool(output.strip())

    def commit_subjects(self, previous_tag: str | None, module_path: str) -> list[str]:
        rev_range = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
        output = self._run("log", "--format=%s", rev_range, "--", module_path)
        return [line.strip() for line in output.splitlines() if line.strip()]


def load_modules(root: Path) -> dict:
    path = root / "tools" / "modules.yaml"
    if yaml is None:
        raise RuntimeError("PyYAML is required to read tools/modules.yaml")
    if not path.exists():
        raise RuntimeError(f"Missing module registry: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    modules = data.get("modules")
    if not isinstance(modules, dict) or not modules:
        raise RuntimeError("tools/modules.yaml has no modules")
    return modules


def _upstream_reason(modules_cfg: dict, selected: set[str], module_id: str) -> str:
    upstreams = [
        other
        for other in selected
        if module_id in (modules_cfg.get(other, {}).get("dependents") or [])
    ]
    if upstreams:
        return "dependent of " + ", ".join(sorted(upstreams))
    return "dependent of upstream module"


def build_release_plan(
    release_mode: str,
    modules_cfg: dict,
    tags: list[str],
    git: GitRepo,
) -> dict:
    if release_mode not in {"changed", "all"}:
        raise ValueError(f"Unsupported release mode: {release_mode}")

    global_base = latest_global_tag(tags)
    direct: set[str] = set()
    for module_id, cfg in modules_cfg.items():
        prefix = cfg.get("release_tag")
        path = cfg.get("path")
        if not prefix or not path:
            raise RuntimeError(f"Module {module_id} is missing release_tag or path")
        previous_tag = latest_matching_tag(tags, prefix)
        compare_ref = previous_tag or global_base
        if release_mode == "all" or git.path_has_changes(compare_ref, path):
            direct.add(module_id)

    selected = expand_dependants(modules_cfg, direct)
    planned: list[dict] = []

    for module_id in topological_release_order(modules_cfg, selected):
        cfg = modules_cfg[module_id]
        prefix = cfg["release_tag"]
        path = cfg["path"]
        previous_tag = latest_matching_tag(tags, prefix)
        compare_ref = previous_tag or global_base
        previous_version = (
            version_from_module_tag(previous_tag, prefix) if previous_tag else None
        )
        subjects = git.commit_subjects(compare_ref, path)
        has_path_changes = git.path_has_changes(compare_ref, path)
        is_direct = module_id in direct and (has_path_changes or compare_ref is None)

        if is_direct and subjects:
            bump = highest_bump(classify_bump(subject) for subject in subjects)
            reason = "direct path changes"
        elif is_direct and previous_tag is None:
            bump = "minor"
            reason = "initial release"
        elif release_mode == "all" and module_id in direct and not has_path_changes:
            bump = "patch"
            reason = "release all"
        else:
            bump = "patch"
            reason = _upstream_reason(modules_cfg, selected, module_id)

        version = bump_version(previous_version, bump)
        planned.append(
            {
                "module_id": module_id,
                "path": path,
                "kind": cfg.get("kind"),
                "image": cfg.get("image"),
                "npm_name": cfg.get("npm_name"),
                "previous_tag": previous_tag,
                "compare_ref": compare_ref,
                "previous_version": previous_version,
                "bump": bump,
                "version": version,
                "next_tag": f"{prefix}{version}",
                "direct_changes": is_direct,
                "reason": reason,
            }
        )

    previous_global = latest_global_tag(tags)
    global_bump = highest_bump(item["bump"] for item in planned) if planned else "patch"
    next_global = bump_version(previous_global, global_bump) if planned else previous_global
    return {
        "release_mode": release_mode,
        "modules": planned,
        "released_modules": {item["module_id"]: item["version"] for item in planned},
        "global_bump": global_bump if planned else None,
        "previous_global_version": previous_global,
        "next_global_version": next_global,
        "reasons": {item["module_id"]: item["reason"] for item in planned},
        "matrix": [
            {"module_id": item["module_id"], "version": item["version"]}
            for item in planned
        ],
    }


def build_release_plan_from_root(release_mode: str, root: Path) -> dict:
    modules_cfg = load_modules(root)
    git = GitRepo(root)
    return build_release_plan(release_mode, modules_cfg, git.tags(), git)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute the monorepo release plan")
    parser.add_argument("--release-mode", choices=("changed", "all"), required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    plan = build_release_plan_from_root(args.release_mode, Path(args.repo_root).resolve())
    text = json.dumps(plan, indent=2)
    if args.output == "-":
        sys.stdout.write(text + "\n")
        return
    Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
