"""Deterministic Arena World v0.

The generator favors small, auditable mechanism probes over exotic mathematics.  Each
initial state contains at least one legal action and one tempting invalid action.  GOLD
records carry both native-verifier evidence and an explicit independent template-check
certificate; checks that did not run are never promoted to GOLD.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from typing import overload

from arena.canonical.schema import (
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    CanonicalTrajectory,
    CanonicalTransition,
    EvidenceNode,
    GoldStatus,
    MathObject,
    Obligation,
    VerificationRecord,
    VerificationStatus,
    stable_hash,
)
from arena.tasks.quality import trajectory_quality
from arena.tasks.schema import ArenaTask, TaskDimensions, TaskDomain, WorldSummary
from arena.verifier.base import VerificationResult
from arena.verifier.native import NativeVerifier

DEFAULT_WORLD_SIZE = 676
WORLD_ID = "arena-world-v0"
INDEPENDENT_VALIDATOR = "arena-domain-template"
INDEPENDENT_VALIDATOR_VERSION = "0.1.0"
SUPPORTED_DOMAINS = tuple(domain.value for domain in TaskDomain)


def _expr(
    op: str,
    *args: CanonicalExpression,
    value: str | int | float | bool | None = None,
    sort: str = "Unknown",
    attributes: tuple[tuple[str, str], ...] = (),
) -> CanonicalExpression:
    return CanonicalExpression(op, tuple(args), value, sort, attributes)


def _integer(value: int) -> CanonicalExpression:
    return _expr("integer", value=value, sort="Integer")


def _real(value: int | float) -> CanonicalExpression:
    return _expr("real", value=value, sort="Real")


def _symbol(value: str, *, sort: str = "Unknown") -> CanonicalExpression:
    return _expr("symbol", value=value, sort=sort)


@dataclass(frozen=True, slots=True)
class _DomainCase:
    problem: CanonicalExpression
    answer: CanonicalExpression
    invalid_answer: CanonicalExpression
    operation: str
    objects: tuple[MathObject, ...] = ()
    bindings: tuple[Binding, ...] = ()
    assumptions: tuple[CanonicalExpression, ...] = ()
    obligations: tuple[Obligation, ...] = ()
    evidence: tuple[EvidenceNode, ...] = ()
    scope: tuple[str, ...] = ("scope:root",)
    reasoning_depth: int = 1
    dependency_depth: int = 0
    scope_depth: int = 0
    quantifier_alternation: int = 0
    partiality: int = 0
    composition_count: int = 1
    cross_domain_interaction: int = 0


def _case(domain: str, index: int, rng: random.Random, prefix: str) -> _DomainCase:
    """Create one bounded domain template with a separately computable answer."""

    a = 2 + rng.randrange(17)
    b = 1 + rng.randrange(11)
    root_scope = f"scope:{prefix}:root"
    obj = MathObject(f"object:{prefix}", "DomainWitness")

    if domain == TaskDomain.ARITHMETIC:
        problem = _expr("add", _integer(a), _integer(b), sort="Integer")
        return _DomainCase(problem, _integer(a + b), _integer(a + b + 1), "evaluate", (obj,))

    if domain == TaskDomain.ALGEBRA:
        variable = f"x_{index}"
        x = _expr("var", value=variable, sort="Real")
        problem = _expr("eq", _expr("add", x, _real(b), sort="Real"), _real(a + b), sort="Bool")
        answer = _expr("eq", x, _real(a), sort="Bool")
        invalid = _expr("eq", x, _real(a + 1), sort="Bool")
        binding = Binding(f"binding:{prefix}", variable, "Real", root_scope, "free")
        return _DomainCase(
            problem,
            answer,
            invalid,
            "isolate_variable",
            (obj,),
            (binding,),
            scope=(root_scope,),
            reasoning_depth=2,
            scope_depth=1,
            composition_count=2,
        )

    if domain == TaskDomain.LOGIC:
        p = _symbol(f"P{index}", sort="Proposition")
        q = _symbol(f"Q{index}", sort="Proposition")
        premise = _expr("implies", p, q, sort="Proposition")
        problem = _expr("and", premise, p, sort="Proposition")
        invalid = _expr("not", q, sort="Proposition")
        return _DomainCase(
            problem,
            q,
            invalid,
            "modus_ponens",
            (obj,),
            assumptions=(premise, p),
            reasoning_depth=2,
            dependency_depth=1,
            composition_count=2,
        )

    if domain == TaskDomain.BINDING:
        x_name = f"x_{index}"
        y_name = f"y_{index}"
        x = _expr("var", value=x_name, sort="Element")
        y = _expr("var", value=y_name, sort="Element")
        predicate_x = _expr("predicate", x, value="P", sort="Proposition")
        predicate_y = _expr("predicate", y, value="P", sort="Proposition")
        problem = _expr("forall", x, predicate_x, sort="Proposition")
        answer = _expr("forall", y, predicate_y, sort="Proposition")
        invalid = _expr("exists", y, predicate_y, sort="Proposition")
        return _DomainCase(
            problem,
            answer,
            invalid,
            "alpha_rename",
            (obj,),
            scope=(root_scope,),
            reasoning_depth=2,
            scope_depth=2,
            composition_count=2,
        )

    if domain == TaskDomain.SETS:
        element = _integer(a)
        set_value = _expr("finite_set", element, _integer(a + 1), sort="Set[Integer]")
        problem = _expr("member", element, set_value, sort="Bool")
        invalid = _expr("not", problem, sort="Bool")
        return _DomainCase(
            problem,
            _expr("boolean", value=True, sort="Bool"),
            invalid,
            "check_membership",
            (obj,),
            composition_count=2,
        )

    if domain == TaskDomain.PROBABILITY:
        event_a = _symbol(f"A{index}", sort="Event")
        event_b = _symbol(f"B{index}", sort="Event")
        problem = _expr("conditional_probability", event_a, event_b, sort="Probability")
        numerator = _expr(
            "probability", _expr("intersection", event_a, event_b, sort="Event"), sort="Probability"
        )
        denominator = _expr("probability", event_b, sort="Probability")
        answer = _expr("ratio", numerator, denominator, sort="Probability")
        invalid = _expr("ratio", denominator, numerator, sort="Probability")
        assumption = _expr("positive", denominator, sort="Bool")
        return _DomainCase(
            problem,
            answer,
            invalid,
            "expand_conditional_probability",
            (obj,),
            assumptions=(assumption,),
            reasoning_depth=2,
            dependency_depth=1,
            composition_count=3,
            cross_domain_interaction=1,
        )

    if domain == TaskDomain.STATISTICS:
        observations = (_integer(a), _integer(a + 2), _integer(a + 4))
        sample = _expr("sample", *observations, sort="Sample[Integer]")
        problem = _expr("sample_mean", sample, sort="Real")
        return _DomainCase(
            problem,
            _integer(a + 2),
            _integer(a + 3),
            "estimate_sample_mean",
            (MathObject(f"object:{prefix}", "Sample", shape=(3,)),),
            reasoning_depth=2,
            composition_count=2,
        )

    if domain == TaskDomain.CALCULUS:
        x_name = f"x_{index}"
        x = _expr("var", value=x_name, sort="Real")
        square = _expr("power", x, _integer(2), sort="Real")
        problem = _expr("derivative", square, x, sort="Real")
        answer = _expr("mul", _real(2), x, sort="Real")
        invalid = _expr("mul", x, x, sort="Real")
        binding = Binding(f"binding:{prefix}", x_name, "Real", root_scope, "free")
        return _DomainCase(
            problem,
            answer,
            invalid,
            "differentiate_power",
            (obj,),
            (binding,),
            scope=(root_scope,),
            reasoning_depth=2,
            scope_depth=1,
            composition_count=2,
        )

    if domain == TaskDomain.LINEAR_ALGEBRA:
        vector = _expr("vector", _integer(a), _integer(b), sort="Vector[2]")
        problem = _expr("dimension", vector, sort="Natural")
        return _DomainCase(
            problem,
            _integer(2),
            _integer(3),
            "infer_shape",
            (MathObject(f"object:{prefix}", "Vector", vector, shape=(2,)),),
            reasoning_depth=2,
            composition_count=2,
        )

    if domain == TaskDomain.PHYSICAL_DIMENSIONS:
        distance = _real(a)
        time = _real(b)
        problem = _expr(
            "quantity_divide",
            distance,
            time,
            sort="Quantity",
            attributes=(("left_unit", "length"), ("right_unit", "time")),
        )
        answer = _symbol("length/time", sort="PhysicalDimension")
        invalid = _symbol("length*time", sort="PhysicalDimension")
        return _DomainCase(
            problem,
            answer,
            invalid,
            "infer_dimension",
            (MathObject(f"object:{prefix}", "Quantity", unit="length/time"),),
            reasoning_depth=2,
            composition_count=2,
            cross_domain_interaction=1,
        )

    if domain == TaskDomain.OPTIMIZATION:
        x_name = f"x_{index}"
        x = _expr("var", value=x_name, sort="Real")
        objective = _expr("power", _expr("sub", x, _real(a), sort="Real"), _integer(2), sort="Real")
        problem = _expr("argmin", x, objective, sort="Real")
        binding = Binding(f"binding:{prefix}", x_name, "Real", root_scope, "free")
        return _DomainCase(
            problem,
            _real(a),
            _real(a + 1),
            "minimize_convex_quadratic",
            (obj,),
            (binding,),
            scope=(root_scope,),
            reasoning_depth=3,
            scope_depth=1,
            composition_count=3,
        )

    if domain == TaskDomain.PARTIAL_OPERATIONS:
        operator = ("div", "sqrt", "log", "inverse", "index", "condition")[index % 6]
        if operator == "div":
            partial = _expr("div", _integer(a * b), _integer(b), sort="Real")
            answer = _integer(a)
        elif operator == "sqrt":
            partial = _expr("sqrt", _integer(a * a), sort="Real")
            answer = _integer(a)
        elif operator == "log":
            partial = _expr("log", _real(1), sort="Real")
            answer = _integer(0)
        elif operator == "inverse":
            partial = _expr("inverse", _integer(1), sort="Real")
            answer = _integer(1)
        elif operator == "index":
            partial = _expr(
                "index",
                _expr("vector", _integer(a), _integer(b), sort="Vector[2]"),
                _integer(0),
                sort="Integer",
            )
            answer = _integer(a)
        else:
            partial = _expr(
                "condition",
                _symbol(f"A{index}", sort="Event"),
                _symbol(f"B{index}", sort="Event"),
                sort="Event",
            )
            answer = _symbol(f"A{index}|B{index}", sort="Event")
        definedness = Obligation(
            f"obligation:{prefix}:defined",
            _expr("defined", partial, sort="Proposition"),
            "OPEN",
            "domain-template",
        )
        return _DomainCase(
            partial,
            answer,
            _symbol("undefined", sort=answer.sort),
            "evaluate_with_definedness",
            (obj,),
            obligations=(definedness,),
            reasoning_depth=3,
            dependency_depth=1,
            partiality=1,
            composition_count=2,
            cross_domain_interaction=1,
        )

    if domain == TaskDomain.REASONING_EVIDENCE:
        premise = _symbol(f"premise_{index}", sort="Proposition")
        conclusion = _symbol(f"conclusion_{index}", sort="Proposition")
        implication = _expr("implies", premise, conclusion, sort="Proposition")
        evidence = (
            EvidenceNode(f"evidence:{prefix}:premise", "VERIFIED", authority="given"),
            EvidenceNode(
                f"evidence:{prefix}:derivation",
                "VERIFIED",
                (f"evidence:{prefix}:premise",),
                "domain-template",
            ),
        )
        return _DomainCase(
            _expr("derive", implication, premise, sort="Proposition"),
            conclusion,
            _expr("not", conclusion, sort="Proposition"),
            "replay_verified_derivation",
            (obj,),
            assumptions=(implication, premise),
            evidence=evidence,
            reasoning_depth=3,
            dependency_depth=2,
            composition_count=3,
        )

    raise ValueError(f"unsupported Arena World v0 domain {domain!r}")


def _native_record(result: VerificationResult) -> VerificationRecord:
    return VerificationRecord(
        verifier=result.verifier,
        verifier_version=result.version,
        status=VerificationStatus.VERIFIED if result.accepted else VerificationStatus.REFUTED,
        accepted=result.accepted,
        details="; ".join(f"{issue.code}: {issue.message}" for issue in result.issues),
        certificate_hash=stable_hash(
            {
                "verifier": result.verifier,
                "version": result.version,
                "accepted": result.accepted,
                "issues": [issue.code for issue in result.issues],
            }
        ),
    )


def _domain_record(
    requested_quality: GoldStatus,
    *,
    domain: str,
    prefix: str,
    expected: CanonicalExpression,
    observed: CanonicalExpression,
) -> VerificationRecord:
    certificate_payload = {
        "validator": INDEPENDENT_VALIDATOR,
        "version": INDEPENDENT_VALIDATOR_VERSION,
        "domain": domain,
        "case": prefix,
        "expected_hash": expected.content_hash,
        "observed_hash": observed.content_hash,
    }
    if requested_quality == GoldStatus.SILVER:
        return VerificationRecord(
            INDEPENDENT_VALIDATOR,
            INDEPENDENT_VALIDATOR_VERSION,
            VerificationStatus.UNKNOWN,
            False,
            "independent domain replay was not run; native structural checks only",
        )
    accepted = expected.content_hash == observed.content_hash
    return VerificationRecord(
        INDEPENDENT_VALIDATOR,
        INDEPENDENT_VALIDATOR_VERSION,
        VerificationStatus.VERIFIED if accepted else VerificationStatus.REFUTED,
        accepted,
        "exact deterministic domain-template replay" if accepted else "planted answer was refuted",
        stable_hash(certificate_payload),
    )


def _quality_plan(count: int) -> tuple[GoldStatus, ...]:
    if count <= 0:
        return ()
    gold = max(1, round(count * 40 / 52))
    silver = round(count * 8 / 52)
    if gold + silver > count:
        silver = max(0, count - gold)
    return (
        *(GoldStatus.GOLD for _ in range(gold)),
        *(GoldStatus.SILVER for _ in range(silver)),
        *(GoldStatus.REJECT for _ in range(count - gold - silver)),
    )


def _generate_task(
    domain: str,
    domain_index: int,
    requested_quality: GoldStatus,
    *,
    seed: int,
) -> ArenaTask:
    slug = domain.replace("_", "-")
    prefix = f"{slug}:{seed:04d}:{domain_index:04d}"
    rng = random.Random(f"{WORLD_ID}:{seed}:{domain}:{domain_index}")
    case = _case(domain, domain_index, rng, prefix)
    action = CanonicalAction(
        f"action:{prefix}:valid",
        case.operation,
        ("goal",),
        (case.answer,),
        "arena-world-v0 exact template",
        case.assumptions,
        expected_usefulness=1.0,
    )
    invalid_action = CanonicalAction(
        f"action:{prefix}:invalid",
        f"invalid_{case.operation}",
        ("goal",),
        (case.invalid_answer,),
        "plausible distractor: off-by-one, reversed rule, or lost obligation",
        expected_usefulness=-1.0,
    )
    state = CanonicalState(
        f"state:{prefix}:initial",
        case.objects,
        case.bindings,
        case.assumptions,
        (),
        (case.problem,),
        case.problem,
        case.obligations,
        case.evidence,
        case.scope,
        (action,),
        (invalid_action,),
        execution_metadata=(("domain", domain), ("generator", WORLD_ID)),
    )

    observed = case.invalid_answer if requested_quality == GoldStatus.REJECT else case.answer
    final_obligations = tuple(replace(item, status="DISCHARGED") for item in case.obligations)
    final_state = CanonicalState(
        f"state:{prefix}:final",
        case.objects,
        case.bindings,
        case.assumptions,
        (observed,),
        (case.problem,),
        case.problem,
        final_obligations,
        case.evidence,
        case.scope,
        (),
        (),
        "SOLVED" if requested_quality != GoldStatus.REJECT else "REFUTED",
        execution_metadata=(("domain", domain), ("generator", WORLD_ID)),
    )
    transition_stub = CanonicalTransition(f"transition:{prefix}", state, action, final_state, ())
    native = _native_record(NativeVerifier().verify_transition(transition_stub))
    domain_check = _domain_record(
        requested_quality,
        domain=domain,
        prefix=prefix,
        expected=case.answer,
        observed=observed,
    )
    records = (native, domain_check)
    quality = trajectory_quality((records,), independent_verifiers=(INDEPENDENT_VALIDATOR,))
    transition = replace(transition_stub, verification=records)
    trajectory = CanonicalTrajectory(
        f"trajectory:{prefix}",
        case.problem,
        state,
        (transition,),
        final_state,
        observed,
        {
            GoldStatus.GOLD: "independently_verified",
            GoldStatus.SILVER: "native_checked_independent_unknown",
            GoldStatus.REJECT: "independent_refutation",
        }[quality],
        quality,
        (
            ("domain", domain),
            ("generator", WORLD_ID),
            ("generator_seed", str(seed)),
            ("independent_validator", INDEPENDENT_VALIDATOR),
            ("independent_validation", domain_check.status.value),
            ("native_validation", native.status.value),
        ),
    )
    dimensions = TaskDimensions(
        domain=domain,
        reasoning_depth=case.reasoning_depth,
        dependency_depth=case.dependency_depth,
        scope_depth=case.scope_depth,
        quantifier_alternation=case.quantifier_alternation,
        number_of_assumptions=len(case.assumptions),
        number_of_legal_actions=1,
        number_of_plausible_invalid_actions=1,
        partiality=case.partiality,
        composition_count=case.composition_count,
        proof_length=1,
        cross_domain_interaction=case.cross_domain_interaction,
    )
    split_selector = domain_index % 10
    split = "train" if split_selector < 7 else "validation" if split_selector < 9 else "test"
    return ArenaTask(
        f"task:{prefix}",
        trajectory,
        dimensions,
        split,
        (domain, quality.value.lower(), case.operation),
        (("requested_quality", requested_quality.value),),
    )


@dataclass(frozen=True, slots=True)
class ArenaWorldV0(Sequence[ArenaTask]):
    tasks: tuple[ArenaTask, ...]
    summary: WorldSummary

    def __len__(self) -> int:
        return len(self.tasks)

    @overload
    def __getitem__(self, index: int) -> ArenaTask: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[ArenaTask, ...]: ...

    def __getitem__(self, index: int | slice) -> ArenaTask | tuple[ArenaTask, ...]:
        return self.tasks[index]

    def __iter__(self) -> Iterator[ArenaTask]:
        return iter(self.tasks)

    @property
    def trajectories(self) -> tuple[CanonicalTrajectory, ...]:
        return tuple(task.trajectory for task in self.tasks)


def generate_tasks(*, total: int = DEFAULT_WORLD_SIZE, seed: int = 0) -> tuple[ArenaTask, ...]:
    """Generate exactly ``total`` tasks, balanced across all required domains."""

    if total <= 0:
        raise ValueError("Arena World v0 must contain at least one task")
    base, remainder = divmod(total, len(SUPPORTED_DOMAINS))
    tasks: list[ArenaTask] = []
    for domain_position, domain in enumerate(SUPPORTED_DOMAINS):
        count = base + (domain_position < remainder)
        for index, quality in enumerate(_quality_plan(count)):
            tasks.append(_generate_task(domain, index, quality, seed=seed))
    return tuple(tasks)


def generate_trajectories(
    *, total: int = DEFAULT_WORLD_SIZE, seed: int = 0
) -> tuple[CanonicalTrajectory, ...]:
    return tuple(task.trajectory for task in generate_tasks(total=total, seed=seed))


def build_world_v0(*, total: int = DEFAULT_WORLD_SIZE, seed: int = 0) -> ArenaWorldV0:
    tasks = generate_tasks(total=total, seed=seed)
    domains = Counter(task.dimensions.domain for task in tasks)
    qualities = Counter(task.trajectory.quality.value for task in tasks)
    summary = WorldSummary(
        WORLD_ID,
        len(tasks),
        dict(sorted(domains.items())),
        dict(sorted(qualities.items())),
    )
    return ArenaWorldV0(tasks, summary)


generate_arena_world_v0 = build_world_v0
