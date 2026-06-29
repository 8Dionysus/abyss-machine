from __future__ import annotations

from pathlib import Path
import sys


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
