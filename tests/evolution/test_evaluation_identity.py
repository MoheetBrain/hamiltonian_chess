"""RT-13: evaluation identity is semantic, so a re-rolled hash buys no second draw.

``docs/HC_V0_RED_TEAM.md`` RT-13 is the finding an evolutionary search would exploit unaided.
Under the old eleven-component identity ``mutation_hash`` was one of the components and was
caller-supplied, so a proposer that re-emitted the same parent -> child edge under a new proposal
id got a second ``FRESH`` record for the same experiment.  With a stochastic evaluator that is
best-of-N sampling reported as one result: the winner's curse of the manual's section 30.4, with
no multiplicity accounting anywhere in the ledger.

The fix is not a check on ``mutation_hash``.  It is that evaluation identity now answers *what
experiment was this*, and proposal bookkeeping is not part of the answer.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from arena.evolution.record import (
    EVALUATION_IDENTITY_COMPONENTS,
    PRIMARY_REPLICATE_ID,
    PROPOSAL_BOOKKEEPING_FIELDS,
    EvaluationMode,
    EvidenceActor,
    EvolutionRecordStore,
    FitnessMemoryIdentityViolation,
    RecordIdentityViolation,
    RecordScope,
    ReplicateAuthorisation,
    UnauthorisedReplicateError,
)
from arena.storage.artifacts import ArtifactStore
from tests.evolution import factory

AUTHORISED_REPLICATE = ReplicateAuthorisation(
    replicate_id="replicate:0001",
    authorised_by="preregistration:HC-V0-VARIANCE",
    reason="measure between-draw variance of a stochastic Solver at fixed condition",
    plan_id="plan:hc-v0-replication-001",
)


def store(tmp_path: Path) -> EvolutionRecordStore:
    return EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)


# ------------------------------------------------------- the identity's declared shape


def test_proposal_bookkeeping_is_not_an_identity_component() -> None:
    """The RT-13 defect, stated as a property of the component list itself."""

    assert not set(PROPOSAL_BOOKKEEPING_FIELDS) & set(EVALUATION_IDENTITY_COMPONENTS)
    assert "mutation_hash" not in EVALUATION_IDENTITY_COMPONENTS
    assert "proposal_id" not in EVALUATION_IDENTITY_COMPONENTS
    assert "created_at" not in EVALUATION_IDENTITY_COMPONENTS


def test_the_identity_binds_every_component_the_experiment_depends_on() -> None:
    """Each name here is a way two evaluations can differ and still be called the same one."""

    assert set(EVALUATION_IDENTITY_COMPONENTS) == {
        "schema_version",
        "harness_version",
        "evaluation_mode",
        "actor",
        "parent_genome_hash",
        "child_genome_hash",
        "intervention_class",
        "environment_version",
        "evaluation_manifest_hash",
        "ladder_level",
        "solver_digest",
        "solver_revision",
        "decoding_hash",
        "tokenizer_condition",
        "runtime_condition",
        "controller",
        "toolset",
        "adaptation_condition",
        "adaptation_budget",
        "inference_condition",
        "replicate_id",
    }
    identity = factory.record().identity
    assert identity["intervention_class"] == "R_ONLY"
    assert identity["replicate_id"] == PRIMARY_REPLICATE_ID


# --------------------------------------------- acceptance 1: a re-roll is reuse, not a draw


def test_rerolling_mutation_metadata_is_reuse_not_a_second_draw(tmp_path: Path) -> None:
    """The headline acceptance test: same experiment, new bookkeeping, one record."""

    base = factory.record()
    rerolled = replace(
        base,
        mutation=replace(
            base.mutation,
            mutation_hash=base.mutation.mutation_hash[::-1],
            proposal_id="mutation:zzzzzzzzzzzzzzzzzzzz",
        ),
        created_at="2027-01-01T12:00:00.000000+00:00",
    )

    assert rerolled.mutation.mutation_hash != base.mutation.mutation_hash
    assert rerolled.mutation.proposal_id != base.mutation.proposal_id
    # Same experiment: same identity, same condition, same content.
    assert rerolled.record_id == base.record_id
    assert rerolled.condition_id == base.condition_id
    assert rerolled.content_hash == base.content_hash
    assert rerolled.result_hash == base.result_hash
    # ... and the derived hash of the mutation itself is untouched by the re-roll.
    assert rerolled.mutation.intervention_hash == base.mutation.intervention_hash

    ledger = store(tmp_path)
    assert ledger.append(base).scope is RecordScope.FRESH
    assert ledger.append(rerolled).scope is RecordScope.SAME_CONDITION_REUSE
    assert len(ledger.record_paths()) == 1


def test_an_arbitrary_extra_field_cannot_buy_a_draw_either(tmp_path: Path) -> None:
    """A nonce has nowhere to go that forks the identity; the worst it does is force a refusal.

    ``parameters`` is the only free-form dict on the descriptor, and it *is* hashed, so a record
    carrying a timestamp there is a different record under the *same* identity - which the
    existing re-scoring guard already refuses.  Refusal is the right answer: it is loud, and it is
    not a second independent draw.
    """

    base = factory.record()
    nonced = replace(
        base,
        mutation=replace(
            base.mutation,
            parameters={**base.mutation.parameters, "nonce": "2026-09-08T00:00:01Z"},
        ),
    )
    assert nonced.record_id == base.record_id

    ledger = store(tmp_path)
    ledger.append(base)
    with pytest.raises(FitnessMemoryIdentityViolation):
        ledger.append(nonced)
    assert len(ledger.record_paths()) == 1


# ------------------------------------- acceptance 2: an authorised replicate still works


def test_an_authorised_replicate_is_a_new_identity_and_a_real_second_draw(tmp_path: Path) -> None:
    base = factory.record()
    replicate = replace(base, replicate=AUTHORISED_REPLICATE)

    assert replicate.record_id != base.record_id
    # ... but the *condition* is shared, which is what makes the two poolable as replicates of
    # one experiment rather than two different experiments.
    assert replicate.condition_id == base.condition_id

    ledger = store(tmp_path)
    assert ledger.append(base).scope is RecordScope.FRESH
    assert ledger.append(replicate).scope is RecordScope.FRESH
    assert len(ledger.record_paths()) == 2
    assert ledger.summary()["replicates"] == [PRIMARY_REPLICATE_ID, "replicate:0001"]


def test_a_replicate_without_an_authorisation_cannot_be_constructed() -> None:
    """The price of a second draw is a declaration; that is the whole difference from a nonce."""

    with pytest.raises(UnauthorisedReplicateError, match="not authorised"):
        ReplicateAuthorisation(replicate_id="replicate:0001", authorised_by="me")
    with pytest.raises(UnauthorisedReplicateError, match="reserved primary authoriser"):
        ReplicateAuthorisation(
            replicate_id="replicate:0002",
            authorised_by="PRIMARY_DRAW",
            reason="r",
            plan_id="p",
        )
    with pytest.raises(UnauthorisedReplicateError, match="unusable replicate id"):
        ReplicateAuthorisation(replicate_id="whatever-i-like")
    with pytest.raises(UnauthorisedReplicateError, match="primary draw"):
        ReplicateAuthorisation(reason="dressing a replicate up as the first draw")


def test_re_authorising_one_replicate_collides_rather_than_replacing_it(tmp_path: Path) -> None:
    """``replicate_id`` is the identity; the justification travels in the hashed content."""

    base = factory.record()
    first = replace(base, replicate=AUTHORISED_REPLICATE)
    rewritten = replace(
        base,
        replicate=replace(AUTHORISED_REPLICATE, reason="a different reason, after the fact"),
    )
    assert rewritten.record_id == first.record_id
    assert rewritten.content_hash != first.content_hash

    ledger = store(tmp_path)
    ledger.append(first)
    with pytest.raises(FitnessMemoryIdentityViolation, match="record content"):
        ledger.append(rewritten)


# --------------------------------- acceptance 3 and 4: conditions and genomes fork identity


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("digest", "e" * 64),
        ("revision", "r2"),
        ("decoding_hash", "f" * 64),
        ("tokenizer_id", "tok:v2"),
        ("tokenizer_exact", True),
        ("runtime_condition", "gpu-live"),
    ],
)
def test_any_change_of_solver_or_runtime_condition_is_a_new_identity(
    field: str, value: object
) -> None:
    base = factory.record()
    moved = replace(base, model=replace(base.model, **{field: value}))
    assert moved.record_id != base.record_id, field
    assert moved.condition_id != base.condition_id, field


@pytest.mark.parametrize(
    "field",
    ["controller", "toolset", "adaptation_condition", "adaptation_budget", "inference_condition"],
)
def test_any_change_of_experimental_condition_is_a_new_identity(field: str) -> None:
    base = factory.record()
    moved = replace(base, condition=replace(base.condition, **{field: "something-else"}))
    assert moved.record_id != base.record_id, field
    assert moved.condition_id != base.condition_id, field


def test_evaluation_mode_forks_the_identity() -> None:
    """A stub run and a scientific run of one edge are different records, never substitutes."""

    assert factory.stub_record().record_id != factory.record().record_id
    assert factory.stub_record().condition_id != factory.record().condition_id


def test_a_parent_or_child_genome_change_is_a_new_identity() -> None:
    base = factory.record()
    assert replace(base, parent_genome_hash="q" * 64).record_id != base.record_id
    assert replace(base, child_genome_hash="q" * 64).record_id != base.record_id


def test_the_evaluation_manifest_not_merely_the_task_ids_is_bound() -> None:
    """The same task ids drawn from a different pool or role are a different evaluation."""

    base = factory.record()
    for change in (
        {"pool_id": "ADV_DEV"},
        {"pool_role": "EVAL"},
        {"fidelity_level": 2},
        {"horizon_bucket": "H5"},
        {"task_ids": ("t:0", "t:2")},
    ):
        moved = replace(base, evaluation_context=replace(base.evaluation_context, **change))
        assert moved.record_id != base.record_id, change
        assert (
            moved.evaluation_context.evaluation_manifest_hash
            != base.evaluation_context.evaluation_manifest_hash
        ), change


def test_the_intervention_class_reaches_the_identity_derived_not_asserted() -> None:
    """Manual section 6.26: the class is a function of the genes, so it cannot be claimed."""

    base = factory.record()
    assert base.identity["intervention_class"] == base.mutation.intervention_class.value
    assert "intervention_class" not in {
        item.name for item in base.mutation.__dataclass_fields__.values()
    }


def test_a_stub_record_still_reproduces_its_identity_across_a_round_trip(tmp_path: Path) -> None:
    """The new components survive serialisation, and a tampered stored identity is refused."""

    ledger = store(tmp_path)
    ledger.append(factory.stub_record())
    reopened = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    (restored,) = reopened.records()
    assert restored.evaluation_mode is EvaluationMode.EXECUTABILITY_STUB
    assert restored.actor is EvidenceActor.SOLVER
    assert restored.record_id == factory.stub_record().record_id
    assert restored.condition.controller == "none:single-shot-choice"
    assert restored.replicate.is_primary


def test_the_bookkeeping_trade_is_exactly_this_and_no_wider(tmp_path: Path) -> None:
    """The honest price of the RT-13 fix, pinned rather than left to be discovered.

    Excluding the four ``BOOKKEEPING_FIELDS`` from every hash means an in-place edit of one of
    them is undetected on read.  That is a real loss and it is the *whole* loss: every other
    field, including the derived ``intervention_hash`` that carries the mutation's semantics, is
    still covered and still refused.
    """

    ledger = store(tmp_path)
    path = ledger.append(factory.record()).path
    payload = json.loads(path.read_text(encoding="utf-8"))

    payload["mutation"]["proposal_id"] = "mutation:edited-after-the-fact"
    payload["mutation"]["mutation_hash"] = "0" * 64
    payload["created_at"] = "2099-01-01T00:00:00.000000+00:00"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    (reread,) = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID).records()
    assert reread.mutation.proposal_id == "mutation:edited-after-the-fact"

    # ... and the semantic hash of the same mutation is untouched by that edit, because it is
    # derived from the operator and the genes rather than stored.
    assert reread.mutation.intervention_hash == factory.record().mutation.intervention_hash

    for field, value in (
        ("operator", "a-different-operator"),
        ("layer", "B"),
        ("evaluation_tier", "TIER_3"),
    ):
        forged = dict(payload)
        forged["mutation"] = {**payload["mutation"], field: value}
        path.write_text(json.dumps(forged, sort_keys=True), encoding="utf-8")
        with pytest.raises(FitnessMemoryIdentityViolation, match="stored content_hash"):
            EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID).records()


def test_bookkeeping_is_unhashed_but_still_required(tmp_path: Path) -> None:
    """Excluded from the hashes is not the same as optional; the audit trail stays mandatory."""

    with pytest.raises(RecordIdentityViolation, match="mutation hash"):
        factory.mutation(mutation_hash="")
    with pytest.raises(RecordIdentityViolation, match="proposal id"):
        factory.mutation(proposal_id="")


def test_a_record_written_under_the_previous_schema_is_refused_not_migrated(
    tmp_path: Path,
) -> None:
    """RT-13/16 changed the schema, so ``v0.2.0`` reads ``v0.2.0``.  Nothing is upgraded in place.

    Silently defaulting the new components onto an old record would invent an evaluation identity
    that nobody ever ran under, which is worse than a refusal to read.
    """

    ledger = store(tmp_path)
    path = ledger.append(factory.record()).path
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "arena-language-fitness-memory-v0.1.0"
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="does not migrate stored records"):
        EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID).records()
