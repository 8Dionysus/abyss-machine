# SCIP Python candidate route

This additive MACHINE route packages and inspects a **supplied, prepared** npm
prefix. It neither installs nor executes a provider. The existing TypeScript
archive, installer, runtime-gate issuer and production workflow are unchanged.

## Three different identities

1. `manifests/code_intelligence_python_provider.lock.json` identifies the
   indexer distribution and its consumer ABI assumptions.
2. `parts/scip-python/package.json` and `package-lock.json` fix the entire npm
   tool dependency closure, including peer dependencies. The lock was resolved
   with npm 10.9.8. TypeScript 4.9.5 satisfies the pinned upstream build range
   `^4.5.4`; pinning it prevents an unconstrained ts-node peer from introducing
   TypeScript 7's conditional native package family. This is not a runtime
   compatibility claim. All install scripts remain disabled.
3. The analyzed project's complete source view, configuration, Python
   interpreter, import paths, dependency files and explicit environment JSON
   are **separate STACK-owned analysis inputs**. They do not belong in the
   public tool archive. An empty dependency list must not stand in for unknown
   resolver state. Host PATH or implicit pip discovery cannot supply this
   identity silently.

The indexer is [SCIP Python 0.6.6 at its exact upstream commit](https://github.com/sourcegraph/scip-python/tree/8b60bbce1f2a4c7a517776cb395bbafb2e731e4f).
Its package integrity comes from the npm version record, not from an execution
test. The pinned source suggests UTF-16 positions despite UTF-8 text metadata.
The ABI remains explicitly **source-inferred** until an admitted Unicode/CRLF
canary verifies both indexer and complete-stream decoder. Do not treat an
individual protobuf fragment as the whole workspace.

The upstream closure retains deprecated `glob` 7 and `inflight`. Preserve npm's
warnings in build evidence. A registry audit is not a security verdict over
the indexer's bundled JavaScript, its parser or its eventual runtime inputs;
do not silently override dependencies and call the result the same provider.

## Preparation and inspection

Run host storage/resource admission before large writes. Stage exact copies of
the two npm input files into a new bounded prefix outside the source checkout.
Prepare that prefix using the pinned npm tool with `npm ci --ignore-scripts
--no-audit --no-fund`; use a machine-managed cache. Do not use `npm install` to
resolve new ranges during a release build. Do not run the resulting provider,
even for a version probe, before its exact consumer admission.

The `build` subcommand of `scripts/code_intelligence_python_provider.py`
requires the prefix, an output inside an existing artifact root, and a truthful
qualified source ref. `--inputs` and `--lock` default to the checked-in source
inputs. It validates the whole installed package set against the complete
lock, binds every regular file's bytes/mode and every internal file symlink,
and creates a deterministic unsigned archive without overwriting an existing
different artifact. It downloads and executes nothing.

The archive's inventory and package metadata checks establish internal
consistency, **not independent equality with upstream package payloads**.
The script-free npm-ci build and its exact tools/inputs must be covered by the
later signed build provenance. The Node executable itself is not included;
its admitted installed identity must also be bound by the eventual consumer.

The dedicated Python archive is an optional fourth subject of the existing
provider aggregate. Optional means old TypeScript-only aggregates can still
exist; it does **not** let those aggregates admit a Python archive. The
`inspect` subcommand requires the exact archive to occur once in the verified
aggregate, checks its digest and source ref, verifies sidecars, and then binds
that aggregate to the latest runtime trust gate. Only `allow` is accepted.
Unsigned, missing, substituted, wrong-source, denied and manual-review
candidates remain blocked. No inspection verdict performs installation.

No new trust root, registry record, privacy waiver, release, provider-health
claim or semantic proof is supplied by these source APIs. Installation and
STACK execution/capture remain separate owner operations.

## Signed production route

The existing manual `Artifact Production Evidence` workflow, selected with
`artifact=code_intelligence_provider` on reviewed `main`, now builds the Python
archive along with the other three provider archives. Its pinned setup-node
action selects Node 22.23.1 (bundled npm 10.9.8), matching the build lock. Both
versions are checked before preparation. Fresh prefixes receive exact tracked
npm inputs; `npm ci` disables lifecycle scripts, audit and funding requests,
ignores user/global npm configuration and uses runner-local temporary cache.
No SCIP executable is invoked during this production step.

The builder runs twice over that prefix with the same exact source commit;
different output bytes stop the job. The repeat archive stays outside the
signed aggregate, leaving exactly one Python archive subject. Existing ABI,
SBOM, SLSA/in-toto, Cosign verification, source-bound GitHub OIDC signature and
attestation steps then cover the complete aggregate. The workflow itself is
part of the provider ABI source surface. Immutable workflow/source provenance
binds these build commands and exact lock inputs; a local unsigned build alone
does not acquire that claim.

The provider class's privacy declaration explicitly excludes all private data,
including host evidence, indexes, worktrees, observations, caches and runtime
state. It is compatible with the existing strict privacy parser; the parser,
mandatory controls and signer policy are unchanged. This source clarification
does not relabel an old registry record or admit an existing artifact. Obtain
fresh signed evidence and an exact latest `allow` decision before consumption.

## Verification

The affected owner test is
`tests/public_smoke/test_code_intelligence_python_provider.py`; use the narrow
and complete owner routes in `VALIDATION.md`. Synthetic package fixtures are
not real provider, Unicode, semantic or performance evidence. The durable
checks protect the distribution, filesystem and artifact-admission boundaries.
