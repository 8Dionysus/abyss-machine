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

## Current Status

This first public seed intentionally keeps the installed CLI as a monolithic
module. The next hardening wave should split it into package modules only after
the public bootstrap and publication boundary are stable.

Known v1 portability debt: the monolithic CLI still contains historical
workstation defaults and fixture paths. New-machine bootstrap uses rendered
templates and profiles; modular path-policy extraction is the first follow-up
before claiming full host-agnostic behavior for every subcommand.
