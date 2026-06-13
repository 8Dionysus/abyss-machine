# Abyss Machine Roadmap

This roadmap tracks host-machine direction for `abyss-machine`.

It is a direction surface, not a task queue, telemetry summary, benchmark log,
release history, or replacement for the host change ledger.

## Authority

Root `ROADMAP.md` owns:

- host-wide direction
- horizon posture for routing, observability, storage, AI, nervous, and bridge work
- maturity posture for this machine as a legible host layer
- owner-boundary pressure between `abyss-machine`, AbyssOS, AoA, ToS, and future `abyss-stack`
- concrete future triggers that belong to the host layer

It does not own subsystem-local logs, live telemetry, command catalogs,
append-only change history, project-repository direction, or owner-local source
truth.

Use the stronger surface when the change is narrower:

- exact command catalog: `{{ABYSS_MACHINE_ETC}}/commands.md`
- documentation hierarchy: `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- agent mesh form: `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`
- host root topology: `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`
- bridge contract: `{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md`
- large local root routing: `{{ABYSS_MACHINE_SRV}}/DESIGN.md`
- subsystem-local guidance: nearest `AGENTS.md`
- current generated evidence: `{{ABYSS_MACHINE_STATE}}/*/latest.json`
- host change history: `{{ABYSS_MACHINE_STATE}}/changes/`
- project or stack direction: the owning project repository

## Update Rule

Update this roadmap when a change moves host-wide direction, horizon posture,
maturity posture, owner-boundary pressure, bridge posture, or a concrete future
trigger.

Do not update this roadmap for a local probe, telemetry refresh, single command
addition, generated fact update, one-off cleanup, or closed host change unless
it changes one of those host-wide directions. Route those changes to the owning
surface instead.

Before closeout, ask: did this change move the machine's direction, or did it
only land a local surface?

## Current Host Direction

`abyss-machine` is moving from host instrumentation into adaptive machine
routing: the machine should be legible, observable, indexed, and able to route
work without bluntly cutting useful activity.

The current host move is:

- keep source contracts compact and readable from `{{ABYSS_MACHINE_ETC}}`
- keep generated facts and indexes useful without letting them author truth
- use the change ledger for actual host mutation history
- shape resource, thermal, memory, and process routing around observed duration,
  trend, attribution, and workload class instead of reacting to short spikes
- keep thin-laptop thermal policy adaptive: stable `100-105C` is an active
  monitored range, not automatic failure
- make resident small agents useful through continuous evidence, bounded jobs,
  and quality gates rather than start-on-demand only behavior
- keep large caches, runtimes, models, temporary AI artifacts, and storage-heavy
  work under `{{ABYSS_MACHINE_SRV}}`, not the limited system root
- keep `abyss-machine` read-only toward AoA, ToS, `abyss-stack`, work, and game
  roots unless the operator explicitly routes work to that owner
- keep stack-facing handoff as evidence-first bridge material, not stack runtime
  truth

## Current Checked Contour

| Anchor | Surface |
|---|---|
| Host form and authority | `{{ABYSS_MACHINE_ETC}}/DESIGN.md`, `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md` |
| Agent mesh and route cards | `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`, `{{ABYSS_MACHINE_ETC}}/agents-mesh.json`, `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh.min.json` |
| Documentation hierarchy | `{{ABYSS_MACHINE_ETC}}/DOCS.md`, `{{ABYSS_MACHINE_ETC}}/ROADMAP.md`, `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md`, `{{ABYSS_MACHINE_ETC}}/decisions/` |
| Host mutation history | `{{ABYSS_MACHINE_STATE}}/changes/` |
| Large local root | `{{ABYSS_MACHINE_SRV}}/DESIGN.md`, `{{ABYSS_MACHINE_SRV}}/AGENTS.md` |
| Stack-facing handoff | `{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md`, `{{ABYSS_MACHINE_ETC}}/stack-bridge.json`, `{{ABYSS_MACHINE_STATE}}/stack-bridge/` |
| Runtime and routing evidence | `{{ABYSS_MACHINE_STATE}}/resource/`, `{{ABYSS_MACHINE_STATE}}/cooling/`, `{{ABYSS_MACHINE_STATE}}/memory/`, `{{ABYSS_MACHINE_STATE}}/processes/` |
| Local memory and retrieval | `{{ABYSS_MACHINE_STATE}}/nervous/` |
| Machine atlas | `{{ABYSS_MACHINE_ETC}}/MAPS.md`, `{{ABYSS_MACHINE_STATE}}/maps/` |
| Machine RAG traces | `{{ABYSS_MACHINE_STATE}}/rag/`, `abyss-machine rag trace --query TEXT --json`, `abyss-machine rag refresh --query TEXT --json`, `abyss-machine-context-refresh.timer` |

Detailed host changes live in the change ledger. `ROADMAP.md` keeps current
direction and future contour. `CHANGELOG.md` keeps curated milestone contour.
Decision records explain durable choices. No roadmap history as change ledger truth.

## Horizon: Documentation And Agent Mesh

| Field | Direction |
|---|---|
| Current posture | The host layer now has root design, agent design, docs contract, topology, command catalog, mesh config, `/srv` large-root design, and local cards. |
| Next honest move | Keep docs compact while adding only the missing durable rationale and direction surfaces future agents need. |
| Guardrail | Do not turn root `AGENTS.md`, `DOCS.md`, `ROADMAP.md`, or README into a second command catalog or full host history. |

## Horizon: Adaptive Resource Routing

| Field | Direction |
|---|---|
| Current posture | Resource launch, work modes, thermal plans, memory plans, process snapshots, game guard, and AI routes exist as host evidence and gates. |
| Next honest move | Improve routing quality for simultaneous workloads: classify duration, attribution, user-visible priority, and resident-agent utility before deciding whether to start, defer, soften, or observe. |
| Guardrail | Prefer routing and scheduling over blunt killing, hard throttling, or false failures from short-lived spikes. |

## Horizon: Thermal And Cooling

| Field | Direction |
|---|---|
| Current posture | Thin-laptop policy treats stable `100-105C` as monitored active range and reserves hard emergency behavior for stronger signals near firmware limits. |
| Next honest move | Keep collecting duration-aware thermal episodes and test safe fan, power, and workload-route options without suppressing normal active work. |
| Guardrail | Do not mistake a second-scale spike for sustained thermal collapse; do not hide sustained heat, throttle collapse, or firmware trips. |

## Horizon: Memory And Zram

| Field | Direction |
|---|---|
| Current posture | Memory status, pressure, process attribution, plan, validation, low-latency swap-in policy, zram-headroom routing, and a facts-only residency route exist for games plus resident agents. |
| Next honest move | Use `abyss-machine memory residency --json` with TTS/dictation/LLM latency probes to measure cold-swapped protected services, then run a runtime-only `MemoryLow`/`MemoryHigh` pilot before any persistent cgroup policy. |
| Guardrail | Do not label memory pressure as critical from swap percentage alone; require PSI, real zram headroom, reclaim, latency, workload, and user-visible impact context; do not set `MemorySwapMax` on already high-swap live services without restart/warmup evidence. |

## Horizon: Local AI And Resident Agents

| Field | Direction |
|---|---|
| Current posture | Local AI evidence, model/runtime routes, E2B/Gemma resident experiments, schema evals, and launch gates exist. |
| Next honest move | Make small resident agents continuously useful through bounded classification, digestion, recall support, and quality-tested structured output. |
| Guardrail | Resident does not mean unobservable, unbounded, or allowed to degrade foreground work; disabled-by-default and readiness labels must stay honest. |

## Horizon: Nervous System And Retrieval

| Field | Direction |
|---|---|
| Current posture | Capture, facts, events, episodes, lexical search, semantic search, rerank, recall, brief, synthesis, eval, retention, and quality audit routes exist. |
| Next honest move | Keep the automatic context refresh honest, then improve freshness, evidence linking, source priors, dedupe, and evals so future agents stop chasing stale or noisy context. |
| Guardrail | Synthesis candidates are not truth. Retrieval must cite evidence and surface uncertainty instead of making the machine sound more certain than it is. |

## Horizon: Storage And Runtime Roots

| Field | Direction |
|---|---|
| Current posture | `{{ABYSS_MACHINE_SRV}}` is the large host root for cache, runtimes, storage, tmp, tools, hooks, and design artifacts. |
| Next honest move | Make cleanup, snapshot, cache, model, browser automation, and runtime storage routes easier to audit and automate without surprising deletion. |
| Guardrail | Do not put large mutable host data on `/`; do not use symlink tails or protected project/work roots as machine-owned storage. |

## Horizon: Process And Desktop Attribution

| Field | Direction |
|---|---|
| Current posture | Process snapshots, thermal attribution, desktop-compositor sampling, game guard, and container health routes exist. |
| Next honest move | Continue separating actual workload cost from GNOME/compositor/browser/rendering side effects, especially after games or heavy UI sessions. |
| Guardrail | Do not blame extensions, games, or compositor paths from weak samples; preserve user-controlled desktop settings unless explicitly routed. |

## Horizon: Bridge And Future Stack

| Field | Direction |
|---|---|
| Current posture | `abyss-machine` exposes read-only bridge, stack bridge, self-awareness, topology, graph, docs, and subsystem evidence for future stack consumers. |
| Next honest move | Keep bridge fields stable and validation-backed while using the running stack as a read-only self-awareness organ across observability, active services, resident AI, RAG/memory, nervous freshness, stack-owned requirements handoff, failure-mode coverage, E2E cycle proof, and governed response routing. |
| Guardrail | Host bridge consumption is not stack ownership; `abyss-machine` must not import or mutate `abyss-stack`. |

## Horizon: Human Input And Dictation

| Field | Direction |
|---|---|
| Current posture | Dictation config, replacements, transcript routes, and host controls exist. |
| Next honest move | Improve punctuation and correction routes so spoken technical work becomes less noisy while keeping user control explicit. |
| Guardrail | Do not let dictation automation rewrite intent, private material, or project source without explicit review. |

## When The Time Comes

Use this block for likely host-wide work that is not useful to land now but has
a clear future trigger.

- Add subsystem-local `ROADMAP.md` surfaces only when a subsystem has repeated
  future pressure that is too narrow for the root roadmap and too broad for a
  single change record.
- Add a machine-readable direction index only after `abyss-stack`, a local
  agent, or another consumer needs stable roadmap metadata.
- Add stronger decision-record validation only after more records exist and
  repeated shape drift appears.
- Add richer decision index query or filters only after agents need more than
  the compact generated index can provide.
- Promote resident AI readiness only after structured evals, runtime evidence,
  thermal/memory behavior, and user-visible quality pass together.
- Promote full OS Abyss stack self-awareness only after stack-owned requirements
  for datasource inventory, trace backend, database/graph inventory, and
  LangGraph/API observability are closed by `abyss-stack` and revalidated here.
- Add fan-curve or firmware-control integration only after a safe, tested route
  is identified for this exact laptop.
- Continue zram policy tuning only after the post-headroom memory investigation
  can explain swap free MiB, PSI, reclaim, latency, and workload impact
  together.

An item belongs here only when its trigger is concrete and host-wide. If the
future pressure is subsystem-local, use the subsystem card first.

## Standing Direction

Across all horizons:

- keep the machine legible
- route before restricting
- validate before claiming readiness
- keep generated facts below source contracts
- use exact time and evidence links to connect events
- protect project-owner boundaries
- keep local agents useful, observable, and quality-gated
