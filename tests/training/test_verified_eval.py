"""The three metrics must genuinely come apart, and no failure may become a pass.

Fixtures are built from real ``generate_tasks`` output rather than hand-written stubs, so
the canonical objects, the target encoding and the verifier all behave as they do in the
experiment.  CPU-only, offline, no model of any kind.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    CanonicalTransition,
)
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.gpu_matched_runner import canonical_json as legacy_canonical_json
from arena.training.gpu_matched_runner import score_prediction as legacy_score_prediction
from arena.training.render_dataset import render_next_action_example
from arena.training.verified_eval import (
    ActionDecodeError,
    EvalItem,
    FailureClass,
    VerifiedEvalReport,
    action_content_key,
    decode_action,
    evaluate_predictions,
    parse_completion,
    score_item,
)
from arena.verifier.base import Severity, VerificationIssue, VerificationResult
from arena.verifier.native import NativeVerifier

TASKS = generate_tasks(total=13, seed=0)


class _Renderer:
    """The minimum ``StateRenderer`` needed to exercise the real target encoding."""

    candidate_id = "test-renderer"

    def render(self, state: CanonicalState) -> str:
        return json.dumps(state.to_dict(), sort_keys=True)


def gold(index: int = 0) -> tuple[CanonicalState, CanonicalAction, str]:
    """Return (oracle state_before, gold action, gold target_text) for a real task."""

    transition = TASKS[index].trajectory.transitions[0]
    example = render_next_action_example(TASKS[index].trajectory, _Renderer())
    return transition.state_before, transition.action, example.target_text


def item(prediction: str, index: int = 0, **overrides: object) -> EvalItem:
    state, _, target_text = gold(index)
    return EvalItem(
        prediction=prediction,
        target_text=target_text,
        state=overrides.get("state", state),  # type: ignore[arg-type]
        item_id=f"item:{index}",
    )


# --------------------------------------------------------------------------------------
# The target encoding really is what we invert.
# --------------------------------------------------------------------------------------


def test_decoder_is_the_inverse_of_the_rendered_target() -> None:
    for index in range(len(TASKS)):
        _, action, target_text = gold(index)
        assert decode_action(json.loads(target_text)) == action


def test_gold_prediction_scores_all_three_metrics_true() -> None:
    for index in range(len(TASKS)):
        _, _, target_text = gold(index)
        score = score_item(item(target_text, index))
        assert (score.schema_valid, score.exact, score.verified) == (True, True, True)
        assert score.failure_class is FailureClass.EXACT
        assert score.adjudicated


# --------------------------------------------------------------------------------------
# Parsing tolerance stays comparable with the historical runner.
# --------------------------------------------------------------------------------------


COMPLETIONS = (
    "",
    "   ",
    "not json at all",
    "{}",
    '{"action_id": "a"}',
    '{"action_id": "a", "operation": "evaluate", "arguments": []}',
    'prose before {"action_id": "a", "operation": "op", "arguments": []} and after',
    '```json\n{"action_id": "a", "operation": "op", "arguments": []}\n```',
    '```\n{"action_id": "a", "operation": "op", "arguments": []}\n```',
    "{ broken",
    "[1, 2, 3]",
    '{"action_id": "a", "operation": "op", "arguments": [], "extra": 1}',
)


@pytest.mark.parametrize("completion", COMPLETIONS)
def test_parse_completion_matches_the_historical_runner(completion: str) -> None:
    assert parse_completion(completion) == legacy_canonical_json(completion)


@pytest.mark.parametrize("completion", COMPLETIONS)
def test_schema_valid_and_exact_match_the_historical_runner(completion: str) -> None:
    _, _, target_text = gold()
    legacy = legacy_score_prediction(completion, target_text)
    score = score_item(item(completion))
    # The historical `verified` field is exactly our `schema_valid`, renamed honestly.
    assert score.schema_valid is bool(legacy["verified"])
    assert score.exact is bool(legacy["exact"])


def test_historical_verified_field_is_a_constant_on_well_formed_output() -> None:
    """The bug this module replaces: the old `verified` cannot distinguish right from wrong."""

    _, _, target_text = gold()
    hollow = json.dumps({"action_id": "action:anything", "operation": "", "arguments": []})
    assert legacy_score_prediction(target_text, target_text)["verified"] == 1
    assert legacy_score_prediction(hollow, target_text)["verified"] == 1


# --------------------------------------------------------------------------------------
# The three metrics come apart.
# --------------------------------------------------------------------------------------


def test_valid_but_not_exact_scores_verified_true_exact_false() -> None:
    """A prediction differing only in the oracle-only usefulness label is still valid."""

    state, action, target_text = gold()
    relabelled = replace(action, expected_usefulness=0.0)
    assert relabelled != action
    score = score_item(
        EvalItem(json.dumps(relabelled.to_dict()), target_text, state, item_id="relabelled")
    )
    assert score.verified is True
    assert score.exact is False
    assert score.schema_valid is True
    assert score.failure_class is FailureClass.VERIFIED_NOT_EXACT


def test_exact_and_verified_differ_from_schema_valid() -> None:
    """A well-formed but wrong action: schema_valid True, exact False, verified False."""

    state, _, target_text = gold()
    wrong = json.dumps(
        {"action_id": "action:not-a-real-id", "operation": "evaluate", "arguments": []}
    )
    score = score_item(EvalItem(wrong, target_text, state, item_id="wrong"))
    assert score.schema_valid is True
    assert score.exact is False
    assert score.verified is False


# --------------------------------------------------------------------------------------
# The trivially-valid-action attack, demonstrated rather than asserted away.
# --------------------------------------------------------------------------------------


#: Domain segment of ``state_id`` -> operation.  A perfect 1:1 map over all 676 Arena World
#: v0 tasks, so it is learnable from training data and needs no mathematics at inference.
DOMAIN_OPERATION = {
    task.trajectory.transitions[0].state_before.state_id.split(":")[1]: (
        task.trajectory.transitions[0].action.operation
    )
    for task in generate_tasks(total=676, seed=0)
}


def hollow_prediction(state: CanonicalState) -> str:
    """The attack, in its strongest form: everything recoverable from the prompt, no maths.

    ``action_id`` is a string rewrite of ``state_id``; ``operation`` is a lookup on the
    domain segment of the same ``state_id``.  The mathematical payload -- ``target_ids``
    and ``arguments``, the only parts that encode what to actually do -- is empty.
    """

    derived = state.state_id.replace("state:", "action:", 1)
    assert derived.endswith(":initial")
    derived = derived[: -len(":initial")] + ":valid"
    return json.dumps(
        {
            "action_id": derived,
            "operation": DOMAIN_OPERATION[state.state_id.split(":")[1]],
            "target_ids": [],
            "arguments": [],
        }
    )


def test_the_answer_identity_is_recoverable_from_the_observation_the_model_is_shown() -> None:
    """The dataset leak: id and operation are string functions of a field left in the prompt."""

    for index in range(len(TASKS)):
        state, action, _ = gold(index)
        observation = project_state_for_observation(state, ObservationKind.NEXT_ACTION)
        assert observation.legal_actions == ()  # the answer key is stripped ...
        assert observation.state_id == state.state_id  # ... but its derivation source is not
        attack = json.loads(hollow_prediction(state))
        assert attack["action_id"] == action.action_id
        assert attack["operation"] == action.operation


def test_native_verifier_alone_accepts_a_hollow_action_with_a_legal_id() -> None:
    """Without the content guard, `verified` is gameable with zero mathematics."""

    for index in range(len(TASKS)):
        state, _, target_text = gold(index)
        attack = EvalItem(hollow_prediction(state), target_text, state, item_id=f"attack:{index}")
        ungarded = score_item(attack, require_content_match=False)
        assert ungarded.verified is True, "NativeVerifier compares action_id and nothing else"
        assert ungarded.exact is False
        guarded = score_item(attack)
        assert guarded.verified is False
        assert guarded.failure_class is FailureClass.CONTENT_MISMATCH


def test_verify_transition_only_consults_the_action_id() -> None:
    """The mechanism behind the attack, asserted directly against the verifier."""

    state, action, _ = gold()
    hollow = CanonicalAction(action_id=action.action_id, operation="", target_ids=(), arguments=())
    result = NativeVerifier().verify_transition(
        CanonicalTransition("transition:probe", state, hollow, state, ())
    )
    assert result.accepted is True


def test_arena_world_v0_offers_exactly_one_legal_action_per_state() -> None:
    """Why verified-but-not-exact cannot be informative on this world."""

    assert {len(task.trajectory.transitions[0].state_before.legal_actions) for task in TASKS} == {1}


# --------------------------------------------------------------------------------------
# Failure taxonomy.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prediction", "expected"),
    [
        ("", FailureClass.UNPARSEABLE),
        ("the next action is to evaluate", FailureClass.UNPARSEABLE),
        ("{ not valid json", FailureClass.UNPARSEABLE),
        ("{}", FailureClass.MISSING_KEYS),
        ('{"action_id": "a", "operation": "evaluate"}', FailureClass.MISSING_KEYS),
        (
            '{"action_id": 1, "operation": "e", "arguments": [{"nope": 1}]}',
            FailureClass.UNDECODABLE,
        ),
        ('{"action_id": "a", "operation": "e", "arguments": [1]}', FailureClass.UNDECODABLE),
    ],
)
def test_malformed_output_lands_in_the_right_failure_class(
    prediction: str, expected: FailureClass
) -> None:
    score = score_item(item(prediction))
    assert score.failure_class is expected
    assert score.verified is False
    assert score.exact is False


def test_unknown_operation_is_classified_separately() -> None:
    state, action, target_text = gold()
    payload = action.to_dict() | {"operation": "summon_the_answer"}
    score = score_item(EvalItem(json.dumps(payload), target_text, state, item_id="unknown-op"))
    assert score.failure_class is FailureClass.UNKNOWN_OPERATION
    assert score.verified is False


def test_bad_arguments_are_caught_by_verify_state_not_by_us() -> None:
    """An action naming an object that does not exist is rejected structurally."""

    state, action, target_text = gold()
    payload = action.to_dict() | {"target_ids": ["object:does-not-exist"]}
    score = score_item(EvalItem(json.dumps(payload), target_text, state, item_id="bad-target"))
    assert score.failure_class is FailureClass.BAD_ARGUMENTS
    assert "UNKNOWN_ACTION_TARGET" in score.issue_codes
    assert score.verified is False


def test_illegal_action_id_is_verifier_rejected() -> None:
    state, action, target_text = gold()
    payload = action.to_dict() | {"action_id": "action:invented"}
    score = score_item(EvalItem(json.dumps(payload), target_text, state, item_id="illegal"))
    assert score.failure_class is FailureClass.VERIFIER_REJECTED
    assert "ILLEGAL_TRANSITION_ACTION" in score.issue_codes
    assert score.verified is False


# --------------------------------------------------------------------------------------
# Fail closed: unadjudicable states and raising verifiers never produce a pass.
# --------------------------------------------------------------------------------------


def test_projected_observation_passed_by_mistake_is_unadjudicated_not_a_zero_score() -> None:
    """The mirror image of the constant-1.000 bug: a silent constant 0.000."""

    state, _, target_text = gold()
    observation = project_state_for_observation(state, ObservationKind.NEXT_ACTION)
    score = score_item(EvalItem(target_text, target_text, observation, item_id="observation"))
    assert score.failure_class is FailureClass.UNADJUDICATED
    assert score.adjudicated is False
    assert score.verified is False
    assert score.exact is True  # the prediction was perfect; the harness could not adjudicate it


def test_a_state_the_verifier_rejects_is_unadjudicated() -> None:
    state, _, target_text = gold()
    broken = replace(state, legal_actions=(*state.legal_actions, *state.legal_actions))
    score = score_item(EvalItem(target_text, target_text, broken, item_id="broken-state"))
    assert score.failure_class is FailureClass.UNADJUDICATED
    assert score.adjudicated is False
    assert score.verified is False


class _RaisingVerifier:
    name = "raising"
    version = "0.0.0"

    def verify_state(self, state: CanonicalState) -> VerificationResult:
        raise RuntimeError("verifier exploded")

    def verify_transition(self, transition: CanonicalTransition) -> VerificationResult:
        raise RuntimeError("verifier exploded")


class _AlwaysAcceptingStateVerifier:
    """Accepts states so adjudication proceeds, then raises on the transition."""

    name = "half-raising"
    version = "0.0.0"

    def verify_state(self, state: CanonicalState) -> VerificationResult:
        return VerificationResult(self.name, self.version, True, ())

    def verify_transition(self, transition: CanonicalTransition) -> VerificationResult:
        raise RuntimeError("verifier exploded")


def test_an_exception_never_becomes_a_pass() -> None:
    _, _, target_text = gold()
    for engine in (_RaisingVerifier(), _AlwaysAcceptingStateVerifier()):
        score = score_item(item(target_text), verifier=engine)
        assert score.verified is False
        assert score.failure_class is FailureClass.VERIFIER_ERROR
        assert "verifier exploded" in score.detail


def test_a_verifier_that_rejects_everything_never_yields_verified() -> None:
    class _Rejecting:
        name = "rejecting"
        version = "0.0.0"

        def _no(self) -> VerificationResult:
            issue = VerificationIssue("NOPE", Severity.CRITICAL, "no")
            return VerificationResult(self.name, self.version, False, (issue,))

        def verify_state(self, state: CanonicalState) -> VerificationResult:
            return self._no()

        def verify_transition(self, transition: CanonicalTransition) -> VerificationResult:
            return self._no()

    _, _, target_text = gold()
    score = score_item(item(target_text), verifier=_Rejecting())
    assert score.verified is False
    assert score.failure_class is FailureClass.UNADJUDICATED


def test_decode_action_raises_rather_than_returning_a_default() -> None:
    with pytest.raises(ActionDecodeError):
        decode_action("not a dict")
    with pytest.raises(ActionDecodeError):
        decode_action({"action_id": "a"})
    with pytest.raises(ActionDecodeError):
        decode_action({"action_id": "a", "operation": "e", "arguments": [{"no_op_key": 1}]})


def test_malformed_target_text_is_a_loud_harness_error_not_a_miss() -> None:
    state, _, _ = gold()
    with pytest.raises(json.JSONDecodeError):
        score_item(EvalItem("{}", "not json", state, item_id="bad-target-text"))


# --------------------------------------------------------------------------------------
# Batch report: vector shapes, taxonomy totals, determinism.
# --------------------------------------------------------------------------------------


def mixed_batch() -> tuple[EvalItem, ...]:
    state, action, target_text = gold()
    return (
        EvalItem(target_text, target_text, state, item_id="exact"),
        EvalItem(
            json.dumps(replace(action, expected_usefulness=0.0).to_dict()),
            target_text,
            state,
            item_id="verified-not-exact",
        ),
        EvalItem(hollow_prediction(state), target_text, state, item_id="hollow"),
        EvalItem("garbage", target_text, state, item_id="unparseable"),
        EvalItem("{}", target_text, state, item_id="missing-keys"),
        EvalItem(
            target_text,
            target_text,
            project_state_for_observation(state, ObservationKind.NEXT_ACTION),
            item_id="unadjudicated",
        ),
    )


def test_report_vectors_have_one_entry_per_item_and_feed_paired_statistics() -> None:
    report = evaluate_predictions(mixed_batch())
    assert report.n == 6
    for vector in (
        report.schema_valid_vector,
        report.exact_vector,
        report.verified_vector,
        report.adjudicated_vector,
    ):
        assert len(vector) == 6
        assert all(value in (0.0, 1.0) for value in vector)

    from arena.training.evaluation import paired_bootstrap_difference, wilson_interval

    interval = paired_bootstrap_difference(
        report.verified_vector, report.exact_vector, resamples=200
    )
    assert interval.n == 6
    assert wilson_interval(int(sum(report.verified_vector)), report.n).n == 6


def test_report_separates_the_three_metrics_and_the_taxonomy() -> None:
    report = evaluate_predictions(mixed_batch())
    assert report.schema_valid_vector == (1.0, 1.0, 1.0, 0.0, 0.0, 1.0)
    assert report.exact_vector == (1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    assert report.verified_vector == (1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    # The three metrics disagree item-by-item; none is a relabelling of another.
    assert report.schema_valid_vector != report.exact_vector
    assert report.schema_valid_vector != report.verified_vector
    assert report.exact_vector != report.verified_vector
    assert report.failure_counts["EXACT"] == 1
    assert report.failure_counts["VERIFIED_NOT_EXACT"] == 1
    assert report.failure_counts["CONTENT_MISMATCH"] == 1
    assert report.failure_counts["UNPARSEABLE"] == 1
    assert report.failure_counts["MISSING_KEYS"] == 1
    assert report.failure_counts["UNADJUDICATED"] == 1
    assert sum(report.failure_counts.values()) == report.n
    assert set(report.failure_counts) == {member.value for member in FailureClass}


def test_verified_not_exact_is_reported_separately_from_exact() -> None:
    report = evaluate_predictions(mixed_batch())
    assert report.verified_not_exact == 1
    assert report.exact_not_verified == 1  # the unadjudicated item; a deliberate red flag


def test_unadjudicated_items_stay_in_the_denominator_and_the_alternative_is_exposed() -> None:
    report = evaluate_predictions(mixed_batch())
    assert report.unadjudicated == 1
    assert report.verified_rate == pytest.approx(2 / 6)
    assert report.verified_rate_excluding_unadjudicated == pytest.approx(2 / 5)
    assert "NOT verified" in report.to_dict()["unadjudicated_policy"]


def test_report_is_deterministic() -> None:
    first = evaluate_predictions(mixed_batch()).to_dict()
    second = evaluate_predictions(mixed_batch()).to_dict()
    assert first == second
    assert first["verifier"] == "arena-native"


def test_report_over_the_whole_generated_slice_is_not_a_constant() -> None:
    """The failure mode being escaped: a metric that reads the same for everything."""

    items = []
    for index in range(len(TASKS)):
        state, _, target_text = gold(index)
        prediction = target_text if index % 2 == 0 else hollow_prediction(state)
        items.append(EvalItem(prediction, target_text, state, item_id=f"item:{index}"))
    report = evaluate_predictions(tuple(items))
    assert 0.0 < report.verified_rate < 1.0
    assert report.schema_valid_rate == 1.0  # every completion is well formed ...
    assert report.verified_rate < report.schema_valid_rate  # ... but half are hollow


def test_action_content_key_ignores_only_the_oracle_label() -> None:
    _, action, _ = gold()
    assert action_content_key(replace(action, expected_usefulness=0.5)) == action_content_key(
        action
    )
    altered = replace(
        action, arguments=(CanonicalExpression(op="integer", sort="Integer", value=1),)
    )
    assert action_content_key(altered) != action_content_key(action)


def test_empty_batch_produces_an_empty_report_rather_than_a_rate() -> None:
    report = evaluate_predictions(())
    assert isinstance(report, VerifiedEvalReport)
    assert report.n == 0
    assert report.verified_vector == ()
    assert report.verified_rate_excluding_unadjudicated is None
