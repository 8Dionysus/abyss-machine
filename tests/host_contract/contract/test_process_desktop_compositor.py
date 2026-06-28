from __future__ import annotations

import json
import subprocess
import sys
import types

import pytest


pytestmark = [pytest.mark.quick, pytest.mark.contract]


def test_atspi_panel_telemetry_timeout_returns_bounded_error(monkeypatch, abyss_machine_module) -> None:
    class FakeRegistry:
        stopped = False

        @staticmethod
        def registerEventListener(callback, event_name):  # noqa: N802 - mirrors pyatspi API
            assert event_name == "object:property-change:accessible-name"

        @staticmethod
        def start():
            raise TimeoutError("atspi_panel_telemetry_timeout")

        @staticmethod
        def stop():
            FakeRegistry.stopped = True

    monkeypatch.setitem(sys.modules, "pyatspi", types.SimpleNamespace(Registry=FakeRegistry))

    result = abyss_machine_module.process_atspi_panel_telemetry_churn(1.0)

    assert result["ok"] is False
    assert result["timed_out"] is True
    assert result["error"] == "atspi_panel_telemetry_timeout"
    assert result["hard_timeout_seconds"] == 2.0
    assert FakeRegistry.stopped is True


def test_atspi_window_probe_code_returns_json_for_import_failure(tmp_path, abyss_machine_module) -> None:
    broken_probe = tmp_path / "abyss-machine"
    broken_probe.write_text("raise RuntimeError('broken probe import')\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-c", abyss_machine_module.process_atspi_window_snapshot_probe_code(str(broken_probe))],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5.0,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert payload["ok"] is False
    assert payload["exception_type"] == "RuntimeError"
    assert "broken probe import" in payload["error"]


def test_atspi_window_probe_code_adds_installed_parent_to_sys_path(tmp_path, abyss_machine_module) -> None:
    package = tmp_path / "abyss_machine"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "fake_dep.py").write_text("VALUE = 'loaded-from-installed-parent'\n", encoding="utf-8")
    probe = tmp_path / "abyss-machine"
    probe.write_text(
        "\n".join(
            [
                "try:",
                "    from . import fake_dep",
                "except ImportError:",
                "    from abyss_machine import fake_dep",
                "def process_atspi_window_snapshot():",
                "    return {'ok': True, 'dep': fake_dep.VALUE}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-c", abyss_machine_module.process_atspi_window_snapshot_probe_code(str(probe))],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5.0,
    )

    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert payload == {"ok": True, "dep": "loaded-from-installed-parent"}


def test_desktop_compositor_guidance_does_not_blame_vitals(abyss_machine_module) -> None:
    result = abyss_machine_module.process_desktop_compositor_assessment(
        samples=[{"cpu_one_core_percent": 18.0, "fd": {"pidfd": 1, "dmabuf": 1}}],
        display={"display": {"current_mode": {"refresh_hz": 120.0}}},
        status_notifiers={"count": 1},
        screen_cast={"active_session_like_paths": 0},
        remote_desktop={"active_session_like_paths": 0},
        shell_signals={"signal_rates_hz": {"WindowsChanged": 0.0, "RunningApplicationsChanged": 0.0}},
        panel_telemetry={"gnome_shell_metric_label_rate_hz": 8.0},
        vitals={"enabled": True},
        gnome_extensions={"enabled_count": 1},
        atspi_windows={"count": 1, "windows": [], "counts_by_app": {}},
        x11_windows={"count": 0, "windows": []},
        wayland_clients={"count": 1},
        desktop_processes={"top": []},
    )

    text = f"{result['route_guidance']} {result['non_claim']}"
    assert "not as proof that Vitals" in text
    assert "preserve best display quality/high refresh" in text
