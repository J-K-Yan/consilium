---
title: Policy Cookbook
---

# Policy Cookbook

Consilium is policy-agnostic. v0.1 ships a simple role-based split that you can tune per repo.

## How policy works

`consilium.yaml` defines the total credit per `pr_merged` event and the role splits:

```yaml
credit:
  pr_merged:
    total: 100
    author: 0.5
    reviewers: 0.3
    approvers: 0.2
```

Rules:
- Shares must sum to 1.0
- If there are no reviewers or approvers, their share is redistributed to the author
- Reviewers and approvers are based on the latest review state

## Example policies

### 1) Balanced default

```yaml
credit:
  pr_merged:
    total: 100
    author: 0.5
    reviewers: 0.3
    approvers: 0.2
```

### 2) Review-heavy (encourages deep review)

```yaml
credit:
  pr_merged:
    total: 100
    author: 0.4
    reviewers: 0.4
    approvers: 0.2
```

### 3) Maintainer-heavy approvals (when approval is scarce)

```yaml
credit:
  pr_merged:
    total: 100
    author: 0.45
    reviewers: 0.2
    approvers: 0.35
```

## Tips

- Keep totals consistent across repos if you want comparable leaderboards
- Start simple, observe behavior, then adjust the split
- For experimental policies (size tiers, labels, clawback), keep them in the roadmap
