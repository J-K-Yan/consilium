---
title: Maintainer Setup
---

# Maintainer Setup

This guide covers two repo-level settings: branch protections and GitHub Pages.

## Branch Protection (recommended)

Settings → Branches → Add branch protection rule

Suggested rule for `main`:
- Require a pull request before merging
- Require status checks to pass: **CI**
- Require branches to be up to date before merging
- Require signed commits (optional but recommended)
- Require linear history (optional)
- Restrict who can push to matching branches (maintainers only)

Note: the **CI** check comes from `.github/workflows/ci.yml`.

## GitHub Pages (docs)

Settings → Pages

Recommended setup:
- **Source**: Deploy from a branch
- **Branch**: `main`
- **Folder**: `/docs`

This publishes:
- `docs/index.md` (home)
- `docs/protocol.md`
- `docs/agent-setup.md`

