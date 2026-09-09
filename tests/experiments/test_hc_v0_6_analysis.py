"""Offline tests for the HC-V0.6 analysis package.

Nothing here calls a model, Lean, or the network.  Every check is against an independent
computation (a hand-evaluated binomial tail, a closed-form beta quantile, a brute-force
simulation with a known ground truth) or a structural property (monotonicity, a refusal that
must fire, determinism of a seeded result).

Two of these are not unit tests but **measurements**, and they are the reason the file exists:

* ``test_type_i_calibration_*`` measures the realised false-positive rate of the preregistered
  cluster test and of the naive row-level bootstrap on the SAME clustered null data.  The gap
  between them is the empirical case for clustering by mathlib file (manual §30.6); it is
  measured, not asserted.
* ``test_simulated_power_matches_analytic_*`` measures the power of the actual permutation test
  against the normal approximation the MDE is computed from.  An approximation never compared
  against the thing it approximates is a claim, not a calculation.

Simulation sizes are cut so that the whole file stays inside a few seconds; the shipped defaults
(``BOOTSTRAP_RESAMPLES = 4000``, ``PERMUTATIONS = 20000``) are unaffected.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np
import pytest

from arena.evolution.record import InterventionClass
from arena.experiments.fitness_v4 import clustered_paired_bootstrap
from arena.experiments.hc_v0_6 import (
    ALPHA_IDENTITY,
    DETERMINISTIC_SOLVER,
    FAMILY_ARMS,
    PREREGISTERED_FAMILY,
    Arm,
    AssayBroken,
    AssayStatus,
    Attribution,
    CellOutcome,
    CellTable,
    ClusterProfile,
    Comparison,
    DesignViolation,
    IdentityControlUnavailable,
    Outcome,
    PairedBinaryModel,
    PairedCells,
    ParseStatus,
    ReplicateCollapse,
    ReplicateModel,
    StepResult,
    analytic_power,
    arm_marginal,
    bootstrap_ci,
    calibrate,
    delta_hat,
    estimate_pair,
    exact_mcnemar,
    family_widening_guard,
    holm_family,
    minimum_detectable_effect,
    permutation_null,
    required_anchors,
    simulate_anchor_deltas,
    simulate_power,
    simulate_type_i,
    split_half_identity,
)
from arena.experiments.hc_v0_6 import power as power_module
from arena.experiments.hc_v0_6.calibration import (
    ALPHA_BYTE_NULL,
    ALPHA_SENSITIVITY,
    CERTIFICATION_GATES,
    GateDirection,
    false_certification_bound,
)
from arena.experiments.hc_v0_6.estimators import ALPHA, PermutationUnit, ResampleUnit
from arena.experiments.hc_v0_6.schema import (
    ENDPOINT_EVENT_RESULTS,
    PRIMARY_ENDPOINT,
    extract_pair,
)

# Reduced inference budgets: enough resolution for every assertion below, fast enough to run in CI.
FAST_RESAMPLES = 400
FAST_PERMUTATIONS = 999
TRIALS = 300
SIM_PERMUTATIONS = 399

#: The REBUILT bank (content hash f13ffee5...): 1127 anchors, 393 theorems, 330 mathlib files.
#: Sizes {1:10, 2:10, 3:260, 4:3, 5:6, 6:33, 7:1, 9:3, 10:2, 11:1, 12:1}; re-derivation 1127/1127.
#: Typed here so the offline tests do not need the artefact, and asserted equal to the artefact by
#: `test_cluster_profile_matches_the_built_anchor_bank_when_it_exists`, which is what stops this
#: constant from going stale the way its 223/75 predecessor did.
REALISED_HISTOGRAM: dict[int, int] = {
    1: 10,
    2: 10,
    3: 260,
    4: 3,
    5: 6,
    6: 33,
    7: 1,
    9: 3,
    10: 2,
    11: 1,
    12: 1,
}
REALISED_SIZES: tuple[int, ...] = tuple(
    size for size, count in REALISED_HISTOGRAM.items() for _ in range(count)
)
REALISED = ClusterProfile.from_sizes(REALISED_SIZES, label="hc-v0.6-realised-bank")
#: Sum of squared cluster sizes, so `m_A = SUM_M_SQUARED / n` is spelled out rather than trusted.
SUM_M_SQUARED = sum(size * size for size in REALISED_SIZES)


# --------------------------------------------------------------------------------- builders


def _pair(
    a_outcomes: Sequence[Sequence[bool]],
    b_outcomes: Sequence[Sequence[bool]],
    clusters: Sequence[str] | None = None,
    *,
    arm_a: Arm = Arm.R_A,
    arm_b: Arm = Arm.R_B,
) -> PairedCells:
    n = len(a_outcomes)
    return PairedCells(
        arm_a=arm_a,
        arm_b=arm_b,
        anchor_ids=tuple(f"a{index:03d}" for index in range(n)),
        cluster_ids=tuple(clusters if clusters is not None else [f"c{i:03d}" for i in range(n)]),
        a_outcomes=tuple(tuple(bool(v) for v in row) for row in a_outcomes),
        b_outcomes=tuple(tuple(bool(v) for v in row) for row in b_outcomes),
    )


def _discordant_pair(n10: int, n01: int, concordant: int = 0) -> PairedCells:
    """``n10`` anchors where only A is accepted, ``n01`` where only B is, plus concordant ones."""

    a = [[True]] * n10 + [[False]] * n01 + [[True]] * concordant
    b = [[False]] * n10 + [[True]] * n01 + [[True]] * concordant
    return _pair(a, b)


def _cell(
    anchor: str,
    cluster: str,
    arm: Arm,
    replicate: int,
    accepted: bool,
) -> CellOutcome:
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"thm::{anchor}",
        reelaboration_key=f"key::{anchor}",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=replicate,
        step_result=(
            StepResult.ACCEPTED_TRANSITION if accepted else StepResult.REJECTED_INVALID_ACTION
        ),
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=100,
        response_tokens=10,
        latency_ms=5,
        solver_digest="digest",
    )


def _table(
    outcomes: dict[Arm, Iterable[Iterable[bool]]],
    *,
    n_clusters: int,
    per_cluster: int,
) -> CellTable:
    """Build a balanced table: ``outcomes[arm][anchor]`` is that cell's replicate outcomes."""

    anchors = [
        (f"a{c:03d}_{i}", f"file{c:03d}") for c in range(n_clusters) for i in range(per_cluster)
    ]
    rows: list[CellOutcome] = []
    for arm, per_anchor in outcomes.items():
        for (anchor, cluster), draws in zip(anchors, per_anchor, strict=True):
            for index, accepted in enumerate(draws):
                rows.append(_cell(anchor, cluster, arm, index, accepted))
    return CellTable(rows)


# ------------------------------------------------------------------- shape of the design


def test_four_arms_each_with_its_own_renderer() -> None:
    assert [arm.value for arm in Arm] == ["R_A", "R_A_PRIME", "R_B", "R_ABLATED"]
    # Design brief §9.4: R_A_PRIME is a whitespace-perturbing renderer of its own, not a second
    # draw through R_A.  If this reverts, C1b stops being a byte-perturbation control.
    assert [arm.renderer_id for arm in Arm] == ["R_A", "R_A_PRIME", "R_B", "R_ABLATED"]
    assert Arm.R_ABLATED.intervention_class is InterventionClass.P_CHANGE
    assert all(
        arm.intervention_class is InterventionClass.R_ONLY
        for arm in Arm
        if arm is not Arm.R_ABLATED
    )


def test_holm_family_has_four_members_and_c1_is_the_identity_pair() -> None:
    assert len(PREREGISTERED_FAMILY) == 4
    assert FAMILY_ARMS[Comparison.C1_IDENTITY] == (Arm.R_A, Arm.R_A)
    assert FAMILY_ARMS[Comparison.C1B_WHITESPACE] == (Arm.R_A, Arm.R_A_PRIME)
    assert FAMILY_ARMS[Comparison.C2_ABLATION] == (Arm.R_A, Arm.R_ABLATED)
    assert set(FAMILY_ARMS) == set(PREREGISTERED_FAMILY)


# ------------------------------------------------------------ known answers: exact McNemar


@pytest.mark.parametrize(
    ("n10", "n01", "expected"),
    [
        # No discordant pairs: nothing to test, p = 1 by definition.
        (0, 0, 1.0),
        # n = 1, k = 0: 2 · P(X ≤ 0 | Bin(1, ½)) = 2 · 1/2.
        (1, 0, 1.0),
        # n = 5, k = 0: 2 · (1/32).
        (5, 0, 2.0 / 32.0),
        # n = 4, k = 1: 2 · (1 + 4)/16.
        (3, 1, 10.0 / 16.0),
        # n = 9, k = 1: 2 · (1 + 9)/512.
        (8, 1, 20.0 / 512.0),
        # n = 10, k = 2: 2 · (1 + 10 + 45)/1024.
        (8, 2, 112.0 / 1024.0),
        # Symmetric in its arguments.
        (2, 8, 112.0 / 1024.0),
    ],
)
def test_exact_mcnemar_matches_hand_computed_binomial_tails(
    n10: int, n01: int, expected: float
) -> None:
    pair = _pair([[True]], [[True]]) if n10 == n01 == 0 else _discordant_pair(n10, n01)
    result = exact_mcnemar(pair)
    assert result.n10 == n10
    assert result.n01 == n01
    assert result.p_value == pytest.approx(expected, abs=1e-12)
    assert result.reportable is True


def test_exact_mcnemar_uses_the_first_replicate_and_says_when_it_does_not() -> None:
    # Replicate 0 discordant, replicate 1 concordant: FIRST_REPLICATE must see the discordance.
    pair = _pair([[True, True]] * 6, [[False, True]] * 6)
    first = exact_mcnemar(pair, collapse=ReplicateCollapse.FIRST_REPLICATE)
    assert (first.n10, first.n01) == (6, 0)
    pooled = exact_mcnemar(pair, collapse=ReplicateCollapse.POOLED_REPLICATE_PAIRS)
    assert pooled.n_pairs == 12
    assert pooled.reportable is False
    assert exact_mcnemar(pair, collapse=ReplicateCollapse.ANY).reportable is False


# ------------------------------------------------------ known answers: Clopper-Pearson


def _marginal_table(accepted: int, total: int) -> CellTable:
    rows = [_cell(f"a{i:03d}", f"file{i // 3:03d}", Arm.R_A, 0, i < accepted) for i in range(total)]
    return CellTable(rows)


def test_clopper_pearson_matches_closed_forms_at_the_boundaries() -> None:
    # successes = 0  ->  [0, 1 - (alpha/2)^(1/n)];  successes = n  ->  [(alpha/2)^(1/n), 1].
    zero = arm_marginal(_marginal_table(0, 10), Arm.R_A, resamples=FAST_RESAMPLES)
    assert zero.clopper_pearson95[0] == 0.0
    assert zero.clopper_pearson95[1] == pytest.approx(1.0 - 0.025 ** (1.0 / 10.0), abs=1e-9)
    full = arm_marginal(_marginal_table(10, 10), Arm.R_A, resamples=FAST_RESAMPLES)
    assert full.clopper_pearson95[0] == pytest.approx(0.025 ** (1.0 / 10.0), abs=1e-9)
    assert full.clopper_pearson95[1] == 1.0


def test_clopper_pearson_matches_hand_solved_beta_quantiles_at_one_of_two() -> None:
    # Beta(1, 2) CDF is 1 - (1-x)^2  ->  lower = 1 - sqrt(0.975).
    # Beta(2, 1) CDF is x^2          ->  upper = sqrt(0.975).
    marginal = arm_marginal(_marginal_table(1, 2), Arm.R_A, resamples=FAST_RESAMPLES)
    assert marginal.clopper_pearson95[0] == pytest.approx(1.0 - math.sqrt(0.975), abs=1e-9)
    assert marginal.clopper_pearson95[1] == pytest.approx(math.sqrt(0.975), abs=1e-9)
    assert marginal.rate == 0.5


def test_clopper_pearson_is_labelled_descriptive_not_inferential() -> None:
    marginal = arm_marginal(_marginal_table(5, 12), Arm.R_A, resamples=FAST_RESAMPLES)
    assert "descriptive only" in marginal.to_dict()["clopper_pearson_note"]


# --------------------------------------------------------- estimators against known truth


def test_delta_hat_is_the_anchor_averaged_difference() -> None:
    pair = _pair([[True], [False], [False], [False]], [[True], [True], [False], [False]])
    assert delta_hat(pair) == pytest.approx(0.25)
    with_replicates = _pair([[True, False]] * 4, [[True, True]] * 4)
    assert delta_hat(with_replicates) == pytest.approx(0.5)


def test_permutation_null_recovers_a_known_delta_and_its_sign() -> None:
    pair = _discordant_pair(n10=0, n01=30, concordant=30)
    result = permutation_null(pair, permutations=FAST_PERMUTATIONS, seed=5)
    assert result.delta == pytest.approx(0.5)
    assert result.p_value < 0.01
    assert result.reportable is True
    null = permutation_null(_discordant_pair(15, 15, 30), permutations=FAST_PERMUTATIONS, seed=5)
    assert null.delta == pytest.approx(0.0)
    assert null.p_value == pytest.approx(1.0)


def test_permutation_p_value_is_valid_at_finite_b() -> None:
    # The observed statistic is in the null, so p >= 1 / (B + 1) always.
    pair = _discordant_pair(n10=0, n01=40)
    result = permutation_null(pair, permutations=FAST_PERMUTATIONS, seed=1)
    assert result.p_value >= 1.0 / (FAST_PERMUTATIONS + 1)


def test_fast_permutation_helper_is_the_shipped_permutation_test() -> None:
    """The simulator must measure the calibration of the shipped test, not of a look-alike."""

    rng_deltas = np.random.default_rng(3)
    deltas = rng_deltas.choice([-1.0, 0.0, 1.0], size=40, p=[0.2, 0.5, 0.3])
    groups = np.repeat(np.arange(10), 4)
    pair = _pair(
        [[bool(value < 0)] for value in deltas],
        [[bool(value > 0)] for value in deltas],
        clusters=[f"c{index:03d}" for index in groups],
    )
    shipped = permutation_null(
        pair, unit=PermutationUnit.CLUSTER, permutations=257, seed=99
    ).p_value
    fast = power_module._permutation_p_value(
        deltas, groups, permutations=257, rng=np.random.default_rng(99)
    )
    assert fast == pytest.approx(shipped, abs=1e-12)


def test_fast_bootstrap_agrees_with_the_shipped_cluster_bootstrap() -> None:
    rng = np.random.default_rng(17)
    deltas = rng.choice([-1.0, 0.0, 1.0], size=REALISED.n_anchors, p=[0.2, 0.5, 0.3])
    groups = np.repeat(np.arange(REALISED.n_clusters), np.asarray(REALISED.sizes))
    shipped = clustered_paired_bootstrap(
        [float(value) for value in deltas],
        [f"c{index:03d}" for index in groups],
        seed=11,
        resamples=4000,
    )
    fast = bootstrap_ci(deltas, groups, resamples=4000, rng=np.random.default_rng(11))
    # Same rule, different RNG: the endpoints agree to Monte-Carlo error, not to the bit.
    assert fast[0] == pytest.approx(shipped[0], abs=0.02)
    assert fast[1] == pytest.approx(shipped[1], abs=0.02)


def test_cluster_bootstrap_covers_a_known_delta_and_the_naive_one_covers_less() -> None:
    model = PairedBinaryModel(baseline_rate=0.25, delta=0.10)
    deltas, groups = simulate_anchor_deltas(model, REALISED, trials=200, cluster_icc=0.4, seed=404)
    anchors = np.arange(deltas.shape[1], dtype=np.int64)
    rng = np.random.default_rng(405)
    clustered = 0
    naive = 0
    for row in deltas:
        low, high = bootstrap_ci(row, groups, resamples=FAST_RESAMPLES, rng=rng)
        clustered += low <= model.delta <= high
        low, high = bootstrap_ci(row, anchors, resamples=FAST_RESAMPLES, rng=rng)
        naive += low <= model.delta <= high
    cluster_coverage = clustered / deltas.shape[0]
    naive_coverage = naive / deltas.shape[0]
    assert cluster_coverage >= 0.90, f"cluster bootstrap covered only {cluster_coverage:.3f}"
    assert naive_coverage < cluster_coverage, (
        f"naive={naive_coverage:.3f} cluster={cluster_coverage:.3f}"
    )


# --------------------------------------------------- type-I calibration, and its negative control


@pytest.fixture(scope="module")
def type_i_at_high_icc() -> dict[str, power_module.SimulationResult]:
    return simulate_type_i(
        REALISED,
        baseline_rate=0.25,
        cluster_icc=0.5,
        alpha=0.05,
        trials=TRIALS,
        permutations=SIM_PERMUTATIONS,
        resamples=800,
        seed=20260908,
    )


def test_clustered_test_holds_its_level_under_a_clustered_null(
    type_i_at_high_icc: dict[str, power_module.SimulationResult],
) -> None:
    """MEASUREMENT: realised false-positive rate of the preregistered cluster permutation test."""

    measured = type_i_at_high_icc["cluster_permutation"]
    assert measured.rate <= 0.09, f"cluster permutation over-rejected at {measured.rate:.4f}"
    assert not measured.anti_conservative
    bootstrap = type_i_at_high_icc["cluster_bootstrap"]
    assert bootstrap.rate <= 0.09, f"cluster bootstrap over-rejected at {bootstrap.rate:.4f}"


def test_naive_row_level_bootstrap_over_rejects_and_that_is_why_we_cluster(
    type_i_at_high_icc: dict[str, power_module.SimulationResult],
) -> None:
    """NEGATIVE CONTROL: the same null data, analysed as if anchors were independent."""

    naive = type_i_at_high_icc["anchor_bootstrap"]
    clustered = type_i_at_high_icc["cluster_permutation"]
    assert naive.rate >= 0.10, f"naive bootstrap only reached {naive.rate:.4f}"
    assert naive.anti_conservative
    assert naive.rate >= 2.0 * clustered.rate
    # The anchor-level permutation is the same mistake made in the test rather than the interval.
    assert type_i_at_high_icc["anchor_permutation"].rate >= 0.10


def test_no_clustering_means_no_penalty_for_ignoring_it() -> None:
    """At ICC = 0 the naive analysis is correct, so the gap above must be the clustering."""

    measured = simulate_type_i(
        REALISED,
        baseline_rate=0.25,
        cluster_icc=0.0,
        alpha=0.05,
        trials=TRIALS,
        permutations=SIM_PERMUTATIONS,
        resamples=800,
        seed=20260908,
    )
    assert measured["anchor_bootstrap"].rate <= 0.09
    assert measured["cluster_permutation"].rate <= 0.09


# ------------------------------------------------------------------------- power calculator


def test_cluster_profile_reads_the_realised_bank_shape() -> None:
    assert REALISED.n_anchors == 1127
    assert REALISED.n_clusters == 330
    assert REALISED.size_histogram == REALISED_HISTOGRAM
    assert SUM_M_SQUARED == 4533
    # m_A = sum(m^2)/sum(m) exceeds the mean whenever the clusters are unequal.
    assert REALISED.effective_cluster_size == pytest.approx(4533 / 1127)
    assert REALISED.effective_cluster_size == pytest.approx(4.0222, abs=5e-4)
    assert REALISED.mean_cluster_size == pytest.approx(1127 / 330)
    assert REALISED.effective_cluster_size > REALISED.mean_cluster_size
    assert REALISED.design_effect(0.0) == 1.0
    assert REALISED.design_effect(0.5) == pytest.approx(1.0 + (4533 / 1127 - 1.0) * 0.5)


def test_cluster_profile_matches_the_built_anchor_bank_when_it_exists() -> None:
    if not power_module.HC_V0_6_BANK_RELPATH.exists():
        pytest.skip(f"anchored bank not built at {power_module.HC_V0_6_BANK_RELPATH}")
    built = ClusterProfile.from_anchor_bank()
    assert built.size_histogram == REALISED.size_histogram
    assert (built.n_anchors, built.n_clusters) == (1127, 330)


def test_the_rebuild_bought_precision_and_paid_for_it_in_design_effect() -> None:
    """The rebuild is not free: n went up 5.05x, but the clusters also got more unequal.

    Recorded because the two effects pull in opposite directions and only their ratio matters.
    """

    old = ClusterProfile.from_sizes((1,) * 2 + (2,) * 7 + (3,) * 63 + (6,) * 3, label="223/75")
    assert (old.n_anchors, old.n_clusters) == (223, 75)
    assert REALISED.n_anchors / old.n_anchors == pytest.approx(5.054, abs=0.01)
    # m_A rose from 3.16 to 4.02: every anchor is worth less than it was.
    assert REALISED.effective_cluster_size > old.effective_cluster_size
    # But the effective sample size still rose by more than 4x at every plausible ICC.
    for icc in (0.0, 0.2, 0.5):
        assert REALISED.effective_n(icc) / old.effective_n(icc) > 4.0


def test_replicates_buy_nothing_when_the_solver_is_deterministic() -> None:
    """The headline consequence of call-for-call determinism: k is free of statistical content."""

    assert DETERMINISTIC_SOLVER.deterministic
    for k in (1, 3, 10):
        model = ReplicateModel(replicates=k, replicate_icc=1.0)
        assert model.factor == pytest.approx(1.0)
        assert model.effective_replicates == pytest.approx(1.0)
    one = minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2)
    three = minimum_detectable_effect(
        0.25, REALISED, replicates=ReplicateModel(3, 1.0), cluster_icc=0.2
    )
    assert one.mde == pytest.approx(three.mde)
    # With independent replicates the same k does buy something.
    noisy = minimum_detectable_effect(
        0.25, REALISED, replicates=ReplicateModel(3, 0.0), cluster_icc=0.2
    )
    assert noisy.mde < one.mde
    assert ReplicateModel(3, 0.0).factor == pytest.approx(1.0 / 3.0)


def test_mde_decreases_in_n_and_increases_in_icc() -> None:
    by_n = [
        minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2, n_anchors=n).mde
        for n in (100, 223, 500, 1000, 4000)
    ]
    assert by_n == sorted(by_n, reverse=True)
    assert by_n[-1] < by_n[0] / 2.0
    by_icc = [
        minimum_detectable_effect(0.25, REALISED, cluster_icc=icc).mde
        for icc in (0.0, 0.1, 0.25, 0.5, 0.9)
    ]
    assert by_icc == sorted(by_icc)
    # And the ICC = 0 value must equal the "if anchors were independent" figure it is compared to.
    independent = minimum_detectable_effect(0.25, REALISED, cluster_icc=0.4)
    assert independent.mde_if_independent == pytest.approx(by_icc[0])
    assert independent.mde > independent.mde_if_independent


def test_required_anchors_decreases_in_delta_and_increases_in_icc() -> None:
    by_delta = [
        required_anchors(PairedBinaryModel(0.25, delta), REALISED, cluster_icc=0.2).anchors_required
        for delta in (0.05, 0.10, 0.15, 0.20, 0.30)
    ]
    assert by_delta == sorted(by_delta, reverse=True)
    by_icc = [
        required_anchors(PairedBinaryModel(0.25, 0.10), REALISED, cluster_icc=icc).anchors_required
        for icc in (0.0, 0.1, 0.3, 0.6)
    ]
    assert by_icc == sorted(by_icc)
    # Required anchors under clustering is the independent figure times the design effect.
    needed = required_anchors(PairedBinaryModel(0.25, 0.10), REALISED, cluster_icc=0.3)
    assert needed.anchors_required >= needed.anchors_if_independent
    assert needed.anchors_required == math.ceil(
        needed.anchors_if_independent * needed.design_effect
    ) or needed.anchors_required == pytest.approx(
        needed.anchors_if_independent * needed.design_effect, abs=1.0
    )
    assert needed.attained_power >= 0.80
    assert needed.clusters_required == math.ceil(
        needed.anchors_required / REALISED.mean_cluster_size
    )


def test_required_anchors_and_mde_are_inverses_of_each_other() -> None:
    """Solve one, feed it to the other: the round trip must return the effect we started from."""

    for delta in (0.08, 0.12, 0.20):
        needed = required_anchors(PairedBinaryModel(0.25, delta), REALISED, cluster_icc=0.3)
        recovered = minimum_detectable_effect(
            0.25, REALISED, cluster_icc=0.3, n_anchors=needed.anchors_required
        )
        assert recovered.mde == pytest.approx(delta, abs=0.006)


def test_analytic_power_is_alpha_at_the_null_and_rises_with_delta() -> None:
    assert analytic_power(PairedBinaryModel(0.25, 0.0), REALISED) == pytest.approx(0.05)
    curve = [
        analytic_power(PairedBinaryModel(0.25, delta), REALISED, cluster_icc=0.2)
        for delta in (0.02, 0.05, 0.10, 0.20, 0.40)
    ]
    assert curve == sorted(curve)
    assert curve[-1] > 0.99


@pytest.mark.parametrize(
    # Deltas chosen at the REBUILT bank's ~80% power point.  At the old 223-anchor deltas
    # (0.15 / 0.20) the rebuilt bank has power ~1.0 and the comparison would be vacuous.
    ("delta", "cluster_icc"),
    [(0.067, 0.2), (0.085, 0.5)],
)
def test_simulated_power_matches_analytic_power(delta: float, cluster_icc: float) -> None:
    """MEASUREMENT: brute-force power of the permutation test vs the normal approximation."""

    model = PairedBinaryModel(baseline_rate=0.25, delta=delta)
    predicted = analytic_power(model, REALISED, cluster_icc=cluster_icc)
    measured = simulate_power(
        model,
        REALISED,
        cluster_icc=cluster_icc,
        trials=TRIALS,
        permutations=SIM_PERMUTATIONS,
        seed=11,
    )
    assert measured.rate == pytest.approx(predicted, abs=0.07), (
        f"analytic={predicted:.3f} simulated={measured.rate:.3f} CI={measured.rate_ci95}"
    )
    # The permutation test is discrete and slightly conservative, so it must not BEAT the
    # approximation by much; over-shooting would mean the MDE is optimistic.
    assert measured.rate <= predicted + 0.05


def test_simulator_reproduces_the_variance_and_icc_it_was_asked_for() -> None:
    model = PairedBinaryModel(baseline_rate=0.30, delta=0.0)
    profile = ClusterProfile.uniform(400, 4)
    deltas, groups = simulate_anchor_deltas(model, profile, trials=200, cluster_icc=0.4, seed=1234)
    assert deltas.var() == pytest.approx(model.unit_variance(), rel=0.05)
    # Realised within-cluster correlation, pooled over trials.
    grid = deltas.reshape(deltas.shape[0], profile.n_clusters, 4)
    centred = grid - grid.mean()
    pairs = [
        float((centred[:, :, i] * centred[:, :, j]).mean())
        for i in range(4)
        for j in range(4)
        if i < j
    ]
    assert float(np.mean(pairs)) / float(centred.var()) == pytest.approx(0.4, abs=0.06)


def test_unreachable_icc_is_refused_rather_than_silently_approximated() -> None:
    with pytest.raises(DesignViolation, match="unreachable"):
        simulate_anchor_deltas(
            PairedBinaryModel(0.25, 0.0),
            REALISED,
            trials=2,
            replicates=ReplicateModel(4, 0.1),
            cluster_icc=0.9,
        )
    with pytest.raises(DesignViolation, match="no systematic component"):
        simulate_anchor_deltas(
            PairedBinaryModel(0.25, 0.0),
            REALISED,
            trials=2,
            replicates=ReplicateModel(4, 0.0),
            cluster_icc=0.3,
        )


def test_independence_assumption_is_the_conservative_one() -> None:
    """Any measured concordance between the arms shrinks the sample the design needs."""

    independent = required_anchors(PairedBinaryModel(0.25, 0.10, 0.0), REALISED, cluster_icc=0.2)
    concordant = required_anchors(PairedBinaryModel(0.25, 0.10, 0.7), REALISED, cluster_icc=0.2)
    assert concordant.anchors_required < independent.anchors_required
    assert PairedBinaryModel(0.25, 0.10, 1.0).discordance == pytest.approx(0.10)


# --------------------------------------------------------------- multiplicity: the frozen family


def test_family_widening_guard_refuses_a_widened_family() -> None:
    family_widening_guard(list(PREREGISTERED_FAMILY))  # exactly the family: allowed
    with pytest.raises(DesignViolation, match="frozen"):
        family_widening_guard([*PREREGISTERED_FAMILY, Comparison.PRIMARY_RB_VS_RA][:3])
    with pytest.raises(DesignViolation, match="duplicate"):
        family_widening_guard([*PREREGISTERED_FAMILY, Comparison.C2_ABLATION])
    with pytest.raises(DesignViolation, match="missing"):
        family_widening_guard([Comparison.PRIMARY_RB_VS_RA, Comparison.C1_IDENTITY])


def test_holm_over_the_four_member_family() -> None:
    raw = {
        Comparison.PRIMARY_RB_VS_RA: 0.01,
        Comparison.C1_IDENTITY: 0.90,
        Comparison.C1B_WHITESPACE: 0.40,
        Comparison.C2_ABLATION: 0.0001,
    }
    decisions = holm_family(raw)
    assert decisions[Comparison.C2_ABLATION].p_holm == pytest.approx(0.0004)
    assert decisions[Comparison.PRIMARY_RB_VS_RA].p_holm == pytest.approx(0.03)
    assert decisions[Comparison.PRIMARY_RB_VS_RA].reject
    assert not decisions[Comparison.C1_IDENTITY].reject
    with pytest.raises(DesignViolation):
        holm_family({Comparison.PRIMARY_RB_VS_RA: 0.01})


# --------------------------------------------------------------------- the C1 identity control


def test_split_half_identity_pairs_a_single_arm_against_itself() -> None:
    table = _table(
        {Arm.R_A: [[True, False]] * 12},
        n_clusters=6,
        per_cluster=2,
    )
    pair = split_half_identity(table)
    assert pair.arm_a is Arm.R_A and pair.arm_b is Arm.R_A
    assert pair.a_outcomes[0] == (True,)
    assert pair.b_outcomes[0] == (False,)
    assert delta_hat(pair) == pytest.approx(-1.0)


def test_split_half_identity_refuses_a_single_replicate() -> None:
    table = _table({Arm.R_A: [[True]] * 12}, n_clusters=6, per_cluster=2)
    with pytest.raises(IdentityControlUnavailable, match="deterministic"):
        split_half_identity(table)


# ------------------------------------------------------------- the control-calibration verdict


def _four_arm_table(
    *,
    n_clusters: int = 40,
    per_cluster: int = 3,
    r_a: Sequence[bool] = (True, True),
    broken_identity: bool = False,
) -> CellTable:
    """A balanced four-arm table whose per-arm outcomes are dictated, not random."""

    n = n_clusters * per_cluster
    a_draws = [list(r_a) for _ in range(n)]
    if broken_identity:
        # R_A's two replicates disagree at four anchors in five: C1 must fire.
        for index in range(n):
            a_draws[index] = [True, index % 5 == 0]
    outcomes: dict[Arm, list[list[bool]]] = {
        Arm.R_A: a_draws,
        Arm.R_A_PRIME: [list(r_a) for _ in range(n)],
        Arm.R_B: [list(r_a) for _ in range(n)],
        # R_ABLATED fails everywhere: a large, unambiguous positive control.
        Arm.R_ABLATED: [[False] * len(r_a) for _ in range(n)],
    }
    return _table(outcomes, n_clusters=n_clusters, per_cluster=per_cluster)


def _effects(table: CellTable) -> dict[Comparison, object]:
    return {
        comparison: estimate_pair(
            table,
            comparison,
            resamples=FAST_RESAMPLES,
            permutations=FAST_PERMUTATIONS,
        )
        for comparison in PREREGISTERED_FAMILY
    }


def test_c1_broken_rule_fires_and_forecloses_every_other_comparison() -> None:
    effects = _effects(_four_arm_table(broken_identity=True))
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.BROKEN_IDENTITY_CONTROL
    assert verdict.broken and not verdict.usable
    assert verdict.identity.significant(ALPHA_IDENTITY)
    assert any("C1 identity control is significant" in reason for reason in verdict.reasons)
    mde = minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2)
    with pytest.raises(AssayBroken, match="BROKEN_IDENTITY_CONTROL"):
        verdict.release(
            effects[Comparison.PRIMARY_RB_VS_RA],
            mde,
            delta_min=0.10,
            equivalence_bound=0.10,
        )
    with pytest.raises(AssayBroken):
        verdict.require_usable()


def test_a_healthy_assay_releases_an_informative_null_with_its_mde_attached() -> None:
    effects = _effects(_four_arm_table())
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.USABLE
    assert verdict.usable and not verdict.broken
    # Every R_A replicate agrees, so C1 is exactly zero: determinism, not calibration.
    assert verdict.identity.degenerate
    assert verdict.identity_informative is False
    assert verdict.sensitivity_floor == pytest.approx(1.0)
    mde = minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2)
    released = verdict.release(
        effects[Comparison.PRIMARY_RB_VS_RA], mde, delta_min=0.10, equivalence_bound=0.10
    )
    assert released.outcome is Outcome.O3_INFORMATIVE_NULL
    assert released.outcome.sentinel == "NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND"
    assert released.attribution is Attribution.NO_EFFECT_TO_ATTRIBUTE
    assert not released.may_claim_structure
    assert f"{mde.points:.1f} points" in released.headline()
    assert any("degenerate" in caveat for caveat in released.caveats)


def test_a_weak_positive_control_makes_a_null_uninformative() -> None:
    # R_ABLATED now succeeds exactly as often as R_A: the assay has shown no sensitivity.
    table = _table(
        {
            Arm.R_A: [[True, True]] * 120,
            Arm.R_A_PRIME: [[True, True]] * 120,
            Arm.R_B: [[True, True]] * 120,
            Arm.R_ABLATED: [[True, True]] * 120,
        },
        n_clusters=40,
        per_cluster=3,
    )
    effects = _effects(table)
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.INSENSITIVE
    assert verdict.sensitivity_floor is None
    released = verdict.release(
        effects[Comparison.PRIMARY_RB_VS_RA],
        minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
        delta_min=0.10,
        equivalence_bound=0.10,
    )
    assert released.outcome is Outcome.O2_NULL_WITHOUT_SENSITIVITY
    assert released.outcome.sentinel == "LANDSCAPE_NOT_ESTABLISHED"
    assert released.attribution is Attribution.UNDETERMINED
    assert not released.may_claim_structure


def test_byte_sensitivity_blocks_a_structure_claim_without_breaking_the_assay() -> None:
    """Design brief §9.4: both C1b and the primary non-zero -> no structural attribution."""

    n = 120
    outcomes = {
        # Two replicates that agree, so C1 stays at zero while C1b and the primary do not.
        Arm.R_A: [[True, True]] * n,
        # A whitespace-only change flips 40% of anchors: C1b fires.
        Arm.R_A_PRIME: [[index % 5 >= 3, index % 5 >= 3] for index in range(n)],
        Arm.R_B: [[index % 5 >= 3, index % 5 >= 3] for index in range(n)],
        Arm.R_ABLATED: [[False, False]] * n,
    }
    effects = _effects(_table(outcomes, n_clusters=40, per_cluster=3))
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.USABLE_ATTRIBUTION_BLOCKED
    assert verdict.usable
    released = verdict.release(
        effects[Comparison.PRIMARY_RB_VS_RA],
        minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
        delta_min=0.10,
        equivalence_bound=0.10,
        p_holm=effects[Comparison.PRIMARY_RB_VS_RA].p_value * 4.0,
    )
    assert released.significant
    assert released.attribution is Attribution.BYTE_PERTURBATION
    assert released.may_claim_structure is False
    assert any("cannot be attributed to structure" in c for c in released.caveats)


def test_c1_identity_uses_the_uncorrected_p_value_and_a_liberal_alpha() -> None:
    """A safety gate corrected for multiplicity is a safety gate biased towards 'fine'."""

    assert ALPHA_IDENTITY >= 0.05


def test_too_few_clusters_is_outcome_o6_not_a_result() -> None:
    effects = _effects(_four_arm_table(n_clusters=8, per_cluster=3))
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.INSUFFICIENT_CLUSTERS
    with pytest.raises(AssayBroken, match="INSUFFICIENT_CLUSTERS"):
        verdict.release(
            effects[Comparison.PRIMARY_RB_VS_RA],
            minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
            delta_min=0.10,
            equivalence_bound=0.10,
        )


def test_release_rechecks_the_primary_comparisons_own_cluster_count() -> None:
    """The verdict saw the controls' clusters; the primary can lose clusters of its own."""

    effects = _effects(_four_arm_table())
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    assert verdict.status is AssayStatus.USABLE
    thin = _effects(_four_arm_table(n_clusters=10, per_cluster=3))[Comparison.PRIMARY_RB_VS_RA]
    with pytest.raises(AssayBroken, match="primary comparison contributes"):
        verdict.release(
            thin,
            minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
            delta_min=0.10,
            equivalence_bound=0.10,
        )


def test_arm_dependent_missingness_is_outcome_o7() -> None:
    effects = _effects(_four_arm_table())
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
        missingness={Arm.R_A: 0, Arm.R_B: 7, Arm.R_A_PRIME: 0, Arm.R_ABLATED: 0},
    )
    assert verdict.status is AssayStatus.ARM_DEPENDENT_MISSINGNESS
    assert not verdict.usable


def test_release_refuses_a_control_in_the_primary_slot() -> None:
    effects = _effects(_four_arm_table())
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    with pytest.raises(DesignViolation, match="primary comparison"):
        verdict.release(
            effects[Comparison.C2_ABLATION],
            minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
            delta_min=0.10,
            equivalence_bound=0.10,
        )
    with pytest.raises(DesignViolation, match="expected C1_IDENTITY"):
        calibrate(
            effects[Comparison.C2_ABLATION],
            effects[Comparison.C1B_WHITESPACE],
            effects[Comparison.C2_ABLATION],
        )


def test_verdict_and_result_serialise_without_losing_the_gate() -> None:
    effects = _effects(_four_arm_table())
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    payload = verdict.to_dict()
    assert payload["status"] == "USABLE"
    assert set(payload["controls"]) == {"C1", "C1b", "C2"}
    released = verdict.release(
        effects[Comparison.PRIMARY_RB_VS_RA],
        minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2),
        delta_min=0.10,
        equivalence_bound=0.10,
    )
    row = released.to_dict()
    assert row["may_claim_structure"] is False
    assert row["mde"]["mde_points"] > 0.0
    assert row["sentinel"] == "NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND"


# ------------------------------------------------------------------------------- determinism


def test_estimates_are_a_pure_function_of_the_table_and_the_seed() -> None:
    table = _four_arm_table(n_clusters=12, per_cluster=3)
    first = estimate_pair(
        table,
        Comparison.C2_ABLATION,
        resamples=200,
        permutations=199,
    ).to_dict()
    second = estimate_pair(
        table,
        Comparison.C2_ABLATION,
        resamples=200,
        permutations=199,
    ).to_dict()
    assert first == second


def test_negative_controls_are_computed_and_labelled_beside_the_preregistered_ones() -> None:
    # A table with genuine within-file structure, so the two units cannot coincide by accident:
    # anchors in even-numbered files fail under R_ABLATED, anchors in odd ones do not.
    n_clusters, per_cluster = 12, 3
    anchors = [(c, i) for c in range(n_clusters) for i in range(per_cluster)]
    outcomes = {
        Arm.R_A: [[True, True]] * len(anchors),
        Arm.R_ABLATED: [[c % 2 == 1, c % 2 == 1] for c, _ in anchors],
    }
    effect = estimate_pair(
        _table(outcomes, n_clusters=n_clusters, per_cluster=per_cluster),
        Comparison.C2_ABLATION,
        resamples=200,
        permutations=199,
    )
    assert effect.permutation.unit is PermutationUnit.CLUSTER
    assert effect.permutation.reportable
    assert effect.permutation_anchor_naive.unit is PermutationUnit.ANCHOR
    assert not effect.permutation_anchor_naive.reportable
    assert effect.p_value == effect.permutation.p_value
    assert effect.delta == pytest.approx(-0.5)
    # The clustering is entirely between files, so the naive anchor interval must be narrower.
    naive_width = effect.delta_ci95_anchor_naive[1] - effect.delta_ci95_anchor_naive[0]
    cluster_width = effect.delta_ci95[1] - effect.delta_ci95[0]
    assert naive_width < cluster_width
    assert ResampleUnit.CLUSTER.value == "CLUSTER"


# ------------------------------------------------ resolution of the REBUILT bank (delta_min)

#: The owner's declared minimum practical effect: 5 absolute percentage points.
DELTA_MIN_OWNER = 0.05

#: The plausible band for the within-file ICC of the paired difference.  Not measured here; the
#: V7 audit measured +0.51 for a paired difference in a comparable twin design
#: (`arena/experiments/precondition_power.py`), which is why the band's top end is 0.5.
PLAUSIBLE_ICCS = (0.2, 0.3, 0.5)


def _icc_ceiling_for(baseline: float, target: float = DELTA_MIN_OWNER) -> float | None:
    """Largest ICC at which the rebuilt bank still resolves ``target``; ``None`` if never."""

    if minimum_detectable_effect(baseline, REALISED, cluster_icc=0.0).mde > target:
        return None
    low, high = 0.0, 1.0
    for _ in range(50):
        mid = (low + high) / 2.0
        if minimum_detectable_effect(baseline, REALISED, cluster_icc=mid).mde <= target:
            low = mid
        else:
            high = mid
    return low


def test_the_rebuilt_bank_cannot_resolve_five_points_at_a_plausible_icc() -> None:
    """MEASUREMENT, and the honest answer to "is delta_min = 0.05 achievable?": mostly no.

    The MDE grows with the baseline rate, so the verdict depends on a baseline nobody has
    measured yet.  Both ends of the plausible baseline range are checked, and the answer is only
    "yes" in the corner where the baseline is low AND the clustering is weak.
    """

    # (a) At a baseline of 0.225 or above it is out of reach even with NO clustering at all.
    for baseline in (0.225, 0.25, 0.30, 0.40):
        floor = minimum_detectable_effect(baseline, REALISED, cluster_icc=0.0).mde
        assert floor > DELTA_MIN_OWNER, f"baseline {baseline}: MDE at ICC=0 is {floor:.4f}"

    # (b) At a LOW baseline it survives only while the ICC stays under about 0.2.
    assert minimum_detectable_effect(0.10, REALISED, cluster_icc=0.2).mde < DELTA_MIN_OWNER
    assert minimum_detectable_effect(0.10, REALISED, cluster_icc=0.3).mde > DELTA_MIN_OWNER

    # (c) Across the plausible ICC band, only a baseline near 0.10 is ever resolvable.
    for icc in PLAUSIBLE_ICCS:
        for baseline in (0.15, 0.20, 0.25, 0.40):
            mde = minimum_detectable_effect(baseline, REALISED, cluster_icc=icc).mde
            assert mde > DELTA_MIN_OWNER, f"baseline={baseline} icc={icc}: MDE={mde:.4f}"


def test_the_icc_ceiling_for_five_points_is_recorded_baseline_by_baseline() -> None:
    """The boundary, frozen: above these ICCs the bank cannot see 5 points at that baseline."""

    ceilings = {
        0.10: 0.2152,
        0.125: 0.1372,
        0.15: 0.0823,
        0.175: 0.0417,
        0.20: 0.0109,
    }
    for baseline, expected in ceilings.items():
        measured = _icc_ceiling_for(baseline)
        assert measured is not None
        assert measured == pytest.approx(expected, abs=2e-3), f"baseline {baseline}: {measured}"
    # Above 0.20 the ceiling does not exist: the bank cannot resolve 5 points at any ICC.
    assert _icc_ceiling_for(0.225) is None
    assert _icc_ceiling_for(0.25) is None


def test_the_mde_grid_on_the_rebuilt_bank_is_recorded() -> None:
    """MEASUREMENT: the table every null must be reported beside (design brief 9.5).

    Percentage points, alpha = 0.05 two-sided, power = 0.80, k = 1 under a deterministic Solver,
    arms assumed independent (the conservative choice).
    """

    grid = {
        (0.10, 0.0): 3.82,
        (0.10, 0.2): 4.92,
        (0.10, 0.5): 6.29,
        (0.25, 0.0): 5.27,
        (0.25, 0.2): 6.72,
        (0.25, 0.5): 8.47,
        (0.40, 0.0): 5.83,
        (0.40, 0.2): 7.39,
        (0.40, 0.5): 9.26,
    }
    for (baseline, icc), expected in grid.items():
        measured = minimum_detectable_effect(baseline, REALISED, cluster_icc=icc).points
        assert measured == pytest.approx(expected, abs=0.02), f"{baseline}/{icc}: {measured:.2f}"


def test_the_bank_needed_for_five_points_is_bigger_than_the_bank_that_exists() -> None:
    """The gap, in anchors and in mathlib files, so the owner can price it."""

    required = {0.0: (1248, 366), 0.2: (2003, 587), 0.5: (3134, 918)}
    for icc, (anchors, files) in required.items():
        need = required_anchors(
            PairedBinaryModel(baseline_rate=0.25, delta=DELTA_MIN_OWNER),
            REALISED,
            cluster_icc=icc,
        )
        assert (need.anchors_required, need.clusters_required) == (anchors, files)
        assert need.anchors_required > REALISED.n_anchors
        assert need.attained_power >= 0.80


def test_replicates_cannot_rescue_five_points_under_a_deterministic_solver() -> None:
    """k is not a way out of section (a) above: under determinism it changes nothing at all."""

    at_k1 = minimum_detectable_effect(0.25, REALISED, cluster_icc=0.2).mde
    at_k5 = minimum_detectable_effect(
        0.25, REALISED, replicates=ReplicateModel(5, 1.0), cluster_icc=0.2
    ).mde
    assert at_k1 == pytest.approx(at_k5)
    assert at_k1 > DELTA_MIN_OWNER


# ------------------------------------- certification as an intersection-union test (no Holm)

IUT_TRIALS = 400
IUT_BLOCK_TRIALS = 200
IUT_RESAMPLES = 50
IUT_PERMUTATIONS = 199
#: 30 files x 2 anchors = the MIN_CLUSTERS floor exactly, so no trial is thrown out on O6.
IUT_CLUSTERS, IUT_PER_CLUSTER = 30, 2


def _random_four_arm_table(
    rng: np.random.Generator,
    *,
    rates: dict[Arm, Sequence[float]],
) -> CellTable:
    """A four-arm table whose cells are independent Bernoulli draws at per-replicate rates.

    ``rates[arm]`` is one rate per replicate, so an arm can be given replicates that disagree in
    distribution -- which is how a genuinely broken C1 identity control is built.
    """

    anchors = [
        (f"a{c:03d}_{i}", f"file{c:03d}")
        for c in range(IUT_CLUSTERS)
        for i in range(IUT_PER_CLUSTER)
    ]
    rows: list[CellOutcome] = []
    for arm, per_replicate in rates.items():
        draws = rng.random((len(anchors), len(per_replicate))) < np.asarray(per_replicate)
        for (anchor, cluster), row in zip(anchors, draws, strict=True):
            for index, event in enumerate(row):
                rows.append(_cell(anchor, cluster, arm, index, bool(event)))
    return CellTable(rows)


def _certifications(
    rates: dict[Arm, Sequence[float]], *, trials: int, seed: int
) -> tuple[int, list[AssayStatus]]:
    """Run the REAL calibrate() over ``trials`` simulated tables; count full certifications."""

    rng = np.random.default_rng(seed)
    certified = 0
    statuses: list[AssayStatus] = []
    controls = (Comparison.C1_IDENTITY, Comparison.C1B_WHITESPACE, Comparison.C2_ABLATION)
    for _ in range(trials):
        table = _random_four_arm_table(rng, rates=rates)
        effects = {
            comparison: estimate_pair(
                table,
                comparison,
                resamples=IUT_RESAMPLES,
                permutations=IUT_PERMUTATIONS,
            )
            for comparison in controls
        }
        verdict = calibrate(
            effects[Comparison.C1_IDENTITY],
            effects[Comparison.C1B_WHITESPACE],
            effects[Comparison.C2_ABLATION],
        )
        statuses.append(verdict.status)
        certified += int(verdict.certified)
    return certified, statuses


def test_certification_gates_are_the_ones_calibrate_actually_uses() -> None:
    """The declared roster may not drift away from the thresholds the gate code reads."""

    by_name = {gate.name: gate for gate in CERTIFICATION_GATES}
    assert set(by_name) == {"C1", "C1b", "C2"}
    assert by_name["C1"].alpha == ALPHA_IDENTITY
    assert by_name["C1b"].alpha == ALPHA_BYTE_NULL
    assert by_name["C2"].alpha == ALPHA_SENSITIVITY
    assert {gate.comparison for gate in CERTIFICATION_GATES} == set(PREREGISTERED_FAMILY) - {
        Comparison.PRIMARY_RB_VS_RA
    }
    # Only C2 is a REJECT_TO_CERTIFY component, so only C2 enters the IUT bound.
    assert by_name["C2"].direction is GateDirection.REJECT_TO_CERTIFY
    assert by_name["C1"].direction is GateDirection.BLOCK_ON_REJECTION
    assert by_name["C1b"].direction is GateDirection.BLOCK_ON_REJECTION
    assert false_certification_bound() == ALPHA_SENSITIVITY == ALPHA
    # A roster with no reject-to-certify gate bounds nothing, and says so rather than returning 0.
    with pytest.raises(DesignViolation, match="not bounded by any alpha"):
        false_certification_bound([by_name["C1"], by_name["C1b"]])


def test_false_certification_rate_is_bounded_by_alpha_under_a_global_null() -> None:
    """MEASUREMENT of the IUT proposition, on the real ``calibrate`` and the real estimators.

    The global null holds through C2: every arm draws from the same rate, so the ablation
    genuinely changes nothing and the assay genuinely has no sensitivity.  Certifying then
    requires rejecting a TRUE component null, which happens at most alpha of the time -- with
    separate, uncorrected, level-alpha component tests and no Holm anywhere.
    """

    base = 0.30
    certified, statuses = _certifications(
        {arm: (base, base) for arm in Arm}, trials=IUT_TRIALS, seed=606
    )
    measured = power_module.SimulationResult(
        label="false certification under a global null (C2 unsafe)",
        unit="CLUSTER",
        trials=IUT_TRIALS,
        alpha=ALPHA,
        rejections=certified,
        nominal=false_certification_bound(),
        note=f"{IUT_CLUSTERS} files x {IUT_PER_CLUSTER} anchors, k=2, all arms at p={base}",
    )
    assert measured.rate <= false_certification_bound(), (
        f"certified {certified}/{IUT_TRIALS} = {measured.rate:.4f} > "
        f"{false_certification_bound()}; CI {measured.rate_ci95}"
    )
    assert measured.valid_level and not measured.anti_conservative
    # The bound is not tight: certification also needs C1 and C1b to stay silent, and the C2 gate
    # additionally demands the right SIGN.  Most trials land on INSENSITIVE, which is O2.
    assert statuses.count(AssayStatus.INSENSITIVE) > IUT_TRIALS // 2
    assert statuses.count(AssayStatus.USABLE) == certified


def test_holm_can_only_move_a_gate_towards_certifying() -> None:
    """Why Holm is not merely unnecessary on the gates but wrong on the blocking ones.

    Holm is monotone: ``p_holm >= p_raw``, always.  On a REJECT_TO_CERTIFY gate that makes
    certification rarer (a false BLOCK, on a bound that was already satisfied).  On a
    BLOCK_ON_REJECTION gate it makes the block rarer -- i.e. it raises the false-certification
    rate in exactly the place the IUT bound does not reach.
    """

    raw = {
        Comparison.PRIMARY_RB_VS_RA: 0.011,
        Comparison.C1_IDENTITY: 0.060,
        Comparison.C1B_WHITESPACE: 0.080,
        Comparison.C2_ABLATION: 0.004,
    }
    decisions = holm_family(raw)
    for comparison, p_raw in raw.items():
        assert decisions[comparison].p_holm >= p_raw

    # C1 raw p = 0.060 <= alpha_identity 0.10 -> the assay is declared BROKEN, correctly.
    assert raw[Comparison.C1_IDENTITY] <= ALPHA_IDENTITY
    # Holm-corrected it is 0.18 > 0.10 -> the block would NOT fire.  That is the failure mode.
    assert decisions[Comparison.C1_IDENTITY].p_holm > ALPHA_IDENTITY
    # Same for C1b: correcting it would silently license a structure claim.
    assert raw[Comparison.C1B_WHITESPACE] <= ALPHA_BYTE_NULL
    assert decisions[Comparison.C1B_WHITESPACE].p_holm > ALPHA_BYTE_NULL


def test_a_blocking_gate_is_governed_by_power_not_by_alpha() -> None:
    """MEASUREMENT, and a limitation stated rather than hidden.

    Here the unsafe gate is C1, which certifies by FAILING to reject.  No alpha bounds that, so
    what is measured is the gate's POWER against a concrete, large violation -- ``R_A``'s two
    replicates drawn from rates 0.45 and 0.15, a true Delta_C1 of -0.30.  C2 is made genuinely
    sensitive so that C1 is the only unsafe gate.  The number below is a power measurement and
    must never be quoted as a level.
    """

    rates: dict[Arm, Sequence[float]] = {
        Arm.R_A: (0.45, 0.15),
        Arm.R_A_PRIME: (0.30, 0.30),
        Arm.R_B: (0.30, 0.30),
        Arm.R_ABLATED: (0.02, 0.02),
    }
    certified, statuses = _certifications(rates, trials=IUT_BLOCK_TRIALS, seed=707)
    caught = statuses.count(AssayStatus.BROKEN_IDENTITY_CONTROL)
    missed = certified / IUT_BLOCK_TRIALS
    assert caught >= int(0.90 * IUT_BLOCK_TRIALS), (
        f"C1 caught a Delta of -0.30 only {caught}/{IUT_BLOCK_TRIALS} times"
    )
    # Measured: 10/200 = 0.050.  It sits near alpha by coincidence, NOT by guarantee -- nothing
    # bounds it, so the assertion is a regression guard on the gate's power, not a level claim.
    assert missed <= 0.10, f"certified with a broken C1 in {missed:.4f} of trials"
    # C1 is evaluated FIRST, so every trial it catches is foreclosed: no other status can appear
    # alongside it, and the certifications are exactly the trials C1 missed.
    assert caught + certified <= IUT_BLOCK_TRIALS
    assert statuses.count(AssayStatus.USABLE) == certified


# ------------------------------------ the primary endpoint: KERNEL_ACCEPTED_STATE_CHANGE


def _cell_with(step_result: StepResult, *, closed: bool = False) -> CellOutcome:
    return CellOutcome(
        anchor_id="a0",
        cluster_id="f0",
        theorem="thm",
        reelaboration_key="key",
        arm=Arm.R_A,
        renderer_id=Arm.R_A.renderer_id,
        intervention_class=Arm.R_A.intervention_class,
        replicate_index=0,
        step_result=step_result,
        parse_status=ParseStatus.OK,
        closed_all_goals=closed,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
    )


def test_an_accepted_no_op_is_not_an_endpoint_event() -> None:
    """The endpoint change, at the atom: Lean accepting is necessary but not sufficient."""

    assert PRIMARY_ENDPOINT == "KERNEL_ACCEPTED_STATE_CHANGE"
    no_op = _cell_with(StepResult.ACCEPTED_NO_OP)
    assert no_op.kernel_accepted, "Lean did accept it"
    assert not no_op.kernel_accepted_state_change, "but it moved nothing, so it scores 0"
    assert not no_op.accepted, "the legacy spelling must mean the endpoint, not the acceptance"
    # And it is a Solver outcome, not a harness failure: it stays in the analysis as a zero.
    assert no_op.analysable
    assert StepResult.ACCEPTED_NO_OP not in ENDPOINT_EVENT_RESULTS

    moved = _cell_with(StepResult.ACCEPTED_TRANSITION)
    assert moved.kernel_accepted and moved.kernel_accepted_state_change and moved.accepted


def test_an_environment_error_is_never_a_mathematical_zero() -> None:
    """ENVIRONMENT_ERROR stays separately typed: excluded, not scored."""

    for result in (StepResult.ENVIRONMENT_ERROR, StepResult.TOOL_TIMEOUT, StepResult.NOT_ATTEMPTED):
        cell = _cell_with(result)
        assert not cell.kernel_accepted_state_change
        assert not cell.analysable, f"{result} must be excluded, not counted as a failure"
        assert result.harness_failure
    # A rejection, by contrast, IS a mathematical zero and stays in.
    rejected = _cell_with(StepResult.REJECTED_INVALID_ACTION)
    assert rejected.analysable and not rejected.kernel_accepted_state_change


def test_closing_the_goal_cannot_be_recorded_against_a_no_op() -> None:
    """An action that closed the task changed the state, so the two cannot disagree."""

    with pytest.raises(DesignViolation, match="KERNEL_ACCEPTED_STATE_CHANGE"):
        _cell_with(StepResult.ACCEPTED_NO_OP, closed=True)
    with pytest.raises(DesignViolation, match="KERNEL_ACCEPTED_STATE_CHANGE"):
        _cell_with(StepResult.REJECTED_INVALID_ACTION, closed=True)


def test_no_ops_reach_the_estimators_as_zeros_and_depress_the_rate() -> None:
    """The endpoint travels all the way through: extract_pair and arm_marginal see 0, not 1."""

    rows = [
        _cell("a0", "f0", Arm.R_A, 0, True),
        _cell("a1", "f0", Arm.R_A, 0, True),
        _cell("a0", "f0", Arm.R_B, 0, True),
        _cell("a1", "f0", Arm.R_B, 0, True),
    ]
    # Replace R_B's second cell with an accepted no-op: Lean said yes, the mathematics did not move.
    rows[3] = _cell_with_arm_anchor("a1", "f0", Arm.R_B, StepResult.ACCEPTED_NO_OP)
    table = CellTable(rows)
    pair = extract_pair(table, Arm.R_A, Arm.R_B)
    assert pair.b_outcomes == ((True,), (False,))
    assert delta_hat(pair) == pytest.approx(-0.5)
    marginal = arm_marginal(table, Arm.R_B, resamples=FAST_RESAMPLES)
    assert (marginal.n_events, marginal.n_cells) == (1, 2)
    assert marginal.rate == pytest.approx(0.5)


def _cell_with_arm_anchor(
    anchor: str, cluster: str, arm: Arm, step_result: StepResult
) -> CellOutcome:
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"thm::{anchor}",
        reelaboration_key=f"key::{anchor}",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=0,
        step_result=step_result,
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
    )


def test_a_stored_row_cannot_declare_an_event_its_step_result_denies() -> None:
    """Round-tripping re-derives the endpoint and refuses a contradictory stored flag."""

    payload = _cell_with(StepResult.ACCEPTED_NO_OP).to_dict()
    assert payload["kernel_accepted"] is True
    assert payload["kernel_accepted_state_change"] is False
    assert payload["accepted"] is False
    assert CellOutcome.from_dict(payload).step_result is StepResult.ACCEPTED_NO_OP
    with pytest.raises(DesignViolation, match="kernel_accepted_state_change"):
        CellOutcome.from_dict({**payload, "kernel_accepted_state_change": True})
    with pytest.raises(DesignViolation, match="accepted"):
        CellOutcome.from_dict({**payload, "accepted": True})
