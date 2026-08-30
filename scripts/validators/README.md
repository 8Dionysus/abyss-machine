# Validators

`scripts/validators/` contains focused source-tree checks. Validators bind
repository paths and assemble evidence; product behavior belongs in the
owning `abyss_machine` contract or adapter module.

The authoritative lane and dependency map is
[VALIDATOR_TOPOLOGY.md](../../docs/validation/VALIDATOR_TOPOLOGY.md). Use the
stable orchestration entrypoints in `scripts/ci_gate.py` and
`scripts/release_check.py` instead of inventing another aggregate runner.

## Catalog

| Validator | Contract checked |
|---|---|
| `artifact_bundle_roundtrip.py` | Public artifact bundle build/verify round trip |
| `artifact_signature_policy.py` | Artifact identity, signature, and producer-admission policy |
| `bootstrap_contract.py` | Bootstrap command and projection contract |
| `first_run_installed_projection.py` | Isolated fresh-machine install, source/install parity, and opt-in defaults |
| `manifest_integrity.py` | Manifest syntax, references, and required source surfaces |
| `mechanics_topology.py` | Mechanic package inventory, cards, and non-placeholder sublanes |
| `path_policy.py` | Shared install, state, cache, runtime, and typing/nervous roots |
| `public_boundary.py` | Secret/live-state exclusions and public-safe source boundary |
| `release_artifact_policy.py` | Release artifact classes and required provenance controls |
| `repo_topology.py` | Public source districts and documentation sections |
| `schema_integrity.py` | Public schema inventory and parseability |
| `source_install_runtime_parity.py` | Compact source/install/runtime closeout evidence |
| `typing_nervous_policy.py` | Typing/nervous path, service, privacy, and opt-in policy |
| `typing_nervous_refresh_logic.py` | Pure refresh/readiness contract parity |

`_common.py` supplies shared reporting and path helpers; it is not an
operator entrypoint.

## Running checks

Run the narrowest validator while editing:

```bash
python scripts/validators/VALIDATOR.py
```

Then use the source gate for repository-level closure:

```bash
python scripts/ci_gate.py --mode source-fast
```

Use `release_check.py` with the pinned `aoa-sdk` scheduler for the complete
owner claim/evidence gate. Host-required and live checks remain separate from
portable source proof; see
[docs/validation/README.md](../../docs/validation/README.md) and
[RELEASE_CHECK_ROUTE.md](../../docs/testing/RELEASE_CHECK_ROUTE.md).

When a validator moves, update its owning source contract, topology document,
validation-lane manifest, focused tests, and generated evidence through their
builders. Do not copy the package/module ownership inventory into this README.
