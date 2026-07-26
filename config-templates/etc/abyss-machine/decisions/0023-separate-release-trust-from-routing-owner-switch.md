# 0023 Separate Release Trust From Routing Owner Switch

## Status

accepted

## Date

2026-07-25

## Index Tags

- artifacts
- owner-boundary
- release-trust
- validation-guard

## Current Applicability

As of 2026-07-26, the separation remains active, but its pre-G5 operational
posture has moved. The two candidate profiles remain bounded historical
admission contracts and do not inherit later authority.
~~Both keep `aoa-routing` canonical and require every G5 authority flag to
remain false.~~ The current canonical route is the receipt-bound `aoa-sdk`
profile in decision 0024 and
`manifests/artifact_signature_policy.manifest.json`; release trust still does
not create owner authority by itself.

## Context

The SDK routing candidate passed local artifact controls and an authorized
runtime canary, but a production runtime record requires a release lifecycle
and a non-local public trust root. Reusing the canary profile would either
block honest release evidence or silently broaden a local candidate into
production authority.

## Options Considered

- Treat the existing `manually-verified` canary record as release evidence.
- Switch canonical routing ownership before producing a public SDK asset.
- Add a separately selected release-candidate profile that can carry public
  release trust while production runtime remains denied.

## Decision

Use an explicit `producer_admission_profile_id` to select the public SDK
routing release-candidate profile. Admit its exact
`release-ready`/`published` lifecycle and `public_release` trust root only for
`release_consumer` and `runtime_canary`. Continue to deny normal `runtime`
until a later policy change carries the exact G5 owner-switch receipt.

## Rationale

Release trust proves that exact bytes came from an exact public release. It
does not decide which repository owns canonical generation. Keeping those
claims separate prevents a public asset, CI attestation, or durable registry
record from becoming an implicit owner switch.

## Consequences

`aoa-sdk` can now establish a production-grade public release root before G5.
The manifest must select the release profile explicitly, and the policy
continues to accept legacy non-publishing candidate manifests without an
explicit profile selector. A later G5 change still needs a separate canonical
policy update and live runtime evidence.

## Boundaries

- This decision does not make `aoa-sdk` canonical.
- It does not allow the normal `runtime` consumer intent.
- It does not mark `aoa-routing` maintenance-only.
- It does not start the compatibility window or authorize archival action.
- GitHub or release evidence remains adapter evidence; the OS Abyss trust gate
  remains the consumption authority.

## Review Log

- 2026-07-25: Initial accepted record.
- 2026-07-26: Reviewed after the G5 switch. The release-trust/owner-authority
  separation remains active; decision 0024 now owns the exact canonical
  profile, while both profiles defined here remain bounded pre-G5 history.

## Source Surfaces

- `manifests/artifact_signature_policy.manifest.json`
- `src/abyss_machine/artifact_bundles.py`
- `tests/public_smoke/test_artifact_bundle_verifier.py`
- `tests/public_smoke/test_artifact_identity_policy.py`

## Validation

- Policy tests prove both candidate profiles remain exact and single-canonical.
- Bundle tests prove a public release candidate is admitted for
  `release_consumer` while the same record is denied for `runtime`.
- Existing non-publishing candidate and tamper tests remain green.

## Follow-up Route

Decision 0024 owns the completed canonical policy transition and its
registry/subject-store/runtime admission sequence. This decision continues to
guard against treating release evidence alone as owner authority.
