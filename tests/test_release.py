from arena.release import ReleaseEvidence, ReleaseStatus, decide_release


def test_no_candidate_is_an_honest_no_winner() -> None:
    evidence = ReleaseEvidence(0, 0, True, 100, 0, 0, 0, 4, False)
    decision = decide_release(None, evidence)
    assert decision.status == ReleaseStatus.NO_WINNER
    assert not decision.released
