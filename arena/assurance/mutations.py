"""Deterministic grammar and canonical-semantic adversarial mutations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from arena.canonical.equivalence import expressions_equivalent
from arena.canonical.schema import (
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    CanonicalTransition,
    EvidenceNode,
    MathObject,
    Obligation,
    stable_hash,
)

Subject = CanonicalState | CanonicalTransition


class AttackClass(StrEnum):
    GRAMMAR = "grammar"
    ALPHA_RENAMING = "alpha_renaming"
    VARIABLE_CAPTURE = "variable_capture"
    SHADOWING = "shadowing"
    UNKNOWN_SCOPE = "unknown_scope"
    UNBOUND_VARIABLE = "unbound_variable"
    DEFINEDNESS = "definedness"
    TYPE_CONFUSION = "type_confusion"
    QUANTIFIER_ORDER = "quantifier_order"
    EVIDENCE_CYCLE = "evidence_cycle"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    ID_COLLISION = "id_collision"
    GOAL_LAUNDERING = "goal_laundering"
    OBLIGATION_LAUNDERING = "obligation_laundering"
    ILLEGAL_TRANSFORMATION = "illegal_transformation"
    PROBABILITY_ROLE = "probability_role"
    MATRIX_SHAPE = "matrix_shape"
    UNIT_CONFUSION = "unit_confusion"
    EXACTNESS_CONFUSION = "exactness_confusion"


@dataclass(frozen=True, slots=True)
class MutationCase:
    mutation_id: str
    attack_class: AttackClass
    description: str
    original: Subject
    subject: Subject
    expected_accepted: bool

    def witness(self, subject: Subject | None = None) -> bool:
        return mutation_witness(self.attack_class, subject or self.subject, self.original)


@dataclass(frozen=True, slots=True)
class GrammarMutation:
    mutation_id: str
    operation: str
    source: str
    expected_parse: bool = False


def _expr(
    op: str, *args: CanonicalExpression, value: object = None, sort: str = "Unknown"
) -> CanonicalExpression:
    return CanonicalExpression(op=op, args=tuple(args), value=value, sort=sort)  # type: ignore[arg-type]


def _fresh(existing: Iterable[str], prefix: str) -> str:
    occupied = set(existing)
    if prefix not in occupied:
        return prefix
    index = 1
    while f"{prefix}_{index}" in occupied:
        index += 1
    return f"{prefix}_{index}"


def _subject_dict(subject: Subject) -> dict[str, object]:
    return subject.to_dict()


def _case(
    attack_class: AttackClass,
    description: str,
    original: Subject,
    subject: Subject,
    *,
    expected_accepted: bool,
) -> MutationCase:
    mutation_id = "mutation:" + stable_hash(
        {
            "class": attack_class.value,
            "description": description,
            "subject": _subject_dict(subject),
            "expected_accepted": expected_accepted,
        }
    )
    return MutationCase(
        mutation_id,
        attack_class,
        description,
        original,
        subject,
        expected_accepted,
    )


def alpha_rename(
    expression: CanonicalExpression, *, suffix: str = "__alpha"
) -> CanonicalExpression:
    """Capture-avoiding, deterministic renaming of every binder in ``expression``."""

    serial = 0

    def visit(
        node: CanonicalExpression, environment: tuple[tuple[str, str], ...]
    ) -> CanonicalExpression:
        nonlocal serial
        if node.op == "var" and isinstance(node.value, str):
            for old, new in reversed(environment):
                if node.value == old:
                    return replace(node, value=new)
            return node
        if (
            node.op in {"forall", "exists", "lambda", "sum_over", "integral_over"}
            and len(node.args) >= 2
        ):
            binder = node.args[0]
            if binder.op == "var" and isinstance(binder.value, str):
                serial += 1
                renamed = f"{binder.value}{suffix}{serial}"
                new_binder = replace(binder, value=renamed)
                bodies = tuple(
                    visit(arg, (*environment, (binder.value, renamed))) for arg in node.args[1:]
                )
                return replace(node, args=(new_binder, *bodies))
        return replace(node, args=tuple(visit(arg, environment) for arg in node.args))

    return visit(expression, ())


def semantic_mutations(state: CanonicalState) -> tuple[MutationCase, ...]:
    """Return a stable suite of positive and negative semantic attacks.

    Negative cases are deliberately invalid according to a local, independently checked
    witness.  Unsupported attacks becoming false accepts are reported by the Refuter;
    they are never silently counted as passes.
    """

    cases: list[MutationCase] = []
    object_ids = [item.object_id for item in state.objects]
    binder_ids = [item.binder_id for item in state.bindings]
    evidence_ids = [item.evidence_id for item in state.evidence_dependencies]
    action_ids = [
        item.action_id for item in (*state.legal_actions, *state.plausible_invalid_actions)
    ]

    renamed_goal = alpha_rename(state.goal)
    alpha_state = replace(state, goal=renamed_goal)
    cases.append(
        _case(
            AttackClass.ALPHA_RENAMING,
            "capture-avoiding bound-variable renaming preserves acceptance",
            state,
            alpha_state,
            expected_accepted=True,
        )
    )

    capture_name = _fresh(
        [*object_ids, *(binding.variable for binding in state.bindings)], "__captured"
    )
    free_occurrence = _expr("var", value=capture_name, sort="Scalar")
    bound_occurrence = _expr("var", value=capture_name, sort="Scalar")
    binder = _expr("var", value=capture_name, sort="Scalar")
    capture_goal = _expr(
        "and",
        free_occurrence,
        _expr("forall", binder, bound_occurrence, sort="Bool"),
        sort="Bool",
    )
    cases.append(
        _case(
            AttackClass.VARIABLE_CAPTURE,
            "a binder in one branch must not bind a free occurrence in its sibling",
            state,
            replace(state, goal=capture_goal),
            expected_accepted=False,
        )
    )

    unbound_name = _fresh(
        [*object_ids, *(binding.variable for binding in state.bindings)], "__unbound"
    )
    cases.append(
        _case(
            AttackClass.UNBOUND_VARIABLE,
            "undeclared free variable",
            state,
            replace(state, goal=_expr("var", value=unbound_name, sort="Scalar")),
            expected_accepted=False,
        )
    )

    scope_id = _fresh(state.local_scope, "__absent_scope")
    scope_binding = Binding(
        binder_id=_fresh(binder_ids, "refuter:binder"),
        variable=_fresh((binding.variable for binding in state.bindings), "__scope_var"),
        type_name="Scalar",
        scope_id=scope_id,
        binder_kind="free",
    )
    cases.append(
        _case(
            AttackClass.UNKNOWN_SCOPE,
            "binding points outside the declared scope set",
            state,
            replace(state, bindings=(*state.bindings, scope_binding)),
            expected_accepted=False,
        )
    )

    partial = _expr(
        "div",
        _expr("literal", value=1, sort="Scalar"),
        _expr("literal", value=0, sort="Scalar"),
        sort="Scalar",
    )
    obligations = tuple(
        obligation
        for obligation in state.obligations
        if not (
            obligation.proposition.op == "defined"
            and obligation.proposition.args
            and obligation.proposition.args[0].content_hash == partial.content_hash
        )
    )
    cases.append(
        _case(
            AttackClass.DEFINEDNESS,
            "partial operation lacks its exact definedness obligation",
            state,
            replace(state, goal=partial, obligations=obligations),
            expected_accepted=False,
        )
    )

    malformed = _expr("forall", _expr("var", value="x", sort="Scalar"), sort="Bool")
    cases.append(
        _case(
            AttackClass.SHADOWING,
            "malformed binder with no body",
            state,
            replace(state, goal=malformed),
            expected_accepted=False,
        )
    )

    ev_a = _fresh(evidence_ids, "refuter:evidence:a")
    ev_b = _fresh([*evidence_ids, ev_a], "refuter:evidence:b")
    cycle = (
        *state.evidence_dependencies,
        EvidenceNode(ev_a, "VERIFIED", (ev_b,)),
        EvidenceNode(ev_b, "VERIFIED", (ev_a,)),
    )
    cases.append(
        _case(
            AttackClass.EVIDENCE_CYCLE,
            "two-node cyclic evidence dependency",
            state,
            replace(state, evidence_dependencies=cycle),
            expected_accepted=False,
        )
    )

    ev_unknown = _fresh(evidence_ids, "refuter:evidence:unknown-owner")
    absent = _fresh([*evidence_ids, ev_unknown], "refuter:evidence:absent")
    cases.append(
        _case(
            AttackClass.UNKNOWN_EVIDENCE,
            "evidence depends on a missing node",
            state,
            replace(
                state,
                evidence_dependencies=(
                    *state.evidence_dependencies,
                    EvidenceNode(ev_unknown, "VERIFIED", (absent,)),
                ),
            ),
            expected_accepted=False,
        )
    )

    collision_id = object_ids[0] if object_ids else "refuter:collision"
    collision_objects = (
        *state.objects,
        MathObject(collision_id, "Scalar"),
        *((MathObject(collision_id, "Scalar"),) if not object_ids else ()),
    )
    cases.append(
        _case(
            AttackClass.ID_COLLISION,
            "duplicate canonical object identity",
            state,
            replace(state, objects=collision_objects),
            expected_accepted=False,
        )
    )

    bool_value = _expr("literal", value=True, sort="Bool")
    scalar_value = _expr("literal", value=1, sort="Scalar")
    cases.append(
        _case(
            AttackClass.TYPE_CONFUSION,
            "arithmetic combines Bool and Scalar operands",
            state,
            replace(state, goal=_expr("add", bool_value, scalar_value, sort="Scalar")),
            expected_accepted=False,
        )
    )

    matrix_left = CanonicalExpression(
        "literal", value="A", sort="Matrix", attributes=(("shape", "2x3"),)
    )
    matrix_right = CanonicalExpression(
        "literal", value="B", sort="Matrix", attributes=(("shape", "4x2"),)
    )
    cases.append(
        _case(
            AttackClass.MATRIX_SHAPE,
            "matrix multiplication has incompatible inner dimensions",
            state,
            replace(state, goal=_expr("matmul", matrix_left, matrix_right, sort="Matrix")),
            expected_accepted=False,
        )
    )

    probability = _expr(
        "conditional_probability",
        _expr("literal", value="parameter", sort="Parameter"),
        _expr("literal", value="event", sort="Event"),
        sort="Probability",
    )
    cases.append(
        _case(
            AttackClass.PROBABILITY_ROLE,
            "conditional probability uses a parameter where an event is required",
            state,
            replace(state, goal=probability),
            expected_accepted=False,
        )
    )

    exactness = _expr(
        "eq",
        _expr("literal", value="0.333333", sort="ApproximateScalar"),
        _expr("literal", value="1/3", sort="ExactScalar"),
        sort="Bool",
    )
    cases.append(
        _case(
            AttackClass.EXACTNESS_CONFUSION,
            "approximate and exact values are asserted equal without tolerance",
            state,
            replace(state, goal=exactness),
            expected_accepted=False,
        )
    )

    unknown_target = _fresh(object_ids, "refuter:missing-target")
    bad_action = CanonicalAction(
        action_id=_fresh(action_ids, "refuter:bad-action"),
        operation="rewrite",
        target_ids=(unknown_target,),
    )
    cases.append(
        _case(
            AttackClass.ILLEGAL_TRANSFORMATION,
            "action targets an absent object",
            state,
            replace(
                state, plausible_invalid_actions=(*state.plausible_invalid_actions, bad_action)
            ),
            expected_accepted=False,
        )
    )

    legal_action = (
        state.legal_actions[0]
        if state.legal_actions
        else CanonicalAction(
            action_id=_fresh(action_ids, "refuter:legal-action"),
            operation="rewrite",
            target_ids=("goal",),
        )
    )
    before = (
        state
        if state.legal_actions
        else replace(state, legal_actions=(*state.legal_actions, legal_action))
    )
    laundered_after = replace(before, goal=_expr("literal", value=True, sort="Bool"))
    goal_transition = CanonicalTransition(
        transition_id="refuter:goal-laundering",
        state_before=before,
        action=legal_action,
        state_after=laundered_after,
        verification=(),
    )
    cases.append(
        _case(
            AttackClass.GOAL_LAUNDERING,
            "goal is replaced by truth without a supporting generated obligation",
            state,
            goal_transition,
            expected_accepted=False,
        )
    )

    obligation = Obligation(
        obligation_id=_fresh((item.obligation_id for item in before.obligations), "refuter:open"),
        proposition=_expr("eq", scalar_value, scalar_value, sort="Bool"),
    )
    obligation_before = replace(before, obligations=(*before.obligations, obligation))
    obligation_after = replace(
        obligation_before, obligations=before.obligations, terminal_status="OPEN"
    )
    obligation_transition = CanonicalTransition(
        transition_id="refuter:obligation-laundering",
        state_before=obligation_before,
        action=legal_action,
        state_after=obligation_after,
        verification=(),
    )
    cases.append(
        _case(
            AttackClass.OBLIGATION_LAUNDERING,
            "an open obligation disappears without discharge evidence",
            state,
            obligation_transition,
            expected_accepted=False,
        )
    )

    return tuple(cases)


def grammar_mutations(source: str) -> tuple[GrammarMutation, ...]:
    """Apply deterministic corruptions that a strict parser should reject."""

    raw_cases = (
        ("empty", ""),
        ("nul-byte", source + "\x00"),
        ("unclosed-delimiter", source + "("),
        ("unexpected-close", ")" + source),
        ("unicode-replacement-tail", source + "\ufffd"),
        ("trailing-garbage", source + " @@REFUTER_INVALID@@"),
    )
    result: list[GrammarMutation] = []
    for operation, mutated in raw_cases:
        mutation_id = "grammar:" + stable_hash(
            {"operation": operation, "source": mutated, "expected_parse": False}
        )
        result.append(GrammarMutation(mutation_id, operation, mutated))
    return tuple(result)


def _walk(expression: CanonicalExpression) -> Iterable[CanonicalExpression]:
    yield expression
    for argument in expression.args:
        yield from _walk(argument)


def _expressions(state: CanonicalState) -> Iterable[CanonicalExpression]:
    yield from state.assumptions
    yield from state.established_facts
    yield from state.propositions
    yield state.goal
    yield from (item.proposition for item in state.obligations)
    for action in (*state.legal_actions, *state.plausible_invalid_actions):
        yield from action.arguments
        yield from action.preconditions


def _has_lexically_unbound(expression: CanonicalExpression, declared: set[str]) -> bool:
    binders = {"forall", "exists", "lambda", "sum_over", "integral_over"}

    def visit(node: CanonicalExpression, environment: tuple[str, ...]) -> bool:
        if node.op == "var" and isinstance(node.value, str):
            return node.value not in declared and node.value not in environment
        if node.op in binders and len(node.args) >= 2:
            binder = node.args[0]
            if binder.op == "var" and isinstance(binder.value, str):
                return any(visit(child, (*environment, binder.value)) for child in node.args[1:])
        return any(visit(child, environment) for child in node.args)

    return visit(expression, ())


def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
    active: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in done:
            return False
        active.add(node)
        if any(visit(dependency) for dependency in graph.get(node, ())):
            return True
        active.remove(node)
        done.add(node)
        return False

    return any(visit(node) for node in graph)


def mutation_witness(
    attack_class: AttackClass, subject: Subject, original: Subject | None = None
) -> bool:
    """Independently recognize the defect (or positive invariant) in a mutation."""

    if attack_class in {AttackClass.GOAL_LAUNDERING, AttackClass.OBLIGATION_LAUNDERING}:
        if not isinstance(subject, CanonicalTransition):
            return False
        if attack_class == AttackClass.GOAL_LAUNDERING:
            goal = subject.state_after.goal
            return (
                subject.state_before.goal != goal
                and goal.op == "literal"
                and goal.value is True
                and not subject.action.generated_obligations
            )
        before = {
            item.obligation_id for item in subject.state_before.obligations if item.status == "OPEN"
        }
        after = {item.obligation_id for item in subject.state_after.obligations}
        return bool(before - after) and not subject.action.generated_obligations

    if not isinstance(subject, CanonicalState):
        return False
    if attack_class == AttackClass.ALPHA_RENAMING:
        return isinstance(original, CanonicalState) and expressions_equivalent(
            original.goal, subject.goal
        )
    if attack_class in {AttackClass.VARIABLE_CAPTURE, AttackClass.UNBOUND_VARIABLE}:
        declared = {item.object_id for item in subject.objects}
        declared.update(item.variable for item in subject.bindings if item.binder_kind == "free")
        return any(
            _has_lexically_unbound(expression, declared) for expression in _expressions(subject)
        )
    if attack_class in {AttackClass.UNKNOWN_SCOPE, AttackClass.SHADOWING}:
        if attack_class == AttackClass.UNKNOWN_SCOPE:
            return any(item.scope_id not in set(subject.local_scope) for item in subject.bindings)
        return any(
            node.op in {"forall", "exists", "lambda", "sum_over", "integral_over"}
            and len(node.args) < 2
            for expression in _expressions(subject)
            for node in _walk(expression)
        )
    if attack_class == AttackClass.DEFINEDNESS:
        defined = {
            node.args[0].content_hash
            for obligation in subject.obligations
            for node in _walk(obligation.proposition)
            if node.op == "defined" and len(node.args) == 1
        }
        return any(
            node.op in {"div", "sqrt", "log", "inverse", "index", "condition"}
            and node.content_hash not in defined
            for expression in _expressions(subject)
            for node in _walk(expression)
        )
    if attack_class == AttackClass.EVIDENCE_CYCLE:
        return _has_cycle(
            {item.evidence_id: item.dependencies for item in subject.evidence_dependencies}
        )
    if attack_class == AttackClass.UNKNOWN_EVIDENCE:
        known = {item.evidence_id for item in subject.evidence_dependencies}
        return any(set(item.dependencies) - known for item in subject.evidence_dependencies)
    if attack_class == AttackClass.ID_COLLISION:
        identity_groups = (
            [item.object_id for item in subject.objects],
            [item.binder_id for item in subject.bindings],
            [item.evidence_id for item in subject.evidence_dependencies],
            [item.obligation_id for item in subject.obligations],
            [
                item.action_id
                for item in (*subject.legal_actions, *subject.plausible_invalid_actions)
            ],
        )
        return any(any(count > 1 for count in Counter(group).values()) for group in identity_groups)
    if attack_class == AttackClass.TYPE_CONFUSION:
        arithmetic = {"add", "sub", "mul", "div"}
        return any(
            node.op in arithmetic
            and len(node.args) == 2
            and (
                "Bool" in {node.args[0].sort, node.args[1].sort}
                or node.args[0].sort != node.args[1].sort
            )
            for expression in _expressions(subject)
            for node in _walk(expression)
        )
    if attack_class == AttackClass.MATRIX_SHAPE:
        for expression in _expressions(subject):
            for node in _walk(expression):
                if node.op == "matmul" and len(node.args) == 2:
                    shapes = [dict(arg.attributes).get("shape", "") for arg in node.args]
                    try:
                        left = tuple(int(item) for item in shapes[0].split("x"))
                        right = tuple(int(item) for item in shapes[1].split("x"))
                    except ValueError:
                        continue
                    if len(left) == len(right) == 2 and left[1] != right[0]:
                        return True
        return False
    if attack_class == AttackClass.PROBABILITY_ROLE:
        return any(
            node.op == "conditional_probability"
            and len(node.args) >= 1
            and node.args[0].sort != "Event"
            for expression in _expressions(subject)
            for node in _walk(expression)
        )
    if attack_class == AttackClass.EXACTNESS_CONFUSION:
        return any(
            node.op == "eq"
            and len(node.args) == 2
            and {node.args[0].sort, node.args[1].sort} == {"ApproximateScalar", "ExactScalar"}
            for expression in _expressions(subject)
            for node in _walk(expression)
        )
    if attack_class == AttackClass.ILLEGAL_TRANSFORMATION:
        targets = {item.object_id for item in subject.objects} | {"goal"}
        return any(
            bool(set(action.target_ids) - targets)
            for action in (*subject.legal_actions, *subject.plausible_invalid_actions)
        )
    return False


def select_mutations(
    state: CanonicalState, predicate: Callable[[MutationCase], bool]
) -> tuple[MutationCase, ...]:
    """Convenience filter that preserves canonical mutation order."""

    return tuple(case for case in semantic_mutations(state) if predicate(case))
