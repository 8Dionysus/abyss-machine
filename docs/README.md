# Docs

Start here when the README is too small:

- `install/`: bootstrap and first-run notes.
- `operations/`: local maintenance and doctor posture.
- `profiles/`: capability-gated install profiles.
- `validation/`: validator and release lanes.
- `testing/`: test topology.
- `host/`: host-root and evidence model.
- `publication/`: public/private boundary.

## Source Homes

- Bootstrap and first-run behavior belongs in `docs/install/` plus
  `scripts/abyss-machine-bootstrap`.
- Public/private publication rules belong in `docs/publication/`.
- Validator lanes belong in `docs/validation/` and `scripts/validators/`.
- Release/artifact trust details belong in `manifests/artifact_bundles/` and
  the artifact policy manifest, not in the root README.
