# Using Consilium in Another Repo (Agent Setup)

This guide shows how to run Consilium in a separate repository so agents (and humans) can receive credit for merged PRs.

## Summary

Consilium runs as a GitHub Action. On each merged PR it:
1) Computes the credit distribution  
2) Posts a PR comment with canonical JSON  
3) Updates a Git-tracked `ledger/` directory

The PR comment is the source of truth; `ledger/` is derived and rebuildable.

## Step 1: Add the Workflow

Copy `.github/workflows/consilium.yml` into your target repo and update the install step to pull Consilium from GitHub.

Example snippet (replace `<ORG>/<REPO>` and `<REF>`):

```yaml
- name: Install Consilium
  run: pip install git+https://github.com/<ORG>/<REPO>@<REF>
```

If you want to pin a release, use a tag for `<REF>` (recommended).
Example: `pip install git+https://github.com/J-K-Yan/consilium@v0.1.2`

## Step 2: Ensure Permissions

The workflow needs:
- `contents: write` (to commit `ledger/`)
- `pull-requests: write` (to post comments)

If your default branch is protected, allow GitHub Actions to push commits.

## Step 3: (Optional) Configure Credit Rules

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

If the config lives elsewhere, set:
```
CONSILIUM_CONFIG=/path/to/consilium.yaml
```

## Step 4: First Run

Merge a PR. The action will:
- Post a Consilium comment with canonical JSON
- Commit `ledger/` to the repo

## Step 5: Verify

From a local checkout of the target repo:

```bash
pip install git+https://github.com/<ORG>/<REPO>@<REF>
GITHUB_TOKEN=xxx consilium verify --github --repo owner/repo
```

## Operational Notes

- **Source of truth**: PR comments with `CONSILIUM:BEGIN/END`.
- **Derived state**: `ledger/` can be rebuilt at any time.
- **Idempotency**: retries avoid duplicate comments by checking for an existing Consilium comment first.
- **Recovery**: if a comment exists but the ledger is out of sync, run `consilium rebuild --repo owner/repo`.
- **Git ignore**: this repo ignores `ledger/`, so the workflow uses `git add -f ledger/` to commit it in downstream repos.

## Troubleshooting (tested behaviors)

- `PR <n> already has Consilium comment <id>; local ledger out of sync. Run rebuild.`
  - Fix: `consilium rebuild --repo owner/repo` (or delete `ledger/` then rebuild).

- `PR <n> already has Consilium comment <id>; ledger append failed (<error>). Run rebuild.`
  - Fix: run `consilium rebuild --repo owner/repo`.

- `Failed to check existing comments: <error>`
  - Fix: verify `GITHUB_TOKEN` and permissions; retry after transient API issues.

- `GitHub API timeout - try again later`
  - Fix: retry; if it persists, reduce load and confirm token validity.

- `Index is out of sync with entry files; run repair_index().`
  - Fix:
    ```bash
    python -c "from consilium.ledger import Ledger; Ledger('ledger').repair_index()"
    ```
    Or delete `ledger/` and rebuild from GitHub.
