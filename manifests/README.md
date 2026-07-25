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
  Sigstore/Cosign, C2PA, TUF-style update metadata, and SCITT integration
  policy by artifact class. The
  `abyss-machine artifacts build-sidecars`, `sign`, `verify`,
  `release-check`, `evidence-promote`, `bundle-register`, `bundle-registry`,
  `registry-latest`, `bundle-registry-upgrade`, `requirements`,
  `producer-profiles`, `scenarios`, `affected`, `update-lane`,
  `update-verify`, `trust-gate`, and `trust-coverage` commands
  consume this. The `affected` read-model reports repo/source-ref drift with
  explicit blocking versus accepted-lag state and can infer sibling owner repos
  from absolute OS Abyss paths before matching owner-relative source refs. This
  policy for the `public_source_seed`,
  external package subjects such as `aoa_sdk_python_distribution`, external
  runtime config subjects such as `abyss_stack_runtime_config_bundle`,
  generated proof reader subjects such as
  `aoa_evals_generated_report_index_bundle`, clean portable session-memory
  exports such as `aoa_session_memory_portable_bundle`, and OS Abyss local
  provenance bundle roundtrips. Artifact-class `producer_admission` records
  preserve one canonical producer while admitting explicitly bounded
  candidates only after their selected profile, exact source ref, provenance
  subject, trust posture, and false authority flags agree. The admission is
  copied into the durable registry record and enforced again by `trust-gate`.
  The legacy SDK routing canary remains limited to `manually-verified`, local
  or host-managed trust, and agent/runtime-canary use. A separately and
  explicitly selected public release-candidate profile may use
  `release-ready` or `published` plus `public_release` trust for
  `release_consumer` and `runtime_canary`; it still denies normal `runtime`.
  Unknown profiles, unauthorized lifecycle/trust/intent expansion, missing or
  damaged admission records, and any true G5 authority flag fail closed.
  External repo bundle manifests may use the
  repo-qualified policy reference
  `repo:abyss-machine/manifests/artifact_signature_policy.manifest.json`.
