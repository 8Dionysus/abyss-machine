from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


DEFAULT_USER = "abyss"
DEFAULT_ETC_ROOT = Path("/etc/abyss-machine")
DEFAULT_STATE_ROOT = Path("/var/lib/abyss-machine")
DEFAULT_SRV_ROOT = Path("/srv/abyss-machine")
DEFAULT_RUN_ROOT = Path("/run/abyss-machine")
DEFAULT_ABYSS_OS_ROOT = Path("/srv/AbyssOS")
DEFAULT_VAULT_MOUNT = Path("/abyss")
DEFAULT_LOCAL_BIN_DIR = Path("/usr/local/bin")
DEFAULT_LOCAL_LIBEXEC_DIR = Path("/usr/local/libexec")
DEFAULT_SYSTEMD_SYSTEM_DIR = Path("/etc/systemd/system")


def _value(value: str | Path | None, default: str | Path) -> Path:
    if value is None or str(value) == "":
        return Path(default)
    return Path(value)


def _text(value: str | Path | None, default: str | Path) -> str:
    if value is None or str(value) == "":
        return str(default)
    return str(value)


def path_from_env(env: str, default: str | Path, *, environ: Mapping[str, str] | None = None) -> Path:
    source = os.environ if environ is None else environ
    return Path(source.get(env, str(default)))


@dataclass(frozen=True)
class AbyssMachinePathPolicy:
    user: str
    home: Path
    etc_root: Path = DEFAULT_ETC_ROOT
    state_root: Path = DEFAULT_STATE_ROOT
    srv_root: Path = DEFAULT_SRV_ROOT
    run_root: Path = DEFAULT_RUN_ROOT
    abyss_os_root: Path = DEFAULT_ABYSS_OS_ROOT
    vault_mount: Path = DEFAULT_VAULT_MOUNT
    local_bin_dir: Path = DEFAULT_LOCAL_BIN_DIR
    local_libexec_dir: Path = DEFAULT_LOCAL_LIBEXEC_DIR
    systemd_system_dir: Path = DEFAULT_SYSTEMD_SYSTEM_DIR
    systemd_user_dir: Path | None = None
    cache_root_override: Path | None = None
    runtimes_root_override: Path | None = None
    storage_root_override: Path | None = None
    tmp_root_override: Path | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "AbyssMachinePathPolicy":
        source = os.environ if environ is None else environ
        user = source.get("ABYSS_USER") or source.get("USER") or DEFAULT_USER
        home = Path(source.get("ABYSS_USER_HOME") or source.get("HOME") or f"/home/{user}")
        return cls(
            user=user,
            home=home,
            etc_root=path_from_env("ABYSS_MACHINE_ETC_ROOT", DEFAULT_ETC_ROOT, environ=source),
            state_root=path_from_env("ABYSS_MACHINE_STATE_ROOT", DEFAULT_STATE_ROOT, environ=source),
            srv_root=path_from_env("ABYSS_MACHINE_ROOT", DEFAULT_SRV_ROOT, environ=source),
            run_root=path_from_env("ABYSS_MACHINE_RUN_ROOT", DEFAULT_RUN_ROOT, environ=source),
            abyss_os_root=path_from_env("ABYSS_OS_ROOT", DEFAULT_ABYSS_OS_ROOT, environ=source),
            vault_mount=path_from_env("ABYSS_VAULT_MOUNT", DEFAULT_VAULT_MOUNT, environ=source),
            local_bin_dir=path_from_env("ABYSS_LOCAL_BIN_DIR", DEFAULT_LOCAL_BIN_DIR, environ=source),
            local_libexec_dir=path_from_env("ABYSS_LOCAL_LIBEXEC_DIR", DEFAULT_LOCAL_LIBEXEC_DIR, environ=source),
            systemd_system_dir=path_from_env("ABYSS_SYSTEMD_SYSTEM_DIR", DEFAULT_SYSTEMD_SYSTEM_DIR, environ=source),
            systemd_user_dir=path_from_env(
                "ABYSS_SYSTEMD_USER_DIR",
                home / ".config/systemd/user",
                environ=source,
            ),
            cache_root_override=Path(source["ABYSS_MACHINE_CACHE_ROOT"]) if source.get("ABYSS_MACHINE_CACHE_ROOT") else None,
            runtimes_root_override=Path(source["ABYSS_MACHINE_RUNTIME_ROOT"]) if source.get("ABYSS_MACHINE_RUNTIME_ROOT") else None,
            storage_root_override=Path(source["ABYSS_MACHINE_STORAGE_ROOT"]) if source.get("ABYSS_MACHINE_STORAGE_ROOT") else None,
            tmp_root_override=Path(source["ABYSS_MACHINE_TMP_ROOT"]) if source.get("ABYSS_MACHINE_TMP_ROOT") else None,
        )

    @classmethod
    def from_values(
        cls,
        *,
        user: str | None = None,
        home: str | Path | None = None,
        etc_root: str | Path | None = None,
        state_root: str | Path | None = None,
        srv_root: str | Path | None = None,
        run_root: str | Path | None = None,
        abyss_os_root: str | Path | None = None,
        vault_mount: str | Path | None = None,
        local_bin_dir: str | Path | None = None,
        local_libexec_dir: str | Path | None = None,
        systemd_system_dir: str | Path | None = None,
        systemd_user_dir: str | Path | None = None,
        cache_root: str | Path | None = None,
        runtimes_root: str | Path | None = None,
        storage_root: str | Path | None = None,
        tmp_root: str | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "AbyssMachinePathPolicy":
        base = cls.from_environment(environ=environ)
        resolved_user = user or base.user
        resolved_home = _value(home, base.home)
        preserve_derived_srv_roots = srv_root is None
        return cls(
            user=resolved_user,
            home=resolved_home,
            etc_root=_value(etc_root, base.etc_root),
            state_root=_value(state_root, base.state_root),
            srv_root=_value(srv_root, base.srv_root),
            run_root=_value(run_root, base.run_root),
            abyss_os_root=_value(abyss_os_root, base.abyss_os_root),
            vault_mount=_value(vault_mount, base.vault_mount),
            local_bin_dir=_value(local_bin_dir, base.local_bin_dir),
            local_libexec_dir=_value(local_libexec_dir, base.local_libexec_dir),
            systemd_system_dir=_value(systemd_system_dir, base.systemd_system_dir),
            systemd_user_dir=_value(systemd_user_dir, base.systemd_user_dir or (resolved_home / ".config/systemd/user")),
            cache_root_override=_value(cache_root, base.cache_root)
            if cache_root is not None
            else (base.cache_root_override if preserve_derived_srv_roots else None),
            runtimes_root_override=_value(runtimes_root, base.runtimes_root)
            if runtimes_root is not None
            else (base.runtimes_root_override if preserve_derived_srv_roots else None),
            storage_root_override=_value(storage_root, base.storage_root)
            if storage_root is not None
            else (base.storage_root_override if preserve_derived_srv_roots else None),
            tmp_root_override=_value(tmp_root, base.tmp_root)
            if tmp_root is not None
            else (base.tmp_root_override if preserve_derived_srv_roots else None),
        )

    @property
    def cache_root(self) -> Path:
        return self.cache_root_override or self.srv_root / "cache"

    @property
    def runtimes_root(self) -> Path:
        return self.runtimes_root_override or self.srv_root / "runtimes"

    @property
    def storage_root(self) -> Path:
        return self.storage_root_override or self.srv_root / "storage"

    @property
    def tmp_root(self) -> Path:
        return self.tmp_root_override or self.srv_root / "tmp"

    @property
    def backup_root(self) -> Path:
        return self.vault_mount / "Backups"

    @property
    def backup_secret_root(self) -> Path:
        return self.backup_root / "secrets"

    @property
    def install_roots(self) -> tuple[Path, ...]:
        return (
            self.etc_root,
            self.state_root,
            self.srv_root,
            self.cache_root,
            self.runtimes_root,
            self.storage_root,
            self.tmp_root,
        )

    def etc_file(self, *parts: str) -> Path:
        return self.etc_root.joinpath(*parts)

    def state_path(self, *parts: str) -> Path:
        return self.state_root.joinpath(*parts)

    def srv_path(self, *parts: str) -> Path:
        return self.srv_root.joinpath(*parts)

    def run_path(self, *parts: str) -> Path:
        return self.run_root.joinpath(*parts)

    def libexec_file(self, *parts: str) -> Path:
        return self.local_libexec_dir.joinpath(*parts)

    def bin_file(self, *parts: str) -> Path:
        return self.local_bin_dir.joinpath(*parts)

    def render_vars(self) -> dict[str, str]:
        return {
            "ABYSS_USER": self.user,
            "ABYSS_USER_HOME": str(self.home),
            "ABYSS_OS_ROOT": str(self.abyss_os_root),
            "ABYSS_MACHINE_ETC": str(self.etc_root),
            "ABYSS_MACHINE_STATE": str(self.state_root),
            "ABYSS_MACHINE_SRV": str(self.srv_root),
            "ABYSS_MACHINE_RUN": str(self.run_root),
            "ABYSS_LOCAL_BIN_DIR": str(self.local_bin_dir),
            "ABYSS_LOCAL_LIBEXEC_DIR": str(self.local_libexec_dir),
            "ABYSS_VAULT_MOUNT": str(self.vault_mount),
            "ABYSS_BACKUP_ROOT": str(self.backup_root),
            "ABYSS_BACKUP_SECRET_ROOT": str(self.backup_secret_root),
        }

    def cli_defaults(self) -> dict[str, str]:
        return {
            "user": self.user,
            "home": str(self.home),
            "etc_root": str(self.etc_root),
            "state_root": str(self.state_root),
            "srv_root": str(self.srv_root),
            "run_root": str(self.run_root),
            "abyss_os_root": str(self.abyss_os_root),
            "vault_mount": str(self.vault_mount),
            "local_bin_dir": str(self.local_bin_dir),
            "local_libexec_dir": str(self.local_libexec_dir),
            "systemd_system_dir": str(self.systemd_system_dir),
            "systemd_user_dir": str(self.systemd_user_dir or self.home / ".config/systemd/user"),
        }


DEFAULT_PATH_POLICY = AbyssMachinePathPolicy.from_environment()
