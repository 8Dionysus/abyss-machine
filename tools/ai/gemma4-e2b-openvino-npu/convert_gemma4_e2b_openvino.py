#!/usr/bin/env python3
"""Convert Gemma 4 E2B HF source into OpenVINO GenAI VLM artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import os
import platform
import resource
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_MODEL_SIZE = 10_246_621_918
EXPECTED_MODEL_SHA256 = "2db5482b20d746879bb3ef79b5203e9075a2e2b98f54ec7c2f281c1477ddc550"


for name, value in {
    "TOKENIZERS_PARALLELISM": "false",
    "OMP_NUM_THREADS": "6",
    "MKL_NUM_THREADS": "6",
    "OPENBLAS_NUM_THREADS": "6",
    "NUMEXPR_NUM_THREADS": "6",
}.items():
    os.environ.setdefault(name, value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def package_versions() -> dict[str, Any]:
    names = [
        "openvino",
        "openvino-genai",
        "openvino-tokenizers",
        "optimum-intel",
        "optimum",
        "optimum-onnx",
        "transformers",
        "nncf",
        "torch",
        "torchvision",
        "numpy",
        "huggingface-hub",
    ]
    versions: dict[str, Any] = {}
    for name in names:
        try:
            versions[name] = md.version(name)
        except Exception as exc:  # pragma: no cover - diagnostic path
            versions[name] = {"error": repr(exc)}
    return versions


def quant_config(variant: str) -> tuple[dict[str, Any], Any]:
    from optimum.intel.openvino import OVWeightQuantizationConfig

    configs: dict[str, dict[str, Any]] = {
        "int4-sym-g128": {"bits": 4, "sym": True, "group_size": 128, "ratio": 1.0},
        "int4-sym-cw": {"bits": 4, "sym": True, "group_size": -1, "ratio": 1.0},
        "int8-sym": {"bits": 8, "sym": True, "ratio": 1.0},
        "bf16": {},
    }
    params = configs[variant]
    if variant == "bf16":
        return params, None
    return params, OVWeightQuantizationConfig(**params)


def export_tokenizer_models(source_dir: Path, output_dir: Path) -> dict[str, Any]:
    import openvino as ov
    import openvino_tokenizers
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(source_dir, local_files_only=True, trust_remote_code=False)
    tokenizer.save_pretrained(output_dir)
    ov_tokenizer, ov_detokenizer = openvino_tokenizers.convert_tokenizer(
        tokenizer,
        with_detokenizer=True,
        skip_special_tokens=True,
    )
    tokenizer_xml = output_dir / "openvino_tokenizer.xml"
    detokenizer_xml = output_dir / "openvino_detokenizer.xml"
    ov.save_model(ov_tokenizer, tokenizer_xml)
    ov.save_model(ov_detokenizer, detokenizer_xml)
    return {
        "tokenizer_class": type(tokenizer).__name__,
        "openvino_tokenizer_xml": str(tokenizer_xml),
        "openvino_detokenizer_xml": str(detokenizer_xml),
    }


def copy_source_sidecars(source_dir: Path, output_dir: Path) -> list[str]:
    copied: list[str] = []
    for name in (
        "config.json",
        "generation_config.json",
        "processor_config.json",
        "chat_template.jinja",
        "README.md",
    ):
        src = source_dir / name
        if src.exists():
            dst = output_dir / name
            if not dst.exists():
                shutil.copy2(src, dst)
                copied.append(name)
    return copied


def summarize_files(root: Path, hash_files: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        item: dict[str, Any] = {"path": rel, "size_bytes": path.stat().st_size}
        if hash_files:
            item["sha256"] = sha256_file(path)
        rows.append(item)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=("int4-sym-g128", "int4-sym-cw", "int8-sym", "bf16"), required=True)
    parser.add_argument("--method", choices=("ovmodel", "main-export"), default="ovmodel")
    parser.add_argument("--manifest-json", type=Path, required=True)
    parser.add_argument("--expected-size", type=int, default=EXPECTED_MODEL_SIZE)
    parser.add_argument("--expected-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--verify-source-hash", action="store_true")
    parser.add_argument("--hash-output", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--task", default="image-text-to-text")
    parser.add_argument("--model-torch-dtype", choices=("auto", "bfloat16", "float16", "float32", "none"), default="bfloat16")
    parser.add_argument("--stateful", dest="stateful", action="store_true", default=True)
    parser.add_argument("--no-stateful", dest="stateful", action="store_false")
    return parser.parse_args()


def export_with_ovmodel(args: argparse.Namespace, qconfig: Any) -> Any:
    from optimum.intel.openvino import OVModelForVisualCausalLM

    return OVModelForVisualCausalLM.from_pretrained(
        args.source_dir,
        export=True,
        compile=False,
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=qconfig,
        stateful=args.stateful,
    )


def export_with_main_export(args: argparse.Namespace, qconfig: Any, manifest: dict[str, Any]) -> None:
    from optimum.exporters.openvino import main_export
    from optimum.intel.openvino import OVModelForVisualCausalLM

    model_loading_kwargs: dict[str, Any] = {"use_safetensors": True}
    if args.model_torch_dtype != "none":
        model_loading_kwargs["torch_dtype"] = args.model_torch_dtype
    manifest["main_export"] = {
        "task": args.task,
        "stateful": args.stateful,
        "model_loading_kwargs": model_loading_kwargs,
        "export_only": args.export_only,
    }

    export_start = time.perf_counter()
    main_export(
        model_name_or_path=str(args.source_dir),
        output=args.output_dir,
        task=args.task,
        device="cpu",
        framework="pt",
        local_files_only=True,
        trust_remote_code=False,
        model_loading_kwargs=model_loading_kwargs,
        stateful=args.stateful,
        convert_tokenizer=False,
        library_name="transformers",
    )
    manifest["main_export"]["seconds"] = time.perf_counter() - export_start

    if args.export_only or qconfig is None:
        return

    quant_start = time.perf_counter()
    model = OVModelForVisualCausalLM.from_pretrained(
        args.output_dir,
        compile=False,
        local_files_only=True,
        trust_remote_code=False,
        quantization_config=qconfig,
        stateful=args.stateful,
    )
    model.save_pretrained(args.output_dir)
    manifest["main_export"]["post_export_quantization_seconds"] = time.perf_counter() - quant_start


def main() -> int:
    args = parse_args()
    args.manifest_json.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    manifest: dict[str, Any] = {
        "schema": "abyss_machine_gemma4_e2b_openvino_conversion_v1",
        "started_at": now_iso(),
        "ok": False,
        "source_dir": str(args.source_dir),
        "output_dir": str(args.output_dir),
        "variant": args.variant,
        "method": args.method,
        "task": args.task,
        "stateful": args.stateful,
        "export_only": args.export_only,
        "model_torch_dtype": args.model_torch_dtype,
        "python": sys.version,
        "platform": platform.platform(),
        "packages": package_versions(),
        "env": {
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "TOKENIZERS_PARALLELISM",
                "HF_HOME",
                "HUGGINGFACE_HUB_CACHE",
                "TORCH_HOME",
            )
        },
    }
    try:
        model_file = args.source_dir / "model.safetensors"
        if not model_file.exists():
            raise FileNotFoundError(model_file)
        source_size = model_file.stat().st_size
        manifest["source_model"] = {
            "path": str(model_file),
            "size_bytes": source_size,
            "expected_size_bytes": args.expected_size,
        }
        if source_size != args.expected_size:
            raise RuntimeError(f"model.safetensors size {source_size} != expected {args.expected_size}")
        if args.verify_source_hash:
            source_sha = sha256_file(model_file)
            manifest["source_model"]["sha256"] = source_sha
            manifest["source_model"]["expected_sha256"] = args.expected_sha256
            if source_sha != args.expected_sha256:
                raise RuntimeError(f"model.safetensors sha256 {source_sha} != expected {args.expected_sha256}")

        if args.output_dir.exists() and not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force to replace")
        if args.output_dir.exists() and args.force:
            shutil.rmtree(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)

        quant_params, qconfig = quant_config(args.variant)
        manifest["quantization"] = quant_params

        from transformers import AutoProcessor

        processor = AutoProcessor.from_pretrained(args.source_dir, local_files_only=True, trust_remote_code=False)
        processor.save_pretrained(args.output_dir)

        convert_start = time.perf_counter()
        if args.method == "ovmodel":
            model = export_with_ovmodel(args, qconfig)
            model.save_pretrained(args.output_dir)
        else:
            export_with_main_export(args, qconfig, manifest)
        manifest["conversion_seconds"] = time.perf_counter() - convert_start

        tok_start = time.perf_counter()
        manifest["tokenizer_export"] = export_tokenizer_models(args.source_dir, args.output_dir)
        manifest["tokenizer_export_seconds"] = time.perf_counter() - tok_start
        manifest["copied_sidecars"] = copy_source_sidecars(args.source_dir, args.output_dir)
        manifest["output_files"] = summarize_files(args.output_dir, args.hash_output)
        manifest["ok"] = True
        return_code = 0
    except Exception as exc:
        manifest["error"] = repr(exc)
        manifest["traceback"] = traceback.format_exc()
        return_code = 2
    finally:
        manifest["total_seconds"] = time.perf_counter() - started
        manifest["ru_maxrss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        manifest["finished_at"] = now_iso()
        args.manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
