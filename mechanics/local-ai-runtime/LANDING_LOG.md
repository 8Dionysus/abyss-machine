# Landing Log

- Extracted local-AI runtime discovery into
  `abyss_machine.ai_runtime_adapters`; model-root normalization, OpenVINO
  runtime probes, RPM/ldconfig/NPU driver discovery, model inventory walks,
  `llama.cpp` runtime/profile probes, tokenizer/library discovery, OpenVINO
  python package-version probes, and kernel-module snapshots now route through
  fakeable ports. CLI remains the concrete binding/latest-write/execution edge.
- Initial skeleton: package created to route host-managed AI runtime work.
