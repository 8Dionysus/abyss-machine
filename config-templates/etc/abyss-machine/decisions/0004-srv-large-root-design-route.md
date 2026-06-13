# 0004 Large Root Design Route

## Status

accepted

## Date

2026-05-13

## Index Tags

- large-root
- storage-topology
- srv-boundary
- source-boundary

## Context

`{{ABYSS_MACHINE_SRV}}` carries large host-owned caches, runtimes, storage, tools,
temporary artifacts, hooks, and design-support material. It is not a project
repository, but it is also not just disposable cache.

Without a local design contract, future agents could either treat `/srv` as
unstructured scratch space or accidentally move source authority out of
`{{ABYSS_MACHINE_ETC}}`.

## Options Considered

- Keep `{{ABYSS_MACHINE_SRV}}` documented only by root topology.
- Use only `{{ABYSS_MACHINE_SRV}}/AGENTS.md`.
- Add a subordinate `{{ABYSS_MACHINE_SRV}}/DESIGN.md` with local route cards and
  mesh validation.

## Decision

Use `{{ABYSS_MACHINE_SRV}}/DESIGN.md` as the local large-root design contract,
subordinate to `{{ABYSS_MACHINE_ETC}}` source authority.

`{{ABYSS_MACHINE_SRV}}/AGENTS.md` stays the root route card for the large root, and
`{{ABYSS_MACHINE_SRV}}/design/AGENTS.md` routes design artifacts.

## Rationale

The large root needs clear internal structure because it carries data that can
be large, mutable, regenerable, durable, or tool-like. A local design contract
makes those distinctions explicit without promoting `/srv` above `/etc`.

This also protects the limited system root by making `{{ABYSS_MACHINE_SRV}}` the
normal place for large caches, runtimes, model artifacts, temporary AI output,
and storage-heavy host work.

## Consequences

Future changes to cache, runtime, storage, tmp, tools, hooks, or design-artifact
routing should review `{{ABYSS_MACHINE_SRV}}/DESIGN.md`.

`{{ABYSS_MACHINE_SRV}}` must not become a source checkout, hidden project root, or
symlink tail for protected owner roots.

## Boundaries

This decision keeps `{{ABYSS_MACHINE_SRV}}` subordinate to `{{ABYSS_MACHINE_ETC}}`.
It does not move policy authority, project source truth, or stack-owned runtime
promotion decisions into the large root.

## Current Applicability

As of 2026-05-21, this decision remains active. `{{ABYSS_MACHINE_SRV}}` remains a
large host-owned mutable plane subordinate to source authority under
`{{ABYSS_MACHINE_ETC}}`.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `{{ABYSS_MACHINE_SRV}}/DESIGN.md`
- `{{ABYSS_MACHINE_SRV}}/AGENTS.md`
- `{{ABYSS_MACHINE_SRV}}/design/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DESIGN.md`
- `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`

## Follow-up Route

Validate through:

```bash
abyss-machine docs mesh-validate --json
abyss-machine docs audit --json
abyss-machine storage validate --json
abyss-machine topology validate --json
```

## Validation

- `abyss-machine docs mesh-validate --json`
- `abyss-machine docs audit --json`
- `abyss-machine storage validate --json`
- `abyss-machine topology validate --json`
