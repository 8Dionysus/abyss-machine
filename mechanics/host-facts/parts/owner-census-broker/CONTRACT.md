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
process's cwd/root/fd descriptors; typed constructors, broker admission, live
scans, wire decoders, and the public schemas apply the same rule before
nested evidence is materialized. Key material is supplied through
`SigningKeyProvider`; it is not
stored in source or emitted in evidence/logs. Replay admission is supplied
through `ReplayStore`; a receiver must select the current broker/key/boot
generation and reject stale receipts.

## Fail-closed rules

The Linux backend snapshots and independently revalidates each admitted
process's cwd/root/fd entry names, readlink presentations, opened identities,
PID/start-tick/boot/UID/namespace identity, and mount identity. Any inventory
churn or readlink/open disagreement is incomplete. Scanner-owned transient
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
