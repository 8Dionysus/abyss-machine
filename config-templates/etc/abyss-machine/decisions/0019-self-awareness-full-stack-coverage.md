# 0019 Self-Awareness Full Stack Coverage

## Status

accepted

## Date

2026-06-04

## Index Tags

- self-awareness
- stack-bridge
- langgraph
- observability
- ai-resident
- rag
- owner-boundary
- validation-guard

## Current Applicability

As of 2026-06-04, this decision extends 0018. The current route is the
expanded `abyss-machine self-awareness ...` command family: capability map,
requirements API/handoff, requirement-probes acceptance verifier, bounded
query, correlation, investigation, replay, semantic brief, failure matrix,
probe, cycle, export, and validation.

As of the later 2026-06-04 review, the same route also covers resident AI and
active stack service organs: STT, embeddings, LLM profiles, TTS, NPU,
warm-E2B/gemma4 resident status, E4B/Qwen escalation gates, RAG/memory,
nervous freshness, `route-api`, `rag-api`, `langchain-api`, Postgres, Neo4j,
governed reactions/responses, explicit failure-mode coverage, and E2E cycle
proof. Stack-owned gaps remain requirements, not host-layer mutations.

As of the 2026-06-05 stack-runbook review, requirement-probes also carry
stack-owner runbook candidates for each stack-owned blocker. The candidates
describe proposed stack work, acceptance steps, risk, blast radius, rollback,
and evidence refs while remaining handoff-only.

As of the 2026-06-05 governance-gate review, the capability map exposes
concrete memory/resource/mode readiness for `host.governance-gates` instead of
placeholder status fields. Model escalation and response routing can now see
current memory class, resource orchestrator state, mode effective state, launch
limits, and non-mutating policy in the same self-awareness capability surface.

As of the 2026-06-05 export-manifest review, the portable self-awareness export
also carries a structured manifest and artifact list with schema checks,
history paths, hashes, evidence refs, and owner-boundary policy.

As of the 2026-06-05 resident-worker detail review, warm-E2B/gemma4 is no
longer represented by status alone. The capability map and investigation graph
carry concrete stack-owned serving health, monitor timers, resource/thermal
posture, candidate queues, heartbeat evals, and non-action policy.

As of the 2026-06-05 AI multimodal detail review, `ai.multimodal.capability-map`
is no longer a status-only list. It carries concrete STT, embeddings, LLM text,
TTS, NPU, stack model-root, OpenVINO device, LLM/TTS profile, eval, host cache,
and non-promotion policy detail.

As of the 2026-06-05 LLM escalation detail review, `llm.escalation.routes` is
no longer a status-only list. It carries sourceful E4B workhorse
pack/review/validate/preflight state, current model-execution gate status, Qwen
lazy-load command/context/cpuset/cache detail, and explicit review-only,
non-action, non-stack-mutating policy.

As of the 2026-06-05 stack handoff probe detail review, open stack-owned
read-route probes are self-contained. Each `requirement-probes.probes[]` row
explicitly marks `stack_handoff: true` and preserves the acceptance contract,
machine closure probe, verifier steps, closure semantics, current state,
evidence refs, and the handoff-only runbook candidate needed by the stack owner.

As of the 2026-06-05 capability-matrix-depth review, `self-awareness
capabilities` is no longer a status-only map. Every capability row carries a
normalized matrix record with endpoint or latest-artifact evidence, schemas,
freshness, history route, auth-safe read-only access, evidence-route counts, and
owner-boundary policy.

As of the 2026-06-05 signal-fabric-depth review, observation events are no
longer loose resource/context/space records. Every event carries a normalized
fabric record with actor, entity, temporal bucket, spatial owner surface,
context links, redacted source query, evidence route, label policy, and
read-only/no-stack-mutation policy.

As of the 2026-06-05 investigation stack-handoff action-map review, the
prioritized stack-owner action map is preserved inside checkpointed
investigation state, not only in the semantic brief or portable export.

As of the 2026-06-05 stack handoff time-space overlay review, open stack-owned
blockers are also projected into timeline markers and spatial graph
nodes/edges, so missing stack potential remains visible across time and space.

As of the 2026-06-05 stack handoff causal-episode review, those same open
stack-owned blockers also become conservative `stack_handoff_blocker` causal
episodes and non-executing alert/reaction/response candidates. The response
contract preserves requirement id, stack-owner runbook, verifier commands,
evidence refs, and no-stack-mutation policy while keeping the claim at
`truth_level=handoff_candidate`.

As of the 2026-06-05 closure-readiness review, stack handoff probes, briefs,
time-space overlays, and exports also preserve `closure_readiness` packets for
each stack-owned blocker. These packets separate fulfilled checks from missing
checks, preserve dependency requirement ids, name evidence still needed for
closure, keep verifier commands, and retain no-stack-mutation policy.

As of the 2026-06-05 closure-readiness replay review, investigation, replay,
and cycle artifacts also preserve `stack_handoff_closure_readiness` as a
first-class replay contract. The E2E cycle cannot claim covered status unless
`replay.stack_handoff_replay` proves the readiness packet survived the
checkpointed investigation states.

As of the 2026-06-05 bounded-context review, `context/latest.json` also carries
`context_packet`: a bounded resident/operator packet that joins compact
correlation context, memory-space, stack handoff, resident worker, governance
gates, escalation gate state, read-only tools, evidence refs, and no-action
policy without storing raw private content or mutating `abyss-stack`.

As of the 2026-06-05 stack-closure dossier review, open stack-owned blockers are
also joined into `stack-closure-dossier/latest.json`: an ordered stack-owner
closure packet over requirements, probes, readiness, dependency graph, runbook
candidates, verifier commands, evidence/artifact refs, and handoff-only policy.

As of the 2026-06-05 stack-closure impact review, the same dossier also carries
reverse unblocks edges and per-entry `closure_impact`, so closing a root blocker
such as trace backend exposes which downstream stack-owned blockers it unblocks.

As of the 2026-06-05 stack-coverage impact review, each dossier entry also
carries `coverage_impact`, mapping the blocker to self-awareness planes, the
affected AI-OS organ, affected stack/machine surfaces, closure value, and proof
commands.

As of the 2026-06-05 coverage-impact propagation review, that same impact is
also carried through the active reasoning loop: `brief.stack_handoff_action_map`,
bounded `context` stack handoff packets, `investigate` request/validation/
conclusion state, and `replay.stack_handoff_replay`. Open stack blockers must
remain visible as blocked AI-OS organs and planes, not only as readiness gaps.

As of the 2026-06-05 stack-compat contract review, each stack-owned blocker
also has a `compat_contract` in requirements handoff and
`stack-closure-dossier`. The contract names exact stack route/export options,
minimum fields, redaction/boundedness policy, dependency and unblocks order,
coverage impact, post-close machine verifiers, and the rule that
`abyss-machine` remains a read-only consumer.

As of the 2026-06-05 from-zero cycle proof review, `cycle/latest.json` also
stores `from_zero_proof`: an artifact-level chain map from capability/signal
fabric through timeline, spatial graph, context, episodes, alerts, warm-E2B,
RAG/memory, investigation, replay, reactions/responses, and export. The E2E
cycle is not covered unless each chain obligation has machine-owned artifact
evidence with schema, hash, freshness metadata, and no-stack-mutation policy.

As of the 2026-06-05 machine-bridge proof review, the cycle also stores
`bridge_proof` and a `machine_bridges` chain obligation. Heartbeats, memory,
mode, resource, process/container/thermal, cooling, typing, nervous, reactions,
and responses must be visible as machine-owned latest artifacts before the E2E
cycle can claim full coverage.

## Context

The first self-awareness layer connected metrics, logs, alerts, process facts,
time, spatial overlays, causal episodes, reaction candidates, and briefs. That
proved the spine, but it did not cover the full stack potential requested for
OS Abyss: capability discovery, explicit stack-owned gaps, SLO/error-budget
views, anomaly baselines, replayable investigation, portable export, resident
model work, memory/RAG evidence, or active stack data/API services.

The owner boundary remains the main pressure. `abyss-stack` owns Prometheus,
Grafana, Loki, Alloy, Alertmanager, trace runtime, dashboards, exporters, and
stack config. `abyss-machine` may read evidence and write host-owned
readmodels, but it must not repair or mutate stack runtime.

## Options Considered

- Treat missing Tempo, Grafana datasource auth, or trace backend as validator
  failures. This would make host validation depend on stack promotion work and
  push the host layer toward stack mutation.
- Add stack changes from `abyss-machine`. This violates the boundary and would
  make future stack ownership unclear.
- Add machine-owned capability and requirement readmodels, then keep the
  investigation/replay/export loop green using the evidence that is available.

## Decision

Add full self-awareness coverage as machine-owned readmodels:

- capability map over Prometheus, Loki, Grafana, Alloy/OTel, Alertmanager,
  optional trace backend, LangGraph runtime, host/container service map, active
  stack services, local AI modalities, resident warm-E2B, and model escalation
  routes;
- capability-matrix row depth for each capability, including endpoint or latest
  artifact route, schemas, freshness, history, auth-safe read-only access, and
  owner-boundary policy;
- requirements report for stack-owned or machine-owned capability gaps;
- requirements API/handoff with owner, expected shape, evidence refs, and
  machine-checkable acceptance contracts for stack-owned blockers;
- requirement-probes verifier that evaluates current stack-owned handoff
  acceptance contracts using bounded read-only evidence and keeps open gaps as
  blockers rather than host-layer failures;
- stack-owner runbook candidates inside requirement-probes so each open blocker
  has a machine-checkable handoff route with risk, blast radius, rollback,
  acceptance steps, and cited evidence;
- self-contained requirement-probe rows preserving the closure probe,
  acceptance contract, verifier steps, closure semantics, current state,
  evidence refs, explicit `stack_handoff: true`, and runbook candidate for each
  stack-owned blocker;
- closure-readiness packets inside requirement-probes and downstream handoff
  artifacts, preserving fulfilled checks, missing checks, dependency
  requirement ids, evidence still needed for closure, verifier commands, safe
  next action, and handoff-only no-stack-mutation policy;
- stack-closure dossier artifact that joins requirements and probes into one
  ordered stack-owner closure packet with current state, readiness, dependency
  graph, reverse unblocks graph, closure impact, runbook candidates, verifier
  chain, coverage impact, artifact refs, and no-execution/no-stack-mutation/
  no-secret policy;
- stack compat contracts for every stack-owned blocker, exposed in
  requirements handoff and the closure dossier, so `abyss-stack` receives the
  exact route/export schema, redaction/boundedness expectations, dependency
  order, coverage impact, and post-close machine verifier contract without
  `abyss-machine` mutating stack-owned surfaces;
- from-zero cycle proof rows in `cycle/latest.json`, binding each E2E chain
  obligation to machine-owned artifact evidence with command, path, schema,
  hash, freshness metadata, evidence refs, and no-stack-mutation policy;
- machine bridge proof rows in `cycle/latest.json` for heartbeat, memory, mode,
  resource, process/container/thermal, cooling, typing, nervous, reactions, and
  responses, so host bridge organs are explicit cycle obligations rather than
  implicit context details;
- failure matrix for open requirements, missing/stale observability, downtime,
  cardinality risk, secret redaction, stale nervous semantics, and resource
  denial;
- signal-fabric depth for every normalized observation event, including actor,
  entity, temporal, spatial, context-link, source-query, evidence-route,
  label-policy, and non-mutating policy metadata;
- bounded query and correlation readmodels for PromQL, LogQL, context joins,
  service dependencies, SLO/error-budget, anomaly baselines, and provenance;
- RAG/memory/nervous freshness evidence as gates before reasoning, with stale
  semantic sidecars exposed instead of hidden;
- memory-space overlay depth in context, spatial graph, and query surfaces,
  including bounded RAG packets, maps/graph/memory/nervous freshness gates,
  Postgres/Neo4j/RAG/embeddings semantic backend state, evidence refs, and
  raw-evidence-is-not-truth/no-stack-mutation policy;
- bounded context packet inside `context/latest.json` for resident/operator
  reasoning, joining compact correlation context, memory-space, stack handoff,
  resident worker, governance gates, escalation gate state, read-only tools,
  evidence refs, redaction bounds, and no-action/no-stack-mutation policy;
- memory/resource/mode governance gate detail before model escalation or
  response routing;
- AI multimodal detail for STT, embeddings, LLM text, TTS, NPU, stack model
  roots, OpenVINO devices, LLM/TTS profile evidence, host-managed cache/runtime
  boundaries, and non-promotion policy;
- LLM escalation detail for E4B workhorse review-only routing, preflight/model
  execution gates, Qwen3.6 lazy-load routes, context/cpuset/cache evidence, and
  non-action/non-stack-mutating policy;
- resident cognitive-worker depth in investigations, including bounded context
  packet, read-only PromQL/LogQL/RAG/graph/context tools, hypothesis tests,
  contradiction notes, evidence-cited summary, and resource/mode-gated
  escalation state;
- checkpointed LangGraph-style investigation with full
  plan/query/resident-context/reason/request/validate/record/brief/conclusion
  node order, resume metadata, replay, conclusion diff, and non-mutating
  failure recovery;
- prioritized stack-handoff action map inside investigation/replay state,
  including `request_more_evidence` action rows, `brief_reaction_candidate`,
  top-level investigation payload, and semantic conclusion copies with closure
  blockers, runbook candidates, verifier commands, safe next action, evidence
  refs, and handoff-only policy;
- first-class stack handoff closure-readiness replay packet inside
  investigation, replay, and cycle artifacts, preserving ordered next actions,
  fulfilled/missing checks, blocker keys, dependency edges, verifier commands,
  safe next action, evidence refs, and no-execution/no-stack-mutation policy
  across the checkpoint chain;
- stack handoff time-space overlay inside timeline and spatial graph artifacts,
  with one marker per open stack-owned blocker and spatial nodes/edges for
  requirements, handoff actions, runbook candidates, affected stack services,
  evidence refs, verifier commands, and non-mutating policy;
- stack handoff causal episodes and alert candidates, with one
  `stack_handoff_blocker` handoff candidate per open stack-owned blocker and
  response-contract depth that preserves requirement id, marker id, stack-owner
  runbook, verifier commands, evidence refs, and handoff-only no-stack-mutation
  policy through reactions and responses;
- cycle proof that binds probe, failure matrix, investigation, replay, brief,
  reactions, responses, and export into one evidence-cited artifact;
- response-layer contracts that preserve validated episode lineage,
  investigation/replay evidence, risk, blast radius, rollback, and runbook
  candidates from self-awareness alerts through reactions and responses;
- resident-context packet support for warm-E2B candidate synthesis under
  evidence, resource, and mode constraints;
- resident-worker detail requiring serving owner/latency, monitor timers,
  resource/thermal posture, candidate readmodel summary, heartbeat evals, and
  explicit no-model-execution/no-stack-mutation/no-action policy;
- export bundle for latest artifacts;
- export manifest for latest artifacts, including per-artifact schema, history,
  hash, evidence ref, and non-mutating owner-boundary metadata;
- stricter probe and validator requiring the full chain.

## Rationale

This gives the machine a deeper self-observation loop without lying about
missing stack capabilities. Missing stack features become owner-routed
requirements, not hidden host-layer mutations. Investigation state is
replayable, bounded, and separate from durable artifacts; conclusions stay
evidence-cited candidates.

## Consequences

- `self-awareness validate` now checks the broader chain.
- `self-awareness context`, `spatial-graph`, and `query` now expose a bounded
  memory-space overlay. Stale freshness gates are surfaced with maintenance
  routes; open stack semantic routes remain owner-routed requirements.
- `self-awareness investigate` now exposes `resident_cognitive_packet` so the
  resident worker is a bounded evidence consumer with read-only tools and
  hypothesis/contradiction discipline, not an automatic model executor.
- `self-awareness investigate` now requires the full LangGraph-style loop
  order: `plan_queries`, `query_evidence`, `resident_context_packet`,
  `reason_over_evidence`, `request_more_evidence`, `validate_evidence`,
  `record_artifact`, `brief_reaction_candidate`, and
  `write_semantic_conclusion`. The validator rejects missing request,
  validation, artifact-record, resume, failure-recovery, or approval-gate
  fields.
- `self-awareness replay` now replays the same node order and exposes resume,
  conclusion diff, failure recovery, and non-action/non-stack-mutating policy.
- `self-awareness alerts`, `reactions`, and `responses` now require a
  self-awareness response contract so validated episodes do not collapse into a
  bare command suggestion. The route preserves episode lineage,
  investigation/replay evidence, risk, blast radius, rollback, runbook
  candidate, evidence refs, and non-mutating owner gates.
- `self-awareness episodes` now converts stack handoff time-space markers into
  `stack_handoff_blocker` causal episodes, and `self-awareness alerts` routes
  those no-event handoff candidates into the same response-contract lineage as
  alert-backed episodes. The stack-owned blocker remains a handoff candidate,
  not a host-layer failure or root-cause fact.
- `self-awareness requirements` exposes stack-owned blockers as a first-class
  handoff instead of making consumers scrape the capability map.
- `self-awareness requirement-probes` executes the machine side of each
  stack-owned acceptance contract and reports open/closed status with evidence
  refs, without treating open stack work as host validation failure.
- `self-awareness requirement-probes` now also emits handoff-only runbook
  candidates for stack-owned blockers. Validation requires those candidates to
  include owner route, no-machine-mutation policy, risk, blast radius,
  rollback, acceptance steps, and evidence refs.
- `self-awareness requirement-probes` rows now preserve their own
  `stack_handoff: true`, `acceptance_contract`, `machine_closure_probe`,
  `acceptance_verifiers`, and `closure_semantics`. A probe row that only reports
  open/closed status is not enough for stack handoff.
- `self-awareness requirement-probes`, `brief`, `timeline`, `spatial-graph`,
  and `export` now preserve closure-readiness packets so stack owner work can
  see which checks are already fulfilled, which evidence is still missing, and
  which stack-owned blockers depend on another blocker before closure.
- Stack-owned handoff entries now include a closure probe plan, verifier
  commands, redaction and boundedness expectations, and explicit no-stack-
  mutation guardrails; a reachable endpoint alone is not enough to close a
  requirement.
- `self-awareness capabilities` now classifies Grafana datasource evidence as
  bounded health plus candidate source inference: Grafana health/version and
  Prometheus/Loki/Alertmanager/Tempo candidates are consumed stack evidence,
  while authoritative datasource inventory remains a stack-owned read-only
  token/export blocker.
- `self-awareness capabilities` now classifies trace/OTel evidence as two
  separate truths: Prometheus/Alloy/Loki metric-log pipeline and bounded
  traceparent LogQL queryability are consumed stack evidence, while
  Tempo-compatible ready/search routes and span/log/metric join support remain
  stack-owned blockers.
- `self-awareness capabilities` now discovers the live stack-owned
  `langchain-api` health/OpenAPI route at `127.0.0.1:5403` as bounded evidence
  and classifies `/run`, `/run/federated`, `/embeddings`, OVMS provider/auth
  metadata, and request schema names as runtime route shape. The stack-owned
  LangChain/LangGraph blocker is narrowed to missing read-only
  thread/checkpoint/trace inventory plus trace-backend coupling, not generic
  API absence.
- `self-awareness capabilities` now discovers live stack-owned route/RAG/DB/
  graph surfaces as bounded memory-space evidence: `route-api` health/OpenAPI,
  `rag-api` health/OpenAPI plus collections/sources/agentic-graph shape,
  Postgres TCP readiness, and Neo4j root metadata. The stack-owned database/
  graph blocker is narrowed to missing Postgres schema/freshness and Neo4j
  label/relationship/freshness inventory, not generic service absence.
- `self-awareness export` now lifts the stack-owned handoff into top-level
  portable `requirements` and `stack_handoff` sections. The export preserves
  open requirement ids, closure blockers, current state, runbook candidates,
  acceptance verifier steps, artifact refs, and no-stack-mutation/no-secret/
  no-action policy so the next stack-owner pass can start from one artifact.
- `self-awareness brief` now exposes an operator-facing
  `stack_handoff_action_map` over the same open stack-owned blockers. It
  prioritizes the next stack-owner review path and carries closure blocker keys,
  current state, runbooks, verifier commands, evidence refs, and handoff-only
  no-execution policy in the semantic brief.
- `self-awareness investigate` now preserves the same `stack_handoff_action_map`
  across `request_more_evidence`, `brief_reaction_candidate`, top-level
  investigation payload, and semantic conclusion. Validation rejects an
  investigation that loses closure blockers, runbooks, verifier commands, safe
  next action, or no-stack-mutation policy.
- `self-awareness timeline` and `self-awareness spatial-graph` now preserve open
  stack-owned blockers as a time-space overlay. Validation rejects missing
  timeline markers, missing spatial requirement/action/runbook nodes, missing
  affected-service edges, or any action/stack-mutation policy in that overlay.
- `self-awareness failure-matrix` makes negative-path coverage part of the
  bridge contract, not an undocumented probe side effect.
- `self-awareness capabilities` now requires concrete governance gate detail
  for memory, resource, and mode readiness. A present capability id with null
  status fields is not enough for full coverage.
- `self-awareness capabilities` now requires normalized matrix depth on every
  row. A present capability id without endpoint/artifact route, schema,
  freshness, history, access, and owner-boundary metadata is not enough for full
  coverage.
- `self-awareness collect/events` now requires normalized signal-fabric depth on
  every event. A present event with only resource/context/space fields is not
  enough for full coverage.
- `self-awareness export` now requires a manifest and artifact list with hashes
  and schema checks. A bundle that only reports missing-count zero is not enough
  for portable proof.
- `self-awareness capabilities` and `self-awareness investigate` now require a
  concrete warm-E2B resident-worker detail. A present `running` status without
  health, monitor, candidate, eval, and policy fields is not enough for full
  coverage.
- `self-awareness capabilities` now requires concrete AI multimodal detail. A
  present modality id without source-model, device, profile/eval, model-root,
  and non-promotion evidence is not enough for full coverage.
- `self-awareness capabilities` now requires concrete LLM escalation detail. A
  present ready profile list without sourceful E4B review state, Qwen lazy-load
  route detail, resource/mode gate status, and non-action policy is not enough
  for full coverage.
- `self-awareness cycle` makes the from-zero end-to-end proof a first-class
  artifact with open stack-owned requirements represented as blockers, not
  hidden host failures.
- `self-awareness stack-closure-dossier` gives stack owners one ordered closure
  packet instead of forcing them to manually join requirements, probes, brief,
  and export artifacts.
- `self-awareness stack-closure-dossier` now preserves closure impact: reverse
  unblocks edges identify which open stack-owned requirements become downstream
  of a root blocker.
- `self-awareness stack-closure-dossier` now preserves coverage impact so stack
  owners can see which self-awareness planes and AI-OS organs remain incomplete
  behind each open stack-owned blocker.
- `self-awareness brief`, bounded context, investigation, and replay now
  preserve the same coverage impact, so the resident/operator reasoning loop
  cannot flatten stack-owned blockers back into generic handoff rows.
- `stack-bridge validate` requires static bridge sync after route expansion.
- Native trace backend absence is visible as a stack-owned requirement.
- Grafana datasource inventory auth is visible as a stack-owned requirement.
- Postgres/Neo4j semantic inventory is visible as a stack-owned requirement
  until the stack exposes a read-only route.
- Native `langchain-api`/LangGraph checkpoint or trace inventory is visible as
  a stack-owned requirement until the stack exposes a bounded endpoint.
- Warm-E2B/gemma4 can participate in investigation as a monitored worker, but
  its conclusions remain candidates backed by cited evidence.
- Reaction and response routes remain owner-gated and non-automatic.

## Boundaries

- This decision does not authorize writes to `abyss-stack`.
- This decision does not install Tempo or modify Grafana datasource auth.
- This decision does not add read credentials, endpoints, or schemas to
  Postgres, Neo4j, `rag-api`, `route-api`, or `langchain-api`.
- This decision does not make the fallback graph a stack runtime.
- This decision does not make warm-E2B output host truth.
- This decision does not authorize auto-remediation.

## Review Log

- 2026-06-04: Initial record.
- 2026-06-04: Reviewed after resident-stack-organ expansion. The decision
  still applies; current source behavior now includes active stack database/API
  surfaces, AI modality coverage, warm-E2B resident evidence, RAG/nervous
  gates, and governed response routing while preserving the no-stack-mutation
  boundary.
- 2026-06-04: Reviewed after failure-matrix expansion. The decision still
  applies; negative-path coverage is now a first-class bridge artifact for
  stack-owned gaps and machine-owned guard failures.
- 2026-06-04: Reviewed after E2E cycle expansion. The decision still applies;
  the full self-awareness loop now has a first-class cycle artifact while
  preserving the no-stack-mutation boundary.
- 2026-06-04: Reviewed after requirements API expansion. The decision still
  applies; stack-owned blockers now have a first-class machine-readable handoff
  with acceptance checks.
- 2026-06-04: Reviewed after contract-test expansion. The decision still
  applies; deterministic quick tests now cover self-awareness event schema,
  redaction, correlation, bounded query plans, requirements handoff identity,
  failure-matrix negative paths, and read-only CLI envelopes.
- 2026-06-04: Reviewed after live read-only test expansion. The decision still
  applies; live tests now prove current stack observability, stack-owned
  requirements handoff, non-mutating E2E cycle policy, and bounded export
  coverage against the running host/stack evidence.
- 2026-06-05: Reviewed after stack handoff causal-episode expansion. The
  decision still applies; open stack-owned blockers now flow from time-space
  overlay into conservative causal episodes, alert candidates, reactions, and
  responses with stack-owner runbook/verifier evidence and no-stack-mutation
  policy.
- 2026-06-05: Reviewed after stack handoff closure-readiness expansion. The
  decision still applies; open stack-owned blockers now carry fulfilled/missing
  check packets, dependency requirement ids, closure evidence needs, verifier
  commands, and no-stack-mutation policy through probes, brief/time-space
  overlays, and portable export.
- 2026-06-05: Reviewed after closure-readiness replay expansion. The decision
  still applies; investigation, replay, and cycle now preserve the same
  readiness packets as first-class checkpoint/replay evidence before the cycle
  can claim covered status.
- 2026-06-05: Reviewed after bounded context-packet expansion. The decision
  still applies; `context/latest.json` now provides a resident/operator bounded
  packet over memory-space, stack handoff, resident worker, governance gates,
  escalation gate state, read-only tools, and evidence refs without raw private
  content or stack mutation.
- 2026-06-04: Reviewed after stack handoff acceptance-contract expansion. The
  decision still applies; stack-owned blockers now carry machine-checkable
  closure probes and verifier commands, so future stack work can close them
  with evidence instead of a textual promise.
- 2026-06-04: Reviewed after requirement-probes verifier expansion. The
  decision still applies; every current stack-owned handoff acceptance
  contract now has a read-only machine verifier route with open/closed status,
  evidence refs, secret checks, and no-stack-mutation checks.
- 2026-06-05: Reviewed after stack-runbook candidate expansion. The decision
  still applies; each current stack-owned requirement probe now includes a
  handoff-only runbook candidate with risk, blast radius, rollback, acceptance
  steps, and evidence refs.
- 2026-06-05: Reviewed after governance-gate detail expansion. The decision
  still applies; `host.governance-gates` now exposes concrete memory,
  resource, and mode readiness with non-mutating policy before model/action
  escalation.
- 2026-06-05: Reviewed after export-manifest expansion. The decision still
  applies; the portable export now indexes each latest artifact with schema,
  history path, hash, evidence ref, and owner-boundary policy.
- 2026-06-05: Reviewed after resident-worker detail expansion. The decision
  still applies; warm-E2B now exposes serving health, monitor timers,
  resource/thermal posture, candidate queues, heartbeat evals, and non-action
  policy in capabilities and investigation state.
- 2026-06-05: Reviewed after AI multimodal detail expansion. The decision
  still applies; STT, embeddings, LLM text, TTS, and NPU readiness now exposes
  concrete source-model, device, profile/eval, stack model-root, host cache,
  and non-promotion policy evidence.
- 2026-06-05: Reviewed after LLM escalation detail expansion. The decision
  still applies; E4B workhorse and Qwen3.6 lazy-load escalation now expose
  review-only evidence, preflight/model-execution gates, route commands, cache
  boundaries, and non-action policy.
- 2026-06-05: Reviewed after stack handoff probe detail expansion. The decision
  still applies; open stack-owned probes now preserve closure probe contracts,
  verifier steps, closure semantics, current evidence, and handoff-only runbook
  candidates in the probe rows themselves.
- 2026-06-05: Reviewed after capability-matrix-depth expansion. The decision
  still applies; every capability row now preserves endpoint/artifact evidence
  routes, schemas, freshness, history, read-only access, and owner-boundary
  metadata instead of exposing only id/status/detail.
- 2026-06-05: Reviewed after signal-fabric-depth expansion. The decision still
  applies; every observation event now preserves actor, entity, temporal,
  spatial, context-link, source-query, evidence-route, label-policy, and
  non-mutating policy metadata.
- 2026-06-05: Reviewed after memory-space-depth expansion. The decision still
  applies; context, spatial graph, and query now expose bounded RAG packets,
  freshness gates, semantic backend state, and no-stack-mutation policy for
  memory/space reasoning.
- 2026-06-05: Reviewed after resident-cognitive-depth expansion. The decision
  still applies; investigations now expose a resident cognitive packet with
  bounded context, read-only tools, hypothesis tests, contradiction notes,
  evidence-cited summary, and gated escalation state.
- 2026-06-05: Reviewed after LangGraph loop-depth expansion. The decision still
  applies; investigation/replay now preserve the full request/validate/record/
  brief node order with resume metadata, conclusion diff, failure recovery, and
  human approval before any mutation.
- 2026-06-05: Reviewed after response-layer-depth expansion. The decision still
  applies; validated self-awareness episodes now preserve lineage,
  investigation/replay evidence, risk, blast radius, rollback, and runbook
  candidates through reactions and responses without authorizing execution.
- 2026-06-05: Reviewed after Grafana datasource handoff-depth expansion. The
  decision still applies; self-awareness now treats Grafana health/version and
  inferred datasource candidates as consumed stack evidence while keeping
  authoritative datasource inventory, read-only auth, and redacted export shape
  as stack-owned blockers.
- 2026-06-05: Reviewed after trace/OTel handoff-depth expansion. The decision
  still applies; self-awareness now treats Prometheus/Alloy/Loki pipeline
  evidence and bounded traceparent LogQL queryability as consumed stack
  evidence while keeping Tempo-compatible ready/search and span/log/metric join
  support as stack-owned blockers.
- 2026-06-05: Reviewed after live LangChain/LangGraph observability-depth
  expansion. The decision still applies; self-awareness now treats
  `langchain-api` health, OpenAPI, runtime routes, federated run, embeddings,
  OVMS metadata, and request schema names on port 5403 as consumed stack
  evidence while keeping thread/checkpoint/trace inventory and trace-backend
  coupling as stack-owned blockers.
- 2026-06-05: Reviewed after database/graph/RAG route-depth expansion. The
  decision still applies; self-awareness now treats route/RAG/Postgres/Neo4j
  readiness and bounded inventory-route metadata as consumed stack evidence
  while keeping schemas, labels, relationships, and freshness as stack-owned
  inventory requirements.
- 2026-06-05: Reviewed after export stack-handoff-depth expansion. The decision
  still applies; export now carries a one-file stack-owner handoff summary with
  open requirements, blockers, current state, runbooks, verifier steps, artifact
  refs, and non-mutating/no-secret/no-action policy.
- 2026-06-05: Reviewed after brief stack-handoff action-map expansion. The
  decision still applies; brief now surfaces the stack-owner handoff as a
  prioritized action map with safe next action, blocker keys, runbooks, verifier
  commands, evidence refs, and no automatic execution.
- 2026-06-05: Reviewed after investigation stack-handoff action-map expansion.
  The decision still applies; investigation/replay now preserve the prioritized
  stack-owner action map through request-more-evidence, brief candidate, top-level
  payload, and semantic conclusion with blockers, runbooks, verifier commands,
  evidence refs, and no stack mutation.
- 2026-06-05: Reviewed after stack handoff time-space overlay expansion. The
  decision still applies; timeline and spatial graph now project open
  stack-owned blockers into markers, requirement/action/runbook nodes, and
  affected-service edges without mutating `abyss-stack`.
- 2026-06-05: Reviewed after stack-closure dossier expansion. The decision still
  applies; open stack-owned blockers now have one ordered closure packet joining
  requirements, probes, readiness, dependency graph, runbooks, verifiers,
  evidence refs, and no-stack-mutation policy.
- 2026-06-05: Reviewed after stack-closure impact expansion. The decision still
  applies; the closure dossier now preserves reverse unblocks edges and
  per-entry closure impact without mutating `abyss-stack`.
- 2026-06-05: Reviewed after stack-coverage impact expansion. The decision still
  applies; every stack-closure dossier entry now carries coverage-plane and
  AI-OS organ impact without mutating `abyss-stack`.
- 2026-06-05: Reviewed after coverage-impact propagation into brief/context/
  investigate/replay. The decision still applies; propagation is machine-owned,
  read-only, and does not mutate `abyss-stack`.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_ETC}}/commands.md`
- `{{ABYSS_MACHINE_ETC}}/SELF-AWARENESS.md`
- `{{ABYSS_MACHINE_STATE}}/self-awareness/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/stack-bridge/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/changes/active/self-awareness-stack-coverage-impact-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/active/self-awareness-coverage-impact-propagation-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/active/self-awareness-stack-closure-impact-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/active/self-awareness-stack-closure-dossier-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-investigation-stack-handoff-action-map-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-time-space-overlay-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-full-coverage-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-resident-stack-organs-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-failure-matrix-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-e2e-cycle-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-requirements-api-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-handoff-id-alias-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-contract-tests-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-live-readonly-tests-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-acceptance-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-requirement-probes-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-runbooks-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-governance-gates-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-export-manifest-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-resident-worker-detail-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-ai-multimodal-detail-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-llm-escalation-detail-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-probe-detail-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-capability-matrix-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-signal-fabric-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-memory-space-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-resident-cognitive-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-langgraph-loop-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-response-layer-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-live-langchain-handoff-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-database-graph-rag-route-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-langchain-langgraph-observability-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-trace-otel-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-grafana-datasource-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-export-stack-handoff-depth-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-brief-stack-handoff-action-map-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-causal-episodes-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-closure-readiness-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-stack-handoff-readiness-replay-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-bounded-context-packet-20260605`
- `{{ABYSS_MACHINE_SRV}}/tests/contract/test_self_awareness_contracts.py`
- `{{ABYSS_MACHINE_SRV}}/tests/live/test_self_awareness_live_readonly.py`

## Validation

- `PYTHONPYCACHEPREFIX={{ABYSS_MACHINE_SRV}}/tmp/pycache python3 -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine self-awareness requirements --json`
- `abyss-machine self-awareness requirement-probes --json`
- `abyss-machine self-awareness failure-matrix --json`
- `abyss-machine self-awareness investigate --query TEXT --json`
- `abyss-machine self-awareness replay --thread-id THREAD_ID --json`
- `abyss-machine self-awareness cycle --json`
- `abyss-machine self-awareness probe --json`
- `abyss-machine self-awareness validate --json`
- `pytest -q {{ABYSS_MACHINE_SRV}}/tests/contract/test_self_awareness_contracts.py`
- `pytest -q {{ABYSS_MACHINE_SRV}}/tests/live/test_self_awareness_live_readonly.py`
- `abyss-machine ai validate --json`
- `abyss-machine rag validate --json`
- `abyss-machine nervous validate --json`
- `abyss-machine stack-bridge sync-static --dry-run --json`
- `abyss-machine stack-bridge validate --json`
- `abyss-machine test quick --json`
- `pytest -q {{ABYSS_MACHINE_SRV}}/tests/contract/test_self_awareness_contracts.py`
- `pytest -q {{ABYSS_MACHINE_SRV}}/tests/live/test_self_awareness_live_readonly.py`
- `abyss-machine test live --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`

## Follow-up Route

When the operator authorizes privileged `/etc` writes, run
`abyss-machine stack-bridge sync-static --json` and re-run stack-bridge
validation. Stack-owned capability gaps must be closed in `abyss-stack`, then
refreshed here through `abyss-machine self-awareness capabilities --json`.
