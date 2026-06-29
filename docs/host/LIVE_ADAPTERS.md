# Live Adapter Audit

`abyss-machine` is a public source seed, not a dump of a live workstation. The
live adapter boundary names the code that touches host/runtime state while
package modules keep stable contracts, policy, and read-model shapes.

## Adapter Classes

| Class | Owns | Public seed rule |
|---|---|---|
| Host/runtime reads | `/proc`, `/sys`, DBus, systemd, browser profiles, AT-SPI, sockets, SQLite stores, JSONL histories, generated latest files, cache inventories, and local config reads. | May produce bounded summaries; must not publish private evidence, captures, local indexes, secrets, or model weights. |
| Latest/history writes | Atomic JSON latest writes, daily JSONL appends, generated index writes, report writes, and compact history records under `/var/lib/abyss-machine`. | Source owns write mechanism and schema shape; host owns generated records. |
| Mutating host actions | systemd starts/stops, profile switches, cleanup apply, retention unlink, browser selftest profile creation, clipboard/audio/text insertion, and explicit repair actions. | Must stay opt-in, reversible or dry-run first where possible, and outside public examples unless synthetic. |
| Subprocess/runtime execution | `systemctl`, `journalctl`, OpenVINO/tokenizer helpers, browser/AT-SPI probes, X11 tools, audio tools, package queries, and local benchmark/eval processes. | Execution plan may be public; runtime outputs and local paths are bounded evidence. |
| Network/socket/browser bridges | BiDi/WebSocket capture, native-host messaging, local HTTP probes, resident model/TTS sockets, and stack observability probes. | Public code may define adapters; live payloads stay local and privacy-gated. |

## Current High-Pressure Surfaces

| Surface | Reads | Writes | Mutates/executes | Current home |
|---|---|---|---|---|
| `typing` | policy files, Codex session JSONL, browser/native-host payloads, saved text files, AT-SPI focus/text metadata, user-systemd status, recent typing records. | typing latest/history JSONL, source-specific selftest latest files, typing saved-text scan state/latest, typing index, compact AT-SPI history. | browser native-host responses, optional focused-browser selftests, AT-SPI focus/insert diagnostics, virtual typing selftests. | Contracts in `typing_capture_contracts`; latest/history persistence and Codex session-tail filesystem reads start in `typing_nervous_adapters`; Codex prompt/session-tail semantic ingest plans live in `typing_codex_semantics`; browser/native-host ingest plans, synthetic selftest documents, route selection, response envelopes, framed native-host byte transport, Firefox profile discovery, temporary Firefox WebExtension, browser-context, browser AT-SPI, focused-browser, and browser-privacy selftest profile prep, loopback/nonloopback local HTTP probes, `web-ext` command selection, subprocess lifecycle, cleanup, probe polling, targeted AT-SPI callback routing, and public-safe result document assembly live in `typing_browser_adapters`; focused-snapshot, AT-SPI text-event sample/metadata/debounce, text-event listener runtime, focused-candidate tree walk, browser focus metadata traversal, path-targeted focus/text read/insert runtime, URL-targeted focused-text runtime, URL-scanned GI/Atspi text insertion runtime, GI/Atspi Firefox frame focus runtime, browser/privacy selftest recent-record readers, supplied-object runtime helpers, and generic GUI selftest semantic plans live in `typing_atspi_adapters`; saved-text filesystem scan limits, path walking, state continuity, decode rejection, candidate/skip accounting, ingest kwargs, state entries, and scan documents live in `typing_saved_text_adapters`; native-host stdin/stdout binding, `typing_ingest`, saved-text state/latest writes, browser selftest latest/index writes, callback binding, policy reads, and command rendering remain CLI edge. |
| `nervous` | source policy, privacy state, fact/event/episode JSONL, browser history DBs, explicit metadata roots, podman metadata, clipboard, screenshot/window state, semantic/index SQLite stores. | nervous facts/events/episodes/latest, index/semantic status, synthesis/eval/retrieval reports, retention plans, privacy audit records. | browser content capture, GNOME/X11 probes, retention apply/unlink, semantic embedding subprocesses, reranker subprocesses. | Contracts split across nervous modules; latest/history persistence starts in `typing_nervous_adapters`; lexical index lifecycle IO lives in `nervous_index_adapters`; semantic sidecar lifecycle/source loading/latest writes and embedding subprocess execution live in `nervous_semantic_adapters`; neural rerank subprocess execution lives in `nervous_rerank_adapters`; recall/rerank live search orchestration and retrieval/eval write routing live in `nervous_retrieval_adapters`; most other probes remain CLI edge. |
| `dictation` | audio devices, runtime config/env, runtime paths, transcripts, WAV metadata, recording/server state. | transcript latest/JSONL, dictation index, validation latest. | recording, server transport, clipboard/text insertion, audio runtime subprocesses, desktop notifications. | `dictation_contracts` owns shapes; `dictation_runtime_adapters` owns XDG runtime path/socket/max-duration env translation; `dictation_profile_adapters` owns config load/save, concrete profile defaults, env-bound runtime/postprocess/profile selection, runtime env projection, and config/profile read documents; `dictation_docs_adapters` owns path/index/AGENTS.md documents and dictation docs scaffolding; `dictation_execution_adapters` owns explicit-file transcription via warm-server/helper runtime, client-side 16 kHz preprocessing, recording lifecycle/process-state execution, toggle debounce, WAV inspection/recent-audio scan, audio-doctor `pactl`/`wpctl` probes, transcript journal policy/JSONL/Markdown/latest/index IO, clipboard/text insertion execution, and mic-calibration recording/apply; `dictation_lock_adapters` owns file-lock execution; `dictation_postprocess_adapters` owns transcript postprocess/intent glue; `dictation_notifications_adapters` owns notification policy and `notify-send` command spawning; `dictation_status_adapters` owns status read-model assembly and readiness path/command probes; `dictation_validation_adapters` owns dictation validation checks and validate latest/history write routing; `dictation_replacements_adapters` owns replacements load/save/list/test/add/remove flow. Rendering remains CLI edge. |
| `ai` | runtime config, model/cache roots, package availability, OpenVINO/runtime package probes, tokenizer/model inventories, generated AoA summaries. | AI runtime/status/eval/token-accounting latest and histories. | OpenVINO, tokenizer, STT/TTS, resident LLM and benchmark subprocesses. | `ai_runtime_contracts`, `ai_runtime_adapters`, `ai_tts_contracts`, `ai_tts_adapters`, and `ai_cpu_routing` own contracts, discovery adapters, bounded OpenVINO benchmark/eval child-process runners, benchmark/eval suite orchestration and latest/daily write routing, workload JSONL discovery/read/dedupe append plus workload taxonomy/stats/refresh/status write routing, devices/models/capabilities/policy/runtime/status/report readmodel assembly and latest/history write routing, token-accounting tokenizer subprocess env/runner execution, resident LLM controller command/timeout runner execution, TTS Unix-socket client transport, server status/stop exchanges, warm server socket/request loop, OpenVINO import/load/generate/write lifecycle, shutdown/unload cleanup, cold TTS synth subprocess env/runner execution, and TTS output audio summary/resource-report assembly; policy-gate binding, STT/dictation transport, broader resource sampling, `.aoa` generated-summary reads, token-accounting profile/count/latest routing, resident LLM parser/result rendering, and concrete command rendering remain CLI edge. |
| `self-awareness` | stack/runtime latest files, observability probes, generated event/fabric stores, systemd state. | self-awareness timeline/context/episode/brief/query/probe/latest surfaces. | probe/cycle/replay/investigate orchestration and stack handoff checks. | `self_awareness_contracts` owns read-model shapes; orchestration remains CLI edge. |
| `storage/process/memory/mode/cooling` | disk usage, `/proc`, cgroups, sensors, power profile, process tables, systemd state. | status/plan/monitor/latest histories and indexes. | cleanup apply, resource launch, profile switch, cooling apply, process/container probes. | Contract modules own policy decisions; live host reads and mutation remain CLI edge. |
| `artifact/release trust` | source manifests, bundle evidence, local statement/receipt files, OCI/TUF/C2PA/SCITT proof surfaces. | artifact latest/history, trust coverage, update-lane status. | local trust-tool subprocesses and publication probes. | Real but separate lane; do not fold into typing/nervous adapter work. |

## Extracted First Seam

`abyss_machine.typing_nervous_adapters` now owns the first shared live adapter
for the agent nervous-system organs:

- latest JSON reads with read-schema envelopes;
- atomic latest JSON writes;
- daily JSONL history appends with file locking;
- optional typing index refresh writes;
- local JSONL history file discovery and bounded recent-record reads;
- source-adapter filtered typing history reads with scan accounting;
- Codex session-tail file discovery, root-contained state-file selection,
  incremental byte reads, fallback tail reads, and stat failure reports;
- write-disabled no-op semantics for public-safe dry paths.

This is intentionally narrow. It does not claim the full AT-SPI runtime,
browser live capture/probes, semantic embedding, retention unlink, or other
subsystem live IO until those are moved behind similarly bounded seams.

## Extracted Codex Semantic Seam

`abyss_machine.typing_codex_semantics` owns the Codex prompt/session-tail
semantic boundary for typing intake:

- prompt text extraction from UserPromptSubmit payload shapes;
- Codex prompt-hook metadata and ingest-plan construction;
- session JSONL user-message route recognition for `event_msg.user_message` and
  `response_item.message.role_user`;
- IDE/goal/environment envelope normalization and skip reasons;
- near-line duplicate keying for fallback raw-route repeats;
- Codex session-tail metadata/context ingest plans;
- public-safe event summary projection without raw text.

The CLI still owns JSON parsing, configured paths, session-tail state
bookkeeping, calling `typing_ingest`, latest/history writes, and command
rendering. The filesystem tail mechanics remain in `typing_nervous_adapters`.

## Extracted Browser Native-Host Seam

`abyss_machine.typing_browser_adapters` owns the browser/WebExtension
native-host semantic adapter boundary for typing intake:

- browser-extension committed-text ingest plans;
- browser AI transcript cleanup/metadata ingest plans using
  `typing_capture_contracts` as policy owner;
- public-safe status documents after `typing_ingest` execution;
- synthetic browser-extension and AI transcript selftest message/document
  builders;
- native-host route selection and response/error envelopes;
- framed native-host little-endian length-prefix read/write, JSON decode/encode,
  and malformed-frame errors;
- temporary Firefox WebExtension selftest runtime orchestration: safe profile
  `user.js` prep, `web-ext`/offline-npm command selection, loopback HTTP test
  page, temp profile/artifact/cache roots, subprocess lifecycle and cleanup,
  typing-record probe polling, and public-safe result document assembly.
- browser-context selftest runtime orchestration: temporary Firefox profile and
  public-safe writing-context page, loopback HTTP serving, Firefox subprocess
  lifecycle, capture env overrides/restoration, bounded live-content polling,
  AT-SPI document-path inference callback routing, redacted process tails, and
  public-safe result document assembly.
- browser AT-SPI selftest runtime orchestration: temporary or release Firefox
  profile selection, synthetic safe page generation, loopback and natural-route
  local HTTP serving, Firefox subprocess lifecycle, readiness/final event
  polling, focused-window and targeted AT-SPI insert callback routing, redacted
  process tails, and public-safe result document assembly.
- focused-browser selftest runtime orchestration: temporary Firefox profile and
  safe focused input page generation, loopback HTTP serving, Firefox subprocess
  lifecycle, readiness event polling, focused-window/path/URL/no-op AT-SPI
  callback routing, redacted process tails, cleanup, and public-safe result
  document assembly.
- browser-privacy selftest runtime orchestration: temporary Firefox profile and
  login-sensitive loopback page generation, Firefox subprocess lifecycle,
  AT-SPI text-event metadata polling, focused-candidate and metadata-focus
  callback routing, absence-proof callback routing, redacted process tails,
  cleanup, and public-safe result document assembly.
- Firefox profile discovery: `profiles.ini` parsing, relative/absolute profile
  path projection, extension sidecar path projection, and release-profile
  selection order.

The CLI still owns binding the adapter to native-messaging stdin/stdout,
calling `typing_ingest`, latest/history writes, WebExtension/browser-context,
browser AT-SPI, focused-browser, and browser-privacy selftest latest/index
writes, callback binding, policy reads, and command rendering.

## Extracted AT-SPI Semantic Seam

`abyss_machine.typing_atspi_adapters` owns the AT-SPI semantic/runtime adapter
boundary for typing intake:

- focused-snapshot ingest plans, candidate projections, metadata, context, and
  public-safe status documents;
- AT-SPI text-event sample envelopes, metadata shaping, browser-context
  bounded summaries, context identity, debounce decisions, and typing-event
  summaries;
- generic GUI selftest ingest plans and final selftest document assembly;
- safe string handling shared by live AT-SPI object readers;
- AT-SPI object runtime helpers for state flags, text payload reads, object
  paths, document attributes, application/proc fallback context, and event
  object context projection over supplied accessibility objects;
- AT-SPI text-event listener runtime: `pyatspi` loading, event type selection,
  Registry listener registration/start/stop, bounded sample timers, heartbeat
  refresh loops, max-event stop, summary counters, compact-history callback
  routing, and listener failure documents;
- focused/browser `pyatspi` traversal runtime: desktop loading, timeout
  setup, safe child traversal, focused-node walks, path parsing/resolution,
  browser URL metadata target discovery, and accessibility focus actions;
- path-targeted AT-SPI text focus/read/insert runtime: desktop loading, path
  resolution, URL/text-hash confirmation, editable-text insert/set fallback,
  focused-state confirmation, and public-safe failure/status documents.
- URL-targeted focused-text runtime: desktop loading, bounded browser document
  walk, safe selftest sensitive-state override, text-hash confirmation,
  accessibility focus action, and public-safe failure/status documents.
- URL-scanned GI/Atspi text insertion runtime: GI Atspi loading, Firefox
  document discovery/priority, URL and current-text hash confirmation,
  editable-text insert/set fallback, focus/caret handling, after-hash
  confirmation, and public-safe failure/status documents.
- GI/Atspi Firefox frame focus runtime: GI Atspi loading, Firefox app/window
  scan, bounded title matching, component/action focus, state confirmation,
  and public-safe failure/status documents.
- Browser/privacy selftest recent-record readers: bounded recent-record reader
  callbacks, AT-SPI event lookup by text hash, privacy URL matching by
  origin/path, public-safe event projection, and absence-proof summaries.

The CLI still owns policy reads, capture-gate decisions, browser-context
inference callbacks, calling `typing_ingest`, latest/history writes,
compact-history persistence callbacks, focused-browser selftest callback
binding, browser-privacy selftest recent-history callbacks, and command
rendering.

## Extracted Saved-Text Scan Seam

`abyss_machine.typing_saved_text_adapters` owns the saved-text filesystem scan
adapter boundary for typing intake:

- bounded scan limits, expanded scan roots, directory/file allow/deny filtering,
  and root-missing/seen-file accounting;
- file stat/read/decode rejection for too-large, binary/NUL, empty, low-text,
  and unreadable files;
- state-continuity comparison by path and sha256 so unchanged files do not
  re-ingest;
- ingest kwargs, event summaries, state entries, disabled documents, and
  public-safe scan documents that omit raw text.

The CLI still owns configured policy reads, `typing_ingest` execution,
state/latest/index writes under `/var/lib/abyss-machine`, timer/service status
reads, and command rendering.

## Extracted Nervous Lexical Index Lifecycle Seam

`abyss_machine.nervous_index_adapters` owns the first nervous-local lexical
SQLite/FTS lifecycle adapter boundary:

- source index SQLite connection creation through the public `nervous_index`
  store contract;
- schema SQL file writes beside the host-owned index database;
- non-blocking index file-lock acquisition and active-lock probes;
- public-safe latest JSON writes for index status/build/validate/vacuum
  documents;
- file mode/group normalization for generated index database files;
- vacuum execution (`PRAGMA optimize` and `VACUUM`) through fakeable
  connection/count ports.

`abyss_machine.nervous_index` still owns JSONL discovery/parsing, source-policy
selection, redacted projection, SQLite/FTS schema/search/store contracts,
status/freshness documents, validation envelopes, and vacuum result envelopes.
The CLI still owns privacy/source/config binding, derived event/episode refresh
orchestration, redactor callback binding, systemd timer probes, validation fact
collection, and command rendering.

## Extracted Nervous Semantic Sidecar Seam

`abyss_machine.nervous_semantic_adapters` owns the nervous-local semantic
sidecar lifecycle and runtime execution seam:

- semantic sidecar SQLite connection and schema initialization through the
  public `nervous_semantic` store contract;
- non-blocking semantic sidecar file-lock acquisition and active-lock probes;
- public-safe latest JSON writes for semantic status/build/search/eval
  documents and semantic-maintain latest/history writes;
- source-chunk loading from the lexical SQLite/FTS index through a fakeable
  source DB port without publishing source rows;
- semantic sidecar build-run metadata/provenance transactions and stale-vector
  deletion;
- generated semantic DB file mode/group normalization;
- embedding batch temp JSONL input/output staging under the configured machine
  temp root;
- OpenVINO embedding subprocess command invocation through a fakeable command
  runner port;
- subprocess env, timeout, stdout/stderr/returncode, and output JSONL readback
  mapping into the `nervous_semantic` result contract;
- before/after resource snapshot and resource-profile callback routing;
- cleanup of temporary input/output files without returning raw embedded text.

The CLI still owns nervous semantic config reads, model/python path discovery,
privacy and AI policy gates, resource-launch orchestration for
`semantic-maintain`, build-window orchestration, and command rendering.

## Extracted Nervous Rerank Execution Seam

`abyss_machine.nervous_rerank_adapters` owns the neural rerank runtime
execution seam:

- OpenVINO reranker scorer temp JSON payload staging under the configured
  machine temp root;
- scorer command invocation through a fakeable command runner port;
- subprocess env, timeout, stdout/stderr/returncode, output JSON fallback
  parsing, and local debug input/output path reporting;
- policy-gate callback routing after runtime path checks, preserving missing
  model/scorer/python error order;
- before/after resource snapshot and resource-profile callback routing.

The CLI still owns nervous rerank config reads, python path discovery, concrete
runtime callback binding, and command rendering. Hybrid lexical/semantic source
collection, semantic maintenance assessment, and rerank latest/history writes
move through `nervous_retrieval_adapters`. The neural execution adapter preserves
the existing local debug input/output files; cleanup or retention policy for
those files is a separate local-private temp-artifact slice.

## Extracted Nervous Retrieval/Rerank Live Search Seam

`abyss_machine.nervous_retrieval_adapters` owns the nervous recall/rerank live
search and write-routing seam:

- hybrid rerank limit/candidate normalization from the public index config;
- lexical source collection through a fakeable search port;
- semantic status/config/maintenance assessment and semantic search through
  fakeable ports;
- lexical/semantic result merge, stable source tags, and rerank scoring through
  the `nervous_rerank` contract module;
- neural rerank application through the existing neural execution port;
- public-safe rerank search document assembly, source summaries, and policy
  fields;
- recall pack search-plan dispatch through fakeable lexical/hybrid ports;
- evidence projection and retrieval-pack document assembly through
  `nervous_recall`;
- shared latest/history write routing for rerank search, rerank eval, and
  retrieval packs.

The CLI still owns privacy refusal checks, concrete config/path/callback
binding, and command rendering. The adapter does not publish host search
evidence; generated latest/history files remain host-owned runtime state.

## Extracted AI Runtime Discovery, OpenVINO Runner, And TTS Client Seam

`abyss_machine.ai_runtime_adapters` owns the local-AI runtime discovery seam
and the first bounded OpenVINO benchmark/eval runner seam; `abyss_machine.ai_tts_adapters`
owns the first TTS execution adapter seam:

- configured model-root normalization with null/duplicate suppression;
- OpenVINO python discovery, runtime/device query execution, JSON parsing, and
  absent-runtime/invalid-output envelopes through fakeable `which`, `exists`,
  and command-runner ports;
- RPM package and `ldconfig` availability probes through fakeable command
  ports;
- NPU user-driver version discovery and AI device readiness assembly;
- configured model-root filesystem inventory, skip-directory policy, bounded
  depth/entry limits, OpenVINO/Hugging Face/GGUF classification, and inventory
  document assembly through `ai_runtime_contracts`;
- `llama.cpp` runtime existence/version probes and profile file/storage status
  assembly through fakeable path, command, storage-protection, and
  host-cache-relative ports;
- token-accounting tokenizer/library discovery through fakeable filesystem and
  executable-access ports;
- token-accounting exact-count tokenizer subprocess command/env/timeout/timing
  execution through fakeable runner and clock ports, while count/result privacy
  shapes remain in `ai_runtime_contracts`;
- resident LLM controller command construction, timeout routing, subprocess
  invocation, stdout/stderr/returncode mapping, and no-output JSON error
  envelopes for `abyss-gemma4-spark-resident` through a fakeable command port;
- OpenVINO python package-version probes and kernel-module snapshots through
  fakeable command ports.
- OpenVINO smoke, embedding-eval, and text-eval child-process invocation,
  timeout/env binding, missing-python/model handling, and per-run resource
  profile callback routing through fakeable runner and resource ports.
- OpenVINO benchmark device-plan orchestration, whole-benchmark resource
  sampling, eval suite execution-plan orchestration, policy-denial short-circuit,
  whole-eval resource sampling, benchmark/eval latest and daily JSONL write
  routing, and workload-measurement callback routing through fakeable suite,
  policy, path, writer, and resource ports.
- AI workload store/readmodel routing: workload run JSONL discovery and
  tolerant reads, record-id dedupe append, stats latest writes,
  refresh-from-latest source gating, refresh history appends, taxonomy latest
  writes, and workload status latest writes through fakeable path, writer,
  source, policy, and systemd ports.
- AI core readmodel store routing: devices/models/capabilities/policy/runtime/
  status/report document assembly, resident latest readmodel reads for
  capabilities, runtime/report latest writes, and runtime/report daily history
  appends through fakeable reader, writer, path, clock, and input ports.
- TTS Unix-socket JSON-line client transport, server status/stop request
  exchanges, warm server socket bind/request loop/JSON command dispatch and
  shutdown cleanup, warm Qwen3 OpenVINO runtime import/path injection,
  model-load config construction, model load/unload callback, request-to-SDK
  mapping, generate call, `soundfile` WAV write, synth success/error document
  assembly, synth subprocess cache/env binding, and BabelVox/Qwen3 OpenVINO
  cold synth child-process invocation through fakeable socket, SDK facade,
  runner, path, clock, and environment ports.
- TTS output WAV summary and runtime resource-report assembly through fakeable
  path, clock, resource snapshot, and resource-profile ports.

The CLI still owns concrete `/etc` config loading, command rendering, policy
gate binding, `.aoa` generated-summary reads, STT fixture/dictation transport,
token-accounting profile selection/latest writes, resident LLM parser/result
rendering, broader resource sampling, and live input collection for the core AI
readmodels.
The adapters do not download models, mutate stack repositories, or publish
generated host evidence. Resident service mutation remains an explicit operator
command routed through the resident controller.

## Extracted Dictation Execution Runtime Seam

`abyss_machine.dictation_execution_adapters` owns the explicit-file dictation
transcription runtime seam, the recording lifecycle/process-state seam, the
toggle debounce seam, the read-only audio inspection seam, the transcript
journal policy/IO seam, the clipboard/text insertion execution seam, and the
mic-calibration execution seam:

- runtime model/helper readiness checks before transcription execution;
- warm-server UNIX socket JSON-line request/response transport through a
  fakeable socket port;
- client-side 16 kHz PCM runtime preprocessing for warm-server audio using a
  fakeable command runner and WAV metadata callbacks;
- helper subprocess command invocation, timeout, stdout/stderr/returncode, and
  invalid JSON mapping into `dictation_contracts` transcript result shapes;
- helper runtime environment projection from dictation runtime options;
- recording runtime/state-file path binding, atomic recording-state writes,
  active/stale state reads, and stale-state cleanup;
- `pw-record` command execution through a fakeable process-start port;
- process liveness, recording age, SIGINT/SIGTERM stop escalation, sleep, and
  state unlink through fakeable process/clock/signal ports;
- duplicate-toggle debounce policy, bypass env interpretation, and debounce
  status result construction through fakeable env/status/clock ports;
- WAV stats extraction and recent runtime WAV discovery through public-safe
  filesystem adapters;
- audio-doctor default-source/status probes through fakeable `pactl`/`wpctl`
  command ports, with summary/recommendation still delegated to
  `dictation_contracts`;
- transcript journal enabled/include-failed policy through a fakeable config
  document port;
- transcript journal event assembly around live audio metadata, append-only
  JSONL writes, readable Markdown appends, latest/index JSON writes, and
  latest/tail reads through public-safe filesystem adapters;
- text insertion via `wtype`, `wl-copy`, and `ydotool` through fakeable
  subprocess/session/sleep ports while `dictation_contracts` keeps insertion
  result and key-sequence policy shapes;
- mic-calibration recent/recorded WAV selection, bounded `pw-record`
  invocation, calibration notification callback, WAV inspection, runtime
  recommendation, and optional config apply through fakeable ports.

`abyss_machine.dictation_runtime_adapters` owns the dictation runtime env/path
seam:

- `XDG_RUNTIME_DIR` and `/run/user/$uid` fallback selection;
- runtime dictation directory creation through a fakeable ensure-directory port;
- `ABYSS_DICTATION_SERVER_SOCKET`, `YDOTOOL_SOCKET`, and
  `ABYSS_DICTATION_MAX_SECONDS` translation without reading live env in
  reusable logic.

`abyss_machine.dictation_lock_adapters` owns dictation file-lock execution for
toggle and completion critical sections through bounded lock timeouts.

`abyss_machine.dictation_postprocess_adapters` owns transcript postprocess and
intent glue:

- common transcript fixes;
- command-intent detection and intent-test documents;
- postprocess application with fakeable config and replacements document ports.

`abyss_machine.dictation_notifications_adapters` owns notification policy and
desktop notification execution:

- `ABYSS_DICTATION_NOTIFY` env override and config desktop gate handling;
- `notify-send` command construction and spawning through fakeable ports.

`abyss_machine.dictation_profile_adapters` owns the config/profile discovery
seam:

- config load/default merge/validation fallback and config save metadata through
  fakeable JSON read/write ports;
- concrete profile defaults from the public model-root route;
- env-bound runtime/postprocess option resolution, requested-profile selection,
  auto-selection from fakeable WAV stats, disabled-profile fallback, and runtime
  env projection;
- config/profile read-model documents for `dictation config get` and
  `dictation profile list/get`.

`abyss_machine.dictation_docs_adapters` owns the dictation docs scaffolding
seam:

- daily transcript path projection, paths document, index document, and
  AGENTS.md content rendering;
- root/transcript directory creation, AGENTS.md touch/update, and index JSON
  writes through fakeable filesystem ports.

`abyss_machine.dictation_status_adapters` owns the dictation status read-model
seam:

- status document assembly from supplied config, profile, recording,
  replacements, and journal facts;
- config/replacements/server-socket/latest/model path readiness checks through
  fakeable path-exists ports;
- command readiness booleans for recording, clipboard, insertion, event
  inspection, and audio default-source probes through fakeable command ports;
- ydotool socket readiness, recording/stale-recording projection, and journal
  readiness fields without reading private transcript contents.

The CLI still owns concrete env/config binding, high-level command dispatch,
callback wiring, and command rendering.
The adapters do not persist WAV files in Git or make model weights public;
runtime audio copies remain under the target host runtime directory.

`abyss_machine.dictation_validation_adapters` owns the dictation validation
seam:

- dictation docs/index validation checks through a fakeable docs ensure port;
- transcript latest schema validation and empty-state projection through
  fakeable path/read ports;
- validate latest/history write routing through a fakeable writer port while
  the generic validation envelope stays in `validation_contracts`.

`abyss_machine.dictation_replacements_adapters` owns the dictation replacements
read/write seam:

- replacements document fallback/load/save through fakeable JSON ports;
- list/test documents, text application, and replacement ID projection;
- add/remove mutation flow through fakeable JSON/path/clock ports while
  `dictation_contracts` keeps rule normalization and application semantics.

## Extracted Host Lifecycle Parity Summary

`abyss_machine.host_lifecycle_parity` owns the compact source/install/runtime
parity summary used during release and installed-host closeout:

- source CLI vs installed CLI digest comparison;
- package module and public-seed digest-map counts with bounded samples instead
  of full file lists;
- installed path identity summaries without file contents;
- runtime command JSON projection into status/check/warning/failure counts;
- privacy flags proving raw runtime stdout and raw runtime JSON are omitted.

`scripts/validators/source_install_runtime_parity.py` is the read-only adapter
that binds the contract to concrete host paths and bounded runtime commands
such as `abyss-machine enter --json`, `typing validate`, and
`nervous validate`. It does not install, repair, or mutate host state; failed
content parity is evidence for an install closeout, not an automatic action.

## Extracted Doctor Validate Probe Seam

`abyss_machine.doctor_adapters` owns the first diagnostic-spine live probe seam
for `abyss-machine doctor validate`:

- file presence checks for doctor root, agent card, policy, reports, and user
  systemd unit files;
- compact latest JSON readability checks for doctor and machine-report latest
  documents;
- user systemd timer state projection through a narrow fakeable port;
- bridge command coverage checks for doctor status, paths, reports, validate,
  and safe repair entrypoints.

`abyss_machine.doctor_contracts` still owns the validate document envelope. The
CLI binds the concrete host probes, writes validate latest/history, and renders
command output. Deeper `doctor` status probes remain live adapter debt.

## Extracted Doctor Core Status Probe Seam

`abyss_machine.doctor_adapters` now owns the first `abyss-machine doctor`
status-probe seam:

- platform readiness classification;
- bridge manifest, topology document, change-ledger, and installed binary path
  checks;
- topology and stack-bridge validate summary projection without writing latest
  files;
- command availability checks for `podman`, `rsync`, and `curl`.

The CLI binds the concrete platform, filesystem, command-map, topology validate,
and stack-bridge validate ports. Power/cooling, storage/process, and
snapshot/observability/dictation status checks are split below; nervous, docs,
AI runtime execution, memory, mode, and timer probes remain deeper live adapter
debt.

## Extracted Doctor Power/Cooling Status Probe Seam

`abyss_machine.doctor_adapters` owns the `abyss-machine doctor` power/cooling
status-probe seam:

- power-profiles-daemon and automatic power-profile timer readiness checks;
- thermald readiness check;
- cooling backend projection with fan/platform profile summary and latest path;
- cooling reconcile timer readiness through a fakeable systemd-unit port.

The CLI binds the current `status()` read-model and concrete systemd lookup. The
adapter does not switch power profiles, write cooling state, sample sensors, or
authorize cooling repair; those remain in their subsystem owners and later live
adapter slices.

## Extracted Doctor Storage/Process Status Probe Seam

`abyss_machine.doctor_adapters` owns the `abyss-machine doctor` storage/process
status-probe seam:

- root and `/srv` filesystem readiness projection from compact filesystem facts;
- storage policy readiness projection with the configured policy path;
- storage hook directory readiness projection from the storage hook read-model;
- process snapshot latest freshness projection with the configured latest path.

The CLI binds the current facts document, storage policy reader, storage hook
status reader, and process latest-summary reader. The adapter does not scan
disks, execute storage hooks, inspect `/proc`, run process snapshots, apply
cleanup, or mutate storage/process state.

## Extracted Doctor Snapshot/Observability Status Probe Seam

`abyss_machine.doctor_adapters` owns the `abyss-machine doctor`
snapshot/observability status-probe seam:

- snapper availability, root config, and cleanup timer readiness projection;
- observability topology projection for root, agent entrypoint, and index;
- observability timer readiness projection using the configured timer name;
- observability latest freshness projection using a caller-supplied maximum age.

The CLI binds the current `status()` read-model and observability timer name.
The adapter does not run snapper cleanup, execute the observability collector,
read or write latest files, mutate systemd units, or repair observability
permissions.

## Extracted Doctor Dictation Status Probe Seam

`abyss_machine.doctor_adapters` owns the `abyss-machine doctor` dictation
status-probe seam:

- dictation config, replacement, microphone calibration, and command readiness
  projection from the dictation status read-model;
- fast/default model readiness projection without model discovery;
- hotkey, warm-server, and input-remapper service readiness through fakeable
  systemd-unit ports;
- input-remapper preset presence through a fakeable path-exists port.

The CLI binds the current `status()` read-model, concrete service lookups, and
operator-local preset path. The adapter does not record audio, inspect WAVs,
contact the dictation server, write transcript journals, insert text, mutate
hotkeys, or repair services.

## Extracted Doctor Report IO Seam

`abyss_machine.doctor_adapters` also owns the diagnostic report IO seam:

- local daily markdown path construction for doctor reports and machine
  reports;
- doctor markdown report writes to latest and daily paths;
- machine-report artifact latest reads through a fakeable read port and compact
  `doctor_contracts.artifact_entry` projection;
- machine-report JSON latest/history writes plus latest/daily markdown writes.

`abyss_machine.doctor_contracts` remains the owner of report and machine-report
document shapes. The CLI still binds concrete filesystem writers/readers,
renders command output, and owns safe repair orchestration.

## Extracted Doctor Machine Report Input Seam

`abyss_machine.doctor_adapters` now owns the machine-report input collection
boundary:

- fakeable ports for doctor, memory residency, nervous brief, AI policy latest,
  live AI policy, and compact artifact reads;
- `--no-thermal-sample` AI policy routing that reuses a readable latest policy
  document and falls back to live policy only when the latest document is absent
  or failed;
- compact protected-service projection through
  `doctor_contracts.machine_report_service_summary`;
- machine-report path projection and ordered compact artifact list execution.

The CLI remains the binder for concrete live functions, configured constants,
latest/history writes, and rendering. This seam is read-only input collection; it
does not stop, restart, repair, or mutate host services.

## Extracted Doctor Safe Repair Orchestration Seam

`abyss_machine.doctor_adapters` now owns the safe repair orchestration boundary
for `abyss-machine doctor --repair --safe-only`:

- outer repair gate: `repair`, `safe_only`, and doctor repair policy
  `enabled`;
- execution selection from `safe_actions` only when an action is explicitly
  marked `automatic`;
- fakeable runner ports for semantic maintenance and docs mesh refresh;
- compact result projection for performed repair actions without copying raw
  runner payloads.

The CLI still computes current safe-action need from live status probes and binds
the concrete host refresh functions. The repair seam is limited to generated
read-model refresh routes. Recovery is to rerun the relevant validate/report
command and regenerate the host-owned latest files; it does not authorize
privileged actions, service stops, restarts, project repository mutation, large
downloads, or destructive cleanup.

## Next Extraction Order

1. AI runtime adapters: broader resource sampling and any remaining resident
   LLM readmodel/write orchestration that is still proven to sit in `cli.py`.
   Runtime/model discovery, bounded OpenVINO benchmark/eval runners,
   benchmark/eval suite orchestration and write routing, workload
   store/readmodel write routing, core devices/models/capabilities/policy/
   runtime/status/report readmodel store routing, token-accounting tokenizer
   execution, resident LLM controller execution, the TTS client/server-loop/warm-runtime/
   cold-synth runner, and TTS output audio/resource reporting are already split into
   `ai_runtime_adapters`/`ai_tts_adapters`;
   dictation should only reappear here when a concrete remaining CLI edge has
   been re-inventoried.
2. Diagnostic and host lifecycle adapters: deeper doctor status probes,
   bootstrap dry-run evidence, and richer installed projection closeout.

## Stop Lines

- Do not publish `/etc/abyss-machine`, `/var/lib/abyss-machine`,
  `/srv/abyss-machine`, browser captures, typed text histories, local indexes,
  secrets, or model weights.
- Do not turn validators into hidden behavior owners.
- Do not collapse typing/nervous into a publication simplification; they are
  first-class host organs and must remain opt-in, privacy-gated, and tested.
