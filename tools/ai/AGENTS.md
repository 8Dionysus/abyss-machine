# Abyss Machine AI Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/ai/`.

## Role

This directory holds host-owned helper tools for AI probes, downloads, canaries,
and benchmark support. It is an implementation lane, not AI policy, model
truth, or runtime evidence.

Source config lives under `/etc/abyss-machine/ai`. Runtime evidence belongs
under `/var/lib/abyss-machine/ai`. Large caches and runtimes belong under
`/srv/abyss-machine/cache` and `/srv/abyss-machine/runtimes`.

## Operating Contract

- Input: AI helper source, operator intent, `/etc/abyss-machine/ai` config, and
  storage/resource policy.
- Output: auditable probe or download helpers; model/cache artifacts route to
  `/srv/abyss-machine/cache` or `/srv/abyss-machine/runtimes`; evidence routes
  to `/var/lib/abyss-machine/ai`.
- Owner: `/etc/abyss-machine/ai` for policy/config and
  `/var/lib/abyss-machine/ai` for observed state.
- Tools: `abyss-machine ai ... --json`, `abyss-machine resource ... --json`,
  and local helper scripts only as thin probes.
- Next route: use `rerankers/AGENTS.md` or `tts/AGENTS.md` for model-family
  work; use `/var/lib/abyss-machine/resource/AGENTS.md` before heavy runs.
- Verify: `abyss-machine ai validate --json`, `abyss-machine resource validate
  --json`, and `abyss-machine docs mesh-validate --json`.

## Read Before Editing

Read:

- `/etc/abyss-machine/AGENTS.md`
- `/srv/abyss-machine/tools/AGENTS.md`
- `/var/lib/abyss-machine/ai/AGENTS.md`
- `/var/lib/abyss-machine/resource/AGENTS.md` before heavy probes

## Boundaries

- Do not download models to `/` or project repositories.
- Do not promote benchmark output into readiness claims without `/var/lib`
  evidence and validation.
- Keep helper scripts thin; stable operator surfaces should route through
  `abyss-machine ... --json`.

## Validation

```bash
abyss-machine ai validate --json
abyss-machine resource validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State which helper moved, what cache/runtime route it uses, whether network or
heavy compute was involved, and which validation ran.
