# Hook Stage: post_podman_migration

Stable policy hooks here run after rootless Podman storage migration.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks post_podman_migration --json`

## Rules

- Verify graphroot and container state after migration.
- Preserve rollback evidence.
- Do not delete old storage until migration is proven and approved.
