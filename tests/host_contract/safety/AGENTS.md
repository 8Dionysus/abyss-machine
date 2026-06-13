# Safety Tests

This lane stores safety and boundary tests.

## Route

- Quick tests: `abyss-machine test quick --json`
- Full tests: `abyss-machine test full --json`

## Rules

- Safety tests must protect root boundaries, project-readonly rules, privacy policy, and destructive-action gates.
- They must not perform destructive actions.
- Prefer dry-run and synthetic evidence.
