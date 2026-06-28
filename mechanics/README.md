# abyss-machine Mechanics Atlas

This atlas routes durable host-machine moves.

| Package | Host question | Start here |
|---|---|---|
| `host-lifecycle` | How is the host layer installed, checked, updated, and repaired? | `scripts/abyss-machine-bootstrap`, `docs/install/`, `docs/operations/` |
| `config-projection` | How do public templates become local `/etc/abyss-machine` without secrets? | `config-templates/`, `env/`, `schemas/` |
| `host-facts` | How are machine facts gathered and exposed without publishing private state? | `docs/host/`, `src/abyss_machine/cli.py` |
| `storage-routing` | How are `/srv`, caches, runtimes, backups, and temp roots kept bounded? | `tools/abyss-storage-reclaim-audit`, `docs/host/` |
| `typing-intake` | How does typed activity become opt-in, redacted evidence? | `tools/typing/`, typing profile units |
| `nervous-local` | How does local nervous intake become privacy-gated memory evidence? | `tools/nervous/`, nervous profile units |
| `local-ai-runtime` | How are host-managed local AI helpers kept outside stack ownership? | `tools/ai/`, ai-local profile units |
| `diagnostic-spine` | How do doctor probes and validators expose repairable host posture? | `docs/validation/`, bootstrap doctor |

The atlas does not create new host authority. It makes existing movements
visible and gives future implementation a place to land.

## Live Adapter Route

Live adapter hardening is tracked from [docs/host/LIVE_ADAPTERS.md](../docs/host/LIVE_ADAPTERS.md).
Use these mechanic owners for the next extraction slices:

- `typing-intake`: typing latest/history persistence, Codex session-tail
  filesystem reads and semantic ingest planning, browser/native-host ingest
  planning/transport/response envelopes, temporary Firefox WebExtension and
  browser-context/browser AT-SPI/focused-browser/browser-privacy selftest runtime, AT-SPI
  focused/text-event/generic GUI semantic plans, saved-text scan filesystem
  mechanics, native-host stdio binding, and remaining `pyatspi` runtime
  adapters.
- `nervous-local`: nervous source capture, privacy state, local JSONL/SQLite
  readers, semantic/rerank execution, retention, and derived memory evidence.
- `local-ai-runtime`: host-managed AI model/runtime subprocesses, resource
  gates, token/STT/TTS execution, dictation transcription/recording/audio
  inspection/journal/insertion adapters, and cache/runtime evidence.
- `diagnostic-spine`: doctor, validation, repair, and freshness probes that
  prove the host layer is healthy without publishing private state.
- `host-lifecycle`: bootstrap, install projection, source/install parity, and
  release/check gates for the portable public seed.
