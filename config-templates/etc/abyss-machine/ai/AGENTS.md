# Abyss Machine AI Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/ai/` and the stable AI config files
inside it.

## Role

This directory owns compact source config for host-local AI runtime policy. It
does not store model files, runtime environments, benchmark artifacts, or live
AI capability evidence.

Runtime evidence belongs under `{{ABYSS_MACHINE_STATE}}/ai`. Large runtimes,
caches, and model artifacts belong under `{{ABYSS_MACHINE_SRV}}`.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DESIGN.md`
- `{{ABYSS_MACHINE_ETC}}/storage-policy.json`
- `{{ABYSS_MACHINE_STATE}}/ai/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/ai/llm/AGENTS.md` when LLM routing is affected

Before durable mutation, run:

```bash
abyss-machine changes preflight --intent TEXT --surface {{ABYSS_MACHINE_ETC}}/ai --json
```

## Boundaries

- Do not download models or create runtimes here.
- Do not write generated benchmark output or capability evidence here.
- Do not mutate `abyss-stack` or AoA repositories from this config lane.
- Do not promote AI readiness from config alone; verify current runtime
  evidence under `{{ABYSS_MACHINE_STATE}}/ai`.

## Validation

```bash
abyss-machine ai validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State which config file changed, which AI/runtime state was consulted, what
validation ran, and whether any large-root route under `{{ABYSS_MACHINE_SRV}}`
also needs follow-up.
