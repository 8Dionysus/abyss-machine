# Abyss Machine Stack Bridge

This is the host-machine handoff contract for future `abyss-stack` integration.

## Contract

- Owner: Abyss Machine host layer.
- Consumer: future `abyss-stack` bridge and local agents.
- Main command: `abyss-machine stack-bridge --json`.
- Validation command: `abyss-machine stack-bridge validate --json`.
- Static manifest: `{{ABYSS_MACHINE_ETC}}/stack-bridge.json`.
- Latest export bundle: `{{ABYSS_MACHINE_STATE}}/stack-bridge/latest.json`.
- Agent entrypoint: `{{ABYSS_MACHINE_STATE}}/stack-bridge/AGENTS.md`.

## Boundaries

- Read-only by default.
- `abyss-stack` may consume `abyss-machine`.
- `abyss-machine` must not import or mutate `abyss-stack`.
- Do not write to `{{ABYSS_OS_ROOT}}`, `/srv/abyss-stack`, `{{ABYSS_USER_HOME}}/src/abyss-stack`, `/work`, `/srv/work`, or `/srv/GAMES` from this bridge.
- Synthesis candidates are orientation artifacts, not canonical truth.

## First Commands

Start from the bridge, topology, nervous, AI, storage, and heartbeat routes in
[commands.md](commands.md).

## Artifact Classes

- `machine`: bridge, topology, graph, change ledger.
- `mode`: host work-mode policy, latest plan, validation, thermal launch gate, and battery saver enforcement.
- `ai`: devices, capabilities, runtime, workloads, LLM registry/validation, TTS profiles.
- `storage`: pressure, cleanup plan, write preflight.
- `processes`: latest process snapshot and thermal attribution.
- `nervous`: facts, events, episodes, retrieval, synthesis, evals, retention.
- `heartbeats`: compact OS Abyss heartbeat readmodel and validation gate.
- `observability`: thermal and battery telemetry.
- `cooling`: cooling status and thermal audit evidence.

## Handoff Rule

Future stack-side agents should treat `{{ABYSS_MACHINE_STATE}}/stack-bridge/latest.json` as a map of evidence pointers. Read cited facts, events, evals, and recall packs before making claims or changing runtime routing.

Treat heartbeat refs as compact orientation only after `abyss-machine heartbeats validate --json` proves `source_freshness`, `rhythm`, `candidate_lifecycle`, `pressure_context`, `capture_health`, and `ai_hygiene`. The heartbeat bridge does not execute reactions, responses, cleanup, browser diagnostics, model review, or stack promotion.

Before starting local AI, compiler, benchmark, or sustained agent work from the stack side, use `abyss-machine resource plan --class CLASS --kind KIND --json` as final host admission. `abyss-machine mode plan --json` exposes `base_max_unattended_class` as power-mode advice and may promote the effective `max_unattended_class` only when the live CPU owner authorizes a route. Neither plan starts workloads or replaces stack-owned runtime launchers.
