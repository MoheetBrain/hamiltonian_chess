from arena.assurance.side_channels import Observation, audit


def observation(index: int, success: bool, input_text: str = "state") -> Observation:
    return Observation(
        task_id=f"t:{index}",
        candidate_id="L0",
        task_family="even" if index % 2 == 0 else "odd",
        answer_class="A" if index < 2 else "B",
        token_length=10 if success else 11,
        success=success,
        input_text=input_text,
        target_text="secret",
    )


def test_literal_target_leak_is_critical() -> None:
    report = audit((observation(0, True, "state secret"), observation(1, False)))
    assert report.literal_answer_leaks == ("t:0",)
    assert report.critical


def test_balanced_clean_records_have_no_literal_leak() -> None:
    report = audit(tuple(observation(index, index % 2 == 0) for index in range(8)))
    assert not report.literal_answer_leaks
