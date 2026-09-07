"""Item K: the acquisition guide must be candidate-neutral, and checkably so."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    BANNED_TERMS,
    RESERVED_ATTRIBUTE_PREFIX,
    Surface,
    acquisition_guide,
    build_default_registry,
    guide_hash,
    shared_sections,
)
from releases.TRAINING_LANGUAGE_V0.acquisition import CLOSING, PREAMBLE, SYNTAX_BUDGET_CHARS

SURFACES = tuple(build_default_registry())
GUIDES = {surface.surface_id: acquisition_guide(surface) for surface in SURFACES}


def test_the_shared_sections_are_byte_identical_for_every_surface() -> None:
    sections = {shared_sections(guide) for guide in GUIDES.values()}
    assert len(sections) == 1
    head, tail = next(iter(sections))
    assert head == PREAMBLE
    assert tail.strip() == CLOSING.strip()


@pytest.mark.parametrize("surface_id", sorted(GUIDES), ids=sorted(GUIDES))
def test_no_guide_uses_comparative_or_evaluative_vocabulary(surface_id: str) -> None:
    lowered = GUIDES[surface_id].lower()
    offenders = [term for term in BANNED_TERMS if term in lowered]
    assert not offenders, offenders


@pytest.mark.parametrize("surface_id", sorted(GUIDES), ids=sorted(GUIDES))
def test_no_guide_names_a_candidate_or_a_surface(surface_id: str) -> None:
    guide = GUIDES[surface_id]
    assert "via:" not in guide
    # The reserved attribute prefix is part of the data format, not a surface name, so it
    # is removed before the surface-identity check.
    without_prefix = guide.replace(RESERVED_ATTRIBUTE_PREFIX, "")
    for surface in SURFACES:
        assert surface.surface_id not in without_prefix
        configuration = dict(surface.descriptor().configuration)
        candidate = configuration.get("candidate_id")
        if candidate:
            assert candidate not in guide
            assert configuration["format_id"] not in guide


@pytest.mark.parametrize("surface", SURFACES, ids=lambda item: item.surface_id)
def test_every_syntax_note_fits_the_shared_budget(surface: Surface) -> None:
    assert len(surface.syntax_note().strip()) <= SYNTAX_BUDGET_CHARS


def test_the_guides_differ_only_in_their_syntax_section() -> None:
    stripped = set()
    for surface_id, guide in GUIDES.items():
        del surface_id
        head, tail = shared_sections(guide)
        stripped.add((head, tail))
    assert len(stripped) == 1
    assert len({guide for guide in GUIDES.values()}) > 1


def test_an_over_budget_syntax_note_is_refused() -> None:
    class Overlong(Surface):
        surface_id = "overlong"
        family = "test"
        summary = "test"

        def render(self, state: object) -> str:  # type: ignore[override]
            raise NotImplementedError

        def parse(self, text: str) -> object:  # type: ignore[override]
            raise NotImplementedError

        def descriptor(self) -> object:  # type: ignore[override]
            raise NotImplementedError

        def syntax_note(self) -> str:
            return "x" * (SYNTAX_BUDGET_CHARS + 1)

    with pytest.raises(ValueError, match="neutrality budget"):
        acquisition_guide(Overlong())


def test_the_guide_is_short_enough_to_be_a_prompt_envelope() -> None:
    for guide in GUIDES.values():
        assert len(guide) < 3000


def test_guide_hashes_are_stable_and_surface_specific() -> None:
    registry = build_default_registry()
    first = guide_hash(registry.get("tl0"))
    assert first == guide_hash(registry.get("tl0"))
    assert first != guide_hash(registry.get("via:L3_JSON_AST"))


def test_the_committed_guide_matches_the_generated_one() -> None:
    from pathlib import Path

    from releases.TRAINING_LANGUAGE_V0.hashes import PACKAGE_ROOT

    committed = Path(PACKAGE_ROOT / "ACQUISITION_GUIDE.md").read_text(encoding="utf-8")
    assert committed == acquisition_guide(build_default_registry().default)


def test_the_guide_states_the_verified_rule() -> None:
    assert "VERIFIED is not yours to assert" in PREAMBLE
    assert "zero, one or many" in PREAMBLE
