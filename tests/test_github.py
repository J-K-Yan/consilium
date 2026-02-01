"""Tests for GitHub client helpers."""

from consilium.github import GitHubClient
from consilium.ledger import LedgerEntry


def test_find_consilium_entry(monkeypatch):
    client = GitHubClient(token="test-token")

    entry = LedgerEntry(
        version="0.1",
        type="credit_mint",
        pr_number=42,
        outcome="pr_merged",
        source="https://github.com/owner/repo/pull/42",
        distribution={"alice": 50.0},
        timestamp="2024-01-15T10:30:00Z",
        prev_hash="genesis",
    )

    comments = [
        {"id": 111, "body": "Regular comment"},
        {"id": 222, "body": entry.to_comment_body()},
    ]

    def fake_get_paginated(endpoint, params=None):
        return comments

    monkeypatch.setattr(client, "_get_paginated", fake_get_paginated)

    found = client.find_consilium_entry(
        owner="owner",
        repo="repo",
        issue_number=42,
        source_url=entry.source,
    )

    assert found is not None
    assert found.comment_id == 222
    assert found.source == entry.source


def test_find_consilium_entry_mismatch(monkeypatch):
    client = GitHubClient(token="test-token")

    entry = LedgerEntry(
        version="0.1",
        type="credit_mint",
        pr_number=42,
        outcome="pr_merged",
        source="https://github.com/owner/repo/pull/42",
        distribution={"alice": 50.0},
        timestamp="2024-01-15T10:30:00Z",
        prev_hash="genesis",
    )

    comments = [
        {"id": 222, "body": entry.to_comment_body()},
    ]

    def fake_get_paginated(endpoint, params=None):
        return comments

    monkeypatch.setattr(client, "_get_paginated", fake_get_paginated)

    found = client.find_consilium_entry(
        owner="owner",
        repo="repo",
        issue_number=42,
        source_url="https://github.com/owner/repo/pull/999",
    )

    assert found is None
