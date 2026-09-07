"""Stage 4: consolidate every measurement into artifacts/reports/next_action_leakage.json."""
from __future__ import annotations
import copy, json, subprocess
from collections import Counter, defaultdict
from pathlib import Path

from arena.training.prepare_matched_data import ARMS, stratified_split
from research.leakage.measure import (
    FIELDS, build_records, evaluate, fit_all, obfuscate, opaque, case_prefix, sub_strings,
)
from research.leakage.lib import induce_affix, apply_affix
from research.leakage.predictors import scalars

tasks, records = build_records(676, 0, with_inputs=True)
train_ix, dev_ix, fresh_ix = stratified_split(tasks, 600, 48, 48, 0)
train = [records[i] for i in train_ix]
dev = [records[i] for i in dev_ix]
fresh = [records[i] for i in fresh_ix]
held = dev + fresh

def variant(recs, tier_allow):
    tr = [recs[i] for i in train_ix]
    rules, desc, arg_info = fit_all(tr, allow_arith=tier_allow)
    return rules, desc, arg_info

consistent = []
for rec in records:
    r = copy.deepcopy(rec); pre = case_prefix(r["state_id"]); tok = opaque(pre)
    r["obs"] = sub_strings(r["obs"], [(pre, tok)])
    r["target"] = sub_strings(r["target"], [(pre, tok)])
    consistent.append(r)

VARIANTS = {
    "V0_baseline_no_obfuscation": records,
    "V1_state_id_replaced_by_opaque_token": obfuscate(records, "state_id_only"),
    "V2_all_case_identifiers_opaque_observation_only": obfuscate(records, "all_ids"),
    "V3_all_case_identifiers_opaque_consistently_on_both_sides": consistent,
}
TIERS = {"TIER_B_zero_arithmetic": False, "TIER_C_arithmetic_permitted": True}

results = {}
for vname, recs in VARIANTS.items():
    results[vname] = {}
    for tname, allow in TIERS.items():
        rules, desc, arg_info = variant(recs, allow)
        splits = {
            "all_676": evaluate(rules, recs),
            "train_580": evaluate(rules, [recs[i] for i in train_ix]),
            "dev_48_the_slice_the_sprint_scored": evaluate(rules, [recs[i] for i in dev_ix]),
            "fresh_48": evaluate(rules, [recs[i] for i in fresh_ix]),
            "heldout_96_dev_plus_fresh": evaluate(rules, [recs[i] for i in dev_ix + fresh_ix]),
        }
        results[vname][tname] = {
            "induced_rules": desc,
            "per_field_exact_all_676": splits["all_676"]["per_field_exact"],
            "per_field_exact_heldout_96": splits["heldout_96_dev_plus_fresh"]["per_field_exact"],
            "whole_target_exact": {k: v["whole_target_exact"] for k, v in splits.items()},
            "target_excluding_action_id_exact": {
                k: evaluate(rules, r_, drop_action_id=True)["whole_target_exact"]
                for k, r_ in (("all_676", recs),
                              ("heldout_96_dev_plus_fresh", [recs[i] for i in dev_ix + fresh_ix]))
            },
        }
        if vname == "V0_baseline_no_obfuscation":
            results[vname][tname]["arguments_rule_by_goal_op"] = arg_info

# ---- leak redundancy for action_id
common = set.intersection(*[set(scalars(r["obs"])) for r in train])
redundant = []
for k in sorted(common, key=repr):
    src = [scalars(r["obs"])[k] for r in train]
    if not all(isinstance(s, str) for s in src):
        continue
    rule = induce_affix(src, [r["target"]["action_id"] for r in train])
    if rule is None:
        continue
    if all(apply_affix(rule, scalars(r["obs"])[k]) == r["target"]["action_id"] for r in records):
        redundant.append({"observation_field": str(k),
                          "rewrite": f"strip {rule[0]!r}/{rule[1]!r}, prepend {rule[2]!r}, append {rule[3]!r}"})

# ---- residual characterisation
rules_b, _, _ = fit_all(train, allow_arith=False)
miss = defaultdict(list)
for r in records:
    if rules_b["arguments"].predict(r["obs"]) != r["target"]["arguments"]:
        miss[(r["domain"], r["obs"]["goal"]["op"])].append(r["index"])
residual = {
    f"{d}/{o}": {"n": len(v),
                 "required_operation": {"add": "integer addition of the two visible operands",
                                        "eq": "integer subtraction of two visible operands",
                                        "div": "integer floor division of two visible operands",
                                        "sqrt": "integer square root of one visible operand"}[o]}
    for (d, o), v in sorted(miss.items())
}

# ---- character share
shares = Counter(); totals = 0
for r in records:
    totals += len(json.dumps(r["target"], ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    for f in FIELDS:
        shares[f] += len(json.dumps({f: r["target"][f]}, ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":"))) - 2
char_share = {f: round(shares[f] / totals, 4) for f in FIELDS}

# ---- projection audit
sample = records[0]
proj_audit = {
    "function": "arena/compiler/projection.py:25 project_state_for_observation(state, NEXT_ACTION)",
    "fields_stripped": ["legal_actions -> ()", "plausible_invalid_actions -> ()",
                        "execution_metadata -> ()"],
    "fields_that_survive_verbatim": [
        "state_id", "objects (incl. object_id)", "bindings (incl. binder_id, scope_id)",
        "assumptions", "established_facts", "propositions", "goal", "obligations",
        "evidence_dependencies", "local_scope", "terminal_status", "schema_version"],
    "state_id_present_verbatim_in_rendered_prompt": {
        arm: f"{sum(r['state_id'] in r['inputs'][arm] for r in records)}/676" for arm in ARMS},
}

report = {
    "report": "NEXT_ACTION answer-leakage audit for Arena World v0",
    "verdict": "TASK_FAMILY_DEGENERATE_FOR_LEARNING_CURVES",
    "headline": {
        "whole_target_model_free_exact_match_all_676": results
            ["V0_baseline_no_obfuscation"]["TIER_C_arithmetic_permitted"]["whole_target_exact"]["all_676"],
        "whole_target_model_free_exact_match_heldout_96": results
            ["V0_baseline_no_obfuscation"]["TIER_C_arithmetic_permitted"]["whole_target_exact"]["heldout_96_dev_plus_fresh"],
        "whole_target_zero_arithmetic_exact_match_all_676": results
            ["V0_baseline_no_obfuscation"]["TIER_B_zero_arithmetic"]["whole_target_exact"]["all_676"],
        "statement": (
            "A deterministic rule set induced from the 580-example train split, containing no "
            "model and no learned parameters beyond a 13-to-18 entry lookup table and four "
            "single-step integer operations, reproduces the complete gold NEXT_ACTION target "
            "on 676/676 tasks, including 96/96 held-out. Seven of the eight target fields are "
            "reproduced with no arithmetic whatever."),
    },
    "method": {
        "data_path": [
            "arena.tasks.generators.world_v0.generate_tasks(total=676, seed=0)",
            "arena.training.render_dataset.render_next_action_example(trajectory, renderer)",
            "arena.compiler.projection.project_state_for_observation(state_before, NEXT_ACTION)",
            "split: arena.training.prepare_matched_data.stratified_split(tasks, 600, 48, 48, 0)"
             " -> train 580 / dev 48 / fresh 48 (train saturates at 580; the sprint used 224 and 576)",
        ],
        "commands": [
            "python -m research.leakage.run_baseline",
            "python -m research.leakage.run_obfuscation",
            "python -m research.leakage.run_residual",
            "python -m research.leakage.write_report",
        ],
        "predictor": (
            "No rule is hand-written per domain. Each field's rule is SEARCHED over a small "
            "generic hypothesis space (constant / minimum-description-length lookup on any "
            "visible scalar / string affix-rewrite / verbatim observation-field copy / "
            "structural anti-unification template whose scalar holes are filled by verbatim "
            "copy, learned affix rewrite, learned two-source string join, or -- Tier C only -- "
            "one unary or binary integer operation over two visible numbers), FITTED on the "
            "580 train examples only, then EVALUATED on the untouched 96 held-out examples."),
        "tiers": {
            "TIER_B_zero_arithmetic": "string rewrites, lookups, constants, subtree copies. No numeric computation.",
            "TIER_C_arithmetic_permitted": "Tier B plus one integer +, -, //, or isqrt over visible operands.",
        },
        "metric": ("decoded-JSON equality of the predicted action dict against the gold action "
                   "dict -- bit-for-bit the predicate gpu_matched_runner.py:81 uses for `exact`."),
    },
    "measurements": results,
    "projection_audit": proj_audit,
    "leak_mechanism": {
        "action_id": {
            "finding": "action_id is a pure string rewrite of an identifier left visible in the prompt.",
            "example": "state:arithmetic:0000:0000:initial -> action:arithmetic:0000:0000:valid",
            "exact_match_676": 1.0,
            "redundant_sources": redundant,
            "note": ("The leak is REDUNDANT: object_id ('object:<case-prefix>') carries the same "
                     "case prefix, so removing state_id alone changes nothing."),
        },
        "operation": {
            "finding": ("13 domains -> 13 operations, every set a singleton; and 18 distinct "
                        "goal.op values -> the same 13 operations, every set a singleton. So "
                        "`operation` is recoverable EITHER from the state_id domain segment OR, "
                        "with no identifier at all, from the root operator of the visible goal."),
            "exact_match_676": 1.0,
        },
        "target_ids": {"finding": "constant [\"goal\"] in 676/676", "exact_match_676": 1.0},
        "warrant": {"finding": "constant \"arena-world-v0 exact template\" in 676/676", "exact_match_676": 1.0},
        "generated_obligations": {"finding": "constant [] in 676/676", "exact_match_676": 1.0},
        "expected_usefulness": {"finding": "constant 1.0 in 676/676", "exact_match_676": 1.0},
        "preconditions": {
            "finding": ("verbatim copy of the observation's own `assumptions` field, which the "
                        "NEXT_ACTION projection does not strip, in 676/676"),
            "exact_match_676": 1.0},
        "arguments": {
            "finding": ("the only field carrying mathematical content. 554/676 (0.8195) is a "
                        "pure structural rewrite of the visible goal -- constant, subtree copy, "
                        "affix rename, or string join -- requiring no arithmetic. The remaining "
                        "122/676 each require exactly ONE integer operation on operands that are "
                        "both already visible."),
            "exact_match_676_zero_arithmetic": 0.819527,
            "exact_match_676_arithmetic_permitted": 1.0},
    },
    "residual_after_zero_arithmetic_rule": {
        "total": 122, "of": 676, "fraction": round(122 / 676, 6),
        "by_group": residual,
        "characterisation": (
            "The residual is genuine arithmetic, not a longer or rarer string pattern -- but it "
            "is arithmetic of the smallest possible kind. Answer magnitudes: add 4..28, eq 2..18, "
            "div 3..17, sqrt 2..17. Each is one operation on two integers that are both printed "
            "verbatim in the prompt. No composition, no multi-step derivation, no search."),
    },
    "obfuscation_counterfactual": {
        "V1_state_id_only": {
            "result": "NO EFFECT. Whole-target exact stays 1.000 (Tier C) / 0.8195 (Tier B).",
            "why": ("objects[0].object_id still spells 'object:<case-prefix>', so the same affix "
                    "rewrite reconstructs action_id; and `operation` falls back to the goal's "
                    "root operator, an 18-entry table, with no loss."),
        },
        "V2_all_case_identifiers_opaque_observation_only": {
            "result": ("action_id becomes genuinely underivable (held-out 0.000), so whole-target "
                       "held-out exact falls to 0.000. But target-excluding-action_id stays at "
                       "1.000 held-out (Tier C) / 0.7917 (Tier B)."),
            "why": ("This is not a repair: it only makes a display identifier unpredictable while "
                    "leaving every mathematically meaningful field exactly as derivable as before."),
        },
        "V3_all_case_identifiers_opaque_consistently_on_both_sides": {
            "result": "Whole-target exact returns to 1.000 (Tier C) / 0.8195 (Tier B), held-out included.",
            "why": ("Under the only obfuscation that keeps the target well defined -- renaming the "
                    "case prefix identically in observation and target -- the affix rewrite "
                    "reconstructs action_id from the opaque token itself. Obfuscation cannot "
                    "remove a leak whose content is a shared arbitrary name."),
        },
        "conclusion": ("Identifier obfuscation does not salvage this task family. It can, at best, "
                       "make one non-mathematical field unpredictable. The mathematical target "
                       "(`arguments`) is 100% derivable with or without identifiers, because it is "
                       "derived from the goal, not from the identifiers."),
    },
    "target_character_share": {
        "by_field": char_share,
        "zero_arithmetic_fields_share": round(sum(v for k, v in char_share.items() if k != "arguments"), 4),
        "note": ("69.05% of the target string's characters live in the seven fields that need no "
                 "arithmetic at all. `arguments` occupies 28.49%, and 81.95% of THAT is itself a "
                 "structural rewrite of the visible goal."),
    },
    "guard_analysis": {
        "function": "arena/compiler/projection.py:47-54 assert_no_answer_leakage",
        "called_on_this_path": False,
        "would_it_have_caught_this_leak": "NO",
        "what_it_actually_checks": [
            "for NEXT_ACTION/COMPLETE: that observation.legal_actions and "
            "observation.plausible_invalid_actions are both EMPTY containers",
            "for every action still present in either container: that expected_usefulness == 0.0",
        ],
        "why_it_cannot_catch_it": [
            "project_state_for_observation already sets both tuples to () at line 35, so check 1 "
            "is satisfied by construction and check 2 iterates over an empty sequence. On the "
            "NEXT_ACTION path the guard is VACUOUSLY TRUE; calling it would have changed nothing.",
            "Its signature is (observation, kind). It never receives the gold target, so it is "
            "structurally incapable of testing any relation between observation and answer.",
            "It tests container membership -- 'is the answer object literally sitting in a "
            "designated answer field' -- not derivability. Every field carrying this leak "
            "(state_id, objects[].object_id, bindings, local_scope, obligations[].obligation_id, "
            "evidence_dependencies[].evidence_id, assumptions) is outside the two fields it reads.",
        ],
        "what_a_real_leak_check_would_need": [
            "Take BOTH the observation and the gold target.",
            "Assert no target string is reconstructible from any visible string by a bounded "
            "affix/substring rewrite (this alone catches action_id at 676/676).",
            "Assert no target subtree is a verbatim copy of a visible subtree beyond what the "
            "task intends to be copied (catches preconditions, and most of `arguments`).",
            "Assert that a generic rule/template search fitted on train does not exceed a "
            "pre-registered held-out ceiling on any target field -- i.e. run this audit as a test.",
            "Assert every constant-valued target field is either removed from the target or "
            "excluded from the scored metric.",
        ],
    },
    "consequence_for_the_tier2_sprint": {
        "artifact": "artifacts/experiments/tier2_sprint/gpu_sprint_results.json",
        "reported": {"L0_STRUCTURED_ENGLISH": {"224/dev": 0.9375, "576/dev": 0.9583},
                     "L1_CURRENT_HML": {"224/dev": 0.8958},
                     "L2_SEXPR": {"224/dev": 0.8333},
                     "L3_JSON_AST": {"224/dev": 0.9792, "576/dev": 1.0, "576/fresh": 1.0},
                     "L5_COMPACT_SYMBOLIC": {"224/dev": 0.9583, "576/dev": 1.0, "576/fresh": 1.0}},
        "what_this_analysis_ESTABLISHES": [
            "The NEXT_ACTION task over Arena World v0 admits a complete model-free shortcut. A "
            "ceiling of exact = 1.000 is reachable with no mathematical reasoning beyond four "
            "single-step integer operations, and 0.8195 is reachable with none at all.",
            "Therefore a reported exact of 1.000 is NOT evidence of mathematical learning, and "
            "the gap between arms at a fixed budget is not, on this evidence, a measurement of "
            "how well a surface conveys mathematics.",
            "The task cannot separate a model that reasons from a model that pattern-matches "
            "identifiers, because both reach the same ceiling.",
        ],
        "what_this_analysis_DOES_NOT_ESTABLISH": [
            "It does NOT establish that the fine-tuned Qwen2.5-7B models actually took the "
            "shortcut. This analysis measures a property of the TASK, not the behaviour of any "
            "model. No model was run, and no model output was inspected.",
            "It does NOT establish that the between-arm ordering (L3/L5 > L0 > L1 > L2 at 224 "
            "examples) is an artefact. That ordering could still reflect a real difference in "
            "how cheaply each surface makes the shortcut available -- which is a finding about "
            "notation, but not the finding the sprint claims.",
            "It does NOT retro-invalidate the run's engineering: the matched-arm machinery, "
            "identical targets, and disjoint splits all did what they claim.",
        ],
        "cheapest_experiment_that_would_settle_it": {
            "design": ("Re-score the EXISTING saved sprint completions -- no GPU, no new training "
                       "-- field by field, and cross-tabulate against the model-free predictor's "
                       "per-item prediction. Two diagnostics settle it: (a) on the 122 items that "
                       "need arithmetic, is per-item exact the same as on the 554 that do not? "
                       "(b) does the model's action_id track the state_id rewrite even when the "
                       "`arguments` field is wrong?"),
            "if_completions_were_not_saved": (
                "One evaluation-only pass (no training) of the already-trained stage-B adapters "
                "over a 96-item probe: 48 items unchanged, 48 identical except that the case "
                "prefix in state_id and object_id is replaced by an opaque token. A model that "
                "learned the mathematics is unaffected; a model that learned the rewrite loses "
                "action_id and its exact score collapses. Cost: minutes of inference, zero "
                "training."),
            "cost": "zero new training; inference only, or pure re-analysis if completions were saved",
        },
    },
    "verdict_detail": {
        "verdict": "TASK_FAMILY_DEGENERATE_FOR_LEARNING_CURVES",
        "justification": [
            "Whole-target model-free exact match = 1.000 (676/676; 96/96 held-out).",
            "Seven of eight target fields = 1.000 with zero arithmetic.",
            "Whole-target with zero arithmetic = 0.8195 (554/676), held-out 0.7917.",
            "Identifier obfuscation does not repair it: 1.000 under V1 and V3; under V2 only the "
            "non-mathematical action_id field is lost, and the mathematical target stays at 1.000.",
            "A learning curve whose ceiling is reachable by string rewriting cannot measure the "
            "sample efficiency of mathematical learning, which is what Route B is for.",
        ],
        "what_would_make_it_usable": [
            "Drop action_id, warrant, target_ids, generated_obligations and expected_usefulness "
            "from the scored target -- they are 100% constant or 100% mechanical and contribute "
            "69% of the target's characters while carrying no information.",
            "Score only `arguments`, and only on instances whose answer is NOT a verbatim subtree "
            "of the observation -- on the present world that is 122 of 676 tasks, too few and too "
            "easy (one integer operation each) for a learning curve.",
            "In practice this means Route B needs a different task family, or a World v1 whose "
            "answers are not one-step functions of a printed goal.",
        ],
    },
}
Path("artifacts/reports").mkdir(parents=True, exist_ok=True)
Path("artifacts/reports/next_action_leakage.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
print("wrote artifacts/reports/next_action_leakage.json",
      Path("artifacts/reports/next_action_leakage.json").stat().st_size, "bytes")
print("verdict:", report["verdict"])
print("headline:", json.dumps(report["headline"], indent=1)[:700])
