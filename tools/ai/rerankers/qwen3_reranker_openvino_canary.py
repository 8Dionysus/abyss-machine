#!/usr/bin/env python3
import argparse
import json
import os
import resource
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_INSTRUCTION = "Given a local machine memory search query, retrieve relevant evidence chunks that answer the query"
PREFIX = (
    "<|im_start|>system\n"
    "Judge whether the Document meets the requirements based on the Query and the Instruct provided. "
    "Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n"
    "<|im_start|>user\n"
)
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


SYNTHETIC_CASES = [
    {
        "id": "zram_memory_pressure",
        "query": "zram_data_mib zram_resident_mib swap_used_percent psi memory pressure",
        "relevant": "memory_pressure_latest reports zram_data_mib, zram_resident_mib, swap_used_percent and PSI memory pressure for the local host.",
        "irrelevant": "Firefox active tab title and a clipboard fragment about a website navigation item.",
    },
    {
        "id": "dictation_tts_services",
        "query": "dictation server TTS service active running local speech stack",
        "relevant": "systemd user units abyss-dictation-server.service and abyss-tts-server.service are active/running and protect speech input and output.",
        "irrelevant": "A historical browser capture mentions unrelated model release notes and page headings.",
    },
    {
        "id": "gemma_resident",
        "query": "Gemma 4 E2B llama.cpp resident service batch ubatch context",
        "relevant": "abyss-gemma4-spark.service runs Gemma 4 E2B through llama.cpp with batch and ubatch tuning and ctx 4096.",
        "irrelevant": "A storage cleanup plan lists browser automation cache paths and old temporary files.",
    },
    {
        "id": "thermal_hot_policy",
        "query": "thermal hot threshold 105 106 critical 109 thin laptop routing",
        "relevant": "Host policy says stable 100-105C is monitored active range, hot starts near 106C, and critical behavior is reserved near 109-110C.",
        "irrelevant": "A note about reranking UI settings does not mention thermal thresholds or CPU routing.",
    },
]


LIVE_QUERIES = [
    {
        "id": "zram_live",
        "query": "zram_data_mib zram_resident_mib swap_used_percent psi memory pressure",
        "preferred_sources": {"abyss_machine_facts", "nervous_events", "nervous_episodes", "systemd_metadata", "podman_metadata"},
        "context_sources": {"browser_active_tab", "clipboard", "screenshots", "audio_transcript_autolog"},
    },
    {
        "id": "tts_dictation_live",
        "query": "abyss dictation tts server service active running speech",
        "preferred_sources": {"systemd_metadata", "abyss_machine_facts", "nervous_events", "nervous_episodes"},
        "context_sources": {"browser_active_tab", "clipboard", "screenshots", "audio_transcript_autolog"},
    },
    {
        "id": "gemma_live",
        "query": "Gemma 4 E2B llama.cpp resident batch ubatch ctx service",
        "preferred_sources": {"systemd_metadata", "abyss_machine_facts", "nervous_events", "nervous_episodes"},
        "context_sources": {"browser_active_tab", "clipboard", "screenshots", "audio_transcript_autolog"},
    },
    {
        "id": "thermal_live",
        "query": "thermal hot threshold 105 106 critical 109 cpu route",
        "preferred_sources": {"abyss_machine_facts", "nervous_events", "nervous_episodes"},
        "context_sources": {"browser_active_tab", "clipboard", "screenshots", "audio_transcript_autolog"},
    },
]


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def format_instruction(instruction: str | None, query: str, doc: str) -> str:
    instruction = instruction or DEFAULT_INSTRUCTION
    return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"


def doc_text(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").strip()
    snippet = str(item.get("snippet") or item.get("body_preview") or "").strip()
    source = str(item.get("source_id") or "").strip()
    schema = str(item.get("document_schema") or "").strip()
    parts = []
    if source or schema:
        parts.append(f"Source: {source} {schema}".strip())
    if title:
        parts.append(f"Title: {title}")
    if snippet:
        parts.append(snippet)
    return "\n".join(parts).strip()


def sigmoid(x: float) -> float:
    import math

    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class Qwen3OpenVINOReranker:
    def __init__(self, model_dir: Path, device: str, cache_dir: Path, max_length: int, batch_size: int):
        self.model_dir = model_dir
        self.device = device
        self.cache_dir = cache_dir
        self.max_length = max_length
        self.batch_size = batch_size
        self.load_sec = 0.0
        self.tokenizer_sec = 0.0

    def load(self) -> None:
        started = time.perf_counter()
        import torch
        from transformers import AutoTokenizer
        from optimum.intel.openvino import OVModelForCausalLM

        tok_started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_dir,
            padding_side="left",
            local_files_only=True,
            fix_mistral_regex=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer_sec = time.perf_counter() - tok_started
        self.model = OVModelForCausalLM.from_pretrained(
            self.model_dir,
            device=self.device,
            ov_config={"CACHE_DIR": str(self.cache_dir)},
            use_cache=False,
            export=False,
            local_files_only=True,
        )
        self.model.eval()
        self.torch = torch
        self.token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        self.token_true_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.prefix_tokens = self.tokenizer.encode(PREFIX, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(SUFFIX, add_special_tokens=False)
        self.load_sec = time.perf_counter() - started

    def _process(self, pairs: list[str]) -> dict[str, Any]:
        inputs = self.tokenizer(
            pairs,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens),
        )
        for index, item in enumerate(inputs["input_ids"]):
            inputs["input_ids"][index] = self.prefix_tokens + item + self.suffix_tokens
        return self.tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=self.max_length)

    def score(self, query: str, documents: list[str], instruction: str | None = DEFAULT_INSTRUCTION) -> dict[str, Any]:
        scores: list[float] = []
        raw_scores: list[float] = []
        tokenize_ms = 0.0
        infer_ms = 0.0
        for offset in range(0, len(documents), self.batch_size):
            batch = documents[offset : offset + self.batch_size]
            pairs = [format_instruction(instruction, query, doc) for doc in batch]
            tokenize_started = now_ms()
            inputs = self._process(pairs)
            tokenize_ms += now_ms() - tokenize_started
            infer_started = now_ms()
            with self.torch.no_grad():
                logits = self.model(**inputs).logits[:, -1, :]
                true_vector = logits[:, self.token_true_id]
                false_vector = logits[:, self.token_false_id]
                two = self.torch.stack([false_vector, true_vector], dim=1)
                log_probs = self.torch.nn.functional.log_softmax(two, dim=1)
                batch_scores = log_probs[:, 1].exp().detach().cpu().tolist()
                raw = (true_vector - false_vector).detach().cpu().tolist()
            infer_ms += now_ms() - infer_started
            scores.extend(float(item) for item in batch_scores)
            raw_scores.extend(float(item) for item in raw)
        return {
            "scores": scores,
            "raw_logit_diff": raw_scores,
            "tokenize_ms": round(tokenize_ms, 3),
            "infer_ms": round(infer_ms, 3),
            "documents": len(documents),
        }


def run_current_rerank(query: str, limit: int) -> dict[str, Any]:
    proc = subprocess.run(
        [
            "abyss-machine",
            "nervous",
            "rerank",
            "--query",
            query,
            "--limit",
            str(limit),
            "--candidate-limit",
            str(limit),
            "--json",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    try:
        parsed = json.loads(proc.stdout)
    except json.JSONDecodeError:
        parsed = {"ok": False, "error": "invalid JSON", "stdout_tail": proc.stdout[-1000:]}
    parsed.setdefault("returncode", proc.returncode)
    if proc.stderr.strip():
        parsed["stderr_tail"] = proc.stderr[-1000:]
    return parsed


def evaluate_synthetic(reranker: Qwen3OpenVINOReranker) -> dict[str, Any]:
    checks = []
    for case in SYNTHETIC_CASES:
        result = reranker.score(case["query"], [case["relevant"], case["irrelevant"]])
        relevant = result["scores"][0]
        irrelevant = result["scores"][1]
        raw_margin = result["raw_logit_diff"][0] - result["raw_logit_diff"][1]
        checks.append(
            {
                "id": case["id"],
                "ok": relevant > irrelevant and raw_margin > 0.0,
                "relevant_score": round(relevant, 6),
                "irrelevant_score": round(irrelevant, 6),
                "probability_margin": round(relevant - irrelevant, 6),
                "raw_logit_margin": round(raw_margin, 6),
                "timing": {key: result[key] for key in ("tokenize_ms", "infer_ms", "documents")},
            }
        )
    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "fails": sum(1 for item in checks if not item["ok"]),
            "min_probability_margin": min((item["probability_margin"] for item in checks), default=None),
            "min_raw_logit_margin": min((item["raw_logit_margin"] for item in checks), default=None),
        },
    }


def evaluate_live(reranker: Qwen3OpenVINOReranker, limit: int) -> dict[str, Any]:
    queries = []
    for spec in LIVE_QUERIES:
        current = run_current_rerank(spec["query"], limit)
        current_results = current.get("results") if isinstance(current.get("results"), list) else []
        docs = [doc_text(item) for item in current_results if isinstance(item, dict) and doc_text(item)]
        if not docs:
            queries.append(
                {
                    "id": spec["id"],
                    "query": spec["query"],
                    "ok": False,
                    "error": current.get("error") or "no current rerank documents",
                    "current_summary": current.get("summary"),
                }
            )
            continue
        scored = reranker.score(spec["query"], docs)
        rows = []
        for index, item in enumerate(current_results[: len(docs)]):
            rows.append(
                {
                    "source_id": item.get("source_id"),
                    "title": item.get("title"),
                    "chunk_id": item.get("chunk_id"),
                    "hybrid_score": item.get("score"),
                    "neural_score": round(scored["scores"][index], 6),
                    "neural_raw_logit_diff": round(scored["raw_logit_diff"][index], 6),
                }
            )
        rows.sort(key=lambda item: (-float(item["neural_score"]), -float(item["hybrid_score"] or 0.0), str(item.get("chunk_id") or "")))
        top = rows[0] if rows else {}
        top_source = str(top.get("source_id") or "")
        preferred_sources = set(spec["preferred_sources"])
        context_sources = set(spec["context_sources"])
        top_context_unmatched = top_source in context_sources
        query_ok = top_source in preferred_sources and not top_context_unmatched
        queries.append(
            {
                "id": spec["id"],
                "query": spec["query"],
                "ok": bool(query_ok),
                "top": top,
                "current_top": {
                    "source_id": current_results[0].get("source_id") if current_results else None,
                    "title": current_results[0].get("title") if current_results else None,
                    "score": current_results[0].get("score") if current_results else None,
                },
                "preferred_sources": sorted(preferred_sources),
                "context_sources": sorted(context_sources),
                "timing": {key: scored[key] for key in ("tokenize_ms", "infer_ms", "documents")},
                "top5": rows[:5],
                "current_summary": current.get("summary"),
                "current_warnings": current.get("warnings"),
                "current_notices": current.get("notices"),
            }
        )
    return {
        "ok": all(item.get("ok") for item in queries),
        "queries": queries,
        "summary": {
            "queries": len(queries),
            "fails": sum(1 for item in queries if not item.get("ok")),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="/srv/abyss-machine/cache/ai/qwen3-reranker-0.6b-int8-ov")
    parser.add_argument("--device", default="AUTO:GPU,CPU")
    parser.add_argument("--cache-dir", default="/srv/abyss-machine/cache/ai/openvino/qwen3-reranker-0.6b-int8-ov")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--live-limit", type=int, default=24)
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--score-input", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    cache_dir = Path(args.cache_dir) / args.device.replace(":", "-").replace(",", "_")
    cache_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    data: dict[str, Any] = {
        "schema": "abyss_machine_qwen3_reranker_openvino_canary_v1",
        "ok": False,
        "model_dir": str(model_dir),
        "device": args.device,
        "cache_dir": str(cache_dir),
        "max_length": args.max_length,
        "batch_size": args.batch_size,
        "live_limit": args.live_limit,
        "score_input": args.score_input or None,
        "environment": {
            "HF_HOME": os.environ.get("HF_HOME"),
            "HUGGINGFACE_HUB_CACHE": os.environ.get("HUGGINGFACE_HUB_CACHE"),
            "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
            "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
            "OPENVINO_LOG_LEVEL": os.environ.get("OPENVINO_LOG_LEVEL"),
        },
    }
    try:
        reranker = Qwen3OpenVINOReranker(model_dir, args.device, cache_dir, args.max_length, args.batch_size)
        reranker.load()
        data["load"] = {
            "ok": True,
            "load_sec": round(reranker.load_sec, 3),
            "tokenizer_sec": round(reranker.tokenizer_sec, 3),
        }
        if args.score_input:
            score_path = Path(args.score_input)
            payload = json.loads(score_path.read_text(encoding="utf-8"))
            documents_payload = payload.get("documents") if isinstance(payload.get("documents"), list) else []
            ids = [str(item.get("id") or index) for index, item in enumerate(documents_payload) if isinstance(item, dict)]
            docs = [str(item.get("text") or "") for item in documents_payload if isinstance(item, dict)]
            scored = reranker.score(
                str(payload.get("query") or ""),
                docs,
                str(payload.get("instruction") or DEFAULT_INSTRUCTION),
            )
            data["scores"] = [
                {
                    "id": ids[index],
                    "score": round(float(scored["scores"][index]), 6),
                    "raw_logit_diff": round(float(scored["raw_logit_diff"][index]), 6),
                }
                for index in range(len(scored["scores"]))
            ]
            data["timing"] = {key: scored[key] for key in ("tokenize_ms", "infer_ms", "documents")}
            data["ok"] = bool(docs and len(data["scores"]) == len(docs))
        else:
            data["synthetic"] = evaluate_synthetic(reranker)
            if not args.skip_live:
                data["live"] = evaluate_live(reranker, args.live_limit)
            else:
                data["live"] = {"ok": True, "skipped": True}
            data["ok"] = bool(data["synthetic"].get("ok") and data["live"].get("ok"))
    except Exception as exc:
        data["error"] = repr(exc)
    finally:
        elapsed = time.perf_counter() - started
        data["elapsed_sec"] = round(elapsed, 3)
        data["resource"] = {
            "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False))
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
