# Regression Tests

This lane stores regression tests for previous host failures.

## Route

- Quick tests: `abyss-machine test quick --json`
- Full tests: `abyss-machine test full --json`

## Rules

- Each regression should protect a real past failure mode or contract edge.
- Keep tests deterministic unless explicitly placed in `live`.
- Do not broaden regression tests into heavy benchmarks.
