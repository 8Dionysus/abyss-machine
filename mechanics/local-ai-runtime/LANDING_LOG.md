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
- Extracted workhorse LLM controller runner execution into
  `abyss_machine.ai_runtime_adapters`; `abyss-gemma4-e4b-harness` command
  construction, timeout routing, subprocess invocation, stdout/stderr/
  returncode mapping, and no-output JSON error envelopes now pass through a
  fakeable command port. CLI remains the argparse binding and rendering edge.
- Extracted resident/workhorse LLM controller result projection into
  `abyss_machine.ai_runtime_adapters`; JSON stdout parsing, bounded invalid-
  JSON error documents, no-output fallback, and text-mode stdout/stderr
  selection now pass through public-safe result envelopes. CLI remains the
  print/argparse/dispatch edge.
- Extracted AI policy-gate binding into
  `abyss_machine.ai_runtime_adapters`; `ai_policy(write_latest=True)` callback
  routing, generated-at binding, declared class/operation/force/class-level
  forwarding, and gate document assembly now pass through fakeable policy and
  clock ports. CLI remains the concrete policy-readmodel/dispatch/rendering
  edge.
- Extracted STT eval dictation transport into
  `abyss_machine.ai_runtime_adapters`; per-profile dictation-client calls,
  monotonic timing, before/after resource snapshots, and client-side
  resource-profile envelopes now pass through fakeable transport, clock, and
  resource ports. CLI remains the eval config, dispatch, and rendering edge.
- Extracted STT synthetic fixture generation into
  `abyss_machine.ai_runtime_adapters`; fixture directory creation, existing WAV
  reuse, `espeak-ng` execution, optional `ffmpeg` resampling, raw WAV
  replace/cleanup, and WAV metadata reads now pass through fakeable filesystem,
  command, and metadata ports. CLI remains the eval config, dispatch, and
  rendering edge.
- Extracted `.aoa` token-accounting generated-summary routing into
  `abyss_machine.ai_runtime_adapters`; session-registry reads, session
  manifest/index fallback reads, generated-summary sanitization, outside-root
  rejection, registry hashing, and latest/history writes now pass through
  fakeable reader, writer, hash, root-check, path, and clock ports. CLI remains
  the argument/env binding, command dispatch, and rendering edge.
- Initial skeleton: package created to route host-managed AI runtime work.
