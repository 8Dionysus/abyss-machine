# 0018 Self-Awareness Observability Layer

## Status

accepted

## Date

2026-06-04

## Index Tags

- self-awareness
- stack-bridge
- observability
- owner-boundary
- validation-guard

## Current Applicability

As of 2026-06-04, this decision is active. The current source route is
`{{ABYSS_MACHINE_ETC}}/SELF-AWARENESS.md`, the local route card is
`{{ABYSS_MACHINE_STATE}}/self-awareness/AGENTS.md`, and the implementation is
the `abyss-machine self-awareness ...` command family.

## Context

`abyss-machine` already had a read-only stack observability bridge proving
Prometheus, Grafana, Loki, Alloy, PromQL, and LogQL availability. That was not
enough for the OS Abyss machine shape: the host layer also needs to connect
metrics, logs, alerts, process/container facts, heartbeats, reactions,
responses, typing, trace context, time, and spatial owner surfaces into a
cited machine understanding layer.

The ambiguity was ownership. `abyss-stack` owns runtime observability
configuration and dashboards. `abyss-machine` needs to consume that evidence
without taking over the stack.

## Options Considered

- Keep only `stack-bridge observability`: simple, but leaves correlation,
  causal episodes, alerts-to-reactions, and synthetic E2E proof outside the
  machine contract.
- Implement the layer in `abyss-stack`: closer to Prometheus/Loki/Grafana, but
  crosses the host owner boundary and makes stack runtime own machine memory,
  reactions, and response routing.
- Add `abyss-machine self-awareness` as a read-only consumer: preserves stack
  ownership while giving the machine a durable evidence-to-understanding route.

## Decision

Add `abyss-machine self-awareness` as a host-owned subsystem. It reads stack
observability and existing machine readmodels, writes only under
`{{ABYSS_MACHINE_STATE}}/self-awareness`, exposes artifacts through
`stack_bridge_artifact_routes()`, and validates through
`abyss-machine self-awareness validate --json`.

## Rationale

This keeps ownership clean. `abyss-stack` continues to own Prometheus, Loki,
Alloy, Grafana, dashboards, scrape config, log shipping, and service runtime.
`abyss-machine` owns host facts, route contracts, reaction candidates, response
routes, and generated understanding readmodels.

The route also keeps causal claims conservative: time adjacency is weak,
trace/request/session context is stronger, alerts group lifecycle but do not
prove cause, and every derived brief claim must carry evidence refs.

## Consequences

- Future agents get one command family for causal-temporal-spatial stack
  understanding.
- Stack runtime mutation remains out of scope for the host layer.
- Alert evidence can become reaction candidates, but never automatic action.
- Synthetic E2E proof is required before claiming the whole chain works.
- Static bridge manifests must be synced after dynamic route changes.

## Boundaries

- This decision does not authorize writes to `abyss-stack`.
- This decision does not install Tempo or any trace backend.
- This decision does not treat synthetic alerts as real stack alert rules.
- This decision does not authorize automatic remediation.
- This decision does not make derived causal episodes source truth.

## Review Log

- 2026-06-04: Initial record.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/SELF-AWARENESS.md`
- `{{ABYSS_MACHINE_STATE}}/self-awareness/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/stack-bridge/self-awareness-goal.md`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/changes/active/self-awareness-observability-20260604`

## Validation

- `PYTHONPYCACHEPREFIX={{ABYSS_MACHINE_SRV}}/tmp/pycache python3 -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine self-awareness probe --json`
- `abyss-machine self-awareness validate --json`
- `abyss-machine stack-bridge validate --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine heartbeats validate --json`
- `abyss-machine reactions validate --json`
- `abyss-machine responses validate --json`

## Follow-up Route

The source route is `abyss-machine self-awareness validate --json`. If stack
ownership later adds a trace backend, update this route through a new decision
or a dated review entry after the stack-owned source surface changes.
