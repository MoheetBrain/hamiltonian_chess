"""Design-stage power for a POSSIBLE transitive-dependency founder pilot.  numpy only, exact.

Run as ``.venv/bin/python -m research.phase8.transitive.power``.  Zero model calls.

(a) Solver vs a FIXED adversary rate.  A frozen surface adversary is a deterministic function of
    the prompt, so its accuracy on the tournament pool is known exactly before any model call; the
    Solver's is not.  The comparison is therefore a ONE-SAMPLE exact one-sided binomial test of the
    Solver's accuracy against a constant, not a paired test: pairing the Solver against the
    adversary item by item (McNemar) needs the Solver's per-item outcomes, which only the founder
    run itself produces.  Two framings are tabulated:
      (i)  detect a 0.10 margin:   H0 p = q         vs H1 p = q + 0.10
      (ii) certify a 0.10 margin:  H0 p = q + 0.10  vs H1 p = q + 0.10 + delta  (delta 0.05 / 0.10)
    plus the operating characteristic of the V7-style fixed cut "observed margin >= 0.10".

(b) Five-arm founder tournament, four founders vs one baseline on identical items, exact
    two-sided McNemar on the discordant pairs at Delta = 0.10 with discordance pi_d = 0.30
    (p10 = 0.20, p01 = 0.10), Holm over k = 4.  Holm's guaranteed per-hypothesis power is the
    Bonferroni power at alpha/k (its first step), so n is sized at alpha/4 = 0.0125 two-sided; the
    unadjusted alpha = 0.05 figure is given for reference.  Twin clustering: n_items = 2 x families;
    the design effect 1 + ICC is applied for the ICC the V7 audit measured (+0.51) and for 0.
    Cross-checked against ``arena.experiments.precondition_power.mcnemar_exact_power`` (read-only).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ALPHA = 0.05
TARGET_POWER = 0.80
MARGIN = 0.10
K_HOLM = 4
DELTA = 0.10
DISCORDANCE = 0.30
ICC_MEASURED = 0.51  # docs/V7_TOTAL_FORENSIC_AUDIT.md / research/audit/a4: paired-difference ICC


# ------------------------------------------------------------------------- exact binomials


def _log_pmf(n: int, p: float) -> np.ndarray:
    k = np.arange(n + 1)
    lc = math.lgamma(n + 1) - np.array([math.lgamma(i + 1) + math.lgamma(n - i + 1) for i in k])
    if p <= 0.0:
        out = np.full(n + 1, -np.inf)
        out[0] = 0.0
        return out
    if p >= 1.0:
        out = np.full(n + 1, -np.inf)
        out[n] = 0.0
        return out
    return lc + k * math.log(p) + (n - k) * math.log1p(-p)


def pmf(n: int, p: float) -> np.ndarray:
    return np.exp(_log_pmf(n, p))


def upper_tail(n: int, p: float) -> np.ndarray:
    """``P(X >= k)`` for k = 0..n."""

    f = pmf(n, p)
    return np.cumsum(f[::-1])[::-1]


def one_sided_binomial(n: int, p0: float, p1: float, alpha: float) -> dict[str, Any]:
    """Exact one-sided test of H0: p = p0 against H1: p > p0, power at p = p1."""

    tail0 = upper_tail(n, p0)
    ks = np.flatnonzero(tail0 <= alpha)
    if len(ks) == 0:
        return {"n": n, "critical_k": None, "size": 0.0, "power": 0.0}
    k = int(ks[0])
    return {
        "n": n,
        "critical_k": k,
        "critical_rate": k / n,
        "size": float(tail0[k]),
        "power": float(upper_tail(n, p1)[k]),
    }


def required_n_one_sided(p0: float, p1: float, alpha: float, target: float, *, max_n: int = 20000) -> dict[str, Any]:
    """Smallest n with power >= target, and the smallest n after which power never dips below."""

    first = None
    stable = None
    run = 0
    for n in range(5, max_n + 1):
        pw = one_sided_binomial(n, p0, p1, alpha)["power"]
        if pw >= target:
            if first is None:
                first = n
            run += 1
            if run >= 50 and stable is None:
                stable = n - 49
                break
        else:
            run = 0
    return {"n_first": first, "n_stable": stable, "target_power": target}


def fixed_cut_operating_characteristic(n: int, q: float, margin: float, p_true: float) -> float:
    """``P(observed accuracy - q >= margin | p_true)`` for the V7-style fixed margin cut."""

    k = math.ceil((q + margin) * n - 1e-9)
    return float(upper_tail(n, p_true)[min(k, n)]) if k <= n else 0.0


# ------------------------------------------------------------------------- exact McNemar


def mcnemar_reject_mask(d: int, alpha: float) -> np.ndarray:
    """Two-sided exact conditional McNemar: reject iff ``min(k, d-k)`` is in the alpha/2 tail."""

    if d == 0:
        return np.zeros(1, dtype=bool)
    f = pmf(d, 0.5)
    lower = np.cumsum(f)
    ks = np.arange(d + 1)
    m = np.minimum(ks, d - ks)
    # largest c with P(X <= c) <= alpha/2
    ok = np.flatnonzero(lower <= alpha / 2.0 + 1e-15)
    c = int(ok[-1]) if len(ok) else -1
    return m <= c


def mcnemar_power(n: int, p10: float, p01: float, alpha: float) -> float:
    pd = p10 + p01
    q = p10 / pd
    pdist = pmf(n, pd)
    power = 0.0
    for d in range(1, n + 1):
        if pdist[d] == 0.0:
            continue
        mask = mcnemar_reject_mask(d, alpha)
        power += float(pdist[d]) * float(pmf(d, q)[mask].sum())
    return min(1.0, power)


def required_n_mcnemar(p10: float, p01: float, alpha: float, target: float, *, max_n: int = 5000) -> dict[str, Any]:
    first = None
    stable = None
    run = 0
    for n in range(10, max_n + 1):
        pw = mcnemar_power(n, p10, p01, alpha)
        if pw >= target:
            if first is None:
                first = n
            run += 1
            if run >= 20 and stable is None:
                stable = n - 19
                break
        else:
            run = 0
    return {"n_pairs_first": first, "n_pairs_stable": stable, "target_power": target}


def representability(n_items: int) -> dict[str, Any]:
    return {
        "quantum": 1.0 / n_items,
        "0.10_exact": abs(0.10 * n_items - round(0.10 * n_items)) < 1e-9,
        "0.125_exact": abs(0.125 * n_items - round(0.125 * n_items)) < 1e-9,
        "0.15_exact": abs(0.15 * n_items - round(0.15 * n_items)) < 1e-9,
    }


# ------------------------------------------------------------------------------- report


def part_a(adversary_rates: dict[str, float]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for label, q in adversary_rates.items():
        detect = required_n_one_sided(q, q + MARGIN, ALPHA, TARGET_POWER)
        certify_05 = required_n_one_sided(q + MARGIN, q + MARGIN + 0.05, ALPHA, TARGET_POWER)
        certify_10 = required_n_one_sided(q + MARGIN, q + MARGIN + 0.10, ALPHA, TARGET_POWER)
        cut = {
            str(n): {
                "false_pass_at_true_margin_0": fixed_cut_operating_characteristic(n, q, MARGIN, q),
                "pass_at_true_margin_0.10": fixed_cut_operating_characteristic(n, q, MARGIN, q + 0.10),
                "pass_at_true_margin_0.15": fixed_cut_operating_characteristic(n, q, MARGIN, q + 0.15),
            }
            for n in (24, 100, 200, 400, 800)
        }
        rows.append(
            {
                "adversary": label,
                "q": q,
                "detect_margin_0.10": {**detect, "H0": q, "H1": q + MARGIN},
                "certify_margin_ge_0.10_true_0.15": {**certify_05, "H0": q + MARGIN, "H1": q + MARGIN + 0.05},
                "certify_margin_ge_0.10_true_0.20": {**certify_10, "H0": q + MARGIN, "H1": q + MARGIN + 0.10},
                "fixed_cut_observed_margin_ge_0.10": cut,
            }
        )
    return {
        "test": "exact one-sided binomial, alpha 0.05, power 0.80",
        "why_not_paired": (
            "the frozen adversary's per-item outcomes are known offline but the Solver's are not; "
            "a paired (McNemar) Solver-vs-adversary test needs the Solver rows the founder run "
            "produces, so no paired design can be sized here"
        ),
        "rows": rows,
    }


def part_b() -> dict[str, Any]:
    p10 = (DISCORDANCE + DELTA) / 2.0
    p01 = (DISCORDANCE - DELTA) / 2.0
    out: dict[str, Any] = {
        "delta": DELTA,
        "discordance": DISCORDANCE,
        "p10": p10,
        "p01": p01,
        "test": "exact two-sided McNemar (conditional binomial on the discordant pairs)",
        "alphas": {},
    }
    for label, alpha in (("unadjusted_0.05", ALPHA), ("holm_worst_case_alpha_over_4", ALPHA / K_HOLM)):
        req80 = required_n_mcnemar(p10, p01, alpha, 0.80)
        req90 = required_n_mcnemar(p10, p01, alpha, 0.90)
        n80 = req80["n_pairs_stable"] or req80["n_pairs_first"]
        n_eff = {
            "icc_0": n80,
            f"icc_{ICC_MEASURED}": math.ceil(n80 * (1.0 + ICC_MEASURED)),
        }
        families = {k: math.ceil(v / 2) for k, v in n_eff.items()}
        rounded = {k: 20 * math.ceil(v / 20) for k, v in families.items()}
        out["alphas"][label] = {
            "alpha": alpha,
            "power_0.80": req80,
            "power_0.90": req90,
            "power_at_n": {str(n): mcnemar_power(n, p10, p01, alpha) for n in (100, 200, 300, 400, 500, 600, 800)},
            "n_items_for_0.80_by_icc": n_eff,
            "families_for_0.80_by_icc": families,
            "families_rounded_to_20": rounded,
            "items_rounded": {k: 2 * v for k, v in rounded.items()},
            "representability_of_rounded_items": {k: representability(2 * v) for k, v in rounded.items()},
            "model_calls_5_arms_base_plus_rotated": {k: 2 * v * 5 * 2 for k, v in rounded.items()},
        }
    # Cross-check against the arena power module (import only; nothing there is modified).
    try:
        from arena.experiments.precondition_power import mcnemar_exact_power

        checks = {str(n): {"local": mcnemar_power(n, p10, p01, ALPHA / K_HOLM), "arena": mcnemar_exact_power(n, p10, p01, ALPHA / K_HOLM)} for n in (100, 300, 500)}
        out["cross_check_vs_arena_precondition_power"] = {
            **checks,
            "max_abs_diff": max(abs(v["local"] - v["arena"]) for v in checks.values()),
        }
    except Exception as exc:  # noqa: BLE001
        out["cross_check_vs_arena_precondition_power"] = f"unavailable: {exc}"
    return out


def measured_adversary_rates(audit_path: Path) -> dict[str, float]:
    """Best frozen-adversary EVALUATION accuracy per level of the frozen V1 generator (max over surfaces)."""

    if not audit_path.exists():
        return {}
    payload = json.loads(audit_path.read_text())
    out: dict[str, float] = {}
    for key, cell in payload["summary"]["per_level"].items():
        if key.startswith("v1_frozen:"):
            out[f"measured_{key}"] = round(float(cell["max_eval_accuracy"]), 4)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, default=HERE / "adversary_audit.json")
    parser.add_argument("--out", type=Path, default=HERE / "power.json")
    args = parser.parse_args(argv)
    t0 = time.time()
    rates = {"chance_0.50": 0.50, "0.60": 0.60, "0.667": 2.0 / 3.0, "0.75": 0.75}
    rates.update(measured_adversary_rates(args.audit))
    payload = {
        "_disclaimer": "Design-stage arithmetic only. Zero model calls. No sentinel is re-scored.",
        "a_solver_vs_fixed_adversary": part_a(rates),
        "b_five_arm_tournament": part_b(),
        "elapsed_seconds": time.time() - t0,
    }
    args.out.write_text(json.dumps(payload, indent=1))
    for r in payload["a_solver_vs_fixed_adversary"]["rows"]:
        d, c5, c10 = r["detect_margin_0.10"], r["certify_margin_ge_0.10_true_0.15"], r["certify_margin_ge_0.10_true_0.20"]
        print(
            f"(a) q={r['q']:.4f} [{r['adversary']}] detect +0.10: n_first={d['n_first']} n_stable={d['n_stable']} | "
            f"certify >=0.10 (true 0.15): {c5['n_stable']} | (true 0.20): {c10['n_stable']} | "
            f"fixed-cut false pass n=24: {r['fixed_cut_observed_margin_ge_0.10']['24']['false_pass_at_true_margin_0']:.3f}"
        )
    b = payload["b_five_arm_tournament"]
    for label, v in b["alphas"].items():
        print(
            f"(b) {label}: n_pairs(0.80)={v['power_0.80']} n_pairs(0.90)={v['power_0.90']} "
            f"items by ICC={v['n_items_for_0.80_by_icc']} families rounded={v['families_rounded_to_20']} "
            f"calls={v['model_calls_5_arms_base_plus_rotated']}"
        )
    print("cross-check:", b["cross_check_vs_arena_precondition_power"])
    print(f"elapsed {payload['elapsed_seconds']:.1f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
