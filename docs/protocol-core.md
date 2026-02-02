# Consilium Protocol Core v0.1 (Summary)

## 1. Purpose
Define the minimal, deterministic, append-only ledger format for Consilium v0.1 that matches the
canonical protocol spec (`docs/protocol.md`). It focuses on entry structure, canonicalization,
hashing, and verification.

Non-goal: define "fair" credit allocation. Allocation policy is specified in the main protocol spec.

## 2. Invariants (MUST)
1) Determinism:
   Given the same ledger entries, every verifier MUST compute the same hashes and balances.
2) Auditability:
   Every credit entry MUST reference a verifiable source (e.g. PR URL).
3) External anchoring:
   The source of truth is GitHub PR comments; local ledger files are derived state.

## 3. Ledger Storage (RECOMMENDED)
- Ledger is append-only.
- Existing entry files MUST NOT be modified or deleted.
- Recommended: one entry per file under `ledger/entries/`.
- Recommended filename: zero-padded sequence (e.g. `0001.json`, `0002.json`), so
  lexicographic order is ledger order.

## 4. Entry Envelope (MUST)
An entry is a JSON object with these required fields:

- `version`: "0.1"
- `type`: `credit_mint` (v0.1 only defines one type)
- `pr_number`: integer PR number
- `outcome`: `pr_merged` (v0.1 only defines one outcome)
- `source`: a string reference to verifiable outcome (e.g. PR URL)
- `distribution`: map<string actor_id, number credit_amount>
- `timestamp`: RFC3339 UTC string (e.g. `2024-01-15T10:30:00Z`)
- `prev_hash`: string (hex). For genesis, use literal `genesis`.
- `hash`: string (hex). SHA-256 of canonical JSON of entry with `hash` field removed.

Optional fields:
- `comment_id`: integer GitHub comment ID (set after posting, not included in hash)

Notes:
- `distribution` values are JSON numbers (v0.1 examples use decimal values like `50.0`).
- Actor IDs are opaque strings at the protocol level (e.g. GitHub handles).

## 5. Canonical JSON (MUST)
To compute hash deterministically, verifiers MUST canonicalize JSON as follows:

- Encode as UTF-8
- Object keys MUST be sorted lexicographically
- No insignificant whitespace
- Numbers MUST be emitted as JSON numbers
- Arrays preserve order (if any)
- `distribution` MUST be sorted by actor_id key
- `hash` and `comment_id` are excluded from the canonical payload

Canonical payload fields (in any key order before sorting):
`version`, `type`, `pr_number`, `outcome`, `source`, `distribution`, `timestamp`, `prev_hash`

## 6. Hash
`hash = SHA256(canonical_json(entry_without_hash_and_comment_id))`

## 7. Verification Algorithm (MUST)
A verifier MUST:
1) Load all entries in ledger order.
   - If one file per entry: order by filename lexicographically.
2) For each entry:
   - Check required fields exist and `version == "0.1"`.
   - Recompute hash and compare to stored `hash`.
   - Check `prev_hash` equals previous entry's `hash` (or `genesis` for first).
3) Optionally compute balances by summing distribution amounts.

Core verification does NOT fetch network resources.
It only ensures the ledger is deterministic and tamper-evident.

## 8. Append-only Enforcement (RECOMMENDED)
CI SHOULD reject changes that:
- modify existing files under `ledger/entries/`
- delete files under `ledger/entries/`
Only new entry files may be added.
