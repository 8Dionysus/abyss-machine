# Changelog

## Unreleased

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

## 0.1.0

- Seed the portable public `abyss-machine` repository.
