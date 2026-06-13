# 0016 Machine Context Refresh Automation

## Status

accepted

## Date

2026-05-26

## Index Tags

- rag
- maps
- automation
- validation-guard

## Current Applicability

As of 2026-05-26, generated machine context is refreshed by the user-scope
`abyss-machine-context-refresh.timer`. The timer runs one bounded read-only
refresh pass: maps build, maps validate, RAG trace/eval, and RAG validate.

## Context

Machine maps and RAG traces are useful only if the latest generated context is
fresh enough for the next agent session. A maps-only timer left the RAG trace
and local trace eval as manual follow-up work, which made the new
`maps -> evidence -> trace -> eval` loop easy to forget.

The automation also needed a clean boundary: refresh generated context, but do
not execute actions, write reviewed memory, publish KAG truth, create proof
verdicts, mutate repositories, or deliver evidence into AoA organs.

## Options Considered

- Keep `abyss-machine-maps-refresh.timer` and add a second RAG timer:
  rejected because it creates duplicate scheduling and ordering ambiguity.
- Extend the maps-only timer to run RAG too:
  rejected because the unit name would no longer match the actual role.
- Replace the maps-only timer with a context-refresh timer:
  accepted because one pass owns the generated context chain directly.

## Decision

Replace the maps-only automatic refresh route with
`abyss-machine-context-refresh.timer`.

The timer runs:

```bash
abyss-machine rag refresh --query scheduled-machine-context-refresh --json
```

`rag refresh` rebuilds maps, validates maps, writes a RAG trace/eval, writes a
RAG refresh record, validates RAG, and updates the RAG status/index.

## Rationale

This keeps freshness and validation together. Future agents can inspect one
timer and one latest refresh record instead of guessing whether maps, traces,
and evals were updated in the right order.

The route stays inside `abyss-machine` because these are host-generated context
signals. External authorities remain external: proof belongs to proof organs,
reviewed memory to reviewed memory intake, and derived truth to the owning
knowledge layer.

## Consequences

- Generated maps, map validation, RAG traces, RAG evals, RAG refresh records,
  and RAG validation now update automatically every 15 minutes while the user
  systemd session is available.
- `abyss-machine maps validate --json` and `abyss-machine rag validate --json`
  now check the context-refresh timer path instead of the old maps-only timer.
- The old `abyss-machine-maps-refresh.*` user units are removed to avoid
  duplicate scheduled refreshes.
- If the user systemd timer is disabled, validators warn instead of claiming
  freshness.

## Boundaries

Automatic refresh is not action automation. It must not execute response
routes, clear systemd state, modify project repositories, write reviewed memory,
publish KAG truth, create proof verdicts, or deliver host evidence into AoA
organs.

## Review Log

- 2026-05-26: Initial accepted record for unified context-refresh automation.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_ETC}}/MAPS.md`
- `{{ABYSS_MACHINE_ETC}}/maps-policy.json`
- `{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-context-refresh.service`
- `{{ABYSS_USER_HOME}}/.config/systemd/user/abyss-machine-context-refresh.timer`
- `{{ABYSS_MACHINE_STATE}}/rag/AGENTS.md`

## Validation

- `PYTHONPYCACHEPREFIX={{ABYSS_MACHINE_SRV}}/tmp/pycache-check python -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine rag refresh --query "manual post-install context refresh" --json`
- `abyss-machine maps validate --json`
- `abyss-machine rag validate --json`
- `systemctl --user status abyss-machine-context-refresh.timer --no-pager`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs mesh-validate --json`

## Follow-up Route

Use `{{ABYSS_MACHINE_STATE}}/rag/refresh/latest.json` to inspect the latest
automatic refresh result. Change timer cadence or refresh scope through
`{{ABYSS_MACHINE_ETC}}/maps-policy.json`, `{{ABYSS_MACHINE_ETC}}/MAPS.md`, and the
user unit files, then rerun the validators above.
