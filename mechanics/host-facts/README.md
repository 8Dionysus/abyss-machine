# Host Facts Mechanic

## Mechanic card

Host facts owns how the machine reports capabilities and posture to agents.

### Trigger

Host fact probes, stack bridge records, resource posture, hardware capability,
and evidence shape changes.

### abyss-machine owns

Fact collection routes, public schema anchors, and local generated evidence
ownership under `/var/lib/abyss-machine`.

### Stronger owner split

The OS and hardware own live truth. `abyss-stack` consumes machine facts
read-only unless a route says otherwise.

### Inputs

Local probes, OS metadata, profile intent, generated latest records.

### Outputs

Machine facts, bridge records, warnings, and agent-readable host posture.

### Must not claim

Host facts are public-safe, a stale fact is current truth, or a recommendation
is service health proof.

### Validation

Use public schemas plus host-contract quick tests when changing fact shape.

### Next route

Use `storage-routing` for large-root policy and `diagnostic-spine` for repair.
