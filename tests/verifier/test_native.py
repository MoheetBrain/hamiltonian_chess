from dataclasses import replace

from arena.canonical.schema import CanonicalExpression, EvidenceNode
from arena.verifier.native import NativeVerifier
from tests.helpers import sample_state


def codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_sample_state_passes_native_verifier() -> None:
    result = NativeVerifier().verify_state(sample_state())
    assert result.accepted, result.issues


def test_untracked_partial_operation_is_critical() -> None:
    state = replace(sample_state(), obligations=())
    result = NativeVerifier().verify_state(state)
    assert not result.accepted
    assert "UNTRACKED_DEFINEDNESS" in codes(result)


def test_evidence_cycle_is_critical() -> None:
    state = replace(
        sample_state(),
        evidence_dependencies=(
            EvidenceNode("e:1", "VERIFIED", ("e:2",)),
            EvidenceNode("e:2", "VERIFIED", ("e:1",)),
        ),
    )
    result = NativeVerifier().verify_state(state)
    assert not result.accepted
    assert "EVIDENCE_CYCLE" in codes(result)


def test_unbound_variable_is_critical() -> None:
    state = replace(
        sample_state(),
        goal=CanonicalExpression("eq", (CanonicalExpression("var", value="ghost"),) * 2),
    )
    result = NativeVerifier().verify_state(state)
    assert not result.accepted
    assert "UNBOUND_VARIABLE" in codes(result)
