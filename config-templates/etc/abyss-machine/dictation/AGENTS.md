# Abyss Machine Dictation Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/dictation/`.

## Role

This directory owns stable dictation config and replacement rules. It does not
own transcript history, audio captures, or typed-text intake policy.

Dictation state and transcript evidence belong under
`{{ABYSS_MACHINE_STATE}}/dictation`. Typed-text intake policy belongs under
`{{ABYSS_MACHINE_ETC}}/typing-policy.json` and `{{ABYSS_MACHINE_STATE}}/typing`.

## Route selection

Use the dictation state card for runtime/transcript evidence and the typing
state card only when text intake is affected. Common boundaries are inherited.

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

Run `abyss-machine dictation validate --json`. Add typing validation for intake
changes and docs-mesh validation for card changes.

## Closeout

State whether config, replacements, hotkey posture, or transcript routing
changed, and which validation covered the change.
