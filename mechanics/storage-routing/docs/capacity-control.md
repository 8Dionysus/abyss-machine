# Capacity-only control

`abyss-storage-capacity.timer` runs the paired oneshot every five minutes. The
service calls the installed `{{ABYSS_LOCAL_BIN_DIR}}/abyss-machine` entrypoint
with `storage capacity --json`. That entrypoint binds the current installed
code generation before importing the capacity implementation, so the feed
uses the same generation guard as the existing monitor `ExecStartPre` route.

The service writes its latest complete result to
`{{ABYSS_MACHINE_STATE}}/storage/capacity-latest.json` on every run. The existing
forecast history retains its half-hour sample spacing; it is not the latest
five-minute observation. Consumers must check the result timestamp and service
status; a failed run can leave an empty or incomplete latest-result file.
The service measures `/` and `/srv`. It does not run the monitor, inventory, candidate refresh, deep scan,
cleanup, lifecycle reaper, or a second notification path. Keeping this cheap
sample outside the hourly medium monitor admission preserves a capacity point
when that monitor is deferred by memory or game policy; it does not claim that
the monitor or deep candidate read model is fresh.

This package is source-only until the owner reviews the rendered units. The
activation route is the existing bootstrap/systemd user-unit projection, then
`systemctl --user daemon-reload` and the owner-selected timer start. Installed
state and capacity observations remain outside this repository.

## Optional secondary benchmark writes

`storage-policy.json` may configure `secondary_write_routes` (empty in the
public template). Each route names one strict subtree of an existing mount:
`name`, absolute `root`, `kind: "benchmark"`, numeric `owner_uid`, and `mount`
with exact `mountpoint`, Linux `device` (`major:minor`), `filesystem`, `source`,
and mount `root` from `/proc/self/mountinfo`. Device numbers may change after
remount/reboot: stale identity denies new admission and requires the host owner
to refresh the configured facts after verifying the same intended volume.
An absent mount cannot fall through to the parent filesystem. Configure these host facts locally;
no portable template admits a whole volume. The route root must already exist
with mode `0700` and be owned by that UID. Symlinks, parent traversal, changed ownership,
unavailable/wrong mounts and nested mounts fail closed. Existing descendant
directories must have the same owner and device.

`storage write-preflight --kind benchmark` and `storage reservations acquire
--kind benchmark` use this route. Resource planning and launch select the
benchmark storage kind for the same admitted target; the workload resource
kind retains its ordinary meaning. Reservations recheck the mount under their
shared lock and after capacity collection, and aggregate all routes by actual
filesystem device. This is capacity accounting, not allocated blocks, inode
admission, held file descriptors, semantic review, publication, or workload fit.
The writing owner must retain custody of its target while writing.

Generic path protection and cleanup admission remain unchanged. Other write
kinds, unrelated volume paths and archive routes receive no added authority.
Removing the route from host policy revokes new write admission; release any
existing reservations through their ordinary owner lifecycle, preserving data.
Installing the source code and configuring a host route are separate actions.
Use the existing generation install route, preserve unrelated installed CLI
changes, and record the host policy change through the change ledger. Creating
and securing the empty route directory belongs to the authorized host operator;
this source patch creates neither that directory nor its mount.
