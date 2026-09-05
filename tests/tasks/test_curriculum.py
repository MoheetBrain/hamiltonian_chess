from arena.tasks.curriculum import InformationCurriculum, acquisition_score
from arena.tasks.generators.world_v0 import build_world_v0


def test_disagreement_beats_unanimously_easy_and_impossible_tasks() -> None:
    task = build_world_v0(total=13)[0]
    disagreement = acquisition_score(task, (0.05, 0.95), dimension_frequency=1)
    impossible = acquisition_score(task, (0.0, 0.0), dimension_frequency=1)
    perfect = acquisition_score(task, (1.0, 1.0), dimension_frequency=1)

    assert disagreement.total > impossible.total
    assert disagreement.total > perfect.total
    assert disagreement.disagreement > 0


def test_curriculum_ranking_is_deterministic_and_uses_frontier() -> None:
    tasks = build_world_v0(total=13).tasks[:3]
    predictions = {
        tasks[0].task_id: {"a": 0.1, "b": 0.9, "irrelevant": 0.5},
        tasks[1].task_id: {"a": 0.5, "b": 0.5, "irrelevant": 0.5},
        tasks[2].task_id: {"a": 1.0, "b": 1.0, "irrelevant": 1.0},
    }
    curriculum = InformationCurriculum()

    first = curriculum.rank(tasks, predictions, frontier_candidates=("a", "b"))
    second = curriculum.rank(reversed(tasks), predictions, frontier_candidates=("b", "a"))

    assert first == second
    assert first[0].task_id == tasks[0].task_id
