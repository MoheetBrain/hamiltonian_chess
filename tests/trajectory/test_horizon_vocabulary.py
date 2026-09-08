"""The four horizon measures stay distinct (manual sections 6.30-6.34, 17.6, correction 4).

The project's historical error was calling a recorded proof length a "reasoning horizon". The
manual forbids it, and these tests make the prohibition mechanical rather than editorial:
``minimal_proof_length`` is UNKNOWN, so no record can license the claim that N recorded tactics
were N *required* steps.
"""

from __future__ import annotations

from arena.trajectory.schema import Horizon


def _h(**kw: int) -> Horizon:
    base = dict(
        achieved=5,
        verified=5,
        reference=9,
        solver_actions=5,
        reference_actions=9,
        kernel_step_count=5,
    )
    base.update(kw)
    return Horizon(**base)  # type: ignore[arg-type]


def test_episode_length_and_observed_trace_length_are_different_numbers() -> None:
    """A solver may close a 9-tactic reference proof in 5 moves; both must remain visible."""

    h = _h()
    assert h.episode_length == 5
    assert h.observed_trace_length == 9
    assert h.episode_length != h.observed_trace_length


def test_minimal_proof_length_is_unknown_and_never_a_number() -> None:
    """Manual 6.34: only a value when independently established. It never has been here."""

    assert _h().minimal_proof_length == "UNKNOWN"
    assert _h(achieved=14, reference=14).minimal_proof_length == "UNKNOWN"


def test_dependency_depth_is_unknown_for_this_backend() -> None:
    assert _h().dependency_depth == "UNKNOWN"


def test_kernel_step_count_is_carried_so_a_macro_cannot_look_cheap() -> None:
    """Manual 6.32 / 13.1: cost is accounted AFTER lowering."""

    bundled = _h(achieved=1, solver_actions=1, kernel_step_count=40)
    assert bundled.episode_length == 1
    assert bundled.kernel_step_count == 40
    assert bundled.to_dict()["kernel_step_count"] == 40


def test_verified_is_zero_unless_the_kernel_closed_the_episode() -> None:
    assert _h(verified=0).to_dict()["verified"] == 0


def test_all_five_measures_are_serialised_together() -> None:
    payload = _h().to_dict()
    for key in (
        "episode_length",
        "observed_trace_length",
        "kernel_step_count",
        "dependency_depth",
        "minimal_proof_length",
    ):
        assert key in payload, key
