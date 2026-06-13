# 0001 Roadmap, Decisions, And Changelog Route

## Status

accepted

## Date

2026-05-13

## Index Tags

- root/topology
- documentation-topology
- direction-split
- change-ledger-boundary

## Context

`abyss-machine` had source contracts, local cards, generated docs mesh, topology,
bridge, command catalog, and a detailed host change ledger. It still lacked a
clean long-horizon direction surface and a durable rationale lane for choices
that future agents are likely to revisit.

The risk was either under-documenting direction or overloading existing files:
`AGENTS.md` could become a process archive, `DOCS.md` could become a roadmap,
and the change ledger could be treated as if it explained design intent.

## Options Considered

- No new surfaces: keep using `DOCS.md`, `AGENTS.md`, and the change ledger.
- Task backlog roadmap: add a roadmap that lists active and future tasks.
- AoA-style direction split: add root `ROADMAP.md`, sparse `CHANGELOG.md`, and
  `decisions/` with strict source-boundary roles.

## Decision

Use the AoA-style direction split adapted to the host layer:

- `{{ABYSS_MACHINE_ETC}}/ROADMAP.md` owns host-wide direction and future triggers.
- `{{ABYSS_MACHINE_ETC}}/decisions/` owns durable rationale for repeatable "why".
- `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md` records sparse curated milestones.
- `{{ABYSS_MACHINE_STATE}}/changes/` remains the canonical host mutation history.

## Rationale

Future agents need to know what direction the machine is moving, why durable
route choices were made, and where exact host mutation evidence lives. One file
cannot do all three without becoming noisy or stale.

This split keeps the roadmap from becoming a backlog, keeps the changelog from
becoming an event stream, and keeps decisions from overriding current source
contracts.

## Consequences

Future host-wide direction changes must review `ROADMAP.md`.

Future structural or boundary changes must run the decision review gate and
either add a record or state why no record was needed.

Detailed chronology stays in the change ledger; the changelog is intentionally
sparse.

## Boundaries

This decision does not make `ROADMAP.md`, `CHANGELOG.md`, `decisions/`, and the
change ledger interchangeable. The roadmap carries direction, the changelog
carries curated milestones, decisions explain durable why, and the change
ledger preserves exact mutation history.

## Current Applicability

As of 2026-05-21, this decision remains active. The direction split still
stands: `ROADMAP.md` owns host-wide direction, `CHANGELOG.md` owns sparse
milestones, `decisions/` owns durable rationale, and the change ledger owns
exact host mutation history.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/ROADMAP.md`
- `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/`
- `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/changes/`

## Follow-up Route

Validate through:

```bash
abyss-machine docs audit --json
abyss-machine docs mesh-validate --json
abyss-machine topology validate --json
```

Add subsystem-local roadmaps only when repeated subsystem future pressure becomes
too narrow for the root roadmap and too broad for a single change record.

## Validation

- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
