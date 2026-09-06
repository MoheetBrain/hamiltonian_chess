"""Render identical canonical examples without giving a language private information."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from arena.canonical.schema import CanonicalState, CanonicalTrajectory, stable_hash
from arena.compiler.projection import ObservationKind, project_state_for_observation


class StateRenderer(Protocol):
    candidate_id: str

    def render(self, state: CanonicalState) -> str: ...


@dataclass(frozen=True)
class RenderedExample:
    example_id: str
    canonical_id: str
    candidate_id: str
    task_kind: str
    input_text: str
    target_text: str
    input_hash: str
    target_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "example_id": self.example_id,
            "canonical_id": self.canonical_id,
            "candidate_id": self.candidate_id,
            "task_kind": self.task_kind,
            "input_text": self.input_text,
            "target_text": self.target_text,
            "input_hash": self.input_hash,
            "target_hash": self.target_hash,
        }


def render_next_action_example(
    trajectory: CanonicalTrajectory, renderer: StateRenderer
) -> RenderedExample:
    if not trajectory.transitions:
        raise ValueError(f"trajectory {trajectory.trajectory_id} has no transition")
    transition = trajectory.transitions[0]
    observation = project_state_for_observation(
        transition.state_before, ObservationKind.NEXT_ACTION
    )
    input_text = renderer.render(observation)
    target = transition.action.to_dict()
    target_text = json.dumps(target, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    identity = {
        "canonical_id": trajectory.trajectory_id,
        "candidate": renderer.candidate_id,
        "task": "NEXT_ACTION",
    }
    return RenderedExample(
        example_id=f"example:{stable_hash(identity)[:20]}",
        canonical_id=trajectory.trajectory_id,
        candidate_id=renderer.candidate_id,
        task_kind="NEXT_ACTION",
        input_text=input_text,
        target_text=target_text,
        input_hash=stable_hash(input_text),
        target_hash=stable_hash(target),
    )


def render_matched_datasets(
    trajectories: tuple[CanonicalTrajectory, ...], renderers: tuple[StateRenderer, ...]
) -> dict[str, tuple[RenderedExample, ...]]:
    canonical_ids = tuple(item.trajectory_id for item in trajectories)
    if len(canonical_ids) != len(set(canonical_ids)):
        raise ValueError("canonical trajectory IDs must be unique")
    return {
        renderer.candidate_id: tuple(
            render_next_action_example(trajectory, renderer) for trajectory in trajectories
        )
        for renderer in renderers
    }


def assert_matched_semantics(datasets: dict[str, tuple[RenderedExample, ...]]) -> None:
    """Fail closed. A matched comparison needs at least two non-empty candidate datasets.

    The first version was vacuously true on an empty mapping: a set of zero sequences and a
    set of one both satisfy ``len(...) > 1`` being false, so zero arms passed. During the
    Tier-2 sprint it reported PASS over a dataset dict built from mis-spelled candidate ids,
    which contained nothing at all. A guard that cannot fail on the empty case is not a
    guard, and the case it missed is the one that would make an entire GPU run meaningless.

    Two surfaces that render byte-identical inputs are also refused: they are the same
    experiment run twice, and any difference between them could only be noise.
    """

    if len(datasets) < 2:
        raise ValueError(
            f"matched comparison requires at least two candidate surfaces, got "
            f"{len(datasets)}: {sorted(datasets)}"
        )
    empty = sorted(candidate for candidate, examples in datasets.items() if not examples)
    if empty:
        raise ValueError(f"candidate datasets are empty for {empty}")
    lengths = {len(examples) for examples in datasets.values()}
    if len(lengths) > 1:
        raise ValueError(f"candidate datasets differ in length: {sorted(lengths)}")
    input_sequences = {
        candidate: tuple(item.input_hash for item in examples)
        for candidate, examples in datasets.items()
    }
    if len(set(input_sequences.values())) != len(input_sequences):
        raise ValueError("two candidate surfaces rendered byte-identical inputs")
    canonical_sequences = {
        candidate: tuple(item.canonical_id for item in examples)
        for candidate, examples in datasets.items()
    }
    if len(set(canonical_sequences.values())) > 1:
        raise ValueError("candidate datasets do not contain identical canonical trajectories")
    target_sequences = {
        candidate: tuple(item.target_hash for item in examples)
        for candidate, examples in datasets.items()
    }
    if len(set(target_sequences.values())) > 1:
        raise ValueError("candidate datasets do not contain identical mathematical targets")


def write_jsonl(path: str | Path, examples: tuple[RenderedExample, ...]) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) for item in examples]
    payload = "\n".join(lines) + ("\n" if lines else "")
    destination.write_text(payload, encoding="utf-8")
    return stable_hash([item.to_dict() for item in examples])
