from arena.fitness.gates import (
    GateStatus,
    GateZeroEvidence,
    evaluate_coverage_gate,
    evaluate_gate_zero,
)
from arena.fitness.metrics import CoverageMetrics, Direction, proportion_metric
from arena.fitness.pareto import Objective, ParetoPoint, pareto_fronts, pareto_ranks


def test_gate_zero_is_hard_and_missing_checks_fail_closed() -> None:
    assert evaluate_gate_zero(GateZeroEvidence()).status == GateStatus.ELIMINATED
    passing = GateZeroEvidence(required_roundtrip_successes=520, required_roundtrip_total=520)
    assert evaluate_gate_zero(passing).status == GateStatus.PASS

    false_accept = GateZeroEvidence(
        critical_false_accepts=1,
        required_roundtrip_successes=1_000_000,
        required_roundtrip_total=1_000_000,
    )
    assert evaluate_gate_zero(false_accept).status == GateStatus.ELIMINATED


def test_coverage_can_be_explicitly_niche_but_not_silently_general() -> None:
    coverage = CoverageMetrics(1.0, 0.7, 0.8, 0.2, 1.0, 1.0, 1.0)
    result = evaluate_coverage_gate(coverage)
    assert result.status == GateStatus.NICHE
    assert result.reasons


def test_metrics_carry_confidence_intervals() -> None:
    estimate = proportion_metric("next_action_accuracy", 80, 100)
    assert estimate.interval.lower < estimate.value < estimate.interval.upper
    assert estimate.sample_count == 100


def test_pareto_ranking_preserves_tradeoffs_and_direction() -> None:
    points = (
        ParetoPoint("compact", {"accuracy": 0.8, "tokens": 10}),
        ParetoPoint("accurate", {"accuracy": 0.9, "tokens": 20}),
        ParetoPoint("dominated", {"accuracy": 0.7, "tokens": 30}),
    )
    objectives = (
        Objective("accuracy", Direction.MAXIMIZE),
        Objective("tokens", Direction.MINIMIZE),
    )
    fronts = pareto_fronts(points, objectives)
    ranks = pareto_ranks(points, objectives)

    assert {point.candidate_id for point in fronts[0]} == {"compact", "accurate"}
    assert ranks["dominated"] > 0
