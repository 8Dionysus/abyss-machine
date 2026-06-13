# Abyss Machine Firefox Typing Extension

## Applies to

This card applies to `/srv/abyss-machine/tools/typing/firefox-extension/`.

## Role

This directory holds the Firefox extension source and local package artifacts
for Abyss Machine typed-text intake.

Source files such as `manifest.json`, `background.js`, and `content.js` are the
local source for the extension package. Signed or uploadable artifacts here are
deliverables and must stay traceable to the source version.

## Operating Contract

- Input: `manifest.json`, extension JavaScript source, browser/native-host
  policy, and packaging/signing intent.
- Output: source zip or `.xpi` deliverables traceable to the source version;
  typed text and page-context evidence route to `/var/lib/abyss-machine`.
- Owner: extension source owns package contents; typing policy owns what may be
  collected; nervous policy owns browser context posture.
- Tools: browser extension source files, native-host route, Mozilla/web-ext
  validation/signing flow, and `abyss-machine typing ... --json`.
- Next route: update policy and validation before broadening capture scope;
  route package artifacts through `/srv/abyss-machine/artifacts` when needed.
- Verify: `abyss-machine typing validate --json`, `abyss-machine nervous
  validate --json`, `abyss-machine docs mesh-validate --json`, and current
  Mozilla/web-ext package validation when packaging changes.

## Read Before Editing

Read:

- `/srv/abyss-machine/tools/typing/AGENTS.md`
- `/var/lib/abyss-machine/typing/AGENTS.md`
- `/etc/abyss-machine/typing-policy.json`
- `/etc/abyss-machine/nervous/AGENTS.md` when browser context or page content
  routing changes

## Boundaries

- Do not add network access from the extension.
- Do not collect password, login, or secret fields.
- Do not broaden capture scope without updating policy, validation, and package
  evidence.
- Do not overwrite signed `.xpi` files without preserving the previous artifact
  or recording a rollback path.
- Keep generated build output under `build/` or `/srv/abyss-machine/artifacts`,
  not mixed with unrelated source files.

## Validation

```bash
abyss-machine typing validate --json
abyss-machine nervous validate --json
abyss-machine docs mesh-validate --json
```

When packaging changes, also verify the produced `.xpi` or source zip through
the current Mozilla/web-ext route before installing or uploading it.

## Closeout

State source files changed, package version/artifacts, install or signing
status, privacy impact, and validation run.
