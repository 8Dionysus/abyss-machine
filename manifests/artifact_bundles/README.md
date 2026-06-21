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
- `bootstrap_install_bundle.bundle.json`: local release-candidate route for an
  ignored `dist/abyss-machine-bootstrap-*.tar.gz` archive. It requires ABI,
  SBOM, SLSA/in-toto, and Sigstore/Cosign verification before registry latest
  selection.
- `runtime_tools_bundle.bundle.json`: local release-candidate route for an
  ignored `dist/abyss-machine-runtime-tools-*.tar.gz` archive containing host
  runtime helper scripts, runtime mechanics docs, and storage policy inputs.
- `ai_runtime_config_bundle.bundle.json`: local release-candidate route for an
  ignored `dist/abyss-machine-ai-runtime-config-*.tar.gz` archive. It is an
  AI framework-config bundle with ML-BOM identities for referenced models and
  conversions, not a model-weights publication.
- `browser_extension_package.bundle.json`: local release-candidate route for
  the Firefox typed-text intake source package under
  `tools/typing/firefox-extension/build/`. Mozilla store signing remains a
  separate external boundary.
- `public_media_export.bundle.json`: local release-candidate route for public
  media/content exports that carry C2PA asset binding before publication.

Bundle manifests may declare lifecycle and consumer-contract fields. The
registry read-model is local state: verified, latest-eligible records can be
selected by `trust-gate` consumers, while terminal states remain evidence and
are excluded from latest. `evidence-promote` is the preferred durable promotion
entrypoint; `bundle-register` remains the lower-level compatible registry write.
`trust-gate` is the fail-closed consumer admission surface and returns
machine-readable decision plus inspected claims for agent audit trails.
Registries created before the durable evidence fields use
`bundle-registry-upgrade` as an explicit host-managed migration; the trust gate
does not silently allow those legacy records.
Use `requirements` before producing a bundle to inspect producer profile,
required controls, trust-root expectations, and owner/source route. Use
`affected` before consuming or landing changes to detect stale source,
manifest, policy, ABI, or sibling-owner evidence.
Use `update-lane` and `update-verify` for updateable/installable artifacts
before update-client consumption. The sidecar name is
`artifact.update.tuf.json`; the verifier blocks rollback, expired metadata, and
unchanged metadata beyond the configured freeze window. This is the OS Abyss v1
TUF-style gate. It does not claim a complete external TUF repository or SCITT
transparency service.

External repo manifests may also provide `artifact_subjects` entries. For
package artifacts, those entries bind built wheel/sdist files to generated SBOM
and SLSA/in-toto sidecars without moving the distribution files into the public
source repository.
Runtime config artifacts use the same manifest route and may set `build_type`
so the generated SLSA statement identifies a runtime-config bundle instead of
the Python distribution default.

Release-artifact subjects can be materialized into the local host subject store
with `abyss-machine artifacts materialize-subjects BUNDLE_DIR --json` only
after the matching bundle has a durable registry record that passes
`trust-gate` for the derived consumer intent. The CLI defaults to the host
bundle registry root, and test/portable lanes can pass `--registry-dir`
explicitly. The public manifest stays repo-relative; installed consumers verify
the signed `artifact.subjects.json` against
`/var/lib/abyss-machine/artifacts/subjects` when the source artifact path is
not available.
