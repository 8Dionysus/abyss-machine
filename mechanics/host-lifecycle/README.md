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

### Live adapter route

Host lifecycle owns the source/install/runtime parity route: source CLI,
installed projection, bootstrap dry-runs, and host quick checks must agree on
public-safe behavior while private `/etc`, `/var/lib`, `/srv`, captures,
indexes, and secrets remain target-host state. Runtime closeout command
catalogs, profiles, and read-only vs latest/readmodel-refresh effect labels
live in `abyss_machine.host_lifecycle_parity`; validator scripts bind those
profiles to concrete installed paths and subprocess execution. Default/read
profiles stay read-only; explicit `*-refresh` profiles may update live
latest/readmodel state.

### Next route

Use `config-projection` for rendered config and `diagnostic-spine` for health.
