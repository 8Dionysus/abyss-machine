# Landing Log

- Initial skeleton: package created to route local nervous work.
- Semantic embedding execution seam: `abyss_machine.nervous_semantic_adapters`
  owns embedding subprocess temp-file staging, runner invocation, output
  readback, cleanup, and resource-profile callback routing. CLI still owns
  source-index locks, privacy/policy gates, sidecar/latest writes, and command
  rendering.
