# Abyss Machine Reranker Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/ai/rerankers/`.

## Role

This directory holds helper tools for reranker model download, OpenVINO canary
runs, and nervous retrieval quality probes.

It does not own the deployed reranker state or retrieval truth. Evidence belongs
under `/var/lib/abyss-machine/ai/rerankers` and
`/var/lib/abyss-machine/nervous/evals`.

## Operating Contract

- Input: reranker helper source, approved model/cache route, and retrieval
  probe intent.
- Output: download/probe helpers and canary evidence; durable evidence routes
  to `/var/lib/abyss-machine/ai/rerankers` or
  `/var/lib/abyss-machine/nervous/evals`.
- Owner: AI config owns model route; nervous evals own retrieval-quality
  evidence.
- Tools: local Python helpers, `abyss-machine ai ... --json`, and
  `abyss-machine nervous ... --json`.
- Next route: storage-policy review before downloads; nervous eval route before
  claiming retrieval quality.
- Verify: `abyss-machine ai validate --json`, `abyss-machine nervous validate
  --json`, and `abyss-machine docs mesh-validate --json`.

## Read Before Editing

Read:

- `/srv/abyss-machine/tools/ai/AGENTS.md`
- `/var/lib/abyss-machine/ai/AGENTS.md`
- `/var/lib/abyss-machine/nervous/AGENTS.md`
- `/etc/abyss-machine/storage-policy.json`

## Boundaries

- Model downloads must route to `/srv/abyss-machine/cache/ai` or another
  storage-policy-approved large cache.
- Do not claim retrieval quality from synthetic canaries alone.
- Do not connect to the network during a validation pass unless the task
  explicitly requires a download or refresh.

## Validation

```bash
abyss-machine ai validate --json
abyss-machine nervous validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State model/cache paths, manifest paths, canary evidence, and whether live
network access was used.
