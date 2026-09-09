"""Design-stage power / minimum-detectable-effect calculator for HC-V0.6.

Design brief §9.5 makes this module load-bearing rather than decorative:

    *"Every null must be reported beside the MDE actually achieved at the realised ``n`` and
    ``k``: 'we could detect ≥ X points; we observed Δ = … (CI …)'.  A null without an MDE is not
    a result."*

So this module answers two questions and stores the answer as a typed object that carries its own
assumptions:

* :func:`required_anchors` — given a baseline rate, a ``delta_min``, a cluster-size distribution,
  the ICC, ``k`` and a target power, how many anchors (and how many mathlib files) are needed;
* :func:`minimum_detectable_effect` — the reverse: given the realised ``n`` and ``k``, the smallest
  Δ the preregistered test would detect with the target power.

What is powered, and why it is not McNemar
------------------------------------------
The preregistered decision procedure is the **cluster sign-flip permutation test on the
anchor-averaged Δ̂** (:func:`arena.experiments.hc_v0_6.estimators.permutation_null` at
:data:`~arena.experiments.hc_v0_6.estimators.PermutationUnit.CLUSTER`), not exact McNemar.
Powering the test that is *reported but never decides* would be a granularity substitution of
exactly the kind ``docs/HC_V0_6_PREREGISTRATION.md`` §3 forbids.  The permutation test on Δ̂ is
asymptotically the cluster-robust z-test for Δ̂, so its power is computed here from the normal
approximation and then **checked against a simulation of the actual permutation test**
(:func:`simulate_power`).  Measured at the realised design, the approximation runs about 4-6
points high (4 at 75 clusters, 5-6 at the rebuilt 330), because the discrete sign-flip test is
mildly conservative; the MDE it produces is therefore
a slight *under*-statement of the effect the design needs, and the tests assert both the agreement
and its direction (``tests/experiments/test_hc_v0_6_analysis.py``).  ``mcnemar_exact_power`` is re-exported from
:mod:`arena.experiments.precondition_power` so the nominal-McNemar number can be reported beside
it, never instead of it.

The variance model, in one line
-------------------------------
::

    Var(Δ̂) = Var(D_i) / n × DEFF        Var(D_i) = (π_d − δ²) × f
    DEFF    = 1 + (m_A − 1) ρ_D          f = (1 + (k − 1) ρ_rep) / k
    m_A     = Σ_c m_c² / Σ_c m_c         (the design effect for UNEQUAL cluster sizes)

* ``D_i = p̂_{i,B} − p̂_{i,A}`` is the per-anchor paired difference the estimators average.
* ``π_d`` is the per-replicate discordance and ``δ`` the effect; at ``k = 1``,
  ``Var(D_i) = π_d − δ²`` exactly, because ``D_i ∈ {−1, 0, +1}`` with mean ``δ``.
* ``ρ_D`` is the intraclass correlation of ``D_i`` **within a mathlib file** — the analysis-level
  quantity the cluster bootstrap and the cluster permutation exist to absorb.
* ``m_A`` is ``Σ m² / Σ m``, not the mean cluster size: with unequal clusters the mean understates
  the design effect.  For the **rebuilt** bank (1127 anchors, 330 files, sizes
  ``{1:10, 2:10, 3:260, 4:3, 5:6, 6:33, 7:1, 9:3, 10:2, 11:1, 12:1}``) the mean is 3.42 and
  ``m_A`` is 4.02 — the rebuild made the bank 5.05× larger and its clusters more unequal, so the
  design effect per anchor got *worse* while the total precision got much better.  Read
  ``m_A`` off :meth:`ClusterProfile.from_anchor_bank`, never from this comment.

**The replicate factor is where determinism enters.**  ``ρ_rep`` is the intraclass correlation of
replicate outcomes inside one cell.  If the Solver is call-for-call deterministic under the frozen
decoding then ``ρ_rep = 1``, ``f = 1`` for every ``k``, and **replicates buy nothing at all**: the
same prompt returns the same bytes, so a second replicate is a copy, not a draw.  That is the
default here (:data:`DETERMINISTIC_SOLVER`) precisely so that a ``k`` chosen for comfort cannot
silently appear as power the design does not have.  With ``ρ_rep = 0`` (pure call noise, no anchor
fixed effect) ``f = 1/k`` and replicates are worth their cost.

Discordance from the marginals
------------------------------
The caller supplies a baseline rate and a δ, not a discordance, so ``π_d`` is derived::

    π_indep = p_A(1 − p_B) + p_B(1 − p_A)          (arms independent given the anchor)
    π_min   = |δ|                                   (arms maximally concordant)
    π_d     = (1 − φ) π_indep + φ π_min

``φ`` (:attr:`PairedBinaryModel.arm_concordance`) defaults to **0**, the independence assumption,
which is the *largest* discordance consistent with the marginals and therefore the largest
variance and the most conservative ``n``.  Any measured concordance between the arms shrinks the
required sample sharply; it is a parameter and not a constant so that a pilot can tighten it
without editing this module.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from arena.experiments.hc_v0_6.schema import DesignViolation

# Reuse, not re-implementation: `_norm_cdf` / `_norm_ppf` are the project's scipy-free normal
# CDF and its bisection inverse, already exercised by `tests/experiments/test_precondition_power.py`.
# Copying them here would create a second definition of the same constant, which is worse than
# reaching across the module boundary for it.
from arena.experiments.precondition_power import _norm_cdf, _norm_ppf, mcnemar_exact_power
from arena.experiments.rendered_prompt_adversary import clopper_pearson

__all__ = [
    "DEFAULT_TARGET_POWER",
    "DETERMINISTIC_SOLVER",
    "HC_V0_6_BANK_RELPATH",
    "POWER_VERSION",
    "ClusterProfile",
    "MinimumDetectableEffect",
    "PairedBinaryModel",
    "ReplicateModel",
    "SampleSizeRequirement",
    "SimulationResult",
    "analytic_power",
    "bootstrap_ci",
    "design_summary",
    "mcnemar_exact_power",
    "minimum_detectable_effect",
    "required_anchors",
    "simulate_anchor_deltas",
    "simulate_power",
    "simulate_type_i",
]

POWER_VERSION: Final = "hc-v0.6-power-v1.0.0"
DEFAULT_TARGET_POWER: Final = 0.80
DEFAULT_ALPHA: Final = 0.05
HC_V0_6_BANK_RELPATH: Final = Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


# ------------------------------------------------------------------------- the cluster profile


@dataclass(frozen=True, slots=True)
class ClusterProfile:
    """The realised anchors-per-cluster distribution.  The cluster is the mathlib **file**.

    Only two functionals of the distribution matter to the design: ``n_anchors`` and the
    *effective* cluster size ``m_A = Σ m² / Σ m``.  Both are stored derived rather than supplied,
    so a profile cannot claim a design effect its own sizes do not produce.
    """

    sizes: tuple[int, ...]
    label: str = "unnamed"

    def __post_init__(self) -> None:
        if not self.sizes:
            raise DesignViolation("a cluster profile needs at least one cluster")
        if any(size < 1 for size in self.sizes):
            raise DesignViolation(f"cluster sizes must be >= 1: {sorted(self.sizes)[:5]}")

    # ---------------------------------------------------------------- constructors

    @classmethod
    def from_sizes(cls, sizes: Iterable[int], *, label: str = "unnamed") -> ClusterProfile:
        return cls(sizes=tuple(sorted(int(size) for size in sizes)), label=label)

    @classmethod
    def from_cluster_ids(cls, cluster_ids: Iterable[str], *, label: str = "unnamed"):
        """Profile of an observed table: one entry per distinct cluster id."""

        counts: dict[str, int] = {}
        for cluster_id in cluster_ids:
            counts[cluster_id] = counts.get(cluster_id, 0) + 1
        if not counts:
            raise DesignViolation("no cluster ids given")
        return cls.from_sizes(counts.values(), label=label)

    @classmethod
    def uniform(cls, n_clusters: int, size: int, *, label: str = "uniform") -> ClusterProfile:
        if n_clusters < 1 or size < 1:
            raise DesignViolation("n_clusters and size must both be >= 1")
        return cls(sizes=(size,) * n_clusters, label=label)

    @classmethod
    def from_anchor_bank(cls, path: Path | str = HC_V0_6_BANK_RELPATH) -> ClusterProfile:
        """Read the built anchored bank and count anchors per ``cluster.file_path``.

        The file, not the theorem, is the preregistered cluster unit
        (``docs/HC_V0_6_PREREGISTRATION.md`` §6), so this reads ``file_path`` deliberately.
        """

        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        anchors = payload.get("anchors")
        if not isinstance(anchors, list) or not anchors:
            raise DesignViolation(f"{path} carries no anchors")
        files = [str(anchor["cluster"]["file_path"]) for anchor in anchors]
        return cls.from_cluster_ids(files, label=f"anchor-bank:{Path(path).name}")

    # ---------------------------------------------------------------- functionals

    @property
    def n_clusters(self) -> int:
        return len(self.sizes)

    @property
    def n_anchors(self) -> int:
        return sum(self.sizes)

    @property
    def mean_cluster_size(self) -> float:
        return self.n_anchors / self.n_clusters

    @property
    def effective_cluster_size(self) -> float:
        """``m_A = Σ m² / Σ m``.  Equals the mean only when every cluster has the same size."""

        return sum(size * size for size in self.sizes) / self.n_anchors

    @property
    def size_histogram(self) -> dict[int, int]:
        histogram: dict[int, int] = {}
        for size in self.sizes:
            histogram[size] = histogram.get(size, 0) + 1
        return dict(sorted(histogram.items()))

    def design_effect(self, cluster_icc: float) -> float:
        """``DEFF = 1 + (m_A − 1) ρ_D``, the variance inflation from within-file dependence."""

        _check_unit_interval(cluster_icc, "cluster_icc")
        return 1.0 + (self.effective_cluster_size - 1.0) * cluster_icc

    def effective_n(self, cluster_icc: float) -> float:
        """The independent-anchor equivalent of this bank at the given ICC."""

        return self.n_anchors / self.design_effect(cluster_icc)

    def clusters_for_anchors(self, n_anchors: int) -> int:
        """Whole clusters of this size distribution needed to reach ``n_anchors``."""

        if n_anchors < 1:
            raise DesignViolation("n_anchors must be at least 1")
        return math.ceil(n_anchors / self.mean_cluster_size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "n_clusters": self.n_clusters,
            "n_anchors": self.n_anchors,
            "mean_cluster_size": self.mean_cluster_size,
            "effective_cluster_size_m_A": self.effective_cluster_size,
            "size_histogram": {str(k): v for k, v in self.size_histogram.items()},
        }


def _check_unit_interval(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise DesignViolation(f"{name} must lie in [0, 1], got {value!r}")


# ------------------------------------------------------------------------- the two-level model


@dataclass(frozen=True, slots=True)
class ReplicateModel:
    """``k`` and the within-cell replicate ICC ``ρ_rep``.

    ``ρ_rep = 1`` means the Solver is call-for-call deterministic: the ``k`` replicates of a cell
    are byte-identical copies, contribute no independent information, and the variance factor
    :attr:`factor` is 1 for every ``k``.
    """

    replicates: int = 1
    replicate_icc: float = 1.0

    def __post_init__(self) -> None:
        if self.replicates < 1:
            raise DesignViolation("replicates must be at least 1")
        _check_unit_interval(self.replicate_icc, "replicate_icc")

    @property
    def factor(self) -> float:
        """``f = (1 + (k − 1) ρ_rep) / k`` — what ``k`` replicates do to ``Var(D_i)``."""

        return (1.0 + (self.replicates - 1) * self.replicate_icc) / self.replicates

    @property
    def deterministic(self) -> bool:
        return self.replicate_icc == 1.0

    @property
    def effective_replicates(self) -> float:
        """``1 / f``: how many independent draws ``k`` replicates are actually worth."""

        return 1.0 / self.factor

    def to_dict(self) -> dict[str, Any]:
        return {
            "replicates": self.replicates,
            "replicate_icc": self.replicate_icc,
            "variance_factor": self.factor,
            "effective_replicates": self.effective_replicates,
            "deterministic_solver": self.deterministic,
        }


#: ``k = 1`` under a call-for-call deterministic Solver: the only remaining randomness is the
#: anchor sample.  This is the default because it is the design that survives determinism.
DETERMINISTIC_SOLVER: Final = ReplicateModel(replicates=1, replicate_icc=1.0)


@dataclass(frozen=True, slots=True)
class PairedBinaryModel:
    """The paired-binary alternative: a baseline endpoint rate and a signed effect.

    ``baseline_rate`` is ``p(KERNEL_ACCEPTED_STATE_CHANGE)`` under ``R_A`` -- the rate at which
    Lean accepts the first action *and* it moves the mathematics.  It is **not** the elaborator's
    raw acceptance rate, and it is not yet known: a preflight measures it, and until it lands
    every MDE in this module is a function of an assumed value.
    """

    baseline_rate: float
    delta: float
    #: 0 = arms independent given the anchor (largest discordance, conservative); 1 = maximally
    #: concordant (discordance ``|δ|``, the smallest value the marginals allow).
    arm_concordance: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 < self.baseline_rate < 1.0:
            raise DesignViolation(f"baseline_rate must lie in (0, 1), got {self.baseline_rate!r}")
        _check_unit_interval(self.arm_concordance, "arm_concordance")
        variant = self.baseline_rate + self.delta
        if not 0.0 <= variant <= 1.0:
            raise DesignViolation(
                f"baseline {self.baseline_rate} + delta {self.delta} = {variant} leaves [0, 1]"
            )

    @property
    def variant_rate(self) -> float:
        return self.baseline_rate + self.delta

    @property
    def independent_discordance(self) -> float:
        a, b = self.baseline_rate, self.variant_rate
        return a * (1.0 - b) + b * (1.0 - a)

    @property
    def discordance(self) -> float:
        """``π_d`` — the probability that one replicate pair disagrees."""

        return (
            1.0 - self.arm_concordance
        ) * self.independent_discordance + self.arm_concordance * abs(self.delta)

    @property
    def cell_probabilities(self) -> tuple[float, float]:
        """``(p10, p01)``: A-only and B-only discordant cell probabilities."""

        pi_d = self.discordance
        return ((pi_d - self.delta) / 2.0, (pi_d + self.delta) / 2.0)

    def unit_variance(self, replicates: ReplicateModel = DETERMINISTIC_SOLVER) -> float:
        """``Var(D_i) = (π_d − δ²) · f`` for one anchor."""

        base = self.discordance - self.delta**2
        if base < 0.0:  # pragma: no cover - only reachable from an inconsistent discordance
            raise DesignViolation(f"discordance {self.discordance} below delta^2 {self.delta**2}")
        return base * replicates.factor

    def to_dict(self) -> dict[str, Any]:
        p10, p01 = self.cell_probabilities
        return {
            "baseline_rate": self.baseline_rate,
            "variant_rate": self.variant_rate,
            "delta": self.delta,
            "arm_concordance": self.arm_concordance,
            "discordance": self.discordance,
            "p10": p10,
            "p01": p01,
        }


# ----------------------------------------------------------------------------- analytic power


def _z_pair(alpha: float, target_power: float) -> tuple[float, float]:
    if not 0.0 < alpha < 1.0:
        raise DesignViolation("alpha must lie strictly inside (0, 1)")
    if not 0.0 < target_power < 1.0:
        raise DesignViolation("target_power must lie strictly inside (0, 1)")
    return _norm_ppf(1.0 - alpha / 2.0), _norm_ppf(target_power)


def analytic_power(
    model: PairedBinaryModel,
    profile: ClusterProfile,
    *,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    cluster_icc: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
    n_anchors: int | None = None,
) -> float:
    """Two-sided normal-approximation power of the cluster-robust test for Δ̂.

    ``n_anchors`` overrides the profile's own size while keeping its shape (``m_A``), which is what
    "extend the bank with more files drawn from the same size distribution" means.
    """

    n = profile.n_anchors if n_anchors is None else int(n_anchors)
    if n < 1:
        raise DesignViolation("n_anchors must be at least 1")
    if model.delta == 0.0:
        return alpha
    variance = model.unit_variance(replicates) * profile.design_effect(cluster_icc) / n
    if variance <= 0.0:
        return 1.0
    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    standardised = abs(model.delta) / math.sqrt(variance)
    return _norm_cdf(standardised - z_alpha) + _norm_cdf(-standardised - z_alpha)


# ----------------------------------------------------------------------------- required sample


@dataclass(frozen=True, slots=True)
class SampleSizeRequirement:
    """How much bank the preregistered test needs to see ``delta_min`` at the target power."""

    delta_min: float
    baseline_rate: float
    alpha: float
    target_power: float
    replicates: ReplicateModel
    cluster_icc: float
    design_effect: float
    effective_cluster_size: float
    unit_variance: float
    #: Anchors required if anchors were independent (``DEFF = 1``).
    anchors_if_independent: int
    #: Anchors required under the clustering — the number that governs.
    anchors_required: int
    clusters_required: int
    #: Power the design actually attains at :attr:`anchors_required` (≥ ``target_power``).
    attained_power: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "power_version": POWER_VERSION,
            "delta_min": self.delta_min,
            "baseline_rate": self.baseline_rate,
            "alpha": self.alpha,
            "target_power": self.target_power,
            "replicates": self.replicates.to_dict(),
            "cluster_icc": self.cluster_icc,
            "design_effect": self.design_effect,
            "effective_cluster_size_m_A": self.effective_cluster_size,
            "unit_variance": self.unit_variance,
            "anchors_if_independent": self.anchors_if_independent,
            "anchors_required": self.anchors_required,
            "clusters_required": self.clusters_required,
            "attained_power": self.attained_power,
        }


def required_anchors(
    model: PairedBinaryModel,
    profile: ClusterProfile,
    *,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    cluster_icc: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_TARGET_POWER,
) -> SampleSizeRequirement:
    """Anchors (and whole mathlib files) needed to detect ``model.delta`` at ``target_power``.

    ``profile`` supplies the *shape* of the bank — its cluster-size distribution and hence ``m_A``
    — not its size: the answer may exceed the bank that exists, which is the point of asking.
    """

    if model.delta == 0.0:
        raise DesignViolation("a sample size for delta = 0 is not defined")
    z_alpha, z_beta = _z_pair(alpha, target_power)
    deff = profile.design_effect(cluster_icc)
    unit_variance = model.unit_variance(replicates)
    independent = (z_alpha + z_beta) ** 2 * unit_variance / model.delta**2
    n_independent = max(1, math.ceil(independent))
    n_required = max(1, math.ceil(independent * deff))
    return SampleSizeRequirement(
        delta_min=model.delta,
        baseline_rate=model.baseline_rate,
        alpha=alpha,
        target_power=target_power,
        replicates=replicates,
        cluster_icc=cluster_icc,
        design_effect=deff,
        effective_cluster_size=profile.effective_cluster_size,
        unit_variance=unit_variance,
        anchors_if_independent=n_independent,
        anchors_required=n_required,
        clusters_required=profile.clusters_for_anchors(n_required),
        attained_power=analytic_power(
            model,
            profile,
            replicates=replicates,
            cluster_icc=cluster_icc,
            alpha=alpha,
            n_anchors=n_required,
        ),
    )


# --------------------------------------------------------------------- minimum detectable effect


@dataclass(frozen=True, slots=True)
class MinimumDetectableEffect:
    """The smallest Δ the realised design can see — the number every null is reported beside."""

    n_anchors: int
    n_clusters: int
    baseline_rate: float
    alpha: float
    target_power: float
    replicates: ReplicateModel
    cluster_icc: float
    design_effect: float
    effective_cluster_size: float
    #: Smallest detectable improvement (``p_B > p_A``) and worsening, in probability points.
    mde_positive: float
    mde_negative: float
    #: The conservative headline: ``max(|mde_positive|, |mde_negative|)``.
    mde: float
    #: The MDE the same design would have if anchors were independent.  Reported so the price of
    #: clustering is visible rather than buried in the design effect.
    mde_if_independent: float

    @property
    def points(self) -> float:
        """The MDE in percentage points, which is how §9.5 asks for it to be reported."""

        return 100.0 * self.mde

    def licenses_null(self, observed_delta: float) -> bool:
        """Whether an observed null is small enough to be *interpretable* against this MDE.

        True only when the observation is inside the window the design could resolve; it is a
        precondition for reading a null, never a proof of absence.
        """

        return abs(observed_delta) < self.mde

    def to_dict(self) -> dict[str, Any]:
        return {
            "power_version": POWER_VERSION,
            "n_anchors": self.n_anchors,
            "n_clusters": self.n_clusters,
            "baseline_rate": self.baseline_rate,
            "alpha": self.alpha,
            "target_power": self.target_power,
            "replicates": self.replicates.to_dict(),
            "cluster_icc": self.cluster_icc,
            "design_effect": self.design_effect,
            "effective_cluster_size_m_A": self.effective_cluster_size,
            "mde_positive": self.mde_positive,
            "mde_negative": self.mde_negative,
            "mde": self.mde,
            "mde_points": self.points,
            "mde_if_independent": self.mde_if_independent,
        }


def _solve_mde(
    baseline_rate: float,
    *,
    sign: int,
    arm_concordance: float,
    gain: float,
) -> float:
    """Positive root of ``(1 + g) δ² − g B δ − g A = 0``.

    ``π_d = A + B δ`` is linear in the (signed) effect, so ``δ² = g (π_d − δ²)`` is a quadratic.
    ``gain = g = (z_α + z_β)² f · DEFF / n``.
    """

    concordant = 1.0 - arm_concordance
    a_coefficient = concordant * 2.0 * baseline_rate * (1.0 - baseline_rate)
    b_coefficient = concordant * (1.0 - 2.0 * baseline_rate) * sign + arm_concordance
    quadratic = 1.0 + gain
    linear = gain * b_coefficient
    constant = gain * a_coefficient
    root = (linear + math.sqrt(linear * linear + 4.0 * quadratic * constant)) / (2.0 * quadratic)
    ceiling = 1.0 - baseline_rate if sign > 0 else baseline_rate
    return min(root, ceiling)


def minimum_detectable_effect(
    baseline_rate: float,
    profile: ClusterProfile,
    *,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    cluster_icc: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_TARGET_POWER,
    arm_concordance: float = 0.0,
    n_anchors: int | None = None,
) -> MinimumDetectableEffect:
    """The smallest ``|Δ|`` detectable at ``target_power`` with the realised bank.

    The discordance depends on the effect being solved for, so this is a quadratic rather than the
    usual square root; both signs are solved because ``π_d`` is not symmetric in ``δ`` unless the
    baseline is ½, and the **larger magnitude is reported** as the headline MDE.
    """

    if not 0.0 < baseline_rate < 1.0:
        raise DesignViolation(f"baseline_rate must lie in (0, 1), got {baseline_rate!r}")
    _check_unit_interval(arm_concordance, "arm_concordance")
    n = profile.n_anchors if n_anchors is None else int(n_anchors)
    if n < 1:
        raise DesignViolation("n_anchors must be at least 1")
    z_alpha, z_beta = _z_pair(alpha, target_power)
    deff = profile.design_effect(cluster_icc)
    gain = (z_alpha + z_beta) ** 2 * replicates.factor / n
    positive = _solve_mde(baseline_rate, sign=1, arm_concordance=arm_concordance, gain=gain * deff)
    negative = _solve_mde(baseline_rate, sign=-1, arm_concordance=arm_concordance, gain=gain * deff)
    independent = max(
        _solve_mde(baseline_rate, sign=1, arm_concordance=arm_concordance, gain=gain),
        _solve_mde(baseline_rate, sign=-1, arm_concordance=arm_concordance, gain=gain),
    )
    return MinimumDetectableEffect(
        n_anchors=n,
        n_clusters=profile.clusters_for_anchors(n),
        baseline_rate=baseline_rate,
        alpha=alpha,
        target_power=target_power,
        replicates=replicates,
        cluster_icc=cluster_icc,
        design_effect=deff,
        effective_cluster_size=profile.effective_cluster_size,
        mde_positive=positive,
        mde_negative=-negative,
        mde=max(positive, negative),
        mde_if_independent=independent,
    )


# ---------------------------------------------------------------------------------- simulation


def _raw_cluster_icc(cluster_icc: float, replicates: ReplicateModel) -> float:
    """Cluster copy-probability that produces ``cluster_icc`` **on the per-anchor difference**.

    The generative model is a two-level common-value mixture: a cluster draws a template cell,
    each anchor copies it with probability ``√ρ_raw`` (else draws independently), and each
    replicate copies its anchor's value with probability ``√ρ_rep``.  Then

        Corr(D_i, D_l) = ρ_raw · k ρ_rep / (1 + (k − 1) ρ_rep)

    so hitting a target ICC **of the analysed quantity** requires inverting that factor.  With a
    deterministic Solver (``ρ_rep = 1``) the factor is 1 and ``ρ_raw = cluster_icc``.
    """

    _check_unit_interval(cluster_icc, "cluster_icc")
    if cluster_icc == 0.0:
        return 0.0
    k, rho = replicates.replicates, replicates.replicate_icc
    if rho == 0.0:
        raise DesignViolation(
            "replicate_icc = 0 means an anchor has no systematic component, so its differences "
            "cannot correlate within a cluster; cluster_icc must then be 0"
        )
    raw = cluster_icc * (1.0 + (k - 1) * rho) / (k * rho)
    if raw > 1.0 + 1e-12:
        raise DesignViolation(
            f"cluster_icc={cluster_icc} is unreachable at k={k}, replicate_icc={rho}: it would "
            f"need a raw within-cluster correlation of {raw:.3f}"
        )
    return min(1.0, raw)


def _draw_cells(
    rng: np.random.Generator, shape: tuple[int, ...], p10: float, p01: float
) -> FloatArray:
    """Draw ``D ∈ {−1, 0, +1}`` with ``P(−1) = p10`` and ``P(+1) = p01``."""

    uniform = rng.random(shape)
    return np.asarray(
        (uniform >= 1.0 - p01).astype(np.float64) - (uniform < p10).astype(np.float64),
        dtype=np.float64,
    )


def simulate_anchor_deltas(
    model: PairedBinaryModel,
    profile: ClusterProfile,
    *,
    trials: int,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    cluster_icc: float = 0.0,
    seed: int = 20260908,
) -> tuple[FloatArray, IntArray]:
    """``(deltas, cluster_index)`` for ``trials`` synthetic banks with the given dependence.

    ``deltas`` is ``trials × n_anchors`` of per-anchor ``D_i = p̂_B − p̂_A``; ``cluster_index``
    maps each anchor column to its cluster.  The construction reproduces, by design, exactly the
    two moments the analytic formula uses: ``Var(D_i) = (π_d − δ²) f`` and
    ``Corr(D_i, D_l) = cluster_icc`` within a cluster.
    """

    if trials < 1:
        raise DesignViolation("trials must be at least 1")
    p10, p01 = model.cell_probabilities
    if min(p10, p01) < -1e-12:
        raise DesignViolation(f"delta {model.delta} exceeds the discordance {model.discordance}")
    p10, p01 = max(p10, 0.0), max(p01, 0.0)
    groups = np.repeat(
        np.arange(profile.n_clusters, dtype=np.int64),
        np.asarray(profile.sizes, dtype=np.int64),
    )
    n_anchors = int(groups.size)
    rng = np.random.default_rng(seed)
    copy_cluster = math.sqrt(_raw_cluster_icc(cluster_icc, replicates))
    templates = _draw_cells(rng, (trials, profile.n_clusters), p10, p01)
    independent = _draw_cells(rng, (trials, n_anchors), p10, p01)
    take_template = rng.random((trials, n_anchors)) < copy_cluster
    anchor_values = np.where(take_template, templates[:, groups], independent)
    k = replicates.replicates
    if k == 1 or replicates.replicate_icc == 1.0:
        return np.asarray(anchor_values, dtype=np.float64), groups
    copy_anchor = math.sqrt(replicates.replicate_icc)
    replicate_independent = _draw_cells(rng, (trials, n_anchors, k), p10, p01)
    take_anchor = rng.random((trials, n_anchors, k)) < copy_anchor
    drawn = np.where(take_anchor, anchor_values[:, :, None], replicate_independent)
    return np.asarray(drawn.mean(axis=2), dtype=np.float64), groups


def _permutation_p_value(
    deltas: FloatArray, groups: IntArray, *, permutations: int, rng: np.random.Generator
) -> float:
    """The cluster (or anchor) sign-flip p-value.

    Written with the identical arithmetic as
    :func:`arena.experiments.hc_v0_6.estimators.permutation_null` so that the simulator measures
    the calibration of the *shipped* test rather than of a look-alike; the tests assert the two
    agree exactly on a fixed dataset.
    """

    observed = float(deltas.mean())
    n_groups = int(groups.max()) + 1
    signs = rng.integers(0, 2, size=(permutations, n_groups)).astype(np.float64) * 2.0 - 1.0
    draws = (signs[:, groups] * deltas[None, :]).mean(axis=1)
    extreme = int(np.count_nonzero(np.abs(draws) >= abs(observed) - 1e-12))
    return min(1.0, (1.0 + extreme) / (permutations + 1.0))


def bootstrap_ci(
    deltas: FloatArray, groups: IntArray, *, resamples: int, rng: np.random.Generator
) -> tuple[float, float]:
    """Vectorised twin of :func:`arena.experiments.fitness_v4.clustered_paired_bootstrap`.

    The statistic of a resample is ``Σ_chosen S_c / Σ_chosen m_c`` — the plain mean of the
    concatenated clusters, which is exactly what the shipped bootstrap computes — and the interval
    is the same ``[⌊0.025 B⌋, ⌈0.975 B⌉ − 1]`` order statistics.  Only the random number source
    differs, so the two agree to Monte-Carlo error; the tests assert that.  Passing anchor indices
    as ``groups`` gives the NAIVE row-level bootstrap: the negative control.
    """

    n_groups = int(groups.max()) + 1
    onehot = np.zeros((deltas.size, n_groups), dtype=np.float64)
    onehot[np.arange(deltas.size), groups] = 1.0
    sums = deltas @ onehot
    sizes = onehot.sum(axis=0)
    picks = rng.integers(0, n_groups, size=(resamples, n_groups))
    draws = np.sort(sums[picks].sum(axis=1) / sizes[picks].sum(axis=1))
    low = draws[max(0, int(0.025 * resamples))]
    high = draws[min(resamples - 1, int(0.975 * resamples) - 1)]
    return (float(low), float(high))


def _bootstrap_excludes_zero(
    deltas: FloatArray, groups: IntArray, *, resamples: int, rng: np.random.Generator
) -> bool:
    low, high = bootstrap_ci(deltas, groups, resamples=resamples, rng=rng)
    return bool(low > 0.0 or high < 0.0)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """A measured rejection rate with its Monte-Carlo interval.  Never a claimed rate."""

    label: str
    unit: str
    trials: int
    alpha: float
    rejections: int
    #: The rate this test SHOULD have (``alpha`` for a type-I run, ``None`` for a power run).
    nominal: float | None
    note: str

    @property
    def rate(self) -> float:
        return self.rejections / self.trials

    @property
    def rate_ci95(self) -> tuple[float, float]:
        return clopper_pearson(self.rejections, self.trials, 0.05)

    @property
    def calibrated(self) -> bool:
        """For a type-I run: is the nominal level inside the Monte-Carlo interval?"""

        if self.nominal is None:
            return False
        low, high = self.rate_ci95
        return low <= self.nominal <= high

    @property
    def anti_conservative(self) -> bool:
        """Rejects MORE often than nominal, beyond Monte-Carlo error.  The only fatal direction."""

        return self.nominal is not None and self.rate_ci95[0] > self.nominal

    @property
    def conservative(self) -> bool:
        """Rejects LESS often than nominal.  Costs power; never invalidates a rejection."""

        return self.nominal is not None and self.rate_ci95[1] < self.nominal

    @property
    def valid_level(self) -> bool:
        """A test is valid at ``alpha`` when it is not measurably anti-conservative."""

        return self.nominal is not None and not self.anti_conservative

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "unit": self.unit,
            "trials": self.trials,
            "alpha": self.alpha,
            "rejections": self.rejections,
            "rate": self.rate,
            "rate_ci95": list(self.rate_ci95),
            "nominal": self.nominal,
            "calibrated": self.calibrated,
            "anti_conservative": self.anti_conservative,
            "conservative": self.conservative,
            "valid_level": self.valid_level,
            "note": self.note,
        }


def _anchor_groups(n_anchors: int) -> IntArray:
    return np.arange(n_anchors, dtype=np.int64)


def simulate_type_i(
    profile: ClusterProfile,
    *,
    baseline_rate: float = 0.25,
    cluster_icc: float = 0.5,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    arm_concordance: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
    trials: int = 400,
    permutations: int = 499,
    resamples: int = 800,
    seed: int = 20260908,
) -> dict[str, SimulationResult]:
    """Realised false-positive rate of each test under a TRUE NULL with clustered data.

    Four tests are measured, and the pairing is the argument for the preregistration:

    ==============================  ====================================================
    ``cluster_permutation``         PREREGISTERED.  Should sit at ``alpha``.
    ``cluster_bootstrap``           PREREGISTERED interval.  Should sit near ``alpha``.
    ``anchor_permutation``          negative control: anchors flipped independently.
    ``anchor_bootstrap``            negative control: the NAIVE row-level bootstrap.
    ==============================  ====================================================

    The two negative controls are expected to over-reject by roughly the design effect; that
    measured inflation is the evidence for clustering by file, and is reported, not asserted.
    """

    model = PairedBinaryModel(
        baseline_rate=baseline_rate, delta=0.0, arm_concordance=arm_concordance
    )
    deltas, groups = simulate_anchor_deltas(
        model,
        profile,
        trials=trials,
        replicates=replicates,
        cluster_icc=cluster_icc,
        seed=seed,
    )
    anchors = _anchor_groups(deltas.shape[1])
    rng = np.random.default_rng(seed + 1)
    counters = {"cp": 0, "ap": 0, "cb": 0, "ab": 0}
    for row in deltas:
        if _permutation_p_value(row, groups, permutations=permutations, rng=rng) <= alpha:
            counters["cp"] += 1
        if _permutation_p_value(row, anchors, permutations=permutations, rng=rng) <= alpha:
            counters["ap"] += 1
        if _bootstrap_excludes_zero(row, groups, resamples=resamples, rng=rng):
            counters["cb"] += 1
        if _bootstrap_excludes_zero(row, anchors, resamples=resamples, rng=rng):
            counters["ab"] += 1
    deff = profile.design_effect(cluster_icc)
    inflation = (
        f"expected to over-reject: the file design effect at ICC={cluster_icc} is {deff:.2f}"
    )
    return {
        "cluster_permutation": SimulationResult(
            label="cluster sign-flip permutation (PREREGISTERED)",
            unit="CLUSTER",
            trials=trials,
            alpha=alpha,
            rejections=counters["cp"],
            nominal=alpha,
            note="exact under the sharp null for arbitrary within-file dependence",
        ),
        "cluster_bootstrap": SimulationResult(
            label="cluster percentile bootstrap (PREREGISTERED interval)",
            unit="CLUSTER",
            trials=trials,
            alpha=alpha,
            rejections=counters["cb"],
            nominal=alpha,
            note="percentile interval over files, resampled with replacement",
        ),
        "anchor_permutation": SimulationResult(
            label="anchor sign-flip permutation (NEGATIVE CONTROL)",
            unit="ANCHOR",
            trials=trials,
            alpha=alpha,
            rejections=counters["ap"],
            nominal=alpha,
            note=inflation,
        ),
        "anchor_bootstrap": SimulationResult(
            label="naive row-level bootstrap (NEGATIVE CONTROL)",
            unit="ANCHOR",
            trials=trials,
            alpha=alpha,
            rejections=counters["ab"],
            nominal=alpha,
            note=inflation,
        ),
    }


def simulate_power(
    model: PairedBinaryModel,
    profile: ClusterProfile,
    *,
    replicates: ReplicateModel = DETERMINISTIC_SOLVER,
    cluster_icc: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
    trials: int = 400,
    permutations: int = 499,
    seed: int = 20260908,
) -> SimulationResult:
    """Brute-force power of the PREREGISTERED cluster permutation test at a known true Δ.

    This is the check on :func:`analytic_power`: the analytic number is a normal approximation to
    a discrete permutation test, and an approximation that is never compared against the thing it
    approximates is a claim, not a calculation.
    """

    deltas, groups = simulate_anchor_deltas(
        model,
        profile,
        trials=trials,
        replicates=replicates,
        cluster_icc=cluster_icc,
        seed=seed,
    )
    rng = np.random.default_rng(seed + 7)
    rejections = sum(
        _permutation_p_value(row, groups, permutations=permutations, rng=rng) <= alpha
        for row in deltas
    )
    return SimulationResult(
        label=f"cluster permutation power at delta={model.delta}",
        unit="CLUSTER",
        trials=trials,
        alpha=alpha,
        rejections=int(rejections),
        nominal=None,
        note=(
            f"n_anchors={profile.n_anchors} n_clusters={profile.n_clusters} "
            f"cluster_icc={cluster_icc} k={replicates.replicates}"
        ),
    )


def design_summary(
    profile: ClusterProfile,
    *,
    baseline_rates: Sequence[float] = (0.10, 0.25, 0.40),
    cluster_iccs: Sequence[float] = (0.0, 0.2, 0.5),
    replicate_models: Sequence[ReplicateModel] = (DETERMINISTIC_SOLVER,),
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_TARGET_POWER,
) -> dict[str, Any]:
    """The MDE grid a null result is reported against (§9.5), as a plain JSON-able mapping."""

    rows: list[Mapping[str, Any]] = []
    for replicates in replicate_models:
        for baseline in baseline_rates:
            for icc in cluster_iccs:
                rows.append(
                    minimum_detectable_effect(
                        baseline,
                        profile,
                        replicates=replicates,
                        cluster_icc=icc,
                        alpha=alpha,
                        target_power=target_power,
                    ).to_dict()
                )
    return {
        "power_version": POWER_VERSION,
        "profile": profile.to_dict(),
        "alpha": alpha,
        "target_power": target_power,
        "mde_grid": rows,
    }
