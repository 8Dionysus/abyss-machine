# Roadmap

## Current Layer

- Keep the public seed reproducible and secret-free.
- Stabilize the source/install mirror around `config-templates/`, `systemd/`,
  `schemas/`, and validation lanes.
- Keep typing and nervous intake first-class, opt-in, and backed by a tested
  organ-specific path/service policy plus refresh decision helpers.

## Next Hardening

- Extract remaining subsystem-specific command glue from the monolithic CLI
  into tested modules.
- Continue live adapter hardening from `docs/host/LIVE_ADAPTERS.md`, starting
  with typing/nervous adapters before wider host mutation/execution seams.
- Add stricter schema validation after real bootstrap reports converge.
- Move mature helper tools into owning mechanic parts.
- Add release checks from `docs/testing/RELEASE_CHECK_ROUTE.md` that combine
  public smoke, bootstrap dry-runs, path scans, secret scans, source/install
  projection, and relevant host quick checks.

## Deferred

- Cross-OS support beyond Linux/systemd.
- Full public examples for private evidence records.
- Automatic migration of existing live hosts.
