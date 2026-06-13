# Config Projection Mechanic

## Mechanic card

Config projection owns how public-safe source files become local host config.

### Trigger

Changes to `config-templates/`, `env/`, schema anchors, and render helpers.

### abyss-machine owns

Template layout, placeholder expectations, bootstrap render behavior, and the
public/private config boundary.

### Stronger owner split

Operators own real secrets and local overrides. The installed host owns rendered
config freshness.

### Inputs

Templates, env examples, host profile variables, operator-provided secrets.

### Outputs

Rendered `/etc/abyss-machine` files and public-safe reports of what was written.

### Must not claim

Templates contain live secrets, rendered config is source truth, or sync is safe
without explicit operator intent.

### Validation

Run bootstrap render dry-run and public smoke tests.

### Next route

Use `host-lifecycle` for install/apply and `diagnostic-spine` for repair.
