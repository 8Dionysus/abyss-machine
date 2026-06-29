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
`/proc/<pid>/fd` target inspection are fakeable adapter-owned IO. The same
adapter owns allowlisted cleanup apply execution for package-manager clean, npm
cache verify/clean, and generated temp cleanup through fakeable command/euid/
clock ports. Cleanup action policy remains in `storage_contracts`; live
inventory/disk scans, hooks, apply preflight orchestration, latest/history
writes, and rendering remain CLI edge.

### Next route

Use `host-facts` for machine posture and `local-ai-runtime` for AI caches.
