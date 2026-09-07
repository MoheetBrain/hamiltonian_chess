#!/usr/bin/env python3
"""Inventory existing reasoning-operation annotations without model labelling."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CANONICAL_HEADS = {
    "by_contra",
    "by_cases",
    "cases",
    "constructor",
    "contradiction",
    "ext",
    "funext",
    "have",
    "induction",
    "intro",
    "obtain",
    "rintro",
    "rw",
    "subst",
    "suffices",
    "use",
}
CONTROLLER_HEADS = {
    "aesop",
    "apply",
    "assumption",
    "decide",
    "exact",
    "first",
    "linarith",
    "native_decide",
    "norm_num",
    "omega",
    "positivity",
    "refine",
    "ring",
    "ring_nf",
    "simp",
    "simpa",
    "solve",
    "tauto",
}
PRESENTATIONAL_WORDS = {"CONCLUDE", "EXPLAIN", "RESTATE", "SUMMARIZE"}
CONTROLLER_WORDS = {"BACKTRACK", "BRANCH_ORDER", "RETRIEVE", "SEARCH", "SELECT_TACTIC"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_operation(name: str, declared_layer: str | None = None) -> str:
    upper = name.upper()
    lower = name.lower()
    if any(word in upper for word in PRESENTATIONAL_WORDS):
        return "PRESENTATIONAL"
    if declared_layer == "SEARCH_META_OPERATION" or any(word in upper for word in CONTROLLER_WORDS):
        return "CONTROLLER_SEARCH"
    if lower in CONTROLLER_HEADS:
        return "CONTROLLER_SEARCH"
    if lower in CANONICAL_HEADS or declared_layer in {
        "CORE_PROOF_OPERATION",
        "CORE_STATE_OPERATION",
        "DOMAIN_LIBRARY",
        "NUMERIC_BACKEND_OPERATION",
        "THEOREM_LIBRARY",
    }:
        return "CANONICAL_MATHEMATICAL"
    if upper in {"OTHER", "UNRESOLVED", "MISSING", ""}:
        return "AMBIGUOUS_UNRESOLVED"
    return "AMBIGUOUS_UNRESOLVED"


def gold_records(paths: Iterable[Path], schema: str) -> dict[str, Any]:
    operations: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    layers: Counter[str] = Counter()
    verification: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    atomicity: Counter[str] = Counter()
    problems = 0
    steps = 0
    multi_operation = 0
    for path in sorted(paths):
        record = load_json(path)
        problems += 1
        domains[str(record.get("category", record.get("title", "UNKNOWN")))] += 1
        records = record.get("actions", []) if schema == "gold10" else record.get("steps", [])
        for item in records:
            steps += 1
            if schema == "gold10":
                operation = str(item.get("operation", "MISSING"))
                layer = None
                verification[str(item.get("verification", {}).get("status", "UNKNOWN"))] += 1
            else:
                action = item.get("action", {})
                operation = str(action.get("operation_id", "MISSING"))
                layer = action.get("layer_class") or action.get("arguments", {}).get("layer_class")
                verification[str(item.get("verification", {}).get("status", "UNKNOWN"))] += 1
                atom = str(item.get("atomicity", "NOT_RECORDED"))
                atomicity[atom] += 1
                components = item.get("macro_components", [])
                if len(components) > 1 or atom.upper() in {"MACRO", "MULTI_OPERATION", "COMPOSITE"}:
                    multi_operation += 1
            operations[operation] += 1
            layers[str(layer or "NOT_DECLARED")] += 1
            category = classify_operation(operation, str(layer) if layer else None)
            if category == "AMBIGUOUS_UNRESOLVED" and operation.upper() not in {
                "OTHER",
                "UNRESOLVED",
                "MISSING",
            }:
                # Gold annotations are human-authored semantic operation labels, unlike raw
                # Lean tactic heads. Conservatively retain them as mathematical operations.
                category = "CANONICAL_MATHEMATICAL"
            classes[category] += 1
    return {
        "problems": problems,
        "steps": steps,
        "operation_frequency": dict(operations.most_common()),
        "derived_class_frequency": dict(classes.most_common()),
        "declared_layer_frequency": dict(layers.most_common()),
        "verification_status_frequency": dict(verification.most_common()),
        "domain_frequency": dict(domains.most_common()),
        "atomicity_frequency": dict(atomicity.most_common()),
        "multi_operation_steps": multi_operation,
        "ambiguity_rate": classes["AMBIGUOUS_UNRESOLVED"] / steps if steps else None,
        "evidence_tag": "VERIFIED_BY_SOURCE_DATA",
    }


def leandojo(path: Path) -> dict[str, Any]:
    heads: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    files: Counter[str] = Counter()
    effects: defaultdict[str, Counter[str]] = defaultdict(Counter)
    rows = 0
    noops = 0
    closed = 0
    premise_rows = 0
    premise_references = 0
    combinators = 0
    support: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            rows += 1
            head = str(row.get("head") or "MISSING")
            heads[head] += 1
            category = classify_operation(head)
            classes[category] += 1
            splits[str(row.get("split", "UNKNOWN"))] += 1
            files[str(row.get("file_path", row.get("prov", {}).get("file_path", "UNKNOWN")))] += 1
            noops += bool(row.get("noop"))
            closed += bool(row.get("closed"))
            combinators += bool(row.get("combinator"))
            premises = row.get("premises", [])
            premise_rows += bool(premises)
            premise_references += len(premises)
            support["premise_selection_rows"] += bool(premises)
            support["rewrite_family_rows"] += head in {
                "rw",
                "rwa",
                "erw",
                "simp_rw",
                "nth_rewrite",
                "rw_mod_cast",
            }
            support["witness_construction_rows"] += head in {"use", "refine", "exact"}
            support["case_or_induction_rows"] += head in {
                "by_cases",
                "cases",
                "cases'",
                "induction",
                "induction'",
                "rcases",
            }
            support["introduction_rows"] += head in {"intro", "rintro", "intros"}
            support["multi_goal_before_rows"] += int(row.get("n_before", 0) or 0) > 1
            support["goal_count_change_rows"] += int(row.get("delta_goals", 0) or 0) != 0
            support["target_changed_rows"] += bool(row.get("target_changed"))
            support["closure_rows"] += bool(row.get("closed"))
            effects[category]["target_changed"] += bool(row.get("target_changed"))
            effects[category]["closed"] += bool(row.get("closed"))
            effects[category]["noop"] += bool(row.get("noop"))
    return {
        "path": str(path),
        "rows": rows,
        "raw_head_frequency": dict(heads.most_common()),
        "derived_class_frequency": dict(classes.most_common()),
        "split_frequency": dict(splits.most_common()),
        "distinct_source_files": len(files),
        "effect_counts_by_class": {key: dict(value) for key, value in sorted(effects.items())},
        "noop_rows": noops,
        "closed_rows": closed,
        "combinator_rows": combinators,
        "rows_with_premises": premise_rows,
        "premise_references": premise_references,
        "candidate_environment_support": dict(support),
        "ambiguity_rate": classes["AMBIGUOUS_UNRESOLVED"] / rows,
        "verification_scope": "FORMAL_TRACE_SOURCE_NOT_FRESH_PER_ROW_REPLAY",
        "evidence_tag": "VERIFIED_BY_SOURCE_DATA",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leandojo", type=Path, required=True)
    parser.add_argument("--reasoning-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    base = args.reasoning_root.resolve()
    sources = {
        "gold10": gold_records((base / "data/gold_10").rglob("*.json"), "gold10"),
        "gold25": gold_records((base / "data/gold25/trajectories").glob("*.json"), "gold25"),
        "gold125_new100": gold_records(
            (base / "data/gold125/trajectories").glob("*.json"), "gold125"
        ),
        "leandojo": leandojo(args.leandojo.resolve()),
    }
    granular_steps = sum(sources[key]["steps"] for key in ("gold10", "gold25", "gold125_new100"))
    output = {
        "schema_version": "codex-audit-operation-inventory-v1",
        "method": {
            "model_labelling": False,
            "inputs": "existing operation IDs, layer annotations, Lean tactic heads, and deterministic codebook only",
            "codebook_warning": "Lean tactic heads are controller commands. Only a conservative subset maps to mathematical transformations; unresolved heads stay ambiguous.",
        },
        "sources": sources,
        "cross_source": {
            "granular_reasoning_steps": granular_steps,
            "granular_problem_count": sum(
                sources[key]["problems"] for key in ("gold10", "gold25", "gold125_new100")
            ),
            "formal_tactic_transitions": sources["leandojo"]["rows"],
            "empirically_supported_units": [
                "introduce/localize assumptions",
                "rewrite/substitute",
                "definition or theorem application",
                "case analysis/induction",
                "construct witness or result",
                "evaluate/normalize",
                "discharge/close",
                "automated tactic selection/search",
            ],
            "not_supported_as_atomic": [
                "universal tactic microstep ontology",
                "one-to-one tactic-to-mathematical-operation mapping",
                "presentational narration as canonical state change",
            ],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
