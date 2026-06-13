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
