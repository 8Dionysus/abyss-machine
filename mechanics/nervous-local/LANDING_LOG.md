# Landing Log

- Initial skeleton: package created to route local nervous work.
- Lexical index lifecycle seam: `abyss_machine.nervous_index_adapters` owns
  source-index DB connection binding, schema file writes, file locks,
  active-lock probes, latest writes, generated DB file mode/group normalization,
  and vacuum execution. CLI still owns config/privacy/source binding, redactor
  callback binding, derived refresh orchestration, timer probes, validation
  fact collection, and command rendering.
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
  and ingest document assembly through fakeable ports. CLI still owns concrete
  path/time/user binding, AT-SPI/BiDi capture runtime callbacks,
  source-policy/privacy orchestration, and rendering.
