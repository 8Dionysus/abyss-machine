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

## Route selection

Use `storage-policy.json` for large-root changes, the AI state card for runtime
evidence, and the LLM state card only when LLM routing is affected. System form
and common host boundaries are inherited from the root card.

Before durable mutation, run:

Run `VALIDATION.md` in this directory for the on-demand preflight.

## Boundaries

- Do not download models or create runtimes here.
- Do not write generated benchmark output or capability evidence here.
- Do not mutate `abyss-stack` or AoA repositories from this config lane.
- Do not promote AI readiness from config alone; verify current runtime
  evidence under `{{ABYSS_MACHINE_STATE}}/ai`.

## Validation

Run `abyss-machine ai validate --json`; add docs-mesh validation when this card
or another agent-facing source changed.

## Closeout

State which config file changed, which AI/runtime state was consulted, what
validation ran, and whether any large-root route under `{{ABYSS_MACHINE_SRV}}`
also needs follow-up.
