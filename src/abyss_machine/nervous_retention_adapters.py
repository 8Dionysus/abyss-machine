from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from . import nervous_retention
from . import typing_nervous_adapters


SymlinkTailPort = Callable[[Path, Path | None], bool]
UnlinkPort = Callable[[Path], None]
LatestHistoryWriterPort = Callable[[dict[str, Any], Path, Path], list[dict[str, Any]]]
LatestJsonWriterPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
LatestJsonReaderPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]


def file_record_time(path: Path) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).astimezone()
    except OSError:
        return None


def path_has_symlink_tail(path: Path, stop_at: Path | None = None) -> bool:
    try:
        resolved_stop = stop_at.resolve() if stop_at else None
    except OSError:
        resolved_stop = None
    current = path
    checked: list[Path] = []
    while True:
        checked.append(current)
        if current.parent == current:
            break
        if resolved_stop is not None:
            try:
                if current.resolve() == resolved_stop:
                    break
            except OSError:
                pass
        current = current.parent
    return any(item.exists() and item.is_symlink() for item in checked)


def collect_file_candidates(
    routes: list[dict[str, Any]],
    *,
    now_time: dt.datetime | None = None,
    stop_at: Path | None = None,
    symlink_tail: SymlinkTailPort = path_has_symlink_tail,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now_time = now_time or dt.datetime.now(dt.timezone.utc).astimezone()
    files: list[dict[str, Any]] = []
    route_errors: list[dict[str, Any]] = []
    for spec in routes:
        root = Path(spec["root"])
        if symlink_tail(root, stop_at):
            route_errors.append({"layer": spec["layer"], "root": str(root), "error": "symlink_tail"})
        if not root.exists():
            files.append(nervous_retention.root_missing_record(spec))
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            try:
                relative = path.relative_to(root)
            except ValueError:
                route_errors.append({"layer": spec["layer"], "root": str(root), "path": str(path), "error": "outside_root"})
                continue
            mtime = file_record_time(path)
            try:
                size = path.stat().st_size
            except OSError:
                size = None
            files.append(
                nervous_retention.file_candidate_record(
                    spec,
                    path=str(path),
                    relative=str(relative),
                    suffix=path.suffix,
                    size_bytes=size,
                    mtime=mtime,
                    now_time=now_time,
                )
            )
    return files, route_errors


def default_latest_history_writer(data: dict[str, Any], latest_path: Path, daily_root: Path) -> list[dict[str, Any]]:
    return typing_nervous_adapters.write_latest_and_history(data, latest_path, daily_root, mode=0o664)


def write_latest_history(
    data: dict[str, Any],
    *,
    latest_path: Path,
    daily_root: Path,
    writer: LatestHistoryWriterPort = default_latest_history_writer,
) -> dict[str, Any]:
    errors = writer(data, latest_path, daily_root)
    if errors:
        data["ok"] = False
        data["write_errors"] = errors
    return data


def plan(
    *,
    routes: list[dict[str, Any]],
    paths: dict[str, Any],
    latest_path: Path,
    daily_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    now_time: dt.datetime | None = None,
    stop_at: Path | None = None,
    write_latest: bool = True,
    latest_history_writer: LatestHistoryWriterPort = default_latest_history_writer,
    symlink_tail: SymlinkTailPort = path_has_symlink_tail,
) -> dict[str, Any]:
    files, route_errors = collect_file_candidates(
        routes,
        now_time=now_time,
        stop_at=stop_at,
        symlink_tail=symlink_tail,
    )
    data = nervous_retention.plan_document(
        routes=routes,
        files=files,
        route_errors=route_errors,
        paths=paths,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest:
        data = write_latest_history(
            data,
            latest_path=latest_path,
            daily_root=daily_root,
            writer=latest_history_writer,
        )
    return data


def _candidate_path(item: Mapping[str, Any]) -> Path | None:
    raw = item.get("path")
    if raw is None:
        return None
    path = Path(str(raw))
    if not str(path):
        return None
    return path


def apply(
    *,
    plan_document: Mapping[str, Any],
    dry_run: bool,
    confirm: bool,
    paths: dict[str, Any],
    latest_path: Path,
    daily_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest: bool = True,
    unlink: UnlinkPort | None = None,
    latest_history_writer: LatestHistoryWriterPort = default_latest_history_writer,
) -> dict[str, Any]:
    unlink = unlink or (lambda path: path.unlink())
    candidates = [
        item
        for item in plan_document.get("candidates", [])
        if isinstance(item, dict) and item.get("candidate")
    ]
    should_apply = bool(plan_document.get("ok")) and bool(confirm) and not dry_run
    removed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if confirm and not dry_run and not plan_document.get("ok"):
        errors.append({"error": "plan_not_ok", "reason": "retention plan has route errors or failed checks"})
    for item in candidates:
        path = _candidate_path(item)
        if path is None:
            errors.append({"layer": item.get("layer"), "error": "missing_candidate_path"})
            continue
        if item.get("protected"):
            errors.append({"path": str(path), "layer": item.get("layer"), "error": "protected_candidate_refused"})
            continue
        if not should_apply:
            continue
        try:
            unlink(path)
            removed.append(
                {
                    "path": str(path),
                    "size_bytes": item.get("size_bytes"),
                    "layer": item.get("layer"),
                    "restore_hint": "restore from operator backup or regenerate through the source route; public repo does not contain private artifacts",
                }
            )
        except OSError as exc:
            errors.append({"path": str(path), "layer": item.get("layer"), "error": str(exc)})
    data = nervous_retention.apply_document(
        plan=plan_document,
        dry_run=dry_run,
        confirm=confirm,
        removed=removed,
        errors=errors,
        paths=paths,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest:
        data = write_latest_history(
            data,
            latest_path=latest_path,
            daily_root=daily_root,
            writer=latest_history_writer,
        )
    return data


def default_latest_reader(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return (data if isinstance(data, dict) else None), None if isinstance(data, dict) else "non-object JSON"
    except OSError as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, str(exc)


def validate(
    *,
    plan_document: Mapping[str, Any],
    latest_path: Path,
    validate_latest_path: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
    write_latest: bool = True,
    latest_reader: LatestJsonReaderPort = default_latest_reader,
    latest_writer: LatestJsonWriterPort = typing_nervous_adapters.safe_atomic_write_json,
) -> dict[str, Any]:
    latest, latest_error = latest_reader(latest_path)
    data = nervous_retention.validate_document(
        plan=plan_document,
        latest_exists=isinstance(latest, dict),
        latest_path=str(latest_path),
        latest_error=latest_error,
        validate_latest_path=str(validate_latest_path),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_latest:
        error = latest_writer(validate_latest_path, data, 0o664)
        if error:
            data["ok"] = False
            data["write_errors"] = [error]
    return data
