"""GitHub REST API client for fetching PR metadata and diffs."""

import re
from typing import Optional, Tuple

import httpx

from backend.config import settings
from backend.models import PRMetadata


def parse_pr_url(url: str) -> Tuple[str, str, int]:
    """Extract owner, repo, and PR number from a GitHub PR URL.

    Supports formats:
      - https://github.com/owner/repo/pull/123
      - http://github.com/owner/repo/pull/123
      - github.com/owner/repo/pull/123
    """
    pattern = r"(?:https?://)?github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, url.strip())
    if not match:
        raise ValueError(
            f"Invalid GitHub PR URL: {url}\n"
            "Expected format: https://github.com/owner/repo/pull/123"
        )
    return match.group(1), match.group(2), int(match.group(3))


def _get_headers() -> dict:
    """Build request headers, including auth token if available."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "CodeSentinel-AI-Review-Agent",
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


async def fetch_pr_metadata(owner: str, repo: str, pr_number: int) -> PRMetadata:
    """Fetch PR metadata (title, author, description, branches)."""
    url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_get_headers())
        response.raise_for_status()
        data = response.json()

    return PRMetadata(
        url=data.get("html_url", ""),
        title=data.get("title", ""),
        author=data.get("user", {}).get("login", ""),
        description=data.get("body", "") or "",
        base_branch=data.get("base", {}).get("ref", ""),
        head_branch=data.get("head", {}).get("ref", ""),
        repo_full_name=f"{owner}/{repo}",
        pr_number=pr_number,
        files_changed=data.get("changed_files", 0),
    )


async def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """Fetch the raw unified diff for a PR."""
    url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = _get_headers()
    headers["Accept"] = "application/vnd.github.v3.diff"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


async def fetch_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Fetch the list of changed files with patches."""
    url = f"{settings.GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"

    all_files = []
    page = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            response = await client.get(
                url,
                headers=_get_headers(),
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            files = response.json()

            if not files:
                break

            all_files.extend(files)
            page += 1

            if len(files) < 100:
                break

    return all_files
