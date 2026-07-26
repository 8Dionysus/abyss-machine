# 0024 Admit Receipt-Bound SDK Routing Canonical Producer

## Status

accepted

## Date

2026-07-26

## Index Tags

- artifacts
- owner-boundary
- routing-succession
- runtime-admission
- validation-guard

## Current Applicability

As of 2026-07-26, `aoa-sdk` is the single canonical producer for
`thin_routing_readmodel_bundle`, but only through the exact
`aoa-sdk-g5-canonical` profile. That profile is bound to SDK source
`e4ffd26ed9e50125be584c00839ee6a8f7016a0d`, the G5 owner-switch receipt,
canonical provenance, public v0.8.0 archive digest, predecessor source
`97f60de1b5992ef6bf5ff0f051bd452d940d9a85`, and abyss-stack consumer
contract `fac82c75d860dd2433cfc1e391f4b6ba117425d7`.

`aoa-routing` is maintenance-only for compatibility, security, rollback, and
deprecation. Repository archival remains forbidden without consumer-zero,
compatibility exit, and separate exact operator approval.

## Context

The public SDK candidate established release trust without changing ownership.
G5 then produced an explicit owner-switch receipt and a new canonical SDK
archive. Changing only `identity.owner_repo` would have let arbitrary SDK
routing artifacts inherit authority and would have collapsed source identity,
release trust, owner succession, and runtime admission into one weak claim.

The host layer needed a fail-closed way to accept one exact canonical artifact
while preserving historical candidate records, predecessor rollback, and the
consumer's independent runtime gate.

## Options Considered

- Change only the canonical owner string from `aoa-routing` to `aoa-sdk`.
- Promote the existing SDK release-candidate registry record into canonical
  runtime use.
- Add a new exact canonical profile and require a new registry record, subject
  store, and runtime trust verdict.

## Decision

Add `aoa-sdk-g5-canonical` as a policy-pinned canonical admission profile.
Validate its exact manifest lifecycle, SDK and predecessor refs, canonical
provenance, canonical-JSON receipt digest, G5 authority map, v0.7 release root,
v0.8.0 canonical archive digest, abyss-stack contract ref, and archival stop
line before sidecars can be built.

Require a new public-release registry record whose trust evidence matches the
v0.8.0 archive. Promotion must read the exact policy-pinned archive and the
runtime-supplied canonical subject root, reject unsafe or extra archive
members, and prove byte parity for `artifact.bundle.json` plus all 29 declared
subjects. It must also reproduce the exact subject aggregate and bind the
archive digest to the exact attestation schema, verifier, and workflow evidence
reference before writing a registry record.

Permit normal `runtime` only after the artifact subjects are materialized and
the latest bound trust gate returns `allow`. Keep the two pre-G5 SDK profiles
as separately selected historical contracts and reject new canonical
production by `aoa-routing`.

## Rationale

This makes canonical authority a conjunction of independently checkable facts:
source ownership, explicit succession, exact bytes, required controls, durable
host admission, and consumer readiness. No single GitHub release, sidecar,
owner string, or runtime command can manufacture the switch.

A new registry record prevents a candidate verdict from being reinterpreted
after policy changes. Archive-to-subject byte parity prevents a caller from
building valid sidecars over locally changed bytes while repeating the known
public archive digest. Keeping the subject store and runtime gate downstream
also proves that the exact reviewed bytes, not merely their metadata, are
available to the consumer.

## Consequences

The SDK becomes the meaningful canonical routing surface for future agent-SDK
and Agent OS control-plane work. Normal runtime can consume the SDK bundle
through a deterministic fail-closed route. Historical candidates remain
auditable without gaining authority.

The exact source and release digests are intentionally narrow. A later SDK
canonical release requires another explicit policy update and fresh admission
record rather than silently floating to a new tag.

Canonical promotion now requires both `--subject-root` and
`--public-release-archive`. The durable record contains no local paths; it
retains the exact archive, manifest, member-set, and subject aggregate digests
plus the five successful parity verdicts so later trust-gate reads fail closed
if that binding is absent or mutated.

## Boundaries

- This decision does not make routing readmodels sibling source truth.
- It does not let release attestation replace the OS Abyss trust gate.
- It does not authorize `aoa-routing` archival or deletion.
- It does not prove consumer-zero or compatibility exit.
- It does not permit reuse or mutation of a pre-G5 registry record.
- It does not let a locally rebuilt subject family inherit authority by
  repeating the canonical public archive digest.
- It does not claim live runtime cutover until abyss-stack produces its own
  owner-routed cutover and rollback evidence.

## Review Log

- 2026-07-26: Initial accepted record for the exact receipt-bound SDK G5
  canonical admission.
- 2026-07-26: Required exact public-release evidence fields in the documented
  promotion route after review found that the example omitted them.
- 2026-07-26: Added byte-level archive-to-subject binding after review found
  that a locally rebuilt subject family could otherwise repeat the known
  archive digest.

## Source Surfaces

- `manifests/artifact_signature_policy.manifest.json`
- `schemas/artifact-signature-policy.schema.json`
- `scripts/validators/artifact_signature_policy.py`
- `src/abyss_machine/artifact_bundles.py`
- `tests/public_smoke/test_artifact_identity_policy.py`
- `tests/public_smoke/test_artifact_bundle_verifier.py`
- `config-templates/etc/abyss-machine/decisions/0023-separate-release-trust-from-routing-owner-switch.md`

## Validation

- Artifact policy validation pins the complete G5 canonical profile.
- Bundle tests exercise canonical build, verify, public-release promotion,
  subject materialization, normal-runtime allow, predecessor rejection, and
  source/receipt/authority/release-digest/archive-member/local-rebuild tamper
  rejection.
- The real public v0.8.0 bundle must pass the same build, verification,
  archive-binding, registry, subject-store, and runtime-gate sequence before
  cutover.
- `PUBLIC_RELEASE_EVIDENCE_JSON` must contain the exact `schema`, `mode`,
  `release_ref`, `asset_ref`, `asset_digest`, `source_repo`, `source_ref`,
  `subject_digest`, `evidence_ref`, and `verifier` values for the canonical
  v0.8.0 archive and built bundle.

```bash
python scripts/validators/artifact_signature_policy.py
pytest -q tests/public_smoke/test_artifact_identity_policy.py tests/public_smoke/test_artifact_bundle_verifier.py
abyss-machine artifacts verify BUNDLE_DIR --subject-root CANONICAL_ROOT --json
abyss-machine artifacts evidence-promote BUNDLE_DIR --registry-dir REGISTRY_DIR --lifecycle-state release-ready --source-repo aoa-sdk --source-ref e4ffd26ed9e50125be584c00839ee6a8f7016a0d --trust-root-mode public_release --trust-root-evidence-json @PUBLIC_RELEASE_EVIDENCE_JSON --subject-root CANONICAL_ROOT --public-release-archive CANONICAL_ARCHIVE --json
abyss-machine artifacts materialize-subjects BUNDLE_DIR --store-root SUBJECT_STORE_ROOT --registry-dir REGISTRY_DIR --manifest CANONICAL_ROOT/artifact.bundle.json --consumer-intent runtime --source-repo aoa-sdk --source-ref e4ffd26ed9e50125be584c00839ee6a8f7016a0d --trust-root-mode public_release --json
abyss-machine artifacts trust-gate --registry-dir REGISTRY_DIR --artifact-class thin_routing_readmodel_bundle --consumer-intent runtime --source-repo aoa-sdk --source-ref e4ffd26ed9e50125be584c00839ee6a8f7016a0d --trust-root-mode public_release --subject-digest SUBJECT_DIGEST --json
```

## Follow-up Route

Admit and audit the exact public v0.8.0 bundle under the landed policy, then
hand the bound verdict to the abyss-stack D-0086 cutover route. Preserve the
predecessor until consumer-zero and compatibility exit are separately proved.
