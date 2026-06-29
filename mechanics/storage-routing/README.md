# Storage Routing Mechanic

## Mechanic card

Storage routing owns where host-local mutable and large artifacts belong.

### Trigger

Storage policy, cache placement, runtime roots, backup routing, and reclaim
audit changes.

### abyss-machine owns

Public storage policy shape, host root classes, and audits that explain what is
regenerable, archive-worthy, or protected.

### Stronger owner split

Operators own deletion/offload intent. Vaults and backups are private. Running
services own active files until proved idle.

### Inputs

Storage policy, disk inventories, process refs, cache/runtime paths.

### Outputs

Reclaim reports, storage warnings, route recommendations, and public policy
templates.

### Must not claim

Large paths are safe to delete, vault contents are public, or project roots can
be moved by host-layer automation.

### Validation

Use dry-run audits and public boundary scans.

### Live adapter route

Storage cleanup planning uses `abyss_machine.storage_adapters` for the
active-process guard: process snapshot projection, path matching, and
`/proc/<pid>/fd` target inspection are fakeable adapter-owned IO, while
low-level process `/proc` snapshot collection is owned by
`abyss_machine.process_adapters`. The same storage adapter owns allowlisted
cleanup apply execution for package-manager clean, npm cache verify/clean, and
generated temp cleanup through fakeable command/euid/clock ports, plus hook
directory scan/execution through fakeable hook-runner and environment ports,
plus inventory path/disk measurement through fakeable `du`/disk-usage/clock/
path-scan ports. Cleanup action policy, hook stage/status contracts, inventory
drift, and pressure rules remain in `storage_contracts`; live inventory spec
selection, podman/memory input binding, configured hook directory/env/time
binding, apply preflight orchestration, latest/history writes, and rendering
remain CLI edge.

### Next route

Use `host-facts` for machine posture and `local-ai-runtime` for AI caches.
