# Validators

This directory is reserved for focused source-tree validators. The first
validation lane is documented in `docs/validation/VALIDATOR_TOPOLOGY.md`.

`artifact_signature_policy.py` validates the public artifact signature policy
that feeds contract ABI signatures, the portable OS Abyss runner contract, and
later release provenance/signing lanes.
`release_artifact_policy.py` validates the release-artifact lane that maps
publishable artifact classes to required sidecar/provenance controls without
performing signing.
