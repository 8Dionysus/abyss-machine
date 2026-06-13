# 0017 Stack Observability Bridge Consumer

## Status

accepted

## Date

2026-06-04

## Index Tags

- stack-bridge
- observability
- owner-boundary
- validation-guard

## Current Applicability

As of 2026-06-04, `abyss-machine` consumes abyss-stack observability through a
read-only stack bridge artifact. The stack remains owned by `abyss-stack`; the
machine layer records host-side evidence under
`{{ABYSS_MACHINE_STATE}}/stack-bridge/observability/latest.json`.

## Context

OS Abyss needs the machine layer to use the stack fully enough for future agents
to know whether Prometheus, Grafana, Loki, Alloy, PromQL, and LogQL are
actually available. The pressure was not to move the stack into
`abyss-machine`, but to stop treating stack observability as something the
machine layer only mentions from outside.

The existing bridge contract already said that `abyss-stack` may consume
`abyss-machine`, and that `abyss-machine` must not import or mutate
`abyss-stack`. The new route needed to strengthen usage without breaking that
owner boundary.

## Options Considered

- Keep stack observability entirely inside `abyss-stack`:
  rejected because `abyss-machine stack-bridge` would remain blind to stack
  readiness and could not provide machine-context evidence.
- Let `abyss-machine` mutate stack configs, dashboards, or compose files:
  rejected because it crosses the owner boundary and would make host evidence
  an unreviewed stack authority.
- Add a read-only stack observability consumer artifact:
  accepted because it gives the machine layer live evidence while keeping stack
  source and runtime ownership in `abyss-stack`.

## Decision

Add `abyss-machine stack-bridge observability --json`.

The command writes a compact latest/history readout under the machine-owned
stack bridge state root. It checks:

- required observability containers through sanitized Podman state;
- PromQL against host-exposed Prometheus;
- Grafana `/api/health` without reading credentials;
- internal Loki readiness and LogQL through a running stack container network;
- Alloy ingestion indirectly through Prometheus target state and Loki
  journald-derived labels/log streams.

Expose that readout as `artifacts.observability.stack_observability` and as the
named `stack_observability_bridge`.

## Rationale

This gives future agents a real machine-side proof point for stack
observability instead of an architectural wish. PromQL and LogQL are exercised
as live queries, not only listed as tools.

The route stays read-only. The host layer can say what it observed and can store
bounded evidence, but it does not become the stack owner and does not patch
stack configs, start services, or publish dashboards.

## Consequences

- `abyss-machine stack-bridge --json` now includes the stack observability
  artifact and named bridge.
- `abyss-machine stack-bridge validate --json` checks that the artifact exists
  and that the latest readout has the expected schema.
- Static `/etc` bridge manifests may lag until a privileged static sync writes
  them; dynamic bridge config still exposes the route.
- LogQL samples are truncated and hashed so the artifact is evidence, not a log
  dump.

## Boundaries

Do not infer that `abyss-machine` owns Loki, Alloy, Grafana, Prometheus,
dashboards, compose modules, or stack service selection.

Do not add Grafana credentials to `abyss-machine` for this route. Authenticated
datasource management belongs to the stack side unless a separate owner-reviewed
contract says otherwise.

Do not use this bridge to start, stop, restart, reload, or reconfigure
`abyss-stack`.

## Review Log

- 2026-06-04: Initial accepted record for the read-only stack observability
  bridge consumer.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_LOCAL_BIN_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/stack-bridge/observability/latest.json`
- `{{ABYSS_MACHINE_ETC}}/stack-bridge.json`
- `{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md`
- `{{ABYSS_MACHINE_STATE}}/changes/active/stack-observability-bridge-20260604`

## Validation

- `PYTHONPYCACHEPREFIX={{ABYSS_MACHINE_SRV}}/tmp/pycache python3 -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine stack-bridge observability --json`
- `abyss-machine stack-bridge --json`
- `abyss-machine stack-bridge validate --json`
- `abyss-machine processes containers --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`

## Follow-up Route

Use `abyss-machine stack-bridge observability --json` for live stack
observability evidence. Use `abyss-machine stack-bridge sync-static --json`
only through a privileged operator route when `/etc` static bridge manifests
need to be synchronized with the dynamic route.
