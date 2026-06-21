# Publication Boundary

`abyss-machine` is published as a portable seed, not as a snapshot of one
workstation.

## Published

- CLI source and thin helper tools.
- Source contracts and policy templates from `/etc/abyss-machine`.
- systemd unit skeletons for Linux/systemd targets.
- typing and nervous-system machinery: adapters, capture gate, redaction,
  privacy controls, retention policy, validators, and opt-in unit templates.
- Bootstrap scripts that render host-local paths and create empty local roots.
- Public smoke tests and host contract tests.
- Route docs, permissive v1 schemas, and mechanics package contracts.
- Artifact signature policy and deterministic contract ABI signatures for
  public contract surfaces.
- Runner-neutral validation lanes that OS Abyss local CLI, host schedulers,
  release pipelines, and GitHub Actions can consume.

## Not Published

- `/var/lib/abyss-machine`: generated facts, latest/index JSON, histories,
  process/memory/self-awareness evidence, typed events, transcripts, local memo,
  and validation output.
- `/srv/abyss-machine/cache`, `runtimes`, `storage`, `tmp`, `backups`, and
  private artifacts.
- `/abyss` vault contents, restic repositories, password files, or local backup
  manifests.
- Browser captures, screenshots, clipboard-derived facts, raw typed text
  histories, Codex sessions, and private retrieval packs.
- Installed binary archives, `.bak` files, signed extension packages, compiled
  caches, and one-off probe output.

## Signatures And Provenance

`abyss-machine` distinguishes compatibility fingerprints from release
signatures:

- Contract ABI signatures are deterministic hashes over tracked public source
  surfaces. They help agents and canaries detect contract drift.
- Artifact identity posture records what each artifact class is, who owns its
  meaning, what consumers must check, and which trust layer applies.
- Host-local evidence uses local provenance packets before any public release
  claim: source refs, producer command, content identity, privacy boundary,
  lineage, and the local validator a consumer relied on.
- SBOM and SLSA/in-toto provenance apply when software, install, runtime,
  container, package, or release artifacts are built for publication.
- ML-BOM applies when AI model, dataset, conversion, or framework-config
  bundles are distributed.
- Sigstore/Cosign applies to published release assets, blobs, OCI artifacts, or
  bundles, not to every source commit.
- C2PA applies only to public media/content exports.
- Live host evidence is not published or signed as public source. If local
  evidence is promoted, it keeps semantic provenance inside the host evidence
  plane first.
- TUF waits until an install/update channel exists. SCITT waits until OS Abyss
  needs federated transparency receipts for signed statements.

The `release-artifact` validation lane checks these rules before publication
without requiring private keys or producing signatures during ordinary CI.
The runner contexts live in `docs/validation/validation_lanes.json`; the CLI
entrypoints live under `scripts/`.

## Artifact Bundle Verification

The first executable bundle layout is `abyss_machine_artifact_bundle_v1`.
For the public source seed it creates:

- `artifact.identity.json`: policy-derived artifact identity, required
  controls, deferred controls, ABI epoch, owner, and privacy boundary.
- `artifact.abi.json`: the matching contract ABI surface from
  `generated/contract_abi_signatures.min.json`.
- `artifact.provenance.json`: minimal OS Abyss bundle provenance for the
  sidecar build, not a SLSA release attestation.
- `artifact.local-provenance.json`: required only for `host_local_evidence`;
  it carries the private evidence packet contract without publishing the
  evidence payload.
- `artifact.signature-decision.json`: either a real signature result later, or
  an explicit policy reason that a cryptographic signature is not required for
  this artifact class.
- `artifact.verify.json`: machine-readable verifier output.

The local bundle registry is the consumer read-model for lifecycle state. A
bundle can become `latest` only through `bundle-register` after verification
succeeds. Terminal states such as `revoked`, `superseded`, `deprecated`, or
`quarantined` remain recorded but are never selected as latest.

Consumer route:

```bash
abyss-machine artifacts build-sidecars --manifest manifests/artifact_bundles/public_source_seed.bundle.json --bundle-dir /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts sign /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts verify /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts release-check /tmp/abyss-machine-public-source-seed --json
abyss-machine artifacts bundle-register /tmp/abyss-machine-public-source-seed --lifecycle-state manually-verified --json
abyss-machine artifacts bundle-registry --artifact-class public_source_seed --json
```

For release artifacts with real blob subjects, `materialize-subjects` copies the
verified files into the local subject store under
`/var/lib/abyss-machine/artifacts/subjects`. This lets installed consumers find
the blob by the signed subject manifest digest without making the public bundle
manifest depend on one workstation path.

For `public_source_seed`, policy requires the ABI sidecar. SBOM, ML-BOM,
SLSA/in-toto, Sigstore/Cosign, and C2PA remain explicit not-required controls
until a publishable artifact class triggers them.

The OS Abyss local sample uses the same verifier path for the local provenance
packet shape without carrying real private host payloads:

```bash
abyss-machine artifacts build-sidecars --manifest manifests/artifact_bundles/host_local_evidence.sample.bundle.json --bundle-dir /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts sign /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts verify /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts release-check /tmp/abyss-machine-host-local-evidence --json
abyss-machine artifacts bundle-register /tmp/abyss-machine-host-local-evidence --lifecycle-state manually-verified --json
abyss-machine artifacts bundle-registry --artifact-class host_local_evidence --json
```

## Lifecycle On A New Machine

```text
repo template
  -> bootstrap doctor probes local capabilities
  -> host profile renders /etc/abyss-machine
  -> validators create /var/lib/abyss-machine facts
  -> optional units maintain local evidence
  -> caches, runtimes, and models appear only when enabled
```

Typing and nervous-system collection are not removed for safety. They are
installed as opt-in organs: the code, policies, units, state roots, and
validators exist, while real collectors stay disabled until the operator enables
the corresponding profile and the selftests pass.
