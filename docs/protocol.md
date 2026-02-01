# Consilium Protocol Specification v0.1

## Overview

Consilium is a credit attribution protocol that uses GitHub PR comments as an append-only public ledger. Credit is minted when externally verifiable outcomes occur and distributed to contributors based on their roles.

## Core Concepts

### Outcome
An externally verifiable event that triggers credit minting. In v0.1, the only outcome type is `pr_merged`.

### Credit
A numeric value representing contribution. Credit is:
- **Non-transferable**: You can't give your credit to someone else
- **Earned only**: Minted only on verified outcomes
- **Publicly attributed**: Always tied to a specific outcome and contributor

### Ledger Entry
A record of credit distribution, containing:
- Outcome details (type, source URL, timestamp)
- Distribution map (contributor → credit amount)
- Hash chain links (prev_hash, hash)
- GitHub comment ID (for verification)

## Ledger Structure

### Entry Format

Each ledger entry is stored as JSON with the following schema:

```json
{
  "version": "0.1",
  "type": "credit_mint",
  "pr_number": 42,
  "outcome": "pr_merged",
  "source": "https://github.com/owner/repo/pull/42",
  "distribution": {
    "alice": 50.0,
    "bob": 30.0,
    "charlie": 20.0
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "prev_hash": "abc123def456",
  "hash": "789xyz012abc",
  "comment_id": 1234567890
}
```
Note: hash values in examples may be shortened for readability.

### Hash Computation

The entry hash is computed from a canonical JSON representation:

```python
canonical = {
    "version": entry.version,
    "type": entry.type,
    "pr_number": entry.pr_number,
    "outcome": entry.outcome,
    "source": entry.source,
    "distribution": dict(sorted(entry.distribution.items())),
    "timestamp": entry.timestamp,
    "prev_hash": entry.prev_hash,
}
content = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
hash = sha256(content)  # Full hex digest
```

Key properties:
- Sorted keys ensure deterministic output
- No whitespace variation
- Distribution is sorted by username
- Hash excludes `hash` and `comment_id` fields
- Full hash is stored in the JSON payload; comments display a shortened hash for readability

### Chain Integrity

Each entry links to the previous via `prev_hash`:
- Genesis entry has `prev_hash = "genesis"`
- Each subsequent entry has `prev_hash = previous_entry.hash`
- Modifying any entry breaks the chain

## Credit Distribution Rules

### PR Merged (v0.1)

When a PR is merged, credit is distributed as follows:

| Role | Share | Notes |
|------|-------|-------|
| Author | 50% | The PR creator |
| Reviewers | 30% | Split equally among users with a substantive review state |
| Approvers | 20% | Split equally among users whose latest review is APPROVED |

Review attribution details:
- Only **latest** review state per user is considered
- Reviewers include latest state in {APPROVED, CHANGES_REQUESTED, DISMISSED}
- COMMENTED/PENDING reviews do not count as reviewers

Edge cases:
- If no reviewers: Author gets the reviewer share
- If no approvers: Author gets the approver share
- If someone is both reviewer and approver: Gets both shares
- Self-reviews are excluded

### Configuration

Rules can be customized via `consilium.yaml`:

```yaml
version: "0.1"
credit:
  pr_merged:
    total: 100
    author: 0.5
    reviewers: 0.3
    approvers: 0.2
```

## GitHub Comment Format

Each credit distribution is posted as a PR comment with:

1. **Machine-readable payload** (canonical JSON in markers)
2. **Human-readable summary** (markdown table)

```markdown
<!-- CONSILIUM:BEGIN -->
```json
{
  "version": "0.1",
  "type": "credit_mint",
  ...
}
```
<!-- CONSILIUM:END -->

## 🏆 Consilium Credit Distribution

**Outcome**: `pr_merged`
**PR**: #42
**Total Credit**: 100.0

| Contributor | Credit |
|-------------|--------|
| @alice | 50.0 |
| @bob | 30.0 |
| @charlie | 20.0 |

---
*Hash: `789xyz012abc...` | Prev: `abc123de...*
*Credit is earned, not given. Verified by outcomes, not votes.*
```

## Verification

### Local Chain Verification

```python
prev_hash = "genesis"
for entry in ledger.iter_entries():
    # Verify entry's own hash
    assert entry.hash == entry.compute_hash()
    # Verify chain link
    assert entry.prev_hash == prev_hash
    prev_hash = entry.hash
```

### GitHub Verification

1. Fetch all comments containing `CONSILIUM:BEGIN` marker
2. Parse JSON payload from each comment
3. Verify each payload's hash matches computed hash
4. Compare with local ledger entries by `comment_id`
5. Report any discrepancies

### Rebuild Process

1. Fetch all Consilium comments from GitHub (paginated)
2. Parse and validate each entry
3. Verify hash chain continuity
4. Write to local ledger files
5. Update index with balances

## Security Model

### Threat: Comment Deletion/Modification

**Attack**: Repo admin deletes or edits a Consilium comment.

**Detection**:
- Local Git-tracked ledger preserves the record
- `consilium verify --github` detects mismatch
- Hash chain breaks if entries are modified

**Mitigation**:
- Git history preserves evidence
- Multiple parties can independently verify
- Consider signing commits that update ledger

### Threat: Fake Comments

**Attack**: Someone posts a fake Consilium comment.

**Detection**:
- Hash chain won't link properly
- `rebuild_from_github()` rejects entries with wrong `prev_hash`

**Mitigation**:
- Only the GitHub Action should post comments
- Verify chain integrity before trusting entries

### Threat: GitHub API Manipulation

**Attack**: Attacker compromises GitHub token.

**Detection**:
- Unexpected credit distributions appear
- Hash chain may be corrupted

**Mitigation**:
- Use minimal token permissions
- Monitor for unexpected entries
- Rebuild and verify periodically

## Limitations

### v0.1 Limitations

1. **No cryptographic identity**: Relies on GitHub usernames
2. **Single repo scope**: No cross-project credit
3. **No reputation decay**: Credit accumulates forever
4. **GitHub as trusted party**: Depends on GitHub's integrity
5. **No dispute resolution**: What's recorded is final

### Future Considerations

- **Signatures**: Sign entries with contributor keys
- **Multi-repo**: Aggregate credit across projects
- **Decay**: Time-weighted credit calculations
- **Disputes**: On-chain arbitration mechanism

## Glossary

| Term | Definition |
|------|------------|
| **Credit** | Numeric contribution value |
| **Outcome** | Externally verifiable event |
| **Ledger** | Append-only record of credit distributions |
| **Entry** | Single credit distribution record |
| **Hash chain** | Linked entries via cryptographic hashes |
| **Source of truth** | GitHub PR comments |
| **Derived state** | Local ledger files (Git-tracked) |
