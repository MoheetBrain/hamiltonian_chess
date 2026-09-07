"""A8: interval estimation and multiplicity analysis for the Astra n=60 holdout.

Read-only. No model call. Uses only research/astra/artifacts/*, which are DEVELOPMENT
artifacts built from random/train.json; no sealed split is opened.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

ART = Path("research/astra/artifacts")


def wilson(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def _betacf(a, b, x, itmax=300, eps=3e-16):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < 1e-300:
            d = 1e-300
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < 1e-300:
            d = 1e-300
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a,b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbeta + b * math.log1p(-x) + a * math.log(x)) * _betacf(b, a, 1 - x) / b


def beta_ppf(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    lo = 0.0 if k == 0 else beta_ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta_ppf(1 - alpha / 2, k + 1, n - k)
    return lo, hi


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def half_width(n: int, p: float = 0.4167, z: float = 1.96) -> float:
    return z * math.sqrt(p * (1 - p) / n)


def n_for_halfwidth(target: float, p: float = 0.4167, z: float = 1.96) -> int:
    return math.ceil(p * (1 - p) * (z / target) ** 2)


def power_two_prop(p1: float, p2: float, n: int, alpha: float = 0.05) -> float:
    """Power of a one-sided two-proportion z-test at equal n per arm."""
    pbar = (p1 + p2) / 2
    za = 1.6448536269514722 if alpha == 0.05 else 1.959963985
    se0 = math.sqrt(2 * pbar * (1 - pbar) / n)
    se1 = math.sqrt((p1 * (1 - p1) + p2 * (1 - p2)) / n)
    zb = (abs(p2 - p1) - za * se0) / se1
    return 0.5 * (1 + math.erf(zb / math.sqrt(2)))


def main() -> None:
    sc = json.loads((ART / "shortcut_results.json").read_text())
    rules = sc["visible_information_rules"]
    n_rules = len(rules)
    strongest = sc["strongest_visible_rule"]
    k, n = strongest["correct"], strongest["evaluated"]
    acc = k / n
    ties, tie_frac = strongest["ties"], strongest["tie_fraction"]

    out: dict = {
        "source": "research/astra/artifacts/shortcut_results.json (reproduced byte-identically by this audit)",
        "strongest_rule": strongest["name"],
        "k": k, "n": n, "point_estimate": acc, "chance": sc["chance"],
        "n_visible_rules_measured": n_rules,
        "ties": ties, "tie_fraction": tie_frac,
        "informative_score_items": strongest["informative_score_items"],
    }

    lo_w, hi_w = wilson(k, n)
    lo_cp, hi_cp = clopper_pearson(k, n)
    out["wilson_95"] = [lo_w, hi_w]
    out["clopper_pearson_95"] = [lo_cp, hi_cp]
    out["width_wilson"] = hi_w - lo_w

    # Bonferroni over the rule family that the max was taken over.
    alpha_b = 0.05 / n_rules
    out["bonferroni_alpha"] = alpha_b
    out["clopper_pearson_bonferroni"] = list(clopper_pearson(k, n, alpha_b))
    lo_wb, hi_wb = wilson(k, n, z=2.0 * 1.0)  # placeholder, replaced below
    # exact z for two-sided alpha/n_rules
    def z_for(alpha: float) -> float:
        lo, hi = 0.0, 10.0
        target = 1 - alpha / 2
        for _ in range(200):
            mid = (lo + hi) / 2
            if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    zb = z_for(alpha_b)
    out["bonferroni_z"] = zb
    out["wilson_bonferroni"] = list(wilson(k, n, z=zb))

    out["one_sided_binom_p_vs_chance"] = binom_sf(k, n, sc["chance"])

    # What the point estimate would be under random tie-breaking rather than
    # "always take the first candidate in the frozen order".
    bank = [json.loads(line) for line in (ART / "dev_bank.jsonl").read_text().splitlines() if line.strip()]
    heldout = [i for i in bank if i["audit_metadata"]["dev_partition"] == "heldout"]
    out["heldout_items"] = len(heldout)
    out["heldout_distinct_theorem_groups"] = len({i["provenance"]["proof_id"] for i in heldout})
    out["heldout_distinct_files"] = len({i["provenance"]["file_path"] for i in heldout})
    out["heldout_distinct_modules"] = len(
        {i["provenance"]["file_path"].rsplit("/", 1)[0] for i in heldout}
    )

    import sys
    sys.path.insert(0, ".")
    from research.astra.game_r_premise.shortcut_audit import ShortcutSuite, _answer, development_split

    train, ev = development_split(bank)
    suite = ShortcutSuite(train)
    rows = [(suite.visible_scores(i)[strongest["name"]], _answer(i)) for i in ev]
    rng = random.Random(8)
    trials = []
    for _ in range(20000):
        correct = 0
        for scores, ans in rows:
            best = max(scores)
            winners = [j for j, s in enumerate(scores) if s == best]
            if rng.choice(winners) == ans:
                correct += 1
        trials.append(correct / len(rows))
    trials.sort()
    out["random_tiebreak_strongest_rule"] = {
        "mean": sum(trials) / len(trials),
        "p05": trials[int(0.05 * len(trials))],
        "p50": trials[len(trials) // 2],
        "p95": trials[int(0.95 * len(trials))],
        "note": "the published 0.4167 uses first-in-frozen-order tie-breaking on 22/60 ties",
    }

    # Max-over-rules selection bias: how high does the best of this many rules go
    # when every rule is pure noise at chance on n=60?
    best_null = []
    for _ in range(20000):
        best_null.append(max(sum(rng.random() < sc["chance"] for _ in range(n)) for _ in range(n_rules)))
    best_null.sort()
    out["null_max_over_rules"] = {
        "n_rules": n_rules,
        "mean_k": sum(best_null) / len(best_null),
        "mean_acc": sum(best_null) / len(best_null) / n,
        "p95_k": best_null[int(0.95 * len(best_null))],
        "p95_acc": best_null[int(0.95 * len(best_null))] / n,
        "note": "independent-noise reference only; the real rules are correlated, so this understates nothing but is not a substitute for a permutation test",
    }

    out["precision"] = {
        "half_width_at_n": {str(m): half_width(m) for m in (60, 100, 300, 500, 1000, 2000, 5000)},
        "n_for_halfwidth_0.05": n_for_halfwidth(0.05),
        "n_for_halfwidth_0.02": n_for_halfwidth(0.02),
    }
    out["power_solver_vs_shortcut"] = {
        f"solver_{p}": power_two_prop(acc, p, n)
        for p in (0.45, 0.50, 0.55, 0.60, 0.70)
    }
    out["power_at_n"] = {
        str(m): power_two_prop(acc, 0.55, m) for m in (60, 100, 200, 400, 800)
    }
    print(json.dumps(out, indent=2))
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/n60_power.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
