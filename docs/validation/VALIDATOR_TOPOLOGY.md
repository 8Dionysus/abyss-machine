# Validator Topology

## Public Lane

- `python -m pytest -q`
- `scripts/abyss-machine-bootstrap doctor --dry-run --json`
- `scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json`

## Host Contract Lane

- `python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"`
- `PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json`

## Publication Smoke

Scan the tracked tree for obvious secret patterns and forbidden live-state
paths before pushing public changes.
