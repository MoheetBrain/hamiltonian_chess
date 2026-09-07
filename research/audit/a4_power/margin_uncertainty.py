"""A4 audit step 2: uncertainty, CIs, posterior probabilities, power, required n, clustering.

READ-ONLY. No model calls. Consumes research/audit/a4_power/paired_items.json.
Writes research/audit/a4_power/margin_uncertainty.json and prints a full report.

NOTHING HERE PROPOSES A DIFFERENT THRESHOLD. SHORTCUT_MARGIN = 0.10 is treated as frozen.
Every quantity is a property of the DECISION PROCEDURE at the preregistered threshold.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
IN = HERE / "paired_items.json"
OUT = HERE / "margin_uncertainty.json"

RNG = np.random.default_rng(20260907)
B = 200_000  # bootstrap / posterior draws
MARGIN = 0.10  # PREREGISTERED, FROZEN. Never varied as a recommendation.


# ------------------------------------------------------------------ interval helpers
def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    a = 1 - conf
    lo = 0.0 if k == 0 else stats.beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else stats.beta.ppf(1 - a / 2, k + 1, n - k)
    return (float(lo), float(hi))


def newcombe_paired(a: int, b: int, c: int, d: int, conf: float = 0.95) -> tuple[float, float]:
    """Newcombe (1998) method 10: score interval for a paired proportion difference."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n, conf)
    l2, u2 = wilson(a + c, n, conf)
    z = stats.norm.ppf(1 - (1 - conf) / 2)
    # phi: correlation of the two paired indicators
    num = a * d - b * c
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if den == 0:
        phi = 0.0
    else:
        phi = num / den
        if num == 0:
            phi = 0.0
    lo = (p1 - p2) - math.sqrt(
        max((p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2, 0.0)
    )
    hi = (p1 - p2) + math.sqrt(
        max((u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2, 0.0)
    )
    return (lo, hi, phi)


def mcnemar_exact(b: int, c: int) -> float:
    m = b + c
    if m == 0:
        return 1.0
    k = max(b, c)
    p = 2 * stats.binom.sf(k - 1, m, 0.5)
    return float(min(1.0, p))


# ------------------------------------------------------------------ core cell analysis
def analyse_cell(cell: dict) -> dict:
    items = cell["items"]
    n = len(items)
    t = cell["table"]
    a, b, c, d = t["both"], t["solver_only"], t["shortcut_only"], t["neither"]
    ks, kh = a + b, a + c
    margin = (b - c) / n

    # --- SEs on the DIFFERENCE, three ways
    se_paired = math.sqrt(max((b + c) - (b - c) ** 2 / n, 0.0)) / n
    ps, ph = ks / n, kh / n
    se_indep = math.sqrt(ps * (1 - ps) / n + ph * (1 - ph) / n)
    se_single_arm = math.sqrt(ps * (1 - ps) / n)  # the PREREG's formula (WRONG for a contrast)

    lo_nc, hi_nc, phi = newcombe_paired(a, b, c, d)

    # --- item bootstrap (ignores clustering)
    idx_solver = np.array([i["solver_correct"] for i in items], dtype=float)
    idx_short = np.array([i["shortcut_correct"] for i in items], dtype=float)
    diff = idx_solver - idx_short
    draws = RNG.integers(0, n, size=(B, n))
    boot_item = diff[draws].mean(axis=1)

    # --- CLUSTER bootstrap: resample FAMILIES (the real independent unit)
    fam: dict[str, list[int]] = defaultdict(list)
    for j, i in enumerate(items):
        fam[i["family_id"]].append(j)
    fam_idx = [np.array(v) for v in fam.values()]
    nf = len(fam_idx)
    fam_sums = np.array([diff[v].sum() for v in fam_idx])
    fam_ns = np.array([len(v) for v in fam_idx])
    fdraws = RNG.integers(0, nf, size=(B, nf))
    boot_cluster = fam_sums[fdraws].sum(axis=1) / fam_ns[fdraws].sum(axis=1)

    # --- cluster-robust analytic SE (family is the unit; equal cluster sizes here)
    fam_mean_diff = fam_sums / fam_ns
    se_cluster = float(fam_mean_diff.std(ddof=1) / math.sqrt(nf))
    deff = (se_cluster / se_paired) ** 2 if se_paired > 0 else float("nan")
    n_eff = n / deff if deff and deff == deff and deff > 0 else float("nan")

    # --- ICC of the difference variable within family (ANOVA estimator, size-2 clusters)
    grand = diff.mean()
    ms_between = sum(len(v) * (diff[v].mean() - grand) ** 2 for v in fam_idx) / (nf - 1)
    ms_within = sum(((diff[v] - diff[v].mean()) ** 2).sum() for v in fam_idx) / (n - nf)
    k = n / nf
    icc = (ms_between - ms_within) / (ms_between + (k - 1) * ms_within) if ms_between + (
        k - 1
    ) * ms_within != 0 else float("nan")

    # --- Bayesian posterior on the margin, Dirichlet on (a,b,c,d)
    post = {}
    for name, alpha in (("uniform_Dir1", 1.0), ("jeffreys_Dir0.5", 0.5), ("haldane_Dir0.001", 1e-3)):
        dr = RNG.dirichlet([a + alpha, b + alpha, c + alpha, d + alpha], size=B)
        delta = dr[:, 1] - dr[:, 2]
        post[name] = {
            "P_margin_gt_0.10": float((delta > MARGIN).mean()),
            "P_margin_gt_0": float((delta > 0).mean()),
            "posterior_mean": float(delta.mean()),
            "ci95": [float(np.quantile(delta, 0.025)), float(np.quantile(delta, 0.975))],
        }
    # --- cluster-aware Bayesian bootstrap (Dirichlet weights over FAMILIES)
    w = RNG.dirichlet(np.ones(nf), size=B)
    bb = (w * fam_mean_diff).sum(axis=1)
    post["bayesian_bootstrap_over_families"] = {
        "P_margin_gt_0.10": float((bb > MARGIN).mean()),
        "P_margin_gt_0": float((bb > 0).mean()),
        "posterior_mean": float(bb.mean()),
        "ci95": [float(np.quantile(bb, 0.025)), float(np.quantile(bb, 0.975))],
    }

    return {
        "mechanism": cell["mechanism"],
        "level": cell["level"],
        "n_items": n,
        "n_families": nf,
        "solver_accuracy": ks / n,
        "shortcut_accuracy": kh / n,
        "best_shortcut_feature": cell["best_shortcut_feature"],
        "best_shortcut_inverted": cell["best_shortcut_inverted"],
        "table_abcd": [a, b, c, d],
        "discordant_pairs": b + c,
        "margin": margin,
        "solver_ci95_wilson": list(wilson(ks, n)),
        "solver_ci95_clopper_pearson": list(clopper_pearson(ks, n)),
        "shortcut_ci95_wilson": list(wilson(kh, n)),
        "shortcut_ci95_clopper_pearson": list(clopper_pearson(kh, n)),
        "se_difference_paired_mcnemar": se_paired,
        "se_difference_if_independent": se_indep,
        "se_single_arm_PREREG_FORMULA": se_single_arm,
        "phi_correlation_solver_vs_shortcut": phi,
        "ci95_newcombe_paired_score": [lo_nc, hi_nc],
        "ci95_bootstrap_item": [
            float(np.quantile(boot_item, 0.025)),
            float(np.quantile(boot_item, 0.975)),
        ],
        "ci95_bootstrap_cluster_family": [
            float(np.quantile(boot_cluster, 0.025)),
            float(np.quantile(boot_cluster, 0.975)),
        ],
        "se_cluster_robust": se_cluster,
        "design_effect": deff,
        "effective_n": n_eff,
        "icc_of_difference_within_family": float(icc),
        "shortcut_constant_within_every_family": bool(
            all(len({items[j]["shortcut_correct"] for j in v}) == 1 for v in fam_idx)
        ),
        "solver_constant_within_every_family": bool(
            all(len({items[j]["solver_correct"] for j in v}) == 1 for v in fam_idx)
        ),
        "family_level_differences": [int(x) for x in fam_sums],
        "mcnemar_exact_p_two_sided_H0_margin_0": mcnemar_exact(b, c),
        "posterior": post,
    }


def main() -> None:
    cells = json.loads(IN.read_text())
    out = {
        "_frozen_threshold": MARGIN,
        "_note": (
            "SHORTCUT_MARGIN = 0.10 is preregistered and frozen. Nothing in this file is a "
            "proposal to change it. Every number characterises the behaviour of the DECISION "
            "PROCEDURE at that fixed threshold."
        ),
        "cells": {k: analyse_cell(v) for k, v in sorted(cells.items())},
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))

    print("=" * 108)
    print("PAIRED UNCERTAINTY ON THE MARGIN (solver - best shortcut), same items, n = 24 per cell")
    print("=" * 108)
    hdr = (
        f"{'cell':<30}{'a/b/c/d':>14}{'marg':>8}{'SE_pair':>9}{'SE_indep':>9}"
        f"{'SE_1arm':>9}{'SE_clust':>9}{'deff':>7}{'n_eff':>7}{'McN p':>8}"
    )
    print(hdr)
    for k, r in out["cells"].items():
        a, b, c, d = r["table_abcd"]
        print(
            f"{k:<30}{f'{a}/{b}/{c}/{d}':>14}{r['margin']:>8.4f}"
            f"{r['se_difference_paired_mcnemar']:>9.4f}{r['se_difference_if_independent']:>9.4f}"
            f"{r['se_single_arm_PREREG_FORMULA']:>9.4f}{r['se_cluster_robust']:>9.4f}"
            f"{r['design_effect']:>7.2f}{r['effective_n']:>7.1f}"
            f"{r['mcnemar_exact_p_two_sided_H0_margin_0']:>8.4f}"
        )

    print()
    print("=" * 108)
    print("transitive_dependency L3 — THE DECISION CELL")
    print("=" * 108)
    r = out["cells"]["transitive_dependency|L3"]
    print(f"  solver accuracy       {r['solver_accuracy']:.4f}  "
          f"Wilson 95% [{r['solver_ci95_wilson'][0]:.4f}, {r['solver_ci95_wilson'][1]:.4f}]  "
          f"Clopper-Pearson [{r['solver_ci95_clopper_pearson'][0]:.4f}, "
          f"{r['solver_ci95_clopper_pearson'][1]:.4f}]")
    print(f"  shortcut accuracy     {r['shortcut_accuracy']:.4f}  "
          f"Wilson 95% [{r['shortcut_ci95_wilson'][0]:.4f}, {r['shortcut_ci95_wilson'][1]:.4f}]  "
          f"Clopper-Pearson [{r['shortcut_ci95_clopper_pearson'][0]:.4f}, "
          f"{r['shortcut_ci95_clopper_pearson'][1]:.4f}]")
    print(f"  best shortcut feature {r['best_shortcut_feature']}  "
          f"INVERTED={r['best_shortcut_inverted']}")
    print(f"  2x2 (a,b,c,d)         {r['table_abcd']}   discordant pairs = {r['discordant_pairs']}")
    print(f"  margin                {r['margin']:.6f}   (= {r['table_abcd'][1]}-{r['table_abcd'][2]} "
          f"of 24 = 2/24)")
    print(f"  phi(solver,shortcut)  {r['phi_correlation_solver_vs_shortcut']:.4f}")
    print()
    print("  CONFIDENCE INTERVALS FOR THE MARGIN")
    print(f"    Newcombe paired score 95%  [{r['ci95_newcombe_paired_score'][0]:+.4f}, "
          f"{r['ci95_newcombe_paired_score'][1]:+.4f}]")
    print(f"    bootstrap, item-level 95%  [{r['ci95_bootstrap_item'][0]:+.4f}, "
          f"{r['ci95_bootstrap_item'][1]:+.4f}]")
    print(f"    bootstrap, CLUSTER    95%  [{r['ci95_bootstrap_cluster_family'][0]:+.4f}, "
          f"{r['ci95_bootstrap_cluster_family'][1]:+.4f}]")
    print()
    print("  CLUSTERING")
    print(f"    families {r['n_families']}, items {r['n_items']} (2 per family: "
          f"ORIGINAL + COUNTERFACTUAL)")
    print(f"    shortcut outcome constant within EVERY family: "
          f"{r['shortcut_constant_within_every_family']}")
    print(f"    ICC of the difference within family: "
          f"{r['icc_of_difference_within_family']:.4f}")
    print(f"    design effect {r['design_effect']:.3f}  ->  effective n = "
          f"{r['effective_n']:.1f} (nominal 24)")
    print(f"    family-level (solver-shortcut) counts: {r['family_level_differences']}")
    print()
    print("  POSTERIOR PROBABILITIES (the two the audit asked for)")
    for name, p in r["posterior"].items():
        print(f"    {name:<34} P(delta>0.10)={p['P_margin_gt_0.10']:.4f}   "
              f"P(delta>0)={p['P_margin_gt_0']:.4f}   "
              f"95% CrI [{p['ci95'][0]:+.4f}, {p['ci95'][1]:+.4f}]")
    print()
    print(f"  McNemar exact two-sided p for H0: margin = 0  ->  "
          f"{r['mcnemar_exact_p_two_sided_H0_margin_0']:.4f}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
