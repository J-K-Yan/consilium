"""Tests for Consilium append-only ledger."""

import shutil
import tempfile
from pathlib import Path

import pytest

from consilium.ledger import Ledger, LedgerEntry, parse_comment


class TestLedgerEntry:
    def test_create_entry(self):
        entry = LedgerEntry(
            version="0.1",
            type="credit_mint",
            pr_number=42,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/42",
            distribution={"alice": 50.0, "bob": 30.0},
            timestamp="2024-01-15T10:30:00Z",
            prev_hash="genesis",
        )
        assert entry.pr_number == 42
        assert entry.hash != ""
        assert len(entry.hash) == 64  # Full SHA-256 hash
        assert len(entry.short_hash) == 16  # Display hash

    def test_hash_is_deterministic(self):
        """Same data should produce same hash."""
        kwargs = {
            "version": "0.1",
            "type": "credit_mint",
            "pr_number": 42,
            "outcome": "pr_merged",
            "source": "https://github.com/owner/repo/pull/42",
            "distribution": {"alice": 50.0, "bob": 30.0},
            "timestamp": "2024-01-15T10:30:00Z",
            "prev_hash": "genesis",
        }
        entry1 = LedgerEntry(**kwargs)
        entry2 = LedgerEntry(**kwargs)
        assert entry1.hash == entry2.hash

    def test_hash_changes_with_data(self):
        """Different data should produce different hash."""
        base = {
            "version": "0.1",
            "type": "credit_mint",
            "pr_number": 42,
            "outcome": "pr_merged",
            "source": "https://github.com/owner/repo/pull/42",
            "distribution": {"alice": 50.0},
            "timestamp": "2024-01-15T10:30:00Z",
            "prev_hash": "genesis",
        }
        entry1 = LedgerEntry(**base)

        # Change PR number
        entry2 = LedgerEntry(**{**base, "pr_number": 43})
        assert entry1.hash != entry2.hash

        # Change distribution
        entry3 = LedgerEntry(**{**base, "distribution": {"alice": 60.0}})
        assert entry1.hash != entry3.hash

    def test_verify_valid_entry(self):
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
        assert entry.verify() is True

    def test_verify_tampered_entry(self):
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
        # Tamper with distribution after hash computed
        entry.distribution["alice"] = 100.0
        assert entry.verify() is False

    def test_to_comment_body(self):
        entry = LedgerEntry(
            version="0.1",
            type="credit_mint",
            pr_number=42,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/42",
            distribution={"alice": 50.0, "bob": 30.0},
            timestamp="2024-01-15T10:30:00Z",
            prev_hash="genesis",
        )
        body = entry.to_comment_body()

        # Check markers
        assert "<!-- CONSILIUM:BEGIN -->" in body
        assert "<!-- CONSILIUM:END -->" in body

        # Check JSON payload
        assert '"version": "0.1"' in body
        assert '"pr_number": 42' in body
        assert entry.hash in body

        # Check human-readable part
        assert "@alice" in body
        assert "@bob" in body
        assert "50.0" in body

    def test_from_dict(self):
        data = {
            "version": "0.1",
            "type": "credit_mint",
            "pr_number": 42,
            "outcome": "pr_merged",
            "source": "https://github.com/owner/repo/pull/42",
            "distribution": {"alice": 50.0},
            "timestamp": "2024-01-15T10:30:00Z",
            "prev_hash": "genesis",
            "hash": "abc123",
            "comment_id": 12345,
        }
        entry = LedgerEntry.from_dict(data)
        assert entry.pr_number == 42
        assert entry.comment_id == 12345


class TestParseComment:
    def test_parse_valid_comment(self):
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
        body = entry.to_comment_body()

        parsed = parse_comment(body)
        assert parsed is not None
        assert parsed.pr_number == 42
        assert parsed.hash == entry.hash

    def test_parse_non_consilium_comment(self):
        body = "This is just a regular comment."
        parsed = parse_comment(body)
        assert parsed is None

    def test_parse_malformed_json(self):
        body = """
        <!-- CONSILIUM:BEGIN -->
        ```json
        {not valid json}
        ```
        <!-- CONSILIUM:END -->
        """
        parsed = parse_comment(body)
        assert parsed is None


class TestLedger:
    @pytest.fixture
    def ledger_dir(self):
        """Create a temporary directory for the ledger."""
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def ledger(self, ledger_dir):
        """Create a ledger instance."""
        ledger = Ledger(ledger_dir)
        ledger.init()
        return ledger

    def test_init_creates_structure(self, ledger_dir):
        ledger = Ledger(ledger_dir)
        ledger.init()

        assert (Path(ledger_dir) / "index.json").exists()
        assert (Path(ledger_dir) / "entries").is_dir()

    def test_initial_state(self, ledger):
        assert ledger.get_head_hash() == "genesis"
        assert ledger.get_entry_count() == 0
        assert ledger.get_balances() == {}

    def test_create_entry(self, ledger):
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        assert entry.prev_hash == "genesis"
        assert entry.version == "0.1"

    def test_append_entry(self, ledger):
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0, "bob": 30.0},
        )
        filename = ledger.append(entry)

        assert filename == "0001.json"
        assert ledger.get_entry_count() == 1
        assert ledger.get_head_hash() == entry.hash
        assert ledger.get_balances() == {"alice": 50.0, "bob": 30.0}

    def test_append_multiple_entries(self, ledger):
        # First entry
        entry1 = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        ledger.append(entry1)

        # Second entry
        entry2 = ledger.create_entry(
            pr_number=2,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/2",
            distribution={"alice": 30.0, "bob": 20.0},
        )
        ledger.append(entry2)

        assert ledger.get_entry_count() == 2
        assert entry2.prev_hash == entry1.hash
        assert ledger.get_balances() == {"alice": 80.0, "bob": 20.0}

    def test_append_rejects_broken_chain(self, ledger):
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        # Tamper with prev_hash
        entry.prev_hash = "wrong_hash"
        entry.hash = entry.compute_hash()  # Recompute to pass hash verification

        with pytest.raises(ValueError, match="Chain broken"):
            ledger.append(entry)

    def test_get_entry(self, ledger):
        entry = ledger.create_entry(
            pr_number=42,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/42",
            distribution={"alice": 50.0},
        )
        ledger.append(entry)

        loaded = ledger.get_entry(1)
        assert loaded is not None
        assert loaded.pr_number == 42
        assert loaded.hash == entry.hash

    def test_get_nonexistent_entry(self, ledger):
        loaded = ledger.get_entry(999)
        assert loaded is None

    def test_iter_entries(self, ledger):
        for i in range(3):
            entry = ledger.create_entry(
                pr_number=i,
                outcome="pr_merged",
                source=f"https://github.com/owner/repo/pull/{i}",
                distribution={"alice": 10.0},
            )
            ledger.append(entry)

        entries = list(ledger.iter_entries())
        assert len(entries) == 3
        assert [e.pr_number for e in entries] == [0, 1, 2]

    def test_verify_chain_valid(self, ledger):
        for i in range(3):
            entry = ledger.create_entry(
                pr_number=i,
                outcome="pr_merged",
                source=f"https://github.com/owner/repo/pull/{i}",
                distribution={"alice": 10.0},
            )
            ledger.append(entry)

        is_valid, error = ledger.verify_chain()
        assert is_valid is True
        assert error is None

    def test_verify_chain_empty(self, ledger):
        is_valid, error = ledger.verify_chain()
        assert is_valid is True

    def test_find_by_source(self, ledger):
        entry = ledger.create_entry(
            pr_number=42,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/42",
            distribution={"alice": 50.0},
        )
        ledger.append(entry)

        found = ledger.find_by_source("https://github.com/owner/repo/pull/42")
        assert found is not None
        assert found.pr_number == 42

        not_found = ledger.find_by_source("https://github.com/owner/repo/pull/999")
        assert not_found is None

    def test_find_by_comment_id(self, ledger):
        entry = ledger.create_entry(
            pr_number=42,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/42",
            distribution={"alice": 50.0},
        )
        entry.comment_id = 12345
        ledger.append(entry)

        found = ledger.find_by_comment_id(12345)
        assert found is not None
        assert found.pr_number == 42

        not_found = ledger.find_by_comment_id(99999)
        assert not_found is None

    def test_verify_chain_detects_balance_drift(self, ledger):
        """Index balances out of sync should be detected."""
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        ledger.append(entry)

        # Manually corrupt the index
        index = ledger._read_index()
        index["balances"]["alice"] = 999.0  # Wrong balance
        ledger._write_index(index)

        is_valid, error = ledger.verify_chain()
        assert is_valid is False
        assert "Balance drift" in error

    def test_verify_chain_detects_count_mismatch(self, ledger):
        """Index entry_count out of sync should be detected."""
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        ledger.append(entry)

        # Manually corrupt the index
        index = ledger._read_index()
        index["entry_count"] = 999  # Wrong count
        ledger._write_index(index)

        is_valid, error = ledger.verify_chain()
        assert is_valid is False
        assert "Entry count mismatch" in error

    def test_repair_index(self, ledger):
        """repair_index should rebuild from entries."""
        # Add some entries
        for i in range(3):
            entry = ledger.create_entry(
                pr_number=i,
                outcome="pr_merged",
                source=f"https://github.com/owner/repo/pull/{i}",
                distribution={"alice": 10.0, "bob": 5.0},
            )
            ledger.append(entry)

        # Corrupt the index
        index = ledger._read_index()
        index["balances"] = {"wrong": 999.0}
        index["entry_count"] = 999
        index["head_hash"] = "corrupted"
        ledger._write_index(index)

        # Verify it's broken
        is_valid, _ = ledger.verify_chain()
        assert is_valid is False

        # Repair
        repaired = ledger.repair_index()

        # Verify it's fixed
        is_valid, error = ledger.verify_chain()
        assert is_valid is True, f"Still invalid: {error}"
        assert repaired["entry_count"] == 3
        assert repaired["balances"] == {"alice": 30.0, "bob": 15.0}

    def test_append_rejects_out_of_sync_index(self, ledger):
        """append should refuse when index is out of sync."""
        entry = ledger.create_entry(
            pr_number=1,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/1",
            distribution={"alice": 50.0},
        )
        ledger.append(entry)

        # Corrupt index to be out of sync
        index = ledger._read_index()
        index["entry_count"] = 0
        ledger._write_index(index)

        entry2 = ledger.create_entry(
            pr_number=2,
            outcome="pr_merged",
            source="https://github.com/owner/repo/pull/2",
            distribution={"alice": 10.0},
        )

        with pytest.raises(ValueError, match="out of sync"):
            ledger.append(entry2)
