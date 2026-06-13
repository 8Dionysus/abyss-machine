# 0010 Typing Journal Preservation Route

## Status

accepted

## Date

2026-05-23

## Index Tags

- typing
- journal-preservation
- compact-history
- storage-guard
- validation-guard

## Current Applicability

As of 2026-05-23, typed-input and browser-interaction journaling must preserve
important evidence before reducing storage. Storage pressure is handled through
lossless compression, compact per-event history, derived readmodels, and sparse
full-state checkpoints, not by deleting canonical journals.

Append-only JSONL writers that may run from overlapping timers, services, or
manual commands must serialize appends with a file lock and preserve corrupted
historical bytes before repairing an active JSONL file.

For AT-SPI text-event intake, every observed event keeps a compact history row.
Full listener state belongs in `latest.json` and sparse checkpoints because
duplicating the full state for every accessibility event caused severe write
amplification without adding proportional evidence.
`typing validate` enforces the compact-row search and causal-binding contract
with `atspi_compact_history_search_binding_keys`.

## Context

The typing subsystem is part of the machine's long-horizon memory surface. It
answers what was written, where it was entered, who or what it was addressed to,
and which route captured it.

The AT-SPI listener had begun appending the full cumulative listener state to
daily JSONL on every accessibility text event. That produced multi-gigabyte
daily files and one 10 GiB+ class offender, while most rows repeated the same
state and sample metadata. A cleanup-only response would have risked losing
evidence; a checkpoint-only response would have made the event stream less
recoverable.

## Options Considered

- Delete or truncate large daily files:
  unacceptable because important journaling evidence may be lost.
- Keep full listener snapshots on every event:
  preserves evidence but creates runaway storage amplification.
- Write only sparse checkpoints:
  small, but loses the per-event diagnostic trace.
- Preserve compact per-event history and sparse full checkpoints:
  keeps event continuity while avoiding repeated full-state duplication.

## Decision

Use a tiered journal route for typing and related interaction evidence:

- canonical accepted text events remain in their owning event journals;
- high-frequency diagnostic routes write compact per-event records;
- full listener/readmodel state is kept in `latest.json` and sparse checkpoints;
- oversized historical JSONL is compressed losslessly, not deleted;
- generated readmodels may summarize or index, but they do not replace source
  journals.

For AT-SPI text events specifically, compact rows preserve event index, event
type, status, source adapter, app/window/url/role metadata, capture-gate summary,
typing event id when present, and listener counters. Compact rows do not store
additional raw text.

## Rationale

This separates evidence from duplication. The machine keeps the causal trail of
observed events while avoiding the failure mode where a large repeated JSON
snapshot impersonates useful memory.

The route also gives future agents a stable rule: reduce storage by changing the
shape and tier of evidence, not by erasing the evidence stream.

## Consequences

- Positive: per-event AT-SPI history remains available for audit and debugging.
- Positive: storage growth becomes proportional to event metadata rather than
  full listener state size.
- Positive: lossless `.zst` archival is acceptable for old bulky history.
- Tradeoff: reconstructing a full listener state for an arbitrary historical
  event requires joining compact history with nearby checkpoints and canonical
  event journals.
- Watch: other high-frequency journals should follow the same tiering if they
  show snapshot amplification.

## Boundaries

This decision does not authorize raw keylogging, password capture, hidden-field
capture, browser secret capture, or automatic action from typed input.

This decision does not make derived readmodels stronger than source journals.

This decision does not prohibit retention policy, but any retention route must
first classify canonical evidence, compact event evidence, derived readmodels,
and regenerable noise.

## Review Log

- 2026-05-23: Initial record. Accepted preservation-first compact journaling for
  typing AT-SPI history and future high-frequency journal repairs.
- 2026-05-23: Added `atspi_compact_history_search_binding_keys` validation so
  compact rows must keep search identity, accessibility identity, capture-gate
  state, and canonical typing-event links when text-role evidence is persisted.
- 2026-05-23: Extended the preservation route from storage amplification to
  append integrity. `safe_append_jsonl` and `safe_append_text` now serialize
  appends under an exclusive file lock. The corrupted
  `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/2026/05/2026-05-21.jsonl`
  active file was repaired only after preserving the original bytes as
  `.corrupt-20260523T160430.bak`.
- 2026-05-23: Refined typing causal-awareness scoring so privacy-gated
  AT-SPI metadata-only browser/chrome events count guarded project/entity axes
  instead of impersonating true missing causal evidence. Actual project gaps in
  Codex, shell, browser-extension, and AI-transcript routes remain visible.

## Source Surfaces

- `{{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/typing/atspi-text-events`
- `{{ABYSS_MACHINE_STATE}}/docs/agents-mesh-validate/2026/05/2026-05-21.jsonl`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/jsonl-append-integrity-repair-20260523`
- `{{ABYSS_MACHINE_STATE}}/changes/closed/typing-atspi-compact-event-history-20260523`

## Validation

- `PYTHONPYCACHEPREFIX=/tmp/abyss-machine-pycache python3 -m py_compile {{ABYSS_LOCAL_LIBEXEC_DIR}}/abyss-machine`
- `abyss-machine typing browser-atspi-selftest --json`
- `abyss-machine typing validate --json`
- `abyss-machine typing coverage --json`
- `abyss-machine docs decisions-index --json`
- `abyss-machine docs mesh-validate --json`
- `abyss-machine docs audit --json`
- `abyss-machine topology validate --json`
- `abyss-machine graph validate --json`
- `abyss-machine stack-bridge validate --json`

## Follow-up Route

Future storage-pressure repairs in typing, memory, process, nervous, or browser
interaction journals should first decide whether a file is canonical evidence,
compact event evidence, a derived readmodel, or regenerable noise. Preserve or
compress evidence before considering deletion.
