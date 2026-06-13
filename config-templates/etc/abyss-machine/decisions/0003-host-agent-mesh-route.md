# 0003 Host Agent Mesh Route

## Status

accepted

## Date

2026-05-13

## Index Tags

- agent-mesh
- route-card-topology
- generated/readout
- validation-guard

## Context

`abyss-machine` has many host roots and subsystems: `/etc`, `/var/lib`, `/srv`,
runtime state, AI, cooling, memory, resource routing, processes, nervous
retrieval, dictation, topology, graph, stack bridge, and change ledger.

Future agents need quick orientation, but a single root `AGENTS.md` cannot carry
all commands, policies, and subsystem details without becoming unreadable.

## Options Considered

- One large root `AGENTS.md` containing every command and subsystem rule.
- Generated-only orientation from latest JSON and indexes.
- Source-backed mesh: compact root route card, local cards, mesh config,
  generated compact mirror, and validation.

## Decision

Use a source-backed agent mesh:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md` remains a compact root route card.
- nearest local `AGENTS.md` owns subsystem or root guidance.
- `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md` owns agent-surface form.
- `{{ABYSS_MACHINE_ETC}}/agents-mesh.json` owns card registration and markers.
- `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json` is generated evidence only.

## Rationale

This keeps low-context entry fast while preserving source truth. The generated
mesh is useful for retrieval and validation, but it cannot author meaning.

The shape matches the long-horizon AoA pattern while respecting that
`abyss-machine` is a host layer with different risks and roots.

## Consequences

Adding a new host card requires registering it in the mesh config and rebuilding
the generated mirror.

Root `AGENTS.md` must stay compact; commands belong in
`{{ABYSS_MACHINE_ETC}}/commands.md`.

Docs audit and topology validation should fail or warn when source docs and
mesh claims drift.

## Boundaries

The mesh does not author subsystem truth. It registers and validates source
cards; local `AGENTS.md` cards and source contracts still own the route they
describe.

## Current Applicability

As of 2026-05-21, this decision remains active. The host agent mesh is still
source-backed, and generated mesh readouts remain evidence rather than
authority.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- `{{ABYSS_MACHINE_ETC}}/agents-mesh.json`
- `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json`
- `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/latest.json`

## Follow-up Route

When card shape, route order, or validation authority moves, update
`DESIGN.AGENTS.md`, `agents-mesh.json`, and docs validators in the same change.

## Validation

- `abyss-machine docs mesh --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine docs audit --json`
- `abyss-machine topology validate --json`
