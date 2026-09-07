"""AUDITOR 3 (A3) DIAGNOSTIC -- model-free classifiers on SURFACE-ONLY features.

These classifiers are a DIAGNOSTIC OF THE INSTRUMENT (how much of each cell's answer is
recoverable without semantics), NOT a re-scoring of V7.  No number produced here may be used
to re-score, promote or reinterpret any recorded sentinel.

Inputs: `bank_features.jsonl` (built by build_bank.py).  Semantic/oracle-adjacent features
(prefix `SEMANTIC_`) are EXCLUDED from every fitted model and reported separately as a
reference line only.

Evaluation, three ways, because the distinction is the point of this audit:
  * `in_sample`         -- fit and score on the same 24 items.  This is the SAME protocol as
                           V5's `shortcut_audit`, which selects `worst_rule` and reports its
                           score on the identical items.  Comparable, and optimistic.
  * `loso_cv`           -- leave-one-FAMILY-out CV (12 folds of 2 twinned items).  Honest.
  * `level_transfer`    -- fit on the other levels of the same mechanism, score on this one.
"""

from __future__ import annotations

import json
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
BANK = HERE / "bank_features.jsonl"
OUT = HERE / "combined_classifiers.json"
SEED = 20260907


def load():
    rows = [json.loads(line) for line in BANK.read_text().splitlines() if line.strip()]
    return rows


def featurise(rows):
    """Antisymmetric surface features: option0 statistic minus option1 statistic, plus
    symmetric global statistics.  Nothing depth-derived, nothing oracle-derived."""
    per_opt = sorted(k for k in rows[0]["opt0"] if not k.startswith("SEMANTIC_"))
    glob = sorted(rows[0]["glob"])
    names = [f"d_{k}" for k in per_opt] + [f"g_{k}" for k in glob]
    X, y, groups = [], [], []
    for r in rows:
        v = [float(r["opt0"][k]) - float(r["opt1"][k]) for k in per_opt]
        v += [float(r["glob"][k]) for k in glob]
        X.append(v)
        y.append(int(r["expected_index"]))
        groups.append(r["family_id"])
    return np.asarray(X, float), np.asarray(y, int), np.asarray(groups), names


def models():
    return {
        "majority_baseline": lambda: DummyClassifier(strategy="most_frequent"),
        "logistic_regression": lambda: make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=5000, C=1.0, random_state=SEED)
        ),
        "decision_stump_d1": lambda: DecisionTreeClassifier(max_depth=1, random_state=SEED),
        "decision_tree_d3": lambda: DecisionTreeClassifier(max_depth=3, random_state=SEED),
        "decision_tree_unbounded": lambda: DecisionTreeClassifier(random_state=SEED),
        "random_forest_300": lambda: RandomForestClassifier(
            n_estimators=300, random_state=SEED, n_jobs=1
        ),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=200, random_state=SEED
        ),
    }


V5_RULE_FEATURES = {
    # V5's live rules re-expressed as thresholds on the diff features, for a like-for-like line.
    "first_mentioned_in_state": ("d_first_offset", "<="),
    "last_mentioned_in_state": ("d_last_offset", ">="),
    "more_frequent_in_state": ("d_count_quoted", ">="),
}


def v5_rule_scores(rows, cell_rows):
    """V5's own family, in-sample, on this cell -- recomputed from the feature table."""
    out = {}
    for name, (feat, op) in V5_RULE_FEATURES.items():
        correct = 0
        for r in cell_rows:
            if feat == "d_first_offset":
                d = r["opt0"]["first_offset"] - r["opt1"]["first_offset"]
                pred = 0 if d <= 0 else 1
            elif feat == "d_last_offset":
                d = r["opt0"]["last_offset"] - r["opt1"]["last_offset"]
                pred = 0 if d >= 0 else 1
            else:
                d = r["opt0"]["count_quoted"] - r["opt1"]["count_quoted"]
                pred = 0 if d >= 0 else 1
            correct += int(pred == r["expected_index"])
        s = correct / len(cell_rows)
        out[name] = max(s, 1.0 - s)  # V5 semantics: rule OR its negation
    out["always_first_option"] = max(
        sum(r["expected_index"] == 0 for r in cell_rows) / len(cell_rows),
        sum(r["expected_index"] == 1 for r in cell_rows) / len(cell_rows),
    )
    return out


def loso(Xc, yc, gc, make):
    preds = np.empty_like(yc)
    for g in np.unique(gc):
        te = gc == g
        tr = ~te
        if len(np.unique(yc[tr])) < 2:
            preds[te] = yc[tr][0] if len(yc[tr]) else 0
            continue
        m = make()
        m.fit(Xc[tr], yc[tr])
        preds[te] = m.predict(Xc[te])
    return float((preds == yc).mean())


def main() -> int:
    rows = load()
    X, y, groups, names = featurise(rows)
    idx_by_cell = defaultdict(list)
    for i, r in enumerate(rows):
        idx_by_cell[(r["mechanism"], r["level"])].append(i)

    results = {}
    for (mech, lvl), idx in sorted(idx_by_cell.items()):
        idx = np.asarray(idx)
        Xc, yc, gc = X[idx], y[idx], groups[idx]
        cell_rows = [rows[i] for i in idx]
        cell = {
            "n": int(len(idx)),
            "n_families": int(len(set(gc))),
            "answer_share_index_0": float((yc == 0).mean()),
            "v5_family_in_sample": v5_rule_scores(rows, cell_rows),
            "models": {},
        }
        cell["v5_best_in_sample"] = max(cell["v5_family_in_sample"].values())
        cell["v5_best_feature"] = max(
            cell["v5_family_in_sample"], key=lambda k: cell["v5_family_in_sample"][k]
        )
        # level transfer: train on the same mechanism's OTHER levels
        other = np.asarray(
            [i for (m, l), ii in idx_by_cell.items() if m == mech and l != lvl for i in ii]
        )
        for name, make in models().items():
            m = make()
            m.fit(Xc, yc)
            in_s = float((m.predict(Xc) == yc).mean())
            cv = loso(Xc, yc, gc, make)
            m2 = make()
            m2.fit(X[other], y[other])
            xfer = float((m2.predict(Xc) == yc).mean())
            cell["models"][name] = {
                "in_sample": in_s,
                "loso_cv": cv,
                "level_transfer": xfer,
            }
        best_in = max(v["in_sample"] for k, v in cell["models"].items() if k != "majority_baseline")
        best_cv = max(v["loso_cv"] for k, v in cell["models"].items() if k != "majority_baseline")
        cell["best_combined_in_sample"] = best_in
        cell["best_combined_loso_cv"] = best_cv
        cell["delta_in_sample_vs_v5"] = best_in - cell["v5_best_in_sample"]
        cell["delta_loso_cv_vs_v5_in_sample"] = best_cv - cell["v5_best_in_sample"]
        results[f"{mech}|L{lvl}"] = cell

    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC of the shortcut instrument. These classifiers are NOT a re-scoring "
            "of V7 and may not be used to re-score, promote or reinterpret any sentinel."
        ),
        "seed": SEED,
        "n_surface_features": len(names),
        "feature_names": names,
        "excluded_semantic_features": ["SEMANTIC_bracket_depth_at_first", "SEMANTIC_bracket_depth_at_last"],
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    hdr = f"{'cell':38s} {'V5best':>7s} {'comb_in':>8s} {'comb_cv':>8s} {'d_in':>7s} {'d_cv':>7s}"
    print(hdr)
    for k, c in results.items():
        print(
            f"{k:38s} {c['v5_best_in_sample']:7.3f} {c['best_combined_in_sample']:8.3f} "
            f"{c['best_combined_loso_cv']:8.3f} {c['delta_in_sample_vs_v5']:+7.3f} "
            f"{c['delta_loso_cv_vs_v5_in_sample']:+7.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
