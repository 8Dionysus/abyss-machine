# Validation

Full validation starts with the owner claim/evidence graph and a bound receipt.
Use the exact command in the repository
[root readiness and release route](../../VALIDATION.md#root-readiness-and-release).

`docs/validation/validation_lanes.json` declares the runner contexts and command
sequences that remain the independent serial completeness oracle. The owner
graph maps claims and risks to the same leaf scope, uses only the admitted
two-worker pytest scheduling delta, and runs through the exact clean shared
`aoa-sdk` scheduler pin. GitHub Actions, local CLI runs, installed host
schedulers, and release pipelines use the same owner entrypoint.

The same root route owns the sub-second edit-loop contract check.

Serial release mode retains the sequential oracle and immediate rollback.
Changed-path routing remains shadow-only and no cross-run receipt is accepted
as current proof.

Host-contract tests exist for development and migration, but they are separate
from the public install smoke lane.

The nervous real-session fixed-point and full/file/record method comparison is
documented in `docs/testing/NERVOUS_INCREMENTAL_DAG.md`; its timing receipts are
shadow evidence and never replace the owner claim/evidence graph.

Artifact signature policy and generated contract ABI signatures are part of the
public lane. They classify what should be ABI-fingerprinted, SBOMed, attested,
signed, or C2PA-tagged when an artifact class becomes publishable.

The release-artifact lane is a cheap CI policy check for publishable artifact
classes:

```bash
python scripts/ci_gate.py --mode release-artifact
```

It does not require keys, OIDC, or private host state.
