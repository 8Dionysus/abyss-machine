# Abyss Machine Observability Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/observability/`.

## Role

This directory owns stable config for low-overhead host telemetry collection.
Telemetry logs and summaries belong under `{{ABYSS_MACHINE_STATE}}/observability`.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/observability/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/cooling/AGENTS.md` when thermal semantics move
- `{{ABYSS_MACHINE_STATE}}/resource/AGENTS.md` when launch gates use telemetry

Before durable mutation, run:

```bash
abyss-machine changes preflight --intent TEXT --surface {{ABYSS_MACHINE_ETC}}/observability --json
```

## Boundaries

- Keep telemetry low overhead.
- Do not turn observability config into response automation.
- Do not encode thermal policy here when the cooling config owns it.
- Do not store logs or large samples in `/etc`.

## Validation

```bash
abyss-machine cooling validate --json
abyss-machine resource validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State the config changed, which telemetry state was inspected, and which
downstream route consumes the signal.
