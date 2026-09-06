import pytest

from arena.training.evaluation import paired_bootstrap_difference, wilson_interval
from arena.training.matched_adaptation import (
    AdaptationConfig,
    BudgetMode,
    validate_matched_configs,
)
from arena.training.render_dataset import RenderedExample, assert_matched_semantics


def config(candidate_tokens: int = 1000, *, seed: int = 0) -> AdaptationConfig:
    return AdaptationConfig(
        base_model="model",
        base_model_digest="digest",
        tokenizer="tokenizer",
        learning_rate=1e-4,
        optimizer="adamw",
        seed=seed,
        update_count=100,
        effective_token_budget=candidate_tokens,
        example_count=100,
        context_length=1024,
        budget_mode=BudgetMode.EXAMPLE_MATCHED,
        runner="external-test-runner-v1",
    )


def test_wilson_interval_contains_observed_rate() -> None:
    interval = wilson_interval(8, 10)
    assert interval.lower < interval.estimate < interval.upper


def test_paired_bootstrap_detects_consistent_improvement() -> None:
    result = paired_bootstrap_difference((1.0,) * 20, (0.0,) * 20, resamples=200)
    assert result.estimate == 1.0
    assert result.lower == 1.0


def test_example_matched_configs_may_have_different_token_counts() -> None:
    validate_matched_configs({"a": config(1000), "b": config(2000)})


def test_mismatched_seed_is_rejected() -> None:
    with pytest.raises(ValueError, match="not matched"):
        validate_matched_configs({"a": config(seed=0), "b": config(seed=1)})


def rendered(candidate: str, input_hash: str = "input") -> RenderedExample:
    return RenderedExample(
        example_id=f"example:{candidate}",
        canonical_id="trajectory:1",
        candidate_id=candidate,
        task_kind="NEXT_ACTION",
        input_text=candidate,
        target_text="target",
        input_hash=input_hash,
        target_hash="target-hash",
    )


@pytest.mark.parametrize("datasets", [{}, {"only": ()}, {"a": (), "b": ()}])
def test_matched_semantics_rejects_missing_or_empty_arms(
    datasets: dict[str, tuple[RenderedExample, ...]],
) -> None:
    with pytest.raises(ValueError):
        assert_matched_semantics(datasets)


def test_matched_semantics_rejects_identical_surfaces() -> None:
    with pytest.raises(ValueError, match="byte-identical"):
        assert_matched_semantics({"a": (rendered("a"),), "b": (rendered("b"),)})


def test_matched_semantics_accepts_distinct_matched_surfaces() -> None:
    assert_matched_semantics({"a": (rendered("a", "input-a"),), "b": (rendered("b", "input-b"),)})
