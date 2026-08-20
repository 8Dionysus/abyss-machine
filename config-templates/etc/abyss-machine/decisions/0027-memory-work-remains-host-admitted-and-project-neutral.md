# 0027 Memory Work Remains Host-Admitted And Project-Neutral

## Status

accepted

## Date

2026-07-29

## Index Tags

- memory
- resource-gate
- owner-boundary
- storage-topology
- runtime-admission
- validation-guard

## Current Applicability

As of 2026-07-29, every R1 model, construction, projection, benchmark,
maintenance, storage-growth, and erasure workload must pass the current
`abyss-machine` resource and storage routes. The host may start, defer, soften,
or deny work. It does not receive memory meaning, policy, permission, proof,
or stack ownership.

## Context

The active-organ architecture needs physical facts about memory, swap, PSI,
temperature, storage, runtimes, and local models. Those facts can constrain
work but must not become semantic memory or a reason for `abyss-machine` to
mutate project or stack owner roots.

Phase 13 also demonstrated the need for this boundary: a local E2B benchmark
was admitted, while an E4B workhorse preflight correctly blocked on resource
and swap policy. Forcing the second run would have made benchmark completion
stronger than host law.

## Options Considered

- Let `abyss-stack` decide host capacity internally.
- Let memory policy override machine admission for important work.
- Let `abyss-machine` schedule and mutate project implementation directly.
- Keep host admission independent and project-neutral.

## Decision

Choose the independent project-neutral boundary.

`abyss-machine` owns C18/C19 host references, resource/storage/model plans,
launch gates, host-local erasure extensions, and physical receipts. It may
deny or defer a request without force. Memory, SDK, eval, and runtime owners
must preserve that result.

`abyss-stack` may consume machine evidence. `abyss-machine` does not import or
mutate stack/project roots. Host facts, nervous maps, RAG traces, and local
model availability remain evidence, not reviewed memory, permission, role, or
proof.

Large regenerable caches, models, benchmark outputs, and AI artifacts remain
under the declared `/srv/abyss-machine` roots rather than the limited system
root.

## Rationale

The host is a real physical participant, but giving it project semantics would
invert ownership and make resource observations into authority. Independent
admission keeps both sides repairable and makes refusal a valid system
outcome.

## Consequences

- Heavy or unknown-demand memory work may remain incomplete when host gates
  block it.
- No benchmark may use force merely to fill a comparison matrix.
- The stack must handle deny/defer/soften explicitly.
- Host-local erasure can return residue but cannot close other owners.

## Boundaries

This decision does not activate a service, choose a memory store, authorize
private ingestion, prove benefit, or grant `abyss-machine` authority over
`aoa-memo`, `aoa-sdk`, `abyss-stack`, or `aoa-evals`.

## Review Log

- 2026-07-29: Initial R1 host-admission and project-neutrality record.

## Source Surfaces

- `docs/host/ACTIVE_ORGAN_CONTRACTS.md`
- `schemas/active-organ-host-capability-snapshot-reference.schema.json`
- `schemas/active-organ-host-resource-storage-plan-reference.schema.json`
- `schemas/active-organ-host-erasure-owner-extension-v0.schema.json`
- `src/abyss_machine/active_organ_contracts.py`
- `config-templates/etc/abyss-machine/storage-policy.json`

## Validation

- Validate the active-organ host schemas/examples/module.
- Run public-smoke and full release checks.
- Validate host documentation, topology, graph, and stack bridge.
- `abyss-machine docs audit --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine stack-bridge validate --json`

## Follow-up Route

Keep R1 pull-only runtime activation outside this decision. Revisit only when
the final landing is complete or a new host contract changes resource,
storage, or erasure semantics.
