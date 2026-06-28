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
- Neural rerank execution seam: `abyss_machine.nervous_rerank_adapters` owns
  OpenVINO scorer temp-payload staging, runner invocation, stdout/output JSON
  parsing, policy-gate callback routing, debug path reporting, and
  resource-profile callback routing. CLI still owns lexical/semantic source
  collection, semantic maintenance assessment, latest/history writes, and
  command rendering.
