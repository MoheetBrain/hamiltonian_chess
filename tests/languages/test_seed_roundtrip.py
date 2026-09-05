import pytest

from arena.genome import SEED_GENOMES
from arena.languages import (
    CURRENT_HML,
    LANGUAGE_REGISTRY,
    SEED_LANGUAGES,
    CandidateLanguage,
    LanguageParseError,
    get_language,
)


def test_registry_exposes_exactly_eight_equal_seed_candidates() -> None:
    assert len(LANGUAGE_REGISTRY) == 8
    assert tuple(language.candidate_id for language in SEED_LANGUAGES) == tuple(
        genome.candidate_id for genome in SEED_GENOMES
    )
    assert all(isinstance(language, CandidateLanguage) for language in SEED_LANGUAGES)
    assert all(get_language(language.candidate_id) is language for language in SEED_LANGUAGES)


@pytest.mark.parametrize("language", SEED_LANGUAGES, ids=lambda item: item.candidate_id)
def test_seed_languages_are_deterministic_and_lossless(language, representative_state) -> None:
    first = language.render(representative_state)
    second = language.render(representative_state)
    reconstructed = language.parse(first)

    assert first == second
    assert reconstructed == representative_state
    assert reconstructed.artifact_hash == representative_state.artifact_hash
    assert reconstructed.mathematical_hash == representative_state.mathematical_hash
    assert language.serialize(representative_state) == first
    assert language.deserialize(first) == representative_state


def test_seed_surfaces_are_distinct_and_transparent(representative_state) -> None:
    rendered = [language.render(representative_state) for language in SEED_LANGUAGES]
    assert len(set(rendered)) == 8
    assert all("state:representative" in source for source in rendered)
    assert all(
        "pickle" not in source.lower() and "base64" not in source.lower() for source in rendered
    )


def test_hml_is_explicitly_only_a_compatibility_seed() -> None:
    assert CURRENT_HML.compatibility_label == "compatibility-only; no imported semantics"
    assert CURRENT_HML.candidate_id == "L1_CURRENT_HML"


@pytest.mark.parametrize("language", SEED_LANGUAGES, ids=lambda item: item.candidate_id)
def test_every_parser_rejects_empty_and_truncated_sources(language, representative_state) -> None:
    source = language.render(representative_state)
    with pytest.raises(LanguageParseError):
        language.parse("")
    with pytest.raises(LanguageParseError):
        language.parse(source[:-1])
