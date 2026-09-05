"""S-expression seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L2_SEXPR

from .._notation import sexpr_decode, sexpr_encode
from ..base import CandidateLanguage

_PREFIX = "(hamiltonian-state-v0 "


class SExpressionLanguage(CandidateLanguage):
    format_id = "arena-sexpr-v0.1"
    genome = L2_SEXPR

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        return f"{_PREFIX}{sexpr_encode(payload)})"

    def _decode_payload(self, source: str) -> dict[str, Any]:
        if not source.startswith(_PREFIX) or not source.endswith(")"):
            raise ValueError("expected one hamiltonian-state-v0 form")
        raw = sexpr_decode(source[len(_PREFIX) : -1])
        if not isinstance(raw, dict):
            raise ValueError("S-expression state body must be a record")
        return raw


SEXPR = SExpressionLanguage()

__all__ = ["SEXPR", "SExpressionLanguage"]
