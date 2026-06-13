# Hook Stage: post_large_write

Stable policy hooks here run after large host-owned writes.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks post_large_write --json`

## Rules

- Use this stage for compact post-write checks and notices.
- Do not mutate project roots or move generated artifacts into `/work`.
- Prefer JSON-readable output.
