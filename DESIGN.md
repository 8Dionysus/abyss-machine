# abyss-machine Design

`abyss-machine` is the host-machine organ for Abyss OS. Its source repo defines
how a fresh Linux/systemd machine becomes observable and routable by agents.
The installed machine creates private local state; the repo publishes only the
seed, contracts, templates, and validators needed to recreate that state safely.

## Shape

- Source truth lives in this repository.
- Installed host config is rendered into `/etc/abyss-machine`.
- Durable generated evidence is created under `/var/lib/abyss-machine`.
- Large mutable host planes live under `/srv/abyss-machine`.
- Ephemeral runtime state belongs under `/run/abyss-machine`.

These roots must stay connected by bootstrap and validators, but they must not
collapse into one public mirror.

## Public Source Districts

- `config-templates/`: public-safe source for rendered host config.
- `systemd/`: installable Linux/systemd unit skeletons.
- `env/`: public-safe environment examples.
- `schemas/`: permissive v1 data-shape anchors.
- `scripts/`: stable operator entrypoints and validators.
- `tools/`: helper probes and migration tools not yet mechanic-owned.
- `mechanics/`: durable host movement packages.
- `docs/`: route, install, operations, testing, validation, and publication
  context.
- `tests/`: public smoke and imported host-contract development lanes.

## Bootstrap Flow

```text
repo source
  -> doctor checks local capabilities
  -> profile renders public-safe config and unit skeletons
  -> install creates local roots and CLI entrypoints
  -> validators create host facts under /var/lib/abyss-machine
  -> opt-in units maintain typing, nervous, diagnostics, and runtime evidence
```

## Stop Lines

- Do not vendor live evidence, captures, secrets, or model caches.
- Do not make `abyss-machine` own `abyss-stack` runtime decisions.
- Do not remove typing/nervous machinery to make publication easy.
- Do not claim cross-OS parity; this seed is Linux/systemd first.
- Do not convert every helper into a mechanic until ownership is real.
