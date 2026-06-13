# Abyss Machine Decisions

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/decisions/` and all descendants.

## Role

`decisions/` holds durable rationale records for host-layer documentation,
topology, routing, validation, bridge, and source-boundary choices.

Decision records explain why a choice was made. Current source surfaces define what
the machine does now.

This lane is the accepted rationale lane. It is not the host-local memory port.
Memo candidates can feed decisions, but accepted decisions live here.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- `{{ABYSS_MACHINE_ETC}}/ROADMAP.md`
- `{{ABYSS_MACHINE_ETC}}/CHANGELOG.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/README.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/TEMPLATE.md`
- `{{ABYSS_MACHINE_STATE}}/memo/AGENTS.md` when promoting a memo candidate
- nearest subsystem `AGENTS.md` when the decision is subsystem-local
- `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json` after it has been
  rebuilt from source records

## Boundaries

- Do not treat decisions as stronger than current source contracts.
- Do not use this directory as a task tracker, changelog, telemetry log, or
  command catalog.
- Do not store private transcripts, secrets, browser content, raw screenshots,
  raw typed text, or generated evidence dumps here.
- Do not record decisions for tiny, self-evident, purely local, or already
  better-documented changes.
- Do not use decisions to claim ownership over AoA, ToS, `abyss-stack`, work,
  game roots, or reviewed `aoa-memo` memory truth.
- Do not hand-edit `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json`.
- Do not renumber accepted records.

## Filename Contract

Decision records must follow `TEMPLATE.md` and use stable numbered names:

```text
NNNN-speaking-name.md
```

The Markdown title must start with the same number:

```markdown
# NNNN Speaking Name
```

Use the next sequence number for new accepted or proposed records. If a route is
replaced, add a new record and mark the older record `superseded`; keep the old
path stable so generated indexes and external references do not break.

## Evolution Contract

Treat an accepted decision as a historical rationale record with an explicit
current-applicability layer. Do not silently rewrite the original context,
options, decision, or rationale so they look as if they were always current.

Every decision record must carry:

- `Current Applicability`: dated statement of what still applies, what changed,
  what was superseded, and what source route owns current behavior.
- `Review Log`: dated amendments, reviews, and substantive applicability
  changes.

When a later change affects an existing decision:

- If the original rationale remains valid, update the same record with a dated
  `Review Log` entry and refresh `Current Applicability`.
- If a specific operational claim is obsolete, mark that claim with Markdown
  strikethrough in `Current Applicability` or the dated review entry, then state
  the replacement route.
- If the route or rationale is replaced, create a new `NNNN-speaking-name.md`
  record, mark the older record `superseded`, and add a dated review entry that
  points to the successor.
- If only a small generated/readout detail changed, use the change close
  decision review gate and do not pad records with noise.

## Indexing Contract

`README.md` is the durable human/agent index. It must carry:

- operating card
- current decisions table
- record evolution pipeline
- index by surface class
- index by guard family
- memo candidate promotion route
- promotion path
- validation commands

`{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json` is generated. It must be
rebuilt after any decision record, README, template, or lane-law change.

## Decision Review Gate

Run this review after meaningful structural, ownership, workflow, route-law,
validator-authority, bridge-contract, documentation-topology, or host-wide
policy changes.

Record a decision when:

- several plausible paths existed and the rationale will matter later
- future agents may repeat the same debate without a durable "why"
- a source-of-truth boundary, host root role, owner route, validator authority,
  bridge contract, or documentation topology changed
- a host-wide convention changed how future work should be closed out
- a reviewed memo candidate becomes accepted host-layer rationale

Do not record a decision when the change is tiny, self-evident, purely local, or
already explained by a more specific active source surface. In that case,
closeout should say `Decision review: no record needed` with a short reason.

## Validation

After changing this lane, run:

```bash
abyss-machine docs mesh --json
abyss-machine docs mesh-validate --json
abyss-machine docs decisions-index --json
abyss-machine docs audit --json
abyss-machine topology validate --json
abyss-machine graph validate --json
abyss-machine stack-bridge validate --json
```

If the change touched a memo candidate route, also validate the local memo port.

## Closeout

Report:

- decision records added, renamed, superseded, or changed
- source surfaces the decisions cite
- whether the next sequence number is clear
- whether `ROADMAP.md` or `CHANGELOG.md` moved
- whether `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json` was rebuilt
- generated docs mesh and audit status
- change ledger record
- rollback route
- skipped checks and remaining risk
