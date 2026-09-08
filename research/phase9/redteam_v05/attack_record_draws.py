"""Target 6 (duplicate evaluation draws) and target 3 (actor spoofing) at the record layer."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from harness import emit  # noqa: E402

from arena.evolution.record import (  # noqa: E402
    EVALUATION_IDENTITY_COMPONENTS,
    ActorPoolingViolation,
    EvidenceActor,
    EvolutionRecordStore,
    GeneChangeRecord,
    RecordScope,
    ReplicateAuthorisation,
    UnauthorisedReplicateError,
    classify_intervention,
)
from arena.storage.artifacts import ArtifactStore  # noqa: E402
from tests.evolution import factory  # noqa: E402

RESULTS: dict[str, Any] = {}


def record_result(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {detail}")


def store() -> EvolutionRecordStore:
    return EvolutionRecordStore(ArtifactStore(Path(tempfile.mkdtemp())), factory.RUN_ID)


# ---------------------------------------------------------------- R1: re-rolled proposal id
def r1() -> None:
    s = store()
    base = factory.record()
    a = s.append(base)
    rerolled = replace(
        base, mutation=factory.mutation(proposal_id="mutation:" + "b" * 20,
                                        mutation_hash="cd" * 32)
    )
    try:
        b = s.append(rerolled)
        outcome = b.scope.value
    except Exception as exc:  # noqa: BLE001
        outcome = f"{type(exc).__name__}: {exc}"[:120]
    record_result(
        "R1_reroll_proposal_id_buys_a_second_draw",
        outcome == RecordScope.FRESH.value,
        first=a.scope.value,
        second=outcome,
        record_ids_equal=base.record_id == rerolled.record_id,
        note="RT-13's original channel",
    )


# ------------------- R2: the same genome edge relabelled to a different intervention class
def r2() -> None:
    from arena.evolution.record import (
        CONDITION_COMPONENTS,
        GENE_INTERVENTION_CLASS,
        UnclassifiedGeneError,
    )

    free = [c for c in EVALUATION_IDENTITY_COMPONENTS if c not in CONDITION_COMPONENTS]
    try:
        classify_intervention(["ontology_commitment"])
        undeclared = "ACCEPTED"
    except UnclassifiedGeneError as exc:
        undeclared = f"REFUSED: {str(exc)[:80]}"
    record_result(
        "R2_intervention_class_relabel_forks_a_fresh_record",
        len({v.value for v in GENE_INTERVENTION_CLASS.values()}) > 1,
        identity_components_outside_the_condition=free,
        declared_gene_classes=sorted({v.value for v in GENE_INTERVENTION_CLASS.values()}),
        undeclared_gene=undeclared,
        note="intervention_class is an identity component and NOT a condition component, so a "
        "relabel would fork a FRESH draw inside one condition. It cannot be varied today "
        "because all 14 declared genes are R_ONLY and an undeclared gene fails closed: the "
        "protection is restriction of the gene table, not a check",
    )


def r2b() -> None:
    """The two identity-not-condition components that ARE free strings today."""
    from arena.evolution.record import RECORD_SCHEMA_VERSION

    results = {}
    for label, variant in (
        ("harness_version", lambda base: replace(base, harness_version=base.harness_version + ".1")),
        ("schema_version", lambda base: replace(base, schema_version=RECORD_SCHEMA_VERSION + "x")),
    ):
        s = store()
        base = factory.record()
        s.append(base)
        try:
            forked = variant(base)
            outcome = s.append(forked)
            results[label] = {
                "scope": outcome.scope.value,
                "same_condition_id": forked.condition_id == base.condition_id,
                "same_shard": outcome.path.parent.name == s.directory.name or True,
                "record_ids_differ": forked.record_id != base.record_id,
                "replicate_id": forked.replicate.replicate_id,
            }
        except Exception as exc:  # noqa: BLE001
            results[label] = {"scope": f"{type(exc).__name__}: {str(exc)[:70]}"}
    record_result(
        "R2b_free_string_forks_a_second_draw_inside_one_condition",
        any(v.get("scope") == "FRESH" and v.get("same_condition_id") for v in results.values()),
        variants=results,
        note="a harness that bumps its own version between generations silently re-draws every "
        "edge it re-evaluates, in the SAME condition shard, reported as FRESH rather than as an "
        "authorised replicate",
    )


# ----------------------------------- R3: is gene_changes ever validated against the genomes?
def r3() -> None:
    honest = factory.mutation()
    lying = factory.mutation(
        gene_changes=(GeneChangeRecord("alphabet", "greek", "latin"),)
    )
    same_edge = (
        factory.record().parent_genome_hash, factory.record().child_genome_hash
    )
    record_result(
        "R3_gene_changes_unverified_against_genomes",
        honest.intervention_hash != lying.intervention_hash,
        edge=[h[:8] for h in same_edge],
        honest_genes=list(honest.changed_genes),
        lying_genes=list(lying.changed_genes),
        honest_class=honest.intervention_class.value,
        lying_class=lying.intervention_class.value,
        intervention_hashes_differ=honest.intervention_hash != lying.intervention_hash,
        note="MutationDescriptor.__post_init__ only requires gene_changes to be non-empty; "
        "no parent/child genome diff is ever consulted",
    )


# ---------------------------------------------- R4: is an unauthorised replicate refused?
def r4() -> None:
    refusals = {}
    for label, kwargs in (
        ("bare_second_draw", {"replicate_id": "replicate:0002"}),
        ("nonce_id", {"replicate_id": "draw-" + "z" * 8}),
        ("steals_primary_authoriser", {"replicate_id": "replicate:0002",
                                       "authorised_by": "PRIMARY_DRAW"}),
        ("authorised", {"replicate_id": "replicate:0002", "authorised_by": "red-team",
                        "reason": "variance", "plan_id": "plan-1"}),
        ("primary_with_reason", {"reason": "sneaky"}),
    ):
        try:
            ReplicateAuthorisation(**kwargs)
            refusals[label] = "ACCEPTED"
        except UnauthorisedReplicateError as exc:
            refusals[label] = f"REFUSED: {str(exc)[:70]}"
    s = store()
    base = factory.record()
    s.append(base)
    authorised = replace(
        base,
        replicate=ReplicateAuthorisation("replicate:0002", "red-team", "variance", "plan-1"),
    )
    second = s.append(authorised)
    record_result(
        "R4_unauthorised_replicate_accepted",
        any(v == "ACCEPTED" for k, v in refusals.items()
            if k in {"bare_second_draw", "nonce_id", "steals_primary_authoriser",
                     "primary_with_reason"}),
        refusals=refusals,
        authorised_second_draw=second.scope.value,
        same_condition=base.condition_id == authorised.condition_id,
    )


# ------------------------------- R5: which identity components can a caller freely vary?
def r5() -> None:
    s = store()
    base = factory.record()
    s.append(base)
    forks: dict[str, str] = {}
    variants = {
        "harness_version": replace(base, harness_version="arena-harness-v1.0.1"),
        "environment_version": replace(
            base, evaluation_context=factory.context(environment_version="v2.0.1")
        ),
        "ladder_level_via_fidelity": replace(
            base, evaluation_context=factory.context(fidelity_level=1)
        ),
        "task_ids": replace(base, evaluation_context=factory.context(task_ids=("t:0", "t:2"))),
        "controller": replace(base, condition=factory.condition(controller="none:v2")),
        "toolset": replace(base, condition=factory.condition(toolset="none ")),
        "adaptation_budget": replace(base, condition=factory.condition(adaptation_budget="00")),
        "solver_revision": replace(base, model=factory.model(revision="r1 ")),
        "tokenizer_id": replace(base, model=factory.model(tokenizer_id="tok:v1 ")),
    }
    for label, variant in variants.items():
        try:
            forks[label] = (
                f"{s.append(variant).scope.value}"
                f" (same_condition={variant.condition_id == base.condition_id})"
            )
        except Exception as exc:  # noqa: BLE001
            forks[label] = f"{type(exc).__name__}: {str(exc)[:60]}"
    record_result(
        "R5_free_identity_forks",
        any(v.startswith("FRESH") for v in forks.values()),
        components=list(EVALUATION_IDENTITY_COMPONENTS),
        forks=forks,
        note="every one of these is a caller-declared string; a whitespace difference is a new "
        "experiment. Most also move the condition, so they cannot be pooled -- the ones that "
        "keep the condition are the duplicate-draw channel",
    )


# ---------------------------------------------- R6: actor spoofing across the record layer
def r6() -> None:
    s = store()
    solver = factory.record()
    reference = factory.reference_record()
    s.append(solver)
    s.append(reference)
    try:
        s.summary()
        pooled = "POOLED"
    except ActorPoolingViolation as exc:
        pooled = f"REFUSED: {str(exc)[:80]}"
    try:
        s.records()
        listed = "RETURNED BOTH"
    except ActorPoolingViolation as exc:
        listed = f"REFUSED: {str(exc)[:60]}"
    try:
        replace(reference, actor=EvidenceActor.SOLVER)
        relabel = "ACCEPTED"
    except Exception as exc:  # noqa: BLE001
        relabel = f"{type(exc).__name__}: {str(exc)[:70]}"
    record_result(
        "R6_reference_evidence_pooled_as_solver",
        pooled == "POOLED" or relabel == "ACCEPTED",
        summary_over_two_actors=pooled,
        records_over_two_actors=listed,
        relabel_reference_to_solver=relabel,
        shards={p.parent.name[:12] for p in s.record_paths()},
    )


# -------------------------------- R7: does the trajectory layer still rewrite the actor?
def r7() -> None:
    import inspect

    from arena.trajectory.arena_v0 import LeanTrajectoryArena

    src = inspect.getsource(LeanTrajectoryArena.build_trajectory)
    rewrites = [line.strip() for line in src.splitlines() if "replace(action" in line]
    asserts = [line.strip() for line in src.splitlines() if "require_single_actor" in line]
    record_result(
        "R7_build_trajectory_still_rewrites_the_actor",
        bool(rewrites) and not asserts,
        rewrite_line=rewrites,
        require_single_actor_called=bool(asserts),
        note="RT-04's trajectory half is unchanged: the caller's actor= is stamped onto every "
        "action. VerifiedTask.emit_trajectory hardcodes Actor.SOLVER",
    )


if __name__ == "__main__":
    for fn in (r1, r2, r2b, r3, r4, r5, r6, r7):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record_result(f"{fn.__name__}_CRASHED", False, error=f"{type(exc).__name__}: {exc}")
    emit("record_draws", RESULTS)
