# Hook Stage: post_cache_cleanup

Stable policy hooks here run after cache cleanup.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks post_cache_cleanup --json`

## Rules

- Record compact cleanup evidence and residual risk.
- Do not create new cleanup targets from this stage alone.
- Preserve rollback-relevant facts when available.
