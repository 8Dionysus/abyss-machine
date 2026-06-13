# Host Model

The installed host layer uses these root classes:

- `/etc/abyss-machine`: rendered host config and local policy.
- `/var/lib/abyss-machine`: compact durable generated evidence.
- `/srv/abyss-machine`: large mutable caches, runtimes, storage, tools, and tmp.
- `/run/abyss-machine`: ephemeral runtime state.

The public repo describes how these roots are created and maintained. It does
not mirror their private contents.
