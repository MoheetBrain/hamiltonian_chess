#!/usr/bin/env python3
"""Compute deterministic zero-model shortcut baselines over all 676 World-v0 tasks."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.tasks.generators.world_v0 import generate_tasks


def mean(values: list[bool]) -> float:
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tasks = list(generate_tasks(total=676, seed=0))

    domain_operation: dict[str, str] = {}
    domain_counts: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for task in tasks:
        action = task.trajectory.transitions[0].action
        domain_counts[task.dimensions.domain][action.operation] += 1
    for domain, counts in domain_counts.items():
        domain_operation[domain] = counts.most_common(1)[0][0]

    operations = [task.trajectory.transitions[0].action.operation for task in tasks]
    majority_operation = collections.Counter(operations).most_common(1)[0][0]
    rows: list[dict[str, Any]] = []
    checks: dict[str, list[bool]] = collections.defaultdict(list)
    for task in tasks:
        state = task.trajectory.initial_state
        visible = project_state_for_observation(state, ObservationKind.NEXT_ACTION)
        action = task.trajectory.transitions[0].action
        predicted_action_id = (
            state.state_id.replace("state:", "action:", 1).removesuffix(":initial") + ":valid"
        )
        predicted_operation = domain_operation[task.dimensions.domain]
        per = {
            "task_id": task.task_id,
            "quality": task.trajectory.quality.value,
            "domain": task.dimensions.domain,
            "visible_state_id": visible.state_id,
            "target_action_id": action.action_id,
            "predicted_action_id_from_state_id": predicted_action_id,
            "target_operation": action.operation,
            "predicted_operation_from_domain": predicted_operation,
            "visible_legal_actions": len(visible.legal_actions),
            "canonical_legal_actions": len(state.legal_actions),
        }
        rows.append(per)
        checks["state_id_rewrite_action_id"].append(predicted_action_id == action.action_id)
        checks["domain_codebook_operation"].append(predicted_operation == action.operation)
        checks["global_majority_operation"].append(majority_operation == action.operation)
        checks["raw_first_legal_action_exact"].append(state.legal_actions[0] == action)
        checks["visible_has_no_legal_action"].append(not visible.legal_actions)
        checks["target_ids_constant_goal"].append(action.target_ids == ("goal",))
        checks["warrant_constant"].append(action.warrant == "arena-world-v0 exact template")
        checks["usefulness_constant_one"].append(action.expected_usefulness == 1.0)
        checks["one_transition"].append(len(task.trajectory.transitions) == 1)
        checks["one_canonical_legal_action"].append(len(state.legal_actions) == 1)

    output = {
        "schema_version": "codex-audit-world-v0-baselines-v1",
        "classification": "VALID_NEGATIVE_EVIDENCE",
        "dataset": {"world_id": "arena-world-v0", "count": len(tasks), "seed": 0},
        "baseline_accuracy": {name: mean(values) for name, values in sorted(checks.items())},
        "domain_to_operation": domain_operation,
        "global_majority_operation": majority_operation,
        "label_leakage_findings": [
            "Every target action_id is exactly recoverable by rewriting the visible state_id.",
            "Every operation is exactly recoverable from the visible domain using a 13-entry codebook.",
            "Every raw canonical initial state contains exactly one legal action, which is the target; NEXT_ACTION projection removes it, so this is an oracle-record leak only if projection is bypassed.",
            "target_ids, warrant, usefulness, transition count, and legal-action count are constants.",
            "These shortcuts make World-v0 unsuitable as a clean causal NEXT_ACTION learnability benchmark without regenerated opaque IDs, held-out operation mappings, and nontrivial action choice.",
        ],
        "claim_boundary": "The baselines diagnose dataset construction and visible metadata. They do not invoke a model and do not measure a representation.",
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
