# Native Codex scratch lifecycle

The native hook adapter assigns temporary shell files to their Codex task and
feeds the existing host storage candidate/claim plane. It does not run agents,
read transcripts, classify task completion, or delete files.

Source entrypoint: `scripts/abyss-codex-storage`. Install that script beside
`abyss-machine` after the corresponding package generation has been installed.
The module is `abyss_machine.codex_storage_lifecycle`. Source invocation needs
no installed host CLI.

## Event behavior

- SessionStart/UserPromptSubmit/SubagentStart registers the managed path and
  renews an activity claim for 48 hours.
- PreToolUse for Bash can prepend a task-local `TMPDIR` when configured with
  `--route-temp`. Other command arguments and the original shell program remain
  intact; an explicit later `TMPDIR` assignment wins.
- Stop, Interrupt, SubagentStop and SessionEnd record an observation and keep
  protection. These events do not prove semantic task completion. Native
  subagent hook calls may share the parent's session ID and temporary root.
- Explicit `close --session-id ID --receipt PATH` records a SHA256 digest of a
  compact owner receipt outside scratch, and releases only the activity claim.
  Unique-data/recovery clearance still belongs to the existing candidate plane.
  A resumed task renews protection and invalidates the earlier closeout.

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
abyss-codex-storage close --session-id TASK_ID --receipt /durable/path/closeout.json
abyss-machine storage candidates explain CANDIDATE_ID --json
```

This creates reviewable lifecycle evidence; it does not override active
processes, unknown contents, owner preservation checks or exact apply gates.

Native interface reference: <https://learn.chatgpt.com/docs/hooks>.
