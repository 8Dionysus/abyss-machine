# Abyss Machine LLM Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/ai/llm/`.

## Role

This lane holds thin host-owned helpers for bounded local `llama.cpp` probes
and on-demand servers. It is not a model cache, runtime root, or stack-owned
serving layer.

## Operating Contract

- Input: operator intent, `/etc/abyss-machine/ai/config.json`, admitted local
  model files, and host-managed runtime binaries.
- Output: helper-owned transient user units plus bounded status/request
  records; durable evidence belongs under `/var/lib/abyss-machine/ai/llm`.
- Owner: AI config owns profiles and promoted settings; dated eval evidence
  owns measured performance.
- Tools: `abyss-machine ai llm ... --json`,
  `abyss-qwen36-lazy-server`, and `qwen36_prefill_matrix.py`.
- Verify: AI, resource, and docs-mesh validation.

## Route selection

Use `/etc/abyss-machine/ai/config.json` for profile, runtime, model, cache, and
promoted tuning truth. Use `/var/lib/abyss-machine/ai/llm/AGENTS.md` for
runtime evidence and `/var/lib/abyss-machine/resource/AGENTS.md` before a
heavy start. The inherited AI-tools card supplies the common storage and
source boundaries.

## Rules

- Route heavy starts through
  `abyss-machine resource plan --class heavy --kind ai --json`.
- Use explicit CPU affinity with `taskset`; systemd `AllowedCPUs` alone is not
  process-affinity evidence on this host.
- Keep helpers small, auditable, reversible, and non-persistent unless the
  operator explicitly promotes a service.
- Use stable-prefix prompts when testing prefill reuse; record benchmark
  results under the configured evidence root, not in this card.

## Boundaries

- Helpers may start or stop only their own transient `abyss-qwen36-*` user
  units.
- Do not stop, rewrite, or re-affinitize stack services, resident models, TTS,
  work containers, games, or editor processes.
- Do not mutate `abyss-stack`, `/srv/AbyssOS`, work roots, or game roots.
- Model blobs, slot caches, runtimes, and benchmark output stay in the
  configured `/srv` and `/var/lib` owner routes.

## Validation

```bash
abyss-machine ai llm registry --json
abyss-machine ai llm validate --json
abyss-machine resource validate --json
abyss-machine docs mesh-validate --json
```

Closeout names the helper/profile, resource admission, cache/evidence routes,
and whether a measured setting was changed in its owning config.
