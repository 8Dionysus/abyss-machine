# Abyss Machine Decisions

This directory is the durable decision-rationale surface for `abyss-machine`.

Decisions explain why. Current source surfaces define what. Generated facts and
history can support a decision, but they do not replace source contracts.

## Operating Card

| Field | Route |
| --- | --- |
| role | durable host-layer decision rationale |
| entry | use when structural, topology, validation, bridge, source-boundary, route-law, or host-wide closeout choices need recoverable rationale |
| input | source pressure, rejected option, owner boundary, validator drift, bridge-contract pressure, or reviewed memo candidate |
| output | numbered decision record, README index row, generated compact index, and validation evidence |
| owner | `AGENTS.md` for lane law; this README for human and agent indexing; numbered records for rationale |
| next route | source surface first, then local route card, generated read model, memo receipt, or owning validator |
| validation | `abyss-machine docs decisions-index --json`, `abyss-machine docs audit --json`, `abyss-machine docs mesh-validate --json` |

Generated quick index:

```text
{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json
```

Rebuild it with:

```bash
abyss-machine docs decisions-index --json
```

The generated index is for fast access to what changed when and why. It does
not replace the source records in this directory.

## Record Contract

Use `TEMPLATE.md`.

Decision files must use stable numbered names:

```text
NNNN-speaking-name.md
```

The title must start with the same number:

```markdown
# NNNN Speaking Name
```

Do not renumber accepted records. New records take the next sequence number.
If a decision is replaced, add a new record and mark the older one
`superseded`; keep the old path stable.

Each record must include status, date, index tags, current applicability,
context, options considered, decision, rationale, consequences, boundaries,
review log, source surfaces, validation, and follow-up route.

## Record Evolution Pipeline

Decision records are historical rationale plus a dated applicability layer. Do
not rewrite old rationale to make it look timeless.

When a later change affects an existing decision:

1. Re-read the existing record and the source surfaces it cites.
2. Decide whether the old rationale still applies, was narrowed, or was
   replaced.
3. If the rationale still applies, update the same record with a dated
   `Review Log` entry and refresh `Current Applicability`.
4. If a concrete claim is obsolete, mark it with Markdown strikethrough in the
   dated applicability/review entry and state the replacement source route.
5. If the route or rationale is replaced, create a new numbered record, mark the
   old record `superseded`, and point both records at each other.
6. Rebuild `abyss-machine docs decisions-index --json` and validate the docs
   mesh.

The review log is not a changelog. It records material reviews and applicability
movement for that decision only.

## Current Decisions

| No. | Decision | Path | Primary index tags | Posture |
| --- | --- | --- | --- | --- |
| 0001 | [Roadmap, Decisions, And Changelog Route](0001-roadmap-decisions-changelog-route.md) | `0001-roadmap-decisions-changelog-route.md` | root/topology, documentation-topology | active rationale |
| 0002 | [Decision Index Route](0002-decision-index-route.md) | `0002-decision-index-route.md` | generated/readout, decision-index | active guard rationale |
| 0003 | [Host Agent Mesh Route](0003-host-agent-mesh-route.md) | `0003-host-agent-mesh-route.md` | agent-mesh, route-card-topology | active guard rationale |
| 0004 | [Large Root Design Route](0004-srv-large-root-design-route.md) | `0004-srv-large-root-design-route.md` | large-root, storage-topology | active rationale |
| 0005 | [Zram Headroom Routing](0005-zram-headroom-routing.md) | `0005-zram-headroom-routing.md` | memory, resource-gate | active rationale |
| 0006 | [Doctor Self-Maintenance Route](0006-doctor-self-maintenance-route.md) | `0006-doctor-self-maintenance-route.md` | doctor, self-maintenance | active rationale |
| 0007 | [OS Abyss Heartbeat Reaction Response Chain](0007-os-abyss-heartbeat-reaction-response-chain.md) | `0007-os-abyss-heartbeat-reaction-response-chain.md` | heartbeats, reactions, responses | active rationale |
| 0008 | [Change Close Decision Review Gate](0008-change-close-decision-review-gate.md) | `0008-change-close-decision-review-gate.md` | change-ledger, decision-review | active guard rationale |
| 0009 | [Decision Record Evolution Route](0009-decision-record-evolution-route.md) | `0009-decision-record-evolution-route.md` | decision-evolution, review-log | active guard rationale |
| 0010 | [Typing Journal Preservation Route](0010-typing-journal-preservation-route.md) | `0010-typing-journal-preservation-route.md` | typing, journal-preservation | active guard rationale |
| 0011 | [E2B Resident Selection Route](0011-e2b-resident-selection-route.md) | `0011-e2b-resident-selection-route.md` | ai-resident, e2b-selection | active rationale |
| 0012 | [Causal Spine Bridge Route](0012-causal-spine-bridge-route.md) | `0012-causal-spine-bridge-route.md` | typing, causal-binding, stack-bridge, heartbeats | active bridge rationale |
| 0013 | [Machine Atlas Maps Route](0013-machine-atlas-maps-route.md) | `0013-machine-atlas-maps-route.md` | maps, route-atlas, boundary-context, validation-guard | active route rationale; packet destination semantics superseded by 0014 |
| 0014 | [Machine Atlas Reader Profile Packets](0014-machine-atlas-reader-profile-packets.md) | `0014-machine-atlas-reader-profile-packets.md` | maps, reader-profile, owner-boundary, validation-guard | active boundary rationale |
| 0015 | [Machine RAG Trace Loop](0015-machine-rag-trace-loop.md) | `0015-machine-rag-trace-loop.md` | rag, maps, evidence-trace, validation-guard | active trace-loop rationale |
| 0016 | [Machine Context Refresh Automation](0016-machine-context-refresh-automation.md) | `0016-machine-context-refresh-automation.md` | rag, maps, automation, validation-guard | active automation rationale |
| 0017 | [Stack Observability Bridge Consumer](0017-stack-observability-bridge-consumer.md) | `0017-stack-observability-bridge-consumer.md` | stack-bridge, observability, owner-boundary, validation-guard | active bridge rationale |
| 0018 | [Self-Awareness Observability Layer](0018-self-awareness-observability-layer.md) | `0018-self-awareness-observability-layer.md` | self-awareness, stack-bridge, observability, owner-boundary, validation-guard | active bridge rationale |
| 0019 | [Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md) | `0019-self-awareness-full-stack-coverage.md` | self-awareness, stack-bridge, langgraph, observability, ai-resident, rag, owner-boundary, validation-guard | active coverage rationale |
| 0020 | [Artifact Evidence Cleanup Route](0020-artifact-evidence-cleanup-route.md) | `0020-artifact-evidence-cleanup-route.md` | artifacts, storage-topology, ai-cache, vault-restore, validation-guard | active cleanup evidence rationale |

## Index By Surface Class

### Root / Topology

- [0001 Roadmap, Decisions, And Changelog Route](0001-roadmap-decisions-changelog-route.md)
- [0003 Host Agent Mesh Route](0003-host-agent-mesh-route.md)
- [0004 Large Root Design Route](0004-srv-large-root-design-route.md)
- [0008 Change Close Decision Review Gate](0008-change-close-decision-review-gate.md)
- [0009 Decision Record Evolution Route](0009-decision-record-evolution-route.md)
- [0020 Artifact Evidence Cleanup Route](0020-artifact-evidence-cleanup-route.md)

### Generated / Readout

- [0002 Decision Index Route](0002-decision-index-route.md)
- [0003 Host Agent Mesh Route](0003-host-agent-mesh-route.md)
- [0009 Decision Record Evolution Route](0009-decision-record-evolution-route.md)
- [0013 Machine Atlas Maps Route](0013-machine-atlas-maps-route.md)
- [0014 Machine Atlas Reader Profile Packets](0014-machine-atlas-reader-profile-packets.md)
- [0017 Stack Observability Bridge Consumer](0017-stack-observability-bridge-consumer.md)
- [0018 Self-Awareness Observability Layer](0018-self-awareness-observability-layer.md)
- [0019 Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md)
- [0020 Artifact Evidence Cleanup Route](0020-artifact-evidence-cleanup-route.md)

### Runtime / Resource

- [0005 Zram Headroom Routing](0005-zram-headroom-routing.md)
- [0006 Doctor Self-Maintenance Route](0006-doctor-self-maintenance-route.md)
- [0007 OS Abyss Heartbeat Reaction Response Chain](0007-os-abyss-heartbeat-reaction-response-chain.md)
- [0008 Change Close Decision Review Gate](0008-change-close-decision-review-gate.md)
- [0010 Typing Journal Preservation Route](0010-typing-journal-preservation-route.md)
- [0011 E2B Resident Selection Route](0011-e2b-resident-selection-route.md)
- [0012 Causal Spine Bridge Route](0012-causal-spine-bridge-route.md)
- [0017 Stack Observability Bridge Consumer](0017-stack-observability-bridge-consumer.md)
- [0018 Self-Awareness Observability Layer](0018-self-awareness-observability-layer.md)
- [0019 Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md)

### AI / Resident Selection

- [0011 E2B Resident Selection Route](0011-e2b-resident-selection-route.md)
- [0019 Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md)
- [0020 Artifact Evidence Cleanup Route](0020-artifact-evidence-cleanup-route.md)

### Storage / Artifact Cleanup

- [0004 Large Root Design Route](0004-srv-large-root-design-route.md)
- [0020 Artifact Evidence Cleanup Route](0020-artifact-evidence-cleanup-route.md)

### Typing / Journaling

- [0010 Typing Journal Preservation Route](0010-typing-journal-preservation-route.md)
- [0012 Causal Spine Bridge Route](0012-causal-spine-bridge-route.md)

### Bridge / Causal Spine

- [0012 Causal Spine Bridge Route](0012-causal-spine-bridge-route.md)
- [0017 Stack Observability Bridge Consumer](0017-stack-observability-bridge-consumer.md)
- [0018 Self-Awareness Observability Layer](0018-self-awareness-observability-layer.md)
- [0019 Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md)

### Observability

- [0017 Stack Observability Bridge Consumer](0017-stack-observability-bridge-consumer.md)
- [0018 Self-Awareness Observability Layer](0018-self-awareness-observability-layer.md)

### Maps / Atlas

- [0013 Machine Atlas Maps Route](0013-machine-atlas-maps-route.md)
- [0014 Machine Atlas Reader Profile Packets](0014-machine-atlas-reader-profile-packets.md)
- [0015 Machine RAG Trace Loop](0015-machine-rag-trace-loop.md)
- [0016 Machine Context Refresh Automation](0016-machine-context-refresh-automation.md)

### RAG / Evidence Trace

- [0015 Machine RAG Trace Loop](0015-machine-rag-trace-loop.md)
- [0016 Machine Context Refresh Automation](0016-machine-context-refresh-automation.md)
- [0019 Self-Awareness Full Stack Coverage](0019-self-awareness-full-stack-coverage.md)

### Memory / Memo Intake

Memo candidates can feed this lane, but they do not become accepted decisions
until a numbered record lands here.

Route:

```text
{{ABYSS_MACHINE_STATE}}/memo/candidates
-> reviewed rationale
-> {{ABYSS_MACHINE_ETC}}/decisions/NNNN-speaking-name.md
-> {{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json
-> optional aoa-memo export receipt
```

## Index By Guard Family

- decision index freshness: [0002](0002-decision-index-route.md)
- agent mesh registration: [0003](0003-host-agent-mesh-route.md)
- large-root source boundary: [0004](0004-srv-large-root-design-route.md)
- resource/memory launch classification: [0005](0005-zram-headroom-routing.md)
- safe self-maintenance authority: [0006](0006-doctor-self-maintenance-route.md)
- owner-gated response boundary: [0007](0007-os-abyss-heartbeat-reaction-response-chain.md)
- decision-review closeout enforcement: [0008](0008-change-close-decision-review-gate.md)
- decision-record evolution and review-log enforcement: [0009](0009-decision-record-evolution-route.md)
- preservation-first journal compaction: [0010](0010-typing-journal-preservation-route.md)
- resident E2B selection and deterministic-default routing: [0011](0011-e2b-resident-selection-route.md)
- causal-spine bridge and freshness semantics: [0012](0012-causal-spine-bridge-route.md)
- machine atlas route signals: [0013](0013-machine-atlas-maps-route.md)
- reader-profile packet boundary: [0014](0014-machine-atlas-reader-profile-packets.md)
- machine RAG trace loop: [0015](0015-machine-rag-trace-loop.md)
- machine context refresh automation: [0016](0016-machine-context-refresh-automation.md)
- stack observability bridge boundary: [0017](0017-stack-observability-bridge-consumer.md)
- self-awareness observability layer: [0018](0018-self-awareness-observability-layer.md)
- self-awareness full stack coverage: [0019](0019-self-awareness-full-stack-coverage.md)
- resident stack-organ evidence: [0019](0019-self-awareness-full-stack-coverage.md)
- artifact cleanup evidence and vault restore guard: [0020](0020-artifact-evidence-cleanup-route.md)

## Promotion Path

A decision can influence current law only when the owning source surface is
updated. For example:

- host direction moves through `{{ABYSS_MACHINE_ETC}}/ROADMAP.md`
- docs hierarchy moves through `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- agent route shape moves through `{{ABYSS_MACHINE_ETC}}/DESIGN.AGENTS.md`
- topology moves through `{{ABYSS_MACHINE_ETC}}/TOPOLOGY.md`
- bridge shape moves through `{{ABYSS_MACHINE_ETC}}/STACK-BRIDGE.md`
- exact host mutation history moves through `{{ABYSS_MACHINE_STATE}}/changes/`
- memory candidates move through `{{ABYSS_MACHINE_STATE}}/memo/` and reviewed
  `aoa-memo` intake, not directly into accepted source law

After promotion, rebuild and validate the relevant generated surfaces.

## Validation

```bash
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine docs audit --json
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
```
