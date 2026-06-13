# Abyss Machine Dictation Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/dictation/`.

## Role

This directory owns stable dictation config and replacement rules. It does not
own transcript history, audio captures, or typed-text intake policy.

Dictation state and transcript evidence belong under
`{{ABYSS_MACHINE_STATE}}/dictation`. Typed-text intake policy belongs under
`{{ABYSS_MACHINE_ETC}}/typing-policy.json` and `{{ABYSS_MACHINE_STATE}}/typing`.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/dictation/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md` when text intake is affected

Before durable mutation, run:

```bash
abyss-machine changes preflight --intent TEXT --surface {{ABYSS_MACHINE_ETC}}/dictation --json
```

## Boundaries

- Do not store raw transcripts, private audio, or session evidence here.
- Do not blur dictation replacement rules with typed-text capture policy.
- Do not add platform-specific hotkey behavior here unless the dictation route
  card and validator cover it.

## Validation

```bash
abyss-machine dictation validate --json
abyss-machine typing validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State whether config, replacements, hotkey posture, or transcript routing
changed, and which validation covered the change.
