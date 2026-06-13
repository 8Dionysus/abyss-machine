# Abyss Machine Topology Tools

This directory holds host-owned topology validation helpers.

The canonical validator is:

```bash
abyss-machine topology validate --json
```

The shell wrapper in this directory exists for operator convenience and for
future agents that are looking for a filesystem-local topology check, similar
to project-local topology skills.

## Operating Contract

- Input: topology helper source and host topology validation intent.
- Output: wrapper behavior only; topology facts and validation evidence route
  to `/var/lib/abyss-machine/topology`.
- Owner: `/etc/abyss-machine/TOPOLOGY.md`, `/etc/abyss-machine/AGENTS.md`, and
  `/var/lib/abyss-machine/topology/AGENTS.md`.
- Tools: `abyss-machine topology validate --json` first; shell wrapper only for
  local convenience.
- Next route: graph and stack-bridge validators when topology changes affect
  bridge or command surfaces.
- Verify: `abyss-machine topology validate --json` and
  `/srv/abyss-machine/tools/topology/check_abyss_machine_topology.sh`.

## Rules

- Keep the CLI validator authoritative; wrapper scripts should only call it or
  format its result.
- Do not copy project-local topology rules from `/srv/work` into this host
  layer. Borrow method only: zones, lifecycle, entrypoints, orphan checks, and
  executable validation.
- Do not scan or mutate `/srv/AbyssOS`, `/work`, or `/srv/work`.
- After changing topology docs, bridge entries, or change-ledger behavior, run
  both:

```bash
abyss-machine topology validate --json
/srv/abyss-machine/tools/topology/check_abyss_machine_topology.sh
```
