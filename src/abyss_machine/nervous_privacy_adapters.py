from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from . import nervous_privacy
from . import typing_nervous_adapters


LoadJsonPort = Callable[[Path], tuple[dict[str, Any] | None, str | None]]
WriteJsonPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
AppendJsonlPort = Callable[[Path, dict[str, Any], int], dict[str, Any] | None]
TodayPathPort = Callable[[Path], Path]
PathExistsPort = Callable[[Path], bool]
NowIsoPort = Callable[[], str]
StateReaderPort = Callable[[], dict[str, Any]]
StateWriterPort = Callable[[Mapping[str, Any], str, str | None], dict[str, Any]]
AuditWriterPort = Callable[[dict[str, Any]], dict[str, Any]]


def path_exists(path: Path) -> bool:
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
    config_path: Path,
    defaults: Mapping[str, Any],
    *,
    generated_at: str,
    load_json: LoadJsonPort = typing_nervous_adapters.read_json_document,
) -> dict[str, Any]:
    loaded, error = load_json(config_path)
    if loaded is None:
        data = dict(defaults)
        if error != "missing":
            data["_load_error"] = error
        data["_config_exists"] = False
    else:
        data = _deep_merge(dict(defaults), loaded)
        data["_config_exists"] = True
    data["_config_path"] = str(config_path)
    data["generated_at"] = generated_at
    data["ok"] = data.get("_load_error") is None
    return data


def write_latest(
    data: Mapping[str, Any],
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


def audit_record_from_event(
    event: Mapping[str, Any],
    *,
    audit_root: Path,
    write_enabled: bool,
    schema_prefix: str,
    version: str,
    generated_at: str,
    jsonl_append: AppendJsonlPort = typing_nervous_adapters.safe_append_jsonl,
    today_path: TodayPathPort = typing_nervous_adapters.daily_jsonl_path,
    mode: int = 0o664,
) -> dict[str, Any]:
    record = nervous_privacy.audit_record(
        event,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )
    if write_enabled:
        error = jsonl_append(today_path(audit_root), record, mode)
        if error:
            record["write_errors"] = [error]
            record["ok"] = False
        else:
            record.setdefault("ok", True)
    return record


def state_document_from_path(
    state_path: Path,
    defaults: Mapping[str, Any],
    *,
    load_json: LoadJsonPort = typing_nervous_adapters.read_json_document,
    path_exists_port: PathExistsPort = path_exists,
) -> dict[str, Any]:
    loaded, error = load_json(state_path)
    return nervous_privacy.state_document(
        defaults=defaults,
        loaded=loaded,
        load_error=error,
        path=str(state_path),
        exists=path_exists_port(state_path),
    )


def save_state_document(
    state: Mapping[str, Any],
    state_path: Path,
    *,
    updated_by: str,
    reason: str | None,
    change_id: str,
    updated_at: str,
    schema_prefix: str,
    version: str,
    writer: WriteJsonPort = typing_nervous_adapters.safe_atomic_write_json,
    mode: int = 0o664,
) -> dict[str, Any]:
    clean = nervous_privacy.saved_state_document(
        state,
        updated_by=updated_by,
        reason=reason,
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


def effective_privacy_document(config: Mapping[str, Any], state: Mapping[str, Any], *, state_path: Path) -> dict[str, Any]:
    return nervous_privacy.effective_privacy(config, state, state_path=str(state_path))


def status_document_from_inputs(
    *,
    effective: Mapping[str, Any],
    config: Mapping[str, Any],
    config_path: Path,
    state_path: Path,
    audit_root: Path,
    schema_prefix: str,
    version: str,
    generated_at: str,
) -> dict[str, Any]:
    return nervous_privacy.status_document(
        effective=effective,
        config=config,
        config_path=str(config_path),
        state_path=str(state_path),
        audit_glob=str(audit_root / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def privacy_set_from_ports(
    target: str,
    enabled: bool,
    *,
    reason: str | None,
    state_reader: StateReaderPort,
    state_writer: StateWriterPort,
    audit_writer: AuditWriterPort,
    now_iso: NowIsoPort,
    schema_prefix: str,
    version: str,
) -> dict[str, Any]:
    generated_at = now_iso()
    if nervous_privacy.target_field(target) is None:
        return nervous_privacy.set_error(schema_prefix, version, generated_at)

    before = state_reader()
    transition = nervous_privacy.set_transition(
        target,
        enabled,
        before,
        active_since=generated_at,
    )
    if not transition.get("ok"):
        return nervous_privacy.set_error(schema_prefix, version, now_iso())

    saved = state_writer(
        transition["state"],
        f"privacy-set:{target}",
        reason or f"{target} {'on' if enabled else 'off'}",
    )
    if saved.get("ok") is False:
        return nervous_privacy.set_write_failed_result(
            target=target,
            field=str(transition["field"]),
            before=bool(transition["before"]),
            after=enabled,
            state=saved,
            schema_prefix=schema_prefix,
            version=version,
            generated_at=now_iso(),
        )

    audit = audit_writer(
        nervous_privacy.set_audit_event(
            change_id=saved.get("last_change_id"),
            target=target,
            field=str(transition["field"]),
            before=bool(transition["before"]),
            after=enabled,
            reason=reason,
        )
    )
    return nervous_privacy.set_result(
        target=target,
        field=str(transition["field"]),
        before=bool(transition["before"]),
        after=enabled,
        state=saved,
        audit=audit,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=now_iso(),
    )
