# Changelog

## Unreleased

- Make source and installed `AGENTS.md` cards inherited, task-conditioned local
  routes; keep root and district README files as human/public entrypoints;
  route adapter and validator inventories to their existing owner maps; and
  remove placeholder-only mechanic `docs/`/`parts/` indexes while retaining
  indexes that have real children.
- Preserve artifact read-model JSON/JSONL/index refresh when optional host group
  ownership is unavailable, including unmapped-group `EINVAL` from `chown`.
- Record decision `0027`: active-organ work remains subject to independent
  host resource/storage/model admission, and the machine layer remains
  project-neutral even when it returns deny, defer, or soften.

- Keep storage inventory measurement inside one per-path latency budget: an
  explicit `du` timeout now remains unmeasured instead of starting an unbounded
  Python walk, while fast failures may use only the remaining budget and an
  incomplete fallback never publishes a partial byte count as complete.
- Isolate Unix-socket publication tests from checkout-path length while keeping
  overlong-path rejection as its own negative contract, preventing false full
  gate failures in long agent worktrees and xdist temp roots.
- Replace the monolithic launch-time thermal diagnostic with a fresh,
  request-specific thermal-map and CPU-route attestation; keep process
  attribution and desktop/compositor analysis available outside the critical
  path, carry the exact attested route into the atomic plan, and fail closed on
  unavailable or mismatched thermal evidence.
- Remove full cleanup/process/container inspection from resource-launch write
  admission, run independent storage and thermal attestations concurrently
  outside the startup lock, refresh aged proof fail closed, and expose complete
  planning, lock, execution, and total latency in the launch receipt.
- Promote the receipt-bound owner claim/evidence graph to the protected
  validation route, retaining the exact serial oracle and rollback while
  overlapping independent obligations and scheduling the full pytest corpus
  with the repeatedly selected two-worker xdist plan.
- Publish the resource-admission Unix socket atomically only after private
  permissions are established, a race exposed by the parallel validation
  comparison rather than hidden as test noise.
- Compact the Artifact Trust skill's global routing description while retaining
  its artifact classes, evidence-pressure triggers, and nearest exclusions in
  the host-visible prefix.
- Admit only the exact receipt-bound `aoa-sdk` G5 canonical routing producer,
  and require promotion to prove byte parity between the policy-pinned public
  v0.8.0 archive, its manifest, all 29 subjects, their aggregate, and exact
  attestation evidence before a durable registry record can be written.
- Add the owner-local Artifact Trust skill bundle and OS-user exposure port,
  keeping artifact policy, registry, producer, and consumer-gate authority with
  their existing owners while adding the canonical skill package to the signed
  public-source surface.
- Add fail-closed KAG owner-family and 24-owner composition trust routes with
  inner identity signatures, outer source-bound ABI envelopes, owner-scoped
  registry latest selection, revocation, and reachability-rechecked CAS
  retention.
- Add the owner-local `stats/` port and measured-duration coverage statistic to
  the existing AI workload stats read model without publishing live host data.
- Consolidate duplicated runnable command and validation lists into their
  executable owner routes while retaining architecture and decision context.
- Establish the full public host-organ skeleton with route docs, mechanics,
  explicit config/systemd source roots, schemas, and validation districts.
- Add artifact signature policy and generated contract ABI signatures for
  source-safe CI/canary compatibility checks.
- Add a release-artifact policy lane for publishable artifact provenance and
  sidecar requirements without requiring signing keys in ordinary CI.
- Add the first policy-driven artifact bundle verifier roundtrip for the
  public source seed: ABI sidecar, minimal provenance sidecar, explicit
  signature-not-required decision, verify, and release-check.
- Add package-subject artifact bundle support for external Python
  distributions, including CycloneDX/SPDX SBOM sidecars and SLSA/in-toto
  provenance sidecars checked against wheel/sdist digests.
- Add runtime-config artifact bundle policy support for public-safe
  `abyss-stack` rendered config bundles with ABI, SBOM, and SLSA/in-toto
  controls.
- Add the OS Abyss local provenance sample bundle so the same verifier path
  checks private-host-evidence packet shape without publishing private payloads.
- Add a portable OS Abyss runner contract so local CLI, host scheduler, release
  pipeline, and GitHub Actions adapters share the same validation entrypoints.
- Add the family-standard GitHub landing workflow to the root route card and
  name the public workflow `Repo Validation`.
- Align the GitHub platform surface with sibling repository landing policy:
  CODEOWNERS, PR template, surface map, protected `Repo Validation` check, and
  auto-deleted merge branches.
- Extract the shared host root path policy into a tested module used by
  bootstrap and CLI imports, and add a source-fast validator for the path
  contract.
- Extract typing/nervous path and service policy into a tested module while
  preserving CLI constants for installed-host compatibility.
- Extract typing/nervous refresh resource-gate and recent-index debounce
  helpers into a tested module while preserving CLI helper exports.
- Extract typing/nervous refresh assessment into the same tested module while
  preserving the CLI helper export.
- Extract typing/nervous refresh latest-status classification into the refresh
  module while keeping the CLI as the live path/systemd adapter.
- Extract typing/nervous refresh index-attempt debounce context into the refresh
  module while keeping live index launch orchestration in the CLI.
- Extract typing/nervous refresh final status and summary context into the
  refresh module while keeping live synthesis orchestration in the CLI.
- Extract typing/nervous refresh snapshot, index, retry, and synthesis
  action-record builders into the refresh module while keeping live calls in
  the CLI.
- Extract typing/nervous refresh document assembly into the refresh module
  while keeping live orchestration and persistence in the CLI.
- Extract typing/nervous refresh fact-state assembly into the refresh module
  while keeping live nervous facts reads in the CLI.
- Add explicit fail-closed decision and inspected-claims fields to the
  artifact trust gate so agents can audit why bundle consumption was allowed,
  denied, or routed to manual review.
- Add a legacy bundle-registry upgrade route so existing host-managed registry
  records can be made explicit under the new durable evidence contract instead
  of weakening the fail-closed trust gate.
- Require abyss-machine artifact bundle manifests to declare durable
  evidence-promotion, materialization, trust-gate, and registry-latest consumer
  paths, with official-manifest roundtrip tests for install/runtime/AI/extension
  subjects.
- Require official artifact bundle manifests to declare fail-closed consumer
  admission, explicit allow/deny verdicts, and either subject-store
  materialization with a `--store-root` or an explicit subject-store deferral
  reason for subjectless source/evidence samples.
- Add a first-run installed projection validator that applies bootstrap into
  isolated temp roots, proves installed CLI parity without source-checkout
  imports, checks package/public-seed projection, and keeps typing/nervous
  activation opt-in.
- Keep materialized artifact subject-store `AGENTS.md` files out of the host
  docs mesh so promoted external evidence cannot masquerade as host route law.
- Retire the numeric `memory orchestrate` ranking and restart executor so
  pressure and footprint remain host facts rather than workload-importance or
  mutation authority.
- Separate pressure from swap reserve, remove static launch memory caps and
  swap/class gates and fake memory recommendations, route host-managed AI work
  through canonical resource admission, learn bounded demand from exact
  transient-unit peaks, and expose only strict empty owner-cgroup cache reclaim
  offers in shadow mode.
- Replace the long-lived resource-launch CLI waiter with a sealed in-memory
  handoff to a lightweight execution adapter while retaining deterministic
  lease cleanup, timeout handling, peak learning, and latest-only receipts.
- Activate the existing lightweight owner cold-load admission server through
  one hardened unprivileged user unit in the core profile, with a private
  Unix-only transport and no resident memory controller or workload caps.

## 0.1.0

- Seed the portable public `abyss-machine` repository.
