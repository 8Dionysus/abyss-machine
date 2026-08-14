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

For an already-installed host where source/install/runtime parity drift is only
the installed CLI/package/public-seed projection, prefer the narrower route:

```bash
scripts/abyss-machine-bootstrap refresh-code --dry-run --json
scripts/abyss-machine-bootstrap refresh-code --apply --json
PYTHONPATH=src python scripts/validators/source_install_runtime_parity.py --summary --json
```

`refresh-code` does not render `/etc/abyss-machine` or systemd units, so no
daemon reload is needed unless another step changes unit files. It still
requires change-ledger preflight before live `/usr/local` mutation and a closeout
with rollback notes after parity and touched-organ smoke checks. Live-root
refresh uses the same admitted install-bundle selector as full install; the
artifact-gate skip remains limited to isolated projection rehearsals.

## Nervous Rebuild Control

Normal event, episode, and lexical-index builds use their incremental fixed
point. Use `--full-rebuild` on the corresponding `nervous ...-build` command
only for an explicit oracle comparison, manifest recovery, or rollback. A full
index build is host-expensive and must use `abyss-machine resource launch` when
run outside the installed scheduler.

Incremental state is policy-bound. A changed derivation ABI, output version,
thermal threshold set, source policy, stale or tampered append witness, or
cross-partition episode group automatically expands the work to a file or full
oracle. Do not suppress that fallback to recover latency.

If no source or policy vertex changed, the index verifies the locked source
snapshot and previous run identity without a write transaction. This no-op does
not advance the database `built_at`; it preserves the last run that actually
proved and stored new index content.

`nervous index-build --no-refresh-derived` is an experiment/debug route for an
index-only comparison. It must not replace the normal session path, which
refreshes events and episodes before indexing.
