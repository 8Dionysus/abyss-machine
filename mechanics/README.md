# abyss-machine Mechanics Atlas

A mechanic packages one durable, recurring host movement with a clear owner,
inputs, outputs, stop-lines, and validation. It is not a generic notes
directory and does not create new host authority.

| Package | Host question |
|---|---|
| [host-lifecycle](host-lifecycle/README.md) | How is the host layer installed, checked, updated, and repaired? |
| [config-projection](config-projection/README.md) | How do public templates become local `/etc/abyss-machine` without secrets? |
| [host-facts](host-facts/README.md) | How are machine facts gathered without publishing private state? |
| [storage-routing](storage-routing/README.md) | How are `/srv`, caches, runtimes, backups, and temporary roots kept bounded? |
| [typing-intake](typing-intake/README.md) | How does typed activity become opt-in, redacted evidence? |
| [nervous-local](nervous-local/README.md) | How does local nervous intake become privacy-gated memory evidence? |
| [local-ai-runtime](local-ai-runtime/README.md) | How are host-managed AI helpers kept outside stack ownership? |
| [diagnostic-spine](diagnostic-spine/README.md) | How do doctor probes and validators expose repairable host posture? |
| [code-intelligence](code-intelligence/README.md) | How is a bounded code-intelligence provider packaged and admitted? |

Each package keeps an `AGENTS.md` owner card and a README mechanic card.
Additional direction, provenance, roadmap, landing-log, `docs/`, or `parts/`
surfaces exist only when they carry package-specific content.

## Cross-cutting implementation maps

Current adapter ownership and residual CLI-edge work are tracked in
[LIVE_ADAPTERS.md](../docs/host/LIVE_ADAPTERS.md). Stable command ownership is
mapped in [SUBSYSTEM_COMMANDS.md](../docs/host/SUBSYSTEM_COMMANDS.md). Those
documents and source modules are authoritative for implementation detail;
this atlas only routes to the owning mechanic.

Validate package shape with:

```bash
python scripts/validators/mechanics_topology.py
```
