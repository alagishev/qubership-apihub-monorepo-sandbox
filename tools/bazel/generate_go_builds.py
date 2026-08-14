#!/usr/bin/env python3
"""Generate BUILD.bazel files for Go modules (minimal gazelle substitute)."""

from __future__ import annotations

import os
import re
from pathlib import Path

IMPORT_BLOCK = re.compile(r"import\s+\((.*?)\)", re.DOTALL)
IMPORT_LINE = re.compile(r'"([^"]+)"')
IMPORT_SINGLE = re.compile(r'import\s+"([^"]+)"')

MODULES = [
    {
        "root": "qubership-apihub-commons-go",
        "module": "github.com/Netcracker/qubership-apihub-commons-go",
        "prefix": "github.com/Netcracker/qubership-apihub-commons-go",
    },
    {
        "root": "qubership-apihub-backend/qubership-apihub-service",
        "module": "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service",
        "prefix": "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service",
        "binary": "qubership-apihub-service",
    },
    {
        "root": "qubership-api-linter-service/qubership-api-linter-service",
        "module": "github.com/Netcracker/qubership-api-linter-service",
        "prefix": "github.com/Netcracker/qubership-api-linter-service",
        "binary": "qubership-api-linter-service",
    },
    {
        "root": "qubership-apihub-agents-backend/qubership-apihub-agents-backend",
        "module": "github.com/Netcracker/qubership-apihub-agents-backend",
        "prefix": "github.com/Netcracker/qubership-apihub-agents-backend",
        "binary": "qubership-apihub-agents-backend",
    },
]

EXTERNAL_DEPS = {
    "github.com/gosimple/slug": "@com_github_gosimple_slug//:slug",
    "gopkg.in/yaml.v3": "@in_gopkg_yaml_v3//:yaml_v3",
}


def parse_imports(content: str) -> set[str]:
    imports: set[str] = set()
    for m in IMPORT_BLOCK.finditer(content):
        for path in IMPORT_LINE.findall(m.group(1)):
            imports.add(path)
    for path in IMPORT_SINGLE.findall(content):
        imports.add(path)
    return imports


def pkg_label(module_root: str, import_path: str, module: str, prefix: str) -> str | None:
    if import_path == module or import_path.startswith(module + "/"):
        rel = import_path[len(module) :].lstrip("/")
        if rel:
            return f"//{module_root}/{rel.replace('/', '/')}:{rel.split('/')[-1]}"
        return f"//{module_root}:{Path(module_root).name}"
    ext = EXTERNAL_DEPS.get(import_path)
    if ext:
        return ext
    if import_path.startswith("github.com/"):
        parts = import_path.split("/")
        if len(parts) >= 3:
            org_repo = f"com_github_{parts[1]}_{parts[2]}"
            for p in parts[3:]:
                org_repo += f"_{p.replace('-', '_').replace('.', '_')}"
            return f"@{org_repo}//:{parts[-1].replace('-', '_')}"
    if import_path.startswith("golang.org/x/"):
        rest = import_path.replace("/", "_").replace(".", "_").replace("-", "_")
        return f"@{rest}//:{import_path.split('/')[-1].replace('-', '_')}"
    if import_path.startswith("gopkg.in/"):
        slug = import_path.replace("/", "_").replace(".", "_").replace("-", "_")
        return f"@{slug}//:{import_path.split('/')[-1]}"
    return None


def collect_packages(root: Path, module_cfg: dict) -> dict[str, dict]:
    packages: dict[str, dict] = {}
    module_root = module_cfg["root"]
    for dirpath, _, files in os.walk(root):
        go_files = [f for f in files if f.endswith(".go")]
        if not go_files:
            continue
        rel = Path(dirpath).relative_to(root).as_posix()
        key = rel or "."
        srcs = [f for f in go_files if not f.endswith("_test.go")]
        tests = [f for f in go_files if f.endswith("_test.go")]
        imports: set[str] = set()
        for gf in go_files:
            imports |= parse_imports((Path(dirpath) / gf).read_text(encoding="utf-8", errors="ignore"))
        packages[key] = {"srcs": srcs, "tests": tests, "imports": imports}
    return packages


def write_build(module_cfg: dict, repo_root: Path) -> None:
    root = repo_root / module_cfg["root"]
    packages = collect_packages(root, module_cfg)
    module = module_cfg["module"]
    prefix = module_cfg["prefix"]
    module_root = module_cfg["root"]

    pkg_to_name: dict[str, str] = {}
    for key in packages:
        name = key.replace("/", "_").replace(".", "_") if key != "." else Path(module_root).name.replace("-", "_")
        if name == "qubership_apihub_service":
            name = "qubership_apihub_service"
        pkg_to_name[key] = name if name else "root"

    for key, data in packages.items():
        dir_path = root if key == "." else root / key
        lib_name = pkg_to_name[key] + "_lib" if module_cfg.get("binary") and key == "." else pkg_to_name[key]
        if key == "." and module_cfg.get("binary"):
            lib_name = Path(module_cfg["binary"]).name + "_lib"

        deps: list[str] = []
        for imp in sorted(data["imports"]):
            if imp == module:
                continue
            if imp.startswith(module + "/"):
                sub = imp[len(module) + 1 :]
                dep_key = sub if sub in packages else sub.split("/")[0]
                # walk up to find package
                found = None
                for pk in packages:
                    if imp == module or imp == f"{module}/{pk}" or (pk != "." and imp.endswith("/" + pk.replace("/", "/"))):
                        found = pk
                        break
                if imp.startswith(module + "/"):
                    rel = imp[len(module) + 1 :]
                    if rel in packages:
                        found = rel
                    else:
                        parts = rel.split("/")
                        for i in range(len(parts), 0, -1):
                            cand = "/".join(parts[:i])
                            if cand in packages:
                                found = cand
                                break
                if found is not None:
                    if found == "." and module_cfg.get("binary"):
                        deps.append(f":{Path(module_cfg['binary']).name}_lib")
                    else:
                        fn = pkg_to_name[found]
                        if found == "." and module_cfg.get("binary"):
                            fn = Path(module_cfg["binary"]).name + "_lib"
                        elif found != ".":
                            fn = pkg_to_name[found]
                        deps.append(f"//{module_root}/{found if found != '.' else ''}".rstrip("/") + f":{fn if not (found == '.' and module_cfg.get('binary')) else Path(module_cfg['binary']).name + '_lib'}")
            else:
                label = pkg_label(module_root, imp, module, prefix)
                if label and label not in deps:
                    deps.append(label)

        deps = sorted(set(d for d in deps if d))

        lines = ['load("@rules_go//go:defs.bzl", "go_library", "go_test")', ""]
        if key == "." and module_cfg.get("binary"):
            lines[0] += ', "go_binary"'

        lines.append('package(default_visibility = ["//visibility:public"])')
        lines.append("")

        lib_target = Path(module_cfg["binary"]).name + "_lib" if key == "." and module_cfg.get("binary") else pkg_to_name[key]
        lines.append("go_library(")
        lines.append(f'    name = "{lib_target}",')
        lines.append("    srcs = " + repr(sorted(data["srcs"])) + ",")
        lines.append(f'    importpath = "{module if key == "." else module + "/" + key}",')
        if deps:
            lines.append("    deps = " + repr(deps) + ",")
        lines.append(")")
        lines.append("")

        if data["tests"]:
            test_deps = [f":{lib_target}"]
            lines.append("go_test(")
            lines.append(f'    name = "{lib_target}_test",')
            lines.append("    srcs = " + repr(sorted(data["tests"])) + ",")
            lines.append(f'    embed = [":{lib_target}"],')
            lines.append("    deps = " + repr(test_deps) + ",")
            lines.append(")")
            lines.append("")

        if key == "." and module_cfg.get("binary"):
            lines.append("go_binary(")
            lines.append(f'    name = "{module_cfg["binary"]}",')
            lines.append(f'    embed = [":{lib_target}"],')
            lines.append(")")
            lines.append("")

        (dir_path / "BUILD.bazel").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    for mod in MODULES:
        write_build(mod, repo)
        print(f"Generated BUILD files under {mod['root']}")


if __name__ == "__main__":
    main()
