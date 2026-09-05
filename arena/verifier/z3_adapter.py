"""Z3 adapter for quantifier-free integer/real arithmetic and propositional logic."""

from __future__ import annotations

import z3

from arena.canonical.schema import CanonicalExpression
from arena.verifier.external import ExternalStatus, ExternalVerdict


class UnsupportedZ3Expression(ValueError):
    pass


def to_z3(node: CanonicalExpression, symbols: dict[str, z3.ExprRef] | None = None):
    symbols = {} if symbols is None else symbols
    if node.op in {"integer", "nat"}:
        if not isinstance(node.value, (str, int)) or isinstance(node.value, bool):
            raise UnsupportedZ3Expression("integer literal is not integral")
        return z3.IntVal(int(node.value))
    if node.op == "real":
        return z3.RealVal(str(node.value))
    if node.op == "bool":
        return z3.BoolVal(bool(node.value))
    if node.op == "var" and isinstance(node.value, str):
        if node.value not in symbols:
            symbols[node.value] = (
                z3.Int(node.value)
                if node.sort in {"Int", "Nat"}
                else z3.Bool(node.value)
                if node.sort == "Bool"
                else z3.Real(node.value)
            )
        return symbols[node.value]
    args = [to_z3(item, symbols) for item in node.args]
    operations = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
        "neg": lambda a: -a,
        "eq": lambda a, b: a == b,
        "lt": lambda a, b: a < b,
        "le": lambda a, b: a <= b,
        "and": z3.And,
        "or": z3.Or,
        "not": z3.Not,
        "implies": z3.Implies,
    }
    try:
        return operations[node.op](*args)
    except (KeyError, TypeError, z3.Z3Exception) as error:
        raise UnsupportedZ3Expression(f"{node.op}: {error}") from error


class Z3Adapter:
    name = "z3"
    version = z3.get_version_string()

    def check_truth(self, proposition: CanonicalExpression) -> ExternalVerdict:
        claim = proposition.content_hash
        try:
            formula = to_z3(proposition)
            solver = z3.Solver()
            solver.add(z3.Not(formula))
            result = solver.check()
        except UnsupportedZ3Expression as error:
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.UNSUPPORTED, claim, str(error)
            )
        except Exception as error:
            return ExternalVerdict(
                self.name, self.version, ExternalStatus.ERROR, claim, repr(error)
            )
        if result == z3.unsat:
            status = ExternalStatus.AGREE
        elif result == z3.sat:
            status = ExternalStatus.DISAGREE
        else:
            status = ExternalStatus.UNSUPPORTED
        return ExternalVerdict(self.name, self.version, status, claim, str(result))
