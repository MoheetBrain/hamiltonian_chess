"""Current-HML-compatible seed surface.

This codec is an Arena-owned compatibility notation only. It imports no truth,
ontology, parser behavior, or privileged semantics from a legacy HML implementation.
"""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L1_CURRENT_HML

from .._json_tools import canonical_json, strict_json_loads
from .._wire import STATE_FIELD_ORDER
from ..base import CandidateLanguage

_HEADER = "HML-COMPATIBILITY-SEED/0.1"


class CurrentHMLCompatibilityLanguage(CandidateLanguage):
    format_id = "arena-hml-compatibility-v0.1"
    compatibility_label = "compatibility-only; no imported semantics"
    genome = L1_CURRENT_HML

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        fields = [f"  {key} := {canonical_json(payload[key])};" for key in STATE_FIELD_ORDER]
        return "\n".join([_HEADER, "state {", *fields, "}"])

    def _decode_payload(self, source: str) -> dict[str, Any]:
        lines = source.splitlines()
        if len(lines) != len(STATE_FIELD_ORDER) + 3:
            raise ValueError("invalid HML compatibility field count")
        if lines[:2] != [_HEADER, "state {"] or lines[-1] != "}":
            raise ValueError("invalid HML compatibility frame")
        result: dict[str, Any] = {}
        for line, key in zip(lines[2:-1], STATE_FIELD_ORDER, strict=True):
            prefix = f"  {key} := "
            if not line.startswith(prefix) or not line.endswith(";"):
                raise ValueError(f"malformed HML compatibility field {key!r}")
            result[key] = strict_json_loads(line[len(prefix) : -1])
        return result


CurrentHMLLanguage = CurrentHMLCompatibilityLanguage
CURRENT_HML = CurrentHMLCompatibilityLanguage()

__all__ = ["CURRENT_HML", "CurrentHMLCompatibilityLanguage", "CurrentHMLLanguage"]
