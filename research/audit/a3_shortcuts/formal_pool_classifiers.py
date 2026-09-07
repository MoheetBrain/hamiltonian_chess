"""AUDITOR 3 (A3) DIAGNOSTIC -- surface-only classifiers on the FULL formal pool.

`build_dev_pool` uses only the first 12 states of each depth stratum.  The length-filtered pool
holds 34/34/36.  Running the same surface-only classifiers on the whole stratum triples n and
gives a better-powered estimate of the best obtainable non-semantic predictor for
`formal_expression_depth` at each ladder level.

Grouped 6-fold CV by twin family.  Zero model calls.  DIAGNOSTIC ONLY -- a measurement of the
INSTRUMENT, never a re-scoring of V7.
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

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    EXPERIMENT_SEED,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    V5Slice,
    _formal_pool,
    derive_probe_family,
)
from research.audit.a3_shortcuts.build_bank import global_features, per_option_features

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
OUT = HERE / "formal_pool_classifiers.json"
SEED = 20260907

MODELS = {
    "logistic_regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=5000, random_state=SEED)),
    "decision_stump_d1": lambda: DecisionTreeClassifier(max_depth=1, random_state=SEED),
    "decision_tree_d5": lambda: DecisionTreeClassifier(max_depth=5, random_state=SEED),
    "random_forest_300": lambda: RandomForestClassifier(
        n_estimators=300, random_state=SEED, n_jobs=1),
    "gradient_boosting": lambda: HistGradientBoostingClassifier(
        max_iter=300, min_samples_leaf=5, random_state=SEED),
}
V5_LIVE = ("first_mentioned_in_state", "more_frequent_in_state", "last_mentioned_in_state")


def v5_rules(p):
    n0 = str(p.options[0].arguments[0].value)
    n1 = str(p.options[1].arguments[0].value)
    t = canonical_json(p.state.to_dict(include_display_identity=False))
    return {
        "first_mentioned_in_state": 0 if t.find(f'"{n0}"') <= t.find(f'"{n1}"') else 1,
        "last_mentioned_in_state": 0 if t.rfind(f'"{n0}"') >= t.rfind(f'"{n1}"') else 1,
        "more_frequent_in_state": 0 if t.count(f'"{n0}"') >= t.count(f'"{n1}"') else 1,
        "shorter_option_text": 0 if (len(n0), n0) <= (len(n1), n1) else 1,
        "alphabetically_first": 0 if n0 <= n1 else 1,
        "always_first_option": 0,
    }


def main() -> int:
    pool = _formal_pool(Path.cwd())
    results = {}
    for level, params in enumerate(LADDERS["formal_expression_depth"]):
        bucket = pool[str(params["stratum"])]
        X, y, g, ruleacc = [], [], [], {k: 0 for k in v5_rules.__doc__ or []} or None
        rules_correct = None
        keys = None
        n_pos = 0
        for index, formal in enumerate(bucket):
            salt = EXPERIMENT_SEED + MECHANISMS.index("formal_expression_depth") * 1000 \
                + level * 100 + index
            for p in derive_probe_family(
                "formal_expression_depth", level, V5Slice.DEV, salt, formal
            ):
                if p.variant.value not in POSITIVE_VARIANTS:
                    continue
                n_pos += 1
                r = v5_rules(p)
                if rules_correct is None:
                    rules_correct = dict.fromkeys(r, 0)
                for k, v in r.items():
                    rules_correct[k] += int(v == p.expected_index)
                f0, f1 = per_option_features(p, 0), per_option_features(p, 1)
                gl = global_features(p)
                if keys is None:
                    keys = (
                        [k for k in sorted(f0) if not k.startswith("SEMANTIC_")],
                        sorted(gl),
                    )
                X.append([f0[k] - f1[k] for k in keys[0]] + [gl[k] for k in keys[1]])
                y.append(p.expected_index)
                g.append(p.family_id)
        X, y, g = np.asarray(X, float), np.asarray(y, int), np.asarray(g)
        v5 = {k: max(c / n_pos, 1 - c / n_pos) for k, c in rules_correct.items()}
        cell = {
            "stratum": str(params["stratum"]),
            "explicit": bool(params["explicit"]),
            "n_states_in_stratum": len(bucket),
            "n_positives": int(n_pos),
            "v5_family_folded_on_full_pool": v5,
            "v5_best_on_full_pool": max(v5.values()),
            "v5_best_rule_on_full_pool": max(v5, key=lambda k: v5[k]),
            "models": {},
        }
        gkf = GroupKFold(n_splits=6)
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
                "grouped_6fold_cv": float((preds == y).mean()),
            }
        cell["best_grouped_cv"] = max(v["grouped_6fold_cv"] for v in cell["models"].values())
        cell["best_grouped_cv_model"] = max(
            cell["models"], key=lambda k: cell["models"][k]["grouped_6fold_cv"]
        )
        cell["combination_gain_over_v5_best"] = cell["best_grouped_cv"] - cell["v5_best_on_full_pool"]
        results[f"formal_expression_depth|L{level}"] = cell

    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC at full-pool n. NOT a re-scoring of V7; no sentinel may be promoted, "
            "re-scored or reinterpreted from these numbers."
        ),
        "seed": SEED,
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"{'cell':34s} {'n':>4s} {'V5best':>7s} {'rule':>26s} {'bestCV':>7s} {'gain':>7s}  model")
    for k, c in results.items():
        print(f"{k:34s} {c['n_positives']:4d} {c['v5_best_on_full_pool']:7.4f} "
              f"{c['v5_best_rule_on_full_pool']:>26s} {c['best_grouped_cv']:7.4f} "
              f"{c['combination_gain_over_v5_best']:+7.4f}  {c['best_grouped_cv_model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
