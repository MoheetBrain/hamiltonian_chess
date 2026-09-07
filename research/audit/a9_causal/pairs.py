"""A9 core measurement: counterfactual matched pairs in the frozen V5/V7 probe bank.

Definitions (operationalised exactly as V5's own audit arithmetic uses them,
``fitness_v5.shortcut_audit`` at ``fitness_v5.py:790-834``):

* A shortcut rule ``r`` maps a positive probe to a predicted option index in {0,1}.
* **Direction A** (mathematics varies, shortcut held constant) -- an unordered pair of
  positive probes (p,q) with ``r(p) == r(q)`` and ``expected_index(p) != expected_index(q)``.
  Such a pair contributes exactly 1 correct of 2 to ``r``: the feature is uninformative on it.
* **Direction B** (shortcut varies, mathematics held constant) -- ``r(p) != r(q)`` and
  ``expected_index(p) == expected_index(q)``.  Also exactly 1 of 2.

Both are the primitives a balanced generator would have to emit.  Makes ZERO model calls.
"""

from __future__ import annotations

import itertools
import json
import pickle
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import POSITIVE_VARIANTS, V5Probe


def names(p: V5Probe) -> tuple[str, str]:
    return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))


def text(p: V5Probe) -> str:
    return canonical_json(p.state.to_dict(include_display_identity=False))


# Byte-for-byte V5's rule set (fitness_v5.py:800-819).
RULES: dict[str, Callable[[V5Probe], int]] = {
    "always_first_option": lambda p: 0,
    "always_second_option": lambda p: 1,
    "first_mentioned_in_state": lambda p: (
        0 if text(p).find(f'"{names(p)[0]}"') <= text(p).find(f'"{names(p)[1]}"') else 1
    ),
    "last_mentioned_in_state": lambda p: (
        0 if text(p).rfind(f'"{names(p)[0]}"') >= text(p).rfind(f'"{names(p)[1]}"') else 1
    ),
    "more_frequent_in_state": lambda p: (
        0 if text(p).count(f'"{names(p)[0]}"') >= text(p).count(f'"{names(p)[1]}"') else 1
    ),
    "shorter_option_text": lambda p: (
        0 if (len(names(p)[0]), names(p)[0]) <= (len(names(p)[1]), names(p)[1]) else 1
    ),
    "alphabetically_first": lambda p: 0 if names(p)[0] <= names(p)[1] else 1,
}
# Rules that are constant by construction carry no pair information; kept for completeness
# because V5's audit scores them, but flagged so the report does not overclaim.
CONSTANT_RULES = {"always_first_option", "always_second_option"}


def cells(probes: Sequence[V5Probe]) -> dict[tuple[str, int], list[V5Probe]]:
    out: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for p in probes:
        if p.variant.value in POSITIVE_VARIANTS:
            out[(p.mechanism, p.level)].append(p)
    return dict(out)


def analyse_cell(cell: Sequence[V5Probe]) -> dict[str, Any]:
    by_family: dict[str, list[V5Probe]] = defaultdict(list)
    for p in cell:
        by_family[p.family_id].append(p)
    families = sorted(by_family)
    report: dict[str, Any] = {
        "positives": len(cell),
        "families": len(families),
        "rules": {},
    }
    for rule_name, rule in RULES.items():
        preds = {p.probe_id: rule(p) for p in cell}
        truth = {p.probe_id: p.expected_index for p in cell}
        score = sum(preds[k] == truth[k] for k in preds) / len(preds)
        # per-family hit count out of the family's two positives
        family_hits: dict[str, int] = {}
        family_pred_constant: dict[str, bool] = {}
        for fam in families:
            members = by_family[fam]
            family_hits[fam] = sum(preds[p.probe_id] == truth[p.probe_id] for p in members)
            family_pred_constant[fam] = len({preds[p.probe_id] for p in members}) == 1
        # Direction A / B pair counts, within-family and across-family (same cell)
        a_within = a_across = b_within = b_across = 0
        for p, q in itertools.combinations(cell, 2):
            same_family = p.family_id == q.family_id
            same_pred = preds[p.probe_id] == preds[q.probe_id]
            same_truth = truth[p.probe_id] == truth[q.probe_id]
            if same_pred and not same_truth:
                if same_family:
                    a_within += 1
                else:
                    a_across += 1
            if not same_pred and same_truth:
                if same_family:
                    b_within += 1
                else:
                    b_across += 1
        report["rules"][rule_name] = {
            "score": score,
            "inverted_score": 1.0 - score,
            "best_of_rule_or_negation": max(score, 1.0 - score),
            "family_hit_histogram": dict(Counter(family_hits.values())),
            "families_with_constant_prediction": sum(family_pred_constant.values()),
            "direction_A_pairs_within_family": a_within,
            "direction_A_pairs_across_family": a_across,
            "direction_B_pairs_within_family": b_within,
            "direction_B_pairs_across_family": b_across,
            "constant_rule": rule_name in CONSTANT_RULES,
        }
    informative = {n: v for n, v in report["rules"].items() if not v["constant_rule"]}
    report["best_shortcut_accuracy"] = max(
        v["best_of_rule_or_negation"] for v in report["rules"].values()
    )
    report["best_shortcut_feature"] = max(
        report["rules"], key=lambda n: abs(report["rules"][n]["score"] - 0.5)
    )
    report["worst_informative_rule"] = max(
        informative, key=lambda n: abs(informative[n]["score"] - 0.5)
    )
    return report


def subset_feasibility(cell: Sequence[V5Probe], target: float = 0.75) -> dict[str, Any]:
    """Can a family SUBSET of this cell drive every rule's best-of-rule-or-negation to <= target?

    Exhaustive over the 2**n family subsets (n = 12 here).  This asks the audit's own
    question of the bank as generated: is the leak a property of the mathematics, or of
    which families the generator happened to emit?
    """

    by_family: dict[str, list[V5Probe]] = defaultdict(list)
    for p in cell:
        by_family[p.family_id].append(p)
    families = sorted(by_family)
    hits: dict[str, list[int]] = {}
    sizes: list[int] = [len(by_family[f]) for f in families]
    for rule_name, rule in RULES.items():
        hits[rule_name] = [
            sum(rule(p) == p.expected_index for p in by_family[f]) for f in families
        ]
    n = len(families)
    best: dict[str, Any] | None = None
    feasible_counts: Counter[int] = Counter()
    for mask in range(1, 1 << n):
        chosen = [i for i in range(n) if mask >> i & 1]
        total = sum(sizes[i] for i in chosen)
        if total < 24:  # V5's min_positives_for_gates
            continue
        worst = 0.0
        for rule_name in RULES:
            s = sum(hits[rule_name][i] for i in chosen) / total
            worst = max(worst, max(s, 1.0 - s))
        if worst <= target:
            feasible_counts[len(chosen)] += 1
            if best is None or (worst, -len(chosen)) < (best["worst"], -best["families"]):
                best = {"worst": worst, "families": len(chosen), "mask": mask}
    return {
        "families_available": n,
        "min_positives_required": 24,
        "target_best_shortcut_max": target,
        "feasible_subsets": sum(feasible_counts.values()),
        "feasible_by_size": dict(sorted(feasible_counts.items())),
        "best": best,
    }


def main() -> int:
    bank = Path(sys.argv[1])
    out = Path(sys.argv[2])
    with bank.open("rb") as handle:
        probes: tuple[V5Probe, ...] = pickle.load(handle)
    table: dict[str, Any] = {"total_probes": len(probes), "cells": {}}
    for (mechanism, level), cell in sorted(cells(probes).items()):
        key = f"{mechanism}/L{level}"
        entry = analyse_cell(cell)
        entry["subset_feasibility"] = subset_feasibility(cell)
        table["cells"][key] = entry
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=2, sort_keys=True))
    for key, entry in table["cells"].items():
        print(
            f"{key:42s} best={entry['best_shortcut_accuracy']:.4f} "
            f"({entry['best_shortcut_feature']}) "
            f"informative={entry['worst_informative_rule']} "
            f"feasible_subsets={entry['subset_feasibility']['feasible_subsets']}"
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
