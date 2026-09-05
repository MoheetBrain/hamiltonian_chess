"""Hybrid role-labelled seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L7_HYBRID_ROLE_LABELLED

from .._notation import sexpr_decode, sexpr_encode
from .._wire import STATE_FIELD_ORDER
from ..base import CandidateLanguage

_HEADER = "ROLE-STATE/HYBRID/0.1"


class HybridRoleLabelledLanguage(CandidateLanguage):
    format_id = "arena-hybrid-role-labelled-v0.1"
    genome = L7_HYBRID_ROLE_LABELLED

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        lines = [_HEADER]
        lines.extend(f"@{key} => {sexpr_encode(payload[key])}" for key in STATE_FIELD_ORDER)
        return "\n".join(lines)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        lines = source.splitlines()
        if len(lines) != len(STATE_FIELD_ORDER) + 1 or lines[0] != _HEADER:
            raise ValueError("invalid hybrid role-labelled header or field count")
        result: dict[str, Any] = {}
        for line, key in zip(lines[1:], STATE_FIELD_ORDER, strict=True):
            prefix = f"@{key} => "
            if not line.startswith(prefix):
                raise ValueError(f"expected hybrid role {key!r}")
            result[key] = sexpr_decode(line[len(prefix) :])
        return result


HYBRID_ROLE_LABELLED = HybridRoleLabelledLanguage()

__all__ = ["HYBRID_ROLE_LABELLED", "HybridRoleLabelledLanguage"]
