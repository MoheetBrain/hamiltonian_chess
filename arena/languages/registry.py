"""Registry for executable candidate language surfaces."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .base import CandidateLanguage
from .graph import GRAPH_TRIPLES
from .hml import CURRENT_HML
from .hybrid import HYBRID_ROLE_LABELLED
from .json_ast import JSON_AST
from .prefix import TYPED_PREFIX
from .sexpr import SEXPR
from .structured_english import STRUCTURED_ENGLISH
from .symbolic import COMPACT_SYMBOLIC


class LanguageRegistry:
    def __init__(self, languages: Iterable[CandidateLanguage] = ()) -> None:
        self._languages: dict[str, CandidateLanguage] = {}
        for language in languages:
            self.register(language)

    def register(self, language: CandidateLanguage) -> None:
        candidate_id = language.candidate_id
        if candidate_id in self._languages:
            raise ValueError(f"candidate language already registered: {candidate_id}")
        self._languages[candidate_id] = language

    def get(self, candidate_id: str) -> CandidateLanguage:
        try:
            return self._languages[candidate_id]
        except KeyError as error:
            raise KeyError(f"unknown candidate language: {candidate_id}") from error

    def __getitem__(self, candidate_id: str) -> CandidateLanguage:
        return self.get(candidate_id)

    def __contains__(self, candidate_id: object) -> bool:
        return candidate_id in self._languages

    def __iter__(self) -> Iterator[CandidateLanguage]:
        return iter(self._languages.values())

    def __len__(self) -> int:
        return len(self._languages)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._languages)


SEED_LANGUAGES = (
    STRUCTURED_ENGLISH,
    CURRENT_HML,
    SEXPR,
    JSON_AST,
    TYPED_PREFIX,
    COMPACT_SYMBOLIC,
    GRAPH_TRIPLES,
    HYBRID_ROLE_LABELLED,
)
LANGUAGE_REGISTRY = LanguageRegistry(SEED_LANGUAGES)


def get_language(candidate_id: str) -> CandidateLanguage:
    return LANGUAGE_REGISTRY.get(candidate_id)


def seed_languages() -> tuple[CandidateLanguage, ...]:
    return SEED_LANGUAGES
