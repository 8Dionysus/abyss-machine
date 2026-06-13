# 0012 Causal Spine Bridge Route

## Status

accepted

## Date

2026-05-25

## Index Tags

- typing
- causal-binding
- stack-bridge
- heartbeats
- source-freshness
- validation-guard

## Current Applicability

As of 2026-05-25, typing and browser interaction evidence must expose a
causal spine that can answer: what was written, where it was written, to whom
or what it was routed, which task/context it belonged to, and when the event
belongs on the timeline.

New typing events should carry explicit `correlation` evidence. Readmodels may
backfill correlation for older records from event id, time, recipient,
interaction, project, and task anchors.

Active change binding is surface-first. A typing event must not inherit a stale
or unrelated active change merely because some host change is open. Contextual
active-change binding requires explicit policy and a freshness bound.

Stack bridge handoff must expose typing, dictation, reactions, and responses as
first-class evidence layers. Heartbeat source freshness measures readability
and age of source artifacts; the source artifact's own quality verdict remains
in that source's `ok` and `status` fields instead of being collapsed into
freshness.

## Context

The machine needs durable causal understanding of operator interaction,
especially browser and AI interaction. Earlier readouts could show good typing
coverage while stack bridge lacked first-class typing/browser/reaction/response
routes. Active change records could also pollute causal context when an
unrelated long-lived change remained active.

Heartbeat freshness had another ambiguity: a fresh quality scorecard with
`ok=false` was treated like a missing or unreadable source. That made
`source_freshness` report invalid even when the source was current and the
actual issue was a quality score.

## Options Considered

- Leave causal evidence inside subsystem-specific status commands:
  easy, but future agents must rediscover and join routes manually.
- Add a broad event bus:
  expressive, but premature and likely to duplicate existing journals.
- Promote a thin causal spine through existing typing, stack-bridge, and
  heartbeat contracts:
  enough structure for future agents without replacing source journals.

## Decision

Promote causal binding through the existing host contracts:

- typing events and readmodels carry correlation, recipient, where, task, and
  policy evidence;
- active-change task binding defaults to surface match only;
- stack bridge exposes typing, dictation, reactions, and responses artifacts
  plus a `typing_bridge` contract;
- heartbeat source freshness classifies source artifact freshness separately
  from the source artifact's own quality verdict;
- validators must prove the causal-spine bridge artifacts and heartbeat stable
  fields.

## Rationale

This gives future agents a small operational map instead of a large pile of
logs. The source journals remain canonical, but the bridge tells agents which
latest/readmodel routes to inspect first and how to join the evidence.

Surface-first active-change binding protects causality from stale task state.
Separating freshness from quality prevents heartbeat from hiding useful
quality failures behind a misleading "invalid source" label.

## Consequences

- Positive: future audits can inspect typing, dictation, reactions, and
  responses from stack bridge without knowing every subsystem path.
- Positive: causal-context readmodels can place old and new typing events on a
  common timeline.
- Positive: heartbeat can show fresh-but-failing quality artifacts without
  claiming the source is missing.
- Tradeoff: the causal spine is still a readmodel/join route, not a global
  event-sourcing replacement.
- Watch: browser/provider identity and task inference still need natural
  production evidence, not only controlled selftests.

## Boundaries

This decision does not authorize raw keylogging, password capture, secret
capture, hidden-field capture, or automatic action from typed input.

This decision does not make derived readmodels stronger than source journals.

This decision does not mutate `abyss-stack`, AoA, game roots, or project
repositories from the host bridge.

## Review Log

- 2026-05-25: Initial record. Accepted causal-spine bridge route for typing,
  dictation, reactions, responses, and heartbeat freshness semantics.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/typing/`
- `{{ABYSS_MACHINE_STATE}}/heartbeats/`
- `{{ABYSS_MACHINE_STATE}}/stack-bridge/`
- `{{ABYSS_MACHINE_STATE}}/changes/active/causal-spine-coverage-20260525`

## Validation

- `PYTHONPYCACHEPREFIX={{ABYSS_MACHINE_SRV}}/tmp/pycache python -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine typing validate --json`
- `abyss-machine nervous quality-audit --refresh --refresh-index --json`
- `abyss-machine nervous brief --scope now --json`
- `abyss-machine heartbeats validate --json`
- `abyss-machine stack-bridge validate --json`
- `python -m pytest -q {{ABYSS_MACHINE_SRV}}/tests/contract/test_typing_intake.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_heartbeat_bridge_phase5.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_heartbeat_readmodel_core.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_heartbeat_pressure_capture.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_heartbeat_ai_hygiene_phase4.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_cli_json_contracts.py {{ABYSS_MACHINE_SRV}}/tests/contract/test_schema_output_contracts.py`

## Follow-up Route

Future interaction-capture work should extend the causal spine through the
owning subsystem first, then expose a compact route through stack bridge and
heartbeat only when the evidence is validated.
