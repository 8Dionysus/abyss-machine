# Artifact Bundles

Repo-local artifact bundle manifests say what this repository can package or
verify. They do not define signing doctrine; controls come from
`manifests/artifact_signature_policy.manifest.json`.

- `public_source_seed.bundle.json`: first executable ABI/signs slice for the
  public source seed. It drives `abyss-machine artifacts build-sidecars` and the
  `release-artifact` validation lane.
- `host_local_evidence.sample.bundle.json`: public-safe OS Abyss local
  provenance sample. It proves the private evidence packet verifier path
  without carrying real `/var/lib/abyss-machine` payloads.
