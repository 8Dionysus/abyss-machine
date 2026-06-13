# Hook Stage: post_runtime_create

Stable policy hooks here run after creating host-owned runtimes.

## Route

- Inventory: `abyss-machine storage hooks --json`
- Run stage: `abyss-machine storage run-hooks post_runtime_create --json`

## Rules

- Record compact runtime evidence only.
- Large logs or build outputs belong under `{{ABYSS_MACHINE_SRV}}`.
- Do not leave unapproved symlink tails.
