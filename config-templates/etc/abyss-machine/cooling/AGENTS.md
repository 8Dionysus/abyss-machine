# Abyss Machine Cooling Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/cooling/` and stable cooling policy
config files.

## Role

This directory owns compact cooling and thermal policy config. It is source
config, not thermal history, fan experiment output, or process attribution
evidence.

Current cooling evidence belongs under `{{ABYSS_MACHINE_STATE}}/cooling`.

## Route selection

Use `TOPOLOGY.md` for sensor/root topology, the cooling state card for current
evidence, and the processes state card only when thermal attribution changes.

Before durable mutation, run:

Run `VALIDATION.md` in this directory for the on-demand preflight.

## Boundaries

- Thin-laptop thermal routing is adaptive: stable `100-105C` is monitored
  active range, not automatic emergency.
- Do not encode emergency behavior from one snapshot without duration, trend,
  distribution, and throttle context.
- Do not kill, throttle, or re-affinitize processes from this config lane.
- Keep historical `*.bak-*` files as rollback evidence unless an explicit
  cleanup route is opened.

## Validation

Run `abyss-machine cooling validate --json`. Add process validation for thermal
attribution and docs-mesh validation for card changes.

## Closeout

State the policy file changed, the current thermal evidence consulted, the
validation status, and the rollback file or route.
