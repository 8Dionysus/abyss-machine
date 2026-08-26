# Owner Census Broker Source Card

## Ownership

`abyss-machine` owns bounded host observation and receipt authentication. A
caller supplies the request, target snapshot, finite limits, broker identity,
boot identity, key provider, and replay store. No host project, user, Goal,
incident, candidate name, or fixed storage path is an input or allowlist.

## Evidence binding

The request, evidence, and receipt bind:

- request id/digest, scope, target snapshot digest, and ordered exact
  `(dev, ino, mount_id, object_kind)` identities;
- process PID, start ticks, boot identity, namespace-derived run identity,
  credential UID, and cwd/root/fd descriptor evidence;
- deleted regular-file status when procfs exposes it;
- finite process, descriptor, target, and duration bounds;
- scan/issue/expiry timestamps, broker and key generations, broker boot
  identity, nonce, replay counter, completeness, reason, signature, and
  content digest.

Wire decoding is exact: missing and unknown fields, bool-as-int, textual
booleans, malformed signatures/digests, and over-limit collections fail
closed. `max_descriptors` is one aggregate bound across every admitted
process's cwd/root/fd descriptors. The owner semantic validator
`validate_census_semantics` is the single authoritative typed admission gate
for process count, target cardinality, per-process descriptors, aggregate
descriptors, duration, and coupled boot/timestamp invariants at constructors,
broker admission, live scans, wire decoders, and both receipt verification
boundaries. The Draft 2020-12 schemas validate only structural shape, scalar
ranges, and absolute per-array wire ceilings; they do not claim to enforce
dynamic owner bounds or the dynamic cross-process sum. Key material is supplied through
`SigningKeyProvider`; it is not
stored in source or emitted in evidence/logs. Replay admission is supplied
through `ReplayStore`; a receiver must select the current broker/key/boot
generation and reject stale receipts.

## Observational stability, not history

For every cwd/root/fd observation, the Linux backend reads the textual procfs
link, follows the descriptor path for a pre-open `(dev, ino, object_kind)`
identity, opens the path and records the fd identity, then performs a
post-open readlink and followed-identity observation. Any observable
readlink/open transition or target-identity mismatch is incomplete. The second
inventory pass repeats the observation and compares the complete internal
sample, including those followed identities.

`complete=true` therefore means observational stability across the bounded
sample, not historical no-churn. An exact same-object A→B→A replacement that
leaves no observable difference between these reads is unprovable in userspace;
this contract makes no claim about it. A future race-safe deletion owner still
needs an atomic claim/quiescence protocol. This evidence is never deletion
authority and cannot weaken that later safety requirement.

## Fail-closed rules

The Linux backend snapshots and independently revalidates each admitted
process's cwd/root/fd entry names, readlink presentations, followed identities,
opened identities, PID/start-tick/boot/UID/namespace identity, and mount
identity. Any inventory churn or readlink/open disagreement is incomplete.
Scanner-owned transient
descriptors are tracked from runtime-owned descriptors and stable process
identity, without fixed fd names.

Optional injected readers are selected by presence (`None` means use the
default), never by callable truthiness. Each backend scanner descriptor has a
generation-tagged ownership record. Open publication, close claims, state
observation, and conditional ledger removal use a short per-backend
synchronization boundary; the injected closer runs outside it so unrelated
census work is not serialized. The close injection ABI is typed and opaque:
an injected callback receives one backend-issued
`ScannerFdCloseCapability`, not a numeric fd, and must call its one-use
`close()` operation exactly once. The capability revalidates the current
generation and observed fd identity at the final owner-controlled boundary,
then performs the syscall while the short ledger boundary is held. Default
close uses the same capability path. Stale, replayed, or reentrant authority
is rejected immediately, and a callback that returns without consuming its
capability is a typed failure. Stale finalization cannot remove a newer
scanner generation. After a closer error, the original exception is
preserved; recovery removes only a definitively closed/reused generation and
otherwise retains a still-owned or unknown descriptor fail-closed. It never
uses a check-then-`os.close` fallback and does not claim an impossible kernel
atomic close-by-inode operation.

The Linux backend returns incomplete evidence for unsupported platforms,
unreadable PID 1, the current process, or another visible UID, missing
credentials, changing PID/start ticks/boot/namespace observations, missing
or ambiguous mount identity, unreadable cwd/root/fd references, and process,
descriptor, or time-bound exhaustion. It never treats a partial scan as a
complete census. A regular file is marked deleted only when procfs presents
the deleted suffix and the opened inode has `st_nlink == 0`; disagreement is
ambiguous and incomplete.

## Boundary

This is evidence only. It exposes no path mutation, process control, command
execution, deletion, rename, quarantine, reclaim, cleanup, operation grant,
storage-pressure authority, free-space threshold, launch decision, installed
activation, or privileged key storage. Any future timer/reconciler may only
observe or recover from a crash; it cannot acquire mutation authority here.
