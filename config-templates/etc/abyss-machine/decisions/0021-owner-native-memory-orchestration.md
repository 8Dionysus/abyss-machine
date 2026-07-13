# 0021 Owner-Native Memory Orchestration

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

As of 2026-07-12, `abyss-machine` owns live host memory facts, synchronous
launch admission, and runtime-only startup reservations. It does not run a
resident forecast, workload registry, evidence database, or generic lifecycle
controller. Reclaim, sleep, unload, checkpoint, resume, and rollback remain
with the workload owner.

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

Preserve the existing fresh resource plan, admission lock, startup demand
model, and runtime-only reservations. Host read routes must honor
`write_latest=False` transitively. Memory observations and resource admission
retain atomic latest-only documents; historical telemetry belongs to journald
or the configured metrics retention instead of daily control-plane JSONL.
Owner-native lifecycle is preferred; unknown, active, protected, or
data-at-risk work is preserved.

A future coordinator is admissible only when all of these are true:

- at least one owner publishes a stable identity and reversible pressure offer;
- the offer includes activity/data-risk, expected relief, health, resume, and
  rollback evidence;
- distributed owner behavior is insufficient under representative load;
- shadow comparison produces no unsafe candidate;
- the coordinator can remain invocation/event scoped or prove that residency
  has a net benefit.

## Rationale

The host can make launch decisions from current facts without retaining a
forecast database or continuously classifying every process. systemd and cgroup
identity remain the host attribution substrate, while models, browsers,
sessions, and services retain semantic authority over their own state. This
keeps automation owner-aware and fail-closed without inventing a central score
for work it cannot safely understand.

## Consequences

The always-resident memory-plane cost becomes zero. Concurrent medium and heavy
starts still serialize through a fresh decision and atomic startup reservation.
There is no host queue fairness layer; owner schedulers may add ordering before
calling the launch route when they have a real scheduling need.

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

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/memory-policy.json`
- `{{ABYSS_MACHINE_ETC}}/resource-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/memory/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md`

## Validation

- `abyss-machine memory validate --json`
- `abyss-machine resource validate --json`
- `abyss-machine resource launch --class medium --kind agent --unattended --dry-run --json -- /usr/bin/true`
- `python -m pytest -q tests/host_contract/regression/test_memory_zram_policy.py`
- `python -m pytest -q tests/host_contract/contract/test_resource_launch_timeout_cleanup.py`
- `python scripts/ci_gate.py --mode source-fast`

## Follow-up Route

Natural-load shadow and soak evidence belongs to the active change record. A
new coordinator proposal starts from an owner contract and controlled pressure
proof, not from resurrecting the retired database or service.
