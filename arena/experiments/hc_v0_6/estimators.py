"""Paired estimators for HC-V0.6's Δ(R_A, R_B), preregistered before any assay data exists.

Everything here is built on four primitives the project already owns and this module deliberately
does **not** re-implement:

============================================  ===================================================
reused                                        from
============================================  ===================================================
``mcnemar_exact``                             :mod:`arena.evaluation.landscape`
``clustered_paired_bootstrap``                :mod:`arena.experiments.fitness_v4`
``clopper_pearson`` / ``holm_adjust``         :mod:`arena.experiments.rendered_prompt_adversary`
============================================  ===================================================

The one estimator that is new is the **cluster-level permutation null**, because the project had
only a within-family label permutation for an unpaired max-over-rules statistic, which is a
different test.

The three decisions this module freezes
---------------------------------------

**0. What the booleans mean.**  Every ``True`` in a :class:`PairedCells` is one
``KERNEL_ACCEPTED_STATE_CHANGE`` event -- Lean accepted the Solver's first action *and* that
action closed the task or moved the backend state.  An accepted no-op is ``False``, and a harness
failure is not a cell at all (:meth:`CellTable.drop_harness_failures`).  Everything below says
"rate" for the rate of that event; none of it says, or means, "the elaborator did not complain".

**1. The estimand is the anchor-averaged Δ.**  With ``k`` replicates per cell the per-anchor
event rate is ``p̂ = events / k`` and

    Δ̂ = (1/n) Σ_i ( p̂_{i,B} − p̂_{i,A} ).

Anchor-averaging, not cell-pooling, is what "paired within anchor" means, and it is the only
weighting that is stable when an anchor loses a replicate to a harness failure.  It uses all ``k``
replicates and is unbiased for the mean per-anchor effect.

**2. Exact McNemar collapses ``k > 1`` to the first replicate.**  McNemar's exactness rests on the
discordant pairs being independent ``Bernoulli(½)`` under the null.  Pooling ``n·k`` replicate
pairs breaks that badly -- replicates inside one anchor are strongly dependent, so the test
becomes anti-conservative (:data:`ReplicateCollapse.POOLED_REPLICATE_PAIRS` exists only so the
size of that error can be measured, never to be reported).  Majority / any / all collapse keeps
the pairs independent but silently changes the estimand from ``p_event`` to a functional of the
replicate distribution, which is not the preregistered primary endpoint.  Taking the lowest-indexed
replicate preserves the estimand and the exactness with respect to replicates.  It is still
anti-conservative with respect to *clustering*, which is precisely why it is reported as the design
brief's nominal paired method and is **not** the test that decides anything.

**3. The preregistered p-value is the cluster-level permutation p-value.**  Under the sharp null
"the arm label changes no cell's outcome", swapping the labels of an anchor negates that anchor's
paired difference.  Flipping anchors independently (:data:`PermutationUnit.ANCHOR` -- the literal
"shuffle arm labels within anchor") is only valid when the anchors are independent; theorems in
one mathlib file are not (manual §30.6), and independent flipping then understates the variance of
Δ̂.  Flipping a whole **file** at once (:data:`PermutationUnit.CLUSTER`) is invariant under
arbitrary within-file dependence and is the preregistered test.  Both are computed and reported;
the anchor-level one is a negative control whose measured type-I inflation is the evidence for
this choice (``docs/HC_V0_6_ANALYSIS_PLAN.md`` §7).

The same reasoning applies to the interval: :data:`ResampleUnit.CLUSTER` resamples files and is the
preregistered CI; :data:`ResampleUnit.ANCHOR` resamples anchors and is the negative control.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from arena.evaluation.landscape import mcnemar_exact
from arena.experiments.fitness_v4 import clustered_paired_bootstrap
from arena.experiments.hc_v0_6.schema import (
    Arm,
    CellOutcome,
    CellTable,
    DesignViolation,
    PairedCells,
    extract_pair,
)
from arena.experiments.rendered_prompt_adversary import clopper_pearson, holm_adjust

__all__ = [
    "ALPHA",
    "BOOTSTRAP_RESAMPLES",
    "Comparison",
    "FAMILY_ARMS",
    "HolmDecision",
    "IdentityControlUnavailable",
    "McNemarResult",
    "PERMUTATIONS",
    "PREREGISTERED_FAMILY",
    "PairedEffect",
    "PermutationResult",
    "PermutationUnit",
    "ReplicateCollapse",
    "ResampleUnit",
    "SEED",
    "ArmMarginal",
    "anchor_deltas",
    "arm_marginal",
    "delta_hat",
    "estimate_pair",
    "exact_mcnemar",
    "family_widening_guard",
    "holm_family",
    "pair_for",
    "paired_bootstrap_ci",
    "permutation_null",
    "split_half_identity",
]

#: Frozen inference constants.  Changing one of these changes the preregistration.
ALPHA: Final = 0.05
BOOTSTRAP_RESAMPLES: Final = 4000
PERMUTATIONS: Final = 20_000
SEED: Final = 20260908

FloatArray = NDArray[np.float64]


# --------------------------------------------------------------------------------- replicates


class ReplicateCollapse(StrEnum):
    """How ``k`` replicates become the one binary outcome per cell that McNemar needs."""

    #: PREREGISTERED.  The lowest-indexed replicate.  Preserves the estimand; exact w.r.t.
    #: replicates; wastes ``k - 1`` draws, which is the price of exactness.
    FIRST_REPLICATE = "FIRST_REPLICATE"
    #: Majority of the ``k`` draws, ties resolved to "no event".  Changes the estimand.
    MAJORITY = "MAJORITY"
    #: The endpoint fired on at least one replicate.  Changes the estimand (upward).
    ANY = "ANY"
    #: The endpoint fired on every replicate.  Changes the estimand (downward).
    ALL = "ALL"
    #: Pair replicate ``j`` of one arm with replicate ``j`` of the other, giving ``n·k`` pairs.
    #: ANTI-CONSERVATIVE under replicate dependence.  Available so the size of that error can be
    #: measured; never to be reported as a result.
    POOLED_REPLICATE_PAIRS = "POOLED_REPLICATE_PAIRS"

    @property
    def preserves_estimand(self) -> bool:
        return self in {ReplicateCollapse.FIRST_REPLICATE, ReplicateCollapse.POOLED_REPLICATE_PAIRS}

    @property
    def reportable(self) -> bool:
        return self is ReplicateCollapse.FIRST_REPLICATE


class ResampleUnit(StrEnum):
    """What the bootstrap resamples."""

    #: PREREGISTERED.  mathlib files, with replacement (manual §30.6).
    CLUSTER = "CLUSTER"
    #: Anchors, ignoring the file structure.  A NEGATIVE CONTROL: too narrow whenever ICC > 0.
    ANCHOR = "ANCHOR"


class PermutationUnit(StrEnum):
    """At what level arm labels are exchanged under the null."""

    #: PREREGISTERED.  A whole file's labels flip together; valid under arbitrary within-file
    #: dependence.
    CLUSTER = "CLUSTER"
    #: Each anchor flips independently.  A NEGATIVE CONTROL: anti-conservative when ICC > 0.
    ANCHOR = "ANCHOR"


# ----------------------------------------------------------------------------------- effects


def anchor_rates(pair: PairedCells) -> tuple[FloatArray, FloatArray]:
    """Per-anchor endpoint rates ``(p̂_A, p̂_B)``, each ``KERNEL_ACCEPTED_STATE_CHANGE / k``."""

    a = np.asarray(pair.a_success, dtype=np.float64) / np.asarray(pair.a_trials, dtype=np.float64)
    b = np.asarray(pair.b_success, dtype=np.float64) / np.asarray(pair.b_trials, dtype=np.float64)
    return a, b


def anchor_deltas(pair: PairedCells) -> FloatArray:
    """The per-anchor paired difference ``D_i = p̂_{i,B} − p̂_{i,A}``."""

    a, b = anchor_rates(pair)
    return np.asarray(b - a, dtype=np.float64)


def delta_hat(pair: PairedCells) -> float:
    """The point estimate: the anchor-averaged Δ."""

    return float(anchor_deltas(pair).mean())


# ----------------------------------------------------------------------------- exact McNemar


@dataclass(frozen=True, slots=True)
class McNemarResult:
    collapse: ReplicateCollapse
    n_pairs: int
    n10: int  # endpoint fired under arm A, not under arm B
    n01: int  # endpoint fired under arm B, not under arm A
    p_value: float
    reportable: bool
    note: str

    @property
    def n_discordant(self) -> int:
        return self.n10 + self.n01

    def to_dict(self) -> dict[str, Any]:
        return {
            "collapse": str(self.collapse.value),
            "n_pairs": self.n_pairs,
            "n10": self.n10,
            "n01": self.n01,
            "n_discordant": self.n_discordant,
            "p_value": self.p_value,
            "reportable": self.reportable,
            "note": self.note,
        }


def _collapse_binary(
    success: Sequence[int], trials: Sequence[int], first: Sequence[bool], how: ReplicateCollapse
) -> list[bool]:
    if how is ReplicateCollapse.FIRST_REPLICATE:
        return list(first)
    if how is ReplicateCollapse.MAJORITY:
        return [2 * s > t for s, t in zip(success, trials, strict=True)]
    if how is ReplicateCollapse.ANY:
        return [s > 0 for s in success]
    if how is ReplicateCollapse.ALL:
        return [s == t for s, t in zip(success, trials, strict=True)]
    raise DesignViolation(f"{how} is not a per-anchor collapse")


def exact_mcnemar(
    pair: PairedCells, *, collapse: ReplicateCollapse = ReplicateCollapse.FIRST_REPLICATE
) -> McNemarResult:
    """Exact (binomial) McNemar on the discordant pairs, via the project's ``mcnemar_exact``.

    Anti-conservative under clustering by construction -- it treats anchors as independent.  It is
    reported because the design brief names it, never used to decide anything; the deciding test is
    :func:`permutation_null` at :data:`PermutationUnit.CLUSTER`.
    """

    if collapse is ReplicateCollapse.POOLED_REPLICATE_PAIRS:
        k = pair.balanced_replicates
        if k is None:
            raise DesignViolation("POOLED_REPLICATE_PAIRS needs a balanced replicate count")
        # Replicate j of one arm is paired with replicate j of the other, giving n*k pairs.
        n10 = 0
        n01 = 0
        for a_draws, b_draws in zip(pair.a_outcomes, pair.b_outcomes, strict=True):
            for a, b in zip(a_draws, b_draws, strict=True):
                n10 += a and not b
                n01 += b and not a
        return McNemarResult(
            collapse=collapse,
            n_pairs=pair.n_anchors * k,
            n10=n10,
            n01=n01,
            p_value=mcnemar_exact(n10, n01),
            reportable=False,
            note=(
                "pooled replicate pairs: anti-conservative under replicate dependence; "
                "diagnostic only"
            ),
        )
    left = _collapse_binary(pair.a_success, pair.a_trials, pair.a_first, collapse)
    right = _collapse_binary(pair.b_success, pair.b_trials, pair.b_first, collapse)
    n10 = sum(a and not b for a, b in zip(left, right, strict=True))
    n01 = sum(b and not a for a, b in zip(left, right, strict=True))
    note = (
        "nominal: treats anchors as independent, so anti-conservative under file clustering"
        if collapse.reportable
        else f"{collapse.value} changes the estimand away from p_event; diagnostic only"
    )
    return McNemarResult(
        collapse=collapse,
        n_pairs=pair.n_anchors,
        n10=n10,
        n01=n01,
        p_value=mcnemar_exact(n10, n01),
        reportable=collapse.reportable,
        note=note,
    )


# -------------------------------------------------------------------------------- bootstrap


def paired_bootstrap_ci(
    pair: PairedCells,
    *,
    unit: ResampleUnit = ResampleUnit.CLUSTER,
    seed: int = SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    """95% percentile bootstrap interval for Δ, resampling ``unit`` with replacement.

    Delegates to the project's frozen :func:`arena.experiments.fitness_v4.clustered_paired_bootstrap`;
    the only difference between the preregistered interval and its negative control is which label
    is handed in as the resampling group.  That function hard-codes the 2.5 / 97.5 percentiles, so
    this interval is 95% and :data:`ALPHA` is not a parameter here.
    """

    deltas = [float(value) for value in anchor_deltas(pair)]
    groups = list(pair.cluster_ids if unit is ResampleUnit.CLUSTER else pair.anchor_ids)
    return clustered_paired_bootstrap(deltas, groups, seed=seed, resamples=resamples)


# ------------------------------------------------------------------------------ permutation


@dataclass(frozen=True, slots=True)
class PermutationResult:
    unit: PermutationUnit
    permutations: int
    delta: float
    p_value: float
    null_mean: float
    null_sd: float
    null_quantiles: tuple[float, float]
    reportable: bool
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit": str(self.unit.value),
            "permutations": self.permutations,
            "delta": self.delta,
            "p_value": self.p_value,
            "null_mean": self.null_mean,
            "null_sd": self.null_sd,
            "null_quantiles_2p5_97p5": list(self.null_quantiles),
            "reportable": self.reportable,
            "note": self.note,
        }


def _flip_matrix(
    rng: np.random.Generator, permutations: int, deltas: FloatArray, groups: NDArray[np.int64]
) -> FloatArray:
    """``permutations × n`` matrix of ±1 arm-label flips, constant within each group."""

    n_groups = int(groups.max()) + 1
    signs = rng.integers(0, 2, size=(permutations, n_groups)).astype(np.float64) * 2.0 - 1.0
    return np.asarray(signs[:, groups] * deltas[None, :], dtype=np.float64)


def permutation_null(
    pair: PairedCells,
    *,
    unit: PermutationUnit = PermutationUnit.CLUSTER,
    permutations: int = PERMUTATIONS,
    seed: int = SEED,
) -> PermutationResult:
    """Empirical null for Δ under exchange of arm labels, and its two-sided p-value.

    Swapping the two arms at an anchor negates that anchor's paired difference, so the label
    permutation is a sign flip.  At :data:`PermutationUnit.CLUSTER` a whole mathlib file flips
    together; at :data:`PermutationUnit.ANCHOR` each anchor flips on its own.

    The p-value is ``(1 + #{|T*| >= |T_obs|}) / (B + 1)``: the observed value is included in the
    null, which is what makes the p-value valid at finite ``B`` rather than merely approximate.
    """

    if permutations < 1:
        raise DesignViolation("permutations must be at least 1")
    deltas = anchor_deltas(pair)
    observed = float(deltas.mean())
    labels = pair.cluster_ids if unit is PermutationUnit.CLUSTER else pair.anchor_ids
    lookup = {label: index for index, label in enumerate(sorted(set(labels)))}
    groups = np.asarray([lookup[label] for label in labels], dtype=np.int64)
    rng = np.random.default_rng(seed)
    draws = _flip_matrix(rng, permutations, deltas, groups).mean(axis=1)
    tolerance = 1e-12
    at_least_as_extreme = int(np.count_nonzero(np.abs(draws) >= abs(observed) - tolerance))
    p_value = (1.0 + at_least_as_extreme) / (permutations + 1.0)
    lo, hi = (float(value) for value in np.quantile(draws, [0.025, 0.975]))
    return PermutationResult(
        unit=unit,
        permutations=permutations,
        delta=observed,
        p_value=float(min(1.0, p_value)),
        null_mean=float(draws.mean()),
        null_sd=float(draws.std(ddof=1)) if permutations > 1 else 0.0,
        null_quantiles=(lo, hi),
        reportable=unit is PermutationUnit.CLUSTER,
        note=(
            "cluster sign-flip: exact under the sharp null for arbitrary within-file dependence"
            if unit is PermutationUnit.CLUSTER
            else "anchor sign-flip: anti-conservative when anchors within a file are dependent"
        ),
    )


# --------------------------------------------------------------------------- arm marginals


@dataclass(frozen=True, slots=True)
class ArmMarginal:
    """One arm's marginal ``KERNEL_ACCEPTED_STATE_CHANGE`` rate, with an exact and an
    inferential interval.

    ``n_events`` counts endpoint events, not elaborator acceptances: an accepted no-op is not
    counted here any more than a rejection is.
    """

    arm: Arm
    n_cells: int
    n_events: int
    n_anchors: int
    n_clusters: int
    #: Cell-pooled rate ``events / cells``.
    rate: float
    #: Anchor-averaged rate; the quantity Δ is a difference of.
    anchor_averaged_rate: float
    #: Exact Clopper-Pearson on the cell counts.  DESCRIPTIVE ONLY: it assumes independent
    #: Bernoulli cells, which replicates inside an anchor and anchors inside a file are not, so it
    #: is too narrow.  Reported because §30.3 asks for the marginal rate's exact interval; never
    #: used to decide anything.
    clopper_pearson95: tuple[float, float]
    #: Cluster bootstrap on the anchor-averaged rate.  The inferential interval.
    cluster_bootstrap95: tuple[float, float]

    @property
    def naive_interval_width(self) -> float:
        return self.clopper_pearson95[1] - self.clopper_pearson95[0]

    @property
    def cluster_interval_width(self) -> float:
        return self.cluster_bootstrap95[1] - self.cluster_bootstrap95[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": str(self.arm.value),
            "n_cells": self.n_cells,
            "n_events": self.n_events,
            "n_anchors": self.n_anchors,
            "n_clusters": self.n_clusters,
            "rate": self.rate,
            "anchor_averaged_rate": self.anchor_averaged_rate,
            "clopper_pearson95": list(self.clopper_pearson95),
            "cluster_bootstrap95": list(self.cluster_bootstrap95),
            "clopper_pearson_note": (
                "exact under independent Bernoulli cells; too narrow here because replicates and "
                "same-file anchors are dependent -- descriptive only"
            ),
        }


def arm_marginal(
    table: CellTable,
    arm: Arm,
    *,
    seed: int = SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> ArmMarginal:
    """Marginal endpoint rate for one arm, with Clopper-Pearson and a cluster bootstrap.

    Harness-decided cells are excluded, exactly as they are in
    :func:`~arena.experiments.hc_v0_6.schema.extract_pair`: spec §4 makes ``ENVIRONMENT_ERROR``
    separately typed and never a mathematical zero, so counting one in the denominator would
    depress the arm's rate for a reason that has nothing to do with the model
    (``docs/HC_V0_6_REDTEAM.md`` RT-V06-01).  ``n_cells`` is therefore the *analysable* cell count;
    what was dropped is reported by :meth:`CellTable.harness_failures_by_arm`.
    """

    rows = tuple(row for row in table.rows_for(arm) if row.analysable)
    if not rows:
        raise DesignViolation(f"no analysable rows for arm {arm.value}")
    per_anchor: dict[str, list[bool]] = {}
    cluster_of: dict[str, str] = {}
    for row in rows:
        per_anchor.setdefault(row.anchor_id, []).append(row.kernel_accepted_state_change)
        cluster_of[row.anchor_id] = row.cluster_id
    anchors = sorted(per_anchor)
    rates = [sum(per_anchor[a]) / len(per_anchor[a]) for a in anchors]
    clusters = [cluster_of[a] for a in anchors]
    n_cells = len(rows)
    n_events = sum(row.kernel_accepted_state_change for row in rows)
    return ArmMarginal(
        arm=arm,
        n_cells=n_cells,
        n_events=n_events,
        n_anchors=len(anchors),
        n_clusters=len(set(clusters)),
        rate=n_events / n_cells,
        anchor_averaged_rate=sum(rates) / len(rates),
        clopper_pearson95=clopper_pearson(n_events, n_cells, ALPHA),
        cluster_bootstrap95=clustered_paired_bootstrap(
            rates, clusters, seed=seed, resamples=resamples
        ),
    )


# ------------------------------------------------------------------------ one full comparison


class Comparison(StrEnum):
    """The **only** four hypotheses HC-V0.6 tests.  The family may not be widened.

    Four, not three: design brief §9.4 adds ``R_A_PRIME`` and with it the C1b byte-perturbation
    control, because ``R_ABLATED`` proves the pipeline is causally connected to the outcome but
    says nothing about sensitivity at the scale a representation change plausibly operates.
    """

    PRIMARY_RB_VS_RA = "PRIMARY_RB_VS_RA"
    #: ``R_A`` against ``R_A``: the runtime-noise floor, built inside ``R_A`` from its own
    #: replicates (design brief §9.2).  Degenerate — exactly zero — under a deterministic Solver.
    C1_IDENTITY = "C1_IDENTITY"
    #: ``R_A`` against the whitespace-perturbed ``R_A_PRIME``: bytes change, structure does not.
    C1B_WHITESPACE = "C1B_WHITESPACE"
    C2_ABLATION = "C2_ABLATION"

    @property
    def is_control(self) -> bool:
        return self is not Comparison.PRIMARY_RB_VS_RA


#: Frozen family for the Holm correction (design brief §9.4: "Holm's family widens to four").
#:
#: The correction applies to the **effect claims**.  The calibration gates in
#: :mod:`arena.experiments.hc_v0_6.calibration` deliberately read the *uncorrected* control
#: p-values, because Holm moves a safety gate in the direction that protects the headline result
#: from its own instrument (``docs/HC_V0_6_PREREGISTRATION.md`` §5).
PREREGISTERED_FAMILY: Final[tuple[Comparison, ...]] = (
    Comparison.PRIMARY_RB_VS_RA,
    Comparison.C1_IDENTITY,
    Comparison.C1B_WHITESPACE,
    Comparison.C2_ABLATION,
)

#: Which arms each family member contrasts, as ``(reference, variant)``.  Δ is variant − reference.
#: ``C1_IDENTITY`` contrasts ``R_A`` with itself; it is the one member that is not extracted by
#: :func:`~arena.experiments.hc_v0_6.schema.extract_pair` but by :func:`split_half_identity`.
FAMILY_ARMS: Final[Mapping[Comparison, tuple[Arm, Arm]]] = {
    Comparison.PRIMARY_RB_VS_RA: (Arm.R_A, Arm.R_B),
    Comparison.C1_IDENTITY: (Arm.R_A, Arm.R_A),
    Comparison.C1B_WHITESPACE: (Arm.R_A, Arm.R_A_PRIME),
    Comparison.C2_ABLATION: (Arm.R_A, Arm.R_ABLATED),
}


class IdentityControlUnavailable(DesignViolation):
    """C1 cannot be built from ``R_A``'s replicates because there are fewer than two of them."""


def split_half_identity(table: CellTable, *, arm: Arm = Arm.R_A) -> PairedCells:
    """C1: split one arm's replicates in half and pair the halves (design brief §9.2).

    The split is by replicate index — first ``⌊k/2⌋`` against the next ``⌊k/2⌋``, odd replicate
    dropped — because a deterministic rule is preregisterable and the replicate index carries no
    information.  The estimator, cluster unit and test are then identical to the headline's; only
    the number of replicates per side is not, so C1 **over-states** the noise floor by roughly a
    factor of two in variance.  That is the conservative direction (it makes the assay easier to
    declare broken) and it is why the construction is acceptable
    (``docs/HC_V0_6_PREREGISTRATION.md`` §4.3).

    **Under a call-for-call deterministic Solver this cannot be built**: ``k = 1`` is then the
    correct design and there is no second draw to split off.  The preregistration's §4.3 branch
    applies — C1 must be run as explicit extra ``R_A`` cells — and those cells are byte-identical
    prompts, so Δ is exactly zero *by construction*.  A zero C1 in that world demonstrates the
    Solver is deterministic; it is not evidence that the analysis pipeline can detect anything.
    """

    rows = tuple(row for row in table.rows_for(arm) if row.analysable)
    if not rows:
        raise DesignViolation(f"no analysable rows for arm {arm.value}")
    by_anchor: dict[str, list[CellOutcome]] = defaultdict(list)
    for row in rows:
        by_anchor[row.anchor_id].append(row)
    cluster_of = table.cluster_of
    anchors: list[str] = []
    clusters: list[str] = []
    left: list[tuple[bool, ...]] = []
    right: list[tuple[bool, ...]] = []
    short = [anchor for anchor, cells in by_anchor.items() if len(cells) < 2]
    if short:
        raise IdentityControlUnavailable(
            f"{arm.value} carries fewer than 2 replicates at {len(short)} anchor(s) "
            f"(e.g. {sorted(short)[:3]}), so the C1 identity control cannot be split out of it; "
            "under a deterministic Solver run C1 as explicit extra cells and report it as "
            "degenerate (preregistration §4.3)"
        )
    for anchor in sorted(by_anchor):
        cells = sorted(by_anchor[anchor], key=lambda row: row.replicate_index)
        half = len(cells) // 2
        anchors.append(anchor)
        clusters.append(cluster_of[anchor])
        left.append(tuple(row.kernel_accepted_state_change for row in cells[:half]))
        right.append(tuple(row.kernel_accepted_state_change for row in cells[half : 2 * half]))
    return PairedCells(
        arm_a=arm,
        arm_b=arm,
        anchor_ids=tuple(anchors),
        cluster_ids=tuple(clusters),
        a_outcomes=tuple(left),
        b_outcomes=tuple(right),
    )


def pair_for(table: CellTable, comparison: Comparison) -> PairedCells:
    """The paired structure of one family member, by the rule that member is defined with."""

    if comparison is Comparison.C1_IDENTITY:
        return split_half_identity(table, arm=Arm.R_A)
    arm_a, arm_b = FAMILY_ARMS[comparison]
    return extract_pair(table, arm_a, arm_b)


@dataclass(frozen=True, slots=True)
class PairedEffect:
    """Everything HC-V0.6 reports about one comparison, raw counts included (§30.7)."""

    comparison: Comparison
    arm_a: Arm
    arm_b: Arm
    n_anchors: int
    n_clusters: int
    replicates: int | None
    rate_a: float
    rate_b: float
    delta: float
    delta_ci95: tuple[float, float]
    delta_ci95_anchor_naive: tuple[float, float]
    mcnemar: McNemarResult
    permutation: PermutationResult
    permutation_anchor_naive: PermutationResult
    marginal_a: ArmMarginal
    marginal_b: ArmMarginal

    @property
    def p_value(self) -> float:
        """The preregistered p-value: the cluster-level permutation p-value."""

        return self.permutation.p_value

    def equivalent_within(self, bound: float) -> bool:
        """Whether the preregistered CI lies entirely inside ``±bound``."""

        if bound <= 0.0:
            raise DesignViolation("an equivalence bound must be positive")
        return -bound <= self.delta_ci95[0] and self.delta_ci95[1] <= bound

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison": str(self.comparison.value),
            "arm_a": str(self.arm_a.value),
            "arm_b": str(self.arm_b.value),
            "n_anchors": self.n_anchors,
            "n_clusters": self.n_clusters,
            "replicates": self.replicates,
            "rate_a": self.rate_a,
            "rate_b": self.rate_b,
            "delta": self.delta,
            "delta_ci95": list(self.delta_ci95),
            "delta_ci95_anchor_naive": list(self.delta_ci95_anchor_naive),
            "p_value_preregistered": self.p_value,
            "mcnemar": self.mcnemar.to_dict(),
            "permutation": self.permutation.to_dict(),
            "permutation_anchor_naive": self.permutation_anchor_naive.to_dict(),
            "marginal_a": self.marginal_a.to_dict(),
            "marginal_b": self.marginal_b.to_dict(),
        }


def estimate_pair(
    table: CellTable,
    comparison: Comparison,
    *,
    seed: int = SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
    permutations: int = PERMUTATIONS,
    collapse: ReplicateCollapse = ReplicateCollapse.FIRST_REPLICATE,
) -> PairedEffect:
    """Run every preregistered estimator, plus both negative controls, for one comparison."""

    arm_a, arm_b = FAMILY_ARMS[comparison]
    pair = pair_for(table, comparison)
    rate_a, rate_b = (float(values.mean()) for values in anchor_rates(pair))
    return PairedEffect(
        comparison=comparison,
        arm_a=arm_a,
        arm_b=arm_b,
        n_anchors=pair.n_anchors,
        n_clusters=pair.n_clusters,
        replicates=pair.balanced_replicates,
        rate_a=rate_a,
        rate_b=rate_b,
        delta=delta_hat(pair),
        delta_ci95=paired_bootstrap_ci(
            pair, unit=ResampleUnit.CLUSTER, seed=seed, resamples=resamples
        ),
        delta_ci95_anchor_naive=paired_bootstrap_ci(
            pair, unit=ResampleUnit.ANCHOR, seed=seed, resamples=resamples
        ),
        mcnemar=exact_mcnemar(pair, collapse=collapse),
        permutation=permutation_null(
            pair, unit=PermutationUnit.CLUSTER, permutations=permutations, seed=seed
        ),
        permutation_anchor_naive=permutation_null(
            pair, unit=PermutationUnit.ANCHOR, permutations=permutations, seed=seed + 1
        ),
        marginal_a=arm_marginal(table, arm_a, seed=seed, resamples=resamples),
        marginal_b=arm_marginal(table, arm_b, seed=seed + 2, resamples=resamples),
    )


# ------------------------------------------------------------------------------ multiplicity


class FamilyWidened(DesignViolation):
    """A comparison outside the preregistered family reached the multiplicity correction."""


def family_widening_guard(members: Sequence[Comparison]) -> None:
    """Raise unless ``members`` is exactly the preregistered family, no more and no fewer.

    Holm's guarantee is over a family fixed in advance.  Adding a fifth comparison after seeing
    the data inflates the family-wise error rate; dropping one deflates the corrected p-values of
    the survivors.  Both are silent, so both are made loud here.
    """

    seen = list(members)
    if len(set(seen)) != len(seen):
        raise FamilyWidened(f"duplicate comparisons: {[str(m.value) for m in seen]}")
    if set(seen) != set(PREREGISTERED_FAMILY):
        missing = sorted(str(m.value) for m in set(PREREGISTERED_FAMILY) - set(seen))
        extra = sorted(str(m.value) for m in set(seen) - set(PREREGISTERED_FAMILY))
        raise FamilyWidened(
            f"the Holm family is frozen at {[str(m.value) for m in PREREGISTERED_FAMILY]}; "
            f"missing={missing} extra={extra}"
        )


@dataclass(frozen=True, slots=True)
class HolmDecision:
    comparison: Comparison
    p_value: float
    p_holm: float
    reject: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison": str(self.comparison.value),
            "p_value": self.p_value,
            "p_holm": self.p_holm,
            "reject": self.reject,
        }


def holm_family(
    p_values: Mapping[Comparison, float], *, alpha: float = ALPHA
) -> dict[Comparison, HolmDecision]:
    """Holm step-down across the frozen family, via the project's ``holm_adjust``.

    The family is checked, not assumed: :func:`family_widening_guard` runs first, so a fifth
    hypothesis cannot be slipped in after the fact.
    """

    members = list(p_values)
    family_widening_guard(members)
    ordered = list(PREREGISTERED_FAMILY)
    raw = [float(p_values[comparison]) for comparison in ordered]
    if any(not 0.0 <= value <= 1.0 for value in raw):
        raise DesignViolation(f"p-values must lie in [0, 1]: {raw}")
    adjusted = holm_adjust(raw)
    return {
        comparison: HolmDecision(
            comparison=comparison,
            p_value=value,
            p_holm=holm,
            reject=holm <= alpha,
        )
        for comparison, value, holm in zip(ordered, raw, adjusted, strict=True)
    }
