# Typing Intake Mechanic

## Mechanic card

Typing intake owns how typed activity becomes opt-in, redacted host evidence.

### Trigger

Typing adapters, AT-SPI capture, browser/native-host integration, saved-text
scan, Codex session-tail intake, privacy gates, or typing profile changes.

### abyss-machine owns

Collector machinery, opt-in profile units, redaction/retention contract
shapes, public-safe adapters, and validators for local generated evidence.

### Stronger owner split

The user owns consent and private content. Applications own their raw text.
The public repository owns mechanisms and policy shape, not captured life.

### Inputs

Opt-in unit state, privacy policy, local text-event sources, redaction rules,
and explicit operator intent.

### Outputs

Local typing facts, bounded context summaries, warnings, and validation
records.

### Must not claim

Collection is enabled by default, raw text is public-safe, redaction makes all
downstream use harmless, or captured context authorizes action.

### Validation

Use the affected public smoke tests, host-contract quick lane, typing/privacy
validators, and package-specific browser or extension checks when relevant.

### Implementation route

Current shell, editor, browser, AT-SPI, saved-text, Codex, persistence, and
readmodel adapter ownership is indexed in
[LIVE_ADAPTERS.md](../../docs/host/LIVE_ADAPTERS.md). Source modules and tests
carry the detailed contract inventory; generated typed evidence remains local
host state.

### Next route

Use `nervous-local` for derived memory intake and `diagnostic-spine` for
freshness or repair.
