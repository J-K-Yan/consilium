"""
Credit calculation logic for Consilium.

Credit is minted when externally verifiable outcomes occur.
Distribution follows configurable rules based on contributor roles.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yaml


class OutcomeType(Enum):
    """Types of externally verifiable outcomes."""
    PR_MERGED = "pr_merged"
    TEST_PASSED = "test_passed"
    STAR_RECEIVED = "star_received"
    DEPENDENCY_ADDED = "dependency_added"


@dataclass
class CreditRule:
    """Rules for distributing credit for a specific outcome type."""
    total: float
    author_share: float      # Fraction for author (0.0 - 1.0)
    reviewer_share: float    # Fraction for reviewers (split equally)
    approver_share: float    # Fraction for approvers (split equally)

    def __post_init__(self):
        total_share = self.author_share + self.reviewer_share + self.approver_share
        if abs(total_share - 1.0) > 0.001:
            raise ValueError(f"Shares must sum to 1.0, got {total_share}")


# Default credit rules for v0.1
DEFAULT_RULES: dict[OutcomeType, CreditRule] = {
    OutcomeType.PR_MERGED: CreditRule(
        total=100,
        author_share=0.5,
        reviewer_share=0.3,
        approver_share=0.2,
    ),
}


class CreditCalculator:
    """
    Calculates credit distribution for outcomes.

    Usage:
        calculator = CreditCalculator()
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=["bob", "charlie"],
            approvers=["dave"]
        )
        # Returns: {"alice": 50.0, "bob": 15.0, "charlie": 15.0, "dave": 20.0}
    """

    def __init__(self, rules: Optional[dict[OutcomeType, CreditRule]] = None):
        self.rules = rules or DEFAULT_RULES.copy()

    @classmethod
    def from_config(cls, config_path: str) -> "CreditCalculator":
        """Load credit rules from a consilium.yaml config file."""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        rules = {}
        credit_config = config.get('credit', {})

        if 'pr_merged' in credit_config:
            pr_config = credit_config['pr_merged']
            rules[OutcomeType.PR_MERGED] = CreditRule(
                total=pr_config.get('total', 100),
                author_share=pr_config.get('author', 0.5),
                reviewer_share=pr_config.get('reviewers', 0.3),
                approver_share=pr_config.get('approvers', 0.2),
            )

        return cls(rules if rules else None)

    def get_rule(self, outcome_type: OutcomeType) -> CreditRule:
        """Get the credit rule for an outcome type."""
        if outcome_type not in self.rules:
            raise ValueError(f"No credit rule defined for {outcome_type}")
        return self.rules[outcome_type]

    def calculate_pr_merged(
        self,
        author: str,
        reviewers: list[str],
        approvers: list[str],
    ) -> dict[str, float]:
        """
        Calculate credit distribution for a merged PR.

        Args:
            author: GitHub username of PR author
            reviewers: List of GitHub usernames who reviewed
            approvers: List of GitHub usernames who approved

        Returns:
            Dictionary mapping username to credit amount
        """
        rule = self.get_rule(OutcomeType.PR_MERGED)
        distribution: dict[str, float] = {}

        # Author gets their share
        distribution[author] = rule.total * rule.author_share

        # Reviewers split their share equally
        if reviewers:
            reviewer_each = (rule.total * rule.reviewer_share) / len(reviewers)
            for reviewer in reviewers:
                distribution[reviewer] = distribution.get(reviewer, 0) + reviewer_each

        # Approvers split their share equally
        if approvers:
            approver_each = (rule.total * rule.approver_share) / len(approvers)
            for approver in approvers:
                distribution[approver] = distribution.get(approver, 0) + approver_each

        # Handle edge case: if no reviewers or approvers, redistribute to author
        if not reviewers:
            distribution[author] += rule.total * rule.reviewer_share
        if not approvers:
            distribution[author] += rule.total * rule.approver_share

        return distribution
