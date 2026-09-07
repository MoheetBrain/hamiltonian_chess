"""A4 audit step 3: power of the frozen gate, required n, estimator resolution, selection bias.

READ-ONLY. No model calls.

THE THRESHOLD IS FROZEN. This file never proposes an alternative value for SHORTCUT_MARGIN.
It characterises (i) the resolution of the margin estimator at n = 24, (ii) the operating
characteristic of the frozen gate as a function of the TRUE margin, (iii) the n required for the
gate to do its stated job, and (iv) the upward bias in `best_shortcut_accuracy` induced by taking
a maximum over 7 rules and their negations on the same 24 items.

Writes research/audit/a4_power/power_and_n.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
OUT = HERE / "power_and_n.json"
RNG = np.random.default_rng(20260907)

MARGIN = 0.10          # PREREGISTERED, FROZEN
GATE_EPSILON = 1e-9    # arena/experiments/fitness_v7.py:184
N_CELL = 24
N_FAM = 12
OBS_MARGIN = 2 / 24
OBS_PI_D = 4 / 24      # observed discordance at transitive_dependency L3
SE_ITEM = 0.0815786    # McNemar paired SE, from margin_uncertainty.py
SE_CLUSTER = 0.1035964  # cluster-robust SE (family is the unit)
DEFF = (SE_CLUSTER / SE_ITEM) ** 2

Z95, Z975, Z80 = stats.norm.ppf(0.95), stats.norm.ppf(0.975), stats.norm.ppf(0.80)


def resolution() -> dict:
    """The margin is (k_solver - k_shortcut)/24: a multiple of 1/24. What can the gate see?"""
    step = 1 / N_CELL
    achievable = sorted({round(i * step, 12) for i in range(-N_CELL, N_CELL + 1)})
    passing = [m for m in achievable if m >= MARGIN - GATE_EPSILON]
    smallest_pass = min(passing)
    largest_fail = max(m for m in achievable if m < MARGIN - GATE_EPSILON)
    return {
        "quantum_of_the_estimator": step,
        "declared_threshold": MARGIN,
        "smallest_ACHIEVABLE_margin_that_passes": smallest_pass,
        "largest_achievable_margin_that_fails": largest_fail,
        "effective_operational_threshold_at_n24": smallest_pass,
        "dead_zone": [largest_fail, smallest_pass],
        "dead_zone_width": smallest_pass - largest_fail,
        "observed_margin_transitive_L3": OBS_MARGIN,
        "observed_is_the_largest_failing_value": abs(OBS_MARGIN - largest_fail) < 1e-12,
        "distance_to_declared_threshold": MARGIN - OBS_MARGIN,
        "distance_in_quanta": (MARGIN - OBS_MARGIN) / step,
        "distance_to_effective_threshold": smallest_pass - OBS_MARGIN,
    }


def gate_operating_characteristic() -> dict:
    """P(observed margin passes the frozen gate) as a function of the TRUE margin.

    Paired model: per item, P(solver only correct) = pb, P(shortcut only) = pc,
    pb + pc = pi_d, pb - pc = delta. Items are simulated in clusters of 2 with the observed
    within-family correlation to respect the ORIGINAL/COUNTERFACTUAL pairing.
    """
    reps = 200_000
    grid = [0.0, 0.05, 1 / 12, 0.0833333333, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]
    out = {}
    for pi_d in (OBS_PI_D, 0.25, 0.3333333):
        rows = {}
        for delta in grid:
            pb = (pi_d + delta) / 2
            pc = (pi_d - delta) / 2
            if pc < -1e-12 or pb > 1 + 1e-12:
                rows[f"{delta:.4f}"] = None  # incompatible with this discordance rate
                continue
            pc = max(pc, 0.0)
            p = [1 - pb - pc, pb, pc]  # 0 = concordant, +1 = solver only, -1 = shortcut only
            # independent-item version
            draw = RNG.choice([0, 1, -1], size=(reps, N_CELL), p=p)
            marg_i = draw.sum(axis=1) / N_CELL
            # clustered version: draw once per family, duplicate to both items
            drawf = RNG.choice([0, 1, -1], size=(reps, N_FAM), p=p)
            marg_c = (drawf * 2).sum(axis=1) / N_CELL
            rows[f"{delta:.4f}"] = {
                "true_margin": delta,
                "P_pass_gate_items_independent": float(
                    (marg_i >= MARGIN - GATE_EPSILON).mean()
                ),
                "P_pass_gate_fully_clustered": float(
                    (marg_c >= MARGIN - GATE_EPSILON).mean()
                ),
            }
        out[f"discordance_{pi_d:.4f}"] = rows
    return out


def power_to_separate() -> dict:
    """Q7: was V7 powered to distinguish an observed .0833 from the .10 gate?"""
    d = MARGIN - OBS_MARGIN  # 0.016667
    res = {"separation_required": d}
    for name, se in (("item_level_mcnemar_SE", SE_ITEM), ("cluster_robust_SE", SE_CLUSTER)):
        res[name] = {
            "SE": se,
            "separation_in_SE_units": d / se,
            "power_one_sided_alpha_0.05": float(stats.norm.cdf(d / se - Z95)),
            "power_two_sided_alpha_0.05": float(stats.norm.cdf(d / se - Z975)),
        }
    res["estimator_resolution_argument"] = {
        "quantum": 1 / N_CELL,
        "separation_in_quanta": d * N_CELL,
        "verdict": (
            "The separation to be resolved (0.016667) is 0.40 of ONE quantum of the estimator "
            "(1/24 = 0.041667). No outcome of the n = 24 experiment can lie strictly between "
            "0.0833 and 0.10. The distinction is not merely underpowered, it is unrepresentable."
        ),
    }
    return res


def required_n() -> dict:
    """Q8: n required to place a true margin on the correct side of the frozen 0.10 gate.

    Framing A (classic): McNemar test of H0 delta = 0, two-sided alpha = 0.05, power 0.80.
    Framing B (what the gate actually does): one-sided test that delta >= 0.10, power 0.80,
              alpha = 0.05 -- i.e. correctly PASS a mechanism whose true margin is delta.
    Framing C (estimation): n for a 95% CI half-width small enough to separate delta from 0.10.
    All inflated by the measured design effect for the ORIGINAL/COUNTERFACTUAL pairing.
    """
    out = {}
    for delta in (0.05, 0.08, 0.10, 0.15):
        entry: dict = {"true_margin": delta}
        for pi_d_name, pi_d in (
            ("discordance_0.1667_observed", OBS_PI_D),
            ("discordance_0.3333", 1 / 3),
        ):
            pd = max(pi_d, abs(delta) + 1e-9)
            var_unit = pd - delta**2
            # A: detect delta != 0
            nA = ((Z975 * math.sqrt(pd) + Z80 * math.sqrt(var_unit)) ** 2) / delta**2
            # B: declare delta >= 0.10 (one-sided) when true margin is delta
            gap = delta - MARGIN
            nB = ((Z95 + Z80) ** 2) * var_unit / gap**2 if abs(gap) > 1e-12 else float("inf")
            # C: 95% CI half-width < |delta - 0.10|
            nC = (Z975**2) * var_unit / gap**2 if abs(gap) > 1e-12 else float("inf")
            entry[pi_d_name] = {
                "assumed_discordance": pd,
                "A_items_to_detect_margin_gt_0": math.ceil(nA),
                "A_items_with_design_effect": math.ceil(nA * DEFF),
                "B_items_to_pass_gate_with_80pct_power": (
                    math.ceil(nB) if math.isfinite(nB) else None
                ),
                "B_items_with_design_effect": (
                    math.ceil(nB * DEFF) if math.isfinite(nB) else None
                ),
                "C_items_for_CI_halfwidth_below_gap": (
                    math.ceil(nC) if math.isfinite(nC) else None
                ),
                "C_items_with_design_effect": (
                    math.ceil(nC * DEFF) if math.isfinite(nC) else None
                ),
                "note": (
                    "delta EQUALS the gate: no finite n separates a point from itself; "
                    "power at the boundary is alpha by construction"
                )
                if abs(gap) <= 1e-12
                else None,
            }
        out[f"margin_{delta:.2f}"] = entry
    out["_design_effect_applied"] = DEFF
    out["_actual_n_run"] = N_CELL
    return out


def shortcut_selection_bias() -> dict:
    """`best_shortcut_accuracy` = max over 7 rules AND their negations, on the SAME 24 items.

    fitness_v5.py:822-823:  worst = max(scores, key=|score-0.5|);  worst_score = max(s, 1-s).
    That is a maximum of 14 correlated statistics selected on the evaluation data. Under a null
    in which no rule carries signal, its expectation exceeds 0.5. Quantify the upward bias, which
    biases the MARGIN DOWNWARD -- against qualification.
    """
    reps = 400_000
    res = {}
    # In every V7 cell answer_share_index_0 == 0.5 exactly, so always_first/always_second score
    # exactly 0.500 and contribute nothing. Five rules are genuinely data-dependent.
    for k_rules in (5, 7):
        s = RNG.binomial(N_CELL, 0.5, size=(reps, k_rules)) / N_CELL
        best = np.max(np.maximum(s, 1 - s), axis=1)
        res[f"{k_rules}_informative_rules"] = {
            "E_best_shortcut_under_null": float(best.mean()),
            "upward_bias_vs_0.5": float(best.mean() - 0.5),
            "P_best_shortcut_ge_0.6667_under_null": float((best >= 2 / 3 - 1e-12).mean()),
            "P_best_shortcut_ge_0.75_under_null": float((best >= 0.75 - 1e-12).mean()),
            "quantiles": {
                q: float(np.quantile(best, q)) for q in (0.5, 0.75, 0.90, 0.95, 0.99)
            },
        }
    # Clustered null: rules resolve per FAMILY (as observed -- shortcut is constant in family)
    s = RNG.binomial(N_FAM, 0.5, size=(reps, 5)) / N_FAM
    best = np.max(np.maximum(s, 1 - s), axis=1)
    res["5_rules_clustered_by_family"] = {
        "E_best_shortcut_under_null": float(best.mean()),
        "upward_bias_vs_0.5": float(best.mean() - 0.5),
        "P_best_shortcut_ge_0.6667_under_null": float((best >= 2 / 3 - 1e-12).mean()),
    }
    res["observed_transitive_L3"] = {
        "best_shortcut_accuracy": 2 / 3,
        "selected_rule": "first_mentioned_in_state",
        "raw_rule_score": 1 / 3,
        "polarity": "INVERTED (0.3333 -> 0.6667)",
        "reading": (
            "The rule the solver is required to beat by 0.10 scores 0.3333 -- it is "
            "ANTI-correlated with the answer. The 0.6667 figure is the accuracy of a "
            "post-hoc negation, selected as the max of |s-0.5| over 7 rules on these same "
            "24 items. It is not a shortcut any adversary proposed in advance."
        ),
    }
    return res


def main() -> None:
    out = {
        "_frozen_threshold": MARGIN,
        "_note": (
            "SHORTCUT_MARGIN = 0.10 is preregistered and frozen and is NOT varied here. All "
            "quantities describe the behaviour of the decision procedure AT that threshold."
        ),
        "estimator_resolution": resolution(),
        "power_to_separate_0.0833_from_0.10": power_to_separate(),
        "required_n": required_n(),
        "gate_operating_characteristic": gate_operating_characteristic(),
        "shortcut_selection_bias": shortcut_selection_bias(),
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))

    r = out["estimator_resolution"]
    print("=" * 100)
    print("1. ESTIMATOR RESOLUTION — what the gate can actually see at n = 24")
    print("=" * 100)
    print(f"  margin = (k_solver - k_shortcut)/24  ->  quantum {r['quantum_of_the_estimator']:.6f}")
    print(f"  declared threshold                    {r['declared_threshold']}")
    print(f"  largest ACHIEVABLE margin that FAILS  {r['largest_achievable_margin_that_fails']:.6f}"
          f"   <- transitive_dependency L3 landed exactly here"
          f" ({r['observed_is_the_largest_failing_value']})")
    print(f"  smallest ACHIEVABLE margin that PASSES {r['smallest_ACHIEVABLE_margin_that_passes']:.6f}")
    print(f"  => EFFECTIVE operational threshold at n=24 is "
          f"{r['effective_operational_threshold_at_n24']:.4f}, not {MARGIN}")
    print(f"  dead zone {r['dead_zone']} width {r['dead_zone_width']:.6f} — no result can land here")
    print(f"  the shortfall (0.0167) is {r['distance_in_quanta']:.2f} of ONE quantum")

    p = out["power_to_separate_0.0833_from_0.10"]
    print()
    print("=" * 100)
    print("2. Q7 — POWER TO DISTINGUISH 0.0833 FROM 0.10")
    print("=" * 100)
    for k in ("item_level_mcnemar_SE", "cluster_robust_SE"):
        v = p[k]
        print(f"  {k:<26} SE={v['SE']:.4f}  separation={v['separation_in_SE_units']:.3f} SE  "
              f"power(1-sided a=.05)={v['power_one_sided_alpha_0.05']:.4f}  "
              f"(2-sided)={v['power_two_sided_alpha_0.05']:.4f}")
    print(f"  {p['estimator_resolution_argument']['verdict']}")

    print()
    print("=" * 100)
    print("3. Q8 — REQUIRED n (alpha = 0.05, power = 0.80); design effect "
          f"{out['required_n']['_design_effect_applied']:.2f} applied")
    print("=" * 100)
    print(f"{'true margin':<13}{'A: detect >0':>16}{'A x deff':>11}"
          f"{'B: pass .10 gate':>19}{'B x deff':>11}{'C: CI sep':>12}{'C x deff':>11}")
    for key in ("margin_0.05", "margin_0.08", "margin_0.10", "margin_0.15"):
        e = out["required_n"][key]
        v = e["discordance_0.1667_observed"]
        b = v["B_items_to_pass_gate_with_80pct_power"]
        bd = v["B_items_with_design_effect"]
        c_ = v["C_items_for_CI_halfwidth_below_gap"]
        cd = v["C_items_with_design_effect"]
        f = lambda x: ("n/a" if x is None else str(x))  # noqa: E731
        print(f"{e['true_margin']:<13.2f}{v['A_items_to_detect_margin_gt_0']:>16}"
              f"{v['A_items_with_design_effect']:>11}{f(b):>19}{f(bd):>11}"
              f"{f(c_):>12}{f(cd):>11}")
    print("  (B/C are 'n/a' at 0.10 because no finite n separates the boundary from itself)")

    print()
    print("=" * 100)
    print("4. GATE OPERATING CHARACTERISTIC — P(pass the frozen gate) vs TRUE margin, n = 24")
    print("=" * 100)
    goc = out["gate_operating_characteristic"][f"discordance_{OBS_PI_D:.4f}"]
    print(f"{'true margin':<13}{'P(pass), items iid':>22}{'P(pass), fully clustered':>27}")
    for k2, v in goc.items():
        if v is None:
            continue
        print(f"{v['true_margin']:<13.4f}{v['P_pass_gate_items_independent']:>22.4f}"
              f"{v['P_pass_gate_fully_clustered']:>27.4f}")

    print()
    print("=" * 100)
    print("5. SELECTION BIAS IN `best_shortcut_accuracy` (max over rules AND negations)")
    print("=" * 100)
    sb = out["shortcut_selection_bias"]
    for k2 in ("5_informative_rules", "7_informative_rules", "5_rules_clustered_by_family"):
        v = sb[k2]
        print(f"  {k2:<30} E[best] = {v['E_best_shortcut_under_null']:.4f}  "
              f"(bias +{v['upward_bias_vs_0.5']:.4f})  "
              f"P(>=0.6667 | null) = {v['P_best_shortcut_ge_0.6667_under_null']:.4f}")
    print(f"  observed at transitive L3: best={2/3:.4f} from a rule scoring "
          f"{1/3:.4f}, i.e. INVERTED")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
