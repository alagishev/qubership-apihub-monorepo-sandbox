#!/usr/bin/env python3
"""Small GitHub REST and GraphQL helpers for release-note generation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

GITHUB_REST = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"


def github_token() -> str:
    return (
        os.getenv("GITHUB_PROJECT_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_TOKEN")
        or ""
    )


def _headers(token: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "qubership-apihub-release-notes",
    }
    if extra:
        headers.update(extra)
    return headers


def rest_get(url: str, token: str) -> Any:
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub REST {exc.code} for {url}: {body}") from exc


def graphql(query: str, variables: dict, token: str) -> dict:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GITHUB_GRAPHQL,
        data=payload,
        headers=_headers(token, {"Content-Type": "application/json", "GraphQL-Features": "issue_types"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL HTTP {exc.code}: {body}") from exc
    if data.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {data['errors']}")
    return data["data"]
