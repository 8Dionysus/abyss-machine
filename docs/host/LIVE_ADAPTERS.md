# Live Adapter Audit

`abyss-machine` is a public source seed, not a dump of a live workstation. The
live adapter boundary names the code that touches host/runtime state while
package modules keep stable contracts, policy, and read-model shapes.

## Adapter Classes

| Class | Owns | Public seed rule |
|---|---|---|
| Host/runtime reads | `/proc`, `/sys`, DBus, systemd, browser profiles, AT-SPI, sockets, SQLite stores, JSONL histories, generated latest files, cache inventories, and local config reads. | May produce bounded summaries; must not publish private evidence, captures, local indexes, secrets, or model weights. |
| Latest/history writes | Atomic JSON latest writes, daily JSONL appends, generated index writes, report writes, and compact history records under `/var/lib/abyss-machine`. | Source owns write mechanism and schema shape; host owns generated records. |
| Mutating host actions | systemd starts/stops, profile switches, cleanup apply, retention unlink, browser selftest profile creation, clipboard/audio/text insertion, and explicit repair actions. | Must stay opt-in, reversible or dry-run first where possible, and outside public examples unless synthetic. |
| Subprocess/runtime execution | `systemctl`, `journalctl`, OpenVINO/tokenizer helpers, browser/AT-SPI probes, X11 tools, audio tools, package queries, and local benchmark/eval processes. | Execution plan may be public; runtime outputs and local paths are bounded evidence. |
| Network/socket/browser bridges | BiDi/WebSocket capture, native-host messaging, local HTTP probes, resident model/TTS sockets, and stack observability probes. | Public code may define adapters; live payloads stay local and privacy-gated. |

## Current High-Pressure Surfaces

| Surface | Reads | Writes | Mutates/executes | Current home |
|---|---|---|---|---|
| `typing` | policy files, Codex session JSONL, browser/native-host payloads, AT-SPI focus/text metadata, user-systemd status, recent typing records. | typing latest/history JSONL, source-specific selftest latest files, typing index, compact AT-SPI history. | browser native-host responses, optional focused-browser selftests, AT-SPI focus/insert diagnostics, virtual typing selftests. | Contracts in `typing_capture_contracts`; latest/history persistence and Codex session-tail filesystem reads start in `typing_nervous_adapters`; Codex prompt/session-tail semantic ingest plans live in `typing_codex_semantics`; browser/native-host ingest plans, synthetic selftest documents, route selection, and response envelopes live in `typing_browser_adapters`; focused-snapshot, AT-SPI text-event sample/metadata/debounce, and generic GUI selftest semantic plans live in `typing_atspi_adapters`; framed native-host bytes, `pyatspi` traversal/listener registration, text reads, and browser/AT-SPI live probes remain CLI edge. |
| `nervous` | source policy, privacy state, fact/event/episode JSONL, browser history DBs, explicit metadata roots, podman metadata, clipboard, screenshot/window state, semantic/index SQLite stores. | nervous facts/events/episodes/latest, index/semantic status, synthesis/eval reports, retention plans, privacy audit records. | browser content capture, GNOME/X11 probes, retention apply/unlink, semantic embedding subprocesses, reranker subprocesses. | Contracts split across nervous modules; latest/history persistence starts in `typing_nervous_adapters`; most probes remain CLI edge. |
| `dictation` | audio devices, runtime config, transcripts, WAV metadata, server state. | transcript latest/JSONL, dictation index, validation latest. | recording, server transport, clipboard/text insertion, audio runtime subprocesses. | `dictation_contracts` owns shapes; live audio/clipboard/server adapters remain CLI edge. |
| `ai` | runtime config, model/cache roots, package availability, tokenizer/model inventories, generated AoA summaries. | AI runtime/status/eval/token-accounting latest and histories. | OpenVINO, tokenizer, STT/TTS, resident LLM and benchmark subprocesses. | `ai_runtime_contracts`, `ai_tts_contracts`, and `ai_cpu_routing` own contracts; live execution remains CLI edge. |
| `self-awareness` | stack/runtime latest files, observability probes, generated event/fabric stores, systemd state. | self-awareness timeline/context/episode/brief/query/probe/latest surfaces. | probe/cycle/replay/investigate orchestration and stack handoff checks. | `self_awareness_contracts` owns read-model shapes; orchestration remains CLI edge. |
| `storage/process/memory/mode/cooling` | disk usage, `/proc`, cgroups, sensors, power profile, process tables, systemd state. | status/plan/monitor/latest histories and indexes. | cleanup apply, resource launch, profile switch, cooling apply, process/container probes. | Contract modules own policy decisions; live host reads and mutation remain CLI edge. |
| `artifact/release trust` | source manifests, bundle evidence, local statement/receipt files, OCI/TUF/C2PA/SCITT proof surfaces. | artifact latest/history, trust coverage, update-lane status. | local trust-tool subprocesses and publication probes. | Real but separate lane; do not fold into typing/nervous adapter work. |

## Extracted First Seam

`abyss_machine.typing_nervous_adapters` now owns the first shared live adapter
for the agent nervous-system organs:

- latest JSON reads with read-schema envelopes;
- atomic latest JSON writes;
- daily JSONL history appends with file locking;
- optional typing index refresh writes;
- local JSONL history file discovery and bounded recent-record reads;
- source-adapter filtered typing history reads with scan accounting;
- Codex session-tail file discovery, root-contained state-file selection,
  incremental byte reads, fallback tail reads, and stat failure reports;
- write-disabled no-op semantics for public-safe dry paths.

This is intentionally narrow. It does not claim the full AT-SPI runtime,
browser live capture/probes, semantic embedding, retention unlink, or
dictation/audio execution are extracted yet. Those remain explicit live
adapter debt until moved behind similarly bounded seams.

## Extracted Codex Semantic Seam

`abyss_machine.typing_codex_semantics` owns the Codex prompt/session-tail
semantic boundary for typing intake:

- prompt text extraction from UserPromptSubmit payload shapes;
- Codex prompt-hook metadata and ingest-plan construction;
- session JSONL user-message route recognition for `event_msg.user_message` and
  `response_item.message.role_user`;
- IDE/goal/environment envelope normalization and skip reasons;
- near-line duplicate keying for fallback raw-route repeats;
- Codex session-tail metadata/context ingest plans;
- public-safe event summary projection without raw text.

The CLI still owns JSON parsing, configured paths, session-tail state
bookkeeping, calling `typing_ingest`, latest/history writes, and command
rendering. The filesystem tail mechanics remain in `typing_nervous_adapters`.

## Extracted Browser Native-Host Seam

`abyss_machine.typing_browser_adapters` owns the browser/WebExtension
native-host semantic adapter boundary for typing intake:

- browser-extension committed-text ingest plans;
- browser AI transcript cleanup/metadata ingest plans using
  `typing_capture_contracts` as policy owner;
- public-safe status documents after `typing_ingest` execution;
- synthetic browser-extension and AI transcript selftest message/document
  builders;
- native-host route selection and response/error envelopes.

The CLI still owns framed native-messaging stdin/stdout bytes, JSON transport
errors, calling `typing_ingest`, latest/history writes, and command rendering.
The temporary Firefox profile, `web-ext` subprocess, loopback HTTP server,
release-profile discovery, focused-browser, browser-privacy, and AT-SPI probes
remain live edge debt.

## Extracted AT-SPI Semantic Seam

`abyss_machine.typing_atspi_adapters` owns the first AT-SPI semantic adapter
boundary for typing intake:

- focused-snapshot ingest plans, candidate projections, metadata, context, and
  public-safe status documents;
- AT-SPI text-event sample envelopes, metadata shaping, browser-context
  bounded summaries, context identity, debounce decisions, and typing-event
  summaries;
- generic GUI selftest ingest plans and final selftest document assembly;
- safe string handling shared by live AT-SPI object readers.

The CLI still owns `pyatspi` imports, accessibility-tree traversal, object text
reads, live listener registration, monotonic clocks, calling `typing_ingest`,
latest/history writes, and command rendering. Browser AT-SPI selftest
execution, release-profile probing, focused-browser diagnostics, and privacy
selftest record readers remain live edge debt.

## Next Extraction Order

1. Typing/nervous source adapters: saved-text scan, browser
   profile/tmp/WebExtension live-probe execution, browser AT-SPI selftest
   execution, focused-browser and privacy/selftest record readers, and the
   remaining `pyatspi` traversal/listener runtime edge.
2. Nervous index/semantic execution adapters: SQLite store lifecycle,
   embedding subprocess execution, rerank subprocess execution, and latest
   provenance writes.
3. Dictation and AI runtime adapters: audio/server/clipboard execution and
   model/runtime subprocess plans.
4. Diagnostic and host lifecycle adapters: doctor probes, bootstrap dry-run
   evidence, installed projection parity, and repair orchestration.

## Stop Lines

- Do not publish `/etc/abyss-machine`, `/var/lib/abyss-machine`,
  `/srv/abyss-machine`, browser captures, typed text histories, local indexes,
  secrets, or model weights.
- Do not turn validators into hidden behavior owners.
- Do not collapse typing/nervous into a publication simplification; they are
  first-class host organs and must remain opt-in, privacy-gated, and tested.
