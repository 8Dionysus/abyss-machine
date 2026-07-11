# Memory Controller

The Memory Controller is the event-driven host memory-governance service. It
observes PSI, cgroup, zram, systemd, runtime registrations, and queued resource
starts; it admits new background work through bounded grants while preserving
protected and unknown workloads.

## Ownership

- Git source owns controller code, the `shadow` policy template, the empty
  registry template, the entrypoint, tests, and the systemd unit skeleton.
- `/etc/abyss-machine` owns the rendered host policy and registry.
- `/run/user/$UID/abyss-machine/memory-controller` owns ephemeral queue,
  grants, registrations, admission, sockets, and action locks.
- `/srv/abyss-machine/tmp/memory-steward/controller` owns local evidence and
  calibration state.

The installed launcher routes `memory controller` directly to the resident
service module and routes every other command to the ordinary CLI. Package
installation uses `abyss_machine.entrypoint:main` for the same behavior.

## Fresh Machine

Bootstrap projects a `shadow` policy, an empty static registry, the controller
package, and `abyss-memory-controller.service`. The core profile can then be
enabled through the normal profile route:

```bash
scripts/abyss-machine-bootstrap install --profile linux-systemd-core --apply --json
scripts/abyss-machine-bootstrap enable-profile linux-systemd-core --now --json
abyss-machine memory controller validate --json
abyss-machine memory controller status --json
```

`shadow` mode observes and records decisions without live queue admission or
lifecycle action execution. Host activation is an explicit local policy
change after registry contracts, validation, and representative workload
evidence are ready. Runtime workloads register and unregister through:

```bash
abyss-machine memory controller register --contract-file CONTRACT.json --json
abyss-machine memory controller unregister --workload-id ID --json
```

## Resource Admission

`abyss-machine resource launch` creates runtime-only demand reservations for
medium-or-larger starts. When the controller advertises fresh `queue_live`
admission, only unattended background starts enter the controller queue.
Operator-visible starts remain outside the queue. Grants are followed by a
fresh resource plan and an atomic startup lease; request, grant, and lease
files are removed after completion or timeout.

The relevant request controls are:

```bash
abyss-machine resource plan --memory-demand-mib MIB --demand-key ID --demand-owner OWNER --json
abyss-machine resource launch --unattended --memory-demand-mib MIB --queue-priority N --queue-deadline SEC --json -- COMMAND...
```

## Upgrade Rehearsal

The public rehearsal validates upgrade, rollback, and reapply without touching
live roots:

```bash
python scripts/validators/memory_controller_upgrade_rehearsal.py --seed-mode synthetic --json
python scripts/validators/memory_controller_upgrade_rehearsal.py --seed-mode host --json
```

Host mode copies the current installed launcher, package, public seed, policy,
registry, unit, and enablement state into temporary roots. It also takes a
consistent read-only SQLite backup of the live evidence database, checks that
its decision sequence covers the observed live checkpoint, and exposes only
counts and digests in the rehearsal report. It then proves:

- the upgraded launcher, package, and public seed match source bytes;
- controller validation succeeds with the copied host policy and registry;
- local policy, registry, evidence database, and enablement remain unchanged;
- rollback restores the copied old code byte-for-byte;
- a second refresh returns to the source-owned projection.

## Live Rollout

The live route is intentionally separate from rehearsal:

1. Capture controller status, sequence, service state, installed code digests,
   local config digests, and a rollback copy.
2. Run the host change preflight for the installed launcher and package.
3. Stop `abyss-memory-controller.service` for the package replacement window.
4. Apply `refresh-code` with the admitted install-bundle selector.
5. Reload the user manager and start the controller.
6. Require source/install parity, controller validation, increasing evidence
   sequence, memory/resource validation, and the host quick lane.
7. Restore the rollback copy and previous service state if any gate fails.

Once the unified source projection is proven, any older host-only projection
broker is retired from active paths. Its immutable snapshot may remain inside
the bounded rollback archive, but it is no longer an installed code authority.
