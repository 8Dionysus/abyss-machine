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
