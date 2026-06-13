# Abyss Machine TTS Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/ai/tts/`.

## Role

This directory holds TTS benchmark and probe helpers. It is a helper lane for
experiments, not the stable speech runtime contract.

Runtime status and evidence belong under `/var/lib/abyss-machine/ai` and the
owning speech/dictation routes.

## Operating Contract

- Input: TTS probe source, operator benchmark intent, model/cache route, and
  speech/dictation owner context.
- Output: benchmark/probe helpers and evidence records; generated audio,
  scratch files, and model blobs stay outside this source tree.
- Owner: `/var/lib/abyss-machine/ai` for AI evidence and
  `/var/lib/abyss-machine/dictation` for speech route evidence.
- Tools: local benchmark helpers plus `abyss-machine ai ... --json` and
  `abyss-machine dictation ... --json`.
- Next route: dictation route before speech I/O claims; AI config route before
  promoting a probe into a stable runtime path.
- Verify: `abyss-machine ai validate --json`, `abyss-machine dictation validate
  --json`, and `abyss-machine docs mesh-validate --json`.

## Read Before Editing

Read:

- `/srv/abyss-machine/tools/ai/AGENTS.md`
- `/var/lib/abyss-machine/ai/AGENTS.md`
- `/var/lib/abyss-machine/dictation/AGENTS.md` when speech input/output routes
  are affected

## Boundaries

- Keep benchmark outputs out of the tools tree.
- Do not promote a probe into the default TTS route without config, evidence,
  and validation.
- Use `/srv/abyss-machine/cache` and `/srv/abyss-machine/tmp` for large model
  or scratch artifacts.

## Validation

```bash
abyss-machine ai validate --json
abyss-machine dictation validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State the probe helper changed, hardware/runtime assumptions, output location,
and validation status.
