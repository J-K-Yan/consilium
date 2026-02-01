"""Tests for Consilium credit calculation logic."""

import pytest

from consilium.credit import CreditCalculator, CreditRule


class TestCreditRule:
    def test_valid_rule(self):
        rule = CreditRule(
            total=100,
            author_share=0.5,
            reviewer_share=0.3,
            approver_share=0.2,
        )
        assert rule.total == 100
        assert rule.author_share == 0.5

    def test_invalid_shares_raises(self):
        with pytest.raises(ValueError):
            CreditRule(
                total=100,
                author_share=0.5,
                reviewer_share=0.3,
                approver_share=0.3,  # Sum = 1.1
            )


class TestCreditCalculator:
    @pytest.fixture
    def calculator(self):
        return CreditCalculator()

    def test_basic_distribution(self, calculator):
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=["bob", "charlie"],
            approvers=["dave"],
        )

        assert distribution["alice"] == 50.0  # 50%
        assert distribution["bob"] == 15.0    # 30% / 2
        assert distribution["charlie"] == 15.0
        assert distribution["dave"] == 20.0   # 20%

    def test_single_reviewer_approver(self, calculator):
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=["bob"],
            approvers=["bob"],
        )

        # Bob is both reviewer and approver
        assert distribution["alice"] == 50.0
        assert distribution["bob"] == 50.0  # 30% + 20%

    def test_no_reviewers(self, calculator):
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=[],
            approvers=["dave"],
        )

        # Author gets reviewer share when no reviewers
        assert distribution["alice"] == 80.0  # 50% + 30%
        assert distribution["dave"] == 20.0

    def test_no_approvers(self, calculator):
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=["bob"],
            approvers=[],
        )

        # Author gets approver share when no approvers
        assert distribution["alice"] == 70.0  # 50% + 20%
        assert distribution["bob"] == 30.0

    def test_solo_contribution(self, calculator):
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=[],
            approvers=[],
        )

        # Author gets everything
        assert distribution["alice"] == 100.0

    def test_many_reviewers(self, calculator):
        reviewers = ["r1", "r2", "r3", "r4", "r5"]
        distribution = calculator.calculate_pr_merged(
            author="alice",
            reviewers=reviewers,
            approvers=["approver"],
        )

        assert distribution["alice"] == 50.0
        for r in reviewers:
            assert distribution[r] == 6.0  # 30% / 5
        assert distribution["approver"] == 20.0

    def test_total_always_100(self, calculator):
        # Test various configurations
        configs = [
            ("a", ["r1"], ["ap1"]),
            ("a", ["r1", "r2"], ["ap1", "ap2"]),
            ("a", [], []),
            ("a", ["r1", "r2", "r3"], []),
            ("a", [], ["ap1", "ap2", "ap3"]),
        ]

        for author, reviewers, approvers in configs:
            distribution = calculator.calculate_pr_merged(author, reviewers, approvers)
            total = sum(distribution.values())
            assert abs(total - 100.0) < 0.001, f"Total was {total} for {author}, {reviewers}, {approvers}"
