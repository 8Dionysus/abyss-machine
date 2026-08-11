# Scripts

Stable commands live here. Helper probes that are not yet stable operator
interfaces may remain in `tools/` until a mechanic owns them.

Current public entrypoint:

- `abyss-machine-bootstrap`: render, install, refresh installed code/public-seed
  projections, and enable profile surfaces.
- `ci_gate.py`: run manifest-backed validation lanes from GitHub, OS Abyss
  local CLI, host schedulers, release pipelines, or agent loops.
- `generate_contract_abi_signatures.py`: build the public contract ABI
  signature read model from the artifact signature policy.
- `validators/release_artifact_policy.py`: validate publishable artifact
  class requirements and public-repo artifact boundaries.
- `release_check.py`: run the authoritative full owner claim/evidence graph by
  default, with an explicit independent serial oracle and rollback.
- `validation_evidence_graph.py`: validate the sub-second graph contract and
  invoke the exact pinned shared scheduler ABI for owner-local claims.
- `generate_scaffold_index.py`: regenerate the committed scaffold read model.
- `validate_local_stats_port.py`: delegate the owner-local stats contract to
  the `aoa-stats` protocol validator selected by the validation environment.
