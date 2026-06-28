from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from . import nervous_rerank


RunCommand = Callable[[list[str], float, Mapping[str, str] | None], Mapping[str, Any]]
ResourceSnapshot = Callable[[], Mapping[str, Any]]
ResourceProfile = Callable[[Mapping[str, Any], Mapping[str, Any], str, str], Mapping[str, Any]]
PolicyGate = Callable[[], Mapping[str, Any]]
TimeNs = Callable[[], int]


def _parse_json_stdout(stdout: str) -> dict[str, Any] | None:
    stdout = str(stdout or "").strip()
    if not stdout:
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            return data if isinstance(data, dict) else None
        marker = stdout.rfind("\n{")
        if marker < 0:
            return None
        try:
            data = json.loads(stdout[marker + 1 :])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _load_json_document(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def score_with_subprocess(
    query: str,
    items: list[dict[str, Any]],
    *,
    config: Mapping[str, Any],
    model_dir: Path,
    scorer: Path,
    python: str,
    tmp_root: Path,
    run_command: RunCommand,
    env: Mapping[str, str] | None,
    resource_snapshot: ResourceSnapshot,
    resource_profile: ResourceProfile,
    policy_gate: PolicyGate,
    cache_dir: Path,
    time_ns: TimeNs = time.time_ns,
) -> dict[str, Any]:
    if not bool(config.get("enabled")):
        return {"ok": False, "skipped": True, "reason": "neural rerank disabled"}
    if not model_dir.exists():
        return {"ok": False, "error": f"neural reranker model missing: {model_dir}", "model_dir": str(model_dir)}
    if not scorer.exists():
        return {"ok": False, "error": f"neural reranker scorer missing: {scorer}", "scorer": str(scorer)}
    if not python or not Path(str(python)).exists():
        return {"ok": False, "error": "abyss-openvino-python not found"}

    gate = dict(policy_gate())
    if not gate.get("ok"):
        return {"ok": False, "policy_denied": True, "error": "host AI policy denied neural rerank", "policy_gate": gate}

    docs = []
    for item in items:
        text = nervous_rerank.neural_text(item)
        if not text:
            continue
        docs.append({"id": str(item.get("chunk_id") or item.get("doc_id") or len(docs)), "text": text})
    if not docs:
        return {"ok": False, "error": "no documents to score", "policy_gate": gate}

    try:
        tmp_root.mkdir(parents=True, exist_ok=True)
        identity = hashlib.sha256(f"{query}\n{time_ns()}".encode("utf-8", errors="replace")).hexdigest()[:16]
        input_path = tmp_root / f"score-{identity}.input.json"
        output_path = tmp_root / f"score-{identity}.output.json"
        payload = {
            "query": query,
            "instruction": config.get("instruction"),
            "documents": docs,
        }
        input_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
        command = [
            str(python),
            str(scorer),
            "--model-dir",
            str(model_dir),
            "--device",
            str(config.get("device") or "GPU"),
            "--cache-dir",
            str(cache_dir),
            "--max-length",
            str(int(config.get("max_length") or 2048)),
            "--batch-size",
            str(int(config.get("batch_size") or 4)),
            "--score-input",
            str(input_path),
            "--output",
            str(output_path),
        ]
        resources_before = dict(resource_snapshot())
        completed = run_command(
            command,
            float(config.get("timeout_sec") or 240),
            dict(env) if env is not None else None,
        )
        resources_after = dict(resource_snapshot())
        stdout = str(completed.get("stdout") or "")
        data = _parse_json_stdout(stdout)
        if data is None and output_path.exists():
            data = _load_json_document(output_path)
        if data is None:
            data = {"ok": False, "error": "neural scorer returned invalid JSON", "stdout_tail": stdout[-1000:]}
        data.update(
            {
                "returncode": completed.get("returncode"),
                "stderr_tail": str(completed.get("stderr") or "")[-2000:],
                "policy_gate": gate,
                "resource_profile": dict(
                    resource_profile(
                        resources_before,
                        resources_after,
                        "child_process",
                        "OpenVINO Qwen3 neural rerank scorer",
                    )
                ),
                "input_path": str(input_path),
                "output_path": str(output_path),
                "command": command,
            }
        )
        data["ok"] = bool(data.get("ok") and completed.get("returncode") == 0)
        return data
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc), "policy_gate": gate}
