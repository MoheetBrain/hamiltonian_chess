"""Item J: the fine-tuning record, its provenance guard and its hash."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Action,
    Evidence,
    Goal,
    Provenance,
    Scope,
    State,
    Status,
    Term,
    TrainingDataError,
    TrainingRecord,
    VerificationOutcome,
    action_envelope,
    build_default_registry,
    parse_action,
    parse_state,
    read_jsonl,
    render_action,
    render_state,
    write_jsonl,
)

from .conftest import NAT, PROP, build_rich_state

SURFACES = tuple(build_default_registry())
GOOD_PROVENANCE = Provenance(
    source="arena.tasks.generators.world_v0",
    source_id="world:676",
    generator="releases.TRAINING_LANGUAGE_V0",
    generator_version="0.1.0",
    sealed_splits_excluded=True,
)
OUTCOME = VerificationOutcome("arena.native", "0.1.0", Status.VERIFIED, True, "cert", "accepted")


def _next_state() -> State:
    return State(
        state_id="state:next",
        scopes=(Scope("s0"), Scope("s1", "s0")),
        goals=(Goal("g.1", "s1", Term("true", PROP, True), Status.OPEN, True),),
        evidence=(Evidence("e.1", Status.VERIFIED, "arena.native", "0.1.0"),),
        terminal_status="CLOSED",
    )


def _record(**overrides: object) -> TrainingRecord:
    state = build_rich_state()
    defaults: dict[str, object] = {
        "trajectory_id": "traj:1",
        "problem_id": "prob:1",
        "step_index": 0,
        "state_t": state,
        "chosen_action": state.actions[0],
        "candidate_actions": state.actions,
        "next_state": _next_state(),
        "verification": OUTCOME,
        "outcome": "SOLVED",
        "provenance": GOOD_PROVENANCE,
    }
    defaults.update(overrides)
    return TrainingRecord(**defaults)  # type: ignore[arg-type]


def test_the_record_carries_every_required_field() -> None:
    payload = _record().to_dict(build_default_registry().default)
    assert set(payload) == {
        "schema_version",
        "trajectory_id",
        "problem_id",
        "step_index",
        "state_t",
        "rendered_state_t",
        "candidate_actions",
        "rendered_candidate_actions",
        "chosen_action",
        "rendered_chosen_action",
        "warrant",
        "next_state",
        "rendered_next_state",
        "verification",
        "outcome",
        "provenance",
        "surface",
        "content_hash",
    }
    assert payload["warrant"] == "commutativity of +"
    assert payload["verification"]["status"] == "VERIFIED"


def test_the_structural_state_is_the_lossless_tl0_text() -> None:
    record = _record()
    payload = record.to_dict(build_default_registry().default)
    assert parse_state(str(payload["state_t"])) == record.state_t
    assert str(payload["state_t"]) == render_state(record.state_t)


@pytest.mark.parametrize("surface", SURFACES, ids=lambda item: item.surface_id)
def test_targets_are_written_in_the_same_grammar_as_the_inputs(surface: object) -> None:
    """Removes ROUTE_B_PARITY_AUDIT defect D3 by construction: every arm is self-consistent."""

    state = build_rich_state()
    action = state.actions[0]
    text = render_action(state, action, surface)  # type: ignore[arg-type]
    assert parse_action(text, surface) == action  # type: ignore[arg-type]


def test_the_action_envelope_leaks_only_what_the_action_refers_to() -> None:
    state = build_rich_state()
    envelope = action_envelope(state, state.actions[0])
    assert {item.goal_id for item in envelope.goals} == {"g.1"}
    assert envelope.declarations == ()
    assert envelope.claims == ()
    assert envelope.substitution == ()
    assert envelope.actions == (state.actions[0],)


def test_content_hash_changes_with_content() -> None:
    surface = build_default_registry().default
    first = _record().content_hash(surface)
    second = _record(outcome="FAILED").content_hash(surface)
    assert first != second
    assert first == _record().content_hash(surface)


def test_content_hash_changes_with_the_surface() -> None:
    registry = build_default_registry()
    record = _record()
    assert record.content_hash(registry.get("tl0")) != record.content_hash(
        registry.get("via:L3_JSON_AST")
    )


def test_a_shard_round_trips_through_jsonl(tmp_path: Path) -> None:
    surface = build_default_registry().default
    path = tmp_path / "shard.jsonl"
    digest = write_jsonl(path, [_record(), _record(step_index=1)], surface)
    rows = list(read_jsonl(path, surface=surface))
    assert len(rows) == 2
    assert digest == write_jsonl(
        tmp_path / "again.jsonl", [_record(), _record(step_index=1)], surface
    )


def test_reading_refuses_a_tampered_record(tmp_path: Path) -> None:
    surface = build_default_registry().default
    path = tmp_path / "shard.jsonl"
    write_jsonl(path, [_record()], surface)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["outcome"] = "SOLVED_ACTUALLY_NOT"
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(TrainingDataError, match="content_hash"):
        list(read_jsonl(path))


def test_writing_refuses_a_record_that_does_not_exclude_the_sealed_splits(tmp_path: Path) -> None:
    leaky = Provenance(
        source="leandojo",
        source_id="novel_premises/test.json",
        generator="x",
        generator_version="0",
        sealed_splits_excluded=False,
    )
    with pytest.raises(TrainingDataError, match="sealed_splits_excluded"):
        write_jsonl(
            tmp_path / "s.jsonl", [_record(provenance=leaky)], build_default_registry().default
        )


def test_reading_refuses_a_record_written_for_another_surface(tmp_path: Path) -> None:
    registry = build_default_registry()
    path = tmp_path / "shard.jsonl"
    write_jsonl(path, [_record()], registry.get("tl0"))
    with pytest.raises(TrainingDataError, match="written for surface"):
        list(read_jsonl(path, surface=registry.get("via:L2_SEXPR")))


def test_a_chosen_action_absent_from_the_candidates_is_refused() -> None:
    state = build_rich_state()
    other = Action("a.other", "close", (), (Term("lit", NAT, 1),))
    with pytest.raises(TrainingDataError, match="not among the candidate actions"):
        _record(chosen_action=other, candidate_actions=state.actions)


def test_an_unsupported_record_schema_is_refused() -> None:
    with pytest.raises(TrainingDataError, match="unsupported record schema"):
        _record(schema_version="tl0-training-record-v0")
    with pytest.raises(TrainingDataError, match="non-negative"):
        _record(step_index=-1)


def test_an_empty_shard_is_written_and_read(tmp_path: Path) -> None:
    surface = build_default_registry().default
    path = tmp_path / "empty.jsonl"
    write_jsonl(path, [], surface)
    assert list(read_jsonl(path)) == []
