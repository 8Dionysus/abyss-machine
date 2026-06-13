# 0006 Doctor Self-Maintenance Route

## Status

accepted

## Date

2026-05-14

## Index Tags

- doctor
- self-maintenance
- safe-repair
- user-timer

## Context

`abyss-machine doctor` existed as a broad diagnostic checker, but it did not have a durable subsystem route, latest/report surfaces, user timer automation, or explicit safe-repair policy.

The operator asked for a long-horizon automated host task. During implementation, privileged prompts were unavailable, so the `/etc` policy and decision record were first prepared under `{{ABYSS_MACHINE_STATE}}/doctor/operator-required/etc/` and installed later with operator GUI authorization.

## Options Considered

- Keep doctor as an ad hoc broad diagnostic command:
  This would preserve the existing surface but would not create a reusable self-maintenance route or durable report path.
- Run doctor as a resident daemon:
  This would make the machine more automatic, but it would add unnecessary always-on behavior and blur the boundary between observation and action.
- Promote doctor as a user-timer oneshot route with safe-only repair:
  This gives regular evidence, validation, and low-risk maintenance without privileged actions, project-repo mutation, or a resident daemon.

## Decision

Promote `doctor` into a host-side oneshot self-maintenance route:

- keep it non-resident;
- run through a compact user timer;
- write `{{ABYSS_MACHINE_STATE}}/doctor/latest.json`;
- write `{{ABYSS_MACHINE_STATE}}/doctor/reports/latest.md`;
- validate through `abyss-machine doctor validate --json`;
- allow only non-privileged host-owned generated/read-model refreshes as safe repair;
- keep `{{ABYSS_MACHINE_ETC}}/doctor-policy.json` as the canonical policy after operator-authenticated install.

## Rationale

This gives future agents a single, durable route for checking machine health, safe maintenance opportunities, and documentation/mesh drift. A oneshot timer fits the host layer better than a daemon because the doctor should report and orchestrate existing safe commands, not become another persistent actor.

Keeping the policy in `{{ABYSS_MACHINE_ETC}}/doctor-policy.json` makes the boundaries reviewable: no privileged actions, no project-repo mutation, no large downloads, no automatic process killing, and no hidden cleanup.

## Consequences

Future host sessions can start with `abyss-machine doctor --json` or `abyss-machine doctor report --markdown` for a compact status pass.

Doctor warnings should be treated as routed evidence, not as permission to mutate unrelated subsystems. Safe repair remains limited to non-privileged host-owned generated/read-model refreshes unless a later accepted decision expands the policy.

If doctor policy changes, update `{{ABYSS_MACHINE_ETC}}/doctor-policy.json`, this decision lane if the route changes materially, and the relevant validation surfaces together.

## Boundaries

This decision does not make doctor a daemon, privileged executor, project-repo
mutator, or broad cleanup authority. Doctor evidence can recommend routes; it
does not grant mutation rights outside its safe repair policy.

## Current Applicability

As of 2026-05-21, this decision remains active. Doctor stays a host-side
oneshot self-maintenance route with bounded safe-repair authority, not a
privileged daemon or broad executor.

## Review Log

- 2026-05-21: Added the standard applicability/review-log surface required by
  decision `0009`; no substantive rationale change.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_ETC}}/doctor-policy.json`
- `{{ABYSS_MACHINE_ETC}}/commands.md`
- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DESIGN.md`
- `{{ABYSS_MACHINE_STATE}}/doctor/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/doctor/latest.json`
- `{{ABYSS_MACHINE_STATE}}/doctor/reports/latest.md`
- `{{ABYSS_MACHINE_STATE}}/doctor/validate/latest.json`
- `{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-doctor.service`
- `{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-doctor.timer`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/doctor-orchestrator-rerank-closeout-20260514`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/doctor-policy-operator-install-20260514`

## Follow-up Route

Validate through:

- `abyss-machine doctor validate --json`
- `abyss-machine doctor report --markdown`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine topology validate --json`

Future changes to doctor automation, policy boundaries, or action authority should open a host-layer change record under `{{ABYSS_MACHINE_STATE}}/changes/` and either update this decision or add a new superseding decision.

## Validation

- `abyss-machine doctor validate --json`
- `abyss-machine doctor report --markdown`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine topology validate --json`
