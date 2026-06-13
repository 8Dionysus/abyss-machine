# 0007 OS Abyss Heartbeat Reaction Response Chain

## Status

accepted

## Date

2026-05-18

## Index Tags

- heartbeats
- reactions
- responses
- owner-gated-action

## Context

OS Abyss needs recurring machine pulses and deeper reaction surfaces without turning every observed fact into permission to mutate the host. Naming is topology here: future agents need stable words that distinguish a recurring pulse, a detected reaction candidate, and an owner-gated response route.

## Options Considered

- Put everything under `heartbeats`:
  compact, but it would blur observation, candidate generation, and response routing.
- Rename the next layer `reflexes`:
  expressive, but it implies automatic execution before an owner-routed policy gate exists.
- Split the chain into `heartbeats`, `reactions`, and `responses`:
  slightly more surface area, but each word maps to a different authority boundary.

## Decision

Use this host-layer chain:

```text
heartbeats -> reactions -> responses -> explicit owner-approved action
```

The plural subsystem names are `heartbeats`, `reactions`, and `responses`. One durable heartbeat record is a `heartbeat_pulse`; one routed response record is a `response_route`.

## Rationale

This keeps recurring observation, evidence-to-candidate analysis, and response routing separate. A heartbeat can run on a timer, a reaction can describe what deserves attention, and a response can preserve the route toward action without executing it.

The word `responses` is intentionally less automatic than `reflexes`. It leaves room for future automation, but only after an explicit owner route, policy gate, validator, and change record exist.

## Consequences

- Future agents can ask for `abyss-machine heartbeats pulse --json` to orient quickly.
- Future agents can ask for `abyss-machine reactions --json` to inspect candidates.
- Future agents can ask for `abyss-machine responses --json` to inspect owner-gated response routes.
- Automatic execution remains out of scope for these three readmodels.
- Any future executor must be introduced as a separate route with separate validation and rollback.

## Boundaries

This decision does not authorize automatic action. Heartbeats observe,
reactions classify candidates, and responses preserve owner-gated routes; any
executor must be introduced as a separate accepted route with its own policy,
validator, and rollback.

## Current Applicability

As of 2026-05-21, this decision remains active. `heartbeats`, `reactions`, and
`responses` remain separate read-model/route layers, and automatic execution
still requires a separate owner route.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`
- `{{ABYSS_MACHINE_ETC}}/commands.md`
- `{{ABYSS_MACHINE_STATE}}/heartbeats/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/reactions/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/responses/AGENTS.md`

## Follow-up Route

The change ledger records are `{{ABYSS_MACHINE_STATE}}/changes/closed/responses-readmodel-20260518` for the implementation and `responses-naming-decision-20260518` for this decision install. Future automatic response execution requires a new owner route and must not be smuggled into `heartbeats`, `reactions`, or `responses`.

## Validation

- `abyss-machine heartbeats validate --json`
- `abyss-machine reactions validate --json`
- `abyss-machine responses validate --json`
- `abyss-machine topology validate --json`
