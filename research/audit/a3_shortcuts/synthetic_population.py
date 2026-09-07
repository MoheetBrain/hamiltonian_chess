"""AUDITOR 3 (A3) DIAGNOSTIC -- the POPULATION shortcut rate of the two synthetic mechanisms.

`transitive_dependency` and `precondition_conjunction` are generated, so their shortcut rate is
not a 24-item estimate: it can be measured to arbitrary precision by drawing more families from
the SAME frozen generator with fresh salts.  That converts "is the observed 0.667 a real leak or
selection noise?" from an n=24 question into an n=800 question.

Zero model calls.  DIAGNOSTIC ONLY -- this is a measurement of the GENERATOR, not a re-scoring
of any V7 cell, and may not be used to promote, re-score or reinterpret any recorded sentinel.
"""

from __future__ import annotations

import json
from pathlib import Path

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    DEV_FAMILIES,
    EXPERIMENT_SEED,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    V5Slice,
    derive_probe_family,
)

HERE = Path(__file__).resolve().parent
OUT = HERE / "synthetic_population.json"
N_FAMILIES = 400


def rule_scores(probes):
    def nm(p):
        return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))

    def tx(p):
        return canonical_json(p.state.to_dict(include_display_identity=False))

    rules = {
        "always_first_option": lambda p: 0,
        "first_mentioned_in_state": lambda p: 0 if tx(p).find(f'"{nm(p)[0]}"') <= tx(p).find(f'"{nm(p)[1]}"') else 1,
        "last_mentioned_in_state": lambda p: 0 if tx(p).rfind(f'"{nm(p)[0]}"') >= tx(p).rfind(f'"{nm(p)[1]}"') else 1,
        "more_frequent_in_state": lambda p: 0 if tx(p).count(f'"{nm(p)[0]}"') >= tx(p).count(f'"{nm(p)[1]}"') else 1,
        "shorter_option_text": lambda p: 0 if (len(nm(p)[0]), nm(p)[0]) <= (len(nm(p)[1]), nm(p)[1]) else 1,
        "alphabetically_first": lambda p: 0 if nm(p)[0] <= nm(p)[1] else 1,
    }
    out = {}
    for name, r in rules.items():
        s = sum(r(p) == p.expected_index for p in probes) / len(probes)
        out[name] = {"raw": s, "folded": max(s, 1 - s)}
    return out


def main() -> int:
    results = {}
    for mechanism in ("transitive_dependency", "precondition_conjunction"):
        for level in range(len(LADDERS[mechanism])):
            dev, extra = [], []
            for index in range(N_FAMILIES):
                salt = (
                    EXPERIMENT_SEED + MECHANISMS.index(mechanism) * 1000 + level * 100 + index
                )
                fam = derive_probe_family(mechanism, level, V5Slice.DEV, salt, None)
                pos = [p for p in fam if p.variant.value in POSITIVE_VARIANTS]
                (dev if index < DEV_FAMILIES else extra).append(pos)
            flat_all = [p for g in dev + extra for p in g]
            flat_out = [p for g in extra for p in g]
            results[f"{mechanism}|L{level}"] = {
                "n_families_total": N_FAMILIES,
                "n_positives_total": len(flat_all),
                "population_scores_all": rule_scores(flat_all),
                "population_scores_excluding_DEV12": rule_scores(flat_out),
                "population_best_folded": max(
                    v["folded"] for v in rule_scores(flat_all).values()
                ),
                "population_best_rule": max(
                    rule_scores(flat_all), key=lambda k: rule_scores(flat_all)[k]["folded"]
                ),
            }
    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC of the frozen GENERATORS. Zero model calls. NOT a re-scoring of V7; "
            "no sentinel may be promoted, re-scored or reinterpreted from these numbers."
        ),
        "n_families_per_cell": N_FAMILIES,
        "dev_families_per_cell": DEV_FAMILIES,
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"{'cell':34s} {'popBest':>8s} {'rule':>26s} {'first_m':>8s} {'more_f':>8s}")
    for k, v in results.items():
        s = v["population_scores_all"]
        print(f"{k:34s} {v['population_best_folded']:8.4f} {v['population_best_rule']:>26s} "
              f"{s['first_mentioned_in_state']['folded']:8.4f} "
              f"{s['more_frequent_in_state']['folded']:8.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
