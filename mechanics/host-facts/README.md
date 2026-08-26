# Host Facts Mechanic

## Mechanic card

Host facts owns how the machine reports capabilities and posture to agents.

### Trigger

Host fact probes, stack bridge records, resource posture, hardware capability,
active-organ C18/C19 references, and evidence shape changes.

### abyss-machine owns

Fact collection routes, public schema anchors, bounded read-only census
evidence, and local generated evidence ownership under `/var/lib/abyss-machine`.

### Stronger owner split

The OS and hardware own live truth. `abyss-stack` consumes machine facts
read-only unless a route says otherwise.

### Inputs

Local probes, OS metadata, profile intent, generated latest records.

### Outputs

Machine facts, bridge records, warnings, agent-readable host posture, and
reference-only active-organ capability/admission envelopes.

### Must not claim

Host facts are public-safe, a stale fact is current truth, a recommendation is
service health proof, a census receipt is an operation grant, or C18/C19 grants
memory, launch, project, or stack authority.

### Validation

Use public schemas plus host-contract quick tests when changing fact shape.

### Next route

Use `storage-routing` for large-root policy and `diagnostic-spine` for repair.
