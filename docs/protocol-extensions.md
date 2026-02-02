# Consilium Protocol Extensions (Roadmap)

This document is NON-NORMATIVE. It describes optional modules that may be adopted
after observing real usage.

## 0. Design Rule
Extensions MUST NOT violate Core invariants:
- determinism
- auditability
- negative externalities representable

## 1) Lifecycle: provisional -> finalize
Trigger:
- Frequent disputes about "credit should be reversed later"
- Or meaningful revert rate

Idea:
- Mint provisional credits on merge
- Finalize after a maturity window if no revert/incident
- Represent finalize/clawback either as separate event types or as policy-level semantics
  using negative/positive deltas referencing earlier events.

Minimal Implementation:
- Keep Core event type `credit_mint`.
- Use `meta.stage = provisional|finalized` (policy-defined).
- Use later negative delta events for clawback.

## 2) Automated clawback
Trigger:
- Reverts are happening
- Incidents cause real maintenance cost

Minimal Implementation:
- A workflow that detects revert commits or linked incident issues
- Emits a negative delta event referencing the original event (`ref`)

## 3) Quality Gates (enforcement)
Trigger:
- PR quality becomes a real pain: broken CI, missing tests/docs, frequent regressions

Start with "measure-only":
- Record metrics in `meta` (tests run, files changed, review count, time-to-merge)
- No enforcement

Then "enforce":
- Policy refuses mint unless gates passed (or reduces base credit)

## 4) Attestations (review/adoption)
Trigger:
- Need to price maintainer attention (review attestations)
- Have real downstream users (adoption attestations)

Minimal Implementation:
- Define a new event type `attestation` (or keep `credit_mint` with `meta.kind`)
- Require strong evidence links
- Consider signatures if attacker model exists

## 5) Backflow / composability dividend
Trigger:
- Multiple downstream projects exist
- Strong adoption evidence is available

Minimal Implementation:
- A small capped portion of impact credit flows upstream (1-2 hops max)
- Strict caps + strong evidence to prevent gaming

## 6) Signatures & Identity
Trigger:
- Cross-domain identity is needed OR
- Evidence of impersonation / malicious forging exists

Minimal Implementation:
- `identities/<actor>.json` binds actor_id to a public key
- Attestation events include signature over canonical payload
- Verifiers validate signatures deterministically
