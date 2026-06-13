# 0013 Machine Atlas Maps Route

## Status

accepted

## Date

2026-05-26

## Index Tags

- maps
- route-atlas
- boundary-context
- validation-guard

## Current Applicability

As of 2026-05-26, this decision establishes `{{ABYSS_MACHINE_ETC}}/MAPS.md` and
`{{ABYSS_MACHINE_STATE}}/maps/` as the host-machine atlas route. It is active for
RAG, GraphRAG, Agentic RAG, eval, memo, KAG, resource, and causal-orientation
work that needs route signals across multiple host subsystems. Packet
destination semantics from the initial route are superseded by
[0014 Machine Atlas Reader Profile Packets](0014-machine-atlas-reader-profile-packets.md):
`maps packet` is reader-profile boundary context, not an AoA organ destination.

## Context

`abyss-machine` already had a generated host graph and a nervous evidence layer.
The graph made host structure visible, and nervous read models made events,
episodes, recall, synthesis, and freshness visible. What was missing was an
agent-facing atlas that could route across time, subsystems, causal chains,
freshness, resource state, privacy risk, actionability, and future
RAG/eval/memo/KAG boundary work without forcing every agent to open heavy
histories or raw captures.

## Options Considered

- Extend `graph`: useful for structure, but it would overload the graph with
  temporal and actionability questions.
- Extend `nervous`: useful for observed facts, but it should not become the
  owner of atlas routing or AoA organ semantics.
- Add `maps`: a generated read model that sits above graph/nervous as a route
  atlas while preserving source and owner boundaries.

## Decision

Add `abyss-machine maps ...` as a generated machine-atlas surface. Source law is
`{{ABYSS_MACHINE_ETC}}/MAPS.md` and `{{ABYSS_MACHINE_ETC}}/maps-policy.json`.
Generated state lives under `{{ABYSS_MACHINE_STATE}}/maps/`.

## Rationale

Maps answer a different question than graph or nervous. They do not ask only
what exists or what was observed; they ask where an agent should route next and
why that route is evidence-backed. This supports future RAG/GraphRAG/Agentic
RAG and DAG work because trace packets, eval packets, memory candidates, and
KAG exports need route context before they become proof, memory, or canonical
derived knowledge.

## Consequences

Future agents get a compact `START.md`, axis indexes, and queryable JSON entries
before opening heavy state. Validators can enforce truth status, evidence refs,
and non-action policy. The host layer becomes more legible without becoming the
canonical owner of AoA proof, reviewed memory, KAG truth, or stack runtime
meaning.

## Boundaries

Maps are route signals, not source truth. They do not authorize automatic
actions. They do not replace `{{ABYSS_MACHINE_ETC}}` source contracts, validators,
change-ledger records, `aoa-evals`, `aoa-memo`, `aoa-kag`, or `abyss-stack`.
Protected project roots remain read-only from the host layer.

## Review Log

- 2026-05-26: Initial accepted record for machine atlas maps.
- 2026-05-26: Packet destination semantics superseded by
  [0014](0014-machine-atlas-reader-profile-packets.md); maps remain active as
  route signals, while packets are reader-profile boundary context.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/MAPS.md`
- `{{ABYSS_MACHINE_ETC}}/maps-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/maps/AGENTS.md`

## Validation

- `abyss-machine maps validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine docs mesh --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine docs audit --json`
- `abyss-machine stack-bridge validate --json`

## Follow-up Route

Future RAG/GraphRAG work should emit trace/evidence packets that appear under
`by-rag-run`, `by-eval-packet`, `by-memory-candidate`, and `by-kag-export`
without making `abyss-machine` the owner of eval, memory, or KAG canon.
