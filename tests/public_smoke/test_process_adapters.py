from __future__ import annotations

import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import process_adapters


def _stat_text(comm: str, *, ppid: int = 1, utime: int = 10, stime: int = 5, threads: int = 3) -> str:
    fields = ["0"] * 40
    fields[0] = "S"
    fields[1] = str(ppid)
    fields[11] = str(utime)
    fields[12] = str(stime)
    fields[15] = "20"
    fields[16] = "0"
    fields[17] = str(threads)
    fields[19] = "12345"
    fields[36] = "7"
    return f"123 ({comm}) " + " ".join(fields)


def _write_proc(
    proc_root: Path,
    pid: int,
    *,
    comm: str = "worker",
    cmdline: bytes | None = None,
    cwd_target: Path | None = None,
    exe_target: Path | None = None,
    utime: int = 10,
    stime: int = 5,
) -> Path:
    root = proc_root / str(pid)
    root.mkdir(parents=True)
    (root / "stat").write_text(_stat_text(comm, utime=utime, stime=stime), encoding="utf-8")
    (root / "status").write_text(
        "\n".join([
            f"Name:\t{comm}",
            "Uid:\t1000\t1000\t1000\t1000",
            "PPid:\t1",
            "Threads:\t3",
            "VmRSS:\t2048 kB",
            "VmSize:\t4096 kB",
        ]),
        encoding="utf-8",
    )
    (root / "cmdline").write_bytes(cmdline if cmdline is not None else b"worker\x00--flag")
    (root / "io").write_text("read_bytes: 11\nwrite_bytes: 22\n", encoding="utf-8")
    (root / "oom_score").write_text("100\n", encoding="utf-8")
    (root / "oom_score_adj").write_text("0\n", encoding="utf-8")
    (root / "cgroup").write_text("0::/user.slice/user-1000.slice\n", encoding="utf-8")
    (root / "fd").mkdir()
    (root / "fd" / "0").write_text("", encoding="utf-8")
    if cwd_target is not None:
        (root / "cwd").symlink_to(cwd_target)
    if exe_target is not None:
        (root / "exe").symlink_to(exe_target)
    return root


def test_process_info_reads_synthetic_proc_and_classifies_storage_and_game(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    storage_root = tmp_path / "cache"
    storage_root.mkdir()
    game_root = tmp_path / "games"
    game_root.mkdir()
    game_dir = game_root / "Example"
    game_dir.mkdir()
    _write_proc(
        proc_root,
        123,
        comm="Example.exe",
        cmdline=f"{game_dir}/Example.exe --cache {storage_root}".encode(),
        cwd_target=game_dir,
        exe_target=game_dir / "Example.exe",
    )

    info = process_adapters.process_info(
        123,
        proc_root=proc_root,
        storage_roots=[storage_root],
        game_roots=[game_root],
        sysconf=lambda name: 100,
    )

    assert info is not None
    assert info["pid"] == 123
    assert info["comm"] == "Example.exe"
    assert info["cmdline"].endswith(str(storage_root))
    assert info["uid"] == 1000
    assert info["vmrss_kib"] == 2048
    assert info["io"] == {"read_bytes": 11, "write_bytes": 22}
    assert info["fd_count"] == 1
    assert info["cpu_time_sec"] == 0.15
    assert info["storage_matches"] == [str(storage_root)]
    assert info["game_role"] == "active_game"
    assert info["workload_hint"] == "game"


def test_collect_process_infos_samples_cpu_percent_with_fake_sleep(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "stat").write_text("cpu 100 0 0 0\n", encoding="utf-8")
    _write_proc(proc_root, 200, comm="python", utime=10, stime=0)

    def fake_sleep(seconds: float) -> None:
        assert seconds == 0.5
        (proc_root / "stat").write_text("cpu 200 0 0 0\n", encoding="utf-8")
        (proc_root / "200" / "stat").write_text(_stat_text("python", utime=20, stime=0), encoding="utf-8")

    scan = process_adapters.collect_process_infos(
        proc_root=proc_root,
        interval=0.5,
        sleep=fake_sleep,
        sysconf=lambda name: 100,
    )

    assert scan["inaccessible"] == 0
    assert scan["cpu_sample"]["sampled_pids"] == 1
    assert scan["processes"][0]["cpu_system_percent"] == 10.0


def test_proc_task_stat_data_includes_processor(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    task = proc_root / "300" / "task" / "301"
    task.mkdir(parents=True)
    (task / "stat").write_text(_stat_text("thread", utime=3, stime=2), encoding="utf-8")

    data = process_adapters.proc_task_stat_data(300, 301, proc_root=proc_root, sysconf=lambda name: 100)

    assert data["comm"] == "thread"
    assert data["cpu_jiffies"] == 5
    assert data["cpu_time_sec"] == 0.05
    assert data["processor"] == 7


def test_process_info_missing_proc_returns_none(tmp_path: Path) -> None:
    assert process_adapters.process_info(404, proc_root=tmp_path / "proc") is None


def _container_doc(*, command_exists=lambda name: True, runner):
    return process_adapters.process_container_health_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-29T00:00:00Z",
        latest_path="/var/lib/abyss-machine/processes/containers/latest.json",
        daily_glob="/var/lib/abyss-machine/processes/containers/YYYY/MM/YYYY-MM-DD.jsonl",
        command_exists=command_exists,
        runner=runner,
    )


def test_process_container_health_reports_missing_podman() -> None:
    data = _container_doc(
        command_exists=lambda name: False,
        runner=lambda command, timeout=0: {"ok": True, "stdout": "[]", "stderr": "", "returncode": 0},
    )

    assert data["ok"] is False
    assert data["error"] == "podman is not installed"
    assert data["summary"] == {"status": "unavailable"}


def test_process_container_health_maps_podman_ps_failure() -> None:
    data = _container_doc(
        runner=lambda command, timeout=0: {"ok": False, "stdout": "", "stderr": "boom", "returncode": 125},
    )

    assert data["ok"] is False
    assert data["error"] == "boom"
    assert data["returncode"] == 125
    assert data["summary"] == {"status": "unavailable"}


def test_process_container_health_sanitizes_and_flags_attention() -> None:
    ps_rows = [
        {
            "Id": "abcdef1234567890",
            "Names": ["abyss_api_1"],
            "Image": "example/api:latest",
            "ImageID": "imageabcdef123456",
            "State": "exited",
            "Status": "Exited (2) 4 minutes ago (unhealthy)",
            "ExitCode": 2,
            "Restarts": 3,
            "Labels": {
                "io.podman.compose.project": "abyss",
                "io.podman.compose.service": "api",
                "secret": "must-not-appear",
            },
        }
    ]
    inspect_rows = [
        {
            "Id": "abcdef1234567890",
            "Name": "/abyss_api_1",
            "Config": {
                "Labels": {
                    "io.podman.compose.project": "abyss",
                    "io.podman.compose.service": "api",
                    "secret": "must-not-appear",
                },
                "Env": ["SECRET=value"],
            },
            "HostConfig": {"RestartPolicy": {"Name": "always"}},
            "State": {
                "Status": "exited",
                "Running": False,
                "Restarting": False,
                "Dead": False,
                "Pid": 0,
                "ExitCode": 2,
                "OOMKilled": False,
                "Health": {"Status": "unhealthy"},
            },
        }
    ]
    calls: list[tuple[list[str], float]] = []

    def runner(command: list[str], timeout: float = 0) -> dict[str, object]:
        calls.append((command, timeout))
        if command[:4] == ["podman", "ps", "-a", "--format"]:
            return {"ok": True, "stdout": json.dumps(ps_rows), "stderr": "", "returncode": 0}
        if command[:2] == ["podman", "inspect"]:
            return {"ok": True, "stdout": json.dumps(inspect_rows), "stderr": "", "returncode": 0}
        raise AssertionError(command)

    data = _container_doc(runner=runner)

    assert calls == [
        (["podman", "ps", "-a", "--format", "json"], 10.0),
        (["podman", "inspect", "abcdef1234567890"], 20.0),
    ]
    assert data["ok"] is True
    assert data["summary"]["status"] == "attention"
    assert data["summary"]["containers"] == 1
    assert data["summary"]["running"] == 0
    assert data["summary"]["unhealthy"] == 1
    assert data["summary"]["abyss_stack_managed"] == 1
    container = data["containers"][0]
    assert container["id"] == "abcdef123456"
    assert container["name"] == "abyss_api_1"
    assert container["labels"] == {
        "io.podman.compose.project": "abyss",
        "io.podman.compose.service": "api",
    }
    assert "secret" not in json.dumps(data)
    assert data["capture"]["includes_env"] is False
    assert set(data["attention"][0]["reasons"]) == {
        "unhealthy",
        "restart_count_nonzero",
        "exited_nonzero",
        "restart_policy_not_running",
        "abyss_stack_not_running",
    }


def test_safe_container_summary_redacts_mounts_and_ports() -> None:
    summary = process_adapters.safe_container_summary({
        "Id": "abcdef1234567890",
        "Name": "/worker",
        "ImageName": "example/worker:latest",
        "State": {"Status": "running", "Running": True, "Pid": 123},
        "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}, "NetworkMode": "bridge"},
        "NetworkSettings": {"Ports": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18080"}]}},
        "Mounts": [
            {"Type": "bind", "Source": "/srv/work/project/db", "Destination": "/data", "RW": True},
            {"Type": "volume", "Name": "pgdata", "Source": "/var/lib/containers/storage/volumes/pgdata", "Destination": "/pg", "RW": True},
        ],
        "Config": {"Env": ["SECRET=value"]},
    })

    assert summary["id"] == "abcdef123456"
    assert summary["running"] is True
    assert summary["redaction"] == {"env_omitted": True, "create_command_omitted": True}
    assert summary["ports"] == {"8080/tcp": [{"host_ip": "127.0.0.1", "host_port": "18080"}]}
    assert summary["work_mounts"][0]["source"] == "/srv/work/project/db"
    assert summary["named_volumes"][0]["name"] == "pgdata"


def _write_task(proc_root: Path, pid: int, tid: int, *, comm: str, utime: int, stime: int, wchan: str = "poll_schedule_timeout") -> None:
    task = proc_root / str(pid) / "task" / str(tid)
    task.mkdir(parents=True, exist_ok=True)
    (task / "stat").write_text(_stat_text(comm, utime=utime, stime=stime), encoding="utf-8")
    (task / "wchan").write_text(wchan, encoding="utf-8")


def test_gnome_shell_cpu_samples_reads_fake_proc_and_units(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "stat").write_text("cpu 100 0 0 0\n", encoding="utf-8")
    shell_root = _write_proc(
        proc_root,
        777,
        comm="gnome-shell",
        cmdline=b"/usr/bin/gnome-shell\x00--mode=user",
        utime=10,
        stime=0,
    )
    (shell_root / "comm").write_text("gnome-shell\n", encoding="utf-8")
    (shell_root / "fd" / "1").symlink_to("anon_inode:[pidfd]")
    (shell_root / "fd" / "2").symlink_to("/dmabuf-gpu-buffer")
    (shell_root / "fd" / "3").symlink_to("socket:[123]")
    _write_task(proc_root, 777, 777, comm="gnome-shell", utime=10, stime=0)
    _write_task(proc_root, 777, 778, comm="KMS thread", utime=4, stime=1)

    assert process_adapters.process_gnome_shell_pid(proc_root=proc_root, sysconf=lambda name: 100) == 777

    monotonic_values = iter([0.0, 0.0, 0.0, 1.0, 1.0])

    def fake_monotonic() -> float:
        return next(monotonic_values, 1.0)

    def fake_sleep(seconds: float) -> None:
        assert seconds == 1.0
        (shell_root / "stat").write_text(_stat_text("gnome-shell", utime=35, stime=5), encoding="utf-8")
        _write_task(proc_root, 777, 777, comm="gnome-shell", utime=30, stime=5)
        _write_task(proc_root, 777, 778, comm="KMS thread", utime=5, stime=2)

    def runner(command: list[str], timeout: float = 0) -> dict[str, object]:
        assert command[:3] == ["systemctl", "--user", "is-active"]
        return {"ok": True, "stdout": "active\n", "stderr": "", "returncode": 0}

    samples = process_adapters.process_gnome_shell_cpu_samples(
        777,
        seconds=1.0,
        interval=1.0,
        units=["abyss-passive-chronicle.service"],
        proc_root=proc_root,
        sysconf=lambda name: 100,
        sleep=fake_sleep,
        monotonic=fake_monotonic,
        command_exists=lambda name: name == "systemctl",
        runner=runner,
    )

    assert len(samples) == 1
    sample = samples[0]
    assert sample["cpu_one_core_percent"] == 30.0
    assert sample["fd"] == {"total": 4, "pidfd": 1, "dmabuf": 1, "socket": 1, "timerfd": 0, "eventfd": 0}
    assert sample["top_threads"][0]["comm"] == "gnome-shell"
    assert sample["top_threads"][0]["cpu_one_core_percent"] == 25.0
    assert sample["units"] == {"abyss-passive-chronicle.service": "active"}


def test_desktop_command_probes_parse_fake_runner_outputs(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    shell_root = _write_proc(
        proc_root,
        777,
        comm="gnome-shell",
        cmdline=b"/usr/bin/gnome-shell\x00--mode=user",
    )
    (shell_root / "comm").write_text("gnome-shell\n", encoding="utf-8")
    status_root = _write_proc(proc_root, 456, comm="firefox", cmdline=b"firefox\x00--wayland")
    (status_root / "comm").write_text("firefox\n", encoding="utf-8")

    home = tmp_path / "home"
    vitals_path = home / ".local" / "share" / "gnome-shell" / "extensions" / "Vitals@CoreCoding.com"
    vitals_path.mkdir(parents=True)
    (vitals_path / "metadata.json").write_text(json.dumps({"name": "Vitals", "version": 70, "url": "https://example.invalid/vitals"}), encoding="utf-8")
    (vitals_path / "schemas").mkdir()
    system_extensions = tmp_path / "system-extensions"
    other_path = system_extensions / "Other@Example"
    other_path.mkdir(parents=True)
    (other_path / "metadata.json").write_text(json.dumps({"name": "Other", "version": 1}), encoding="utf-8")

    available = {"gdbus", "busctl", "gsettings", "timeout", "dbus-monitor", "wmctrl", "xprop", "ss", "ps"}

    def command_exists(name: str) -> bool:
        return name in available

    def result(stdout: str, *, ok: bool = True, returncode: int = 0, stderr: str = "") -> dict[str, object]:
        return {"ok": ok, "stdout": stdout, "stderr": stderr, "returncode": returncode}

    def runner(command: list[str], timeout: float = 0) -> dict[str, object]:
        if command == ["busctl", "--user", "status", "org.gnome.Shell"]:
            return result("PID=777\nUniqueName=:1.42\nComm=gnome-shell\nCommandLine=/usr/bin/gnome-shell --mode=user\n")
        if command[:3] == ["busctl", "--user", "status"]:
            return result("PID=456\nComm=firefox\n")
        if command[:3] == ["busctl", "--user", "tree"]:
            service = command[3]
            return result(f"`-/org/gnome/Mutter/{service.rsplit('.', 1)[-1]}/Session/u1\n`-/org/gnome/Mutter/{service.rsplit('.', 1)[-1]}/Stream/u2\n")
        if command[:2] == ["gsettings", "get"] and command[-1] == "enabled-extensions":
            return result("['Vitals@CoreCoding.com', 'Other@Example']\n")
        if command[:2] == ["gsettings", "get"] and command[-1] == "disabled-extensions":
            return result("[]\n")
        if command[:2] == ["gsettings", "--schemadir"]:
            return result(
                "\n".join([
                    "org.gnome.shell.extensions.vitals update-time 1",
                    "org.gnome.shell.extensions.vitals hot-sensors ['_processor_usage_']",
                    "org.gnome.shell.extensions.vitals show-temperature true",
                ])
            )
        if command[:4] == ["gdbus", "call", "--session", "--dest"]:
            dest = command[command.index("--dest") + 1]
            method = command[command.index("--method") + 1]
            if dest == "org.gnome.Mutter.DisplayConfig" and method == "org.gnome.Mutter.DisplayConfig.GetCurrentState":
                return result("('mode-id', 2560, 1440, 120.0, 1.0, {'is-current': <true>, 'display-name': <'Panel'>, 'min-refresh-rate': <48.0>}), [(0, 0, 1.0, uint32 1, true)]")
            if method == "org.freedesktop.DBus.Properties.Get" and command[-1] == "AnimationsEnabled":
                return result("(<true>,)\n")
            if method == "org.freedesktop.DBus.Properties.Get" and command[-1] == "ScreenSize":
                return result("(<(2560, 1440)>,)\n")
            if method == "org.freedesktop.DBus.Properties.Get" and command[-1] == "RegisteredStatusNotifierItems":
                return result("(['org.example.StatusNotifierItem-1-1@/StatusNotifierItem'],)\n")
            if method == "org.freedesktop.DBus.Properties.GetAll":
                return result("({'Id': <'firefox'>, 'Title': <'Firefox'>, 'Status': <'Active'>, 'IconName': <'firefox'>},)\n")
        if command[:2] == ["timeout", "1.00"]:
            return result(
                "\n".join([
                    "signal time=10.000 sender=:1.42 -> destination=(null destination) serial=1 path=/org/gnome/Shell/Introspect; interface=org.gnome.Shell.Introspect; member=WindowsChanged",
                    "signal time=10.500 sender=:1.42 -> destination=(null destination) serial=2 path=/org/gnome/Shell/Introspect; interface=org.gnome.Shell.Introspect; member=RunningApplicationsChanged",
                ]),
                returncode=124,
            )
        if command == ["env", "DISPLAY=:0", "wmctrl", "-lpGx"]:
            return result("0x01  0  999 0 0 800 600 steam.Steam Steam\n")
        if command[:4] == ["env", "DISPLAY=:0", "xprop", "-id"]:
            return result('WM_CLASS(STRING) = "steam", "Steam"\n_NET_WM_PID(CARDINAL) = 999\n')
        if command == ["ss", "-xapH", "-n", "-O"]:
            return result(
                "\n".join([
                    '/run/user/1000/wayland-0 111 * 222 users:(("gnome-shell",pid=777,fd=10))',
                    '* 222 /run/user/1000/wayland-0 111 users:(("firefox",pid=456,fd=11))',
                ])
            )
        if command[:2] == ["ps", "-eo"]:
            return result(
                "\n".join([
                    "PID PPID COMM %CPU %MEM RSS ELAPSED COMMAND",
                    "777 1 gnome-shell 12.5 1.0 100000 00:01 /usr/bin/gnome-shell --mode=user",
                    "456 1 firefox 5.0 2.0 200000 00:02 firefox --wayland",
                ])
            )
        raise AssertionError(command)

    probes = process_adapters.process_desktop_compositor_command_probes(
        seconds=1.0,
        command_exists=command_exists,
        runner=runner,
        proc_root=proc_root,
        home_path=home,
        system_extension_root=system_extensions,
    )

    assert probes["shell_bus"]["unique_name"] == ":1.42"
    assert probes["display"]["display"]["current_mode"]["refresh_hz"] == 120.0
    assert probes["display"]["screen_size"] == {"width": 2560, "height": 1440}
    assert probes["status_notifiers"]["count"] == 1
    assert probes["screencast"]["active_session_like_paths"] == 2
    assert probes["vitals"]["enabled"] is True
    assert probes["vitals"]["metadata"]["name"] == "Vitals"
    assert probes["gnome_extensions"]["enabled_count"] == 2
    assert probes["shell_signals"]["signal_counts"] == {"WindowsChanged": 1, "RunningApplicationsChanged": 1}
    assert probes["x11_windows"]["windows"][0]["wm_class"] == "steam.Steam"
    assert probes["wayland_clients"]["clients"][0]["cmdline"] == "firefox --wayland"
    assert probes["desktop_processes"]["top"][0]["comm"] == "gnome-shell"


def test_desktop_compositor_document_preserves_observe_only_policy() -> None:
    document = process_adapters.process_desktop_compositor_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-29T00:00:00Z",
        paths={"desktop_compositor_latest": "/tmp/latest.json"},
        seconds=1.0,
        interval=1.0,
        pid=777,
        process_info_data={"pid": 777, "comm": "gnome-shell"},
        samples=[{"cpu_one_core_percent": 18.0, "fd": {"total": 4, "pidfd": 1, "dmabuf": 1}, "top_threads": [{"tid": 777, "comm": "gnome-shell"}]}],
        display={"display": {"current_mode": {"refresh_hz": 120.0}}},
        shell_bus={"unique_name": ":1.42"},
        shell_signals={"signal_rates_hz": {"WindowsChanged": 0.0, "RunningApplicationsChanged": 0.0}},
        panel_telemetry={"gnome_shell_metric_label_rate_hz": 8.0},
        atspi_windows={"count": 1, "windows": [], "counts_by_app": {}},
        vitals={"enabled": True},
        gnome_extensions={"enabled_count": 1},
        x11_windows={"count": 0, "windows": []},
        wayland_clients={"count": 1},
        desktop_processes={"top": []},
        status_notifiers={"count": 1},
        screen_cast={"active_session_like_paths": 0},
        remote_desktop={"active_session_like_paths": 0},
    )

    assert document["ok"] is True
    assert document["capture"]["facts_only"] is True
    assert document["capture"]["mutates_desktop_state"] is False
    assert document["policy"]["automation"] == "observe_only"
    assert document["policy"]["do_not_toggle_gnome_extensions_from_this_result"] is True
    assert document["summary"]["classification"] == "panel_telemetry_compositor_churn"
    assert "not as proof that Vitals" in document["summary"]["route_guidance"]


class _FakeSignal:
    SIGALRM = 14
    ITIMER_REAL = 0

    def __init__(self) -> None:
        self.handler = None
        self.timers: list[float] = []

    def getsignal(self, signum: int):
        assert signum == self.SIGALRM
        return self.handler

    def signal(self, signum: int, handler):
        assert signum == self.SIGALRM
        self.handler = handler

    def setitimer(self, which: int, seconds: float) -> None:
        assert which == self.ITIMER_REAL
        self.timers.append(seconds)


class _FakeTimer:
    def __init__(self, seconds: float, callback) -> None:
        self.seconds = seconds
        self.callback = callback
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def test_atspi_panel_telemetry_churn_counts_fake_metric_events() -> None:
    class FakeSource:
        name = "42%"

        @staticmethod
        def getApplication():
            return types.SimpleNamespace(name="gnome-shell")

        @staticmethod
        def getRoleName():
            return "label"

    class FakeRegistry:
        callback = None
        stopped = False

        @classmethod
        def registerEventListener(cls, callback, event_name):  # noqa: N802 - mirrors pyatspi API
            assert event_name == "object:property-change:accessible-name"
            cls.callback = callback

        @classmethod
        def start(cls):
            assert cls.callback is not None
            cls.callback(types.SimpleNamespace(source=FakeSource(), type="object:property-change:accessible-name"))

        @classmethod
        def stop(cls):
            cls.stopped = True

    monotonic_values = iter([0.0, 0.25, 1.0])
    signal_module = _FakeSignal()

    result = process_adapters.process_atspi_panel_telemetry_churn(
        1.0,
        pyatspi_module=types.SimpleNamespace(Registry=FakeRegistry),
        timer_factory=_FakeTimer,
        signal_module=signal_module,
        monotonic=lambda: next(monotonic_values, 1.0),
    )

    assert result["ok"] is True
    assert result["timed_out"] is False
    assert result["event_counts"]["gnome_shell_label_accessible_name"] == 1
    assert result["event_counts"]["gnome_shell_metric_label_accessible_name"] == 1
    assert result["top_metric_labels"] == [{"label": "42%", "count": 1}]
    assert result["samples"][0]["name"] == "42%"
    assert signal_module.timers == [2.0, 0.0]


def test_atspi_window_snapshot_reads_fake_desktop_tree() -> None:
    class FakeAccessible:
        def __init__(self, name: str, role: str, children: list["FakeAccessible"] | None = None) -> None:
            self.name = name
            self._role = role
            self._children = children or []

        def getRoleName(self) -> str:  # noqa: N802 - mirrors AT-SPI API
            return self._role

        def __iter__(self):
            return iter(self._children)

    class FakeRegistry:
        @staticmethod
        def getDesktop(index: int):  # noqa: N802 - mirrors pyatspi API
            assert index == 0
            return [
                FakeAccessible(
                    "org.gnome.Nautilus",
                    "application",
                    [FakeAccessible("Files", "frame"), FakeAccessible("Sidebar", "panel")],
                )
            ]

    result = process_adapters.process_atspi_window_snapshot(
        pyatspi_module=types.SimpleNamespace(Registry=FakeRegistry),
        signal_module=_FakeSignal(),
    )

    assert result["ok"] is True
    assert result["application_count"] == 1
    assert result["count"] == 2
    assert result["counts_by_app"] == {"org.gnome.Nautilus": 2}
    assert result["counts_by_role"] == {"application": 1, "frame": 1}
    assert result["windows"][1]["name"] == "Files"
    assert result["mutates_desktop_state"] is False


def test_atspi_window_snapshot_bounded_falls_back_to_latest_on_timeout(tmp_path: Path) -> None:
    latest_path = tmp_path / "desktop-compositor" / "latest.json"
    calls: list[tuple[list[str], float]] = []

    def runner(command: list[str], timeout: float = 0) -> dict[str, object]:
        calls.append((command, timeout))
        return {"ok": False, "returncode": 124, "error": "timeout", "command": command}

    def latest_loader(path: Path):
        assert path == latest_path
        return (
            {
                "generated_at": "2026-06-29T00:00:00Z",
                "atspi_windows": {
                    "ok": True,
                    "count": 3,
                    "windows": [{"app": "cached", "name": "Cached Window"}],
                    "applications": [],
                },
            },
            None,
        )

    result = process_adapters.process_atspi_window_snapshot_bounded(
        timeout_sec=0.1,
        command_runner_json=runner,
        latest_loader=latest_loader,
        latest_path=latest_path,
        python_executable="/usr/bin/python-test",
        probe_path="/tmp/abyss-machine-probe",
    )

    assert calls
    assert calls[0][0][:2] == ["/usr/bin/python-test", "-c"]
    assert calls[0][1] == 0.8
    assert result["ok"] is True
    assert result["count"] == 3
    assert result["degraded"] is True
    assert result["fresh_timeout"] is True
    assert result["fallback"]["source"] == "latest_desktop_compositor"
    assert result["_bounded_source"] == "latest_fallback_after_subprocess_failure"
