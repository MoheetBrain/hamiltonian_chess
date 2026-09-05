from arena.evaluation.landscape import (
    landscape_summary,
    mcnemar_exact,
    paired_comparison,
    spearman,
)


def test_exact_mcnemar_and_clustered_paired_counts() -> None:
    a = (True, True, False, True, False, False)
    b = (True, False, True, True, False, True)
    result = paired_comparison(a, b, ("x", "x", "y", "y", "z", "z"), resamples=200)
    assert result.n10 == 1
    assert result.n01 == 2
    assert result.clusters == 3
    assert result.delta == -1 / 6
    assert result.mcnemar_exact_p == mcnemar_exact(1, 2) == 1.0


def test_spearman_handles_order_and_ties() -> None:
    assert spearman((1, 2, 3), (10, 20, 30)) == 1.0
    assert spearman((1, 2, 3), (30, 20, 10)) == -1.0
    assert spearman((1, 1, 1), (1, 2, 3)) is None


def test_landscape_metrics_are_edge_and_rank_based() -> None:
    edges = [
        {
            "changed_gene": "grammar",
            "old_value": "a",
            "new_value": "b",
            "parent_accuracy": 0.5,
            "child_accuracy": 0.75,
            "promotion_delta": 0.1,
            "token_ratio": 1.1,
        },
        {
            "changed_gene": "grammar",
            "old_value": "a",
            "new_value": "b",
            "parent_accuracy": 0.6,
            "child_accuracy": 0.7,
            "promotion_delta": 0.0,
            "token_ratio": 1.0,
        },
    ]
    rankings = [
        {
            "candidate_id": "L5_COMPACT_SYMBOLIC",
            "scout_accuracy": 0.7,
            "promotion_accuracy": 0.8,
            "mean_input_tokens": 100,
        },
        {
            "candidate_id": "CONTROL",
            "scout_accuracy": 0.6,
            "promotion_accuracy": 0.7,
            "mean_input_tokens": 200,
        },
    ]
    result = landscape_summary(proposal_count=4, gate0_survivors=2, edges=edges, rankings=rankings)
    assert result["valid_neighbor_rate"] == 0.5
    assert result["beneficial_mutation_rate"] == 1.0
    assert result["rank_stability_spearman"] == 1.0
    assert result["l5_verdict"]["static_advantage_was_useful"] is True
