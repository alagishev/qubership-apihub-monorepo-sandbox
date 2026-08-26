#!/usr/bin/env python3
"""Generate global application release notes from GitHub Project/Sprint data."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from tools.ci.compute_release_plan import bump_version, highest_bump
from tools.ci.github_api import github_token, graphql

DEFAULT_PROJECT_URL = "https://github.com/orgs/Netcracker/projects/9"
STATUS_FILTER = {"Done", "In Test"}
ITEMS_QUERY = """
query(
  $owner: String!,
  $projectNumber: Int!,
  $pageSize: Int = 100,
  $cursor: String,
  $labelLimit: Int = 5,
  $prLimit: Int = 5
) {
  organization(login: $owner) {
    projectV2(number: $projectNumber) {
      items(first: $pageSize, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          statusField: fieldValueByName(name: "Status") {
            __typename
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          sprintField: fieldValueByName(name: "Sprint") {
            __typename
            ... on ProjectV2ItemFieldIterationValue { title }
          }
          prField: fieldValueByName(name: "Pull requests") {
            __typename
            ... on ProjectV2ItemFieldPullRequestValue {
              pullRequests(first: $prLimit) {
                nodes {
                  number
                  title
                  url
                  author { login }
                }
              }
            }
          }
          content {
            __typename
            ... on Issue {
              number
              title
              url
              issueType { name }
              parent { title url }
              closedByPullRequestsReferences(first: $prLimit, includeClosedPrs: true) {
                nodes {
                  number
                  title
                  url
                  author { login }
                }
              }
            }
            ... on PullRequest {
              number
              title
              url
              author { login }
            }
          }
        }
      }
    }
  }
}
"""


def compute_next_global_version(previous_version: str, bumps: list[str]) -> str:
    return bump_version(previous_version, highest_bump(bumps))


def build_released_modules_section(released_modules: dict[str, str]) -> str:
    lines = ["## Released modules", ""]
    for module_id, version in released_modules.items():
        lines.append(f"- `{module_id}` -> `{version}`")
    return "\n".join(lines)


def _markdown_table(rows: list[str]) -> str:
    if not rows:
        return ""
    header = "| Work item | Name | Author | Epic |\n|-----------|------|--------|------|"
    return header + "\n" + "\n".join(rows)


def render_global_release_notes(
    version: str,
    sprint_name: str,
    released_modules: dict[str, str],
    images: list[str],
    features: list[str],
    bugfixes: list[str],
    other: list[str],
    docs_repo: str = "https://github.com/Netcracker/qubership-apihub",
) -> str:
    images_block = "\n".join(images) if images else "_No container images in this release._"
    return "\n".join(
        [
            f"Release Notes: {version}",
            "",
            f"Sprint: `{sprint_name}`",
            "",
            "### Artifacts",
            "",
            "#### Docker images",
            "",
            images_block,
            "",
            build_released_modules_section(released_modules),
            "",
            f"### [Documentation]({docs_repo}/tree/{version}/docs)",
            "",
            "### Installation",
            "",
            f"- [Installation notes]({docs_repo}/blob/{version}/docs/installation-guide.md)",
            f"- docker-compose: {docs_repo}/tree/{version}/docker-compose/apihub-generic",
            f"- Helm chart: {docs_repo}/tree/{version}/helm-templates/qubership-apihub",
            "",
            "## Features and Improvements",
            "",
            _markdown_table(features) or "_No new features this release._",
            "",
            "## Bugfixes",
            "",
            _markdown_table(bugfixes) or "_No bugfixes this release._",
            "",
            "## Tech Improvements & Other Changes",
            "",
            _markdown_table(other) or "_No tech tasks or other changes this release._",
            "",
        ]
    )


def parse_project_url(url: str) -> tuple[str, int]:
    match = re.match(
        r"https://github\.com/(?:orgs|users)/([^/]+)/projects/(\d+)/?$",
        url.rstrip("/"),
    )
    if not match:
        raise ValueError(f"Unsupported GitHub project URL: {url}")
    return match.group(1), int(match.group(2))


def fetch_project_items(owner: str, project_number: int, token: str) -> list[dict]:
    items: list[dict] = []
    cursor = None
    while True:
        data = graphql(
            ITEMS_QUERY,
            {
                "owner": owner,
                "projectNumber": project_number,
                "pageSize": 100,
                "cursor": cursor,
                "prLimit": 5,
                "labelLimit": 5,
            },
            token,
        )
        project = (data.get("organization") or {}).get("projectV2")
        if not project:
            raise RuntimeError(
                f"GitHub Project {owner}/{project_number} was not found or is not readable"
            )
        page = project["items"]
        items.extend(page.get("nodes") or [])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return items


def _issue_row(content: dict, pr_nodes: list[dict]) -> str:
    parent = content.get("parent") or {}
    epic = f"[{parent['title']}]({parent['url']})" if parent.get("url") else ""
    pr_list = []
    seen = set()
    for pr in pr_nodes + (content.get("closedByPullRequestsReferences", {}).get("nodes") or []):
        url = pr.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        pr_list.append(pr)
    if pr_list:
        work_items = [f"Issue: <{content.get('url')}>"]
        names = [content.get("title") or ""]
        authors = []
        for pr in pr_list:
            work_items.append(f"PR: <{pr.get('url')}>")
            names.append(pr.get("title") or "")
            login = (pr.get("author") or {}).get("login")
            if login:
                authors.append("@" + login)
        work_item = "<br/><br/>".join(work_items)
        name_cell = "<br/><br/>".join(names)
        author_cell = "<br/><br/>".join(sorted(set(authors)))
        return f"| {work_item} | {name_cell} | {author_cell} | {epic} |"
    return f"| Issue: <{content.get('url')}> | {content.get('title')} |  | {epic} |"


def process_items(items: list[dict], sprint_name: str) -> dict[str, list[str]]:
    features: list[str] = []
    bugfixes: list[str] = []
    other: list[str] = []
    for node in items:
        status_node = node.get("statusField") or {}
        sprint_node = node.get("sprintField") or {}
        status_val = status_node.get("name")
        sprint_val = sprint_node.get("title")
        if sprint_val != sprint_name or status_val not in STATUS_FILTER:
            continue
        content = node.get("content") or {}
        content_type = content.get("__typename")
        pr_field = node.get("prField") or {}
        pr_nodes = []
        if pr_field.get("__typename") == "ProjectV2ItemFieldPullRequestValue":
            pr_nodes = pr_field.get("pullRequests", {}).get("nodes") or []
        if content_type == "Issue":
            row = _issue_row(content, pr_nodes)
            issue_type = ((content.get("issueType") or {}).get("name") or "").lower()
            if issue_type == "feature":
                features.append(row)
            elif issue_type == "bug":
                bugfixes.append(row)
            else:
                other.append(row)
        elif content_type == "PullRequest":
            author = (content.get("author") or {}).get("login") or ""
            other.append(
                f"| No Issue<br/><br/>PR: <{content.get('url')}> | "
                f"No Issue<br/><br/>{content.get('title')} | {author} |  |"
            )
    return {"Feature": features, "Bug": bugfixes, "Other": other}


def image_lines(plan_modules: list[dict]) -> list[str]:
    lines = []
    for item in plan_modules:
        image = item.get("image")
        version = item.get("version")
        if image and version:
            lines.append(f"{image}:{version}")
    return lines


def generate_global_release_notes(
    sprint_name: str,
    released_modules: dict[str, str],
    version: str,
    plan_modules: list[dict] | None = None,
    project_url: str | None = None,
    token: str | None = None,
) -> str:
    token = token or github_token()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to generate global release notes")
    project_url = (
        project_url
        or os.getenv("GITHUB_PROJECT_URL")
        or DEFAULT_PROJECT_URL
    )
    if not str(project_url).strip():
        project_url = DEFAULT_PROJECT_URL
    owner, number = parse_project_url(project_url)
    items = fetch_project_items(owner, number, token)
    categorized = process_items(items, sprint_name)
    return render_global_release_notes(
        version=version,
        sprint_name=sprint_name,
        released_modules=released_modules,
        images=image_lines(plan_modules or []),
        features=categorized["Feature"],
        bugfixes=categorized["Bug"],
        other=categorized["Other"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate global application release notes")
    parser.add_argument("--sprint-name", required=True)
    parser.add_argument("--plan-file", required=True)
    parser.add_argument("--output", default="-")
    parser.add_argument("--project-url")
    args = parser.parse_args()
    plan = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
    version = plan.get("next_global_version")
    if not version:
        raise SystemExit("Release plan has no next_global_version")
    body = generate_global_release_notes(
        sprint_name=args.sprint_name,
        released_modules=plan.get("released_modules") or {},
        version=version,
        plan_modules=plan.get("modules") or [],
        project_url=args.project_url,
    )
    if args.output == "-":
        sys.stdout.write(body)
        return
    Path(args.output).write_text(body, encoding="utf-8")


if __name__ == "__main__":
    main()
