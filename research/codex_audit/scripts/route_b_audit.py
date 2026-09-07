#!/usr/bin/env python3
"""Static/data audit of the historical Route-B matched-adaptation sprint."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.gpu_matched_runner import score_prediction
from arena.training.prepare_matched_data import stratified_split


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlap(eval_ix: list[int], train_ix: list[int], key: Callable[[int], str]) -> dict[str, Any]:
    train_values = {key(i) for i in train_ix}
    matched = [i for i in eval_ix if key(i) in train_values]
    return {"count": len(matched), "rate": len(matched) / len(eval_ix), "indices": matched}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    tasks = list(generate_tasks(total=676, seed=0))
    train, dev, fresh = map(list, stratified_split(tasks, 600, 48, 48, 0))

    def task_id(i: int) -> str:
        return tasks[i].task_id

    def trajectory_id(i: int) -> str:
        return tasks[i].trajectory.trajectory_id

    def problem(i: int) -> str:
        return canonical(tasks[i].trajectory.problem.to_dict())

    def answer(i: int) -> str:
        value = tasks[i].trajectory.final_answer
        assert value is not None
        return canonical(value.to_dict())

    def action(i: int) -> str:
        return canonical(tasks[i].trajectory.transitions[0].action.to_dict())

    def action_without_ids(i: int) -> str:
        value = tasks[i].trajectory.transitions[0].action.to_dict()
        for field in ("action_id", "target_ids", "warrant", "expected_usefulness"):
            value.pop(field, None)
        return canonical(value)

    def operation(i: int) -> str:
        return tasks[i].trajectory.transitions[0].action.operation

    split_source = inspect.getsource(stratified_split)
    tree = ast.parse(split_source)
    seed_loads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "seed" and isinstance(node.ctx, ast.Load)
    ]
    split_by_seed = {}
    for seed in (0, 1, 17):
        seeded_tasks = list(generate_tasks(total=676, seed=seed))
        groups = stratified_split(seeded_tasks, 600, 48, 48, seed)
        split_by_seed[str(seed)] = {
            "world_hash": stable_hash([task.to_dict() for task in seeded_tasks]),
            "index_hashes": [stable_hash(list(group)) for group in groups],
        }

    def quality(indices: list[int]) -> dict[str, int]:
        return dict(collections.Counter(tasks[i].trajectory.quality.value for i in indices))

    overlap_sets: dict[str, Any] = {}
    for budget in (16, 32, 64, 128, 224, 576, 580):
        budget_train = train[:budget]
        record = {}
        for name, fn in (
            ("task_id", task_id),
            ("trajectory_id", trajectory_id),
            ("problem_exact", problem),
            ("answer_exact", answer),
            ("action_exact", action),
            ("action_without_ids", action_without_ids),
            ("operation", operation),
        ):
            record[name] = overlap(dev, budget_train, fn)
        train_answers = {answer(i) for i in budget_train}
        train_problems = {problem(i) for i in budget_train}
        union = [i for i in dev if answer(i) in train_answers or problem(i) in train_problems]
        record["answer_or_problem"] = {
            "count": len(union),
            "rate": len(union) / len(dev),
            "indices": union,
        }
        overlap_sets[str(budget)] = record

    wrong = canonical({"action_id": "wrong", "operation": "wrong", "arguments": []})
    correct_target = canonical(tasks[dev[0]].trajectory.transitions[0].action.to_dict())
    vacuity_demo = score_prediction(wrong, correct_target)

    sprint_path = root / "artifacts/experiments/tier2_sprint/gpu_sprint_results.json"
    sprint = json.loads(sprint_path.read_text(encoding="utf-8"))
    stage_quality = {
        "stage_a_first_224": quality(train[:224]),
        "stage_b_first_576": quality(train[:576]),
        "available_train_580": quality(train),
        "dev": quality(dev),
        "fresh": quality(fresh),
    }

    output = {
        "schema_version": "codex-audit-route-b-v1",
        "classification": "HISTORICAL_GUIDANCE",
        "causal_verdict": "NOT_A_CLEAN_REPRESENTATION_LEARNABILITY_ESTIMATE",
        "source_artifact": {
            "path": str(sprint_path.relative_to(root)),
            "sha256": hash_file(sprint_path),
            "budget_mode": sprint.get("budget_mode"),
            "model": sprint.get("provenance", {}).get("base_model"),
            "model_revision": sprint.get("provenance", {}).get("base_model_revision"),
            "config": sprint.get("config"),
        },
        "split_audit": {
            "requested_sizes": {"train": 600, "dev": 48, "fresh": 48},
            "actual_sizes": {"train": len(train), "dev": len(dev), "fresh": len(fresh)},
            "seed_argument_loaded_inside_stratified_split": bool(seed_loads),
            "finding": "The seed changes generated task contents but not split allocation indices; stratified_split never reads its seed parameter.",
            "seed_trials": split_by_seed,
            "quality_counts": stage_quality,
            "id_disjoint": not (
                set(train) & set(dev) or set(train) & set(fresh) or set(dev) & set(fresh)
            ),
        },
        "overlap_audit_dev_48": overlap_sets,
        "headline_overlap": {
            "at_224_answer_or_problem": overlap_sets["224"]["answer_or_problem"],
            "interpretation": "21/48 DEV items repeat an exact final answer or exact canonical problem seen in the first 224 training items; IDs and full actions remain disjoint.",
        },
        "metric_audit": {
            "verified_implementation": "schema_valid and presence of action_id, operation, arguments",
            "wrong_action_demo": {"prediction": json.loads(wrong), "score": vacuity_demo},
            "finding": "verified is a key-presence/schema proxy, not NativeVerifier acceptance, optimality, or mathematical correctness.",
        },
        "renderer_audit": {
            "seed_registry_uses_specialized_fixed_codecs": True,
            "specialized_codecs": [
                "StructuredEnglishLanguage",
                "CurrentHMLCompatibilityLanguage",
                "SExpressionLanguage",
                "JsonAstLanguage",
                "CompactSymbolicLanguage",
            ],
            "finding": "The sprint compares five concrete codec implementations. Their render methods are hard-coded and their genome class attributes label the codec; the output is not mechanically generated from all declared genome genes. This does not erase byte-level arm differences, but it prevents gene-level causal attribution.",
        },
        "loss_comparability": {
            "cross_arm_loss_is_comparable": False,
            "reason": "Loss is averaged over representation-dependent token sequences, while the run is example-matched rather than token-matched and input truncation keeps only the final max_len tokens.",
            "max_len": sprint.get("config", {}).get("max_len"),
            "recorded_train_tokens": {
                arm: {
                    stage: record[stage]["train_tokens"]
                    for stage in ("stage_a", "stage_b", "stage_c")
                    if stage in record
                }
                for arm, record in sprint["results"].items()
            },
        },
        "usable_evidence": [
            "The run establishes that the pipeline can fit this synthetic NEXT_ACTION corpus.",
            "Held-out exact outcomes are paired at 224 and 576 examples.",
            "Early loss curves identify when memorisation/fitting occurs within an arm, not which R is causally superior.",
        ],
        "invalid_claims": [
            "verified accuracy proves mathematical verification",
            "the split seed randomised membership",
            "cross-arm per-token loss ranks representation learnability",
            "Stage-A accuracy is free of answer/problem recurrence",
            "a genome gene caused the observed arm difference",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
