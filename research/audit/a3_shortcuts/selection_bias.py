"""AUDITOR 3 (A3) DIAGNOSTIC -- how much of the reported `worst_score` is SELECTION NOISE?

`fitness_v5.shortcut_audit` SELECTS `worst_rule = argmax |score - 0.5|` and REPORTS that same
rule's score on the SAME 24 items.  Selection and evaluation share every item, so the reported
statistic is a maximum of |k| correlated statistics and is biased UPWARD under the null of no
leakage.  This script quantifies that bias three ways:

 1. EXACT binomial nulls, under two exchangeability models:
      Null A (item-level)   : each item independently correct w.p. 1/2  -> Binomial(24, 1/2)
      Null B (twin-paired)  : a relabel-sensitive surface rule is right on BOTH twins of a
                              family or NEITHER -> 2*Binomial(12, 1/2)/24.  This is the correct
                              null for V5's construction and has effective n = 12, not 24.
 2. An EXACT-STRUCTURE randomisation test on the REAL bank: permute `expected_index` WITHIN each
    twin pair (the only degree of freedom V5's construction leaves), recompute the full audit,
    and read off the null distribution of the reported `worst_score`.  This accounts for the real
    correlation among rules and the real degeneracy of the family.
 3. SPLIT-SAMPLE: select the rule on one half of the families, evaluate on the other half.

DIAGNOSTIC ONLY.  No threshold is changed; no sentinel is re-scored.
"""

from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BANK = HERE / "bank_features.jsonl"
OUT = HERE / "selection_bias.json"
RNG = np.random.default_rng(20260907)
NPERM = 50000

RULES = ("always_first_option", "first_mentioned_in_state", "last_mentioned_in_state",
         "more_frequent_in_state", "shorter_option_text", "alphabetically_first")
# always_second_option is the exact negation of always_first_option and cannot change
# `worst_score`, which already folds a rule with its negation.


def rule_preds(rows):
    """Predicted index for each V5 rule, recomputed from the cached surface features."""
    P = {}
    P["always_first_option"] = np.zeros(len(rows), int)
    P["first_mentioned_in_state"] = np.array(
        [0 if r["opt0"]["first_offset"] <= r["opt1"]["first_offset"] else 1 for r in rows]
    )
    P["last_mentioned_in_state"] = np.array(
        [0 if r["opt0"]["last_offset"] >= r["opt1"]["last_offset"] else 1 for r in rows]
    )
    P["more_frequent_in_state"] = np.array(
        [0 if r["opt0"]["count_quoted"] >= r["opt1"]["count_quoted"] else 1 for r in rows]
    )
    P["shorter_option_text"] = np.array(
        [0 if (len(r["name_0"]), r["name_0"]) <= (len(r["name_1"]), r["name_1"]) else 1
         for r in rows]
    )
    P["alphabetically_first"] = np.array(
        [0 if r["name_0"] <= r["name_1"] else 1 for r in rows]
    )
    return P


def worst_score_from(preds: dict, y: np.ndarray) -> tuple[float, str]:
    scores = {n: float((p == y).mean()) for n, p in preds.items()}
    best = max(scores, key=lambda n: abs(scores[n] - 0.5))
    return max(scores[best], 1.0 - scores[best]), best


def binom_tail(n, k):
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n


def exact_nulls():
    out = {}
    for label, n_eff, step in (("null_A_item_level", 24, 1), ("null_B_twin_paired", 12, 2)):
        # distribution of s (accuracy) for ONE rule
        vals = np.array([(i * step) / 24 for i in range(n_eff + 1)])
        probs = np.array([math.comb(n_eff, i) / 2**n_eff for i in range(n_eff + 1)])
        w = np.maximum(vals, 1 - vals)  # folded statistic
        order = np.argsort(w)
        w_s, p_s = w[order], probs[order]
        # CDF of the folded statistic
        uniq = sorted(set(w_s.round(12)))
        cdf = {u: float(p_s[w_s.round(12) <= u].sum()) for u in uniq}
        row = {
            "effective_n": n_eff,
            "single_rule_E[worst_score]": float((w * probs).sum()),
            "single_rule_P(worst>=0.75)": float(probs[w >= 0.75 - 1e-9].sum()),
            "single_rule_P(worst>=0.833)": float(probs[w >= 0.8333 - 1e-9].sum()),
            "single_rule_P(worst>=0.917)": float(probs[w >= 0.9166 - 1e-9].sum()),
            "single_rule_P(worst=1.0)": float(probs[w >= 1.0 - 1e-9].sum()),
            "max_of_k_independent": {},
        }
        for k in (1, 2, 3, 6, 7, 12, 30, 100):
            e = sum(u * ((cdf[u] ** k) - (cdf[prev] ** k if i else 0.0))
                    for i, (u, prev) in enumerate(zip(uniq, [uniq[0]] + uniq[:-1])))
            row["max_of_k_independent"][str(k)] = {
                "E[max worst_score]": float(e),
                "P(max>=0.75)": float(1 - cdf[max(u for u in uniq if u < 0.75 - 1e-9)] ** k)
                if any(u < 0.75 - 1e-9 for u in uniq) else 1.0,
            }
        out[label] = row
    return out


def randomisation(rows, preds, nperm=NPERM):
    """Permute `expected_index` WITHIN each twin pair; recompute the audit's reported statistic."""
    y = np.array([r["expected_index"] for r in rows])
    fams = defaultdict(list)
    for i, r in enumerate(rows):
        fams[r["family_id"]].append(i)
    pair_idx = [np.array(v) for v in fams.values()]
    obs, obs_rule = worst_score_from(preds, y)
    names = list(preds)
    P = np.stack([preds[n] for n in names])  # (R, n)
    null = np.empty(nperm)
    for t in range(nperm):
        yp = y.copy()
        flip = RNG.random(len(pair_idx)) < 0.5
        for j, idx in enumerate(pair_idx):
            if flip[j]:
                yp[idx] = 1 - yp[idx]
        s = (P == yp).mean(axis=1)
        w = np.maximum(s, 1 - s)
        null[t] = w[np.argmax(np.abs(s - 0.5))]
    return {
        "observed_worst_score": obs,
        "observed_worst_rule": obs_rule,
        "null_mean": float(null.mean()),
        "null_median": float(np.median(null)),
        "null_q90": float(np.quantile(null, 0.90)),
        "null_q95": float(np.quantile(null, 0.95)),
        "null_max": float(null.max()),
        "p_value_ge_observed": float((null >= obs - 1e-9).mean()),
        "P(null>=0.75)": float((null >= 0.75 - 1e-9).mean()),
        "selection_bias_floor_E[worst|no leakage]": float(null.mean()),
        "excess_over_null_mean": float(obs - null.mean()),
        "n_permutations": nperm,
    }


def split_sample(rows, preds):
    """Select the rule on half the families; evaluate (with V5's negation fold) on the other half.

    All C(12,6)/2 = 462 balanced splits, exhaustively; no sampling error."""
    y = np.array([r["expected_index"] for r in rows])
    fams = defaultdict(list)
    for i, r in enumerate(rows):
        fams[r["family_id"]].append(i)
    keys = sorted(fams)
    h = len(keys) // 2
    names = list(preds)
    P = np.stack([preds[n] for n in names])
    evals, sel_scores = [], []
    seen = set()
    for combo in itertools.combinations(range(len(keys)), h):
        comp = tuple(sorted(set(range(len(keys))) - set(combo)))
        if comp in seen:
            continue
        seen.add(combo)
        a = np.concatenate([fams[keys[i]] for i in combo])
        b = np.concatenate([fams[keys[i]] for i in comp])
        sa = (P[:, a] == y[a]).mean(axis=1)
        j = int(np.argmax(np.abs(sa - 0.5)))
        sign = 1 if sa[j] >= 0.5 else -1
        sb = float((P[j, b] == y[b]).mean())
        evals.append(sb if sign == 1 else 1 - sb)
        sel_scores.append(float(max(sa[j], 1 - sa[j])))
    evals = np.array(evals)
    sel_scores = np.array(sel_scores)
    return {
        "n_splits": int(len(evals)),
        "mean_selection_half_worst_score": float(sel_scores.mean()),
        "mean_heldout_accuracy_of_selected_rule": float(evals.mean()),
        "median_heldout": float(np.median(evals)),
        "q05_heldout": float(np.quantile(evals, 0.05)),
        "q95_heldout": float(np.quantile(evals, 0.95)),
        "optimism_selection_minus_heldout": float(sel_scores.mean() - evals.mean()),
    }


def main() -> int:
    rows_all = [json.loads(l) for l in BANK.read_text().splitlines() if l.strip()]
    cells = defaultdict(list)
    for r in rows_all:
        cells[(r["mechanism"], r["level"])].append(r)

    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC of selection bias in `fitness_v5.shortcut_audit`. Not a re-scoring "
            "of V7. No recorded sentinel may be reinterpreted from these numbers."
        ),
        "exact_nulls": exact_nulls(),
        "cells": {},
    }
    for (mech, lvl), rows in sorted(cells.items()):
        preds = rule_preds(rows)
        out["cells"][f"{mech}|L{lvl}"] = {
            "randomisation": randomisation(rows, preds),
            "split_sample": split_sample(rows, preds),
        }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    n = out["exact_nulls"]
    print("EXACT NULLS (one rule):")
    for k, v in n.items():
        print(f"  {k:22s} n_eff={v['effective_n']:2d} "
              f"E[worst]={v['single_rule_E[worst_score]']:.4f} "
              f"P(>=.75)={v['single_rule_P(worst>=0.75)']:.4f} "
              f"P(=1.0)={v['single_rule_P(worst=1.0)']:.2e}")
        for k2, v2 in v["max_of_k_independent"].items():
            print(f"        k={k2:>3s} E[max]={v2['E[max worst_score]']:.4f} "
                  f"P(max>=.75)={v2['P(max>=0.75)']:.4f}")
    print()
    print(f"{'cell':34s} {'obs':>6s} {'nullE':>6s} {'p':>7s} {'split_sel':>9s} {'split_held':>10s}")
    for k, c in out["cells"].items():
        r, s = c["randomisation"], c["split_sample"]
        print(f"{k:34s} {r['observed_worst_score']:6.3f} {r['null_mean']:6.3f} "
              f"{r['p_value_ge_observed']:7.4f} {s['mean_selection_half_worst_score']:9.3f} "
              f"{s['mean_heldout_accuracy_of_selected_rule']:10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
