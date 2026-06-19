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
