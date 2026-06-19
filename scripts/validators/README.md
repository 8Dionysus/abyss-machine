# Validators

This directory is reserved for focused source-tree validators. The first
validation lane is documented in `docs/validation/VALIDATOR_TOPOLOGY.md`.

`path_policy.py` validates the shared install/root path contract that keeps
bootstrap, CLI imports, generated state roots, `/srv` storage planes, and
typing/nervous organs pointed at one policy source.

`artifact_signature_policy.py` validates the public artifact identity and
signature policy that feeds contract ABI signatures, local provenance packet
shape, the portable OS Abyss runner contract, and later release
provenance/signing lanes.
`release_artifact_policy.py` validates the release-artifact lane that maps
publishable artifact classes to required sidecar/provenance controls without
performing signing.
