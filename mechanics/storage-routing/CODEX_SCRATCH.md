# Native Codex scratch lifecycle

The native hook adapter assigns temporary shell files to their Codex task and
enrolls newly created scratch paths in the existing managed-workspace lifecycle
as well as the storage candidate/claim plane. It does not run agents, read
transcripts, classify task completion, or delete files.

Installed entrypoint: `abyss-machine storage codex`. The standard bootstrap
launcher dispatches directly into the active package generation without
importing the large CLI binder. The module is
`abyss_machine.codex_storage_lifecycle`; `scripts/abyss-codex-storage` is a source
convenience wrapper. No separate helper installation is required.

## Event behavior

- SessionStart creates and registers a managed path with a 48-hour lease;
  UserPromptSubmit and active tool hooks renew that lease and the activity claim.
  An existing native record from before this integration remains candidate-only
  and is never adopted for automatic disposal.
- PreToolUse for Bash can prepend a task-local `TMPDIR` when configured with
  `--route-temp`. Other command arguments and the original shell program remain
  intact; an explicit later `TMPDIR` assignment wins.
- Stop, Interrupt, SubagentStop and SessionEnd record an observation and keep
  protection. These events do not prove semantic task completion. Native
  subagent hook calls may share the parent's session ID and temporary root.
- Explicit `close --session-id ID --receipt PATH --decision ...` records a SHA256
  digest of a compact owner receipt outside scratch and finalizes the existing
  lifecycle. `KEEP` and `UNKNOWN` seal and preserve the path. `DELETE` or
  `ARCHIVE --archive-target ABSOLUTE_PATH` are explicit owner dispositions that
  move the managed record to the existing bounded reaper after its grace period.
  Unique-data/recovery clearance still belongs to the existing candidate plane.
  Stop, idle and expiry remain protective. A later prompt in the same Codex
  task creates a new scratch generation; the previous generation retains its
  disposition and is never reopened or adopted.

Paths use the host storage roots by default. The adapter refuses traversal,
symlink ancestors, existing unowned directories, and an absent `/srv` mount.
It retains no command, prompt, assistant message, or transcript contents.
Small state files are replaced, rather than accumulating per-event JSONL.

## Native wiring

Merge the adjacent `codex-storage-hooks.json` fragment with existing hooks;
do not replace session-memory or other handlers. Existing handlers keep their
array positions. Native Codex requires review/trust for each new exact hook
definition before it will run. Do not manufacture trusted hashes or install
managed policy to bypass that review.

The source fragment routes shell temporary files only. Hooks are not a quota
or a complete write interceptor: programs with explicit destinations, native
apps, package managers and detached producers need their own owner route.
Large writes still need storage admission/reservation. A temporary directory
does not hold canonical source, source worktrees, final reports or persistent
runtime state.

Example owner closeout after preserving results:

```sh
abyss-machine storage codex close --session-id TASK_ID \
  --receipt /durable/path/closeout.json --decision KEEP
# or, after preserving the required results:
abyss-machine storage codex close --session-id TASK_ID \
  --receipt /durable/path/closeout.json --decision DELETE
abyss-machine storage candidates explain CANDIDATE_ID --json
```

The closeout writes reviewable lifecycle evidence; it does not override active
processes, unknown contents, owner preservation checks or exact apply gates.
The lease capability is retained only in the mode-0600 native metadata while a
managed scratch is open and is never emitted by `show` or `close`.

Native interface reference: <https://learn.chatgpt.com/docs/hooks>.
