import pytest

from arena.evaluation.static import evaluate_static
from arena.languages.registry import seed_languages
from arena.tasks.generators.world_v0 import build_world_v0


@pytest.mark.parametrize("language", seed_languages(), ids=lambda item: item.candidate_id)
def test_seed_languages_pass_static_semantic_gate(language) -> None:
    world = build_world_v0(total=13, seed=4)
    result = evaluate_static(language, world.tasks, fuzz_cases=2)
    assert result.passed_gate_zero
    assert result.exact_roundtrips == result.states_checked
    assert result.answer_leaks == 0
    assert result.coverage.canonical_world_coverage == 1.0
