"""Deterministic two-parent crossover for valid language genomes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Self

from .genes import GeneFamily
from .schema import LanguageGenome, derive_candidate_id
from .validation import affected_tests, require_valid_genome


def _stable_hash(raw: object) -> str:
    encoded = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CrossoverRecord:
    crossover_id: str
    parent_ids: tuple[str, str]
    genes_from_second_parent: tuple[GeneFamily, ...]
    result_candidate_id: str
    result_candidate_hash: str

    @property
    def changed_genes(self) -> tuple[GeneFamily, ...]:
        return self.genes_from_second_parent

    @property
    def affected_tests(self) -> tuple[str, ...]:
        return affected_tests(self.changed_genes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "crossover_id": self.crossover_id,
            "parent_ids": list(self.parent_ids),
            "genes_from_second_parent": [gene.value for gene in self.genes_from_second_parent],
            "result_candidate_id": self.result_candidate_id,
            "result_candidate_hash": self.result_candidate_hash,
            "affected_tests": list(self.affected_tests),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        expected = {
            "crossover_id",
            "parent_ids",
            "genes_from_second_parent",
            "result_candidate_id",
            "result_candidate_hash",
            "affected_tests",
        }
        if set(raw) != expected:
            raise ValueError("crossover record has missing or unknown fields")
        parent_ids = raw["parent_ids"]
        genes = raw["genes_from_second_parent"]
        if (
            not isinstance(parent_ids, list)
            or len(parent_ids) != 2
            or not all(isinstance(item, str) for item in parent_ids)
        ):
            raise ValueError("crossover parent_ids must contain two strings")
        if not isinstance(genes, list) or not all(isinstance(item, str) for item in genes):
            raise ValueError("crossover genes must be a list of gene-family names")
        record = cls(
            crossover_id=str(raw["crossover_id"]),
            parent_ids=(parent_ids[0], parent_ids[1]),
            genes_from_second_parent=tuple(GeneFamily(item) for item in genes),
            result_candidate_id=str(raw["result_candidate_id"]),
            result_candidate_hash=str(raw["result_candidate_hash"]),
        )
        if raw["affected_tests"] != list(record.affected_tests):
            raise ValueError("crossover affected_tests do not match selected genes")
        identity = {
            "parent_ids": list(record.parent_ids),
            "genes_from_second_parent": [gene.value for gene in record.genes_from_second_parent],
            "result_candidate_id": record.result_candidate_id,
            "result_candidate_hash": record.result_candidate_hash,
        }
        expected_id = f"crossover:{_stable_hash(identity)[:20]}"
        if record.crossover_id != expected_id:
            raise ValueError("crossover_id does not match crossover content")
        return record


def crossover(
    first: LanguageGenome,
    second: LanguageGenome,
    *,
    genes_from_second: Iterable[GeneFamily | str],
) -> tuple[LanguageGenome, CrossoverRecord]:
    if first.candidate_id == second.candidate_id:
        raise ValueError("crossover parents must have distinct candidate IDs")
    selected = tuple(sorted({GeneFamily(gene) for gene in genes_from_second}, key=str))
    if not selected:
        raise ValueError("crossover must select at least one gene from the second parent")

    gene_values = first.genes_dict()
    for family in selected:
        gene_values[family.value] = second.gene(family)
    parent_ids = (first.candidate_id, second.candidate_id)
    candidate_id = derive_candidate_id(parent_ids=parent_ids, genes=gene_values, prefix="X")
    selected_values: dict[GeneFamily | str, str] = {
        family: gene_values[family.value] for family in selected
    }
    child = first.with_gene_values(
        selected_values,
        candidate_id=candidate_id,
        parent_ids=parent_ids,
    )
    require_valid_genome(child)

    identity = {
        "parent_ids": list(parent_ids),
        "genes_from_second_parent": [gene.value for gene in selected],
        "result_candidate_id": child.candidate_id,
        "result_candidate_hash": child.candidate_hash,
    }
    record = CrossoverRecord(
        crossover_id=f"crossover:{_stable_hash(identity)[:20]}",
        parent_ids=parent_ids,
        genes_from_second_parent=selected,
        result_candidate_id=child.candidate_id,
        result_candidate_hash=child.candidate_hash,
    )
    return child, record
