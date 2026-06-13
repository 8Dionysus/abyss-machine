# Abyss Machine Typing Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/typing/`.

## Role

This directory holds helper tools for typed-text intake integration, including
browser native-host wrappers and browser extension source/package material.

It does not own typed-text policy or event evidence. Policy lives under
`/etc/abyss-machine/typing-policy.json`; evidence belongs under
`/var/lib/abyss-machine/typing`.

## Operating Contract

- Input: native-host wrapper source, browser extension source/package material,
  typing policy, and operator integration intent.
- Output: thin integration helpers and signed/uploadable package artifacts;
  typed-text evidence routes to `/var/lib/abyss-machine/typing`.
- Owner: `/etc/abyss-machine/typing-policy.json` owns capture policy;
  `/var/lib/abyss-machine/typing` owns event evidence.
- Tools: `abyss-machine typing ... --json`, browser native-host wrappers, and
  extension packaging/signing routes.
- Next route: `firefox-extension/AGENTS.md` for extension source/package work;
  nervous route when page context is collected.
- Verify: `abyss-machine typing validate --json`, `abyss-machine nervous
  validate --json`, and `abyss-machine docs mesh-validate --json`.

## Read Before Editing

Read:

- `/etc/abyss-machine/AGENTS.md`
- `/srv/abyss-machine/tools/AGENTS.md`
- `/var/lib/abyss-machine/typing/AGENTS.md`
- `/etc/abyss-machine/nervous/AGENTS.md` when browser context capture is
  affected

## Boundaries

- Do not store typed text, secrets, browser profiles, or private transcripts in
  the tools tree.
- Keep native-host wrappers thin and routed through stable `abyss-machine`
  commands.
- Browser extension artifacts must preserve source/package/version traceability.

## Validation

```bash
abyss-machine typing validate --json
abyss-machine nervous validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State helper paths changed, extension/native-host impact, package artifacts, and
validation status.
