"""AUDITOR 3 (A3) DIAGNOSTIC -- what the ANCESTOR's own decision procedure would report.

`fitness_v4.py:1396-1402` states the audit is "Adapted from HML_V3
`src/hml_v3/micromath/shortcut_v2.py`".  That ancestor decides a cell by a **Bonferroni-corrected
Clopper-Pearson lower bound** against chance (`shortcut_v2.py:24-28, 108-131`), and its docstring
records WHY: "A flat tolerance made the verdict a function of sample size ... the first version
called that a leak on one split and clean on another from the same construction."

Arena's port kept the rule list idea, added a negation fold (`worst_score = max(s, 1-s)`, which
DOUBLES the number of tests actually searched), and replaced the corrected interval with the flat
constant `shortcut_rule_max = 0.75`.  This script reports, side by side:

  * the flat-threshold verdict actually used (V5/V7)
  * the ancestor-style corrected-interval verdict
  * the exact two-sided binomial p at n = 24 items and at n_eff = 12 twin pairs

This is a DIAGNOSTIC OF THE DECISION PROCEDURE.  It is NOT a re-scoring of V7 and may not be used
to promote, re-score or reinterpret any recorded sentinel.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from scipy.stats import beta

HERE = Path(__file__).resolve().parent
INV = HERE / "predictor_inventory.json"
SEL = HERE / "selection_bias.json"
OUT = HERE / "ancestor_procedure.json"

FLAT_THRESHOLD = 0.75          # fitness_v5.py:225
FAMILY_CONFIDENCE = 0.90       # shortcut_v2.py:25
NOMINAL_RULES = 7              # fitness_v5.py:800-819
FOLDED_TESTS = 14              # each rule is also searched in its negated polarity


def clopper_pearson_lower(k: int, n: int, conf: float) -> float:
    if k == 0:
        return 0.0
    alpha = 1.0 - conf
    return float(beta.ppf(alpha / 2, k, n - k + 1))


def two_sided_binom_p(k: int, n: int) -> float:
    """Exact two-sided p for H0: p = 1/2 (equal-tail, symmetric)."""
    d = abs(k - n / 2)
    lo, hi = math.floor(n / 2 - d), math.ceil(n / 2 + d)
    return min(
        1.0,
        sum(math.comb(n, i) for i in range(0, lo + 1)) / 2**n
        + sum(math.comb(n, i) for i in range(hi, n + 1)) / 2**n,
    )


def main() -> int:
    inv = json.loads(INV.read_text())
    sel = json.loads(SEL.read_text())
    rows = {}
    for mech, levels in inv["reproduced_audit"].items():
        for lvl, cell in levels.items():
            key = f"{mech}|L{lvl}"
            n = int(cell["items"])
            w = float(cell["best_shortcut_accuracy"])
            k = int(round(w * n))
            live = len(inv["live_rules_per_cell"][key])
            # effective twin-paired sample: a relabel-sensitive rule is right on both twins of a
            # family or neither, so it has 12 independent trials, not 24.
            n_eff = n // 2
            k_eff = int(round(w * n_eff))
            per_rule_nominal = 1.0 - (1.0 - FAMILY_CONFIDENCE) / FOLDED_TESTS
            per_rule_live = 1.0 - (1.0 - FAMILY_CONFIDENCE) / max(1, 2 * live)
            rows[key] = {
                "items": n,
                "observed_worst_score": w,
                "observed_worst_rule": cell["best_shortcut_feature"],
                "live_rules_in_family": live,
                "flat_threshold_verdict_ACTUALLY_USED": "LEAKS" if w > FLAT_THRESHOLD else "CLEAN",
                "exact_two_sided_p_at_n24": two_sided_binom_p(k, n),
                "exact_two_sided_p_at_neff12_twin_paired": two_sided_binom_p(k_eff, n_eff),
                "bonferroni_p_x14_at_neff12": min(1.0, FOLDED_TESTS * two_sided_binom_p(k_eff, n_eff)),
                "bonferroni_p_x2live_at_neff12": min(
                    1.0, 2 * max(1, live) * two_sided_binom_p(k_eff, n_eff)
                ),
                "ancestor_style_lower_bound_n24_bonf14": clopper_pearson_lower(
                    k, n, per_rule_nominal
                ),
                "ancestor_style_lower_bound_neff12_bonf14": clopper_pearson_lower(
                    k_eff, n_eff, per_rule_nominal
                ),
                "ancestor_style_lower_bound_neff12_bonf_live": clopper_pearson_lower(
                    k_eff, n_eff, per_rule_live
                ),
                "randomisation_p": sel["cells"][key]["randomisation"]["p_value_ge_observed"],
                "randomisation_null_mean": sel["cells"][key]["randomisation"]["null_mean"],
                "split_sample_heldout": sel["cells"][key]["split_sample"][
                    "mean_heldout_accuracy_of_selected_rule"
                ],
            }
            for tag, lb in (
                ("n24_bonf14", rows[key]["ancestor_style_lower_bound_n24_bonf14"]),
                ("neff12_bonf14", rows[key]["ancestor_style_lower_bound_neff12_bonf14"]),
                ("neff12_bonf_live", rows[key]["ancestor_style_lower_bound_neff12_bonf_live"]),
            ):
                rows[key][f"ancestor_verdict_{tag}"] = "LEAKS" if lb > 0.5 else "CLEAN"
    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC of the DECISION PROCEDURE. NOT a re-scoring of V7. No sentinel may be "
            "promoted, re-scored or reinterpreted from these numbers."
        ),
        "flat_threshold": FLAT_THRESHOLD,
        "ancestor_family_confidence": FAMILY_CONFIDENCE,
        "nominal_rules": NOMINAL_RULES,
        "tests_actually_searched_after_negation_fold": FOLDED_TESTS,
        "cells": rows,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    hdr = (f"{'cell':32s} {'obs':>5s} {'flat':>6s} {'p24':>7s} {'p12':>7s} {'bonf12':>7s} "
           f"{'rand_p':>7s} {'LB12':>6s} {'anc':>6s} {'split':>6s}")
    print(hdr)
    for k, r in rows.items():
        print(f"{k:32s} {r['observed_worst_score']:5.3f} "
              f"{r['flat_threshold_verdict_ACTUALLY_USED']:>6s} "
              f"{r['exact_two_sided_p_at_n24']:7.4f} "
              f"{r['exact_two_sided_p_at_neff12_twin_paired']:7.4f} "
              f"{r['bonferroni_p_x2live_at_neff12']:7.4f} "
              f"{r['randomisation_p']:7.4f} "
              f"{r['ancestor_style_lower_bound_neff12_bonf_live']:6.3f} "
              f"{r['ancestor_verdict_neff12_bonf_live']:>6s} "
              f"{r['split_sample_heldout']:6.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
