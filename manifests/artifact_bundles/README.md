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

External repo manifests may also provide `artifact_subjects` entries. For
package artifacts, those entries bind built wheel/sdist files to generated SBOM
and SLSA/in-toto sidecars without moving the distribution files into the public
source repository.
Runtime config artifacts use the same manifest route and may set `build_type`
so the generated SLSA statement identifies a runtime-config bundle instead of
the Python distribution default.
