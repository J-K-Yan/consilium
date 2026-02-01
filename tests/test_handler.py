"""Tests for Consilium handler error/skip paths."""

from consilium.github import PRInfo
from consilium.handler import ConsiliumHandler
from consilium.ledger import LedgerEntry


class DummyLedger:
    def __init__(self, head_hash="genesis", append_error=None):
        self._head_hash = head_hash
        self.append_error = append_error

    def find_by_source(self, source: str):
        return False

    def get_head_hash(self) -> str:
        return self._head_hash

    def append(self, entry):
        if self.append_error:
            raise self.append_error


class DummyClient:
    def __init__(self, entry=None, error=None):
        self.entry = entry
        self.error = error

    def find_consilium_entry(self, owner, repo, issue_number, source_url):
        if self.error:
            raise self.error
        return self.entry


def _make_pr_info(url: str) -> PRInfo:
    return PRInfo(
        number=42,
        title="Test PR",
        author="alice",
        reviewers=[],
        approvers=[],
        url=url,
        repo_owner="owner",
        repo_name="repo",
        merged=True,
        merged_at="2024-01-15T10:30:00Z",
    )


def test_process_pr_existing_comment_out_of_sync():
    entry = LedgerEntry(
        version="0.1",
        type="credit_mint",
        pr_number=42,
        outcome="pr_merged",
        source="https://github.com/owner/repo/pull/42",
        distribution={"alice": 50.0},
        timestamp="2024-01-15T10:30:00Z",
        prev_hash="prev_hash",
    )

    handler = ConsiliumHandler(github_token="test", owner="owner", repo="repo")
    handler.ledger = DummyLedger(head_hash="different")
    handler.client = DummyClient(entry=entry)

    result = handler.process_pr(_make_pr_info(entry.source))
    assert result.success is True
    assert result.skipped is True
    assert "local ledger out of sync. Run rebuild." in (result.skip_reason or "")


def test_process_pr_existing_comment_append_fails():
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

    handler = ConsiliumHandler(github_token="test", owner="owner", repo="repo")
    handler.ledger = DummyLedger(head_hash="genesis", append_error=ValueError("boom"))
    handler.client = DummyClient(entry=entry)

    result = handler.process_pr(_make_pr_info(entry.source))
    assert result.success is True
    assert result.skipped is True
    assert "ledger append failed" in (result.skip_reason or "")
    assert "Run rebuild." in (result.skip_reason or "")


def test_process_pr_comment_check_error():
    handler = ConsiliumHandler(github_token="test", owner="owner", repo="repo")
    handler.ledger = DummyLedger(head_hash="genesis")
    handler.client = DummyClient(error=RuntimeError("nope"))

    result = handler.process_pr(_make_pr_info("https://github.com/owner/repo/pull/42"))
    assert result.success is False
    assert "Failed to check existing comments: nope" in (result.error or "")
