# Security

This document describes Consilium's threat model, required permissions, and token hygiene.

## Summary

Consilium trusts GitHub's record of PR events and comment storage. It does not trust local ledger files.
The canonical source of truth is the PR comment that contains JSON between `CONSILIUM:BEGIN/END`.

## Workflow permissions (least privilege)

The default workflow requires:
- `pull-requests: write` (post PR comments)
- `contents: write` (commit `ledger/` updates)

If you only need read-only verification (no writes), use a token with:
- `pull-requests: read` (read PR metadata and comments)
- `contents: read` (read repo state for rebuild/verify)

## Token guidance

- Prefer `GITHUB_TOKEN` in GitHub Actions when possible
- Use fine-grained PATs only when cross-repo access is required
- Rotate tokens regularly and scope them to the smallest repo set
- Do not paste tokens into third-party sites, posts, or chat logs

## Threat model

Known risks and how v0.1 handles them:

- Comment deletion or modification by admins
  - Detection: `consilium verify --github` detects mismatches
  - Mitigation: Git-tracked `ledger/` provides an audit trail

- Forged Consilium comments
  - Detection: hash chain breaks on rebuild/verify
  - Mitigation: only the workflow should post Consilium comments

- Token compromise
  - Impact: attacker can post comments or push ledger commits within token scope
  - Mitigation: least-privilege tokens, rotation, audit logs

- Replay or reordering
  - Detection: hash chain enforces a single ordered history

## Reporting

If you find a security issue, please open a GitHub issue with a clear reproduction path.
