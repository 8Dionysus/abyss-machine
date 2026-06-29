# Local AI Runtime Mechanic

## Mechanic card

Local AI runtime owns host-managed AI helper processes and runtime placement
that are not `abyss-stack` service substrate.

### Trigger

Host AI helper tools, model runtime caches, accelerator probes, and ai-local
profile changes.

### abyss-machine owns

Host resource guards, runtime/cache placement rules, helper scripts, and local
capability evidence.

### Stronger owner split

`abyss-stack` owns runtime substrate services. Model providers own model
licenses. Operators own downloads and cache retention.

### Inputs

Host capabilities, model paths, runtime roots, resource policy, operator intent.

### Outputs

Local helper processes, runtime reports, resource warnings, and cache routing.

### Must not claim

Model weights are public source, a benchmark is portable truth, or a local AI
helper is stack service health.

### Validation

Use dry-run resource planning and public boundary scans.

### Live adapter route

`abyss_machine.ai_runtime_adapters` owns the local-AI discovery seam and the
first bounded OpenVINO runner seam: model-root normalization, OpenVINO
runtime/package/NPU driver probes, model inventory walks, `llama.cpp`
runtime/profile file probes, tokenizer/library discovery, OpenVINO python
package versions, kernel-module snapshots, and OpenVINO smoke/embedding/text
child-process execution through fakeable ports. Remaining AI runtime adapters
should focus on TTS server/audio execution, resident LLM execution, tokenizer
subprocess execution, and broader resource-sampling evidence. Keep model
weights, benchmark outputs, and generated runtime state outside Git; only
plans, contracts, and bounded summaries belong in the public seed.

### Landing log

- Extracted local-AI runtime discovery into
  `abyss_machine.ai_runtime_adapters`; the adapter owns model-root
  normalization, OpenVINO runtime probes, RPM/ldconfig/NPU driver discovery,
  model inventory filesystem walks, `llama.cpp` runtime/profile probes,
  tokenizer/library discovery, OpenVINO python package-version probes, and
  kernel-module snapshots through fakeable ports. CLI still owns concrete
  config binding, latest/history writes, policy-gated benchmark/eval/TTS
  execution, resource sampling, `.aoa` reads, and rendering.
- Extracted bounded OpenVINO benchmark/eval runner execution into
  `abyss_machine.ai_runtime_adapters`; the adapter owns smoke,
  embedding-eval, and text-eval child-process invocation, timeout/env binding,
  missing-python/model handling, and per-run resource-profile callback routing
  through fakeable ports. CLI still owns concrete config binding, policy gates,
  suite/device orchestration, latest/history writes, `.aoa` reads, STT/TTS/
  resident/tokenizer execution, and rendering.
- Extracted explicit-file dictation transcription runtime into
  `abyss_machine.dictation_execution_adapters`; the adapter owns warm-server
  socket transport, client-side 16 kHz runtime preprocessing, helper subprocess
  invocation, and helper runtime env projection through fakeable ports.
- Extracted dictation recording lifecycle/process-state execution into
  `abyss_machine.dictation_execution_adapters`; the adapter owns runtime
  recording state IO, active/stale detection, process start, stop signalling,
  and state cleanup through fakeable ports.
- Extracted dictation audio inspection and audio-doctor probes into
  `abyss_machine.dictation_execution_adapters`; the adapter owns WAV stats,
  recent runtime WAV discovery, and `pactl`/`wpctl` probe execution through
  fakeable ports. CLI still owns rendering.
- Extracted dictation transcript journal IO into
  `abyss_machine.dictation_execution_adapters`; the adapter owns audio metadata
  shaping, append-only JSONL/Markdown journal writes, latest/index JSON writes,
  latest/tail reads, and journal enabled/include-failed policy through
  public-safe filesystem/config ports. CLI still owns rendering.
- Extracted dictation runtime env/path translation into
  `abyss_machine.dictation_runtime_adapters`; the adapter owns XDG runtime root
  fallback, runtime directory creation, server socket override, ydotool socket
  projection, and max-duration env translation through fakeable ports. CLI
  still binds the concrete process environment and uid.
- Extracted dictation lock execution into
  `abyss_machine.dictation_lock_adapters`; the adapter owns bounded file locks
  for toggle and completion critical sections through fakeable lock paths.
- Extracted dictation toggle debounce policy into
  `abyss_machine.dictation_execution_adapters`; the adapter owns bypass env
  interpretation and debounce result construction through fakeable env/status
  ports while CLI still owns high-level start/stop/stale orchestration.
- Extracted dictation clipboard/text insertion execution into
  `abyss_machine.dictation_execution_adapters`; the adapter owns `wtype`,
  `wl-copy`, and `ydotool` execution through fakeable subprocess/session/sleep
  ports while `dictation_contracts` keeps insertion result and key-sequence
  policy shapes. CLI still owns rendering.
- Extracted dictation mic-calibration execution into
  `abyss_machine.dictation_execution_adapters`; the adapter owns recent/recorded
  WAV selection, bounded `pw-record` execution, notification callback routing,
  WAV inspection, runtime recommendation, and optional config apply through
  fakeable ports. CLI still owns rendering.
- Extracted dictation profile/config discovery into
  `abyss_machine.dictation_profile_adapters`; the adapter owns config
  load/save, concrete profile defaults, env-bound runtime/postprocess/profile
  selection, runtime env projection, and config/profile read documents through
  fakeable ports. CLI still owns rendering.
- Extracted dictation postprocess and intent glue into
  `abyss_machine.dictation_postprocess_adapters`; the adapter owns common
  transcript fixes, command-intent detection, intent-test documents, and
  postprocess application through fakeable config/replacements ports.
- Extracted dictation notification policy and desktop notification spawning into
  `abyss_machine.dictation_notifications_adapters`; the adapter owns env/config
  notification gating, `notify-send` command construction, and spawn execution
  through fakeable ports.
- Extracted dictation docs scaffolding into
  `abyss_machine.dictation_docs_adapters`; the adapter owns daily transcript
  path projection, paths/index/AGENTS.md documents, directory creation,
  AGENTS.md touch/update, and index JSON writes through fakeable ports. CLI
  still owns rendering.
- Extracted dictation status read-model assembly into
  `abyss_machine.dictation_status_adapters`; the adapter owns config,
  replacements, server-socket, transcript-latest, model path, command, ydotool
  socket, audio default-source, recording, and journal readiness projection
  through fakeable ports. CLI still owns rendering.
- Extracted dictation validation/latest routing into
  `abyss_machine.dictation_validation_adapters`; the adapter owns dictation
  docs/index validation checks, transcript latest validation/empty-state
  checks, and validate latest/history write routing through fakeable ports. CLI
  still owns rendering.
- Extracted dictation replacements read/write flow into
  `abyss_machine.dictation_replacements_adapters`; the adapter owns
  replacements document fallback/load/save, list/test documents, text
  application, and add/remove mutation flow through fakeable JSON/path/clock
  ports while `dictation_contracts` keeps replacement rule normalization and
  application semantics. CLI still owns rendering.

### Next route

Use `storage-routing` for caches and `host-facts` for capability reports.
