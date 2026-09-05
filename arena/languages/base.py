"""Common language renderer/parser contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from arena.canonical.schema import CanonicalState
from arena.genome.schema import LanguageGenome

from ._wire import WireValidationError, payload_to_state, state_to_payload


class LanguageParseError(ValueError):
    """A candidate surface is malformed or not a canonical state encoding."""


class CandidateLanguage(ABC):
    """Bidirectional, deterministic view of the shared canonical state."""

    format_id: str
    genome: LanguageGenome
    compatibility_label: str | None = None

    @property
    def candidate_id(self) -> str:
        return self.genome.candidate_id

    @property
    def language_id(self) -> str:
        return self.candidate_id

    def render(self, state: CanonicalState) -> str:
        payload = state_to_payload(state)
        rendered = self._encode_payload(payload)
        if not isinstance(rendered, str):
            raise TypeError("language renderer must return text")
        return rendered

    def parse(self, source: str) -> CanonicalState:
        if not isinstance(source, str):
            raise LanguageParseError("candidate source must be text")
        try:
            payload = self._decode_payload(source)
            return payload_to_state(payload)
        except LanguageParseError:
            raise
        except (KeyError, TypeError, ValueError, WireValidationError) as error:
            raise LanguageParseError(f"invalid {self.format_id} source: {error}") from error

    def serialize(self, state: CanonicalState) -> str:
        return self.render(state)

    def deserialize(self, source: str) -> CanonicalState:
        return self.parse(source)

    @abstractmethod
    def _encode_payload(self, payload: dict[str, Any]) -> str: ...

    @abstractmethod
    def _decode_payload(self, source: str) -> dict[str, Any]: ...
