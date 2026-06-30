# abyss-machine

`abyss-machine` is the portable seed for the Abyss OS host-machine layer.

It publishes the organ that makes a machine legible to agents: the CLI, source
contracts, public-safe config templates, typing/nervous intake machinery,
systemd unit skeletons, validation routes, and bootstrap logic.

It does not publish the private life of a specific machine. Generated facts,
typed events, browser captures, transcripts, process histories, model caches,
runtimes, backup vaults, and local indexes are created locally by the installed
machine under `/var/lib/abyss-machine` and `/srv/abyss-machine`.

## Reading Route

Start with:

1. [AGENTS.md](AGENTS.md)
2. [DESIGN.md](DESIGN.md)
3. [BOUNDARIES.md](BOUNDARIES.md)
4. [mechanics/README.md](mechanics/README.md)
5. [docs/publication/PUBLICATION_BOUNDARY.md](docs/publication/PUBLICATION_BOUNDARY.md)

## Bootstrap Shape

```bash
python -m pip install -e .
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
scripts/abyss-machine-bootstrap install --profile linux-systemd-core --apply --json
python scripts/validators/first_run_installed_projection.py --json
```

The bootstrap CLI and installed `abyss-machine` CLI share
`abyss_machine.path_policy` for root defaults and environment overrides.
Bootstrap `install` is fail-closed by default: it consumes
`bootstrap_install_bundle` only after the durable artifact trust-gate admits the
selected registry latest. Use `--skip-artifact-trust-gate` only for isolated
local projection rehearsals that are not consuming an install artifact.
Bootstrap installs the CLI entrypoint together with its `abyss_machine` package
modules and a compact public seed projection under
`/usr/local/share/abyss-machine` so installed validators and read models do not
depend on a live source checkout.
Shared validation summary and validation-document envelopes live in
`abyss_machine.validation_contracts`; the CLI supplies schema, version, current
time, and subsystem-specific facts.
The artifact bundle/trust lane remains owned by
`abyss_machine.artifact_bundles`; the CLI only supplies collected checks,
paths, latest refs, and write adapters for `artifacts validate`.
Consumer verification commands for update metadata, external TUF repositories,
and OCI/ORAS publication evidence are fail-closed by default: use
`--inspect-only` only when checking evidence shape without consuming the
artifact.
Typing/nervous path and service defaults plus typing paths/index document contracts live in
`abyss_machine.typing_nervous_policy`; refresh resource-gate and recent-index
debounce helpers, refresh assessment, latest-status classification, and
status resource-field naming, nervous-processing readiness document and acceptance, fact-state,
index-attempt, final-status, action-record, and refresh-document
builders live in `abyss_machine.typing_nervous_refresh`. Nervous index JSONL
source discovery, source loading/hash, source-record parsing/metadata,
source-policy helpers, record/chunk/document projection, build projection
summary, build result/meta envelopes, SQLite/FTS store/count/run contracts,
search shaping, vacuum result envelopes, status/freshness envelopes, and bounded/full validation
document envelopes live in
`abyss_machine.nervous_index`; shared typing/nervous secret-pattern and
high-entropy redaction contracts live in `abyss_machine.nervous_redaction`;
typing/nervous source metadata plus redacted text and URL payload contracts live
in `abyss_machine.nervous_sources`, along with browser-content record, quality,
dedupe, web-context classification, source state merge, effective source maps,
catalog, lookup, and source-set contracts; browser-content daily path projection,
recent duplicate scanning, JSONL append routing, latest write routing, ingest
document assembly, and record-from-page callback binding live in
`abyss_machine.nervous_browser_content_adapters`; typing saved-text/browser intake policy,
saved-text scan policy status, saved-text recent-record validation,
recent record policy/causal shape status,
causal project binding/resolution, causal interaction identity/context-anchor and URL/AI recipient helpers,
typing process project/dedupe/interaction/continuity/lane/context/recipient helpers, causal-context readmodel assembly, process readmodel assembly, and causal-awareness event/readmodel status,
capture-gate policy and decision documents, safe URL checks, recent browser-content
context inference, focused-browser selftest and browser-privacy record summaries,
Codex prompt hook/session-tail evidence summaries, prompt route coverage
assessment, browser selftest proof summary, browser context fallback status,
browser WebExtension, AT-SPI, generic GUI, focused-browser, and browser-privacy
selftest validation status, browser AI transcript selftest status and validation
status, browser input recency classification/readmodel assembly, status, and validation freshness, AT-SPI text-event
policy merge and heartbeat status, AT-SPI compact-history record and contract documents, typing
coverage document assembly plus route-note/gap and status decisions, typing status, validate, and end-to-end proof document assembly,
session-tail latest-status contracts, metadata envelopes, title fingerprints,
and AI transcript cleanup/role contracts live in
`abyss_machine.typing_capture_contracts`;
Codex prompt/session-tail text extraction, user-message route recognition,
context-envelope normalization, near-line duplicate semantics, metadata/context
ingest plans, and public-safe event summaries live in
`abyss_machine.typing_codex_semantics`; browser/native-host ingest plans,
response envelopes, framed native-host byte transport, synthetic selftest
documents, safe Firefox selftest profile prefs, temporary WebExtension selftest
profile/tmp roots, `web-ext` execution, loopback HTTP probe serving, subprocess
cleanup, probe polling, and public-safe WebExtension selftest documents live in
`abyss_machine.typing_browser_adapters`, along with browser-context, browser
AT-SPI, focused-browser, and browser-privacy selftest runtime orchestration,
Firefox `profiles.ini` parsing, and release-profile selection; focused-snapshot, AT-SPI text-event
sample/metadata/debounce, text-event listener runtime, focused-candidate tree
walk, browser focus metadata traversal, path-targeted focus/text read/insert
runtime, URL-scanned GI/Atspi text insertion runtime, GI/Atspi Firefox frame
focus runtime, supplied-object runtime helpers, and generic GUI selftest
semantic plans plus browser/privacy selftest recent-record readers live in
`abyss_machine.typing_atspi_adapters`; saved-text
filesystem scan limits, path walking, state continuity, file decode rejection,
candidate/skip accounting, ingest kwargs, state entries, and public-safe scan
documents live in `abyss_machine.typing_saved_text_adapters`; CLI still owns
configured policy reads, native-host stdin/stdout binding, `typing_ingest`
execution, state/latest writes, latest/history writes, browser selftest
callback binding, and command rendering;
nervous derived event/episode record shapes, classification/grouping,
build-envelope, and validation contracts live in `abyss_machine.nervous_events`;
local JSONL reads, derived event/episode replacement writes, latest read
envelopes, and build/validate latest write routing for events/episodes live in
`abyss_machine.nervous_events_adapters`;
nervous synthesis selection, candidate build orchestration, path/write-result
envelopes, markdown, validation, eval run execution-plan, and deterministic eval run/validate envelopes live in
`abyss_machine.nervous_synthesis`; local episode/event/candidate JSONL reads,
synthesis latest/period JSONL/markdown writes, synthesis validate latest
routing, and eval latest/history/validate routing live in
`abyss_machine.nervous_synthesis_adapters`. Nervous semantic sidecar schema,
freshness/status contract assembly, maintenance assessments, batch policy,
build-command shaping, source chunk projection, sidecar store/count/reuse
contracts, embedding subprocess payload/script/result contracts, and
vector/search shaping live in `abyss_machine.nervous_semantic`. Embedding
subprocess temp-file staging, OpenVINO runner invocation, output readback,
cleanup, and resource-profile callback routing live in
`abyss_machine.nervous_semantic_adapters`.
Nervous retention route specs, root/file candidate classification, retention
policy, plan/apply/validate result envelopes, and privacy-review route
contracts live in
`abyss_machine.nervous_retention`. Retention filesystem scan, symlink-tail
guards, dry-run/confirmed unlink execution, mutation receipts, and
plan/apply/validate latest write routing live in
`abyss_machine.nervous_retention_adapters`.
Nervous screenshot recurring-extension query policy and capture backend plan
contracts live in `abyss_machine.nervous_screenshot`; GNOME extension status
probes, allowlisted DBus screenshot execution, X11 active/game-risk window
probes, capture command execution, and public-safe screenshot fact assembly live
in `abyss_machine.nervous_screenshot_adapters`.
Nervous clipboard Wayland readiness, `wl-paste` MIME probing, text read
execution, backend failure mapping, redacted payload projection, and public-safe
clipboard fact assembly live in `abyss_machine.nervous_clipboard_adapters`.
Nervous rerank profile/defaults, source-prior scoring, machine-query caps,
merge policy, hybrid result scoring, neural text shaping, neural config
normalization, guarded neural-score blending, and eval document envelopes live in
`abyss_machine.nervous_rerank`; OpenVINO neural scorer temp-payload staging,
command invocation, stdout/output JSON parsing, policy-gate callback routing,
and resource-profile callback routing live in
`abyss_machine.nervous_rerank_adapters`.
Nervous recall refusal, mode normalization, search execution-plan, evidence projection,
summary counts, pack identity, and retrieval-pack document contracts live in
`abyss_machine.nervous_recall`.
Nervous brief scope/limit/cache keys, semantic-maintenance thresholds,
recent-episode compact projection, readiness/gap/next-action decisions, and document envelope live in
`abyss_machine.nervous_brief`.
Nervous quality derived-refresh status, validation compaction, check matrix,
and audit document envelope live in `abyss_machine.nervous_quality`.
Nervous privacy defaults, state merge/normalization, effective privacy,
status, set-transition, audit-record, and set-result contracts live in
`abyss_machine.nervous_privacy`.
Resource policy normalization, gate decisions,
systemd-run plan shapes, and launch argv contracts live in
`abyss_machine.resource_planning`. AI CPU route selection, routed-heavy policy,
thread/env hints, and route contract assembly live in
`abyss_machine.ai_cpu_routing`. AI runtime env/cache/resource-profile, model inventory, LLM
paths/registry/validate/runtime/profile status, OpenVINO benchmark-plan/probe/eval command/result contracts, AI eval
suite-policy/execution-plan/STT scoring/result envelopes, AI token-accounting privacy/count/count-execution/tokenizer-route/projection
contracts, AI capabilities projection, AI policy decision/gate, AI workload
taxonomy/measurement extraction plus stats/refresh/status routing, and AI
paths/status/runtime/report read-model envelopes live in
`abyss_machine.ai_runtime_contracts`. TTS profile/artifact/status, denial/error,
server response/payload, synth subprocess script/argv/result, synth/eval/compare
result, and success-index helper contracts live in
`abyss_machine.ai_tts_contracts`. Doctor policy/path/status/report, validate
document, and machine-report document contracts live in
`abyss_machine.doctor_contracts`; doctor core status probe collection for
platform/path/topology/stack-bridge/binary/command availability, doctor
power/cooling status probe collection, doctor storage/process status probe
collection, doctor snapshot/observability status probe collection, doctor
dictation status probe collection, doctor validate probe collection for
file/latest/systemd/bridge checks, report writes, machine-report artifact reads,
machine-report input collection, safe repair orchestration, and machine-report
latest/history/markdown writes live in
`abyss_machine.doctor_adapters`.
Memory policy/path, pressure-classification, zram-relief, headroom attribution,
launch-gate, and plan document contracts live in
`abyss_machine.memory_contracts`. Memory orchestration target snapshots,
Podman inspect/restart execution, local model HTTP probes, cgroup CPU sampling,
live locks, rehydrate polling, read-only pressure/process/cgroup collection,
and residency service snapshots live in `abyss_machine.memory_adapters`
through fakeable ports; memory hotpath probe document assembly and orchestration
plus concrete hotpath TTS/STT/LLM probe execution wrappers live there through
fakeable synth/transcribe/LLM-runner, residency, AI-policy, path-existence, and
monotonic ports. Memory-orchestrate candidate ranking, target identity,
confirmation-contract, health-route, future-executor, preflight/apply guard, and
live-authorization safety policy also live there through public-safe fakeable
documents. CLI owns concrete live runtime/path binding, latest/history/index
writes, and rendering. Mode policy/path/state, definitions,
target-profile, thermal launch caps, external power-profile guard decisions,
plan/status, validate document, and lightweight reconcile status document contracts live in
`abyss_machine.mode_contracts`. Mode runtime state load/save,
`powerprofilesctl` get/set execution, recent GameMode journal probes, and
external profile-guard input collection plus mode plan/status live input
collection live in `abyss_machine.mode_adapters` through fakeable ports;
concrete live reader binding, cooling apply concrete binding, latest writes, and
rendering remain at the CLI edge. Observability path, latest-read, manual-collect
probe, status, and sample-temperature contracts live in
`abyss_machine.observability_contracts`. Cooling config/path/status,
recommendation, apply-envelope, RAPL smoothing state/status, and guarded fan
series decision contracts live in `abyss_machine.cooling_contracts`. Cooling
platform-profile, Lenovo fan-mode, RAPL-MMIO, package-throttle, kernel
fan-error, thermal-zone/cooling-device sysfs sampling, trusted sensor
projection, temperature summary/sample, sample-series ports, profile apply
orchestration, guarded TFN1 write, fan-validate, fan-series orchestration, and
RAPL smoothing decision/state orchestration live in `abyss_machine.cooling_adapters`. Process
role/workload/game classifiers, paths/latest read models, game-guard envelope,
and snapshot summary/top-list contracts live in `abyss_machine.process_contracts`.
Low-level process `/proc` stat/status/cmdline/io/cgroup/fd reads, storage-root
matching, CPU jiffy sampling, process info collection, sanitized Podman
container health reads, and container inspect redaction live in
`abyss_machine.process_adapters` through fakeable proc-root/sysconf/sleep and
command-runner ports. Read-only GNOME Shell desktop-compositor command/proc
probes, AT-SPI hard-timeout desktop capture, and document assembly live there
too; thermal sampling, gamemode binding, broader container orchestration,
latest/history writes, and command rendering remain at the CLI edge.
Runtime evidence path/read-model contracts, heartbeat source freshness/rhythm/
lifecycle helpers, reaction candidate/status envelopes, and owner-gated response
route/profile/status contracts plus validate documents live in
`abyss_machine.runtime_evidence_contracts`.
Host lifecycle source/install/runtime parity document contracts, compact digest
map comparisons, path identity summaries, runtime JSON projection, and
privacy-preserving no-raw-runtime-output policy live in
`abyss_machine.host_lifecycle_parity`; runtime closeout command catalogs and
read-only/explicit-refresh profiles live there too. The validator script binds
those contracts to live installed paths and bounded subprocess execution for
closeout; runtime checks that refresh latest/readmodel state require explicit
opt-in.
Storage policy/env read models, hook stage/status contracts, cache env routes,
inventory drift, pressure classes/recommendations, cleanup action contracts,
protected-root decisions, write-preflight decisions, dry-run apply shape, and
paths read models live in `abyss_machine.storage_contracts`; cleanup-plan
active-process guard path matching, `/proc` fd target inspection, allowlisted
cleanup apply execution, storage hook directory scan/execution, and storage
inventory path/disk measurement live in `abyss_machine.storage_adapters` through
fakeable process snapshot/fd, command-runner, euid, clock, hook-runner,
environment, disk-usage, size-measurement, and path-scan ports.
Changes ledger paths/index/status/latest read models, id and decision-review
contracts, record/event/result shapes, surface classification, and preflight
decision envelopes live in `abyss_machine.changes_contracts`.
Docs markdown/decision-record parsing, decision-index document, docs paths,
docs index, docs agents-mesh validate document, and spec-id contracts live in
`abyss_machine.docs_contracts`.
Topology paths/status/index, validate document envelope, surface-state vocabulary, and forbidden-root
classifier contracts live in `abyss_machine.topology_contracts`.
Graph node/query/index/validate document contracts, maps policy/path/entry/query/packet/validate document
contracts, and machine RAG trace/eval/validate/status/index document contracts live in
`abyss_machine.context_contracts`.
Stack-bridge paths, extension command map, typing/heartbeat/observability
handoff contracts, heartbeat readiness, export envelope, latest-read contracts, and validate document
contracts live in `abyss_machine.stack_bridge_contracts`.
Self-awareness paths, bridge command contracts, validate document, read-only event/fabric
contracts, redaction/bounded-shape helpers, query matching, time buckets,
stack-handoff service mapping, working-stack role/status/link identity, and
activation-gap handoff route contracts live in
`abyss_machine.self_awareness_contracts`; live stack/runtime probes, latest JSON
reads, refresh orchestration, investigate/replay/probe/cycle execution,
validation reads/writes, and command rendering remain at the CLI edge.
Dictation config/profile/runtime env, replacements, postprocess, intent,
busy/max-duration, audio-doctor summary/recommended-runtime decisions,
mic-calibration command/result contracts, recording command/state, stop/toggle
lifecycle envelopes, transcript helper/server request/result envelopes,
insertion result/key-sequence policy, and journal event/markdown contracts live in
`abyss_machine.dictation_contracts`; explicit-file transcription runtime
execution, warm-server socket transport, client-side 16 kHz runtime
preprocessing, helper subprocess invocation, helper runtime env projection,
recording lifecycle/process-state execution, WAV inspection/recent-audio scan,
audio-doctor `pactl`/`wpctl` probes, and transcript journal
JSONL/Markdown/latest/index IO, clipboard/text insertion execution, and
mic-calibration recording/apply live in
`abyss_machine.dictation_execution_adapters`. Config load/save, concrete
profile defaults, env-bound runtime/postprocess/profile selection, runtime env
projection, and config/profile read documents live in
`abyss_machine.dictation_profile_adapters`. Path/index/AGENTS.md documents and
dictation docs scaffolding live in `abyss_machine.dictation_docs_adapters`.
Status read-model assembly and readiness path/command probes live in
`abyss_machine.dictation_status_adapters`. Dictation validation checks and
validate latest/history write routing live in
`abyss_machine.dictation_validation_adapters`. Replacements load/save/list/test
and add/remove mutation flow live in `abyss_machine.dictation_replacements_adapters`.
Postprocess glue, notification flow, and rendering remain at the CLI edge.
These surfaces
are re-exported or adapted by the CLI for installed-host compatibility. A fresh
machine should render
`/etc/abyss-machine`, create durable evidence under `/var/lib/abyss-machine`,
reserve large mutable planes under `/srv/abyss-machine`, and keep ephemeral
state under `/run/abyss-machine` without copying private state from this
workstation.
The first-run installed projection validator proves this shape in isolated
temporary roots and compares the source CLI against the temp-installed CLI
without relying on a live source checkout.

Typing and nervous-system collectors are installed as a first-class organ, but
real collection is opt-in:

```bash
scripts/abyss-machine-bootstrap enable-profile typing-intake --dry-run --json
scripts/abyss-machine-bootstrap enable-profile nervous-local --dry-run --json
```

## Public Boundary

Start with [docs/publication/PUBLICATION_BOUNDARY.md](docs/publication/PUBLICATION_BOUNDARY.md)
before adding files. The short rule is:

- publish source, contracts, config templates, schemas, validators, and tests;
- do not publish generated evidence or private local state.
- keep release/artifact trust details in their manifest and validation homes,
  not as the first route through the repository.

## Test Lanes

Default public smoke:

```bash
python scripts/ci_gate.py --mode source-fast
```

Validation lanes are OS Abyss CLI contracts. GitHub Actions, local host
schedulers, release pipelines, and agent goal loops use the same
`scripts/ci_gate.py` entrypoints.

Host contract tests imported from the current workstation are kept for
development and migration work, but they are not the bootstrap smoke lane:

```bash
python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
```

Release checks:

```bash
python scripts/ci_gate.py --mode release-artifact
python scripts/release_check.py
python scripts/release_check.py --include-host-contracts
```

Artifact and release-trust command routes are real, but they are not the primary
orientation path for this repo. Use
[manifests/artifact_bundles/README.md](manifests/artifact_bundles/README.md)
and [docs/validation/VALIDATOR_TOPOLOGY.md](docs/validation/VALIDATOR_TOPOLOGY.md)
when working on that lane.

## Current Status

The installed CLI is still a large entrypoint, but it is no longer a lone script
projection. Bootstrap carries the package modules needed by installed-host
compatibility, including typing/nervous helper logic and source-backed public
read models. Shared root policy, typing/nervous organ policy, typing/nervous
refresh decision helpers, the refresh latest-status classifier, action-record
builders, refresh status resource-field naming, nervous-processing readiness document and acceptance,
the final refresh document shape, nervous index source discovery,
source loading/hash, source-record parsing/metadata, source-policy, build
projection, build result/meta envelopes, status/freshness envelopes,
store/search/vacuum/bounded/full validation document envelopes, shared typing/nervous redaction, nervous
event/episode contracts, nervous synthesis build/validation/eval execution-plan/envelopes and local read/write adapter,
nervous brief readiness contracts, nervous quality audit/derived-refresh
contracts, typing/nervous
source metadata, redacted payload, browser-content record/quality/dedupe/web-context,
and source state/effective/catalog/source-set contracts, typing browser/saved-text
capture-gate plus recent browser-content context-inference and focused-browser
selftest, browser-privacy record summary, Codex prompt evidence summary, route
coverage assessment, browser selftest proof summary, browser context fallback
status, browser input recency classification/readmodel assembly, status, and validation freshness, AT-SPI text-event
policy merge and heartbeat status, AT-SPI compact-history record and contract documents, typing coverage document assembly plus route-note/gap and status
decisions, typing status, validate, and end-to-end proof document assembly, saved-text recent-record validation, recent record policy/causal
shape status, causal project binding/resolution, causal interaction identity/context-anchor and URL/AI recipient helpers,
typing process project/dedupe/interaction/continuity/lane/context/recipient helpers, causal-context readmodel assembly, process readmodel assembly, and causal-awareness event/readmodel status, session-tail latest-status
contracts, Codex prompt/session-tail semantic ingest planning, AT-SPI
focused/text-event/generic GUI semantic plans, saved-text scan filesystem
mechanics, and resource plan/launch
contracts are now
module-owned with public
validators. AI CPU route policy is
also module-owned; the CLI still gathers
live thermal/policy/mode/battery facts. Nervous semantic
schema, status/freshness decisions, maintenance gate decisions, batch policy,
build-command shaping, source chunk projection, semantic sidecar store/reuse,
embedding subprocess payload/script/result parsing, and vector search are
module-owned; embedding subprocess temp-file staging, OpenVINO runner
invocation, output readback, cleanup, and resource-profile callback routing are
adapter-owned while source-index connection, locking, policy gates, resource
launch, sidecar writes, and latest writes remain at the CLI edge. Nervous
rerank profile/defaults, hybrid source-prior scoring, machine-query caps,
neural text/config shaping, guarded neural-score blending, and eval envelopes
are module-owned; OpenVINO neural scorer temp-payload staging, command
execution, stdout/output JSON parsing, policy-gate callback routing, and
resource-profile callback routing are adapter-owned while lexical/semantic
source collection, semantic maintenance assessment, latest/history writes, and
command rendering remain at the CLI edge. Nervous
retention route specs, file-candidate classification, policy,
plan/apply/validate envelopes, and privacy-review route contracts are
module-owned; route scanning, symlink-tail checks, dry-run/confirmed unlink
execution, mutation receipts, and latest/history/validate write routing are
adapter-owned while privacy/path binding and rendering remain at the CLI edge.
Nervous screenshot recurring
extension-query policy and backend capture plan are module-owned while GNOME
extension status probes, process/X11 risk probes, capture execution, artifact
source callbacks, and fact assembly are adapter-owned; CLI binds source policy,
environment flags, paths, process callbacks, and rendering. Nervous
rerank profile/source-prior rules, machine-query caps, merge policy, hybrid
scoring, neural config/text shaping, guarded neural-score blending, and eval
document envelopes are
module-owned while lexical/semantic source collection, semantic maintenance
assessment, OpenVINO scorer subprocess execution, and latest/history writes
remain at the CLI edge. Nervous recall refusal, mode normalization, search
execution-plan, evidence projection, summary counts, pack identity, and
retrieval-pack envelope are module-owned while lexical/hybrid search adapter calls and latest/history writes
remain at the CLI edge. Nervous brief scope/limit/cache keys,
semantic-maintenance thresholds, recent-episode compact projection,
readiness/gap/next-action decisions, and document envelope are module-owned
while live quality/status/privacy/capture/
index/semantic/synthesis/host read-model collection, episode JSONL reads, and latest/history writes
remain at the CLI edge. Nervous quality derived-refresh status, validation
compaction, check matrix, and audit document envelope are module-owned while
refresh execution, live validators/systemd/latest/redaction input collection,
latest/history writes, and command rendering remain at the CLI edge. Nervous privacy defaults, state merge/normalization,
effective privacy, status, set-transition, audit-record, and set-result
contracts are module-owned while state file reads/writes, audit JSONL appends,
and latest writes remain at the CLI edge. AI runtime env/cache/resource-profile, model inventory shaping, LLM paths/registry/validate/runtime/profile status,
OpenVINO benchmark-plan/probe/eval command/result contracts, AI eval suite-policy/execution-plan/STT scoring/result
envelopes, token-accounting privacy/count/count-execution/profile/tokenizer-route/aoa-summary contracts,
capabilities projection, AI policy decision/gate, workload taxonomy/measurement
extraction plus stats/refresh/status routing, and paths/status/runtime/report
read-model envelopes are module-owned. AI runtime adapters own filesystem
walks, package/runtime discovery, tokenizer discovery, bounded subprocess
runner seams, benchmark/eval/workload/core readmodel write routing, LLM
registry/latest/validate store routing, token-accounting store/readmodel and runner seams,
`.aoa` generated-summary read/write routing, and resident controller execution
through fakeable ports; concrete config/path binding, policy gates, STT fixture
generation, live input/env binding, resident parser/result rendering, broader
resource sampling, and command rendering remain at the CLI edge. TTS profile/artifact/status decisions,
policy-denial/error summaries, server response/payload shaping, synth
subprocess script/argv/result contracts, synth/eval/compare envelopes, and
success-index entries are module-owned while module probing, server/socket
transport, audio IO, subprocess execution, resource snapshots, and latest
writes remain at the CLI edge. Doctor policy/path/status, readiness scoring,
validate document, report markdown/document shape, machine-report artifact
summary/status, and machine-report document/markdown contracts are module-owned;
`doctor_adapters` owns validate/core/power/cooling/storage/process/snapshot/
observability/dictation probe collection, report IO, machine-report
input/writes, and safe repair orchestration while remaining live diagnostic
probes, concrete port binding, systemd/file reads, latest/report writes, and
rendering remain at the CLI edge. Dictation config/profile/runtime env,
replacement rules, transcript postprocessing, command-intent detection, busy
result, max-duration policy, audio-doctor summary/recommended-runtime decisions,
mic-calibration command/result contracts, recording command/state, stop/toggle
lifecycle envelopes, transcript helper/server request/result envelopes,
insertion result/key-sequence policy, and journal event/markdown contracts are
module-owned; `dictation_execution_adapters` owns explicit-file transcription
through warm-server socket transport, client-side 16 kHz runtime preprocessing,
helper subprocess invocation, helper runtime env projection, and recording
lifecycle/process-state execution, WAV inspection/recent-audio scan, and
audio-doctor `pactl`/`wpctl` probes, and transcript journal
JSONL/Markdown/latest/index IO, clipboard/text insertion execution, and
mic-calibration recording/apply. `dictation_profile_adapters` owns config
load/save, concrete profile defaults, env-bound runtime/postprocess/profile
selection, runtime env projection, and config/profile read documents.
`dictation_docs_adapters` owns path/index/AGENTS.md documents and dictation docs
scaffolding. `dictation_status_adapters` owns status read-model assembly and
readiness path/command probes. `dictation_validation_adapters` owns dictation
validation checks and validate latest/history write routing.
`dictation_replacements_adapters` owns replacements load/save/list/test and
add/remove mutation flow. Postprocess glue, notification flow, and rendering remain at the CLI edge. Memory policy/path,
pressure-classification, zram-relief, headroom attribution, launch-gate, and
plan document contracts are module-owned. Memory live adapters own read/process
collection, orchestration target snapshots, hotpath execution wrappers, and
orchestration safety policy; concrete live binding, latest/history writes, and
rendering remain at the CLI edge. Mode policy/path/state, definitions, target-profile,
thermal classification/launch caps, external power-profile guard decisions,
plan/status, validate document, and lightweight reconcile status document contracts are
module-owned; mode state load/save, `powerprofilesctl` get/set, GameMode
journal probing, external guard input collection, mode plan/status input
collection, and reconcile orchestration are adapter-owned through fakeable
ports. Concrete live/mutation port binding, cooling apply concrete execution,
systemd reads, latest/history writes, and rendering remain at the CLI edge.
Observability path, latest-read, manual-collect probe, status, and sample
temperature contracts are module-owned while collector subprocess execution,
filesystem permission probing, line counts, systemd reads, and live latest reads
remain at the CLI edge. Cooling config/path/status/recommend/apply envelope,
RAPL smoothing state/status, fan-level parsing, and guarded fan-series decision
contracts are module-owned; platform-profile, Lenovo fan-mode, RAPL-MMIO,
package-throttle, kernel fan-error, thermal-zone/cooling-device sysfs sampling,
trusted sensor projection, temperature summary/sample, sample-series ports,
profile apply orchestration, guarded TFN1 write, fan-validate, and fan-series
orchestration, and RAPL smoothing decision/state orchestration are adapter-owned
through `cooling_adapters`. Systemd reads, concrete config/battery/sensors/mode
binding, latest/history writes, and rendering remain at the CLI edge.
Process role/workload/game classifiers, paths/latest read models, game-guard
envelope, and snapshot summary/top-list contracts are module-owned while live
`/proc` process-info collection is adapter-owned through `process_adapters`;
Podman container health reads are adapter-owned through fakeable command ports;
read-only GNOME Shell desktop-compositor command/proc probes are adapter-owned;
AT-SPI hard-timeout desktop capture is adapter-owned through fakeable
`pyatspi`, timer/signal, subprocess, and latest-loader ports; thermal sampling,
gamemode binding, broader container orchestration, and latest/history writes
remain at the CLI edge.
Storage hook execution belongs to the storage adapter boundary. Heartbeat/reaction/response path surfaces,
heartbeat source freshness/rhythm/
candidate lifecycle, reaction candidate/status envelopes, and owner-gated
response command profiles/routes/status envelopes plus validate documents are module-owned while live
latest reads, systemd/PSI probes, self-awareness refreshes, reaction source
collection, response route-depth validation, and latest/history writes remain at
the CLI edge. Storage policy/env read models, hook stage/status contracts,
inventory drift, pressure classification/recommendation rules, cleanup action
contracts, protected-root decisions, write-preflight decision logic, dry-run
apply shape, paths read models, cleanup-plan process guards, allowlisted cleanup
apply execution, storage hook directory scan/execution, and storage inventory
path/disk measurement are module/adapter-owned while policy file reads,
configured hook directory/env binding, inventory spec selection, podman/memory
input binding, process snapshot binding, monitor/status orchestration, pressure
and apply preflight orchestration, latest/history writes, and command rendering
remain at the CLI edge. Changes ledger
paths/index/status/latest read models,
id and decision-review contracts, record/event/result shapes, surface
classification, and preflight decision envelopes are module-owned while
active/closed directory scans, JSON reads, decision-ref existence checks,
record/close file writes, directory moves, latest/history writes, and command
rendering remain at the CLI edge. Docs markdown/decision-record parsing,
decision-index document, docs paths, docs index, docs agents-mesh validate
document, and spec-id contracts are
module-owned while source document discovery, file reads/stat/hash input
collection, agent-mesh discovery/validation, audit orchestration, generated
index writes, latest/history writes, and command rendering remain at the CLI
edge. Graph node/query/index/validate document contracts, maps policy/path/entry/query/packet/validate document
contracts, and machine RAG trace/eval/validate/status/index document contracts are
module-owned while source-ref stat/hash reads, generated atlas file writes,
bounded evidence snapshot reads, systemd/timer validation, refresh
orchestration, latest/history writes, and command rendering remain at the CLI
edge. Topology paths/status/index, validate document envelope, surface-state vocabulary, and forbidden-root
classifier contracts are module-owned while live path stats, topology
validate/audit checks, bridge/ledger validation, installed-binary checks,
latest/history writes, and command rendering remain at the CLI
edge. Stack-bridge paths, extension command map, typing/heartbeat/observability
handoff contracts, heartbeat readiness, export envelope, and latest-read
contracts are module-owned while artifact route catalog assembly, latest JSON
reads, static sync planning/writes, observability HTTP probes, stack bridge
validation orchestration, latest/history writes, and command rendering remain at
the CLI
edge. Self-awareness paths, bridge command contracts, validate document, read-only event/fabric
contracts, redaction/bounded-shape helpers, query matching, time buckets, and
stack-handoff service mapping plus working-stack role/status/link identity and
activation-gap handoff route contracts are module-owned while live
stack/runtime probes, latest JSON reads, refresh orchestration,
investigate/replay/probe/cycle execution, validation reads/writes, and command
rendering remain at the CLI edge. The public
cold-start route now checks for private operator path and current-checkout
leakage across source and temporary installed projections. The compact
source/install/runtime parity summary now reports installed drift without
dumping live host payloads. Remaining hardening
should keep moving lexical index live write/latest adapters, semantic embedding
provenance adapters, memory orchestration write-routing/broader container
orchestration seams, browser-content capture runtime adapters, rerank live search/latest adapters,
recall live search adapter/write adapters, AI runtime live execution adapters,
TTS live server/audio execution adapters, dictation postprocess/notification adapters, plus
remaining self-awareness live probe/readmodel orchestration, process thermal
probes, broader container orchestration, and remaining cooling host-control orchestration
adapters behind smaller modules before claiming full
host-agnostic behavior for every subcommand.
