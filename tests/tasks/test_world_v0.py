from collections import Counter

from arena.canonical.schema import GoldStatus, VerificationRecord, VerificationStatus
from arena.tasks.generators.world_v0 import (
    DEFAULT_WORLD_SIZE,
    INDEPENDENT_VALIDATOR,
    SUPPORTED_DOMAINS,
    build_world_v0,
)
from arena.tasks.quality import classify_quality
from arena.verifier.native import NativeVerifier


def test_default_world_is_balanced_deterministic_and_native_valid() -> None:
    world = build_world_v0()

    assert len(world) == DEFAULT_WORLD_SIZE == 676
    assert set(world.summary.domain_counts) == set(SUPPORTED_DOMAINS)
    assert set(world.summary.domain_counts.values()) == {52}
    assert world.summary.quality_counts == {"GOLD": 520, "REJECT": 52, "SILVER": 104}
    assert len({task.task_id for task in world}) == len(world)
    assert [task.content_hash for task in world] == [task.content_hash for task in build_world_v0()]

    verifier = NativeVerifier()
    for task in world:
        initial = task.trajectory.initial_state
        assert initial.legal_actions
        assert initial.plausible_invalid_actions
        assert all(
            verifier.verify_transition(transition).accepted
            for transition in task.trajectory.transitions
        )


def test_gold_requires_explicit_independent_verification() -> None:
    native = VerificationRecord("arena-native", "0.1", VerificationStatus.VERIFIED, True)
    independent = VerificationRecord(
        INDEPENDENT_VALIDATOR, "0.1", VerificationStatus.VERIFIED, True
    )

    assert classify_quality((native,)) == GoldStatus.SILVER
    assert (
        classify_quality((native, independent), independent_verifiers=(INDEPENDENT_VALIDATOR,))
        == GoldStatus.GOLD
    )
    assert classify_quality(()) == GoldStatus.REJECT


def test_generated_quality_has_matching_validator_provenance() -> None:
    world = build_world_v0(total=338, seed=11)
    observed = Counter(task.trajectory.quality for task in world)
    assert set(observed) == {GoldStatus.GOLD, GoldStatus.SILVER, GoldStatus.REJECT}

    for task in world:
        transition = task.trajectory.transitions[0]
        independent = next(
            record for record in transition.verification if record.verifier == INDEPENDENT_VALIDATOR
        )
        if task.trajectory.quality == GoldStatus.GOLD:
            assert independent.accepted
            assert independent.status == VerificationStatus.VERIFIED
            assert independent.certificate_hash
        elif task.trajectory.quality == GoldStatus.SILVER:
            assert independent.status == VerificationStatus.UNKNOWN
            assert not independent.accepted
        else:
            assert independent.status == VerificationStatus.REFUTED
