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
`validate_aggregate_descriptor_bound` is authoritative for that dynamic
aggregate at typed constructors, broker admission, live scans, and wire
decoders. The Draft 2020-12 schemas validate only structural shape, scalar
ranges, and absolute per-array wire ceilings; they do not claim to enforce the
dynamic cross-process sum. Key material is supplied through
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
