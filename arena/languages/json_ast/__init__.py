"""Generic JSON AST seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L3_JSON_AST

from .._json_tools import canonical_json, strict_json_loads
from ..base import CandidateLanguage


class JsonAstLanguage(CandidateLanguage):
    format_id = "arena-json-ast-v0.1"
    genome = L3_JSON_AST

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        return canonical_json(
            {"candidate": self.candidate_id, "format": self.format_id, "state": payload}
        )

    def _decode_payload(self, source: str) -> dict[str, Any]:
        root = strict_json_loads(source)
        if not isinstance(root, dict) or set(root) != {"candidate", "format", "state"}:
            raise ValueError("JSON AST envelope must contain candidate, format, and state")
        if root["candidate"] != self.candidate_id or root["format"] != self.format_id:
            raise ValueError("JSON AST envelope identifies a different candidate or format")
        if not isinstance(root["state"], dict):
            raise ValueError("JSON AST state must be an object")
        return root["state"]


JSON_AST = JsonAstLanguage()

__all__ = ["JSON_AST", "JsonAstLanguage"]
