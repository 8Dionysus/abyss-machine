# abyss-machine

`abyss-machine` is the portable public seed for the Abyss OS host-machine
layer. It makes a Linux/systemd host observable, routable, and maintainable
without publishing the private life of a workstation.

The repository contains source contracts, public-safe configuration templates,
the host CLI, unit skeletons, schemas, validators, and bootstrap logic. Private
facts, typed activity, browser captures, transcripts, process histories, model
caches, runtimes, backup data, and local indexes are created only on the
installed machine.

## Ownership boundary

`abyss-machine` owns host policy, facts, diagnostics, resource and storage
routing, opt-in typing/nervous intake, and host-managed AI helpers.
`abyss-stack` owns application runtime orchestration. Sibling AoA repositories
retain their own doctrine, memory, evaluation, routing, and proof authority.

## Source and runtime planes

| Plane | Role |
|---|---|
| This repository | Public source, contracts, templates, schemas, and tests |
| `/etc/abyss-machine` | Host-specific configuration rendered from public templates |
| `/usr/local/{bin,libexec,share}` | Installed CLI, package modules, and compact public seed |
| `/var/lib/abyss-machine` | Durable generated facts, indexes, and validation evidence |
| `/srv/abyss-machine` | Large mutable caches, runtimes, storage, and temporary work |
| `/run/abyss-machine` | Ephemeral runtime state and sockets |

Bootstrap connects these planes on a target host; it does not copy private
state from another machine.

## Repository map

| Path | Purpose |
|---|---|
| `src/abyss_machine/` | Python package and stable command implementation |
| `config-templates/` | Public-safe sources rendered into host configuration |
| `systemd/` | System and user unit skeletons |
| `mechanics/` | Durable host movements and their owner routes |
| `scripts/` | Stable bootstrap, validation, and release entrypoints |
| `tools/` | Bounded helper probes that are not stable interfaces |
| `schemas/`, `manifests/` | Data contracts and executable source inventories |
| `tests/` | Public smoke tests and fixture-backed host contracts |
| `docs/` | Install, operation, validation, host, and publication detail |

Start with [DESIGN.md](DESIGN.md) for system form,
[BOUNDARIES.md](BOUNDARIES.md) for stop-lines, and the
[mechanics atlas](mechanics/README.md) for durable host movements.

## Bootstrap and validation

Inspecting or rendering a checkout is dry-run first and does not change the
host. Exact development, bootstrap-smoke, host-contract, and release commands
live in the on-demand [root validation route](VALIDATION.md); its complete
owner gate binds the required clean `aoa-sdk` scheduler pin and receipt.
Validation-lane meaning and host-specific closeout are explained in
[docs/validation/README.md](docs/validation/README.md) and
[docs/testing/RELEASE_CHECK_ROUTE.md](docs/testing/RELEASE_CHECK_ROUTE.md).

## Implementation maps

The detailed adapter inventory is maintained in
[LIVE_ADAPTERS.md](docs/host/LIVE_ADAPTERS.md); command ownership is mapped in
[SUBSYSTEM_COMMANDS.md](docs/host/SUBSYSTEM_COMMANDS.md); validator ownership
is mapped in [VALIDATOR_TOPOLOGY.md](docs/validation/VALIDATOR_TOPOLOGY.md).
Those owner sources, the package modules, manifests, and tests carry current
implementation detail. This README intentionally remains a stable public
entrypoint rather than duplicating that changing inventory.

## Safety defaults

- Bootstrap and operator routes are dry-run first and fail closed.
- Typing and nervous machinery is installed as a first-class organ, but real
  collection remains opt-in.
- Never commit secrets, captures, transcripts, generated `/var/lib` state, or
  mutable `/srv` contents.
- This seed targets Linux with systemd; it does not claim cross-OS parity.
- Read the nearest `AGENTS.md` before changing an owned district.

The precise publication boundary is in
[PUBLICATION_BOUNDARY.md](docs/publication/PUBLICATION_BOUNDARY.md).
