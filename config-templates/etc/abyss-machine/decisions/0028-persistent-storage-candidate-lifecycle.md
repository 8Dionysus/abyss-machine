# 0028 Persistent Storage Candidate Lifecycle

## Status

accepted

## Date

2026-08-01

## Index Tags

- storage-topology
- cleanup-candidates
- owner-evidence
- vault-restore
- validation-guard

## Current Applicability

As of 2026-08-01, recurring storage review is owned by the persistent
`abyss-machine storage candidates` lifecycle under
`{{ABYSS_MACHINE_STATE}}/storage/candidates`. Decision 0020 remains the owner
of artifact-specific evidence; this route joins that evidence with exact
filesystem, Git, Podman, runtime, Vault, process, lease, and owner verdicts.

## Context

Repeated storage pressure investigations rediscovered the same large paths and
then reconstructed safety from names, dates, and a partial process snapshot.
That work did not preserve why a path was blocked, what changed since the last
review, or which exact recovery route would make an action reversible.

The existing cleanup plan is deliberately cautious, but its broad directory
actions and top-process guard cannot establish object-level delete or archive
readiness. A mounted Vault, an old backup record, a missing PID, or an expired
session lease is not enough.

## Options Considered

- Continue manual `du` archaeology. This is accurate only for the current
  operator session and loses evidence history.
- Add a cleanup score. Scores can hide one fatal blocker behind several weak
  positive signals.
- Persist exact candidates and classify them only through hard owner gates.

## Decision

Persist stable candidate records and observation history. Classification uses
named verdicts and hard blockers, never a weighted score. A ready verdict
requires physical on-device size, unique reclaimable size, complete fingerprint,
owner allowlist, current dependency checks, unique-data proof, recovery or
replacement proof, repeated stable observations, and a quiet window.

Use an hourly cheap carry-forward, a daily deep scan, and a rate-limited deep
scan under pressure or significant inventory growth. Emit notification records
only for verdict transitions.

Creation routes may register manifests and renewable claims. Missing or expired
claims never grant removal permission. Validation, approval, and receipt records
bind to one candidate, snapshot, fingerprint, and evidence digest.

## Rationale

The durable unit is the evidence-bearing candidate, not a directory name or a
one-off shell conclusion. Hard gates keep active, unique, protected, stale,
truncated, or owner-unknown objects out of ready states while still preserving
the work needed to make a future decision.

## Consequences

Candidate state is compact host state on `/`; large data remains on `/srv`.
Deep scans can take minutes and therefore run through low-priority resource
admission with bounded time. Parent candidates become summary-only when child
candidates overlap, preventing double-counted reclaim claims.

The first source stage records and validates external actions but does not
contain a new automatic deletion executor.

## Boundaries

- No candidate command automatically deletes, moves, archives, stops, or
  rewrites the subject.
- A ready verdict is not apply permission; exact deep revalidation and explicit
  operator approval are still required.
- Vault mount/timer state is not freshness. Archive readiness requires a fresh
  covering lane, digest match, and verified restore command.
- Podman uses unique layer bytes; unused volumes remain unique-data blockers.
- `.aoa` is never generically classified. Only the session-memory owner dry-run
  may supply cleanup candidates, and its negative verdict cannot be overridden.
- Project, work, game, stack, and unknown `/srv` owners remain protected.

## Review Log

- 2026-08-26: Renumbered from the branch-local `0025` name during current-main
  integration because `0025` is already the accepted external-actor decision;
  the storage source route remains the same and this record is the current
  rationale owner.
- 2026-08-01: Initial accepted route; extends decision 0020 without replacing
  artifact-specific evidence ownership.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/storage-policy.json`
- `{{ABYSS_MACHINE_STATE}}/storage/AGENTS.md`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/storage/candidates/latest.json`
- `{{ABYSS_MACHINE_STATE}}/storage/candidates/manifests/`
- `{{ABYSS_MACHINE_STATE}}/storage/candidates/claims/`
- `{{ABYSS_MACHINE_STATE}}/storage/candidates/validation/`

## Validation

Contract tests cover hard-gate verdicts, sparse physical size, fingerprint
drift, linked and dirty Git worktrees, Podman unique sizes, stale Vault
coverage, `.aoa` owner refusal, leases, approval, and external receipts. CLI,
bootstrap, timer, decision-index, documentation, and full host-contract lanes
must also pass before landing.

## Follow-up Route

Install through the normal bootstrap/change-ledger route, observe several deep
snapshots, then review false-positive and false-negative pressure before any
owner-specific executor is allowed to consume approval records.
