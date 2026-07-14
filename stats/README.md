# abyss-machine local stats port

This directory exposes statistical questions whose domain meaning belongs to
`abyss-machine`. It uses the shared `aoa-stats` measurement grammar without
moving host evidence or stack decisions into the central organ.

## Current measurement

`abyss-machine/ai-workload-measured-duration-coverage-ratio` asks what fraction
of the AI workload measurement records accepted for one workload-stats window
contain a finite, non-negative `measured_duration_sec` observation.

The existing `abyss-machine ai workload stats --json` read model is the
consumer. It reports numerator, denominator, ratio, missing count, invalid
count, population identity, window identity, and reporting rule. A zero ratio
is observed only for a non-empty population; an empty population is unknown.

## Evidence posture

The contract is live-capable and internal, but the Git export is
declaration-only. Live workload records and generated statistics remain under
the installed host's private state roots and are never copied into this public
repository.

## Authority

Duration coverage describes whether the selected records carry one valid
measurement field. It does not measure workload correctness, speed, quality,
resource efficiency, user value, promotion readiness, or permission to change
host or `abyss-stack` policy.

## Surfaces

- `port.manifest.json` declares the owner-local question and measurement.
- `src/abyss_machine/ai_runtime_contracts.py` owns the pure derivation and
  workload-stats document shape.
- `src/abyss_machine/ai_runtime_adapters.py` binds private workload records to
  that read model.
- `aoa-stats` owns shared validation and cross-owner composition.
