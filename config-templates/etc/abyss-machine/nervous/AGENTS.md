# Abyss Machine Nervous Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/nervous/`.

## Role

This directory owns stable source config for the local nervous system:
sources, privacy, policy, and compact config indexes. It does not store
captures, retrieval packs, facts history, synthesis, or quality evidence.

Runtime evidence and read models belong under `{{ABYSS_MACHINE_STATE}}/nervous`.
Large private captures belong under `{{ABYSS_MACHINE_SRV}}/storage/nervous`.

## Read before editing

Read:

- `{{ABYSS_MACHINE_ETC}}/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/nervous/AGENTS.md`
- `{{ABYSS_MACHINE_STATE}}/typing/AGENTS.md` when typed input or browser
  context is affected
- `{{ABYSS_MACHINE_ETC}}/storage-policy.json` when capture storage changes

Before durable mutation, run:

```bash
abyss-machine changes preflight --intent TEXT --surface {{ABYSS_MACHINE_ETC}}/nervous --json
```

## Boundaries

- Privacy config is source policy. Do not weaken it from one calibration sample.
- Do not store screenshots, browser DOM captures, clipboard payloads, or private
  transcripts here.
- Nervous facts are evidence; they do not authorize automatic mutation.
- Noisy screenshot capture must stay explicit opt-in. Unattended capture should
  remain silent or fail visible in validation.

## Validation

```bash
abyss-machine nervous validate --json
abyss-machine typing validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State which policy/source/privacy file changed, which live facts or captures
were consulted, which validator proved the route, and what privacy risk remains.
