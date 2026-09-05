from dataclasses import replace

import pytest

from arena.genome import (
    GENE_AFFECTED_TESTS,
    GENE_FAMILIES,
    GENE_IMPACT_CLASS,
    L0_STRUCTURED_ENGLISH,
    L3_JSON_AST,
    SEED_GENOME_REGISTRY,
    SEED_GENOMES,
    GeneFamily,
    GenomeRegistry,
    SerializationPolicy,
    gene_field_names,
    validate_genome,
)


def test_all_fourteen_gene_families_are_machine_readable() -> None:
    assert len(GENE_FAMILIES) == 14
    assert gene_field_names() == tuple(family.value for family in GeneFamily)
    assert set(GENE_AFFECTED_TESTS) == set(GeneFamily)
    assert set(GENE_IMPACT_CLASS) == set(GeneFamily)
    assert all(GENE_AFFECTED_TESTS[family] for family in GeneFamily)


def test_seed_population_has_stable_unique_ids_and_hashes() -> None:
    expected_ids = tuple(
        f"L{index}_{suffix}"
        for index, suffix in enumerate(
            (
                "STRUCTURED_ENGLISH",
                "CURRENT_HML",
                "SEXPR",
                "JSON_AST",
                "TYPED_PREFIX",
                "COMPACT_SYMBOLIC",
                "GRAPH_TRIPLES",
                "HYBRID_ROLE_LABELLED",
            )
        )
    )
    assert tuple(genome.candidate_id for genome in SEED_GENOMES) == expected_ids
    assert len({genome.genome_hash for genome in SEED_GENOMES}) == 8
    assert len({genome.candidate_hash for genome in SEED_GENOMES}) == 8
    assert all(len(genome.genome_hash) == 64 for genome in SEED_GENOMES)
    assert all(not genome.parent_ids for genome in SEED_GENOMES)
    assert all(validate_genome(genome).valid for genome in SEED_GENOMES)


def test_genome_roundtrip_preserves_hash() -> None:
    original = L0_STRUCTURED_ENGLISH
    decoded = type(original).from_dict(original.to_dict())
    assert decoded == original
    assert decoded.genome_hash == original.genome_hash
    assert decoded.candidate_hash == original.candidate_hash


def test_invalid_dependency_is_reported() -> None:
    invalid = replace(L3_JSON_AST, serialization=SerializationPolicy.LINE_ORIENTED)
    result = validate_genome(invalid)
    assert not result.valid
    assert {issue.constraint_id for issue in result.issues} == {"json-grammar-is-tree-serialized"}


def test_registry_rejects_duplicate_ids_and_gene_vectors() -> None:
    registry = GenomeRegistry([L0_STRUCTURED_ENGLISH])
    with pytest.raises(ValueError, match="candidate ID"):
        registry.register(L0_STRUCTURED_ENGLISH)
    same_genes_new_name = replace(L0_STRUCTURED_ENGLISH, candidate_id="copy")
    with pytest.raises(ValueError, match="gene-identical"):
        registry.register(same_genes_new_name)
    assert SEED_GENOME_REGISTRY.get("L3_JSON_AST") is L3_JSON_AST


def test_genome_parser_rejects_missing_unknown_and_invalid_gene_values() -> None:
    raw = L0_STRUCTURED_ENGLISH.to_dict()
    del raw["genes"]["alphabet"]
    with pytest.raises(ValueError, match="exactly the fourteen"):
        type(L0_STRUCTURED_ENGLISH).from_dict(raw)

    raw = L0_STRUCTURED_ENGLISH.to_dict()
    raw["genes"]["alphabet"] = "klingon"
    with pytest.raises(ValueError):
        type(L0_STRUCTURED_ENGLISH).from_dict(raw)
