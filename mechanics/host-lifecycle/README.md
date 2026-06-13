# Host Lifecycle Mechanic

## Mechanic card

Host lifecycle owns how the public seed becomes an installed host layer.

### Trigger

Bootstrap, install, doctor, profile enablement, update, and repair changes.

### abyss-machine owns

Install flow, dry-run reporting, local root creation, CLI entrypoint install,
and host-layer validation routes.

### Stronger owner split

The operator owns apply intent. The OS owns package/service availability. Live
state is generated on the target host.

### Inputs

Source checkout, profile selection, target roots, operator apply flags.

### Outputs

Rendered config, installed unit skeletons, CLI entrypoints, empty local roots,
and reviewable bootstrap reports.

### Must not claim

Service health, private host parity, or destructive migration safety without a
specific validator.

### Validation

Run public smoke tests and bootstrap dry-runs.

### Next route

Use `config-projection` for rendered config and `diagnostic-spine` for health.
