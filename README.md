# abyss-machine

`abyss-machine` is the portable seed for the Abyss OS host-machine layer.

It publishes the organ that makes a machine legible to agents: the CLI, source
contracts, public-safe config templates, typing/nervous intake machinery,
systemd unit skeletons, validation routes, and bootstrap logic.

It does not publish the private life of a specific machine. Generated facts,
typed events, browser captures, transcripts, process histories, model caches,
runtimes, backup vaults, and local indexes are created locally by the installed
machine under `/var/lib/abyss-machine` and `/srv/abyss-machine`.

## Reading Route

Start with:

1. [AGENTS.md](AGENTS.md)
2. [DESIGN.md](DESIGN.md)
3. [BOUNDARIES.md](BOUNDARIES.md)
4. [mechanics/README.md](mechanics/README.md)
5. [docs/publication/PUBLICATION_BOUNDARY.md](docs/publication/PUBLICATION_BOUNDARY.md)

## Bootstrap Shape

```bash
python -m pip install -e .
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
scripts/abyss-machine-bootstrap install --profile linux-systemd-core --apply --json
```

The bootstrap CLI and installed `abyss-machine` CLI share
`abyss_machine.path_policy` for root defaults and environment overrides.
Typing/nervous path and service defaults live in
`abyss_machine.typing_nervous_policy`; refresh resource-gate and recent-index
debounce helpers, refresh assessment, latest-status classification, and
index-attempt, final-status, action-record, and refresh-document builders live in
`abyss_machine.typing_nervous_refresh`. These surfaces are re-exported or
adapted by the CLI for installed-host compatibility. A fresh machine
should render `/etc/abyss-machine`, create durable evidence under
`/var/lib/abyss-machine`, reserve large mutable planes under
`/srv/abyss-machine`, and keep ephemeral state under `/run/abyss-machine`
without copying private state from this workstation.

Typing and nervous-system collectors are installed as a first-class organ, but
real collection is opt-in:

```bash
scripts/abyss-machine-bootstrap enable-profile typing-intake --dry-run --json
scripts/abyss-machine-bootstrap enable-profile nervous-local --dry-run --json
```

## Public Boundary

Start with [docs/publication/PUBLICATION_BOUNDARY.md](docs/publication/PUBLICATION_BOUNDARY.md)
before adding files. The short rule is:

- publish source, contracts, config templates, schemas, validators, and tests;
- do not publish generated evidence or private local state.
- keep artifact signing policy explicit: ABI fingerprints for public contract
  surfaces, release provenance/signatures only for publishable artifacts.

## Test Lanes

Default public smoke:

```bash
python scripts/ci_gate.py --mode source-fast
```

Validation lanes are OS Abyss CLI contracts. GitHub Actions, local host
schedulers, release pipelines, and agent goal loops use the same
`scripts/ci_gate.py` entrypoints.

Host contract tests imported from the current workstation are kept for
development and migration work, but they are not the bootstrap smoke lane:

```bash
python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
```

Release checks:

```bash
python scripts/ci_gate.py --mode release-artifact
python scripts/release_check.py
python scripts/release_check.py --include-host-contracts
```

First executable ABI/signs bundle slice:

```bash
abyss-machine artifacts build-sidecars --manifest manifests/artifact_bundles/public_source_seed.bundle.json --bundle-dir /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts sign /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts verify /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts release-check /tmp/abyss-machine-public-source-seed --json
```

OS Abyss local provenance verifier sample:

```bash
abyss-machine artifacts build-sidecars --manifest manifests/artifact_bundles/host_local_evidence.sample.bundle.json --bundle-dir /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts sign /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts verify /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts release-check /tmp/abyss-machine-host-local-evidence --json
```

## Current Status

The installed CLI remains mostly monolithic, but shared root policy,
typing/nervous organ policy, and typing/nervous refresh decision helpers have
been split into package modules with public validators. The typing/nervous
refresh latest-status classifier is also module-owned, with the CLI kept as a
thin adapter to live `latest.json` and systemd state. Refresh index-attempt
debounce context, final status/summary context, and snapshot, index, retry, and
synthesis action-record builders are module-owned. The final refresh document
shape is also module-owned, while live index launch, synthesis orchestration,
and persistence still stay in the CLI. Known v1
portability debt remains in subsystem command glue and some historical
workstation fixture paths; further hardening should move command implementation
behind smaller modules before claiming full host-agnostic behavior for every
subcommand.
