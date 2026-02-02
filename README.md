# Consilium

**A multi-agent collaboration credit protocol — credit is earned, not given; verified by outcomes, not votes.**

## What is this?

Consilium tracks contributions in collaborative projects using GitHub PR events as the source of truth. When a PR is merged, credit is automatically calculated and distributed to contributors.

Key properties:
- **Externally anchored**: Credit only exists when tied to real GitHub events
- **Publicly verifiable**: All credit distributions are posted as PR comments
- **Tamper-evident**: Hash chain ensures integrity, anyone can verify
- **Rebuildable**: Ledger can be reconstructed from GitHub at any time

## Agent Quick Brief

If you are an AI agent integrating with Consilium, treat these as invariant rules:

- **Source of truth**: GitHub PR comments containing canonical JSON between `CONSILIUM:BEGIN/END`.
- **Derived state**: `ledger/` files are cached and disposable; rebuild from GitHub when in doubt.
- **Deterministic**: Same inputs → same credit distribution (no subjective scoring).
- **Idempotent**: Safe to retry; duplicates are detected by source/comment_id.
- **Verify first**: Use `consilium verify` and `consilium verify --github --repo owner/repo`.

## 60-Second Demo (Live Output)

Live demo: the GitHub Action posted a Consilium comment on PR #2 in this repo.
- [PR #2 comment (bot output)](https://github.com/J-K-Yan/consilium/pull/2#issuecomment-3832204340)

Excerpt:

````markdown
<!-- CONSILIUM:BEGIN -->
```json
{
  "distribution": {
    "J-K-Yan": 100.0
  },
  "hash": "b84d21d2d16431f2e166ea1c12b0e97c731a22f4ca48db21221969fcc5d7124a",
  "outcome": "pr_merged",
  "pr_number": 2,
  "prev_hash": "genesis",
  "source": "https://github.com/J-K-Yan/consilium/pull/2",
  "timestamp": "2026-02-01T22:50:55.600495Z",
  "type": "credit_mint",
  "version": "0.1"
}
```
<!-- CONSILIUM:END -->

## 🏆 Consilium Credit Distribution

**Outcome**: `pr_merged`
**PR**: #2
**Total Credit**: 100.0

| Contributor | Credit |
|-------------|--------|
| @J-K-Yan | 100.0 |

---
*Hash: `b84d21d2d16431f2...` | Prev: `genesis...`*
*Credit is earned, not given. Verified by outcomes, not votes.*
````

## How It Works

```
PR Merged → Credit Calculated → Comment Posted → Ledger Updated
                                      ↓
                            (Source of Truth)
                                      ↓
                            Anyone can verify
```

1. A PR gets merged
2. Consilium calculates credit distribution:
   - **Author**: 50%
   - **Reviewers**: 30% (split equally; latest review state only)
   - **Approvers**: 20% (split equally; latest state = APPROVED)
3. A comment is posted to the PR with:
   - Human-readable credit table
   - Canonical JSON payload with full content hash (display uses short hash)
   - Link to previous entry (hash chain)
4. Local ledger files are updated (derived state, always rebuildable)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOURCE OF TRUTH                               │
│                                                                  │
│   GitHub PR Comments (public, auditable, tamper-evident)         │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │ <!-- CONSILIUM:BEGIN -->                                  │  │
│   │ ```json                                                   │  │
│   │ { "hash": "abc123", "prev_hash": "xyz789", ... }         │  │
│   │ ```                                                       │  │
│   │ <!-- CONSILIUM:END -->                                    │  │
│   └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    rebuild_from_github()
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DERIVED STATE (Git-tracked)                   │
│                                                                  │
│   ledger/                                                        │
│   ├── index.json        # head_hash, balances, entry_count      │
│   └── entries/                                                   │
│       ├── 0001.json     # Entry with comment_id                 │
│       ├── 0002.json                                              │
│       └── ...                                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Interaction Model

For agents, the contract is simple and repeatable:

- **Input**: merged PR event (author, reviewers, approvers).
- **Output**: a PR comment with canonical JSON + a hash link to the prior entry.
- **Authoritative data**: PR comments (public, auditable, rebuildable).
- **Local cache**: `ledger/` is derived and must match GitHub or be rebuilt.

## Quick Start (5 minutes)

### 1) Install (pin to a tag)

```bash
pipx install git+https://github.com/J-K-Yan/consilium@v0.1.2
# or
pip install git+https://github.com/J-K-Yan/consilium@v0.1.2
```

Pin to a tag for reproducible behavior; avoid installing from `main`.

### 2) Add GitHub Action

Copy `.github/workflows/consilium.yml` to your repository. The action triggers on merged PRs.
For running Consilium in another repo (agent contributions), see `docs/agent-setup.md`.

If you copy the workflow into a different repo, update the install step to pin a release tag:

```yaml
- name: Install Consilium
  run: pip install git+https://github.com/J-K-Yan/consilium@v0.1.2
```

### 3) Configure (optional)

Create `consilium.yaml` to customize credit rules (or set `CONSILIUM_CONFIG` to point at a different path):

```yaml
version: "0.1"

project:
  name: "my-project"
  repo: "owner/my-project"

credit:
  pr_merged:
    total: 100
    author: 0.5
    reviewers: 0.3
    approvers: 0.2
```

Use `consilium.yaml.example` as a starting point.

### 4) Merge a PR

Merge any PR. The action will post a Consilium comment and commit `ledger/`.

### 5) Verify

Use the CLI to verify ledger integrity:

```bash
# Check local chain
consilium verify

# Verify against GitHub
GITHUB_TOKEN=xxx consilium verify --github --repo owner/repo

# View leaderboard
consilium balance

# View specific entry
consilium show 1
```

Want the full walkthrough and expected outputs? See `docs/demo.md`.

## Policy Cookbook

Ready-to-copy credit policies (balanced, review-heavy, maintainer-heavy) live in `docs/policy.md`.

## Docs

- `docs/index.md` (GitHub Pages ready)
- `docs/demo.md`
- `docs/policy.md`
- `docs/protocol.md` (core spec)
- `docs/protocol-core.md` (minimal ledger summary)
- `docs/protocol-extensions.md` (roadmap)
- `docs/agent-setup.md`
- `docs/maintainers.md`
- `SECURITY.md`

## CLI Commands

```bash
# Show credit leaderboard
consilium balance

# Show specific user's credit
consilium balance alice

# Verify local chain integrity
consilium verify

# Verify against GitHub comments
consilium verify --github --repo owner/repo

# Rebuild ledger from GitHub (incremental)
consilium rebuild --repo owner/repo

# Full rebuild from scratch
consilium rebuild --repo owner/repo --full

# Show specific ledger entry
consilium show 42
consilium show 42 --json
```

## Trust Model

### What Consilium trusts:
- GitHub's record of PR events (who authored, reviewed, approved)
- GitHub's comment storage (source of truth)

### What Consilium doesn't trust:
- Local ledger files (derived, always rebuildable)
- Any single actor's claims (everything is publicly verifiable)

### Agent rule of thumb:
- If GitHub comments and local ledger disagree, treat local ledger as stale and rebuild.

### How tampering is detected:
1. **Hash chain**: Each entry contains hash of previous entry
2. **Content hash**: Each entry's hash is computed from its content
3. **Public comments**: Anyone can see the authoritative record
4. **Rebuild verification**: `consilium verify --github` compares local vs GitHub

### Limitations:
- Repo admins can delete comments (mitigated by Git-tracked ledger)
- GitHub is a trusted third party
- No cryptographic signatures (v0.1 simplification)

See `SECURITY.md` for threat model, permissions, and token guidance.

## Design Principles

### Agent-First Design (Recommended)
Consilium is built for AI agents to act on it safely and autonomously. Recommended design choices:

- **Deterministic rules**: same inputs → same outputs; no subjective scoring.
- **Machine-readable source of truth**: canonical JSON in PR comments, not prose.
- **Append-only & replayable**: ledgers are rebuildable from public events.
- **Idempotent operations**: safe retries when ledger is in sync; duplicates are detected by source/comment_id during rebuild/verification.
- **Tamper-evident integrity**: hash-chained entries, verifiable by any agent.
- **Bounded complexity**: simple roles, explicit schemas, minimal branching.
- **Explicit failure modes**: clear validation errors agents can handle.
- **Latest-review attribution**: approvers are only those whose latest review is APPROVED.
- **Multi-agent friendly**: Consilium itself can be developed by multiple agents using the same rules.

### Ostrom Layer (Incentive Alignment)
Based on Elinor Ostrom's work on commons governance:
- **Clear attribution**: Every contribution is signed and tracked
- **Recoverable benefits**: Contributors earn credit from outcomes
- **Accountability**: All distributions are public and auditable

### External Anchoring
- Credit only minted on verifiable GitHub events
- No self-issued credit, no voting, no karma
- Human usage is the ultimate validation

### Minimal Constitution
> "Don't over-design. Let the system run, observe what happens, then decide what to add."

## Project Structure

```
consilium/
├── consilium/         # Python package
│   ├── credit.py      # Credit calculation rules
│   ├── github.py      # GitHub API interaction
│   ├── ledger.py      # Append-only hash-chained ledger
│   ├── rebuild.py     # Rebuild/verify from GitHub
│   ├── handler.py     # Main orchestration
│   └── cli.py         # Command-line interface
├── tests/
├── ledger/            # Git-tracked derived state
│   ├── index.json
│   └── entries/
├── .github/
│   └── workflows/
│       └── consilium.yml
└── consilium.yaml     # Optional configuration
```

## What v0.1 Doesn't Do (Yet)

| Feature | Why Not Yet |
|---------|-------------|
| Cryptographic signatures | GitHub identity is enough for now |
| Reputation decay | Accumulate data first |
| Cross-project trust | Single project first |
| Complex role weights | Simple role-based split works |

## Contributing

See `CONTRIBUTING.md` for guidelines (agents and humans are both welcome).

## Philosophy

> "Credit is earned, not given"

This is the soul of the project. When a design decision confuses you, return to this statement.

## Background

This project emerged from discussions about multi-agent collaboration, trust networks, and institutional economics. Key references:

- **Ostrom's Commons Governance**: Property rights, attribution, profit-sharing, sanctions
- **Robert's Rules of Order**: Procedural justice, role separation, decision traceability
- **GitHub as Credit Anchor**: External signal verification
- **Lessons from Moltbook**: Systems without outcome anchoring devolve into performance theater

## Pilot Repos Wanted

We are looking for 3-5 pilot repos to run Consilium for 2 weeks.

Please report:
- disputes about attribution
- attempted gaming
- whether the rules feel fair

We will not add provisional states or clawbacks until we have real data.

## License

MIT
