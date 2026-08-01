# Persistent candidate lifecycle

## Purpose

`abyss-machine storage candidates` remembers exact reclaim candidates and the
evidence that blocks or advances them. It replaces repeated directory-size
archaeology, not operator authority.

Lifecycle:

```text
discovered -> observed -> classified -> validated -> operator-approved
           -> externally applied -> receipted
```

No command in this source stage automatically deletes, archives, moves, or
stops the subject.

## State and cadence

- latest: `/var/lib/abyss-machine/storage/candidates/latest.json`
- history: `/var/lib/abyss-machine/storage/candidates/history/`
- manifests: `/var/lib/abyss-machine/storage/candidates/manifests/`
- renewable claims: `/var/lib/abyss-machine/storage/candidates/claims/`
- validations, approvals, external receipts, and changed-only notification
  records live in sibling directories.
- the hourly storage monitor performs a cheap carry-forward and records evidence
  age; it never promotes a candidate.
- `abyss-storage-candidates-deep.timer` performs the daily deep scan.
- pressure or significant inventory growth requests a deep scan at most once
  per 12 hours.

## Reading the result

Start with:

```bash
abyss-machine storage candidates list --min-bytes 1073741824 --json
abyss-machine storage candidates explain CANDIDATE_ID --json
```

`physical_bytes` is measured with same-filesystem physical blocks. Podman image
reclaim uses unique layer bytes, not total image size. A parent with child
candidates is summary-only and has zero reclaimable bytes.

Ready verdicts are hard-gate results, not scores. Any incomplete fingerprint,
unreadable process surface, active route, unknown owner, unique data, stale
backup, missing restore proof, active claim, instability, or drift blocks
readiness.

## Producer integration

Large-write and runtime producers should call post hooks with a
`candidate_manifest` payload or invoke `storage candidates register`. A
manifest declares purpose, owner, exact path, retention, recovery/replacement,
preserved references, and owner executor. Declaration is not verification
unless the producer supplies the corresponding verified evidence.

Long-running sessions and host changes renew claims with a bounded TTL. Claim
release or expiry only removes a blocker; it never grants permission.

## Validation, approval, and receipts

`storage candidates validate ID` performs a fresh deep collection for exactly
one candidate and fails closed on fingerprint or verdict drift. `approve`
binds a short-lived operator approval to that validation. `receipt` records an
action performed by an external owner executor and requires evidence refs.

The candidate subsystem intentionally does not execute that external action.
Any future executor must consume the exact approval, revalidate immediately,
admit only the executor registered for the candidate kind, and write a receipt.

## Owner adapters

- Git worktrees require clean status and reachability from authority outside
  the removable worktree; dirty/untracked patches are unique data.
- Hugging Face cache candidates require a decodable repository identity and a
  canonical cache layout.
- OpenVINO/model cache candidates require an owner workload rebuild or verified
  replacement, not merely an old mtime.
- unused Podman volumes remain archive/unique-data blockers.
- `.aoa` is consumed only through the session-memory owner's
  `maintenance-cleanup` dry-run. The generic scanner never enters `.aoa` and
  cannot override an owner refusal or active writer.
- Vault readiness requires a fresh covering lane plus digest and restore
  verification; mount and timer state are insufficient.

## Deployment and migration

Install through the normal `abyss-machine-bootstrap` owner route. The install
adds the daily user timer and CLI modules. Existing storage inventory,
cleanup-plan, artifact, Vault, and runtime records are read-only inputs; no
large data migration occurs. The first hourly refresh may be empty until the
first deep scan seeds candidates.

Before enabling the timer, run source tests and one deep refresh with
`ABYSS_MACHINE_STORAGE_CANDIDATES_ROOT` pointed at a scratch directory. Inspect
candidate counts, truncated fingerprints, unknown owners, and top reclaimable
objects. Then enable the timer through bootstrap and validate the installed
projection.

## Rollback

Disable `abyss-storage-candidates-deep.timer` and restore the previous installed
code generation through the normal bootstrap rollback. Do not delete candidate
state during rollback: it is compact evidence and can be inspected by older
tools as inert JSON. The legacy inventory/pressure/cleanup-plan routes continue
to work independently.

Rollback never removes subject data and never requires Vault mutation.

## Monitoring

Review timer state, latest deep time, deep duration, candidate count, truncated
fingerprints, process scan errors, owner-unknown blockers, verdict transitions,
and changed-only notifications. A quiet notification stream means no observed
verdict change, not that no storage changed.
