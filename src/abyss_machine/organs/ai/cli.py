"""AI model runtime management organ CLI, moved out of the abyss_machine core CLI.

`abyss_machine.cli` keeps the `ai` command names and
delegates here lazily. Shared core helpers are reached as `_core.<name>`,
so callers and tests that patch `abyss_machine.cli` keep the same effect.
"""

from __future__ import annotations

import argparse
import array
import concurrent.futures
from contextlib import contextmanager
import datetime as dt
import fcntl
import fnmatch
import grp
import hashlib
import importlib.util
import json
import os
import platform
import re
import resource
import secrets
import signal
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from abyss_machine import cli as _core

_ORGAN_PACKAGE = "abyss_machine.organs.ai"
sys.dont_write_bytecode = True

globals().update(
    {
        "ai_runtime_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.ai_runtime_adapters"),
        "ai_tts_adapters": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.ai_tts_adapters"),
        "ai_tts_contracts": _core._lazy_import_module(f"{_ORGAN_PACKAGE}.ai_tts_contracts"),
    }
)
from abyss_machine.organs.ai import ai_runtime_contracts

dictation_cli = _core._lazy_import_module("abyss_machine.organs.dictation.cli", allow_eager=False)


AI_WORKLOAD_CLASS_LEVELS = ai_runtime_contracts.WORKLOAD_CLASS_LEVELS


AI_EVAL_ROOT = _core.AI_ROOT / "evals"


AI_EVAL_LATEST_PATH = AI_EVAL_ROOT / "latest.json"


AI_STORAGE_CLEANUP_ROOT = _core.AI_ROOT / "storage" / "cleanups"


AI_WORKLOAD_TAXONOMY_PATH = _core.AI_WORKLOAD_ROOT / "taxonomy.json"


AI_WORKLOAD_RUNS_ROOT = _core.AI_WORKLOAD_ROOT / "runs"


AI_WORKLOAD_REFRESH_ROOT = _core.AI_WORKLOAD_ROOT / "refresh"


AI_WORKLOAD_REFRESH_SERVICE = "abyss-ai-workload-refresh.service"


AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH = _core.AI_TOKEN_ACCOUNTING_COUNTS_ROOT / "latest.json"


TOKEN_ACCOUNTING_CONTRACT = ai_runtime_contracts.TOKEN_ACCOUNTING_CONTRACT


TOKEN_ACCOUNTING_SCHEMA_VERSION = ai_runtime_contracts.TOKEN_ACCOUNTING_SCHEMA_VERSION


AI_FIXTURE_ROOT = _core.AI_ROOT / "fixtures"


AI_LLM_WORKHORSE_CONTROLLER = Path("/srv/abyss-machine/tools/abyss-gemma4-e4b-harness")


ABYSS_STACK_READONLY_ROOTS = (
    "/srv/AbyssOS",
    "/srv/AbyssOS/abyss-stack",
    "/srv/abyss-stack",
    str(_core.ABYSS_STACK_USER_SOURCE_ROOT),
)


AI_TTS_INVENTORY_ROOT = _core.AI_TTS_ROOT / "inventory"


AI_TTS_INVENTORY_LATEST_PATH = AI_TTS_INVENTORY_ROOT / "latest.json"


AI_TTS_EVAL_LATEST_PATH = _core.AI_TTS_EVAL_ROOT / "latest.json"


AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT = _core.AI_TTS_EVAL_ROOT / "success"


AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH = _core.AI_TTS_EVAL_ROOT / "latest_success_by_profile.json"


AI_TTS_COMPARE_ROOT = _core.AI_TTS_ROOT / "compare"


AI_TTS_COMPARE_LATEST_PATH = AI_TTS_COMPARE_ROOT / "latest.json"


AI_TTS_SYNTH_ROOT = _core.AI_TTS_ROOT / "synth"


def default_ai_config() -> dict[str, Any]:
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_config_v1",
        "version": _core.VERSION,
        "model_roots": [str(path) for path in _core.AI_MODEL_ROOTS],
        "openvino": {
            "python": str(Path.home() / ".local/bin/abyss-openvino-python"),
            "benchmark_app": str(Path.home() / ".local/bin/abyss-openvino-benchmark"),
            "venv": str(_core.ABYSS_AI_HOME / "openvino-2026.2"),
            "cache_root": str(_core.AI_OPENVINO_CACHE_ROOT),
        },
        "benchmark": {
            "default_devices": ["CPU", "GPU", "NPU"],
            "per_device_timeout_sec": 30,
            "npu_timeout_sec": 60,
            "retention_days": 90,
        },
        "eval": {
            "quick_suites": ["stt", "embeddings", "text"],
            "stt_profiles": ["fast", "quality"],
            "stt_reference_text": "локальный искусственный интеллект готов к работе",
            "stt_similarity_warn_below": 0.35,
            "embedding_model": "/srv/AbyssOS/abyss-stack/Models/ovms/OpenVINO/Qwen3-Embedding-0.6B-int8-ov",
            "embedding_device": "AUTO:GPU,CPU",
            "text_model": "/srv/AbyssOS/abyss-stack/Models/ovms-text-phi35-mini-int4/OpenVINO/Phi-3.5-mini-instruct-int4-ov",
            "text_device": "AUTO:GPU,CPU",
            "text_prompt": "Answer with one short token: 2 + 2 =",
            "timeout_sec": 240,
        },
        "tts": {
            "python": str(Path.home() / ".local/bin/abyss-openvino-python"),
            "default_profile": "quality",
            "eval_text": "Привет. Это проверка локального синтеза речи для Abyss Machine.",
            "language": "Russian",
            "timeout_sec": 300,
            "profiles": {
                "quality": {
                    "enabled": True,
                    "engine": "qwen3_tts_openvino",
                    "model": "/srv/AbyssOS/abyss-stack/Models/hf/local/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                    "speaker": "Ryan",
                    "device": "AUTO:GPU,CPU",
                    "declared_class": "heavy",
                    "description": "High-quality Qwen3-TTS 1.7B bridge target. Runtime must be proven before promotion.",
                },
                "npu-fast-experimental": {
                    "enabled": True,
                    "engine": "babelvox",
                    "python": str(Path.home() / ".local/bin/abyss-babelvox-python"),
                    "model": "host-managed",
                    "device": "NPU",
                    "declared_class": "heavy",
                    "precision": "int8",
                    "use_kv_cache": True,
                    "use_cp_kv_cache": True,
                    "max_kv_len": 64,
                    "max_speaker_frames": 128,
                    "max_decoder_frames": 64,
                    "max_new_tokens": 44,
                    "temperature": 0.8,
                    "top_k": 30,
                    "description": "Experimental Qwen3-TTS 0.6B INT8 OpenVINO NPU KV-cache path; measured but not yet interactive-speed.",
                },
                "gpu-fast-experimental": {
                    "enabled": True,
                    "engine": "babelvox",
                    "python": str(Path.home() / ".local/bin/abyss-babelvox-python"),
                    "model": "host-managed",
                    "device": "GPU",
                    "declared_class": "heavy",
                    "precision": "int8",
                    "use_cp_kv_cache": True,
                    "max_new_tokens": 44,
                    "temperature": 0.8,
                    "top_k": 30,
                    "description": "Experimental Qwen3-TTS 0.6B INT8 OpenVINO GPU path; measured but not yet interactive-speed.",
                },
                "cpu-fast-experimental": {
                    "enabled": True,
                    "engine": "babelvox",
                    "python": str(Path.home() / ".local/bin/abyss-babelvox-python"),
                    "model": "host-managed",
                    "device": "CPU",
                    "declared_class": "heavy",
                    "precision": "int8",
                    "use_cp_kv_cache": True,
                    "max_new_tokens": 44,
                    "temperature": 0.8,
                    "top_k": 30,
                    "description": "Experimental Qwen3-TTS 0.6B INT8 OpenVINO CPU path; measured as fastest short smoke but CPU-heavy.",
                },
                "fallback": {
                    "enabled": False,
                    "engine": "piper",
                    "model": None,
                    "device": "CPU",
                    "declared_class": "light",
                    "description": "Future CPU fallback for short system phrases.",
                },
            },
        },
        "thermal_policy": {
            "warm_temperature_c": 80.0,
            "hot_temperature_c": 106.0,
            "critical_temperature_c": 109.0,
            "rolling_window_sec": 180,
            "rolling_sample_limit": 12,
            "falling_trend_min_c": 3.0,
            "balanced_warm_heavy_max_c": 105.0,
            "thin_laptop_active_range_c": [100.0, 105.0],
            "watch_above_c": 105.0,
            "hard_emergency_temperature_c": 109.0,
            "min_battery_percent_for_heavy": 35,
            "telemetry_max_age_sec": 300,
        },
        "cpu_routing": {
            "avoid_core_temperature_c": 106.0,
            "hard_avoid_core_temperature_c": 109.0,
            "critical_temperature_c": 109.0,
            "package_critical_temperature_c": 109.0,
            "routed_heavy_min_cpus": 4,
            "routed_heavy_max_hot_cpus": 2,
            "routed_heavy_max_critical_cpus": 1,
            "routed_heavy_broad_heat_hot_core_count": 4,
            "routed_heavy_broad_heat_avoid_cpu_count": 6,
            "routed_heavy_block_on_package_hot": False,
            "test_max_seconds": 5.0,
            "thread_limits": {
                "background": 2,
                "probe": 2,
                "light": 3,
                "interactive": 4,
                "medium": 4,
                "heavy": 6,
                "sustained": 6,
            },
        },
        "storage": {
            "largest_files_limit": 30,
            "largest_dirs_limit": 30,
            "duplicate_candidates_limit": 50,
            "cache_dir_name": "model_cache",
        },
        "workload": {
            "retention_days": 180,
            "refresh_from_latest": True,
            "auto_refresh": {
                "run_quick_benchmark": True,
                "allow_on_battery": False,
                "allow_when_hot": False
            },
            "duration_bands_sec": {
                "probe": 1.0,
                "light": 5.0,
                "medium": 30.0,
                "heavy": 180.0
            },
        },
        "inventory": {
            "max_depth": 9,
            "max_entries": 300,
            "include_size_bytes": True,
        },
        "policy": {
            "read_only_stack_roots": True,
            "host_layer_mutates_stack": False,
            "stack_dependency_direction": "abyss-stack may consume abyss-machine; abyss-machine must not import or mutate abyss-stack",
        },
    }


def ai_config() -> dict[str, Any]:
    defaults = default_ai_config()
    loaded, error = _core.load_json_document(_core.AI_CONFIG_PATH)
    if loaded is None:
        config = defaults
        if error != "missing":
            config["_load_error"] = error
    else:
        config = _core.deep_merge(defaults, loaded)
    if not isinstance(config.get("model_roots"), list):
        config["model_roots"] = defaults["model_roots"]
        config["_load_error"] = "model_roots must be a list"
    return config


def ai_openvino_cache_dir(label: str = "general") -> Path:
    path = ai_runtime_contracts.cache_dir_path(_core.AI_OPENVINO_CACHE_ROOT, label)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ai_openvino_cache_path(label: str = "general") -> Path:
    return ai_runtime_contracts.cache_dir_path(_core.AI_OPENVINO_CACHE_ROOT, label)


def ai_model_cache_label(model_path: str | Path, prefix: str) -> str:
    return ai_runtime_contracts.model_cache_label(model_path, prefix)


def ai_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    return ai_runtime_adapters.subprocess_env_binding(
        environ=os.environ,
        machine_cache_root=_core.ABYSS_MACHINE_CACHE_ROOT,
        ai_cache_root=_core.AI_CACHE_ROOT,
        tmp_root=_core.ABYSS_MACHINE_TMP_ROOT,
        openvino_cache_root=_core.AI_OPENVINO_CACHE_ROOT,
        extra=extra,
    )


def ai_config_get() -> dict[str, Any]:
    config = ai_config()
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_config_read_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "path": str(_core.AI_CONFIG_PATH),
        "exists": _core.AI_CONFIG_PATH.exists(),
        "load_error": config.get("_load_error"),
        "config": config,
    }


def ai_benchmark_today_path() -> Path:
    today = dt.datetime.now(dt.timezone.utc).astimezone()
    return _core.AI_BENCHMARK_ROOT / f"{today.year:04d}" / f"{today.month:02d}" / f"{today.strftime('%Y-%m-%d')}.jsonl"


def ai_runtime_path_refs() -> dict[str, Any]:
    return {
        "AI_ROOT": str(_core.AI_ROOT),
        "AI_AGENTS_PATH": str(_core.AI_AGENTS_PATH),
        "AI_INDEX_PATH": str(_core.AI_INDEX_PATH),
        "AI_CONFIG_PATH": str(_core.AI_CONFIG_PATH),
        "AI_DEVICES_LATEST_PATH": str(_core.AI_DEVICES_LATEST_PATH),
        "AI_MODELS_LATEST_PATH": str(_core.AI_MODELS_LATEST_PATH),
        "AI_BENCHMARK_ROOT": str(_core.AI_BENCHMARK_ROOT),
        "AI_BENCHMARK_LATEST_PATH": str(_core.AI_BENCHMARK_LATEST_PATH),
        "AI_BENCHMARK_TODAY_PATH": str(ai_benchmark_today_path()),
        "AI_BENCHMARK_DAILY_GLOB": str(_core.AI_BENCHMARK_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_EVAL_ROOT": str(AI_EVAL_ROOT),
        "AI_EVAL_LATEST_PATH": str(AI_EVAL_LATEST_PATH),
        "AI_EVAL_TODAY_PATH": str(_core.ai_daily_jsonl_path(AI_EVAL_ROOT)),
        "AI_EVAL_DAILY_GLOB": str(AI_EVAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_CAPABILITIES_LATEST_PATH": str(_core.AI_CAPABILITIES_LATEST_PATH),
        "AI_POLICY_LATEST_PATH": str(_core.AI_POLICY_LATEST_PATH),
        "AI_TOKEN_ACCOUNTING_ROOT": str(_core.AI_TOKEN_ACCOUNTING_ROOT),
        "AI_TOKEN_ACCOUNTING_LATEST_PATH": str(_core.AI_TOKEN_ACCOUNTING_LATEST_PATH),
        "AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH": str(_core.AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH),
        "AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH": str(AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH),
        "AI_TOKEN_ACCOUNTING_COUNTS_DAILY_GLOB": str(_core.AI_TOKEN_ACCOUNTING_COUNTS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH": str(_core.AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH),
        "AI_TOKEN_ACCOUNTING_AOA_DAILY_GLOB": str(_core.AI_TOKEN_ACCOUNTING_AOA_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_LLM_PATHS": ai_llm_paths(),
        "AI_LLM_REGISTRY_LATEST_PATH": str(_core.AI_LLM_REGISTRY_LATEST_PATH),
        "AI_LLM_VALIDATE_LATEST_PATH": str(_core.AI_LLM_VALIDATE_LATEST_PATH),
        "AI_CPU_ROOT": str(_core.AI_CPU_ROOT),
        "AI_CPU_TOPOLOGY_LATEST_PATH": str(_core.AI_CPU_TOPOLOGY_LATEST_PATH),
        "AI_CPU_THERMAL_MAP_LATEST_PATH": str(_core.AI_CPU_THERMAL_MAP_LATEST_PATH),
        "AI_CPU_ROUTE_LATEST_PATH": str(_core.AI_CPU_ROUTE_LATEST_PATH),
        "AI_CPU_TEST_LATEST_PATH": str(_core.AI_CPU_TEST_LATEST_PATH),
        "AI_CPU_TEST_DAILY_GLOB": str(_core.AI_CPU_TEST_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "COOLING_AGENTS_PATH": str(_core.COOLING_AGENTS_PATH),
        "COOLING_LATEST_PATH": str(_core.COOLING_LATEST_PATH),
        "COOLING_ACTION_DAILY_GLOB": str(_core.COOLING_ACTION_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "COOLING_CONFIG_PATH": str(_core.COOLING_CONFIG_PATH),
        "STORAGE_LATEST_PATH": str(_core.STORAGE_LATEST_PATH),
        "STORAGE_INDEX_PATH": str(_core.STORAGE_INDEX_PATH),
        "STORAGE_POLICY_PATH": str(_core.STORAGE_POLICY_PATH),
        "STORAGE_POLICY_ENV_PATH": str(_core.STORAGE_POLICY_ENV_PATH),
        "AI_STORAGE_LATEST_PATH": str(_core.AI_STORAGE_LATEST_PATH),
        "AI_STORAGE_CLEANUP_DAILY_GLOB": str(AI_STORAGE_CLEANUP_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "HOOKS_ETC_DIR": str(_core.HOOKS_ETC_DIR),
        "HOOKS_SRV_DIR": str(_core.HOOKS_SRV_DIR),
        "PROCESS_ROOT": str(_core.PROCESS_ROOT),
        "PROCESS_AGENTS_PATH": str(_core.PROCESS_AGENTS_PATH),
        "PROCESS_INDEX_PATH": str(_core.PROCESS_INDEX_PATH),
        "PROCESS_LATEST_PATH": str(_core.PROCESS_LATEST_PATH),
        "PROCESS_SNAPSHOT_DAILY_GLOB": str(_core.PROCESS_SNAPSHOT_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_RUNTIME_LATEST_PATH": str(_core.AI_RUNTIME_LATEST_PATH),
        "AI_RUNTIME_TODAY_PATH": str(_core.ai_daily_jsonl_path(_core.AI_RUNTIME_ROOT)),
        "AI_RUNTIME_DAILY_GLOB": str(_core.AI_RUNTIME_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_REPORT_LATEST_PATH": str(_core.AI_REPORT_LATEST_PATH),
        "AI_REPORT_TODAY_PATH": str(_core.ai_daily_jsonl_path(_core.AI_REPORT_ROOT)),
        "AI_REPORT_DAILY_GLOB": str(_core.AI_REPORT_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_WORKLOAD_ROOT": str(_core.AI_WORKLOAD_ROOT),
        "AI_WORKLOAD_LATEST_PATH": str(_core.AI_WORKLOAD_LATEST_PATH),
        "AI_WORKLOAD_LATEST_EXISTS": _core.AI_WORKLOAD_LATEST_PATH.exists(),
        "AI_WORKLOAD_TAXONOMY_PATH": str(AI_WORKLOAD_TAXONOMY_PATH),
        "AI_WORKLOAD_STATS_LATEST_PATH": str(_core.AI_WORKLOAD_STATS_LATEST_PATH),
        "AI_WORKLOAD_RUNS_TODAY_PATH": str(_core.ai_daily_jsonl_path(AI_WORKLOAD_RUNS_ROOT)),
        "AI_WORKLOAD_RUNS_DAILY_GLOB": str(AI_WORKLOAD_RUNS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_WORKLOAD_REFRESH_TODAY_PATH": str(_core.ai_daily_jsonl_path(AI_WORKLOAD_REFRESH_ROOT)),
        "AI_WORKLOAD_REFRESH_DAILY_GLOB": str(AI_WORKLOAD_REFRESH_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_TTS_ROOT": str(_core.AI_TTS_ROOT),
        "AI_TTS_LATEST_PATH": str(_core.AI_TTS_LATEST_PATH),
        "AI_TTS_INVENTORY_LATEST_PATH": str(AI_TTS_INVENTORY_LATEST_PATH),
        "AI_TTS_PROFILES_LATEST_PATH": str(_core.AI_TTS_PROFILES_LATEST_PATH),
        "AI_TTS_EVAL_LATEST_PATH": str(AI_TTS_EVAL_LATEST_PATH),
        "AI_TTS_EVAL_LATEST_SUCCESS_PATH": str(_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH),
        "AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH": str(AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH),
        "AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT": str(AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT),
        "AI_TTS_EVAL_TODAY_PATH": str(_core.ai_daily_jsonl_path(_core.AI_TTS_EVAL_ROOT)),
        "AI_TTS_EVAL_DAILY_GLOB": str(_core.AI_TTS_EVAL_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_TTS_COMPARE_LATEST_PATH": str(AI_TTS_COMPARE_LATEST_PATH),
        "AI_TTS_SERVER_LATEST_PATH": str(_core.AI_TTS_SERVER_LATEST_PATH),
        "AI_TTS_SYNTH_ROOT": str(AI_TTS_SYNTH_ROOT),
        "AI_TTS_SYNTH_TODAY_PATH": str(_core.ai_daily_jsonl_path(AI_TTS_SYNTH_ROOT).with_suffix("")),
        "AI_TTS_CACHE_ROOT": str(_core.AI_TTS_CACHE_ROOT),
        "AI_FIXTURE_ROOT": str(AI_FIXTURE_ROOT),
        "AI_FIXTURE_STT_RU_SMOKE": str(AI_FIXTURE_ROOT / "stt" / "ru-smoke.wav"),
        "AI_CACHE_ROOT": str(_core.AI_CACHE_ROOT),
        "AI_OPENVINO_CACHE_ROOT": str(_core.AI_OPENVINO_CACHE_ROOT),
        "TOKEN_ACCOUNTING_CONTRACT": TOKEN_ACCOUNTING_CONTRACT,
        "TOKEN_ACCOUNTING_SCHEMA_VERSION": TOKEN_ACCOUNTING_SCHEMA_VERSION,
        "MANIFEST_PATH": str(_core.MANIFEST_PATH),
    }


def ai_paths() -> dict[str, Any]:
    return ai_runtime_contracts.ai_paths_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        refs=ai_runtime_path_refs(),
        stack_model_roots=ai_model_roots(),
        openvino_config=ai_config().get("openvino", {}),
    )


def ai_model_roots() -> list[Path]:
    return ai_runtime_adapters.model_roots(ai_config())


def openvino_runtime_info() -> dict[str, Any]:
    return ai_runtime_adapters.openvino_runtime_info(
        config=ai_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        run_command=_core.run,
        which=shutil.which,
    )


def immediate_file_summary(path: Path, max_files: int = 1000) -> dict[str, Any]:
    return ai_runtime_adapters.immediate_file_summary(path, max_files=max_files)


def ai_models_inventory(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.models_inventory_readmodel(
        config=ai_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        write_latest=write_latest,
        latest_path=_core.AI_MODELS_LATEST_PATH,
        write_json=_core.safe_atomic_write_json,
    )


def ai_tts_config() -> dict[str, Any]:
    config = ai_config()
    tts = config.get("tts", {}) if isinstance(config.get("tts"), dict) else {}
    profiles = tts.get("profiles", {}) if isinstance(tts.get("profiles"), dict) else {}
    return {
        "python": str(tts.get("python") or config.get("openvino", {}).get("python") or ""),
        "default_profile": str(tts.get("default_profile") or "quality"),
        "default_quality": str(tts.get("default_quality") or tts.get("default_profile") or "quality"),
        "default_fast": str(tts.get("default_fast") or "quality-compact"),
        "default_system_voice": str(tts.get("default_system_voice") or tts.get("default_fast") or "quality-compact"),
        "server_profile": str(tts.get("server_profile") or tts.get("default_fast") or "quality-compact"),
        "eval_text": str(tts.get("eval_text") or "Привет. Это проверка локального синтеза речи для Abyss Machine."),
        "language": str(tts.get("language") or "Russian"),
        "timeout_sec": float(tts.get("timeout_sec", 300)),
        "profiles": profiles,
    }


def ai_tts_today_synth_dir() -> Path:
    today = dt.datetime.now(dt.timezone.utc).astimezone()
    return AI_TTS_SYNTH_ROOT / f"{today.year:04d}" / f"{today.month:02d}" / today.strftime("%Y-%m-%d")


def ai_tts_default_output_path(profile: str) -> Path:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", profile).strip("-") or "tts"
    stamp = dt.datetime.now(dt.timezone.utc).astimezone().strftime("%H%M%S")
    return ai_tts_today_synth_dir() / f"{stamp}-{clean}.wav"


def ai_tts_cache_dir(label: str = "general") -> Path:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "general"
    path = _core.AI_TTS_CACHE_ROOT / clean
    path.mkdir(parents=True, exist_ok=True)
    return path


def python_modules_status(python: str, packages: dict[str, str], timeout: float = 10.0) -> dict[str, Any]:
    if not python or not Path(python).exists():
        return {"ok": False, "python": python or None, "error": "python not found", "modules": {}}
    script = r'''
import importlib.metadata as metadata
import importlib.util
import json
import sys

packages = json.loads(sys.argv[1])
modules = {}
for package, module in packages.items():
    found = importlib.util.find_spec(module) is not None
    version = None
    try:
        version = metadata.version(package)
    except metadata.PackageNotFoundError:
        pass
    modules[module] = {"package": package, "present": found, "version": version}
print(json.dumps({"ok": True, "modules": modules}, sort_keys=False))
'''
    out = _core.run([python, "-c", script, json.dumps(packages, sort_keys=True)], timeout=timeout, env=ai_subprocess_env())
    data = _core.parse_json_stdout(out["stdout"])
    if data is None:
        data = {"ok": False, "error": "invalid module status JSON", "stdout_tail": out["stdout"][-1000:], "stderr_tail": out["stderr"][-1000:]}
    data["python"] = python
    data["returncode"] = out["returncode"]
    return data


def ai_tts_profile_python(profile: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    return ai_tts_contracts.profile_python(profile, config or ai_tts_config())


def ai_tts_module_status(python: str | None = None) -> dict[str, Any]:
    packages = {
        "openvino": "openvino",
        "openvino-genai": "openvino_genai",
        "optimum-intel": "optimum",
        "transformers": "transformers",
        "qwen-tts": "qwen_tts",
        "babelvox": "babelvox",
        "pydantic": "pydantic",
        "safetensors": "safetensors",
        "soundfile": "soundfile",
        "librosa": "librosa",
        "scipy": "scipy",
        "numpy": "numpy",
    }
    return python_modules_status(str(python or ai_tts_config().get("python") or ""), packages)


def path_has_file_payload(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    try:
        return any(item.is_file() for item in path.rglob("*"))
    except OSError:
        return False


def ai_tts_host_managed_model_artifacts(profile_name: str) -> dict[str, Any]:
    cache_dir = _core.AI_TTS_CACHE_ROOT / ai_tts_contracts.profile_slug(profile_name)
    exists = cache_dir.exists()
    has_payload = path_has_file_payload(cache_dir)
    data = ai_tts_contracts.model_artifacts(
        "host-managed",
        exists=exists,
        required_files={"cache_payload": has_payload},
        file_summary=immediate_file_summary(cache_dir) if exists and cache_dir.is_dir() else {},
    )
    data["cache_dir"] = str(cache_dir)
    return data


def ai_tts_model_artifacts(model_path: Any, profile_name: str | None = None) -> dict[str, Any]:
    if model_path is None:
        return ai_tts_contracts.model_artifacts(model_path)
    if str(model_path) == "host-managed":
        if profile_name:
            return ai_tts_host_managed_model_artifacts(profile_name)
        return ai_tts_contracts.model_artifacts(model_path)
    path = Path(str(model_path)).expanduser()
    exists = path.exists()
    return ai_tts_contracts.model_artifacts(
        model_path,
        exists=exists,
        required_files={item: (path / item).exists() for item in ai_tts_contracts.TTS_MODEL_REQUIRED_FILES},
        file_summary=immediate_file_summary(path) if exists and path.is_dir() else {},
        read_only_source=any(_core.is_relative_to_path(path, root) for root in ai_model_roots() if root.exists()),
    )


def ai_tts_openvino_artifacts(ov_dir: Any) -> dict[str, Any]:
    if ov_dir is None:
        return ai_tts_contracts.openvino_artifacts(ov_dir)
    path = Path(str(ov_dir)).expanduser()
    exists = path.exists()
    return ai_tts_contracts.openvino_artifacts(
        ov_dir,
        exists=exists,
        required_files={item: (path / item).exists() for item in ai_tts_contracts.TTS_OPENVINO_REQUIRED_FILES},
        file_summary=immediate_file_summary(path) if exists and path.is_dir() else {},
    )


def ai_tts_profile_declared_class(profile: dict[str, Any]) -> str:
    return ai_tts_contracts.profile_declared_class(profile, set(AI_WORKLOAD_CLASS_LEVELS))


def ai_tts_profile_status(name: str, profile: dict[str, Any], inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory = inventory or ai_tts_inventory(write_latest=False)
    config = ai_tts_config()
    runtime_python = ai_tts_profile_python(profile, config)
    model = ai_tts_model_artifacts(profile.get("model"), profile_name=name)
    ov_model = ai_tts_openvino_artifacts(profile.get("ov_dir")) if str(profile.get("engine") or "") == "qwen3_tts_openvino" else None
    adapter_src = Path(str(profile.get("adapter_src") or "")).expanduser()
    return ai_tts_contracts.profile_status(
        name=name,
        profile=profile,
        inventory=inventory,
        config=config,
        model=model,
        openvino_model=ov_model,
        adapter_ready=(adapter_src / "openvino" / "ov_infer.py").exists(),
        runtime_python=runtime_python,
        valid_workload_classes=set(AI_WORKLOAD_CLASS_LEVELS),
    )


def ai_tts_inventory(write_latest: bool = True) -> dict[str, Any]:
    models = ai_models_inventory(write_latest=False)
    tts_entries = [item for item in models.get("entries", []) if "tts" in str(item.get("path", "")).lower()]
    module_status = ai_tts_module_status()
    config = ai_tts_config()
    profile_module_statuses = {
        name: ai_tts_module_status(ai_tts_profile_python(profile, config))
        for name, profile in config.get("profiles", {}).items()
        if isinstance(profile, dict)
    }
    configured_models = {
        name: ai_tts_model_artifacts(profile.get("model"))
        for name, profile in config.get("profiles", {}).items()
        if isinstance(profile, dict)
    }
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_tts_inventory_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "paths": {
            "root": str(_core.AI_TTS_ROOT),
            "inventory_latest": str(AI_TTS_INVENTORY_LATEST_PATH),
            "profiles_latest": str(_core.AI_TTS_PROFILES_LATEST_PATH),
            "eval_latest": str(AI_TTS_EVAL_LATEST_PATH),
            "eval_latest_success": str(_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH),
            "eval_latest_success_by_profile": str(AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH),
            "eval_success_by_profile_root": str(AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT),
            "compare_latest": str(AI_TTS_COMPARE_LATEST_PATH),
            "server_latest": str(_core.AI_TTS_SERVER_LATEST_PATH),
            "synth_root": str(AI_TTS_SYNTH_ROOT),
            "cache": str(_core.AI_TTS_CACHE_ROOT),
        },
        "config": {
            "python": config.get("python"),
            "default_profile": config.get("default_profile"),
            "default_quality": config.get("default_quality"),
            "default_fast": config.get("default_fast"),
            "default_system_voice": config.get("default_system_voice"),
            "server_profile": config.get("server_profile"),
            "language": config.get("language"),
            "profiles": sorted(config.get("profiles", {}).keys()),
        },
        "model_inventory": {
            "source": str(_core.AI_MODELS_LATEST_PATH),
            "tts_entries": tts_entries,
            "configured_models": configured_models,
        },
        "runtime": {
            "python_modules": module_status,
            "profile_python_modules": profile_module_statuses,
            "binaries": {
                "piper": shutil.which("piper"),
                "ffmpeg": shutil.which("ffmpeg"),
                "espeak-ng": shutil.which("espeak-ng"),
            },
            "cache": {
                "path": str(_core.AI_TTS_CACHE_ROOT),
                "exists": _core.AI_TTS_CACHE_ROOT.exists(),
                "size_bytes": _core.directory_size(_core.AI_TTS_CACHE_ROOT) if _core.AI_TTS_CACHE_ROOT.exists() else 0,
            },
        },
        "policy": {
            "read_only_stack_roots": True,
            "host_layer_mutates_stack": False,
            "large_downloads_are_not_implicit": True,
            "profile_python_isolation": True,
        },
        "non_claims": [
            "Inventory proves files and runtime modules only; it does not prove synthesis quality or speed.",
            "Qwen3-TTS model roots are read-only sources for this host bridge.",
        ],
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(AI_TTS_INVENTORY_LATEST_PATH, data, 0o664)
        root_error = _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, data, 0o664)
        errors = [error for error in (latest_error, root_error) if error]
        if errors:
            data["write_errors"] = errors
    return data


def ai_tts_profiles(write_latest: bool = True) -> dict[str, Any]:
    config = ai_tts_config()
    inventory = ai_tts_inventory(write_latest=True)
    profiles = {
        name: ai_tts_profile_status(name, profile, inventory)
        for name, profile in config.get("profiles", {}).items()
        if isinstance(profile, dict)
    }
    summary = {
        "profiles": len(profiles),
        "executable": sum(1 for item in profiles.values() if item.get("status") == "executable"),
        "model_ready_adapter_missing": sum(1 for item in profiles.values() if item.get("status") == "model-ready-adapter-missing"),
        "runtime_missing": sum(1 for item in profiles.values() if item.get("status") == "runtime-missing"),
        "disabled": sum(1 for item in profiles.values() if item.get("status") == "disabled"),
    }
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_tts_profiles_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": bool(profiles),
        "default_profile": config.get("default_profile"),
        "profiles": profiles,
        "summary": summary,
        "paths": {
            "latest": str(_core.AI_TTS_PROFILES_LATEST_PATH),
            "inventory_latest": str(AI_TTS_INVENTORY_LATEST_PATH),
        },
        "policy": {
            "facts_only": True,
            "profile_status_is_not_stack_promotion": True,
        },
    }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(_core.AI_TTS_PROFILES_LATEST_PATH, data, 0o664)
        root_error = _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, data, 0o664)
        errors = [error for error in (latest_error, root_error) if error]
        if errors:
            data["write_errors"] = errors
    return data


def ai_tts_latest_eval() -> dict[str, Any]:
    return _core.load_latest_json(AI_TTS_EVAL_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_tts_eval_latest_read_v1")


def ai_tts_latest_success_eval() -> dict[str, Any]:
    return _core.load_latest_json(_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH, f"{_core.SCHEMA_PREFIX}_ai_tts_eval_latest_success_read_v1")


def ai_tts_profile_slug(profile_name: str) -> str:
    return ai_tts_contracts.profile_slug(profile_name)


def ai_tts_profile_success_path(profile_name: str) -> Path:
    return AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT / f"{ai_tts_profile_slug(profile_name)}.json"


def ai_tts_success_index_entry(data: dict[str, Any], path: Path) -> dict[str, Any]:
    return ai_tts_contracts.success_index_entry(data, path)


def ai_tts_write_profile_success_eval(data: dict[str, Any], update_global: bool = False) -> list[dict[str, Any]]:
    profile_name = str(data.get("profile") or "").strip()
    if not profile_name:
        return [{"path": str(AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT), "error": "successful TTS eval has no profile"}]

    profile_path = ai_tts_profile_success_path(profile_name)
    errors: list[dict[str, Any]] = []
    profile_error = _core.safe_atomic_write_json(profile_path, data, 0o664)
    if profile_error:
        errors.append(profile_error)

    index, _ = _core.load_json_document(AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH)
    if not isinstance(index, dict):
        index = {}
    profiles = index.get("profiles") if isinstance(index.get("profiles"), dict) else {}
    profiles[profile_name] = ai_tts_success_index_entry(data, profile_path)
    index.update({
        "schema": f"{_core.SCHEMA_PREFIX}_ai_tts_eval_latest_success_by_profile_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "profiles": profiles,
        "paths": {
            "root": str(AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT),
            "latest": str(AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH),
        },
        "policy": {
            "facts_only": True,
            "host_layer_mutates_stack": False,
        },
    })
    index_error = _core.safe_atomic_write_json(AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH, index, 0o664)
    if index_error:
        errors.append(index_error)
    if update_global:
        global_error = _core.safe_atomic_write_json(_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH, data, 0o664)
        if global_error:
            errors.append(global_error)
    return errors


def ai_tts_find_success_eval_in_history(profile_name: str) -> dict[str, Any] | None:
    for path in sorted(_core.AI_TTS_EVAL_ROOT.rglob("*.jsonl"), reverse=True):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("ok") and data.get("profile") == profile_name:
                found = dict(data)
                found["history_source"] = str(path)
                return found
    return None


def ai_tts_success_eval_for_profile(profile_name: str, write_back: bool = True) -> dict[str, Any]:
    profile_path = ai_tts_profile_success_path(profile_name)
    data, error = _core.load_json_document(profile_path)
    if data and data.get("ok") and data.get("profile") == profile_name:
        data["read_from"] = str(profile_path)
        return data

    found = ai_tts_find_success_eval_in_history(profile_name)
    if found:
        if write_back:
            ai_tts_write_profile_success_eval(found, update_global=False)
        found["read_from"] = str(profile_path if write_back else found.get("history_source") or "")
        return found

    return {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_tts_eval_profile_success_read_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": False,
        "profile": profile_name,
        "path": str(profile_path),
        "error": error or "missing_success_eval",
        "policy": {
            "no_model_execution": True,
            "rerun_hint": "Use `abyss-machine ai tts compare --run` or `abyss-machine ai tts eval --profile <name> --force` when an explicit fresh measurement is needed.",
        },
    }


def ai_tts_profile_for_request(profile_name: str | None) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    config = ai_tts_config()
    name = str(profile_name or config.get("default_profile") or "quality")
    profiles = config.get("profiles", {})
    raw = profiles.get(name) if isinstance(profiles, dict) else None
    return name, raw if isinstance(raw, dict) else None, config


def ai_tts_denied_result(command: str, profile: str, gate: dict[str, Any]) -> dict[str, Any]:
    return ai_tts_contracts.denied_result(ai_policy_denied_result(command, profile, [profile], gate), profile)


def ai_tts_result_error(result: dict[str, Any]) -> str | None:
    return ai_tts_contracts.result_error(result)


def ai_tts_server_socket_path() -> Path:
    return ai_tts_adapters.server_socket_path(os.environ, os.getuid())


def ai_tts_server_request(payload: dict[str, Any], timeout: float = 2.0, socket_path: Path | None = None) -> dict[str, Any]:
    return ai_tts_adapters.server_request(
        payload=payload,
        socket_path=socket_path or ai_tts_server_socket_path(),
        timeout=timeout,
        path_exists=Path.exists,
    )


def ai_tts_server_status(write_latest: bool = True) -> dict[str, Any]:
    sock_path = ai_tts_server_socket_path()
    probe = ai_tts_adapters.server_status_probe(
        socket_path=sock_path,
        request=ai_tts_server_request,
        path_exists=Path.exists,
    )
    data = ai_tts_contracts.server_status_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        socket_path=sock_path,
        socket_exists=bool(probe["socket_exists"]),
        ping=probe["ping"],
        service=_core.user_systemd_unit("abyss-tts-server.service"),
        latest_path=_core.AI_TTS_SERVER_LATEST_PATH,
    )
    if write_latest:
        error = _core.safe_atomic_write_json(_core.AI_TTS_SERVER_LATEST_PATH, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def ai_tts_server_stop(write_latest: bool = True) -> dict[str, Any]:
    sock_path = ai_tts_server_socket_path()
    probe = ai_tts_adapters.server_stop_probe(
        socket_path=sock_path,
        request=ai_tts_server_request,
        path_exists=Path.exists,
    )
    data = ai_tts_contracts.server_stop_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        socket_path=sock_path,
        socket_exists_after=bool(probe["socket_exists_after"]),
        response=probe["response"],
        service=_core.user_systemd_unit("abyss-tts-server.service"),
        latest_path=_core.AI_TTS_SERVER_LATEST_PATH,
    )
    if write_latest:
        error = _core.safe_atomic_write_json(_core.AI_TTS_SERVER_LATEST_PATH, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def ai_tts_voices(write_latest: bool = True) -> dict[str, Any]:
    profiles = ai_tts_profiles(write_latest=write_latest)
    profile_map = profiles.get("profiles") if isinstance(profiles.get("profiles"), dict) else {}
    voices = ai_tts_contracts.voices_from_profiles(profile_map)
    return ai_tts_contracts.voices_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        default_profile=profiles.get("default_profile"),
        voices=voices,
        server=ai_tts_server_status(write_latest=True),
    )


def ai_tts_server_run(profile_name: str | None = None, socket_path: str | None = None) -> dict[str, Any]:
    profile_key, profile, config = ai_tts_profile_for_request(profile_name)
    if profile is None:
        return {"ok": False, "error": "unknown TTS profile", "profile": profile_key}
    status = ai_tts_profile_status(profile_key, profile)
    if status.get("status") != "executable":
        return {"ok": False, "error": status.get("runtime", {}).get("reason") or f"profile is not executable: {status.get('status')}", "profile": profile_key}
    if str(profile.get("engine") or "") != "qwen3_tts_openvino":
        return {"ok": False, "error": "warm server currently supports qwen3_tts_openvino profiles", "profile": profile_key, "engine": profile.get("engine")}

    try:
        runtime = ai_tts_adapters.load_qwen3_openvino_server_runtime(
            profile_key=profile_key,
            profile=profile,
            config=config,
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            now_iso=_core.now_iso,
            server_pid=os.getpid(),
            default_output_path=ai_tts_default_output_path,
            time_now=time.perf_counter,
        )
    except ai_tts_adapters.Qwen3OpenVINOServerImportError as exc:
        return {"ok": False, "error": f"server import failed: {exc.original!r}", "profile": profile_key}

    sock_path = Path(socket_path).expanduser() if socket_path else ai_tts_server_socket_path()

    server_state = ai_tts_contracts.server_state_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=runtime.started_at,
        profile=profile_key,
        socket_path=sock_path,
        pid=os.getpid(),
        load_sec=runtime.load_sec,
        status=status,
    )
    _core.safe_atomic_write_json(_core.AI_TTS_SERVER_LATEST_PATH, server_state, 0o664)

    return ai_tts_adapters.run_server_loop(
        socket_path=sock_path,
        server_state=server_state,
        profile=profile_key,
        synth_once=runtime.synth_once,
        stopped_at=_core.now_iso,
        unload_model=runtime.unload_model,
    )


def ai_tts_synth(
    profile_name: str | None,
    text: str,
    output: str | None = None,
    force: bool = False,
    allow_download: bool = False,
    use_server: bool = True,
    write_latest: bool = True,
) -> dict[str, Any]:
    resources_before = _core.ai_resource_snapshot()
    profile_key, profile, config = ai_tts_profile_for_request(profile_name)
    if profile is None:
        return ai_tts_contracts.synth_unknown_profile_document(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            profile=profile_key,
        )
    text = str(text or "").strip()
    if not text:
        return ai_tts_contracts.synth_empty_text_document(
            schema_prefix=_core.SCHEMA_PREFIX,
            version=_core.VERSION,
            generated_at=_core.now_iso(),
            profile=profile_key,
        )
    declared = ai_tts_profile_declared_class(profile)
    gate = ai_policy_gate_for_class(declared, f"ai tts synth --profile {profile_key}", force=force)
    if not gate.get("ok"):
        denied = ai_tts_denied_result("ai tts synth", profile_key, gate)
        denied["resource_profile"] = _core.ai_resource_profile(resources_before, _core.ai_resource_snapshot(), "policy_check_only", "TTS synth denied before model execution")
        return denied

    profiles_status = ai_tts_profiles(write_latest=True)
    status = profiles_status.get("profiles", {}).get(profile_key, {})
    out_path = Path(output).expanduser() if output else ai_tts_default_output_path(profile_key)
    engine = str(profile.get("engine") or "unknown")
    cache_dir = ai_tts_cache_dir(profile_key)
    result = ai_tts_contracts.synth_base_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        profile=profile_key,
        engine=engine,
        declared_class=declared,
        device=profile.get("device"),
        model=status.get("model"),
        text_chars=len(text),
        output=out_path,
        cache_dir=cache_dir,
        allow_download=bool(allow_download),
        policy_gate=gate,
        profile_status=status,
        output_under_host_state=_core.is_relative_to_path(out_path, AI_TTS_SYNTH_ROOT),
    )
    if status.get("status") != "executable":
        result["error"] = status.get("runtime", {}).get("reason") or f"profile is not executable: {status.get('status')}"
        result["resource_profile"] = _core.ai_resource_profile(resources_before, _core.ai_resource_snapshot(), "policy_and_runtime_check_only", "TTS synth stopped before model execution")
        if write_latest:
            _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, result, 0o664)
        return result

    out_path.parent.mkdir(parents=True, exist_ok=True)
    python = ai_tts_profile_python(profile, config)
    env = ai_tts_adapters.synth_subprocess_env(
        cache_root=_core.AI_TTS_CACHE_ROOT,
        allow_download=allow_download,
        build_env=ai_subprocess_env,
    )

    started = time.monotonic()
    if engine == "qwen3_tts_openvino" and use_server and os.environ.get("ABYSS_TTS_NO_SERVER", "").lower() not in {"1", "true", "yes"}:
        server_started = time.monotonic()
        server_response = ai_tts_server_request(
            ai_tts_contracts.synth_server_request_payload(
                profile=profile_key,
                text=text,
                output=out_path,
                speaker=profile.get("speaker"),
                language=profile.get("language") or config.get("language"),
                instruct=profile.get("instruct"),
                options=ai_tts_contracts.synth_options(profile),
            ),
            timeout=float(config.get("timeout_sec", 300)),
        )
        result["server_attempt"] = ai_tts_contracts.synth_server_attempt(
            socket_path=ai_tts_server_socket_path(),
            elapsed_sec=time.monotonic() - server_started,
            response=server_response,
        )
        if server_response.get("ok") and out_path.exists():
            result["server"] = server_response
            result["ok"] = True
            result = ai_tts_adapters.synth_runtime_report(
                result=result,
                output=out_path,
                started_at=started,
                time_now=time.monotonic,
                resources_before=resources_before,
                resource_snapshot=_core.ai_resource_snapshot,
                resource_profile=_core.ai_resource_profile,
                scope="warm_server_client",
                basis="TTS synth through persistent warm server",
                path_exists=Path.exists,
            )
            if write_latest:
                _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, result, 0o664)
            return result

    result.update(
        ai_tts_adapters.synth_subprocess(
            engine=engine,
            python=python,
            profile=profile,
            config=config,
            text=text,
            output=out_path,
            cache_dir=cache_dir,
            timeout_sec=float(config.get("timeout_sec", 300)),
            subprocess_env=env,
            run_command=_core.run,
            path_exists=Path.exists,
        )
    )

    result = ai_tts_adapters.synth_runtime_report(
        result=result,
        output=out_path,
        started_at=started,
        time_now=time.monotonic,
        resources_before=resources_before,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
        scope="child_process",
        basis="TTS synth subprocess",
        path_exists=Path.exists,
    )
    if write_latest:
        _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, result, 0o664)
    return result


def ai_tts_eval(profile_name: str | None, force: bool = False, allow_download: bool = False, write_latest: bool = True) -> dict[str, Any]:
    profile_key, profile, config = ai_tts_profile_for_request(profile_name)
    text = str(config.get("eval_text") or "Привет. Это проверка локального синтеза речи для Abyss Machine.")
    output = ai_tts_default_output_path(f"eval-{profile_key}")
    synth = ai_tts_synth(profile_key, text, str(output), force=force, allow_download=allow_download, write_latest=False)
    data = ai_tts_contracts.eval_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        profile=profile_key,
        declared_class=ai_tts_profile_declared_class(profile or {}),
        text=text,
        synth=synth,
        latest_path=AI_TTS_EVAL_LATEST_PATH,
        latest_success_path=_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH,
        daily_path=_core.ai_daily_jsonl_path(_core.AI_TTS_EVAL_ROOT),
    )
    if write_latest:
        latest_error = _core.safe_atomic_write_json(AI_TTS_EVAL_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(_core.AI_TTS_EVAL_ROOT), data, 0o664)
        root_error = _core.safe_atomic_write_json(_core.AI_TTS_LATEST_PATH, data, 0o664)
        success_errors = ai_tts_write_profile_success_eval(data, update_global=True) if data.get("ok") else []
        errors = [error for error in (latest_error, daily_error, root_error) if error] + success_errors
        if errors:
            data["write_errors"] = errors
        data["workload_update"] = ai_workload_append_measurements(ai_workload_measurements_from_tts_eval(data), write_stats=True)
    return data


def ai_tts_compare(
    profile_names: list[str] | None = None,
    force: bool = False,
    allow_download: bool = False,
    write_latest: bool = True,
    run_evals: bool = False,
) -> dict[str, Any]:
    config = ai_tts_config()
    requested = profile_names or ["quality", "quality-compact"]
    if run_evals:
        results = [ai_tts_eval(name, force=force, allow_download=allow_download, write_latest=True) for name in requested]
        evidence_source = "fresh_eval"
    else:
        results = [ai_tts_success_eval_for_profile(name, write_back=True) for name in requested]
        evidence_source = "latest_success_by_profile"
    data = ai_tts_contracts.compare_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        requested_profiles=requested,
        evidence_source=evidence_source,
        results=results,
        latest_path=AI_TTS_COMPARE_LATEST_PATH,
        daily_path=_core.ai_daily_jsonl_path(AI_TTS_COMPARE_ROOT),
        latest_success_path=_core.AI_TTS_EVAL_LATEST_SUCCESS_PATH,
        latest_success_by_profile_path=AI_TTS_EVAL_LATEST_SUCCESS_BY_PROFILE_PATH,
        success_by_profile_root=AI_TTS_EVAL_SUCCESS_BY_PROFILE_ROOT,
    )
    if not run_evals and (force or allow_download):
        data["ignored_eval_options"] = {
            "force": bool(force),
            "allow_download": bool(allow_download),
            "reason": "compare reads indexed successful evals by default; add --run to execute fresh evals",
        }
    if write_latest:
        latest_error = _core.safe_atomic_write_json(AI_TTS_COMPARE_LATEST_PATH, data, 0o664)
        daily_error = _core.safe_append_jsonl(_core.ai_daily_jsonl_path(AI_TTS_COMPARE_ROOT), data, 0o664)
        errors = [error for error in (latest_error, daily_error) if error]
        if errors:
            data["write_errors"] = errors
    return data


def ai_latest_benchmark() -> dict[str, Any]:
    data, error = _core.load_json_document(_core.AI_BENCHMARK_LATEST_PATH)
    if data is None:
        return {
            "schema": f"{_core.SCHEMA_PREFIX}_ai_benchmark_latest_read_v1",
            "version": _core.VERSION,
            "generated_at": _core.now_iso(),
            "ok": False,
            "path": str(_core.AI_BENCHMARK_LATEST_PATH),
            "error": error or "missing",
        }
    data["read_at"] = _core.now_iso()
    return data


def ai_openvino_smoke_device(device: str, timeout_sec: float) -> dict[str, Any]:
    python = shutil.which("abyss-openvino-python") or str(ai_config().get("openvino", {}).get("python", ""))
    return ai_runtime_adapters.openvino_smoke_device(
        device=device,
        timeout_sec=timeout_sec,
        python=python,
        run_command=_core.run,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
    )


def ai_benchmark_quick(devices: list[str] | None = None, write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.run_openvino_benchmark_suite(
        devices=devices,
        config=ai_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        policy_gate=ai_policy_gate_for_class,
        runtime_info=openvino_runtime_info,
        smoke_device=ai_openvino_smoke_device,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
        write_latest=write_latest,
        latest_path=_core.AI_BENCHMARK_LATEST_PATH,
        daily_path=ai_benchmark_today_path,
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
        workload_update=lambda data: ai_workload_append_measurements(
            ai_workload_measurements_from_benchmark(dict(data)),
            write_stats=True,
        ),
    )


def ensure_stt_fixture(reference_text: str) -> dict[str, Any]:
    return ai_runtime_adapters.stt_eval_fixture(
        reference_text=reference_text,
        fixture=AI_FIXTURE_ROOT / "stt" / "ru-smoke.wav",
        command_exists=_core.command_exists,
        run_command=_core.run,
    )


def ai_eval_stt() -> dict[str, Any]:
    config = ai_config()
    eval_config = config.get("eval", {}) if isinstance(config.get("eval"), dict) else {}
    reference = str(eval_config.get("stt_reference_text") or "локальный искусственный интеллект готов к работе")
    profiles = eval_config.get("stt_profiles")
    if not isinstance(profiles, list):
        profiles = ["fast", "quality"]
    fixture = ensure_stt_fixture(reference)
    warn_threshold = float(eval_config.get("stt_similarity_warn_below", 0.35))
    return ai_runtime_adapters.stt_eval_run(
        reference_text=reference,
        fixture=fixture,
        profiles=[str(item) for item in profiles],
        similarity_warn_below=warn_threshold,
        transcribe_audio=dictation_cli.dictation_transcribe,
        monotonic=time.monotonic,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
    )


def ai_eval_embeddings() -> dict[str, Any]:
    config = ai_config()
    eval_config = config.get("eval", {}) if isinstance(config.get("eval"), dict) else {}
    model_dir = Path(str(eval_config.get("embedding_model")))
    device = str(eval_config.get("embedding_device") or "AUTO:GPU,CPU")
    cache_dir = ai_openvino_cache_dir(ai_model_cache_label(model_dir, "embedding"))
    python = shutil.which("abyss-openvino-python") or str(config.get("openvino", {}).get("python", ""))
    return ai_runtime_adapters.openvino_embedding_eval(
        model_dir=model_dir,
        device=device,
        cache_dir=cache_dir,
        timeout_sec=float(eval_config.get("timeout_sec", 240)),
        python=python,
        subprocess_env=ai_subprocess_env(),
        run_command=_core.run,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
    )


def ai_eval_text() -> dict[str, Any]:
    config = ai_config()
    eval_config = config.get("eval", {}) if isinstance(config.get("eval"), dict) else {}
    model_dir = Path(str(eval_config.get("text_model")))
    device = str(eval_config.get("text_device") or "AUTO:GPU,CPU")
    prompt = str(eval_config.get("text_prompt") or "Answer with one short token: 2 + 2 =")
    cache_dir = ai_openvino_cache_dir(ai_model_cache_label(model_dir, "text"))
    python = shutil.which("abyss-openvino-python") or str(config.get("openvino", {}).get("python", ""))
    return ai_runtime_adapters.openvino_text_eval(
        model_dir=model_dir,
        device=device,
        cache_dir=cache_dir,
        prompt=prompt,
        timeout_sec=float(eval_config.get("timeout_sec", 240)),
        python=python,
        subprocess_env=ai_subprocess_env(),
        run_command=_core.run,
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
    )


def ai_eval_suites_for_request(suite: str, config: dict[str, Any] | None = None) -> list[str]:
    config = config or ai_config()
    eval_config = config.get("eval", {}) if isinstance(config.get("eval"), dict) else {}
    return ai_runtime_contracts.eval_suites_for_request(suite, eval_config)


def ai_eval_suite_declared_class(suite: str) -> str:
    return ai_runtime_contracts.eval_suite_declared_class(suite)


def ai_highest_workload_class(classes: list[str]) -> str:
    return ai_runtime_contracts.highest_workload_class(classes, AI_WORKLOAD_CLASS_LEVELS)


def ai_policy_gate_for_class(declared_class: str, operation: str, force: bool = False) -> dict[str, Any]:
    return ai_runtime_adapters.policy_gate_binding(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        declared_class=declared_class,
        operation=operation,
        policy=ai_policy,
        force=force,
        class_levels=AI_WORKLOAD_CLASS_LEVELS,
    )


def ai_policy_denied_result(command: str, requested_suite: str, suites: list[str], gate: dict[str, Any]) -> dict[str, Any]:
    return ai_runtime_contracts.policy_denied_result(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        command=command,
        requested_suite=requested_suite,
        suites=suites,
        gate=gate,
    )


def ai_eval_quick(suite: str = "quick", write_latest: bool = True, force: bool = False) -> dict[str, Any]:
    return ai_runtime_adapters.run_eval_suite(
        requested_suite=suite,
        config=ai_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        class_levels=AI_WORKLOAD_CLASS_LEVELS,
        policy_gate=ai_policy_gate_for_class,
        suite_runners={
            "stt": ai_eval_stt,
            "embeddings": ai_eval_embeddings,
            "text": ai_eval_text,
        },
        resource_snapshot=_core.ai_resource_snapshot,
        resource_profile=_core.ai_resource_profile,
        openvino_cache_root=_core.AI_OPENVINO_CACHE_ROOT,
        write_latest=write_latest,
        latest_path=AI_EVAL_LATEST_PATH,
        daily_path=lambda: _core.ai_daily_jsonl_path(AI_EVAL_ROOT),
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
        workload_update=lambda data: ai_workload_append_measurements(
            ai_workload_measurements_from_eval(dict(data)),
            write_stats=True,
        ),
        force=force,
    )


def ai_latest_eval() -> dict[str, Any]:
    return _core.load_latest_json(AI_EVAL_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_eval_latest_read_v1")


def ai_workload_slug(value: Any) -> str:
    return ai_runtime_contracts.workload_slug(value)


def ai_workload_taxonomy(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.workload_taxonomy(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        class_levels=AI_WORKLOAD_CLASS_LEVELS,
        write_latest=write_latest,
        taxonomy_path=AI_WORKLOAD_TAXONOMY_PATH,
        write_json=_core.safe_atomic_write_json,
    )


def ai_workload_numeric(value: Any) -> float | None:
    return ai_runtime_contracts.workload_numeric(value)


def ai_workload_token_int(value: Any) -> int | None:
    return ai_runtime_contracts.workload_token_int(value)


def ai_workload_token_accounting(source: Any, *, duration_sec: float | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    return ai_runtime_contracts.workload_token_accounting(source, duration_sec=duration_sec)


def ai_workload_component_sum(metrics: dict[str, Any], keys: list[str]) -> float | None:
    return ai_runtime_contracts.workload_component_sum(metrics, keys)


def ai_workload_record_id(parts: list[Any]) -> str:
    return ai_runtime_contracts.workload_record_id(parts)


def ai_workload_duration_band(seconds: float | None, config: dict[str, Any] | None = None) -> str | None:
    return ai_runtime_contracts.workload_duration_band(seconds, config or ai_config())


def ai_workload_base_record(source: dict[str, Any], workload_id: str, workload_class: str, capability: str, operation: str) -> dict[str, Any]:
    return ai_runtime_contracts.workload_base_record(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        recorded_at=_core.now_iso(),
        source=source,
        workload_id=workload_id,
        workload_class=workload_class,
        capability=capability,
        operation=operation,
    )


def ai_workload_measurements_from_benchmark(data: dict[str, Any]) -> list[dict[str, Any]]:
    return ai_runtime_contracts.workload_measurements_from_benchmark(
        data,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        recorded_at=_core.now_iso(),
        benchmark_latest_path=str(_core.AI_BENCHMARK_LATEST_PATH),
        config=ai_config(),
    )


def ai_workload_measurements_from_eval(data: dict[str, Any]) -> list[dict[str, Any]]:
    return ai_runtime_contracts.workload_measurements_from_eval(
        data,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        recorded_at=_core.now_iso(),
        eval_latest_path=str(AI_EVAL_LATEST_PATH),
        dictation_profile_defs=dictation_cli.dictation_profiles(),
        config=ai_config(),
    )


def ai_workload_measurements_from_resident_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    return ai_runtime_contracts.workload_measurements_from_resident_audit(
        data,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        recorded_at=_core.now_iso(),
        resident_audit_latest_path=str(_core.AI_LLM_RESIDENT_AUDIT_LATEST_PATH),
        config=ai_config(),
    )


def ai_workload_measurements_from_tts_eval(data: dict[str, Any]) -> list[dict[str, Any]]:
    return ai_runtime_contracts.workload_measurements_from_tts_eval(
        data,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        recorded_at=_core.now_iso(),
        tts_eval_latest_path=str(AI_TTS_EVAL_LATEST_PATH),
        class_levels=AI_WORKLOAD_CLASS_LEVELS,
        config=ai_config(),
    )


def ai_workload_measurement_files() -> list[Path]:
    return ai_runtime_adapters.workload_measurement_files(AI_WORKLOAD_RUNS_ROOT)


def ai_workload_read_measurements() -> list[dict[str, Any]]:
    return ai_runtime_adapters.workload_read_measurements(AI_WORKLOAD_RUNS_ROOT)


def ai_workload_append_measurements(records: list[dict[str, Any]], write_stats: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.workload_append_measurements(
        records,
        runs_root=AI_WORKLOAD_RUNS_ROOT,
        runs_daily_path=lambda: _core.ai_daily_jsonl_path(AI_WORKLOAD_RUNS_ROOT),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        append_jsonl=_core.safe_append_jsonl,
        stats_latest_path=_core.AI_WORKLOAD_STATS_LATEST_PATH,
        stats_update=lambda: ai_workload_stats(write_latest=True),
        write_stats=write_stats,
    )


def ai_workload_refresh_from_latest() -> dict[str, Any]:
    return ai_runtime_adapters.workload_refresh_from_latest(
        latest_benchmark=ai_latest_benchmark(),
        latest_eval=ai_latest_eval(),
        latest_tts_eval=ai_tts_latest_eval(),
        latest_resident_audit=_core.load_latest_json(_core.AI_LLM_RESIDENT_AUDIT_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_llm_resident_audit_latest_read_v1"),
        schema_prefix=_core.SCHEMA_PREFIX,
        benchmark_measurements=ai_workload_measurements_from_benchmark,
        eval_measurements=ai_workload_measurements_from_eval,
        tts_eval_measurements=ai_workload_measurements_from_tts_eval,
        resident_audit_measurements=ai_workload_measurements_from_resident_audit,
        append_measurements=ai_workload_append_measurements,
    )


def ai_workload_refresh(write_latest: bool = True, run_probe: bool | None = None) -> dict[str, Any]:
    config = ai_config()
    policy = ai_policy(write_latest=True)
    return ai_runtime_adapters.workload_refresh(
        config=config,
        policy=policy,
        run_probe=run_probe,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        benchmark_runner=lambda: ai_benchmark_quick(write_latest=True),
        refresh_from_latest=ai_workload_refresh_from_latest,
        stats=lambda: ai_workload_stats(write_latest=True),
        stats_latest_path=_core.AI_WORKLOAD_STATS_LATEST_PATH,
        write_latest=write_latest,
        refresh_daily_path=lambda: _core.ai_daily_jsonl_path(AI_WORKLOAD_REFRESH_ROOT),
        append_jsonl=_core.safe_append_jsonl,
    )


def ai_workload_metric_stats(values: list[float]) -> dict[str, Any]:
    return ai_runtime_contracts.workload_metric_stats(values)


def ai_workload_stats(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.workload_stats(
        config=ai_config(),
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        runs_root=AI_WORKLOAD_RUNS_ROOT,
        runs_daily_glob=str(AI_WORKLOAD_RUNS_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        latest_path=_core.AI_WORKLOAD_STATS_LATEST_PATH,
        write_latest=write_latest,
        write_json=_core.safe_atomic_write_json,
        records=ai_workload_read_measurements(),
    )


def ai_workload_route_level(policy: dict[str, Any]) -> tuple[int, str]:
    return ai_runtime_contracts.policy_workload_route_level(policy)


def ai_workload_status(write_latest: bool = True, refresh_from_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.workload_status(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        taxonomy=lambda: ai_workload_taxonomy(write_latest=True),
        refresh_from_latest=ai_workload_refresh_from_latest,
        stats=lambda: ai_workload_stats(write_latest=True),
        policy=lambda: ai_policy(write_latest=True),
        refresh_from_latest_enabled=refresh_from_latest,
        paths={
            "root": str(_core.AI_WORKLOAD_ROOT),
            "latest": str(_core.AI_WORKLOAD_LATEST_PATH),
            "taxonomy": str(AI_WORKLOAD_TAXONOMY_PATH),
            "stats_latest": str(_core.AI_WORKLOAD_STATS_LATEST_PATH),
            "runs_today": str(_core.ai_daily_jsonl_path(AI_WORKLOAD_RUNS_ROOT)),
            "refresh_today": str(_core.ai_daily_jsonl_path(AI_WORKLOAD_REFRESH_ROOT)),
        },
        auto_refresh={
            "service": _core.systemd_unit(AI_WORKLOAD_REFRESH_SERVICE),
            "timer": _core.systemd_unit(_core.AI_WORKLOAD_REFRESH_TIMER),
            "command": "abyss-machine ai workload refresh --json",
        },
        write_latest=write_latest,
        latest_path=_core.AI_WORKLOAD_LATEST_PATH,
        write_json=_core.safe_atomic_write_json,
    )


def ai_llm_path_refs() -> dict[str, Any]:
    today = _core.ai_daily_jsonl_path(_core.AI_LLM_REGISTRY_ROOT)
    return {
        "AI_LLM_ROOT": str(_core.AI_LLM_ROOT),
        "AI_LLM_AGENTS_PATH": str(_core.AI_LLM_ROOT / "AGENTS.md"),
        "AI_CONFIG_PATH": str(_core.AI_CONFIG_PATH),
        "AI_LLM_REGISTRY_ROOT": str(_core.AI_LLM_REGISTRY_ROOT),
        "AI_LLM_REGISTRY_LATEST_PATH": str(_core.AI_LLM_REGISTRY_LATEST_PATH),
        "AI_LLM_REGISTRY_TODAY_PATH": str(today),
        "AI_LLM_REGISTRY_DAILY_GLOB": str(_core.AI_LLM_REGISTRY_ROOT / "YYYY" / "MM" / "YYYY-MM-DD.jsonl"),
        "AI_LLM_VALIDATE_ROOT": str(_core.AI_LLM_VALIDATE_ROOT),
        "AI_LLM_VALIDATE_LATEST_PATH": str(_core.AI_LLM_VALIDATE_LATEST_PATH),
        "AI_LLM_RESIDENT_ROOT": str(_core.AI_LLM_RESIDENT_ROOT),
        "AI_LLM_RESIDENT_CONTROLLER": str(_core.AI_LLM_RESIDENT_CONTROLLER),
        "AI_LLM_RESIDENT_STATUS_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "status" / "latest.json"),
        "AI_LLM_RESIDENT_MONITOR_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "monitor" / "latest.json"),
        "AI_LLM_RESIDENT_DIGEST_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "digests" / "latest.json"),
        "AI_LLM_RESIDENT_JOBS_ROOT": str(_core.AI_LLM_RESIDENT_ROOT / "jobs"),
        "AI_LLM_RESIDENT_JOBS_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "jobs" / "latest.json"),
        "AI_LLM_RESIDENT_MICRO_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "jobs" / "micro" / "latest.json"),
        "AI_LLM_RESIDENT_JOBS_VALIDATE_LATEST_PATH": str(_core.AI_LLM_RESIDENT_ROOT / "jobs" / "validate" / "latest.json"),
        "AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH": str(_core.AI_LLM_RESIDENT_CANDIDATES_LATEST_PATH),
        "AI_LLM_RESIDENT_CANDIDATES_VALIDATE_LATEST_PATH": str(_core.AI_LLM_RESIDENT_CANDIDATES_VALIDATE_LATEST_PATH),
        "AI_LLM_RESIDENT_EVALS_LATEST_PATH": str(_core.AI_LLM_RESIDENT_EVALS_LATEST_PATH),
        "AI_LLM_RESIDENT_EVALS_VALIDATE_LATEST_PATH": str(_core.AI_LLM_RESIDENT_EVALS_VALIDATE_LATEST_PATH),
        "AI_LLM_RESIDENT_JOB_NAMES": _core.AI_LLM_RESIDENT_JOB_NAMES,
        "AI_LLM_WORKHORSE_ROOT": str(_core.AI_LLM_WORKHORSE_ROOT),
        "AI_LLM_WORKHORSE_CONTROLLER": str(AI_LLM_WORKHORSE_CONTROLLER),
        "AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH": str(_core.AI_LLM_WORKHORSE_PREFLIGHT_LATEST_PATH),
        "AI_LLM_WORKHORSE_PACK_LATEST_PATH": str(_core.AI_LLM_WORKHORSE_PACK_LATEST_PATH),
        "AI_LLM_WORKHORSE_REVIEW_LATEST_PATH": str(_core.AI_LLM_WORKHORSE_REVIEW_LATEST_PATH),
        "AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH": str(_core.AI_LLM_WORKHORSE_VALIDATE_LATEST_PATH),
        "AI_CACHE_ROOT": str(_core.AI_CACHE_ROOT),
    }


def ai_llm_paths() -> dict[str, Any]:
    return ai_runtime_contracts.llm_paths_document(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        generated_at=_core.now_iso(),
        refs=ai_llm_path_refs(),
        config=ai_llm_config(),
    )


def ai_llm_default_config() -> dict[str, Any]:
    runtime_root = _core.ABYSS_MACHINE_RUNTIME_ROOT / "llama.cpp" / "05ff59c" / "llama-05ff59c-vulkan"
    gemma_root = _core.AI_CACHE_ROOT / "gemma4"
    return {
        "backend": "llama.cpp",
        "model_root_base": str(_core.AI_CACHE_ROOT),
        "runtime": {
            "name": "llama.cpp",
            "version": "05ff59c",
            "release_url": "https://github.com/ggml-org/llama.cpp/commit/05ff59cb57860cc992fc6dcede32c696efea711c",
            "root": str(runtime_root),
            "llama_cli": str(runtime_root / "llama-cli"),
            "llama_server": str(runtime_root / "llama-server"),
            "llama_bench": str(runtime_root / "llama-bench"),
            "backend": "vulkan+cpu",
            "source": "local host-managed build from ggml-org/llama.cpp master commit 05ff59cb57860cc992fc6dcede32c696efea711c with GGML_VULKAN=ON",
        },
        "families": {
            "gemma4": {
                "status": "candidate",
                "provider": "google",
                "format_provider": "unsloth",
                "license": "apache-2.0",
                "upstream": {
                    "announcement": "https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/",
                    "e2b": "https://huggingface.co/google/gemma-4-E2B-it",
                    "e4b": "https://huggingface.co/google/gemma-4-E4B-it",
                    "gguf_e2b": "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF",
                    "gguf_e4b": "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF",
                },
                "local_root": str(gemma_root),
                "notes": [
                    "Gemma 4 GGUF requires a fresh llama.cpp build; Fedora b6153 is too old for this route.",
                    "Profiles are host-managed evidence and do not promote abyss-stack serving by themselves.",
                    "MMProj files are optional multimodal bridge material; text profiles must work without them.",
                ],
                "profiles": {
                    "spark": {
                        "role": "resident_small_brain",
                        "model_id": "unsloth/gemma-4-E2B-it-GGUF",
                        "revision": "90f9618340396838ee7ff5b0ba2da27da62953d3",
                        "hf_file": "gemma-4-E2B-it-UD-Q4_K_XL.gguf",
                        "local_path": str(gemma_root / "e2b" / "gemma-4-E2B-it-UD-Q4_K_XL.gguf"),
                        "mmproj_file": "mmproj-F16.gguf",
                        "mmproj_path": str(gemma_root / "e2b" / "mmproj-F16.gguf"),
                        "declared_class": "medium",
                        "warm_policy": "resident_candidate_after_latency_eval",
                        "context_size": 8192,
                        "gpu_layers": 99,
                        "quant": "UD-Q4_K_XL",
                    },
                    "workhorse": {
                        "role": "on_demand_better_reasoning",
                        "model_id": "unsloth/gemma-4-E4B-it-GGUF",
                        "revision": "653803f092503c04a65164346f3208a36e707693",
                        "hf_file": "gemma-4-E4B-it-UD-Q5_K_XL.gguf",
                        "local_path": str(gemma_root / "e4b" / "gemma-4-E4B-it-UD-Q5_K_XL.gguf"),
                        "mmproj_file": "mmproj-F16.gguf",
                        "mmproj_path": str(gemma_root / "e4b" / "mmproj-F16.gguf"),
                        "declared_class": "heavy",
                        "warm_policy": "on_demand_warm_after_resource_gate",
                        "context_size": 8192,
                        "gpu_layers": 99,
                        "quant": "UD-Q5_K_XL",
                    },
                },
            }
        },
    }


def ai_llm_config() -> dict[str, Any]:
    config = ai_config()
    defaults = ai_llm_default_config()
    raw = config.get("llm") if isinstance(config.get("llm"), dict) else {}
    merged = defaults | raw
    if isinstance(defaults.get("runtime"), dict) or isinstance(raw.get("runtime"), dict):
        merged["runtime"] = (defaults.get("runtime") or {}) | (raw.get("runtime") or {})
    if isinstance(defaults.get("families"), dict) or isinstance(raw.get("families"), dict):
        families = dict(defaults.get("families") or {})
        for family, value in (raw.get("families") or {}).items():
            if isinstance(value, dict) and isinstance(families.get(family), dict):
                family_merged = dict(families[family])
                family_merged.update(value)
                if isinstance(families[family].get("profiles"), dict) or isinstance(value.get("profiles"), dict):
                    profiles = dict(families[family].get("profiles") or {})
                    for profile, profile_value in (value.get("profiles") or {}).items():
                        if isinstance(profile_value, dict) and isinstance(profiles.get(profile), dict):
                            profile_merged = dict(profiles[profile])
                            profile_merged.update(profile_value)
                            profiles[profile] = profile_merged
                        else:
                            profiles[profile] = profile_value
                    family_merged["profiles"] = profiles
                families[family] = family_merged
            else:
                families[family] = value
        merged["families"] = families
    return merged


def ai_llm_runtime_status(config: dict[str, Any] | None = None, runtime_override: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config if isinstance(config, dict) else ai_llm_config()
    return ai_runtime_adapters.llm_runtime_status(
        config,
        runtime_override=runtime_override,
        run_command=_core.run,
    )


def ai_llm_profile_status(family_name: str, profile_name: str, profile: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    return ai_runtime_adapters.llm_profile_status(
        family_name=family_name,
        profile_name=profile_name,
        profile=profile,
        runtime=runtime,
        cache_root=_core.AI_CACHE_ROOT,
        storage_protection=_core.storage_path_protection,
        is_relative_to_path=_core.is_relative_to_path,
    )


def ai_llm_registry(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.llm_registry_readmodel(
        config=ai_llm_config(),
        runtime_status=ai_llm_runtime_status,
        profile_status=ai_llm_profile_status,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        registry_latest_path=_core.AI_LLM_REGISTRY_LATEST_PATH,
        registry_daily_path=_core.ai_daily_jsonl_path(_core.AI_LLM_REGISTRY_ROOT),
        validate_latest_path=_core.AI_LLM_VALIDATE_LATEST_PATH,
        write_latest=write_latest,
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
    )


def ai_llm_latest() -> dict[str, Any]:
    return ai_runtime_adapters.llm_latest_readmodel(
        latest_path=_core.AI_LLM_REGISTRY_LATEST_PATH,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        read_json=_core.load_json_document,
    )


def ai_llm_validate(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.llm_validate_readmodel_from_live_inputs(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        config=ai_llm_config(),
        registry=ai_llm_registry,
        token_profiles=ai_token_accounting_profiles,
        paths=ai_llm_paths,
        protected_roots=[*ABYSS_STACK_READONLY_ROOTS, "/work"],
        llm_root=_core.AI_LLM_ROOT,
        llm_agents_path=_core.AI_LLM_ROOT / "AGENTS.md",
        workhorse_controller=AI_LLM_WORKHORSE_CONTROLLER,
        ai_config_path=_core.AI_CONFIG_PATH,
        path_check=_core.validation_add_path_exists,
        json_file_check=_core.validation_json_file,
        write_latest=write_latest,
        latest_path=_core.AI_LLM_VALIDATE_LATEST_PATH,
        write_json=_core.safe_atomic_write_json,
    )


def ai_token_accounting_contract(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.token_accounting_contract_readmodel(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        root=_core.AI_TOKEN_ACCOUNTING_ROOT,
        latest_path=_core.AI_TOKEN_ACCOUNTING_LATEST_PATH,
        profiles_latest_path=_core.AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH,
        counts_latest_path=AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH,
        write_latest=write_latest,
        write_json=_core.safe_atomic_write_json,
    )


def ai_token_accounting_tokenizer_candidates(profile: dict[str, Any]) -> list[Path]:
    return ai_runtime_contracts.token_accounting_tokenizer_candidates(profile)


def ai_token_accounting_library_paths(tokenizer: Path, profile: dict[str, Any]) -> list[Path]:
    return ai_runtime_adapters.token_accounting_library_paths(tokenizer, profile, path_exists=Path.exists)


def ai_token_accounting_resolve_tokenizer(profile: dict[str, Any]) -> dict[str, Any]:
    return ai_runtime_adapters.token_accounting_resolve_tokenizer(profile, path_exists=Path.exists, access=os.access)


def ai_token_accounting_profiles(write_latest: bool = True, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry if isinstance(registry, dict) else ai_llm_registry(write_latest=True)
    return ai_runtime_adapters.token_accounting_profiles_readmodel(
        registry=registry,
        resolve_tokenizer=ai_token_accounting_resolve_tokenizer,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        root=_core.AI_TOKEN_ACCOUNTING_ROOT,
        write_latest=write_latest,
        latest_path=_core.AI_TOKEN_ACCOUNTING_PROFILES_LATEST_PATH,
        daily_path=lambda: _core.ai_daily_jsonl_path(_core.AI_TOKEN_ACCOUNTING_PROFILES_ROOT),
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
    )


def ai_token_accounting_latest() -> dict[str, Any]:
    return ai_runtime_adapters.token_accounting_latest_readmodel(
        latest_path=AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        read_json=_core.load_json_document,
    )


def ai_token_accounting_int(value: Any) -> int | None:
    return ai_runtime_contracts.token_accounting_int(value)


def ai_token_accounting_sanitize_summary(summary: Any) -> dict[str, Any]:
    return ai_runtime_contracts.token_accounting_sanitize_summary(summary)


def ai_token_accounting_summary_has_counts(summary: dict[str, Any]) -> bool:
    return ai_runtime_contracts.token_accounting_summary_has_counts(summary)


def ai_token_accounting_context_pressure(summary: dict[str, Any]) -> dict[str, Any]:
    return ai_runtime_contracts.token_accounting_context_pressure(summary)


def ai_token_accounting_merge_summaries(summaries: list[dict[str, Any]], scope: dict[str, Any]) -> dict[str, Any]:
    return ai_runtime_contracts.token_accounting_merge_summaries(summaries, scope)


def ai_token_accounting_aoa_summary(
    *,
    aoa_root: Path = _core.DEFAULT_AOA_SESSION_MEMORY_ROOT,
    target: str = "all",
    since: str | None = None,
    since_days: int | None = 7,
    until: str | None = None,
    limit: int | None = 100,
    write_latest: bool = True,
) -> dict[str, Any]:
    return ai_runtime_adapters.token_accounting_aoa_summary_readmodel(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        aoa_root=aoa_root,
        target=target,
        since=since,
        since_days=since_days,
        until=until,
        limit=limit,
        write_latest=write_latest,
        latest_path=_core.AI_TOKEN_ACCOUNTING_AOA_LATEST_PATH,
        history_root=_core.AI_TOKEN_ACCOUNTING_AOA_ROOT,
        read_json=_core.load_json_document,
        sha256_path=_core.sha256_path,
        write_latest_history=_core.write_latest_and_history,
        is_relative_to_path=_core.is_relative_to_path,
    )


def ai_token_accounting_self_test() -> dict[str, Any]:
    tmp_root = _core.ABYSS_MACHINE_TMP_ROOT / "ai-token-accounting-self-test"
    tmp_root.mkdir(parents=True, exist_ok=True)
    forbidden = "SECRET_PROMPT_TEXT_SHOULD_NOT_LEAK"
    checks: list[dict[str, Any]] = []

    def add(level: str, key: str, message: str, details: dict[str, Any] | None = None) -> None:
        item: dict[str, Any] = {"level": level, "key": key, "message": message}
        if details is not None:
            item["details"] = details
        checks.append(item)

    with tempfile.TemporaryDirectory(prefix="aoa-token-bridge-", dir=str(tmp_root)) as tmp:
        aoa_root = Path(tmp) / ".aoa"
        aoa_root.mkdir(parents=True)
        session_dir = aoa_root / "sessions" / "2026-06-02__001__contains-secret-title"
        session_dir.mkdir(parents=True)
        safe_summary = {
            "schema": TOKEN_ACCOUNTING_CONTRACT,
            "schema_version": TOKEN_ACCOUNTING_SCHEMA_VERSION,
            "generator_version": 2,
            "provider_reported_event_count": 1,
            "estimated_event_count": 1,
            "count_by_basis": {"provider_reported": 1, "estimated": 1},
            "totals_by_basis": {
                "provider_reported": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
                "estimated": {"total_tokens": 9},
            },
        }
        registry = {
            "schema_version": 1,
            "updated_at": "2026-06-02T00:00:00Z",
            "sessions": [
                {
                    "session_id": "self-test-session",
                    "session_label": f"2026-06-02__001__{forbidden}",
                    "session_title": forbidden,
                    "path": str(session_dir),
                    "transcript_path": f"/tmp/{forbidden}.jsonl",
                    "updated_at": "2026-06-02T00:00:00Z",
                    "archive_status": "indexed",
                    "event_count": 2,
                    "segment_count": 1,
                    "raw": {"path": f"/tmp/{forbidden}/session.raw.jsonl"},
                    "token_accounting": safe_summary,
                },
                {
                    "session_id": "missing-generated",
                    "session_label": "2026-06-02__002__missing",
                    "path": str(aoa_root / "sessions" / "2026-06-02__002__missing"),
                    "updated_at": "2026-06-02T00:01:00Z",
                    "archive_status": "indexed",
                    "event_count": 0,
                    "segment_count": 0,
                },
            ],
        }
        _core.safe_atomic_write_json(aoa_root / "session-registry.json", registry, 0o664)
        result = ai_token_accounting_aoa_summary(
            aoa_root=aoa_root,
            target="all",
            since=None,
            since_days=None,
            until=None,
            limit=None,
            write_latest=False,
        )
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    add("ok" if result.get("ok") else "fail", "aoa_summary_ok", "synthetic .aoa summary bridge returns ok", result.get("summary"))
    add(
        "ok" if _core.nested_get(result, ["policy", "raw_transcripts_read"]) is False and _core.nested_get(result, ["policy", "mutates_aoa"]) is False else "fail",
        "read_only_policy",
        "bridge policy is read-only and does not read raw transcripts",
        result.get("policy"),
    )
    add(
        "ok" if forbidden not in encoded else "fail",
        "privacy_no_session_text",
        "projection omits session title/label/transcript/raw text",
        {"forbidden_present": forbidden in encoded},
    )
    add(
        "ok" if _core.nested_get(result, ["aggregate", "totals_by_basis", "provider_reported", "total_tokens"]) == 5 else "fail",
        "aggregate_provider_tokens",
        "provider-reported totals survive sanitization",
        _core.nested_get(result, ["aggregate", "totals_by_basis", "provider_reported"]),
    )
    add(
        "ok" if _core.nested_get(result, ["summary", "missing_generated_token_accounting"]) == 1 else "fail",
        "missing_generated_diagnostic",
        "missing generated token ledgers are diagnostics, not raw recomputation",
        result.get("diagnostics"),
    )
    fails = sum(1 for item in checks if item["level"] == "fail")
    warnings = sum(1 for item in checks if item["level"] == "warn")
    return {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_token_accounting_self_test_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": fails == 0,
        "summary": {
            "status": "fail" if fails else "warn" if warnings else "ok",
            "fails": fails,
            "warnings": warnings,
            "checks": len(checks),
        },
        "checks": checks,
        "policy": {
            "uses_tmp_root": str(tmp_root),
            "writes_aoa": False,
            "persists_prompt_text": False,
        },
    }


def ai_token_accounting_parse_count(stdout: str) -> int | None:
    return ai_runtime_contracts.token_accounting_parse_count(stdout)


def ai_token_accounting_count_text(
    *,
    profile_name: str,
    text: str,
    write_latest: bool = True,
    timeout: float = 60.0,
) -> dict[str, Any]:
    profiles_payload = ai_token_accounting_profiles(write_latest=True)
    return ai_runtime_adapters.token_accounting_count_text_readmodel(
        profile_name=profile_name,
        text=text,
        profiles_payload=profiles_payload,
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        write_latest=write_latest,
        latest_path=AI_TOKEN_ACCOUNTING_COUNTS_LATEST_PATH,
        daily_path=lambda: _core.ai_daily_jsonl_path(_core.AI_TOKEN_ACCOUNTING_COUNTS_ROOT),
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
        timeout=timeout,
        environ=os.environ,
        count_subprocess=ai_runtime_adapters.token_accounting_count_subprocess,
    )


def ai_capabilities(write_latest: bool = True) -> dict[str, Any]:
    return ai_runtime_adapters.capabilities_readmodel_from_live_inputs(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        devices_status=_core.ai_devices_status,
        models_inventory=ai_models_inventory,
        dictation_status=dictation_cli.dictation_status,
        tts_profiles=ai_tts_profiles,
        tts_latest_eval=ai_tts_latest_eval,
        tts_latest_success=ai_tts_latest_success_eval,
        llm_registry=ai_llm_registry,
        refs=ai_runtime_path_refs,
        resident_status_path=_core.AI_LLM_RESIDENT_ROOT / "status" / "latest.json",
        resident_monitor_path=_core.AI_LLM_RESIDENT_ROOT / "monitor" / "latest.json",
        resident_digest_path=_core.AI_LLM_RESIDENT_ROOT / "digests" / "latest.json",
        resident_micro_path=_core.AI_LLM_RESIDENT_ROOT / "jobs" / "micro" / "latest.json",
        resident_jobs_path=_core.AI_LLM_RESIDENT_ROOT / "jobs" / "latest.json",
        resident_jobs_validate_path=_core.AI_LLM_RESIDENT_ROOT / "jobs" / "validate" / "latest.json",
        resident_job_names=_core.AI_LLM_RESIDENT_JOB_NAMES,
        read_json=_core.load_json_document,
        write_latest=write_latest,
        latest_path=_core.AI_CAPABILITIES_LATEST_PATH,
        write_json=_core.safe_atomic_write_json,
    )


def ai_capabilities_latest() -> dict[str, Any]:
    data = _core.load_latest_json(_core.AI_CAPABILITIES_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_capabilities_v1")
    return ai_runtime_contracts.ai_capabilities_latest_document(data, latest_path=str(_core.AI_CAPABILITIES_LATEST_PATH))


def ai_policy(
    write_latest: bool = True,
    cpu_thermal_map: dict[str, Any] | None = None,
    mode_data: dict[str, Any] | None = None,
    battery_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ai_runtime_adapters.policy_readmodel_from_live_inputs(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        config=ai_config(),
        observability_status=_core.observability_status,
        observability_latest=_core.observability_latest,
        mode_status=_core.mode_status,
        battery_summary=_core.battery_summary,
        thermal_policy_snapshot=_core.ai_thermal_policy_snapshot,
        cpu_thermal_map=_core.ai_cpu_thermal_map,
        cpu_thermal_map_input=cpu_thermal_map,
        observability_latest_path=str(_core.OBSERVABILITY_ROOT / "thermal-battery" / "latest.json"),
        cpu_thermal_map_latest_path=str(_core.AI_CPU_THERMAL_MAP_LATEST_PATH),
        write_latest=write_latest,
        latest_path=_core.AI_POLICY_LATEST_PATH,
        write_json=_core.safe_atomic_write_json,
        mode_input=mode_data,
        battery_input=battery_data,
    )


AI_COUNTERPART_RULES = [
    {"entity_id": "ai:openai:chatgpt", "provider": "OpenAI", "product": "ChatGPT", "family": "gpt", "hosts": ["chatgpt.com", "chat.openai.com"], "aliases": ["chatgpt", "gpt"], "surface": "ai_chat"},
    {"entity_id": "ai:google:gemini", "provider": "Google", "product": "Gemini", "family": "gemini", "hosts": ["gemini.google.com", "bard.google.com"], "aliases": ["gemini", "bard"], "surface": "ai_chat"},
    {"entity_id": "ai:google:ai-studio", "provider": "Google", "product": "Google AI Studio", "family": "gemini", "hosts": ["aistudio.google.com"], "aliases": ["ai studio", "google ai studio"], "surface": "ai_tool"},
    {"entity_id": "ai:google:notebooklm", "provider": "Google", "product": "NotebookLM", "family": "notebooklm", "hosts": ["notebooklm.google.com"], "aliases": ["notebooklm"], "surface": "ai_tool"},
    {"entity_id": "ai:anthropic:claude", "provider": "Anthropic", "product": "Claude", "family": "claude", "hosts": ["claude.ai"], "aliases": ["claude"], "surface": "ai_chat"},
    {"entity_id": "ai:perplexity:perplexity", "provider": "Perplexity", "product": "Perplexity", "family": "perplexity", "hosts": ["perplexity.ai"], "aliases": ["perplexity"], "surface": "ai_chat"},
    {"entity_id": "ai:microsoft:copilot", "provider": "Microsoft", "product": "Copilot", "family": "copilot", "hosts": ["copilot.microsoft.com"], "aliases": ["copilot", "bing chat"], "surface": "ai_chat"},
    {"entity_id": "ai:poe:poe", "provider": "Quora", "product": "Poe", "family": "poe", "hosts": ["poe.com"], "aliases": ["poe"], "surface": "ai_router"},
    {"entity_id": "ai:xai:grok", "provider": "xAI", "product": "Grok", "family": "grok", "hosts": ["grok.com"], "aliases": ["grok"], "surface": "ai_chat"},
    {"entity_id": "ai:deepseek:deepseek", "provider": "DeepSeek", "product": "DeepSeek", "family": "deepseek", "hosts": ["chat.deepseek.com", "deepseek.com"], "aliases": ["deepseek"], "surface": "ai_chat"},
    {"entity_id": "ai:mistral:le-chat", "provider": "Mistral AI", "product": "Le Chat", "family": "mistral", "hosts": ["chat.mistral.ai", "lechat.mistral.ai"], "aliases": ["le chat", "mistral"], "surface": "ai_chat"},
    {"entity_id": "ai:alibaba:qwen", "provider": "Alibaba Cloud", "product": "Qwen Chat", "family": "qwen", "hosts": ["chat.qwen.ai", "qwen.ai"], "aliases": ["qwen"], "surface": "ai_chat"},
    {"entity_id": "ai:moonshot:kimi", "provider": "Moonshot AI", "product": "Kimi", "family": "kimi", "hosts": ["kimi.com", "kimi.moonshot.cn"], "aliases": ["kimi"], "surface": "ai_chat"},
    {"entity_id": "ai:huggingface:huggingchat", "provider": "Hugging Face", "product": "HuggingChat", "family": "huggingchat", "hosts": ["huggingface.co"], "path_prefixes": ["/chat"], "aliases": ["huggingchat"], "surface": "ai_chat"},
    {"entity_id": "ai:openrouter:openrouter", "provider": "OpenRouter", "product": "OpenRouter", "family": "openrouter", "hosts": ["openrouter.ai"], "aliases": ["openrouter"], "surface": "ai_router"},
    {"entity_id": "ai:you:you", "provider": "You.com", "product": "You.com AI", "family": "you", "hosts": ["you.com"], "aliases": ["you.com", "you ai"], "surface": "ai_chat"},
    {"entity_id": "ai:phind:phind", "provider": "Phind", "product": "Phind", "family": "phind", "hosts": ["phind.com"], "aliases": ["phind"], "surface": "ai_search"},
    {"entity_id": "ai:characterai:character-ai", "provider": "Character.AI", "product": "Character.AI", "family": "character-ai", "hosts": ["character.ai"], "aliases": ["character.ai"], "surface": "ai_chat"},
    {"entity_id": "ai:meta:meta-ai", "provider": "Meta", "product": "Meta AI", "family": "meta-ai", "hosts": ["meta.ai"], "aliases": ["meta ai"], "surface": "ai_chat"},
]


AI_COUNTERPART_RULES = _core.typing_capture_contracts.AI_COUNTERPART_RULES


def browser_ai_normalized_title(title: str | None) -> str:
    return _core.typing_capture_contracts.browser_ai_normalized_title(title)


def browser_ai_title_rule_basis(rule: dict[str, Any], title: str | None) -> str | None:
    return _core.typing_capture_contracts.browser_ai_title_rule_basis(rule, title)


def browser_ai_counterpart_identity(url: str | None, title: str | None = None) -> dict[str, Any]:
    return _core.typing_capture_contracts.browser_ai_counterpart_identity(
        url,
        title,
        schema_prefix=_core.SCHEMA_PREFIX,
    )


def ai_storage_status(write_latest: bool = True) -> dict[str, Any]:
    storage_config = ai_config().get("storage", {}) if isinstance(ai_config().get("storage"), dict) else {}
    largest_files_limit = int(storage_config.get("largest_files_limit", 30))
    largest_dirs_limit = int(storage_config.get("largest_dirs_limit", 30))
    duplicate_limit = int(storage_config.get("duplicate_candidates_limit", 50))
    cache_name = str(storage_config.get("cache_dir_name", "model_cache"))
    roots_summary: list[dict[str, Any]] = []
    largest_files: list[dict[str, Any]] = []
    top_dirs: dict[str, int] = {}
    duplicates: dict[tuple[str, int], list[str]] = {}
    cache_dirs: list[dict[str, Any]] = []

    for root in ai_model_roots():
        summary = {"path": str(root), "exists": root.exists(), "total_bytes": 0, "file_count": 0, "dir_count": 0}
        roots_summary.append(summary)
        if not root.exists():
            continue
        for current, dirnames, filenames in os.walk(root):
            current_path = Path(current)
            summary["dir_count"] = int(summary["dir_count"]) + 1
            if current_path.name == cache_name:
                cache_dirs.append({"path": str(current_path), "root": str(root)})
            for filename in filenames:
                file_path = current_path / filename
                try:
                    size = file_path.stat().st_size
                except OSError:
                    continue
                summary["total_bytes"] = int(summary["total_bytes"]) + size
                summary["file_count"] = int(summary["file_count"]) + 1
                try:
                    relative = file_path.relative_to(root)
                    top = relative.parts[0] if relative.parts else file_path.name
                except ValueError:
                    top = file_path.name
                top_key = f"{root}:{top}"
                top_dirs[top_key] = top_dirs.get(top_key, 0) + size
                largest_files.append({"path": str(file_path), "size_bytes": size, "root": str(root)})
                key = (filename, size)
                duplicates.setdefault(key, []).append(str(file_path))
    largest_files = sorted(largest_files, key=lambda item: int(item["size_bytes"]), reverse=True)[:largest_files_limit]
    largest_dirs = [
        {"path": key, "size_bytes": size}
        for key, size in sorted(top_dirs.items(), key=lambda item: item[1], reverse=True)[:largest_dirs_limit]
    ]
    duplicate_candidates = [
        {"name": key[0], "size_bytes": key[1], "paths": paths}
        for key, paths in duplicates.items()
        if len(paths) > 1
    ][:duplicate_limit]
    for cache in cache_dirs:
        path = Path(str(cache["path"]))
        cache["size_bytes"] = _core.directory_size(path)
        cache["generated_cache"] = True
    cache_root_status = {
        "path": str(_core.AI_OPENVINO_CACHE_ROOT),
        "exists": _core.AI_OPENVINO_CACHE_ROOT.exists(),
        "size_bytes": _core.directory_size(_core.AI_OPENVINO_CACHE_ROOT) if _core.AI_OPENVINO_CACHE_ROOT.exists() else 0,
    }
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_storage_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": True,
        "roots": roots_summary,
        "summary": {
            "total_bytes": sum(int(item.get("total_bytes") or 0) for item in roots_summary),
            "file_count": sum(int(item.get("file_count") or 0) for item in roots_summary),
            "stack_local_openvino_cache_dirs": len(cache_dirs),
            "stack_local_openvino_cache_bytes": sum(int(item.get("size_bytes") or 0) for item in cache_dirs),
        },
        "largest_files": largest_files,
        "largest_top_dirs": largest_dirs,
        "duplicate_candidates": duplicate_candidates,
        "stack_local_openvino_cache_dirs": cache_dirs,
        "host_cache": {
            "openvino": cache_root_status,
            "tts": {
                "path": str(_core.AI_TTS_CACHE_ROOT),
                "exists": _core.AI_TTS_CACHE_ROOT.exists(),
                "size_bytes": _core.directory_size(_core.AI_TTS_CACHE_ROOT) if _core.AI_TTS_CACHE_ROOT.exists() else 0,
            },
            "environment_routes": _core.storage_cache_env_routes(),
        },
        "policy": {
            "read_only_by_default": True,
            "cleanup_command": "abyss-machine ai storage clean-caches --stack-local-openvino --json",
            "host_storage_policy": str(_core.STORAGE_POLICY_PATH),
            "host_storage_command": "abyss-machine storage status --json",
            "hook_command": "abyss-machine storage hooks --json",
        },
        "processes": _core.process_latest_summary(),
    }
    if write_latest:
        error = _core.safe_atomic_write_json(_core.AI_STORAGE_LATEST_PATH, data, 0o664)
        if error:
            data["write_error"] = error
    return data


def ai_storage_cleanup_stack_openvino_caches(write_latest: bool = True) -> dict[str, Any]:
    storage = ai_storage_status(write_latest=True)
    pre_hooks = _core.run_storage_hooks(
        "pre_cache_cleanup",
        {
            "command": "abyss-machine ai storage clean-caches --stack-local-openvino --json",
            "scope": "stack-local OpenVINO model_cache dirs",
            "summary": storage.get("summary"),
        },
        enforce=True,
    )
    if not pre_hooks.get("ok"):
        return {
            "schema": f"{_core.SCHEMA_PREFIX}_ai_storage_cleanup_v1",
            "version": _core.VERSION,
            "generated_at": _core.now_iso(),
            "ok": False,
            "error": "blocked by pre_cache_cleanup hook",
            "hooks": {"pre_cache_cleanup": pre_hooks},
        }
    removed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    roots = [root for root in ai_model_roots() if root.exists()]
    for item in storage.get("stack_local_openvino_cache_dirs", []):
        path = Path(str(item.get("path")))
        if path.name != "model_cache" or not any(_core.is_relative_to_path(path, root) for root in roots):
            errors.append({"path": str(path), "error": "refusing non-model_cache or out-of-root path"})
            continue
        size = int(item.get("size_bytes") or _core.directory_size(path))
        try:
            shutil.rmtree(path)
            removed.append({"path": str(path), "size_bytes": size})
        except OSError as exc:
            errors.append({"path": str(path), "error": str(exc)})
    data = {
        "schema": f"{_core.SCHEMA_PREFIX}_ai_storage_cleanup_v1",
        "version": _core.VERSION,
        "generated_at": _core.now_iso(),
        "ok": not errors,
        "removed": removed,
        "errors": errors,
        "summary": {
            "removed_dirs": len(removed),
            "removed_bytes": sum(int(item.get("size_bytes") or 0) for item in removed),
            "errors": len(errors),
        },
        "policy": {
            "scope": "directories named model_cache below configured model roots only",
            "model_weights_removed": False,
        },
    }
    post_hooks = _core.run_storage_hooks(
        "post_cache_cleanup",
        {
            "command": "abyss-machine ai storage clean-caches --stack-local-openvino --json",
            "summary": data.get("summary"),
            "removed": removed,
            "errors": errors,
        },
        enforce=False,
    )
    data["hooks"] = {
        "pre_cache_cleanup": pre_hooks,
        "post_cache_cleanup": post_hooks,
    }
    if write_latest:
        _core.safe_append_jsonl(_core.ai_daily_jsonl_path(AI_STORAGE_CLEANUP_ROOT), data, 0o664)
        ai_storage_status(write_latest=True)
    return data


def ai_python_runtime_versions() -> dict[str, Any]:
    return ai_runtime_adapters.python_runtime_versions(
        config=ai_config(),
        run_command=_core.run,
        which=shutil.which,
        subprocess_env=ai_subprocess_env(),
    )


def kernel_module_snapshot() -> dict[str, Any]:
    return ai_runtime_adapters.kernel_module_snapshot(command_exists=_core.command_exists, run_command=_core.run)


def ai_runtime_snapshot(write_latest: bool = True) -> dict[str, Any]:
    previous, _ = _core.load_json_document(_core.AI_RUNTIME_LATEST_PATH)
    devices = _core.ai_devices_status(write_latest=True)
    runtime_versions = ai_python_runtime_versions()
    return ai_runtime_adapters.runtime_snapshot_readmodel(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        kernel=platform.release(),
        os_release=_core.os_release(),
        devices=devices,
        python_runtime=runtime_versions,
        kernel_modules=kernel_module_snapshot(),
        previous_latest=previous,
        write_latest=write_latest,
        latest_path=_core.AI_RUNTIME_LATEST_PATH,
        daily_path=lambda: _core.ai_daily_jsonl_path(_core.AI_RUNTIME_ROOT),
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
    )


def ai_report(write_latest: bool = True) -> dict[str, Any]:
    status_data = ai_status(include_report=False)
    capabilities = ai_capabilities(write_latest=True)
    policy = ai_policy(write_latest=True)
    runtime = ai_runtime_snapshot(write_latest=True)
    storage = ai_storage_status(write_latest=True)
    llm_registry = ai_llm_registry(write_latest=True)
    llm_validate = ai_llm_validate(write_latest=True)
    token_accounting_profiles = ai_token_accounting_profiles(write_latest=True, registry=llm_registry)
    aoa_token_summary = ai_token_accounting_aoa_summary(write_latest=True)
    latest_eval = ai_latest_eval()
    latest_benchmark = ai_latest_benchmark()
    latest_tts_eval = ai_tts_latest_eval()
    latest_tts_success = ai_tts_latest_success_eval()
    tts_profiles = ai_tts_profiles(write_latest=True)
    tts_server = ai_tts_server_status(write_latest=True)
    workload = ai_workload_status(write_latest=True, refresh_from_latest=True)
    cpu_route_latest = _core.load_latest_json(_core.AI_CPU_ROUTE_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_cpu_route_latest_read_v1")
    cpu_thermal_latest = _core.load_latest_json(_core.AI_CPU_THERMAL_MAP_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_cpu_thermal_map_latest_read_v1")
    cooling_latest = _core.load_latest_json(_core.COOLING_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_cooling_latest_read_v1")
    observability = _core.observability_status()
    dictation = dictation_cli.dictation_status()
    return ai_runtime_adapters.report_readmodel(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        paths=ai_paths(),
        status_data=status_data,
        capabilities=capabilities,
        policy=policy,
        runtime=runtime,
        storage=storage,
        llm_registry=llm_registry,
        llm_validate=llm_validate,
        token_accounting_profiles=token_accounting_profiles,
        aoa_token_summary=aoa_token_summary,
        latest_eval=latest_eval,
        latest_benchmark=latest_benchmark,
        latest_tts_eval=latest_tts_eval,
        latest_tts_success=latest_tts_success,
        tts_profiles=tts_profiles,
        tts_server=tts_server,
        workload=workload,
        cpu_route_latest=cpu_route_latest,
        cpu_thermal_latest=cpu_thermal_latest,
        cooling_latest=cooling_latest,
        observability=observability,
        dictation=dictation,
        refs=ai_runtime_path_refs(),
        write_latest=write_latest,
        latest_path=_core.AI_REPORT_LATEST_PATH,
        daily_path=lambda: _core.ai_daily_jsonl_path(_core.AI_REPORT_ROOT),
        write_json=_core.safe_atomic_write_json,
        append_jsonl=_core.safe_append_jsonl,
    )


def ai_status(include_report: bool = True) -> dict[str, Any]:
    devices = _core.ai_devices_status(write_latest=True)
    models = ai_models_inventory(write_latest=True)
    llm_registry = ai_llm_registry(write_latest=True)
    latest_benchmark = ai_latest_benchmark()
    latest_eval = ai_latest_eval()
    latest_tts_eval = ai_tts_latest_eval()
    latest_tts_success = ai_tts_latest_success_eval()
    tts_profiles = ai_tts_profiles(write_latest=True)
    tts_server = ai_tts_server_status(write_latest=True)
    dictation = dictation_cli.dictation_status()
    cpu_route_latest = _core.load_latest_json(_core.AI_CPU_ROUTE_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_cpu_route_latest_read_v1")
    cpu_thermal_latest = _core.load_latest_json(_core.AI_CPU_THERMAL_MAP_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_ai_cpu_thermal_map_latest_read_v1")
    cooling_latest = _core.load_latest_json(_core.COOLING_LATEST_PATH, f"{_core.SCHEMA_PREFIX}_cooling_latest_read_v1")
    return ai_runtime_adapters.status_readmodel(
        schema_prefix=_core.SCHEMA_PREFIX,
        version=_core.VERSION,
        now_iso=_core.now_iso,
        paths=ai_paths(),
        config_path=_core.AI_CONFIG_PATH,
        config_exists=_core.AI_CONFIG_PATH.exists(),
        config_load_error=ai_config().get("_load_error"),
        devices=devices,
        models=models,
        llm_registry=llm_registry,
        latest_benchmark=latest_benchmark,
        latest_eval=latest_eval,
        latest_tts_eval=latest_tts_eval,
        latest_tts_success=latest_tts_success,
        tts_profiles=tts_profiles,
        tts_server=tts_server,
        dictation=dictation,
        cpu_route_latest=cpu_route_latest,
        cpu_thermal_latest=cpu_thermal_latest,
        cooling_latest=cooling_latest,
        refs=ai_runtime_path_refs(),
        include_report=include_report,
        report_latest_path=_core.AI_REPORT_LATEST_PATH,
        report_exists=_core.AI_REPORT_LATEST_PATH.exists(),
    )


def print_ai_status_text(data: dict[str, Any]) -> None:
    ready = data.get("ready", {})
    devices = data.get("devices", {})
    models = data.get("models", {}).get("summary", {})
    benchmark = data.get("benchmark", {})
    print(f"openvino: {ready.get('openvino')} devices={devices.get('available_devices')}")
    print(f"gpu: {ready.get('gpu')} npu={ready.get('npu')} models={models.get('entries')}")
    print(f"benchmark latest: {benchmark.get('latest_ok')} {benchmark.get('latest_generated_at')}")
    print(f"root: {data.get('paths', {}).get('root')}")


def print_ai_models_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(f"model entries: {summary.get('entries')} truncated={summary.get('truncated')}")
    for category, count in (summary.get("by_category") or {}).items():
        print(f"{category}: {count}")


def print_ai_benchmark_text(data: dict[str, Any]) -> None:
    print(f"benchmark: ok={data.get('ok')} {data.get('benchmark')}")
    for item in data.get("results", []):
        if item.get("ok"):
            print(
                f"{item.get('device'):<4} "
                f"compile={item.get('compile_sec')}s "
                f"infer={item.get('median_infer_sec')}s"
            )
        else:
            suffix = "skipped" if item.get("skipped") else "failed"
            print(f"{item.get('device'):<4} {suffix}: {item.get('reason') or item.get('error')}")


def print_ai_eval_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(f"eval: ok={data.get('ok')} suites={summary.get('suites_ok')}/{summary.get('suites')}")
    for item in data.get("results", []):
        print(f"{item.get('suite'):<10} ok={item.get('ok')}")


def print_ai_tts_inventory_text(data: dict[str, Any]) -> None:
    config = data.get("config", {})
    runtime = data.get("runtime", {})
    modules = runtime.get("python_modules", {}).get("modules", {})
    print(f"tts inventory: ok={data.get('ok')} default={config.get('default_profile')}")
    print(f"python: {config.get('python')}")
    for module in ("qwen_tts", "babelvox", "soundfile", "openvino"):
        info = modules.get(module, {}) if isinstance(modules.get(module), dict) else {}
        print(f"{module:<10} present={info.get('present')} version={info.get('version')}")


def print_ai_tts_profiles_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(f"tts profiles: {summary.get('profiles')} executable={summary.get('executable')} runtime_missing={summary.get('runtime_missing')}")
    for name, profile in data.get("profiles", {}).items():
        print(f"{name:<24} {profile.get('status'):<28} {profile.get('engine')} {profile.get('device')}")


def print_ai_tts_eval_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(f"tts eval: ok={data.get('ok')} profile={data.get('profile')} wall={summary.get('wall_sec')} rtf={summary.get('rtf')}")
    if summary.get("error"):
        print(f"error: {summary.get('error')}")


def print_ai_tts_synth_text(data: dict[str, Any]) -> None:
    audio = data.get("audio", {}) if isinstance(data.get("audio"), dict) else {}
    print(f"tts synth: ok={data.get('ok')} profile={data.get('profile')} engine={data.get('engine')} wall={data.get('wall_sec')} rtf={data.get('rtf')}")
    print(f"output: {data.get('output')} audio={audio.get('duration_sec')}s")
    if data.get("error"):
        print(f"error: {data.get('error')}")


def print_ai_capabilities_text(data: dict[str, Any]) -> None:
    for name, capability in data.get("capabilities", {}).items():
        print(f"{name:<12} {capability.get('status')}")


def print_ai_policy_text(data: dict[str, Any]) -> None:
    print(
        f"policy: {data.get('class')} "
        f"heavy={data.get('can_run_heavy')} "
        f"routed={data.get('can_run_routed_heavy')} "
        f"mode={data.get('heavy_policy')}"
    )
    reasons = ",".join(data.get("reasons", [])) or "none"
    print(f"reasons: {reasons}")


def print_ai_storage_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(f"model bytes: {summary.get('total_bytes')}")
    print(f"files: {summary.get('file_count')}")
    print(f"stack-local OpenVINO cache dirs: {summary.get('stack_local_openvino_cache_dirs')} bytes={summary.get('stack_local_openvino_cache_bytes')}")


def print_ai_runtime_text(data: dict[str, Any]) -> None:
    current = data.get("current", {})
    print(f"runtime: ok={data.get('ok')} kernel={current.get('kernel')}")
    print(f"openvino: {current.get('openvino_version')} devices={current.get('available_devices')}")
    drift = ",".join(data.get("drift_from_previous_latest", [])) or "none"
    print(f"drift: {drift}")


def print_ai_report_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    print(
        f"report: ok={data.get('ok')} "
        f"policy={summary.get('policy_class')} "
        f"heavy={summary.get('can_run_heavy')} "
        f"routed={summary.get('can_run_routed_heavy')}"
    )
    print(f"capabilities: {summary.get('capabilities')}")


def print_ai_workload_text(data: dict[str, Any]) -> None:
    summary = data.get("summary", {})
    routing = data.get("routing", {})
    print(f"workload: ok={data.get('ok')} records={summary.get('records')} groups={summary.get('groups')}")
    print(f"route: max_level={routing.get('current_max_recommended_level')} basis={routing.get('basis')}")
    for group in data.get("stats", {}).get("groups", [])[:12]:
        label = group.get("workload_id")
        if group.get("device"):
            label = f"{label}/{group.get('device')}"
        if group.get("profile"):
            label = f"{label}/{group.get('profile')}"
        duration = group.get("metrics", {}).get("component_sum_sec") or group.get("metrics", {}).get("wall_sec") or group.get("metrics", {}).get("elapsed_sec")
        latest = duration.get("latest") if isinstance(duration, dict) else None
        print(f"{label:<38} {group.get('declared_class'):<8} n={group.get('count')} latest_sec={latest}")


def add_ai_parser(add_top_level_parser: Any, selected_parser_choices: Any) -> None:
    ai_parser = add_top_level_parser("ai", help="inspect local AI host topology, devices, models and smoke benchmarks")
    ai_sub = ai_parser.add_subparsers(dest="ai_command", required=True)
    for name in ("status", "paths", "validate", "devices", "models", "capabilities", "policy", "storage", "runtime", "report"):
        p = ai_sub.add_parser(name)
        if name == "validate":
            p.add_argument("--strict", action="store_true", help="treat warnings as non-zero")
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_llm_parser = ai_sub.add_parser("llm", help="inspect host-managed llama.cpp LLM profiles")
    ai_llm_sub = ai_llm_parser.add_subparsers(dest="ai_llm_command", required=True)
    for name in ("paths", "registry", "latest", "validate"):
        p = ai_llm_sub.add_parser(name)
        if name == "validate":
            p.add_argument("--strict", action="store_true", help="treat warnings as non-zero")
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_token_parser = ai_sub.add_parser("token-accounting", help="inspect and run host-owned LLM token accounting")
    ai_token_sub = ai_token_parser.add_subparsers(dest="ai_token_accounting_command", required=True)
    for name in ("contract", "profiles", "latest"):
        p = ai_token_sub.add_parser(name)
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_token_aoa = ai_token_sub.add_parser("aoa-summary", help="read .aoa generated token summaries into host planning facts")
    ai_token_aoa.add_argument("--aoa-root", default=str(_core.DEFAULT_AOA_SESSION_MEMORY_ROOT))
    ai_token_aoa.add_argument("--target", default="all", help="all, latest, session id, or session label fragment")
    ai_token_aoa.add_argument("--since")
    ai_token_aoa.add_argument("--since-days", type=int, default=7)
    ai_token_aoa.add_argument("--until")
    ai_token_aoa.add_argument("--limit", type=int, default=100)
    ai_token_aoa.add_argument("--no-write", action="store_true", help="Do not write latest/history bridge artifacts.")
    ai_token_aoa.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_token_self_test = ai_token_sub.add_parser("self-test", help="run token accounting bridge privacy/read-only tests")
    ai_token_self_test.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_token_count = ai_token_sub.add_parser("count", help="count text with a model-matched local tokenizer")
    ai_token_count.add_argument("--profile", default="gemma4.spark", help="LLM profile name such as gemma4.spark or qwen36.ordinary")
    ai_token_count.add_argument("--text", default=None, help="Text to count. Not persisted.")
    ai_token_count.add_argument("--text-file", default=None, help="Read text from this file. File contents are not persisted.")
    ai_token_count.add_argument("--timeout", type=float, default=60.0)
    ai_token_count.add_argument("--no-write", action="store_true", help="Do not write latest/history count artifacts.")
    ai_token_count.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_llm_resident_parser = ai_llm_sub.add_parser("resident", help="inspect and control the Gemma4 Spark resident candidate")
    ai_llm_resident_sub = ai_llm_resident_parser.add_subparsers(dest="ai_llm_resident_command", required=True)
    for name in ("paths", "preflight", "status", "monitor", "digest", "policy", "job", "micro", "jobs", "jobs-validate", "candidates", "candidates-validate", "evals", "evals-validate", "smoke", "audit", "validate", "start", "stop"):
        p = ai_llm_resident_sub.add_parser(name)
        if name == "job":
            p.add_argument("job_name", choices=_core.AI_LLM_RESIDENT_JOB_NAMES)
        if name == "jobs":
            p.add_argument("jobs_action", nargs="?", choices=["latest", "status", "list", "run", "refresh"], default="latest")
        if name == "policy":
            p.add_argument("job_name", nargs="?", choices=_core.AI_LLM_RESIDENT_JOB_NAMES)
            p.add_argument("--request-class", choices=["foreground", "digest", "job", "jobs", "sustained"], default="job")
        if name == "audit":
            p.add_argument("--no-generation", action="store_true", help="skip the audit tiny live generation probe")
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
        if name == "preflight":
            p.add_argument("--force", action="store_true", help="show forced-gate result without changing the service")
        if name in {"digest", "job", "micro", "jobs", "candidates"}:
            p.add_argument("--limit", type=int, default=5 if name == "digest" else None, help="maximum source records to process")
    ai_llm_workhorse_parser = ai_llm_sub.add_parser("workhorse", help="inspect the non-resident Gemma4 E4B review harness")
    ai_llm_workhorse_sub = ai_llm_workhorse_parser.add_subparsers(dest="ai_llm_workhorse_command", required=True)
    for name in ("paths", "preflight", "pack", "review", "validate", "self-test"):
        p = ai_llm_workhorse_sub.add_parser(name)
        if name in {"pack", "review"}:
            p.add_argument("--limit", type=int, default=24, help="maximum candidate records to pack")
            p.add_argument("--refresh-candidates", action="store_true", help="refresh E2B resident candidate read-model before packing")
        if name == "review":
            p.add_argument("--run-model", action="store_true", help="execute E4B after workhorse preflight; default is deterministic no-model review")
            p.add_argument("--n-predict", type=int, default=768)
            p.add_argument("--timeout", type=float, default=420.0)
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_workload_parser = ai_sub.add_parser("workload")
    ai_workload_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_workload_sub = ai_workload_parser.add_subparsers(dest="ai_workload_command")
    for name in ("taxonomy", "stats", "latest", "refresh"):
        p = ai_workload_sub.add_parser(name)
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
        if name == "refresh":
            p.add_argument("--no-probe", action="store_true", help="refresh from latest files without running quick benchmark")
    ai_cpu_parser = ai_sub.add_parser("cpu", help="inspect CPU topology and thermal-aware affinity routes")
    ai_cpu_sub = ai_cpu_parser.add_subparsers(dest="ai_cpu_command", required=True)
    ai_cpu_topology_parser = ai_cpu_sub.add_parser("topology")
    ai_cpu_topology_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_cpu_thermal_parser = ai_cpu_sub.add_parser("thermal-map")
    ai_cpu_thermal_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_cpu_route_parser = ai_cpu_sub.add_parser("route")
    ai_cpu_route_parser.add_argument("--class", dest="workload_class", default="medium", choices=["background", "probe", "light", "interactive", "medium", "heavy", "sustained"])
    ai_cpu_route_parser.add_argument("--latency", default="balanced", choices=["background", "balanced", "interactive"])
    ai_cpu_route_parser.add_argument("--force", action="store_true", help="return an operator-forced route even when heavy work is normally deferred")
    ai_cpu_route_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_cpu_launch_parser = ai_cpu_sub.add_parser("launch")
    ai_cpu_launch_parser.add_argument("--class", dest="workload_class", default="medium", choices=["background", "probe", "light", "interactive", "medium", "heavy", "sustained"])
    ai_cpu_launch_parser.add_argument("--latency", default="balanced", choices=["background", "balanced", "interactive"])
    ai_cpu_launch_parser.add_argument("--force", action="store_true", help="operator override when route denies new work")
    ai_cpu_launch_parser.add_argument("--unattended", action="store_true", help="enforce unattended launch gate instead of operator-controlled gate")
    ai_cpu_launch_parser.add_argument("--dry-run", action="store_true", help="plan route and argv without starting the command")
    ai_cpu_launch_parser.add_argument("--timeout", type=float, default=0.0, help="command timeout in seconds; 0 means no timeout")
    ai_cpu_launch_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_cpu_launch_parser.add_argument("launch_command", nargs=argparse.REMAINDER)
    ai_cpu_test_parser = ai_cpu_sub.add_parser("test")
    ai_cpu_test_parser.add_argument("--profile", default="mixed-safe", choices=["mixed-safe", "background", "lp-e", "e-cores", "cool-p"])
    ai_cpu_test_parser.add_argument("--seconds", type=float, default=1.0)
    ai_cpu_test_parser.add_argument("--force", action="store_true", help="skip heavy-route policy denial only for the route object; hard-avoid CPUs are still excluded")
    ai_cpu_test_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_parser = ai_sub.add_parser("tts")
    ai_tts_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_sub = ai_tts_parser.add_subparsers(dest="ai_tts_command", required=True)
    for name in ("inventory", "profiles", "voices"):
        p = ai_tts_sub.add_parser(name)
        p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_eval_parser = ai_tts_sub.add_parser("eval")
    ai_tts_eval_parser.add_argument("--profile", default=None)
    ai_tts_eval_parser.add_argument("--force", action="store_true", help="override AI host policy gate for this eval")
    ai_tts_eval_parser.add_argument("--allow-download", action="store_true", help="allow runtime to download host-owned model assets when supported")
    ai_tts_eval_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_compare_parser = ai_tts_sub.add_parser("compare")
    ai_tts_compare_parser.add_argument("--profiles", default="quality,quality-compact", help="comma-separated TTS profiles to compare")
    ai_tts_compare_parser.add_argument("--run", action="store_true", help="run fresh evals instead of comparing indexed successful evals")
    ai_tts_compare_parser.add_argument("--force", action="store_true", help="override AI host policy gate for each eval")
    ai_tts_compare_parser.add_argument("--allow-download", action="store_true", help="allow runtime to download host-owned model assets when supported")
    ai_tts_compare_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_synth_parser = ai_tts_sub.add_parser("synth")
    ai_tts_synth_parser.add_argument("--profile", default=None)
    ai_tts_synth_parser.add_argument("--text", default=None)
    ai_tts_synth_parser.add_argument("--text-file", default=None)
    ai_tts_synth_parser.add_argument("--output", default=None)
    ai_tts_synth_parser.add_argument("--force", action="store_true", help="override AI host policy gate for this synthesis")
    ai_tts_synth_parser.add_argument("--allow-download", action="store_true", help="allow runtime to download host-owned model assets when supported")
    ai_tts_synth_parser.add_argument("--no-server", action="store_true", help="skip warm server and run one-shot synthesis")
    ai_tts_synth_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_server_parser = ai_tts_sub.add_parser("server")
    ai_tts_server_sub = ai_tts_server_parser.add_subparsers(dest="ai_tts_server_command", required=True)
    ai_tts_server_status_parser = ai_tts_server_sub.add_parser("status")
    ai_tts_server_status_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_server_stop_parser = ai_tts_server_sub.add_parser("stop")
    ai_tts_server_stop_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_tts_server_run_parser = ai_tts_server_sub.add_parser("run")
    ai_tts_server_run_parser.add_argument("--profile", default=None)
    ai_tts_server_run_parser.add_argument("--socket", default=None)
    ai_tts_server_run_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON on startup failure")
    ai_eval_parser = ai_sub.add_parser("eval")
    ai_eval_parser.add_argument("--suite", choices=["quick", "stt", "embeddings", "text"], default="quick")
    ai_eval_parser.add_argument("--quick", action="store_true", help="run the configured quick eval suite")
    ai_eval_parser.add_argument("--force", action="store_true", help="override AI host policy gate for this eval")
    ai_eval_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_storage_parser = ai_sub.choices["storage"]
    ai_storage_sub = ai_storage_parser.add_subparsers(dest="ai_storage_command")
    ai_storage_clean = ai_storage_sub.add_parser("clean-caches")
    ai_storage_clean.add_argument("--stack-local-openvino", action="store_true", help="remove generated model_cache dirs below configured model roots")
    ai_storage_clean.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_benchmark_parser = ai_sub.add_parser("benchmark")
    ai_benchmark_parser.add_argument("--quick", action="store_true", help="run quick OpenVINO smoke benchmark")
    ai_benchmark_parser.add_argument("--real", action="store_true", help="run configured real host eval suite")
    ai_benchmark_parser.add_argument("--devices", default=None, help="comma-separated OpenVINO devices, e.g. CPU,GPU,NPU")
    ai_benchmark_parser.add_argument("--force", action="store_true", help="override AI host policy gate for --real eval")
    ai_benchmark_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ai_config_parser = ai_sub.add_parser("config")
    ai_config_sub = ai_config_parser.add_subparsers(dest="ai_config_command", required=True)
    ai_config_get_parser = ai_config_sub.add_parser("get")
    ai_config_get_parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def dispatch_ai(args: Any, parser: Any, argv: list[str]) -> int:
    if args.command == "ai":
        if args.ai_command == "status":
            data = ai_status()
            if args.json:
                _core.print_json(data)
            else:
                print_ai_status_text(data)
            return 0

        if args.ai_command == "validate":
            data = _core.subsystem_validate("ai", strict=bool(getattr(args, "strict", False)), write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                summary = data.get("summary", {})
                print(f"ai validate: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
            if data.get("summary", {}).get("fails"):
                return 1
            if getattr(args, "strict", False) and data.get("summary", {}).get("warnings"):
                return 2
            return 0

        if args.ai_command == "paths":
            data = ai_paths()
            _core.print_json(data)
            return 0

        if args.ai_command == "devices":
            data = _core.ai_devices_status(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                ready = data.get("ready", {})
                devices = data.get("openvino", {}).get("available_devices")
                print(f"openvino={ready.get('openvino')} devices={devices}")
                print(f"gpu={ready.get('gpu')} npu={ready.get('npu')}")
            return 0 if data.get("openvino", {}).get("ok") else 1

        if args.ai_command == "models":
            data = ai_models_inventory(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_models_text(data)
            return 0

        if args.ai_command == "token-accounting":
            command = getattr(args, "ai_token_accounting_command", None)
            if command == "contract":
                data = ai_token_accounting_contract(write_latest=True)
            elif command == "profiles":
                data = ai_token_accounting_profiles(write_latest=True)
            elif command == "latest":
                data = ai_token_accounting_latest()
            elif command == "aoa-summary":
                data = ai_token_accounting_aoa_summary(
                    aoa_root=Path(str(getattr(args, "aoa_root", _core.DEFAULT_AOA_SESSION_MEMORY_ROOT))),
                    target=str(getattr(args, "target", "all")),
                    since=getattr(args, "since", None),
                    since_days=getattr(args, "since_days", None),
                    until=getattr(args, "until", None),
                    limit=getattr(args, "limit", None),
                    write_latest=not bool(getattr(args, "no_write", False)),
                )
            elif command == "self-test":
                data = ai_token_accounting_self_test()
            elif command == "count":
                if getattr(args, "text_file", None):
                    text = Path(str(args.text_file)).read_text(encoding="utf-8", errors="replace")
                elif getattr(args, "text", None) is not None:
                    text = str(args.text)
                else:
                    text = _core.sys.stdin.read()
                data = ai_token_accounting_count_text(
                    profile_name=str(getattr(args, "profile", "gemma4.spark")),
                    text=text,
                    write_latest=not bool(getattr(args, "no_write", False)),
                    timeout=float(getattr(args, "timeout", 60.0)),
                )
            else:
                parser.error("unknown ai token-accounting command")
            if args.json:
                _core.print_json(data)
            else:
                if command == "profiles":
                    summary = data.get("summary", {})
                    print(f"token-accounting profiles: exact_ready={summary.get('exact_ready_profiles')}/{summary.get('profiles')}")
                elif command == "aoa-summary":
                    summary = data.get("summary", {})
                    planning = data.get("planning", {}) if isinstance(data.get("planning"), dict) else {}
                    print(
                        "aoa token summary: "
                        f"ok={data.get('ok')} sessions={summary.get('selected_sessions')} "
                        f"basis={planning.get('primary_basis')} total={planning.get('primary_total_tokens')}"
                    )
                elif command == "self-test":
                    summary = data.get("summary", {})
                    print(f"token-accounting self-test: {summary.get('status')} ({summary.get('fails')} fail, {summary.get('warnings')} warn, {summary.get('checks')} checks)")
                elif command == "count":
                    token = data.get("token_accounting") if isinstance(data.get("token_accounting"), dict) else {}
                    print(f"token count: ok={data.get('ok')} profile={data.get('profile')} total={token.get('total_tokens')} basis={token.get('count_basis')}")
                else:
                    print(f"token-accounting: ok={data.get('ok')} contract={data.get('contract') or data.get('schema')}")
            return 0 if data.get("ok", True) else 1

        if args.ai_command == "llm":
            command = getattr(args, "ai_llm_command", None)
            if command == "paths":
                data = ai_llm_paths()
            elif command == "registry":
                data = ai_llm_registry(write_latest=True)
            elif command == "latest":
                data = ai_llm_latest()
            elif command == "validate":
                data = ai_llm_validate(write_latest=True)
            elif command == "resident":
                resident_command = getattr(args, "ai_llm_resident_command", None)
                out = ai_runtime_adapters.llm_resident_controller_run(
                    controller=_core.AI_LLM_RESIDENT_CONTROLLER,
                    command=resident_command,
                    job_name=str(getattr(args, "job_name", "")) if getattr(args, "job_name", None) else None,
                    jobs_action=str(getattr(args, "jobs_action", "latest")),
                    request_class=str(getattr(args, "request_class", "job")),
                    force=bool(getattr(args, "force", False)),
                    no_generation=bool(getattr(args, "no_generation", False)),
                    limit=getattr(args, "limit", None),
                    json_output=bool(getattr(args, "json", False)),
                    run_command=_core.run,
                )
                projection = ai_runtime_adapters.llm_controller_result_projection(
                    out,
                    json_output=bool(getattr(args, "json", False)),
                    empty_error="resident command produced no output",
                    invalid_json_error="resident command produced invalid JSON",
                )
                if projection.get("format") == "json":
                    _core.print_json(projection.get("data") or {})
                else:
                    print(str(projection.get("text") or ""))
                return int(projection.get("returncode") or 0)
            elif command == "workhorse":
                workhorse_command = getattr(args, "ai_llm_workhorse_command", None)
                out = ai_runtime_adapters.llm_workhorse_controller_run(
                    controller=AI_LLM_WORKHORSE_CONTROLLER,
                    command=workhorse_command,
                    limit=getattr(args, "limit", None),
                    refresh_candidates=bool(getattr(args, "refresh_candidates", False)),
                    run_model=bool(getattr(args, "run_model", False)),
                    n_predict=getattr(args, "n_predict", None),
                    timeout=getattr(args, "timeout", None),
                    json_output=bool(getattr(args, "json", False)),
                    run_command=_core.run,
                )
                projection = ai_runtime_adapters.llm_controller_result_projection(
                    out,
                    json_output=bool(getattr(args, "json", False)),
                    empty_error="workhorse command produced no output",
                    invalid_json_error="workhorse command produced invalid JSON",
                )
                if projection.get("format") == "json":
                    _core.print_json(projection.get("data") or {})
                else:
                    print(str(projection.get("text") or ""))
                return int(projection.get("returncode") or 0)
            else:
                parser.error("unknown ai llm command")
            if args.json:
                _core.print_json(data)
            else:
                if command == "paths":
                    print(f"llm root: {data.get('root')}")
                elif command == "validate":
                    summary = data.get("summary", {})
                    print(f"llm validate: ok={data.get('ok')} fails={summary.get('fails')} warnings={summary.get('warnings')}")
                else:
                    summary = data.get("summary", {})
                    print(f"llm registry: runtime_ok={_core.nested_get(data, ['runtime', 'ok'])} ready={summary.get('ready_profiles')}/{summary.get('profiles')}")
            if command == "validate" and getattr(args, "strict", False) and data.get("summary", {}).get("warnings"):
                return 2
            return 0 if data.get("ok", True) else 1

        if args.ai_command == "cpu":
            command = getattr(args, "ai_cpu_command", None)
            if command == "topology":
                data = _core.ai_cpu_topology(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    _core.print_ai_cpu_topology_text(data)
                return 0 if data.get("ok") else 1
            if command == "thermal-map":
                data = _core.ai_cpu_thermal_map(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    _core.print_ai_cpu_thermal_map_text(data)
                return 0 if data.get("ok") else 1
            if command == "route":
                data = _core.ai_cpu_route(
                    workload_class=getattr(args, "workload_class", "medium"),
                    latency=getattr(args, "latency", "balanced"),
                    force=bool(getattr(args, "force", False)),
                    write_latest=True,
                )
                if args.json:
                    _core.print_json(data)
                else:
                    _core.print_ai_cpu_route_text(data)
                return 0 if data.get("ok") else 1
            if command == "launch":
                data = _core.ai_cpu_launch(
                    command=getattr(args, "launch_command", []),
                    workload_class=getattr(args, "workload_class", "medium"),
                    latency=getattr(args, "latency", "balanced"),
                    force=bool(getattr(args, "force", False)),
                    unattended=bool(getattr(args, "unattended", False)),
                    dry_run=bool(getattr(args, "dry_run", False)),
                    timeout_sec=float(getattr(args, "timeout", 0.0)),
                    write_latest=True,
                )
                if args.json:
                    _core.print_json(data)
                else:
                    _core.print_ai_cpu_launch_text(data)
                return 0 if data.get("ok") else 1
            if command == "test":
                data = _core.ai_cpu_test_profile(
                    getattr(args, "profile", "mixed-safe"),
                    seconds=float(getattr(args, "seconds", 1.0)),
                    force=bool(getattr(args, "force", False)),
                    write_latest=True,
                )
                if args.json:
                    _core.print_json(data)
                else:
                    _core.print_ai_cpu_test_text(data)
                return 0 if data.get("ok") else 1
            parser.error("unknown ai cpu command")

        if args.ai_command == "tts":
            command = getattr(args, "ai_tts_command", None)
            if command == "inventory":
                data = ai_tts_inventory(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_tts_inventory_text(data)
                return 0 if data.get("ok") else 1
            if command == "profiles":
                data = ai_tts_profiles(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_tts_profiles_text(data)
                return 0 if data.get("ok") else 1
            if command == "voices":
                data = ai_tts_voices(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_tts_profiles_text({"summary": {"profiles": len(data.get("voices", [])), "executable": sum(1 for item in data.get("voices", []) if item.get("status") == "executable"), "runtime_missing": 0}, "profiles": {item.get("profile"): item for item in data.get("voices", [])}})
                return 0 if data.get("ok") else 1
            if command == "eval":
                data = ai_tts_eval(getattr(args, "profile", None), force=bool(args.force), allow_download=bool(args.allow_download), write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_tts_eval_text(data)
                return 0 if data.get("ok") else 1
            if command == "compare":
                profiles = [item.strip() for item in str(getattr(args, "profiles", "") or "").split(",") if item.strip()]
                data = ai_tts_compare(
                    profiles,
                    force=bool(args.force),
                    allow_download=bool(args.allow_download),
                    write_latest=True,
                    run_evals=bool(getattr(args, "run", False)),
                )
                if args.json:
                    _core.print_json(data)
                else:
                    ok_count = sum(1 for item in data.get("results", []) if isinstance(item, dict) and item.get("ok"))
                    print(f"tts compare: ok={data.get('ok')} successful={ok_count}/{len(data.get('results', []))} selection={data.get('selection')}")
                return 0 if data.get("ok") else 1
            if command == "server":
                server_command = getattr(args, "ai_tts_server_command", None)
                if server_command == "status":
                    data = ai_tts_server_status(write_latest=True)
                    if args.json:
                        _core.print_json(data)
                    else:
                        ping = data.get("ping", {})
                        print(f"tts server: ok={data.get('ok')} profile={ping.get('profile')} socket={data.get('socket')}")
                    return 0 if data.get("ok") else 1
                if server_command == "stop":
                    data = ai_tts_server_stop(write_latest=True)
                    if args.json:
                        _core.print_json(data)
                    else:
                        print(f"tts server stop: ok={data.get('ok')} socket_exists_after={data.get('socket_exists_after')}")
                    return 0 if data.get("ok") else 1
                if server_command == "run":
                    data = ai_tts_server_run(getattr(args, "profile", None), socket_path=getattr(args, "socket", None))
                    if args.json:
                        _core.print_json(data)
                    return 0 if data.get("ok") else 1
                parser.error("unknown ai tts server command")
            if command == "synth":
                text = args.text
                if args.text_file:
                    try:
                        text = Path(args.text_file).expanduser().read_text(encoding="utf-8")
                    except OSError as exc:
                        data = {
                            "schema": f"{_core.SCHEMA_PREFIX}_ai_tts_synth_v1",
                            "version": _core.VERSION,
                            "generated_at": _core.now_iso(),
                            "ok": False,
                            "error": str(exc),
                            "text_file": args.text_file,
                        }
                        if args.json:
                            _core.print_json(data)
                        else:
                            print_ai_tts_synth_text(data)
                        return 1
                data = ai_tts_synth(
                    getattr(args, "profile", None),
                    text or "",
                    output=getattr(args, "output", None),
                    force=bool(args.force),
                    allow_download=bool(args.allow_download),
                    use_server=not bool(getattr(args, "no_server", False)),
                    write_latest=True,
                )
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_tts_synth_text(data)
                return 0 if data.get("ok") else 1
            parser.error("unknown ai tts command")

        if args.ai_command == "eval":
            suite = "quick" if args.quick else args.suite
            data = ai_eval_quick(suite=suite, write_latest=True, force=bool(args.force))
            if args.json:
                _core.print_json(data)
            else:
                print_ai_eval_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "benchmark":
            if args.real:
                data = ai_eval_quick(suite="quick", write_latest=True, force=bool(args.force))
                if args.json:
                    _core.print_json(data)
                else:
                    print_ai_eval_text(data)
                return 0 if data.get("ok") else 1
            raw_devices = args.devices
            devices = [item.strip().upper() for item in raw_devices.split(",") if item.strip()] if raw_devices else None
            data = ai_benchmark_quick(devices=devices, write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_benchmark_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "capabilities":
            data = ai_capabilities(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_capabilities_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "policy":
            data = ai_policy(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_policy_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "storage":
            if getattr(args, "ai_storage_command", None) == "clean-caches":
                if not args.stack_local_openvino:
                    data = {
                        "schema": f"{_core.SCHEMA_PREFIX}_ai_storage_cleanup_v1",
                        "version": _core.VERSION,
                        "generated_at": _core.now_iso(),
                        "ok": False,
                        "error": "refusing cleanup without --stack-local-openvino",
                    }
                else:
                    data = ai_storage_cleanup_stack_openvino_caches(write_latest=True)
                if args.json:
                    _core.print_json(data)
                else:
                    print(f"removed: {data.get('summary', {}).get('removed_dirs', 0)} errors={data.get('summary', {}).get('errors', 0)}")
                return 0 if data.get("ok") else 1
            data = ai_storage_status(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_storage_text(data)
            return 0

        if args.ai_command == "runtime":
            data = ai_runtime_snapshot(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_runtime_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "report":
            data = ai_report(write_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_report_text(data)
            return 0 if data.get("ok") else 1

        if args.ai_command == "workload":
            command = getattr(args, "ai_workload_command", None)
            if command == "taxonomy":
                data = ai_workload_taxonomy(write_latest=True)
            elif command == "stats":
                ai_workload_refresh_from_latest()
                data = ai_workload_stats(write_latest=True)
            elif command == "refresh":
                data = ai_workload_refresh(write_latest=True, run_probe=False if args.no_probe else None)
            else:
                data = ai_workload_status(write_latest=True, refresh_from_latest=True)
            if args.json:
                _core.print_json(data)
            else:
                print_ai_workload_text(data)
            return 0 if data.get("ok", True) else 1

        if args.ai_command == "config":
            if args.ai_config_command == "get":
                data = ai_config_get()
            else:
                parser.error("unknown ai config command")
            if args.json:
                _core.print_json(data)
            else:
                print(f"path: {data.get('path')}")
                print(f"exists: {data.get('exists')}")
            return 0
    parser.error("unknown command")
    return 64
