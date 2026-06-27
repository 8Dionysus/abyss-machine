# Typing Intake Mechanic

## Mechanic card

Typing intake owns how typed activity becomes opt-in, redacted host evidence.

### Trigger

Typing adapters, AT-SPI capture, saved-text scan, Codex session tail, privacy
gates, and typing profile changes.

### abyss-machine owns

Collector machinery, opt-in profile units, redaction contracts, retention
policy shape, and validators for local generated evidence.

### Stronger owner split

The user owns consent and private content. Applications own their raw text.
The public repo owns mechanisms, not captured life.

### Inputs

Opt-in unit state, privacy policy, local text-event sources, redaction rules.

### Outputs

Local typing facts, derived summaries, warnings, and validation records.

### Must not claim

Collection is enabled by default, raw text is public-safe, or redaction makes
all downstream use harmless.

### Validation

Use public smoke plus host-contract quick tests when changing typed evidence
shape.

### Live adapter route

Shared latest/history persistence, local JSONL history reads, and Codex
session-tail filesystem reads for typing and nervous organs start in
`abyss_machine.typing_nervous_adapters`. Codex prompt/session-tail text
extraction, user-message route recognition, context-envelope normalization,
duplicate semantics, metadata/context ingest plans, and public-safe event
summaries live in `abyss_machine.typing_codex_semantics`.
Browser/WebExtension native-host ingest plans, AI transcript cleanup/metadata
plans, synthetic selftest documents, and native-host response envelopes live in
`abyss_machine.typing_browser_adapters`. AT-SPI focused snapshot, text-event
sample/metadata/debounce, and generic GUI selftest semantic plans live in
`abyss_machine.typing_atspi_adapters`. Keep the remaining typing adapters
bounded by source type: framed native-host byte transport, temporary browser
profile/WebExtension live probes, saved-text scan, remaining `pyatspi`
traversal/listener runtime, browser AT-SPI selftest execution, focused-browser
selftests, and privacy probes. The mechanic owns the route and tests;
generated typed evidence remains local host state.

### Next route

Use `nervous-local` for derived memory intake and `diagnostic-spine` for repair.
