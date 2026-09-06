"""Compiler boundary between immutable canonical truth and evolvable model views."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from arena.canonical.schema import CanonicalAction, CanonicalState, canonical_json, stable_hash
from arena.languages.phenotype import GenomePhenotypeLanguage

from .genome import ModelViewGenome, SearchTrack
from .projection import TruthDerivedView, derive_truth_view

MODEL_VIEW_FORMAT_VERSION = "arena-model-view-compiler-v1.0.0"
_VIEW_MARKER = "\n\n=== TRUTH-DERIVED MODEL VIEW ===\n"


@dataclass(frozen=True, slots=True)
class InformationAccounting:
    canonical_state_hash: str
    previous_state_hash: str | None
    option_set_hash: str
    derived_relation_hashes: tuple[str, ...]
    omitted_relations: tuple[str, ...]
    repeated_witness_count: int
    surface_utf8_bytes: int
    projection_utf8_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_state_hash": self.canonical_state_hash,
            "previous_state_hash": self.previous_state_hash,
            "option_set_hash": self.option_set_hash,
            "derived_relation_hashes": list(self.derived_relation_hashes),
            "omitted_relations": list(self.omitted_relations),
            "repeated_witness_count": self.repeated_witness_count,
            "surface_utf8_bytes": self.surface_utf8_bytes,
            "projection_utf8_bytes": self.projection_utf8_bytes,
        }


@dataclass(frozen=True, slots=True)
class CompiledModelView:
    candidate_id: str
    track: SearchTrack
    text: str
    projection: TruthDerivedView | None
    accounting: InformationAccounting

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "candidate_id": self.candidate_id,
                "track": self.track.value,
                "text": self.text,
                "accounting": self.accounting.to_dict(),
            }
        )


class ModelViewCompiler:
    def __init__(self, genome: ModelViewGenome) -> None:
        self.genome = genome
        self.surface = GenomePhenotypeLanguage(genome.surface)

    def compile(
        self,
        state: CanonicalState,
        *,
        options: tuple[CanonicalAction, ...] = (),
        previous_state: CanonicalState | None = None,
    ) -> CompiledModelView:
        surface_text = self.surface.render(state)
        projection: TruthDerivedView | None = None
        projection_text = ""
        if self.genome.track == SearchTrack.CONTENT_PROJECTION:
            projection = derive_truth_view(
                state, self.genome.content, options=options, previous_state=previous_state
            )
            projection_text = canonical_json(projection.to_dict())
        text = surface_text + (_VIEW_MARKER + projection_text if projection else "")
        relation_dicts = [item.to_dict() for item in projection.relations] if projection else []
        witnesses = [value for item in relation_dicts for value in item["witness_hashes"]]
        accounting = InformationAccounting(
            canonical_state_hash=state.mathematical_hash,
            previous_state_hash=previous_state.mathematical_hash if previous_state else None,
            option_set_hash=stable_hash(
                tuple(
                    {
                        key: value
                        for key, value in action.to_dict().items()
                        if key != "expected_usefulness"
                    }
                    for action in options
                )
            ),
            derived_relation_hashes=tuple(item["relation_hash"] for item in relation_dicts),
            omitted_relations=projection.omissions if projection else (),
            repeated_witness_count=len(witnesses) - len(set(witnesses)),
            surface_utf8_bytes=len(surface_text.encode("utf-8")),
            projection_utf8_bytes=len(projection_text.encode("utf-8")),
        )
        return CompiledModelView(
            candidate_id=self.genome.candidate_id,
            track=self.genome.track,
            text=text,
            projection=projection,
            accounting=accounting,
        )

    def recover_canonical_state(self, compiled: CompiledModelView) -> CanonicalState:
        surface_text = compiled.text.split(_VIEW_MARKER, 1)[0]
        return self.surface.parse(surface_text)

    def validate(
        self,
        compiled: CompiledModelView,
        state: CanonicalState,
        *,
        options: tuple[CanonicalAction, ...] = (),
        previous_state: CanonicalState | None = None,
    ) -> None:
        recovered = self.recover_canonical_state(compiled)
        if recovered.mathematical_hash != state.mathematical_hash:
            raise ValueError("model-view surface does not recover the canonical mathematical state")
        expected = self.compile(state, options=options, previous_state=previous_state)
        if compiled != expected:
            raise ValueError(
                "model view or information accounting is not independently reproducible"
            )
        if compiled.projection is not None:
            raw = json.loads(compiled.text.split(_VIEW_MARKER, 1)[1])
            if stable_hash(raw) != stable_hash(compiled.projection.to_dict()):
                raise ValueError("serialized truth-derived projection differs from compiled record")
