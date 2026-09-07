"""Scoped, lossless source envelope. This is not Arena canonical-v0 or a Lean AST."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from arena.languages._json_tools import canonical_json

SCHEMA_VERSION = "astra-premise-v1"
PROJECTION_VERSION = "astra-premise-visible-v1"
QUESTION = "Select the candidate cited by the recorded next proof step. Reply with one option letter."


@dataclass(frozen=True, slots=True)
class BackendText:
    text: str
    role: str
    backend: str = "lean4-pretty"
    assurance: str = "source-text-not-elaborated"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not isinstance(self.role, str):
            raise ValueError("backend text and role must be strings")
        if self.backend not in {"lean4-pretty", "lean4-source"}:
            raise ValueError("unsupported backend")


@dataclass(frozen=True, slots=True)
class Candidate:
    premise_id: str
    name: str
    statement: BackendText
    provenance: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CanonicalPremiseSelectionState:
    task_id: str
    provenance: dict[str, Any]
    formal_system: str
    context: BackendText
    goal: BackendText
    candidate_premises: tuple[Candidate, ...]
    target_choice_id: str
    oracle_evidence: dict[str, Any]
    source_raw_state: str
    audit_metadata: dict[str, Any]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported premise schema")
        ids = [c.premise_id for c in self.candidate_premises]
        if not 2 <= len(ids) <= 26 or len(ids) != len(set(ids)):
            raise ValueError("require 2..26 uniquely identified candidates")
        if self.target_choice_id not in ids:
            raise ValueError("canonical target missing from candidates")
        if not self.task_id or not self.provenance or not self.oracle_evidence:
            raise ValueError("task, provenance and oracle evidence are required")
        if not self.goal.text.strip() or self.context.text + self.goal.text != self.source_raw_state:
            raise ValueError("context and goal must reconstruct exact recorded source state")
        if any(not c.name or not c.statement.text.strip() or not c.provenance for c in self.candidate_premises):
            raise ValueError("all candidates require names, complete source statements and provenance")
        if len({c.name for c in self.candidate_premises}) != len(ids):
            raise ValueError("duplicate candidate names")

    def to_dict(self) -> dict[str, Any]:
        # JSON normalization returns a detached snapshot, including tuple -> list.
        import json
        return json.loads(canonical_json(asdict(self)))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CanonicalPremiseSelectionState:
        raw = dict(raw)
        raw["context"] = BackendText(**raw["context"])
        raw["goal"] = BackendText(**raw["goal"])
        raw["candidate_premises"] = tuple(
            Candidate(**{**c, "statement": BackendText(**c["statement"])})
            for c in raw["candidate_premises"]
        )
        return cls(**raw)

    @property
    def canonical_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode()).hexdigest()


def order_candidates(task_id: str, candidates: tuple[Candidate, ...], seed: int) -> tuple[Candidate, ...]:
    """One frozen order for every representation; independent of oracle and input order."""
    return tuple(sorted(candidates, key=lambda c: (
        hashlib.sha256(canonical_json([seed, task_id, c.premise_id]).encode()).hexdigest(),
        c.premise_id,
    )))


def visible_projection(state: CanonicalPremiseSelectionState) -> dict[str, Any]:
    """Allowlist only. No renderer receives this state's private oracle or metadata."""
    return {
        "projection_version": PROJECTION_VERSION,
        "question": QUESTION,
        "formal_system": state.formal_system,
        "context": {"backend": state.context.backend, "text": state.context.text},
        "goal": {"backend": state.goal.backend, "text": state.goal.text},
        "candidates": [
            {"option_id": f"option_{i + 1:02d}", "label": chr(65 + i), "name": c.name,
             "statement": {"backend": c.statement.backend, "text": c.statement.text}}
            for i, c in enumerate(state.candidate_premises)
        ],
    }


def label_to_choice_id(state: CanonicalPremiseSelectionState, label: str) -> str:
    if not isinstance(label, str) or len(label) != 1 or not "A" <= label <= "Z":
        raise ValueError("response must be exactly one uppercase option letter")
    index = ord(label) - 65
    if index >= len(state.candidate_premises):
        raise ValueError("response outside candidate set")
    return state.candidate_premises[index].premise_id


def verify_response(state: CanonicalPremiseSelectionState, label: str) -> bool:
    """Recorded citation correctness only; not proof validity or premise sufficiency."""
    return label_to_choice_id(state, label) == state.target_choice_id
