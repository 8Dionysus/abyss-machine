# 0011 E2B Resident Selection Route

## Status

accepted

## Date

2026-05-23

## Index Tags

- ai-resident
- e2b-selection
- resource-gate
- validation-guard

## Current Applicability

As of 2026-05-23, resident E2B is a selected work lane, not a default
catch-all generator. The active source behavior lives in
`{{ABYSS_MACHINE_SRV}}/tools/abyss-gemma4-spark-resident`: jobs that can be
computed safely and completely from structured local evidence should default to
deterministic output under the shared stack endpoint, with model execution kept
as an explicit opt-in calibration path.

This decision also keeps occupied zram distinct from active memory pressure:
ordinary resident jobs should not degrade only because zram is highly occupied
when memory PSI is low and usable memory remains available. Sustained or heavy
routes may still defer.

## Context

The resident Gemma/E2B lane had become too broad. Several routing and
classification jobs were asking the model to produce outputs that deterministic
code could already produce with better boundedness:

- route-only or safety-only jobs risked timeouts and `ok_fallback` artifacts
  without adding useful judgment;
- stale dictation material could be fed into model work after the operator had
  moved on;
- high zram occupancy was treated too much like immediate load even when PSI
  and available memory showed no current stall;
- the heartbeat and candidate read models needed a clean distinction between
  useful model judgment and background route mechanics.

## Options Considered

- Keep all resident jobs model-backed:
  preserves uniformity, but creates unnecessary latency, parse fallback, and
  quality noise.
- Disable the weak jobs entirely:
  avoids bad artifacts, but loses heartbeat, safety, and candidate-selection
  visibility.
- Make deterministic jobs first-class and leave model execution opt-in:
  preserves useful read models while keeping E2B for work where language
  judgment adds value.

## Decision

Use deterministic defaults for resident jobs whose output is route, guard,
coverage, or compact readout material and whose source IDs can be preserved
without model interpretation.

The active resident route is:

- deterministic by default for query expansion, storage classification, daily
  brief, resident-quality eval, action-card compilation, bounded hint
  generation, risk sentinel, and short document classification under the stack
  endpoint;
- model-backed for selected jobs where bounded language judgment is useful,
  such as lightweight reranking, source-quality scoring, browser reading, and
  thermal-performance review;
- stale source material becomes `idle` or review-only instead of being pushed
  through a model path;
- high zram occupancy with low PSI is a warning/route signal for ordinary jobs,
  not an automatic degradation verdict.

Model execution for deterministic-default jobs may be enabled only through
explicit environment opt-ins on the resident runner, for calibration or
investigation.

## Rationale

Selection is the quality layer. A small resident model is most useful when it
is asked to rank, compress, or label bounded evidence where language judgment
matters. It is weaker when asked to repeat deterministic policy decisions,
emit route-only safety cards, or classify source shapes that are already
structured.

Making deterministic outputs first-class keeps the system breathing: heartbeat
and candidate queues stay fresh, parse fallback disappears, and E2B remains
available for the few jobs where it earns its cost. This also gives future E4B
or workhorse lanes cleaner review inputs instead of noisy resident artifacts.

## Consequences

- Resident jobs can refresh more often without consuming a model slot.
- `jobs refresh` can rebuild aggregates and candidate read models without
  generation.
- Heartbeat can distinguish E2B quality from unrelated source freshness,
  pressure, or change-ledger warnings.
- Future agents must treat `ok_deterministic` as a valid selected result, not
  as degraded fallback.
- Model-backed calibration remains available, but opt-in calibration must be
  explicit and validated.

## Boundaries

- This does not ban resident model use.
- This does not make E2B a replacement for E4B/workhorse review.
- This does not promote stack-owned runtime winner decisions into
  `abyss-machine`; abyss-stack still owns stack runtime promotion.
- This does not authorize automatic execution from action cards or risk routes.
- Exact job lists and thresholds are source behavior, not frozen by this
  rationale record.

## Review Log

- 2026-05-23: Initial record after resident artifacts were repaired to remove
  model parse fallback, stale source use, and inappropriate zram-only
  degradation.
- 2026-05-23: A live `query_expansion` model-backed probe timed out and wrote
  an `ok_fallback` artifact under current stack endpoint conditions. Query
  expansion moved into the deterministic-default set with explicit opt-in model
  calibration through `ABYSS_GEMMA4_SPARK_MODEL_QUERY_EXPANSION`.

## Source Surfaces

- `{{ABYSS_MACHINE_SRV}}/tools/abyss-gemma4-spark-resident`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_USER_HOME}}/src/abyss-stack/compose/tuning/llamacpp.gemma4-e2b.intel-285h.vulkan.yml`
- `{{ABYSS_OS_ROOT}}/abyss-stack/Configs/compose/tuning/llamacpp.gemma4-e2b.intel-285h.vulkan.yml`
- `{{ABYSS_MACHINE_STATE}}/changes/active/e2b-residual-quality-identity-20260523`

## Validation

- `python3 -m py_compile {{ABYSS_MACHINE_SRV}}/tools/abyss-gemma4-spark-resident`
- `abyss-machine ai llm resident validate --json`
- `abyss-machine ai llm resident jobs-validate --json`
- `abyss-machine ai llm resident candidates-validate --json`
- `abyss-machine ai llm resident evals --json`
- `abyss-machine ai llm resident evals-validate --json`
- `abyss-machine ai llm resident smoke --json`
- `abyss-machine typing validate --json`
- `abyss-machine nervous brief --scope now --json`
- `abyss-machine heartbeats pulse --json`

## Follow-up Route

Future resident-job changes should update the runner first, then refresh
candidate/eval read models, then decide through the change close gate whether
this record needs a dated review entry or a successor decision.
