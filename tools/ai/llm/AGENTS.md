# Abyss Machine LLM Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/ai/llm/`.

## Role

This directory holds thin host-owned LLM helper tools for bounded local
`llama.cpp` probes and on-demand server routes. It is not a model cache,
runtime root, or stack-owned serving layer.

Source profile truth lives in `/etc/abyss-machine/ai/config.json`. Runtime
evidence belongs under `/var/lib/abyss-machine/ai/llm`. Large model and runtime
artifacts belong under `/srv/abyss-machine/cache/ai` and
`/srv/abyss-machine/runtimes`.

## Operating Contract

- Input: operator intent, `/etc/abyss-machine/ai/config.json`, local model
  files under `/srv/abyss-machine/cache/ai`, and runtime binaries under
  `/srv/abyss-machine/runtimes/llama.cpp`.
- Output: bounded transient user units, JSON status/request records, and
  evidence under `/var/lib/abyss-machine/ai/llm`.
- Authority: `abyss-machine ai llm registry --json` for configured profile
  presence, `abyss-machine resource plan --class heavy --kind ai --json` for
  start gating, and dated eval notes for measured performance.

## Rules

- Keep helpers small, auditable, and reversible.
- Route heavy starts through `abyss-machine resource plan --class heavy --kind ai --json`.
- Use explicit CPU affinity with `taskset`; systemd `AllowedCPUs` alone is not
  sufficient evidence of process affinity on this host.
- Do not enable persistent services from this directory without explicit
  operator direction.
- Do not mutate `abyss-stack`, `/srv/AbyssOS`, work roots, or game roots.

## Boundaries

- This directory may start and stop only helper-owned transient
  `abyss-qwen36-*` user units.
- It must not stop, rewrite, or re-affinitize stack-owned servers, resident
  Gemma services, TTS services, work containers, games, or editor processes.
- It must not become a cache, benchmark-output archive, or long-term model
  registry. Store those artifacts in the owning `/srv` or `/var/lib` routes.

## Qwen3.6 Route

`abyss-qwen36-lazy-server` controls Qwen3.6 27B Q3_K_M single-model
`llama-server` units:

```bash
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server status --json
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server start --profile ordinary --ctx 8192 --json
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server prefill --profile ordinary --ctx 8192 --prompt-file FILE --save-slot SLOT.bin --write-evidence --json
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server restore-slot --profile ordinary --ctx 8192 --filename SLOT.bin --json
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server request --profile ordinary --ctx 8192 --prompt-file FILE --json
/srv/abyss-machine/tools/ai/llm/abyss-qwen36-lazy-server stop --profile ordinary --ctx 8192 --json
/srv/abyss-machine/tools/ai/llm/qwen36_prefill_matrix.py --case b512-u256-8k,8192,512,256
```

The Qwen3.6 wrapper exposes the prefill-cache lane explicitly:

- slot cache files live under
  `/srv/abyss-machine/cache/ai/qwen3.6/prefill-cache/slots`;
- durable, redacted cache/reuse evidence lives under
  `/var/lib/abyss-machine/ai/llm/evals/qwen36/prefill-cache`;
- `prefill` evaluates a prompt with `n_predict=0` and can save a named slot;
- `request` can restore a named slot before completion and save it afterward;
- optional server controls include `--cache-reuse`, `--ctx-checkpoints`,
  `--checkpoint-every-n-tokens`, `--cache-ram`,
  `--slot-prompt-similarity`, `--batch`, `--ubatch`, and
  `--threads-batch`.

Use stable-prefix prompts for large RAG/DAG contexts. Put durable context maps,
rules, and retrieved long documents first, then append the changing task suffix;
otherwise prompt cache and slot restore cannot avoid prefill work.

Measured on 2026-05-31:

- b9060 remains the safe Qwen3.6 baseline runtime;
- slot save/restore works mechanically, but 8k restore/live-slot tests still
  re-evaluated the full prompt (`cache_n=0`), so do not treat slot cache as a
  proven prefill accelerator on b9060;
- `--batch 512 --ubatch 256` remains the general safe default for 8k/16k;
- `--batch 1024 --ubatch 512` is only an 8k candidate and crashed 16k with
  Vulkan `DeviceLost`;
- runtime `22cadc1` exposes `draft-mtp`/speculative flags but is experimental
  here until a matching local Qwen3.6 MTP GGUF is installed and measured.

Use `qwen36_prefill_matrix.py` for bounded batch/ubatch evidence. It writes a
JSONL record under `/var/lib/abyss-machine/ai/llm/evals/qwen36/prefill-matrix`
and stores only summarized completion data, not prompt text.

Router mode is intentionally not the promoted path until the local Vulkan
`DeviceLost` crash is resolved by a newer runtime or workaround. Use
single-model server units for lazy-load work.

## Validation

```bash
abyss-machine ai llm registry --json
abyss-machine ai llm validate --json
abyss-machine resource validate --json
abyss-machine docs mesh-validate --json
```
