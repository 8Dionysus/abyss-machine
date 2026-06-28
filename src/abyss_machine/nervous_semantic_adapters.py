from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping

from . import nervous_semantic


RunCommand = Callable[[list[str], float, Mapping[str, str] | None], Mapping[str, Any]]
ResourceSnapshot = Callable[[], Mapping[str, Any]]
ResourceProfile = Callable[[Mapping[str, Any], Mapping[str, Any], str, str], Mapping[str, Any]]


def embed_texts_with_subprocess(
    text_items: list[dict[str, str]],
    *,
    embedding: Mapping[str, Any],
    model_dir: Path,
    device: str,
    cache_dir: Path,
    python: str,
    tmp_root: Path,
    run_command: RunCommand,
    env: Mapping[str, str] | None,
    resource_snapshot: ResourceSnapshot,
    resource_profile: ResourceProfile,
) -> dict[str, Any]:
    if not text_items:
        return {"ok": True, "vectors": {}, "summary": {"items": 0}}

    if not model_dir.exists():
        return {"ok": False, "error": f"embedding model directory missing: {model_dir}"}
    if not python or not Path(str(python)).exists():
        return {"ok": False, "error": "abyss-openvino-python not found"}

    options = nervous_semantic.embedding_runtime_options(dict(embedding))
    tmp_root.mkdir(parents=True, exist_ok=True)
    input_path: Path | None = None
    output_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(tmp_root),
            prefix="embed-input-",
            suffix=".jsonl",
            delete=False,
        ) as handle:
            input_path = Path(handle.name)
            handle.write(nervous_semantic.embedding_input_jsonl(text_items))
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(tmp_root),
            prefix="embed-output-",
            suffix=".jsonl",
            delete=False,
        ) as handle:
            output_path = Path(handle.name)

        resources_before = dict(resource_snapshot())
        command = nervous_semantic.embedding_subprocess_command(
            python=str(python),
            input_path=str(input_path),
            output_path=str(output_path),
            model_dir=str(model_dir),
            device=str(device),
            cache_dir=str(cache_dir),
            options=options,
        )
        completed = run_command(
            command,
            float(options.get("timeout_sec") or 1800),
            dict(env) if env is not None else None,
        )
        resources_after = dict(resource_snapshot())
        output_jsonl = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
        return nervous_semantic.embedding_subprocess_result(
            stdout=str(completed.get("stdout") or ""),
            stderr=str(completed.get("stderr") or ""),
            returncode=completed.get("returncode"),
            output_jsonl=output_jsonl,
            expected_items=len(text_items),
            resource_profile=dict(resource_profile(resources_before, resources_after, "child_process", "semantic embedding batch")),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        for path in (input_path, output_path):
            if isinstance(path, Path):
                try:
                    path.unlink()
                except OSError:
                    pass
