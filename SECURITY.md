# Security

`abyss-machine` is public source for a host-local organ. Treat accidental state
publication as the main security risk.

## Do Not Publish

- tokens, password files, SSH material, vault manifests, or restic secrets
- raw typed text, browser captures, screenshots, transcripts, and private
  retrieval packs
- generated host facts or histories from `/var/lib/abyss-machine`
- large runtime artifacts, model weights, caches, backups, and indexes from
  `/srv/abyss-machine`

## Safe Contributions

- public-safe templates and examples
- code and tests that can run without private host data
- schemas that describe shape without embedding live records
- docs that explain how local state is generated and maintained

## Local Checks

Run public tests and scan the staged tree for obvious token patterns and known
private path classes before pushing.
