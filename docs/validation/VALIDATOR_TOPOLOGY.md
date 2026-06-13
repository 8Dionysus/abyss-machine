# Validator Topology

## Public Lane

- `python scripts/ci_gate.py --mode source-fast`

The source-fast lane is defined in `docs/validation/validation_lanes.json` and
loads through `scripts/validation_lanes.py`. It checks repo topology,
mechanics topology, manifests, schemas, bootstrap dry-runs, public boundary,
generated scaffold index freshness, compileall, and public smoke tests.

## Host Contract Lane

- `python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"`
- `PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json`

## Release Lane

- `python scripts/release_check.py`
- `python scripts/release_check.py --include-host-contracts`

## Publication Smoke

Scan the tracked tree for obvious secret patterns and forbidden live-state
paths before pushing public changes.
