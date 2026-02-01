"""
Main handler for Consilium PR events.

This module ties together:
- GitHub webhook processing
- Credit calculation
- Ledger management
- Comment posting

Usage:
    handler = ConsiliumHandler(
        github_token="ghp_xxx",
        owner="owner",
        repo="repo",
    )
    result = handler.process_webhook(payload)
"""

import os
from dataclasses import dataclass
from typing import Optional

from .credit import CreditCalculator
from .github import GitHubClient, PRInfo, parse_webhook_payload
from .ledger import Ledger, LedgerEntry


@dataclass
class ProcessResult:
    """Result of processing a PR event."""
    success: bool
    pr_number: Optional[int] = None
    entry: Optional[LedgerEntry] = None
    comment_id: Optional[int] = None
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


class ConsiliumHandler:
    """
    Main handler for Consilium events.

    Processes PR merges and creates credit distributions.
    """

    def __init__(
        self,
        github_token: str,
        owner: str,
        repo: str,
        ledger_dir: str = "ledger",
        calculator: Optional[CreditCalculator] = None,
    ):
        self.owner = owner
        self.repo = repo
        self.client = GitHubClient(token=github_token)
        self.ledger = Ledger(ledger_dir)
        if calculator is None:
            config_path = os.environ.get("CONSILIUM_CONFIG", "consilium.yaml")
            if os.path.exists(config_path):
                self.calculator = CreditCalculator.from_config(config_path)
            else:
                self.calculator = CreditCalculator()
        else:
            self.calculator = calculator

        # Initialize ledger
        self.ledger.init()

    def process_webhook(self, payload: dict) -> ProcessResult:
        """
        Process a GitHub webhook payload.

        Args:
            payload: The webhook payload from GitHub

        Returns:
            ProcessResult indicating success/failure
        """
        # Parse the webhook to check if it's a merged PR
        basic_info = parse_webhook_payload(payload)
        if basic_info is None:
            return ProcessResult(
                success=True,
                skipped=True,
                skip_reason="Not a merged PR event",
            )

        # Fetch full PR info
        pr_info = self.client.get_pr_info(
            self.owner,
            self.repo,
            basic_info.number,
        )

        return self.process_pr(pr_info)

    def process_pr(self, pr_info: PRInfo) -> ProcessResult:
        """
        Process a merged PR and distribute credit.

        Args:
            pr_info: Information about the PR

        Returns:
            ProcessResult indicating success/failure
        """
        # Check for duplicate processing
        if self.ledger.find_by_source(pr_info.url):
            return ProcessResult(
                success=True,
                pr_number=pr_info.number,
                skipped=True,
                skip_reason=f"PR {pr_info.number} already processed",
            )

        # Check for existing Consilium comment to avoid duplicate posts
        try:
            existing_entry = self.client.find_consilium_entry(
                self.owner,
                self.repo,
                pr_info.number,
                pr_info.url,
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                pr_number=pr_info.number,
                error=f"Failed to check existing comments: {e}",
            )

        if existing_entry:
            # Try to sync ledger if possible; otherwise instruct rebuild
            if not self.ledger.find_by_source(pr_info.url):
                if self.ledger.get_head_hash() == existing_entry.prev_hash:
                    try:
                        self.ledger.append(existing_entry)
                    except Exception as e:
                        return ProcessResult(
                            success=True,
                            pr_number=pr_info.number,
                            skipped=True,
                            skip_reason=(
                                f"PR {pr_info.number} already has Consilium comment "
                                f"{existing_entry.comment_id}; ledger append failed ({e}). "
                                "Run rebuild."
                            ),
                        )
                else:
                    return ProcessResult(
                        success=True,
                        pr_number=pr_info.number,
                        skipped=True,
                        skip_reason=(
                            f"PR {pr_info.number} already has Consilium comment "
                            f"{existing_entry.comment_id}; local ledger out of sync. "
                            "Run rebuild."
                        ),
                    )

            return ProcessResult(
                success=True,
                pr_number=pr_info.number,
                skipped=True,
                skip_reason=(
                    f"PR {pr_info.number} already has Consilium comment "
                    f"{existing_entry.comment_id}"
                ),
            )

        # Calculate credit distribution
        distribution = self.calculator.calculate_pr_merged(
            author=pr_info.author,
            reviewers=pr_info.reviewers,
            approvers=pr_info.approvers,
        )

        # Create ledger entry
        entry = self.ledger.create_entry(
            pr_number=pr_info.number,
            outcome="pr_merged",
            source=pr_info.url,
            distribution=distribution,
        )

        try:
            # Post comment to GitHub
            _, comment_id = self.client.post_credit_comment(
                self.owner,
                self.repo,
                pr_info.number,
                entry,
            )
            entry.comment_id = comment_id

            # Append to ledger (after successful comment post)
            self.ledger.append(entry)

            return ProcessResult(
                success=True,
                pr_number=pr_info.number,
                entry=entry,
                comment_id=comment_id,
            )

        except Exception as e:
            return ProcessResult(
                success=False,
                pr_number=pr_info.number,
                error=str(e),
            )

    def get_balances(self) -> dict[str, float]:
        """Get current credit balances for all identities."""
        return self.ledger.get_balances()

    def get_leaderboard(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get top contributors by credit."""
        balances = self.get_balances()
        sorted_balances = sorted(
            balances.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_balances[:limit]

    def verify_integrity(self) -> tuple[bool, Optional[str]]:
        """Verify ledger chain integrity."""
        return self.ledger.verify_chain()
