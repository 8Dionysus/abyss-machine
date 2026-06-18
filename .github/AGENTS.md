# AGENTS.md

## Guidance for `.github/`

`.github/` is this repository's GitHub platform surface: workflows, PR
templates, CODEOWNERS, and repository metadata.

Read the root `AGENTS.md` first. Root `AGENTS.md` owns repository identity,
host/public-state boundaries, the branch/PR/CI/merge route, and the shortest
local validation path. This file owns only GitHub-native files under
`.github/`. Use `.github/GITHUB_SURFACE.md` as the short human map for this
directory.

Do not add `.github/README.md`: GitHub can select it as the repository homepage
README and hide the source-checkout front door.

Do not encode sibling-repo doctrine, private workstation assumptions, host
secrets, or hidden release behavior here. Do not add workflow steps that mutate
installed `/etc/abyss-machine`, generated `/var/lib/abyss-machine`, large
`/srv/abyss-machine` state, sibling repositories, or deployed runtime state
without explicit owner routing. Keep GitHub automation public-safe,
deterministic, and weaker than source-owned repository docs. Do not make CI
green by weakening the guardrail that should catch drift.

## Platform Sync

Keep `.github/CODEOWNERS`, `.github/pull_request_template.md`, workflow names,
and branch-protection expectations aligned with the root route card.

`Repo Validation` is the landing check expected by the root GitHub landing
workflow and by the protected `main` branch. The workflow must expose a check
named `Repo Validation`, not only a workflow with that display name. If that
check is added, renamed, split, or its meaning changes, update the root route,
PR expectations, branch protection, and this file in the same change.

When workflow or repository-policy files change, report:

- GitHub surface touched
- local validation run
- whether `Repo Validation` was added, renamed, skipped, or changed
- whether branch protection and auto-delete settings still match the sibling
  repository family
- remaining platform risk

## Verify

Use the root `AGENTS.md` verification path for the changed surface. For
GitHub-only edits, inspect the workflow YAML and run the nearest repo-local
static, release, or validation check when available. If branch protection or
repository settings are part of the change, verify them with the GitHub API
instead of relying on the web UI by memory.
