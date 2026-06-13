# Contract Tests

This lane stores host-machine contract tests.

## Route

- Quick tests: `abyss-machine test quick --json`
- Full tests: `abyss-machine test full --json`

## Rules

- Contract tests should be deterministic and not require network, sudo, service restarts, or model downloads.
- Prefer synthetic fixtures.
- Tests here protect host contracts, not project doctrine.
