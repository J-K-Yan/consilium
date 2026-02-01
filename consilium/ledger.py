"""
Append-only ledger for Consilium.

Design principles:
- PR comments are the source of truth (public, auditable)
- Git-tracked JSON files are derived state (convenient queries)
- Everything is rebuildable from GitHub
- Content hashes ensure integrity

Comment format:
```
<!-- CONSILIUM:BEGIN -->
```json
{
  "version": "0.1",
  "type": "credit_mint",
  "pr_number": 42,
  "outcome": "pr_merged",
  "source": "https://github.com/owner/repo/pull/42",
  "distribution": {"alice": 50.0, "bob": 30.0, "charlie": 20.0},
  "timestamp": "2024-01-15T10:30:00Z",
  "prev_hash": "abc123...",
  "hash": "def456..."
}
```
<!-- CONSILIUM:END -->

🏆 **Credit Distribution** ...
```
"""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Markers for parsing comments
COMMENT_BEGIN = "<!-- CONSILIUM:BEGIN -->"
COMMENT_END = "<!-- CONSILIUM:END -->"
JSON_PATTERN = re.compile(
    rf"{re.escape(COMMENT_BEGIN)}\s*```json\s*({{.*?}})\s*```\s*{re.escape(COMMENT_END)}",
    re.DOTALL
)

# Display hash length (for comments), storage uses full hash
DISPLAY_HASH_LENGTH = 16


@dataclass
class LedgerEntry:
    """A single entry in the Consilium ledger."""
    version: str
    type: str  # "credit_mint" for now
    pr_number: int
    outcome: str  # "pr_merged", etc.
    source: str  # GitHub URL
    distribution: dict[str, float]
    timestamp: str  # ISO format
    prev_hash: str  # Hash of previous entry ("genesis" for first)
    hash: str = field(default="")  # Full SHA-256 hash
    comment_id: Optional[int] = None  # GitHub comment ID (set after posting)

    def __post_init__(self):
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute full SHA-256 hash of the entry's canonical content."""
        # Canonical representation: sorted keys, no whitespace variation
        canonical = {
            "version": self.version,
            "type": self.type,
            "pr_number": self.pr_number,
            "outcome": self.outcome,
            "source": self.source,
            "distribution": dict(sorted(self.distribution.items())),
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
        }
        content = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode()).hexdigest()  # Full 64-char hash

    @property
    def short_hash(self) -> str:
        """Truncated hash for display purposes."""
        return self.hash[:DISPLAY_HASH_LENGTH]

    @property
    def short_prev_hash(self) -> str:
        """Truncated prev_hash for display purposes."""
        if self.prev_hash == "genesis":
            return "genesis"
        return self.prev_hash[:8]

    def verify(self) -> bool:
        """Verify that the stored hash matches computed hash."""
        return self.hash == self.compute_hash()

    def to_json_payload(self) -> str:
        """Generate canonical JSON payload for comment."""
        data = {
            "version": self.version,
            "type": self.type,
            "pr_number": self.pr_number,
            "outcome": self.outcome,
            "source": self.source,
            "distribution": dict(sorted(self.distribution.items())),
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "hash": self.hash,  # Full hash in payload
        }
        return json.dumps(data, indent=2, sort_keys=True)

    def to_comment_body(self) -> str:
        """Generate full comment body with JSON payload and human-readable summary."""
        json_payload = self.to_json_payload()

        # Human-readable part
        lines = [
            COMMENT_BEGIN,
            "```json",
            json_payload,
            "```",
            COMMENT_END,
            "",
            "## 🏆 Consilium Credit Distribution",
            "",
            f"**Outcome**: `{self.outcome}`",
            f"**PR**: #{self.pr_number}",
            f"**Total Credit**: {sum(self.distribution.values()):.1f}",
            "",
            "| Contributor | Credit |",
            "|-------------|--------|",
        ]

        # Sort by credit descending
        for username, credit in sorted(
            self.distribution.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"| @{username} | {credit:.1f} |")

        lines.extend([
            "",
            "---",
            f"*Hash: `{self.short_hash}...` | Prev: `{self.short_prev_hash}...`*",
            "*Credit is earned, not given. Verified by outcomes, not votes.*",
        ])

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict) -> "LedgerEntry":
        """Create entry from dictionary."""
        return cls(
            version=data["version"],
            type=data["type"],
            pr_number=data["pr_number"],
            outcome=data["outcome"],
            source=data["source"],
            distribution=data["distribution"],
            timestamp=data["timestamp"],
            prev_hash=data["prev_hash"],
            hash=data.get("hash", ""),
            comment_id=data.get("comment_id"),
        )


def parse_comment(body: str) -> Optional[LedgerEntry]:
    """Parse a GitHub comment to extract LedgerEntry if present."""
    match = JSON_PATTERN.search(body)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        return LedgerEntry.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


class Ledger:
    """
    Append-only ledger backed by JSON files.

    Structure:
        ledger/
        ├── index.json          # Chain metadata + identity balances
        ├── entries/
        │   ├── 0001.json       # First entry
        │   ├── 0002.json
        │   └── ...
    """

    def __init__(self, ledger_dir: str = "ledger"):
        self.ledger_dir = Path(ledger_dir)
        self.entries_dir = self.ledger_dir / "entries"
        self.index_path = self.ledger_dir / "index.json"

    def init(self):
        """Initialize ledger directory structure."""
        self.entries_dir.mkdir(parents=True, exist_ok=True)

        if not self.index_path.exists():
            self._write_index({
                "version": "0.1",
                "head_hash": "genesis",
                "entry_count": 0,
                "balances": {},
                "last_updated": datetime.utcnow().isoformat() + "Z",
            })

    def _read_index(self) -> dict:
        """Read the index file."""
        with open(self.index_path) as f:
            return json.load(f)

    def _write_index(self, index: dict):
        """Write the index file atomically."""
        # Write to temp file then rename for atomicity
        fd, tmp_path = tempfile.mkstemp(
            dir=self.ledger_dir,
            prefix=".index_",
            suffix=".json"
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(index, f, indent=2)
            os.replace(tmp_path, self.index_path)
        except Exception:
            os.unlink(tmp_path)
            raise

    def get_head_hash(self) -> str:
        """Get the hash of the most recent entry."""
        if not self.index_path.exists():
            return "genesis"
        return self._read_index()["head_hash"]

    def get_balances(self) -> dict[str, float]:
        """Get current credit balances."""
        if not self.index_path.exists():
            return {}
        return self._read_index()["balances"]

    def get_entry_count(self) -> int:
        """Get total number of entries."""
        if not self.index_path.exists():
            return 0
        return self._read_index()["entry_count"]

    def _count_entry_files(self) -> int:
        """Count actual entry files on disk."""
        if not self.entries_dir.exists():
            return 0
        return len(list(self.entries_dir.glob("*.json")))

    def _list_entry_numbers(self) -> list[int]:
        """List numeric entry filenames present on disk, sorted ascending."""
        if not self.entries_dir.exists():
            return []
        numbers = []
        for path in self.entries_dir.glob("*.json"):
            try:
                numbers.append(int(path.stem))
            except ValueError:
                continue
        return sorted(numbers)

    def create_entry(
        self,
        pr_number: int,
        outcome: str,
        source: str,
        distribution: dict[str, float],
    ) -> LedgerEntry:
        """Create a new ledger entry (not yet appended)."""
        return LedgerEntry(
            version="0.1",
            type="credit_mint",
            pr_number=pr_number,
            outcome=outcome,
            source=source,
            distribution=distribution,
            timestamp=datetime.utcnow().isoformat() + "Z",
            prev_hash=self.get_head_hash(),
        )

    def append(self, entry: LedgerEntry) -> str:
        """
        Append an entry to the ledger atomically.

        Returns the entry filename.
        """
        self.init()

        # Verify entry integrity
        if not entry.verify():
            raise ValueError("Entry hash verification failed")

        # Verify chain integrity
        if entry.prev_hash != self.get_head_hash():
            raise ValueError(
                f"Chain broken: entry.prev_hash={entry.prev_hash}, "
                f"head_hash={self.get_head_hash()}"
            )

        # Prepare entry data
        index = self._read_index()
        entry_numbers = self._list_entry_numbers()
        if entry_numbers:
            expected = list(range(1, entry_numbers[-1] + 1))
            if entry_numbers != expected or index.get("entry_count", 0) != entry_numbers[-1]:
                raise ValueError("Index is out of sync with entry files; run repair_index().")
        elif index.get("entry_count", 0) != 0:
            raise ValueError("Index indicates entries but none found; run repair_index().")

        entry_num = index["entry_count"] + 1
        entry_filename = f"{entry_num:04d}.json"
        entry_path = self.entries_dir / entry_filename
        if entry_path.exists():
            raise ValueError(
                f"Entry file already exists ({entry_filename}). "
                "Index is out of sync; run repair_index()."
            )

        entry_data = {
            "version": entry.version,
            "type": entry.type,
            "pr_number": entry.pr_number,
            "outcome": entry.outcome,
            "source": entry.source,
            "distribution": entry.distribution,
            "timestamp": entry.timestamp,
            "prev_hash": entry.prev_hash,
            "hash": entry.hash,
            "comment_id": entry.comment_id,
        }

        # Update balances
        balances = index["balances"].copy()
        for identity, credit in entry.distribution.items():
            balances[identity] = balances.get(identity, 0) + credit

        new_index = {
            "version": "0.1",
            "head_hash": entry.hash,
            "entry_count": entry_num,
            "balances": balances,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

        # Write atomically: index first (with new count), then entry
        # This way, if we crash after index but before entry, verify_chain will detect it
        # Actually, better: write entry first, then index
        # If crash after entry but before index, we have orphan that verify detects

        # Write entry file atomically
        fd, tmp_entry = tempfile.mkstemp(
            dir=self.entries_dir,
            prefix=".entry_",
            suffix=".json"
        )
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(entry_data, f, indent=2)
            os.replace(tmp_entry, entry_path)
        except Exception:
            if os.path.exists(tmp_entry):
                os.unlink(tmp_entry)
            raise

        # Write index atomically
        self._write_index(new_index)

        return entry_filename

    def get_entry(self, entry_num: int) -> Optional[LedgerEntry]:
        """Get an entry by number (1-indexed)."""
        entry_path = self.entries_dir / f"{entry_num:04d}.json"
        if not entry_path.exists():
            return None

        with open(entry_path) as f:
            data = json.load(f)

        return LedgerEntry.from_dict(data)

    def iter_entries(self):
        """Iterate over all entries in order based on files on disk."""
        for entry_num in self._list_entry_numbers():
            entry = self.get_entry(entry_num)
            if entry:
                yield entry

    def verify_chain(self) -> tuple[bool, Optional[str]]:
        """
        Verify the entire chain integrity including index consistency.

        Checks:
        1. Each entry's hash matches its content
        2. Chain links are valid (prev_hash matches)
        3. Index entry_count matches actual files
        4. Index head_hash matches last entry
        5. Index balances match recomputed balances

        Returns (is_valid, error_message).
        """
        prev_hash = "genesis"
        computed_balances: dict[str, float] = {}
        actual_count = 0

        entry_numbers = self._list_entry_numbers()
        if entry_numbers:
            expected = list(range(1, entry_numbers[-1] + 1))
            if entry_numbers != expected:
                return False, (
                    "Entry gap or extra file detected "
                    f"(expected 1..{expected[-1]}, found {entry_numbers})"
                )

        for i, entry in enumerate(self.iter_entries(), 1):
            actual_count = i

            # Verify entry's own hash
            if not entry.verify():
                return False, f"Entry {i}: hash mismatch"

            # Verify chain link
            if entry.prev_hash != prev_hash:
                return False, f"Entry {i}: chain broken (expected prev_hash={prev_hash}, got {entry.prev_hash})"

            # Accumulate balances
            for identity, credit in entry.distribution.items():
                computed_balances[identity] = computed_balances.get(identity, 0) + credit

            prev_hash = entry.hash

        # Verify index consistency
        if self.index_path.exists():
            index = self._read_index()

            # Verify head hash
            if prev_hash != index.get("head_hash", "genesis"):
                return False, f"Head hash mismatch (index={index.get('head_hash')}, computed={prev_hash})"

            # Verify entry count
            if actual_count != index.get("entry_count", 0):
                return False, f"Entry count mismatch (index={index.get('entry_count')}, actual={actual_count})"

            # Verify balances
            index_balances = index.get("balances", {})
            if computed_balances != index_balances:
                return False, "Balance drift detected (index and entries disagree)"

        return True, None

    def find_by_source(self, source: str) -> Optional[LedgerEntry]:
        """Find an entry by its source URL (for deduplication)."""
        for entry in self.iter_entries():
            if entry.source == source:
                return entry
        return None

    def find_by_comment_id(self, comment_id: int) -> Optional[LedgerEntry]:
        """Find an entry by its GitHub comment ID."""
        for entry in self.iter_entries():
            if entry.comment_id == comment_id:
                return entry
        return None

    def repair_index(self) -> dict:
        """
        Rebuild index from entry files.

        Use when index is corrupted or out of sync.
        Returns the repaired index.
        """
        prev_hash = "genesis"
        balances: dict[str, float] = {}
        count = 0

        for entry in self.iter_entries():
            if not entry.verify():
                raise ValueError(f"Cannot repair: entry {count + 1} has invalid hash")
            if entry.prev_hash != prev_hash:
                raise ValueError(f"Cannot repair: chain broken at entry {count + 1}")

            for identity, credit in entry.distribution.items():
                balances[identity] = balances.get(identity, 0) + credit

            prev_hash = entry.hash
            count += 1

        new_index = {
            "version": "0.1",
            "head_hash": prev_hash,
            "entry_count": count,
            "balances": balances,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

        self._write_index(new_index)
        return new_index
