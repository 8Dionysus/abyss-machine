"""Native Codex scratch ownership; hook events never authorize deletion.

Only identifiers, paths and lifecycle facts are retained. Prompt, command and
transcript contents are not stored. The existing storage candidate contract is
the sole candidate/claim shape; this adapter does not introduce another GC.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
from typing import Any, Iterator, Mapping

from . import storage_candidate_adapters as adapters
from . import storage_candidate_contracts as contracts

OWNER = "codex-native-scratch"
SCHEMA = "abyss_machine_codex_scratch_v1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
ACTIVE_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart"}
OBSERVED_EVENTS = ACTIVE_EVENTS | {"Stop", "SessionEnd", "SubagentStop", "Interrupt"}


def _stamp(when: dt.datetime) -> str:
    return when.astimezone(dt.timezone.utc).isoformat()


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("invalid Codex session identifier")
    return value


def _directory(path: Path, *, create: bool) -> Path:
    """Refuse symlink ancestors, including a symlink to an otherwise safe root."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute lexical roots without traversal are required")
    for parent in (*reversed(path.parents), path):
        if parent.is_symlink():
            raise ValueError(f"symlink directory refused: {parent}")
        if parent.exists() and not parent.is_dir():
            raise ValueError(f"directory required: {parent}")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


@contextlib.contextmanager
def _lock(root: Path) -> Iterator[None]:
    _directory(root, create=True)
    descriptor = os.open(root / ".lifecycle.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        deadline = time.monotonic() + 1.0
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("scratch lifecycle lock busy")
                time.sleep(0.01)
        yield
    finally:
        os.close(descriptor)


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError(f"symlink metadata refused: {path}")
    if not path.exists():
        return {}
    if path.stat().st_size > 65536:
        raise ValueError("oversized scratch metadata")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("scratch metadata must be an object")
    return value


class Lifecycle:
    def __init__(self, *, state_root: Path, scratch_root: Path, candidates_root: Path,
                 required_mount: Path | None = Path("/srv"), claim_seconds: int = 172800):
        self.state_root = _directory(state_root, create=False)
        self.scratch_root = _directory(scratch_root, create=False)
        self.candidates_root = _directory(candidates_root, create=False)
        self.required_mount = required_mount
        self.claim_seconds = max(300, claim_seconds)

    def _mount(self) -> None:
        if self.required_mount is None:
            return
        mount = _directory(self.required_mount, create=False)
        if not os.path.ismount(mount):
            raise ValueError("scratch mount is absent; root fallback is forbidden")
        if not self.scratch_root.is_relative_to(mount) or self.scratch_root == mount:
            raise ValueError("scratch root must be beneath its required mount")

    def _manifest(self, session_id: str, path: Path, now: dt.datetime,
                  previous: Mapping[str, Any]) -> dict[str, Any]:
        return contracts.manifest_document(
            path=str(path), owner=OWNER, kind="generated_tmp",
            purpose="Temporary files belonging to one native Codex task",
            producer="native-codex-hooks", source_id=f"codex:{session_id}",
            recovery_command=None, replacement_ref=None, retention_until=None,
            executor_type="age_bounded_tmp_cleanup",
            created_at=str(previous.get("created_at") or _stamp(now)),
            unique_data_clear=False, archivable=True,
        )

    def observe(self, event: Mapping[str, Any], *, route_temp: bool = False,
                now: dt.datetime | None = None) -> dict[str, Any]:
        """Renew ownership; Stop/SessionEnd are facts, not semantic closeout."""
        session_id = _identifier(event.get("session_id"))
        name = str(event.get("hook_event_name") or "")
        if name not in OBSERVED_EVENTS:
            return {}
        now = now or dt.datetime.now(dt.timezone.utc)
        self._mount()
        path = self.scratch_root / session_id
        metadata = self.state_root / f"{session_id}.json"
        claim_id = f"codex-{session_id}"
        with _lock(self.state_root):
            previous = _load(metadata)
            if previous and (previous.get("schema") != SCHEMA or previous.get("path") != str(path)):
                raise ValueError("scratch ownership metadata mismatch")
            if not previous and path.exists():
                raise ValueError("refusing to adopt an existing unowned scratch directory")
            if previous.get("state") == "closed" and name not in ACTIVE_EVENTS:
                return {}
            _directory(path, create=True)
            record = dict(previous)
            record.update(schema=SCHEMA, session_id=session_id, owner=OWNER,
                          path=str(path), created_at=previous.get("created_at") or _stamp(now),
                          last_event=name, observed_at=_stamp(now),
                          state="active" if name in ACTIVE_EVENTS else "idle_observed",
                          event_count=int(previous.get("event_count", 0)) + 1,
                          automatic_deletion=False)
            if name in ACTIVE_EVENTS:
                record.pop("closeout", None)
                record.pop("closed_at", None)
            # Commands, prompts and transcript bytes deliberately never enter this record.
            manifest = self._manifest(session_id, path, now, record)
            adapters.write_manifest(_directory(self.candidates_root / "manifests", create=True), manifest)
            claim = contracts.claim_document(
                claim_id=claim_id, candidate_id=manifest["candidate_id"], path=str(path),
                owner=OWNER, session_id=session_id, change_id=None,
                purpose="Protect task scratch until explicit owner closeout",
                issued_at=_stamp(now), expires_at=_stamp(now + dt.timedelta(seconds=self.claim_seconds)),
            )
            adapters.write_claim(_directory(self.candidates_root / "claims", create=True), claim)
            record["candidate_id"] = manifest["candidate_id"]
            adapters.atomic_write_json(metadata, record)

        context = (
            f"Managed temporary directory for this Codex task: {path}. "
            "Keep durable results and source worktrees outside it. "
            "Before a large write reserve its bytes through the host storage route. "
            "At actual task closeout preserve results, then explicitly close this scratch "
            "with abyss-machine storage codex close --session-id ID --receipt PATH. "
            "Stop, idle and claim expiry do not authorize deletion."
        )
        if name == "PreToolUse" and route_temp and event.get("tool_name") in {"Bash", "exec_command"}:
            tool_input = event.get("tool_input")
            if not isinstance(tool_input, Mapping) or not isinstance(tool_input.get("command"), str):
                raise ValueError("Bash hook requires tool_input.command")
            # A prefix is shell code, not eval: the original command remains byte-for-byte.
            # Explicit assignments in the user's command retain their normal precedence.
            prefix = f"export TMPDIR={shlex.quote(str(path))}\nexport ABYSS_STORAGE_SESSION_ID={shlex.quote(session_id)}\n"
            updated = dict(tool_input)
            updated["command"] = prefix + tool_input["command"]
            return {"hookSpecificOutput": {"hookEventName": name, "permissionDecision": "allow", "updatedInput": updated}}
        if name in {"SessionStart", "UserPromptSubmit", "SubagentStart"}:
            return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": context}}
        return {}

    def close(self, session_id: str, receipt: Path, *, now: dt.datetime | None = None) -> dict[str, Any]:
        """Record explicit owner closeout without inventing recovery proof."""
        session_id = _identifier(session_id)
        now = now or dt.datetime.now(dt.timezone.utc)
        receipt = receipt.absolute()
        _directory(receipt.parent, create=False)
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("a compact regular closeout receipt is required")
        if receipt.is_relative_to(self.scratch_root):
            raise ValueError("preserve the closeout receipt outside scratch")
        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
        with _lock(self.state_root):
            path = self.state_root / f"{session_id}.json"
            record = _load(path)
            if record.get("schema") != SCHEMA or record.get("path") != str(self.scratch_root / session_id):
                raise ValueError("unknown or mismatched managed scratch")
            record.update(state="closed", closed_at=_stamp(now),
                          closeout={"path": str(receipt), "sha256": digest}, automatic_deletion=False)
            # Clearance remains unknown until the owner proves preservation/recovery.
            # Releasing a claim only removes an activity blocker in the existing plane.
            adapters.release_claim(self.candidates_root / "claims", f"codex-{session_id}", released_at=_stamp(now))
            adapters.atomic_write_json(path, record)
            return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/abyss-machine/storage/codex-tasks"))
    parser.add_argument("--scratch-root", type=Path, default=Path("/srv/abyss-machine/tmp/codex"))
    parser.add_argument("--candidates-root", type=Path, default=Path("/var/lib/abyss-machine/storage/candidates"))
    parser.add_argument("--required-mount", type=Path, default=Path("/srv"))
    sub = parser.add_subparsers(dest="action", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--route-temp", action="store_true")
    close = sub.add_parser("close")
    close.add_argument("--session-id", required=True)
    close.add_argument("--receipt", required=True, type=Path)
    show = sub.add_parser("show")
    show.add_argument("--session-id", required=True)
    args = parser.parse_args(argv)
    try:
        lifecycle = Lifecycle(state_root=args.state_root, scratch_root=args.scratch_root,
                              candidates_root=args.candidates_root, required_mount=args.required_mount)
        if args.action == "hook":
            raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("oversized native hook input")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("native hook input must be an object")
            result = lifecycle.observe(payload, route_temp=args.route_temp)
        elif args.action == "close":
            result = lifecycle.close(args.session_id, args.receipt)
        else:
            result = _load(lifecycle.state_root / f"{_identifier(args.session_id)}.json")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TimeoutError) as exc:
        # A failure is visible to Codex; it never grants deletion or approvals.
        print(f"codex storage lifecycle: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
