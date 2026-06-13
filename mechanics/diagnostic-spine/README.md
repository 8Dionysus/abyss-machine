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

### Next route

Use the relevant mechanic package named by the diagnostic result.
