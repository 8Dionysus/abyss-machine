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

AI runtime adapters should own concrete subprocess execution, cache/runtime
path translation, model/tool discovery, and resource-sampling evidence. Keep
model weights, benchmark outputs, and generated runtime state outside Git; only
plans, contracts, and bounded summaries belong in the public seed.

### Landing log

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
  and latest/tail reads through public-safe filesystem ports. CLI still owns
  validation/latest writes and rendering.
- Extracted dictation clipboard/text insertion execution into
  `abyss_machine.dictation_execution_adapters`; the adapter owns `wtype`,
  `wl-copy`, and `ydotool` execution through fakeable subprocess/session/sleep
  ports while `dictation_contracts` keeps insertion result and key-sequence
  policy shapes. CLI still owns validation/latest writes and rendering.
- Extracted dictation mic-calibration execution into
  `abyss_machine.dictation_execution_adapters`; the adapter owns recent/recorded
  WAV selection, bounded `pw-record` execution, notification callback routing,
  WAV inspection, runtime recommendation, and optional config apply through
  fakeable ports. CLI still owns validation/latest writes and rendering.
- Extracted dictation profile/config discovery into
  `abyss_machine.dictation_profile_adapters`; the adapter owns config
  load/save, concrete profile defaults, env-bound runtime/postprocess/profile
  selection, runtime env projection, and config/profile read documents through
  fakeable ports. CLI still owns postprocess glue, replacements reads/writes,
  validation/latest writes, and rendering.
- Extracted dictation docs scaffolding into
  `abyss_machine.dictation_docs_adapters`; the adapter owns daily transcript
  path projection, paths/index/AGENTS.md documents, directory creation,
  AGENTS.md touch/update, and index JSON writes through fakeable ports. CLI
  still owns validation/latest writes, replacements read/write glue, and
  rendering.
- Extracted dictation status read-model assembly into
  `abyss_machine.dictation_status_adapters`; the adapter owns config,
  replacements, server-socket, transcript-latest, model path, command, ydotool
  socket, audio default-source, recording, and journal readiness projection
  through fakeable ports. CLI still owns validation/latest writes,
  replacements read/write glue, postprocess glue, notification flow, and
  rendering.

### Next route

Use `storage-routing` for caches and `host-facts` for capability reports.
