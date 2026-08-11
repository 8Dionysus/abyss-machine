# Validation

Full validation starts with the owner claim/evidence graph and a bound receipt:

```bash
python scripts/release_check.py --sdk-root PATH_TO_PINNED_AOA_SDK --receipt /tmp/abyss-machine-validation.json
```

`docs/validation/validation_lanes.json` declares the runner contexts and command
sequences that remain the independent serial completeness oracle. The owner
graph maps claims and risks to the same leaf scope, uses only the admitted
two-worker pytest scheduling delta, and runs through the exact clean shared
`aoa-sdk` scheduler pin. GitHub Actions, local CLI runs, installed host
schedulers, and release pipelines use the same owner entrypoint.

For a sub-second edit-loop contract check, use:

```bash
python scripts/validation_evidence_graph.py --profile instant --sdk-root PATH_TO_PINNED_AOA_SDK
```

`python scripts/release_check.py --mode serial` retains the sequential oracle
and immediate rollback. Changed-path routing remains shadow-only and no
cross-run receipt is accepted as current proof.

Host-contract tests exist for development and migration, but they are separate
from the public install smoke lane.

Artifact signature policy and generated contract ABI signatures are part of the
public lane. They classify what should be ABI-fingerprinted, SBOMed, attested,
signed, or C2PA-tagged when an artifact class becomes publishable.

The release-artifact lane is a cheap CI policy check for publishable artifact
classes:

```bash
python scripts/ci_gate.py --mode release-artifact
```

It does not require keys, OIDC, or private host state.
