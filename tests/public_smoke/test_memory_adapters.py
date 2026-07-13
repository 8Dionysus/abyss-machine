from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine import memory_adapters


def test_memory_status_parsers_use_fake_roots_and_runners(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    (proc_root / "vmstat").write_text("pswpin 2\npgmajfault 7\nignored 99\n", encoding="utf-8")
    pressure = tmp_path / "memory.pressure"
    pressure.write_text("some avg10=0.50 avg60=0.25 total=100\nfull avg10=0.00 total=0\n", encoding="utf-8")

    cgroup_root = tmp_path / "cgroup"
    user_scope = cgroup_root / "user.slice" / "user-1000.slice"
    user_scope.mkdir(parents=True)
    (cgroup_root / "memory.current").write_text("1048576\n", encoding="utf-8")
    (cgroup_root / "memory.max").write_text("max\n", encoding="utf-8")
    (user_scope / "memory.current").write_text("2097152\n", encoding="utf-8")
    (user_scope / "memory.events").write_text("oom 1\n", encoding="utf-8")

    zswap_root = tmp_path / "zswap"
    zswap_root.mkdir()
    (zswap_root / "enabled").write_text("Y\n", encoding="utf-8")

    def runner(command: list[str], timeout: float) -> dict[str, Any]:
        if command[0] == "swapon":
            return {"ok": True, "stdout": "NAME TYPE SIZE USED PRIO\n/dev/zram0 partition 4096 1024 100\n", "stderr": ""}
        if command[0] == "zramctl":
            return {
                "ok": True,
                "stdout": "NAME ALGORITHM DISKSIZE DATA COMPR TOTAL STREAMS\n/dev/zram0 zstd 4096 2048 1024 1536 4\n",
                "stderr": "",
            }
        if command[0] == "sysctl":
            return {"ok": True, "stdout": "vm.swappiness = 60\nvm.overcommit_memory = 0\n", "stderr": ""}
        raise AssertionError(command)

    assert memory_adapters.parse_pressure_file(pressure)["some"]["avg10"] == 0.5
    assert memory_adapters.vmstat_snapshot(proc_root=proc_root) == {"pswpin": 2, "pgmajfault": 7}
    assert memory_adapters.swap_status(runner=runner)["summary"]["used_percent"] == 25.0
    assert memory_adapters.zram_status(runner=runner)["summary"]["logical_to_memory_ratio"] == 1.333
    assert memory_adapters.sysctl_snapshot(runner=runner)["values"]["vm.swappiness"] == "60"
    assert memory_adapters.zswap_status(module_root=zswap_root)["enabled"] is True
    assert memory_adapters.cgroup_status(cgroup_root=cgroup_root, uid=1000)["user"]["memory_events"]["oom"] == 1


def test_hotpath_tts_probe_uses_fake_synth_port() -> None:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monotonic_values = iter([1.0, 2.25])

    def synth_port(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append((args, kwargs))
        return {
            "ok": True,
            "profile": "quality-compact",
            "engine": "piper",
            "device": "cpu",
            "wall_sec": 0.75,
            "audio": {"duration_sec": 3.5},
            "rtf": 0.21,
            "output": "/fake/audio.wav",
            "server": {"warm": True, "synth_sec": 0.42},
            "policy_gate": {
                "policy_class": "green",
                "allowed": True,
                "reasons": ["synthetic"],
            },
        }

    result = memory_adapters.hotpath_tts_probe(
        "synthetic hot path",
        2,
        synth_port=synth_port,
        monotonic=lambda: next(monotonic_values),
    )

    assert calls == [
        (
            ("quality-compact", "synthetic hot path"),
            {
                "output": None,
                "force": False,
                "allow_download": False,
                "use_server": True,
                "write_latest": True,
            },
        )
    ]
    assert result["index"] == 2
    assert result["ok"] is True
    assert result["profile"] == "quality-compact"
    assert result["client_wall_sec"] == 1.25
    assert result["server_synth_sec"] == 0.42
    assert result["audio_sec"] == 3.5
    assert result["server_used"] is True
    assert result["server_warm"] is True
    assert result["policy_allowed"] is True
    assert result["policy_reasons"] == ["synthetic"]


def test_hotpath_stt_probe_uses_fake_transcribe_port() -> None:
    calls: list[tuple[str, str]] = []
    monotonic_values = iter([10.0, 12.5])

    def transcribe_port(audio: str, profile: str) -> dict[str, Any]:
        calls.append((audio, profile))
        return {
            "ok": True,
            "via": "local",
            "client_elapsed_sec": 2.4,
            "elapsed_sec": 2.3,
            "timings": {"generate_sec": 1.7, "cache_hit": False},
            "processed_audio_duration_sec": 4.0,
            "segments": [
                {
                    "duration_sec": 4.0,
                    "elapsed_sec": 2.3,
                    "num_beams": 1,
                    "ignored": "not part of the adapter contract",
                }
            ],
            "raw_text": "recognized text",
        }

    result = memory_adapters.hotpath_stt_probe(
        "/fake/audio.wav",
        "command",
        transcribe_port=transcribe_port,
        monotonic=lambda: next(monotonic_values),
    )

    assert calls == [("/fake/audio.wav", "command")]
    assert result["profile"] == "command"
    assert result["ok"] is True
    assert result["via"] == "local"
    assert result["client_wall_sec"] == 2.5
    assert result["generate_sec"] == 1.7
    assert result["cache_hit"] is False
    assert result["audio_sec"] == 4.0
    assert result["segments"] == [{"duration_sec": 4.0, "elapsed_sec": 2.3, "num_beams": 1}]
    assert result["recognized_text"] == "recognized text"


def test_hotpath_llm_probe_latest_and_executed_use_fake_ports(tmp_path: Path) -> None:
    latest_path = tmp_path / "latest.json"
    controller_path = tmp_path / "resident-controller"
    load_calls: list[Path] = []
    runner_calls: list[tuple[list[str], float]] = []

    def load_json(path: Path) -> tuple[dict[str, Any], None]:
        load_calls.append(path)
        return (
            {
                "ok": True,
                "summary": {
                    "selected_job": "previous",
                    "status": "ok",
                    "elapsed_ms": 123,
                    "policy_decision": "allow",
                    "fallback_used": False,
                    "model_used": "gemma",
                },
            },
            None,
        )

    latest_result = memory_adapters.hotpath_llm_probe(
        False,
        4,
        latest_path=latest_path,
        controller_path=controller_path,
        load_json_document=load_json,
    )

    assert load_calls == [latest_path]
    assert runner_calls == []
    assert latest_result["mode"] == "latest_only"
    assert latest_result["executed"] is False
    assert latest_result["latest_ok"] is True
    assert latest_result["selected_job"] == "previous"

    monotonic_values = iter([20.0, 23.0])

    def runner(command: list[str], timeout: float) -> dict[str, Any]:
        runner_calls.append((command, timeout))
        return {
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "ok": True,
                    "summary": {
                        "selected_job": "a",
                        "next_job": "b",
                        "status": "ok",
                        "elapsed_ms": 456,
                        "policy_decision": "allow",
                        "fallback_used": False,
                        "model_used": "gemma",
                    },
                }
            ),
            "stderr": "",
        }

    executed_result = memory_adapters.hotpath_llm_probe(
        True,
        99,
        latest_path=latest_path,
        controller_path=controller_path,
        load_json_document=load_json,
        runner=runner,
        monotonic=lambda: next(monotonic_values),
    )

    assert runner_calls == [([str(controller_path), "micro", "--limit", "16", "--json"], 360.0)]
    assert executed_result["mode"] == "executed"
    assert executed_result["executed"] is True
    assert executed_result["ok"] is True
    assert executed_result["client_wall_sec"] == 3.0
    assert executed_result["selected_job"] == "a"
    assert executed_result["next_job"] == "b"
    assert executed_result["stdout_parse_error"] is None


def test_hotpath_probe_document_uses_fake_probe_ports() -> None:
    residency_calls: list[int] = []
    tts_calls: list[tuple[str, int]] = []
    stt_calls: list[tuple[str, str]] = []
    monotonic_values = iter([10.0, 21.25])

    residency_samples = [
        {"status": "before", "summary": {"swap_used_percent": 60.0, "psi_full_avg10": 0.0}, "services": []},
        {"status": "after_tts", "summary": {"swap_used_percent": 45.0, "psi_full_avg10": 0.0}, "services": []},
        {"status": "after", "summary": {"swap_used_percent": 44.0, "psi_full_avg10": 0.75}, "services": []},
    ]

    def residency(top: int) -> dict[str, Any]:
        residency_calls.append(top)
        return residency_samples[len(residency_calls) - 1]

    def tts_probe(text: str, index: int) -> dict[str, Any]:
        tts_calls.append((text, index))
        return {
            "ok": True,
            "output": f"/fake/audio-{index}.wav",
            "reported_wall_sec": 16.0 if index == 1 else 7.0,
        }

    def stt_probe(audio: str, profile: str) -> dict[str, Any]:
        stt_calls.append((audio, profile))
        return {
            "ok": True,
            "profile": profile,
            "client_elapsed_sec": 1.5 if profile == "command" else 5.0,
        }

    data = memory_adapters.hotpath_probe_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-29T12:00:00Z",
        text="synthetic hot path",
        repeat_tts=2,
        stt_profiles=["command", "quality"],
        include_llm=True,
        llm_limit=4,
        top=12,
        monotonic=lambda: next(monotonic_values),
        residency_port=residency,
        tts_status_port=lambda: {"ok": True, "service": {"active": True, "enabled": True}, "ping": {"profile": "quality-compact"}},
        ai_policy_port=lambda: {"class": "green", "heavy_policy": "allow", "can_run_heavy": True},
        tts_probe_port=tts_probe,
        stt_probe_port=stt_probe,
        llm_probe_port=lambda include_llm, limit: {"executed": include_llm, "elapsed_ms": 31000.0, "fallback_used": True},
        output_exists_port=lambda output: output == "/fake/audio-1.wav",
        paths_refs={
            "root": "/fake/memory/hotpath",
            "latest": "/fake/memory/hotpath/latest.json",
            "memory_residency_latest": "/fake/memory/residency/latest.json",
            "tts_latest": "/fake/tts/latest.json",
            "llm_micro_latest": "/fake/llm/micro/latest.json",
        },
    )

    assert data["schema"] == "abyss_machine_memory_hotpath_probe_v1"
    assert data["status"] == "watch"
    assert data["summary"]["duration_sec"] == 11.25
    assert data["summary"]["findings"] == [
        "dictation_command_path_interactive",
        "tts_second_run_faster_after_swapin",
        "tts_warmup_reclaimed_zram_headroom",
    ]
    assert data["summary"]["issues"] == [
        "active_memory_stalls_after_probe",
        "dictation_quality_path_slow",
        "first_tts_slow",
        "resident_llm_fallback_used",
        "resident_llm_micro_slow",
    ]
    assert data["summary"]["stt_runs"] == 2
    assert residency_calls == [12, 12, 12]
    assert tts_calls == [("synthetic hot path", 1), ("synthetic hot path", 2)]
    assert stt_calls == [("/fake/audio-1.wav", "command"), ("/fake/audio-1.wav", "quality")]


def test_hotpath_probe_document_failed_tts_skips_stt_ports() -> None:
    stt_calls: list[tuple[str, str]] = []
    monotonic_values = iter([1.0, 2.0])

    data = memory_adapters.hotpath_probe_document(
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-29T12:00:00Z",
        text="synthetic hot path",
        repeat_tts=1,
        stt_profiles=["command"],
        include_llm=False,
        llm_limit=4,
        top=5,
        monotonic=lambda: next(monotonic_values),
        residency_port=lambda top: {"status": "ok", "summary": {"swap_used_percent": 10.0, "psi_full_avg10": 0.0}, "services": []},
        tts_status_port=lambda: {"ok": True},
        ai_policy_port=lambda: {"class": "green"},
        tts_probe_port=lambda text, index: {"ok": False, "output": "/fake/missing.wav", "client_wall_sec": 1.0},
        stt_probe_port=lambda audio, profile: stt_calls.append((audio, profile)) or {"ok": True, "profile": profile},
        llm_probe_port=lambda include_llm, limit: {"mode": "latest_only", "elapsed_ms": 1000.0},
        output_exists_port=lambda output: False,
        paths_refs={"root": "/fake/memory/hotpath"},
    )

    assert data["ok"] is False
    assert data["status"] == "failed"
    assert data["summary"]["stt_runs"] == 0
    assert data["probes"]["dictation"] == []
    assert stt_calls == []


def test_process_snapshot_uses_fake_proc_cgroup_and_podman_ports(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    cgroup_root = tmp_path / "cgroup"
    cgroup = cgroup_root / "user.slice" / "model.service"
    for pid in ("10", "11"):
        (proc_root / pid).mkdir(parents=True)
    cgroup.mkdir(parents=True)
    (proc_root / "10" / "smaps_rollup").write_text("Rss: 4096 kB\nPss: 2048 kB\nSwap: 1024 kB\n", encoding="utf-8")
    (proc_root / "11" / "smaps_rollup").write_text("Rss: 2048 kB\nPss: 1024 kB\nSwap: 0 kB\n", encoding="utf-8")
    (cgroup / "memory.current").write_text("4194304\n", encoding="utf-8")
    (cgroup / "memory.swap.current").write_text("1048576\n", encoding="utf-8")

    def process_info(pid: int) -> dict[str, Any] | None:
        return {
            "pid": pid,
            "name": f"model-{pid}",
            "vmrss_kib": 4096 if pid == 10 else 2048,
            "oom_score": 100 if pid == 10 else 50,
            "cgroup": "0::/user.slice/model.service",
            "workload_hint": "ai_runtime",
            "capability_role": "persistent_model",
            "cmdline": "model --serve",
        }

    body = memory_adapters.process_snapshot(
        top=5,
        proc_root=proc_root,
        cgroup_root=cgroup_root,
        process_info=process_info,
        podman_index_port=lambda: {
            "containers": 1,
            "error": None,
            "by_pid": {10: {"id": "abcdef123456", "name": "model-api", "compose_service": "model"}},
        },
        protected_roles={"persistent_model", "persistent_ai_service", "operator_dictation"},
    )

    assert body["capture"]["smaps_rollup_read"] == 2
    assert body["summary"]["processes"] == 2
    assert body["summary"]["top_cgroup_memory_total_kib"] == 4096
    top_cgroup = body["top"]["cgroup_memory"][0]
    assert top_cgroup["protected"] is True
    assert top_cgroup["podman"]["name"] == "model-api"
    assert body["top"]["pss"][0]["pss_kib"] == 2048


def test_codex_thread_identity_uses_open_rollout_fd_without_exposing_path(tmp_path: Path) -> None:
    fd_root = tmp_path / "proc" / "42" / "fd"
    fd_root.mkdir(parents=True)
    thread_id = "019f1568-843b-7832-888f-e17c5d74d697"
    (fd_root / "7").symlink_to(
        f"/srv/runtime/custom-codex-home/sessions/2026/07/12/rollout-2026-07-12T00-00-00-{thread_id}.jsonl"
    )

    identity = memory_adapters.codex_thread_identity(42, proc_root=tmp_path / "proc")

    assert identity == {
        "owner": "codex",
        "identity_scope": "thread",
        "stable_id": thread_id,
        "candidate_ids": [thread_id],
        "ambiguous": False,
        "evidence": "open_rollout_fd",
        "content_read": False,
    }
    assert "/srv/runtime" not in json.dumps(identity)


def test_codex_thread_identity_preserves_ambiguous_owner_evidence(tmp_path: Path) -> None:
    fd_root = tmp_path / "proc" / "42" / "fd"
    fd_root.mkdir(parents=True)
    first = "019f1568-843b-7832-888f-e17c5d74d697"
    second = "019f4e25-20ec-77f0-9d41-e88b8cf1fae8"
    for fd, thread_id in (("7", first), ("8", second)):
        (fd_root / fd).symlink_to(
            f"/home/operator/.codex/sessions/2026/07/12/rollout-2026-07-12T00-00-00-{thread_id}.jsonl"
        )

    identity = memory_adapters.codex_thread_identity(42, proc_root=tmp_path / "proc")

    assert identity is not None
    assert identity["stable_id"] is None
    assert identity["candidate_ids"] == sorted([first, second])
    assert identity["ambiguous"] is True


def test_process_snapshot_carries_codex_thread_identity_to_cgroup(tmp_path: Path) -> None:
    proc_root = tmp_path / "proc"
    cgroup_root = tmp_path / "cgroup"
    cgroup = cgroup_root / "user.slice" / "codex.scope"
    (proc_root / "42").mkdir(parents=True)
    cgroup.mkdir(parents=True)
    (cgroup / "memory.current").write_text("4194304\n", encoding="utf-8")
    (cgroup / "memory.swap.current").write_text("0\n", encoding="utf-8")
    thread_id = "019f1568-843b-7832-888f-e17c5d74d697"
    identity = {
        "owner": "codex",
        "identity_scope": "thread",
        "stable_id": thread_id,
        "candidate_ids": [thread_id],
        "ambiguous": False,
        "evidence": "open_rollout_fd",
        "content_read": False,
    }

    body = memory_adapters.process_snapshot(
        top=5,
        smaps=False,
        proc_root=proc_root,
        cgroup_root=cgroup_root,
        process_info=lambda pid: {
            "pid": pid,
            "name": "codex",
            "comm": "codex",
            "vmrss_kib": 4096,
            "oom_score": 100,
            "cgroup": "0::/user.slice/codex.scope",
            "workload_hint": "development",
            "capability_role": "none",
            "cmdline": "codex",
        },
        owner_identity_port=lambda _pid: identity,
        podman_index_port=lambda: {"containers": 0, "error": None, "by_pid": {}},
        protected_roles={"persistent_model", "persistent_ai_service", "operator_dictation"},
    )

    assert body["summary"]["codex_thread_processes_identified"] == 1
    assert body["top"]["rss"][0]["owner_identity"]["stable_id"] == thread_id
    assert body["top"]["cgroup_memory"][0]["owner_identities"] == [identity]


def test_residency_service_status_uses_fake_systemd_cgroup_and_rollup_ports(tmp_path: Path) -> None:
    cgroup_root = tmp_path / "cgroup"
    service_cgroup = cgroup_root / "user.slice" / "tts.service"
    service_cgroup.mkdir(parents=True)
    (service_cgroup / "memory.current").write_text(str(512 * 1024 * 1024), encoding="utf-8")
    (service_cgroup / "memory.swap.current").write_text(str(640 * 1024 * 1024), encoding="utf-8")
    (service_cgroup / "memory.low").write_text(str(768 * 1024 * 1024), encoding="utf-8")
    (service_cgroup / "memory.high").write_text(str(4096 * 1024 * 1024), encoding="utf-8")
    (service_cgroup / "memory.max").write_text("max\n", encoding="utf-8")
    (service_cgroup / "memory.swap.max").write_text("max\n", encoding="utf-8")
    (service_cgroup / "memory.events").write_text("oom 0\n", encoding="utf-8")
    (service_cgroup / "memory.stat").write_text("anon 1024\npgfault 3\nnoise 99\n", encoding="utf-8")
    (service_cgroup / "cgroup.procs").write_text("22\n", encoding="utf-8")

    def systemd_props(unit: str, properties: list[str], user: bool, timeout: float) -> dict[str, Any]:
        assert unit == "tts.service"
        assert user is True
        assert "MemorySwapMax" in properties
        return {
            "ok": True,
            "properties": {
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": "22",
                "ControlGroup": "/user.slice/tts.service",
                "Slice": "abyss-machine-hot.slice",
                "MemoryCurrent": str(512 * 1024 * 1024),
                "MemoryPeak": str(768 * 1024 * 1024),
                "MemorySwapCurrent": str(640 * 1024 * 1024),
                "MemoryMin": "0",
                "MemoryLow": str(768 * 1024 * 1024),
                "MemoryHigh": str(4096 * 1024 * 1024),
                "MemoryMax": "max",
                "MemorySwapMax": "max",
                "CPUWeight": "100",
                "IOWeight": "100",
            },
        }

    policy = {
        "thresholds": {"hot_interactive_swap_warn_mib": 256, "swap_to_pss_ratio_warn": 4.0},
        "classes": {
            "hot_interactive": {
                "target_slice": "abyss-machine-hot.slice",
                "runtime_pilot": {"memory_low_mib": 768, "memory_high_mib": 4096},
            }
        },
    }

    status = memory_adapters.residency_service_status(
        {"unit": "tts.service", "scope": "user", "class": "hot_interactive", "protected": True},
        policy,
        systemd_unit_properties=systemd_props,
        process_info=lambda pid: {
            "name": "tts",
            "workload_hint": "ai_runtime",
            "capability_role": "persistent_ai_service",
            "vmrss_kib": 512 * 1024,
            "cmdline": "tts --serve",
        },
        process_rollup_port=lambda pid: {
            "available": True,
            "rss_kib": 512 * 1024,
            "pss_kib": 128 * 1024,
            "swap_kib": 640 * 1024,
            "swap_pss_kib": 640 * 1024,
        },
        cgroup_file_snapshot_port=lambda control_group: memory_adapters.cgroup_file_snapshot(
            control_group,
            cgroup_root=cgroup_root,
        ),
    )

    issue_codes = [issue["code"] for issue in status["issues"]]
    assert status["target"]["runtime_pilot_active"] is True
    assert status["derived"]["cgroup_swap_to_sampled_pss_ratio"] == 5.0
    assert "high_cgroup_swap" in issue_codes
    assert "cold_resident_pages" in issue_codes
