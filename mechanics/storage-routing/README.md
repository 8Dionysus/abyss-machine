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

### Next route

Use `host-facts` for machine posture and `local-ai-runtime` for AI caches.
