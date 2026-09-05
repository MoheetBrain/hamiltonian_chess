"""Cached local-model execution for the frozen representation-fitness experiment."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from arena.canonical.schema import stable_hash
from arena.experiments.fitness_v1 import (
    EXPERIMENT_SEED,
    EXPERIMENT_VERSION,
    build_prompt,
    correct_choice,
    frozen_task_split,
    materialize_population,
    parse_choice,
)
from arena.genome.schema import LanguageGenome
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.storage.artifacts import ArtifactStore
from arena.tasks.generators.world_v0 import build_world_v0

MODEL_CONFIG: dict[str, Any] = {
    "model": "gemma3:4b",
    "ollama_list_id": "a2af6cc3eb7f",
    "model_blob_sha256": "aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25",
    "quantization": "Q4_K_M",
    "tokenizer": "GGUF llama metadata (Gemma SentencePiece vocabulary)",
    "num_ctx": 8192,
    "temperature": 0.0,
    "seed": EXPERIMENT_SEED,
    "num_predict": 32,
    "top_k": 64,
    "top_p": 0.95,
    "ollama_version": "0.33.2",
}
MODEL_CONFIG_HASH = stable_hash(MODEL_CONFIG)
CONTROL_IDS = (
    "L0_STRUCTURED_ENGLISH",
    "L1_CURRENT_HML",
    "L2_SEXPR",
    "L3_JSON_AST",
)


def _candidate_genomes() -> dict[str, LanguageGenome]:
    result = dict(SEED_GENOME_BY_ID)
    result.update({item.candidate_id: item.genome for item in materialize_population()})
    return result


def _call_ollama(prompt: str, *, base_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    options = {
        "num_ctx": MODEL_CONFIG["num_ctx"],
        "temperature": MODEL_CONFIG["temperature"],
        "seed": MODEL_CONFIG["seed"],
        "num_predict": MODEL_CONFIG["num_predict"],
        "top_k": MODEL_CONFIG["top_k"],
        "top_p": MODEL_CONFIG["top_p"],
    }
    body = json.dumps(
        {"model": MODEL_CONFIG["model"], "prompt": prompt, "stream": False, "options": options}
    ).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:  # noqa: S310 - fixed local runtime URL
        raw = json.loads(response.read().decode("utf-8"))
    return {
        "response": str(raw.get("response", "")),
        "done": bool(raw.get("done", False)),
        "done_reason": raw.get("done_reason"),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "total_duration_ns": int(raw.get("total_duration", 0)),
        "load_duration_ns": int(raw.get("load_duration", 0)),
        "prompt_eval_duration_ns": int(raw.get("prompt_eval_duration", 0)),
        "eval_duration_ns": int(raw.get("eval_duration", 0)),
    }


def evaluate_cell(
    root: Path,
    candidate_id: str,
    task_id: str,
    *,
    slice_name: str,
) -> dict[str, Any]:
    world = build_world_v0()
    task_by_id = {task.task_id: task for task in world.tasks}
    task = task_by_id[task_id]
    genome = _candidate_genomes()[candidate_id]
    prompt = build_prompt(genome, task)
    identity = {
        "experiment_version": EXPERIMENT_VERSION,
        "model_config_hash": MODEL_CONFIG_HASH,
        "model_blob_sha256": MODEL_CONFIG["model_blob_sha256"],
        "candidate_id": candidate_id,
        "candidate_genome_hash": genome.genome_hash,
        "task_id": task_id,
        "task_hash": task.content_hash,
        "prompt_hash": stable_hash(prompt),
    }
    cache_key = stable_hash(identity)
    cache_path = root / "artifacts" / "cache" / "fitness_v1" / f"{cache_key}.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        cache_hit = True
    else:
        started = time.monotonic()
        try:
            raw = _call_ollama(prompt)
            raw["error"] = None
        except Exception as error:  # preserve failures as measured outcomes
            raw = {
                "response": "",
                "done": False,
                "done_reason": None,
                "prompt_eval_count": 0,
                "eval_count": 0,
                "total_duration_ns": 0,
                "load_duration_ns": 0,
                "prompt_eval_duration_ns": 0,
                "eval_duration_ns": 0,
                "error": repr(error),
            }
        raw["wall_seconds"] = time.monotonic() - started
        raw["cache_identity"] = identity
        ArtifactStore(root / "artifacts").write_json(f"cache/fitness_v1/{cache_key}.json", raw)
        cache_hit = False
    parsed = parse_choice(raw["response"])
    truth = correct_choice(task)
    return {
        **identity,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "slice": slice_name,
        "domain": task.dimensions.domain,
        "group": f"{task.dimensions.domain}|{task.tags[2]}",
        "dimensions": task.dimensions.to_dict(),
        "raw_output": raw["response"],
        "parsed_choice": parsed,
        "correct_choice": truth,
        "correct": parsed == truth,
        "invalid_action_selected": parsed is not None and parsed != truth,
        "malformed": parsed is None,
        "error": raw.get("error"),
        "prompt_tokens": raw.get("prompt_eval_count", 0),
        "completion_tokens": raw.get("eval_count", 0),
        "latency_seconds": raw.get("total_duration_ns", 0) / 1_000_000_000,
    }


def _summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["candidate_id"]].append(row)
    result = {}
    for candidate_id, values in sorted(grouped.items()):
        correct = sum(row["correct"] for row in values)
        malformed = sum(row["malformed"] for row in values)
        result[candidate_id] = {
            "correct": correct,
            "tasks": len(values),
            "accuracy": correct / len(values),
            "malformed": malformed,
            "mean_prompt_tokens": sum(row["prompt_tokens"] for row in values) / len(values),
            "mean_latency_seconds": sum(row["latency_seconds"] for row in values) / len(values),
            "domain_accuracy": {
                domain: sum(row["correct"] for row in values if row["domain"] == domain)
                / sum(row["domain"] == domain for row in values)
                for domain in sorted({row["domain"] for row in values})
            },
        }
    return result


def _calibration_verdict(scores: dict[str, Any]) -> str:
    strongest = max(float(score["accuracy"]) for score in scores.values())
    if strongest >= 0.9:
        return "SEVERE_CEILING"
    if strongest <= 0.1:
        return "SEVERE_FLOOR"
    if strongest >= 0.8:
        return "BORDERLINE_CEILING"
    if strongest <= 0.3:
        return "BORDERLINE_FLOOR"
    return "USEFUL_HEADROOM"


def _calibration_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Fitness calibration",
        "",
        f"Experiment: `{EXPERIMENT_VERSION}`",
        f"Model: `{MODEL_CONFIG['model']}` / `{MODEL_CONFIG['model_blob_sha256']}`",
        f"Verdict: **{result['headroom_verdict']}**",
        "",
        "| Rung | Control | Correct | Tasks | Accuracy | Malformed | Mean input tokens |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for rung in result["rungs"]:
        for candidate_id, score in rung["scores"].items():
            lines.append(
                f"| {rung['slice']} | {candidate_id} | {score['correct']} | "
                f"{score['tasks']} | {score['accuracy']:.3f} | {score['malformed']} | "
                f"{score['mean_prompt_tokens']:.1f} |"
            )
    lines.extend(
        [
            "",
            f"Calls: {result['calls']}; cache hits: {result['cache_hits']}.",
            "",
            "Raw-output inspection sample:",
            "",
            "```json",
            json.dumps(result["raw_inspection_sample"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_calibration(root: Path) -> dict[str, Any]:
    manifest = frozen_task_split(build_world_v0())
    rungs = []
    all_rows: list[dict[str, Any]] = []

    def run_rung(slice_name: str) -> dict[str, Any]:
        rows = [
            evaluate_cell(root, candidate_id, task_id, slice_name=slice_name)
            for candidate_id in CONTROL_IDS
            for task_id in manifest["protocol_slices"][slice_name]
        ]
        all_rows.extend(rows)
        return {"slice": slice_name, "scores": _summaries(rows), "rows": rows}

    initial = run_rung("CALIBRATION_DEV")
    rungs.append(initial)
    initial_verdict = _calibration_verdict(initial["scores"])
    if initial_verdict == "SEVERE_CEILING":
        hard = run_rung("CALIBRATION_HARD_DEV")
        rungs.append(hard)
        final_verdict = _calibration_verdict(hard["scores"])
    else:
        final_verdict = initial_verdict

    benchmark_valid = final_verdict not in {"SEVERE_CEILING", "SEVERE_FLOOR"}
    result = {
        "schema_version": "arena-fitness-calibration-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "preregistration_commit": "f17bb0f73ac942d43b614704e54c019a64284368",
        "model_config": MODEL_CONFIG,
        "model_config_hash": MODEL_CONFIG_HASH,
        "task_split_hash": manifest["manifest_hash"],
        "rungs": rungs,
        "calls": len(all_rows),
        "cache_hits": sum(row["cache_hit"] for row in all_rows),
        "headroom_verdict": final_verdict,
        "benchmark_valid": benchmark_valid,
        "next_stage": "TIER2A" if benchmark_valid else "STOP_MODEL_FITNESS_BENCHMARK_INVALID",
        "raw_inspection_sample": [
            {
                "candidate_id": row["candidate_id"],
                "task_id": row["task_id"],
                "raw_output": row["raw_output"],
                "parsed_choice": row["parsed_choice"],
                "correct_choice": row["correct_choice"],
            }
            for row in all_rows[:4]
        ],
    }
    store = ArtifactStore(root / "artifacts")
    store.write_json("reports/fitness-calibration.json", result)
    store.write_text("reports/fitness-calibration.md", _calibration_markdown(result))
    return result


def experiment_status(root: Path) -> dict[str, Any]:
    calibration = root / "artifacts" / "reports" / "fitness-calibration.json"
    if not calibration.exists():
        return {
            "experiment": EXPERIMENT_VERSION,
            "stage": "PREREGISTERED",
            "next_command": "arena fitness calibrate",
        }
    result = json.loads(calibration.read_text(encoding="utf-8"))
    return {
        "experiment": EXPERIMENT_VERSION,
        "stage": "CALIBRATION_COMPLETE",
        "headroom_verdict": result["headroom_verdict"],
        "benchmark_valid": result["benchmark_valid"],
        "next_command": (
            "arena fitness scout --tier 2a"
            if result["benchmark_valid"]
            else "STOP: MODEL_FITNESS_BENCHMARK_INVALID"
        ),
    }


__all__ = [
    "CONTROL_IDS",
    "MODEL_CONFIG",
    "MODEL_CONFIG_HASH",
    "evaluate_cell",
    "experiment_status",
    "run_calibration",
]
