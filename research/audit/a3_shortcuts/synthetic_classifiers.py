"""AUDITOR 3 (A3) DIAGNOSTIC -- best obtainable SURFACE-ONLY predictor at LARGE n.

The two synthetic mechanisms can be sampled without limit, so the question "is the shortcut
family too weak?" can be answered at n = 800 positives per cell instead of n = 24.  Features are
the same surface-only block used in `combined_classifiers.py` (no depth, no oracle, no semantics),
recomputed here directly from freshly generated families.

Evaluation is grouped 5-fold CV by twin family, so no family straddles the train/test boundary.

Zero model calls.  DIAGNOSTIC ONLY -- a measurement of the INSTRUMENT, never a re-scoring of V7.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from arena.experiments.fitness_v5 import (
    EXPERIMENT_SEED,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    V5Slice,
    derive_probe_family,
)
from research.audit.a3_shortcuts.build_bank import (
    global_features,
    per_option_features,
)

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
OUT = HERE / "synthetic_classifiers.json"
N_FAMILIES = 400
SEED = 20260907

MODELS = {
    "logistic_regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=5000, random_state=SEED)),
    "decision_stump_d1": lambda: DecisionTreeClassifier(max_depth=1, random_state=SEED),
    "decision_tree_d5": lambda: DecisionTreeClassifier(max_depth=5, random_state=SEED),
    "random_forest_300": lambda: RandomForestClassifier(
        n_estimators=300, random_state=SEED, n_jobs=1),
    "gradient_boosting": lambda: HistGradientBoostingClassifier(
        max_iter=300, random_state=SEED),
}


def build(mechanism: str, level: int):
    X, y, g = [], [], []
    keys = None
    for index in range(N_FAMILIES):
        salt = EXPERIMENT_SEED + MECHANISMS.index(mechanism) * 1000 + level * 100 + index
        for p in derive_probe_family(mechanism, level, V5Slice.DEV, salt, None):
            if p.variant.value not in POSITIVE_VARIANTS:
                continue
            f0, f1 = per_option_features(p, 0), per_option_features(p, 1)
            gl = global_features(p)
            if keys is None:
                keys = ([k for k in sorted(f0) if not k.startswith("SEMANTIC_")], sorted(gl))
            X.append([f0[k] - f1[k] for k in keys[0]] + [gl[k] for k in keys[1]])
            y.append(p.expected_index)
            g.append(p.family_id)
    names = [f"d_{k}" for k in keys[0]] + [f"g_{k}" for k in keys[1]]
    return np.asarray(X, float), np.asarray(y, int), np.asarray(g), names


def main() -> int:
    results = {}
    for mechanism in ("transitive_dependency", "precondition_conjunction"):
        for level in range(len(LADDERS[mechanism])):
            X, y, g, names = build(mechanism, level)
            cell = {"n_positives": int(len(y)), "n_families": int(len(set(g))), "models": {}}
            gkf = GroupKFold(n_splits=5)
            for name, make in MODELS.items():
                preds = np.empty_like(y)
                for tr, te in gkf.split(X, y, groups=g):
                    m = make()
                    m.fit(X[tr], y[tr])
                    preds[te] = m.predict(X[te])
                m = make()
                m.fit(X, y)
                cell["models"][name] = {
                    "in_sample": float((m.predict(X) == y).mean()),
                    "grouped_5fold_cv": float((preds == y).mean()),
                }
            cell["best_grouped_cv"] = max(v["grouped_5fold_cv"] for v in cell["models"].values())
            cell["best_grouped_cv_model"] = max(
                cell["models"], key=lambda k: cell["models"][k]["grouped_5fold_cv"]
            )
            results[f"{mechanism}|L{level}"] = cell
    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC at large n. NOT a re-scoring of V7; no sentinel may be promoted, "
            "re-scored or reinterpreted from these numbers."
        ),
        "n_families_per_cell": N_FAMILIES,
        "seed": SEED,
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"{'cell':34s} {'n':>5s} {'bestCV':>7s}  model")
    for k, c in results.items():
        print(f"{k:34s} {c['n_positives']:5d} {c['best_grouped_cv']:7.4f}  "
              f"{c['best_grouped_cv_model']}")
        for m, v in c["models"].items():
            print(f"{'':34s}       {m:22s} in={v['in_sample']:.4f} cv={v['grouped_5fold_cv']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
