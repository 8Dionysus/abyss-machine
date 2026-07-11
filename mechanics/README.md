# abyss-machine Mechanics Atlas

This atlas routes durable host-machine moves.

| Package | Host question | Start here |
|---|---|---|
| `host-lifecycle` | How is the host layer installed, checked, updated, and repaired? | `scripts/abyss-machine-bootstrap`, `docs/install/`, `docs/operations/` |
| `config-projection` | How do public templates become local `/etc/abyss-machine` without secrets? | `config-templates/`, `env/`, `schemas/` |
| `host-facts` | How are machine facts gathered and exposed without publishing private state? | `docs/host/`, `src/abyss_machine/cli.py` |
| `storage-routing` | How are `/srv`, caches, runtimes, backups, and temp roots kept bounded? | `tools/abyss-storage-reclaim-audit`, `docs/host/` |
| `typing-intake` | How does typed activity become opt-in, redacted evidence? | `tools/typing/`, typing profile units |
| `nervous-local` | How does local nervous intake become privacy-gated memory evidence? | `tools/nervous/`, nervous profile units |
| `local-ai-runtime` | How are host-managed local AI helpers kept outside stack ownership? | `tools/ai/`, ai-local profile units |
| `diagnostic-spine` | How do doctor probes and validators expose repairable host posture? | `docs/validation/`, bootstrap doctor |
| `self-awareness` | How do host readmodels become bounded awareness/status evidence without mutating the stack? | `docs/host/LIVE_ADAPTERS.md`, `docs/host/SUBSYSTEM_COMMANDS.md` |

The atlas does not create new host authority. It makes existing movements
visible and gives future implementation a place to land.

## Live Adapter Route

Live adapter hardening is tracked from [docs/host/LIVE_ADAPTERS.md](../docs/host/LIVE_ADAPTERS.md).
Use these mechanic owners for the next extraction slices:

- `typing-intake`: typing latest/history persistence, Codex session-tail
  filesystem reads and semantic ingest planning, browser/native-host ingest
  planning/transport/response envelopes, temporary Firefox WebExtension and
  browser-context/browser AT-SPI/focused-browser/browser-privacy selftest runtime, AT-SPI
  focused/text-event/generic GUI semantic plans, saved-text scan filesystem
  mechanics, native-host stdio binding, and remaining `pyatspi` runtime
  adapters.
- `nervous-local`: nervous source capture, privacy state, local JSONL readers,
  browser-content store/dedupe/latest write adapter, AT-SPI browser-content
  capture runtime adapter, BiDi/WebSocket browser-content capture runtime
  adapter, Firefox browser-history capture runtime adapter, derived
  event/episode JSONL/latest write adapters, synthesis/eval local read/write
  adapter, screenshot live capture adapter, clipboard live read adapter, lexical
  SQLite/FTS lifecycle, semantic sidecar lifecycle/execution, semantic-build
  window execution, and semantic-maintain orchestration, rerank execution,
  retention contracts plus filesystem/apply adapter, top-level status readmodel
  assembly/write routing, capture-status readmodel filesystem/latest probes,
  and derived memory evidence.
- `local-ai-runtime`: host-managed AI model/runtime subprocesses, resource
  gates, token/STT/TTS execution, dictation transcription/recording/audio
  inspection/journal/insertion/calibration/profile/docs/status/validation/replacements,
  runtime-path, lock, postprocess, and notification adapters, and cache/runtime
  evidence.
- `diagnostic-spine`: doctor, validation, repair, and freshness probes that
  prove the host layer is healthy without publishing private state.
- `self-awareness`: latest surface specs, fakeable latest load dispatch,
  latest artifact-ref filesystem ports, artifact evidence-ref stat projection,
  freshness-gate readmodel assembly, event dedupe/correlation-index/checkpoint-
  observation contracts with explicit clock/host/path inputs, complete
  capabilities stack/container/
  HTTP/AI/RAG/nervous/latest-read orchestration, capability and requirement
  readmodel assembly, ordered requirements/capabilities persistence, complete
  status latest/body/open-potential/open-requirement readmodel orchestration,
  read-only systemd timer/service discovery,
  state normalization, and observation-event orchestration through fakeable
  ports, ordered collect input acquisition across latest reads, subsystem
  refreshes, optional network queries, time windows, and scheduler/service
  events, collect event/fabric/readmodel assembly through supplied contract
  ports and explicit host-path binding, ordered collect events/collect/index
  persistence through shared atomic/locked-append filesystem adapters, replay
  latest-read/checkpoint-chain validation/readmodel persistence through
  purpose-shaped ports, cycle latest-read/bridge-document dispatch,
  validation latest-spec selection, bounded status latest summaries,
  body-closure status document builders, status open-potential/open-requirement
  row builders, resource preflight guard decisions, bounded HTTP status probe
  ports, working-stack endpoint/TCP/container runtime probes,
  TTS smoke artifact evidence/probe projection, working-stack source inventory
  projections, working-stack inventory assembly/readmodel, working-stack
  movement/event assembly, working-stack usage-gap episode builders,
  working-stack link-integrity matrix assembly plus match/freshness
  predicates, autolink row-state/completion/episode-coverage, autolink
  document builders,
  activation-entry builders/completion predicates, activation-dossier document
  builders, activation-smoke and stack-organ-use
  completion/compact/refresh predicates, activation-gap and stack-requirement
  handoff route builders/completion predicates, activation synthetic-scenario,
  closure-acceptance, activation synthetic-proof, and export-overlay
  builders/completion predicates, working-stack model/tool bridge policy, probe/cycle
  resource-denial documents, probe result/movement-smoke document assembly,
  cycle artifact step manifest/order/nonblocking bridge policy, cycle artifact
  evidence snapshots, cycle open-requirement/issue guard input assembly, cycle
  chain assembly through supplied completion predicates, cycle post-export chain
  updates, cycle stack-handoff summary document assembly, and cycle
  partial/building/final result document assembly, complete probe preflight,
  traced request and synthetic movement, refresh-chain, validation, and
  two-stage persistence orchestration, complete investigation
  input/refresh ordering, episode selection, checkpoint-graph/evidence/
  conclusion assembly and latest/history persistence, and complete replay
  orchestration, plus complete export latest-read/refresh/artifact-manifest/
  handoff/persistence orchestration through fakeable runtime, refresh,
  contract, and persistence ports live in `self_awareness_adapters`; CLI binds
  concrete paths, live functions, contract builders, and write intent. Complete cycle
  preflight/probe/double-investigate-replay/artifact/proof/two-stage
  persistence orchestration also lives in `self_awareness_adapters`;
  `self_awareness_completion_contracts` owns completion readiness path/state
  inputs, autolink/owner-boundary predicates, gate/blocker assembly, and
  deterministic action priority/ranking, stack-requirement and working-stack
  usage-gap drilldown packets, and deterministic completion route-map
  assembly; `self_awareness_completion_graph_contracts` owns explicit latest
  document paths plus action, stack-organ, machine-bridge, event, document,
  and route-binding map assembly with fail-closed mapping readiness, plus
  deterministic completion route-packet indexing with graph joins and
  no-execution handoff envelopes;
  `self_awareness_completion_document_contracts` owns completion backlog and
  final audit document assembly, compact coverage projection, and degraded/
  incomplete/watch/complete status transitions;
  `self_awareness_adapters` owns ordered completion-audit status/latest/
  preflight/artifact-ref input acquisition, contract assembly, and optional
  latest/history persistence through explicit ports. It also owns validation
  optional-refresh order, document/root/latest/history intake, and final
  latest/history persistence;
  `self_awareness_validation_contracts` owns conditional validation repair
  decisions, the full cross-document check matrix, and final validate document
  assembly through explicit repair/contract ports without concrete live IO;
  `self_awareness_export_handoff_contracts` owns public artifact-ref projection
  plus deterministic requirements, closure-order, dependency, coverage,
  verifier, activation, and stack-owner handoff assembly without live IO or
  stack mutation; `self_awareness_causal_readmodel_contracts` owns timeline,
  spatial-graph, bounded-context, and causal-episode refresh/assembly/
  persistence pipelines through explicit runtime, refresh, contract, and
  latest/history ports; `self_awareness_stack_closure_contracts` owns
  requirement-probes and stack-closure-dossier refresh/assembly/persistence,
  dependency and acceptance matrices, ordered artifact refs, and stack-owner
  handoff through explicit ports; `self_awareness_stack_probe_adapters` owns
  bounded HTTP/TCP stack probes, capability artifact metadata, OpenAPI/name
  projection, Grafana datasource redaction, and optional external-evidence
  intake through fakeable runtime ports;
  `self_awareness_failure_matrix_contracts` owns ordered bounded latest intake,
  negative-path/requirement guard assembly, completeness checks, and optional
  persistence through fakeable ports;
  `self_awareness_causal_overlay_contracts` owns memory-space and stack-handoff
  time-space overlay assembly through explicit runtime, refresh, contract,
  path, and config ports without host IO or stack mutation;
  `self_awareness_query_correlation_contracts` owns bounded query scoring and
  current-window correlation joins/SLO/baseline/provenance assembly through
  explicit runtime, refresh, contract, persistence, path, and config ports;
  `self_awareness_trace_context_contracts` owns bounded trace-link extraction,
  trace-backend fallback/readiness, ordered next-requirement routing,
  completion, and optional persistence through the same explicit port style;
  `self_awareness_body_trace_contracts` owns episode temporal/spatial/context/
  host-body projection, deterministic bounded lineage, and completion through
  explicit path, config, runtime, and contract ports;
  `self_awareness_response_contracts` owns common and episode-specific response
  assembly plus response/candidate/route depth predicates through explicit
  host paths, latest-loader, and dependent-contract ports;
  `self_awareness_alert_contracts` owns conditional alert intake/refresh,
  owner-gated candidate assembly, response/body-trace enrichment, depth
  accounting, and optional persistence through explicit ports;
  `self_awareness_brief_contracts` owns ordered brief intake, stack-handoff
  priority/action maps, referenced claims, health/degradation summaries, and
  optional persistence through explicit ports;
  `self_awareness_resident_worker_contracts` owns bounded resident health,
  serving, monitor, resource, candidate, eval, and non-authoritative cognitive-
  contract projection plus completion;
  `self_awareness_resident_cognitive_contracts` owns completion-route context,
  bounded cognitive packet/replay state preservation, completion predicates,
  and cycle overlay through explicit ports;
  `self_awareness_activation_smoke_contracts` owns activation-smoke latest/
  refresh/persistence orchestration and per-organ movement/use-packet summary
  assembly through explicit ports;
  `self_awareness_autolink_contracts` owns complete autolink latest intake,
  stale-input decisions, ordered dependency refresh, existing document-builder
  dispatch, and optional latest/history persistence through typed ports;
  `self_awareness_activation_contracts` owns stack-organ signal/state/movement,
  episode identity, activation row/use-packet assembly, and completion/compact/
  refresh contracts through typed paths, config, and dependent-contract ports;
  `self_awareness_lineage_contracts` owns artifact/spec maps, e2e and top-level
  lineage proof assembly, and completion through typed paths/config and
  artifact/filesystem runtime ports;
  `self_awareness_coverage_contracts` owns objective specs/planes and complete
  coverage-audit intake, refresh, stack-blocker/activation linkage, assembly,
  and persistence through typed runtime, refresh, and contract ports;
  `self_awareness_requirement_contracts` owns requirement acceptance,
  compatibility, negative controls, closure readiness, runbook, coverage
  impact, probe evaluation, readiness enrichment, and requirements persistence
  through typed path/config/runtime/refresh/contract ports;
  `self_awareness_cognitive_contracts` owns bounded freshness/trace/context,
  multimodal and LLM escalation detail, governance gates, investigation
  recovery, and working-stack gap handoff contracts through typed paths,
  policy config, and completion ports;
  `self_awareness_entity_context_contracts` owns fail-closed entity/event/
  document and completion-route-packet validation plus bounded response
  context selection through typed latest paths and loader;
  `self_awareness_cycle_proof_contracts` owns machine-bridge catalogs/proofs
  and from-zero chain/proof contracts through typed paths/config plus artifact-
  ref and stat ports. The final
  residual CLI-edge classification and family completion audit remain.
- `host-facts`: low-level process `/proc` snapshot collection, sanitized
  process container-health reads, and read-only desktop-compositor command/proc
  probes plus AT-SPI desktop hard-timeout capture now live in
  `process_adapters`; process thermal attribution/plan read-only orchestration
  also lives in `process_adapters`; memory orchestration target snapshots,
  local model HTTP probes, cgroup CPU sampling, live locks, narrow Podman
  restart/rerank unload execution, rehydrate polling, read-only memory
  pressure/process/cgroup collection, residency service snapshots, and hotpath
  probe document assembly/orchestration and hotpath TTS/STT/LLM execution
  wrappers plus memory-orchestrate safety policy live in `memory_adapters`; mode-state IO, `powerprofilesctl` get/set, recent GameMode
  journal probes, external profile-guard input collection, mode plan/status
  live input collection, and reconcile orchestration live in `mode_adapters`;
  cooling platform-profile, Lenovo fan-mode, RAPL-MMIO, package-throttle,
  kernel fan-error, thermal-zone/cooling-device sysfs sampling, trusted sensor
  projection, temperature summary/sample, sample-series ports, profile apply
  orchestration, guarded TFN1 write, fan-validate, fan-series orchestration, and
  RAPL smoothing decision/state orchestration live in `cooling_adapters`.
  Continue broader container orchestration and write-routing ports only as
  bounded public-safe adapter slices.
- `host-lifecycle`: bootstrap, install projection, source/install parity, and
  release/check gates for the portable public seed.
