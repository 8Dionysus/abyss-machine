from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from . import nervous_sources
from . import typing_nervous_adapters


LoadJsonPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
PathExistsPort = Callable[[Path], bool]
WriteJsonPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
SourceLookupPort = Callable[[str], dict[str, Any] | None]
StateReaderPort = Callable[[], dict[str, Any]]
StateWriterPort = Callable[[dict[str, Any], str], dict[str, Any]]
AuditWriterPort = Callable[[dict[str, Any]], dict[str, Any]]
NowIsoPort = Callable[[], str]


def _path_exists(path: Path) -> bool:
    return path.exists()


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = value
    return result


def config_document_from_path(
    path: Path,
    defaults: dict[str, Any],
    *,
    generated_at: str,
    load_json: LoadJsonPort = typing_nervous_adapters.read_json_document,
) -> dict[str, Any]:
    loaded, error = load_json(path)
    if loaded is None:
        data = dict(defaults)
        if error != "missing":
            data["_load_error"] = error
        data["_config_exists"] = False
    else:
        data = _deep_merge(dict(defaults), loaded)
        data["_config_exists"] = True
    data["_config_path"] = str(path)
    data["generated_at"] = generated_at
    data["ok"] = data.get("_load_error") is None
    return data


def write_latest(
    data: dict[str, Any],
    latest_path: Path,
    *,
    writer: WriteJsonPort = typing_nervous_adapters.safe_atomic_write_json,
    mode: int = 0o664,
) -> dict[str, Any]:
    result = dict(data)
    error = writer(latest_path, result, mode)
    if error:
        result["write_errors"] = [error]
        result["ok"] = False
    return result


def state_document_from_path(
    state_path: Path,
    defaults: Mapping[str, Any],
    *,
    load_json: LoadJsonPort = typing_nervous_adapters.read_json_document,
    path_exists: PathExistsPort = _path_exists,
) -> dict[str, Any]:
    loaded, error = load_json(state_path)
    return nervous_sources.state_document(
        defaults=defaults,
        loaded=loaded,
        load_error=error,
        path=str(state_path),
        exists=path_exists(state_path),
    )


def save_state_document(
    state: Mapping[str, Any],
    state_path: Path,
    *,
    updated_by: str,
    change_id: str,
    updated_at: str,
    schema_prefix: str,
    version: str,
    writer: WriteJsonPort = typing_nervous_adapters.safe_atomic_write_json,
    mode: int = 0o664,
) -> dict[str, Any]:
    clean = nervous_sources.saved_state_document(
        state,
        updated_by=updated_by,
        change_id=change_id,
        updated_at=updated_at,
        schema_prefix=schema_prefix,
        version=version,
    )
    error = writer(state_path, clean, mode)
    if error:
        clean["write_errors"] = [error]
        clean["ok"] = False
    return clean


def source_set_from_ports(
    source_id: str,
    enabled: bool,
    *,
    reason: str | None,
    source_lookup: SourceLookupPort,
    state_reader: StateReaderPort,
    state_writer: StateWriterPort,
    audit_writer: AuditWriterPort,
    effective_lookup: SourceLookupPort,
    now_iso: NowIsoPort,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    item = source_lookup(source_id)
    generated_at = now_iso()
    if item is None:
        return nervous_sources.source_set_unknown_result(
            source_id,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )
    if enabled and not item.get("can_enable_now"):
        return nervous_sources.source_set_blocked_result(
            source_id,
            item,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=generated_at,
        )

    transition = nervous_sources.source_set_transition(
        source_id=source_id,
        enabled=enabled,
        source_status=item,
        state=state_reader(),
        updated_at=generated_at,
        reason=reason,
    )
    saved = state_writer(transition["state"], f"source-{'enable' if enabled else 'disable'}:{source_id}")
    audit = audit_writer(
        nervous_sources.source_set_audit_event(
            change_id=saved.get("last_change_id"),
            source_id=source_id,
            before=bool(transition["before"]),
            after=enabled,
            reason=reason,
        )
    )
    return nervous_sources.source_set_result(
        source_id=source_id,
        before=bool(transition["before"]),
        after=enabled,
        state=saved,
        audit=audit,
        effective=effective_lookup(source_id),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
    )
