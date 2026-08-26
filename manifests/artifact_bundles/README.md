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
- `bootstrap_install_bundle.bundle.json`: GitHub production release route for
  an ignored `dist/abyss-machine-bootstrap-*.tar.gz` archive. It requires ABI,
  SBOM, SLSA/in-toto, and keyless Sigstore/Cosign verification before registry
  latest selection.
- `runtime_tools_bundle.bundle.json`: local release-candidate route for an
  ignored `dist/abyss-machine-runtime-tools-*.tar.gz` archive containing host
  runtime helper scripts, runtime mechanics docs, and storage policy inputs.
- `abyss_stack_external_codex_agent.bundle.json`: shared runtime-root manifest
  for the exact content-addressed `abyss-stack` external Codex actor release.
  The source owner, exact source ref, and immutable release root are supplied
  at build time; machine-local activation begins as a `runtime_canary` and does
  not become a public or normal-runtime release claim.
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
- `kag_owner_family_release.bundle.json`: shared runtime-root template for a
  complete public content-addressed owner KAG family. The source owner and
  exact source commit plus exported family root are supplied explicitly at
  build/verify time; absolute host paths are never embedded in public
  sidecars. The inner KAG identity signature is verified before the outer
  bundle can be built.
- `kag_os_composition.bundle.json`: signed 24-owner federation composition
  contract. It carries only verified owner coordinates and measurements, not
  a replacement OS-wide corpus monolith. Its outer signature binds the ABI
  envelope containing the exact builder ref, inner identity claims, and full
  subject-inventory digest.

Bundle manifests may declare lifecycle and consumer-contract fields. The
registry read-model is local state: verified, latest-eligible records can be
selected by `trust-gate` consumers, while terminal states remain evidence and
are excluded from latest. `evidence-promote` is the preferred durable promotion
entrypoint; `bundle-register` remains the lower-level compatible registry write.
`trust-gate` is the fail-closed consumer admission surface and returns
machine-readable decision plus inspected claims for agent audit trails.
Official `abyss-machine` manifests must declare fail-closed admission and an
explicit allow/deny verdict requirement. Manifests that emit artifact subjects
must also require subject-store materialization with an explicit `--store-root`;
source-tree or provenance-sample manifests that do not emit materializable
subjects must say why subject-store admission is deferred instead of silently
omitting the lane.
Registries created before the durable evidence fields use
`bundle-registry-upgrade` as an explicit host-managed migration; the trust gate
does not silently allow those legacy records.
KAG retention is reachability-based. `kag-retention-apply` recomputes current
registry, composition, pin, and subject-store reachability after reading the
signed plan and before deleting bytes; a candidate that became reachable is
rejected rather than deleted.
Use `requirements` before producing a bundle to inspect producer profile,
required controls, trust-root expectations, and owner/source route. Use
`affected` before consuming or landing changes to detect stale source,
manifest, policy, ABI, or sibling-owner evidence.
Use `producer-profiles --workspace-root /srv/AbyssOS --require-command-resolution`
for OS-wide profile validation when sibling checkouts are present; add
`--owner-repo-root OWNER=PATH` for repos outside that workspace. This resolves
declared owner-local command references and fails on missing or renamed
producer scripts without executing sibling validators or importing sibling
authority into `abyss-machine`.
Use `registry-latest` when an agent needs the selected durable latest record and
its consumer `trust-gate` verdict without hand-parsing the full registry.
Use `trust-coverage --durable-only` when the question is whether persistent
registry latest records and consumer `trust-gate` verdicts still work after the
tmp/manual evidence layer is ignored; the default coverage mode still requires
manual positive and negative evidence before claiming `FULLY_COVERED`.

## Host-Local Cosign Profile

The `cosign-local-key` backend is deliberately network-independent. It uses
`cosign-local.signing-config.json` and `cosign-local.trusted-root.json`, which
disable remote Fulcio, OIDC, Rekor, and TSA services for this host-managed trust
domain. Signing therefore does not contact or upload to a public transparency
log. Verification explicitly ignores transparency-log inclusion while still
checking the exact subject bytes, Sigstore bundle, and configured public key.

This profile proves possession of the host-managed local key; it is not a
keyless public release identity and must not be described as Fulcio/Rekor proof.
Organization-backed public publication remains a separate trust-root and
credential-onboarding route.

The `cosign-github-oidc` backend is reserved for the declared GitHub Actions
production workflow. It signs the exact `artifact.subjects.json` bytes without
reading a local private key or password, and requires a Fulcio certificate,
Rekor inclusion evidence, and the policy-bound issuer, repository, workflow,
ref, trigger, source SHA, and subject digest. The resulting signature is still
only one claim in the installer route: external TUF metadata, durable registry
promotion, subject materialization, and the final consumer trust gate remain
separate required evidence.

## Pre-Organization Operating Mode

OS Abyss can run artifact trust for the next transition window before an
organization-backed public identity exists. The operating profile is
`pre_organization`: internal OS consumers may admit artifacts only through
durable registry evidence, subject-store materialization where required, and a
fresh `trust-gate` verdict. Public release claims must stay narrower than the
internal evidence. In particular, `public_media_export` may prove C2PA asset
binding and claim-signature integrity, but it must keep the warning verdict and
must not be described as production C2PA Trust List proof until a legal subject,
accepted conforming product, trust-list credential, and host-managed signer all
exist.

This mode is meant to last at least three months or until the organization-backed
credential exists. Each public release candidate and each monthly review should
check `trust-coverage --durable-only`, `update-lane`, the current
`public_media_export` credential onboarding record, and any stale ABI, SBOM,
SLSA/in-toto, C2PA, TUF, SCITT, or subject-store evidence reported by
`affected` or `validate`. The transition to organization-backed publication must
only change the credential/onboarding posture and trust roots; it must not move
tmp evidence into authority or bypass the existing consumer gates.

Use `update-lane` and `update-verify` for updateable/installable artifacts
before update-client consumption. The sidecar name is
`artifact.update.tuf.json`; the verifier blocks rollback, expired metadata, and
unchanged metadata beyond the configured freeze window. CLI consumer use is
fail-closed by default and must carry registry, subject digest, source repo, and
trust-root mode so metadata freshness cannot bypass artifact `trust-gate`; use
`--inspect-only` only for evidence-shape checks that do not consume the target.
Use `update-repo-build` and `update-repo-verify` when the updateable artifact is
distributed through an external TUF repository with `root`, `targets`,
`snapshot`, and `timestamp` metadata plus trusted-root bootstrap. This is the
OS Abyss external TUF producer/verifier v1; live SCITT transparency service and
public-channel key ceremony remain separate production layers.
Use `oci-layout-publish`, `oci-verify`, and `oci-consume` for OCI/ORAS runtime,
container, model, or bundle routes. `oci-layout-publish` creates a local OCI
layout proof with a digest-pinned subject and attached referrer manifests;
`oci-consume` is fail-closed by default and materializes the subject only after
digest/referrer verification and durable `trust-gate` admission. Local OCI
layout proof is useful for OS and CI E2E coverage, but it remains distinct from
an external registry push; external producer adapters must supply the same
digest-pinned evidence contract from their registry.

External repo manifests may also provide `artifact_subjects` entries. For
package artifacts, those entries bind built wheel/sdist files to generated SBOM
and SLSA/in-toto sidecars without moving the distribution files into the public
source repository.
Glob entries may set `optional: true` when several format-specific alternatives
belong to one artifact route; the aggregate subject set must still contain at
least one matched file.
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

The `code_intelligence_provider.bundle.json` manifest is the dedicated
Universal Ctags route. Its archive is prepared outside Git, and its source
subject, sidecars, registry record, subject-store materialization, trust-gate
allow, installation identity, and bounded exercise remain separate evidence
steps. No provider archive is consumable while Sigstore/Cosign evidence or the
root-owned G58 consumer gate is absent.
