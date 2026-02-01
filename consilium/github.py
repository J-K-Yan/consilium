"""
GitHub API interaction for Consilium.

Handles:
- Parsing PR webhook payloads
- Fetching PR details (author, reviewers, approvers)
- Posting credit report comments with ledger entries
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

import requests

from .ledger import LedgerEntry, parse_comment


@dataclass
class PRInfo:
    """Information extracted from a GitHub PR."""
    number: int
    title: str
    author: str
    reviewers: list[str]
    approvers: list[str]
    url: str
    repo_owner: str
    repo_name: str
    merged: bool
    merged_at: Optional[str] = None

    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


class GitHubClient:
    """
    Client for GitHub API interactions.

    Usage:
        client = GitHubClient(token="ghp_xxx")
        pr_info = client.get_pr_info("owner", "repo", 123)
        client.post_comment("owner", "repo", 123, "Hello!")
    """

    API_BASE = "https://api.github.com"
    DEFAULT_TIMEOUT = 30  # seconds

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token required. Set GITHUB_TOKEN env var or pass token parameter.")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle rate limiting by waiting if necessary."""
        if response.status_code == 403:
            # Check if it's rate limiting
            remaining = response.headers.get("X-RateLimit-Remaining", "1")
            if remaining == "0":
                reset_time = int(response.headers.get("X-RateLimit-Reset", "0"))
                wait_time = max(0, reset_time - int(time.time())) + 1
                if wait_time <= 300:  # Only wait up to 5 minutes
                    time.sleep(wait_time)
                    return
            raise requests.HTTPError(f"Rate limited: {response.text}")

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Make a GET request to the GitHub API with rate limit handling."""
        url = f"{self.API_BASE}{endpoint}"
        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.DEFAULT_TIMEOUT
        )

        if response.status_code == 403:
            self._handle_rate_limit(response)
            # Retry once after rate limit handling
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )

        response.raise_for_status()
        return response.json()

    def _get_paginated(self, endpoint: str, params: dict = None) -> list[dict]:
        """Fetch all pages of a paginated endpoint."""
        results = []
        params = params or {}
        params["per_page"] = 100  # Max allowed
        page = 1

        while True:
            params["page"] = page
            data = self._get(endpoint, params)

            if not data:
                break

            results.extend(data)
            page += 1

            # Stop if we got less than a full page
            if len(data) < 100:
                break

        return results

    def list_issue_comments(self, owner: str, repo: str, issue_number: int) -> list[dict]:
        """Fetch all comments on a PR/issue."""
        return self._get_paginated(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        )

    def find_consilium_entry(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        source_url: str,
    ) -> Optional[LedgerEntry]:
        """
        Find an existing Consilium comment for a PR by source URL.

        Returns the parsed LedgerEntry if found, otherwise None.
        """
        comments = self.list_issue_comments(owner, repo, issue_number)
        for comment in comments:
            body = comment.get("body", "")
            entry = parse_comment(body)
            if entry and entry.source == source_url:
                entry.comment_id = comment.get("id")
                return entry
        return None

    def _post(self, endpoint: str, data: dict) -> dict:
        """Make a POST request to the GitHub API."""
        url = f"{self.API_BASE}{endpoint}"
        response = requests.post(
            url,
            headers=self._headers(),
            json=data,
            timeout=self.DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        return response.json()

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """
        Get information about a pull request.

        Uses latest review state per user (not "any approval ever").
        A user who approved then requested changes is NOT an approver.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number

        Returns:
            PRInfo with author, reviewers, and approvers
        """
        # Get PR details
        pr_data = self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")

        author = pr_data["user"]["login"]
        merged = pr_data.get("merged", False)
        merged_at = pr_data.get("merged_at")

        # Get all reviews (paginated) to find reviewers and approvers
        reviews = self._get_paginated(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")

        # Track latest review state per user
        # Reviews are returned in chronological order, so later ones override earlier
        latest_review_state: dict[str, str] = {}

        for review in reviews:
            if not review.get("user"):
                continue

            reviewer = review["user"]["login"]
            if reviewer == author:
                continue  # Skip self-reviews

            state = review.get("state", "")
            # Only track meaningful states (ignore COMMENTED, PENDING)
            if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                latest_review_state[reviewer] = state

        # Build reviewer and approver lists from latest states
        reviewers = set(latest_review_state.keys())
        approvers = {
            user for user, state in latest_review_state.items()
            if state == "APPROVED"
        }

        return PRInfo(
            number=pr_number,
            title=pr_data["title"],
            author=author,
            reviewers=list(reviewers),
            approvers=list(approvers),
            url=pr_data["html_url"],
            repo_owner=owner,
            repo_name=repo,
            merged=merged,
            merged_at=merged_at,
        )

    def post_comment(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        """
        Post a comment on a PR or issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: PR/issue number
            body: Comment body (markdown)

        Returns:
            API response with comment details
        """
        return self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            {"body": body}
        )

    def post_credit_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        entry: LedgerEntry,
    ) -> tuple[dict, int]:
        """
        Post a credit distribution comment with ledger entry.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            entry: LedgerEntry to post

        Returns:
            Tuple of (API response, comment_id)
        """
        body = entry.to_comment_body()
        response = self.post_comment(owner, repo, pr_number, body)
        comment_id = response["id"]
        return response, comment_id


def parse_webhook_payload(payload: dict) -> Optional[PRInfo]:
    """
    Parse a GitHub webhook payload for PR events.

    Args:
        payload: The webhook payload dictionary

    Returns:
        PRInfo if this is a merged PR event, None otherwise
    """
    # Check if this is a PR event
    if "pull_request" not in payload:
        return None

    # Check if the PR was merged
    action = payload.get("action")
    pr_data = payload["pull_request"]

    if action != "closed" or not pr_data.get("merged"):
        return None

    # Extract repo info
    repo = payload["repository"]
    repo_parts = repo["full_name"].split("/")

    # Extract author
    author = pr_data["user"]["login"]

    # Note: Webhook payload doesn't include full review info
    # We'll need to fetch reviews separately
    return PRInfo(
        number=pr_data["number"],
        title=pr_data["title"],
        author=author,
        reviewers=[],  # Need to fetch separately
        approvers=[],  # Need to fetch separately
        url=pr_data["html_url"],
        repo_owner=repo_parts[0],
        repo_name=repo_parts[1],
        merged=True,
        merged_at=pr_data.get("merged_at"),
    )


def process_merged_pr(
    payload: dict,
    client: Optional[GitHubClient] = None,
) -> Optional[PRInfo]:
    """
    Process a merged PR webhook and get full PR info.

    Args:
        payload: GitHub webhook payload
        client: GitHubClient instance (creates one if not provided)

    Returns:
        PRInfo with full details, or None if not a merged PR
    """
    # Parse basic info from webhook
    basic_info = parse_webhook_payload(payload)
    if basic_info is None:
        return None

    # Create client if needed
    if client is None:
        client = GitHubClient()

    # Fetch full PR info including reviews
    return client.get_pr_info(
        basic_info.repo_owner,
        basic_info.repo_name,
        basic_info.number,
    )
