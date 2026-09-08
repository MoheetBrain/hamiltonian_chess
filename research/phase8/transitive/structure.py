"""Structural (generator-level) explanation of every surface cue the audit can find.

Run as ``.venv/bin/python -m research.phase8.transitive.structure``.  Zero model calls.

Reads the canonical states of the SAME fresh population the adversary audit renders and asks,
analytically rather than statistically, where a rendered-prompt cue could come from:

* ``junction``: V1 lets ``other[0]`` depend on ``attached[junction]``; when ``junction == hops-1``
  that node IS the answer, so the answer carries one extra in-reference (P = 1/hops).
* ``parent degree``: the alternate ``other[hops-1]`` is named in ``other[hops-2]``'s dependency
  list; at hops = 2 that node is ``other[0]``, which ALWAYS has two dependencies, while the
  answer's parent ``attached[0]`` always has one.  A 32-character window around the mention sees
  the difference on every L1 family.
* ``slots``: ``_shuffled`` is keyed by the family salt, so the permutation is identical across the
  twin and every node keeps its list slot while the CONTENT swaps (audit item C7 / A9-F2).

The C3f analogue is measured directly: over every node reachable from ``e:leaf`` the Spearman
correlation between hop distance and three surface statistics (evidence-list slot, mention count,
first byte offset in the rendered L3_JSON_AST prompt).  C3f found rho(preorder rank, depth) = 0.735
for ``formal_expression_depth`` because currying makes "earlier" and "deeper" the same fact; if a
comparable correlation existed here the cue would be semantic rather than a construction artifact.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from arena.experiments.fitness_v4 import _h

from .common import (
    LEVELS,
    N_FAMILIES,
    Item,
    build_population,
    family_salt,
    hop_distances,
    hops_for_level,
    render,
)

HERE = Path(__file__).resolve().parent
V5_EXPERIMENT_VERSION = "arena-representation-fitness-v5"


def v1_junction(level: int, index: int) -> int:
    """Re-derive V1's junction exactly as ``fitness_v5.derive_probe_family`` seeds it."""

    salt = f"{V5_EXPERIMENT_VERSION}|transitive_dependency|{level}|{family_salt(level, index)}"
    return _h(f"{salt}|junction", hops_for_level(level))


def evidence_stats(item: Item) -> dict[str, Any]:
    """Per-candidate slot, mention count and parent degrees from the canonical evidence list."""

    ev = item.state.evidence_dependencies
    a, b = item.names
    answer = item.names[item.expected_index]
    alternate = item.names[1 - item.expected_index]
    out: dict[str, Any] = {}
    for role, name in (("answer", answer), ("alternate", alternate)):
        slot = next(i for i, n in enumerate(ev) if n.evidence_id == name)
        mentions = 1 + sum(n.dependencies.count(name) for n in ev)
        parents = [n for n in ev if name in n.dependencies]
        out[role] = {
            "slot": slot,
            "mentions": mentions,
            "in_degree": len(parents),
            "parent_degrees": sorted(len(p.dependencies) for p in parents),
        }
    return out


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    rx = np.argsort(np.argsort(x, kind="stable"), kind="stable").astype(float)
    ry = np.argsort(np.argsort(y, kind="stable"), kind="stable").astype(float)
    # average ranks for ties
    for r, v in ((rx, x), (ry, y)):
        for val in np.unique(v):
            mask = v == val
            if mask.sum() > 1:
                r[mask] = r[mask].mean()
    return float(np.corrcoef(rx, ry)[0, 1])


def c3f_analogue(items: list[Item], surface: str = "L3_JSON_AST") -> dict[str, Any]:
    """Hop distance vs surface statistics over every reachable node (C3f analogue)."""

    hops_all: list[float] = []
    slot_all: list[float] = []
    count_all: list[float] = []
    offset_all: list[float] = []
    per_family_rho: list[float] = []
    for item in items:
        if item.variant != "ORIGINAL":
            continue
        dist = hop_distances(item.state)
        ev = item.state.evidence_dependencies
        prompt = render(item, surface)
        state_text = prompt.split("\nCURRENT STATE:\n", 1)[1]
        rows = []
        for slot, node in enumerate(ev):
            if node.evidence_id not in dist:
                continue
            mentions = 1 + sum(n.dependencies.count(node.evidence_id) for n in ev)
            rows.append((dist[node.evidence_id], slot, mentions, state_text.find(node.evidence_id)))
        arr = np.asarray(rows, dtype=float)
        hops_all.extend(arr[:, 0])
        slot_all.extend(arr[:, 1])
        count_all.extend(arr[:, 2])
        offset_all.extend(arr[:, 3])
        per_family_rho.append(spearman(arr[:, 0], arr[:, 3]))
    h = np.asarray(hops_all)
    fam = np.asarray(per_family_rho)
    fam = fam[~np.isnan(fam)]
    return {
        "surface": surface,
        "n_reachable_nodes": int(len(h)),
        "rho_hops_vs_list_slot": spearman(h, np.asarray(slot_all)),
        "rho_hops_vs_mention_count": spearman(h, np.asarray(count_all)),
        "rho_hops_vs_first_byte_offset": spearman(h, np.asarray(offset_all)),
        "per_family_rho_hops_vs_first_byte_offset": {
            "mean": float(fam.mean()) if len(fam) else None,
            "sd": float(fam.std()) if len(fam) else None,
            "n": int(len(fam)),
        },
        "reference_C3f_formal_expression_depth": 0.735,
    }


def analyse_generator(generator: str, level: int, n_families: int) -> dict[str, Any]:
    items = build_population(generator, level, n_families)
    hops = hops_for_level(level)
    by_family: dict[int, dict[str, Item]] = {}
    for it in items:
        by_family.setdefault(it.family_index, {})[it.variant] = it
    junction_is_answer = 0
    answer_more_mentions = 0
    alt_more_mentions = 0
    parent_degree_differs = 0
    slots_fixed_across_twins = 0
    stats_swapped_across_twins = 0
    stats_identical_across_twins = 0
    leaf_dep_only_difference = 0
    for index, fam in by_family.items():
        o, c = fam["ORIGINAL"], fam["COUNTERFACTUAL"]
        so, sc = evidence_stats(o), evidence_stats(c)
        if generator == "v1_frozen":
            junction_is_answer += int(v1_junction(level, index) == hops - 1)
        answer_more_mentions += int(so["answer"]["mentions"] > so["alternate"]["mentions"])
        alt_more_mentions += int(so["answer"]["mentions"] < so["alternate"]["mentions"])
        parent_degree_differs += int(so["answer"]["parent_degrees"] != so["alternate"]["parent_degrees"])
        slots_fixed_across_twins += int(
            so["answer"]["slot"] == sc["answer"]["slot"] and so["alternate"]["slot"] == sc["alternate"]["slot"]
        )
        # per-OPTION statistics: identical across the twin (balanced) or swapped (confounded)?
        opt_o = [so["answer" if o.expected_index == i else "alternate"] for i in range(2)]
        opt_c = [sc["answer" if c.expected_index == i else "alternate"] for i in range(2)]
        key = lambda d: (d["slot"], d["mentions"], tuple(d["parent_degrees"]))  # noqa: E731
        if [key(d) for d in opt_o] == [key(d) for d in opt_c]:
            stats_identical_across_twins += 1
        if [key(d) for d in opt_o] == [key(d) for d in reversed(opt_c)]:
            stats_swapped_across_twins += 1
        diff = [
            (x.evidence_id, y.evidence_id)
            for x, y in zip(o.state.evidence_dependencies, c.state.evidence_dependencies, strict=True)
            if x != y
        ]
        leaf_dep_only_difference += int(diff == [("e:leaf", "e:leaf")])
    n = len(by_family)
    expected_count_rule = 0.5 + 0.5 / hops if generator == "v1_frozen" else 0.5
    return {
        "generator": generator,
        "level": level,
        "hops": hops,
        "n_families": n,
        "junction_equals_answer_families": junction_is_answer,
        "junction_equals_answer_fraction": junction_is_answer / n,
        "expected_fraction_1_over_hops": 1.0 / hops,
        "answer_has_more_mentions": answer_more_mentions / n,
        "alternate_has_more_mentions": alt_more_mentions / n,
        "predicted_mention_count_rule_accuracy": expected_count_rule,
        "measured_mention_count_rule_accuracy": (answer_more_mentions + 0.5 * (n - answer_more_mentions - alt_more_mentions)) / n,
        "parent_degree_differs_fraction": parent_degree_differs / n,
        "slots_fixed_across_twins_fraction": slots_fixed_across_twins / n,
        "per_option_stats_identical_across_twins_fraction": stats_identical_across_twins / n,
        "per_option_stats_swapped_across_twins_fraction": stats_swapped_across_twins / n,
        "twins_differ_only_in_leaf_dependency_fraction": leaf_dep_only_difference / n,
        "analytic_surface_ceiling": (
            1.0 if (generator == "v1_frozen" and hops == 2) else expected_count_rule
        ),
        "analytic_surface_ceiling_reason": (
            "hops=2: the alternate's parent other[0] always has two dependencies (junction edge); "
            "the answer's parent attached[0] always has one -> every family is separable"
            if generator == "v1_frozen" and hops == 2
            else (
                "only the junction families (P=1/hops) expose a per-candidate asymmetry; every "
                "other family is an exact content swap with fixed slots -> 0.5 by construction"
                if generator == "v1_frozen"
                else "twins differ only in e:leaf's dependency, which names neither candidate"
            )
        ),
        "c3f_analogue": c3f_analogue(items),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-families", type=int, default=N_FAMILIES)
    parser.add_argument("--out", type=Path, default=HERE / "structure.json")
    args = parser.parse_args(argv)
    t0 = time.time()
    cells = [
        analyse_generator(g, level, args.n_families)
        for g in ("v1_frozen", "v2_candidate")
        for level in LEVELS
    ]
    payload = {
        "_disclaimer": (
            "Structural diagnostic of the generator. Zero model calls. Nothing here re-scores V7 or "
            "reinterprets a recorded sentinel."
        ),
        "cells": cells,
        "elapsed_seconds": time.time() - t0,
    }
    args.out.write_text(json.dumps(payload, indent=1))
    for c in cells:
        print(
            f"{c['generator']:12s} L{c['level']} hops={c['hops']} junction==answer {c['junction_equals_answer_fraction']:.3f} "
            f"count-rule {c['measured_mention_count_rule_accuracy']:.4f} (pred {c['predicted_mention_count_rule_accuracy']:.4f}) "
            f"parent-degree-differs {c['parent_degree_differs_fraction']:.3f} slots-fixed {c['slots_fixed_across_twins_fraction']:.3f} "
            f"swapped {c['per_option_stats_swapped_across_twins_fraction']:.3f} identical {c['per_option_stats_identical_across_twins_fraction']:.3f} "
            f"rho(hops,offset)={c['c3f_analogue']['rho_hops_vs_first_byte_offset']:.3f}"
        )
    print(f"elapsed {payload['elapsed_seconds']:.1f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
