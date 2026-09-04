# Abyss Machine Host Layer

Root route card for installed `abyss-machine` work. Use the nearest local card
and source contract for the target subsystem.

## Applies to

Applies to host-machine work under `{{ABYSS_MACHINE_ETC}}`,
`{{ABYSS_MACHINE_STATE}}`, `{{ABYSS_MACHINE_SRV}}`, the installed
`abyss-machine` entrypoints, and host-owned units operating those roots.

It does not grant write authority over `{{ABYSS_OS_ROOT}}`, `abyss-stack`,
work projects, games, or private roots.

## Role

`abyss-machine` owns host facts and policy, hardware evidence, storage and
resource routing, dictation and opt-in typed/nervous intake, host-managed AI
runtime evidence, and read-only bridges.

System form belongs to `{{ABYSS_MACHINE_ETC}}/DESIGN.md`; agent-surface form
to `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`; documentation hierarchy to
`{{ABYSS_MACHINE_ETC}}/DOCS.md`; direction to
`{{ABYSS_MACHINE_ETC}}/ROADMAP.md`; durable rationale to
`{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md`; command syntax to
`{{ABYSS_MACHINE_ETC}}/commands.md`.

## Read before editing

For broad orientation, run `abyss-machine enter --json`. Then use the nearest
local `AGENTS.md` and only the source contracts implicated by the task.

- `/etc` local cards own stable config and policy.
- `{{ABYSS_MACHINE_STATE}}/AGENTS.md` routes durable generated facts and
  subsystem evidence.
- `{{ABYSS_MACHINE_SRV}}/AGENTS.md` routes large caches, runtimes, storage,
  backups, and temporary work.
- `{{ABYSS_MACHINE_STATE}}/changes/AGENTS.md` owns the change ledger.
- `{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md` is required before medium,
  heavy, sustained, or unattended work.
- `{{ABYSS_MACHINE_STATE}}/storage/AGENTS.md` and
  `{{ABYSS_MACHINE_ETC}}/storage-policy.json` govern large writes and cleanup.

Before durable mutation, run
`abyss-machine changes preflight --intent TEXT --surface SURFACE --json`.
Use `commands.md` for the full subsystem command and validator catalog.

## Boundaries

- `abyss-stack` may consume host evidence; this layer must not import or mutate
  the stack or sibling owner repositories without an explicit owner route.
- Large mutable caches, model downloads, compile blobs, browser automation
  caches, benchmarks, and AI scratch must use the `/srv` routes selected by
  `storage-policy.json`, never the constrained system root.
- Generated latest/index JSON accelerates orientation but never replaces
  authored source contracts or local cards.
- Artifact age, size, old mtime, or zero refs never proves delete safety;
  cleanup requires restore evidence and an owner/operator route.
- Nervous facts, screenshots, clipboard metadata, browser captures, retrieval
  packs, and synthesis candidates are evidence, not action authority.
- Game guard is read-only: do not kill, throttle, re-affinitize, or clean game
  processes or roots from this layer.
- Use GUI-authorized privilege escalation only through the documented
  `pkexec` route; stop and report missed or unavailable authorization.

## Validation

Run the narrowest owning subsystem validator first. Documentation or card
changes require:

Run the documentation route in `VALIDATION.md#documentation-mesh`.

Add decision-index, topology, graph, stack-bridge, RAG, or subsystem
validation only when the corresponding source surface moved. The exact
commands are owned by `{{ABYSS_MACHINE_ETC}}/commands.md`.

## Post-change route review

Update only the owner surfaces whose meaning moved:

- `ROADMAP.md` for host-wide direction or future triggers;
- `CHANGELOG.md` for curated public milestones;
- `DESIGN.AGENTS.md` for card shape, route order, or mesh posture;
- `DOCS.md` for document roles or freshness law;
- `decisions/` when durable rationale is required;
- generated mirrors only through their builders after authored sources change.

Do not turn route cards, README files, roadmap/changelog, or latest JSON into
archives of probes and local experiments.

## Closeout

Report changed source contracts/cards, generated views rebuilt, exact checks
and status, change-ledger state, decision-review result, skipped checks,
remaining risk, and rollback for any config, binary, unit, timer, or policy
effect. Keep live/private payloads out of public evidence.
