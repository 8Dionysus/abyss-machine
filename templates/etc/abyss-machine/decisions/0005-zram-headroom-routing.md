# 0005 Zram Headroom Routing

## Status

accepted

## Date

2026-05-13

## Index Tags

- memory
- resource-gate
- zram
- game-guard

## Context

The machine hard-froze during an active game plus resident/background work. The
previous boot did not show a clean OOM kill, GPU reset, or thermal trip, but did
show zram saturation, heavy swap-in/swap-out and major-fault activity, and a
late GNOME/libinput "system too slow" symptom. This made the earlier memory
classification too blunt: high zram percentage was treated as critical even
when PSI was zero and a real zram headroom device was present.

## Options Considered

- Keep the 12 GiB zram-only setup and only defer background tasks:
  insufficient, because it leaves almost no swap headroom when games and
  resident models overlap.
- Stop resident models or convert them to on-demand:
  rejected as the default route because promoted resident capabilities are part
  of the machine direction and should be routed around, not discarded.
- Persist larger zram headroom and make classification consider low PSI plus
  real free zram capacity:
  accepted as the least blunt route for this thin laptop and resident-agent
  stack.

## Decision

Persist `vm.page-cluster = 0`, move next-boot zram to
`zram-size = min(ram / 2, 16384)` with `lzo-rle`, and allow memory routing to
cap zram-only swap pressure at `warm` when PSI is low and either MemAvailable is
healthy or at least 2 GiB of real swap headroom remains.

## Rationale

The failure mode was latency/reclaim collapse, not simple capacity accounting.
Using real headroom and PSI keeps the route adaptive: the machine can continue
small resident-agent work while game guard protects foreground work, but it
returns to critical gating when zram headroom collapses or PSI shows stalls.

## Consequences

Light work and interactive medium work can proceed under active games when
memory is warm rather than critical. Unattended medium, heavy, and sustained
work remain gated by game guard and memory policy. Future tuning must watch PSI,
major faults, zram free MiB, and user-visible latency together instead of using
swap percentage alone.

## Boundaries

This decision does not authorize heavy or unattended work during foreground
game pressure. It narrows blunt memory classification, while game guard,
resource policy, and live PSI/swap evidence still gate launches.

## Current Applicability

As of 2026-05-21, this decision remains active. Memory routing should still
consider PSI, real swap headroom, game guard, and user-visible latency together
instead of treating swap percentage alone as a hard truth.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `/etc/sysctl.d/80-abyss-machine-memory-latency.conf`
- `/etc/systemd/zram-generator.conf`
- `{{ABYSS_MACHINE_ETC}}/memory-policy.json`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/memory/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/changes/active/memory-headroom-zram-routing-20260513`

## Follow-up Route

Use `abyss-machine memory status --json`, `abyss-machine memory plan --json`,
`abyss-machine resource plan --class CLASS --kind KIND --json`, and system logs
after the next heavy game/resident-agent session. If zram headroom again
collapses under low PSI, tune cgroup/resident workload policy before adding
more blunt restrictions.

## Validation

- `abyss-machine memory status --json`
- `abyss-machine memory plan --json`
- `abyss-machine resource plan --class CLASS --kind KIND --json`
- `abyss-machine topology validate --json`
