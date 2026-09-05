import pytest

from arena.pipeline import ArenaRuntime


@pytest.mark.integration
def test_runtime_builds_league_and_refuses_untrained_release(tmp_path) -> None:
    runtime = ArenaRuntime(tmp_path)
    world = runtime.build_worlds(total=13, seed=9)
    assert world["count"] == 13
    assert runtime.validate_worlds()["valid"]
    assert runtime.seed_candidate_languages()["count"] == 8
    assert runtime.mutate("L1_CURRENT_HML", count=3, seed=2)["proposed"] == 3

    league = runtime.run_league(tier=0)
    assert league["candidates"] == 8
    assert league["fronts"][0]

    decision = runtime.release_decision("L5_COMPACT_SYMBOLIC")
    assert decision.status.value == "RSTAR_BLOCKED_BY_MODEL_FITNESS"
    assert not decision.released
    assert not (tmp_path / "artifacts/rstar/v0").exists()

    status = runtime.status()
    assert status["records"]["worlds"] == 13
    assert status["records"]["mutations"] == 3
    assert status["scoreboard"] is not None
