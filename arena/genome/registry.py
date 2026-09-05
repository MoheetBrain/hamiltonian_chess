"""Genome registry with duplicate identity protection."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .schema import LanguageGenome
from .seeds import SEED_GENOMES
from .validation import require_valid_genome


class GenomeRegistry:
    def __init__(self, genomes: Iterable[LanguageGenome] = ()) -> None:
        self._by_id: dict[str, LanguageGenome] = {}
        self._id_by_hash: dict[str, str] = {}
        for genome in genomes:
            self.register(genome)

    def register(self, genome: LanguageGenome) -> None:
        require_valid_genome(genome)
        if genome.candidate_id in self._by_id:
            raise ValueError(f"candidate ID already registered: {genome.candidate_id}")
        duplicate = self._id_by_hash.get(genome.genome_hash)
        if duplicate is not None:
            raise ValueError(
                f"gene-identical candidate already registered as {duplicate}: {genome.candidate_id}"
            )
        self._by_id[genome.candidate_id] = genome
        self._id_by_hash[genome.genome_hash] = genome.candidate_id

    def get(self, candidate_id: str) -> LanguageGenome:
        try:
            return self._by_id[candidate_id]
        except KeyError as error:
            raise KeyError(f"unknown language genome: {candidate_id}") from error

    def by_genome_hash(self, genome_hash: str) -> LanguageGenome:
        try:
            return self._by_id[self._id_by_hash[genome_hash]]
        except KeyError as error:
            raise KeyError(f"unknown genome hash: {genome_hash}") from error

    def __contains__(self, candidate_id: object) -> bool:
        return candidate_id in self._by_id

    def __iter__(self) -> Iterator[LanguageGenome]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)


SEED_GENOME_REGISTRY = GenomeRegistry(SEED_GENOMES)
