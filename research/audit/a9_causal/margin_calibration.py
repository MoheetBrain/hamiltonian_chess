"""A9: is ``SHORTCUT_MARGIN = 0.10`` calibrated against the statistic it gates?

``best_shortcut_accuracy`` is ``max`` over V5's seven rules AND their negations
(``fitness_v5.py:829``), i.e. a maximum of a set of correlated estimates.  A maximum is biased
upward even when every underlying rule is exactly uninformative, so a fixed margin against it is
not a one-standard-error test of anything.

The preregistration (``docs/FITNESS_V7_PREREGISTRATION.md:71-74``) justifies 0.10 as "at n = 24 the
binomial standard error near 0.8 is 0.082".  That is the SE of the SOLVER's accuracy, not the SE of
the max-statistic it is differenced against.

This computes the exact null distribution of ``best-of-rule-or-negation`` for an antisymmetric rule
on a 12-family / 24-positive cell that is balanced only IN EXPECTATION (each family independently
lands 0-of-2 or 2-of-2 with probability 1/2 -- the polarity structure ``relabel`` forces), and for
the maximum over m such independent rules.  Pure arithmetic; ZERO model calls.
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

FAMILIES = 12
POSITIVES = 24


def single_rule_null() -> list[tuple[float, float]]:
    """(best_of_rule_or_negation, probability) for one antisymmetric rule."""

    dist: dict[float, float] = {}
    for k in range(FAMILIES + 1):
        p = comb(FAMILIES, k) / 2**FAMILIES
        score = 2 * k / POSITIVES
        best = max(score, 1.0 - score)
        dist[best] = dist.get(best, 0.0) + p
    return sorted(dist.items())


def max_over(m: int) -> dict[str, float]:
    dist = single_rule_null()
    values = [v for v, _ in dist]
    probs = [p for _, p in dist]
    cdf = []
    running = 0.0
    for p in probs:
        running += p
        cdf.append(running)
    exp = 0.0
    tail_above = {t: 0.0 for t in (0.5, 0.5834, 0.6667, 0.75)}
    prev = 0.0
    for value, c in zip(values, cdf, strict=True):
        mass = c**m - prev
        prev = c**m
        exp += value * mass
        for t in tail_above:
            if value > t + 1e-12:
                tail_above[t] += mass
    return {"expected_best": exp, **{f"P(best>{t})": v for t, v in tail_above.items()}}


def main() -> int:
    report = {
        "families": FAMILIES,
        "positives": POSITIVES,
        "single_rule_null_distribution": [
            {"best_of_rule_or_negation": v, "probability": p} for v, p in single_rule_null()
        ],
        "max_over_m_independent_rules": {str(m): max_over(m) for m in (1, 2, 3, 5)},
        "note": (
            "Under a generator that is balanced only in expectation, the gated statistic sits well "
            "above 0.5 by construction, so a fixed 0.10 margin is a moving target."
        ),
    }
    out = Path("research/audit/a9_causal/margin_calibration.json")
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print("single antisymmetric rule, 12 families, perfectly unbiased polarity:")
    for m in (1, 2, 3, 5):
        r = max_over(m)
        print(
            f"  max over m={m}: E[best]={r['expected_best']:.4f}  "
            f"P(>0.5834)={r['P(best>0.5834)']:.3f}  P(>0.6667)={r['P(best>0.6667)']:.3f}  "
            f"P(>0.75)={r['P(best>0.75)']:.3f}"
        )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
