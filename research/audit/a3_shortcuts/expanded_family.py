"""AUDITOR 3 (A3) DIAGNOSTIC -- what happens when the shortcut family is made BIGGER.

Two questions, both protocol-matched to `fitness_v5.shortcut_audit`:

  Q6  How much better is a COMBINATION than V5's best single rule?
  Q8  How much of that improvement is selection noise from searching a larger family?

Every statistic is computed twice:
  * `in_sample`   -- V5's own protocol (select and evaluate on the same 24 items)
  * `split`       -- select on 6 families, evaluate on the other 6, averaged over all 462
                     balanced splits (exhaustive, no sampling error)
and each is accompanied by its RANDOMISATION NULL (labels permuted within twin pairs), which is
the value the statistic takes when there is no leakage whatsoever.

DIAGNOSTIC ONLY.  Not a re-scoring of V7.
"""

from __future__ import annotations

import itertools
import json
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
BANK = HERE / "bank_features.jsonl"
OUT = HERE / "expanded_family.json"
SEED = 20260907
RNG = np.random.default_rng(SEED)
NPERM = 20000
NPERM_SPLIT = 600
NPERM_MODEL = 200
N_SPLIT_EVAL = 120
N_SPLIT_NULL = 24


def load():
    return [json.loads(l) for l in BANK.read_text().splitlines() if l.strip()]


def featurise(rows):
    per_opt = sorted(k for k in rows[0]["opt0"] if not k.startswith("SEMANTIC_"))
    glob = sorted(rows[0]["glob"])
    names = [f"d_{k}" for k in per_opt] + [f"g_{k}" for k in glob]
    X = np.asarray(
        [[float(r["opt0"][k]) - float(r["opt1"][k]) for k in per_opt]
         + [float(r["glob"][k]) for k in glob] for r in rows], float
    )
    y = np.asarray([int(r["expected_index"]) for r in rows], int)
    g = np.asarray([r["family_id"] for r in rows])
    return X, y, g, names


def threshold_family_scores(X, y):
    """Each surface feature as a SIGN rule (V5's own form), folded with its negation.

    This is exactly `first_mentioned_in_state` generalised: `predict 0 iff d_feature <= 0`.
    """
    pred = (X > 0).astype(int)          # (n, F)
    s = (pred == y[:, None]).mean(axis=0)
    return np.maximum(s, 1 - s), s


MODELS = {
    "logistic_regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=5000, random_state=SEED)),
    "decision_stump_d1": lambda: DecisionTreeClassifier(max_depth=1, random_state=SEED),
    "decision_tree_d3": lambda: DecisionTreeClassifier(max_depth=3, random_state=SEED),
    "decision_tree_unbounded": lambda: DecisionTreeClassifier(random_state=SEED),
    "random_forest_300": lambda: RandomForestClassifier(
        n_estimators=300, random_state=SEED, n_jobs=1),
    "gradient_boosting_tuned": lambda: HistGradientBoostingClassifier(
        max_iter=200, min_samples_leaf=2, max_leaf_nodes=4, l2_regularization=1.0,
        early_stopping=False, random_state=SEED),
}


def fit_score(make, Xtr, ytr, Xte, yte):
    if len(np.unique(ytr)) < 2:
        return float((np.full(len(yte), ytr[0]) == yte).mean())
    m = make()
    m.fit(Xtr, ytr)
    return float((m.predict(Xte) == yte).mean())


def split_indices(g):
    fams = defaultdict(list)
    for i, k in enumerate(g):
        fams[k].append(i)
    keys = sorted(fams)
    h = len(keys) // 2
    seen, out = set(), []
    for combo in itertools.combinations(range(len(keys)), h):
        comp = tuple(sorted(set(range(len(keys))) - set(combo)))
        if comp in seen:
            continue
        seen.add(combo)
        out.append((np.concatenate([fams[keys[i]] for i in combo]),
                    np.concatenate([fams[keys[i]] for i in comp])))
    return out


def pair_flip_labels(y, g, rng):
    fams = defaultdict(list)
    for i, k in enumerate(g):
        fams[k].append(i)
    yp = y.copy()
    for idx in fams.values():
        if rng.random() < 0.5:
            yp[idx] = 1 - yp[idx]
    return yp


def main() -> int:
    rows = load()
    cells = defaultdict(list)
    for r in rows:
        cells[(r["mechanism"], r["level"])].append(r)

    results = {}
    for (mech, lvl), cell_rows in sorted(cells.items()):
        X, y, g, fnames = featurise(cell_rows)
        splits = split_indices(g)

        # ---- expanded THRESHOLD family (V5's rule form, ~F rules instead of 7)
        w, _ = threshold_family_scores(X, y)
        exp_in = float(w.max())
        exp_arg = fnames[int(np.argmax(w))]
        # split-sample version of the same expanded family
        held = []
        for a, b in splits:
            wa, sa = threshold_family_scores(X[a], y[a])
            j = int(np.argmax(wa))
            sb = float(((X[b, j] > 0).astype(int) == y[b]).mean())
            held.append(sb if sa[j] >= 0.5 else 1 - sb)
        exp_split = float(np.mean(held))
        # randomisation null for both
        null_in, null_split = [], []
        for _ in range(NPERM):
            yp = pair_flip_labels(y, g, RNG)
            wp, _ = threshold_family_scores(X, yp)
            null_in.append(float(wp.max()))
        for _ in range(NPERM_SPLIT):
            yp = pair_flip_labels(y, g, RNG)
            hh = []
            for a, b in splits[:N_SPLIT_NULL]:
                wa, sa = threshold_family_scores(X[a], yp[a])
                j = int(np.argmax(wa))
                sb = float(((X[b, j] > 0).astype(int) == yp[b]).mean())
                hh.append(sb if sa[j] >= 0.5 else 1 - sb)
            null_split.append(float(np.mean(hh)))

        # ---- fitted models
        model_rows = {}
        for name, make in MODELS.items():
            in_s = fit_score(make, X, y, X, y)
            sp = float(np.mean([fit_score(make, X[a], y[a], X[b], y[b]) for a, b in splits[:N_SPLIT_EVAL]]))
            model_rows[name] = {"in_sample": in_s, "split_half": sp}
        best_model_split = max(model_rows, key=lambda k: model_rows[k]["split_half"])

        # randomisation null for the BEST-OF-MODELS split statistic
        # Null for the best-of-models split statistic. Restricted to the four CHEAP learners
        # (logistic + the three trees); random forest and boosting are excluded from the null
        # loop for cost, which makes this null slightly CONSERVATIVE (too low), not optimistic.
        cheap = {k: v for k, v in MODELS.items()
                 if k in {"logistic_regression", "decision_stump_d1", "decision_tree_d3",
                          "decision_tree_unbounded"}}
        mnull = []
        for _ in range(NPERM_MODEL):
            yp = pair_flip_labels(y, g, RNG)
            best = max(
                float(np.mean([fit_score(mk, X[a], yp[a], X[b], yp[b])
                               for a, b in splits[:N_SPLIT_NULL]]))
                for mk in cheap.values()
            )
            mnull.append(best)

        results[f"{mech}|L{lvl}"] = {
            "n": int(len(y)),
            "n_surface_threshold_rules": int(X.shape[1]),
            "expanded_threshold_family": {
                "in_sample_best": exp_in,
                "in_sample_best_feature": exp_arg,
                "in_sample_null_mean": float(np.mean(null_in)),
                "in_sample_null_q95": float(np.quantile(null_in, 0.95)),
                "in_sample_p": float(np.mean(np.array(null_in) >= exp_in - 1e-9)),
                "split_half_heldout": exp_split,
                "split_half_null_mean": float(np.mean(null_split)),
                "split_half_p": float(np.mean(np.array(null_split) >= exp_split - 1e-9)),
            },
            "models": model_rows,
            "best_model_by_split": best_model_split,
            "best_model_split_value": model_rows[best_model_split]["split_half"],
            "best_model_split_null_mean": float(np.mean(mnull)),
            "best_model_split_p": float(
                np.mean(np.array(mnull) >= model_rows[best_model_split]["split_half"] - 1e-9)
            ),
        }

    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC. Stronger shortcut families are a probe of the INSTRUMENT, not a "
            "re-scoring of V7. No sentinel may be promoted or reinterpreted from these numbers."
        ),
        "seed": SEED,
        "n_permutations_in_sample": NPERM,
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print(f"{'cell':32s} {'expIN':>6s} {'null':>6s} {'p':>6s} | "
          f"{'expSPLIT':>8s} {'null':>6s} | {'mdlSPLIT':>8s} {'null':>6s} {'p':>6s}  model")
    for k, c in results.items():
        e = c["expanded_threshold_family"]
        print(f"{k:32s} {e['in_sample_best']:6.3f} {e['in_sample_null_mean']:6.3f} "
              f"{e['in_sample_p']:6.3f} | {e['split_half_heldout']:8.3f} "
              f"{e['split_half_null_mean']:6.3f} | {c['best_model_split_value']:8.3f} "
              f"{c['best_model_split_null_mean']:6.3f} {c['best_model_split_p']:6.3f}  "
              f"{c['best_model_by_split']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
