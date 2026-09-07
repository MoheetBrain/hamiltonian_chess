"""Verifier-backed scoring for NEXT_ACTION predictions, with the three metrics kept apart.

WHY THIS MODULE EXISTS
----------------------
``gpu_matched_runner.score_prediction`` emits a field called ``verified`` that is nothing
of the sort: it is ``parsed is a dict and contains action_id/operation/arguments``.  It is
self-documented there as *not* a correctness claim, but the name survives into
``artifacts/experiments/tier2_sprint/gpu_sprint_results.json``, where it reads 1.000 for
every arm in every stage.  A constant carries no information, and a reader who takes it for
verifier-backed accuracy is misled.  The real verifier, ``arena.verifier.native
.NativeVerifier``, is not imported anywhere under ``arena/training/``.

This module keeps three metrics separate and never conflates them:

``schema_valid``
    The completion parses and carries the required keys.  This is exactly what the old
    ``verified`` measured, named honestly.  Parsing tolerance is a deliberate reproduction
    of ``gpu_matched_runner.canonical_json`` so historical numbers stay comparable.

``exact``
    Structural equality with the gold target action, computed as ``parsed == target`` on
    decoded JSON -- bit-for-bit the same predicate as ``gpu_matched_runner``'s ``exact``.

``verified``
    The prediction is decoded back into a :class:`CanonicalAction` and adjudicated by a
    :class:`~arena.verifier.base.Verifier`.  This is the only metric that consults the
    verifier at all.

WHAT ``NativeVerifier`` ACTUALLY ESTABLISHES HERE -- READ BEFORE QUOTING A NUMBER
--------------------------------------------------------------------------------
``NextActionVerification`` is assembled from two verifier calls:

1.  ``verify_state`` on a probe state that carries the decoded action in
    ``plausible_invalid_actions``.  This makes the verifier check the *action's own*
    expressions -- operator arity, sort confusion, unbound variables, definedness
    obligations for partial operators -- and that ``target_ids`` name objects that exist
    (``UNKNOWN_ACTION_TARGET``).  It grants the action no legality.
2.  ``verify_transition`` on ``CanonicalTransition(state, decoded, state)``.  Its only
    non-vacuous check for us is ``ILLEGAL_TRANSITION_ACTION``: is the predicted
    ``action_id`` a member of ``state.legal_actions``?

The identity successor (``state_after is state_before``) is forced on us: a *predicted*
action has no successor state, and substituting the gold successor would presuppose the
prediction produced it.  The consequence is that ``OBLIGATION_LAUNDERING`` and
``GOAL_LAUNDERING`` are vacuous here and ``NO_STATE_CHANGE`` fires as a WARNING on every
item; it is a warning, so it does not affect ``accepted``.

So ``NativeVerifier`` establishes that the predicted action is **structurally well formed
and legally available in the state**.  It does NOT establish that the action is *correct*,
*useful*, or *optimal*, and it does not evaluate the action's effect -- nothing in
``arena/verifier/`` executes an action.  "Verified accuracy" must never be read as
"solved the problem".

THE TRIVIALLY-VALID-ACTION ATTACK (MEASURED, NOT HYPOTHETICAL)
--------------------------------------------------------------
``verify_transition`` compares ``action_id`` strings and nothing else.  A prediction of
``{"action_id": <any legal id>, "operation": "", "target_ids": [], "arguments": []}`` is
therefore accepted by ``NativeVerifier`` while containing no mathematics whatsoever.  On
Arena World v0 this was confirmed on 676/676 tasks.

It is worse than that on this world.  The gold ``action_id`` is a pure string rewrite of
the ``state_id`` that ``project_state_for_observation(..., NEXT_ACTION)`` leaves *in the
prompt*: ``state:arithmetic:0000:0000:initial`` -> ``action:arithmetic:0000:0000:valid``.
That rewrite recovers the correct id on 676/676 Arena World v0 tasks.  A model that learns
``state:``->``action:``, ``:initial``->``:valid`` and emits an otherwise empty action would
score ``verified == 1.000`` with zero mathematical competence.

Two mitigations, both of which a reader must know about:

*   ``require_content_match`` (default ``True``, fail closed) additionally requires the
    decoded action to be *mathematically identical* to the legal action bearing that id --
    identical on every field except ``expected_usefulness``, which
    ``arena.compiler.projection.scrub_action_labels`` defines as evaluation-only metadata
    rather than mathematical content.  This kills the hollow-action attack.  It is NOT a
    verifier judgement; it is a guard bolted on because ``NativeVerifier`` alone cannot
    tell a correct action from a hollow one wearing a legal id.  ``test_verified_eval.py``
    demonstrates the attack succeeding with the guard turned off.
*   The id leak is a *dataset* defect, not something this module can repair.  It is
    reported here so that no one presents ``verified`` from Arena World v0 as evidence of
    reasoning without addressing it.

A FURTHER LIMIT SPECIFIC TO ARENA WORLD v0
------------------------------------------
Every state in the 676-task world offers exactly **one** legal action, which is always the
gold target.  ``verified-but-not-exact`` -- the entire scientific reason to prefer a
verifier over exact match, since it counts predictions that are valid but different from
the reference -- is therefore **structurally impossible on this world**, except through
``expected_usefulness`` (an oracle label the model cannot see and which is excluded from
the content comparison).  The class is reported separately regardless, because it becomes
informative the moment a world offers branching states, and because a non-zero count on
Arena World v0 would itself be a finding about the generator.

FAIL-CLOSED POLICY
------------------
*   A prediction that cannot be parsed, decoded, or adjudicated is NOT verified.  No
    exception path returns a pass; every ``except`` sets ``verified=False`` and records a
    failure class and a message.
*   If the reference state cannot be adjudicated -- it fails ``verify_state`` itself, or it
    carries no ``legal_actions`` (which is what a NEXT_ACTION *observation* looks like
    after projection strips the answer key) -- the item is marked
    :attr:`FailureClass.UNADJUDICATED` and ``adjudicated=False``.
*   No specification yet says how unadjudicated items should be treated.  Until one does,
    **they count as NOT verified and remain in the denominator**.  The counts are exposed
    (:attr:`VerifiedEvalReport.unadjudicated`) and the alternative estimate is available
    as :attr:`VerifiedEvalReport.verified_rate_excluding_unadjudicated`, so a future spec
    can choose the other convention without rerunning anything.  A silent choice here would
    be the same class of mistake this module exists to undo.

The per-item vectors are ``tuple[float, ...]`` of 0.0/1.0, directly consumable by
``arena.training.evaluation.paired_bootstrap_difference`` and ``wilson_interval``.  Scoring
is deterministic: no RNG, no ordering dependence, no I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalState,
    CanonicalTransition,
    canonical_json,
)
from arena.verifier.base import Severity, VerificationResult, Verifier
from arena.verifier.native import NativeVerifier

#: The keys ``gpu_matched_runner.score_prediction`` requires for its (misnamed) ``verified``
#: field.  Reproduced so ``schema_valid`` here is the same predicate as the historical one.
REQUIRED_ACTION_KEYS: tuple[str, ...] = ("action_id", "operation", "arguments")

#: Fields of a ``CanonicalAction`` that are evaluation metadata rather than mathematical
#: content.  ``arena.compiler.projection.scrub_action_labels`` zeroes exactly this field
#: when projecting an observation, on the stated grounds that doing so does not change the
#: mathematical action content.  The content comparison honours that definition.
ORACLE_ONLY_ACTION_FIELDS: frozenset[str] = frozenset({"expected_usefulness"})


class ActionDecodeError(ValueError):
    """A model completion could not be turned back into a ``CanonicalAction``."""


class FailureClass(StrEnum):
    """Exactly one class per scored item.  The first four are decided without the verifier."""

    #: Completion is not JSON, or the JSON is not an object.
    UNPARSEABLE = "UNPARSEABLE"
    #: A JSON object, but missing one of :data:`REQUIRED_ACTION_KEYS`.
    MISSING_KEYS = "MISSING_KEYS"
    #: Required keys present, but ``CanonicalAction.from_dict`` rejected the payload.
    UNDECODABLE = "UNDECODABLE"
    #: The verifier cannot adjudicate this item -- the reference state is itself rejected,
    #: or it carries no ``legal_actions`` to adjudicate against.  Counted as NOT verified.
    UNADJUDICATED = "UNADJUDICATED"
    #: ``operation`` is outside the vocabulary the state (or the caller) admits.
    UNKNOWN_OPERATION = "UNKNOWN_OPERATION"
    #: ``verify_state`` rejected the action's own expressions or targets.
    BAD_ARGUMENTS = "BAD_ARGUMENTS"
    #: ``verify_transition`` rejected the action -- in practice, an illegal ``action_id``.
    VERIFIER_REJECTED = "VERIFIER_REJECTED"
    #: Legal, well-formed id, but the action's mathematical content differs from the legal
    #: action bearing that id.  This is where the hollow-action attack lands.
    CONTENT_MISMATCH = "CONTENT_MISMATCH"
    #: The verifier raised.  Never a pass; recorded so it can never be mistaken for one.
    VERIFIER_ERROR = "VERIFIER_ERROR"
    #: Verified, and different from the gold target.  The reason a verifier beats exact
    #: match -- and structurally impossible on Arena World v0 (see the module docstring).
    VERIFIED_NOT_EXACT = "VERIFIED_NOT_EXACT"
    #: Verified and identical to the gold target.
    EXACT = "EXACT"


#: Classes in which ``verified`` is True.  Everything else is a failure of some kind.
PASSING_CLASSES: frozenset[FailureClass] = frozenset(
    {FailureClass.EXACT, FailureClass.VERIFIED_NOT_EXACT}
)


def parse_completion(text: str | None) -> Any:
    """Parse a model completion into a comparable object, or ``None``.

    A deliberate reproduction of ``arena.training.gpu_matched_runner.canonical_json``.  It
    is copied rather than imported so this CPU-only module never depends on a GPU script;
    ``tests/training/test_verified_eval.py`` asserts the two agree on a battery of inputs,
    which is what actually keeps the historical numbers comparable.
    """

    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.split("\n", 1)[-1] if text[:4].isalpha() else text
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


def has_required_keys(parsed: Any) -> bool:
    """``schema_valid``: the predicate the historical ``verified`` field really computed."""

    return isinstance(parsed, dict) and all(key in parsed for key in REQUIRED_ACTION_KEYS)


def decode_action(parsed: Any) -> CanonicalAction:
    """Invert ``render_dataset.render_next_action_example``'s target encoding.

    That function writes ``json.dumps(transition.action.to_dict(), sort_keys=True,
    separators=(",", ":"))``, so the inverse of the dict half is ``CanonicalAction
    .from_dict``.  ``from_dict`` tolerates absent optional fields, which is the tolerance a
    model completion needs; every other malformation raises :class:`ActionDecodeError`.
    """

    if not isinstance(parsed, dict):
        raise ActionDecodeError("prediction is not a JSON object")
    missing = [key for key in REQUIRED_ACTION_KEYS if key not in parsed]
    if missing:
        raise ActionDecodeError(f"missing required keys {missing}")
    try:
        return CanonicalAction.from_dict(parsed)
    except Exception as error:  # fail closed: any malformation is a decode failure
        raise ActionDecodeError(f"{type(error).__name__}: {error}") from error


def action_content_key(action: CanonicalAction) -> str:
    """Canonical JSON of an action's *mathematical* content, oracle-only fields removed."""

    payload = action.to_dict()
    for field in ORACLE_ONLY_ACTION_FIELDS:
        payload.pop(field, None)
    return canonical_json(payload)


def _critical_codes(*results: VerificationResult) -> tuple[str, ...]:
    return tuple(
        issue.code
        for result in results
        for issue in result.issues
        if issue.severity == Severity.CRITICAL
    )


def state_is_adjudicable(state: CanonicalState, verifier: Verifier) -> tuple[bool, str]:
    """Can the verifier say anything about a prediction against this state?

    Two ways it cannot.  The state fails ``verify_state`` on its own, so every rejection
    would be the harness's fault rather than the model's.  Or the state carries no
    ``legal_actions`` -- which is precisely what a NEXT_ACTION *observation* looks like
    after ``project_state_for_observation`` strips the answer key.  Passing an observation
    where the oracle state belongs would otherwise make ``verified`` read 0.000 for every
    arm, a mirror image of the constant-1.000 bug this module replaces.
    """

    if not state.legal_actions:
        return False, "reference state carries no legal_actions to adjudicate against"
    result = verifier.verify_state(state)
    if not result.accepted:
        codes = ", ".join(sorted(set(_critical_codes(result)))) or "unknown"
        return False, f"reference state is itself rejected by the verifier ({codes})"
    return True, ""


@dataclass(frozen=True)
class EvalItem:
    """One (prediction, target, state) triple.

    ``state`` must be the *oracle* ``transition.state_before`` -- the state with its
    ``legal_actions`` intact, not the projected observation the model was shown.
    """

    prediction: str
    target_text: str
    state: CanonicalState
    item_id: str = ""


@dataclass(frozen=True)
class ItemScore:
    """Three independent metrics plus the single reason class for this item."""

    item_id: str
    schema_valid: bool
    exact: bool
    verified: bool
    adjudicated: bool
    failure_class: FailureClass
    detail: str = ""
    issue_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "schema_valid": int(self.schema_valid),
            "exact": int(self.exact),
            "verified": int(self.verified),
            "adjudicated": int(self.adjudicated),
            "failure_class": self.failure_class.value,
            "detail": self.detail,
            "issue_codes": list(self.issue_codes),
        }


def score_item(
    item: EvalItem,
    *,
    verifier: Verifier | None = None,
    require_content_match: bool = True,
    known_operations: Iterable[str] | None = None,
) -> ItemScore:
    """Score one prediction.  Deterministic, offline, and fail-closed at every branch.

    ``require_content_match=False`` reduces ``verified`` to what ``NativeVerifier`` alone
    can say, which is gameable by a hollow action carrying a legal ``action_id``.  It exists
    so that gap can be measured and tested, not because it is a defensible setting.
    """

    engine: Verifier = NativeVerifier() if verifier is None else verifier
    parsed = parse_completion(item.prediction)
    schema_valid = has_required_keys(parsed)

    # The target is ours, not the model's.  A malformed one is a harness bug and must be
    # loud rather than silently scored as a miss.
    target = json.loads(item.target_text)
    exact = parsed is not None and parsed == target

    def score(
        verified: bool,
        adjudicated: bool,
        failure_class: FailureClass,
        detail: str = "",
        issue_codes: tuple[str, ...] = (),
    ) -> ItemScore:
        return ItemScore(
            item_id=item.item_id,
            schema_valid=schema_valid,
            exact=exact,
            verified=verified,
            adjudicated=adjudicated,
            failure_class=failure_class,
            detail=detail,
            issue_codes=issue_codes,
        )

    try:
        adjudicable, reason = state_is_adjudicable(item.state, engine)
    except Exception as error:  # fail closed
        return score(False, False, FailureClass.VERIFIER_ERROR, f"{type(error).__name__}: {error}")

    if parsed is None:
        return score(
            False, adjudicable, FailureClass.UNPARSEABLE, "completion is not a JSON object"
        )
    if not schema_valid:
        absent = [
            key for key in REQUIRED_ACTION_KEYS if not isinstance(parsed, dict) or key not in parsed
        ]
        return score(False, adjudicable, FailureClass.MISSING_KEYS, f"missing {absent}")
    try:
        decoded = decode_action(parsed)
    except ActionDecodeError as error:
        return score(False, adjudicable, FailureClass.UNDECODABLE, str(error))

    if not adjudicable:
        return score(False, False, FailureClass.UNADJUDICATED, reason)

    vocabulary = (
        set(known_operations)
        if known_operations is not None
        else {
            action.operation
            for action in (*item.state.legal_actions, *item.state.plausible_invalid_actions)
        }
    )
    if decoded.operation not in vocabulary:
        return score(
            False,
            True,
            FailureClass.UNKNOWN_OPERATION,
            f"operation {decoded.operation!r} is outside {sorted(vocabulary)}",
        )

    try:
        # The decoded action rides in `plausible_invalid_actions` so `verify_state` checks
        # its expressions and targets without granting it any legality.
        probe = replace(item.state, legal_actions=(), plausible_invalid_actions=(decoded,))
        structural = engine.verify_state(probe)
        transition = CanonicalTransition(
            transition_id=f"transition:predicted:{item.item_id or 'unnamed'}",
            state_before=item.state,
            action=decoded,
            state_after=item.state,
            verification=(),
        )
        legality = engine.verify_transition(transition)
    except Exception as error:  # fail closed
        return score(False, True, FailureClass.VERIFIER_ERROR, f"{type(error).__name__}: {error}")

    codes = _critical_codes(structural, legality)
    if not structural.accepted:
        return score(
            False, True, FailureClass.BAD_ARGUMENTS, "verify_state rejected the action", codes
        )
    if not legality.accepted:
        return score(
            False,
            True,
            FailureClass.VERIFIER_REJECTED,
            "verify_transition rejected the action",
            codes,
        )

    if require_content_match:
        legal = {action.action_id: action for action in item.state.legal_actions}
        reference = legal.get(decoded.action_id)
        if reference is None or action_content_key(reference) != action_content_key(decoded):
            return score(
                False,
                True,
                FailureClass.CONTENT_MISMATCH,
                "action_id is legal but its mathematical content differs from that legal action",
                codes,
            )

    return score(
        True, True, FailureClass.EXACT if exact else FailureClass.VERIFIED_NOT_EXACT, "", codes
    )


@dataclass(frozen=True)
class VerifiedEvalReport:
    """Per-item vectors, the failure taxonomy, and the numbers that may be quoted."""

    scores: tuple[ItemScore, ...]
    verifier: str
    verifier_version: str
    require_content_match: bool

    @property
    def n(self) -> int:
        return len(self.scores)

    @property
    def schema_valid_vector(self) -> tuple[float, ...]:
        return tuple(float(score.schema_valid) for score in self.scores)

    @property
    def exact_vector(self) -> tuple[float, ...]:
        return tuple(float(score.exact) for score in self.scores)

    @property
    def verified_vector(self) -> tuple[float, ...]:
        """Unadjudicated items are 0.0 here and stay in the denominator.  See the docstring."""

        return tuple(float(score.verified) for score in self.scores)

    @property
    def adjudicated_vector(self) -> tuple[float, ...]:
        return tuple(float(score.adjudicated) for score in self.scores)

    @property
    def failure_counts(self) -> dict[str, int]:
        """Every class, including the zeroes -- an absent key is easy to misread as absent evidence."""

        counts = dict.fromkeys((item.value for item in FailureClass), 0)
        for score in self.scores:
            counts[score.failure_class.value] += 1
        return counts

    @property
    def unadjudicated(self) -> int:
        return sum(not score.adjudicated for score in self.scores)

    @property
    def verified_not_exact(self) -> int:
        """Valid but different from the reference: the whole point of having a verifier."""

        return sum(score.verified and not score.exact for score in self.scores)

    @property
    def exact_not_verified(self) -> int:
        """Should be 0.  Anything else means the verifier disagrees with the gold label."""

        return sum(score.exact and not score.verified for score in self.scores)

    def _rate(self, vector: tuple[float, ...]) -> float:
        return sum(vector) / len(vector) if vector else 0.0

    @property
    def schema_valid_rate(self) -> float:
        return self._rate(self.schema_valid_vector)

    @property
    def exact_rate(self) -> float:
        return self._rate(self.exact_vector)

    @property
    def verified_rate(self) -> float:
        """The primary endpoint under the current fail-closed convention."""

        return self._rate(self.verified_vector)

    @property
    def verified_rate_excluding_unadjudicated(self) -> float | None:
        """The alternative a future spec may adopt.  ``None`` when nothing is adjudicable."""

        adjudicated = tuple(float(s.verified) for s in self.scores if s.adjudicated)
        return self._rate(adjudicated) if adjudicated else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier": self.verifier,
            "verifier_version": self.verifier_version,
            "require_content_match": self.require_content_match,
            "n": self.n,
            "schema_valid_rate": self.schema_valid_rate,
            "exact_rate": self.exact_rate,
            "verified_rate": self.verified_rate,
            "verified_rate_excluding_unadjudicated": self.verified_rate_excluding_unadjudicated,
            "unadjudicated": self.unadjudicated,
            "verified_not_exact": self.verified_not_exact,
            "exact_not_verified": self.exact_not_verified,
            "failure_counts": self.failure_counts,
            "unadjudicated_policy": (
                "counted as NOT verified and retained in the denominator; no specification "
                "yet chooses otherwise"
            ),
            "items": [score.to_dict() for score in self.scores],
        }


def evaluate_predictions(
    items: Sequence[EvalItem],
    *,
    verifier: Verifier | None = None,
    require_content_match: bool = True,
    known_operations: Iterable[str] | None = None,
) -> VerifiedEvalReport:
    """Score a batch and return per-item vectors plus the failure taxonomy."""

    engine: Verifier = NativeVerifier() if verifier is None else verifier
    vocabulary = None if known_operations is None else tuple(known_operations)
    scores = tuple(
        score_item(
            item,
            verifier=engine,
            require_content_match=require_content_match,
            known_operations=vocabulary,
        )
        for item in items
    )
    return VerifiedEvalReport(
        scores=scores,
        verifier=engine.name,
        verifier_version=engine.version,
        require_content_match=require_content_match,
    )
