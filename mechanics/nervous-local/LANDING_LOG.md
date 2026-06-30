# Landing Log

- Initial skeleton: package created to route local nervous work.
- Lexical index lifecycle seam: `abyss_machine.nervous_index_adapters` owns
  source-index DB connection binding, schema file writes, file locks,
  active-lock probes, latest writes, generated DB file mode/group normalization,
  and vacuum execution. At that landing, CLI still owned config/privacy/source
  binding, redactor callback binding, derived refresh orchestration, timer
  probes, validation fact collection, and command rendering.
- Lexical index status/freshness input seam:
  `abyss_machine.nervous_index_adapters` owns latest fact/event/episode freshness
  reads, local JSONL history line counts, and index status latest/counts/
  freshness/service/timer fact collection through fakeable ports. At that
  landing, CLI still owned config/privacy/source/path binding, redactor callback
  binding, derived refresh orchestration, validation fact collection, concrete
  port wiring, and command rendering.
- Lexical index validation input seam:
  `abyss_machine.nervous_index_adapters` owns validation storage-route checks,
  symlink-tail probe invocation, DB counts/freshness reads, bounded index scan,
  and event/episode JSONL line-count facts through fakeable ports. CLI still owns
  config/privacy/source/path binding, redactor callback binding, derived refresh
  orchestration, concrete validation port wiring, latest writes, and command
  rendering.
- Lexical index SQLite FTS probe seam:
  `abyss_machine.nervous_index_adapters` owns SQLite FTS5 runtime capability
  probing through a fakeable in-memory connection port. CLI keeps the command
  preflight/policy binding and rendering paths, while the concrete SQLite probe
  no longer lives in command code.
- Lexical index symlink-tail probe seam:
  `abyss_machine.nervous_index_adapters` owns index-route symlink-tail
  filesystem probing through a fakeable path probe. CLI keeps the compatibility
  wrapper, validation port binding, policy gates, latest writes, and rendering,
  while the concrete symlink traversal no longer lives in command code.
- Lexical index DB-count read seam:
  `abyss_machine.nervous_index_adapters` owns source-index DB count reads
  through a fakeable count port. CLI keeps the compatibility wrapper, call-site
  binding, policy gates, latest writes, and rendering.
- Lexical index bounded-scan seam:
  `abyss_machine.nervous_index_adapters` owns bounded index scan dispatch
  through a fakeable scan port. CLI keeps compatibility wrapper and path/query
  binding for validation and typing nervous-processing fallback routes.
- Lexical index search-dispatch seam:
  `abyss_machine.nervous_index_adapters` owns index-search read-meta,
  freshness, refusal, option, and search-runner dispatch through fakeable ports.
  `abyss_machine.nervous_index` keeps search option/refusal/result contracts,
  while CLI keeps config/privacy/path binding, command dispatch, and rendering.
- Lexical index build source-input seam:
  `abyss_machine.nervous_index_adapters` owns index build source-root to
  build-document assembly: source-file discovery, JSONL source-record loading,
  enabled-source calculation, redacted projection, and build document creation
  through fakeable ports. `abyss_machine.nervous_index` still owns the
  JSONL/projection/document contracts, while CLI owns config/privacy/path
  binding, derived refresh orchestration at that landing, redactor callback
  binding, concrete build port wiring, latest writes, and command rendering.
- Lexical index build derived-refresh seam:
  `abyss_machine.nervous_index_adapters` owns the optional event/episode refresh
  orchestration that precedes an index build through fakeable event-build,
  episode-build, and summary ports. CLI still owns config/privacy/path binding,
  redactor callback binding, concrete build port wiring, latest writes, and
  command rendering; event/episode record contracts remain in their own
  nervous-local modules.
- Lexical index build write-stage seam:
  `abyss_machine.nervous_index_adapters` owns the SQLite write stage under the
  index lock: semantic pre-write deferral, DB connect/init/schema write, meta
  construction, content replacement, generated DB file-mode normalization,
  counts, and success/error wrapping through fakeable ports. CLI still owns
  config/privacy/source/path binding, derived refresh orchestration at that
  landing, redactor callback binding, concrete build port wiring, latest writes,
  and command rendering.
- Semantic embedding execution seam: `abyss_machine.nervous_semantic_adapters`
  owns embedding subprocess temp-file staging, runner invocation, output
  readback, cleanup, and resource-profile callback routing. CLI still owns
  source-index locks, privacy/policy gates, sidecar/latest writes, and command
  rendering.
- Semantic sidecar lifecycle seam: `abyss_machine.nervous_semantic_adapters`
  owns semantic DB connection/init/counts, file locks/active-lock probes,
  source-chunk loading from the lexical index, latest and semantic-maintain
  latest/history writes, build-run metadata/provenance transactions, generated
  DB mode/group normalization, and embedding execution. CLI still owns semantic
  config/model/python binding, privacy/policy gates, resource-launch
  orchestration, build-window orchestration, and command rendering.
- Neural rerank execution seam: `abyss_machine.nervous_rerank_adapters` owns
  OpenVINO scorer temp-payload staging, runner invocation, stdout/output JSON
  parsing, policy-gate callback routing, debug path reporting, and
  resource-profile callback routing. CLI still owns lexical/semantic source
  collection, semantic maintenance assessment, latest/history writes, and
  command rendering.
- Retrieval/rerank live search seam: `abyss_machine.nervous_retrieval_adapters`
  owns lexical/semantic search-port collection, semantic maintenance assessment
  routing, hybrid rerank result assembly, recall search-plan dispatch,
  retrieval-pack assembly through `nervous_recall`, and latest/history write
  routing for rerank search, rerank eval, and retrieval packs. CLI still owns
  privacy refusal binding, concrete config/path/callback binding, and command
  rendering.
- Synthesis/eval local file seam: `abyss_machine.nervous_synthesis_adapters`
  owns episode/event/candidate JSONL root reads, latest reads, synthesis
  latest/period JSONL/markdown writes, synthesis validate latest routing, eval
  latest/history routing, and eval validate latest routing through fakeable
  ports. CLI still owns privacy refusal binding, concrete paths, eval
  dependency command orchestration, and rendering.
- Screenshot live capture seam: `abyss_machine.nervous_screenshot_adapters`
  owns GNOME extension status probes, allowlisted DBus screenshot execution,
  X11 active/game-risk window probes, game-safe capture command execution, and
  public-safe screenshot fact assembly through fakeable ports. CLI still owns
  source-policy/env/path binding, process callbacks, fact routing, and
  rendering.
- Clipboard live read seam: `abyss_machine.nervous_clipboard_adapters` owns
  Wayland clipboard readiness projection, `wl-paste` MIME/text command
  execution, Wayland backend failure-to-skip mapping, redacted payload
  projection, and public-safe clipboard fact assembly through fakeable ports.
  CLI still owns concrete env binding, source-policy/redaction callbacks, fact
  routing, and rendering.
- Browser-content local store seam:
  `abyss_machine.nervous_browser_content_adapters` owns daily JSONL path
  projection, record-from-page callback binding, bounded recent duplicate
  scanning, JSONL append routing, latest write routing, write-error projection,
  and ingest document assembly through fakeable ports. At that landing, CLI
  still owned concrete path/time/user binding, AT-SPI/BiDi capture runtime
  callbacks, source-policy/privacy orchestration, and rendering.
- Browser-content AT-SPI capture runtime seam:
  `abyss_machine.nervous_browser_content_adapters` owns bounded AT-SPI capture
  settings, fakeable Firefox runtime environment summary, `gi.repository.Atspi`
  loading, Firefox accessibility-tree app/document traversal, document
  attribute reads, visible text extraction, sensitive-field detection, document
  priority, capture result assembly, and latest write routing through fakeable
  ports. At that landing, CLI still owned concrete path/time/user binding,
  source-policy/privacy orchestration, BiDi/WebSocket and browser-history
  capture execution, and rendering.
- Browser-content BiDi/WebSocket capture runtime seam:
  `abyss_machine.nervous_browser_content_adapters` owns WebSocket URL parsing,
  handshake, frame encode/decode, JSON send/receive, close/ping handling, BiDi
  session creation/end, context tree flattening/filtering, capture-script
  evaluation, remote-value decode, public-safe error URL projection, capture
  result assembly, and latest routing through fakeable socket, BiDi call, store,
  summary, and latest-writer ports. CLI still owns concrete path/time/user
  binding, source-policy/privacy orchestration, browser-history capture
  execution, capture orchestration, and rendering.
- Browser-content browser-history capture runtime seam:
  `abyss_machine.nervous_browser_content_adapters` owns Firefox profile
  `places.sqlite` discovery, temporary copied SQLite reads, recent history
  query/cutoff/limit handling, visit-time normalization, temp cleanup, duplicate
  URL suppression, redacted title/URL payload assembly, content-record callback
  binding, browser-history fact summary assembly, and virtual-source routing
  through fakeable ports. CLI still owns concrete path/time/user binding,
  source-policy/privacy orchestration, latest/live-capture selection, and
  rendering.
