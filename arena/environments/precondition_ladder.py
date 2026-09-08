"""Precondition-conjunction difficulty ladder v2 (auxiliary measurement environment, NOT Gold).

The mechanism is the one V4/V5/V7 call ``precondition_conjunction``: a state lists two
candidate answer identifiers ``a`` and ``b``, propositions ``requires(answer, premise)`` and
assumptions ``holds(premise)``.  Exactly one answer has every required premise held.  Truth is
an independent subset check (:func:`independent_truth`).

Why this module exists.  The V7 Solver sits at ceiling (>= 0.958) at ``premises`` 2/3/5, so the
frozen V4 ladder (1/2/3/5/8) cannot place a frontier.  This module extends the ladder *upward*
and adds explicitly parameterised controls, while keeping the canonical encoding of the
mechanism byte-for-byte compatible with V4/V5/V7: the same ``requires``/``holds``/
``fully_licensed_answer`` relations, the same ``object:id:<answer>`` objects, the same
``propose_structural_answer`` option shape, the same question text, and premise ids of the
same lexical form ``p:dddd`` (four digits 1-9).  Only the *difficulty parameters* move.

Balance by construction.  ``objects``, ``propositions`` and ``goal`` are built once and the
same tuple objects are reused by the ORIGINAL (``a`` licensed), COUNTERFACTUAL (mirror: ``b``
licensed) and DESTROYED (neither) states; only ``assumptions`` differ.  Any feature that
ignores the assumptions block is therefore identical across a twin pair while the truth flips.
Two deliberate strengthenings over V4:

* the twin assumption lists are filled from ONE shuffled slot template, so the twins differ
  only at the ``1 + missing_near_misses`` substituted positions (V4 reshuffled per variant);
* no two real premise ids in a family are within one digit transposition of each other, and
  every planted near-miss is a transposition of exactly one real premise, so the confusability
  in a state is exactly the confusability the parameters declare.

Nothing here reads a file, opens a socket or calls a model.  All ordering is salted SHA-256; the
module imports none of ``random``, ``time``, ``uuid`` or ``os`` (asserted by the test module).
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from math import comb
from typing import Any

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    MathObject,
    Obligation,
    stable_hash,
)
from arena.experiments.game_r_formal_v1 import MaterialisedItem
from arena.verifier.native import NativeVerifier

ENVIRONMENT_VERSION = "arena-precondition-ladder-v2.0.0"
MECHANISM = "precondition_conjunction"

#: Identical to ``arena.experiments.fitness_v4._premise_family``'s question text.
QUESTION = (
    "Which answer ID has every one of its requires(answer, premise) propositions matched "
    "by an identical holds(premise) assumption?"
)
TRUTH_RULE = "independent subset check of required premises against held premises"

#: One neutral display identity for every state.  ``state_id`` is rendered on the page by
#: several surfaces, so it must carry no information; it is excluded from mathematical hashes.
STATE_ID = "state:precondition-ladder:neutral"

#: V4's premise-id form: four digits drawn from 1-9.  Grown only when the collision rule
#: cannot accommodate the requested id count (see :func:`premise_digits`).
BASE_PREMISE_DIGITS = 4
_PREMISE_PATTERN = re.compile(r"^p:[1-9]+$")
#: Deterministic re-draw budget when a salted draw cannot satisfy the near-miss constraints.
MAX_ATTEMPTS = 32


class Pool(StrEnum):
    """Disjoint item pools.  The pool name enters every salt, so pools cannot overlap."""

    DEV = "DEV"
    ADV_DEV = "ADV_DEV"
    SHORTCUT_EVAL = "SHORTCUT_EVAL"
    TOURNAMENT = "TOURNAMENT"
    SMOKE = "SMOKE"


class Variant(StrEnum):
    ORIGINAL = "ORIGINAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DESTROYED_ORIGINAL = "DESTROYED_ORIGINAL"
    DESTROYED_COUNTERFACTUAL = "DESTROYED_COUNTERFACTUAL"


# ------------------------------------------------------------------------------ parameters


@dataclass(frozen=True, slots=True)
class LadderParams:
    """Every knob of one stratum, explicit and frozen.

    ``premises``: required premises per answer (``a`` and ``b`` each).
    ``extras``: irrelevant held premises (V4 used 6).
    ``missing_near_misses``: held digit-transposed copies of the *unlicensed* answer's missing
    premise (V4 used 1).  Distinct transpositions, never equal to a real premise.
    ``decoy_near_misses``: held transposed copies of premises that ARE held, drawn alternately
    from ``a``'s and ``b``'s held premises and identical across the twins; truth is unchanged.
    They add confusability without any length asymmetry between the twins.
    ``distractor_objects``: unrelated ``Distractor`` objects (V4 used 4).
    ``explicit``: level-0 positive control; appends the established fact
    ``the_answer_is(<licensed>)`` exactly as ``fitness_v5._synthetic_family`` does.
    """

    premises: int
    extras: int = 6
    missing_near_misses: int = 1
    decoy_near_misses: int = 0
    distractor_objects: int = 4
    explicit: bool = False

    def __post_init__(self) -> None:
        if self.premises < 1:
            raise ValueError("premises must be at least 1")
        for name in ("extras", "missing_near_misses", "decoy_near_misses", "distractor_objects"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.decoy_near_misses > 2 * (self.premises - 1):
            raise ValueError(
                "decoy_near_misses needs a distinct held source premise each; at most "
                f"{2 * (self.premises - 1)} are available at premises={self.premises}"
            )

    @property
    def level(self) -> int:
        """``TaskItem.level``: 0 is reserved for the explicit-positive arm."""

        return 0 if self.explicit else self.premises

    @property
    def held_per_twin(self) -> int:
        """Number of ``holds`` assumptions in ORIGINAL and in COUNTERFACTUAL (equal)."""

        return (
            self.extras
            + 2 * (self.premises - 1)
            + self.decoy_near_misses
            + 1
            + self.missing_near_misses
        )

    @property
    def held_destroyed(self) -> int:
        return (
            self.extras
            + 2 * (self.premises - 1)
            + self.decoy_near_misses
            + 2 * self.missing_near_misses
        )

    @property
    def premise_ids_needed(self) -> int:
        return 2 * self.premises + self.extras

    def to_dict(self) -> dict[str, Any]:
        return {
            "premises": self.premises,
            "extras": self.extras,
            "missing_near_misses": self.missing_near_misses,
            "decoy_near_misses": self.decoy_near_misses,
            "distractor_objects": self.distractor_objects,
            "explicit": self.explicit,
        }


#: Ordered named strata.  Keys are part of the public contract; tests pin the exact set.
LADDER: dict[str, LadderParams] = {
    # level-0 explicit-positive control
    "P05_EXPLICIT": LadderParams(premises=5, explicit=True),
    # primary one-dimensional premise ladder (V4 defaults otherwise)
    "P05": LadderParams(premises=5),
    "P07": LadderParams(premises=7),
    "P09": LadderParams(premises=9),
    "P12": LadderParams(premises=12),
    "P16": LadderParams(premises=16),
    "P20": LadderParams(premises=20),
    # length controls at premises=5: more irrelevant held premises, same logic
    "P05_X16": LadderParams(premises=5, extras=16),
    "P05_X32": LadderParams(premises=5, extras=32),
    # confusability controls: more near-misses, no length asymmetry
    "P05_M2_D2": LadderParams(premises=5, missing_near_misses=2, decoy_near_misses=2),
    "P05_M3_D4": LadderParams(premises=5, missing_near_misses=3, decoy_near_misses=4),
    "P12_M2_D2": LadderParams(premises=12, missing_near_misses=2, decoy_near_misses=2),
}
PRIMARY_LADDER: tuple[str, ...] = ("P05", "P07", "P09", "P12", "P16", "P20")
STRATUM_ROLE: dict[str, str] = {
    "P05_EXPLICIT": "explicit_positive_control",
    "P05": "primary",
    "P07": "primary",
    "P09": "primary",
    "P12": "primary",
    "P16": "primary",
    "P20": "primary",
    "P05_X16": "length_control",
    "P05_X32": "length_control",
    "P05_M2_D2": "confusability_control",
    "P05_M3_D4": "confusability_control",
    "P12_M2_D2": "confusability_control",
}


def stratum_params(stratum: str) -> LadderParams:
    try:
        return LADDER[stratum]
    except KeyError:
        raise ValueError(f"unknown stratum {stratum!r}; known: {', '.join(LADDER)}") from None


def family_salt(stratum: str, pool: Pool | str, family_index: int) -> str:
    """Deterministic salt.  Version, stratum, pool and index all enter it, so pools are
    disjoint by construction and a version bump re-keys every family."""

    if stratum not in LADDER:
        raise ValueError(f"unknown stratum {stratum!r}")
    if family_index < 0:
        raise ValueError("family_index must be non-negative")
    return f"{ENVIRONMENT_VERSION}|{MECHANISM}|{stratum}|{Pool(pool).value}|{family_index}"


# ----------------------------------------------------------------------------- helpers
#
# Copied from ``arena.experiments.fitness_v4`` (a frozen instrument that must not be imported
# for its private helpers) so that this module encodes the mechanism identically.  ``_state``
# differs only in its neutral ``state_id``; ``_shuffled`` only in its type annotation.


def _h(seed: str, modulus: int) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16) % max(1, modulus)


def _hex(seed: str, length: int = 5) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def _shuffled[T](items: Sequence[T], seed: str) -> list[T]:
    order = sorted(range(len(items)), key=lambda index: _hex(f"{seed}|order|{index}", 16))
    return [items[index] for index in order]


def _atom(value: str) -> CanonicalExpression:
    return CanonicalExpression("symbol", value=value, sort="Identifier")


def _relation(name: str, *values: str) -> CanonicalExpression:
    return CanonicalExpression(name, tuple(_atom(value) for value in values), sort="Proposition")


def _distractors(prefix: str, count: int) -> tuple[MathObject, ...]:
    return tuple(
        MathObject(
            f"object:{prefix}:{index:02d}",
            "Distractor",
            _relation("tag", prefix, f"value:{(index * 7 + 3) % 29}"),
        )
        for index in range(count)
    )


def _identifier_objects(names: Sequence[str]) -> tuple[MathObject, ...]:
    return tuple(MathObject(f"object:id:{name}", "Identifier", _atom(name)) for name in names)


def _state(
    *,
    goal: CanonicalExpression,
    assumptions: tuple[CanonicalExpression, ...],
    propositions: tuple[CanonicalExpression, ...],
    objects: tuple[MathObject, ...],
) -> CanonicalState:
    return CanonicalState(
        state_id=STATE_ID,
        objects=objects,
        bindings=(),
        assumptions=assumptions,
        established_facts=(),
        propositions=propositions,
        goal=goal,
        obligations=(),
        evidence_dependencies=(),
        local_scope=("scope:root",),
        legal_actions=(),
        plausible_invalid_actions=(),
        terminal_status="OPEN",
        execution_metadata=(),
    )


def _option(index: int, answer: str, alternate: str) -> CanonicalAction:
    """A symmetric option: only the proposed identity differs between A and B."""

    obligation = Obligation(f"obligation:option:{index}", _relation("prove", answer), source=answer)
    return CanonicalAction(
        action_id=f"option:{index}",
        operation="propose_structural_answer",
        target_ids=(f"object:id:{answer}",),
        arguments=(_atom(answer),),
        warrant=f"evidence-authority:{answer}",
        preconditions=(_relation("requires", answer), _relation("exclude", alternate)),
        generated_obligations=(obligation,),
        expected_usefulness=0.0,
    )


# ------------------------------------------------------------------ premise identifiers


def _body(premise: str) -> str:
    return premise.split(":", 1)[1]


def _adjacent_swaps(body: str) -> tuple[str, ...]:
    """Distinct strings obtained by swapping one adjacent pair (V4's near-miss family)."""

    out: list[str] = []
    for index in range(len(body) - 1):
        if body[index] != body[index + 1]:
            chars = list(body)
            chars[index], chars[index + 1] = chars[index + 1], chars[index]
            out.append("".join(chars))
    return tuple(out)


def _distant_swaps(body: str) -> tuple[str, ...]:
    """Distinct strings obtained by swapping one non-adjacent pair."""

    out: list[str] = []
    for left in range(len(body)):
        for right in range(left + 2, len(body)):
            if body[left] != body[right]:
                chars = list(body)
                chars[left], chars[right] = chars[right], chars[left]
                out.append("".join(chars))
    return tuple(out)


def transposition_neighbours(premise: str) -> frozenset[str]:
    """Every premise id exactly one digit transposition away from ``premise``."""

    body = _body(premise)
    return frozenset(f"p:{item}" for item in (*_adjacent_swaps(body), *_distant_swaps(body)))


def premise_digits(ids_needed: int) -> int:
    """Smallest digit count (>= 4) whose id space holds ``ids_needed`` ids under the
    collision rule with 4x slack.  Each accepted id excludes itself, its reversal and its
    ``C(d, 2)`` transposition neighbours."""

    digits = BASE_PREMISE_DIGITS
    while ids_needed * (2 + comb(digits, 2)) * 4 > 9**digits:
        digits += 1
    return digits


def _premise_ids(count: int, digits: int, salt: str) -> tuple[str, ...]:
    """``count`` premise ids ``p:d...d`` (digits 1-9).  V4's rule (no id equals another or
    its reversal) plus: no id is one transposition away from another."""

    ids: list[str] = []
    seen: set[str] = set()
    excluded: set[str] = set()
    probe = 0
    limit = 64 * count + 64
    while len(ids) < count:
        if probe >= limit:
            raise ValueError("premise id space exhausted under the collision rule")
        body = "".join(
            str(_h(f"{salt}|digit|{probe}|{position}", 9) + 1) for position in range(digits)
        )
        probe += 1
        if body in seen or body[::-1] in seen or body in excluded:
            continue
        seen.add(body)
        excluded.update(_adjacent_swaps(body))
        excluded.update(_distant_swaps(body))
        ids.append(f"p:{body}")
    return tuple(ids)


def _near_misses(
    premise: str, salt: str, count: int, forbidden: set[str]
) -> tuple[str, ...] | None:
    """``count`` distinct transpositions of ``premise`` outside ``forbidden``, adjacent swaps
    first in a salted rotation (V4's rule for count=1), then non-adjacent swaps.  ``None``
    when the premise cannot supply enough."""

    body = _body(premise)
    ordered: list[str] = []
    for key, group in (("swap", _adjacent_swaps(body)), ("distant", _distant_swaps(body))):
        if group:
            start = _h(f"{salt}|{key}", len(group))
            ordered.extend(group[(start + offset) % len(group)] for offset in range(len(group)))
    chosen: list[str] = []
    for item in ordered:
        candidate = f"p:{item}"
        if candidate == premise or candidate in forbidden or candidate in chosen:
            continue
        chosen.append(candidate)
        if len(chosen) == count:
            return tuple(chosen)
    return tuple(chosen) if count == 0 else None


# ------------------------------------------------------------------------------ truth


def _proposed_answer(option: CanonicalAction) -> str:
    if len(option.arguments) != 1 or option.arguments[0].op != "symbol":
        raise ValueError(f"option {option.action_id} does not propose a single identifier")
    return str(option.arguments[0].value)


def held_premises(state: CanonicalState) -> frozenset[str]:
    return frozenset(
        str(item.args[0].value)
        for item in state.assumptions
        if item.op == "holds" and len(item.args) == 1
    )


def required_premises(state: CanonicalState) -> dict[str, frozenset[str]]:
    required: dict[str, set[str]] = defaultdict(set)
    for item in state.propositions:
        if item.op == "requires" and len(item.args) == 2:
            required[str(item.args[0].value)].add(str(item.args[1].value))
    return {owner: frozenset(premises) for owner, premises in required.items()}


def licensed_answers(state: CanonicalState) -> frozenset[str]:
    """Answers whose every required premise is held.  Written from the relation semantics,
    not from the construction; it never looks at a family."""

    held = held_premises(state)
    return frozenset(
        owner for owner, premises in required_premises(state).items() if premises <= held
    )


def independent_truth(state: CanonicalState, options: Sequence[CanonicalAction]) -> int:
    """Index of the unique licensed option.  Raises when zero or several are licensed."""

    proposed = [_proposed_answer(option) for option in options]
    licensed = licensed_answers(state)
    hits = [index for index, answer in enumerate(proposed) if answer in licensed]
    if len(licensed) != 1 or len(hits) != 1:
        raise ValueError(
            f"expected exactly one licensed option, found licensed={sorted(licensed)} "
            f"among proposed={proposed}"
        )
    return hits[0]


# ------------------------------------------------------------------------------ family


@dataclass(frozen=True, slots=True)
class PreconditionFamily:
    """One twin pair plus its negative control.  ``objects``, ``propositions``, ``goal`` and
    ``options`` are the same tuple objects in every state and item of the family."""

    family_id: str
    stratum: str
    pool: Pool
    params: LadderParams
    answer_a: str
    answer_b: str
    objects: tuple[MathObject, ...]
    propositions: tuple[CanonicalExpression, ...]
    goal: CanonicalExpression
    original: CanonicalState
    counterfactual: CanonicalState
    destroyed: CanonicalState
    options: tuple[CanonicalAction, CanonicalAction]
    missing_a: str
    missing_b: str
    near_misses_a: tuple[str, ...]
    near_misses_b: tuple[str, ...]
    #: Held transpositions of held premises, identical across the twins (see LadderParams).
    decoys: tuple[str, ...]
    decoy_sources: tuple[str, ...]
    family_index: int
    attempt: int
    premise_digits: int

    @property
    def level(self) -> int:
        return self.params.level

    @property
    def salt(self) -> str:
        return family_salt(self.stratum, self.pool, self.family_index)

    def _provenance(self, variant: Variant, twin: Variant, truth_kind: str) -> dict[str, Any]:
        return {
            "generator_version": ENVIRONMENT_VERSION,
            "mechanism": MECHANISM,
            "stratum": self.stratum,
            "stratum_role": STRATUM_ROLE.get(self.stratum, "custom"),
            "pool": self.pool.value,
            "family_index": self.family_index,
            "params": self.params.to_dict(),
            "premise_digits": self.premise_digits,
            "attempt": self.attempt,
            "variant": variant.value,
            "twin_of": f"{self.family_id}:{twin.value}",
            "truth_kind": truth_kind,
            "truth_rule": TRUTH_RULE,
            "source": "synthetic; deterministic salted SHA-256 generator; no model, no network",
        }

    def _item(
        self, variant: Variant, state: CanonicalState, correct_index: int, twin: Variant
    ) -> MaterialisedItem:
        truth_kind = "MATHEMATICAL" if variant in _POSITIVE else "NEGATIVE_CONTROL_TARGET"
        return MaterialisedItem(
            task_id=f"{self.family_id}:{variant.value}",
            family_id=self.family_id,
            level=self.level,
            variant=variant.value,
            question=QUESTION,
            canonical_state=state,
            options=self.options,
            correct_index=correct_index,
            provenance=self._provenance(variant, twin, truth_kind),
        )

    def items(self) -> tuple[MaterialisedItem, MaterialisedItem]:
        """ORIGINAL (correct_index 0) and COUNTERFACTUAL (correct_index 1)."""

        return (
            self._item(Variant.ORIGINAL, self.original, 0, Variant.COUNTERFACTUAL),
            self._item(Variant.COUNTERFACTUAL, self.counterfactual, 1, Variant.ORIGINAL),
        )

    def destroyed_item(self, expected_index: int) -> MaterialisedItem:
        """Negative control: the destroyed state licenses nothing; the two targets share one
        state and differ only in the index they are scored against."""

        if expected_index == 0:
            variant, twin = Variant.DESTROYED_ORIGINAL, Variant.DESTROYED_COUNTERFACTUAL
        elif expected_index == 1:
            variant, twin = Variant.DESTROYED_COUNTERFACTUAL, Variant.DESTROYED_ORIGINAL
        else:
            raise ValueError("expected_index must be 0 or 1")
        return self._item(variant, self.destroyed, expected_index, twin)

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "generator_version": ENVIRONMENT_VERSION,
            "stratum": self.stratum,
            "pool": self.pool.value,
            "params": self.params.to_dict(),
            "family_index": self.family_index,
            "attempt": self.attempt,
            "premise_digits": self.premise_digits,
            "answer_a": self.answer_a,
            "answer_b": self.answer_b,
            "missing_a": self.missing_a,
            "missing_b": self.missing_b,
            "near_misses_a": list(self.near_misses_a),
            "near_misses_b": list(self.near_misses_b),
            "decoys": list(self.decoys),
            "decoy_sources": list(self.decoy_sources),
            "original_hash": self.original.mathematical_hash,
            "counterfactual_hash": self.counterfactual.mathematical_hash,
            "destroyed_hash": self.destroyed.mathematical_hash,
            "options": [option.to_dict() for option in self.options],
        }


_POSITIVE = frozenset({Variant.ORIGINAL, Variant.COUNTERFACTUAL})


class _Unbuildable(Exception):
    """The salted draw cannot satisfy the near-miss constraints; redraw deterministically."""


def _construct(
    params: LadderParams,
    salt: str,
    *,
    family_id: str,
    stratum: str,
    pool: Pool,
    family_index: int,
    attempt: int,
) -> PreconditionFamily:
    count, missing_count, decoy_count = (
        params.premises,
        params.missing_near_misses,
        params.decoy_near_misses,
    )
    digits = premise_digits(params.premise_ids_needed)
    ids = _premise_ids(params.premise_ids_needed, digits, salt)
    a_premises, b_premises = ids[:count], ids[count : 2 * count]
    extras = ids[2 * count :]
    real = set(ids)
    neighbours = {premise: transposition_neighbours(premise) for premise in ids}
    answer_a, answer_b = f"answer:{_hex(f'{salt}|A')}", f"answer:{_hex(f'{salt}|B')}"
    if answer_a == answer_b:
        raise _Unbuildable("answer identifiers collide")

    planted: set[str] = set()

    def forbidden_for(source: str) -> set[str]:
        # Real ids, everything already planted, and every transposition of any *other* real
        # id: a planted near-miss must be confusable with exactly one real premise.
        out = set(real) | planted
        for premise, neighbourhood in neighbours.items():
            if premise != source:
                out |= neighbourhood
        return out

    def pick_missing(premises: tuple[str, ...], key: str) -> tuple[str, tuple[str, ...]]:
        start = _h(f"{salt}|{key}", count)
        for offset in range(count):
            premise = premises[(start + offset) % count]
            near = _near_misses(
                premise, f"{salt}|{key}|near", missing_count, forbidden_for(premise)
            )
            if near is not None:
                planted.update(near)
                return premise, near
        raise _Unbuildable(f"no premise of {key} admits {missing_count} near-misses")

    missing_b, near_b = pick_missing(b_premises, "missing_b")
    missing_a, near_a = pick_missing(a_premises, "missing_a")
    a_held = tuple(premise for premise in a_premises if premise != missing_a)
    b_held = tuple(premise for premise in b_premises if premise != missing_b)

    decoys: list[str] = []
    decoy_sources: list[str] = []
    for index in range(decoy_count):
        candidates = a_held if index % 2 == 0 else b_held
        start = _h(f"{salt}|decoy|{index}", len(candidates))
        for offset in range(len(candidates)):
            source = candidates[(start + offset) % len(candidates)]
            if source in decoy_sources:
                continue
            near = _near_misses(source, f"{salt}|decoy|{index}|near", 1, forbidden_for(source))
            if near is None:
                continue
            decoys.append(near[0])
            decoy_sources.append(source)
            planted.add(near[0])
            break
        else:
            raise _Unbuildable(f"no held premise admits decoy {index}")

    propositions = tuple(
        _shuffled(
            [
                *(_relation("requires", answer_a, premise) for premise in a_premises),
                *(_relation("requires", answer_b, premise) for premise in b_premises),
            ],
            f"{salt}|props",
        )
    )

    # One slot template for both twins: shared premises keep their positions, and the
    # licensed answer's would-be-missing premise plus the near-misses of the unlicensed
    # answer's missing premise are substituted in place.
    shared = (*extras, *a_held, *b_held, *decoys)
    slots: list[tuple[str, int]] = [("shared", index) for index in range(len(shared))]
    slots.append(("licensed", 0))
    slots.extend(("near", index) for index in range(missing_count))
    template = _shuffled(slots, f"{salt}|held")

    def fill(licensed_missing: str, near: tuple[str, ...]) -> tuple[CanonicalExpression, ...]:
        out: list[CanonicalExpression] = []
        for kind, index in template:
            if kind == "shared":
                out.append(_relation("holds", shared[index]))
            elif kind == "licensed":
                out.append(_relation("holds", licensed_missing))
            else:
                out.append(_relation("holds", near[index]))
        return tuple(out)

    destroyed_held = tuple(
        _relation("holds", premise)
        for premise in _shuffled([*shared, *near_a, *near_b], f"{salt}|held|destroyed")
    )

    objects = (
        *_identifier_objects((answer_a, answer_b)),
        *_distractors(_hex(salt), params.distractor_objects),
    )
    goal = _relation("fully_licensed_answer", "query")
    original = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=fill(missing_a, near_b)
    )
    counter = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=fill(missing_b, near_a)
    )
    destroyed = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=destroyed_held
    )
    if params.explicit:
        # Exactly fitness_v5._synthetic_family: the licensed answer is asserted outright; the
        # destroyed control asserts ``a`` as V5 does.
        def assert_answer(state: CanonicalState, answer: str) -> CanonicalState:
            return replace(
                state,
                established_facts=(*state.established_facts, _relation("the_answer_is", answer)),
            )

        original = assert_answer(original, answer_a)
        counter = assert_answer(counter, answer_b)
        destroyed = assert_answer(destroyed, answer_a)

    family = PreconditionFamily(
        family_id=family_id,
        stratum=stratum,
        pool=pool,
        params=params,
        answer_a=answer_a,
        answer_b=answer_b,
        objects=objects,
        propositions=propositions,
        goal=goal,
        original=original,
        counterfactual=counter,
        destroyed=destroyed,
        options=(_option(0, answer_a, answer_b), _option(1, answer_b, answer_a)),
        missing_a=missing_a,
        missing_b=missing_b,
        near_misses_a=near_a,
        near_misses_b=near_b,
        decoys=tuple(decoys),
        decoy_sources=tuple(decoy_sources),
        family_index=family_index,
        attempt=attempt,
        premise_digits=digits,
    )
    family_invariants(family)
    return family


def build_family(stratum: str, pool: Pool | str, family_index: int) -> PreconditionFamily:
    """Deterministic: the same (stratum, pool, index) always yields the identical family.
    A draw that cannot satisfy the near-miss constraints is redrawn under a nonce that is
    itself deterministic; the nonce is recorded as ``attempt``."""

    pool = Pool(pool)
    params = stratum_params(stratum)
    base = family_salt(stratum, pool, family_index)
    family_id = f"pl2:{pool.value.lower()}:{stratum}:{family_index:04d}"
    failures: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        salt = base if attempt == 0 else f"{base}|attempt|{attempt}"
        try:
            return _construct(
                params,
                salt,
                family_id=family_id,
                stratum=stratum,
                pool=pool,
                family_index=family_index,
                attempt=attempt,
            )
        except _Unbuildable as error:
            failures.append(str(error))
    raise ValueError(f"{family_id}: no buildable draw in {MAX_ATTEMPTS} attempts: {failures[-1]}")


def build_pool(
    stratum: str, pool: Pool | str, families: int, *, start: int = 0
) -> tuple[MaterialisedItem, ...]:
    """ORIGINAL then COUNTERFACTUAL for each family, in family-major order."""

    if families < 0 or start < 0:
        raise ValueError("families and start must be non-negative")
    return tuple(
        item
        for index in range(start, start + families)
        for item in build_family(stratum, pool, index).items()
    )


# --------------------------------------------------------------------------- invariants


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def family_invariants(family: PreconditionFamily) -> dict[str, Any]:
    """Every property the balance-by-construction claim rests on.  Raises ``ValueError`` on
    the first violation; returns the checked facts as a record otherwise."""

    params = family.params
    tag = family.family_id
    original, counter, destroyed = family.original, family.counterfactual, family.destroyed
    states = (original, counter, destroyed)

    # 1. shared structure is the same object, not merely equal
    for state in states:
        _check(state.objects is family.objects, f"{tag}: objects tuple is not shared")
        _check(state.propositions is family.propositions, f"{tag}: propositions not shared")
        _check(state.goal is family.goal, f"{tag}: goal not shared")
        _check(state.state_id == STATE_ID, f"{tag}: state_id is not the neutral constant")
        _check(not state.bindings and not state.obligations, f"{tag}: unexpected bindings")
        _check(not state.evidence_dependencies, f"{tag}: unexpected evidence")
        _check(
            not state.legal_actions and not state.plausible_invalid_actions,
            f"{tag}: state leaks action membership",
        )
    for item in (*family.items(), family.destroyed_item(0), family.destroyed_item(1)):
        _check(item.options is family.options, f"{tag}: item options tuple is not shared")
        _check(item.question == QUESTION, f"{tag}: question text drifted")
    _check(
        family.goal == _relation("fully_licensed_answer", "query"), f"{tag}: goal relation drifted"
    )

    # 2. options: symmetric, oracle-silent, canonical order (a, b)
    _check(len(family.options) == 2, f"{tag}: exactly two options required")
    _check(family.answer_a != family.answer_b, f"{tag}: answers collide")
    _check(
        _proposed_answer(family.options[0]) == family.answer_a
        and _proposed_answer(family.options[1]) == family.answer_b,
        f"{tag}: options are not in canonical (a, b) order",
    )
    for option in family.options:
        _check(option.expected_usefulness == 0.0, f"{tag}: option leaks oracle usefulness")
        _check(option.operation == "propose_structural_answer", f"{tag}: option operation drifted")

    # 3. objects: the two identifiers plus exactly the declared distractors
    object_ids = [item.object_id for item in family.objects]
    _check(len(set(object_ids)) == len(object_ids), f"{tag}: duplicate object ids")
    _check(
        object_ids[:2] == [f"object:id:{family.answer_a}", f"object:id:{family.answer_b}"],
        f"{tag}: identifier objects missing or misordered",
    )
    distractors = [item for item in family.objects if item.type_name == "Distractor"]
    _check(
        len(distractors) == params.distractor_objects
        and len(family.objects) == 2 + len(distractors),
        f"{tag}: distractor count differs from params",
    )

    # 4. requires: exactly `premises` per answer, only for a and b, all real ids
    required = required_premises(original)
    _check(set(required) == {family.answer_a, family.answer_b}, f"{tag}: requires owners drifted")
    _check(
        all(len(premises) == params.premises for premises in required.values()),
        f"{tag}: requires count differs from params.premises",
    )
    _check(len(family.propositions) == 2 * params.premises, f"{tag}: non-requires proposition")
    _check(
        all(item.op == "requires" for item in family.propositions), f"{tag}: foreign proposition"
    )
    a_required, b_required = required[family.answer_a], required[family.answer_b]
    _check(not (a_required & b_required), f"{tag}: a and b share a required premise")

    # 5. holds: sets, counts, and the exact twin difference
    for state in states:
        _check(
            all(item.op == "holds" and len(item.args) == 1 for item in state.assumptions),
            f"{tag}: assumption that is not holds(premise)",
        )
        _check(len(held_premises(state)) == len(state.assumptions), f"{tag}: duplicate holds")
    held_o, held_c, held_d = (held_premises(state) for state in states)
    _check(len(original.assumptions) == len(counter.assumptions), f"{tag}: hold counts differ")
    _check(
        len(original.assumptions) == params.held_per_twin,
        f"{tag}: hold count {len(original.assumptions)} != declared {params.held_per_twin}",
    )
    _check(len(destroyed.assumptions) == params.held_destroyed, f"{tag}: destroyed hold count")
    always_held = (held_o & held_c & held_d) - set(family.decoys)
    real = frozenset(a_required | b_required | always_held)
    extras = always_held - a_required - b_required
    _check(len(extras) == params.extras, f"{tag}: extras {len(extras)} != {params.extras}")
    pattern_digits = family.premise_digits
    for premise in (
        real | set(family.near_misses_a) | set(family.near_misses_b) | set(family.decoys)
    ):
        _check(
            bool(_PREMISE_PATTERN.match(premise)) and len(_body(premise)) == pattern_digits,
            f"{tag}: premise id {premise!r} is not p:{'d' * pattern_digits}",
        )
    _check(
        family.missing_a in a_required and family.missing_b in b_required,
        f"{tag}: missing premises are not required premises of their answers",
    )
    near_a, near_b = set(family.near_misses_a), set(family.near_misses_b)
    _check(
        len(near_a) == params.missing_near_misses == len(family.near_misses_a)
        and len(near_b) == params.missing_near_misses == len(family.near_misses_b),
        f"{tag}: near-miss counts differ from params",
    )
    expected_difference = {family.missing_a, family.missing_b} | near_a | near_b
    _check(
        held_o ^ held_c == expected_difference,
        f"{tag}: twin held sets differ by {sorted(held_o ^ held_c)}, "
        f"expected {sorted(expected_difference)}",
    )
    _check(
        family.missing_a in held_o and family.missing_b not in held_o and near_b <= held_o,
        f"{tag}: ORIGINAL assumptions are not (a licensed, b missing one, near-miss held)",
    )
    _check(
        family.missing_b in held_c and family.missing_a not in held_c and near_a <= held_c,
        f"{tag}: COUNTERFACTUAL assumptions are not the mirror of ORIGINAL",
    )
    differing_slots = 0
    for left, right in zip(original.assumptions, counter.assumptions, strict=True):
        if left == right:
            continue
        differing_slots += 1
        left_id, right_id = str(left.args[0].value), str(right.args[0].value)
        _check(
            (left_id == family.missing_a and right_id == family.missing_b)
            or (left_id in near_b and right_id in near_a),
            f"{tag}: twin slot substitution {left_id}->{right_id} is not licensed/near-miss",
        )
    _check(
        differing_slots == 1 + params.missing_near_misses,
        f"{tag}: twins differ at {differing_slots} slots, expected {1 + params.missing_near_misses}",
    )
    _check(
        held_d == (held_o & held_c) | near_a | near_b,
        f"{tag}: destroyed held set is not shared + both near-miss sets",
    )
    _check(
        family.missing_a not in held_d and family.missing_b not in held_d,
        f"{tag}: destroyed state holds a missing premise",
    )

    # 6. near-misses and decoys: transpositions of exactly one real premise, never real
    planted = [*family.near_misses_a, *family.near_misses_b, *family.decoys]
    _check(len(set(planted)) == len(planted), f"{tag}: planted near-miss ids repeat")
    _check(not (set(planted) & real), f"{tag}: a near-miss equals a real premise")
    for premise in real:
        _check(
            not (transposition_neighbours(premise) & real),
            f"{tag}: real premises {premise} and a neighbour are one transposition apart",
        )
    for near, source in (
        *((item, family.missing_a) for item in family.near_misses_a),
        *((item, family.missing_b) for item in family.near_misses_b),
        *zip(family.decoys, family.decoy_sources, strict=True),
    ):
        _check(
            near in transposition_neighbours(source),
            f"{tag}: {near} is not a transposition of its source {source}",
        )
        others = [
            other for other in real if other != source and near in transposition_neighbours(other)
        ]
        _check(not others, f"{tag}: {near} is also a transposition of {others}")
    _check(
        len(family.decoys) == params.decoy_near_misses
        and len(set(family.decoy_sources)) == len(family.decoy_sources),
        f"{tag}: decoy count or source distinctness violated",
    )
    _check(
        set(family.decoy_sources) <= (held_o & held_c) and set(family.decoys) <= (held_o & held_c),
        f"{tag}: decoys must derive from and be held in both twins",
    )

    # 7. truth, re-derived independently of the construction
    _check(independent_truth(original, family.options) == 0, f"{tag}: ORIGINAL truth is not 0")
    _check(independent_truth(counter, family.options) == 1, f"{tag}: COUNTERFACTUAL truth != 1")
    _check(not licensed_answers(destroyed), f"{tag}: destroyed state licenses an answer")
    items = family.items()
    _check(
        (items[0].correct_index, items[1].correct_index) == (0, 1)
        and items[0].variant == Variant.ORIGINAL.value
        and items[1].variant == Variant.COUNTERFACTUAL.value,
        f"{tag}: item variants or indices drifted",
    )

    # 8. explicit control: the_answer_is and nothing else
    for state, answer in (
        (original, family.answer_a),
        (counter, family.answer_b),
        (destroyed, family.answer_a),
    ):
        if params.explicit:
            _check(
                state.established_facts == (_relation("the_answer_is", answer),),
                f"{tag}: explicit stratum must assert exactly the_answer_is({answer})",
            )
        else:
            _check(not state.established_facts, f"{tag}: unexpected established fact")

    # 9. every state is a valid canonical record
    verifier = NativeVerifier()
    for state in states:
        result = verifier.verify_state(state)
        _check(result.accepted, f"{tag}: NativeVerifier rejected a state: {result.issues}")

    return {
        "family_id": family.family_id,
        "stratum": family.stratum,
        "pool": family.pool.value,
        "params": params.to_dict(),
        "shared_structure_identity": True,
        "requires": len(family.propositions),
        "holds_per_twin": len(original.assumptions),
        "holds_destroyed": len(destroyed.assumptions),
        "extras": len(extras),
        "twin_differing_slots": differing_slots,
        "held_symmetric_difference": sorted(held_o ^ held_c),
        "independent_truth_original": 0,
        "independent_truth_counterfactual": 1,
        "destroyed_licensed": [],
        "verifier_accepted": True,
        "explicit": params.explicit,
        "premise_digits": family.premise_digits,
        "original_hash": original.mathematical_hash,
        "counterfactual_hash": counter.mathematical_hash,
        "destroyed_hash": destroyed.mathematical_hash,
        "options_hash": stable_hash([option.to_dict() for option in family.options]),
    }


# ------------------------------------------------------------------------ surface lengths


def surface_length_summary(
    stratum: str, pool: Pool | str, families: int, surface_ids: Sequence[str]
) -> dict[str, Any]:
    """Rendered prompt length in characters per surface (min/mean/max over the ORIGINAL and
    COUNTERFACTUAL items of ``families`` families), through the tournament harness's own
    envelope with the shared constant guide.  Imports the harness lazily."""

    from arena.experiments.game_r_formal_v1 import SyntaxGuidePolicy, build_prompt, founder_genome

    pool = Pool(pool)
    items = build_pool(stratum, pool, families)
    surfaces: dict[str, Any] = {}
    for surface_id in surface_ids:
        genome = founder_genome(surface_id)
        by_variant: dict[str, list[int]] = defaultdict(list)
        for item in items:
            prompt = build_prompt(genome, item, guide_policy=SyntaxGuidePolicy.SHARED_CONSTANT)
            by_variant[item.variant].append(len(prompt))
        lengths = [length for values in by_variant.values() for length in values]
        surfaces[surface_id] = {
            "min": min(lengths),
            "mean": sum(lengths) / len(lengths),
            "max": max(lengths),
            "by_variant": {
                variant: {
                    "min": min(values),
                    "mean": sum(values) / len(values),
                    "max": max(values),
                }
                for variant, values in sorted(by_variant.items())
            },
        }
    return {
        "generator_version": ENVIRONMENT_VERSION,
        "stratum": stratum,
        "pool": pool.value,
        "params": stratum_params(stratum).to_dict(),
        "families": families,
        "items": len(items),
        "guide_policy": "SHARED_CONSTANT",
        "unit": "characters",
        "surfaces": surfaces,
    }


def ladder_summary(pool: Pool | str = Pool.DEV, families: int = 1) -> dict[str, dict[str, Any]]:
    """Declared and measured counts per stratum, for reports."""

    if families < 1:
        raise ValueError("families must be at least 1")
    out: dict[str, dict[str, Any]] = {}
    for stratum, params in LADDER.items():
        records = [
            family_invariants(build_family(stratum, pool, index)) for index in range(families)
        ]
        record = records[0]
        if any(
            (item["requires"], item["holds_per_twin"], item["holds_destroyed"])
            != (record["requires"], record["holds_per_twin"], record["holds_destroyed"])
            for item in records
        ):
            raise ValueError(f"{stratum}: counts vary across families")
        out[stratum] = {
            "role": STRATUM_ROLE.get(stratum, "custom"),
            "level": params.level,
            "params": params.to_dict(),
            "requires": record["requires"],
            "holds_per_twin": record["holds_per_twin"],
            "holds_destroyed": record["holds_destroyed"],
            "families_checked": families,
        }
    return out


__all__ = [
    "BASE_PREMISE_DIGITS",
    "ENVIRONMENT_VERSION",
    "LADDER",
    "MAX_ATTEMPTS",
    "MECHANISM",
    "PRIMARY_LADDER",
    "QUESTION",
    "STATE_ID",
    "STRATUM_ROLE",
    "TRUTH_RULE",
    "LadderParams",
    "Pool",
    "PreconditionFamily",
    "Variant",
    "build_family",
    "build_pool",
    "family_invariants",
    "family_salt",
    "held_premises",
    "independent_truth",
    "ladder_summary",
    "licensed_answers",
    "premise_digits",
    "required_premises",
    "stratum_params",
    "surface_length_summary",
    "transposition_neighbours",
]
