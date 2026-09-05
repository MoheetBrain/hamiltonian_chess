"""Explicit labelled-linear Structured English seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L0_STRUCTURED_ENGLISH

from .._json_tools import canonical_json, strict_json_loads
from .._wire import STATE_FIELD_ORDER
from ..base import CandidateLanguage

_HEADER = "HAMILTONIAN ARENA STRUCTURED ENGLISH 0.1"
_LABELS = {
    "schema_version": "Schema version",
    "state_id": "State identity",
    "objects": "Mathematical objects",
    "bindings": "Bindings",
    "assumptions": "Assumptions",
    "established_facts": "Established facts",
    "propositions": "Propositions",
    "goal": "Goal",
    "obligations": "Open obligations",
    "evidence_dependencies": "Evidence dependencies",
    "local_scope": "Local scope",
    "legal_actions": "Legal actions",
    "plausible_invalid_actions": "Plausible invalid actions",
    "terminal_status": "Terminal status",
    "execution_metadata": "Execution metadata",
}


class StructuredEnglishLanguage(CandidateLanguage):
    format_id = "arena-structured-english-v0.1"
    genome = L0_STRUCTURED_ENGLISH

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        lines = [_HEADER]
        lines.extend(f"{_LABELS[key]}: {canonical_json(payload[key])}" for key in STATE_FIELD_ORDER)
        return "\n".join(lines)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        lines = source.splitlines()
        if len(lines) != len(STATE_FIELD_ORDER) + 1 or lines[0] != _HEADER:
            raise ValueError("invalid Structured English header or field count")
        result: dict[str, Any] = {}
        for line, key in zip(lines[1:], STATE_FIELD_ORDER, strict=True):
            prefix = f"{_LABELS[key]}: "
            if not line.startswith(prefix):
                raise ValueError(f"expected field label {_LABELS[key]!r}")
            result[key] = strict_json_loads(line[len(prefix) :])
        return result


STRUCTURED_ENGLISH = StructuredEnglishLanguage()

__all__ = ["STRUCTURED_ENGLISH", "StructuredEnglishLanguage"]
