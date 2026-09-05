"""Cached local-model execution for the frozen representation-fitness experiment."""

from __future__ import annotations

import json
import math
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
    audit = result.get("instrument_audit")
    display_verdict = audit["verdict"] if audit else result["headroom_verdict"]
    lines = [
        "# Fitness calibration",
        "",
        f"Experiment: `{EXPERIMENT_VERSION}`",
        f"Model: `{MODEL_CONFIG['model']}` / `{MODEL_CONFIG['model_blob_sha256']}`",
        f"Verdict: **{display_verdict}**",
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
            f"Task cells: {result['calls']}; unique cached model observations: "
            f"{result.get('unique_model_observations', result['calls'])}; cache hits while "
            f"rendering this report: {result['cache_hits']}.",
            "",
            "Raw-output inspection sample:",
            "",
            "```json",
            json.dumps(result["raw_inspection_sample"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    if audit:
        lines.extend(
            [
                "## Raw-completion instrument audit",
                "",
                f"Nominal threshold verdict: **{audit['nominal_threshold_verdict']}**.",
                f"Scientific instrument verdict: **{audit['verdict']}**.",
                "",
                f"Always-A accuracy: {audit['constant_position_baselines']['always_A']:.3f}; "
                f"always-B accuracy: {audit['constant_position_baselines']['always_B']:.3f}.",
                "",
                "| Control | A | B | Malformed | Choice entropy (bits) |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for candidate_id, summary in audit["control_choice_behavior"].items():
            lines.append(
                f"| {candidate_id} | {summary['A']} | {summary['B']} | "
                f"{summary['malformed']} | {summary['choice_entropy_bits']:.3f} |"
            )
        lines.extend(
            [
                "",
                audit["reason"],
                "",
                "Tier 2A was not run. Calibration rows and the nominal heuristic result are "
                "preserved; the audit adds an instrument-validity decision without relabelling "
                "a model response.",
                "",
            ]
        )
    return "\n".join(lines)


def _binary_entropy(a: int, b: int) -> float:
    total = a + b
    if total == 0 or a == 0 or b == 0:
        return 0.0
    p = a / total
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def audit_calibration(root: Path) -> dict[str, Any]:
    """Apply the mandatory raw-output/position-baseline validity check.

    The numerical 30--80% rule is a headroom heuristic, not permission to ignore a solver
    that implements a constant answer-position policy. Raw inspection was pre-registered
    precisely because earlier HML instruments passed automated thresholds while measuring the
    wrong relation.
    """

    path = root / "artifacts" / "reports" / "fitness-calibration.json"
    if not path.exists():
        raise FileNotFoundError("run calibration before its instrument audit")
    result = json.loads(path.read_text(encoding="utf-8"))
    initial = result["rungs"][0]
    rows = initial["rows"]
    truth_a = sum(
        row["correct_choice"] == "A" for row in rows if row["candidate_id"] == CONTROL_IDS[0]
    )
    tasks = sum(row["candidate_id"] == CONTROL_IDS[0] for row in rows)
    baselines = {"always_A": truth_a / tasks, "always_B": (tasks - truth_a) / tasks}
    behavior = {}
    for candidate_id in CONTROL_IDS:
        candidate_rows = [row for row in rows if row["candidate_id"] == candidate_id]
        a = sum(row["parsed_choice"] == "A" for row in candidate_rows)
        b = sum(row["parsed_choice"] == "B" for row in candidate_rows)
        behavior[candidate_id] = {
            "A": a,
            "B": b,
            "malformed": sum(row["parsed_choice"] is None for row in candidate_rows),
            "choice_entropy_bits": _binary_entropy(a, b),
            "accuracy": initial["scores"][candidate_id]["accuracy"],
        }
    strongest = max(float(score["accuracy"]) for score in initial["scores"].values())
    best_constant = max(baselines.values())
    constant_controls = [
        candidate_id
        for candidate_id, summary in behavior.items()
        if summary["choice_entropy_bits"] == 0.0 and summary["malformed"] == 0
    ]
    paired = {
        row["task_id"]: row["parsed_choice"]
        for row in rows
        if row["candidate_id"] == CONTROL_IDS[0]
    }
    hml_rows = [row for row in rows if row["candidate_id"] == CONTROL_IDS[1]]
    se_hml_identical = sum(paired[row["task_id"]] == row["parsed_choice"] for row in hml_rows)
    invalid = (
        strongest <= best_constant
        and len(constant_controls) >= 2
        and se_hml_identical == len(hml_rows)
    )
    audit = {
        "nominal_threshold_verdict": result["headroom_verdict"],
        "verdict": "INSTRUMENT_INVALID_POSITION_ONLY" if invalid else "INSTRUMENT_VALID",
        "constant_position_baselines": baselines,
        "strongest_control_accuracy": strongest,
        "all_controls_at_or_below_best_constant": strongest <= best_constant,
        "constant_choice_controls": constant_controls,
        "structured_english_current_hml_identical_choices": {
            "numerator": se_hml_identical,
            "denominator": len(hml_rows),
        },
        "control_choice_behavior": behavior,
        "reason": (
            "The strongest controls implemented an always-A policy and no control beat the "
            "best constant answer-position policy. The nominal accuracy therefore does not "
            "demonstrate that the solver read the mathematical state or alternatives."
            if invalid
            else "Controls varied choices and exceeded the best constant-position policy."
        ),
    }
    result["threshold_headroom_verdict"] = result["headroom_verdict"]
    result["unique_model_observations"] = len(
        {row["cache_key"] for rung in result["rungs"] for row in rung["rows"]}
    )
    result["instrument_audit"] = audit
    result["benchmark_valid"] = not invalid and bool(result["benchmark_valid"])
    result["next_stage"] = (
        "TIER2A" if result["benchmark_valid"] else "STOP_MODEL_FITNESS_BENCHMARK_INVALID"
    )
    store = ArtifactStore(root / "artifacts")
    store.write_json("reports/fitness-calibration.json", result)
    store.write_text("reports/fitness-calibration.md", _calibration_markdown(result))
    decision = {
        "schema_version": "arena-fitness-decision-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "decision": (
            "PROCEED_TIER2A" if result["benchmark_valid"] else "MODEL_FITNESS_BENCHMARK_INVALID"
        ),
        "tier2a_run": False,
        "tier2b_run": False,
        "matched_adaptation_run": False,
        "evidence": audit,
        "uncertainty": (
            "This invalidates this model/task interface; it does not show that all "
            "representations or all solvers have no fitness landscape."
        ),
        "highest_ev_next_action": (
            "Build a new versioned acquisition instrument with a demonstrated positive "
            "mathematical-reading control and a relation-destroyed negative control, then "
            "recalibrate without reusing these responses."
        ),
    }
    store.write_json("reports/experiment-decision.json", decision)
    return decision


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
    audit_calibration(root)
    return json.loads(
        (root / "artifacts" / "reports" / "fitness-calibration.json").read_text(encoding="utf-8")
    )


def experiment_status(root: Path) -> dict[str, Any]:
    calibration = root / "artifacts" / "reports" / "fitness-calibration.json"
    if not calibration.exists():
        return {
            "experiment": EXPERIMENT_VERSION,
            "stage": "PREREGISTERED",
            "next_command": "arena fitness calibrate",
        }
    result = json.loads(calibration.read_text(encoding="utf-8"))
    decision_path = root / "artifacts" / "reports" / "experiment-decision.json"
    decision = (
        json.loads(decision_path.read_text(encoding="utf-8"))["decision"]
        if decision_path.exists()
        else None
    )
    return {
        "experiment": EXPERIMENT_VERSION,
        "stage": "CALIBRATION_COMPLETE",
        "headroom_verdict": result["headroom_verdict"],
        "benchmark_valid": result["benchmark_valid"],
        "decision": decision,
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
    "audit_calibration",
    "evaluate_cell",
    "experiment_status",
    "run_calibration",
]
