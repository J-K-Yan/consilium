"""Tests for rebuild error paths."""

import tempfile

import requests

from consilium.rebuild import GitHubCommentFetcher, rebuild_from_github


def test_rebuild_timeout(monkeypatch):
    def fake_fetch(self, since_comment_id=None):
        raise requests.Timeout()

    monkeypatch.setattr(GitHubCommentFetcher, "fetch_consilium_comments", fake_fetch)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = rebuild_from_github(
            token="test",
            owner="owner",
            repo="repo",
            ledger_dir=tmpdir,
        )

    assert result.success is False
    assert result.errors == ["GitHub API timeout - try again later"]
