from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Sequence

from . import storage_candidate_contracts as contracts
from . import storage_contracts


CommandRunner = Callable[[Sequence[str], float], Mapping[str, Any]]
Clock = Callable[[], dt.datetime]


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def run_command(command: Sequence[str], timeout: float) -> dict[str, Any]:
    try:
        process = subprocess.run(
            list(command),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "ok": process.returncode == 0,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def physical_size_bytes(
    path: Path,
    *,
    timeout: float = 120.0,
    runner: CommandRunner = run_command,
) -> tuple[int | None, dict[str, Any]]:
    if not path.exists() and not path.is_symlink():
        return None, {"checked": True, "ok": False, "error": "path_missing", "method": "du -sx -B1"}
    result = runner(["du", "-sx", "-B1", "--", str(path)], timeout)
    if result.get("ok"):
        first = str(result.get("stdout") or "").strip().splitlines()
        if first:
            token = first[0].split(maxsplit=1)[0]
            try:
                return int(token), {"checked": True, "ok": True, "method": "du -sx -B1", "physical": True}
            except ValueError:
                pass
    return None, {
        "checked": True,
        "ok": False,
        "method": "du -sx -B1",
        "physical": True,
        "error": str(result.get("stderr") or result.get("stdout") or "invalid_du_output").strip()[:1000],
    }


def _fingerprint_row(path: Path, stat_result: os.stat_result, relative: str) -> bytes:
    kind = "l" if path.is_symlink() else ("d" if path.is_dir() else "f")
    payload = (
        relative,
        kind,
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_result.st_mode),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        int(stat_result.st_ctime_ns),
    )
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8", errors="replace")


def filesystem_fingerprint(path: Path, *, max_entries: int = 20_000) -> dict[str, Any]:
    digest = hashlib.sha256()
    errors: list[dict[str, str]] = []
    entries = 0
    files = 0
    directories = 0
    symlinks = 0
    latest_mtime_ns = 0
    truncated = False
    root_device: int | None = None

    try:
        root_stat = path.lstat()
    except OSError as exc:
        return {
            "digest": None,
            "complete": False,
            "entries": 0,
            "errors": [{"path": str(path), "error": str(exc)}],
            "reason": "root_stat_failed",
        }
    root_device = int(root_stat.st_dev)

    def include(item: Path, relative: str) -> bool:
        nonlocal entries, files, directories, symlinks, latest_mtime_ns, truncated
        if entries >= max(1, int(max_entries)):
            truncated = True
            return False
        try:
            stat_result = item.lstat()
        except OSError as exc:
            errors.append({"path": str(item), "error": str(exc)})
            return True
        if int(stat_result.st_dev) != root_device:
            errors.append({"path": str(item), "error": "cross_device_entry_skipped"})
            return True
        digest.update(_fingerprint_row(item, stat_result, relative))
        entries += 1
        latest_mtime_ns = max(latest_mtime_ns, int(stat_result.st_mtime_ns))
        if item.is_symlink():
            symlinks += 1
        elif item.is_dir():
            directories += 1
        else:
            files += 1
        return True

    include(path, ".")
    if path.is_dir() and not path.is_symlink() and not truncated:
        for current, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            current_path = Path(current)
            dirnames.sort()
            filenames.sort()
            allowed_dirs: list[str] = []
            for name in dirnames:
                child = current_path / name
                try:
                    relative = str(child.relative_to(path))
                except ValueError:
                    errors.append({"path": str(child), "error": "outside_root"})
                    continue
                if not include(child, relative):
                    break
                try:
                    if child.is_symlink() or child.lstat().st_dev != root_device:
                        continue
                except OSError:
                    continue
                allowed_dirs.append(name)
            dirnames[:] = allowed_dirs
            if truncated:
                break
            for name in filenames:
                child = current_path / name
                try:
                    relative = str(child.relative_to(path))
                except ValueError:
                    errors.append({"path": str(child), "error": "outside_root"})
                    continue
                if not include(child, relative):
                    break
            if truncated:
                break
    latest_mtime = None
    if latest_mtime_ns:
        latest_mtime = dt.datetime.fromtimestamp(latest_mtime_ns / 1_000_000_000, dt.timezone.utc).isoformat()
    return {
        "digest": digest.hexdigest(),
        "complete": not errors and not truncated,
        "bounded": True,
        "max_entries": max_entries,
        "truncated": truncated,
        "entries": entries,
        "files": files,
        "directories": directories,
        "symlinks": symlinks,
        "device": root_device,
        "latest_mtime": latest_mtime,
        "errors": errors[:20],
    }


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "non_object_json"
    return value, None


def atomic_write_json(path: Path, document: Mapping[str, Any], mode: int = 0o664) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
        temporary = Path(handle.name)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def load_json_records(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        document, _error = load_json(path)
        if document is not None:
            records.append(document)
    return records


def write_manifest(root: Path, manifest: Mapping[str, Any]) -> Path:
    candidate_id = str(manifest.get("candidate_id") or "")
    if not candidate_id or manifest.get("valid") is not True:
        raise ValueError("valid candidate manifest required")
    path = root / f"{candidate_id}.json"
    atomic_write_json(path, manifest)
    return path


def write_claim(root: Path, claim: Mapping[str, Any]) -> Path:
    claim_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(claim.get("claim_id") or "")).strip("-")
    if not claim_id or claim.get("valid") is not True:
        raise ValueError("valid storage candidate claim required")
    path = root / f"{claim_id}.json"
    atomic_write_json(path, claim)
    return path


def release_claim(root: Path, claim_id: str, *, released_at: str) -> tuple[Path | None, str | None]:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", claim_id).strip("-")
    path = root / f"{safe_id}.json"
    document, error = load_json(path)
    if document is None:
        return None, error or "claim_not_found"
    document["released_at"] = released_at
    document["expires_at"] = released_at
    document["active"] = False
    atomic_write_json(path, document)
    return path, None


def mount_references(path: Path, *, mountinfo_path: Path = Path("/proc/self/mountinfo")) -> dict[str, Any]:
    refs: list[dict[str, str]] = []
    errors: list[str] = []
    try:
        lines = mountinfo_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"checked": False, "active": False, "refs": [], "errors": [str(exc)]}
    candidate = str(path)
    for line in lines:
        parts = line.split()
        try:
            separator = parts.index("-")
        except ValueError:
            continue
        if len(parts) < 6 or separator + 2 >= len(parts):
            continue
        mountpoint = parts[4].replace("\\040", " ")
        source = parts[separator + 2].replace("\\040", " ")
        if mountpoint == candidate or mountpoint.startswith(candidate.rstrip("/") + "/") or source == candidate or source.startswith(candidate.rstrip("/") + "/"):
            refs.append({"mountpoint": mountpoint, "source": source, "filesystem": parts[separator + 1]})
    return {"checked": True, "active": bool(refs), "refs": refs, "errors": errors}


def json_path_references(path: str, documents: Sequence[tuple[str, Mapping[str, Any]]]) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []

    def walk(value: Any, location: str, source: str) -> None:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                walk(nested, f"{location}.{key}" if location else str(key), source)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, nested in enumerate(value):
                walk(nested, f"{location}[{index}]", source)
        elif isinstance(value, str) and (value == path or value.startswith(path.rstrip("/") + "/")):
            hits.append({"source": source, "location": location, "value": value})

    for source, document in documents:
        walk(document, "", source)
    return {"checked": True, "active": bool(hits), "matches": hits[:100], "match_count": len(hits)}


def _target_matches_candidate(target: str, candidate: str) -> bool:
    if not target or not candidate or target.startswith("podman://"):
        return False
    clean_target = target.removesuffix(" (deleted)")
    candidate_root = candidate.rstrip("/") or "/"
    return clean_target == candidate_root or clean_target.startswith(candidate_root.rstrip("/") + "/")


def process_references(
    paths: Sequence[str],
    *,
    proc_root: Path = Path("/proc"),
    max_refs_per_path: int = 100,
) -> dict[str, dict[str, Any]]:
    """Scan every accessible PID once and map exact path ancestry references."""
    selected = sorted({str(Path(path)) for path in paths if path and not str(path).startswith("podman://")})
    result = {
        path: {"checked": True, "active": False, "refs": [], "errors": [], "pids_scanned": 0}
        for path in selected
    }
    global_errors: list[str] = []
    try:
        pid_dirs = [item for item in proc_root.iterdir() if item.name.isdigit() and item.is_dir()]
    except OSError as exc:
        return {
            path: {"checked": False, "active": False, "refs": [], "errors": [str(exc)], "pids_scanned": 0}
            for path in selected
        }
    for pid_dir in pid_dirs:
        pid = int(pid_dir.name)
        targets: list[tuple[str, str]] = []
        for label in ("cwd", "root", "exe"):
            try:
                targets.append((label, os.readlink(pid_dir / label)))
            except FileNotFoundError:
                pass
            except (OSError, PermissionError) as exc:
                global_errors.append(f"pid={pid} {label}: {exc}")
        try:
            for fd in (pid_dir / "fd").iterdir():
                try:
                    targets.append((f"fd:{fd.name}", os.readlink(fd)))
                except FileNotFoundError:
                    continue
                except (OSError, PermissionError) as exc:
                    global_errors.append(f"pid={pid} fd={fd.name}: {exc}")
        except FileNotFoundError:
            pass
        except (OSError, PermissionError) as exc:
            global_errors.append(f"pid={pid} fd-dir: {exc}")
        try:
            for line in (pid_dir / "maps").read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and fields[5].startswith("/"):
                    targets.append(("maps", fields[5]))
        except FileNotFoundError:
            pass
        except (OSError, PermissionError) as exc:
            global_errors.append(f"pid={pid} maps: {exc}")
        try:
            cmdline = (pid_dir / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()[:1000]
        except OSError:
            cmdline = ""
        for candidate in selected:
            item = result[candidate]
            item["pids_scanned"] += 1
            refs = item["refs"]
            for source, target in targets:
                if _target_matches_candidate(target, candidate) and len(refs) < max_refs_per_path:
                    reference = {"pid": pid, "source": source, "target": target, "cmdline": cmdline}
                    if reference not in refs:
                        refs.append(reference)
    for item in result.values():
        item["active"] = bool(item["refs"])
        if global_errors:
            item["checked"] = False
            item["error_count"] = len(global_errors)
            item["errors"] = global_errors[:3]
    return result


def _path_is_under(path: Path, root: Path) -> bool:
    return storage_contracts.is_relative_to_path(path, root)


def direct_child_specs(root: Path, *, owner: str, kind: str, source_adapter: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError:
        return []
    return [
        {
            "path": str(child),
            "owner": owner,
            "kind": kind,
            "source_id": f"{source_adapter}:{child.name}",
            "source_adapter": source_adapter,
            "executor": {
                "type": contracts.EXECUTORS_BY_KIND.get(kind),
                "owner_specific": contracts.EXECUTORS_BY_KIND.get(kind) is not None,
            },
            "unique_data": {"status": "unknown", "reasons": ["no creation manifest or owner verdict"]},
            "recovery": {"verified": False, "command": None},
            "replacement": {"verified": False},
        }
        for child in children
        if child.name not in {"AGENTS.md", "DESIGN.md"} and not child.is_symlink()
    ]


def runtime_specs(root: Path) -> list[dict[str, Any]]:
    specs = direct_child_specs(root, owner="abyss-machine:runtimes", kind="runtime", source_adapter="runtime_children")
    failed_markers = ("failed", "aborted", "incomplete", "broken-build", "build-failure")
    for spec in specs:
        name = Path(str(spec.get("path") or "")).name.lower()
        if any(marker in name for marker in failed_markers):
            spec["kind"] = "failed_runtime"
            spec["executor"] = {
                "type": "runtime_retire_preserve_receipts",
                "owner_specific": True,
                "preserve": ["creation manifest", "build receipt", "failure diagnostics"],
            }
            spec["unique_data"] = {
                "status": "unknown",
                "archivable": True,
                "reasons": ["failed-name signal is discovery only; preservation and replacement still require owner evidence"],
            }
    return specs


def manifest_specs(manifests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for manifest in manifests:
        if manifest.get("valid") is not True or not manifest.get("path"):
            continue
        recovery = manifest.get("recovery") if isinstance(manifest.get("recovery"), Mapping) else {}
        replacement = manifest.get("replacement") if isinstance(manifest.get("replacement"), Mapping) else {}
        executor = manifest.get("executor") if isinstance(manifest.get("executor"), Mapping) else {}
        specs.append({
            "candidate_id": manifest.get("candidate_id"),
            "path": str(manifest.get("path")),
            "owner": str(manifest.get("owner") or "unknown"),
            "kind": str(manifest.get("kind") or "unknown"),
            "source_id": str(manifest.get("source_id") or manifest.get("candidate_id") or "manifest"),
            "source_adapter": "creation_manifest",
            "retention_until": manifest.get("retention_until"),
            "manifest": dict(manifest),
            "executor": dict(executor),
            "unique_data": {
                "status": "clear" if manifest.get("unique_data_clear") is True else "unknown",
                "reasons": manifest.get("preserved_refs") or ["manifest does not prove unique-data clearance"],
                "archivable": manifest.get("archivable") is True,
            },
            "recovery": {
                "verified": recovery.get("verified") is True,
                "command": recovery.get("command"),
                "declared": recovery.get("declared") is True,
            },
            "replacement": {
                "verified": replacement.get("verified") is True,
                "ref": replacement.get("ref"),
                "declared": replacement.get("declared") is True,
            },
            "archive": manifest.get("archive") if isinstance(manifest.get("archive"), Mapping) else {},
        })
    return specs


def artifact_specs(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    records = snapshot.get("records") if isinstance(snapshot.get("records"), list) else []
    for record in records:
        if not isinstance(record, Mapping) or not record.get("path"):
            continue
        kind_raw = str(record.get("kind") or "model-cache")
        kind = "openvino_cache" if "openvino" in kind_raw else "model_cache"
        decision = record.get("decision") if isinstance(record.get("decision"), Mapping) else {}
        classification = str(record.get("classification") or decision.get("classification") or "unknown")
        active = classification == "active-route"
        regenerable = classification == "regenerable"
        probe = record.get("workload_probe") or record.get("source_route")
        specs.append({
            "path": str(record.get("path")),
            "owner": str(record.get("owner_guess") or record.get("owner") or "abyss-machine:ai"),
            "kind": kind,
            "source_id": str(record.get("id") or record.get("path")),
            "source_adapter": "artifact_snapshot",
            "artifact_record": dict(record),
            "executor": {"type": "owner_cache_cleanup", "owner_specific": True},
            "unique_data": {
                "status": "clear" if regenerable else "unknown",
                "reasons": [f"artifact classification: {classification}"],
            },
            "recovery": {
                "verified": bool(regenerable and probe),
                "command": f"run owner workload probe and rebuild route: {probe}" if regenerable and probe else None,
            },
            "replacement": {"verified": False},
            "forced_active": active,
        })
    return specs


def huggingface_specs(cache_root: Path) -> list[dict[str, Any]]:
    hub = cache_root / "hub"
    if not hub.exists():
        return []
    specs: list[dict[str, Any]] = []
    for path in sorted(hub.glob("models--*")):
        if not path.is_dir() or path.is_symlink():
            continue
        encoded = path.name.removeprefix("models--")
        parts = encoded.split("--", 1)
        if len(parts) != 2 or not all(parts):
            recovery = {"verified": False, "command": None}
            unique = {"status": "unknown", "reasons": ["model repository identity could not be decoded"]}
        else:
            repo_id = "/".join(parts)
            recovery = {"verified": True, "command": f"hf download {shlex.quote(repo_id)}"}
            unexpected = [
                item.name
                for item in path.iterdir()
                if item.name not in {"blobs", "refs", "snapshots", ".no_exist"}
            ]
            unique = {
                "status": "clear" if not unexpected else "unknown",
                "reasons": ["canonical Hugging Face cache layout"] if not unexpected else [f"unexpected entries: {unexpected[:20]}"],
            }
        specs.append({
            "path": str(path),
            "owner": "abyss-machine:huggingface",
            "kind": "huggingface_model",
            "source_id": f"huggingface:{encoded}",
            "source_adapter": "huggingface_cache",
            "executor": {"type": "owner_cache_cleanup", "owner_specific": True},
            "unique_data": unique,
            "recovery": recovery,
            "replacement": {"verified": False},
        })
    return specs


def discover_git_roots(roots: Sequence[Path], *, max_depth: int = 7, max_repositories: int = 500) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            try:
                depth = len(current_path.relative_to(root).parts)
            except ValueError:
                continue
            if depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [name for name in dirnames if name not in {"node_modules", ".venv", "venv", "target", "dist", "build", "__pycache__"}]
            if ".git" in dirnames or ".git" in filenames:
                found.add(current_path)
                if len(found) >= max_repositories:
                    return sorted(found)
                if ".git" in dirnames:
                    dirnames.remove(".git")
    return sorted(found)


def _git(command: Sequence[str], *, cwd: Path, runner: CommandRunner, timeout: float = 15.0) -> dict[str, Any]:
    return dict(runner(["git", "-C", str(cwd), *command], timeout))


def git_worktree_evidence(path: Path, *, runner: CommandRunner = run_command) -> dict[str, Any]:
    status = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=path, runner=runner)
    head = _git(["rev-parse", "HEAD"], cwd=path, runner=runner)
    common = _git(["rev-parse", "--git-common-dir"], cwd=path, runner=runner)
    refs = _git(["for-each-ref", "--format=%(refname)", "--contains", "HEAD"], cwd=path, runner=runner)
    remote_refs = _git(["for-each-ref", "--format=%(refname)", "--contains", "HEAD", "refs/remotes"], cwd=path, runner=runner)
    errors = [
        str(result.get("stderr") or result.get("stdout") or "git command failed")[:1000]
        for result in (status, head, common, refs, remote_refs)
        if not result.get("ok")
    ]
    status_lines = [line for line in str(status.get("stdout") or "").splitlines() if line]
    ref_lines = [line for line in str(refs.get("stdout") or "").splitlines() if line]
    remote_lines = [line for line in str(remote_refs.get("stdout") or "").splitlines() if line]
    common_text = str(common.get("stdout") or "").strip()
    common_path = (path / common_text).resolve() if common_text and not Path(common_text).is_absolute() else Path(common_text or path / ".git")
    linked_worktree = (path / ".git").is_file() and not _path_is_under(common_path, path)
    unique_clear = bool(not status_lines and head.get("ok") and ref_lines and (linked_worktree or remote_lines))
    removal_command = f"git -C {shlex.quote(str(common_path.parent))} worktree remove -- {shlex.quote(str(path))}" if linked_worktree else None
    return {
        "checked": not errors,
        "errors": errors,
        "head": str(head.get("stdout") or "").strip() or None,
        "status_lines": status_lines[:200],
        "dirty": bool(status_lines),
        "containing_refs": ref_lines[:100],
        "remote_containing_refs": remote_lines[:100],
        "common_git_dir": str(common_path),
        "linked_worktree": linked_worktree,
        "worktree_registration_observed": linked_worktree,
        "unique_data": {
            "status": "clear" if unique_clear else ("present" if status_lines else "unknown"),
            "archivable": bool(status_lines),
            "reasons": status_lines[:100] or (["clean HEAD is retained by a Git ref outside the linked worktree"] if unique_clear else ["HEAD reachability or external Git authority is incomplete"]),
        },
        "recovery": {
            "verified": bool(linked_worktree and unique_clear and removal_command),
            "command": removal_command,
        },
        "executor": {
            "type": "git_worktree_remove",
            "owner_specific": linked_worktree,
            "command": removal_command,
        },
    }


def git_specs(roots: Sequence[Path], *, runner: CommandRunner = run_command) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for path in discover_git_roots(roots):
        evidence = git_worktree_evidence(path, runner=runner)
        specs.append({
            "path": str(path),
            "owner": "git",
            "kind": "git_worktree",
            "source_id": f"git:{evidence.get('common_git_dir')}:{path}",
            "source_adapter": "git_worktree",
            "executor": evidence["executor"],
            "unique_data": evidence["unique_data"],
            "recovery": evidence["recovery"],
            "replacement": {"verified": False},
            "git": evidence,
        })
    return specs


def parse_size(text: str) -> int | None:
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGTPE]?B)\s*", text, flags=re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).upper()
    factor = {"B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4, "PB": 1000**5, "EB": 1000**6}[unit]
    return int(value * factor)


def parse_podman_df_verbose(text: str) -> dict[str, list[dict[str, Any]]]:
    section: str | None = None
    records: dict[str, list[dict[str, Any]]] = {"images": [], "containers": [], "volumes": []}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line == "Images space usage:":
            section = "images"
            continue
        if line == "Containers space usage:":
            section = "containers"
            continue
        if line == "Local Volumes space usage:":
            section = "volumes"
            continue
        if not line or section is None:
            continue
        columns = re.split(r"\s{2,}", line.strip())
        if section == "images":
            if columns and columns[0] == "REPOSITORY":
                continue
            if len(columns) < 8:
                continue
            records[section].append({
                "repository": columns[0],
                "tag": columns[1],
                "id": columns[2],
                "created": columns[3],
                "size_bytes": parse_size(columns[4]),
                "shared_bytes": parse_size(columns[5]),
                "unique_bytes": parse_size(columns[6]),
                "containers": int(columns[7]) if columns[7].isdigit() else None,
            })
        elif section == "containers":
            if columns and columns[0] == "CONTAINER ID":
                continue
            if len(columns) < 8:
                continue
            records[section].append({
                "id": columns[0],
                "image": columns[1],
                "local_volumes": int(columns[-5]) if columns[-5].isdigit() else None,
                "size_bytes": parse_size(columns[-4]),
                "created": columns[-3],
                "status": columns[-2],
                "name": columns[-1],
            })
        elif section == "volumes":
            if columns and columns[0] == "VOLUME NAME":
                continue
            if len(columns) < 3:
                continue
            records[section].append({
                "name": columns[0],
                "links": int(columns[1]) if columns[1].isdigit() else None,
                "size_bytes": parse_size(columns[2]),
            })
    return records


def podman_specs(verbose_text: str) -> list[dict[str, Any]]:
    parsed = parse_podman_df_verbose(verbose_text)
    specs: list[dict[str, Any]] = []
    for image in parsed["images"]:
        image_id = str(image.get("id") or "")
        if not image_id:
            continue
        containers = image.get("containers")
        tagged = image.get("repository") not in {None, "", "<none>"} and image.get("tag") not in {None, "", "<none>"}
        recovery_command = None
        if tagged:
            recovery_command = f"podman pull {shlex.quote(str(image['repository']))}:{shlex.quote(str(image['tag']))}"
        unique_bytes = image.get("unique_bytes")
        specs.append({
            "path": f"podman://image/{image_id}",
            "owner": "podman",
            "kind": "podman_image",
            "source_id": f"podman-image:{image_id}",
            "source_adapter": "podman",
            "virtual": True,
            "physical_bytes": image.get("size_bytes"),
            "reclaimable_bytes": unique_bytes,
            "virtual_fingerprint": image,
            "executor": {"type": "podman_image_remove", "owner_specific": True, "argv": ["podman", "image", "rm", image_id]},
            "unique_data": {
                "status": "clear" if containers == 0 and tagged else "unknown",
                "reasons": [f"containers={containers}", f"tagged={tagged}", "Podman unique size used instead of total layer size"],
            },
            "recovery": {"verified": bool(recovery_command), "command": recovery_command},
            "replacement": {"verified": False},
            "podman": image,
            "forced_active": bool(containers and containers > 0),
        })
    for volume in parsed["volumes"]:
        name = str(volume.get("name") or "")
        if not name:
            continue
        size = volume.get("size_bytes")
        links = volume.get("links")
        specs.append({
            "path": f"podman://volume/{name}",
            "owner": "podman",
            "kind": "podman_volume",
            "source_id": f"podman-volume:{name}",
            "source_adapter": "podman",
            "virtual": True,
            "physical_bytes": size,
            "reclaimable_bytes": size if links == 0 else 0,
            "virtual_fingerprint": volume,
            "executor": {"type": "podman_volume_remove", "owner_specific": True, "argv": ["podman", "volume", "rm", name]},
            "unique_data": {
                "status": "unknown",
                "archivable": True,
                "reasons": ["unlinked Podman volume may still contain unique application data"],
            },
            "recovery": {"verified": False, "command": None},
            "replacement": {"verified": False},
            "podman": volume,
            "forced_active": bool(links and links > 0),
        })
    return specs


def aoa_specs(owner_document: Mapping[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    active_writer = str(owner_document.get("status") or "").startswith("deferred_active") or owner_document.get("lock_active") is True
    sections = ("graph_rebuild_temps", "search_rebuild_temps", "session_projection_stages")
    for section in sections:
        payload = owner_document.get(section) if isinstance(owner_document.get(section), Mapping) else {}
        entries = payload.get("entries") if isinstance(payload.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, Mapping) or not entry.get("path"):
                continue
            safe = entry.get("safe_to_remove") is True
            status = str(entry.get("status") or payload.get("status") or owner_document.get("status") or "unknown")
            specs.append({
                "path": str(entry.get("path")),
                "owner": "aoa-session-memory",
                "kind": "aoa_owner_debris",
                "source_id": f"aoa-maintenance:{section}:{entry.get('content_digest') or entry.get('path')}",
                "source_adapter": "aoa_owner_verdict",
                "executor": {
                    "type": "aoa_maintenance_cleanup",
                    "owner_specific": True,
                    "command": "aoa_session_memory.py maintenance-cleanup --apply with exact owner confirmation when required",
                },
                "unique_data": {
                    "status": "clear" if safe else "unknown",
                    "reasons": entry.get("diagnostics") or [status],
                },
                "recovery": {
                    "verified": bool(safe and entry.get("raw_authority", {}).get("verified")),
                    "command": "regenerate projection from owner-verified stronger raw authority" if safe else None,
                },
                "replacement": {
                    "verified": bool(safe and entry.get("raw_authority", {}).get("verified")),
                    "ref": entry.get("raw_authority", {}).get("authority_ref"),
                },
                "owner_verdict": {
                    "authoritative": True,
                    "safe_to_remove": safe,
                    "preservation_verified": bool(entry.get("raw_authority", {}).get("verified")),
                    "active_writer": active_writer,
                    "status": status,
                    "content_digest": entry.get("content_digest"),
                    "source_document_status": owner_document.get("status"),
                },
                "physical_bytes": entry.get("size_bytes"),
                "reclaimable_bytes": entry.get("size_bytes") if safe else 0,
            })
    return specs


def backup_evidence_for_path(
    path: Path,
    *,
    lane_documents: Sequence[tuple[str, Mapping[str, Any]]],
    candidate_mtime: str | None,
    archive_manifest: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    archive_manifest = archive_manifest if isinstance(archive_manifest, Mapping) else {}
    covered: list[dict[str, Any]] = []
    candidate_time = contracts.parse_time(candidate_mtime)
    for source_path, document in lane_documents:
        results = document.get("results") if isinstance(document.get("results"), list) else []
        for result in results:
            if not isinstance(result, Mapping) or result.get("status") != "ok" or not result.get("source"):
                continue
            source = Path(str(result.get("source")))
            if path == source or _path_is_under(path, source):
                finished = contracts.parse_time(document.get("finished_at") or document.get("updated_at"))
                covered.append({
                    "lane": document.get("lane"),
                    "status": document.get("status"),
                    "finished_at": document.get("finished_at") or document.get("updated_at"),
                    "source": str(source),
                    "destination": result.get("destination"),
                    "record": source_path,
                    "fresh_for_candidate": bool(finished and (candidate_time is None or finished >= candidate_time)),
                })
    fresh = any(item.get("fresh_for_candidate") for item in covered)
    digest_match = archive_manifest.get("digest_match") is True
    restore_verified = archive_manifest.get("restore_verified") is True
    restore_command = archive_manifest.get("restore_command")
    return (
        {
            "checked": True,
            "fresh": fresh,
            "digest_match": digest_match,
            "status": "fresh_lane_and_digest_verified" if fresh and digest_match else ("covered_but_stale_or_digest_unverified" if covered else "not_covered"),
            "coverage": covered,
            "manifest": dict(archive_manifest),
        },
        {
            "checked": True,
            "verified": bool(restore_verified and restore_command),
            "command": restore_command,
            "status": "verified" if restore_verified and restore_command else "not_verified",
        },
    )


def _virtual_fingerprint(value: Mapping[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return {"digest": digest, "complete": True, "virtual": True, "entries": 1, "latest_mtime": None}


def collect_observation(
    spec: Mapping[str, Any],
    *,
    protection: Mapping[str, Any],
    process_refs: Mapping[str, Any],
    claims: Sequence[Mapping[str, Any]],
    runtime_documents: Sequence[tuple[str, Mapping[str, Any]]],
    lane_documents: Sequence[tuple[str, Mapping[str, Any]]],
    deep: bool,
    generated_at: str,
    max_fingerprint_entries: int,
    service_refs: Mapping[str, Any] | None = None,
    container_refs: Mapping[str, Any] | None = None,
    config_refs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    path_text = contracts.canonical_candidate_path(str(spec.get("path") or ""))
    path = Path(path_text)
    virtual = spec.get("virtual") is True
    if virtual:
        fingerprint = _virtual_fingerprint(spec.get("virtual_fingerprint") if isinstance(spec.get("virtual_fingerprint"), Mapping) else spec)
        physical_bytes = spec.get("physical_bytes")
        size_evidence = {"checked": True, "ok": isinstance(physical_bytes, int), "method": "owner unique-size report", "physical": True}
        exists = True
    else:
        fingerprint = filesystem_fingerprint(path, max_entries=max_fingerprint_entries)
        physical_bytes, size_evidence = physical_size_bytes(path)
        exists = path.exists() or path.is_symlink()
    latest_mtime = fingerprint.get("latest_mtime")
    archive_manifest = spec.get("archive") if isinstance(spec.get("archive"), Mapping) else {}
    backup, restore = backup_evidence_for_path(
        path,
        lane_documents=lane_documents,
        candidate_mtime=latest_mtime,
        archive_manifest=archive_manifest,
    ) if not virtual else (
        {"checked": True, "fresh": False, "digest_match": False, "status": "not_applicable_without_owner_export"},
        {"checked": True, "verified": False, "command": None, "status": "not_verified"},
    )
    artifact_record = spec.get("artifact_record") if isinstance(spec.get("artifact_record"), Mapping) else {}
    artifact_process = artifact_record.get("process_refs") if isinstance(artifact_record.get("process_refs"), Mapping) else {}
    selected_process = dict(artifact_process or process_refs)
    selected_process.setdefault("checked", True)
    selected_service = dict(service_refs or (artifact_record.get("service_refs") if isinstance(artifact_record.get("service_refs"), Mapping) else {}))
    selected_container = dict(container_refs or (artifact_record.get("container_refs") if isinstance(artifact_record.get("container_refs"), Mapping) else {}))
    selected_config = dict(config_refs or (artifact_record.get("config_refs") if isinstance(artifact_record.get("config_refs"), Mapping) else {}))
    for selected in (selected_service, selected_container, selected_config):
        selected.setdefault("checked", bool(artifact_record) or deep)
        selected.setdefault("active", False)
    if spec.get("forced_active") is True:
        selected_container["active"] = True
        selected_container.setdefault("containers", [spec.get("podman") or {"source": spec.get("source_adapter")}])
    candidate_id = str(spec.get("candidate_id") or contracts.stable_candidate_id(
        owner=str(spec.get("owner") or "unknown"),
        kind=str(spec.get("kind") or "unknown"),
        path=path_text,
        source_id=str(spec.get("source_id") or ""),
    ))
    active_claims = contracts.active_claims(
        claims,
        candidate_id=candidate_id,
        path=path_text,
        now_time=contracts.parse_time(generated_at),
    )
    runtime_refs = json_path_references(path_text, runtime_documents) if deep and not virtual else {"checked": virtual, "active": False, "matches": []}
    mount_refs = mount_references(path) if deep and not virtual else {"checked": virtual, "active": False, "refs": []}
    evidence = {
        "protection": dict(protection),
        "physical_size": size_evidence,
        "process_refs": selected_process,
        "mount_refs": mount_refs,
        "service_refs": selected_service,
        "container_refs": selected_container,
        "config_refs": selected_config,
        "runtime_refs": runtime_refs,
        "active_claims": active_claims,
        "unique_data": dict(spec.get("unique_data") if isinstance(spec.get("unique_data"), Mapping) else {"status": "unknown"}),
        "recovery": dict(spec.get("recovery") if isinstance(spec.get("recovery"), Mapping) else {}),
        "replacement": dict(spec.get("replacement") if isinstance(spec.get("replacement"), Mapping) else {}),
        "backup": backup,
        "restore": restore,
    }
    for key in ("owner_verdict", "git", "podman", "manifest"):
        if isinstance(spec.get(key), Mapping):
            evidence[key] = dict(spec[key])
    return {
        "candidate_id": candidate_id,
        "path": path_text,
        "owner": str(spec.get("owner") or "unknown"),
        "kind": str(spec.get("kind") or "unknown"),
        "source_id": str(spec.get("source_id") or ""),
        "source_adapter": spec.get("source_adapter"),
        "retention_until": spec.get("retention_until"),
        "exists": exists,
        "physical_bytes": physical_bytes,
        "reclaimable_bytes": spec.get("reclaimable_bytes") if isinstance(spec.get("reclaimable_bytes"), int) else physical_bytes,
        "fingerprint": fingerprint,
        "latest_mtime": latest_mtime,
        "observed_at": generated_at,
        "executor": dict(spec.get("executor") if isinstance(spec.get("executor"), Mapping) else {}),
        "evidence": evidence,
    }
