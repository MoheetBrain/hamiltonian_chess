"""Representation-independent structural and semantic survival checks."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import replace

from arena.canonical.schema import CanonicalExpression, CanonicalState, CanonicalTransition
from arena.verifier.base import Severity, VerificationIssue, VerificationResult

PARTIAL_OPERATORS = {"div", "sqrt", "log", "inverse", "index", "condition"}
BINDER_OPERATORS = {"forall", "exists", "lambda", "sum_over", "integral_over"}


def walk(expression: CanonicalExpression) -> Iterable[CanonicalExpression]:
    yield expression
    for argument in expression.args:
        yield from walk(argument)


def _duplicates(values: Iterable[str]) -> set[str]:
    return {key for key, count in Counter(values).items() if count > 1}


def _cycle(nodes: dict[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    active: list[str] = []
    completed: set[str] = set()

    def visit(node: str) -> tuple[str, ...] | None:
        if node in active:
            start = active.index(node)
            return tuple((*active[start:], node))
        if node in completed:
            return None
        active.append(node)
        for dependency in nodes.get(node, ()):
            found = visit(dependency)
            if found:
                return found
        active.pop()
        completed.add(node)
        return None

    for node in nodes:
        found = visit(node)
        if found:
            return found
    return None


class NativeVerifier:
    name = "arena-native"
    version = "0.1.0"

    def verify_state(self, state: CanonicalState) -> VerificationResult:
        issues: list[VerificationIssue] = []
        object_ids = [item.object_id for item in state.objects]
        binder_ids = [item.binder_id for item in state.bindings]
        evidence_ids = [item.evidence_id for item in state.evidence_dependencies]
        obligation_ids = [item.obligation_id for item in state.obligations]
        action_ids = [
            item.action_id for item in (*state.legal_actions, *state.plausible_invalid_actions)
        ]

        for label, values in (
            ("object", object_ids),
            ("binder", binder_ids),
            ("evidence", evidence_ids),
            ("obligation", obligation_ids),
            ("action", action_ids),
        ):
            for duplicate in sorted(_duplicates(values)):
                issues.append(
                    VerificationIssue(
                        f"DUPLICATE_{label.upper()}_ID",
                        Severity.CRITICAL,
                        f"duplicate {label} identity {duplicate}",
                    )
                )

        scope_ids = set(state.local_scope)
        for binding in state.bindings:
            if binding.scope_id not in scope_ids:
                issues.append(
                    VerificationIssue(
                        "UNKNOWN_SCOPE",
                        Severity.CRITICAL,
                        f"binding {binding.binder_id} refers to absent scope {binding.scope_id}",
                    )
                )

        evidence_graph = {
            item.evidence_id: item.dependencies for item in state.evidence_dependencies
        }
        known_evidence = set(evidence_graph)
        for item in state.evidence_dependencies:
            for dependency in item.dependencies:
                if dependency not in known_evidence:
                    issues.append(
                        VerificationIssue(
                            "UNKNOWN_EVIDENCE_DEPENDENCY",
                            Severity.CRITICAL,
                            f"evidence {item.evidence_id} depends on absent {dependency}",
                        )
                    )
        if cycle := _cycle(evidence_graph):
            issues.append(
                VerificationIssue(
                    "EVIDENCE_CYCLE",
                    Severity.CRITICAL,
                    "cyclic evidence path: " + " -> ".join(cycle),
                )
            )

        expressions = [
            *state.assumptions,
            *state.established_facts,
            *state.propositions,
            state.goal,
            *(item.proposition for item in state.obligations),
        ]
        expressions.extend(
            argument
            for action in (*state.legal_actions, *state.plausible_invalid_actions)
            for argument in (*action.arguments, *action.preconditions)
        )
        defined_targets = {
            node.args[0].content_hash
            for obligation in state.obligations
            for node in walk(obligation.proposition)
            if node.op == "defined"
            and len(node.args) == 1
            and obligation.status in {"OPEN", "DISCHARGED"}
        }
        free_names = {item.variable for item in state.bindings if item.binder_kind == "free"}
        free_names.update(object_ids)
        for expression in expressions:
            for name in sorted(self._unbound_variables(expression) - free_names):
                issues.append(
                    VerificationIssue(
                        "UNBOUND_VARIABLE",
                        Severity.CRITICAL,
                        f"variable {name!r} is neither bound nor declared",
                    )
                )
            for node in walk(expression):
                if node.op in BINDER_OPERATORS and len(node.args) < 2:
                    issues.append(
                        VerificationIssue(
                            "MALFORMED_BINDER",
                            Severity.CRITICAL,
                            f"{node.op} must contain a binder and body",
                        )
                    )
                if node.op in PARTIAL_OPERATORS and node.content_hash not in defined_targets:
                    issues.append(
                        VerificationIssue(
                            "UNTRACKED_DEFINEDNESS",
                            Severity.CRITICAL,
                            f"partial operation {node.op} has no matching definedness obligation",
                        )
                    )
                if (
                    node.op in {"add", "sub", "mul", "div", "eq", "lt", "le"}
                    and len(node.args) != 2
                ):
                    issues.append(
                        VerificationIssue(
                            "ARITY_MISMATCH",
                            Severity.CRITICAL,
                            f"{node.op} expects two arguments, received {len(node.args)}",
                        )
                    )
                if (
                    node.op in {"add", "sub", "mul", "div"}
                    and len(node.args) == 2
                    and (
                        "Bool" in {node.args[0].sort, node.args[1].sort}
                        or node.args[0].sort != node.args[1].sort
                    )
                ):
                    issues.append(
                        VerificationIssue(
                            "TYPE_CONFUSION",
                            Severity.CRITICAL,
                            f"{node.op} combines {node.args[0].sort} and {node.args[1].sort}",
                        )
                    )
                if node.op == "matmul" and len(node.args) == 2:
                    left_shape = self._shape(node.args[0])
                    right_shape = self._shape(node.args[1])
                    if (
                        left_shape is not None
                        and right_shape is not None
                        and left_shape[1] != right_shape[0]
                    ):
                        issues.append(
                            VerificationIssue(
                                "MATRIX_SHAPE_MISMATCH",
                                Severity.CRITICAL,
                                f"cannot multiply shapes {left_shape} and {right_shape}",
                            )
                        )
                if (
                    node.op == "conditional_probability"
                    and len(node.args) >= 2
                    and any(argument.sort != "Event" for argument in node.args[:2])
                ):
                    issues.append(
                        VerificationIssue(
                            "PROBABILITY_ROLE_MISMATCH",
                            Severity.CRITICAL,
                            "conditional probability requires Event/Event arguments",
                        )
                    )
                if (
                    node.op == "eq"
                    and len(node.args) == 2
                    and {node.args[0].sort, node.args[1].sort}
                    == {"ApproximateScalar", "ExactScalar"}
                ):
                    issues.append(
                        VerificationIssue(
                            "EXACTNESS_LAUNDERING",
                            Severity.CRITICAL,
                            "approximate and exact values require an explicit tolerance relation",
                        )
                    )

        all_targets = set(object_ids) | {"goal"}
        for action in (*state.legal_actions, *state.plausible_invalid_actions):
            unknown_targets = set(action.target_ids) - all_targets
            if unknown_targets:
                issues.append(
                    VerificationIssue(
                        "UNKNOWN_ACTION_TARGET",
                        Severity.CRITICAL,
                        f"action {action.action_id} targets {sorted(unknown_targets)}",
                    )
                )

        accepted = not any(issue.severity == Severity.CRITICAL for issue in issues)
        return VerificationResult(self.name, self.version, accepted, tuple(issues))

    @staticmethod
    def _shape(node: CanonicalExpression) -> tuple[int, int] | None:
        raw = dict(node.attributes).get("shape")
        if not raw:
            return None
        try:
            parts = tuple(int(item) for item in raw.split("x"))
        except ValueError:
            return None
        return parts if len(parts) == 2 else None

    def _unbound_variables(self, expression: CanonicalExpression) -> set[str]:
        def visit(node: CanonicalExpression, environment: tuple[str, ...]) -> set[str]:
            if node.op == "var" and isinstance(node.value, str):
                return set() if node.value in environment else {node.value}
            if node.op in BINDER_OPERATORS and len(node.args) >= 2:
                binder = node.args[0]
                if binder.op == "var" and isinstance(binder.value, str):
                    found: set[str] = set()
                    for argument in node.args[1:]:
                        found.update(visit(argument, (*environment, binder.value)))
                    return found
            found = set()
            for argument in node.args:
                found.update(visit(argument, environment))
            return found

        return visit(expression, ())

    def verify_transition(self, transition: CanonicalTransition) -> VerificationResult:
        before = self.verify_state(transition.state_before)
        after = self.verify_state(transition.state_after)
        issues = [*before.issues, *after.issues]
        action_ids = {action.action_id for action in transition.state_before.legal_actions}
        if transition.action.action_id not in action_ids:
            issues.append(
                VerificationIssue(
                    "ILLEGAL_TRANSITION_ACTION",
                    Severity.CRITICAL,
                    f"{transition.action.action_id} is not legal in the before-state",
                )
            )
        before_open = {
            item.obligation_id
            for item in transition.state_before.obligations
            if item.status == "OPEN"
        }
        after_ids = {item.obligation_id for item in transition.state_after.obligations}
        vanished = before_open - after_ids
        if vanished and not transition.action.generated_obligations:
            issues.append(
                VerificationIssue(
                    "OBLIGATION_LAUNDERING",
                    Severity.CRITICAL,
                    f"open obligations disappeared without discharge evidence: {sorted(vanished)}",
                )
            )
        after_goal = transition.state_after.goal
        if (
            transition.state_before.goal != after_goal
            and after_goal.op in {"literal", "bool"}
            and after_goal.value is True
            and not transition.action.generated_obligations
            and not transition.verification
        ):
            issues.append(
                VerificationIssue(
                    "GOAL_LAUNDERING",
                    Severity.CRITICAL,
                    "goal was replaced by truth without obligation or verification evidence",
                )
            )
        if transition.state_before.mathematical_hash == transition.state_after.mathematical_hash:
            issues.append(
                VerificationIssue(
                    "NO_STATE_CHANGE",
                    Severity.WARNING,
                    "transition leaves mathematical state unchanged",
                )
            )
        accepted = not any(issue.severity == Severity.CRITICAL for issue in issues)
        return VerificationResult(self.name, self.version, accepted, tuple(issues))


def force_reject(result: VerificationResult, issue: VerificationIssue) -> VerificationResult:
    return replace(result, accepted=False, issues=(*result.issues, issue))
