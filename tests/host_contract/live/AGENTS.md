# Live Tests

This lane stores tests that sample current host state.

## Route

- Live tests: `abyss-machine test live --json`

## Rules

- Live tests may depend on current machine state and should be clearly separated from quick/full tests.
- They must not mutate services or require passwords unless explicitly marked manual elsewhere.
- Record residual risk when live state is unavailable or stale.
