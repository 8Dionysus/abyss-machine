# Host Model

The installed host layer uses these root classes:

- `/etc/abyss-machine`: rendered host config and local policy.
- `/var/lib/abyss-machine`: compact durable generated evidence.
- `/srv/abyss-machine`: large mutable caches, runtimes, storage, tools, and tmp.
- `/run/abyss-machine`: ephemeral runtime state.

The public repo describes how these roots are created and maintained. It does
not mirror their private contents.

Command ownership is tracked in [SUBSYSTEM_COMMANDS.md](SUBSYSTEM_COMMANDS.md):
the CLI remains the public entrypoint, while stable subsystem contracts should
live in importable `abyss_machine` package modules. Live host adapters are
tracked separately in [LIVE_ADAPTERS.md](LIVE_ADAPTERS.md) so public contracts
do not get confused with private runtime reads, writes, probes, and mutations.

On a new machine, bootstrap creates the empty root shape and projected source
contracts. Validators and opt-in units populate local evidence later:

- config templates render into `/etc/abyss-machine`;
- package modules install under `/usr/local/libexec`;
- the CLI entrypoint installs under `/usr/local/bin`;
- compact public seed read models install under `/usr/local/share/abyss-machine`;
- typing and nervous policy/config files render under `/etc/abyss-machine`;
- generated typing, nervous, artifact, process, and host facts remain local
  under `/var/lib/abyss-machine`;
- large captures, indexes, caches, runtimes, and temporary work stay under
  `/srv/abyss-machine`;
- runtime sockets, locks, and ephemeral state belong under `/run/abyss-machine`.
