# Hook Stage: pre_cache_cleanup

Stable policy hooks here run before cache cleanup.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks pre_cache_cleanup --json`

## Rules

- Treat cleanup as destructive until proven otherwise.
- Never target project roots, games, work roots, or stack source material.
- Prefer dry-run evidence before enforced cleanup.
