# Abyss Machine Host Layer

Root route card for `abyss-machine`: read this first, then the nearest local card and source contract.

## Applies to

Applies to host-machine work under:

- `{{ABYSS_MACHINE_ETC}}`
- `{{ABYSS_LOCAL_BIN_DIR}}/abyss-machine`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `/usr/local/share/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}`
- `{{ABYSS_MACHINE_SRV}}`
- host-owned user or system units that operate those roots

Does not grant write authority over `{{ABYSS_OS_ROOT}}`, `abyss-stack`, work
projects, games, or private roots.

## Role

`abyss-machine` owns host facts, policies, hardware evidence, storage routing,
resource launch planning, dictation controls, safe typed-text intake, local AI
runtime evidence, and read-only bridge contracts.

For system form, read `{{ABYSS_MACHINE_ETC}}/DESIGN.md`.
For agent-surface form, read `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`.
For documentation hierarchy, read `{{ABYSS_MACHINE_ETC}}/DOCS.md`.
For host-wide direction, read `{{ABYSS_MACHINE_ETC}}/ROADMAP.md`.
For durable rationale, read `{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md`.
For curated milestone contour, read `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md`.
For root, surface, and owner-boundary topology, read `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`.

Keep this file as a route card. Do not turn it into a command catalog; command
lists belong in `{{ABYSS_MACHINE_ETC}}/commands.md`.

## Read before editing

For broad host work:

```bash
abyss-machine enter --json
abyss-machine topology --json
abyss-machine topology audit --json
abyss-machine doctor --json
abyss-machine heartbeats pulse --json
abyss-machine reactions --json
abyss-machine responses --json
abyss-machine stack-bridge --json
abyss-machine mode plan --json
abyss-machine docs audit --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
abyss-machine rag validate --json
```

Then read the nearest local card or local design contract:

- `{{ABYSS_MACHINE_ETC}}/*/AGENTS.md` for stable config lanes, hooks, and local source-policy boundaries.
- `{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md` before durable structural, route-law, validation, bridge, or topology rationale.
- `{{ABYSS_MACHINE_SRV}}/DESIGN.md` and `{{ABYSS_MACHINE_SRV}}/AGENTS.md` for large host-owned roots.
- `{{ABYSS_MACHINE_STATE}}/AGENTS.md` for durable facts.
- `{{ABYSS_MACHINE_STATE}}/changes/AGENTS.md` for host change-ledger work.
- `{{ABYSS_MACHINE_STATE}}/doctor/AGENTS.md` before doctor/self-maintenance route work.
- `{{ABYSS_MACHINE_STATE}}/ai/AGENTS.md` before local AI/runtime/model work.
- `{{ABYSS_MACHINE_STATE}}/ai/llm/AGENTS.md` before resident LLM work.
- `{{ABYSS_MACHINE_STATE}}/cooling/AGENTS.md` before fan, thermal, or power-profile work.
- `{{ABYSS_MACHINE_STATE}}/memory/AGENTS.md` before RAM, zram, PSI, or memory-gated launches.
- `{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md` before starting medium, heavy, sustained, or unattended work.
- `{{ABYSS_MACHINE_STATE}}/heartbeats/AGENTS.md` before recurring pulse or OS Abyss heartbeat route work.
- `{{ABYSS_MACHINE_STATE}}/reactions/AGENTS.md` before reaction-candidate or evidence-to-action routing work.
- `{{ABYSS_MACHINE_STATE}}/responses/AGENTS.md` before owner-gated response-route work.
- `{{ABYSS_MACHINE_STATE}}/processes/AGENTS.md` before process, game-guard, GNOME Shell, or compositor attribution work.
- `{{ABYSS_MACHINE_STATE}}/nervous/AGENTS.md` before local chronicle, capture, index, retrieval, synthesis, or quality work.
- `{{ABYSS_MACHINE_STATE}}/storage/AGENTS.md` before storage cleanup, large writes, caches, runtimes, or Podman graphroot review.
- `{{ABYSS_MACHINE_STATE}}/artifacts/AGENTS.md` before classifying large host-local artifact evidence, planning archive/offload cleanup, or proving restore routes.
- `{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md` before typed-text intake, source adapters, or text privacy work.
- `{{ABYSS_MACHINE_STATE}}/dictation/AGENTS.md` before dictation config, hotkey, profile, or transcript journal work.
- `{{ABYSS_MACHINE_STATE}}/stack-bridge/AGENTS.md` for stack handoff; `{{ABYSS_MACHINE_STATE}}/self-awareness/AGENTS.md` for causal stack/host observability.
- `{{ABYSS_MACHINE_STATE}}/topology/AGENTS.md` and `{{ABYSS_MACHINE_STATE}}/graph/AGENTS.md` before generated topology or graph work.
- `{{ABYSS_MACHINE_STATE}}/rag/AGENTS.md` before machine RAG trace or trace-eval work.

Before durable mutation, run `abyss-machine changes preflight --intent TEXT --surface SURFACE --json`.
Record real host-layer changes with `abyss-machine changes record ...`; close
with explicit decision review after validation and rollback notes.
Use `added`/`existing` with `--decision-ref`; use `no-record-needed` or
`backfill-required` only with `--decision-reason`.

## Boundaries

- `abyss-stack` may consume `abyss-machine`; `abyss-machine` must not import or
  mutate `abyss-stack`.
- Do not write to `{{ABYSS_OS_ROOT}}`, `/srv/abyss-stack`,
  `{{ABYSS_USER_HOME}}/src/abyss-stack`, `/work`, `/srv/work`, `/srv/games`, or
  `/srv/GAMES` from host-layer automation unless the operator explicitly routes
  work to the owning project.
- Do not put large mutable caches, model downloads, OpenVINO/NPU compile blobs,
  browser automation caches, benchmark outputs, or AI scratch artifacts on `/`.
  Prefer `{{ABYSS_MACHINE_SRV}}/cache`, `{{ABYSS_MACHINE_SRV}}/runtimes`,
  `{{ABYSS_MACHINE_SRV}}/storage`, or `{{ABYSS_MACHINE_SRV}}/tmp` according to
  `{{ABYSS_MACHINE_ETC}}/storage-policy.json`.
- Use `pkexec COMMAND ...` for GUI-authorized privileged host changes. If
  authorization is missed or unavailable, stop the hanging auth process and
  rerun cleanly or ask for the next privileged route.
- Generated latest/index JSON accelerates orientation but never replaces source
  contracts under `{{ABYSS_MACHINE_ETC}}` or local `AGENTS.md` cards.
- Artifact evidence under `{{ABYSS_MACHINE_STATE}}/artifacts` is a facts-only
  cleanup compass. Date, size, old mtime, and refs=0 are never enough for
  delete-ok; cleanup requires backup/restore evidence plus a controlled
  workload or explicit operator route.
- Nervous facts, screenshots, clipboard metadata, browser captures, retrieval
  packs, and synthesis candidates are evidence; they do not execute user intent
  or authorize automatic mutation.
- Thermal routing on this thin laptop should be adaptive. Stable `100-105C` is
  monitored active range, above `105C` needs duration/trend/distribution
  context, and hard emergency behavior is reserved for roughly `109-110C`,
  throttle collapse, broad sustained heat, or firmware trip behavior.
- Game guard is protective and non-mutating. Do not kill, throttle,
  re-affinitize, or clean game processes/roots from this layer.

## Memory route

Use `aoa_memo` when the host task asks to recall, continue, preserve, compare
with past host work, recover after compaction, inspect `{{ABYSS_MACHINE_STATE}}/memo`,
or route host evidence toward reviewed memory.

- Need continuity or context: call `aoa_memo_brief` with `repo=abyss-machine`
  and the current intent.
- Need to preserve host-local memory: write through `{{ABYSS_MACHINE_STATE}}/memo`
  and validate the local port.
- Need durable reviewed memory: prepare reviewed intake for `aoa-memo`; host
  evidence stays evidence until reviewed.
- Need live host truth: use `abyss-machine` validators and source contracts;
  memo carries recall, provenance, and candidate handoff.

## Validation

Use the narrowest relevant subsystem validator first, then broader gates when
contracts, docs, bridge routes, or generated surfaces changed.

Documentation and agent mesh:

```bash
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine docs audit --json
```

Topology and bridge:

```bash
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
abyss-machine rag validate --json
```

Subsystem validators include:

```bash
abyss-machine storage validate --json
abyss-machine artifacts validate --json
abyss-machine memory validate --json
abyss-machine resource validate --json
abyss-machine heartbeats validate --json
abyss-machine reactions validate --json
abyss-machine responses validate --json
abyss-machine doctor validate --json
abyss-machine ai validate --json
abyss-machine cooling validate --json
abyss-machine mode validate --json
abyss-machine processes validate --json
abyss-machine nervous validate --json
abyss-machine typing validate --json
abyss-machine dictation validate --json
```

## Post-change route review

After meaningful host-layer work, update only the surfaces whose role moved:

- `ROADMAP.md` when host-wide direction, horizon posture, maturity posture,
  bridge posture, owner-boundary pressure, or concrete future triggers changed.
- `CHANGELOG.md` when a curated host milestone, release-visible contour, public
  docs, validation contract, or repo/root structure changed.
- `DESIGN.AGENTS.md` when agent-facing form, card shape, route order, or mesh
  posture changed.
- `DOCS.md` when documentation hierarchy, document roles, or freshness rules
  changed.
- `decisions/` when future agents need durable rationale for a structural,
  ownership, route-law, validator-authority, bridge-contract, or topology
  choice.
- `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json` when decision records
  changed and future agents need fast access to what changed when and why.
- generated mirrors and validators when their source-backed surface changed.

Do not turn `AGENTS.md`, `ROADMAP.md`, `CHANGELOG.md`, README files, or
generated latest JSON into archives of every probe, sample, local experiment, or
change-ledger event.

## Closeout

Closeout must state:

- which source contracts or local cards changed;
- which generated facts or indexes were rebuilt;
- exact validation commands and pass/warn/fail status;
- active or closed change ledger record;
- decision review result: `added`, `existing`, `no-record-needed`, or
  `backfill-required`, with decision ref or reason;
- whether `ROADMAP.md` or `CHANGELOG.md` changed and why;
- rollback route for config, binary, service, timer, or policy changes;
- skipped checks and remaining risk.

Mesh source: `{{ABYSS_MACHINE_ETC}}/agents-mesh.json`; generated index: `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json`; validation evidence: `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/latest.json`.
