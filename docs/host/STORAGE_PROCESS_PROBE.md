# Storage Process Probe

`storage_process_probe` is a source-managed, read-only observation seam for
the storage lifecycle owner.  It is deliberately separate from the lifecycle
reaper: the probe reports whether a process has a path reference, while the
caller keeps the existing fail-closed decision and mutation policy.

The optional systemd socket and service templates are dormant source
templates.  They are not enabled by the bootstrap profiles and their
presence is not evidence that a host has installed or activated them.

## Protocol and boundary

The worker accepts one bounded JSON-lines request on an AF_UNIX stream.  A
request names at most 4096 absolute paths, a maximum of 32 references per path,
and a timeout between 100 ms and 30 seconds.  The worker request and response
are bounded to 1 MiB and 8 MiB respectively.  Lifecycle callers retain the
smaller 16-path/64 KiB/256 KiB route; the deep candidate refresh uses one
4096-path request with one reference per path.  The worker accepts no command,
file-content, glob, or arbitrary process query.

The root-owned unit supplies the exact allowed roots through
`ABYSS_STORAGE_PROCESS_PROBE_ALLOWED_ROOTS`.  The default source allowlist is
`/srv/abyss-machine` and `/srv/AbyssOS`; a user cache must be added explicitly
by the owner unit.  `/` is rejected, traversal is rejected, and resolved
paths must remain below an allowed root.  The worker returns only bounded
`pid`, `source`, and `target` path-reference fields.  Process command lines
and all other process metadata are omitted.  The owner client keeps absolute
paths outside this allowlist in a separate diagnostic result; they are never
sent to the privileged worker and remain `checked: false`.

The service authenticates the connecting peer with Linux `SO_PEERCRED` and
accepts only the UID named by the root-owned
`ABYSS_STORAGE_PROCESS_PROBE_ALLOWED_USER` setting.  The client authenticates
the service peer and expects UID 0 by default.  A malformed, unauthorized, or
incomplete exchange cannot become a positive safety observation.

The worker runs the existing `/proc` path-reference scanner in a killable
bounded child.  The service is capped at 512 MiB and 128 tasks, including the
bounded scanner child.  Permission failures, scanner failures, and timeouts preserve
`checked: false`.  If the socket is unavailable, an unprivileged caller may
use the existing scanner as a diagnostic fallback.  A real `/proc` fallback
always remains incomplete, including when it happens to see no references;
synthetic proc roots retain their fixture semantics for public tests.  Foreign
UID processes are never silently excluded.

## Owner installation route

Installation remains an owner decision.  A reviewed host projection should
render both `systemd/system/abyss-storage-process-probe.socket` and
`systemd/system/abyss-storage-process-probe.service`, verify the rendered
allowlist and peer user, run the focused probe tests, then daemon-reload and
activate the socket/service only through the host's narrow change route.
The unit has no network address family, no writable system or home view,
private devices and temporary directory, and only `CAP_SYS_PTRACE` plus
`CAP_DAC_READ_SEARCH` in its capability bounding and ambient sets so it can
inspect foreign `/proc` entries and their fd directories on this host.  No
other capability is granted by this template.  There is no root reaper, kill, deletion, archive, or
arbitrary command path in this helper.

Rollback is the inverse owner change: stop and disable the probe socket and
service, remove the rendered helper units if the owner route permits, and
restore the prior lifecycle package projection.  Existing storage records and
the lifecycle reaper's fail-closed behavior remain the recovery path while the
worker is absent.
