# 0022 Owner-Native Memory Orchestration

## Status

accepted

## Date

2026-07-12

## Index Tags

- memory
- resource-gate
- owner-boundary
- runtime-lifecycle
- validation-guard

## Current Applicability

As of 2026-07-14, `abyss-machine` owns live pressure and swap-reserve facts,
synchronous launch admission, runtime-only startup reservations, bounded
runtime peak learning, one canonical resource-launch path, a narrow runtime
cold-load admission lease for existing owner processes, and shadow-only
owner-cgroup reclaim offers. The cold-load route accepts explicit owner
activity and demand through a private same-user Unix socket; it does not import
the monolithic CLI while idle or gain model lifecycle authority. The older AI
CPU launch command is only a compatibility wrapper over that path. It does not
run a resident forecast, workload registry, evidence database, or generic
lifecycle controller. The older numeric `memory orchestrate` candidate ranking
and restart executor are retired. Reclaim, sleep, unload, checkpoint, resume,
and rollback remain with the workload owner.

## Context

A resident Memory Controller combined PSI polling, forecasts, utility scoring,
runtime registry, background-start queueing, lifecycle plans, and SQLite
evidence. Live use showed that its only effective mutation was queue admission
for new starts: no workload had an actionable registered lifecycle contract,
while owner-native model and service mechanisms delivered the measured memory
relief. The controller also duplicated process/pressure histories and created a
second operational authority beside systemd, resource admission, and workload
owners.

## Options Considered

- Keep the controller and reduce its storage and memory footprint. This leaves
  the false central ownership model in place.
- Replace it with a smaller resident broker immediately. This still adds a
  daemon before any owner exposes a pressure action that requires arbitration.
- Keep synchronous host admission and distribute lifecycle to explicit owners,
  adding a coordinator only after a real owner contract proves it necessary.

## Decision

Remove the resident Memory Controller, its policy/registry projection, SQLite
evidence, queue/grant protocol, dedicated entrypoint, systemd unit, rehearsal,
and implementation-specific tests.

Preserve the existing fresh resource plan, admission lock, and runtime-only
reservations. Replace class/swap memory gates and static `MemoryHigh` with a
hard cooperative physical-RAM floor for known projected demand and cautious
startup serialization only while demand is unknown. Learn demand from the
exact transient unit's journald `MEMORY_PEAK` plus `MEMORY_SWAP_PEAK`; keep at
most 64 routes and 16 recent samples per route under `/run`, with an explicit
owner estimate taking precedence. A class/kind estimate is bootstrap evidence
only until a measured profile exists and therefore remains in the bounded
unknown-startup lane.

Memory plan publishes pressure and reserve facts, not an all-true compatibility
recommendation table. Every host-managed execution path, including the AI CPU
compatibility command, delegates to resource launch for fresh admission,
atomic lease creation, cgroup identity, and post-run learning.

Pressure class derives from MemAvailable and PSI. Swap occupancy has a separate
reserve status and has neither pressure nor action authority. Empty stable
resource-owner cgroups may publish a shadow-only file-cache reclaim offer only
when anon, shmem, dirty, and writeback are all zero. No reclaim is executed by
this slice. Host read routes must honor
`write_latest=False` transitively. Memory observations and resource admission
retain atomic latest-only documents; historical telemetry belongs to journald
or the configured metrics retention instead of daily control-plane JSONL.
Owner-native lifecycle is preferred; unknown, active, protected, or
data-at-risk work is preserved.

An owner that needs to materialize a model inside an already-running process
may atomically request a short runtime-only cold-load lease. The request must
name a stable owner/workload/request identity, explicit owner activity, and
incremental physical-memory demand. Admission reads fresh
MemAvailable and memory PSI, counts outstanding leases, preserves the hard
physical-RAM floor, and checks direct CPU thermal emergency evidence. Battery
and power mode remain routing advice rather than workload-importance authority.
The owner releases the capability-protected lease immediately after load or
failure; broker restart preserves it only until its bounded TTL. This endpoint
does not load, unload, restart, cap, or rank any workload.

A future coordinator is admissible only when all of these are true:

- at least one owner publishes a stable identity and reversible pressure offer;
- the offer includes activity/data-risk, expected relief, health, resume, and
  rollback evidence;
- distributed owner behavior is insufficient under representative load;
- shadow comparison produces no unsafe candidate;
- the coordinator can remain invocation/event scoped or prove that residency
  has a net benefit.

## Rationale

The host can protect a point-in-time launch reserve for work entering the
canonical route from current and learned facts, without retaining a forecast
database or continuously classifying every process. This does not claim
control over unregistered starts by other agents. systemd and cgroup identity
remain the host attribution substrate, while models, browsers, sessions, and
services retain semantic authority over their own state. This keeps automation
owner-aware without inventing a central score for work it cannot safely
understand.

## Consequences

The always-resident lifecycle-controller cost becomes zero. Known starts
reserve their learned or owner-declared incremental footprint atomically and
may proceed
concurrently while the hard floor remains intact. Unknown starts serialize only
through their bounded startup window and are held during active stalls or low
physical headroom. There is no host queue fairness layer; owner schedulers may
add ordering before calling the launch route when they have a real scheduling
need. Unregistered starts remain an explicit integration gap for shadow and
owner-contract work, never an inferred permission to constrain them.
When the optional cold-load endpoint is active, its lightweight server is the
only resident admission transport; the 2026-07-14 canary held about 15 MiB at
idle and during reserve/release, with no swap. A monolithic-CLI server candidate
measured about 70 MiB and was rejected before deployment.

Existing host-only controller state remains migration evidence until backup and
restore-proof cleanup. A future pressure offer requires a new reviewed source
change rather than silently reactivating the removed controller.

## Boundaries

- This decision does not authorize killing, freezing, restarting, or capping
  important work.
- High zram occupancy alone is not active pressure or permission to reclaim.
- `systemd-oomd` remains an emergency mechanism only for explicitly disposable
  cgroups, not the orchestration plane.
- `abyss-machine` does not take ownership of stack models, Codex threads, or
  browser tabs.
- Historical controller evidence is not current source truth.

## Review Log

- 2026-07-12: Initial record.
- 2026-07-13: Removed the pre-existing numeric candidate ranking, confirmation,
  restart executor, CLI/bridge surface, and required route card. Historical
  host evidence remains until restore-proof cleanup.
- 2026-07-13: Separated pressure from swap reserve, removed static launch memory
  caps, swap/class gates, and the fake recommendation table; unified the AI
  compatibility launcher behind resource admission, added bounded transient-
  unit peak learning, and exposed strict empty-cgroup cache reclaim as shadow
  evidence only.
- 2026-07-13: Replaced the long-lived resource-launch CLI waiter with a sealed
  in-memory handoff to a lightweight execution adapter while preserving lease,
  timeout cleanup, peak learning, and latest-only receipts.
- 2026-07-14: Added explicit owner activity and a private runtime cold-load
  lease for models materialized inside existing processes. The accepted server
  reads fresh memory/PSI and direct thermal emergency facts without a resident
  CLI, stores only bounded `/run` leases with hashed release capabilities, and
  passed an isolated reserve/replay/release canary below the 32 MiB RSS limit.
- 2026-07-15: Wired the accepted server into the core profile as a hardened
  unprivileged user service. The launcher execs into the lightweight server;
  the unit is Unix-only, has no memory cap, and gains no process-lifecycle
  authority.
- 2026-07-23: Made power-mode class caps explicitly advisory to live CPU-owner
  authorization. Normal green/warm routes no longer impose cpuset or thread
  caps; placement is applied only when the owner requires it or reports CPUs to
  avoid, while physical-memory reserve and emergency gates remain authoritative.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/memory-policy.json`
- `{{ABYSS_MACHINE_ETC}}/resource-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/memory/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md`

## Validation

```bash
abyss-machine memory validate --json
abyss-machine resource validate --json
abyss-machine docs decisions-index --json
python -m pytest -q
PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
```

Current invocations are owned by [commands.md](../commands.md) and the
canonical test/validation routes.

## Follow-up Route

Natural-load shadow and soak evidence belongs to the active change record. A
new coordinator proposal starts from an owner contract and controlled pressure
proof, not from resurrecting the retired database or service.
