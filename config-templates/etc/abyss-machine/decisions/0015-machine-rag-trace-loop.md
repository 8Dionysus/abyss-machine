# 0015 Machine RAG Trace Loop

## Status

accepted

## Date

2026-05-26

## Index Tags

- rag
- maps
- evidence-trace
- validation-guard

## Current Applicability

As of 2026-05-26, this decision is active for `abyss-machine rag ...`.
Current source behavior is owned by `{{ABYSS_MACHINE_ETC}}/MAPS.md`,
`{{ABYSS_MACHINE_ETC}}/maps-policy.json`, `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`, and
`{{ABYSS_MACHINE_STATE}}/rag/AGENTS.md`.

## Context

Machine atlas maps made route context visible, but route context alone is not a
living retrieval loop. Agents still needed a repeatable way to start from a
maps context packet, open the cited evidence safely, preserve the trace, and
check whether the trace respected source refs and authority boundaries.

The tempting shortcut was to push machine moments into external AoA organs. That
would blur ownership: `aoa-evals` owns proof authority, `aoa-memo` owns reviewed
memory, and `aoa-kag` owns derived KAG truth. The host layer needs a local
trace loop that can inform those future routes without pretending to be them.

## Options Considered

- Keep maps only: simple, but leaves no saved retrieval trace or eval gate.
- Add a broad agent event bus: too early and too easy to confuse with source
  truth.
- Add a read-only machine RAG trace loop over maps packets and bounded evidence
  summaries.

## Decision

Add `abyss-machine rag ...` as a generated, read-only trace surface:

```text
maps context packet -> bounded evidence summaries -> deterministic answer trace -> trace eval
```

The default trace uses `by-rag-run` with `retrieval-context`, writes generated
traces under `{{ABYSS_MACHINE_STATE}}/rag/traces/`, and writes local trace evals
under `{{ABYSS_MACHINE_STATE}}/rag/evals/`.

## Rationale

This gives agents the first working retrieval loop without moving authority out
of the host layer. The trace cites map entries and evidence refs, opens only
bounded summaries, preserves non-claims, and lets validation check the shape.
Future proof, reviewed memory, or KAG work can inspect the trace as external
evidence through its own owner route.

## Consequences

Agents can now ask for a trace rather than manually stitching map entries and
latest files. The host layer gains generated RAG state and a validator. The
tradeoff is that this is deterministic trace synthesis, not a semantic answer
engine or proof bundle. Richer model-backed synthesis can be added later only
after this evidence-preserving loop stays clean.

## Boundaries

RAG traces are not source truth, proof verdicts, reviewed memory, KAG truth,
operator authorization, automatic action, automatic response, or repository
mutation. They do not expose raw private capture payloads and do not deliver
evidence into AoA organs.

## Review Log

- 2026-05-26: Initial accepted record for the read-only machine RAG trace loop.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/MAPS.md`
- `{{ABYSS_MACHINE_ETC}}/maps-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/rag/AGENTS.md`
- `{{ABYSS_USER_HOME}}/src/abyss-stack/mcp/services/abyss-machine-mcp`

## Validation

- `abyss-machine rag validate --json`
- `abyss-machine maps validate --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine stack-bridge validate --json`

## Follow-up Route

Future model-backed RAG, GraphRAG, Agentic RAG, DAG execution, proof review,
memory review, or KAG publication must build on this trace as evidence while
keeping final authority in the owning layer.
