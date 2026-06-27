from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.ai_tts_contracts import (
    TTS_MODEL_REQUIRED_FILES,
    TTS_OPENVINO_REQUIRED_FILES,
    audio_summary,
    babelvox_synth_command,
    babelvox_synth_options,
    babelvox_synth_script,
    compare_document,
    denied_result,
    eval_document,
    model_artifacts,
    openvino_artifacts,
    parse_json_stdout,
    parse_server_response,
    profile_declared_class,
    profile_python,
    profile_slug,
    profile_status,
    qwen3_openvino_synth_command,
    qwen3_openvino_synth_script,
    rtf,
    server_status_document,
    server_stop_document,
    synth_base_document,
    synth_options,
    synth_subprocess_result,
    synth_server_attempt,
    synth_server_request_payload,
    result_error,
    success_index_entry,
    voices_document,
    voices_from_profiles,
)


def test_tts_model_and_openvino_artifact_contract_shapes_are_module_owned() -> None:
    model = model_artifacts(
        "/srv/AbyssOS/abyss-stack/Models/hf/local/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        exists=True,
        required_files={item: True for item in TTS_MODEL_REQUIRED_FILES},
        file_summary={"immediate_files": 4},
        read_only_source=True,
    )
    incomplete_ov = openvino_artifacts(
        "/srv/abyss-machine/runtimes/tts/qwen3",
        exists=True,
        required_files={item: item != "talker.bin" for item in TTS_OPENVINO_REQUIRED_FILES},
        file_summary={"immediate_files": 14},
    )

    assert model["complete"] is True
    assert model["model_type"] == "custom_voice"
    assert model["size_class"] == "1.7B"
    assert model["read_only_source"] is True
    assert model_artifacts(None)["path"] is None
    assert model_artifacts("host-managed")["host_managed"] is True

    assert incomplete_ov["exists"] is True
    assert incomplete_ov["complete"] is False
    assert incomplete_ov["host_managed"] is True
    assert incomplete_ov["required_files"]["talker.bin"] is False


def test_tts_profile_status_contract_separates_runtime_facts_from_decision() -> None:
    profile = {
        "enabled": True,
        "engine": "qwen3_tts_openvino",
        "description": "fixture profile",
        "declared_class": "medium",
        "device": "GPU",
        "language": "Russian",
        "speaker": "Ryan",
        "model_type": "custom_voice",
        "ov_dir": "/srv/abyss-machine/runtimes/tts/qwen3",
        "adapter_src": "/srv/abyss-machine/tools/tts/qwen3",
        "temperature": 0.8,
    }
    inventory = {
        "runtime": {
            "profile_python_modules": {
                "quality": {
                    "ok": True,
                    "modules": {
                        "openvino": {"present": True},
                        "transformers": {"present": True},
                        "pydantic": {"present": True},
                        "soundfile": {"present": True},
                        "numpy": {"present": True},
                    },
                }
            },
            "binaries": {},
        }
    }
    model = model_artifacts("/models/Qwen3-TTS-0.6B-CustomVoice", exists=True, required_files={item: True for item in TTS_MODEL_REQUIRED_FILES})
    ov_model = openvino_artifacts("/runtime/tts", exists=True, required_files={item: True for item in TTS_OPENVINO_REQUIRED_FILES})
    status = profile_status(
        name="quality",
        profile=profile,
        inventory=inventory,
        config={"python": "/venv/bin/python", "language": "Russian"},
        model=model,
        openvino_model=ov_model,
        adapter_ready=True,
        runtime_python="/venv/bin/python",
    )
    missing_adapter = profile_status(
        name="quality",
        profile=profile,
        inventory=inventory,
        config={"python": "/venv/bin/python", "language": "Russian"},
        model=model,
        openvino_model=ov_model,
        adapter_ready=False,
        runtime_python="/venv/bin/python",
    )

    assert status["status"] == "executable"
    assert status["runtime"]["ready"] is True
    assert status["runtime"]["synth_supported"] is True
    assert status["runtime_parameters"] == {
        "temperature": 0.8,
        "model_type": "custom_voice",
        "ov_dir": "/srv/abyss-machine/runtimes/tts/qwen3",
        "adapter_src": "/srv/abyss-machine/tools/tts/qwen3",
    }
    assert status["policy"]["host_layer_mutates_stack"] is False
    assert missing_adapter["status"] == "runtime-missing"
    assert missing_adapter["runtime"]["reason"] == "OpenVINO Qwen3-TTS adapter source is missing"


def test_tts_small_contract_helpers_are_module_owned() -> None:
    assert profile_python({"python": "/custom/python"}, {"python": "/default/python"}) == "/custom/python"
    assert profile_python({}, {"python": "/default/python"}) == "/default/python"
    assert profile_slug("quality fast!") == "quality-fast"
    assert profile_declared_class({"declared_class": "nonsense"}) == "heavy"

    base = {
        "ok": False,
        "policy_denied": True,
        "reasons": ["battery", "thermal"],
    }
    denied = denied_result(base, "quality")
    entry = success_index_entry(
        {
            "schema": "abyss_machine_ai_tts_eval_v1",
            "profile": "quality",
            "generated_at": "2026-06-25T12:00:00+00:00",
            "summary": {"wall_sec": 1.2},
            "result": {"output": "/srv/abyss-machine/state/tts/out.wav"},
        },
        Path("/srv/abyss-machine/state/tts/success/quality.json"),
    )

    assert denied["profile"] == "quality"
    assert denied["non_claims"][0] == "Policy-denied TTS commands do not execute model inference."
    assert result_error(denied) == "policy_denied:battery,thermal"
    assert result_error({"ok": False}) == "synthesis_failed"
    assert result_error({"ok": True}) is None
    assert entry["profile"] == "quality"
    assert entry["result_output"] == "/srv/abyss-machine/state/tts/out.wav"


def test_tts_server_response_and_status_envelopes_are_module_owned() -> None:
    parsed = parse_server_response('debug\n{"ok": true, "profile": "quality"}\n', "/run/tts.sock")
    invalid = parse_server_response("not-json", "/run/tts.sock")
    status = server_status_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        socket_path="/run/tts.sock",
        socket_exists=True,
        ping=parsed,
        service="abyss-tts-server.service",
        latest_path="/var/lib/abyss-machine/ai/tts/server/latest.json",
    )
    stop = server_stop_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:01:00+00:00",
        socket_path="/run/tts.sock",
        socket_exists_after=False,
        response={"ok": True, "command": "shutdown"},
        service="abyss-tts-server.service",
        latest_path="/var/lib/abyss-machine/ai/tts/server/latest.json",
    )

    assert parsed == {"ok": True, "profile": "quality"}
    assert invalid["ok"] is False
    assert invalid["stdout_tail"] == "not-json"
    assert status["schema"] == "abyss_machine_ai_tts_server_status_v1"
    assert status["ok"] is True
    assert status["policy"]["transport"] == "unix_socket_json_line"
    assert stop["socket_exists_after"] is False
    assert stop["response"]["command"] == "shutdown"


def test_tts_voices_and_synth_envelopes_are_module_owned() -> None:
    voices = voices_from_profiles({
        "quality": {
            "status": "executable",
            "engine": "qwen3_tts_openvino",
            "speaker": "Ryan",
            "language": "Russian",
            "device": "GPU",
            "precision": "fp16",
            "declared_class": "medium",
            "description": "quality voice",
        },
        "broken": "not-a-profile",
    })
    voice_doc = voices_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        default_profile="quality",
        voices=voices,
        server={"ok": False},
    )
    profile = {"speaker": "Ryan", "temperature": 0.7, "no_sample": True, "ignored": "x"}
    payload = synth_server_request_payload(
        profile="quality",
        text="hello",
        output="/tmp/out.wav",
        speaker=profile["speaker"],
        language="Russian",
        instruct=None,
        options=synth_options(profile),
    )
    base = synth_base_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        profile="quality",
        engine="qwen3_tts_openvino",
        declared_class="medium",
        device="GPU",
        model={"complete": True},
        text_chars=5,
        output="/tmp/out.wav",
        cache_dir="/srv/abyss-machine/cache/tts",
        allow_download=False,
        policy_gate={"ok": True, "policy_class": "medium"},
        profile_status={"status": "executable"},
        output_under_host_state=False,
    )
    attempt = synth_server_attempt(
        socket_path="/run/tts.sock",
        elapsed_sec=0.1234,
        response={"ok": True, "profile": "quality", "warm": True},
    )
    audio = audio_summary(exists=True, duration_sec=2.0, sample_rate=24000, size_bytes=1234)

    assert voice_doc["voices"][0]["profile"] == "quality"
    assert voice_doc["policy"]["voice_list_is_profile_contract"] is True
    assert payload["command"] == "synth"
    assert payload["options"] == {"temperature": 0.7, "no_sample": True}
    assert base["schema"] == "abyss_machine_ai_tts_synth_v1"
    assert base["policy"]["output_under_host_state"] is False
    assert attempt["elapsed_sec"] == 0.123
    assert attempt["server_profile"] == "quality"
    assert audio["size_bytes"] == 1234
    assert rtf(1.0, 2.0) == 0.5


def test_tts_subprocess_adapter_contracts_are_module_owned() -> None:
    profile = {
        "device": "GPU",
        "precision": "fp16",
        "talker_buckets": [1, 2],
        "temperature": 0.7,
        "no_sample": True,
        "adapter_src": "/srv/abyss-machine/tools/tts/qwen3",
        "ov_dir": "/srv/abyss-machine/runtimes/tts/qwen3",
        "model_type": "custom_voice",
        "cp_device": "",
        "speaker": "Ryan",
        "language": "Russian",
        "instruct": "warm",
    }
    babelvox = babelvox_synth_command(
        python="/venv/bin/python",
        profile=profile,
        config={"language": "Russian"},
        text="hello",
        output="/tmp/out.wav",
        cache_dir="/cache/tts",
    )
    qwen3 = qwen3_openvino_synth_command(
        python="/venv/bin/python",
        profile=profile,
        config={"language": "Russian"},
        text="hello",
        output="/tmp/out.wav",
    )
    parsed = parse_json_stdout('debug\n{"ok": true, "engine": "babelvox"}\n')
    success = synth_subprocess_result(
        {"ok": True, "returncode": 0, "stdout": 'debug\n{"ok": true, "engine": "babelvox"}\n', "stderr": "minor"},
        output_exists=True,
    )
    invalid = synth_subprocess_result(
        {"ok": True, "returncode": 0, "stdout": "not-json", "stderr": "long stderr"},
        output_exists=False,
        stderr_tail_limit=4,
    )

    assert babelvox[:3] == ["/venv/bin/python", "-c", babelvox_synth_script()]
    assert babelvox[3] == "hello"
    assert json.loads(babelvox[-1]) == babelvox_synth_options(profile)
    assert qwen3[:3] == ["/venv/bin/python", "-c", qwen3_openvino_synth_script()]
    assert qwen3[3] == "/srv/abyss-machine/tools/tts/qwen3"
    assert json.loads(qwen3[-1]) == synth_options(profile)
    assert parsed == {"ok": True, "engine": "babelvox"}
    assert success["ok"] is True
    assert success["subprocess"]["engine"] == "babelvox"
    assert invalid["ok"] is False
    assert invalid["subprocess"]["error"] == "TTS subprocess returned invalid JSON"
    assert invalid["stderr_tail"] == "derr"


def test_tts_eval_and_compare_documents_are_module_owned() -> None:
    synth = {
        "ok": True,
        "profile": "quality",
        "device": "GPU",
        "text_chars": 11,
        "output": "/tmp/out.wav",
        "wall_sec": 1.2,
        "rtf": 0.6,
        "audio": {"duration_sec": 2.0, "sample_rate": 24000},
        "subprocess": {"load_sec": 0.3, "synth_sec": 0.9},
        "policy_gate": {"policy_class": "medium"},
    }
    eval_doc = eval_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        profile="quality",
        declared_class="medium",
        text="hello world",
        synth=synth,
        latest_path="/var/lib/abyss-machine/ai/tts/eval/latest.json",
        latest_success_path="/var/lib/abyss-machine/ai/tts/eval/latest-success.json",
        daily_path="/var/lib/abyss-machine/ai/tts/eval/2026-06-25.jsonl",
    )
    compare = compare_document(
        schema_prefix="abyss_machine",
        version="0.8.test",
        generated_at="2026-06-25T12:00:00+00:00",
        requested_profiles=["quality", "fast"],
        evidence_source="latest_success_by_profile",
        results=[
            eval_doc,
            {"ok": True, "profile": "fast", "summary": {"wall_sec": 0.8, "synth_sec": 0.7, "rtf": 0.4}},
        ],
        latest_path="/var/lib/abyss-machine/ai/tts/compare/latest.json",
        daily_path="/var/lib/abyss-machine/ai/tts/compare/2026-06-25.jsonl",
        latest_success_path="/var/lib/abyss-machine/ai/tts/eval/latest-success.json",
        latest_success_by_profile_path="/var/lib/abyss-machine/ai/tts/eval/latest-success-by-profile.json",
        success_by_profile_root="/var/lib/abyss-machine/ai/tts/eval/success-by-profile",
    )

    assert eval_doc["schema"] == "abyss_machine_ai_tts_eval_v1"
    assert eval_doc["summary"]["load_sec"] == 0.3
    assert eval_doc["summary"]["policy_class"] == "medium"
    assert eval_doc["policy"]["host_layer_mutates_stack"] is False
    assert compare["schema"] == "abyss_machine_ai_tts_compare_v1"
    assert compare["selection"]["default_quality"] == "quality"
    assert compare["selection"]["default_fast"] == "fast"
    assert compare["policy"]["default_compare_runs_no_model_execution"] is True
