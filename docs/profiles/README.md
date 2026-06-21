# Profiles

Profiles select capability bundles such as `linux-systemd-core`,
`typing-intake`, `nervous-local`, `ai-local`, `backup-vault`, and
`stack-bridge`.

Profiles make units and roots available. Collection or service activation
remains opt-in unless an apply path explicitly enables it.

`typing-intake` includes the typing nervous-refresh timer as an opt-in helper
so typed-intake facts, freshness, and nervous handoff stay part of the same
agent-OS organ. The public bootstrap proof only renders and dry-runs these
units; it does not enable collectors or collect raw typed/browser content.
