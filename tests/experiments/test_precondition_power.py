"""Offline tests for the Phase 8 precondition power analysis.

Nothing here calls a model or the network; every check is against an independent computation
(brute-force enumeration, :func:`arena.evaluation.landscape.mcnemar_exact`, closed forms) or a
structural property (monotonicity, calibration, determinism).  Simulation sizes are reduced so
the file runs well inside 40 s.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pytest

from arena.evaluation.landscape import mcnemar_exact
from arena.experiments import precondition_power as pp

P10, P01 = 0.20, 0.10  # Δ = 0.10 at discordance 0.30 — the headline cell


def _adjacent_nondecreasing(values: list[float], tolerance: float = 1e-12) -> bool:
    return all(
        later >= earlier - tolerance for earlier, later in zip(values, values[1:], strict=False)
    )


# ------------------------------------------------------------------ exact McNemar power


def test_version_constant() -> None:
    assert pp.POWER_ANALYSIS_VERSION == "arena-precondition-power-v1.0.0"


def test_exact_power_equals_size_at_null() -> None:
    for alpha in (0.05, 0.05 / 4, 0.05 / 10):
        size = pp.mcnemar_exact_power(200, 0.15, 0.15, alpha)
        assert 0.0 < size <= alpha + 0.01  # exact test is conservative, never anti-conservative
        assert size <= alpha + 1e-12


def test_exact_power_matches_brute_force_enumeration_n6() -> None:
    n = 6
    p_concordant = 1.0 - P10 - P01
    for alpha in (0.05, 0.2, 0.5):
        brute = 0.0
        for cells in itertools.product((0, 1, 2), repeat=n):
            n10, n01 = cells.count(1), cells.count(2)
            probability = p_concordant ** cells.count(0) * P10**n10 * P01**n01
            if mcnemar_exact(n10, n01) <= alpha:
                brute += probability
        assert pp.mcnemar_exact_power(n, P10, P01, alpha) == pytest.approx(brute, abs=1e-12)


def test_exact_power_monotone_in_n() -> None:
    for alpha in (0.05, 0.05 / 4):
        curve = [pp.mcnemar_exact_power(n, P10, P01, alpha) for n in range(1, 401)]
        assert _adjacent_nondecreasing(curve)


def test_exact_power_monotone_in_delta() -> None:
    discordance = 0.30
    curve = []
    for delta in np.linspace(0.0, 0.30, 13):
        p10, p01 = (discordance + delta) / 2.0, (discordance - delta) / 2.0
        curve.append(pp.mcnemar_exact_power(300, p10, p01, 0.05))
    assert _adjacent_nondecreasing(curve)
    assert curve[0] <= 0.05 and curve[-1] > 0.99


def test_decision_rule_matches_landscape_mcnemar_exact() -> None:
    for alpha in (0.05, 0.05 / 4, 0.05 / 10, 0.1):
        for n10 in range(60):
            for n01 in range(60):
                expected = mcnemar_exact(n10, n01) <= alpha
                assert pp.mcnemar_rejects(n10, n01, alpha) is expected


def test_one_sided_power_at_least_two_sided() -> None:
    two = pp.mcnemar_exact_power(200, P10, P01, 0.05)
    one = pp.mcnemar_exact_power(200, P10, P01, 0.05, two_sided=False)
    assert one >= two


def test_exact_power_validates_inputs() -> None:
    with pytest.raises(ValueError):
        pp.mcnemar_exact_power(0, P10, P01, 0.05)
    with pytest.raises(ValueError):
        pp.mcnemar_exact_power(10, 0.7, 0.5, 0.05)
    with pytest.raises(ValueError):
        pp.mcnemar_exact_power(10, P10, P01, 1.5)
    assert pp.mcnemar_exact_power(10, 0.0, 0.0, 0.05) == 0.0


# ------------------------------------------------------------------ clustered (twin) power


def test_family_kernel_is_the_twin_copy_mixture() -> None:
    icc = 0.5
    kernel = pp._family_kernel(P10, P01, icc)
    assert kernel.sum() == pytest.approx(1.0)
    assert kernel[2, 0] == pytest.approx(icc * P10 + (1.0 - icc) * P10**2)  # both items "10"
    assert kernel[1, 1] == pytest.approx((1.0 - icc) * 2.0 * P10 * P01)
    with pytest.raises(ValueError):
        pp._family_kernel(P10, P01, 1.5)


def test_clustered_exact_reduces_to_independent_at_icc_zero() -> None:
    for n_families in (25, 150):
        clustered = pp.clustered_mcnemar_power_exact(n_families, P10, P01, 0.05 / 4, 0.0)
        independent = pp.mcnemar_exact_power(2 * n_families, P10, P01, 0.05 / 4)
        assert clustered == pytest.approx(independent, abs=1e-9)


def test_clustered_simulated_within_0_03_of_exact_at_icc_zero_n150() -> None:
    simulated = pp.clustered_mcnemar_power(150, P10, P01, 0.05, 0.0, resamples=4000, seed=7)
    exact = pp.mcnemar_exact_power(300, P10, P01, 0.05)
    assert abs(simulated - exact) <= 0.03


def test_clustered_simulated_tracks_exact_at_positive_icc() -> None:
    simulated = pp.clustered_mcnemar_power(150, P10, P01, 0.05 / 4, 0.5, resamples=4000, seed=3)
    exact = pp.clustered_mcnemar_power_exact(150, P10, P01, 0.05 / 4, 0.5)
    assert abs(simulated - exact) <= 0.03


def test_clustered_power_decreases_with_icc() -> None:
    powers = [
        pp.clustered_mcnemar_power_exact(150, P10, P01, 0.05 / 4, icc)
        for icc in (0.0, 0.3, 0.5, 0.8)
    ]
    assert powers == sorted(powers, reverse=True)


def test_clustered_exact_power_monotone_in_families() -> None:
    curve = [pp.clustered_mcnemar_power_exact(n, P10, P01, 0.05 / 4, 0.5) for n in range(1, 201)]
    assert _adjacent_nondecreasing(curve)


def test_paired_bootstrap_ci_width_close_to_analytic() -> None:
    simulated = pp.paired_bootstrap_ci_width(100, P10, P01, 0.5, seed=1, datasets=30, resamples=500)
    analytic = pp.bootstrap_ci_halfwidth_analytic(100, P10, P01, 0.5)
    assert abs(simulated - analytic) < 0.015
    assert (
        pp.paired_bootstrap_ci_width(100, P10, P01, 0.5, seed=1, datasets=30, resamples=500)
        == simulated
    )


# ------------------------------------------------------------------ sample-size searches


def test_required_n_pairs_reaches_target_and_is_minimal() -> None:
    n = pp.required_n_pairs(0.8, P10, P01, 0.05 / 4)
    assert pp.mcnemar_exact_power(n, P10, P01, 0.05 / 4) >= 0.8
    assert pp.mcnemar_exact_power(n - 1, P10, P01, 0.05 / 4) < 0.8
    approx = pp.normal_approximation_n_pairs(0.10, 0.30, 0.05 / 4, 0.8)
    assert abs(n - approx) / approx < 0.10


def test_required_families_monotone_in_target_power() -> None:
    targets = (0.5, 0.7, 0.8, 0.9, 0.95)
    families = [pp.required_families(t, P10, P01, 0.05 / 4, 0.5) for t in targets]
    pairs = [pp.required_n_pairs(t, P10, P01, 0.05 / 4) for t in targets]
    assert families == sorted(families) and len(set(families)) == len(families)
    assert pairs == sorted(pairs)


def test_required_families_reaches_target_and_is_minimal() -> None:
    n = pp.required_families(0.8, P10, P01, 0.05 / 4, 0.5)
    assert pp.clustered_mcnemar_power_exact(n, P10, P01, 0.05 / 4, 0.5) >= 0.8
    assert pp.clustered_mcnemar_power_exact(n - 1, P10, P01, 0.05 / 4, 0.5) < 0.8
    at_icc0 = pp.required_families(0.8, P10, P01, 0.05 / 4, 0.0)
    assert 2 * at_icc0 - pp.required_n_pairs(0.8, P10, P01, 0.05 / 4) in (0, 1)
    assert n > at_icc0


def test_required_families_raises_when_capped_or_ill_posed() -> None:
    with pytest.raises(ValueError):
        pp.required_families(0.8, 0.151, 0.149, 0.05, 0.5, max_families=10)
    with pytest.raises(ValueError):
        pp.required_families(0.8, 0.1, 0.2, 0.05, 0.5)
    with pytest.raises(ValueError):
        pp.required_families(1.0, P10, P01, 0.05, 0.5)


# ------------------------------------------------------------------ discreteness and design table


def test_representability_of_project_thresholds() -> None:
    at_24 = pp.representability(24)
    assert at_24["quantum"] == pytest.approx(1 / 24)
    assert at_24["thresholds"]["0.100"]["representable"] is False
    assert at_24["thresholds"]["0.125"] == {
        "representable": True,
        "count": 3,
        "largest_failing_margin": pytest.approx(2 / 24),
        "smallest_passing_margin": pytest.approx(3 / 24),
    }
    assert at_24["thresholds"]["0.150"]["representable"] is False
    assert at_24["all_thresholds_representable"] is False
    at_40 = pp.representability(40)
    assert at_40["all_thresholds_representable"] is True
    assert [at_40["thresholds"][k]["count"] for k in ("0.100", "0.125", "0.150")] == [4, 5, 6]
    assert pp.representability(400)["all_thresholds_representable"] is True


def test_derive_cells_parameterisation() -> None:
    cells = pp.derive_cells(0.75, 0.10, 0.30)
    assert cells["p10"] - cells["p01"] == pytest.approx(0.10)
    assert cells["p10"] + cells["p01"] == pytest.approx(0.30)
    assert cells["p11"] + cells["p10"] + cells["p01"] + cells["p00"] == pytest.approx(1.0)
    assert cells["p11"] + cells["p10"] == pytest.approx(0.85)  # candidate accuracy
    assert cells["p11"] + cells["p01"] == pytest.approx(0.75)  # baseline accuracy
    assert cells["feasible"] is True
    assert pp.derive_cells(0.75, 0.30, 0.20)["feasible"] is False
    assert pp.derive_cells(0.95, 0.10, 0.30)["feasible"] is False


def test_design_table_flags_infeasible_and_orders_families() -> None:
    table = pp.design_table(
        deltas=(0.15, 0.30),
        discordance_rates=(0.20,),
        accuracies=(0.75,),
        alphas=(0.05,),
        iccs=(0.0, 0.5),
        max_pairs=1000,
        max_families=500,
    )
    assert table["infeasible_count"] == 2
    feasible = [row for row in table["rows"] if row["feasible"]]
    assert len(feasible) == 2
    by_icc = {row["icc"]: row for row in feasible}
    assert by_icc[0.5]["required_families_clustered"] > by_icc[0.0]["required_families_clustered"]
    assert 2 * by_icc[0.0]["required_families_clustered"] - by_icc[0.0][
        "required_n_pairs_exact"
    ] in (0, 1)
    assert all(
        row["required_n_pairs_exact"] is None for row in table["rows"] if not row["feasible"]
    )


# ------------------------------------------------------------------ equivalence (TOST)


def test_equivalence_established_on_clear_parity_not_on_clear_effect() -> None:
    parity = pp.equivalence_test(60, 60, 500, region=0.125)
    assert parity["established"] is True
    assert parity["wald"]["established"] is True and parity["exact"]["established"] is True
    lo, hi = parity["wald"]["ci_1_minus_2alpha"]
    assert -0.125 < lo < hi < 0.125
    effect = pp.equivalence_test(110, 40, 500, region=0.125)
    assert effect["established"] is False
    assert effect["wald"]["established"] is False and effect["exact"]["established"] is False
    assert effect["mcnemar_exact_p"] < 0.001
    assert effect["exact"]["region_conditionally_unattainable"] is False


def test_equivalence_wald_matches_interval_rule_and_edge_cases() -> None:
    for n10, n01 in (
        (
            70,
            50,
        ),
        (52, 48),
        (90, 30),
        (0, 0),
    ):
        result = pp.equivalence_test(n10, n01, 400, region=0.10)
        if result["degenerate"]:
            assert result["established"] is False
            continue
        lo, hi = result["wald"]["ci_1_minus_2alpha"]
        assert result["wald"]["established"] is (lo > -0.10 and hi < 0.10)
    small = pp.equivalence_test(1, 1, 24, region=0.125)
    assert small["exact"]["region_conditionally_unattainable"] is True
    v7 = pp.equivalence_test(3, 1, 24, region=0.125)
    assert v7["established"] is False
    with pytest.raises(ValueError):
        pp.equivalence_test(10, 20, 24, region=0.1)


def test_parity_sample_size_grows_as_region_shrinks() -> None:
    wide = pp.parity_sample_size(0.125, 0.0, 0.30, 0.5)
    narrow = pp.parity_sample_size(0.10, 0.0, 0.30, 0.5)
    offset = pp.parity_sample_size(0.125, 0.05, 0.30, 0.5)
    assert narrow["n_items"] > wide["n_items"]
    assert offset["n_items"] > wide["n_items"]
    assert wide["n_families"] == math.ceil(wide["n_items"] / 2)
    with pytest.raises(ValueError):
        pp.parity_sample_size(0.10, 0.10, 0.30, 0.5)


# ------------------------------------------------------------------ shortcut gate


def test_shortcut_gate_probabilities_bounded_and_null_max_increasing() -> None:
    for n_eval in (200, 800):
        oc = pp.shortcut_gate_operating_characteristic(n_eval)
        assert all(0.0 <= g["p_max_upper_bound_exceeds_threshold"] <= 1.0 for g in oc["gates"])
        expected = [row["expected_max_observed_accuracy"] for row in oc["null_max"]]
        assert expected == sorted(expected) and len(set(expected)) == 3
        assert all(0.5 < value < 0.7 for value in expected)
        for threshold in (0.55, 0.60):
            for m in (20, 40, 80):
                trips = [
                    g["p_max_upper_bound_exceeds_threshold"]
                    for g in oc["gates"]
                    if g["threshold"] == threshold and g["n_rules"] == m
                ]
                assert _adjacent_nondecreasing(trips)  # harder to clear as true rate rises


def test_shortcut_gate_k_star_is_the_clopper_pearson_boundary() -> None:
    n_eval, threshold, m = 800, 0.60, 40
    gamma = 0.05 / m
    k_star = pp._gate_k_star(n_eval, threshold, gamma)
    assert pp._clopper_pearson_bounds(k_star, n_eval, gamma)[1] <= threshold
    assert pp._clopper_pearson_bounds(k_star + 1, n_eval, gamma)[1] > threshold
    clear = pp.shortcut_gate_clear_probability(n_eval, threshold, m, true_rate=0.5)
    oc = pp.shortcut_gate_operating_characteristic(n_eval, thresholds=(threshold,), n_rules=(m,))
    row = next(g for g in oc["gates"] if g["true_rate"] == 0.5)
    assert row["p_max_upper_bound_exceeds_threshold"] == pytest.approx(1.0 - clear)
    assert 0.0 < clear < 1.0


def test_shortcut_gate_min_n_eval() -> None:
    n = pp.shortcut_gate_min_n_eval(0.60, 20, clear_probability=0.5)
    assert n is not None
    assert pp.shortcut_gate_clear_probability(n, 0.60, 20) >= 0.5
    assert pp.shortcut_gate_clear_probability(n - 1, 0.60, 20) < 0.5
    stricter = pp.shortcut_gate_min_n_eval(0.60, 20, clear_probability=0.8)
    assert stricter is not None and stricter > n
    assert pp.shortcut_gate_min_n_eval(0.55, 20, true_rate=0.55) is None
    assert pp.shortcut_gate_min_n_eval(0.60, 20, max_n_eval=50) is None


# ------------------------------------------------------------------ budget


def test_budget_arithmetic() -> None:
    seconds = {"a": 20.0, "b": 10.0, "c": 5.0, "d": 4.0, "e": 1.0}
    table = pp.budget_table(200, 5, include_rotated=True, seconds_per_call_by_arm=seconds)
    assert table["n_items"] == 400
    assert table["primary_calls"] == 2000 and table["rotated_calls"] == 2000
    assert table["primary_hours"] == pytest.approx(400 * 40.0 / 3600)
    assert table["rotated_hours"] == pytest.approx(2000 * 2.0 / 3600)
    assert table["total_hours"] == pytest.approx(table["primary_hours"] + table["rotated_hours"])
    plain = pp.budget_table(200, 5, include_rotated=False, seconds_per_call_by_arm=seconds)
    assert plain["rotated_calls"] == 0 and plain["total_hours"] == pytest.approx(
        plain["primary_hours"]
    )
    with pytest.raises(ValueError):
        pp.budget_table(200, 4, include_rotated=True, seconds_per_call_by_arm=seconds)


def test_arm_profiles_follow_the_measured_facts() -> None:
    p12 = pp.arm_profile("P12")
    assert p12["R_json_ast"] == {"prompt_tokens": 12_093, "seconds": 21.9, "provenance": "measured"}
    assert p12["R_hml"]["seconds"] == pytest.approx(0.55 * 21.9)
    assert p12["R_sexpr"]["prompt_tokens"] == pytest.approx(0.45 * 12_093)
    p09 = pp.arm_profile("P09")
    assert p09["R_compact_symbolic"]["seconds"] == pytest.approx(0.8 * 8.4)
    assert "interpolated" in p09["R_json_ast"]["provenance"]
    with pytest.raises(ValueError):
        pp.arm_profile("P99")
    grid = pp.budget_grid()
    assert len(grid["rows"]) == 15
    p12_200 = grid["total_hours_by_stratum"]["P12"]["200"]
    per_item = 21.9 + 16.6 + 8.4 + 0.55 * 21.9 + 0.45 * 21.9
    assert p12_200 == pytest.approx((400 * per_item + 400 * 5 * 2.0) / 3600)
    fit = pp.latency_fit()
    assert fit["points"] == 9 and 1.5 < fit["seconds_per_1000_tokens"] < 2.5


# ------------------------------------------------------------------ report


def test_main_writes_valid_json_and_is_deterministic(tmp_path: Path) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    assert pp.main(["--out", str(first), "--resamples", "300"]) == 0
    assert pp.main(["--out", str(second), "--resamples", "300"]) == 0
    assert first.read_bytes() == second.read_bytes()
    report = json.loads(first.read_text(encoding="utf-8"))
    assert report["version"] == pp.POWER_ANALYSIS_VERSION
    primary = report["recommendation"]["primary_delta_0.10_holm_k4_icc_0.5"]
    assert primary["recommended_families"] % 20 == 0
    assert primary["power_at_recommended"]["exact_clustered"] >= 0.8
    assert primary["representability"]["all_thresholds_representable"] is True
    assert set(report["budget"]["grid"]["total_hours_by_stratum"]) == {"P09", "P12", "P16"}
    assert "n_eval=800" in report["shortcut_gate"]["operating_characteristic"]
