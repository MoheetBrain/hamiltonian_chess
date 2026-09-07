"""Leak-boundary and deterministic-fit tests; no corpus or sealed split reads."""
import copy

import pytest

from research.astra.game_r_premise.shortcut_audit import (
    ShortcutSuite, development_split, group_id, run_shortcut_audit,
)


def item(index, answer=0, proof=None):
    return {
        "task_id":f"t{index}",
        "provenance":{"proof_id":proof or f"p{index}","theorem_id":f"theorem{index}",
                      "file_path":"Mathlib/Example.lean","split":"train"},
        "context":{"text":"x : Nat"}, "goal":{"text":f"x = {index}"},
        "candidate_premises":[{"premise_id":f"p{n}","name":f"Lemma{n}",
            "statement":{"text":f"theorem Lemma{n} : x = {n}"},
            "provenance":{"source_path":"Mathlib/Example.lean","declaration_order":n}}
            for n in range(4)],
        "target_choice_id":f"p{answer}",
    }


def test_theorem_groups_never_cross_split_and_order_is_stable():
    bank = [item(n, proof=f"proof{n//2}") for n in range(20)]
    train, evaluation = development_split(bank)
    assert not ({group_id(i) for i in train} & {group_id(i) for i in evaluation})
    rt,re = development_split(list(reversed(bank)))
    assert {group_id(i) for i in train} == {group_id(i) for i in rt}
    assert {group_id(i) for i in evaluation} == {group_id(i) for i in re}


def test_evaluation_labels_cannot_change_fit_or_predictions():
    bank = [item(n,n%4) for n in range(20)]
    train,evaluation = development_split(bank)
    suite = ShortcutSuite(train)
    scores = [suite.visible_scores(i) for i in evaluation]
    changed = copy.deepcopy(evaluation)
    for i in changed: i["target_choice_id"] = "p3"
    assert scores == [suite.visible_scores(i) for i in changed]
    assert suite.name_frequency == ShortcutSuite(train).name_frequency
    assert suite.mdl_rule == ShortcutSuite(train).mdl_rule


def test_private_metadata_cannot_change_visible_rule_predictions():
    bank = [item(n,n%4) for n in range(20)]
    train,evaluation = development_split(bank)
    suite = ShortcutSuite(train)
    candidate = copy.deepcopy(evaluation[0])
    before = suite.visible_scores(candidate)
    candidate["provenance"] = {"proof_id":"forged","theorem_id":"Lemma3"}
    for c in candidate["candidate_premises"]: c["provenance"] = {"answer":True}
    candidate["audit_metadata"] = {"target":"p3"}
    assert before == suite.visible_scores(candidate)


def test_report_honest_about_same_proof_coverage_and_no_gate():
    report = run_shortcut_audit([item(n,n%4) for n in range(20)])
    assert report["private_metadata_controls"]["same_proof_frequency_train"]["status"] == "NOT_APPLICABLE"
    assert not report["qualification_gate_applied"]
    assert report["future_preregistration_recommendation"]["numeric_ceiling"] is None
    assert report["chance"] == .25
    assert report["model_calls"] == 0
    assert report == run_shortcut_audit([item(n,n%4) for n in range(20)])


def test_refuses_heldout_source_and_duplicate_items():
    bank = [item(n) for n in range(3)]
    bank[0]["provenance"]["split"] = "test"
    with pytest.raises(ValueError,match="DEVELOPMENT"): run_shortcut_audit(bank)
    with pytest.raises(ValueError,match="Duplicate"): run_shortcut_audit([item(1),item(1)])


def test_visible_train_lookup_never_reads_eval_answers():
    train = [item(0,0)]
    suite = ShortcutSuite(train)
    new = item(1,3)
    assert suite.visible_scores(new)["premise_name_frequency_train"] == [1,0,0,0]
    assert suite.visible_scores(new)["exact_goal_lookup_train"] == [0,0,0,0]


def test_honors_declared_partitions_and_refuses_group_crossing():
    bank = [item(n) for n in range(6)]
    for n,i in enumerate(bank):
        i["audit_metadata"] = {"dev_partition":"train" if n < 4 else "heldout"}
    train,evaluation = development_split(bank)
    assert [i["task_id"] for i in evaluation] == ["t4","t5"]
    bank[5]["provenance"]["proof_id"] = bank[0]["provenance"]["proof_id"]
    with pytest.raises(ValueError,match="crosses"): development_split(bank)
