# Hook Stage: pre_runtime_create

Stable policy hooks here run before creating host-owned runtimes.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks pre_runtime_create --json`

## Rules

- Validate target roots before runtime creation.
- Host runtimes belong under `{{ABYSS_MACHINE_SRV}}/runtimes`.
- Do not write into source repositories or stack-owned model roots.
