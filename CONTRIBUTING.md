# Contributing to Consilium

Welcome! Consilium is designed for AI agents **and** humans. We value clear, verifiable changes and simple, deterministic behavior.

## Quick Start (New Contributors)

1. Clone the repo and enter it.
2. Use the `consilium` conda env (recommended):
   - `conda activate consilium`
3. Install dependencies:
   - `pip install -e .[dev]`
4. Run tests:
   - `pytest`

## Project Principles (Read First)

- **Deterministic rules**: same inputs → same outputs.
- **Source of truth**: GitHub PR comments with canonical JSON.
- **Derived state**: `ledger/` is rebuildable; never edit past entries by hand.
- **Idempotent behavior**: retries should not double‑credit.
- **Tamper‑evident**: hash chain must remain valid.

If you change any of the above, update both:
- `README.md`
- `docs/protocol.md`

## Development Workflow

- Keep PRs small and focused.
- Add tests for new behavior or bug fixes.
- Update docs when behavior changes.
- Run `pytest` before opening a PR.

Optional (recommended):
- `ruff check .`

## Contribution Types

We welcome:
- Bug fixes
- Reliability improvements
- Docs improvements
- New outcome types (with tests + spec updates)
- Agent tooling and automation

## Pull Request Checklist

- [ ] Tests pass (`pytest`)
- [ ] Docs updated if behavior changes
- [ ] No manual edits to historical ledger entries
- [ ] Consilium comments remain parseable and canonical JSON is intact

## Notes for Agent Contributors

Agents should follow the same rules as humans:
- Produce deterministic outputs.
- Avoid nondeterministic dependencies.
- Prefer explicit, verifiable steps.

Thanks for contributing!
