# Validator Topology

## Public Lane

- `python scripts/ci_gate.py --mode source-fast`

The source-fast lane is defined in `docs/validation/validation_lanes.json` and
loads through `scripts/validation_lanes.py`. It checks repo topology,
mechanics topology, manifests, schemas, bootstrap dry-runs, shared path policy,
the first-run installed projection, typing/nervous organ policy,
typing/nervous refresh logic, public boundary, artifact signature policy,
contract ABI signature freshness, generated scaffold index freshness,
compileall, and public smoke tests.

## Runner Contexts

`docs/validation/validation_lanes.json` declares lanes, command sequences, and
runner contexts.

The same entrypoints can run from:

- `os_abyss_local_cli`: direct local repo checkout validation.
- `os_abyss_host_scheduler`: recurring public-safe canaries from an installed
  OS Abyss host timer or service.
- `github_actions`: public CI and scheduled public-seed canary adapter.
- `release_pipeline`: publication gate before artifact upload or signing.
- `os_abyss_host_contract`: local installed-host checks that may read private
  host state and are therefore excluded from public-safe lanes.

GitHub CI runs the public and release-artifact lanes on push, pull request,
manual dispatch, and a weekly public-seed canary schedule.

## Host Contract Lane

- `python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"`
- `PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json`

## Release Lane

- `python scripts/release_check.py`
- `python scripts/release_check.py --include-host-contracts`

`release-public` runs the source-fast gate and the release-artifact gate.
`release-full` adds the fixture-backed host-contract gate.
Release pipelines should call the same CLI gates before publishing SBOM,
ML-BOM, SLSA/in-toto, Sigstore/Cosign, or C2PA sidecars.

## Release Artifact Lane

- `python scripts/ci_gate.py --mode release-artifact`
- `python scripts/validators/release_artifact_policy.py`
- `python scripts/validators/artifact_bundle_roundtrip.py`

This lane validates the policy consequences for publishable artifacts. It checks
that wheel/sdist, runtime/container, AI model/runtime bundle,
browser-extension, and public media export classes declare the expected ABI,
SBOM, ML-BOM, SLSA/in-toto, Sigstore/Cosign, or C2PA requirements, and that
publishable artifacts are not tracked as ordinary public source files. It also
builds and verifies the first public-source-seed bundle sidecars plus the
public-safe host-local-evidence provenance sample. It also promotes a synthetic
durable evidence record, verifies that it becomes `latest`, runs a positive
consumer `trust-gate`, then writes a terminal `revoked` state and verifies that
the gate denies consumption and the record disappears from `latest`. This keeps
lifecycle/read-model and fail-closed consumer-gate behavior executable,
including the gate's explicit decision and inspected-claims contract, while
still avoiding private keys, release signing, and private host payloads in
ordinary CI.

The same lane covers legacy registry migration: an old registry record with
missing durable evidence fields must be denied by `trust-gate`, reported by
`bundle-registry-upgrade --dry-run`, upgraded with an explicit
`legacy_evidence_upgrade` assertion, and then admitted only when the upgraded
claims satisfy the same gate.

## Path Policy Lane

- `python scripts/validators/path_policy.py`
- `python scripts/validators/first_run_installed_projection.py`
- `python scripts/validators/typing_nervous_policy.py`
- `python scripts/validators/typing_nervous_refresh_logic.py`

The path-policy validator checks that bootstrap and CLI imports share the same
root contract for `/etc/abyss-machine`, `/var/lib/abyss-machine`,
`/srv/abyss-machine`, `/run/abyss-machine`, install roots, and opt-in
typing/nervous state paths. It also verifies that CLI constants honor
environment overrides at import time, so a fresh machine or test harness can
render the same organ shape without editing source.

The first-run installed projection validator performs a real
`install --apply` into isolated temporary roots, then runs the installed CLI
without `PYTHONPATH=src`. It enforces source-vs-temp-installed command parity,
critical artifact-trust option surfaces, package-module projection, public seed
share projection, `/run` root creation, typing/nervous config and unit
projection, and opt-in profile dry-runs. The live
`/usr/local/bin/abyss-machine` comparison is read-only and advisory by default;
use `--require-host-installed` during a real host install closeout.

The typing/nervous policy validator keeps the first subsystem split honest:
private nervous captures, search and semantic indexes, browser/tool adapters,
typing tmp/cache paths, and user-level systemd unit paths must derive from the
shared path policy while the CLI preserves the historical `TYPING_*` and
`NERVOUS_*` constants for installed-host compatibility.

The typing/nervous refresh logic validator keeps the next split bounded: soft
resource-gate, recent-index debounce, refresh assessment, latest-status
classification, index-attempt debounce context, and final status/summary
context plus fact-state, action-record, and refresh-document helpers live in
`abyss_machine.typing_nervous_refresh`, remain re-exported or adapted by the
CLI, and do not read live typing, nervous, capture, or index state.

## Publication Smoke

Scan the tracked tree for obvious secret patterns and forbidden live-state
paths before pushing public changes.

## Signature Policy

- `python scripts/validators/artifact_signature_policy.py`
- `python scripts/generate_contract_abi_signatures.py --check`
- `python scripts/validators/release_artifact_policy.py`
- `python scripts/validators/artifact_bundle_roundtrip.py`

The policy validator keeps artifact identity posture, ABI, local provenance,
SBOM, ML-BOM, SLSA/in-toto, Sigstore/Cosign, C2PA, and deferred TUF/SCITT
posture explicit by artifact class. The ABI signature generator publishes a
deterministic compatibility read model for public contract surfaces. It is not a
release signature and does not sign live host evidence. The bundle roundtrip is
the first executable consumer route: it creates ABI/provenance/signature-decision
sidecars for `public_source_seed`, local provenance sidecars for the
`host_local_evidence` sample, verifies both with the same policy-driven bundle
verifier exposed by `abyss-machine artifacts verify`, and exercises
`requirements`/`affected` preflight read-models,
`evidence-promote`/`bundle-registry` latest behavior, positive `trust-gate`
selection, terminal-state revocation, negative `trust-gate` denial, legacy
registry upgrade, durable-only `trust-coverage` without tmp/manual evidence,
and the gate's explicit decision/claims explanation. Public smoke tests also
cover external sibling subjects, including the
`aoa_session_memory_portable_bundle` update-client path with ABI, SBOM,
SLSA/in-toto, registry promotion, and a negative missing-control gate.
