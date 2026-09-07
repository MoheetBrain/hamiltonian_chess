#!/usr/bin/env python3
"""Deterministically audit shortcut policies in the V5 formal-depth DEV bank."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from arena.experiments.fitness_v5 import build_dev_pool

POSITIVE = {"ORIGINAL", "COUNTERFACTUAL"}


def option_names(probe: Any) -> tuple[str, str]:
    return tuple(str(option.arguments[0].value) for option in probe.options)  # type: ignore[return-value]


def state_text(probe: Any) -> str:
    return json.dumps(
        probe.state.to_dict(include_display_identity=False),
        sort_keys=True,
        separators=(",", ":"),
    )


def target_preorder_values(expression: Any) -> list[str]:
    values: list[str] = []
    if expression.value is not None:
        values.append(str(expression.value))
    for child in expression.args:
        values.extend(target_preorder_values(child))
    return values


def score(probes: list[Any], rule: Callable[[Any], int]) -> dict[str, Any]:
    correct = sum(rule(probe) == probe.expected_index for probe in probes)
    return {"correct": correct, "n": len(probes), "accuracy": correct / len(probes)}


def audit(probes: list[Any]) -> dict[str, Any]:
    def first_mentioned(probe: Any) -> int:
        names = option_names(probe)
        text = state_text(probe)
        return 0 if text.find(f'"{names[0]}"') <= text.find(f'"{names[1]}"') else 1

    def last_mentioned(probe: Any) -> int:
        names = option_names(probe)
        text = state_text(probe)
        return 0 if text.rfind(f'"{names[0]}"') >= text.rfind(f'"{names[1]}"') else 1

    def more_frequent(probe: Any) -> int:
        names = option_names(probe)
        text = state_text(probe)
        counts = tuple(text.count(f'"{name}"') for name in names)
        return 0 if (counts[0], names[0]) >= (counts[1], names[1]) else 1

    def lexical_first(probe: Any) -> int:
        names = option_names(probe)
        return 0 if names[0] <= names[1] else 1

    def shorter_identifier(probe: Any) -> int:
        names = option_names(probe)
        return 0 if (len(names[0]), names[0]) <= (len(names[1]), names[1]) else 1

    def first_in_target(probe: Any) -> int:
        names = option_names(probe)
        values = target_preorder_values(probe.state.goal.args[0])
        positions = tuple(values.index(name) if name in values else len(values) for name in names)
        return 0 if positions[0] <= positions[1] else 1

    def first_declared_object(probe: Any) -> int:
        names = option_names(probe)
        object_ids = [obj.object_id.removeprefix("object:id:") for obj in probe.state.objects]
        positions = tuple(
            object_ids.index(name) if name in object_ids else len(object_ids) for name in names
        )
        return 0 if positions[0] <= positions[1] else 1

    rules = {
        "option_order_always_A": lambda probe: 0,
        "option_order_always_B": lambda probe: 1,
        "first_mentioned_in_serialized_state": first_mentioned,
        "last_mentioned_in_serialized_state": last_mentioned,
        "identifier_lexical_order": lexical_first,
        "identifier_length_shorter": shorter_identifier,
        "occurrence_count_more_frequent": more_frequent,
        "target_source_order_preorder": first_in_target,
        "canonical_object_declaration_order": first_declared_object,
    }
    return {
        "n": len(probes),
        "answer_index_counts": dict(sorted(Counter(p.expected_index for p in probes).items())),
        "rules": {name: score(probes, rule) for name, rule in rules.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    probes = [
        probe
        for probe in build_dev_pool(args.root.resolve(), mechanisms=("formal_expression_depth",))
        if probe.variant.value in POSITIVE
    ]
    by_level = {
        str(level): audit([probe for probe in probes if probe.level == level]) for level in range(4)
    }
    output = {
        "schema_version": "codex-audit-formal-depth-shortcuts-v1",
        "evidence_tag": "VERIFIED_BY_CODE",
        "bank": "V5 formal_expression_depth DEV positive arms",
        "all_levels": audit(probes),
        "by_level": by_level,
        "reported_numbers_reconciled": {
            "approximately_0_913": by_level["3"]["rules"]["first_mentioned_in_serialized_state"],
            "shallow_1_0": by_level["1"]["rules"]["first_mentioned_in_serialized_state"],
            "note": "The reported ~0.913 is the deep L3 stratum (22/24 = 0.9167), not the pooled four-level bank (78/96 = 0.8125).",
        },
        "repair_assessment": {
            "identifier_obfuscation_alone": "INSUFFICIENT",
            "order_randomisation_alone": "INSUFFICIENT",
            "matched_counterfactuals": "REQUIRED_BUT_NOT_SUFFICIENT",
            "recommended_disposition": "REBUILD_THEN_REAUDIT; retire if no construction can jointly balance order, frequency, and target traversal cues while preserving depth truth.",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
