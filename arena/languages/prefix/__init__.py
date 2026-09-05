"""Typed prefix seed language."""

from __future__ import annotations

from typing import Any

from arena.genome.seeds import L4_TYPED_PREFIX

from .._notation import typed_prefix_decode, typed_prefix_encode
from ..base import CandidateLanguage

_PREFIX = "TYPED-STATE/0.1 "


class TypedPrefixLanguage(CandidateLanguage):
    format_id = "arena-typed-prefix-v0.1"
    genome = L4_TYPED_PREFIX

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        return _PREFIX + typed_prefix_encode(payload)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        if not source.startswith(_PREFIX):
            raise ValueError("missing typed-prefix state header")
        raw = typed_prefix_decode(source[len(_PREFIX) :])
        if not isinstance(raw, dict):
            raise ValueError("typed-prefix state body must be a dictionary")
        return raw


TYPED_PREFIX = TypedPrefixLanguage()

__all__ = ["TYPED_PREFIX", "TypedPrefixLanguage"]
