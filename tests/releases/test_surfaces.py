"""Item: the selection seam.  The package must wrap whichever surface is selected."""

from __future__ import annotations

import pytest

from arena.genome.genes import GeneFamily
from arena.genome.seeds import L3_JSON_AST
from arena.languages.registry import SEED_LANGUAGES
from releases.TRAINING_LANGUAGE_V0 import (
    DEFAULT_REGISTRY,
    DEFAULT_SURFACE_ID,
    PROMPT_VIEW,
    CanonicalSurface,
    NativeSurface,
    State,
    SurfaceError,
    SurfaceRegistry,
    build_default_registry,
    wrap_candidate,
    wrap_genome,
)

from .conftest import build_rich_state

SURFACES = tuple(build_default_registry())


@pytest.mark.parametrize("surface", SURFACES, ids=lambda item: item.surface_id)
def test_every_registered_surface_round_trips_a_state(surface: object) -> None:
    state = build_rich_state()
    if not surface.descriptor().lossless_round_trip:  # type: ignore[attr-defined]
        pytest.skip("declared lossy view")
    text = surface.render(state)  # type: ignore[attr-defined]
    assert surface.parse(text) == state  # type: ignore[attr-defined]


@pytest.mark.parametrize("surface", SURFACES, ids=lambda item: item.surface_id)
def test_every_surface_renders_deterministically(surface: object) -> None:
    state = build_rich_state()
    assert len({surface.render(state) for _ in range(5)}) == 1  # type: ignore[attr-defined]


def test_the_shipped_default_is_the_native_surface() -> None:
    assert DEFAULT_REGISTRY.default_id == DEFAULT_SURFACE_ID == "tl0"
    assert isinstance(DEFAULT_REGISTRY.default, NativeSurface)


def test_selecting_a_tournament_winner_is_one_call() -> None:
    registry = build_default_registry()
    winner = SEED_LANGUAGES[2]
    registry.set_default(f"via:{winner.candidate_id}")
    assert isinstance(registry.default, CanonicalSurface)
    assert registry.default.language is winner
    state = build_rich_state()
    assert registry.default.parse(registry.default.render(state)) == state


def test_an_unregistered_candidate_can_be_added_and_selected() -> None:
    registry = SurfaceRegistry(default_id="tl0")
    registry.register(NativeSurface())
    surface = registry.register(wrap_candidate(SEED_LANGUAGES[0], surface_id="selected"))
    registry.set_default("selected")
    assert registry.default is surface
    assert registry.ids() == ("selected", "tl0")


def test_an_evolved_genome_can_be_wrapped() -> None:
    mutant = L3_JSON_AST.with_gene_values(
        {GeneFamily.GRAMMAR: "s-expression"}, candidate_id="M-test-0001"
    )
    surface = wrap_genome(mutant)
    state = build_rich_state()
    assert surface.parse(surface.render(state)) == state
    assert dict(surface.descriptor().configuration)["grammar"] == "s-expression"


def test_registering_a_duplicate_surface_id_is_refused() -> None:
    registry = build_default_registry()
    with pytest.raises(SurfaceError, match="already registered"):
        registry.register(NativeSurface())
    registry.register(NativeSurface(), replace=True)


def test_an_unknown_surface_id_is_refused() -> None:
    with pytest.raises(SurfaceError, match="unknown surface"):
        build_default_registry().get("via:nonexistent")
    with pytest.raises(SurfaceError, match="unknown surface"):
        build_default_registry().set_default("via:nonexistent")


def test_descriptors_distinguish_surfaces() -> None:
    hashes = {surface.descriptor().config_hash for surface in SURFACES}
    assert len(hashes) == len(SURFACES)


def test_the_prompt_view_is_declared_lossy() -> None:
    surface = NativeSurface(PROMPT_VIEW, surface_id="tl0.prompt")
    assert not surface.descriptor().lossless_round_trip


def test_a_wrapper_surface_reports_the_losses_of_its_encoding() -> None:
    surface = CanonicalSurface(SEED_LANGUAGES[3])
    losses = surface.losses(build_rich_state())
    assert losses.is_lossless and not losses.is_native
    assert NativeSurface().losses(build_rich_state()).items == ()


def test_a_wrapper_surface_fails_closed_on_junk() -> None:
    surface = CanonicalSurface(SEED_LANGUAGES[3])
    with pytest.raises(SurfaceError, match="could not parse"):
        surface.parse("not a state at all")


def test_a_state_is_not_mutated_by_being_rendered(rich_state: State) -> None:
    before = build_rich_state()
    for surface in SURFACES:
        surface.render(rich_state)
    assert rich_state == before
