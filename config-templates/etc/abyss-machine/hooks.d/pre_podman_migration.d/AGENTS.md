# Hook Stage: pre_podman_migration

Stable policy hooks here run before rootless Podman storage migration.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks pre_podman_migration --json`

## Rules

- Do not migrate while containers are running.
- Use the storage-policy migration route and preflight evidence.
- This stage must not run broad filesystem cleanup.
