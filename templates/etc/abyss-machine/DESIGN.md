# Abyss Machine Design

This document defines the host-machine form of `abyss-machine`.

It is not an operator command catalog, a stack runtime contract, or a replacement
for `Agents-of-Abyss`, `Tree-of-Sophia`, or `abyss-stack` source truth.

## Role

`abyss-machine` is the local host layer for Abyss OS integration. It owns
machine facts, local policies, hardware evidence, storage routing, launch
planning, dictation controls, safe typed-text intake, local AI runtime evidence,
and read-only bridge contracts for future stack consumers.
It also owns generated machine atlas maps that make those facts navigable across
time, subsystem ownership, causal chains, freshness, and owner-gated handoffs.

The layer exists to make this machine legible and routable. It should help
agents decide what is safe to start, where evidence lives, which source contract
owns a claim, and which project roots must stay read-only from host work.

## System Shape

The host layer is split by root class:

- `{{ABYSS_MACHINE_ETC}}` holds source contracts, policy JSON, manifests, and
  operator-readable law.
- `{{ABYSS_MACHINE_STATE}}` holds durable compact facts, latest JSON, generated
  indexes, validation output, and append-only histories.
- `{{ABYSS_MACHINE_SRV}}` holds large host-owned caches, runtimes, storage,
  tools, temporary artifacts, and design support material.
- `{{ABYSS_MACHINE_RUN}}` and `/run/user/*/abyss-machine` hold ephemeral runtime
  sockets, recordings, and process-local state.
- `{{ABYSS_OS_ROOT}}`, `{{ABYSS_USER_HOME}}/src/abyss-stack`, `/srv/abyss-stack`,
  `/srv/work`, `/work`, `/srv/games`, and `/srv/GAMES` are protected from
  machine-owned mutation unless the operator explicitly routes work there.

The dependency direction is fixed: future `abyss-stack` may consume
`abyss-machine`; `abyss-machine` must not import or mutate `abyss-stack`.

## Authority Layers

When surfaces disagree, prefer this order:

1. Source contracts and policy JSON under `{{ABYSS_MACHINE_ETC}}`.
2. The nearest owner-local `AGENTS.md` for the subsystem or root being changed.
3. Generated compact facts and indexes under `{{ABYSS_MACHINE_STATE}}`.
4. Append-only JSONL histories under `{{ABYSS_MACHINE_STATE}}`.
5. Live runtime/cache state under `/run` and `{{ABYSS_MACHINE_SRV}}`.

Generated facts are evidence and route accelerators. They are not stronger than
source contracts.

## Operating Principles

- Legibility before automation: every durable behavior should have a source
  contract, a machine-readable path, and a validation route.
- Routing before restriction: prefer clear launch plans, CPU/memory/storage
  routes, and context-aware gates over blunt process mutation.
- Evidence before synthesis: use facts, events, episodes, indexes, and quality
  gates before relying on summaries.
- Maps before heavy archives: route through generated atlas entries when a
  question spans time, subsystems, causal chains, or future handoffs, while
  treating those entries as route signals rather than source truth.
- Local ownership before project mutation: host work may expose bridges to
  project repos, but it does not edit project source truth by default.
- Small agents stay useful: resident and recurring local agents should remain
  observable, policy-gated, and easy to route without turning spikes into false
  global failures.
- Documentation is infrastructure: stale, duplicated, or unindexed docs are a
  routing bug, not cosmetic debt.
- Self-maintenance is a oneshot route: `doctor` may coordinate safe generated
  refreshes and reports, but it must not become an unbounded daemon or privileged
  actor.
- Direction, rationale, and history stay split: roadmap records host-wide
  direction, decisions explain durable choices, and the change ledger records
  exact mutation history.

## Non-Goals

- Do not make `abyss-machine` the canonical source for AoA, ToS, or
  `abyss-stack` meaning.
- Do not hide command catalogs inside root orientation documents.
- Do not turn generated `latest.json` files into prose authority.
- Do not turn generated maps into proof, reviewed memory, canonical KAG truth,
  or permission to act.
- Do not claim autonomous action from captured facts, nervous synthesis, or
  stack bridge handoff data.
- Do not use `/work` or `/srv/work` for machine-owned caches, runtimes, logs, or
  generated host artifacts.

## Growth Smells

- Root `AGENTS.md` grows into a second command catalog.
- A subsystem gets a durable root without a local card or index.
- A generated file is cited as source truth without a source contract.
- A bridge claims a writable route into project/work/game roots.
- A timer, resident model, or capture route exists without quality validation.
- A text-input route claims global typing capture without a committed-text
  adapter, secret redaction, and password-field exclusion.
- A command changes without updating `commands.md`, bridge manifests, docs
  audit, and the owning local card.
- `ROADMAP.md` grows into a task list or `CHANGELOG.md` grows into a duplicate
  change ledger.
- Future agents must rediscover why a structural route, boundary, validator, or
  bridge choice was made.

## Validation

Use these checks after changing host design, documentation topology, bridge
contracts, or agent routes:

```bash
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs audit --json
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
```
