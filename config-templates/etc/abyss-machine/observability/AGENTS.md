# Abyss Machine Observability Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/observability/`.

## Role

This directory owns stable config for low-overhead host telemetry collection.
Telemetry logs and summaries belong under `{{ABYSS_MACHINE_STATE}}/observability`.

## Route selection

Use the observability state card for live evidence, the cooling state card only
when thermal semantics move, and the resource state card only when a launch
gate consumes telemetry.

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

Run the validator for each affected consumer: cooling for thermal semantics,
resource for launch gates, and docs mesh when this card changes.

## Closeout

State the config changed, which telemetry state was inspected, and which
downstream route consumes the signal.
