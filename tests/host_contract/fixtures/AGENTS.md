# Test Fixtures

This lane stores small deterministic test fixtures.

## Route

- Fixture root: `/srv/abyss-machine/tests/fixtures`
- Quick tests: `abyss-machine test quick --json`

## Rules

- Fixtures must be small, non-secret, and reproducible.
- Do not store live operator input, private browser content, or credentials here.
- If a fixture is derived from real data, keep the derivation safe and documented.
