"""Conservative SymPy translation for the explicitly supported expression subset."""

from __future__ import annotations

import sympy

from arena.canonical.schema import CanonicalExpression
from arena.verifier.external import ExternalStatus, ExternalVerdict


class UnsupportedSympyExpression(ValueError):
    pass


def to_sympy(node: CanonicalExpression, symbols: dict[str, sympy.Symbol] | None = None):
    symbols = {} if symbols is None else symbols
    if node.op in {"integer", "nat"}:
        return sympy.Integer(node.value)
    if node.op == "real":
        return sympy.Rational(str(node.value))
    if node.op == "bool":
        return sympy.true if bool(node.value) else sympy.false
    if node.op == "var" and isinstance(node.value, str):
        return symbols.setdefault(node.value, sympy.Symbol(node.value, real=True))
    args = [to_sympy(item, symbols) for item in node.args]
    operations = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
        "pow": lambda a, b: a**b,
        "neg": lambda a: -a,
        "sqrt": sympy.sqrt,
        "log": sympy.log,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "eq": sympy.Eq,
        "lt": sympy.Lt,
        "le": sympy.Le,
        "and": sympy.And,
        "or": sympy.Or,
        "not": sympy.Not,
        "implies": sympy.Implies,
        "equiv": sympy.Equivalent,
    }
    if node.op == "derivative" and len(args) == 2:
        return sympy.diff(args[0], args[1])
    if node.op == "integral" and len(args) == 2:
        return sympy.integrate(args[0], args[1])
    try:
        operation = operations[node.op]
    except KeyError as error:
        raise UnsupportedSympyExpression(node.op) from error
    try:
        return operation(*args)
    except (TypeError, ValueError) as error:
        raise UnsupportedSympyExpression(f"{node.op}: {error}") from error


class SympyAdapter:
    name = "sympy"
    version = sympy.__version__

    def check_equivalence(
        self, left: CanonicalExpression, right: CanonicalExpression
    ) -> ExternalVerdict:
        claim = f"{left.content_hash} == {right.content_hash}"
        try:
            difference = sympy.simplify(to_sympy(left) - to_sympy(right))
        except UnsupportedSympyExpression as error:
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.UNSUPPORTED, claim, str(error)
            )
        except Exception as error:  # SymPy is an independent boundary.
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.ERROR, claim, repr(error)
            )
        status = ExternalStatus.AGREE if difference == 0 else ExternalStatus.DISAGREE
        return ExternalVerdict(self.name, self.version, status, claim, str(difference))

    def check_truth(self, proposition: CanonicalExpression) -> ExternalVerdict:
        claim = proposition.content_hash
        try:
            result = sympy.simplify(to_sympy(proposition))
        except UnsupportedSympyExpression as error:
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.UNSUPPORTED, claim, str(error)
            )
        except Exception as error:
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.ERROR, claim, repr(error)
            )
        if result == sympy.true:
            status = ExternalStatus.AGREE
        elif result == sympy.false:
            status = ExternalStatus.DISAGREE
        else:
            status = ExternalStatus.UNSUPPORTED
        return ExternalVerdict(self.name, self.version, status, claim, str(result))
