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
from typing import Any, Iterator, Mapping, Sequence

from . import storage_candidate_adapters as adapters
from . import storage_candidate_contracts as contracts
from . import storage_lifecycle_adapters
from . import storage_lifecycle_contracts

OWNER = "codex-native-scratch"
SCHEMA = "abyss_machine_codex_scratch_v1"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
ACTIVE_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "SubagentStart"}
OBSERVED_EVENTS = ACTIVE_EVENTS | {"Stop", "SessionEnd", "SubagentStop", "Interrupt"}
DEFAULT_LIFECYCLE_ROOT = Path("/var/lib/abyss-machine/storage/lifecycle")
LIFECYCLE_FIELD = "workspace_lifecycle"


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


def _without_secrets(value: Any) -> Any:
    """Return a JSON-safe view without private lifecycle capabilities."""
    if isinstance(value, Mapping):
        return {
            key: _without_secrets(item)
            for key, item in value.items()
            if key != "lease_token"
        }
    if isinstance(value, list):
        return [_without_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [_without_secrets(item) for item in value]
    return value


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return _without_secrets(record)


class Lifecycle:
    def __init__(self, *, state_root: Path, scratch_root: Path, candidates_root: Path,
                 lifecycle_root: Path | None = None,
                 required_mount: Path | None = Path("/srv"), claim_seconds: int = 172800):
        self.state_root = _directory(state_root, create=False)
        self.scratch_root = _directory(scratch_root, create=False)
        self.candidates_root = _directory(candidates_root, create=False)
        self.lifecycle_root = _directory(
            lifecycle_root if lifecycle_root is not None else state_root.parent / "lifecycle",
            create=False,
        )
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

    def _scratch_path(self, session_id: str, generation: Any) -> Path:
        if type(generation) is not int or not 1 <= generation <= 1_000_000:
            raise ValueError("invalid scratch generation")
        name = session_id if generation == 1 else f"{session_id}-g{generation}"
        return self.scratch_root / name

    def _register_new_workspace(self, path: Path, now: dt.datetime) -> dict[str, Any]:
        _directory(self.scratch_root, create=True)
        registered = storage_lifecycle_adapters.register_workspace(
            self.lifecycle_root,
            owner=OWNER,
            workspace=path,
            unit=None,
            lease_seconds=self.claim_seconds,
            create=True,
            now_time=now,
        )
        if registered.get("ok") is not True:
            errors = ", ".join(str(item) for item in registered.get("errors", [])[:3])
            raise ValueError(f"managed scratch registration failed{': ' + errors if errors else ''}")
        managed = registered.get("record")
        token = registered.get("lease_token")
        if not isinstance(managed, Mapping) or not isinstance(token, str) or not token:
            raise ValueError("managed scratch registration returned incomplete capability")
        if managed.get("launcher_created") is not True:
            raise ValueError("refusing to adopt existing managed scratch")
        if str(managed.get("path") or "") != str(path):
            raise ValueError("managed scratch registration path mismatch")
        _directory(path, create=False)
        return {
            "root": str(self.lifecycle_root),
            "workspace_id": str(managed["workspace_id"]),
            "callback_path": str(managed["callback_path"]),
            "lease_token": token,
        }

    def _managed_workspace(self, record: Mapping[str, Any], path: Path) -> dict[str, Any] | None:
        value = record.get(LIFECYCLE_FIELD)
        if value is None:
            return None
        _directory(path, create=False)
        if not path.exists():
            raise ValueError("managed scratch path is missing")
        if not isinstance(value, Mapping):
            raise ValueError("managed scratch lifecycle metadata must be an object")
        root = Path(str(value.get("root") or ""))
        if root != self.lifecycle_root:
            raise ValueError("managed scratch lifecycle root mismatch")
        workspace_id = str(value.get("workspace_id") or "")
        token = value.get("lease_token")
        if not IDENTIFIER.fullmatch(workspace_id) or not isinstance(token, str) or not token:
            raise ValueError("managed scratch lifecycle capability is missing")
        managed_path = storage_lifecycle_adapters.record_path(root, workspace_id)
        managed = storage_lifecycle_adapters.read_json(managed_path)
        if managed is None:
            raise ValueError("managed scratch lifecycle record is missing")
        if str(managed.get("path") or "") != str(path) or managed.get("owner") != OWNER:
            raise ValueError("managed scratch lifecycle identity mismatch")
        if managed.get("launcher_created") is not True:
            raise ValueError("managed scratch was not created by the lifecycle launcher")
        callback = storage_lifecycle_adapters.callback_path(root, workspace_id)
        if str(managed.get("callback_path") or "") != str(callback):
            raise ValueError("managed scratch callback path mismatch")
        return {
            "root": str(root),
            "workspace_id": workspace_id,
            "callback_path": str(callback),
            "lease_token": token,
        }

    def _renew_managed_workspace(self, lifecycle: Mapping[str, Any], now: dt.datetime) -> None:
        renewed = storage_lifecycle_adapters.renew_registered_workspace(
            self.lifecycle_root,
            workspace_id=str(lifecycle["workspace_id"]),
            lease_token=str(lifecycle["lease_token"]),
            lease_seconds=self.claim_seconds,
            now_time=now,
        )
        if renewed.get("ok") is not True:
            errors = ", ".join(str(item) for item in renewed.get("errors", [])[:3])
            raise ValueError(f"managed scratch lease renewal failed{': ' + errors if errors else ''}")

    def observe(self, event: Mapping[str, Any], *, route_temp: bool = False,
                now: dt.datetime | None = None) -> dict[str, Any]:
        """Renew ownership; Stop/SessionEnd are facts, not semantic closeout."""
        session_id = _identifier(event.get("session_id"))
        name = str(event.get("hook_event_name") or "")
        if name not in OBSERVED_EVENTS:
            return {}
        now = now or dt.datetime.now(dt.timezone.utc)
        self._mount()
        metadata = self.state_root / f"{session_id}.json"
        claim_id = f"codex-{session_id}"
        with _lock(self.state_root):
            previous = _load(metadata)
            generation = previous.get("generation", 1)
            path = self._scratch_path(session_id, generation)
            if previous and (previous.get("schema") != SCHEMA or previous.get("path") != str(path)):
                raise ValueError("scratch ownership metadata mismatch")
            if previous.get("state") == "closed" and name not in ACTIVE_EVENTS:
                return {}
            previous_workspace_id = previous.get("previous_workspace_id")
            if previous.get("state") == "closed" and name in ACTIVE_EVENTS:
                # A Codex task can receive another prompt after explicit owner
                # closeout. Allocate a new generation without reopening or
                # adopting the old path, which may still await its reaper.
                old_lifecycle = previous.get(LIFECYCLE_FIELD)
                if isinstance(old_lifecycle, Mapping):
                    previous_workspace_id = old_lifecycle.get("workspace_id")
                generation += 1
                path = self._scratch_path(session_id, generation)
                previous = {}
            if not previous and path.exists():
                raise ValueError("refusing to adopt an existing unowned scratch directory")
            managed_lifecycle = self._managed_workspace(previous, path) if previous else None
            if previous and managed_lifecycle is not None:
                if name in ACTIVE_EVENTS:
                    self._renew_managed_workspace(managed_lifecycle, now)
                _directory(path, create=False)
            elif previous:
                # Legacy native records remain candidate-only.  They are never
                # retroactively adopted by the automatic managed lifecycle.
                _directory(path, create=True)
            else:
                managed_lifecycle = self._register_new_workspace(path, now)
            record = dict(previous)
            record.update(schema=SCHEMA, session_id=session_id, owner=OWNER,
                          generation=generation,
                          path=str(path), created_at=previous.get("created_at") or _stamp(now),
                          last_event=name, observed_at=_stamp(now),
                          state="active" if name in ACTIVE_EVENTS else "idle_observed",
                          event_count=int(previous.get("event_count", 0)) + 1,
                          automatic_deletion=False)
            if previous_workspace_id:
                record["previous_workspace_id"] = previous_workspace_id
            if managed_lifecycle is not None:
                record[LIFECYCLE_FIELD] = managed_lifecycle
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
            storage_lifecycle_adapters.atomic_write_json(metadata, record, mode=0o600)

        context = (
            f"Managed temporary directory for this Codex task: {path}. "
            "Keep durable results and source worktrees outside it. "
            "Before a large write reserve its bytes through the host storage route. "
            "At actual task closeout preserve results outside scratch, write a compact "
            "receipt outside it, then explicitly close this scratch with "
            "abyss-machine storage codex close --session-id ID --receipt PATH "
            "--decision DELETE|ARCHIVE|KEEP|UNKNOWN; ARCHIVE also requires "
            "--archive-target ABSOLUTE_PATH. New managed scratch is handled by this "
            "owner closeout and does not require a daily manual review. "
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

    def close(self, session_id: str, receipt: Path, *, decision: str = "UNKNOWN",
              archive_target: Path | None = None,
              owner_evidence_refs: Sequence[str] = (), grace_seconds: int = 60,
              now: dt.datetime | None = None) -> dict[str, Any]:
        """Finalize explicit owner closeout through the managed lifecycle."""
        session_id = _identifier(session_id)
        now = now or dt.datetime.now(dt.timezone.utc)
        receipt = receipt.absolute()
        _directory(receipt.parent, create=False)
        if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("a compact regular closeout receipt is required")
        if receipt.is_relative_to(self.scratch_root):
            raise ValueError("preserve the closeout receipt outside scratch")
        digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
        selected_decision = str(decision or "UNKNOWN").upper()
        if selected_decision not in storage_lifecycle_contracts.DECISIONS:
            raise ValueError("unsupported owner disposition")
        try:
            grace = max(0, int(grace_seconds))
        except (TypeError, ValueError) as exc:
            raise ValueError("grace seconds must be a nonnegative integer") from exc
        plan: dict[str, Any] = {}
        if selected_decision == "DELETE":
            plan = {"kind": "delete_workspace"}
        elif selected_decision == "ARCHIVE":
            if archive_target is None:
                raise ValueError("archive target is required for ARCHIVE")
            target = Path(archive_target).expanduser()
            if not target.is_absolute() or ".." in target.parts:
                raise ValueError("ARCHIVE requires an absolute target without traversal")
            plan = {"kind": "archive_workspace", "target": str(target)}
        if isinstance(owner_evidence_refs, (str, bytes)):
            evidence_refs = [str(owner_evidence_refs)]
        else:
            evidence_refs = [str(item) for item in owner_evidence_refs if str(item)]
        receipt_ref = f"codex-receipt-sha256:{digest}"
        if receipt_ref not in evidence_refs:
            evidence_refs.append(receipt_ref)
        disposition = {
            "decision": selected_decision,
            "plan": plan,
            "owner_evidence_refs": evidence_refs,
        }
        normalized = storage_lifecycle_contracts.disposition_document(disposition)
        if normalized.get("valid") is not True:
            errors = ", ".join(str(item) for item in normalized.get("errors", [])[:3])
            raise ValueError(f"invalid owner disposition{': ' + errors if errors else ''}")
        with _lock(self.state_root):
            metadata = self.state_root / f"{session_id}.json"
            record = _load(metadata)
            workspace = self._scratch_path(session_id, record.get("generation", 1))
            if record.get("schema") != SCHEMA or record.get("path") != str(workspace):
                raise ValueError("unknown or mismatched managed scratch")
            managed_lifecycle = self._managed_workspace(record, workspace)
            if managed_lifecycle is None:
                if selected_decision in storage_lifecycle_contracts.MUTATING_DECISIONS:
                    raise ValueError("existing native scratch is unmanaged; DELETE/ARCHIVE is refused")
                record.update(
                    state="closed",
                    closed_at=_stamp(now),
                    closeout={"path": str(receipt), "sha256": digest},
                    disposition=normalized,
                    automatic_deletion=False,
                )
                adapters.release_claim(self.candidates_root / "claims", f"codex-{session_id}", released_at=_stamp(now))
                storage_lifecycle_adapters.atomic_write_json(metadata, record, mode=0o600)
                return _public_record(record)

            callback_path = storage_lifecycle_adapters.callback_path(
                self.lifecycle_root,
                str(managed_lifecycle["workspace_id"]),
            )
            managed_path = storage_lifecycle_adapters.record_path(
                self.lifecycle_root,
                str(managed_lifecycle["workspace_id"]),
            )
            managed_record = storage_lifecycle_adapters.read_json(managed_path)
            if managed_record is None:
                raise ValueError("managed scratch lifecycle record is missing")
            storage_lifecycle_adapters.atomic_write_json(callback_path, disposition, mode=0o600)
            if managed_record.get("state") == "open":
                finalized = storage_lifecycle_adapters.finalize_managed_workspace(
                    self.lifecycle_root,
                    managed_lifecycle,
                    grace_seconds=grace,
                )
            elif managed_record.get("state") == "sealed":
                consumed = storage_lifecycle_adapters.consume_owner_callback(
                    self.lifecycle_root,
                    workspace_id=str(managed_lifecycle["workspace_id"]),
                    grace_seconds=grace,
                )
                consumed_record = consumed.get("record") if isinstance(consumed.get("record"), Mapping) else {}
                finalized = {
                    "ok": bool(consumed.get("ok")),
                    "workspace_id": str(managed_lifecycle["workspace_id"]),
                    "sealed": True,
                    "released": consumed.get("released") is True,
                    "state": str(consumed_record.get("state") or "sealed"),
                    "disposition": consumed_record.get("disposition"),
                    "errors": consumed.get("errors") or [],
                }
            else:
                finalized = {
                    "ok": False,
                    "workspace_id": str(managed_lifecycle["workspace_id"]),
                    "errors": ["managed_workspace_not_open_or_sealed"],
                }
            if finalized.get("ok") is not True:
                errors = ", ".join(str(item) for item in finalized.get("errors", [])[:3])
                raise ValueError(f"managed scratch closeout failed{': ' + errors if errors else ''}")
            record.update(
                state="closed",
                closed_at=_stamp(now),
                closeout={"path": str(receipt), "sha256": digest},
                disposition=normalized,
                lifecycle_closeout={
                    "workspace_id": str(managed_lifecycle["workspace_id"]),
                    "state": str(finalized.get("state") or "sealed"),
                    "sealed": finalized.get("sealed") is True,
                    "released": finalized.get("released") is True,
                },
                automatic_deletion=False,
            )
            # The lifecycle record no longer needs the capability after seal;
            # remove the only plaintext token copy before publishing metadata.
            record_lifecycle = dict(managed_lifecycle)
            record_lifecycle.pop("lease_token", None)
            record_lifecycle["state"] = str(finalized.get("state") or "sealed")
            record[LIFECYCLE_FIELD] = record_lifecycle
            # Clearance remains unknown until the owner proves preservation/recovery.
            adapters.release_claim(self.candidates_root / "claims", f"codex-{session_id}", released_at=_stamp(now))
            storage_lifecycle_adapters.atomic_write_json(metadata, record, mode=0o600)
            return _public_record(record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("/var/lib/abyss-machine/storage/codex-tasks"))
    parser.add_argument("--scratch-root", type=Path, default=Path("/srv/abyss-machine/tmp/codex"))
    parser.add_argument("--candidates-root", type=Path, default=Path("/var/lib/abyss-machine/storage/candidates"))
    parser.add_argument("--lifecycle-root", type=Path, default=DEFAULT_LIFECYCLE_ROOT)
    parser.add_argument("--required-mount", type=Path, default=Path("/srv"))
    sub = parser.add_subparsers(dest="action", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--route-temp", action="store_true")
    close = sub.add_parser("close")
    close.add_argument("--session-id", required=True)
    close.add_argument("--receipt", required=True, type=Path)
    close.add_argument("--decision", choices=sorted(storage_lifecycle_contracts.DECISIONS), default="UNKNOWN")
    close.add_argument("--archive-target", type=Path)
    close.add_argument("--evidence-ref", action="append", default=[])
    close.add_argument("--grace-seconds", type=int, default=60)
    show = sub.add_parser("show")
    show.add_argument("--session-id", required=True)
    args = parser.parse_args(argv)
    try:
        lifecycle = Lifecycle(state_root=args.state_root, scratch_root=args.scratch_root,
                              candidates_root=args.candidates_root, lifecycle_root=args.lifecycle_root,
                              required_mount=args.required_mount)
        if args.action == "hook":
            raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("oversized native hook input")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("native hook input must be an object")
            result = lifecycle.observe(payload, route_temp=args.route_temp)
        elif args.action == "close":
            result = lifecycle.close(
                args.session_id,
                args.receipt,
                decision=args.decision,
                archive_target=args.archive_target,
                owner_evidence_refs=args.evidence_ref,
                grace_seconds=args.grace_seconds,
            )
        else:
            result = _public_record(_load(lifecycle.state_root / f"{_identifier(args.session_id)}.json"))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, TimeoutError) as exc:
        # A failure is visible to Codex; it never grants deletion or approvals.
        print(f"codex storage lifecycle: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
