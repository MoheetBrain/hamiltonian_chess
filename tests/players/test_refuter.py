from arena.players.refuter import Refuter
from arena.verifier.base import VerificationResult
from arena.verifier.native import NativeVerifier
from tests.helpers import sample_state


class AcceptEverythingVerifier:
    name = "unsound"
    version = "0"

    def verify_state(self, state):
        return VerificationResult(self.name, self.version, True, ())

    def verify_transition(self, transition):
        return VerificationResult(self.name, self.version, True, ())


def test_native_refuter_campaign_has_no_known_false_accept(tmp_path) -> None:
    report = Refuter(NativeVerifier(), tmp_path / "failures.jsonl").run("native", sample_state())
    assert report.critical_count == 0


def test_refuter_finds_unsound_accept_everything_verifier(tmp_path) -> None:
    report = Refuter(AcceptEverythingVerifier(), tmp_path / "failures.jsonl").run(
        "bad", sample_state()
    )
    assert report.critical_count >= 8
    assert report.novel_failure_classes
