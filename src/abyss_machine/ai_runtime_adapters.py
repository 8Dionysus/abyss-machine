from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from . import ai_runtime_contracts


RunPort = Callable[..., Mapping[str, Any]]
CommandExistsPort = Callable[[str], bool]
WhichPort = Callable[[str], str | None]
PathExistsPort = Callable[[Path], bool]
PathAccessPort = Callable[[Path, int], bool]
ResourceSnapshotPort = Callable[[], Mapping[str, Any]]
ResourceProfilePort = Callable[[dict[str, Any], dict[str, Any], str, str], dict[str, Any]]
SystemdUnitPort = Callable[[str], Mapping[str, Any]]
StorageProtectionPort = Callable[[Path], Mapping[str, Any]]
RelativeToPort = Callable[[Path, Path], bool]
WalkPort = Callable[[Path], Iterable[tuple[str, list[str], list[str]]]]


OPENVINO_RUNTIME_QUERY_SCRIPT = r'''
import json
try:
    import openvino as ov
    core = ov.Core()
    info = {
        "ok": True,
        "openvino_version": getattr(ov, "__version__", None),
        "available_devices": list(core.available_devices),
        "device_properties": {},
    }
    for device in core.available_devices:
        props = {}
        for key in ("FULL_DEVICE_NAME", "DEVICE_TYPE", "OPTIMIZATION_CAPABILITIES"):
            try:
                props[key] = core.get_property(device, key)
            except Exception as exc:
                props[key] = {"error": str(exc)}
        info["device_properties"][device] = props
except Exception as exc:
    info = {"ok": False, "error": repr(exc)}
print(json.dumps(info, default=str, sort_keys=False))
'''


PYTHON_RUNTIME_VERSION_SCRIPT = r'''
import json
import importlib.metadata as metadata
packages = ["openvino", "openvino-genai", "optimum-intel", "transformers", "numpy", "torch", "huggingface-hub", "qwen-tts", "babelvox", "soundfile", "librosa"]
versions = {}
for package in packages:
    try:
        versions[package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        versions[package] = None
print(json.dumps({"ok": True, "packages": versions}, sort_keys=False))
'''


def default_walk(root: Path) -> Iterable[tuple[str, list[str], list[str]]]:
    return os.walk(root)


def _path_exists(path: Path, path_exists: PathExistsPort) -> bool:
    try:
        return bool(path_exists(path))
    except OSError:
        return False


def _path_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _python_exists(python: str | None, path_exists: PathExistsPort) -> bool:
    if not python:
        return False
    return _path_exists(Path(str(python)), path_exists)


def model_roots(config: Mapping[str, Any]) -> list[Path]:
    roots: list[Path] = []
    raw_roots = config.get("model_roots", []) if isinstance(config, Mapping) else []
    for raw in raw_roots if isinstance(raw_roots, list) else []:
        if raw is None:
            continue
        try:
            path = Path(str(raw)).expanduser()
        except TypeError:
            continue
        if path not in roots:
            roots.append(path)
    return roots


def openvino_runtime_info(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_command: RunPort,
    which: WhichPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    openvino_config = config.get("openvino", {}) if isinstance(config.get("openvino"), Mapping) else {}
    python = which("abyss-openvino-python") or str(openvino_config.get("python", ""))
    if not python or not _path_exists(Path(python), path_exists):
        return {
            "schema": f"{schema_prefix}_ai_openvino_runtime_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "python": python or None,
            "error": "abyss-openvino-python not found",
        }

    out = dict(run_command([python, "-c", OPENVINO_RUNTIME_QUERY_SCRIPT], timeout=12.0))
    data = ai_runtime_contracts.parse_json_stdout(str(out.get("stdout") or ""))
    if data is None:
        return {
            "schema": f"{schema_prefix}_ai_openvino_runtime_v1",
            "version": version,
            "generated_at": generated_at,
            "ok": False,
            "python": python,
            "error": "OpenVINO query returned invalid JSON",
            "returncode": out.get("returncode"),
            "stderr": str(out.get("stderr") or "")[-1000:],
            "stdout_tail": str(out.get("stdout") or "")[-1000:],
        }
    data.setdefault("schema", f"{schema_prefix}_ai_openvino_runtime_v1")
    data["version"] = version
    data["generated_at"] = generated_at
    data["python"] = python
    data["returncode"] = out.get("returncode")
    data["stderr"] = out.get("stderr")
    return data


def openvino_smoke_device(
    *,
    device: str,
    timeout_sec: float,
    python: str | None,
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.openvino_smoke_missing_python(device)

    before = dict(resource_snapshot())
    out = dict(run_command(ai_runtime_contracts.openvino_smoke_command(str(python), device), timeout=timeout_sec))
    after = dict(resource_snapshot())
    return ai_runtime_contracts.openvino_smoke_result(
        device,
        out,
        resource_profile(before, after, "child_process", "OpenVINO smoke subprocess"),
    )


def openvino_embedding_eval(
    *,
    model_dir: Path,
    device: str,
    cache_dir: Path,
    timeout_sec: float,
    python: str | None,
    subprocess_env: Mapping[str, str],
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _path_exists(model_dir, path_exists):
        return ai_runtime_contracts.embedding_eval_missing_model(model_dir)
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.embedding_eval_missing_python()

    before = dict(resource_snapshot())
    out = dict(
        run_command(
            ai_runtime_contracts.embedding_eval_command(str(python), model_dir, device, cache_dir),
            timeout=timeout_sec,
            env=dict(subprocess_env),
        )
    )
    after = dict(resource_snapshot())
    return ai_runtime_contracts.embedding_eval_result(
        out,
        resource_profile(before, after, "child_process", "embedding eval subprocess"),
    )


def openvino_text_eval(
    *,
    model_dir: Path,
    device: str,
    cache_dir: Path,
    prompt: str,
    timeout_sec: float,
    python: str | None,
    subprocess_env: Mapping[str, str],
    run_command: RunPort,
    resource_snapshot: ResourceSnapshotPort,
    resource_profile: ResourceProfilePort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    if not _path_exists(model_dir, path_exists):
        return ai_runtime_contracts.text_eval_missing_model(model_dir)
    if not _python_exists(python, path_exists):
        return ai_runtime_contracts.text_eval_missing_python()

    before = dict(resource_snapshot())
    out = dict(
        run_command(
            ai_runtime_contracts.text_eval_command(str(python), model_dir, device, cache_dir, prompt),
            timeout=timeout_sec,
            env=dict(subprocess_env),
        )
    )
    after = dict(resource_snapshot())
    return ai_runtime_contracts.text_eval_result(
        out,
        resource_profile(before, after, "child_process", "OpenVINO GenAI text eval subprocess"),
    )


def rpm_package_status(
    names: list[str],
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    result: dict[str, Any] = {"rpm_available": command_exists("rpm"), "packages": {}}
    if not result["rpm_available"]:
        return result
    for name in names:
        out = dict(run_command(["rpm", "-q", name], timeout=3.0))
        result["packages"][name] = {
            "installed": bool(out.get("ok")),
            "query": out.get("stdout") or out.get("stderr"),
        }
    return result


def ldconfig_libraries(
    patterns: list[str],
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    result: dict[str, Any] = {"ldconfig_available": command_exists("ldconfig"), "matches": []}
    if not result["ldconfig_available"]:
        return result
    out = dict(run_command(["ldconfig", "-p"], timeout=3.0))
    result["ok"] = bool(out.get("ok"))
    if not out.get("ok"):
        result["error"] = out.get("stderr")
        return result
    lowered_patterns = [item.lower() for item in patterns]
    for line in str(out.get("stdout") or "").splitlines():
        lowered = line.lower()
        if any(pattern in lowered for pattern in lowered_patterns):
            result["matches"].append(line.strip())
    return result


def npu_user_driver_status(
    *,
    root: Path = Path("/opt/intel/linux-npu-driver"),
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    exists = _path_exists(root, path_exists)
    versions: list[str] = []
    error = None
    if exists:
        try:
            versions = sorted(item.name for item in root.iterdir())
        except OSError as exc:
            error = str(exc)
    data = {
        "root": str(root),
        "exists": exists,
        "versions": versions,
        "preferred_version": versions[-1] if versions else None,
    }
    if error:
        data["error"] = error
    return data


def devices_status(
    *,
    device_nodes: Mapping[str, Any],
    paths: Mapping[str, Any],
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    run_command: RunPort,
    command_exists: CommandExistsPort,
    which: WhichPort,
    user_systemd_unit: SystemdUnitPort,
    path_exists: PathExistsPort | None = None,
    npu_driver_root: Path = Path("/opt/intel/linux-npu-driver"),
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    runtime = openvino_runtime_info(
        config=config,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
        run_command=run_command,
        which=which,
        path_exists=path_exists,
    )
    available = runtime.get("available_devices") if isinstance(runtime.get("available_devices"), list) else []
    packages = rpm_package_status(
        [
            "intel-openvino-runtime",
            "intel-level-zero-gpu",
            "intel-npu-driver",
            "level-zero",
            "level-zero-devel",
        ],
        command_exists=command_exists,
        run_command=run_command,
    )
    return {
        "schema": f"{schema_prefix}_ai_devices_v1",
        "version": version,
        "generated_at": generated_at,
        "paths": dict(paths),
        "device_nodes": dict(device_nodes),
        "openvino": runtime,
        "packages": packages,
        "ldconfig": ldconfig_libraries(["npu", "level_zero", "ze_intel_gpu"], command_exists=command_exists, run_command=run_command),
        "npu_user_driver": npu_user_driver_status(root=npu_driver_root, path_exists=path_exists),
        "dictation_server": dict(user_systemd_unit("abyss-dictation-server.service")),
        "ready": {
            "openvino": bool(runtime.get("ok")),
            "cpu": "CPU" in available,
            "gpu": "GPU" in available and bool(device_nodes.get("dev_dri_present")),
            "npu": "NPU" in available and bool(device_nodes.get("dev_accel_present")),
        },
    }


def immediate_file_summary(path: Path, max_files: int = 1000) -> dict[str, Any]:
    files = 0
    size = 0
    extensions: dict[str, int] = {}
    truncated = False
    try:
        for item in path.iterdir():
            if not item.is_file():
                continue
            files += 1
            suffix = item.suffix.lower() or "[none]"
            extensions[suffix] = extensions.get(suffix, 0) + 1
            item_size = _path_size(item)
            if item_size is not None:
                size += item_size
            if files >= max_files:
                truncated = True
                break
    except OSError as exc:
        return {"error": str(exc)}
    return {
        "immediate_files": files,
        "immediate_file_bytes": size,
        "extensions": dict(sorted(extensions.items())),
        "truncated": truncated,
    }


def classify_model_dir(path: Path, root: Path, filenames: list[str]) -> dict[str, Any] | None:
    return ai_runtime_contracts.classify_model_dir(path, root, filenames, immediate_file_summary(path))


def models_inventory(
    *,
    config: Mapping[str, Any],
    schema_prefix: str,
    version: str,
    generated_at: str,
    path_exists: PathExistsPort | None = None,
    walk: WalkPort = default_walk,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    inventory = config.get("inventory", {}) if isinstance(config.get("inventory"), Mapping) else {}
    max_depth = int(inventory.get("max_depth", 9))
    max_entries = int(inventory.get("max_entries", 300))
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"}
    entries: list[dict[str, Any]] = []
    root_status: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    truncated = False

    for root in model_roots(config):
        status = {"path": str(root), "exists": _path_exists(root, path_exists), "entries_seen": 0}
        root_status.append(status)
        if not status["exists"]:
            continue
        try:
            for current, dirnames, filenames in walk(root):
                current_path = Path(current)
                try:
                    relative = current_path.relative_to(root)
                    depth = 0 if str(relative) == "." else len(relative.parts)
                except ValueError:
                    depth = 0
                if depth >= max_depth:
                    dirnames[:] = []
                else:
                    dirnames[:] = [name for name in dirnames if name not in skip_dirs]

                item = classify_model_dir(current_path, root, filenames)
                if item:
                    entries.append(item)
                    status["entries_seen"] = int(status["entries_seen"]) + 1

                for filename in sorted(filenames):
                    file_path = current_path / filename
                    file_entry = ai_runtime_contracts.model_file_entry(file_path, root, size_bytes=_path_size(file_path))
                    if not file_entry:
                        continue
                    entries.append(file_entry)
                    status["entries_seen"] = int(status["entries_seen"]) + 1

                if len(entries) >= max_entries:
                    truncated = True
                    break
        except OSError as exc:
            errors.append({"path": str(root), "error": str(exc)})
        if truncated:
            break

    return ai_runtime_contracts.build_models_inventory_document(
        entries=entries,
        roots=root_status,
        errors=errors,
        truncated=truncated,
        max_entries=max_entries,
        max_depth=max_depth,
        schema_prefix=schema_prefix,
        version=version,
        generated_at=generated_at,
    )


def llm_runtime_status(
    config: Mapping[str, Any],
    *,
    runtime_override: Mapping[str, Any] | None = None,
    run_command: RunPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    runtime = dict(runtime_override) if isinstance(runtime_override, Mapping) else config.get("runtime") if isinstance(config.get("runtime"), dict) else {}
    cli = Path(str(runtime.get("llama_cli") or ""))
    server = Path(str(runtime.get("llama_server") or ""))
    cli_exists = _path_exists(cli, path_exists)
    version_probe = None
    if cli_exists:
        version_probe = dict(run_command([str(cli), "--version"], timeout=5.0))
    return ai_runtime_contracts.llm_runtime_status(
        runtime,
        cli_exists=cli_exists,
        server_exists=_path_exists(server, path_exists),
        version_probe=version_probe,
    )


def llm_profile_status(
    *,
    family_name: str,
    profile_name: str,
    profile: Mapping[str, Any],
    runtime: Mapping[str, Any],
    cache_root: Path,
    storage_protection: StorageProtectionPort,
    is_relative_to_path: RelativeToPort,
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    local_path = Path(str(profile.get("local_path") or ""))
    mmproj_raw = str(profile.get("mmproj_path") or "")
    mmproj_path = Path(mmproj_raw) if mmproj_raw else None
    exists = _path_exists(local_path, path_exists)
    mmproj_exists = bool(mmproj_path and _path_exists(mmproj_path, path_exists))
    protection = (
        dict(storage_protection(local_path))
        if str(local_path).startswith("/")
        else {"decision": "deny", "reason": "profile local path is not absolute"}
    )
    return ai_runtime_contracts.llm_profile_status(
        family_name=family_name,
        profile_name=profile_name,
        profile=dict(profile),
        runtime=dict(runtime),
        local_path=local_path,
        local_exists=exists,
        local_size_bytes=_path_size(local_path) if exists else None,
        mmproj_path=mmproj_path,
        mmproj_exists=mmproj_exists,
        mmproj_size_bytes=_path_size(mmproj_path) if mmproj_path and mmproj_exists else None,
        storage_protection=protection,
        under_host_cache=is_relative_to_path(local_path, cache_root),
    )


def token_accounting_library_paths(
    tokenizer: Path,
    profile: Mapping[str, Any],
    *,
    path_exists: PathExistsPort | None = None,
) -> list[Path]:
    path_exists = path_exists or Path.exists
    paths: list[Path] = []
    seen: set[str] = set()
    for child in ai_runtime_contracts.token_accounting_library_candidates(tokenizer, dict(profile)):
        if _path_exists(child, path_exists):
            key = str(child)
            if key not in seen:
                seen.add(key)
                paths.append(child)
    return paths


def token_accounting_resolve_tokenizer(
    profile: Mapping[str, Any],
    *,
    path_exists: PathExistsPort | None = None,
    access: PathAccessPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    access = access or os.access
    candidates = ai_runtime_contracts.token_accounting_tokenizer_candidates(dict(profile))
    found = next((candidate for candidate in candidates if _path_exists(candidate, path_exists) and access(candidate, os.X_OK)), None)
    library_paths = token_accounting_library_paths(found, profile, path_exists=path_exists) if found else []
    return ai_runtime_contracts.token_accounting_tokenizer_resolution(
        tokenizer=found,
        candidate_paths=candidates,
        library_paths=library_paths,
    )


def python_runtime_versions(
    *,
    config: Mapping[str, Any],
    run_command: RunPort,
    which: WhichPort,
    subprocess_env: Mapping[str, str],
    path_exists: PathExistsPort | None = None,
) -> dict[str, Any]:
    path_exists = path_exists or Path.exists
    openvino_config = config.get("openvino", {}) if isinstance(config.get("openvino"), Mapping) else {}
    python = which("abyss-openvino-python") or str(openvino_config.get("python", ""))
    if not python or not _path_exists(Path(python), path_exists):
        return {"ok": False, "python": python or None, "error": "abyss-openvino-python not found"}
    out = dict(run_command([python, "-c", PYTHON_RUNTIME_VERSION_SCRIPT], timeout=10.0, env=dict(subprocess_env)))
    data = ai_runtime_contracts.parse_json_stdout(str(out.get("stdout") or ""))
    if data is None:
        data = {"ok": False, "error": "invalid package version JSON", "stderr": out.get("stderr")}
    data["python"] = python
    return data


def kernel_module_snapshot(
    *,
    command_exists: CommandExistsPort,
    run_command: RunPort,
) -> dict[str, Any]:
    modules = {}
    if command_exists("lsmod"):
        out = dict(run_command(["lsmod"], timeout=3.0))
        if out.get("ok"):
            interesting = {"i915", "xe", "intel_vpu", "intel_uncore", "drm_buddy", "drm_display_helper"}
            for line in str(out.get("stdout") or "").splitlines()[1:]:
                parts = line.split()
                if parts and parts[0] in interesting:
                    modules[parts[0]] = {"size": parts[1] if len(parts) > 1 else None, "used_by": parts[3:] if len(parts) > 3 else []}
    modinfo = {}
    if command_exists("modinfo"):
        for name in ("i915", "xe", "intel_vpu"):
            out = dict(run_command(["modinfo", name], timeout=3.0))
            modinfo[name] = {"ok": bool(out.get("ok")), "summary": "\n".join(str(out.get("stdout") or "").splitlines()[:20]) if out.get("ok") else out.get("stderr")}
    return {"loaded": modules, "modinfo": modinfo}
