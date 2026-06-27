# Diagnostic Spine Mechanic

## Mechanic card

Diagnostic spine owns how the host layer proves posture and points to repair.

### Trigger

Doctor checks, validator topology, freshness, topology audit, heartbeat, and
repair handoff changes.

### abyss-machine owns

Diagnostic command surfaces, report schemas, freshness interpretation, and
host-layer repair hints.

### Stronger owner split

Services own their real health. Validators own evidence quality. Operators own
repair intent.

### Inputs

Doctor probes, generated latest records, systemd state, test lanes, source tree.

### Outputs

Diagnostic reports, validator results, warnings, repair candidates, and
machine-readable causal links.

### Must not claim

A warning is a fix, a stale report is current truth, or a diagnostic result
authorizes destructive repair.

### Validation

Use `docs/validation/VALIDATOR_TOPOLOGY.md` and public smoke checks.

### Live adapter route

Diagnostic adapters should separate probe execution from diagnosis shape:
systemd, filesystem, process, and validator probes gather current host facts;
contract modules decide bounded status and repair hints. A diagnostic warning is
evidence for routing, not authority to mutate the host.

### Next route

Use the relevant mechanic package named by the diagnostic result.
