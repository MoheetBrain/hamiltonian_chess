from arena.fitness.metrics import Direction
from arena.fitness.pareto import Objective
from arena.league.hall_of_fame import HallOfFame, HallOfFameSuite
from arena.league.matches import LeagueMatch, MatchObservation
from arena.league.registry import DEFAULT_BASELINES, LeagueRegistry
from arena.league.selection import rank_registry
from arena.tasks.generators.world_v0 import build_world_v0


def test_registry_seeds_required_baselines_and_keeps_axis_ratings(tmp_path) -> None:
    registry = LeagueRegistry()
    assert set(registry.candidates) >= {candidate for candidate, _ in DEFAULT_BASELINES}

    match = LeagueMatch(
        "match:1",
        (
            MatchObservation("candidate:x", "task:1", "algebra", ("binding",), 1.0),
            MatchObservation("candidate:x", "task:2", "logic", ("scope",), 0.0),
            MatchObservation("candidate:x", "task:3", "algebra", ("binding",), 0.5),
        ),
    )
    registry.record_match(match)
    record = registry.candidates["candidate:x"]

    assert set(record.domain_ratings) == {"algebra", "logic"}
    assert set(record.mechanism_ratings) == {"binding", "scope"}
    assert not hasattr(record, "elo")

    path = registry.save(tmp_path / "league.json")
    restored = LeagueRegistry.load(path)
    assert restored.to_dict() == registry.to_dict()


def test_hall_of_fame_suite_uses_gold_and_registry_gets_pareto_status() -> None:
    world = build_world_v0(total=65)
    suite = HallOfFameSuite.from_tasks(world)
    hall = HallOfFame(suite)
    assert hall.validate_baselines()
    assert len(suite.task_ids) < len(world)

    hall.registry.register("candidate:a")
    hall.registry.register("candidate:b")
    hall.registry.set_objectives("candidate:a", {"accuracy": 0.9, "tokens": 20})
    hall.registry.set_objectives("candidate:b", {"accuracy": 0.8, "tokens": 10})
    fronts = rank_registry(
        hall.registry,
        (
            Objective("accuracy", Direction.MAXIMIZE),
            Objective("tokens", Direction.MINIMIZE),
        ),
        candidate_ids=("candidate:a", "candidate:b"),
    )
    assert set(fronts[0]) == {"candidate:a", "candidate:b"}
    assert hall.registry.candidates["candidate:a"].pareto_status == "FRONTIER"
