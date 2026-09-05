from arena.canonical.schema import CanonicalExpression
from arena.verifier.differential import DifferentialVerifier
from arena.verifier.external import ExternalStatus
from arena.verifier.sympy_adapter import SympyAdapter
from arena.verifier.z3_adapter import Z3Adapter
from tests.helpers import integer, variable


def test_sympy_equivalence() -> None:
    x = variable("x")
    expression = CanonicalExpression("add", (x, integer(0)), sort="Real")
    assert SympyAdapter().check_equivalence(expression, x).status == ExternalStatus.AGREE


def test_z3_tautology() -> None:
    x = variable("x", "Int")
    proposition = CanonicalExpression("eq", (x, x), sort="Proposition")
    assert Z3Adapter().check_truth(proposition).status == ExternalStatus.AGREE


def test_differential_result_counts_supported_verifiers() -> None:
    proposition = CanonicalExpression("eq", (integer(2), integer(2)), sort="Proposition")
    result = DifferentialVerifier().check_truth(proposition)
    assert result.supported_verifiers >= 2
    assert not result.unresolved_disagreement
