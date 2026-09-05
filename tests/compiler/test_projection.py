import pytest

from arena.compiler.projection import (
    ObservationKind,
    assert_no_answer_leakage,
    project_state_for_observation,
)
from tests.helpers import sample_state


@pytest.mark.parametrize("kind", [ObservationKind.NEXT_ACTION, ObservationKind.COMPLETE])
def test_action_answer_sets_are_hidden(kind: ObservationKind) -> None:
    projected = project_state_for_observation(sample_state(), kind)
    assert projected.legal_actions == ()
    assert projected.plausible_invalid_actions == ()
    assert_no_answer_leakage(projected, kind)


def test_decode_projection_removes_oracle_usefulness_and_metadata() -> None:
    projected = project_state_for_observation(
        sample_state(metadata=(("answer", "leak"),)), ObservationKind.FULL_DECODE
    )
    assert projected.execution_metadata == ()
    assert projected.legal_actions[0].expected_usefulness == 0.0
    assert_no_answer_leakage(projected, ObservationKind.FULL_DECODE)
