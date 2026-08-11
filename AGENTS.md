# abyss-machine Agent Route

`abyss-machine` is the public source home for the Abyss OS host-machine layer.
It makes a machine legible, routable, and maintainable by agents without
publishing the private life of a workstation.

## Read First

1. `README.md`
2. `DESIGN.md`
3. `BOUNDARIES.md`
4. `docs/publication/PUBLICATION_BOUNDARY.md`
5. `stats/README.md` when owner-local statistical questions or contracts move
6. `mechanics/README.md`
7. `skills/README.md` when an owner-callable agent procedure moves
8. the nearest local `AGENTS.md`

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

## GitHub Landing Workflow

Root `AGENTS.md` owns the repository-wide branch, PR, CI, and merge route.
`.github/AGENTS.md` owns the GitHub-native files that support it.

When the user asks to commit, push, and merge in this repository, use this
route:

1. Start from a clean branch based on current `origin/main`.
2. Commit only the intended diff with a message that names the changed surface.
3. Push the branch and open a pull request with changed surfaces, validation,
   skipped checks, remaining risk, and any local live-host evidence that GitHub
   cannot reproduce.
4. Wait for GitHub `Repo Validation` to finish. If it fails, fix the branch and
   wait for the new result.
5. Merge through GitHub after green validation. Use squash unless repository
   settings report a different allowed method; report which method landed.
6. Return to `main`, fast-forward from `origin/main`, and confirm the worktree
   is clean before closeout.

GitHub validation is public-safe proof for the repository seed. It does not
replace local host evidence. For changes that touched installed
`abyss-machine`, typing/nervous, self-awareness, or generated host contracts,
report the local host checks separately and do not publish live `/var/lib`,
`/srv`, secrets, captures, or indexes.

If GitHub status or merge permissions cannot be observed, stop the landing route
and report the exact blocker instead of guessing.

## Validation

During the edit loop, run the narrowest affected test plus the sub-second graph
contract. The graph command requires the exact clean `aoa-sdk` scheduler pin
named by `scripts/validation_evidence_graph.py`:

```bash
python -m pytest -q PATH_TO_AFFECTED_TEST
python scripts/validation_evidence_graph.py --profile instant --sdk-root PATH_TO_PINNED_AOA_SDK
scripts/abyss-machine-bootstrap doctor --dry-run --json
scripts/abyss-machine-bootstrap render --profile linux-systemd-core --dry-run --json
```

Before landing, run the complete owner claim/evidence gate. It schedules the
same owner obligations as the independent serial oracle and writes a bound
receipt:

```bash
python scripts/release_check.py --sdk-root PATH_TO_PINNED_AOA_SDK --receipt /tmp/abyss-machine-validation.json
```

Use `python scripts/release_check.py --mode serial` only as the explicit
completeness oracle and rollback, not as the ordinary fast path.

For host-contract migration work, also run:

```bash
python -m pytest -q tests/host_contract -m "quick and not live and not long and not manual"
PYTHONDONTWRITEBYTECODE=1 tools/abyss-machine-test quick --json
```

Before publication, scan for obvious secrets and forbidden live paths.
