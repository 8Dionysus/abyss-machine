# 0002 Decision Index Route

## Status

accepted

## Date

2026-05-13

## Index Tags

- generated/readout
- decision-index
- documentation-topology
- validation-guard

## Context

`abyss-machine` now has durable decision records, but reading every record is
too slow for quick orientation. Future agents need a compact way to answer what
changed when and why before opening the full source record.

The risk is creating a second source of truth: an index can make decisions easy
to find, but it must not become stronger than the Markdown records or current
source contracts.

## Options Considered

- Keep only `decisions/README.md` as a hand-maintained table.
- Add a generated compact JSON index under `{{ABYSS_MACHINE_STATE}}/docs/`.
- Add a richer query database before enough decision records exist.

## Decision

Add a generated compact decision index:

- command: `abyss-machine docs decisions-index --json`
- generated path: `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json`
- source records: `{{ABYSS_MACHINE_ETC}}/decisions/*.md`

The generated index extracts title, status, date, source surfaces, summaries,
follow-up route, validation commands, and source hashes.

## Rationale

This gives agents fast access to what changed when and why without forcing them
to scan every decision record. It also lets `docs audit` detect stale generated
decision indexes after source records change.

Keeping the index generated protects the source-of-truth boundary: decisions
remain Markdown records, and current source surfaces still define what the
machine does now.

## Consequences

Decision records must be rebuilt into the index after changes.

`docs audit` should fail if decision records cannot be parsed or if the generated
index is stale.

Richer querying and filtering should wait until repeated use proves that the
compact JSON index is not enough.

## Boundaries

The generated index is a read model only. It must not become stronger than the
Markdown decision records, and decision records must not become stronger than
the current source surfaces they explain.

## Current Applicability

As of 2026-05-21, this decision remains active and is extended by decision
`0009`: the generated index now also carries and validates dated
current-applicability and review-log evidence. The generated JSON remains a read
model only.

## Review Log

- 2026-05-21: Extended the index contract to require `Current Applicability`
  and `Review Log` sections with dated entries, as formalized by decision
  `0009`.

## Source Surfaces

- `{{ABYSS_MACHINE_ETC}}/decisions/`
- `{{ABYSS_MACHINE_ETC}}/decisions/README.md`
- `{{ABYSS_MACHINE_ETC}}/decisions/AGENTS.md`
- `{{ABYSS_MACHINE_ETC}}/DOCS.md`
- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/docs/decisions-index.min.json`

## Follow-up Route

Validate through:

```bash
abyss-machine docs decisions-index --json
abyss-machine docs audit --json
abyss-machine docs mesh-validate --json
abyss-machine topology validate --json
```

## Validation

- `abyss-machine docs decisions-index --json`
- `abyss-machine docs audit --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine topology validate --json`
