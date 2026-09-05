"""Conservative quality classification for canonical trajectories."""

from __future__ import annotations

from collections.abc import Collection, Iterable

from arena.canonical.schema import GoldStatus, VerificationRecord, VerificationStatus

NATIVE_VERIFIER_NAMES = frozenset({"arena-native", "native"})


def classify_quality(
    records: Iterable[VerificationRecord],
    *,
    independent_verifiers: Collection[str] = (),
) -> GoldStatus:
    """Classify checks without treating absence of evidence as verification.

    GOLD requires a verified native check and at least one explicitly designated,
    verified independent checker.  A refutation or rejected check is REJECT.  Accepted
    native checks with absent/unknown independent evidence are only SILVER.
    """

    checks = tuple(records)
    if not checks:
        return GoldStatus.REJECT
    if any(record.status == VerificationStatus.REFUTED for record in checks):
        return GoldStatus.REJECT
    if any(
        record.status == VerificationStatus.VERIFIED and not record.accepted for record in checks
    ):
        return GoldStatus.REJECT

    native_verified = any(
        record.verifier in NATIVE_VERIFIER_NAMES
        and record.status == VerificationStatus.VERIFIED
        and record.accepted
        for record in checks
    )
    if not native_verified:
        return GoldStatus.REJECT

    trusted = set(independent_verifiers)
    trusted_checks = tuple(record for record in checks if record.verifier in trusted)
    if any(record.status == VerificationStatus.UNKNOWN for record in trusted_checks):
        return GoldStatus.SILVER
    independent_verified = any(
        record.verifier not in NATIVE_VERIFIER_NAMES
        and record.status == VerificationStatus.VERIFIED
        and record.accepted
        for record in trusted_checks
    )
    return GoldStatus.GOLD if independent_verified else GoldStatus.SILVER


def trajectory_quality(
    transition_records: Iterable[Iterable[VerificationRecord]],
    *,
    independent_verifiers: Collection[str] = (),
) -> GoldStatus:
    """Use the least trustworthy transition as the trajectory quality."""

    qualities = tuple(
        classify_quality(records, independent_verifiers=independent_verifiers)
        for records in transition_records
    )
    if not qualities or GoldStatus.REJECT in qualities:
        return GoldStatus.REJECT
    if GoldStatus.SILVER in qualities:
        return GoldStatus.SILVER
    return GoldStatus.GOLD
