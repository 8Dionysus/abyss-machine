# Validators

This directory is reserved for focused source-tree validators. The first
validation lane is documented in `docs/validation/VALIDATOR_TOPOLOGY.md`.

`path_policy.py` validates the shared install/root path contract that keeps
bootstrap, CLI imports, generated state roots, `/srv` storage planes, and
typing/nervous organs pointed at one policy source.

`first_run_installed_projection.py` validates the fresh-machine installed
projection. It applies bootstrap into isolated temporary roots, runs the
temp-installed CLI without source-checkout `PYTHONPATH`, compares critical
source and installed command surfaces, checks projected package modules and
public seed read models, proves typing/nervous config and unit skeletons are
present, and keeps profile activation dry-run/opt-in. The live installed CLI
comparison is advisory unless `--require-host-installed` is passed for host
closeout.

`validation_contracts.py` owns the shared validation summary, document envelope,
and generic subsystem validate/all envelope contracts used by CLI validators;
validators should remain route and portability checks, not hidden subsystem
product logic.
`artifact_bundles.py` owns artifact bundle/trust read models and the
`artifacts validate` document envelope; artifact checks, latest writes, and
command rendering remain CLI adapters in this command-glue slice.

`typing_nervous_policy.py` validates the first organ-specific policy split:
typing and nervous path/service constants plus typing paths/index document contracts remain CLI-compatible while deriving
captures, indexes, browser tooling, tmp/cache, and user-systemd paths from the
shared root contract.

`typing_nervous_refresh_logic.py` validates the pure refresh decision helpers
that classify soft resource gates, bounded recent-index debounce windows,
refresh assessment state, latest-status readmodel health, status resource-field
naming, nervous-processing readiness document and acceptance, index-attempt debounce plus final status
contexts, fact-state assembly, action-record
builders, and the final refresh document builder. The CLI must use
`abyss_machine.typing_nervous_refresh` for this logic instead of redefining it
in the monolith.
Typing saved-text/browser intake policy helpers, saved-text scan policy status,
saved-text recent-record validation, recent record policy/causal shape status,
causal project binding/resolution, causal interaction identity/context-anchor and URL/AI recipient helpers,
typing process project/dedupe/interaction/continuity/lane/context/recipient helpers, causal-context readmodel assembly, process readmodel assembly, and causal-awareness event/readmodel status,
capture-gate policy and decision documents, safe URL checks, recent browser-content context inference,
focused-browser selftest and browser-privacy record summaries, metadata
envelopes, Codex prompt hook/session-tail evidence summaries, prompt route
coverage assessment, typing coverage document assembly plus route-note/gap and status decisions, typing status, validate, and end-to-end proof document assembly,
browser selftest proof summary, browser context fallback status, browser AI
transcript selftest status and validation status, browser WebExtension selftest
and AT-SPI selftest validation status, generic GUI, focused-browser, and
browser-privacy selftest validation status,
browser input recency classification/readmodel assembly, status, and validation freshness, AT-SPI text-event
policy merge and heartbeat status, AT-SPI compact-history record and contract documents, session-tail latest-status contracts, title
fingerprints, and AI transcript cleanup/role contracts live in
`abyss_machine.typing_capture_contracts`. Codex prompt/session-tail text
extraction, user-message route recognition, context-envelope normalization,
near-line duplicate semantics, metadata/context ingest plans, and public-safe
event summaries live in `abyss_machine.typing_codex_semantics`; Codex
session-tail filesystem reads live in `abyss_machine.typing_nervous_adapters`.
Browser/WebExtension native-host ingest plans, AI transcript cleanup/metadata
plans, synthetic selftest documents, and native-host response envelopes live in
`abyss_machine.typing_browser_adapters`. AT-SPI focused-snapshot ingest/document
plans, text-event sample envelopes, metadata shaping, bounded browser-context
summaries, context identity/debounce helpers, typing-event summaries, and
generic GUI selftest documents live in `abyss_machine.typing_atspi_adapters`.
Saved-text scan filesystem limits, path walking, state continuity, decode
rejection, candidate/skip accounting, ingest kwargs, state entries, and
public-safe scan documents live in `abyss_machine.typing_saved_text_adapters`.
Policy file reads, framed native-host byte IO, live browser/WebExtension
probes, `pyatspi` access, listener registration, text reads, systemd status
reads, `typing_ingest`, latest/index writes, and event writes remain at the CLI
edge.

Nervous index JSONL source discovery/loading/hash rules,
source-record parsing/metadata, source-policy helpers, record/chunk/document
projection, build projection summary, SQLite/FTS store/count/run contracts,
build result/meta envelopes, search shaping, vacuum result envelopes, status/freshness envelopes,
bounded scan, and bounded/full validation document envelopes live in
`abyss_machine.nervous_index`. Shared typing/nervous secret-pattern and
high-entropy redaction contracts live in `abyss_machine.nervous_redaction`.
Typing/nervous source metadata envelopes, redacted text/URL payload contracts,
browser-content record/quality/dedupe/web-context contracts, source state merge,
effective source maps, catalog, lookup, and source-set contracts live in
`abyss_machine.nervous_sources`.
Nervous derived event/episode record shapes, classification/grouping,
build-envelope, and validation contracts live in `abyss_machine.nervous_events`.
Nervous synthesis period selection, candidate build orchestration,
path/write-result envelopes, markdown projection, validation, and deterministic
eval run execution-plan/run/validate envelopes live in
`abyss_machine.nervous_synthesis`. Nervous semantic schema,
status/freshness contract assembly, maintenance assessment, batch policy, build
command shaping, source chunk projection, semantic sidecar store/reuse/count
contracts, embedding subprocess payload/script/result contracts, and
vector/search shaping live in `abyss_machine.nervous_semantic`. Nervous
retention route specs, root/file candidate classification, retention policy,
plan/apply/validate result envelopes, and privacy-review route contracts live in
`abyss_machine.nervous_retention`; root scans, symlink-tail checks, unlink
execution, and latest/history writes remain at the CLI edge. Nervous screenshot
recurring-extension query policy and capture backend plan contracts live in
`abyss_machine.nervous_screenshot`; GNOME extension status probes, process/X11
risk probes, file writes, capture execution, artifact hashing, and fact writes
remain at the CLI edge. Nervous rerank profile/defaults, source-prior scoring,
machine-query caps, merge policy, hybrid result scoring, neural text shaping,
neural config normalization, guarded neural-score blending, and eval document
envelopes live in
`abyss_machine.nervous_rerank`; lexical/semantic source collection, semantic
maintenance assessment, OpenVINO scorer subprocess execution, and latest/history
writes remain at the CLI edge. Nervous recall refusal, mode normalization,
search execution-plan, evidence projection, summary counts, pack identity, and
retrieval-pack document contracts live in `abyss_machine.nervous_recall`;
lexical/hybrid search adapter calls and latest/history writes remain at the CLI edge.
Nervous brief scope/limit/cache keys, semantic-maintenance thresholds,
recent-episode compact projection, readiness/gap/next-action decisions, and
document envelope live in
`abyss_machine.nervous_brief`; live quality/status/privacy/capture/index/
semantic/synthesis/host read-model collection, episode JSONL reads, and latest/history writes remain
at the CLI edge. Nervous quality derived-refresh status, validation compaction,
check matrix, and audit document envelope live in
`abyss_machine.nervous_quality`; refresh execution, live validators/systemd/latest/redaction
input collection, latest/history writes, and command rendering remain at the
CLI edge. Nervous privacy
defaults, state merge/normalization, effective privacy, status, set-transition,
audit-record, and set-result contracts live in `abyss_machine.nervous_privacy`;
state file reads/writes, audit JSONL appends, and latest writes remain at the
CLI edge. Resource class/kind
normalization, gate decisions, systemd plan shape, systemd output parsing, and
launch argv contracts live in `abyss_machine.resource_planning`.
The CLI must adapt these modules instead of owning the subsystem contracts
directly.
AI CPU route selection, routed-heavy policy, thread/env hints, and route
contract assembly live in `abyss_machine.ai_cpu_routing`; live thermal/policy/
mode/battery collection remains at the CLI edge.
AI runtime env/cache defaults, resource-profile envelopes, model inventory classification/document shaping,
LLM paths/registry/validate/runtime/profile contract assembly, OpenVINO benchmark-plan/probe/eval command/result
envelopes, AI eval suite-policy/execution-plan/STT scoring/result envelopes, token-accounting privacy/
count/count-execution/profile/tokenizer-route/aoa-summary contracts, AI capabilities projection, AI policy
decision/gate, workload taxonomy/measurement extraction plus stats/refresh/status
routing, and AI paths/status/runtime/report read-model envelopes live in
`abyss_machine.ai_runtime_contracts`; live filesystem walks, package/runtime
discovery, tokenizer discovery, `.aoa` generated-summary reads, latest-input
collection, subprocess execution, resource sampling, and latest writes remain at
the CLI edge.
TTS profile/artifact/status decisions, policy-denial/error summaries, server
response/payload shaping, synth subprocess script/argv/result contracts,
synth/eval/compare envelopes, and success-index entries live in
`abyss_machine.ai_tts_contracts`; module probes, server/socket transport, audio
IO, subprocess execution, resource snapshots, and latest writes remain at the
CLI edge.
Doctor policy/path/status/report, validate document, and machine-report document
contracts live in `abyss_machine.doctor_contracts`; live probes, safe repair orchestration,
systemd/file reads, report writes, and latest writes remain at the CLI edge.
Memory policy/path, pressure-classification, zram-relief, headroom attribution,
launch-gate, and plan document contracts live in
`abyss_machine.memory_contracts`; `/proc`, `/sys`, cgroup/systemd reads,
process sampling, orchestration/apply routes, and latest/history writes remain
at the CLI edge.
Mode policy/path/state, definitions, target-profile, thermal classification/
launch caps, external power-profile guard decisions, plan/status document
shape, validate document, and lightweight reconcile status contracts live in
`abyss_machine.mode_contracts`; live battery/power-profile/sensor/cooling/AI
CPU/storage/memory/process sampling, `set`/`reconcile` host mutation, cooling
apply, systemd/file reads, and latest/history writes remain at the CLI edge.
Observability path, latest-read, manual-collect probe, status, and sample
temperature contracts live in `abyss_machine.observability_contracts`;
collector subprocess execution, filesystem permission probing, line counts,
systemd reads, and live latest reads remain at the CLI edge.
Cooling config/path/status/recommend/apply envelope, RAPL smoothing state/status,
fan-level parsing, and guarded fan-series decision contracts live in
`abyss_machine.cooling_contracts`; `/sys`, `systemd`, `journalctl`, platform/
fan/RAPL writes, live samples, and latest/history writes remain at the CLI edge.
Process role/workload/game classifiers, paths/latest read models, game-guard
envelope, and snapshot summary/top-list contracts live in
`abyss_machine.process_contracts`; live `/proc`, podman, DBus, AT-SPI, desktop/
window probes, storage hooks, thermal sampling, and latest/history writes remain
at the CLI edge.
Heartbeat/reaction/response path surfaces, heartbeat source freshness/rhythm/
candidate lifecycle, reaction candidate/status envelopes, and owner-gated
response command profiles/routes/status envelopes plus validate documents live in
`abyss_machine.runtime_evidence_contracts`; live latest reads, systemd/PSI
probes, self-awareness refreshes, reaction source collection, response
route-depth validation, and latest/history writes remain at the CLI edge.
Storage policy env/read-model helpers, hook stage/status contracts, cache env
route filtering, inventory drift, pressure classes/recommendations, cleanup
action contracts, protected-root decisions, write-preflight decision logic,
dry-run apply shape, and storage paths read models live in
`abyss_machine.storage_contracts`; policy file reads, directory scans, disk
usage, `/proc` guards, hook execution, monitor/status orchestration, actual
apply execution, and latest/history writes remain at the CLI edge.
Changes ledger paths/index/status/latest read models, id and decision-review
contracts, record/event/result shapes, surface classification, and preflight
decision envelopes live in `abyss_machine.changes_contracts`; active/closed
directory scans, JSON reads, decision-ref existence checks, record/close file
writes, directory moves, latest/history writes, and command rendering remain at
the CLI edge.
Docs markdown/decision-record parsing, decision-index document, docs paths,
docs index, docs agents-mesh validate document, and spec-id contracts live in
`abyss_machine.docs_contracts`;
source document discovery, file reads/stat/hash input collection, agent-mesh
discovery/validation, audit orchestration, generated index writes,
latest/history writes, and command rendering remain at the CLI edge.
Topology paths/status/index, validate document envelope, surface-state vocabulary, and forbidden-root
classifier contracts live in `abyss_machine.topology_contracts`; live path
stats, topology validate/audit checks, bridge/ledger validation,
installed-binary checks, latest/history writes, and command rendering remain at
the CLI edge.
Graph node/query/index/validate document contracts, maps policy/path/entry/query/packet/validate document
contracts, and machine RAG trace/eval/validate/status/index document contracts live in
`abyss_machine.context_contracts`; source-ref stat/hash reads, generated atlas
file writes, bounded evidence snapshot reads, systemd/timer validation, refresh
orchestration, latest/history writes, and command rendering remain at the CLI
edge.
Stack-bridge paths, extension command map, typing/heartbeat/observability
handoff contracts, heartbeat readiness, export envelope, latest-read contracts, and validate document
contracts live in `abyss_machine.stack_bridge_contracts`; artifact route catalog
assembly, latest JSON reads, static sync planning/writes, observability HTTP
probes, stack bridge validation orchestration, latest/history writes, and
command rendering remain at the CLI edge.
Self-awareness paths, bridge command contracts, validate document, read-only event/fabric
contracts, redaction/bounded-shape helpers, query matching, time buckets, and
stack-handoff service mapping plus working-stack role/status/link identity and
activation-gap handoff route contracts live in
`abyss_machine.self_awareness_contracts`; live stack/runtime probes, latest JSON
reads, refresh orchestration, investigate/replay/probe/cycle execution,
validation reads/writes, and command rendering remain at the CLI edge.
Dictation config/profile/runtime env contracts, replacement rules, transcript
postprocessing, command-intent detection, busy/max-duration results,
audio-doctor summary/recommended-runtime decisions, recording command/state
contracts, mic-calibration command/result contracts, stop/toggle lifecycle
envelopes, transcript helper/server request/result envelopes, insertion
result/key-sequence policy, and journal event/markdown envelopes live in
`abyss_machine.dictation_contracts`; WAV inspection, server/socket transport,
live insertion execution, document writes, and latest writes remain at the CLI
edge.

`artifact_signature_policy.py` validates the public artifact identity and
signature policy that feeds contract ABI signatures, local provenance packet
shape, the portable OS Abyss runner contract, and later release
provenance/signing lanes.
`release_artifact_policy.py` validates the release-artifact lane that maps
publishable artifact classes to required sidecar/provenance controls without
performing signing.
