"""Design-stage power analysis for the Phase 8 representation comparison.

Phase 8 compares several representations ``R_A, R_B, ...`` of the SAME precondition-conjunction
tasks against one fixed Solver.  Every task ``t`` yields a binary outcome ``Y[R, t]`` for each
representation, so the primary endpoint is the PAIRED accuracy difference on identical tasks::

    Δ(R_A, R_B) = acc_A - acc_B = (n10 - n01) / n

where ``n10`` counts tasks ``R_A`` gets right and ``R_B`` wrong and ``n01`` the reverse.  Tasks
come in twin families (ORIGINAL + COUNTERFACTUAL sharing objects, propositions and options), so
outcomes cluster by family.  The test is the exact McNemar test on the discordant pairs, with a
family-clustered paired bootstrap interval and a Holm correction across ``k`` comparisons against
the baseline representation (``k = 4`` for a five-arm roster; ``k = 10`` for all pairs).

This module never calls a model.  Every quantity is computed either exactly (enumeration or FFT
convolution) or by seeded simulation, and :func:`main` writes one deterministic JSON report.

Parameterisation
----------------
A design cell is ``(baseline accuracy, Δ, discordance π_d, α, ICC)``.  With the candidate arm as
``A`` and the baseline arm as ``B``::

    p10 - p01 = Δ                p10 + p01 = π_d
    p10 = (π_d + Δ) / 2          p01 = (π_d - Δ) / 2
    p11 = baseline + Δ - p10     p00 = 1 - baseline - p10      (all four cells must be ≥ 0)

The exact McNemar power depends on ``(n, p10, p01)`` only; the baseline accuracy enters through
feasibility (and through the candidate ceiling ``baseline + Δ``).

Clustering model
----------------
Twin clustering is modelled by the two-item Dirichlet-multinomial ("beta-binomial" generalised to
the four paired cells): each family draws cell probabilities ``π_f ~ Dirichlet(a · p)`` and its
two items are drawn i.i.d. from ``π_f``.  With ``ρ = 1 / (1 + a)`` the pairwise joint law of two
items in a family is *exactly* the mixture "with probability ``ρ`` the twin copies the original's
cell, otherwise it draws independently".  Consequently every item-level statistic — including the
paired difference ``Y_A - Y_B`` whose intraclass correlation the V7 audit measured at +0.51 in the
decisive cell — has ICC exactly ``ρ``, and the design effect for two items per family is
``1 + ρ``.  The (n10, n01) law under this model is a ``n_families``-fold convolution of a 3×3
family kernel, which :func:`clustered_mcnemar_power_exact` evaluates by FFT; the simulated
:func:`clustered_mcnemar_power` samples the same construction and serves as its cross-check.

Discreteness
------------
Every accuracy is ``k / n`` and every paired difference ``(n10 - n01) / n``, so the smallest
representable margin at ``n`` items is ``1 / n``; :func:`representability` reports, for a given
``n``, whether the project's thresholds 0.10 / 0.125 / 0.15 are exact counts.  The V7 audit found
that at ``n = 24`` the declared 0.10 gate was operationally 0.125 (research/audit/a4_margin_power.md
§D3); the recommended designs below are multiples of 20 families (40 items) precisely so that all
three thresholds are representable.
"""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from arena.canonical.schema import canonical_json
from arena.evaluation.landscape import mcnemar_exact

POWER_ANALYSIS_VERSION = "arena-precondition-power-v1.0.0"
DEFAULT_SEED = 20260907
DEFAULT_OUT = Path("artifacts/reports/precondition_power_analysis.json")
ITEMS_PER_FAMILY = 2

# Project constants this design must respect (arena/experiments/fitness_v5.py PROMOTION_RULE).
PRACTICAL_EFFECT_MIN = 0.10
SMALLEST_EFFECT_OF_INTEREST = 0.15
PRACTICAL_EQUIVALENCE_REGION = 0.125
THRESHOLDS = (PRACTICAL_EFFECT_MIN, PRACTICAL_EQUIVALENCE_REGION, SMALLEST_EFFECT_OF_INTEREST)

# Budget inputs.  MEASURED on the frozen Solver: exact prompt tokens and wall-clock seconds per
# call for three representations at three strata (P12 / P16 / P20).  The HML and S-expression
# arms are DERIVED from their character share of the JSON AST prompt (seconds and tokens assumed
# proportional); stratum P09 is INTERPOLATED as 0.8 × P12.  A rotated-option twin run issued
# immediately after its base call hits the prefix cache and costs ≈ 2 s regardless of arm.
ROTATED_CALL_SECONDS = 2.0
ARM_ORDER = ("R_json_ast", "R_structured_english", "R_compact_symbolic", "R_hml", "R_sexpr")
MEASURED_ARM_PROFILES: dict[str, dict[str, tuple[int, float]]] = {  # stratum → arm → (tokens, s)
    "P12": {
        "R_json_ast": (12_093, 21.9),
        "R_structured_english": (9_805, 16.6),
        "R_compact_symbolic": (5_183, 8.4),
    },
    "P16": {
        "R_json_ast": (15_162, 28.2),
        "R_structured_english": (12_298, 22.1),
        "R_compact_symbolic": (6_508, 11.0),
    },
    "P20": {
        "R_json_ast": (18_147, 36.0),
        "R_structured_english": (14_707, 29.3),
        "R_compact_symbolic": (7_749, 14.2),
    },
}
DERIVED_ARM_JSON_SHARE: dict[str, float] = {"R_hml": 0.55, "R_sexpr": 0.45}
INTERPOLATED_STRATA: dict[str, tuple[str, float]] = {"P09": ("P12", 0.8)}
BUDGET_STRATA = ("P09", "P12", "P16")
BUDGET_FAMILY_GRID = (100, 150, 200, 250, 300)

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


# ------------------------------------------------------------------ numerical primitives


_LOG_FACTORIALS: FloatArray = np.zeros(1)


def _log_factorials(n: int) -> FloatArray:
    """Return ``log(k!)`` for ``k = 0..n`` (grown lazily, never shrunk)."""

    global _LOG_FACTORIALS
    if len(_LOG_FACTORIALS) <= n:
        size = max(n + 1, 2 * len(_LOG_FACTORIALS))
        _LOG_FACTORIALS = np.concatenate(
            [[0.0], np.cumsum(np.log(np.arange(1, size, dtype=np.float64)))]
        )
    return _LOG_FACTORIALS


def _binomial_pmf(d: int, q: float) -> FloatArray:
    """Exact-to-double binomial pmf ``P(X = k | d, q)`` for ``k = 0..d`` via log-space."""

    if d < 0:
        raise ValueError("d must be non-negative")
    pmf = np.zeros(d + 1)
    if q <= 0.0:
        pmf[0] = 1.0
        return pmf
    if q >= 1.0:
        pmf[d] = 1.0
        return pmf
    lf = _log_factorials(d)
    k = np.arange(d + 1)
    log_pmf = lf[d] - lf[k] - lf[d - k] + k * math.log(q) + (d - k) * math.log1p(-q)
    return np.exp(log_pmf)


def _binomial_cdf(d: int, q: float) -> FloatArray:
    return np.minimum(1.0, np.cumsum(_binomial_pmf(d, q)))


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse normal CDF by bisection on ``math.erf`` (no scipy dependency)."""

    if not 0.0 < p < 1.0:
        raise ValueError("p must lie strictly inside (0, 1)")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


_CRITICAL_CACHE: dict[tuple[float, bool], IntArray] = {}


def _critical_values(d_max: int, alpha: float, two_sided: bool) -> IntArray:
    """``crit[d]`` = largest ``c`` with ``P(X ≤ c | Bin(d, ½)) ≤ α_eff`` (``-1`` if none).

    ``α_eff = α/2`` two-sided, ``α`` one-sided.  The two-sided exact McNemar test therefore
    rejects iff ``min(n10, n01) ≤ crit[n10 + n01]``, which is identical to
    ``arena.evaluation.landscape.mcnemar_exact(n10, n01) ≤ α`` (verified exhaustively in tests).
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly inside (0, 1)")
    key = (alpha, two_sided)
    cached = _CRITICAL_CACHE.get(key)
    if cached is not None and len(cached) > d_max:
        return cached
    size = max(d_max + 1, 2 * len(cached) if cached is not None else 0, 64)
    alpha_eff = alpha / 2.0 if two_sided else alpha
    lf = _log_factorials(size)
    crit = np.full(size, -1, dtype=np.int64)
    for d in range(1, size):
        k = np.arange(d // 2 + 1)
        log_pmf = lf[d] - lf[k] - lf[d - k] - d * math.log(2.0)
        cdf = np.cumsum(np.exp(log_pmf))
        crit[d] = int(np.count_nonzero(cdf <= alpha_eff)) - 1
    _CRITICAL_CACHE[key] = crit
    return crit


def mcnemar_rejects(n10: int, n01: int, alpha: float, *, two_sided: bool = True) -> bool:
    """Decision of the exact McNemar test, one- or two-sided (one-sided: ``H1: p10 > p01``)."""

    if n10 < 0 or n01 < 0:
        raise ValueError("discordant counts must be non-negative")
    d = n10 + n01
    crit = _critical_values(d, alpha, two_sided)
    if two_sided:
        return min(n10, n01) <= int(crit[d])
    return n01 <= int(crit[d])


def _validate_cell_probabilities(p10: float, p01: float) -> None:
    if p10 < 0.0 or p01 < 0.0 or p10 + p01 > 1.0 + 1e-12:
        raise ValueError("p10 and p01 must be non-negative with p10 + p01 ≤ 1")


# ------------------------------------------------------------------ exact McNemar power


def mcnemar_exact_power(
    n_pairs: int, p10: float, p01: float, alpha: float, *, two_sided: bool = True
) -> float:
    """EXACT power of the exact McNemar test for ``n_pairs`` independent paired outcomes.

    Enumerates the number of discordant pairs ``D ~ Binomial(n, p10 + p01)`` and, for each
    ``D = d``, the conditional law ``n10 | d ~ Binomial(d, p10 / (p10 + p01))`` over the exact
    rejection region at level ``alpha``.  No simulation.
    """

    if n_pairs < 1:
        raise ValueError("n_pairs must be at least 1")
    _validate_cell_probabilities(p10, p01)
    discordance = p10 + p01
    if discordance == 0.0:
        return 0.0
    q = p10 / discordance
    crit = _critical_values(n_pairs, alpha, two_sided)
    p_d = _binomial_pmf(n_pairs, discordance)
    power = 0.0
    for d in range(1, n_pairs + 1):
        c = int(crit[d])
        if c < 0 or p_d[d] == 0.0:
            continue
        cdf = _binomial_cdf(d, q)
        upper = 1.0 - cdf[d - c - 1]  # P(n10 ≥ d - c)
        reject = (cdf[c] + upper) if two_sided else upper
        power += float(p_d[d]) * float(reject)
    return min(1.0, power)


def normal_approximation_n_pairs(
    delta: float, discordance: float, alpha: float, target_power: float, *, two_sided: bool = True
) -> float:
    """Closed-form McNemar sample size (Connor 1987); used only to bracket exact searches."""

    if delta <= 0.0 or discordance <= 0.0 or delta > discordance:
        raise ValueError("need 0 < delta ≤ discordance")
    z_alpha = _norm_ppf(1.0 - (alpha / 2.0 if two_sided else alpha))
    z_beta = _norm_ppf(target_power)
    numerator = z_alpha * math.sqrt(discordance) + z_beta * math.sqrt(discordance - delta**2)
    return (numerator / delta) ** 2


# ------------------------------------------------------------------ clustered (twin) power


def _family_kernel(p10: float, p01: float, icc: float) -> FloatArray:
    """3×3 law of one family's contribution ``(a, b)`` to ``(n10, n01)`` under the twin model."""

    _validate_cell_probabilities(p10, p01)
    if not 0.0 <= icc <= 1.0:
        raise ValueError("icc must lie in [0, 1]")
    pc = 1.0 - p10 - p01
    kernel = np.zeros((3, 3))
    # Copy branch: both items share one cell.
    kernel[0, 0] += icc * pc
    kernel[2, 0] += icc * p10
    kernel[0, 2] += icc * p01
    # Independent branch: two i.i.d. items.
    kernel[0, 0] += (1.0 - icc) * pc * pc
    kernel[1, 0] += (1.0 - icc) * 2.0 * p10 * pc
    kernel[0, 1] += (1.0 - icc) * 2.0 * p01 * pc
    kernel[2, 0] += (1.0 - icc) * p10 * p10
    kernel[0, 2] += (1.0 - icc) * p01 * p01
    kernel[1, 1] += (1.0 - icc) * 2.0 * p10 * p01
    return kernel


def _clustered_joint_pmf(n_families: int, p10: float, p01: float, icc: float) -> FloatArray:
    """Exact joint law of ``(n10, n01)`` for ``n_families`` twin families (FFT convolution)."""

    if n_families < 1:
        raise ValueError("n_families must be at least 1")
    size = ITEMS_PER_FAMILY * n_families + 1
    kernel = _family_kernel(p10, p01, icc)
    # Spectrum of the 3×3 kernel zero-padded to size×size, written directly in rfft2 layout:
    # F[u, v] = Σ_{a,b} K[a,b] · exp(-2πi (u·a + v·b) / size), v = 0 .. size // 2.
    angles_u = np.exp(-2j * np.pi * np.arange(size) / size)
    angles_v = np.exp(-2j * np.pi * np.arange(size // 2 + 1) / size)
    spectrum = np.zeros((size, size // 2 + 1), dtype=np.complex128)
    for a in range(3):
        for b in range(3):
            if kernel[a, b]:
                spectrum += kernel[a, b] * np.outer(angles_u**a, angles_v**b)
    joint = np.fft.irfft2(spectrum**n_families, s=(size, size))
    joint = np.clip(joint, 0.0, None)
    return joint / joint.sum()


def _reject_mask(n_items: int, alpha: float, two_sided: bool) -> npt.NDArray[np.bool_]:
    size = n_items + 1
    crit = _critical_values(n_items, alpha, two_sided)
    index = np.arange(size)
    d = np.minimum(index[:, None] + index[None, :], n_items)
    if two_sided:
        return np.minimum(index[:, None], index[None, :]) <= crit[d]
    return index[None, :] <= crit[d]


def clustered_mcnemar_power_exact(
    n_families: int, p10: float, p01: float, alpha: float, icc: float, *, two_sided: bool = True
) -> float:
    """Exact power under twin clustering (see module docstring); ``icc = 0`` reproduces
    :func:`mcnemar_exact_power` at ``2 · n_families`` pairs."""

    joint = _clustered_joint_pmf(n_families, p10, p01, icc)
    mask = _reject_mask(ITEMS_PER_FAMILY * n_families, alpha, two_sided)
    return min(1.0, float(joint[mask].sum()))


def _sample_family_counts(
    rng: np.random.Generator,
    replicates: int,
    n_families: int,
    p10: float,
    p01: float,
    icc: float,
) -> tuple[IntArray, IntArray, IntArray]:
    """Sample ``(n10, n01, family_sums)``; cells coded 0 = concordant, 1 = ``10``, 2 = ``01``."""

    lower, upper = 1.0 - p10 - p01, 1.0 - p01
    first = rng.random((replicates, n_families))
    second = rng.random((replicates, n_families))
    copy = rng.random((replicates, n_families)) < icc
    cell_a = (first >= lower).astype(np.int64) + (first >= upper).astype(np.int64)
    cell_b = (second >= lower).astype(np.int64) + (second >= upper).astype(np.int64)
    cell_b = np.where(copy, cell_a, cell_b)
    diff = (cell_a == 1).astype(np.int64) - (cell_a == 2).astype(np.int64)
    diff += (cell_b == 1).astype(np.int64) - (cell_b == 2).astype(np.int64)
    n10 = (cell_a == 1).sum(axis=1) + (cell_b == 1).sum(axis=1)
    n01 = (cell_a == 2).sum(axis=1) + (cell_b == 2).sum(axis=1)
    return n10.astype(np.int64), n01.astype(np.int64), diff


def clustered_mcnemar_power(
    n_families: int,
    p10: float,
    p01: float,
    alpha: float,
    icc: float,
    *,
    resamples: int = 20000,
    seed: int = DEFAULT_SEED,
    two_sided: bool = True,
) -> float:
    """SIMULATED power under twin clustering: sample families under the twin-copy model and run
    the exact McNemar test per replicate.  Cross-checks :func:`clustered_mcnemar_power_exact`."""

    if n_families < 1 or resamples < 1:
        raise ValueError("n_families and resamples must be at least 1")
    _family_kernel(p10, p01, icc)  # validates
    crit = _critical_values(ITEMS_PER_FAMILY * n_families, alpha, two_sided)
    rng = np.random.default_rng(seed)
    rejections = 0
    chunk = max(1, min(resamples, 4_000_000 // max(1, n_families)))
    done = 0
    while done < resamples:
        take = min(chunk, resamples - done)
        n10, n01, _ = _sample_family_counts(rng, take, n_families, p10, p01, icc)
        d = n10 + n01
        if two_sided:
            rejections += int(np.count_nonzero(np.minimum(n10, n01) <= crit[d]))
        else:
            rejections += int(np.count_nonzero(n01 <= crit[d]))
        done += take
    return rejections / resamples


def bootstrap_ci_halfwidth_analytic(
    n_families: int, p10: float, p01: float, icc: float, *, level: float = 0.95
) -> float:
    """Large-sample half-width ``z · sqrt((π_d - Δ²)(1 + ICC) / n_items)`` of the Δ interval."""

    delta = p10 - p01
    variance = (p10 + p01 - delta**2) * (1.0 + icc) / (ITEMS_PER_FAMILY * n_families)
    return _norm_ppf(0.5 + level / 2.0) * math.sqrt(max(variance, 0.0))


def paired_bootstrap_ci_width(
    n_families: int,
    p10: float,
    p01: float,
    icc: float,
    *,
    seed: int = DEFAULT_SEED,
    datasets: int = 100,
    resamples: int = 2000,
) -> float:
    """Expected 95% family-clustered percentile-bootstrap half-width for Δ.

    ``datasets`` synthetic experiments are drawn from the twin model; each is bootstrapped by
    resampling families with replacement (the same scheme as
    :func:`arena.evaluation.landscape.paired_comparison`, vectorised), and the mean half-width
    ``(hi - lo) / 2`` is returned.
    """

    if n_families < 1 or datasets < 1 or resamples < 2:
        raise ValueError("need n_families ≥ 1, datasets ≥ 1, resamples ≥ 2")
    rng = np.random.default_rng(seed)
    _, _, family_sums = _sample_family_counts(rng, datasets, n_families, p10, p01, icc)
    weights_p = np.full(n_families, 1.0 / n_families)
    n_items = ITEMS_PER_FAMILY * n_families
    half_widths = []
    for sums in family_sums:
        weights = rng.multinomial(n_families, weights_p, size=resamples)
        draws = np.sort(weights @ sums / n_items)
        lo = draws[max(0, int(0.025 * resamples))]
        hi = draws[min(resamples - 1, int(0.975 * resamples) - 1)]
        half_widths.append(0.5 * float(hi - lo))
    return float(np.mean(half_widths))


# ------------------------------------------------------------------ sample-size searches


def _smallest_n(power_at: Any, target_power: float, guess: float, maximum: int, label: str) -> int:
    """Smallest ``n ≤ maximum`` with ``power_at(n) ≥ target_power`` at the bracketed crossing.

    Brackets from the normal-approximation ``guess`` (doubling upward / halving downward), then
    bisects; the cap is only evaluated when doubling reaches it.  The *unconditional* exact
    McNemar power (averaged over the discordant count) was verified monotone in ``n`` on the
    grids this module uses (tests ``test_exact_power_monotone_in_n`` and
    ``test_clustered_exact_power_monotone_in_families``), so the crossing is the global minimum
    there.  For a sawtoothed curve the result is the crossing nearest the bracket.
    """

    if not 0.0 < target_power < 1.0:
        raise ValueError("target_power must lie strictly inside (0, 1)")
    if maximum < 1:
        raise ValueError("maximum must be at least 1")
    cache: dict[int, float] = {}

    def power(n: int) -> float:
        if n not in cache:
            cache[n] = power_at(n)
        return cache[n]

    hi = min(maximum, max(1, int(math.ceil(guess))))
    while power(hi) < target_power:
        if hi >= maximum:
            raise ValueError(
                f"{label}: power {power(maximum):.3f} at the cap of {maximum} is below the target"
            )
        hi = min(maximum, 2 * hi)
    lo = max(1, hi // 2)
    while lo > 1 and power(lo) >= target_power:
        lo = max(1, lo // 2)
    if power(lo) >= target_power:
        return lo
    while hi - lo > 1:  # invariant: power(lo) < target ≤ power(hi)
        mid = (lo + hi) // 2
        if power(mid) >= target_power:
            hi = mid
        else:
            lo = mid
    return hi


def required_n_pairs(
    target_power: float,
    p10: float,
    p01: float,
    alpha: float,
    *,
    max_pairs: int = 4000,
    two_sided: bool = True,
) -> int:
    """Smallest number of independent pairs whose exact McNemar power reaches ``target_power``."""

    _validate_cell_probabilities(p10, p01)
    if p10 <= p01:
        raise ValueError("required_n_pairs needs p10 > p01 (a positive Δ)")
    guess = normal_approximation_n_pairs(
        p10 - p01, p10 + p01, alpha, target_power, two_sided=two_sided
    )
    return _smallest_n(
        lambda n: mcnemar_exact_power(n, p10, p01, alpha, two_sided=two_sided),
        target_power,
        guess,
        max_pairs,
        "required_n_pairs",
    )


def required_families(
    target_power: float,
    p10: float,
    p01: float,
    alpha: float,
    icc: float,
    *,
    max_families: int = 2000,
    two_sided: bool = True,
) -> int:
    """Smallest number of twin families whose exact clustered power reaches ``target_power``.

    Uses :func:`clustered_mcnemar_power_exact`, so the answer is deterministic; raises
    ``ValueError`` when even ``max_families`` is insufficient (the design table flags this).
    """

    _family_kernel(p10, p01, icc)
    if p10 <= p01:
        raise ValueError("required_families needs p10 > p01 (a positive Δ)")
    guess = normal_approximation_n_pairs(
        p10 - p01, p10 + p01, alpha, target_power, two_sided=two_sided
    )
    guess *= (1.0 + icc) / ITEMS_PER_FAMILY

    def power_at(n: int) -> float:
        if icc == 0.0:  # two independent items per family: no convolution needed
            return mcnemar_exact_power(ITEMS_PER_FAMILY * n, p10, p01, alpha, two_sided=two_sided)
        return clustered_mcnemar_power_exact(n, p10, p01, alpha, icc, two_sided=two_sided)

    return _smallest_n(power_at, target_power, guess, max_families, "required_families")


# ------------------------------------------------------------------ discreteness


def representability(n_items: int, thresholds: Sequence[float] = THRESHOLDS) -> dict[str, Any]:
    """Quantum ``1/n`` and, per threshold, whether it is an exact count ``k/n``."""

    if n_items < 1:
        raise ValueError("n_items must be at least 1")
    per_threshold = {}
    for threshold in thresholds:
        exact_count = threshold * n_items
        below = math.floor(exact_count + 1e-9)
        representable = abs(exact_count - round(exact_count)) < 1e-9
        per_threshold[f"{threshold:.3f}"] = {
            "representable": representable,
            "count": round(exact_count) if representable else None,
            "largest_failing_margin": (below if not representable else below - 1) / n_items,
            "smallest_passing_margin": (below + 1 if not representable else below) / n_items,
        }
    return {
        "n_items": n_items,
        "quantum": 1.0 / n_items,
        "thresholds": per_threshold,
        "all_thresholds_representable": all(v["representable"] for v in per_threshold.values()),
    }


def _round_up_to_multiple(value: int, multiple: int) -> int:
    return int(math.ceil(value / multiple)) * multiple


# ------------------------------------------------------------------ design table


def derive_cells(baseline_accuracy: float, delta: float, discordance: float) -> dict[str, Any]:
    """Map ``(baseline, Δ, π_d)`` to the four paired-cell probabilities and a feasibility flag."""

    p10 = (discordance + delta) / 2.0
    p01 = (discordance - delta) / 2.0
    p11 = baseline_accuracy + delta - p10  # candidate right = p11 + p10
    p00 = 1.0 - baseline_accuracy - p10  # baseline wrong = p10 + p00
    reasons = []
    if delta > discordance + 1e-12:
        reasons.append("delta exceeds the discordance rate (p01 < 0)")
    if p11 < -1e-12:
        reasons.append("candidate accuracy below p10 (p11 < 0)")
    if p00 < -1e-12:
        reasons.append("baseline gets fewer items wrong than p10 requires (p00 < 0)")
    if baseline_accuracy + delta > 1.0 + 1e-12:
        reasons.append("candidate accuracy exceeds 1")
    return {
        "baseline_accuracy": baseline_accuracy,
        "candidate_accuracy": baseline_accuracy + delta,
        "delta": delta,
        "discordance": discordance,
        "p10": p10,
        "p01": p01,
        "p11": p11,
        "p00": p00,
        "feasible": not reasons,
        "infeasible_reasons": reasons,
    }


def design_table(
    *,
    deltas: Sequence[float] = (0.075, 0.10, 0.15),
    discordance_rates: Sequence[float] = (0.20, 0.30, 0.40),
    accuracies: Sequence[float] = (0.70, 0.75, 0.80),
    alphas: Sequence[float] = (0.05, 0.05 / 4, 0.05 / 10),
    iccs: Sequence[float] = (0.0, 0.3, 0.5),
    target_power: float = 0.80,
    max_pairs: int = 4000,
    max_families: int = 2000,
) -> dict[str, Any]:
    """Required ``n`` for every ``(accuracy, Δ, π_d, α, ICC)`` combination.

    ``required_n_pairs_exact`` is the independent-pairs answer (depends on Δ, π_d, α only);
    ``required_families_clustered`` is the twin-model answer (adds ICC).  Combinations whose
    cell probabilities are impossible, or that exceed the search caps, are flagged rather than
    dropped.
    """

    pairs_cache: dict[tuple[float, float, float], int | None] = {}
    families_cache: dict[tuple[float, float, float, float], int | None] = {}
    rows: list[dict[str, Any]] = []
    infeasible: list[dict[str, Any]] = []
    for accuracy in accuracies:
        for delta in deltas:
            for discordance in discordance_rates:
                cells = derive_cells(accuracy, delta, discordance)
                for alpha in alphas:
                    for icc in iccs:
                        row: dict[str, Any] = {
                            **cells,
                            "alpha": alpha,
                            "icc": icc,
                            "target_power": target_power,
                        }
                        if not cells["feasible"]:
                            row["required_n_pairs_exact"] = None
                            row["required_families_clustered"] = None
                            infeasible.append(row)
                            rows.append(row)
                            continue
                        p10, p01 = cells["p10"], cells["p01"]
                        key_pairs = (delta, discordance, alpha)
                        if key_pairs not in pairs_cache:
                            try:
                                pairs_cache[key_pairs] = required_n_pairs(
                                    target_power, p10, p01, alpha, max_pairs=max_pairs
                                )
                            except ValueError:
                                pairs_cache[key_pairs] = None
                        key_fam = (delta, discordance, alpha, icc)
                        if key_fam not in families_cache:
                            try:
                                families_cache[key_fam] = required_families(
                                    target_power, p10, p01, alpha, icc, max_families=max_families
                                )
                            except ValueError:
                                families_cache[key_fam] = None
                        n_pairs = pairs_cache[key_pairs]
                        n_fam = families_cache[key_fam]
                        row["required_n_pairs_exact"] = n_pairs
                        row["required_families_clustered"] = n_fam
                        row["required_items_clustered"] = (
                            None if n_fam is None else ITEMS_PER_FAMILY * n_fam
                        )
                        row["normal_approximation_pairs"] = normal_approximation_n_pairs(
                            delta, discordance, alpha, target_power
                        )
                        row["quantum_at_required_items"] = (
                            None if n_fam is None else 1.0 / (ITEMS_PER_FAMILY * n_fam)
                        )
                        row["search_capped"] = n_pairs is None or n_fam is None
                        if row["search_capped"]:
                            row["infeasible_reasons"] = [
                                *row["infeasible_reasons"],
                                f"required n exceeds the caps (pairs ≤ {max_pairs}, "
                                f"families ≤ {max_families})",
                            ]
                            row["feasible"] = False
                            infeasible.append(row)
                        rows.append(row)
    return {
        "parameterisation": {
            "p10": "(discordance + delta) / 2  — candidate right, baseline wrong",
            "p01": "(discordance - delta) / 2  — baseline right, candidate wrong",
            "p11": "baseline + delta - p10",
            "p00": "1 - baseline - p10",
            "clustering": "two-item Dirichlet-multinomial ≡ twin-copy mixture; ICC exact",
            "test": "two-sided exact McNemar on discordant pairs (landscape.mcnemar_exact)",
            "items_per_family": ITEMS_PER_FAMILY,
        },
        "grid": {
            "deltas": list(deltas),
            "discordance_rates": list(discordance_rates),
            "accuracies": list(accuracies),
            "alphas": list(alphas),
            "iccs": list(iccs),
            "target_power": target_power,
            "max_pairs": max_pairs,
            "max_families": max_families,
        },
        "rows": rows,
        "infeasible_count": len(infeasible),
    }


# ------------------------------------------------------------------ shortcut gate OC


def _clopper_pearson_bounds(k: int, n: int, alpha: float) -> tuple[float, float]:
    """Exact (Clopper–Pearson) one-sided ``1 - alpha`` lower and upper bounds for a proportion."""

    if not 0 <= k <= n or n < 1:
        raise ValueError("need 0 ≤ k ≤ n and n ≥ 1")

    def solve(target: float, tail_upper: bool) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            cdf = _binomial_cdf(n, mid)
            value = float(cdf[k]) if tail_upper else 1.0 - (float(cdf[k - 1]) if k > 0 else 0.0)
            # tail_upper: P(X ≤ k | p) decreases in p; find p with P(X ≤ k | p) = alpha.
            # lower bound: P(X ≥ k | p) increases in p; find p with P(X ≥ k | p) = alpha.
            if tail_upper:
                if value > target:
                    lo = mid
                else:
                    hi = mid
            elif value < target:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)

    lower = 0.0 if k == 0 else solve(alpha, tail_upper=False)
    upper = 1.0 if k == n else solve(alpha, tail_upper=True)
    return lower, upper


def shortcut_gate_operating_characteristic(
    n_eval: int,
    thresholds: Sequence[float] = (0.55, 0.60),
    true_rates: Sequence[float] = (0.50, 0.55, 0.60, 0.65),
    n_rules: Sequence[int] = (20, 40, 80),
    *,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Operating characteristic of a Bonferroni Clopper–Pearson shortcut gate.

    The gate clears a rule only when its one-sided ``1 - alpha / n_rules`` upper bound is at or
    below the threshold.  For ``n_rules`` independent rules all at ``true_rate`` this returns
    ``P(max upper bound > threshold)``: under ``true_rate = 0.5`` that is the false-void rate,
    under ``true_rate ≥ threshold`` the detection rate.  ``k_star`` is the largest observed count
    that still clears; ``max_clearing_accuracy = k_star / n_eval``.  Correlated rules make the
    null maximum stochastically smaller, so the independent-rule numbers are conservative for the
    false-void rate and optimistic for detection.
    """

    if n_eval < 1:
        raise ValueError("n_eval must be at least 1")
    result: dict[str, Any] = {"n_eval": n_eval, "alpha": alpha, "gates": [], "null_max": []}
    null_cdf = _binomial_cdf(n_eval, 0.5)
    k = np.arange(n_eval + 1)
    for m in n_rules:
        cdf_max = null_cdf**m
        pmf_max = np.diff(np.concatenate([[0.0], cdf_max]))
        expected_max = float((k * pmf_max).sum()) / n_eval
        result["null_max"].append(
            {
                "n_rules": m,
                "expected_max_observed_accuracy": expected_max,
                "p95_max_observed_accuracy": float(k[np.searchsorted(cdf_max, 0.95)]) / n_eval,
            }
        )
    for threshold in thresholds:
        for m in n_rules:
            gamma = alpha / m
            k_star = _gate_k_star(n_eval, threshold, gamma)
            for rate in true_rates:
                p_all_clear = shortcut_gate_clear_probability(
                    n_eval, threshold, m, alpha=alpha, true_rate=rate
                )
                result["gates"].append(
                    {
                        "threshold": threshold,
                        "n_rules": m,
                        "true_rate": rate,
                        "bonferroni_level": gamma,
                        "k_star": k_star,
                        "max_clearing_accuracy": k_star / n_eval if k_star >= 0 else None,
                        "p_max_upper_bound_exceeds_threshold": 1.0 - p_all_clear,
                    }
                )
    result["note"] = (
        "independent rules; correlated rules shrink the null maximum, so the false-void "
        "probabilities are upper bounds and the detection probabilities lower bounds"
    )
    return result


def _gate_k_star(n_eval: int, threshold: float, gamma: float) -> int:
    """Largest observed count whose one-sided ``1 - gamma`` Clopper–Pearson upper bound is at or
    below ``threshold`` (``-1`` when no count clears)."""

    clears = np.flatnonzero(_binomial_cdf(n_eval, threshold) <= gamma)
    return int(clears[-1]) if len(clears) else -1


def shortcut_gate_clear_probability(
    n_eval: int, threshold: float, n_rules: int, *, alpha: float = 0.05, true_rate: float = 0.5
) -> float:
    """P(every one of ``n_rules`` independent rules at ``true_rate`` clears the Bonferroni gate)."""

    if n_eval < 1 or n_rules < 1:
        raise ValueError("n_eval and n_rules must be at least 1")
    if not 0.0 < threshold < 1.0 or not 0.0 <= true_rate <= 1.0:
        raise ValueError("threshold must lie in (0, 1) and true_rate in [0, 1]")
    k_star = _gate_k_star(n_eval, threshold, alpha / n_rules)
    if k_star < 0:
        return 0.0
    return float(_binomial_cdf(n_eval, true_rate)[k_star]) ** n_rules


def shortcut_gate_min_n_eval(
    threshold: float,
    n_rules: int,
    *,
    alpha: float = 0.05,
    true_rate: float = 0.5,
    clear_probability: float = 0.8,
    max_n_eval: int = 50_000,
) -> int | None:
    """Smallest ``n_eval`` at which the gate clears with probability ≥ ``clear_probability`` when
    every rule is truly at ``true_rate`` (``None`` when ``true_rate ≥ threshold`` or beyond the cap).

    Bracketed from a normal approximation and bisected (see :func:`_smallest_n`); the exact
    clear-probability curve has a small sawtooth, so read the answer as the bracketed crossing.
    """

    if true_rate >= threshold:
        return None
    gamma = alpha / n_rules
    z_gamma = _norm_ppf(1.0 - gamma)
    z_clear = _norm_ppf(clear_probability ** (1.0 / n_rules))
    spread = z_gamma * math.sqrt(threshold * (1.0 - threshold))
    spread += z_clear * math.sqrt(true_rate * (1.0 - true_rate))
    guess = (spread / (threshold - true_rate)) ** 2
    try:
        return _smallest_n(
            lambda n: shortcut_gate_clear_probability(
                n, threshold, n_rules, alpha=alpha, true_rate=true_rate
            ),
            clear_probability,
            guess,
            max_n_eval,
            "shortcut_gate_min_n_eval",
        )
    except ValueError:
        return None


# ------------------------------------------------------------------ equivalence (TOST)


def equivalence_test(
    n10: int, n01: int, n: int, *, region: float, alpha: float = 0.05
) -> dict[str, Any]:
    """Paired TOST for ``|Δ| < region`` in two flavours.

    Wald: ``Δ̂ = (n10 - n01)/n``, ``SE = sqrt(n10 + n01 - (n10 - n01)²/n) / n``; equivalence iff
    both one-sided z-tests reject at ``alpha`` (⇔ the ``1 - 2α`` Wald interval sits inside
    ``(-region, region)``).  Exact: conditional on ``d = n10 + n01`` with the discordance rate
    fixed at ``d/n``, ``Δ = (d/n)(2q - 1)`` for ``q = p10/(p10 + p01)``; the two hypotheses
    ``Δ ≥ region`` and ``Δ ≤ -region`` become ``q ≥ q₊`` and ``q ≤ q₋`` and are tested with exact
    binomial tails.  With ``d = 0`` both flavours are degenerate and equivalence is NOT claimed.

    Both flavours condition on the observed discordant count.  When ``d/n < region`` the
    conditional parameter space ``|Δ| ≤ d/n`` cannot reach the region at all, the exact tails are
    identically zero and the result is flagged ``region_conditionally_unattainable``: treat such
    a verdict as "parity given the observed discordance", not as an unconditional claim about
    ``π_d``.  The combined ``established`` flag requires BOTH flavours.
    """

    if n10 < 0 or n01 < 0 or n < 1 or n10 + n01 > n:
        raise ValueError("need n10, n01 ≥ 0 and n10 + n01 ≤ n")
    if region <= 0.0 or not 0.0 < alpha < 0.5:
        raise ValueError("need region > 0 and 0 < alpha < 0.5")
    d = n10 + n01
    delta = (n10 - n01) / n
    result: dict[str, Any] = {
        "n": n,
        "n10": n10,
        "n01": n01,
        "discordant": d,
        "delta": delta,
        "region": region,
        "alpha": alpha,
        "mcnemar_exact_p": mcnemar_exact(n10, n01),
        "degenerate": d == 0,
    }
    if d == 0:
        result.update(
            {
                "wald": {"established": False, "reason": "no discordant pairs; SE undefined"},
                "exact": {"established": False, "reason": "no discordant pairs; q undefined"},
                "established": False,
            }
        )
        return result
    se = math.sqrt(max(d - (n10 - n01) ** 2 / n, 0.0)) / n
    z = _norm_ppf(1.0 - alpha)
    if se > 0.0:
        p_lower = 1.0 - _norm_cdf((delta + region) / se)
        p_upper = 1.0 - _norm_cdf((region - delta) / se)
    else:  # all discordant pairs point one way: Δ̂ = ±d/n exactly, no sampling spread
        p_lower = 0.0 if delta > -region else 1.0
        p_upper = 0.0 if delta < region else 1.0
    wald = {
        "se": se,
        "ci_1_minus_2alpha": [delta - z * se, delta + z * se],
        "p_delta_le_minus_region": p_lower,
        "p_delta_ge_region": p_upper,
        "established": max(p_lower, p_upper) <= alpha,
    }
    pi_hat = d / n
    q_plus = 0.5 * (1.0 + region / pi_hat)
    q_minus = 0.5 * (1.0 - region / pi_hat)
    # |Δ| ≤ d/n given d: when the region exceeds the observed discordance rate the boundary
    # hypotheses lie outside the conditional parameter space and their tails are empty (p = 0).
    # At q₊ = 1 exactly the binomial tail still applies (it is 1 iff every discordant pair is 10).
    unattainable = pi_hat < region
    p_exact_upper = 0.0 if q_plus > 1.0 else float(_binomial_cdf(d, q_plus)[n10])
    if q_minus < 0.0:
        p_exact_lower = 0.0
    else:
        cdf = _binomial_cdf(d, q_minus)
        p_exact_lower = 1.0 - (float(cdf[n10 - 1]) if n10 > 0 else 0.0)
    q_lo, q_hi = _clopper_pearson_bounds(n10, d, alpha)
    exact = {
        "q_hat": n10 / d,
        "q_plus": q_plus,
        "q_minus": q_minus,
        "p_delta_ge_region": p_exact_upper,
        "p_delta_le_minus_region": p_exact_lower,
        "conditional_ci_1_minus_2alpha": [pi_hat * (2 * q_lo - 1), pi_hat * (2 * q_hi - 1)],
        "region_conditionally_unattainable": unattainable,
        "established": max(p_exact_upper, p_exact_lower) <= alpha,
    }
    result.update({"wald": wald, "exact": exact})
    result["established"] = bool(wald["established"] and exact["established"])
    return result


def parity_sample_size(
    region: float,
    true_delta: float,
    discordance: float,
    icc: float,
    *,
    alpha: float = 0.05,
    target_power: float = 0.80,
) -> dict[str, Any]:
    """Normal-approximation items needed for TOST power ``target_power`` at ``true_delta``."""

    if abs(true_delta) >= region:
        raise ValueError("true_delta must lie inside the region")
    sigma2 = (discordance - true_delta**2) * (1.0 + icc)
    z_alpha = _norm_ppf(1.0 - alpha)
    if true_delta == 0.0:
        z_beta = _norm_ppf(0.5 + target_power / 2.0)
        n_items = (z_alpha + z_beta) ** 2 * sigma2 / region**2
    else:
        z_beta = _norm_ppf(target_power)
        n_items = (z_alpha + z_beta) ** 2 * sigma2 / (region - abs(true_delta)) ** 2
    return {
        "region": region,
        "true_delta": true_delta,
        "discordance": discordance,
        "icc": icc,
        "alpha": alpha,
        "target_power": target_power,
        "required_ci_half_width_at_true_delta": region - abs(true_delta),
        "n_items": int(math.ceil(n_items)),
        "n_families": int(math.ceil(n_items / ITEMS_PER_FAMILY)),
    }


# ------------------------------------------------------------------ budget


def arm_profile(stratum: str) -> dict[str, dict[str, Any]]:
    """Per-arm ``prompt_tokens`` / ``seconds`` / ``provenance`` for one stratum.

    Measured strata come straight from :data:`MEASURED_ARM_PROFILES`; interpolated strata scale a
    measured reference; the HML and S-expression arms scale the JSON AST row by their character
    share (:data:`DERIVED_ARM_JSON_SHARE`).
    """

    if stratum in MEASURED_ARM_PROFILES:
        base, scale, source = MEASURED_ARM_PROFILES[stratum], 1.0, "measured"
    elif stratum in INTERPOLATED_STRATA:
        reference, scale = INTERPOLATED_STRATA[stratum]
        base, source = MEASURED_ARM_PROFILES[reference], f"interpolated ({scale:g} × {reference})"
    else:
        raise ValueError(f"unknown stratum {stratum!r}")
    json_tokens, json_seconds = base["R_json_ast"]
    profile: dict[str, dict[str, Any]] = {}
    for arm in ARM_ORDER:
        tokens: float
        seconds: float
        if arm in base:
            tokens, seconds = base[arm]
            provenance = source
        else:
            share = DERIVED_ARM_JSON_SHARE[arm]
            tokens, seconds = json_tokens * share, json_seconds * share
            provenance = f"{source}; {share:g} × JSON AST characters, seconds assumed proportional"
        profile[arm] = {
            "prompt_tokens": tokens * scale,
            "seconds": seconds * scale,
            "provenance": provenance,
        }
    return profile


def latency_fit() -> dict[str, Any]:
    """Least-squares ``seconds ≈ a + b · prompt_tokens / 1000`` over the nine measured calls.

    Reference only — the budget uses the measured seconds directly.  The residuals show the
    per-token cost rising with prompt length (1.6 → 2.0 ms/token), i.e. output length is not
    constant across strata.
    """

    tokens = np.array(
        [t for stratum in MEASURED_ARM_PROFILES.values() for t, _ in stratum.values()],
        dtype=np.float64,
    )
    seconds = np.array(
        [s for stratum in MEASURED_ARM_PROFILES.values() for _, s in stratum.values()],
        dtype=np.float64,
    )
    design = np.column_stack([np.ones_like(tokens), tokens / 1000.0])
    coef, _, _, _ = np.linalg.lstsq(design, seconds, rcond=None)
    residuals = seconds - design @ coef
    return {
        "intercept_seconds": float(coef[0]),
        "seconds_per_1000_tokens": float(coef[1]),
        "max_abs_residual_seconds": float(np.abs(residuals).max()),
        "ms_per_token_range": [
            float((seconds / tokens).min() * 1e3),
            float((seconds / tokens).max() * 1e3),
        ],
        "points": int(len(tokens)),
    }


def budget_table(
    n_families: int,
    arms: int,
    *,
    include_rotated: bool,
    seconds_per_call_by_arm: Mapping[str, float],
    rotated_seconds_per_call: float = ROTATED_CALL_SECONDS,
    items_per_family: int = ITEMS_PER_FAMILY,
    prompt_tokens_by_arm: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Model calls and SEQUENTIAL wall-clock hours for ``n_families`` twin families × ``arms``.

    Every item is sent once per arm (``primary``); with ``include_rotated`` every item is also
    sent once more per arm with its options rotated, at ``rotated_seconds_per_call`` each
    (prefix cache).  Hours are for one call at a time; ``c`` concurrent workers divide them by
    ``c``.  ``prompt_tokens_by_arm`` (optional) adds a token total for cost accounting.
    """

    if n_families < 1 or arms < 1 or items_per_family < 1:
        raise ValueError("n_families, arms and items_per_family must be positive")
    if len(seconds_per_call_by_arm) != arms:
        raise ValueError("seconds_per_call_by_arm must name exactly `arms` arms")
    if rotated_seconds_per_call <= 0.0:
        raise ValueError("rotated seconds per call must be positive")
    n_items = items_per_family * n_families
    per_arm = []
    primary_seconds = 0.0
    prompt_tokens_total = 0.0
    for arm, seconds in seconds_per_call_by_arm.items():
        if seconds <= 0.0:
            raise ValueError("seconds per call must be positive")
        tokens = None if prompt_tokens_by_arm is None else float(prompt_tokens_by_arm[arm])
        per_arm.append(
            {
                "arm": arm,
                "seconds_per_call": seconds,
                "prompt_tokens_per_call": tokens,
                "calls": n_items,
                "seconds": n_items * seconds,
            }
        )
        primary_seconds += n_items * seconds
        if tokens is not None:
            prompt_tokens_total += n_items * tokens * (2 if include_rotated else 1)
    primary_calls = n_items * arms
    rotated_calls = n_items * arms if include_rotated else 0
    rotated_seconds = rotated_calls * rotated_seconds_per_call
    total_seconds = primary_seconds + rotated_seconds
    return {
        "n_families": n_families,
        "n_items": n_items,
        "arms": arms,
        "include_rotated": include_rotated,
        "per_arm": per_arm,
        "primary_calls": primary_calls,
        "primary_hours": primary_seconds / 3600.0,
        "rotated_calls": rotated_calls,
        "rotated_seconds_per_call": rotated_seconds_per_call if include_rotated else None,
        "rotated_hours": rotated_seconds / 3600.0,
        "total_calls": primary_calls + rotated_calls,
        "total_hours": total_seconds / 3600.0,
        "prompt_tokens_total": None if prompt_tokens_by_arm is None else prompt_tokens_total,
        "sequential": True,
    }


def budget_grid(
    *,
    n_families_grid: Sequence[int] = BUDGET_FAMILY_GRID,
    strata: Sequence[str] = BUDGET_STRATA,
    include_rotated: bool = True,
) -> dict[str, Any]:
    """Five-arm budget for every ``stratum × n_families`` cell, with and without the rotated audit."""

    rows = []
    hours: dict[str, dict[str, float]] = {}
    for stratum in strata:
        profile = arm_profile(stratum)
        seconds = {arm: profile[arm]["seconds"] for arm in ARM_ORDER}
        tokens = {arm: profile[arm]["prompt_tokens"] for arm in ARM_ORDER}
        hours[stratum] = {}
        for n_families in n_families_grid:
            base = budget_table(
                n_families,
                len(ARM_ORDER),
                include_rotated=False,
                seconds_per_call_by_arm=seconds,
                prompt_tokens_by_arm=tokens,
            )
            full = budget_table(
                n_families,
                len(ARM_ORDER),
                include_rotated=include_rotated,
                seconds_per_call_by_arm=seconds,
                prompt_tokens_by_arm=tokens,
            )
            rows.append(
                {
                    "stratum": stratum,
                    "n_families": n_families,
                    "n_items": full["n_items"],
                    "primary_calls": full["primary_calls"],
                    "primary_hours": full["primary_hours"],
                    "rotated_calls": full["rotated_calls"],
                    "rotated_hours": full["rotated_hours"],
                    "total_calls": full["total_calls"],
                    "total_hours_without_rotated": base["total_hours"],
                    "total_hours": full["total_hours"],
                    "prompt_tokens_total": full["prompt_tokens_total"],
                }
            )
            hours[stratum][str(n_families)] = full["total_hours"]
    return {
        "arms": list(ARM_ORDER),
        "strata": list(strata),
        "n_families_grid": list(n_families_grid),
        "include_rotated": include_rotated,
        "rotated_call_seconds": ROTATED_CALL_SECONDS,
        "rows": rows,
        "total_hours_by_stratum": hours,
    }


# ------------------------------------------------------------------ report


def _rounded(value: Any, ndigits: int = 6) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return round(value, ndigits)
    if isinstance(value, dict):
        return {str(k): _rounded(v, ndigits) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_rounded(v, ndigits) for v in value]
    if isinstance(value, np.floating):
        return round(float(value), ndigits)
    if isinstance(value, np.integer):
        return int(value)
    return value


def power_curves(
    *,
    baseline_accuracy: float = 0.75,
    discordance: float = 0.30,
    deltas: Sequence[float] = (0.075, 0.10, 0.15),
    alphas: Sequence[float] = (0.05, 0.05 / 4),
    iccs: Sequence[float] = (0.0, 0.5),
    n_items_grid: Sequence[int] = (24, 48, 100, 200, 300, 400, 500, 600, 800, 1000),
) -> list[dict[str, Any]]:
    """Exact power (independent items, and twin-clustered) along a grid of item counts."""

    curves = []
    for delta in deltas:
        cells = derive_cells(baseline_accuracy, delta, discordance)
        for alpha in alphas:
            for icc in iccs:
                points = []
                for n_items in n_items_grid:
                    if n_items % ITEMS_PER_FAMILY:
                        raise ValueError("n_items must be a multiple of items per family")
                    if icc == 0.0:
                        power = mcnemar_exact_power(n_items, cells["p10"], cells["p01"], alpha)
                    else:
                        power = clustered_mcnemar_power_exact(
                            n_items // ITEMS_PER_FAMILY, cells["p10"], cells["p01"], alpha, icc
                        )
                    points.append({"n_items": n_items, "quantum": 1.0 / n_items, "power": power})
                curves.append(
                    {
                        "delta": delta,
                        "alpha": alpha,
                        "icc": icc,
                        "baseline_accuracy": baseline_accuracy,
                        "discordance": discordance,
                        "p10": cells["p10"],
                        "p01": cells["p01"],
                        "points": points,
                    }
                )
    return curves


def recommend(
    *,
    baseline_accuracy: float = 0.75,
    discordance: float = 0.30,
    delta: float = PRACTICAL_EFFECT_MIN,
    alpha: float = 0.05 / 4,
    icc: float = 0.5,
    target_power: float = 0.80,
    family_multiple: int = 20,
    seed: int = DEFAULT_SEED,
    resamples: int = 20000,
) -> dict[str, Any]:
    """Recommended design for one ``(Δ, α, ICC)`` plus its sensitivity and cross-checks."""

    cells = derive_cells(baseline_accuracy, delta, discordance)
    p10, p01 = cells["p10"], cells["p01"]
    exact_families = required_families(target_power, p10, p01, alpha, icc)
    rounded_families = _round_up_to_multiple(exact_families, family_multiple)
    n_items = ITEMS_PER_FAMILY * rounded_families
    exact_power_rounded = clustered_mcnemar_power_exact(rounded_families, p10, p01, alpha, icc)
    simulated = clustered_mcnemar_power(
        rounded_families, p10, p01, alpha, icc, resamples=resamples, seed=seed
    )
    sensitivity = []
    for disc in (0.20, 0.30, 0.40):
        for icc_alt in (0.0, 0.3, 0.5):
            alt = derive_cells(baseline_accuracy, delta, disc)
            try:
                fam = required_families(target_power, alt["p10"], alt["p01"], alpha, icc_alt)
            except ValueError:
                fam = None
            sensitivity.append(
                {
                    "discordance": disc,
                    "icc": icc_alt,
                    "required_families": fam,
                    "required_items": None if fam is None else ITEMS_PER_FAMILY * fam,
                    "power_at_recommended_families": clustered_mcnemar_power_exact(
                        rounded_families, alt["p10"], alt["p01"], alpha, icc_alt
                    ),
                }
            )
    se_items = math.sqrt((discordance - delta**2) * (1.0 + icc) / n_items)
    return {
        "inputs": {
            "baseline_accuracy": baseline_accuracy,
            "candidate_accuracy": cells["candidate_accuracy"],
            "delta": delta,
            "discordance": discordance,
            "p10": p10,
            "p01": p01,
            "alpha": alpha,
            "icc": icc,
            "target_power": target_power,
            "family_multiple": family_multiple,
        },
        "required_families_exact": exact_families,
        "required_items_exact": ITEMS_PER_FAMILY * exact_families,
        "recommended_families": rounded_families,
        "recommended_items": n_items,
        "power_at_recommended": {
            "exact_clustered": exact_power_rounded,
            "simulated_clustered": simulated,
            "simulation_resamples": resamples,
            "exact_independent_items": mcnemar_exact_power(n_items, p10, p01, alpha),
        },
        "representability": representability(n_items),
        "ci_half_width_95": {
            "clustered_bootstrap_simulated": paired_bootstrap_ci_width(
                rounded_families, p10, p01, icc, seed=seed
            ),
            "analytic": bootstrap_ci_halfwidth_analytic(rounded_families, p10, p01, icc),
        },
        "approximate_se_of_delta": se_items,
        "approximate_minimal_significant_delta": _norm_ppf(1.0 - alpha / 2.0) * se_items,
        "sensitivity": sensitivity,
    }


def build_report(*, seed: int = DEFAULT_SEED, resamples: int = 20000) -> dict[str, Any]:
    """Assemble every analysis into one deterministic, JSON-serialisable report."""

    baseline, discordance = 0.75, 0.30
    holm_k4, holm_k10 = 0.05 / 4, 0.05 / 10
    primary = recommend(
        baseline_accuracy=baseline,
        discordance=discordance,
        delta=PRACTICAL_EFFECT_MIN,
        alpha=holm_k4,
        icc=0.5,
        seed=seed,
        resamples=resamples,
    )
    alternative = recommend(
        baseline_accuracy=baseline,
        discordance=discordance,
        delta=SMALLEST_EFFECT_OF_INTEREST,
        alpha=holm_k4,
        icc=0.5,
        seed=seed + 1,
        resamples=resamples,
    )
    all_pairs = recommend(
        baseline_accuracy=baseline,
        discordance=discordance,
        delta=PRACTICAL_EFFECT_MIN,
        alpha=holm_k10,
        icc=0.5,
        seed=seed + 2,
        resamples=resamples,
    )
    cells = derive_cells(baseline, PRACTICAL_EFFECT_MIN, discordance)
    audit_anchor = {
        "note": (
            "V7 ran 24 positives per cell (12 twin families); power of the two-sided exact "
            "McNemar test at that size, at the design discordance 0.30 and at the V7-observed "
            "discordance 4/24"
        ),
        "n_items": 24,
        "quantum": 1.0 / 24,
        "representability": representability(24),
        "power": {
            f"delta={delta:.3f},discordance={disc:.4f},alpha={alpha:.4f}": mcnemar_exact_power(
                24,
                derive_cells(baseline, delta, disc)["p10"],
                derive_cells(baseline, delta, disc)["p01"],
                alpha,
            )
            for delta in (0.075, 0.10, 0.15)
            for disc in (discordance, 4 / 24)
            for alpha in (0.05, holm_k4)
        },
    }
    equivalence_examples = {
        "clear_parity": equivalence_test(
            60, 60, 500, region=PRACTICAL_EQUIVALENCE_REGION, alpha=0.05
        ),
        "clear_effect": equivalence_test(
            110, 40, 500, region=PRACTICAL_EQUIVALENCE_REGION, alpha=0.05
        ),
        "significant_but_below_floor": equivalence_test(
            95, 55, 500, region=PRACTICAL_EQUIVALENCE_REGION, alpha=0.05
        ),
        "recommended_n_parity": equivalence_test(
            60, 60, 400, region=PRACTICAL_EQUIVALENCE_REGION, alpha=0.05
        ),
        "recommended_n_parity_region_0.10": equivalence_test(
            60, 60, 400, region=PRACTICAL_EFFECT_MIN, alpha=0.05
        ),
        "v7_decisive_cell": equivalence_test(
            3, 1, 24, region=PRACTICAL_EQUIVALENCE_REGION, alpha=0.05
        ),
    }
    parity = [
        parity_sample_size(region, true_delta, discordance, icc)
        for region in (PRACTICAL_EQUIVALENCE_REGION, PRACTICAL_EFFECT_MIN)
        for true_delta in (0.0, 0.05)
        for icc in (0.0, 0.5)
    ]
    ci_half_width_needed = {
        "rule": (
            "TOST at alpha ⇔ the (1 - 2·alpha) Wald interval lies inside (-region, region); "
            "at alpha 0.05 that is the 90% interval, so the half-width must be ≤ region - |Δ̂|"
        ),
        "half_width_90_at_delta_hat_0": {
            f"region={region:.3f}": region
            for region in (PRACTICAL_EQUIVALENCE_REGION, PRACTICAL_EFFECT_MIN)
        },
        "half_width_90_at_recommended_n": {
            f"icc={icc:.1f}": _norm_ppf(0.95)
            * math.sqrt((discordance - 0.0) * (1.0 + icc) / primary["recommended_items"])
            for icc in (0.0, 0.5)
        },
    }
    clearability = [
        {
            "threshold": threshold,
            "n_rules": m,
            "true_rate": 0.5,
            "clear_probability": target,
            "min_n_eval": shortcut_gate_min_n_eval(threshold, m, clear_probability=target),
        }
        for threshold in (0.55, 0.60)
        for m in (20, 40, 80)
        for target in (0.5, 0.8)
    ]
    budget = {
        "inputs": {
            "rotated_call_seconds": ROTATED_CALL_SECONDS,
            "measured": {
                stratum: {
                    arm: {"prompt_tokens": tokens, "seconds": seconds}
                    for arm, (tokens, seconds) in arms.items()
                }
                for stratum, arms in MEASURED_ARM_PROFILES.items()
            },
            "derived_arm_json_share": DERIVED_ARM_JSON_SHARE,
            "interpolated_strata": {
                stratum: {"reference": reference, "scale": scale}
                for stratum, (reference, scale) in INTERPOLATED_STRATA.items()
            },
            "arm_profiles": {
                stratum: arm_profile(stratum) for stratum in ("P09", "P12", "P16", "P20")
            },
            "latency_fit_reference": latency_fit(),
        },
        "grid": budget_grid(),
        "recommended_design_with_rotated_audit": {
            stratum: budget_table(
                primary["recommended_families"],
                len(ARM_ORDER),
                include_rotated=True,
                seconds_per_call_by_arm={
                    arm: arm_profile(stratum)[arm]["seconds"] for arm in ARM_ORDER
                },
                prompt_tokens_by_arm={
                    arm: arm_profile(stratum)[arm]["prompt_tokens"] for arm in ARM_ORDER
                },
            )
            for stratum in BUDGET_STRATA
        },
    }
    report = {
        "version": POWER_ANALYSIS_VERSION,
        "seed": seed,
        "endpoint": {
            "definition": "Δ(R_A, R_B) = acc_A - acc_B = (n10 - n01)/n on identical tasks",
            "test": "two-sided exact McNemar on discordant pairs",
            "interval": "family-clustered paired percentile bootstrap, 95%",
            "multiplicity": {
                "holm_k4_worst_case_alpha": holm_k4,
                "holm_k10_worst_case_alpha": holm_k10,
                "note": "Holm's first step equals Bonferroni; designing at α/k is conservative",
            },
            "project_constants": {
                "practical_effect_min": PRACTICAL_EFFECT_MIN,
                "smallest_effect_of_interest": SMALLEST_EFFECT_OF_INTEREST,
                "practical_equivalence_region": PRACTICAL_EQUIVALENCE_REGION,
            },
            "cells_at_headline_design": cells,
        },
        "audit_anchor_n24": audit_anchor,
        "power_curves": power_curves(),
        "recommendation": {
            "primary_delta_0.10_holm_k4_icc_0.5": primary,
            "alternative_delta_0.15_holm_k4_icc_0.5": alternative,
            "all_pairs_delta_0.10_holm_k10_icc_0.5": all_pairs,
        },
        "design_table": design_table(),
        "shortcut_gate": {
            "operating_characteristic": {
                f"n_eval={n_eval}": shortcut_gate_operating_characteristic(n_eval)
                for n_eval in (200, 400, 800)
            },
            "clearability_at_chance": clearability,
        },
        "equivalence": {
            "region": PRACTICAL_EQUIVALENCE_REGION,
            "examples": equivalence_examples,
            "ci_half_width_needed": ci_half_width_needed,
            "parity_sample_sizes": parity,
        },
        "budget": budget,
    }
    return _rounded(report)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0] if __doc__ else "")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--resamples", type=int, default=20000)
    args = parser.parse_args(argv)
    report = build_report(seed=args.seed, resamples=args.resamples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    primary = report["recommendation"]["primary_delta_0.10_holm_k4_icc_0.5"]
    print(
        canonical_json(
            {
                "out": str(args.out),
                "recommended_families": primary["recommended_families"],
                "recommended_items": primary["recommended_items"],
                "power_exact_clustered": primary["power_at_recommended"]["exact_clustered"],
            }
        )
    )
    return 0


__all__ = [
    "ARM_ORDER",
    "BUDGET_FAMILY_GRID",
    "BUDGET_STRATA",
    "DERIVED_ARM_JSON_SHARE",
    "INTERPOLATED_STRATA",
    "MEASURED_ARM_PROFILES",
    "POWER_ANALYSIS_VERSION",
    "PRACTICAL_EFFECT_MIN",
    "PRACTICAL_EQUIVALENCE_REGION",
    "ROTATED_CALL_SECONDS",
    "SMALLEST_EFFECT_OF_INTEREST",
    "arm_profile",
    "bootstrap_ci_halfwidth_analytic",
    "budget_grid",
    "budget_table",
    "build_report",
    "clustered_mcnemar_power",
    "clustered_mcnemar_power_exact",
    "derive_cells",
    "design_table",
    "equivalence_test",
    "latency_fit",
    "main",
    "mcnemar_exact_power",
    "mcnemar_rejects",
    "normal_approximation_n_pairs",
    "paired_bootstrap_ci_width",
    "parity_sample_size",
    "power_curves",
    "recommend",
    "representability",
    "required_families",
    "required_n_pairs",
    "shortcut_gate_clear_probability",
    "shortcut_gate_min_n_eval",
    "shortcut_gate_operating_characteristic",
]


if __name__ == "__main__":
    raise SystemExit(main())
