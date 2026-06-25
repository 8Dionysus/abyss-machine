# GitHub Surface

`.github/` contains the GitHub-native platform surface for this repository.
This map is intentionally not named `README.md`: GitHub may select
`.github/README.md` as the repository homepage README and hide the root
source-checkout front door.

## Current Surfaces

- [workflows/repo-validation.yml](workflows/repo-validation.yml): protected
  repository validation check for public seed landing.
- [workflows/artifact-production-evidence.yml](workflows/artifact-production-evidence.yml):
  manual public-safe producer for GitHub OIDC/Sigstore artifact evidence.
- [pull_request_template.md](pull_request_template.md): PR closeout template.
- [CODEOWNERS](CODEOWNERS): ownership routing for review.

GitHub automation must remain public-safe and weaker than source-owned
repository docs. It validates the public source seed; it must not mutate
installed host state, private generated evidence, sibling repositories, or
large runtime/cache/storage paths.

See [AGENTS.md](AGENTS.md) for editing rules.
