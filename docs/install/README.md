# Install

Install starts from this source repo, renders public-safe templates, creates
empty local roots, and installs the CLI when explicitly applied.

The installed CLI surface is the entrypoint plus the `abyss_machine` package
modules under the configured libexec root. Bootstrap also projects compact
public seed read models under the adjacent share root so installed validators
can run without importing a source checkout.

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
  `trust-gate`, and `evidence-promote`.

For a real host install closeout, run the same validator with
`--require-host-installed` after the host projection has been applied and the
systemd daemon reloads have completed.
