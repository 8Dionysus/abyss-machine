# Validation

Validation starts with the manifest-backed source-fast lane:

```bash
python scripts/ci_gate.py --mode source-fast
```

`docs/validation/validation_lanes.json` declares the runner contexts and command
sequences for OS Abyss validation. GitHub Actions, local CLI runs, installed
host schedulers, and release pipelines use those command sequences.

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
