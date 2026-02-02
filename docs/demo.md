---
title: Demo
---

# Demo: 5-minute walkthrough

This is a clean-room walkthrough for a brand-new repo. It assumes GitHub Actions are enabled.

## Prerequisites

- A repo where you can add workflows and merge PRs
- GitHub Actions enabled
- For verification: a token in `GITHUB_TOKEN` with read access to PRs and comments
- See `SECURITY.md` for least-privilege permissions

## Step 1: Copy the workflow

Copy `.github/workflows/consilium.yml` into your repo. If this is a new repo, update the install
step to pin a release tag:

```yaml
- name: Install Consilium
  run: pip install git+https://github.com/J-K-Yan/consilium@v0.1.2
```

## Step 2: Add minimal config

Create `consilium.yaml` in the repo root:

```yaml
version: "0.1"
credit:
  pr_merged:
    total: 100
    author: 0.5
    reviewers: 0.3
    approvers: 0.2
```

## Step 3: Merge a PR

Open a small PR and merge it. The action runs on `pull_request` close events and only proceeds if the PR was merged.

## Step 4: Expected output

You should see:
- A PR comment from `github-actions[bot]` that includes canonical JSON and a credit table
- New ledger files committed under `ledger/`
  - `ledger/index.json`
  - `ledger/entries/0001.json`

Example comment shape:

````markdown
<!-- CONSILIUM:BEGIN -->
```json
{
  "version": "0.1",
  "type": "credit_mint",
  "outcome": "pr_merged",
  "pr_number": 1,
  "source": "https://github.com/owner/repo/pull/1",
  "distribution": {
    "alice": 50.0,
    "bob": 30.0,
    "charlie": 20.0
  },
  "timestamp": "2026-02-01T22:50:55Z",
  "prev_hash": "genesis",
  "hash": "<full sha256>"
}
```
<!-- CONSILIUM:END -->

## Consilium Credit Distribution

**Outcome**: `pr_merged`
**PR**: #1
**Total Credit**: 100.0

| Contributor | Credit |
|-------------|--------|
| @alice | 50.0 |
| @bob | 30.0 |
| @charlie | 20.0 |
````

## Step 5: Verify

From a local checkout of the repo:

```bash
pipx install git+https://github.com/J-K-Yan/consilium@v0.1.2
GITHUB_TOKEN=xxx consilium verify --github --repo owner/repo
```

## Troubleshooting

- Action did not run
  - Confirm GitHub Actions are enabled and the PR was merged (not closed unmerged)
- No comment posted
  - Check workflow permissions; see `SECURITY.md`
- Ledger did not update
  - Confirm the workflow can push to the default branch
- Verification fails against GitHub
  - Rebuild and compare: `consilium rebuild --repo owner/repo`

## Verifying on someone else's repo

You can verify any repo that runs Consilium:

```bash
GITHUB_TOKEN=xxx consilium verify --github --repo owner/repo
```
