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
  `abyss-machine artifacts build-sidecars`, `sign`, `verify`,
  `release-check`, `bundle-register`, `bundle-registry`, and
  `trust-coverage` commands consume this policy for the `public_source_seed`,
  external package subjects such as `aoa_sdk_python_distribution`, external
  runtime config subjects such as `abyss_stack_runtime_config_bundle`,
  generated proof reader subjects such as
  `aoa_evals_generated_report_index_bundle`, and OS Abyss local provenance
  bundle roundtrips. External repo bundle manifests may use the repo-qualified
  policy reference `repo:abyss-machine/manifests/artifact_signature_policy.manifest.json`.
