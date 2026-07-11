# Install

Install starts from this source repo, renders public-safe templates, creates
empty local roots, and installs the CLI when explicitly applied.

The installed CLI surface is the entrypoint plus the `abyss_machine` package
modules under the configured libexec root. Bootstrap also projects compact
public seed read models under the adjacent share root so installed validators
can run without importing a source checkout.

The `bootstrap_install_bundle` archive must carry the bootstrap script, package
modules, config and systemd templates, schemas, and the repo-local `manifests/`
plus `generated/` read models. An extracted archive must be able to run
`scripts/abyss-machine-bootstrap doctor --dry-run --json` before any live host
mutation.

Dry-runs are the default review surface.

## Fresh-Machine Projection

Use the first-run validator to prove the install shape without touching live
host roots:

```bash
python scripts/validators/first_run_installed_projection.py --json
```

The validator performs a real `install --apply` into isolated temporary roots,
then runs the temp-installed CLI without `PYTHONPATH=src`. It checks:

- `/etc/abyss-machine` config projection;
- `/var/lib/abyss-machine` durable state root;
- `/srv/abyss-machine` cache, runtimes, storage, and tmp roots;
- `/run/abyss-machine` ephemeral runtime root;
- `/usr/local/bin`, `/usr/local/libexec`, and `/usr/local/share` equivalents;
- system and user unit skeletons;
- source-vs-temp-installed CLI command parity;
- critical artifact trust CLI option surfaces such as `materialize-subjects`,
  `trust-gate`, `evidence-promote`, `registry-latest`, and durable-only
  `trust-coverage`.

For a real host install closeout, run the same validator with
`--require-host-installed` after the host projection has been applied and the
systemd daemon reloads have completed.

## Installed Code Refresh

When the host is already installed and only the CLI package modules plus compact
public seed projection must be refreshed after a landed source change, use the
bounded refresh route instead of the full install route:

```bash
scripts/abyss-machine-bootstrap refresh-code --dry-run --skip-artifact-trust-gate --json
scripts/abyss-machine-bootstrap refresh-code --apply --artifact-record-id <bootstrap-install-bundle-record-id> --json
# or:
scripts/abyss-machine-bootstrap refresh-code --apply --artifact-subject-digest sha256:<bootstrap-install-bundle-subject> --json
```

`refresh-code` uses the same artifact trust-gate admission as full install, but
it does not render `/etc/abyss-machine` templates or systemd units. Host
closeout still needs change-ledger preflight, parity validation, and rollback
notes for `/usr/local/bin/abyss-machine`, `/usr/local/libexec/abyss-machine`,
and `/usr/local/share/abyss-machine`.
Live `--apply` requires the same admitted install-bundle selector as full
install. Use `--skip-artifact-trust-gate` only for dry-run review or isolated
projection rehearsals whose refresh mutation targets are redirected away from
live roots.

## Memory Controller Lifecycle

Fresh installs project the event-driven Memory Controller in `shadow` mode,
with an empty registry and an opt-in systemd unit. Existing hosts with an older
controller overlay use the isolated upgrade/rollback rehearsal before the live
code refresh. See [Memory Controller](../operations/MEMORY_CONTROLLER.md).
