"""Immutable, content-addressable language genomes."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, Self

from .genes import (
    ActionPolicy,
    Alphabet,
    BinderPolicy,
    CompositionPolicy,
    ErrorLocalityPolicy,
    EvidencePolicy,
    GeneFamily,
    GrammarFamily,
    Morphology,
    ObligationPolicy,
    RedundancyPolicy,
    SerializationPolicy,
    StatePolicy,
    TokenPolicy,
    TypePolicy,
    parse_gene_value,
)

GENOME_SCHEMA_VERSION = "arena-language-genome-v0.1.0"
_CANDIDATE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LanguageGenome:
    """The fourteen evolvable language gene families and explicit ancestry.

    ``candidate_id`` is a stable display identity. ``genome_hash`` is the identity of
    the gene vector, while ``candidate_hash`` additionally commits to ancestry and the
    display identity. This keeps named seed IDs useful without weakening reproducibility.
    """

    candidate_id: str
    parent_ids: tuple[str, ...]
    alphabet: Alphabet
    token_policy: TokenPolicy
    morphology: Morphology
    grammar: GrammarFamily
    composition: CompositionPolicy
    types: TypePolicy
    binders: BinderPolicy
    state: StatePolicy
    actions: ActionPolicy
    obligations: ObligationPolicy
    evidence: EvidencePolicy
    serialization: SerializationPolicy
    redundancy: RedundancyPolicy
    error_locality: ErrorLocalityPolicy
    schema_version: str = GENOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not _CANDIDATE_ID_RE.fullmatch(self.candidate_id):
            raise ValueError(f"invalid candidate_id: {self.candidate_id!r}")
        if len(set(self.parent_ids)) != len(self.parent_ids):
            raise ValueError("parent_ids must be unique")
        if self.candidate_id in self.parent_ids:
            raise ValueError("a candidate cannot be its own parent")
        for parent_id in self.parent_ids:
            if not _CANDIDATE_ID_RE.fullmatch(parent_id):
                raise ValueError(f"invalid parent candidate ID: {parent_id!r}")
        if self.schema_version != GENOME_SCHEMA_VERSION:
            raise ValueError(f"unsupported genome schema: {self.schema_version!r}")

    @property
    def id(self) -> str:
        """Compatibility alias for callers using the directive's shorter field name."""

        return self.candidate_id

    def genes_dict(self) -> dict[str, str]:
        return {family.value: getattr(self, family.value).value for family in GeneFamily}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "parent_ids": list(self.parent_ids),
            "genes": self.genes_dict(),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        if not isinstance(raw, dict) or set(raw) != {
            "schema_version",
            "candidate_id",
            "parent_ids",
            "genes",
        }:
            raise ValueError("genome record has missing or unknown fields")
        genes = raw["genes"]
        if not isinstance(genes, dict) or set(genes) != {family.value for family in GeneFamily}:
            raise ValueError("genome must contain exactly the fourteen gene families")
        parent_ids = raw["parent_ids"]
        if not isinstance(parent_ids, list) or not all(
            isinstance(item, str) for item in parent_ids
        ):
            raise ValueError("parent_ids must be a list of strings")
        return cls(
            candidate_id=str(raw["candidate_id"]),
            parent_ids=tuple(parent_ids),
            schema_version=str(raw["schema_version"]),
            alphabet=Alphabet(genes["alphabet"]),
            token_policy=TokenPolicy(genes["token_policy"]),
            morphology=Morphology(genes["morphology"]),
            grammar=GrammarFamily(genes["grammar"]),
            composition=CompositionPolicy(genes["composition"]),
            types=TypePolicy(genes["types"]),
            binders=BinderPolicy(genes["binders"]),
            state=StatePolicy(genes["state"]),
            actions=ActionPolicy(genes["actions"]),
            obligations=ObligationPolicy(genes["obligations"]),
            evidence=EvidencePolicy(genes["evidence"]),
            serialization=SerializationPolicy(genes["serialization"]),
            redundancy=RedundancyPolicy(genes["redundancy"]),
            error_locality=ErrorLocalityPolicy(genes["error_locality"]),
        )

    @property
    def genome_hash(self) -> str:
        """Stable SHA-256 identity of the fourteen-gene vector."""

        return _sha256({"schema_version": self.schema_version, "genes": self.genes_dict()})

    @property
    def candidate_hash(self) -> str:
        """Stable SHA-256 identity including candidate name and ancestry."""

        return _sha256(self.to_dict())

    @property
    def content_hash(self) -> str:
        return self.candidate_hash

    def gene(self, family: GeneFamily | str) -> str:
        parsed = GeneFamily(family)
        return getattr(self, parsed.value).value

    def with_gene_values(
        self,
        values: Mapping[GeneFamily | str, str],
        *,
        candidate_id: str,
        parent_ids: tuple[str, ...] | None = None,
    ) -> Self:
        updated_genes = self.genes_dict()
        for family_value, value in values.items():
            family = GeneFamily(family_value)
            updated_genes[family.value] = parse_gene_value(family, value).value
        raw = self.to_dict()
        raw["candidate_id"] = candidate_id
        raw["parent_ids"] = list(parent_ids if parent_ids is not None else (self.candidate_id,))
        raw["genes"] = updated_genes
        return type(self).from_dict(raw)


def derive_candidate_id(
    *,
    parent_ids: tuple[str, ...],
    genes: dict[str, str],
    prefix: str = "R",
) -> str:
    """Derive a deterministic, ancestry-aware candidate ID."""

    if not _CANDIDATE_ID_RE.fullmatch(prefix):
        raise ValueError(f"invalid candidate ID prefix: {prefix!r}")
    digest = _sha256(
        {
            "schema_version": GENOME_SCHEMA_VERSION,
            "parent_ids": list(parent_ids),
            "genes": genes,
        }
    )
    return f"{prefix}-{digest[:20]}"


def gene_field_names() -> tuple[str, ...]:
    """Return the schema's gene fields in stable declaration order."""

    non_genes = {"candidate_id", "parent_ids", "schema_version"}
    return tuple(item.name for item in fields(LanguageGenome) if item.name not in non_genes)
