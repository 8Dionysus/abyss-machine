# Validation routes

Run only the route needed for the changed surface.

## Root readiness and release

```bash
python -m pytest -q PATH_TO_AFFECTED_TEST
python scripts/validation_evidence_graph.py --profile instant --sdk-root PATH_TO_PINNED_AOA_SDK
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
```

```bash
python scripts/release_check.py --sdk-root PATH_TO_PINNED_AOA_SDK --receipt /tmp/abyss-machine-validation.json
```

```bash
python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json
```

## Documentation and topology

Use the documentation and topology routes in `config-templates/etc/abyss-machine/VALIDATION.md` and `tools/VALIDATION.md` when those surfaces are affected.
