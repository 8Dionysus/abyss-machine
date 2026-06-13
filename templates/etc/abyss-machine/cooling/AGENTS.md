# Abyss Machine Cooling Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/cooling/` and stable cooling policy
config files.

## Role

This directory owns compact cooling and thermal policy config. It is source
config, not thermal history, fan experiment output, or process attribution
evidence.

Current cooling evidence belongs under `{{ABYSS_MACHINE_STATE}}/cooling`.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`
- `{{ABYSS_MACHINE_STATE}}/cooling/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/processes/AGENTS.md` when thermal attribution is part
  of the change

Before durable mutation, run:

```bash
abyss-machine changes preflight --intent TEXT --surface {{ABYSS_MACHINE_ETC}}/cooling --json
```

## Boundaries

- Thin-laptop thermal routing is adaptive: stable `100-105C` is monitored
  active range, not automatic emergency.
- Do not encode emergency behavior from one snapshot without duration, trend,
  distribution, and throttle context.
- Do not kill, throttle, or re-affinitize processes from this config lane.
- Keep historical `*.bak-*` files as rollback evidence unless an explicit
  cleanup route is opened.

## Validation

```bash
abyss-machine cooling validate --json
abyss-machine processes validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State the policy file changed, the current thermal evidence consulted, the
validation status, and the rollback file or route.
