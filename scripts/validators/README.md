# Validators

This directory is reserved for focused source-tree validators. The first
validation lane is documented in `docs/validation/VALIDATOR_TOPOLOGY.md`.

`path_policy.py` validates the shared install/root path contract that keeps
bootstrap, CLI imports, generated state roots, `/srv` storage planes, and
typing/nervous organs pointed at one policy source.

`first_run_installed_projection.py` validates the fresh-machine installed
projection. It applies bootstrap into isolated temporary roots, runs the
temp-installed CLI without source-checkout `PYTHONPATH`, compares critical
source and installed command surfaces, checks projected package modules and
public seed read models, proves typing/nervous config and unit skeletons are
present, and keeps profile activation dry-run/opt-in. The live installed CLI
comparison is advisory unless `--require-host-installed` is passed for host
closeout.

`typing_nervous_policy.py` validates the first organ-specific policy split:
typing and nervous path/service constants remain CLI-compatible while deriving
captures, indexes, browser tooling, tmp/cache, and user-systemd paths from the
shared root contract.

`typing_nervous_refresh_logic.py` validates the pure refresh decision helpers
that classify soft resource gates, bounded recent-index debounce windows,
refresh assessment state, latest-status readmodel health, index-attempt
debounce plus final status contexts, fact-state assembly, action-record
builders, and the final refresh document builder. The CLI must use
`abyss_machine.typing_nervous_refresh` for this logic instead of redefining it
in the monolith.

`artifact_signature_policy.py` validates the public artifact identity and
signature policy that feeds contract ABI signatures, local provenance packet
shape, the portable OS Abyss runner contract, and later release
provenance/signing lanes.
`release_artifact_policy.py` validates the release-artifact lane that maps
publishable artifact classes to required sidecar/provenance controls without
performing signing.
