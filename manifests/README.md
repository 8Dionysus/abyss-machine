# Manifests

Manifests are executable scaffold contracts consumed by validators and release
checks.

- `repo_scaffold.manifest.json`: expected root files, districts, docs, and
  mechanics package shape.
- `bootstrap_profiles.manifest.json`: expected bootstrap profiles and units.
- `public_boundary.manifest.json`: publication-blocking path and token rules.
- `schema_inventory.manifest.json`: schema files that must remain present and
  valid JSON.
- `artifact_signature_policy.manifest.json`: ABI, portable runner,
  provenance, SBOM, SLSA/in-toto, Sigstore/Cosign, and C2PA policy by artifact
  class.
