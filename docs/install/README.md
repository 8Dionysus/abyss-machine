# Install

Install starts from this source repo, renders public-safe templates, creates
empty local roots, and installs the CLI when explicitly applied.

The installed CLI surface is the entrypoint plus the `abyss_machine` package
modules under the configured libexec root. Bootstrap also projects compact
public seed read models under the adjacent share root so installed
artifact-bundle verification can run without importing a source checkout.

Dry-runs are the default review surface.
