# Landing Log

- Extracted the first TTS execution adapter seam into
  `abyss_machine.ai_tts_adapters`; Unix-socket JSON-line client transport,
  server status/stop exchanges, synth subprocess cache/env binding, and
  BabelVox/Qwen3 OpenVINO cold synth child-process invocation now pass through
  fakeable ports. CLI remains the concrete profile/config/policy/latest,
  resident server loop, audio summary, resource-reporting, and rendering edge.
- Extracted bounded OpenVINO benchmark/eval runner execution into
  `abyss_machine.ai_runtime_adapters`; smoke, embedding-eval, and text-eval
  child-process invocation, timeout/env binding, missing-python/model handling,
  and per-run resource-profile callback routing now pass through fakeable
  ports. CLI remains the concrete config/policy/latest/suite orchestration and
  rendering edge.
- Extracted local-AI runtime discovery into
  `abyss_machine.ai_runtime_adapters`; model-root normalization, OpenVINO
  runtime probes, RPM/ldconfig/NPU driver discovery, model inventory walks,
  `llama.cpp` runtime/profile probes, tokenizer/library discovery, OpenVINO
  python package-version probes, and kernel-module snapshots now route through
  fakeable ports. CLI remains the concrete binding/latest-write/execution edge.
- Extracted token-accounting store/readmodel routing into
  `abyss_machine.ai_runtime_adapters`; contract/profile/latest/count document
  assembly and latest/history writes now pass through fakeable registry,
  tokenizer resolver, reader, writer, path, subprocess, environment, and clock
  ports. CLI remains the concrete registry/env/text/command rendering edge.
- Extracted LLM registry/latest/validate store/readmodel routing into
  `abyss_machine.ai_runtime_adapters`; registry document assembly,
  latest/history writes, latest reads, validate contract-check assembly, and
  validate latest writes now pass through fakeable runtime, profile,
  token-profile, reader, writer, path, and clock ports. CLI remains the
  concrete config/path/validation-input/command rendering edge.
- Initial skeleton: package created to route host-managed AI runtime work.
