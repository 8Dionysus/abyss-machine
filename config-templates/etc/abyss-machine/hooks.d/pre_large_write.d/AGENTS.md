# Hook Stage: pre_large_write

Stable policy hooks here run before large host-owned writes.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks pre_large_write --json`

## Rules

- Keep scripts compact and policy-focused.
- Non-zero exits block only when the caller uses `--enforce`.
- Do not write caches, runtimes, or logs here; use `{{ABYSS_MACHINE_SRV}}` or `{{ABYSS_MACHINE_STATE}}`.
