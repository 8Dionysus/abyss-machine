# Local AI Runtime Mechanic

## Mechanic card

Local AI runtime owns host-managed AI helper processes and runtime placement
that are not `abyss-stack` service substrate.

### Trigger

Host AI helper tools, model/runtime caches, accelerator probes, and ai-local
profile changes.

### abyss-machine owns

Host resource guards, runtime/cache placement rules, helper scripts, and
public-safe local capability evidence.

### Stronger owner split

`abyss-stack` owns application runtime services. Model providers own licenses
and distribution terms. The operator owns downloads, activation, and cache
retention.

### Inputs

Host capabilities, approved model paths, runtime roots, resource policy, and
operator intent.

### Outputs

Bounded helper processes, runtime reports, resource refusals/warnings, and
cache-routing evidence.

### Must not claim

Model weights are public source, a local benchmark is portable truth, or a
host helper proves stack service health.

### Validation

Use dry-run resource planning, the affected AI/dictation tests, and public
boundary scans. Heavy or download work must also follow the machine storage
and resource-admission policy.

### Implementation route

Current AI, TTS, dictation, token-accounting, and runtime adapter ownership is
indexed in [LIVE_ADAPTERS.md](../../docs/host/LIVE_ADAPTERS.md). Historical
package landings remain in [LANDING_LOG.md](LANDING_LOG.md). Source modules,
tests, and those owner maps carry the detailed inventory; this mechanic card
keeps only the stable boundary and route.

Keep model weights, benchmark output, generated audio, and runtime state
outside Git.

### Next route

Use `storage-routing` for caches, `host-facts` for capability reports, and
`diagnostic-spine` for runtime diagnosis.
