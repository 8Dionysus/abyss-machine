# Abyss Machine Tests

This card applies to `/srv/abyss-machine/tests`.

## Role

This tree owns host-machine test topology for `abyss-machine`. Tests here are
implementation companions for the host layer; they do not define AoA, Tree of
Sophia, `.aoa`, or `abyss-stack` source truth.

## Test Lanes

- `quick`: deterministic fixture, contract, and safety tests.
- `full`: all non-live/non-long/non-manual tests.
- `live`: read-only checks against the current machine and generated evidence.
- `long`: slow or resource-sensitive checks.
- `manual`: requires operator confirmation, credentials, restart, or live apply.

Local cards:

- `/srv/abyss-machine/tests/contract/AGENTS.md` - deterministic contract tests.
- `/srv/abyss-machine/tests/fixtures/AGENTS.md` - small synthetic fixtures.
- `/srv/abyss-machine/tests/live/AGENTS.md` - live host-state tests.
- `/srv/abyss-machine/tests/regression/AGENTS.md` - previous-failure regression tests.
- `/srv/abyss-machine/tests/safety/AGENTS.md` - safety and boundary tests.

`quick` and `full` must not require `sudo`, `pkexec`, root, network downloads,
service restarts, model downloads, dictation input, TTS mutation, or stack
mutation.

## Edit Rules

- Prefer synthetic fixtures and pure function tests for previous failure modes.
- Keep live tests explicitly marked `live`.
- Keep password-prompting or mutating actions out of automated tests.
- Do not write project-owned state under `/srv/AbyssOS`, `/srv/abyss-stack`,
  `/home/dionysus/src/abyss-stack`, `/work`, or `/srv/work`.
- When a test proves a host contract, point to the exact command or function it
  protects.

## Validation

```bash
abyss-machine test quick --json
abyss-machine test full --json
abyss-machine test live --json
```

Use `live` only when current host state should be sampled. Use `manual` only
with an operator present.
