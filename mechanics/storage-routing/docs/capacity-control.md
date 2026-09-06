# Capacity-only control

`abyss-storage-capacity.timer` runs the paired oneshot every five minutes. The
service calls the installed `{{ABYSS_LOCAL_BIN_DIR}}/abyss-machine` entrypoint
with `storage capacity --json`. That entrypoint binds the current installed
code generation before importing the capacity implementation, so the feed
uses the same generation guard as the existing monitor `ExecStartPre` route.

The service records the existing compact capacity observation for `/` and
`/srv`. It does not run the monitor, inventory, candidate refresh, deep scan,
cleanup, lifecycle reaper, or a second notification path. Keeping this cheap
sample outside the hourly medium monitor admission preserves a capacity point
when that monitor is deferred by memory or game policy; it does not claim that
the monitor or deep candidate read model is fresh.

This package is source-only until the owner reviews the rendered units. The
activation route is the existing bootstrap/systemd user-unit projection, then
`systemctl --user daemon-reload` and the owner-selected timer start. Installed
state and capacity observations remain outside this repository.
