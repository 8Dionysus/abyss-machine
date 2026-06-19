# Roadmap

## Current Layer

- Keep the public seed reproducible and secret-free.
- Stabilize the source/install mirror around `config-templates/`, `systemd/`,
  `schemas/`, and validation lanes.
- Keep typing and nervous intake first-class, opt-in, and backed by a tested
  organ-specific path/service policy.

## Next Hardening

- Extract remaining subsystem-specific command glue from the monolithic CLI
  into tested modules.
- Add stricter schema validation after real bootstrap reports converge.
- Move mature helper tools into owning mechanic parts.
- Add release checks that combine public smoke, bootstrap dry-runs, path scans,
  and secret scans.

## Deferred

- Cross-OS support beyond Linux/systemd.
- Full public examples for private evidence records.
- Automatic migration of existing live hosts.
