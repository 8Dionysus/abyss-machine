# Manifests

Manifests are executable scaffold contracts consumed by validators and release
checks.

- `repo_scaffold.manifest.json`: expected root files, districts, docs, and
  mechanics package shape.
- `bootstrap_profiles.manifest.json`: expected bootstrap profiles and units.
- `public_boundary.manifest.json`: publication-blocking path and token rules.
- `schema_inventory.manifest.json`: schema files that must remain present and
  valid JSON.
- `artifact_signature_policy.manifest.json`: artifact identity posture, ABI,
  portable runner, local provenance, SBOM/ML-BOM, SLSA/in-toto,
  Sigstore/Cosign, C2PA, and deferred TUF/SCITT policy by artifact class. The
  `abyss-machine artifacts build-sidecars`, `sign`, `verify`, and
  `release-check` commands consume this policy for the `public_source_seed`,
  external package subjects such as `aoa_sdk_python_distribution`, and OS Abyss
  local provenance bundle roundtrips.
