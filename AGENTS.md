# abyss-machine Agent Route

`abyss-machine` is the public source home for the Abyss OS host-machine layer.
It makes a machine legible, routable, and maintainable by agents without
publishing the private life of a workstation.

## Route Selection

Start with this card and the nearest local `AGENTS.md`. Load supporting
documents only when their owner surface is involved:

- `README.md` for the public repository entrypoint;
- `DESIGN.md` and `BOUNDARIES.md` for system form or owner-boundary changes;
- `docs/publication/PUBLICATION_BOUNDARY.md` for publication or private-state
  questions;
- `stats/README.md`, `mechanics/README.md`, or `skills/README.md` for the
  corresponding public district map.

Do not preload a district README for unrelated work. Detailed inventories and
historical state belong in their owning docs, manifests, source, or generated
views rather than this inherited route card.

## Owns

- host contracts, public policy templates, and bootstrap/install projection
- host facts, diagnostic routes, and machine-readable evidence shapes
- typing and nervous-system intake machinery as opt-in host organs
- local AI runtime helpers when they are host-managed rather than stack-owned
- callable procedures whose meaning belongs specifically to the host-machine
  owner, with global exposure remaining a derived OS projection
- validators and smoke tests that prove the public seed can be rendered safely

## Does Not Own

- private `/etc/abyss-machine` deployments on any host
- generated `/var/lib/abyss-machine` evidence or histories
- large `/srv/abyss-machine` caches, runtimes, storage, backups, and temp data
- `abyss-stack` runtime substrate or sibling AoA doctrine
- browser captures, typed text histories, transcripts, vault contents, secrets,
  model weights, or local indexes

## Editing Law

- Keep public source separate from installed state.
- Put rendered-config sources under `config-templates/`, not under live paths.
- Put systemd skeletons under `systemd/`, not under a generic template bucket.
- Put stable operator entrypoints under `scripts/`; helper probes may remain in
  `tools/` until a mechanic package owns them.
- Use mechanics packages for durable host moves, not for miscellaneous notes.
- Keep typing and nervous surfaces first-class, privacy-gated, and opt-in.

## Landing

`.github/AGENTS.md` owns GitHub-native files and `.github/GITHUB_SURFACE.md`
owns the platform map. When landing is authorized: use a clean branch based on
current `origin/main`, commit only the intended diff, open a PR with checks and
residual risk, wait for green `Repo Validation`, merge through an allowed
method, then synchronize and verify clean `main`. If status or permissions
cannot be observed, stop instead of guessing.

Keep GitHub source proof separate from live-host evidence and never publish
private `/var/lib`, `/srv`, capture, secret, or index payloads.

## Validation

Run the narrowest affected test plus the graph contract using the exact clean
`aoa-sdk` scheduler pin named by `scripts/validation_evidence_graph.py`:

```bash
python -m pytest -q PATH_TO_AFFECTED_TEST
python scripts/validation_evidence_graph.py --profile instant --sdk-root PATH_TO_PINNED_AOA_SDK
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
```

The bootstrap dry-runs are required only when install/projection surfaces move.
Before landing, run the complete owner claim/evidence gate:

```bash
python scripts/release_check.py --sdk-root PATH_TO_PINNED_AOA_SDK --receipt /tmp/abyss-machine-validation.json
```

For host-contract migration work, also run the quick non-live lane:

```bash
python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json
```

Use serial release mode only as the explicit completeness oracle or rollback.
Before publication, scan for secrets and forbidden live paths.
