"""Every candidate comparison carries an InterventionClass (manual sections 6.26, 12.3, 26).

The class decides the *fairness contract*, so a mislabelled comparison is a scientific defect,
not a cosmetic one: only ``R_ONLY`` may support a representation claim, and only ``R_ONLY``
asserts visible-information parity.  These tests pin the two properties that make the label
trustworthy -- it is DERIVED from the genes actually changed, and it FAILS CLOSED on a gene whose
class has not been declared.
"""

from __future__ import annotations

import pytest

from arena.evolution.record import (
    GENE_INTERVENTION_CLASS,
    GeneChangeRecord,
    InterventionClass,
    MutationDescriptor,
    UnclassifiedGeneError,
    classify_intervention,
)


def _descriptor(*genes: str) -> MutationDescriptor:
    return MutationDescriptor(
        operator="point",
        proposal_id="P-1",
        mutation_hash="h" * 8,
        gene_changes=tuple(GeneChangeRecord(g, "a", "b") for g in genes),
    )


def test_every_current_gene_has_a_declared_class() -> None:
    """A gene with no declared class would otherwise be silently reported as R_ONLY."""

    from dataclasses import fields

    from arena.genome.schema import LanguageGenome

    # Identity and bookkeeping fields are not genes; every remaining field is.
    non_genes = {"candidate_id", "parent_ids", "schema_version"}
    genome_genes = {f.name for f in fields(LanguageGenome) if f.name not in non_genes}
    assert len(genome_genes) == 14, f"expected the 14-family genome, got {len(genome_genes)}"
    assert genome_genes <= set(GENE_INTERVENTION_CLASS), (
        f"undeclared genes: {sorted(genome_genes - set(GENE_INTERVENTION_CLASS))}"
    )


def test_current_genome_is_entirely_representation_only() -> None:
    """A fact about today's fourteen-family genome, asserted so a future O/P gene breaks it."""

    assert set(GENE_INTERVENTION_CLASS.values()) == {InterventionClass.R_ONLY}


def test_single_family_change_is_r_only() -> None:
    assert classify_intervention(["token_policy"]) is InterventionClass.R_ONLY
    assert _descriptor("grammar").intervention_class is InterventionClass.R_ONLY


def test_unknown_gene_fails_closed_rather_than_defaulting() -> None:
    """The defect this prevents: an ontology gene reported as a pure representation effect."""

    with pytest.raises(UnclassifiedGeneError, match="refusing to assume R_ONLY"):
        classify_intervention(["ontology_subgoal"])
    mixed = _descriptor("token_policy", "projection_dependency_edges")
    with pytest.raises(UnclassifiedGeneError):
        _ = mixed.intervention_class


def test_empty_change_set_has_no_class() -> None:
    with pytest.raises(ValueError, match="no changed gene"):
        classify_intervention([])


def test_mixed_classes_are_joint() -> None:
    """Simulates the meta-genome landing: two classes in one child must degrade to JOINT."""

    patched = dict(GENE_INTERVENTION_CLASS)
    patched["ontology_subgoal"] = InterventionClass.O_CHANGE
    saved = dict(GENE_INTERVENTION_CLASS)
    GENE_INTERVENTION_CLASS.clear()
    GENE_INTERVENTION_CLASS.update(patched)
    try:
        assert (
            classify_intervention(["token_policy", "ontology_subgoal"]) is InterventionClass.JOINT
        )
        assert classify_intervention(["ontology_subgoal"]) is InterventionClass.O_CHANGE
    finally:
        GENE_INTERVENTION_CLASS.clear()
        GENE_INTERVENTION_CLASS.update(saved)


def test_only_r_only_asserts_parity_and_permits_a_representation_claim() -> None:
    assert InterventionClass.R_ONLY.requires_visible_information_parity
    assert InterventionClass.R_ONLY.permits_representation_claim
    for other in (
        InterventionClass.P_CHANGE,
        InterventionClass.O_CHANGE,
        InterventionClass.T_CHANGE,
        InterventionClass.A_CHANGE,
        InterventionClass.TAU_CHANGE,
        InterventionClass.C_CHANGE,
        InterventionClass.JOINT,
    ):
        assert not other.requires_visible_information_parity
        assert not other.permits_representation_claim


def test_descriptor_serialises_the_class_and_its_contract() -> None:
    payload = _descriptor("serialization").to_dict()
    assert payload["intervention_class"] == "R_ONLY"
    assert payload["requires_visible_information_parity"] is True
    assert payload["permits_representation_claim"] is True


def test_class_cannot_be_asserted_independently_of_the_genes() -> None:
    """Derived, not stored: a descriptor cannot claim a class its genes do not support."""

    assert "intervention_class" not in {
        f.name for f in MutationDescriptor.__dataclass_fields__.values()
    }
