# 0029 Managed Workspace Thin Waist

## Status

accepted

## Date

2026-08-30

## Index Tags

- storage-topology
- runtime-lifecycle
- owner-boundary
- cleanup-executor
- validation-guard

## Current Applicability

As of 2026-08-30, new heavy workspaces may opt into the three-state managed
lifecycle through `abyss-machine resource launch`. Decision 0028 remains the
evidence and reconciliation route for old or unmanaged data; it is not an
automatic deletion authority.

## Context

Repeated storage incidents showed two failures at once: old data required
expensive semantic reconstruction, while new agent work kept creating more
unmanaged data. A path-pattern cleaner would be cheap but unsafe. A detailed
manifest supplied by every agent would be safer but too ceremonial to remain in
use.

## Options Considered

- Continue read-only discovery and manual removal after every incident.
- Grant cleanup from path, age, missing process, or storage pressure rules.
- Put a minimal lease/seal/release protocol in common launchers and leave the
  disposition meaning with each owner.

## Decision

Adopt `open -> sealed -> released` as the managed-workspace thin waist.
Launchers own lease registration and sealing. Owners return only `KEEP`,
`DELETE(plan)`, `ARCHIVE(plan)`, or `UNKNOWN`. The host executor consumes only
valid released plans, revalidates the exact object, applies one bounded action,
and records a receipt.

## Rationale

The common protocol stays small enough to be automatic while preserving the
real semantic boundary: Git decides merge state, Goal decides closure, and each
producer decides which result is preserved. Storage executes a capability it
does not invent.

## Consequences

New managed growth becomes attributable and reclaimable without recurring
whole-tree scans. Existing data is not retroactively trusted and must use the
candidate/reconciliation route. Producers outside common launchers remain
visible as unmanaged integration gaps.

## Boundaries

- Age, pressure, lease expiry, process absence, and a sealed fingerprint do not
  grant release.
- Only launcher-created managed workspaces may be automatically deleted or
  archived in this first stage.
- `KEEP`, `UNKNOWN`, malformed callbacks, fingerprint drift, live references,
  and archive conflicts fail closed.
- The host layer does not infer Git, Goal, pytest, model, or research value.
- This decision does not authorize migration or cleanup of existing `/srv`
  data.

## Review Log

- 2026-08-30: Initial accepted route.

## Source Surfaces

- `src/abyss_machine/storage_lifecycle_contracts.py`
- `src/abyss_machine/storage_lifecycle_adapters.py`
- `src/abyss_machine/resource_runner.py`
- `mechanics/storage-routing/docs/managed-workspace-lifecycle.md`
- `systemd/user/abyss-storage-lifecycle-reaper.timer`

## Validation

- Public smoke covers release authority, existing-directory refusal, callback
  defaults, exact fingerprint execution, and receipts.
- Bootstrap and systemd source tests cover automatic retry installation.

```bash
abyss-machine storage lifecycle status --json
abyss-machine storage lifecycle reap --limit 1 --json
```

## Follow-up Route

Integrate owner callbacks into external-agent, Goal, pytest, worktree, runtime,
build, and benchmark factories through their canonical owner launchers. Track
remaining unmanaged growth as producer integration work, not cleanup policy.
