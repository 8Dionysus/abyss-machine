# Landing Log

- Initial skeleton: package created to route local nervous work.
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
