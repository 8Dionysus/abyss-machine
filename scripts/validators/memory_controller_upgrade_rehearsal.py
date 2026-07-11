#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any

from _common import REPO_ROOT, fail, ok


SCHEMA = "abyss_machine_memory_controller_upgrade_rehearsal_v1"
BOOTSTRAP = REPO_ROOT / "scripts" / "abyss-machine-bootstrap"
SOURCE_PACKAGE = REPO_ROOT / "src" / "abyss_machine"
SOURCE_ENTRYPOINT = SOURCE_PACKAGE / "entrypoint.py"
SOURCE_SHARE = {
    "manifests": REPO_ROOT / "manifests",
    "generated": REPO_ROOT / "generated",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digests(root: Path, *, ignore_bytecode: bool = True) -> dict[str, str]:
    if not root.is_dir():
        return {}
    rows: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if ignore_bytecode and ("__pycache__" in relative.parts or path.suffix == ".pyc"):
            continue
        rows[relative.as_posix()] = file_sha256(path)
    return rows


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)


def copy_sqlite_snapshot(source: Path, destination: Path) -> dict[str, Any]:
    if not source.is_file():
        raise RuntimeError(f"host evidence database is missing: {source}")
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30.0) as source_connection:
        with sqlite3.connect(destination, timeout=30.0) as destination_connection:
            source_connection.backup(destination_connection)
    destination.chmod(0o600)
    with sqlite3.connect(destination) as connection:
        integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        counts = {
            table: int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'
                ).fetchone()[0]
            )
            for table in sorted(tables)
        }
        sequence = (
            int(connection.execute("SELECT COALESCE(MAX(sequence), 0) FROM decisions").fetchone()[0])
            if "decisions" in tables
            else None
        )
    if integrity != "ok":
        raise RuntimeError(f"host evidence snapshot failed quick_check: {integrity}")
    return {
        "source": str(source),
        "snapshot": str(destination),
        "integrity": integrity,
        "size_bytes": destination.stat().st_size,
        "tables": sorted(tables),
        "row_counts": counts,
        "decision_sequence": sequence,
    }


def projection_paths(root: Path) -> dict[str, Path]:
    home = root / "home" / "agent"
    libexec = root / "usr" / "local" / "libexec"
    return {
        "root": root,
        "home": home,
        "etc": root / "etc" / "abyss-machine",
        "state": root / "var" / "lib" / "abyss-machine",
        "srv": root / "srv" / "abyss-machine",
        "run": root / "run" / "abyss-machine",
        "bin": root / "usr" / "local" / "bin",
        "libexec": libexec,
        "launcher": libexec / "abyss-machine",
        "package": libexec / "abyss_machine",
        "share": root / "usr" / "local" / "share" / "abyss-machine",
        "systemd_system": root / "etc" / "systemd" / "system",
        "systemd_user": home / ".config" / "systemd" / "user",
        "policy": root / "etc" / "abyss-machine" / "memory-controller-policy.json",
        "registry": root / "etc" / "abyss-machine" / "memory-controller-registry.json",
        "unit": home / ".config" / "systemd" / "user" / "abyss-memory-controller.service",
        "enablement": home / ".config" / "systemd" / "user" / "default.target.wants" / "abyss-memory-controller.service",
        "evidence": root / "srv" / "abyss-machine" / "tmp" / "memory-steward" / "controller",
    }


def render_unit(paths: dict[str, Path]) -> str:
    source = (REPO_ROOT / "systemd" / "user" / "abyss-memory-controller.service").read_text(encoding="utf-8")
    values = {
        "ABYSS_MACHINE_STATE": str(paths["state"]),
        "ABYSS_MACHINE_ETC": str(paths["etc"]),
        "ABYSS_LOCAL_BIN_DIR": str(paths["bin"]),
        "ABYSS_MACHINE_SRV": str(paths["srv"]),
    }
    for key, value in values.items():
        source = source.replace("{{" + key + "}}", value)
    if "{{" in source or "}}" in source:
        raise RuntimeError("synthetic controller unit contains unresolved template placeholders")
    return source


def write_evidence_marker(paths: dict[str, Path], payload: dict[str, Any]) -> None:
    paths["evidence"].mkdir(parents=True, exist_ok=True)
    marker = paths["evidence"] / "continuity-marker.json"
    marker.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    database = paths["evidence"] / "evidence.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE continuity (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO continuity(id, value) VALUES (?, ?)", ("seed", str(payload.get("seed") or "unknown")))


def seed_synthetic(paths: dict[str, Path]) -> dict[str, Any]:
    copy_tree(SOURCE_PACKAGE, paths["package"])
    (paths["package"] / "legacy_overlay_only.py").write_text("LEGACY_OVERLAY = True\n", encoding="utf-8")
    (paths["package"] / "__init__.py").write_text('__version__ = "0.8.86"\n', encoding="utf-8")
    paths["launcher"].parent.mkdir(parents=True, exist_ok=True)
    paths["launcher"].write_text("#!/usr/bin/env python3\nprint('legacy controller overlay')\n", encoding="utf-8")
    paths["launcher"].chmod(0o755)
    paths["bin"].mkdir(parents=True, exist_ok=True)
    (paths["bin"] / "abyss-machine").symlink_to(paths["launcher"])
    for root_id, source in SOURCE_SHARE.items():
        copy_tree(source, paths["share"] / root_id)
        (paths["share"] / root_id / "legacy-overlay.marker").write_text("legacy\n", encoding="utf-8")
    copy_file(REPO_ROOT / "config-templates" / "etc" / "abyss-machine" / "memory-controller-policy.json", paths["policy"])
    copy_file(REPO_ROOT / "config-templates" / "etc" / "abyss-machine" / "memory-controller-registry.json", paths["registry"])
    paths["unit"].parent.mkdir(parents=True, exist_ok=True)
    paths["unit"].write_text(render_unit(paths), encoding="utf-8")
    paths["enablement"].parent.mkdir(parents=True, exist_ok=True)
    paths["enablement"].symlink_to(paths["unit"])
    write_evidence_marker(paths, {"seed": "synthetic_0.8.86_controller_overlay", "sequence": 7})
    return {"mode": "synthetic", "version": "0.8.86", "exact_live_code_copy": False}


def controller_status_summary(executable: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(executable), "memory", "controller", "status", "--json"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "returncode": result.returncode,
        "ok": payload.get("ok") is True,
        "mode": payload.get("mode"),
        "sequence": payload.get("sequence"),
        "status": payload.get("status"),
    }


def seed_host(paths: dict[str, Path], args: argparse.Namespace) -> dict[str, Any]:
    source_launcher = Path(args.host_cli)
    source_package = Path(args.host_libexec_dir) / "abyss_machine"
    source_share = Path(args.host_share_root)
    source_policy = Path(args.host_policy)
    source_registry = Path(args.host_registry)
    source_unit = Path(args.host_unit)
    source_evidence_database = Path(args.host_evidence_root) / "evidence.sqlite3"
    required = (
        source_launcher,
        source_package,
        source_share,
        source_policy,
        source_registry,
        source_unit,
        source_evidence_database,
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("host seed missing required surfaces: " + ", ".join(missing))
    copy_file(source_launcher.resolve(), paths["launcher"])
    paths["launcher"].chmod(0o755)
    copy_tree(source_package, paths["package"])
    copy_tree(source_share, paths["share"])
    paths["bin"].mkdir(parents=True, exist_ok=True)
    (paths["bin"] / "abyss-machine").symlink_to(paths["launcher"])
    copy_file(source_policy, paths["policy"])
    copy_file(source_registry, paths["registry"])
    copy_file(source_unit, paths["unit"])
    enabled = subprocess.run(
        ["systemctl", "--user", "is-enabled", "abyss-memory-controller.service"],
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    ).returncode == 0
    if enabled:
        paths["enablement"].parent.mkdir(parents=True, exist_ok=True)
        paths["enablement"].symlink_to(paths["unit"])
    status = controller_status_summary(source_launcher)
    if status.get("ok") is not True or status.get("sequence") is None:
        raise RuntimeError(f"live controller status is not continuity-capable: {status}")
    evidence_snapshot = copy_sqlite_snapshot(source_evidence_database, paths["evidence"] / "evidence.sqlite3")
    database_sequence = evidence_snapshot.get("decision_sequence")
    if database_sequence is None or int(database_sequence) < int(status["sequence"]):
        raise RuntimeError(
            "evidence snapshot sequence predates the live controller checkpoint: "
            f"database={database_sequence} controller={status['sequence']}"
        )
    marker_payload = {
        "seed": "exact_live_code_and_evidence_projection",
        "controller_mode": status.get("mode"),
        "controller_sequence": status.get("sequence"),
        "database_sequence": database_sequence,
    }
    marker = paths["evidence"] / "continuity-marker.json"
    marker.write_text(json.dumps(marker_payload, sort_keys=True) + "\n", encoding="utf-8")
    marker.chmod(0o600)
    version = None
    init_path = source_package / "__init__.py"
    if init_path.is_file():
        for line in init_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__") and "=" in line:
                version = line.split("=", 1)[1].strip().strip('"\'')
                break
    return {
        "mode": "host",
        "version": version,
        "exact_live_code_copy": True,
        "controller": status,
        "evidence_snapshot": evidence_snapshot,
        "service_enabled": enabled,
    }


def protected_snapshot(paths: dict[str, Path]) -> dict[str, Any]:
    files = {
        "policy": paths["policy"],
        "registry": paths["registry"],
        "unit": paths["unit"],
        "evidence_marker": paths["evidence"] / "continuity-marker.json",
        "evidence_database": paths["evidence"] / "evidence.sqlite3",
    }
    return {
        "files": {name: file_sha256(path) for name, path in files.items()},
        "service_enabled": paths["enablement"].is_symlink(),
        "enablement_target": os.readlink(paths["enablement"]) if paths["enablement"].is_symlink() else None,
    }


def code_snapshot(paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "launcher": file_sha256(paths["launcher"]) if paths["launcher"].is_file() else None,
        "package": tree_digests(paths["package"]),
        "share": {root_id: tree_digests(paths["share"] / root_id) for root_id in SOURCE_SHARE},
    }


def backup_code(paths: dict[str, Path], backup: Path) -> None:
    remove_path(backup)
    backup.mkdir(parents=True)
    copy_file(paths["launcher"], backup / "launcher")
    copy_tree(paths["package"], backup / "package")
    copy_tree(paths["share"], backup / "share")


def restore_code(paths: dict[str, Path], backup: Path) -> None:
    copy_file(backup / "launcher", paths["launcher"])
    paths["launcher"].chmod(0o755)
    copy_tree(backup / "package", paths["package"])
    copy_tree(backup / "share", paths["share"])
    link = paths["bin"] / "abyss-machine"
    remove_path(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(paths["launcher"])


def bootstrap_args(paths: dict[str, Path]) -> list[str]:
    return [
        "refresh-code",
        "--profile", "linux-systemd-core",
        "--apply",
        "--skip-artifact-trust-gate",
        "--user", "agent",
        "--home", str(paths["home"]),
        "--etc-root", str(paths["etc"]),
        "--state-root", str(paths["state"]),
        "--srv-root", str(paths["srv"]),
        "--run-root", str(paths["run"]),
        "--abyss-os-root", str(paths["root"] / "srv" / "AbyssOS"),
        "--vault-mount", str(paths["root"] / "abyss"),
        "--local-bin-dir", str(paths["bin"]),
        "--local-libexec-dir", str(paths["libexec"]),
        "--systemd-system-dir", str(paths["systemd_system"]),
        "--systemd-user-dir", str(paths["systemd_user"]),
        "--json",
    ]


def apply_refresh(paths: dict[str, Path]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(BOOTSTRAP), *bootstrap_args(paths)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"refresh-code emitted invalid JSON: {exc}: {result.stderr[-500:]}") from exc
    if result.returncode != 0 or payload.get("ok") is not True:
        raise RuntimeError(f"refresh-code failed: {payload.get('artifact_admission') or result.stderr[-500:]}")
    return {
        "ok": True,
        "command": payload.get("command"),
        "mutation_scope": payload.get("mutation_scope"),
        "actions": len(payload.get("actions") or []),
    }


def controller_validation(paths: dict[str, Path]) -> dict[str, Any]:
    result = subprocess.run(
        [
            str(paths["bin"] / "abyss-machine"),
            "memory", "controller", "validate",
            "--policy", str(paths["policy"]),
            "--registry", str(paths["registry"]),
            "--runtime-root", str(paths["run"] / "memory-controller"),
            "--evidence-root", str(paths["evidence"]),
            "--json",
        ],
        cwd=paths["root"],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "ok": result.returncode == 0 and payload.get("ok") is True,
        "returncode": result.returncode,
        "status": payload.get("status"),
        "policy_mode": payload.get("policy_mode"),
        "issue_count": len(payload.get("issues") or []),
    }


def verify_source_projection(paths: dict[str, Path]) -> dict[str, Any]:
    source_package = tree_digests(SOURCE_PACKAGE)
    installed_package = tree_digests(paths["package"])
    source_share = {root_id: tree_digests(source) for root_id, source in SOURCE_SHARE.items()}
    installed_share = {root_id: tree_digests(paths["share"] / root_id) for root_id in SOURCE_SHARE}
    controller = controller_validation(paths)
    checks = {
        "launcher_matches_entrypoint": file_sha256(paths["launcher"]) == file_sha256(SOURCE_ENTRYPOINT),
        "package_matches_source": installed_package == source_package,
        "public_seed_matches_source": installed_share == source_share,
        "legacy_overlay_removed": "legacy_overlay_only.py" not in installed_package,
        "controller_valid": controller.get("ok") is True,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "controller": controller,
        "package_files": len(installed_package),
        "public_seed_files": sum(len(rows) for rows in installed_share.values()),
    }


def build_report(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    paths = projection_paths(root)
    seed = seed_host(paths, args) if args.seed_mode == "host" else seed_synthetic(paths)
    initial_code = code_snapshot(paths)
    initial_protected = protected_snapshot(paths)
    backup = root / "rollback" / "code"
    backup_code(paths, backup)

    first_apply = apply_refresh(paths)
    first_verify = verify_source_projection(paths)
    protected_after_first = protected_snapshot(paths)

    restore_code(paths, backup)
    rollback_code = code_snapshot(paths)
    protected_after_rollback = protected_snapshot(paths)
    rollback = {
        "ok": rollback_code == initial_code and protected_after_rollback == initial_protected,
        "byte_exact_code_restore": rollback_code == initial_code,
        "protected_surfaces_unchanged": protected_after_rollback == initial_protected,
    }

    second_apply = apply_refresh(paths)
    final_verify = verify_source_projection(paths)
    final_protected = protected_snapshot(paths)
    protected_ok = (
        protected_after_first == initial_protected
        and protected_after_rollback == initial_protected
        and final_protected == initial_protected
    )
    ok_result = first_verify["ok"] and rollback["ok"] and final_verify["ok"] and protected_ok
    return {
        "schema": SCHEMA,
        "ok": ok_result,
        "seed": seed,
        "first_upgrade": {"apply": first_apply, "verify": first_verify},
        "rollback": rollback,
        "second_upgrade": {"apply": second_apply, "verify": final_verify},
        "protected_surfaces": {
            "unchanged_across_upgrade_rollback_reapply": protected_ok,
            "policy_preserved": final_protected["files"]["policy"] == initial_protected["files"]["policy"],
            "registry_preserved": final_protected["files"]["registry"] == initial_protected["files"]["registry"],
            "evidence_database_preserved": final_protected["files"]["evidence_database"] == initial_protected["files"]["evidence_database"],
            "service_enablement_preserved": final_protected["service_enabled"] == initial_protected["service_enabled"],
        },
        "claim_limit": "The rehearsal mutates only an isolated copy. Live continuity is proven separately during the operator rollout.",
        "failures": [] if ok_result else ["memory controller upgrade rehearsal did not satisfy every gate"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rehearse legacy controller-overlay upgrade, rollback, and reapply in isolated roots.")
    parser.add_argument("--seed-mode", choices=("synthetic", "host"), default="synthetic")
    parser.add_argument("--tmp-root")
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--host-cli", default="/usr/local/libexec/abyss-machine")
    parser.add_argument("--host-libexec-dir", default="/usr/local/libexec")
    parser.add_argument("--host-share-root", default="/usr/local/share/abyss-machine")
    parser.add_argument("--host-policy", default="/etc/abyss-machine/memory-controller-policy.json")
    parser.add_argument("--host-registry", default="/etc/abyss-machine/memory-controller-registry.json")
    parser.add_argument("--host-unit", default=str(Path.home() / ".config/systemd/user/abyss-memory-controller.service"))
    parser.add_argument("--host-evidence-root", default="/srv/abyss-machine/tmp/memory-steward/controller")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    parent = Path(args.tmp_root) if args.tmp_root else Path(os.environ.get("ABYSS_MACHINE_FIRST_RUN_TMPDIR", "/srv/abyss-machine/tmp"))
    parent.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="abyss-machine-controller-upgrade-", dir=parent))
    try:
        report = build_report(args, root)
    except Exception as exc:
        report = {"schema": SCHEMA, "ok": False, "failures": [str(exc)]}
    finally:
        if not args.keep_temp:
            shutil.rmtree(root, ignore_errors=True)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report.get("ok") is True:
        return 0 if args.json else ok("memory controller upgrade rehearsal passed")
    return 1 if args.json else fail("memory controller upgrade rehearsal failed", [str(item) for item in report.get("failures", [])])


if __name__ == "__main__":
    raise SystemExit(main())
