# stats Route

## Applies to

Everything under `stats/` in `abyss-machine`.

## Role

This directory owns host-local statistical questions and their measurement
contracts. Shared statistical grammar and cross-owner composition remain owned
by `aoa-stats`.

## Route selection

Use `stats/port.manifest.json`, the affected workload contracts/adapters under
`src/abyss_machine/`, and the central measurement protocol under `aoa-stats`.
Consult `stats/README.md` when the public question or local-port explanation
changes, and `DESIGN.md` or `BOUNDARIES.md` only for owner-boundary changes.

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
