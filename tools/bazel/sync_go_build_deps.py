#!/usr/bin/env python3
"""Sync go_library deps in BUILD.bazel from Go source imports.

In-tree labels use package-path targets (//pkg or //pkg/sub).
External go_deps use @repo//:go_default_library or @repo//sub:go_default_library.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

IMPORT_BLOCK = re.compile(r"import\s+\((.*?)\)", re.DOTALL)
IMPORT_LINE = re.compile(r'(?:[a-zA-Z0-9_]+)?\s*"([^"]+)"')
IMPORT_SINGLE = re.compile(r'import\s+(?:[a-zA-Z0-9_]+\s+)?"([^"]+)"')
GO_LIBRARY = re.compile(r"go_library\(\s*\n(?P<body>.*?)\n\)", re.DOTALL)
SRCS_RE = re.compile(r"srcs\s*=\s*\[([^\]]*)\]", re.DOTALL)
DEPS_RE = re.compile(r"[ \t]*deps\s*=\s*\[[^\]]*\]\s*,?", re.DOTALL)
STRING_RE = re.compile(r'"([^"]+)"')

MODULE_ROOTS = {
    "github.com/Netcracker/qubership-apihub-commons-go": "qubership-apihub-commons-go",
    "github.com/Netcracker/qubership-apihub-backend/qubership-apihub-service": (
        "qubership-apihub-backend/qubership-apihub-service"
    ),
    "github.com/Netcracker/qubership-api-linter-service": (
        "qubership-api-linter-service/qubership-api-linter-service"
    ),
    "github.com/Netcracker/qubership-apihub-agents-backend": (
        "qubership-apihub-agents-backend/qubership-apihub-agents-backend"
    ),
}

EXTERNAL_MODULES = {
    "github.com/asaiyusuke/jsonpath/v2": "com_github_asaiyusuke_jsonpath_v2",
    "github.com/AsaiYusuke/jsonpath/v2": "com_github_asaiyusuke_jsonpath_v2",
    "github.com/buraksezer/olric": "com_github_buraksezer_olric",
    "github.com/buraksezer/olric-cloud-plugin": "com_github_buraksezer_olric_cloud_plugin",
    "github.com/coreos/go-oidc/v3": "com_github_coreos_go_oidc_v3",
    "github.com/crewjam/saml": "com_github_crewjam_saml",
    "github.com/go-ldap/ldap": "com_github_go_ldap_ldap",
    "github.com/go-pg/pg/v10": "com_github_go_pg_pg_v10",
    "github.com/go-playground/validator/v10": "com_github_go_playground_validator_v10",
    "github.com/google/uuid": "com_github_google_uuid",
    "github.com/gorilla/handlers": "com_github_gorilla_handlers",
    "github.com/gorilla/mux": "com_github_gorilla_mux",
    "github.com/gosimple/slug": "com_github_gosimple_slug",
    "github.com/iancoleman/orderedmap": "com_github_iancoleman_orderedmap",
    "github.com/invopop/jsonschema": "com_github_invopop_jsonschema",
    "github.com/mark3labs/mcp-go": "com_github_mark3labs_mcp_go",
    "github.com/minio/minio-go/v7": "com_github_minio_minio_go_v7",
    "github.com/mitchellh/mapstructure": "com_github_mitchellh_mapstructure",
    "github.com/openai/openai-go/v3": "com_github_openai_openai_go_v3",
    "github.com/pkg/errors": "com_github_pkg_errors",
    "github.com/prometheus/client_golang": "com_github_prometheus_client_golang",
    "github.com/robfig/cron/v3": "com_github_robfig_cron_v3",
    "github.com/russellhaering/goxmldsig": "com_github_russellhaering_goxmldsig",
    "github.com/shaj13/go-guardian/v2": "com_github_shaj13_go_guardian_v2",
    "github.com/shaj13/libcache": "com_github_shaj13_libcache",
    "github.com/sirupsen/logrus": "com_github_sirupsen_logrus",
    "github.com/spf13/viper": "com_github_spf13_viper",
    "github.com/stretchr/testify": "com_github_stretchr_testify",
    "github.com/x-cray/logrus-prefixed-formatter": "com_github_x_cray_logrus_prefixed_formatter",
    "github.com/xuri/excelize/v2": "com_github_xuri_excelize_v2",
    "github.com/zeebo/xxh3": "com_github_zeebo_xxh3",
    "gopkg.in/natefinch/lumberjack.v2": "in_gopkg_natefinch_lumberjack_v2",
    "gopkg.in/resty.v1": "in_gopkg_resty_v1",
    "gopkg.in/square/go-jose.v2": "in_gopkg_square_go_jose_v2",
    "gopkg.in/yaml.v3": "in_gopkg_yaml_v3",
    "golang.org/x/crypto": "org_golang_x_crypto",
    "golang.org/x/net": "org_golang_x_net",
    "golang.org/x/oauth2": "org_golang_x_oauth2",
    "golang.org/x/sync": "org_golang_x_sync",
    "golang.org/x/time": "org_golang_x_time",
}


def parse_imports(content: str) -> set[str]:
    imports: set[str] = set()
    for m in IMPORT_BLOCK.finditer(content):
        for path in IMPORT_LINE.findall(m.group(1)):
            imports.add(path)
    for path in IMPORT_SINGLE.findall(content):
        imports.add(path)
    return imports


def is_stdlib(imp: str) -> bool:
    if not imp or imp.startswith("."):
        return True
    return "." not in imp.split("/")[0]


def resolve_label(imp: str) -> str | None:
    if is_stdlib(imp):
        return None

    for prefix, root in sorted(MODULE_ROOTS.items(), key=lambda x: -len(x[0])):
        if imp == prefix:
            return f"//{root}"
        if imp.startswith(prefix + "/"):
            return f"//{root}/{imp[len(prefix) + 1 :]}"

    for prefix, repo in sorted(EXTERNAL_MODULES.items(), key=lambda x: -len(x[0])):
        if imp == prefix:
            return f"@{repo}//:go_default_library"
        if imp.startswith(prefix + "/"):
            return f"@{repo}//{imp[len(prefix) + 1 :]}:go_default_library"

    return None


def package_label(repo: Path, pkg_dir: Path) -> str | None:
    rel = pkg_dir.resolve().relative_to(repo.resolve()).as_posix()
    for root in MODULE_ROOTS.values():
        if rel == root or rel.startswith(root + "/"):
            return f"//{rel}"
    return None


def format_deps(deps: list[str]) -> str:
    if not deps:
        return "    deps = [],"
    lines = ["    deps = ["]
    for d in deps:
        lines.append(f'        "{d}",')
    lines.append("    ],")
    return "\n".join(lines)


def sync_build(repo: Path, build_path: Path) -> bool:
    text = build_path.read_text(encoding="utf-8")
    m = GO_LIBRARY.search(text)
    if not m:
        return False

    body = m.group("body")
    srcs_m = SRCS_RE.search(body)
    if not srcs_m:
        return False

    srcs = STRING_RE.findall(srcs_m.group(1))
    pkg_dir = build_path.parent
    self_label = package_label(repo, pkg_dir)

    imports: set[str] = set()
    for src in srcs:
        src_path = pkg_dir / src
        if src_path.is_file():
            imports |= parse_imports(src_path.read_text(encoding="utf-8", errors="ignore"))

    wanted: list[str] = []
    unresolved: list[str] = []
    for imp in sorted(imports):
        label = resolve_label(imp)
        if label is None:
            if not is_stdlib(imp):
                unresolved.append(imp)
            continue
        if self_label and (label == self_label or label.startswith(self_label + ":")):
            continue
        if label not in wanted:
            wanted.append(label)

    if unresolved:
        print(f"WARN {build_path.relative_to(repo)}: unresolved {unresolved}", file=sys.stderr)

    # Prefer package-dir target names over go_default_library for in-tree packages.
    if 'name = "go_default_library"' in body:
        text = text.replace('name = "go_default_library"', f'name = "{pkg_dir.name}"', 1)
        m = GO_LIBRARY.search(text)
        assert m is not None
        body = m.group("body")

    new_deps = format_deps(wanted)
    deps_m = DEPS_RE.search(body)
    if deps_m:
        new_body = body[: deps_m.start()] + new_deps + body[deps_m.end() :]
    else:
        new_body = body.rstrip() + "\n" + new_deps

    new_text = text[: m.start("body")] + new_body + text[m.end("body") :]
    if new_text != text:
        build_path.write_text(new_text, encoding="utf-8", newline="\n")
        print(f"updated {build_path.relative_to(repo)}")
        return True
    return False


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    roots = [
        repo / "qubership-apihub-commons-go",
        repo / "qubership-apihub-backend/qubership-apihub-service",
        repo / "qubership-api-linter-service/qubership-api-linter-service",
        repo / "qubership-apihub-agents-backend/qubership-apihub-agents-backend",
    ]
    changed = 0
    for root in roots:
        if not root.is_dir():
            continue
        for build in sorted(root.rglob("BUILD.bazel")):
            if sync_build(repo, build):
                changed += 1
    print(f"updated {changed} BUILD files")


if __name__ == "__main__":
    main()
