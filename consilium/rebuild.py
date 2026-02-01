"""
Rebuild ledger from GitHub PR comments.

This module provides the ability to:
1. Fetch all Consilium comments from a repo's PRs
2. Validate hashes and chain integrity
3. Compare with local ledger
4. Rebuild ledger from scratch if needed
"""

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .ledger import Ledger, parse_comment


@dataclass
class RebuildResult:
    """Result of a rebuild operation."""
    success: bool
    entries_found: int
    entries_added: int
    errors: list[str]
    warnings: list[str]


class GitHubCommentFetcher:
    """
    Fetch Consilium comments from GitHub with pagination.

    Handles:
    - Rate limiting with backoff
    - Pagination
    - Incremental fetching (from last seen comment_id)
    - Timeouts
    """

    API_BASE = "https://api.github.com"
    CONSILIUM_MARKER = "CONSILIUM:BEGIN"
    DEFAULT_TIMEOUT = 30  # seconds
    MAX_RATE_LIMIT_WAIT = 300  # 5 minutes max wait for rate limit

    def __init__(self, token: str, owner: str, repo: str):
        self.token = token
        self.owner = owner
        self.repo = repo

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _handle_rate_limit(self, response: requests.Response) -> bool:
        """
        Handle rate limiting by waiting if necessary.

        Returns True if we should retry, False if we should give up.
        """
        if response.status_code != 403:
            return False

        remaining = response.headers.get("X-RateLimit-Remaining", "1")
        if remaining != "0":
            return False

        reset_time = int(response.headers.get("X-RateLimit-Reset", "0"))
        wait_time = max(0, reset_time - int(time.time())) + 1

        if wait_time <= self.MAX_RATE_LIMIT_WAIT:
            time.sleep(wait_time)
            return True

        return False

    def _get(self, endpoint: str, params: dict = None) -> requests.Response:
        """Make a GET request with rate limit handling and timeout."""
        url = f"{self.API_BASE}{endpoint}"

        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.DEFAULT_TIMEOUT
        )

        # Handle rate limiting with one retry
        if response.status_code == 403 and self._handle_rate_limit(response):
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )

        return response

    def _get_paginated(
        self,
        endpoint: str,
        params: dict = None,
        since_id: Optional[int] = None,
    ) -> list[dict]:
        """
        Fetch all pages of a paginated endpoint.

        If since_id is provided, uses GitHub's 'since' parameter for efficient
        incremental fetching when supported, otherwise filters client-side.
        """
        results = []
        params = params or {}
        params["per_page"] = 100  # Max allowed
        page = 1

        while True:
            params["page"] = page

            response = self._get(endpoint, params)
            response.raise_for_status()

            raw_data = response.json()
            if not raw_data:
                break

            # Filter by ID if needed (for endpoints that don't support 'since' by ID)
            data = raw_data
            if since_id:
                data = [item for item in raw_data if item.get("id", 0) > since_id]

            results.extend(data)
            page += 1

            # Stop if we got less than a full page (based on raw data, not filtered)
            if len(raw_data) < 100:
                break

        return results

    def fetch_consilium_comments(
        self,
        since_comment_id: Optional[int] = None
    ) -> list[dict]:
        """
        Fetch all Consilium comments from the repo.

        Args:
            since_comment_id: Only fetch comments after this ID (for incremental updates)

        Returns:
            List of comment dicts with parsed LedgerEntry, sorted by comment_id
        """
        # Fetch issue comments (PRs are issues in GitHub API)
        endpoint = f"/repos/{self.owner}/{self.repo}/issues/comments"
        params = {"sort": "created", "direction": "asc"}

        all_comments = self._get_paginated(endpoint, params, since_id=since_comment_id)

        # Filter for Consilium comments and parse
        consilium_comments = []
        for comment in all_comments:
            body = comment.get("body", "")
            if self.CONSILIUM_MARKER not in body:
                continue

            # Try to parse the entry
            entry = parse_comment(body)
            if entry:
                entry.comment_id = comment["id"]
                consilium_comments.append({
                    "comment_id": comment["id"],
                    "pr_number": self._extract_pr_number(comment),
                    "created_at": comment["created_at"],
                    "url": comment["html_url"],
                    "entry": entry,
                })

        # Sort by comment_id to ensure chronological order
        consilium_comments.sort(key=lambda x: x["comment_id"])

        return consilium_comments

    def _extract_pr_number(self, comment: dict) -> int:
        """Extract PR number from comment's issue_url."""
        # issue_url looks like: https://api.github.com/repos/owner/repo/issues/42
        issue_url = comment.get("issue_url", "")
        try:
            return int(issue_url.split("/")[-1])
        except (ValueError, IndexError):
            return 0


def rebuild_from_github(
    token: str,
    owner: str,
    repo: str,
    ledger_dir: str = "ledger",
    incremental: bool = True,
) -> RebuildResult:
    """
    Rebuild/verify ledger from GitHub comments.

    Args:
        token: GitHub API token
        owner: Repository owner
        repo: Repository name
        ledger_dir: Path to ledger directory
        incremental: If True, only fetch new comments since last entry

    Returns:
        RebuildResult with status and statistics
    """
    errors = []
    warnings = []

    # Initialize fetcher and ledger
    fetcher = GitHubCommentFetcher(token, owner, repo)
    ledger = Ledger(ledger_dir)
    ledger.init()

    # Determine starting point for incremental fetch
    since_comment_id = None
    if incremental:
        # Find the last comment_id we have
        for entry in ledger.iter_entries():
            if entry.comment_id:
                since_comment_id = entry.comment_id

    # Fetch comments from GitHub
    try:
        comments = fetcher.fetch_consilium_comments(since_comment_id)
    except requests.Timeout:
        return RebuildResult(
            success=False,
            entries_found=0,
            entries_added=0,
            errors=["GitHub API timeout - try again later"],
            warnings=[],
        )
    except requests.RequestException as e:
        return RebuildResult(
            success=False,
            entries_found=0,
            entries_added=0,
            errors=[f"GitHub API error: {e}"],
            warnings=[],
        )

    entries_added = 0

    for comment_data in comments:
        entry = comment_data["entry"]
        comment_id = comment_data["comment_id"]

        # Check for duplicates by comment_id
        existing = ledger.find_by_comment_id(comment_id)
        if existing:
            continue  # Already have this entry

        # Check for duplicates by source URL
        existing_by_source = ledger.find_by_source(entry.source)
        if existing_by_source:
            warnings.append(
                f"Duplicate source {entry.source}: "
                f"existing comment_id={existing_by_source.comment_id}, "
                f"new comment_id={comment_id}"
            )
            continue

        # Verify entry hash
        if not entry.verify():
            errors.append(f"Comment {comment_id}: hash verification failed")
            continue

        # Verify chain link
        expected_prev = ledger.get_head_hash()
        if entry.prev_hash != expected_prev:
            errors.append(
                f"Comment {comment_id}: chain broken "
                f"(expected prev_hash={expected_prev}, got {entry.prev_hash})"
            )
            # This is a critical error - chain is broken
            # Skip this entry but continue processing to report all errors
            continue

        # Append to ledger
        try:
            entry.comment_id = comment_id
            ledger.append(entry)
            entries_added += 1
        except ValueError as e:
            errors.append(f"Comment {comment_id}: {e}")

    return RebuildResult(
        success=len(errors) == 0,
        entries_found=len(comments),
        entries_added=entries_added,
        errors=errors,
        warnings=warnings,
    )


def verify_ledger_against_github(
    token: str,
    owner: str,
    repo: str,
    ledger_dir: str = "ledger",
) -> tuple[bool, list[str]]:
    """
    Verify local ledger matches GitHub comments.

    Returns (is_valid, list of discrepancies).
    """
    discrepancies = []

    fetcher = GitHubCommentFetcher(token, owner, repo)
    ledger = Ledger(ledger_dir)

    # First verify local chain
    is_valid, error = ledger.verify_chain()
    if not is_valid:
        discrepancies.append(f"Local chain invalid: {error}")
        return False, discrepancies

    # Fetch all comments
    try:
        comments = fetcher.fetch_consilium_comments()
    except requests.Timeout:
        discrepancies.append("GitHub API timeout")
        return False, discrepancies
    except requests.RequestException as e:
        discrepancies.append(f"GitHub API error: {e}")
        return False, discrepancies

    # Build map of comment_id -> entry from GitHub
    github_entries = {c["comment_id"]: c["entry"] for c in comments}

    # Check each local entry has matching GitHub comment
    for entry in ledger.iter_entries():
        if not entry.comment_id:
            discrepancies.append(f"Entry {entry.short_hash}: missing comment_id")
            continue

        github_entry = github_entries.get(entry.comment_id)
        if not github_entry:
            discrepancies.append(
                f"Entry {entry.short_hash}: comment_id {entry.comment_id} not found on GitHub"
            )
            continue

        # Compare hashes (full hash comparison)
        if entry.hash != github_entry.hash:
            discrepancies.append(
                f"Entry {entry.short_hash}: hash mismatch with GitHub "
                f"(local={entry.short_hash}, github={github_entry.short_hash})"
            )

    # Check for GitHub comments not in local ledger
    local_comment_ids = {e.comment_id for e in ledger.iter_entries() if e.comment_id}
    for comment_id, github_entry in github_entries.items():
        if comment_id not in local_comment_ids:
            discrepancies.append(
                f"GitHub comment {comment_id} not in local ledger "
                f"(hash={github_entry.short_hash})"
            )

    return len(discrepancies) == 0, discrepancies
