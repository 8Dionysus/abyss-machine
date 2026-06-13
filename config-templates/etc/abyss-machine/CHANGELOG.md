# Abyss Machine Changelog

This changelog records curated host-layer milestones for `abyss-machine`.

It is intentionally human-first and sparse. Canonical host mutation history
lives in `{{ABYSS_MACHINE_STATE}}/changes/`; use the change ledger for exact
records, validation notes, rollback notes, and closeout evidence.

Do not record every probe, sample, generated refresh, or local experiment here.

## [Unreleased]

### Added

- `abyss-machine self-awareness` full-stack resident coverage over active
  stack services, local AI modalities, warm-E2B/gemma4 resident evidence,
  RAG/memory, nervous freshness gates, governed reactions/responses, and
  stack-owned requirements API, failure-matrix, and E2E cycle reporting
  without mutating `abyss-stack`.
- Deterministic self-awareness contract tests for observation event schema,
  redaction, correlation, bounded query plans, requirements handoff identity,
  failure-matrix negative paths, and read-only CLI envelopes.
- Live read-only self-awareness tests proving current stack observability,
  requirements handoff, E2E cycle policy, and export bundle coverage without
  mutating `abyss-stack`.
- Machine-checkable acceptance contracts for stack-owned self-awareness
  handoff items, including closure probes, redaction rules, boundedness
  expectations, verifier commands, and no-stack-mutation guardrails.
- `abyss-machine self-awareness requirement-probes --json` as the read-only
  acceptance verifier that evaluates current stack-owned handoff contracts
  without mutating `abyss-stack` and keeps open gaps visible as blockers.
- Stack-owner runbook candidates inside requirement-probes, with risk, blast
  radius, rollback, acceptance steps, evidence refs, and explicit handoff-only
  policy for every current stack-owned blocker.
- Capability-matrix depth for every self-awareness capability row, preserving
  endpoint or artifact routes, schemas, freshness, history, auth-safe read-only
  access, evidence-route counts, and owner-boundary policy.
- Signal-fabric depth for every self-awareness observation event, preserving
  actor/entity/time/space/context/source-query/evidence-route/label-policy
  metadata and read-only non-mutating policy.
- Memory-space overlay depth for self-awareness context, spatial graph, and
  query, preserving bounded RAG packets, maps/graph/memory/nervous freshness
  gates, Postgres/Neo4j/RAG/embeddings backend state, evidence refs, and
  raw-evidence-is-not-truth/no-stack-mutation policy.
- Bounded self-awareness context packet in `context/latest.json`, joining
  compact correlation context, memory-space, stack handoff, warm-E2B resident
  worker, governance gates, escalation state, read-only tools, evidence refs,
  redaction bounds, and no-action/no-stack-mutation policy for resident/operator
  reasoning.
- Concrete self-awareness governance gate detail for memory, resource, and
  mode readiness before model escalation or response routing.
- Structured self-awareness export manifest with per-artifact schemas, history
  paths, hashes, evidence refs, owner boundary, and non-mutating policy.
- Concrete AI multimodal self-awareness detail for STT, embeddings, LLM text,
  TTS, NPU, stack model roots, OpenVINO devices, profile/eval evidence, and
  non-promotion policy.
- Concrete warm-E2B resident-worker detail in self-awareness capabilities and
  investigations, including stack-owned serving health, monitor timers,
  resource/thermal posture, candidate queues, heartbeat evals, and non-action
  policy.
- Resident cognitive-worker depth for self-awareness investigations, including
  bounded context packets, read-only tool inventory, hypothesis tests,
  contradiction notes, evidence-cited summary, and resource/mode-gated
  E4B/Qwen escalation state without model execution or stack mutation.
- Full LangGraph-style investigation loop depth for `self-awareness
  investigate` and `replay`, including request-more-evidence, evidence
  validation, artifact-record, brief/reaction candidate, resume metadata,
  conclusion diff, failure recovery, and human approval before mutation.
- Stack coverage-impact propagation through the reasoning loop: stack-owned
  handoff blockers now carry AI-OS organ, blocked self-awareness planes,
  affected surfaces, closure value, proof commands, and no-stack-mutation policy
  in `brief`, bounded `context`, `investigate`, and `replay`, not only in the
  stack-closure dossier.
- Stack compat-contract depth for self-awareness handoff: each open
  stack-owned blocker now carries exact route/export options, required fields,
  redaction/boundedness rules, dependency order, coverage impact, post-close
  machine verifiers, and no-stack-mutation policy in requirements handoff and
  `stack-closure-dossier` top-level `compat_contracts`.
- From-zero cycle proof depth: `self-awareness cycle` now carries
  `from_zero_proof` rows for the artifact-level E2E path, including
  command/path/schema/hash/freshness/evidence refs and chain obligations for
  capability inventory, signal fabric, timeline, graph, context, episodes,
  alerts, warm-E2B/RAG/nervous gates, investigation, replay, responses, and
  export.
- Machine bridge proof depth for `self-awareness cycle`: heartbeat, memory,
  mode, resource, process snapshot, container health, thermal plan, cooling,
  typing events/validation, nervous brief, reactions, and responses are now
  explicit bridge-proof rows and a `machine_bridges` chain obligation.
- Self-awareness response-layer depth across `alerts`, `reactions`, and
  `responses`, preserving validated episode lineage, investigation/replay
  evidence, risk, blast radius, rollback, runbook candidate, and non-mutating
  owner gates through the response route.
- Live Grafana datasource handoff depth in self-awareness capabilities and
  requirement-probes: Grafana health/version plus inferred Prometheus, Loki,
  Alertmanager, and Tempo datasource candidates are now consumed as bounded
  evidence, while datasource/search/settings inventory routes remain
  auth-denied and require a stack-owned read-only token or bounded export.
- Live trace/OTel handoff depth in self-awareness capabilities and
  requirement-probes: Prometheus/Alloy/Loki pipeline evidence and bounded
  traceparent LogQL queryability are now consumed as stack evidence, while the
  remaining blocker is specifically Tempo-compatible ready/search routes and
  span/log/metric join support rather than generic trace absence.
- Live `langchain-api` handoff depth in self-awareness capabilities and
  requirement-probes: health, bounded OpenAPI, `/run`, `/run/federated`,
  `/embeddings`, OVMS provider/auth metadata, and request schema names on
  `127.0.0.1:5403` are now consumed as stack evidence, while the remaining
  blocker is specifically LangGraph thread/checkpoint/trace inventory plus
  trace-backend coupling rather than generic API absence.
- Live database/graph/RAG route depth in self-awareness capabilities and
  requirement-probes: `route-api` health/OpenAPI, `rag-api` health/OpenAPI plus
  collections/sources/agentic-graph shape, Postgres readiness, and Neo4j root
  metadata are now consumed as bounded stack evidence while schema/label/
  relationship/freshness inventory remains a stack-owned blocker.
- Portable self-awareness export handoff depth: `export/latest.json` now carries
  top-level `requirements` and `stack_handoff` summaries with open stack-owned
  blocker ids, closure checks, current state, runbook candidates, acceptance
  verifier steps, artifact refs, and no-stack-mutation/no-secret/no-action
  policy, so the stack owner can start from one bundle.
- Operator-facing self-awareness brief handoff depth: `brief/latest.json` now
  carries `stack_handoff_action_map` with prioritized open stack-owned blockers,
  safe next action, closure blocker keys, current state, runbook candidates,
  verifier commands, evidence refs, and handoff-only no-execution policy.
- Investigation stack-handoff action-map depth: `investigate/latest.json` now
  carries the same prioritized stack-owner action map through
  `request_more_evidence`, `brief_reaction_candidate`, top-level investigation
  payload, and semantic conclusion, with closure blockers, runbooks, verifier
  commands, safe next action, and handoff-only no-stack-mutation policy.
- Stack handoff time-space overlay: `timeline/latest.json` and
  `spatial-graph/latest.json` now expose open stack-owned blockers as
  evidence-cited temporal markers and spatial nodes/edges tied to affected
  services, priority, runbooks, verifier commands, safe next action, and
  no-stack-mutation policy.
- Stack handoff causal episodes: `episodes/latest.json` now emits
  conservative `stack_handoff_blocker` handoff candidates for open stack-owned
  blockers, and `alerts/latest.json` routes them into non-executing
  self-awareness candidates with response contracts preserving requirement ids,
  stack-owner runbooks, verifier commands, evidence refs, and no-stack-mutation
  policy.
- Concrete LLM escalation detail for E4B workhorse and Qwen3.6 lazy-load
  routes, including sourceful review-only workhorse pack/review/validate state,
  preflight/model-execution gate status, Qwen context/cpuset/cache commands,
  and non-stack-mutating policy.
- Self-contained stack handoff probe rows for open self-awareness requirements,
  explicitly marking `stack_handoff: true` and preserving machine closure probes,
  acceptance verifier steps, closure semantics, live current state, evidence refs,
  and handoff-only runbook
  candidates for each stack-owned read-route gap.
- Stack handoff closure-readiness packets inside requirement-probes, brief/
  time-space overlays, and portable export, preserving fulfilled checks,
  missing checks, dependency requirement ids, evidence still needed for closure,
  verifier commands, and no-stack-mutation policy for each open stack-owned
  blocker.
- Stack handoff closure-readiness replay depth: `investigate`, `replay`, and
  `cycle` now preserve ordered next actions, fulfilled/missing checks, blocker
  keys, dependency edges, verifier commands, safe next action, evidence refs,
  and no-execution/no-stack-mutation policy as a first-class replay contract
  before the E2E cycle can claim covered status.
- `abyss-machine self-awareness stack-closure-dossier --json` as the ordered
  stack-owner closure packet joining open requirements, live probes,
  closure-readiness, dependency graph, runbook candidates, verifier commands,
  artifact refs, and no-execution/no-stack-mutation/no-secret policy.
- Stack-closure dossier impact depth: dependency graph now includes reverse
  unblocks edges and each dossier entry carries `closure_impact`, so stack
  owners can see which open blockers are downstream of a requirement.
- Stack-closure dossier coverage-impact depth: each open stack-owned blocker now
  names the self-awareness planes, AI-OS organ, affected stack/machine surfaces,
  closure value, and proof commands it blocks.
- `abyss-machine rag trace --query TEXT --json` as the first read-only
  `maps -> evidence -> trace -> eval` loop over machine atlas context packets,
  bounded evidence summaries, deterministic answer traces, and local trace
  evals.
- `abyss-machine rag refresh --query TEXT --json` and
  `abyss-machine-context-refresh.timer` as the automatic generated-context
  refresh pass for maps, maps validation, RAG trace/eval, and RAG validation.
- `abyss-machine memory residency --json` as a facts-only cgroup residency
  observation route for protected TTS, dictation, and resident LLM services,
  including `MemoryLow`/`MemoryHigh`/`MemorySwapMax`, cgroup swap, sampled
  PSS/swap, memory events/stat, PSI, zram headroom, and runtime-only pilot
  candidates.
- `ROADMAP.md` as the host-wide direction surface for machine routing, adaptive
  thermal/memory/resource posture, resident agents, nervous retrieval, storage,
  and future stack bridge growth.
- `decisions/` as the durable rationale lane for structural host-layer choices
  where future agents need the "why" behind the current source surfaces.
- curated milestone `CHANGELOG.md` route that points detailed chronology back
  to the host change ledger instead of duplicating it.

### Changed

- memory routing now distinguishes high zram percentage from real low-PSI
  headroom, with a first persisted zram/page-cluster policy for active games
  plus resident agents.
- memory residency now treats high protected-service swap as a measure/warm/protect
  signal rather than a stop, disable, or cleanup recommendation.
- mode validation now treats active GameMode/game-guard performance boost as
  a protected external workload state instead of generic power-profile drift.
- documentation closeout now includes a decision review and roadmap/changelog
  route review when host-wide direction, durable rationale, or milestone
  contour changes.
- docs audit, topology, and agent mesh validation now know about the roadmap,
  decision lane, and curated changelog surfaces.

### Ledger

Detailed records:

- `{{ABYSS_MACHINE_STATE}}/changes/closed/docs-agent-mesh-20260513`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/srv-large-root-design-20260513`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/roadmap-decisions-route-20260513`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/memory-headroom-zram-routing-20260513`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/machine-rag-trace-loop-20260526`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/machine-context-refresh-automation-20260526`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-resident-stack-organs-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-failure-matrix-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-e2e-cycle-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-requirements-api-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/mode-external-boost-guard-20260604`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-contract-tests-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-live-readonly-tests-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/self-awareness-requirement-probes-20260605`
- `{{ABYSS_MACHINE_STATE}}/changes/active/memory-residency-orchestration-20260514`

## Notes

- `CHANGELOG.md` keeps milestone contour.
- `{{ABYSS_MACHINE_STATE}}/changes/` keeps host mutation history.
- `ROADMAP.md` keeps current direction and future triggers.
- `decisions/` explains durable choices; current source surfaces define what.
