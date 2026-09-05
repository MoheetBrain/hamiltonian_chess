from pathlib import Path

from arena.experiments import model_fitness
from arena.experiments.fitness_v1 import correct_choice, frozen_task_split
from arena.storage.artifacts import ArtifactStore
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


def test_position_only_controls_invalidate_nominal_headroom(tmp_path: Path) -> None:
    rows = []
    scores = {}
    for candidate_id in model_fitness.CONTROL_IDS:
        candidate_rows = [
            {
                "candidate_id": candidate_id,
                "task_id": "t-a",
                "cache_key": f"{candidate_id}-t-a",
                "parsed_choice": "A",
                "correct_choice": "A",
            },
            {
                "candidate_id": candidate_id,
                "task_id": "t-b",
                "cache_key": f"{candidate_id}-t-b",
                "parsed_choice": "A",
                "correct_choice": "B",
            },
        ]
        rows.extend(candidate_rows)
        scores[candidate_id] = {
            "correct": 1,
            "tasks": 2,
            "accuracy": 0.5,
            "malformed": 0,
            "mean_prompt_tokens": 10.0,
        }
    result = {
        "headroom_verdict": "USEFUL_HEADROOM",
        "benchmark_valid": True,
        "next_stage": "TIER2A",
        "rungs": [{"slice": "CALIBRATION_DEV", "scores": scores, "rows": rows}],
        "calls": 8,
        "cache_hits": 0,
        "raw_inspection_sample": [],
    }
    ArtifactStore(tmp_path / "artifacts").write_json("reports/fitness-calibration.json", result)
    decision = model_fitness.audit_calibration(tmp_path)
    assert decision["decision"] == "MODEL_FITNESS_BENCHMARK_INVALID"
    assert decision["tier2a_run"] is False
    status = model_fitness.experiment_status(tmp_path)
    assert status["benchmark_valid"] is False
    assert status["decision"] == "MODEL_FITNESS_BENCHMARK_INVALID"
