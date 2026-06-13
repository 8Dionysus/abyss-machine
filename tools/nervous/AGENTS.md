# Abyss Machine Nervous Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/nervous/`.

## Role

This directory holds helper tools for local nervous-system capture and
calibration. It is not the facts store, policy store, or capture archive.

Config belongs under `/etc/abyss-machine/nervous`. Facts and validation evidence
belong under `/var/lib/abyss-machine/nervous`. Large captures belong under
`/srv/abyss-machine/storage/nervous`.

## Operating Contract

- Input: capture/calibration helper source, nervous policy/config, and operator
  intent.
- Output: helper behavior and capture evidence pointers; raw captures and
  facts route to storage or `/var/lib/abyss-machine/nervous`.
- Owner: `/etc/abyss-machine/nervous` owns policy; `/var/lib/abyss-machine/nervous`
  owns observed facts and validation evidence.
- Tools: `abyss-machine nervous ... --json` and explicit local launch/probe
  helpers.
- Next route: `browser-capture/AGENTS.md` for browser launch helpers; typing
  route when typed input or browser context is involved.
- Verify: `abyss-machine nervous validate --json` and `abyss-machine docs
  mesh-validate --json`.

## Read Before Editing

Read:

- `/etc/abyss-machine/AGENTS.md`
- `/srv/abyss-machine/tools/AGENTS.md`
- `/etc/abyss-machine/nervous/AGENTS.md`
- `/var/lib/abyss-machine/nervous/AGENTS.md`

## Boundaries

- Do not store captures or retrieval packs in the tools tree.
- Do not weaken privacy policy from helper behavior.
- Browser helpers must not become unattended capture policy by themselves.

## Validation

```bash
abyss-machine nervous validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State which helper moved, the owning nervous source/config route, and where any
capture evidence landed.
