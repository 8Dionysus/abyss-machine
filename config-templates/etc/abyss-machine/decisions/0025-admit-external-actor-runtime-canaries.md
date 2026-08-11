# 0025 Admit External Actor Runtime Canaries

## Status

accepted

## Date

2026-08-10

## Index Tags

- artifacts
- owner-boundary
- runtime-admission
- agent-runtime
- validation-guard

## Current Applicability

As of 2026-08-10, a machine-local external Codex actor release owned by
abyss-stack may enter real role trials only as an exact
runtime_or_container_artifact canary. The source ref, content-addressed
release manifest, signed subject inventory, host-managed trust root,
materialized subject, and fresh runtime_canary verdict remain required.
Normal runtime and public-release claims remain separate later admissions.

## Context

abyss-stack gained a content-addressed external actor runtime whose stable
surface is role- and obligation-oriented rather than model-named. Its local
installer already verifies the runtime, SDK, owner schemas, Python identity,
immutable release closure, and stable wrappers. The host artifact plane,
however, exposed only the abyss-machine runtime-tools bundle for the shared
runtime_or_container_artifact class.

Reusing that unrelated latest record would have admitted the wrong producer
and bytes. Refusing every real trial until a public release existed would have
turned artifact trust into a barrier to the evidence-producing canary work
needed to qualify landing, eval, stats, and memo actors.

## Options Considered

- Reuse the latest abyss-machine runtime-tools record for the external actor
  runtime.
- Activate the owner-local release directly and treat the installer receipt as
  the whole host admission.
- Add an exact abyss-stack producer and bundle manifest for machine-local
  runtime_canary admission while keeping normal runtime and publication
  separate.

## Decision

Extend the abyss-stack producer profile to the shared
runtime_or_container_artifact class and add a dedicated external actor bundle
manifest. Build the outer ABI over the host admission manifest and bind the
actual owner release through its immutable release-manifest.json subject.

The canary route must:

1. name the exact abyss-stack source ref and materialized release root;
2. build ABI, SBOM, SLSA/in-toto, and Sigstore/Cosign sidecars;
3. verify the release-manifest subject against the supplied release root;
4. promote only manually-verified host-managed evidence for the named
   external actor canary;
5. materialize the signed release-manifest subject into the selected host
   subject store;
6. re-promote the verified bundle so the durable latest record contains the
   materialized subject-store evidence; and
7. obtain a fresh runtime_canary trust-gate allow or warn verdict before
   activation.

The runtime remains owned and admitted internally by abyss-stack; the host
plane owns only artifact evidence, durable selection, and consumer admission.

## Rationale

This route lets real work produce model- and role-fit evidence without
pretending that an unpublished canary is a normal runtime or public release.
It binds the host verdict to the exact producer, source, and content-addressed
release instead of using a class-wide green proxy. Keeping the owner installer
and host consumer gate distinct preserves both authorities without duplicating
the runtime implementation in abyss-machine.

## Consequences

- Fresh Codex sessions can eventually consume one host-admitted external actor
  canary through stable wrappers while the runtime owner remains replaceable.
- Canary trials may proceed before public release evidence exists, with every
  warning retained.
- A later normal-runtime or public-release transition needs fresh evidence and
  an explicit lifecycle/trust-root decision; it does not inherit canary
  authority.
- The host registry may contain several records in the shared artifact class,
  so consumers must always bind source repo, source ref, trust-root mode,
  consumer intent, and subject digest.

## Boundaries

- This decision does not make abyss-machine the owner of actor roles, model
  choice, A2A relations, runtime implementation, or task acceptance.
- It does not bind landing or any other role permanently to Luna.
- It does not admit built-in Codex subagents as the external actor transport.
- It does not let a class-wide latest record substitute for the exact
  abyss-stack source and subject.
- It does not authorize normal runtime, public publication, or automatic
  promotion from canary evidence.

## Review Log

- 2026-08-10: Initial accepted record.

## Source Surfaces

- manifests/artifact_signature_policy.manifest.json
- manifests/artifact_bundles/abyss_stack_external_codex_agent.bundle.json
- generated/contract_abi_signatures.min.json
- src/abyss_machine/artifact_bundles.py
- tests/public_smoke/test_artifact_bundle_verifier.py

## Validation

- The artifact policy validator must admit the abyss-stack producer and the
  dedicated contract surface.
- A real content-addressed external actor release must build, sign, verify,
  promote, materialize, and return an exact runtime_canary trust-gate allow or
  warn verdict in an isolated registry before host activation.
- Negative proof must keep unrelated class latest records and missing subject
  stores fail closed.

## Follow-up Route

abyss-stack owns landing the runtime and its installer. The host change ledger
owns machine activation and rollback. Real landing, eval, stats, and memo
pilots own canary evidence; a later decision owns normal-runtime or public
release admission.
