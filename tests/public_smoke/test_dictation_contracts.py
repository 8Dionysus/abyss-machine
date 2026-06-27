from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from abyss_machine.dictation_contracts import (
    apply_replacements,
    auto_select_profile,
    build_replacement_item,
    busy_result,
    calibration_recording_command,
    default_config,
    default_replacements_document,
    detect_intent,
    helper_failure_result,
    helper_invalid_json_result,
    helper_success_result,
    helper_transcript_command,
    insert_empty_result,
    insert_error_result,
    insert_final_result,
    insert_wtype_success_result,
    journal_entry_id,
    journal_event,
    journal_markdown,
    max_seconds,
    mic_calibration_error_result,
    mic_calibration_result,
    normalize_clipboard_provider,
    normalize_paste_combo,
    paste_combo_order,
    paste_key_sequence,
    parse_transcript_json,
    postprocess_options,
    postprocess_transcript_data,
    recording_command,
    recording_state,
    recommended_audio_runtime,
    replacements_test_document,
    requested_profile_name,
    runtime_env,
    runtime_options,
    server_transcript_request,
    server_transcript_result_from_raw,
    stale_missing_audio_transcript,
    stop_inactive_result,
    stopped_recording_result,
    summarize_audio_stats,
    transcript_error_result,
    toggle_result,
    validate_config,
    validate_replacements_document,
)


def test_dictation_profile_runtime_contracts_are_module_owned() -> None:
    config = default_config("abyss_machine", "test")
    assert validate_config(config) == []

    profile = {
        "runtime": {"vad_segments": False, "target_rms_dbfs": -26.0},
        "postprocess": {"punctuation_style": "off"},
    }
    env = {
        "ABYSS_DICTATION_TARGET_RMS_DBFS": "-99",
        "ABYSS_DICTATION_VAD_SEGMENTS": "1",
        "ABYSS_DICTATION_SMART_PUNCTUATION": "1",
        "ABYSS_DICTATION_PROFILE": "not-a-profile",
    }

    runtime = runtime_options(profile, config, env)
    postprocess = postprocess_options(profile, config, env)

    assert runtime["target_rms_dbfs"] == -36.0
    assert runtime["vad_segments"] is True
    assert postprocess["punctuation_style"] == "off"
    assert postprocess["smart_punctuation"] is True
    assert requested_profile_name(None, config, env) == "quality"

    selected, selection = auto_select_profile(
        {"ok": True, "duration_sec": 60.0, "dbfs": -21.0, "peak": 0.4, "clip_percent": 0.0},
        config,
        {"quality": {"enabled": True}, "long": {"enabled": True}},
        {},
    )
    assert selected == "long"
    assert selection["reason"] == "long-recording"

    assert runtime_env({"vad_segments": False, "max_gain": 3.5}, {"KEEP": "1"})["ABYSS_DICTATION_VAD_SEGMENTS"] == "0"
    assert max_seconds({"ABYSS_DICTATION_MAX_SECONDS": "9999"}, 180) == 3600
    assert busy_result("toggle", "abyss_machine", "test", "2026-06-25T12:00:00+00:00")["error"] == "dictation is busy"


def test_dictation_insert_result_and_key_sequence_contracts_are_module_owned() -> None:
    assert normalize_clipboard_provider("weird") == "foreground"
    assert normalize_clipboard_provider("daemon") == "daemon"
    assert normalize_paste_combo("ctrl-shift-v") == "ctrl-shift-v"
    assert normalize_paste_combo("bad") == "ctrl-v"
    assert paste_combo_order("auto") == ["ctrl-v"]
    assert paste_key_sequence("ctrl-shift-v")[:3] == ["47:0", "29:0", "42:0"]
    assert paste_key_sequence("ctrl-shift-v")[10:16] == ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]

    generated_at = "2026-06-25T12:00:00+00:00"
    empty = insert_empty_result("abyss_machine", "test", generated_at)
    failed = insert_error_result("wl-copy not found", "abyss_machine", "test", generated_at)
    wtype = insert_wtype_success_result("hello", "abyss_machine", "test", generated_at)
    final = insert_final_result(
        text="hello",
        clipboard_provider="invalid",
        copy_returncode=0,
        attempts=[
            {"combo": "ctrl-v", "returncode": 1, "stderr": "first fail", "paste_sent": False},
            {"combo": "ctrl-v", "returncode": 0, "stderr": "", "paste_sent": True},
        ],
        fallback={"method": "wtype", "returncode": 1, "stderr": "not wayland"},
        copy_stderr="",
        combo_name="bad",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )

    assert empty["schema"] == "abyss_machine_dictation_insert_v1"
    assert empty["error"] == "empty text"
    assert failed["error"] == "wl-copy not found"
    assert wtype["ok"] is True
    assert wtype["method"] == "wtype"
    assert final["ok"] is True
    assert final["method"] == "wl-copy+ydotool-ctrl-v"
    assert final["clipboard_provider"] == "foreground"
    assert final["paste_sent"] is True
    assert final["fallback"]["method"] == "wtype"
    assert final["stderr"] == "first fail"


def test_dictation_recording_lifecycle_contracts_are_module_owned() -> None:
    generated_at = "2026-06-25T12:00:00+00:00"
    command = recording_command(
        "/run/user/1000/abyss-machine/dictation/dictation-20260625.wav",
        max_seconds_value=180,
        timeout_available=True,
    )
    state = recording_state(
        pid=4242,
        audio_path="/run/user/1000/abyss-machine/dictation/dictation-20260625.wav",
        log_path="/run/user/1000/abyss-machine/dictation/dictation-20260625.log",
        profile="quality",
        started_at=generated_at,
        max_seconds_value=180,
        schema_prefix="abyss_machine",
    )
    inactive = stop_inactive_result("abyss_machine", "test", generated_at)
    stopped = stopped_recording_result(
        state,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )
    stale_transcript = stale_missing_audio_transcript("abyss_machine", "test", generated_at)
    toggle = toggle_result(
        action="transcribe-stale",
        recording=stopped,
        transcript=stale_transcript,
        status={"recording_active": False},
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )

    assert command[:4] == ["timeout", "--signal=INT", "--kill-after=5s", "180s"]
    assert command[-8:] == ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "/run/user/1000/abyss-machine/dictation/dictation-20260625.wav"]
    assert recording_command("/tmp/a.wav", max_seconds_value=0, timeout_available=True)[0] == "pw-record"
    assert state["schema"] == "abyss_machine_dictation_recording_v1"
    assert state["pid"] == 4242
    assert inactive["schema"] == "abyss_machine_dictation_stop_v1"
    assert inactive["stopped"] is False
    assert stopped["schema"] == "abyss_machine_dictation_stop_v1"
    assert stopped["stopped"] is True
    assert stopped["audio"] == state["audio"]
    assert stale_transcript["error"] == "stale recording has no audio path"
    assert toggle["schema"] == "abyss_machine_dictation_toggle_v1"
    assert toggle["action"] == "transcribe-stale"
    assert toggle["recording"]["stopped"] is True
    assert toggle["transcript"]["ok"] is False


def test_dictation_audio_doctor_summary_contracts_are_module_owned() -> None:
    stats = [
        {
            "ok": True,
            "dbfs": -31.2,
            "peak": 0.2,
            "clip_percent": 0.0,
            "frame_dbfs_p10": -48.0,
            "frame_dbfs_p50": -33.0,
            "frame_dbfs_p90": -25.0,
        },
        {
            "ok": True,
            "dbfs": -29.8,
            "peak": 0.18,
            "clip_percent": 0.0,
            "frame_dbfs_p10": -46.0,
            "frame_dbfs_p50": -31.0,
            "frame_dbfs_p90": -24.0,
        },
        {"ok": False, "error": "bad wav"},
    ]

    summary = summarize_audio_stats(stats)
    runtime = recommended_audio_runtime(summary)

    assert summary["files_analyzed"] == 2
    assert summary["avg_dbfs"] == -30.5
    assert summary["noise_floor_dbfs"] == -47.0
    assert summary["recommendation"] == "input is clean but quiet; digital normalization before Whisper is useful"
    assert runtime["target_rms_dbfs"] == -24.0
    assert runtime["max_gain"] == 5.0
    assert summarize_audio_stats([])["recommendation"] == "no recent dictation wav files"
    assert recommended_audio_runtime({"avg_dbfs": -20.0, "max_clip_percent": 0.1})["max_gain"] == 2.0


def test_dictation_mic_calibration_contracts_are_module_owned() -> None:
    command = calibration_recording_command("/tmp/mic.wav", seconds=8, timeout_available=True)
    error = mic_calibration_error_result(
        error="pw-record not found",
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )
    summary = {
        "files_analyzed": 1,
        "avg_dbfs": -30.0,
        "max_clip_percent": 0.0,
        "recommendation": "input is clean but quiet; digital normalization before Whisper is useful",
    }
    recommended = recommended_audio_runtime(summary)
    result = mic_calibration_result(
        source="recorded",
        recorded_path="/tmp/mic.wav",
        summary=summary,
        recommended_runtime=recommended,
        schema_prefix="abyss_machine",
        version="test",
        generated_at="2026-06-25T12:00:00+00:00",
    )

    assert command[:4] == ["timeout", "--signal=INT", "--kill-after=3s", "8s"]
    assert command[-8:] == ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "/tmp/mic.wav"]
    assert calibration_recording_command("/tmp/mic.wav", seconds=8, timeout_available=False)[0] == "pw-record"
    assert error["schema"] == "abyss_machine_dictation_mic_calibration_v1"
    assert error["ok"] is False
    assert result["ok"] is True
    assert result["source"] == "recorded"
    assert result["recorded_path"] == "/tmp/mic.wav"
    assert result["applied"] is False


def test_dictation_cli_recording_wrapper_uses_contract_shapes() -> None:
    from abyss_machine import cli

    command = cli.dictation_contracts.recording_command(
        "/tmp/dictation.wav",
        max_seconds_value=10,
        timeout_available=False,
    )
    state = cli.dictation_contracts.recording_state(
        pid=7,
        audio_path="/tmp/dictation.wav",
        log_path="/tmp/dictation.log",
        profile="fast",
        started_at="2026-06-25T12:00:00+00:00",
        max_seconds_value=10,
        schema_prefix=cli.SCHEMA_PREFIX,
    )
    assert command == ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", "/tmp/dictation.wav"]
    assert state["schema"] == "abyss_machine_dictation_recording_v1"
    summary = cli.summarize_audio_stats([
        {"ok": True, "dbfs": -20.0, "peak": 0.4, "clip_percent": 0.0},
    ])
    assert cli.recommended_audio_runtime(summary) == recommended_audio_runtime(summary)
    assert cli.dictation_contracts.calibration_recording_command("/tmp/mic.wav", seconds=5, timeout_available=False)[0] == "pw-record"


def test_dictation_transcript_server_and_helper_contracts_are_module_owned() -> None:
    generated_at = "2026-06-25T12:00:00+00:00"
    profile = {
        "name": "quality",
        "model_dir": "/srv/abyss-machine/runtimes/dictation/whisper",
        "device": "CPU",
        "language": "ru",
        "runtime": {"vad_segments": True},
    }
    selection = {"reason": "default-quality"}
    request = server_transcript_request(
        audio="/run/audio-16k.wav",
        profile=profile,
        runtime_options=profile["runtime"],
        max_new_tokens=192,
        num_beams=3,
    )
    server = server_transcript_result_from_raw(
        '{"ok": true, "text": "hello", "audio": "/run/audio-16k.wav"}',
        profile=profile,
        socket_path="/run/dictation.sock",
        client_elapsed_sec=1.2345,
        client_preprocess={"ok": True, "output": "/run/audio-16k.wav"},
        original_audio="/tmp/audio.wav",
        server_audio="/run/audio-16k.wav",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )
    invalid_server = server_transcript_result_from_raw(
        "not json",
        profile=profile,
        socket_path="/run/dictation.sock",
        client_elapsed_sec=0.1,
        client_preprocess=None,
        original_audio="/tmp/audio.wav",
        server_audio="/tmp/audio.wav",
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )
    command = helper_transcript_command(
        helper="/usr/local/libexec/abyss-machine/dictation/transcribe",
        audio="/tmp/audio.wav",
        model_dir=profile["model_dir"],
        profile=profile,
        max_new_tokens=256,
        num_beams=1,
    )
    parsed = parse_transcript_json('noise\n{"ok": true, "text": "hello"}')
    failed = helper_failure_result(
        {"stderr": "model failed", "stdout": ""},
        profile=profile,
        profile_selection=selection,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )
    invalid_helper = helper_invalid_json_result(
        "bad stdout",
        "bad stderr",
        profile=profile,
        profile_selection=selection,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )
    success = helper_success_result(
        {"text": "hello"},
        profile=profile,
        profile_selection=selection,
        client_elapsed_sec=2.3456,
    )
    missing = transcript_error_result(
        "model directory missing: /missing",
        profile=profile,
        profile_selection=selection,
        schema_prefix="abyss_machine",
        version="test",
        generated_at=generated_at,
    )

    assert request["task"] == "transcribe"
    assert request["runtime"] == {"vad_segments": True}
    assert server is not None and server["schema"] == "abyss_machine_dictation_transcript_v1"
    assert server["audio"] == "/tmp/audio.wav"
    assert server["server_audio"] == "/run/audio-16k.wav"
    assert server["client_elapsed_sec"] == 1.234
    assert invalid_server is not None and invalid_server["error"] == "dictation server returned invalid JSON"
    assert command[-5:] == ["--max-new-tokens", "256", "--num-beams", "1", "--json"]
    assert parsed == {"ok": True, "text": "hello"}
    assert failed["error"] == "model failed"
    assert invalid_helper["stdout_tail"] == "bad stdout"
    assert success["ok"] is True
    assert success["via"] == "helper"
    assert success["client_elapsed_sec"] == 2.346
    assert missing["profile_selection"] == selection


def test_dictation_replacements_postprocess_and_intent_are_portable_contracts() -> None:
    config = default_config("abyss_machine", "test")
    replacements_doc = default_replacements_document("abyss_machine", "test")
    assert validate_replacements_document(replacements_doc) == []

    fixed, applied = apply_replacements("абис машина читает agents md", replacements_doc["items"])
    assert fixed == "abyss-machine читает AGENTS.md"
    assert {"abyss-machine-name", "agents-md-spaced"}.issubset(set(applied))

    item = build_replacement_item("literal", "Tree of Sofia", "Tree of Sophia", "tree-fix", True)
    literal_doc = {"items": [item]}
    test_doc = replacements_test_document(
        "tree of sofia",
        literal_doc,
        generated_at="2026-06-25T12:00:00+00:00",
        schema_prefix="abyss_machine",
        version="test",
    )
    assert test_doc["output"] == "Tree of Sophia"
    assert test_doc["applied"] == ["tree-fix"]

    transcript = postprocess_transcript_data(
        {"ok": True, "text": "команда открой agents md"},
        {"postprocess": {"text_fixes": True, "final_punctuation": True, "final_space": True}},
        config=config,
        replacements_doc=replacements_doc,
        schema_prefix="abyss_machine",
    )
    assert transcript["text"] == "Команда открой AGENTS.md. "
    assert transcript["raw_text"] == "команда открой agents md"
    assert transcript["intent"]["type"] == "command"
    assert transcript["intent"]["payload"] == "открой AGENTS.md."

    assert detect_intent("просто текст", config, "abyss_machine")["reason"] == "no-trigger-prefix"


def test_dictation_journal_contract_shapes_are_independent_from_live_audio() -> None:
    result = {
        "generated_at": "2026-06-25T12:00:00+00:00",
        "action": "insert",
        "recording": {
            "profile": "auto",
            "audio": "/tmp/dictation.wav",
            "started_at": "2026-06-25T11:59:58+00:00",
            "generated_at": "2026-06-25T12:00:00+00:00",
            "max_seconds": 180,
            "log": "/tmp/dictation.log",
        },
        "transcript": {
            "ok": True,
            "text": "Abyss online. ",
            "raw_text": "abyss online",
            "profile": {
                "name": "quality",
                "device": "CPU",
                "model_id": "openai/whisper-large-v3-turbo",
                "model_dir": "/srv/abyss-machine/runtimes/dictation/whisper",
            },
            "num_beams": 3,
            "via": "server",
            "elapsed_sec": 1.2,
            "client_elapsed_sec": 1.4,
            "postprocess": {"capitalization": True},
            "intent": {"type": "dictation", "triggered": False},
        },
        "insert": {"ok": True, "method": "ydotool", "stderr": "", "attempts": 1},
    }
    event_id = journal_entry_id(result, "/tmp/dictation.wav", "2026-06-25T12:00:01+00:00")
    event = journal_event(
        result,
        include_failed=True,
        audio_metadata={"path": "/tmp/dictation.wav", "exists": False},
        event_id=event_id,
        generated_at="2026-06-25T12:00:01+00:00",
        paths={"jsonl": "/tmp/day.jsonl", "readable": "/tmp/day.md", "latest": "/tmp/latest.json"},
        schema_prefix="abyss_machine",
        version="test",
    )

    assert event is not None
    assert event["id"] == event_id
    assert event["profile"]["selected"] == "quality"
    assert event["paths"]["latest"] == "/tmp/latest.json"

    markdown = journal_markdown(event, include_header=True, day="2026-06-25")
    assert markdown.startswith("# Dictation Journal - 2026-06-25")
    assert "Abyss online." in markdown
    assert "Raw:" in markdown
