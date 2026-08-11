# 0026 Promote Claim Evidence Validation Graph

## Status

accepted

## Date

2026-08-11

## Index Tags

- validation-scheduler
- owner-boundary
- proof-sufficiency
- resource-concurrency
- rollback-guard

## Current Applicability

As of 2026-08-11, the complete owner claim/evidence graph is the default local
release check and protected GitHub `Repo Validation` route. It uses the exact
clean `aoa-sdk` scheduler pin, graph width three, and
`pytest-xdist==3.8.0` with two workers. The serial release-public route remains
the independent completeness oracle and explicit rollback. Changed-path routing
is shadow-only, and cross-run receipt reuse is not admitted.

## Context

The serial public and release-artifact lanes preserved strong proof but forced
the isolated first-run projection, the complete public pytest corpus, short
source contracts, and repeated artifact checks to wait on one another. Protected
same-head runs spent 225 to 240 seconds in those serial steps, so every repair
and retry amplified landing latency for real agent sessions.

The owner needed lower latency without deleting checks, weakening fail-closed
behavior, treating a partial route as full proof, or trusting an unbound shared
scheduler. Isolated pytest speed was also insufficient evidence because pytest
workers compete with other graph nodes for the same runner.

## Options Considered

- Keep the serial route as the default and optimize individual validators only.
- Run the unchanged serial pytest command inside owner DAGs of width two or
  three.
- Combine DAG widths two and three with pytest-xdist at two or four workers.
- Combine both DAG widths with deterministic static two-way file sharding.
- Promote changed-path selection or cross-run receipts together with the full
  graph.

## Decision

Make the full owner graph the default and protected gate. Bind it to clean
`aoa-sdk@b73c8aca9ef5275df0ec9e3e55d446db08823fb2`, graph width three, and
exact `pytest-xdist==3.8.0` scheduling with two workers.

Require the owner adapter to prove that every non-pytest leaf command is an
exact multiset match to the serial oracle and that the only scheduler delta is
`python -m pytest -q` becoming `python -m pytest -q -n 2`. A changed test
selection, extra or missing obligation, scheduler-version drift, dirty or
wrong SDK checkout, unstable owner or runner identity, unreadable input,
missing evidence, or failed node must deny sufficiency.

Keep `python scripts/release_check.py --mode serial` and
`ABYSS_MACHINE_VALIDATION_MODE=serial` as the independent rollback. Keep the
one-second instant profile explicitly bounded and non-full. Keep path routing
shadow-only and retain no cross-run reuse. Move the six-way comparison workflow
to manual dispatch after promotion.

## Rationale

The full serial-command DAG at width three completed in 114.293 seconds while
preserving all five evidence classes. Combined hosted repetitions then measured
the scheduler candidates under real contention. Successful width-three samples
for xdist-2 were 79.419, 83.035, and 81.886 seconds, with an 81.886-second
median. Static-2 had an 89.326-second median; xdist-4 had a 90.466-second median
and much higher variance. Width two was consistently slower because it delayed
one of the two dominant nodes.

The selected route reduces the full owner proof by about 64 percent relative
to the 226-second same-head serial source-plus-artifact route while retaining
the same obligations. Two pytest workers also consume less peak parallelism
than xdist-4 and were more stable across hosted runners.

One repeated xdist-2 run did not pass: it exposed that the resource-admission
Unix socket became visible between `bind()` and `chmod(0600)`. That result was
treated as a product defect, not discarded as noise. The server now prepares
the socket in a private staging directory and atomically publishes the already
private inode without replacing or deleting a competing path. Two post-fix
same-head combined runs then supplied the complete evidence set.

## Consequences

- Ordinary full validation overlaps independent expensive obligations and
  produces a receipt-bound sufficiency decision.
- Edit loops gain a sub-second graph-contract tier, while focused behavioral
  tests remain selected by the engineer or agent.
- CI and local full validation require the exact SDK checkout and pinned xdist
  dependency.
- Serial remains intentionally available and is expected to be slower.
- Full-gate timing still varies with hosted CPU allocation; decisions use
  repeated whole-graph samples rather than one record run.
- Partial routing and reuse can be evaluated later without inheriting authority
  from this decision.

## Boundaries

- This decision does not remove, skip, or narrow an owner proof obligation.
- It does not make a shadow, instant, partial, stale, or foreign-owner receipt
  sufficient for the full owner gate.
- It does not make the SDK runner authoritative for owner claims; the manifest,
  risks, evidence requirements, and serial oracle remain `abyss-machine` owned.
- It does not replace installed-host, runtime-health, artifact-publication, or
  sibling-owner evidence.
- It does not authorize changed-path routing or cross-run receipt reuse.

## Review Log

- 2026-08-11: Initial accepted record after standalone, combined, repeated,
  negative-control, and same-head serial comparisons.

## Source Surfaces

- `docs/validation/validation_evidence_graph.json`
- `scripts/validation_evidence_graph.py`
- `scripts/release_check.py`
- `scripts/pytest_scheduler_experiment.py`
- `scripts/validation_scheduler_experiment.py`
- `.github/workflows/repo-validation.yml`
- `.github/workflows/validation-evidence-shadow.yml`
- `src/abyss_machine/resource_admission_adapters.py`
- `tests/public_smoke/test_validation_evidence_graph.py`
- `tests/public_smoke/test_resource_admission_adapters.py`

## Validation

- Hosted standalone and DAG comparison: run `31536733765`.
- Hosted combined comparison before the race fix: run `31539244992`, attempts
  one and two; attempt two is the required negative result.
- Same-head protected serial oracle: runs `31539244997` and `31540515125`.
- Hosted post-fix combined comparison: run `31540515119`, attempts one and two;
  every receipt has stable owner and runner identity and no missing evidence.
- The promoted protected run must upload an authoritative full receipt before
  landing; postmerge runs retain the same check name and explicit serial
  rollback.

## Follow-up Route

Use `docs/validation/validation_evidence_graph.json` for owner claims and the
adapter tests for scheduler equivalence. Evaluate changed-path routing and
cross-run reuse independently in shadow with false-positive and false-negative
controls. Roll the same ABI out owner by owner across AbyssOS; do not infer
another repository's claims or safe concurrency from this owner result.
