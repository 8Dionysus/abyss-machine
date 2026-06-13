# Abyss Machine Maps

Status: source contract for the generated `abyss-machine` machine atlas.
Authority: subordinate to `{{ABYSS_MACHINE_ETC}}/DESIGN.md`,
`{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`, and `{{ABYSS_MACHINE_ETC}}/DOCS.md`.

## Role

Machine maps are the agent-facing atlas over host-machine evidence. They answer
where to look next across time, subsystem ownership, causal chains, freshness,
resource state, privacy risk, RAG/eval/memo/KAG boundary context, and
actionability.

They do not replace the structural host graph, the nervous event/index layer,
source contracts, validators, the change ledger, or reviewed AoA organs.

`abyss-machine rag ...` is the first live read-only loop built on top of this
atlas. It turns a maps context packet into bounded evidence summaries, a
deterministic answer trace, and a trace-quality eval. It remains generated
route evidence, not source truth, proof verdict, reviewed memory, KAG truth, or
permission to act.

## Source And Generated Boundary

Source-owned:

- `{{ABYSS_MACHINE_ETC}}/MAPS.md`
- `{{ABYSS_MACHINE_ETC}}/maps-policy.json`
- `abyss-machine maps ...` CLI behavior
- `abyss-machine rag ...` CLI behavior for read-only trace loops

Generated:

- `{{ABYSS_MACHINE_STATE}}/maps/START.md`
- `{{ABYSS_MACHINE_STATE}}/maps/latest.json`
- `{{ABYSS_MACHINE_STATE}}/maps/index.json`
- `{{ABYSS_MACHINE_STATE}}/maps/by-*/index.json`
- `{{ABYSS_MACHINE_STATE}}/maps/by-*/INDEX.md`
- `{{ABYSS_MACHINE_STATE}}/maps/by-*/entries/*.json`
- `{{ABYSS_MACHINE_STATE}}/maps/validate/latest.json`
- `{{ABYSS_MACHINE_STATE}}/rag/latest.json`
- `{{ABYSS_MACHINE_STATE}}/rag/index.json`
- `{{ABYSS_MACHINE_STATE}}/rag/traces/latest.json`
- `{{ABYSS_MACHINE_STATE}}/rag/evals/latest.json`
- `{{ABYSS_MACHINE_STATE}}/rag/validate/latest.json`

## Axis Contract

Each axis must answer one routing question. The initial axes are:

- `by-time`
- `by-subsystem`
- `by-event-type`
- `by-episode`
- `by-causal-chain`
- `by-owner-route`
- `by-freshness`
- `by-resource-state`
- `by-risk-privacy`
- `by-actionability`
- `by-correlation`
- `by-rag-run`
- `by-memory-candidate`
- `by-eval-packet`
- `by-kag-export`

Add an axis only when it routes future agents to evidence faster than the
existing axes.

## Rules

- Every generated entry must carry `truth_status` and `evidence_refs`.
- Entries are route signals, not reviewed truth and not permission to act.
- Captured facts, screenshots, browser content, synthesis candidates,
  reactions, responses, and retrieval packs remain evidence only.
- Reader-profile packets are boundary context for agents; they are not
  destinations and do not deliver machine moments into AoA organs.
- RAG traces open bounded evidence summaries only; raw private capture payloads
  remain closed.
- RAG evals check trace quality only; they do not produce proof verdicts.
- AoA organs remain external owner surfaces: proof belongs to `aoa-evals`,
  reviewed memory belongs to `aoa-memo`, and derived KAG truth belongs to
  `aoa-kag`.
- Protected project roots stay read-only from this host layer.

## Commands

```bash
abyss-machine maps --json
abyss-machine maps paths --json
abyss-machine maps policy --json
abyss-machine maps build --json
abyss-machine maps query --axis by-freshness --query semantic --json
abyss-machine maps packet --axis by-eval-packet --reader-profile proof-context --json
abyss-machine maps validate --json
abyss-machine rag refresh --query TEXT --json
abyss-machine rag trace --query TEXT --json
abyss-machine rag latest --json
abyss-machine rag eval --json
abyss-machine rag validate --json
```

`maps packet` returns a bounded boundary-context packet for an agent reader
profile such as `agent`, `retrieval-context`, `graph-context`,
`proof-context`, `memory-context`, `knowledge-context`, or `runtime-context`.
Packets carry atlas entries, evidence refs, freshness/owner route hints, and
authority boundaries. Profiles are lenses, not recipients. Packets do not run
retrieval, evals, memory writeback, KAG publication, responses, or actions.

`rag trace` uses `maps packet` as its seed, opens only bounded evidence
summaries from cited refs, writes a generated trace under
`{{ABYSS_MACHINE_STATE}}/rag/traces/`, and writes a local trace eval under
`{{ABYSS_MACHINE_STATE}}/rag/evals/`. The eval is a quality gate over the trace
contract; it is not an `aoa-evals` proof bundle and does not deliver evidence
to any external organ.

## Local LLM Prompt Packaging

When maps or RAG packets are used as input for a local long-context LLM, package
large reusable material as a stable prefix and append only the changing task as
the suffix. The stable prefix order is:

1. machine identity, route law, and source contracts;
2. current maps packet with stable sorting, digests, truth status, owner route,
   and evidence refs;
3. bounded RAG trace/eval summaries and runtime/eval summaries;
4. active change and rollback context;
5. task-specific retrieved evidence that is likely to be reused across nearby
   turns.

The suffix is for the current user question, proposed action, fresh ad hoc
snippets, and any material expected to change on the next turn. Do not rewrite
the prefix when only the suffix changes. If a prefix exceeds the practical
Qwen3.6 8k lane, prefer a tighter maps packet before jumping to 16k; 16k is a
deep-task lane and must use the measured safe server settings.

This packaging rule is an optimization contract only. It does not make maps
source truth, does not grant action permission, and does not deliver evidence to
AoA organs.

## Automation

`abyss-machine-context-refresh.timer` is the user-scope automatic refresh
route. It runs `abyss-machine rag refresh --query scheduled-machine-context-refresh
--json` as a bounded oneshot every 15 minutes with low CPU/IO weight.

That refresh pass rebuilds maps, validates maps, writes a RAG trace/eval, and
validates the RAG loop. It refreshes generated context only; it is not a
resident daemon and does not execute actions, responses, memory writeback,
proof verdicts, KAG publication, or AoA organ delivery.

## Validation

After changing this contract, policy, CLI behavior, or generated atlas route,
run:

```bash
abyss-machine maps validate --json
abyss-machine rag validate --json
abyss-machine graph validate --json
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs audit --json
abyss-machine stack-bridge validate --json
```
