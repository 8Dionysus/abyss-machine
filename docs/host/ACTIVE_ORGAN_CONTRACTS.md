# Active-Organ Host Contracts

`abyss-machine` owns two reference-only admission contracts and one
reference-lab erasure owner extension in the active-organ spine:

| Contract | Owner role | Source |
| --- | --- | --- |
| C18 `HostCapabilitySnapshotReference` | cite a fresh, sanitized host capability snapshot | `schemas/active-organ-host-capability-snapshot-reference.schema.json` |
| C19 `HostResourceStoragePlanReference` | carry host admission over the existing resource plan and storage preflight | `schemas/active-organ-host-resource-storage-plan-reference.schema.json` |
| ER6 `active-organ-host-erasure-owner-extension-v0` | bind host-owned erasure evidence and recovery posture into the memo C14-C17 manifest | `schemas/active-organ-host-erasure-owner-extension-v0.schema.json` |

The pure cross-field implementation is
`src/abyss_machine/active_organ_contracts.py`. Public-safe positive and
negative cases live under `mechanics/host-facts/examples/` and are exercised by
`tests/public_smoke/test_active_organ_host_contracts.py`.

## C18 boundary

C18 contains refs, versions, digests, timestamps, freshness, policy, and
sanitized capability classes. It does not contain raw `/proc`, device
inventory, model paths, hostnames, process lists, absolute host paths, or
private latest payloads.

A `current` C18 requires every cited capability to be current and the envelope
to be valid. The capture command and every cited capability artifact must be
owned by `abyss-machine` and retained in `source_refs`. C18 remains evidence
only; SDK, stack, and eval consumers cannot infer memory truth or permission
from it.

## C19 boundary

C19 does not replace `abyss_machine_resource_plan_v1` or
`abyss_machine_storage_write_preflight_v1`. It pins their exact refs and maps
the host decision into one bounded disposition:

| Resource plan | C19 disposition |
| --- | --- |
| `allow`, current and valid | `start`, or `soften` with explicit constraints |
| `force_required` or an explicit soft block | `defer` |
| `deny` or an owner denial | `deny` |

A storage-writing request additionally requires positive requested bytes, an
allowlisted machine-owned target class, a machine-owned target ref, and the
storage preflight ref. A no-write request must carry none of them.

C19 always keeps `launch_executed=false`. It may start, defer, soften, or deny
host admission for new work, but it cannot mutate an existing workload,
project root, stack root, memory object, or authority policy. Actual launch
remains with the workload owner through the existing resource-launch route.

## Shadow and canary admission

`admit_shadow_workload` is a pure C18/C19 join. It returns a content-addressed
host admission without launching work or authoring memory meaning.

`admit_canary_workload` reuses that exact host decision and only adds the
separate memory consumer identity
`codex_owner_orientation_canary_v0`. The runtime consumer remains
`abyss-stack`. The added fields explicitly keep delivery semantic authority
and canary effect authority at `none`; the inherited host effect ceiling
remains `host_admission_only`. Another memory consumer fails closed.

Neither admission is a runtime launch, deployment, semantic-memory decision,
policy approval, permission grant, or stack mutation. The source-local Phase 8
lab may consume the canary admission as evidence, but live host projection
still requires the normal owner route.

## ER6 host-local erasure boundary

ER6 is the only distributed-erasure surface whose C16 target class may be
`host`, and its worker remains exactly `abyss-machine`. The owner extension
records a managed-root class, digest-only target refs, physical evidence ref,
rebuild/recovery check, result, residue, and explicit retention exceptions.
It does not disclose an absolute host path or the erased subject.

Project-root and stack-root mutation are forbidden. The extension is
owner-local evidence only: it cannot claim canonical memory deletion, raw
session deletion, runtime or backup purge, model unlearning, global
completion, or deployment. An unavailable physical check, recovered material,
or residue must remain visible and block the composed private-memory
deployment gate.

The Phase 11 implementation is a public-safe reference-lab contract. It does
not touch `/etc/abyss-machine`, `/srv/abyss-machine` runtime state, services,
timers, caches, or physical storage.

## Versioning and migration

Both contracts use strict `1.0.0` schemas and fail closed on unknown fields or
versions. Once landed, v1 is immutable. A semantic change requires:

1. a new versioned schema;
2. old-versus-new positive and negative fixtures;
3. exact consumer compatibility evidence;
4. a bounded migration and rollback route;
5. a separate live-host projection decision.

The repository contracts do not activate live `/etc`, `/var/lib`, services,
timers, resource launches, or stack consumption. Installed-host projection is
a later owner landing and must use the normal bootstrap, change-ledger, and
source/install/runtime parity routes.

## Validation

```bash
python -m pytest -q tests/public_smoke/test_active_organ_host_contracts.py
PYTHONPATH=src python scripts/ci_gate.py --mode source-fast
PYTHONPATH=src python scripts/generate_contract_abi_signatures.py --check
PYTHONPATH=src python scripts/generate_scaffold_index.py --check
```
