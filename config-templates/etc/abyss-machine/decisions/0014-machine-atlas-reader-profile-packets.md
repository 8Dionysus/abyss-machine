# 0014 Machine Atlas Reader Profile Packets

## Status

accepted

## Date

2026-05-26

## Index Tags

- maps
- reader-profile
- owner-boundary
- validation-guard

## Current Applicability

As of 2026-05-26, this decision is active for `abyss-machine maps packet`.
Machine atlas packets are agent reader-profile context: a bounded lens for the
current agent, not delivery into AoA organs. Current behavior is owned by
`{{ABYSS_MACHINE_ETC}}/MAPS.md`, `{{ABYSS_MACHINE_ETC}}/maps-policy.json`, and the
`abyss-machine maps packet --reader-profile PROFILE --json` CLI.

## Context

An earlier draft of the maps packet route used destination language and organ
examples. That made host-machine moments look like material being sent into
AoA organs. The organ boundary is stricter: `aoa-evals` owns bounded proof,
`aoa-memo` owns reviewed memory, and `aoa-kag` owns derived KAG truth.
`abyss-machine` may expose host context to an agent, but it must not model AoA
organs as destinations for machine packets.

## Options Considered

- Keep the initial destination model: less churn, but preserves the wrong
  model.
- Keep organ-named profiles with stronger warnings: still suggests that organs
  are destinations.
- Replace the public shape with reader profiles and remove organ destinations.

## Decision

Use reader-profile context packets exclusively. Use profiles such as `agent`,
`proof-context`, `memory-context`, `knowledge-context`, `graph-context`,
`retrieval-context`, and `runtime-context`. The maps packet contract exposes
`--reader-profile`, `reader_profile`, and `profile_route`; no
destination-shaped packet API is retained.

## Rationale

This keeps the host boundary honest. The packet describes how the current agent
should read host evidence; it does not prescribe what an AoA organ should
accept. External repositories remain authority surfaces, and any later proof,
memory, or KAG movement must be pulled and reviewed through that owning layer.

## Consequences

Agents get a clean packet contract with no destination semantics. Calls using
the retired destination-shaped API fail and must be corrected. Maps may
still point to owner boundaries through `by-owner-route`, but context packets
should carry host evidence first and avoid treating AoA route cards as packet
payload.

## Boundaries

Reader profiles are not destinations, acceptance records, import queues,
reviewed memory, proof bundles, KAG publications, or stack promotion decisions.
This decision does not grant `abyss-machine` authority over `aoa-evals`,
`aoa-memo`, `aoa-kag`, or `abyss-stack`.

## Review Log

- 2026-05-26: Initial accepted record replacing destination packet semantics
  with reader-profile boundary context.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/MAPS.md`
- `{{ABYSS_MACHINE_ETC}}/maps-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_USER_HOME}}/src/abyss-stack/mcp/services/abyss-machine-mcp`

## Validation

- `abyss-machine maps validate --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `python mcp/services/abyss-machine-mcp/scripts/validate_machine_mcp.py`
- `python -m pytest mcp/services/abyss-machine-mcp/tests -q`

## Follow-up Route

If a future task needs real proof, memory, KAG, or runtime publication, route
to the owning organ or repo explicitly. Do not add organ destinations back to
`abyss-machine` packet contracts.
