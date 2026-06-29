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
child-process execution plus token-accounting tokenizer subprocess
command/env/timeout/timing execution, resident LLM controller
command/timeout/subprocess execution plus JSON/result projection, and workhorse
LLM controller command/timeout/subprocess execution plus JSON/result
projection, AI subprocess env binding through fakeable environment/root ports,
resource snapshot/profile assembly through fakeable memory/thermal/battery/
rusage/load ports, policy readmodel input collection through fakeable
observability/mode/battery/thermal/CPU ports, benchmark/eval suite orchestration,
STT eval dictation-client transport timing/resource envelopes, whole-command
resource before/after sampling, STT synthetic fixture directory/path setup,
`espeak-ng`/`ffmpeg` execution, raw WAV cleanup, WAV metadata reads,
latest/daily JSONL write routing, workload-measurement callback routing,
workload run JSONL discovery/read/dedupe append, refresh-from-latest source
gating, and workload taxonomy/stats/refresh/status write routing, LLM
registry/latest/validate store/readmodel routing, plus token-accounting
contract/profiles/latest/count store/readmodel routing and `.aoa`
generated-summary session-registry/manifest/index reads plus latest/history
write routing, capabilities input collection through fakeable devices/models/
dictation/TTS/LLM registry/resident-latest ports, plus policy-gate
callback/clock/class-level binding through fakeable ports.
`abyss_machine.ai_tts_adapters` owns the first TTS execution seam: Unix-socket
client transport, server status/stop request exchange, warm server
socket/request loop, Qwen3 OpenVINO import/load/generate/write lifecycle,
shutdown/unload cleanup, synth subprocess cache/env binding, and cold
BabelVox/Qwen3 OpenVINO synth child-process invocation plus output WAV summary
and synth runtime resource-report assembly. Core devices/models/capabilities/
policy/runtime/status/report readmodel assembly and store routing also live in
`ai_runtime_adapters`. Remaining AI runtime adapters should focus on live
readmodel/write orchestration that proves reusable; concrete live reader
implementations and env source selection stay at the CLI edge unless a reusable
center appears.
Keep model weights, benchmark outputs, and generated runtime state outside Git;
only plans, contracts, and bounded summaries belong in the public seed.

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
  through fakeable ports. At that landing, CLI still owned concrete config
  binding, policy gates, higher-level benchmark/eval coordination,
  latest/history writes, `.aoa` reads, STT/TTS/resident/tokenizer execution,
  and rendering.
- Extracted OpenVINO benchmark/eval suite orchestration into
  `abyss_machine.ai_runtime_adapters`; the adapter owns benchmark device-plan
  execution, eval suite execution-plan dispatch, policy-denial short-circuit,
  whole-command resource before/after sampling, benchmark/eval latest and daily
  JSONL write routing, and workload-measurement callback routing through
  fakeable policy, runtime, suite-runner, writer, path, and resource ports. At
  that landing, CLI still owned concrete config/path binding, policy-gate
  binding, STT fixture and dictation transport, suite callback binding, command
  dispatch, and rendering.
- Extracted AI workload store/readmodel routing into
  `abyss_machine.ai_runtime_adapters`; the adapter owns workload run JSONL
  discovery, tolerant record reads, record-id dedupe append, refresh-from-latest
  source gating, taxonomy latest writes, stats latest writes, refresh history
  appends, and workload status latest writes through fakeable paths, writers,
  source extractors, policy/status, and systemd ports. CLI still owns concrete
  config/path binding, latest source readers, policy binding, systemd binding,
  command dispatch, and rendering.
- Extracted AI core readmodel store routing into
  `abyss_machine.ai_runtime_adapters`; the adapter owns
  devices/models/capabilities/policy/runtime/status/report document assembly,
  resident latest readmodel reads for capabilities, runtime/report latest
  writes, and runtime/report daily history appends through fakeable reader,
  writer, path, clock, and input ports. At that landing, CLI still owned
  concrete live input collection, policy-gate binding, `.aoa`
  generated-summary reads, token-accounting live text/env binding, resident
  parser/rendering, command dispatch, and rendering.
- Extracted token-accounting tokenizer runner execution into
  `abyss_machine.ai_runtime_adapters`; the adapter owns exact-count tokenizer
  subprocess command/env/timeout/timing execution through fakeable runner and
  clock ports while `ai_runtime_contracts` keeps count privacy/result shapes.
  CLI still owns profile selection, generated-at binding, latest/history
  writes, and rendering.
- Extracted token-accounting store/readmodel routing into
  `abyss_machine.ai_runtime_adapters`; the adapter owns contract/profile/latest
  readmodel assembly, count-text document assembly, and latest/history write
  routing through fakeable registry, tokenizer resolver, reader, writer, path,
  subprocess, environment, and clock ports. At that landing, CLI still owned
  concrete registry, env/text input binding, `.aoa` generated-summary reads,
  command dispatch, and rendering.
- Extracted `.aoa` token-accounting generated-summary routing into
  `abyss_machine.ai_runtime_adapters`; the adapter owns session-registry reads,
  session manifest/index fallback reads, generated token-summary sanitization,
  outside-root rejection, session projection without titles/labels/raw paths,
  registry hashing, and latest/history writes through fakeable reader, writer,
  hash, root-check, path, and clock ports. CLI still owns argument/env binding,
  command dispatch, and rendering.
- Extracted LLM registry/latest/validate store/readmodel routing into
  `abyss_machine.ai_runtime_adapters`; the adapter owns registry document
  assembly, registry latest/history routing, latest readmodel reads, validate
  contract-check assembly, and validate latest writes through fakeable runtime,
  profile, token-profile, reader, writer, path, and clock ports. CLI still owns
  concrete config/path binding, path validation input collection, command
  dispatch, and rendering.
- Extracted resident LLM controller runner execution into
  `abyss_machine.ai_runtime_adapters`; the adapter owns
  `abyss-gemma4-spark-resident` command construction, timeout routing,
  subprocess invocation, stdout/stderr/returncode mapping, and no-output JSON
  error envelopes through a fakeable command port. CLI still owns argparse
  binding, user-visible result rendering, and command dispatch.
- Extracted workhorse LLM controller runner execution into
  `abyss_machine.ai_runtime_adapters`; the adapter owns
  `abyss-gemma4-e4b-harness` command construction, timeout routing, subprocess
  invocation, stdout/stderr/returncode mapping, and no-output JSON error
  envelopes through a fakeable command port. CLI still owns argparse binding,
  user-visible result rendering, and command dispatch.
- Extracted resident/workhorse LLM controller result projection into
  `abyss_machine.ai_runtime_adapters`; the adapter owns JSON stdout parsing,
  bounded invalid-JSON error documents, no-output fallback, and text-mode
  stdout/stderr selection for controller results. CLI still owns printing,
  argparse binding, and command dispatch.
- Extracted AI policy-gate binding into
  `abyss_machine.ai_runtime_adapters`; the adapter owns
  `ai_policy(write_latest=True)` callback routing, generated-at binding,
  declared class/operation/force/class-level forwarding, and gate document
  assembly through fakeable policy and clock ports. CLI still owns the
  concrete policy callback route, command dispatch, and rendering.
- Extracted AI policy readmodel input collection into
  `abyss_machine.ai_runtime_adapters`; the adapter owns observability
  status/latest collection, mode status, battery fallback, thermal-policy
  snapshot, and CPU thermal-map selection through fakeable ports. CLI still
  owns concrete live reader implementations, command dispatch, and rendering.
- Extracted AI capabilities input collection into
  `abyss_machine.ai_runtime_adapters`; the adapter owns devices/models/
  dictation/TTS eval and success/LLM registry callback routing, resident latest
  path binding, resident latest JSON reads, and capabilities latest writes
  through fakeable ports. CLI still owns concrete live reader implementations,
  command dispatch, and rendering.
- Extracted AI env/resource binding into
  `abyss_machine.ai_runtime_adapters`; the adapter owns subprocess env
  construction through fakeable environment/root ports, resource snapshot
  envelope assembly through fakeable memory/thermal/battery/rusage/load ports,
  and resource-profile document forwarding. CLI still owns concrete `/proc`,
  sensor, battery, rusage, loadavg, and `os.environ` readers plus command
  dispatch and rendering.
- Extracted STT eval dictation transport and resource sampling into
  `abyss_machine.ai_runtime_adapters`; the adapter owns per-profile
  dictation-client calls, monotonic timing, before/after resource snapshots,
  and client-side resource-profile envelopes through fakeable transport, clock,
  and resource ports while `ai_runtime_contracts` keeps scoring/result shapes.
  At that landing, CLI still owned eval config selection, fixture construction,
  command dispatch, and rendering.
- Extracted STT synthetic fixture generation into
  `abyss_machine.ai_runtime_adapters`; the adapter owns fixture directory
  creation, existing WAV reuse checks, `espeak-ng` command execution, optional
  `ffmpeg` resampling, raw WAV replace/cleanup, and duration/sample-rate reads
  through fakeable filesystem, command, and WAV metadata ports. CLI still owns
  eval config selection, command dispatch, and rendering.
- Extracted TTS output audio summary and synth resource-report assembly into
  `abyss_machine.ai_tts_adapters`; the adapter owns WAV stat/duration/sample
  rate inspection, wall-clock result timing, RTF derivation, and resource-profile
  callback routing through fakeable path, clock, resource snapshot, and
  resource-profile ports. CLI still owns profile/config selection, policy gates,
  latest writes, command dispatch, and rendering.
- Extracted resident TTS warm server loop/socket lifecycle into
  `abyss_machine.ai_tts_adapters`; the adapter owns Unix-socket bind/unlink,
  JSON-line request parsing, ping/status/synth/shutdown command dispatch,
  shutdown loop termination, socket cleanup, and sync/awaitable unload callback
  execution through fakeable ports. CLI still owns profile/config selection,
  policy gates, latest writes, command dispatch, and rendering.
- Extracted resident TTS Qwen3 OpenVINO server runtime lifecycle into
  `abyss_machine.ai_tts_adapters`; the adapter owns SDK import/path injection,
  model-load config construction, model load/unload callback, synth request
  option/language/speaker mapping, model generate call, `soundfile` WAV write,
  and server synth success/error document assembly through fakeable importer,
  path, clock, and output-path ports. CLI still owns profile/config/status
  selection, policy gates, server-state latest write, command dispatch, and
  rendering.
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
