# Storage Routing Mechanic

## Mechanic card

Storage routing owns where host-local mutable and large artifacts belong.

### Trigger

Storage policy, cache placement, runtime roots, backup routing, and reclaim
audit changes, including the C19 storage-plan reference boundary.

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
templates. C19 may cite an existing write-preflight decision but does not
perform a write.

### Must not claim

Large paths are safe to delete, vault contents are public, or project roots can
be moved by host-layer automation. C19 can never widen the allowlisted
machine-owned root set.

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

Persistent candidate classification is a separate hard-gated layer owned by
`storage_candidate_contracts` and `storage_candidate_adapters`. It stores exact
candidate history under `/var/lib/abyss-machine/storage/candidates`, measures
physical same-filesystem bytes, distinguishes Podman unique bytes, joins
runtime/Vault/Git/process/claim evidence, and fails closed on incomplete scans
or fingerprint drift. `.aoa` candidates are accepted only from the
session-memory owner's maintenance dry-run. The layer records validation,
approval, and external receipts but does not add automatic deletion.

### Next route

The storage monitor keeps at most 168 capacity samples per mount in compact
state. `storage capacity` records the same observation before the monitor's
resource admission, allowing the next sample when monitor admission is
deferred by memory pressure. It keeps the historical available-endpoint net
rate for compatibility, and when all retained samples carry `reserved_bytes`,
derives physical free-space consumption from available plus reserved bytes.
Reserve-policy shifts are reported explicitly; depletion headroom holds the
current reserve fixed while using that physical rate. Older samples without
reserve values stay on an explicit legacy basis rather than inventing zeros.
The forecast requires four observations spanning at least three hours on the
same filesystem. A missing mount or insufficient history produces an unknown
forecast. Cleanup remains part of the observed rate; the result is an
extrapolation, not a write reservation or a deletion decision.

Use `host-facts` for machine posture and `local-ai-runtime` for AI caches.
