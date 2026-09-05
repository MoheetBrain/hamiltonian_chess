from pathlib import Path

from arena.experiments import model_fitness
from arena.experiments.fitness_v1 import correct_choice, frozen_task_split
from arena.tasks.generators.world_v0 import build_world_v0


def test_model_cell_persists_task_level_cache(monkeypatch, tmp_path: Path) -> None:
    world = build_world_v0()
    task_id = frozen_task_split(world)["protocol_slices"]["CALIBRATION_DEV"][0]
    task = next(task for task in world.tasks if task.task_id == task_id)
    calls = 0

    def fake_call(prompt: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        assert "Return exactly one JSON object" in prompt
        return {
            "response": f'{{"choice":"{correct_choice(task)}"}}',
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 123,
            "eval_count": 5,
            "total_duration_ns": 2_000_000_000,
            "load_duration_ns": 0,
            "prompt_eval_duration_ns": 1,
            "eval_duration_ns": 1,
        }

    monkeypatch.setattr(model_fitness, "_call_ollama", fake_call)
    first = model_fitness.evaluate_cell(
        tmp_path, "L0_STRUCTURED_ENGLISH", task_id, slice_name="CALIBRATION_DEV"
    )
    second = model_fitness.evaluate_cell(
        tmp_path, "L0_STRUCTURED_ENGLISH", task_id, slice_name="CALIBRATION_DEV"
    )
    assert calls == 1
    assert first["correct"] is True and first["cache_hit"] is False
    assert second["correct"] is True and second["cache_hit"] is True
    assert first["prompt_tokens"] == 123
    assert first["cache_key"] == second["cache_key"]
    assert len(list((tmp_path / "artifacts/cache/fitness_v1").glob("*.json"))) == 1


def test_calibration_thresholds_are_frozen() -> None:
    def scores(value: float) -> dict[str, dict[str, float]]:
        return {"control": {"accuracy": value}}

    assert model_fitness._calibration_verdict(scores(0.95)) == "SEVERE_CEILING"
    assert model_fitness._calibration_verdict(scores(0.05)) == "SEVERE_FLOOR"
    assert model_fitness._calibration_verdict(scores(0.85)) == "BORDERLINE_CEILING"
    assert model_fitness._calibration_verdict(scores(0.2)) == "BORDERLINE_FLOOR"
    assert model_fitness._calibration_verdict(scores(0.5)) == "USEFUL_HEADROOM"
