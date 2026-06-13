# Abyss Machine Hooks

This directory is the stable host-level hook contract for storage, runtime, cache, migration, and process-snapshot events.

## Contract

- Owner: host machine layer.
- Scope: compact policy hooks only. Large hook state or generated evidence belongs under `{{ABYSS_MACHINE_SRV}}` or `{{ABYSS_MACHINE_STATE}}`.
- Do not mutate `abyss-stack` repositories from hooks.
- Do not write machine-owned caches, runtimes, model artifacts, or logs to `/work`.
- Hook command: `abyss-machine storage run-hooks STAGE --json`.
- Hook inventory: `abyss-machine storage hooks --json`.
- Policy: `{{ABYSS_MACHINE_ETC}}/storage-policy.json`.

## Stages

Hook directories are named `<stage>.d`. Executable files are run in lexical order from `{{ABYSS_MACHINE_ETC}}/hooks.d/<stage>.d`, then `{{ABYSS_MACHINE_SRV}}/hooks.d/<stage>.d`.

Valid stages:

- `pre_large_write`
- `post_large_write`
- `pre_runtime_create`
- `post_runtime_create`
- `pre_cache_cleanup`
- `post_cache_cleanup`
- `pre_podman_migration`
- `post_podman_migration`
- `process_snapshot`

Hooks receive a JSON object on stdin with schema `abyss_machine_storage_hook_event_v1`. A non-zero exit blocks only when the caller uses `--enforce`.

## Local Cards

Each stable hook stage directory has its own `AGENTS.md` route card. Use the
stage card before adding executable scripts or changing block/allow behavior.
Writable host-local overlays live under `{{ABYSS_MACHINE_SRV}}/hooks.d`.
