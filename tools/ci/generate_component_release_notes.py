#!/usr/bin/env python3
"""Generate per-module release notes from git history."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from tools.ci.compute_release_plan import GitRepo, latest_matching_tag, load_modules
from tools.ci.github_api import github_token, graphql

PR_QUERY = """
query($owner: String!, $repo: String!, $oid: GitObjectID!) {
  repository(owner: $owner, name: $repo) {
    object(oid: $oid) {
      ... on Commit {
        associatedPullRequests(first: 1) {
          nodes {
            number
            title
            url
            author { login }
            closingIssuesReferences(first: 10) {
              nodes {
                title
                url
                issueType { name }
                labels(first: 10) { nodes { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


def classify_section(message: str) -> str:
    first = message.strip().lower()
    if first.startswith("breaking") or first.startswith("feat"):
        return "Features"
    if first.startswith("fix") or first.startswith("bug"):
        return "Bugfixes"
    return "Other"


def render_dependent_only_notes(module_id: str, upstream_module: str, upstream_version: str) -> str:
    return (
        f"# {module_id}\n\n"
        "## Changed\n\n"
        f"- Release triggered by an upstream dependency update in `{upstream_module}` "
        f"to `{upstream_version}`.\n"
    )


def render_component_notes(
    module_id: str,
    version: str,
    previous_tag: str | None,
    next_tag: str,
    image: str | None,
    entries: list[dict],
    dependency_changes: str,
    repo_url: str = "",
) -> str:
    features = [item["line"] for item in entries if item["section"] == "Features"]
    bugfixes = [item["line"] for item in entries if item["section"] == "Bugfixes"]
    other = [item["line"] for item in entries if item["section"] == "Other"]
    docker_line = f"{image}:{version}" if image else "No container image for this module."
    changelog = "No previous module tag."
    if previous_tag and repo_url:
        changelog = f"{repo_url}/compare/{previous_tag}...{next_tag}"
    elif previous_tag:
        changelog = f"{previous_tag}...{next_tag}"
    return "\n".join(
        [
            f"# {next_tag}",
            "",
            "# Artifacts",
            "",
            "## Docker image" if image else "## Packages",
            "",
            docker_line,
            "",
            "# Release Notes",
            "",
            "## Features and Improvements",
            "",
            "\n".join(features) if features else "No new features or improvements.",
            "",
            "## Bugfixes",
            "",
            "\n".join(bugfixes) if bugfixes else "No bugfixes.",
            "",
            "## Tech Improvements & Tasks",
            "",
            "\n".join(other) if other else "No tech improvements or tasks.",
            "",
            "## Dependency Changes",
            "",
            dependency_changes,
            "",
            "## Full Changelog",
            "",
            changelog,
            "",
        ]
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _should_skip(title: str) -> bool:
    lowered = title.strip().lower()
    return "merge develop into master" in lowered or "merge develop into main" in lowered


def _repo_slug(root: Path) -> tuple[str, str]:
    env = os.getenv("GITHUB_REPOSITORY", "")
    if env.count("/") == 1:
        owner, repo = env.split("/", 1)
        return owner, repo
    remote = _git(root, "remote", "get-url", "origin").strip()
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", remote)
    if not match:
        raise RuntimeError(f"Cannot parse GitHub repository from origin: {remote}")
    return match.group(1), match.group(2)


def _commits_for_path(root: Path, previous_tag: str | None, module_path: str) -> list[dict]:
    rev_range = f"{previous_tag}..HEAD" if previous_tag else "HEAD"
    output = _git(root, "log", "--format=%H%x09%an%x09%s", rev_range, "--", module_path)
    commits = []
    for line in output.splitlines():
        sha, author, subject = line.split("\t", 2)
        if _should_skip(subject):
            continue
        commits.append({"sha": sha, "author": author, "subject": subject})
    return commits


def _pr_for_commit(owner: str, repo: str, sha: str, token: str) -> dict | None:
    data = graphql(PR_QUERY, {"owner": owner, "repo": repo, "oid": sha}, token)
    obj = data["repository"]["object"] or {}
    nodes = obj.get("associatedPullRequests", {}).get("nodes") or []
    return nodes[0] if nodes else None


def _section_from_issue(issue_type_name: str | None, labels: list[str]) -> str:
    if issue_type_name:
        lowered = issue_type_name.strip().lower()
        if lowered in {"feature", "feat"}:
            return "Features"
        if lowered == "bug":
            return "Bugfixes"
        return "Other"
    for label in labels:
        lowered = label.lower()
        if lowered in {"feature", "feat"}:
            return "Features"
        if lowered == "bug":
            return "Bugfixes"
    return "Other"


def collect_entries(root: Path, previous_tag: str | None, module_path: str) -> list[dict]:
    commits = _commits_for_path(root, previous_tag, module_path)
    token = github_token()
    owner = repo = ""
    if token:
        owner, repo = _repo_slug(root)
    entries: list[dict] = []
    seen_prs: set[int] = set()
    for commit in commits:
        pr = _pr_for_commit(owner, repo, commit["sha"], token) if token else None
        if pr and not _should_skip(pr.get("title") or ""):
            number = pr["number"]
            if number in seen_prs:
                continue
            seen_prs.add(number)
            author = (pr.get("author") or {}).get("login") or commit["author"]
            issues = pr.get("closingIssuesReferences", {}).get("nodes") or []
            if issues:
                for issue in issues:
                    labels = [node["name"] for node in issue.get("labels", {}).get("nodes", [])]
                    issue_type = (issue.get("issueType") or {}).get("name")
                    section = _section_from_issue(issue_type, labels)
                    line = (
                        f"- {pr['title']} by @{author} in {pr['url']} "
                        f"for issue ([{issue.get('title')}]({issue.get('url')}))"
                    )
                    entries.append({"section": section, "line": line})
            else:
                section = classify_section(pr.get("title") or commit["subject"])
                line = f"- {pr['title']} by @{author} in {pr['url']} (PR #{number})"
                entries.append({"section": section, "line": line})
            continue
        section = classify_section(commit["subject"])
        line = f"- {commit['subject']} by @{commit['author']} (direct commit)"
        entries.append({"section": section, "line": line})
    return entries


def _parse_go_mod_require(content: str) -> dict[str, str]:
    requires: dict[str, str] = {}
    in_block = False
    for raw in content.splitlines():
        line = raw.strip()
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            parts = line.split()
            if len(parts) >= 2:
                requires[parts[0]] = parts[1]
        elif line.startswith("require "):
            parts = line[len("require ") :].split()
            if len(parts) >= 2:
                requires[parts[0]] = parts[1]
    return requires


def _file_at_ref(root: Path, ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def diff_go_dependencies(root: Path, previous_tag: str | None, next_ref: str, module_path: str) -> str:
    go_mod = f"{module_path}/go.mod"
    if previous_tag is None:
        return "No previous release to compare dependencies against."
    old = _parse_go_mod_require(_file_at_ref(root, previous_tag, go_mod))
    new = _parse_go_mod_require(_file_at_ref(root, next_ref, go_mod))
    if not old and not new:
        return "No dependencies found in either go.mod."
    rows = []
    for module_name in sorted(set(old) | set(new)):
        old_ver, new_ver = old.get(module_name, ""), new.get(module_name, "")
        if old_ver != new_ver:
            rows.append(f"| {module_name} | {old_ver} | {new_ver} |")
    if not rows:
        return "No dependency changes."
    return "\n".join(["| Module | Old Version | New Version |", "|---|---|---|", *rows])


def generate_release_notes(
    root: Path,
    module_id: str,
    previous_tag: str | None,
    next_tag: str,
    module_path: str,
    version: str,
    image: str | None = None,
) -> str:
    entries = collect_entries(root, previous_tag, module_path)
    deps = diff_go_dependencies(root, previous_tag, "HEAD", module_path)
    try:
        owner, repo = _repo_slug(root)
        repo_url = f"https://github.com/{owner}/{repo}"
    except RuntimeError:
        repo_url = ""
    return render_component_notes(
        module_id=module_id,
        version=version,
        previous_tag=previous_tag,
        next_tag=next_tag,
        image=image,
        entries=entries,
        dependency_changes=deps,
        repo_url=repo_url,
    )


def _upstream_from_reason(reason: str) -> list[str]:
    prefix = "dependent of "
    if not reason.startswith(prefix):
        return []
    rest = reason[len(prefix) :]
    if rest == "upstream module":
        return []
    return [part.strip() for part in rest.split(",") if part.strip()]


def generate_notes_for_plan(root: Path, plan: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    released = plan.get("released_modules") or {}
    for item in plan.get("modules") or []:
        module_id = item["module_id"]
        reason = item.get("reason") or ""
        upstreams = _upstream_from_reason(reason)
        if not item.get("direct_changes") and upstreams:
            upstream = upstreams[0]
            body = render_dependent_only_notes(
                module_id, upstream, released.get(upstream, "unknown")
            )
        elif not item.get("direct_changes") and reason == "release all":
            body = (
                f"# {item['next_tag']}\n\n"
                "## Changed\n\n"
                "- Included because `release_mode=all`; there were no path changes since the previous release.\n"
            )
        else:
            body = generate_release_notes(
                root=root,
                module_id=module_id,
                previous_tag=item.get("compare_ref") or item.get("previous_tag"),
                next_tag=item["next_tag"],
                module_path=item["path"],
                version=item["version"],
                image=item.get("image"),
            )
        (output_dir / f"{module_id}.md").write_text(body, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate component release notes")
    parser.add_argument("--plan-file")
    parser.add_argument("--output-dir")
    parser.add_argument("--module-id")
    parser.add_argument("--previous-tag")
    parser.add_argument("--next-tag")
    parser.add_argument("--module-path")
    parser.add_argument("--version")
    parser.add_argument("--image")
    parser.add_argument("--output", default="-")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if args.plan_file:
        if not args.output_dir:
            raise SystemExit("--output-dir is required with --plan-file")
        plan = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        generate_notes_for_plan(root, plan, Path(args.output_dir))
        return
    required = [args.module_id, args.next_tag, args.module_path, args.version]
    if not all(required):
        raise SystemExit("module-id, next-tag, module-path and version are required")
    previous_tag = args.previous_tag or None
    if previous_tag is None:
        modules_cfg = load_modules(root)
        prefix = modules_cfg[args.module_id]["release_tag"]
        tags = [tag for tag in GitRepo(root).tags() if tag != args.next_tag]
        previous_tag = latest_matching_tag(tags, prefix)
    body = generate_release_notes(
        root=root,
        module_id=args.module_id,
        previous_tag=previous_tag,
        next_tag=args.next_tag,
        module_path=args.module_path,
        version=args.version,
        image=args.image,
    )
    if args.output == "-":
        sys.stdout.write(body)
        return
    Path(args.output).write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()
