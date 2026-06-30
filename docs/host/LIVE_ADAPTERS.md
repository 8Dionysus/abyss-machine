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
| `nervous` | source policy, privacy state, fact/event/episode JSONL, browser history DBs, explicit metadata roots, podman metadata, clipboard, screenshot/window state, semantic/index SQLite stores. | nervous facts/events/episodes/latest, browser-content JSONL/latest, index/semantic status, synthesis/eval/retrieval reports, retention plans, privacy audit records. | browser content capture, GNOME/X11 probes, clipboard reads, retention apply/unlink, semantic embedding subprocesses, reranker subprocesses. | Contracts split across nervous modules; latest/history persistence starts in `typing_nervous_adapters`; browser-content daily path projection, recent duplicate scanning, JSONL append routing, latest write routing, ingest document assembly, Firefox runtime env summary, AT-SPI accessibility-tree traversal/text extraction, AT-SPI capture result assembly, WebSocket frame/connection handling, BiDi session/context/script-evaluation routing, remote-value decode, BiDi capture result/latest routing, Firefox history profile discovery, copied `places.sqlite` recency queries, redacted history-entry assembly, and browser-history fact summary routing live in `nervous_browser_content_adapters`; lexical index lifecycle and status/freshness input collection live in `nervous_index_adapters`; semantic sidecar lifecycle/source loading/latest writes and embedding subprocess execution live in `nervous_semantic_adapters`; synthesis/eval local evidence reads, latest/period/markdown writes, validate latest writes, and eval latest/history routing live in `nervous_synthesis_adapters`; screenshot GNOME-extension, allowlisted DBus, X11 active/game-risk window probes, and capture execution/fact assembly live in `nervous_screenshot_adapters`; clipboard Wayland readiness, `wl-paste` MIME/text reads, backend failure mapping, redacted payload projection, and fact assembly live in `nervous_clipboard_adapters`; retention filesystem scan, symlink-tail guard, dry-run/confirmed unlink, mutation receipts, validate latest write, and latest/history write routing live in `nervous_retention_adapters`; neural rerank subprocess execution lives in `nervous_rerank_adapters`; recall/rerank live search orchestration and retrieval/eval write routing live in `nervous_retrieval_adapters`; most other probes remain CLI edge. |
| `dictation` | audio devices, runtime config/env, runtime paths, transcripts, WAV metadata, recording/server state. | transcript latest/JSONL, dictation index, validation latest. | recording, server transport, clipboard/text insertion, audio runtime subprocesses, desktop notifications. | `dictation_contracts` owns shapes; `dictation_runtime_adapters` owns XDG runtime path/socket/max-duration env translation; `dictation_profile_adapters` owns config load/save, concrete profile defaults, env-bound runtime/postprocess/profile selection, runtime env projection, and config/profile read documents; `dictation_docs_adapters` owns path/index/AGENTS.md documents and dictation docs scaffolding; `dictation_execution_adapters` owns explicit-file transcription via warm-server/helper runtime, client-side 16 kHz preprocessing, recording lifecycle/process-state execution, toggle debounce, WAV inspection/recent-audio scan, audio-doctor `pactl`/`wpctl` probes, transcript journal policy/JSONL/Markdown/latest/index IO, clipboard/text insertion execution, and mic-calibration recording/apply; `dictation_lock_adapters` owns file-lock execution; `dictation_postprocess_adapters` owns transcript postprocess/intent glue; `dictation_notifications_adapters` owns notification policy and `notify-send` command spawning; `dictation_status_adapters` owns status read-model assembly and readiness path/command probes; `dictation_validation_adapters` owns dictation validation checks and validate latest/history write routing; `dictation_replacements_adapters` owns replacements load/save/list/test/add/remove flow. Rendering remains CLI edge. |
| `ai` | runtime config, model/cache roots, package availability, OpenVINO/runtime package probes, tokenizer/model inventories, generated AoA summaries. | AI runtime/status/eval/LLM registry/token-accounting latest and histories. | OpenVINO, tokenizer, STT/TTS, resident LLM, workhorse LLM, and benchmark subprocesses. | `ai_runtime_contracts`, `ai_runtime_adapters`, `ai_tts_contracts`, `ai_tts_adapters`, and `ai_cpu_routing` own contracts, discovery adapters, bounded OpenVINO benchmark/eval child-process runners, subprocess env binding through fakeable environment/root ports, resource snapshot/profile assembly through fakeable memory/thermal/battery/rusage/load ports, STT eval dictation-transport timing/resource envelopes, STT synthetic fixture generation and WAV metadata checks, benchmark/eval suite orchestration and latest/daily write routing, workload JSONL discovery/read/dedupe append plus workload taxonomy/stats/refresh/status write routing, devices/models/capabilities/policy/runtime/status/report readmodel assembly and latest/history write routing, capabilities live input collection through fakeable devices/models/dictation/TTS/LLM registry/resident-latest ports, policy readmodel input collection through fakeable observability/mode/battery/thermal/CPU ports, policy-gate binding through fakeable policy/clock ports, LLM registry/latest/validate readmodel assembly, validate live input collection, and write routing through fakeable ports, token-accounting tokenizer subprocess env/runner execution, token-accounting contract/profiles/latest/count readmodel and store routing, `.aoa` generated-summary session-registry/manifest/index reads plus latest/history write routing, resident LLM controller command/timeout runner execution and JSON/result projection, workhorse LLM controller command/timeout runner execution and JSON/result projection, TTS Unix-socket client transport, server status/stop exchanges, warm server socket/request loop, OpenVINO import/load/generate/write lifecycle, shutdown/unload cleanup, cold TTS synth subprocess env/runner execution, and TTS output audio summary/resource-report assembly; concrete live reader/env source selection and concrete command rendering remain CLI edge. |
| `self-awareness` | stack/runtime latest files, observability probes, generated event/fabric stores, systemd state. | self-awareness timeline/context/episode/brief/query/probe/latest surfaces. | probe/cycle/replay/investigate orchestration and stack handoff checks. | `self_awareness_contracts` owns read-model shapes; orchestration remains CLI edge. |
| `storage/process/memory/mode/cooling` | disk usage, `/proc`, cgroups, sensors, power profile, process tables, systemd state. | status/plan/monitor/latest histories and indexes. | cleanup apply, storage hook subprocesses, resource launch, profile switch, cooling apply, process/container probes. | Contract modules own policy decisions; `storage_adapters` owns the cleanup-plan active-process guard over process snapshots and `/proc` fd targets, allowlisted cleanup apply execution, storage hook directory scan/execution, and storage path/disk inventory measurement through fakeable ports; `process_adapters` owns low-level `/proc` process info collection, CPU jiffy sampling, sanitized Podman container health reads, read-only GNOME Shell desktop-compositor command/proc probes, AT-SPI hard-timeout desktop capture through fakeable proc-root/sysconf/sleep/command/`pyatspi`/subprocess/latest-loader ports, and process thermal attribution/plan read-only orchestration through fakeable proc-root/thermal-map/process-info/game/mode/policy/route/desktop ports; `memory_adapters` owns read-only memory pressure/process/cgroup/residency collection plus memory orchestration target snapshots, Podman inspect/restart execution, local model HTTP probes, cgroup CPU sampling, live locks, rehydrate polling, hotpath probe document assembly/orchestration, hotpath TTS/STT/LLM execution wrappers, and memory-orchestrate candidate/confirmation/preflight/apply/live-authorization safety policy through fakeable ports/documents; `mode_adapters` owns mode-state load/save, `powerprofilesctl` get/set execution, recent GameMode journal probes, external profile-guard input collection, mode plan/status live input collection, and mode reconcile orchestration through fakeable ports; `cooling_adapters` owns platform-profile, Lenovo fan-mode, RAPL-MMIO, package-throttle, kernel fan-error, thermal-zone/cooling-device sysfs sampling, trusted sensor projection, temperature summary/sample, cooling sample-series ports, profile apply orchestration, guarded TFN1 write, fan-validate, fan-series orchestration, and RAPL smoothing decision/state orchestration through fakeable ports; broader live host reads, inventory policy/spec orchestration, broader container orchestration, concrete live binding, latest/history writes, and command rendering remain CLI edge. |
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

## Extracted Storage Guard, Inventory, Hook, And Apply Execution Seam

`abyss_machine.storage_adapters` owns bounded storage cleanup live-adapter
mechanics:

- candidate path text matching across process `cmdline`, `cwd`, `exe`,
  `cgroup`, and file-descriptor targets;
- `/proc/<pid>/fd` target inspection through a fakeable fd-target port;
- process snapshot projection through a fakeable process-snapshot port;
- compact path guard documents with active process refs, fd scan error counts,
  and non-claims that a clear sample is not deletion permission;
- allowlisted cleanup apply execution for package-manager clean, npm cache
  verify/clean, and age-based generated temp cleanup through fakeable
  command-runner, euid, and clock ports;
- hook directory status scans with hidden-file filtering, executable counts,
  disabled suffix accounting, and error projection;
- hook payload serialization, bounded environment projection, subprocess result
  mapping, timeout/OSError mapping, and enforce-block summaries through a
  fakeable hook-runner port;
- filesystem size measurement through a fakeable `du`/command-runner port with
  directory-walk fallback;
- disk usage summaries rooted at the nearest existing ancestor through a
  fakeable disk-usage port;
- storage path status and inventory item measurement including mtime, age,
  symlink, resolve, measured, and size fields;
- home top-level review path scanning with deterministic public-safe ids and no
  automatic cleanup authority.

`abyss_machine.storage_contracts` remains the owner of cleanup action decisions,
protected-root policy, inventory drift, pressure classification, hook
stage/status contracts, and dry-run apply shapes. The CLI still binds storage
inventory spec selection, podman store inputs, memory summaries, configured hook
directories, current environment, current time, the live process snapshot,
storage policy/pressure reads, process guard/preflight orchestration,
latest/history writes, and command rendering.

## Extracted Process Proc Snapshot Seam

`abyss_machine.process_adapters` owns the bounded process `/proc` live-read
mechanics used by process snapshots and game guards:

- `/proc/stat` CPU jiffy parsing;
- per-process `stat`, `status`, `cmdline`, `io`, `cgroup`, `cwd`, `exe`, and
  fd-count reads through a fakeable proc-root port;
- process storage-root matching over command/cwd/exe text;
- process info assembly that delegates game/workload/capability classification
  to `process_contracts`;
- optional interval CPU percentage sampling through fakeable sysconf and sleep
  ports.

`abyss_machine.process_contracts` remains the owner of process role/workload/game
classifiers, game-guard documents, path/latest read models, and snapshot
summary/top-list contracts. The CLI still binds protected game roots, storage
match roots, gamemode status, system summaries, storage hooks, latest/history
writes, broader container orchestration, and rendering.

## Extracted Process Container Health Seam

`abyss_machine.process_adapters` also owns the bounded read-only Podman
container-health probe used by `abyss-machine processes containers`:

- `podman ps -a --format json` execution through a fakeable command runner;
- optional `podman inspect` execution through the same fakeable command port;
- command-missing, command-failure, invalid-JSON, and missing-inspect fallback
  projection;
- container name normalization, label allowlisting, restart/health/exit
  attention-reason classification, and abyss-stack compose/service detection;
- mount and port redaction helpers that omit environment variables, create
  commands, and mount contents while preserving public-safe route facts.

The CLI still binds schema/version/current time, generated latest/history paths,
latest/index writes, and command rendering. This seam does not start, stop,
restart, inspect payload contents beyond sanitized state, or mutate containers.
Other Podman routes such as storage migration preflight, memory orchestration,
self-awareness stack probes, and artifact-reference scans remain in their own
owner lanes until a separate bounded seam is proven.

## Extracted Process Desktop Compositor Probe Seam

`abyss_machine.process_adapters` also owns the read-only command/proc/AT-SPI probe
mechanics used by `abyss-machine processes desktop-compositor`:

- GNOME Shell PID, fd-kind, thread, and CPU jiffy sampling through fakeable
  proc-root/sysconf/sleep ports;
- `systemctl --user`, `gdbus`, `busctl`, `gsettings`, bounded
  `dbus-monitor`, `wmctrl`, `xprop`, `ss`, and `ps` reads through a fakeable
  command runner;
- GNOME display/current-mode projection, shell bus/signal sampling,
  status-notifier projection, Mutter screencast/remote-desktop path summary,
  GNOME Shell extension/Vitals metadata and preference snapshots, X11 window
  context, Wayland socket peer context, and desktop process candidate context;
- desktop-compositor assessment and document assembly, including observe-only
  policy and non-claim text that forbids extension toggles, desktop-quality
  downgrades, process killing, or throttling from the result alone.
- AT-SPI panel telemetry churn sampling through fakeable `pyatspi`, timer,
  signal, and monotonic ports;
- AT-SPI application/window snapshot traversal through fakeable `pyatspi` and
  signal ports;
- bounded AT-SPI window snapshot subprocess probe code plus latest-fallback
  projection through fakeable command-runner and latest-loader ports.

The CLI still binds schema/version/current time, generated path documents,
latest/history/index writes, command rendering, and concrete installed-probe
paths. This seam does not mutate desktop state, toggle GNOME Shell extensions,
change refresh/quality settings, kill processes, or claim a specific visible
window/extension as the cause without separate operator-visible isolation
evidence.

## Extracted Process Thermal Attribution And Plan Seam

`abyss_machine.process_adapters` also owns the read-only thermal process
attribution and new-work plan mechanics used by
`abyss-machine processes thermal-attribution` and
`abyss-machine processes thermal-plan`:

- `/proc/<pid>/task/<tid>/stat` thread CPU sample collection through fakeable
  proc-root, sysconf, sleep, monotonic, and timestamp ports;
- thermal focus CPU projection from the existing AI CPU thermal-map document
  through a fakeable thermal-map port;
- per-thread/per-process CPU-delta aggregation, focus-CPU attribution,
  confidence ranking, CPU distribution, incident classification, and non-claim
  text that keeps attribution as candidate evidence rather than exclusive
  causality proof;
- thermal-plan document assembly through fakeable attribution, thermal-map,
  game-guard, mode, AI-policy, route, battery, and desktop-compositor ports;
- game-guard adjustment for new medium/heavy/sustained work without mutating
  running user, game, or stack processes.

The CLI still binds concrete upstream commands/functions, schema/version/current
time, generated latest/history/index writes, and command rendering. This seam
does not kill, throttle, re-affinitize, lower desktop quality, toggle cooling,
or authorize unattended background work by itself; it only reports facts and
new-work route hints for explicit consumers.

## Extracted Memory Read And Orchestration Seam

`abyss_machine.memory_adapters` owns the bounded memory read IO used by
`abyss-machine memory status|processes|pressure|headroom|residency` and the
memory-orchestration live IO used by `abyss-machine memory orchestrate
idle|confirm|apply`:

- PSI pressure, vmstat, sysctl, swap, zram, zswap, meminfo, and cgroup status
  parsing through fakeable roots/command runners;
- process `smaps_rollup` reads, cgroup memory/swap attribution, Podman
  container index joins, and protected-capability bucket routing through
  fakeable proc-root/cgroup-root/process-info/Podman ports;
- service residency snapshots through fakeable systemd, cgroup, process-info,
  and process-rollup ports;
- Podman container identity detection and sanitized read-only `podman inspect`
  snapshots through fakeable command ports;
- target snapshot assembly through fakeable cgroup, process-info, systemd,
  memory-control, and Podman-snapshot ports;
- local HTTP JSON/status probes for llama.cpp, rerank-api, and OVMS idle/health
  checks through fakeable HTTP ports;
- cgroup `cpu.stat` interval sampling through fakeable cgroup-root, sleep,
  monotonic, and CPU-count ports;
- executor/live lock files under the user runtime directory;
- the narrow live executor command route: `podman restart CONTAINER` or the
  registered rerank-api `POST /admin/unload?exit_process=true` endpoint only;
- post-executor rehydrate polling through fakeable target-snapshot, idle-probe,
  health-summary, sleep, and monotonic ports.
- hotpath probe document assembly/orchestration and hotpath TTS/STT/LLM
  execution wrappers through fakeable synth/transcribe/LLM-runner, residency,
  AI-policy, path-existence, and monotonic ports.
- memory-orchestrate candidate ranking, target identity, confirmation-contract,
  health-route, future-executor, preflight/apply guard summaries, and
  live-authorization safety checks through public-safe fakeable documents.

The CLI still owns memory policy/path binding, latest/history/index writes,
concrete upstream/live port binding, and command rendering. The adapter does not broaden
mutation authority: without the
existing confirm/execute-live/acknowledgement/operator/reason gates no live
restart is possible, and even live execution remains scoped to managed model
containers or the registered rerank-api unload route.

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
- freshness input collection from latest fact/event/episode documents and
  local JSONL line-count history through fakeable reader/count ports;
- index status read-model input collection through fakeable latest, counts,
  freshness, and user service/timer status ports;
- index validation read-model fact collection through fakeable storage route,
  symlink-tail, counts, freshness, scan, and event/episode line-count ports;
- vacuum execution (`PRAGMA optimize` and `VACUUM`) through fakeable
  connection/count ports.

`abyss_machine.nervous_index` still owns JSONL discovery/parsing, source-policy
selection, redacted projection, SQLite/FTS schema/search/store contracts,
status/freshness documents, validation envelopes, and vacuum result envelopes.
The CLI still owns privacy/source/config/path binding, derived event/episode
refresh orchestration, redactor callback binding, concrete status port wiring,
concrete validation port wiring, and command rendering.

## Extracted Nervous Derived Events/Episodes File Seam

`abyss_machine.nervous_events_adapters` owns the local file/read/write adapter
boundary for derived nervous events and episodes:

- facts/events/episodes JSONL root reads through the shared typing/nervous
  local-history reader;
- daily JSONL path selection from observed/start/generated timestamps;
- derived event/episode replacement writes that preserve records with other
  `derived_by` values and report bounded parse/write errors;
- latest build/read envelopes for events and episodes;
- build/validate latest write routing through fakeable writer ports.

`abyss_machine.nervous_events` still owns the stable record shapes,
classification/grouping logic, build documents, and validation documents. The
CLI still owns privacy/global-pause refusal, source-policy/config/path binding,
episode refresh orchestration, and command rendering. The adapter keeps the
public repo at the method/contract layer: it can be tested with fake roots, but
generated `/var/lib/abyss-machine` event/episode evidence stays private host
state.

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

## Extracted Nervous Retention Filesystem/Apply Seam

`abyss_machine.nervous_retention_adapters` owns the nervous-local retention
filesystem and dry-run/apply seam:

- route-root scanning and root-missing projection through public-safe file
  candidate documents;
- symlink-tail route-error detection before any confirmed unlink;
- candidate stat/mtime/size collection without copying file contents;
- dry-run-first apply orchestration where confirmed deletion is blocked if the
  plan is not `ok`;
- protected/latest candidate refusal and mutation receipts with operator
  restore hints;
- public-safe latest/history writes for retention plan/apply documents and
  validate latest writes through fakeable writer ports.

`abyss_machine.nervous_retention` still owns route specs, file-candidate
classification, retention policy, plan/apply/validate result envelopes, and the
privacy-review route. The CLI still owns privacy/config/path binding,
global-pause refusal, and command rendering.

## Extracted Nervous Screenshot Live Capture Seam

`abyss_machine.nervous_screenshot_adapters` owns the screenshot live probe and
capture execution seam:

- GNOME screenshot extension status probing through fakeable command ports and
  stable locale env binding;
- allowlisted GNOME Shell screenshot DBus execution with bounded timeout;
- X11 active-window and game-window-risk probes through fakeable `xprop`,
  process-info, and process-classifier ports;
- game-safe capture execution from the `nervous_screenshot` plan, including
  ImageMagick X11 routes, `grim`, opt-in DBus, and opt-in noisy screenshot
  backends;
- public-safe screenshot fact assembly from file-source and virtual-source
  callbacks without indexing raw pixels.

`abyss_machine.nervous_screenshot` still owns recurring-extension query policy
and capture backend planning. The CLI still owns source-policy binding,
environment flag binding, concrete path/callback binding, process owner
callbacks, fact routing, and command rendering. Browser-history
capture execution remains a separate nervous-local adapter debt.

## Extracted Nervous Clipboard Live Read Seam

`abyss_machine.nervous_clipboard_adapters` owns the clipboard live read and
fact assembly seam:

- source-policy refusal before any command or host probe;
- Wayland clipboard readiness projection from `XDG_RUNTIME_DIR`,
  `WAYLAND_DISPLAY`, and a fakeable socket-exists port;
- `wl-paste --list-types` MIME probing and `wl-paste --no-newline` text reads
  through fakeable command ports;
- Wayland/compositor/display/socket backend failures mapped to source skips
  instead of failed facts;
- redacted text payload projection and virtual-source assembly without binary
  clipboard content capture.

The CLI still owns concrete environment binding, command lookup/runner binding,
redaction callback binding, source-policy callback binding, fact routing, and
command rendering. Browser-content source-policy and capture orchestration
remain separate nervous-local CLI-edge debt.

## Extracted Nervous Browser-Content Store, AT-SPI, BiDi, And History Seam

`abyss_machine.nervous_browser_content_adapters` owns the browser-content local
store, ingest seam, Firefox AT-SPI accessibility-tree capture runtime, and
Firefox WebDriver BiDi/WebSocket capture runtime plus Firefox history capture
runtime:

- daily JSONL path projection from captured/source time using the target host's
  local day boundary;
- record-from-page assembly through `nervous_sources` with fakeable clock,
  UID/GID, schema, version, and text-limit ports;
- recent duplicate detection over bounded JSONL tails using browser-content
  dedupe keys;
- JSONL append routing, latest write routing, write-error projection, and
  ingest-summary document assembly through fakeable write ports.
- AT-SPI capture settings from bounded environment overrides;
- Firefox runtime environment summary through a fakeable `/proc` root;
- `gi.repository.Atspi` loading, desktop/app discovery, Firefox document
  traversal, document attributes, visible text extraction, sensitive field
  detection, document priority, and public-safe capture summaries through
  fakeable ports;
- AT-SPI capture latest write routing through a fakeable latest writer;
- WebSocket URL parsing, handshake, frame encode/decode, JSON send/receive, and
  close/ping handling through fakeable socket ports;
- BiDi session creation/end, context tree flattening/filtering, capture-script
  evaluation, remote-value decode, and public-safe error URL projection;
- BiDi capture result/latest write routing through fakeable socket, BiDi call,
  store, summary, and latest-writer ports;
- Firefox profile `places.sqlite` discovery, temporary copied SQLite reads,
  recent history query/cutoff/limit handling, visit-time normalization, and
  temp-file cleanup through fakeable ports;
- browser-history fact assembly with redacted titles, stripped URL
  query/fragment payloads, content-record callback binding, and virtual-source
  summary routing.

The CLI still owns concrete path constants, clock/user binding,
source-policy/privacy decisions, capture orchestration, latest/live-capture
selection, and command rendering.

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

## Extracted Nervous Synthesis/Eval File Seam

`abyss_machine.nervous_synthesis_adapters` owns the nervous synthesis and eval
local file/read/write seam:

- episode/event/candidate JSONL root reads through fakeable record-reader
  ports;
- latest JSON reads for synthesis and eval validation through fakeable ports;
- synthesis candidate assembly through the `nervous_synthesis` contract module;
- synthesis latest JSON write routing, period JSONL replacement that preserves
  other periods, and daily markdown writes;
- synthesis validation input collection and validate-latest write routing;
- eval run document assembly from already-executed dependency documents plus
  eval latest/history write routing;
- eval validate latest-read and validate-latest write routing.

The CLI still owns global-pause refusal checks, concrete path binding,
dependency command orchestration for `nervous eval`, and command rendering.
The adapter does not publish local nervous evidence; generated state remains
host-owned runtime data.

## Extracted AI Runtime Discovery, STT Fixture, OpenVINO Runner, And TTS Client Seam

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
- LLM registry assembly, registry latest/history routing, latest readmodel
  reads, and LLM validate document/input-collection/write routing through
  fakeable runtime, profile, reader, writer, path, path-check, JSON-check,
  token-profile, and clock ports;
- token-accounting tokenizer/library discovery through fakeable filesystem and
  executable-access ports;
- token-accounting exact-count tokenizer subprocess command/env/timeout/timing
  execution through fakeable runner and clock ports, while count/result privacy
  shapes remain in `ai_runtime_contracts`;
- token-accounting contract/profiles/latest/count readmodel assembly plus
  latest/history write routing through fakeable registry, tokenizer resolver,
  reader, writer, path, subprocess, environment, and clock ports;
- resident LLM controller command construction, timeout routing, subprocess
  invocation, stdout/stderr/returncode mapping, and no-output JSON error
  envelopes for `abyss-gemma4-spark-resident` through a fakeable command port;
- workhorse LLM controller command construction, timeout routing, subprocess
  invocation, stdout/stderr/returncode mapping, and no-output JSON error
  envelopes for `abyss-gemma4-e4b-harness` through a fakeable command port;
- resident/workhorse controller result projection: JSON stdout parsing, bounded
  invalid-JSON error documents, no-output fallback, and text-mode stdout/stderr
  selection through public-safe result envelopes;
- STT eval dictation-client transport orchestration, per-profile monotonic
  timing, before/after resource snapshots, and client-side resource-profile
  envelopes through fakeable transport, clock, and resource ports, while
  scoring/result shapes remain in `ai_runtime_contracts`;
- STT synthetic fixture generation: fixture directory creation, existing WAV
  reuse checks, `espeak-ng` command execution, optional `ffmpeg` resampling,
  raw WAV replace/cleanup, and duration/sample-rate metadata reads through
  fakeable filesystem, command, and WAV metadata ports;
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
- AI capabilities live input collection: devices/models/dictation/TTS eval and
  success/LLM registry callbacks, resident latest path binding, resident latest
  JSON reads, and capabilities latest writes through fakeable reader, writer,
  callback, path, clock, and input ports.
- AI policy readmodel input collection: observability status/latest, mode
  status, battery fallback, thermal-policy snapshot, and CPU thermal-map
  selection through fakeable ports while the policy decision contract remains
  in `ai_runtime_contracts`.
- AI policy-gate binding: `ai_policy(write_latest=True)` callback routing,
  generated-at binding, declared-class/operation/force/class-level forwarding,
  and gate document assembly through fakeable policy and clock ports while the
  gate contract remains in `ai_runtime_contracts`.
- AI env/resource binding: AI subprocess environment construction through
  fakeable environment/root ports, resource snapshot envelope assembly through
  fakeable memory/thermal/battery/rusage/load ports, and resource-profile
  document forwarding while the live `/proc`, sensor, battery, rusage, loadavg,
  and `os.environ` readers remain CLI-owned concrete ports.
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

The CLI still owns concrete `/etc` config loading, command rendering,
token-accounting live text input binding, and concrete live reader/env source
implementations for the core AI readmodels.
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
- runtime closeout command catalog, profile selection, de-duplication, and
  fake-runner collection for base/read profiles and explicit `*-refresh`
  typing/nervous, storage, diagnostic, AI, and AI LLM closeout profiles;
- runtime command effect labels that separate read-only checks from commands
  that refresh latest/readmodel state;
- privacy flags proving raw runtime stdout and raw runtime JSON are omitted.

`scripts/validators/source_install_runtime_parity.py` binds the contract to
concrete host paths and subprocess invocation. It does not own the runtime
command law and does not install or repair host state. Default/read profiles are
read-only; `*-refresh` profiles require `--allow-runtime-refresh` because they
may update live latest/readmodel state. Failed content parity is evidence for an
install closeout, not an automatic action.

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

1. Storage/process/memory/mode/cooling adapters: continue with concrete
   mutation-safety seams after the storage cleanup guard/apply execution
   and storage hook/inventory measurement plus process `/proc` snapshot,
   container-health, desktop-compositor command/proc/AT-SPI, and thermal
   attribution/plan adapters plus memory read/orchestration adapters and the
   first mode mutation/reconcile adapters and cooling host-control/TFN/RAPL orchestration adapters.
   Continue with broader container orchestration and write-routing seams only
   when the fakeable live port is clear. Keep
   dry-run/preflight and operator intent ahead of every mutating route.
2. Self-awareness live orchestration adapters: split probe/cycle/replay/
   investigate execution only when a fakeable live probe/readmodel port proves a
   reusable center still sits in CLI.
3. Further AI runtime adapters: only after a fresh inventory proves a concrete
   reusable center still sits in `cli.py`.
   Runtime/model discovery, bounded OpenVINO benchmark/eval runners,
   benchmark/eval suite orchestration and write routing, workload
   store/readmodel write routing, core devices/models/capabilities/policy/
   runtime/status/report readmodel store routing, LLM registry/latest/validate
   store routing plus validate input collection, token-accounting tokenizer
   execution plus token-accounting store/readmodel routing, capabilities input
   collection, policy input collection, resource snapshot/profile assembly,
   subprocess env binding, resident and workhorse LLM controller execution,
   STT eval dictation-transport timing/resource envelopes, the TTS client/
   server-loop/warm-runtime/cold-synth runner, and TTS output audio/resource
   reporting are already split into `ai_runtime_adapters`/`ai_tts_adapters`;
   concrete live readers and command rendering stay in CLI by design unless a
   reusable adapter center is proven.

## Stop Lines

- Do not publish `/etc/abyss-machine`, `/var/lib/abyss-machine`,
  `/srv/abyss-machine`, browser captures, typed text histories, local indexes,
  secrets, or model weights.
- Do not turn validators into hidden behavior owners.
- Do not collapse typing/nervous into a publication simplification; they are
  first-class host organs and must remain opt-in, privacy-gated, and tested.
