# Operations

Operations docs describe how a local machine maintains evidence after install:
doctor probes, validators, opt-in units, and local repair loops.

Generated records stay under local state roots, not in this repo.

## Host Install Closeout

For source-only work, use the temp projection validator and do not mutate the
live host ledger:

```bash
python scripts/validators/first_run_installed_projection.py --json
```

For an actual host projection, close the loop explicitly:

1. Run `abyss-machine changes preflight` for the host surfaces that will change.
2. Apply `scripts/abyss-machine-bootstrap install --profile linux-systemd-core --apply --json`; this fails closed unless the durable `bootstrap_install_bundle` trust-gate admits the selected registry latest.
3. Run system and user `daemon-reload` for the unit skeletons that were
   projected.
4. Run `python scripts/validators/first_run_installed_projection.py --require-host-installed --json`.
5. Run the narrow installed smoke checks for touched organs, such as
   `abyss-machine typing validate --json` or
   `abyss-machine nervous validate --json`.
6. Record and close the change ledger with rollback notes and decision review.

The temp validator never enables units, runs collectors, records live ledger
entries, or writes raw typing/browser evidence.
