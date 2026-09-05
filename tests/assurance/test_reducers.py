from arena.assurance.reducers import ddmin_sequence, is_one_minimal_sequence, minimize_text


def test_ddmin_returns_one_minimal_witness() -> None:
    items = ("noise", "open", "noise2", "sesame", "noise3")

    def predicate(values):
        return "open" in values and "sesame" in values

    reduced = ddmin_sequence(items, predicate)
    assert set(reduced) == {"open", "sesame"}
    assert is_one_minimal_sequence(reduced, predicate)


def test_text_minimizer_preserves_trigger() -> None:
    result = minimize_text("lots of PREFIX BUG suffix", lambda value: "BUG" in value)
    assert result == "BUG"
