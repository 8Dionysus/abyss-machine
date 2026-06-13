# Abyss Machine Test Topology

This tree gives `abyss-machine` a convex test shape: fast local regression tests
near the host contracts, live read-only smoke tests separated from them, and
explicit slow/manual lanes for work that can affect operator experience.

## Lanes

| Lane | Command | Purpose |
| --- | --- | --- |
| `quick` | `abyss-machine test quick --json` | fixture, JSON contract, and safety regressions |
| `full` | `abyss-machine test full --json` | all non-live, non-long, non-manual tests |
| `live` | `abyss-machine test live --json` | read-only current-machine validators and smoke checks |
| `long` | `abyss-machine test long --json` | slow/resource-sensitive probes |
| `manual` | `abyss-machine test manual --json` | operator-gated checks only |

`quick` and `full` are safe to run unattended. They must not open password
prompts, restart services, mutate TTS/dictation, tune memory, or change stack
services. `live` may refresh generated evidence through existing read-only
validators, but it still must not apply changes.

## Layout

- `contract/`: CLI JSON, stable schema names, bridge, and output-shape contracts.
- `regression/`: synthetic fixtures for previous failure modes.
- `safety/`: boundary, dry-run, and non-mutation checks.
- `live/`: explicitly marked read-only checks against current host state.
- `fixtures/`: reusable sample payloads.

## Direct Pytest Use

```bash
python -m pytest -q /srv/abyss-machine/tests -m "quick and not live and not long and not manual"
python -m pytest -q /srv/abyss-machine/tests -m "not live and not long and not manual"
python -m pytest -q /srv/abyss-machine/tests -m "live and not manual"
```

The wrapper under `/srv/abyss-machine/tools/abyss-machine-test` and the
`abyss-machine test` command use the same marker routes.
