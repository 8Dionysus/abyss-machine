# 0009 Decision Record Evolution Route

## Status

accepted

## Date

2026-05-21

## Index Tags

- decision-evolution
- review-log
- documentation-topology
- validation-guard
- agent-discipline

## Current Applicability

As of 2026-05-21, this is the active route for evolving existing decision
records. Decision records remain historical rationale records, but every record
must also carry dated current-applicability and review-log sections so later
agents can see what still applies and what changed.

No older claim is struck in this record. Future obsolete claims should be marked
with Markdown strikethrough in `Current Applicability` or the dated `Review Log`
entry that replaces them.

## Context

The decision-review close gate now forces agents to state whether a durable
decision record was added, reused, skipped, or left for backfill. That fixed the
silent-close failure mode, but it did not define how an existing decision should
move when reality changes.

The operator proposed a readable pattern: keep writing inside the same decision
when the same rationale is still being evolved, always date the addition, and
mark stale text with Markdown strikethrough. The remaining risk was turning
accepted decisions into mutable wiki pages where original rationale disappears.

## Options Considered

- Always create a new record for any later change:
  maximally immutable, but too noisy for small applicability shifts.
- Rewrite old records in place:
  easy to read today, but destroys the evidence of why the earlier route was
  accepted.
- Keep historical rationale stable and add dated applicability/review sections:
  preserves the original decision while giving future agents a current route.

## Decision

Use a two-layer decision record model:

- the original `Context`, `Options Considered`, `Decision`, and `Rationale`
  remain the historical rationale;
- `Current Applicability` states the current state of the decision with a date;
- `Review Log` records dated amendments, reviews, applicability changes, and
  supersession notes;
- stale operational claims are marked with Markdown strikethrough only in the
  dated applicability/review layer, paired with the replacement route;
- full route or rationale replacement still requires a new numbered record and
  a `superseded` status on the older record.

The generated decision index must require `Current Applicability` and
`Review Log`, and it must reject records that do not contain dated evidence in
those sections.

## Rationale

This keeps decisions useful for both history and present routing. Future agents
can answer two different questions without mixing them: "why was this accepted
then?" and "what is true now?" Dated review entries make gradual evolution
visible, while superseding records keep major route changes from being hidden
inside a long amendment thread.

## Consequences

- Positive: existing decisions can evolve without losing original rationale.
- Positive: stale claims get visible replacement context instead of silent
  deletion.
- Positive: generated validation now catches records that lack dated
  applicability or review evidence.
- Tradeoff: existing records need a small standardized applicability/review
  backfill.
- Watch: review logs must stay material; they must not become a duplicate
  change ledger.

## Boundaries

This decision does not make `decisions/` a changelog, task tracker, telemetry
log, or command catalog.

This decision does not require a new decision for every small implementation
detail. If no durable rationale moved, close the change with
`--decision-review no-record-needed` and a reason.

This decision does not let agents edit away original rationale. Historical
sections should only be corrected for factual errors, formatting repairs, or
clearly scoped clarifications; material movement belongs in the dated
applicability/review layer or a superseding record.

## Review Log

- 2026-05-21: Initial record. Formalized dated applicability, review logs,
  strikethrough handling for stale claims, and supersede routing.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/README.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/TEMPLATE.md`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/decisions-evolution-route-20260521`

## Validation

- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine stack-bridge validate --json`
- `abyss-machine test quick --json`

## Follow-up Route

Future changes to decision-lane structure should update this record when the
same evolution route still applies, or create a new superseding record when the
record model itself changes. Always rebuild
`abyss-machine docs decisions-index --json` after decision source changes.
