# Abyss Machine Topology

This document is the host-machine topology contract for `abyss-machine`.

It tells future agents where machine-side truth lives, where generated facts
land, where large data belongs, and which roots must not be mutated from the
host layer.

## Layer

`abyss-machine` is the host-machine layer for Abyss OS integration.

It owns host facts, host policies, local hardware evidence, storage routing,
thermal and process observability, dictation controls, AI runtime evidence, and
machine-readable bridge contracts.

It does not own AoA, ToS, or `abyss-stack` source truth.

Dependency direction:

```text
abyss-stack may consume abyss-machine.
abyss-machine must not import or mutate abyss-stack.
```

## First Commands

```bash
abyss-machine enter --json
abyss-machine docs mesh-validate --json
abyss-machine topology --json
abyss-machine topology validate --json
abyss-machine topology audit --json
abyss-machine graph --json
abyss-machine graph validate --json
abyss-machine bridge --json
abyss-machine stack-bridge --json
abyss-machine stack-bridge validate --json
abyss-machine doctor --json
abyss-machine heartbeats pulse --json
abyss-machine reactions --json
abyss-machine responses --json
abyss-machine changes status --json
abyss-machine changes preflight --intent TEXT --surface SURFACE --json
abyss-machine storage pressure --json
abyss-machine nervous status --json
```

## Root Classes

| Class | Root | Role |
|---|---|---|
| stable config | `{{ABYSS_MACHINE_ETC}}` | source configs, docs, bridge contracts, operator-readable policy |
| durable facts | `{{ABYSS_MACHINE_STATE}}` | latest facts, append-only histories, indexes, change ledger |
| large machine root | `{{ABYSS_MACHINE_SRV}}` | large host-owned caches, runtimes, tools, storage, design artifacts |
| ephemeral runtime | `{{ABYSS_MACHINE_RUN}}`, `/run/user/1000/abyss-machine` | sockets, recordings, process-local state |
| project workspace | `{{ABYSS_OS_ROOT}}` | read-only project material unless an explicit owner route says otherwise |

Do not use `/work` or `/srv/work` for machine-owned caches, runtimes, logs, or
model artifacts.

## Surface States

| State | Meaning | Normal route |
|---|---|---|
| `source-config` | stable host policy and contracts | `{{ABYSS_MACHINE_ETC}}` |
| `host-fact` | latest compact generated fact | `{{ABYSS_MACHINE_STATE}}/*/latest.json` |
| `history` | append-only evidence | `{{ABYSS_MACHINE_STATE}}/*/YYYY/MM/YYYY-MM-DD.jsonl` |
| `large-cache` | regenerable host-owned cache | `{{ABYSS_MACHINE_SRV}}/cache` |
| `large-runtime` | large mutable host runtime/storage | `{{ABYSS_MACHINE_SRV}}/runtimes`, `{{ABYSS_MACHINE_SRV}}/storage` |
| `runtime` | ephemeral live state | `{{ABYSS_MACHINE_RUN}}`, `/run/user/1000/abyss-machine` |
| `bridge` | machine-readable entry contract | `{{ABYSS_MACHINE_ETC}}/bridge.json`, `{{ABYSS_MACHINE_ETC}}/stack-bridge.json`, `{{ABYSS_MACHINE_STATE}}/topology`, `{{ABYSS_MACHINE_STATE}}/changes`, `{{ABYSS_MACHINE_STATE}}/stack-bridge` |
| `project-readonly` | source repositories and project material | `{{ABYSS_OS_ROOT}}`, `/srv/abyss-stack`, `{{ABYSS_USER_HOME}}/src/abyss-stack` |

When two surfaces disagree, prefer:

1. source config under `{{ABYSS_MACHINE_ETC}}`
2. owner-local `AGENTS.md`
3. generated latest/index JSON under `{{ABYSS_MACHINE_STATE}}`
4. append-only history JSONL
5. runtime or cache state

## Change Ledger

Host-layer changes are recorded under:

```text
{{ABYSS_MACHINE_STATE}}/changes/
```

Use:

```bash
abyss-machine changes record --id ID --title TITLE --intent TEXT --surface SURFACE --json
abyss-machine changes close --id ID --decision-review existing --decision-ref DECISION --note "validated and complete" --json
abyss-machine changes status --json
abyss-machine changes latest --json
abyss-machine changes preflight --intent TEXT --surface SURFACE --json
abyss-machine topology validate --json
```

The ledger is for machine-side changes only. It must not become a hidden issue
tracker for AoA, ToS, `abyss-stack`, work projects, or private notes.

## Protected Roots

The host layer may read these roots for routing evidence, but must not mutate
them unless the operator explicitly routes work to the owning repository:

```text
{{ABYSS_OS_ROOT}}
{{ABYSS_OS_ROOT}}/abyss-stack
/srv/abyss-stack
{{ABYSS_USER_HOME}}/src/abyss-stack
/srv/GAMES
/srv/games
/srv/work
/work
```

Storage automation must use `abyss-machine storage write-preflight` before
large writes and must route machine-owned data to `{{ABYSS_MACHINE_SRV}}`.

## Bridge Contract

Stable machine-readable entry points:

```text
{{ABYSS_MACHINE_ETC}}/bridge.json
{{ABYSS_MACHINE_ETC}}/stack-bridge.json
{{ABYSS_MACHINE_ETC}}/DESIGN.md
{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md
{{ABYSS_MACHINE_ETC}}/ROADMAP.md
{{ABYSS_MACHINE_ETC}}/CHANGELOG.md
{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md
{{ABYSS_MACHINE_ETC}}/agents-mesh.json
{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md
{{ABYSS_MACHINE_SRV}}/DESIGN.md
{{ABYSS_MACHINE_STATE}}/topology/latest.json
{{ABYSS_MACHINE_STATE}}/topology/index.json
{{ABYSS_MACHINE_STATE}}/topology/validate/latest.json
{{ABYSS_MACHINE_STATE}}/topology/audit/latest.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json
{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/latest.json
{{ABYSS_MACHINE_STATE}}/changes/index.json
{{ABYSS_MACHINE_STATE}}/changes/preflight/latest.json
{{ABYSS_MACHINE_STATE}}/graph/latest.json
{{ABYSS_MACHINE_STATE}}/graph/index.json
{{ABYSS_MACHINE_STATE}}/graph/validate/latest.json
{{ABYSS_MACHINE_STATE}}/stack-bridge/latest.json
{{ABYSS_MACHINE_STATE}}/stack-bridge/validate/latest.json
```

Bridge consumers should start with:

```bash
abyss-machine enter --json
abyss-machine docs mesh-validate --json
abyss-machine stack-bridge --json
abyss-machine topology validate --json
abyss-machine stack-bridge validate --json
abyss-machine graph validate --json
abyss-machine mode plan --json
abyss-machine mode validate --json
```

Then follow the specific owner command for storage, AI, dictation, cooling, mode,
processes, observability, or nervous-system facts.

## Growth Guards

Use these before expanding the host layer:

```bash
abyss-machine changes preflight --intent TEXT --surface SURFACE --json
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs audit --json
abyss-machine storage validate --json
abyss-machine ai validate --json
abyss-machine cooling validate --json
abyss-machine mode validate --json
abyss-machine processes validate --json
abyss-machine nervous validate --json
abyss-machine stack-bridge validate --json
abyss-machine dictation validate --json
abyss-machine graph query --node ai --json
```

Preflight is a mutation gate, not a bureaucracy gate: it hard-denies protected
boundaries by default, but warnings are allowed for stale or optional evidence
so future expansion is not blocked prematurely.

## Non-Claims

- This topology does not redefine `Agents-of-Abyss`, `Tree-of-Sophia`, or
  `abyss-stack`.
- Generated host facts accelerate orientation, but they do not replace stronger
  owner repositories.
- The host layer may prepare bridges for future `abyss-stack` integration, but
  it does not promote stack runtime truth by itself.
