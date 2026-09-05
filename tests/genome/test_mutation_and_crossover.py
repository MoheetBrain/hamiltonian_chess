from dataclasses import replace

import pytest

from arena.genome import (
    L0_STRUCTURED_ENGLISH,
    L6_GRAPH_TRIPLES,
    Alphabet,
    EvaluationTier,
    GeneFamily,
    GenomeValidationError,
    ImpactClass,
    MutationDecision,
    MutationHistory,
    MutationOperator,
    MutationProposal,
    SoundnessRisk,
    apply_mutation,
    crossover,
)


def _alphabet_proposal() -> MutationProposal:
    return MutationProposal.build(
        parent=L0_STRUCTURED_ENGLISH,
        operator=MutationOperator.CHANGE_TOKEN,
        changes={GeneFamily.ALPHABET: Alphabet.UNICODE.value},
        hypothesis="Unicode operators reduce token count without changing meaning.",
        expected_benefit="Lower message length on symbolic expressions.",
        soundness_risk=SoundnessRisk.LOW,
        required_evaluation_tier=EvaluationTier.SURFACE,
    )


def test_mutation_is_deterministic_and_records_parent_and_tests() -> None:
    proposal = _alphabet_proposal()
    first, first_record = apply_mutation(L0_STRUCTURED_ENGLISH, proposal)
    second, second_record = apply_mutation(L0_STRUCTURED_ENGLISH, proposal)

    assert proposal.proposal_id.startswith("mutation:")
    assert proposal.proposal_hash == _alphabet_proposal().proposal_hash
    assert first == second
    assert first.candidate_id == second.candidate_id
    assert first.parent_ids == (L0_STRUCTURED_ENGLISH.candidate_id,)
    assert first.alphabet is Alphabet.UNICODE
    assert first_record == second_record
    assert {"roundtrip", "token_budget", "unicode_safety"} <= set(proposal.affected_tests)
    assert MutationProposal.from_dict(proposal.to_dict()) == proposal


def test_history_is_explicit_and_immutable() -> None:
    proposal = _alphabet_proposal()
    child, pending = apply_mutation(L0_STRUCTURED_ENGLISH, proposal)
    completed = replace(
        pending,
        evaluation="Passed frozen roundtrip and perturbation suites.",
        regressions=("one extra byte in ASCII-only tasks",),
        decision=MutationDecision.PROMOTED,
    )
    history = MutationHistory().append(completed)
    assert history.records == (completed,)
    assert history.for_candidate(child.candidate_id) == (completed,)
    assert len(completed.record_hash) == 64
    assert MutationHistory.from_dict(history.to_dict()) == history
    with pytest.raises(ValueError, match="duplicate"):
        history.append(completed)


def test_proposal_cannot_understate_structural_impact() -> None:
    with pytest.raises(ValueError, match="understates"):
        MutationProposal.build(
            parent=L0_STRUCTURED_ENGLISH,
            operator=MutationOperator.CHANGE_BINDER_ENCODING,
            changes={GeneFamily.BINDERS: "structural-id"},
            hypothesis="Structural IDs may prevent capture.",
            expected_benefit="Fewer binding errors.",
            soundness_risk=SoundnessRisk.MEDIUM,
            required_evaluation_tier=EvaluationTier.STRUCTURAL,
            impact_class=ImpactClass.SURFACE_ONLY,
        )


def test_mutation_rejects_invalid_resulting_combination() -> None:
    proposal = MutationProposal.build(
        parent=L0_STRUCTURED_ENGLISH,
        operator=MutationOperator.LINEAR_TO_TREE,
        changes={GeneFamily.GRAMMAR: "graph-triple"},
        hypothesis="Test a graph syntax.",
        expected_benefit="Expose dependencies.",
        soundness_risk=SoundnessRisk.HIGH,
        required_evaluation_tier=EvaluationTier.STRUCTURAL,
    )
    with pytest.raises(GenomeValidationError):
        apply_mutation(L0_STRUCTURED_ENGLISH, proposal)


def test_crossover_is_deterministic_and_rejects_incompatible_selection() -> None:
    first, record = crossover(
        L0_STRUCTURED_ENGLISH,
        L6_GRAPH_TRIPLES,
        genes_from_second=(GeneFamily.TOKEN_POLICY,),
    )
    second, repeat = crossover(
        L0_STRUCTURED_ENGLISH,
        L6_GRAPH_TRIPLES,
        genes_from_second=(GeneFamily.TOKEN_POLICY,),
    )
    assert first == second
    assert record == repeat
    assert first.parent_ids == (
        L0_STRUCTURED_ENGLISH.candidate_id,
        L6_GRAPH_TRIPLES.candidate_id,
    )
    assert record.crossover_id.startswith("crossover:")
    assert "token_budget" in record.affected_tests
    assert type(record).from_dict(record.to_dict()) == record

    with pytest.raises(GenomeValidationError):
        crossover(
            L0_STRUCTURED_ENGLISH,
            L6_GRAPH_TRIPLES,
            genes_from_second=(GeneFamily.GRAMMAR,),
        )
