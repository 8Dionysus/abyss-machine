# Stack Bridge Hooks

This stable hook lane declares stack-bridge hook contracts.

## Route

- Stack bridge validate: `abyss-machine stack-bridge validate --json`
- Hook inventory: `abyss-machine storage hooks --json`

## Rules

- Hooks are contracts and handoff helpers, not automatic stack mutation.
- Do not mutate `{{ABYSS_OS_ROOT}}`, `/srv/abyss-stack`, or `{{ABYSS_USER_HOME}}/src/abyss-stack`.
- Large generated hook material belongs under `{{ABYSS_MACHINE_SRV}}/hooks.d/stack-bridge`.
