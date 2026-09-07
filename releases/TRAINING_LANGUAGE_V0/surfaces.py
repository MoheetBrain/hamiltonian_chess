"""The selection seam.

This package must be able to wrap **whichever representation the integrator selects**, and
that selection is not this package's to make.  A :class:`Surface` is therefore the single
plug point: it turns a TL0 :class:`core.State` into model-facing text and back, and the
rest of the package -- training records, acquisition guide, hashes -- refers only to the
:class:`SurfaceDescriptor` it publishes.

Two implementations ship:

:class:`NativeSurface`
    Renders TL0's own text.  This is the **default**, on one narrow and defensible ground:
    it is the only surface that renders the whole TL0 core without routing through a schema
    that cannot express multi-goal, scope, substitution or let-values.  That is an
    expressiveness argument, **not** a claim that it trains better.  No such claim is made
    anywhere in this release; see ``VERSION`` and the evidence level
    ``TRAINING_LANGUAGE_V0_BASELINE``.

:class:`CanonicalSurface`
    Wraps any ``arena.languages.base.CandidateLanguage`` -- the eight seed surfaces, a
    ``GenomePhenotypeLanguage`` built from an evolved genome, or whatever the Game-R
    tournament returns.  TL0 state goes through :func:`canonical_adapter.to_canonical`
    first, so the loss report travels with the rendering.

Swapping the default is one call: ``registry.set_default(surface_id)``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass

from arena.canonical.schema import stable_hash
from arena.genome.schema import LanguageGenome
from arena.languages.base import CandidateLanguage
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.languages.registry import SEED_LANGUAGES

from .canonical_adapter import (
    CompatibilityProfile,
    LossPolicy,
    LossReport,
    from_canonical,
    to_canonical,
)
from .core import LANGUAGE_VERSION, State, TL0Error
from .parser import parse_state
from .renderer import LOSSLESS, PROMPT_VIEW, RenderConfig, render_state

DEFAULT_SURFACE_ID = "tl0"


class SurfaceError(TL0Error):
    """A surface could not render or parse."""


@dataclass(frozen=True, slots=True)
class SurfaceDescriptor:
    """Everything downstream needs to know about a surface, and nothing more."""

    surface_id: str
    family: str
    summary: str
    lossless_round_trip: bool
    configuration: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "surface_id": self.surface_id,
            "family": self.family,
            "summary": self.summary,
            "lossless_round_trip": self.lossless_round_trip,
            "configuration": [list(item) for item in self.configuration],
            "tl0_version": LANGUAGE_VERSION,
        }

    @property
    def config_hash(self) -> str:
        return stable_hash(self.to_dict())


class Surface(ABC):
    """Bidirectional view of a TL0 state as model-facing text."""

    surface_id: str
    family: str
    summary: str

    @abstractmethod
    def render(self, state: State) -> str: ...

    @abstractmethod
    def parse(self, text: str) -> State: ...

    @abstractmethod
    def descriptor(self) -> SurfaceDescriptor: ...

    @abstractmethod
    def syntax_note(self) -> str:
        """One mechanically-derived paragraph of *syntax*, never of strategy.

        The acquisition guide splices this between two frozen, byte-identical sections.
        Nothing here may say or imply that one surface is preferable.
        """

    def losses(self, state: State) -> LossReport:
        """What this surface's encoding does to the state.  Empty for a native surface."""

        del state
        return LossReport()

    def target_surface(self) -> Surface:
        """The surface used to render supervision targets.

        A prompt view legitimately hides the candidate action list from the *input*, but a
        target must still be renderable.  This returns a surface of the same grammar family
        whose configuration can carry an action, so input-grammar == output-grammar holds
        even when the input is a view.  Most surfaces are their own target surface.
        """

        return self


class NativeSurface(Surface):
    family = "tl0-native"

    def __init__(
        self, config: RenderConfig = LOSSLESS, *, surface_id: str = DEFAULT_SURFACE_ID
    ) -> None:
        self.surface_id = surface_id
        self.config = config
        self.summary = "TL0's own line-oriented record text."

    def render(self, state: State) -> str:
        return render_state(state, self.config)

    def parse(self, text: str) -> State:
        return parse_state(text)

    def descriptor(self) -> SurfaceDescriptor:
        return SurfaceDescriptor(
            surface_id=self.surface_id,
            family=self.family,
            summary=self.summary,
            lossless_round_trip=self.config.is_lossless,
            configuration=self.config.describe(),
        )

    def target_surface(self) -> Surface:
        if self.config.is_lossless:
            return self
        return NativeSurface(LOSSLESS, surface_id=self.surface_id)

    def syntax_note(self) -> str:
        return (
            "Each line is one record: a keyword then fixed fields. Records are "
            "lib, scope, decl, claim, goal, oblig, evid, subst, dep, ext and status; "
            "act opens a block closed by end. A term is (op [Type] value args...) where "
            'value is _ or a tagged literal #i 1, #f 1.5, #b true, #s "text". A type is '
            '[Head params...]. Attributes are {key="value"}. An underscore means absent.'
        )


class CanonicalSurface(Surface):
    """Wrap any Arena candidate language.  The plug point for the tournament's winner."""

    family = "arena-canonical-wrapper"

    def __init__(
        self,
        language: CandidateLanguage,
        *,
        surface_id: str | None = None,
        profile: CompatibilityProfile = CompatibilityProfile.ARENA_VERIFIER,
        policy: LossPolicy = LossPolicy.CARRY,
    ) -> None:
        self.language = language
        self.profile = profile
        self.policy = policy
        self.surface_id = surface_id or f"via:{language.candidate_id}"
        self.summary = f"TL0 state rendered through the {language.format_id} surface."

    def render(self, state: State) -> str:
        mapping = to_canonical(state, policy=self.policy, profile=self.profile)
        return self.language.render(mapping.canonical)

    def parse(self, text: str) -> State:
        try:
            canonical = self.language.parse(text)
        except Exception as error:  # noqa: BLE001 - candidate codecs raise their own types
            raise SurfaceError(f"{self.surface_id} could not parse: {error}") from error
        return from_canonical(canonical).state

    def losses(self, state: State) -> LossReport:
        return to_canonical(state, policy=self.policy, profile=self.profile).losses

    def descriptor(self) -> SurfaceDescriptor:
        return SurfaceDescriptor(
            surface_id=self.surface_id,
            family=self.family,
            summary=self.summary,
            lossless_round_trip=self.policy is LossPolicy.CARRY,
            configuration=(
                ("format_id", self.language.format_id),
                ("candidate_id", self.language.candidate_id),
                ("profile", self.profile.value),
                ("policy", self.policy.value),
                *sorted(self.language.genome.genes_dict().items()),
            ),
        )

    def syntax_note(self) -> str:
        genes = self.language.genome.genes_dict()
        return (
            "The state is a lossless typed record rendered with "
            f"{genes['grammar']} grammar, {genes['serialization']} serialization, "
            f"{genes['types']} type marking, {genes['binders']} binders, "
            f"{genes['morphology']} field morphology and {genes['redundancy']} redundancy. "
            "Fields named tl0.* on the goal carry structure the record shape has no slot "
            "for: the other goals, the scope forest, the substitution and the declarations."
        )


class SurfaceRegistry:
    """A tiny registry.  The integrator selects here; nothing else needs to change."""

    def __init__(self, *, default_id: str = DEFAULT_SURFACE_ID) -> None:
        self._surfaces: dict[str, Surface] = {}
        self._default_id = default_id

    def register(self, surface: Surface, *, replace: bool = False) -> Surface:
        if surface.surface_id in self._surfaces and not replace:
            raise SurfaceError(f"surface already registered: {surface.surface_id}")
        self._surfaces[surface.surface_id] = surface
        return surface

    def get(self, surface_id: str) -> Surface:
        try:
            return self._surfaces[surface_id]
        except KeyError as error:
            raise SurfaceError(f"unknown surface: {surface_id}") from error

    def set_default(self, surface_id: str) -> None:
        """Select the shipped surface.  This is the whole integration step."""

        self.get(surface_id)
        self._default_id = surface_id

    @property
    def default(self) -> Surface:
        return self.get(self._default_id)

    @property
    def default_id(self) -> str:
        return self._default_id

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._surfaces))

    def __iter__(self) -> Iterator[Surface]:
        return iter(self._surfaces[key] for key in sorted(self._surfaces))

    def __len__(self) -> int:
        return len(self._surfaces)


def wrap_candidate(language: CandidateLanguage, **kwargs: object) -> CanonicalSurface:
    """Wrap a selected Arena candidate language as a TL0 surface."""

    return CanonicalSurface(language, **kwargs)  # type: ignore[arg-type]


def wrap_genome(genome: LanguageGenome) -> CanonicalSurface:
    """Wrap an evolved genome through the genome-driven phenotype codec."""

    return CanonicalSurface(GenomePhenotypeLanguage(genome))


def build_default_registry() -> SurfaceRegistry:
    """The shipped registry: TL0 native, a TL0 prompt view, and every seed surface."""

    registry = SurfaceRegistry()
    registry.register(NativeSurface())
    registry.register(NativeSurface(PROMPT_VIEW, surface_id="tl0.prompt"))
    for language in SEED_LANGUAGES:
        registry.register(CanonicalSurface(language))
    return registry


DEFAULT_REGISTRY = build_default_registry()

__all__ = [
    "DEFAULT_REGISTRY",
    "DEFAULT_SURFACE_ID",
    "CanonicalSurface",
    "NativeSurface",
    "Surface",
    "SurfaceDescriptor",
    "SurfaceError",
    "SurfaceRegistry",
    "build_default_registry",
    "wrap_candidate",
    "wrap_genome",
]
