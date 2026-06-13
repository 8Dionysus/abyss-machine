# Abyss Machine Browser Capture Tools

## Applies to

This card applies to `/srv/abyss-machine/tools/nervous/browser-capture/`.

## Role

This directory holds browser-launch helper tools for nervous browser capture
calibration. It is not a browser profile store and not capture policy.

## Operating Contract

- Input: browser launch helper source, operator calibration intent, and nervous
  capture policy.
- Output: launch behavior only; browser profiles, page content, and capture
  evidence route to their owning stores.
- Owner: `/etc/abyss-machine/nervous` owns capture policy;
  `/var/lib/abyss-machine/nervous` owns evidence.
- Tools: explicit launch wrappers such as `firefox-bidi-launch` plus
  `abyss-machine nervous ... --json`.
- Next route: typing route for typed input context; nervous state route for
  page/capture evidence.
- Verify: `abyss-machine nervous validate --json`, `abyss-machine typing
  validate --json`, and `abyss-machine docs mesh-validate --json`.

## Read Before Editing

Read:

- `/srv/abyss-machine/tools/nervous/AGENTS.md`
- `/etc/abyss-machine/nervous/AGENTS.md`
- `/var/lib/abyss-machine/nervous/AGENTS.md`
- `/var/lib/abyss-machine/typing/AGENTS.md` when typed input or browser context
  is involved

## Boundaries

- Do not store browser profiles, cookies, login databases, or page content here.
- Keep launch helpers explicit and inspectable.
- Do not turn a debugging port helper into unattended capture authority.

## Validation

```bash
abyss-machine nervous validate --json
abyss-machine typing validate --json
abyss-machine docs mesh-validate --json
```

## Closeout

State the launch behavior changed, privacy impact, and where any browser
capture evidence is stored.
