# Hook Stage: process_snapshot

Stable policy hooks here run during process snapshot capture.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks process_snapshot --json`

## Rules

- Keep hooks read-only against process state.
- Do not kill, throttle, or restart processes from this stage.
- Large or derived process evidence belongs under `{{ABYSS_MACHINE_STATE}}/processes`.
