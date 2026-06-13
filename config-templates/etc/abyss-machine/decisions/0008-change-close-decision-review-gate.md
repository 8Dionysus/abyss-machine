# 0008 Change Close Decision Review Gate

## Status

accepted

## Date

2026-05-21

## Index Tags

- change-ledger
- decision-review
- validation-guard
- agent-discipline

## Context

`decisions/` was not being updated during several meaningful `abyss-machine`
changes. Backfilling records can repair the archive, but it does not fix the
mechanism that allowed future agents to close host-layer work without deciding
whether durable rationale was needed.

The failure mode is procedural: agents can remember to run validators, but skip
the decision review gate unless the tool forces an explicit closeout choice.

## Options Considered

- Keep the rule only in `AGENTS.md`:
  readable, but already proved too easy to skip.
- Add a separate audit that reports missing decisions later:
  useful for backfill, but still allows the bad close to happen.
- Require decision review in `abyss-machine changes close`:
  makes the close path itself carry the discipline future agents need.

## Decision

Require every `abyss-machine changes close` call to include an explicit
decision review:

- `--decision-review added` with `--decision-ref` when a decision record was
  added;
- `--decision-review existing` with `--decision-ref` when an accepted decision
  already covers the work;
- `--decision-review no-record-needed` with `--decision-reason` when no durable
  rationale is needed;
- `--decision-review backfill-required` with `--decision-reason` when the work
  cannot honestly close the rationale gap yet.

The close result writes the review into `change.json`, the close event, and
`closeout.md`.

## Rationale

This turns decision review from an agent memory burden into a tool-enforced
host-layer contract. The agent still has to judge whether a decision is needed,
but it cannot close a durable host change without making that judgment explicit
and recoverable.

## Consequences

- Positive: future skipped decision reviews become command failures, not silent
  drift.
- Positive: changes can point at an existing accepted decision instead of
  misusing `no-record-needed`.
- Positive: `changes index` can expose decision-review status for closed records.
- Tradeoff: simple generated-refresh changes need a short no-record-needed
  reason at closeout.
- Watch: older scripts that call `changes close` need to be updated when they
  are still active operational routes.

## Boundaries

This decision does not require a new decision for every small implementation
step. It requires every closeout to state the decision-review result.

This decision does not make the change ledger stronger than accepted decision
records or current source surfaces.

## Current Applicability

As of 2026-05-21, this decision remains active. The close gate still enforces
explicit decision review for change closeout, and decision `0009` now defines
how existing accepted decision records should evolve after that review.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; close-gate behavior itself did not change.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/changes/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/changes/active/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/commands.md`
- `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/README.md`

## Validation

- `abyss-machine changes close --help`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine test quick --json`

## Follow-up Route

Backfill missing post-2026-05-18 decisions from the closed change ledger, then
use the close gate to prevent the same class of drift from returning.
