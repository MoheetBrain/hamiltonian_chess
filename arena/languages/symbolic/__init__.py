"""Compact symbolic seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L5_COMPACT_SYMBOLIC

from .._json_tools import canonical_json, strict_json_loads
from .._wire import STATE_FIELD_ORDER
from ..base import CandidateLanguage

_HEADER = "ΣHC0|"
_ALIASES = dict(
    zip(
        STATE_FIELD_ORDER,
        ("v", "i", "o", "b", "a", "f", "p", "g", "q", "e", "s", "l", "x", "t", "m"),
        strict=True,
    )
)
_FIELDS = {alias: field for field, alias in _ALIASES.items()}


class CompactSymbolicLanguage(CandidateLanguage):
    format_id = "arena-compact-symbolic-v0.1"
    genome = L5_COMPACT_SYMBOLIC

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        compact = {_ALIASES[field]: payload[field] for field in STATE_FIELD_ORDER}
        return _HEADER + canonical_json(compact)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        if not source.startswith(_HEADER):
            raise ValueError("missing compact-symbolic header")
        compact = strict_json_loads(source[len(_HEADER) :])
        if not isinstance(compact, dict) or set(compact) != set(_FIELDS):
            raise ValueError("compact-symbolic state has missing or unknown roles")
        return {field: compact[alias] for field, alias in _ALIASES.items()}


COMPACT_SYMBOLIC = CompactSymbolicLanguage()

__all__ = ["COMPACT_SYMBOLIC", "CompactSymbolicLanguage"]
