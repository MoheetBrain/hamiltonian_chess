"""``result_hash`` must answer "did the same mathematics happen", not "did it take as long".

This test exists because the absence of it cost the project a wrong finding. HC-V0.5 reported that
the runtime was not reproducible, on the evidence that two runs of an identical configuration
produced different ``result_hash`` values. Four re-runs on 2026-09-09 showed every prompt, every
proposed tactic and every Lean verdict identical across all four -- the hash was differing on
``wall_ms``, which :class:`~arena.trajectory.schema.TrajectoryAction` documents as "excluded from
every content hash" and which :data:`~arena.trajectory.episode.NON_DETERMINISTIC_FIELDS` was the
one place not to exclude.

The wrong finding then propagated into the design of the next milestone as a demand for
replicates. A hash that silently measures machine load is worse than no hash.
"""

from __future__ import annotations

from typing import Any

from arena.trajectory.episode import (
    NON_DETERMINISTIC_FIELDS,
    EpisodeResult,
    EpisodeStep,
    build_manifest,
    summarise,
)
from arena.trajectory.solver import ScriptedSolver


def _step(**overrides: Any) -> EpisodeStep:
    payload: dict[str, Any] = {
        "index": 0,
        "proposal_status": "OK",
        "tactic": "rw [polar_sub]",
        "action_result": "REJECTED_INVALID_ACTION",
        "terminal_status": "OPEN",
        "diagnostic": "",
        "prompt_tokens": 161,
        "completion_tokens": 16,
        "latency_ms": 500,
        "state_id": "0",
        "prompt_sha256": "1e9c61ec" * 8,
    }
    payload.update(overrides)
    return EpisodeStep(**payload)


def _episode(*, wall_ms: int, **step_overrides: Any) -> EpisodeResult:
    result = EpisodeResult(
        task_id="t", problem_id="p", terminal_status="FAILED", terminal_outcome="FAILED"
    )
    result.steps.append(_step(**step_overrides))
    result.wall_clock_s = wall_ms / 1000
    result.trajectory = {
        "trajectory_id": "traj-1",
        "actions": [
            {"index": 0, "actor": "SOLVER", "tactic": "rw [polar_sub]", "wall_ms": wall_ms}
        ],
    }
    return result


def _hash(episode: EpisodeResult) -> str:
    solver = ScriptedSolver(default="skip")
    return build_manifest([episode], solver=solver, selection=None)["result_hash"]


def test_wall_clock_does_not_change_the_result_hash() -> None:
    """The regression: two runs of the same mathematics on a busier machine."""

    assert _hash(_episode(wall_ms=12)) == _hash(_episode(wall_ms=4_000))


def test_wall_ms_is_actually_in_the_exclusion_set() -> None:
    """Named directly, so deleting it from the set fails here and not only via the test above."""

    assert "wall_ms" in NON_DETERMINISTIC_FIELDS


def test_a_different_tactic_does_change_the_result_hash() -> None:
    """The negative control: an exclusion set that excluded everything would pass the first test."""

    assert _hash(_episode(wall_ms=12)) != _hash(_episode(wall_ms=12, tactic="simp"))


def test_a_different_lean_verdict_changes_the_result_hash() -> None:
    assert _hash(_episode(wall_ms=12)) != _hash(
        _episode(wall_ms=12, action_result="ACCEPTED_TRANSITION")
    )


def test_a_different_completion_token_count_still_changes_the_hash() -> None:
    """Deliberately NOT excluded: it differed once in 13 calls for an identical parsed tactic,
    which means the response bytes differed. That is a real fact about the runtime and the hash
    should keep reporting it rather than smoothing it away."""

    assert _hash(_episode(wall_ms=12)) != _hash(_episode(wall_ms=12, completion_tokens=12))


def test_summarise_counts_what_it_says_it_counts() -> None:
    episodes = [_episode(wall_ms=1), _episode(wall_ms=1, action_result="ACCEPTED_TRANSITION")]
    summary = summarise(episodes)
    assert summary["episodes"] == 2
    assert summary["accepted_solver_transitions"] == 1
    assert summary["rejected_actions"] == 1


def test_a_per_run_scratch_path_does_not_change_verifier_evidence() -> None:
    """The second half of the same defect, found by the noise study after the first was fixed.

    Excluding ``wall_ms`` was not enough: Lean writes its own scratch directory into rejection
    messages, and that directory is freshly made per session. Two runs of identical mathematics
    still hashed differently until the path was normalised.
    """

    from arena.trajectory.arena_v0 import normalise_backend_diagnostic
    from arena.trajectory.schema import EvidenceKind, Verdict, VerifierEvidence

    def evidence(scratch: str) -> VerifierEvidence:
        return VerifierEvidence(
            kind=EvidenceKind.STEP,
            verifier="lean4-repl",
            verdict=Verdict.REJECTED,
            step=0,
            tactic="rw [polar_sub]",
            backend_error=normalise_backend_diagnostic(
                f"/var/folders/w9/{scratch}/T/hamiltonian-lean-{scratch}/probe_Foo.lean:3:5: "
                "error: rewrite failed"
            ),
        )

    assert evidence("aaa111").to_dict() == evidence("bbb222").to_dict()


def test_the_normalisation_keeps_the_message_and_the_probe_name() -> None:
    """A redaction that removed the diagnostic would pass the test above and be useless."""

    from arena.trajectory.arena_v0 import normalise_backend_diagnostic

    cleaned = normalise_backend_diagnostic(
        "/var/folders/w9/xyz/T/hamiltonian-lean-ab12/probe_Foo.lean:3:5: error: rewrite failed"
    )
    assert cleaned is not None
    assert "probe_Foo.lean:3:5" in cleaned
    assert "rewrite failed" in cleaned
    assert "hamiltonian-lean-ab12" not in cleaned


def test_an_ordinary_diagnostic_is_left_alone() -> None:
    from arena.trajectory.arena_v0 import normalise_backend_diagnostic

    message = "unknown identifier 'polar_sub'"
    assert normalise_backend_diagnostic(message) == message
    assert normalise_backend_diagnostic(None) is None
