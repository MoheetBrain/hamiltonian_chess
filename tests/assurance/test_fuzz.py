import json

from arena.assurance.fuzz import fuzz_cases, run_parser_fuzz


def test_fuzz_cases_are_deterministic() -> None:
    assert fuzz_cases("{}", seed=7) == fuzz_cases("{}", seed=7)


def test_strict_json_parser_rejects_declared_cases() -> None:
    report = run_parser_fuzz("{}", json.loads, seed=0, random_cases=16)
    assert report.total == 22
    assert not report.unexpected_accepts
