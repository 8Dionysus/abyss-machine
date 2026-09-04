# Abyss Machine Nervous Config

## Applies to

This card applies to `{{ABYSS_MACHINE_ETC}}/nervous/`.

## Role

This directory owns stable source config for the local nervous system:
sources, privacy, policy, and compact config indexes. It does not store
captures, retrieval packs, facts history, synthesis, or quality evidence.

Runtime evidence and read models belong under `{{ABYSS_MACHINE_STATE}}/nervous`.
Large private captures belong under `{{ABYSS_MACHINE_SRV}}/storage/nervous`.

## Route selection

Use the nervous state card for evidence, the typing state card only when typed
input/browser context is affected, and `storage-policy.json` when capture
storage changes.

Before durable mutation, run:

Run `VALIDATION.md` in this directory for the on-demand preflight.

## Boundaries

- Privacy config is source policy. Do not weaken it from one calibration sample.
- Do not store screenshots, browser DOM captures, clipboard payloads, or private
  transcripts here.
- Nervous facts are evidence; they do not authorize automatic mutation.
- Noisy screenshot capture must stay explicit opt-in. Unattended capture should
  remain silent or fail visible in validation.

## Validation

Run `abyss-machine nervous validate --json`. Add typing validation for typed or
browser intake and docs-mesh validation for card changes.

## Closeout

State which policy/source/privacy file changed, which live facts or captures
were consulted, which validator proved the route, and what privacy risk remains.
