# stats Route

## Applies to

Everything under `stats/` in `abyss-machine`.

## Role

This directory owns host-local statistical questions and their measurement
contracts. Shared statistical grammar and cross-owner composition remain owned
by `aoa-stats`.

## Read before editing

1. Root `AGENTS.md`, `DESIGN.md`, and `BOUNDARIES.md`.
2. `stats/README.md` and `stats/port.manifest.json`.
3. The workload stats contracts and adapter in `src/abyss_machine/`.
4. The central measurement and local-port contracts under `aoa-stats/stats/`.

## Boundaries

- `port.manifest.json` owns the host-local question and measurement meaning.
- Live values remain in private installed-host evidence; do not commit a live
  packet or copy workload records into this directory.
- Duration coverage reports measurement presence only. It does not establish
  workload success, performance, quality, readiness, or stack policy.
- Missing and invalid duration fields remain in the population denominator.

## Validation

Manually exercise positive, invalid, missing, and empty-population inputs
against the workload stats read model before changing its invariants. Then run:

```bash
python scripts/validate_local_stats_port.py
```

Use the root validation route for the implementation and public seed.

## Closeout

Report the local question changed, manual cases inspected, runtime read model
affected, central protocol validation, and public-seed validation.
