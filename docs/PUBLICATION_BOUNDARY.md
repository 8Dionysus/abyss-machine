# Publication Boundary

`abyss-machine` is published as a portable seed, not as a snapshot of one
workstation.

## Published

- CLI source and thin helper tools.
- Source contracts and policy templates from `/etc/abyss-machine`.
- systemd unit templates for Linux/systemd targets.
- typing and nervous-system machinery: adapters, capture gate, redaction,
  privacy controls, retention policy, validators, and opt-in unit templates.
- Bootstrap scripts that render host-local paths and create empty local roots.
- Public smoke tests and host contract tests.

## Not Published

- `/var/lib/abyss-machine`: generated facts, latest/index JSON, histories,
  process/memory/self-awareness evidence, typed events, transcripts, local memo,
  and validation output.
- `/srv/abyss-machine/cache`, `runtimes`, `storage`, `tmp`, `backups`, and
  private artifacts.
- `/abyss` vault contents, restic repositories, password files, or local backup
  manifests.
- Browser captures, screenshots, clipboard-derived facts, raw typed text
  histories, Codex sessions, and private retrieval packs.
- Installed binary archives, `.bak` files, signed extension packages, compiled
  caches, and one-off probe output.

## Lifecycle On A New Machine

```text
repo template
  -> bootstrap doctor probes local capabilities
  -> host profile renders /etc/abyss-machine
  -> validators create /var/lib/abyss-machine facts
  -> optional units maintain local evidence
  -> caches, runtimes, and models appear only when enabled
```

Typing and nervous-system collection are not removed for safety. They are
installed as opt-in organs: the code, policies, units, state roots, and
validators exist, while real collectors stay disabled until the operator enables
the corresponding profile and the selftests pass.
