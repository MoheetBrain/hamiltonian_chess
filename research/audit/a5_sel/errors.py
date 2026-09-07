"""A5 Part G: rigorous error taxonomy for the V7 artifact.

The naive statistic "on wrong rows, does the model's answer equal rule R's prediction?" is,
on a 2-alternative task, ALGEBRAICALLY IDENTICAL to "is R also wrong on that row?".  So the
only sound test of shortcut-following is the 2x2 contingency of (model correct) x (rule
correct) with an association measure.  Both are reported.

READ-ONLY, zero model calls.   python -m research.audit.a5_sel.errors
"""
from __future__ import annotations
import json, math, pathlib, sys, random
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from arena.experiments import fitness_v7 as v7                  # noqa: E402
from arena.experiments.fitness_v5 import build_dev_pool         # noqa: E402
from arena.canonical.schema import canonical_json               # noqa: E402

ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = ROOT / "research/audit/a5_sel"
POS = v7.POSITIVE_VARIANTS


def _names(p):
    return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))

def _text(p):
    return canonical_json(p.state.to_dict(include_display_identity=False))

RULES = {
    "always_first_option":      lambda p: 0,
    "always_second_option":     lambda p: 1,
    "first_mentioned_in_state": lambda p: 0 if _text(p).find(f'"{_names(p)[0]}"') <= _text(p).find(f'"{_names(p)[1]}"') else 1,
    "last_mentioned_in_state":  lambda p: 0 if _text(p).rfind(f'"{_names(p)[0]}"') >= _text(p).rfind(f'"{_names(p)[1]}"') else 1,
    "more_frequent_in_state":   lambda p: 0 if _text(p).count(f'"{_names(p)[0]}"') >= _text(p).count(f'"{_names(p)[1]}"') else 1,
    "shorter_option_text":      lambda p: 0 if (len(_names(p)[0]), _names(p)[0]) <= (len(_names(p)[1]), _names(p)[1]) else 1,
    "alphabetically_first":     lambda p: 0 if _names(p)[0] <= _names(p)[1] else 1,
}


def fisher_two_sided(a, b, c, d):
    """Exact Fisher on [[a,b],[c,d]] (sum of tables no more probable than observed)."""
    from math import comb
    n = a + b + c + d
    r1, c1 = a + b, a + c
    def p(x):
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    p0 = p(a) * (1 + 1e-12)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    return sum(p(x) for x in range(lo, hi + 1) if p(x) <= p0)


def phi(a, b, c, d):
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return (a * d - b * c) / den if den else float("nan")


def contingency(rows, rule):
    """rows: annotated dicts. Returns 2x2 of (model correct) x (rule correct)."""
    a = sum(1 for r in rows if r["correct"] and r["rule_correct"][rule])       # both right
    b = sum(1 for r in rows if r["correct"] and not r["rule_correct"][rule])   # model right, rule wrong
    c = sum(1 for r in rows if not r["correct"] and r["rule_correct"][rule])   # model wrong, rule right
    d = sum(1 for r in rows if not r["correct"] and not r["rule_correct"][rule])
    return a, b, c, d


def main() -> int:
    art = json.loads(ART.read_text())
    probes = {p.probe_id: p for p in build_dev_pool(ROOT)}
    ann = []
    for r in art["rows"]:
        p = probes[r["probe_id"]]
        preds = {k: fn(p) for k, fn in RULES.items()}
        sd = p.state.to_dict(include_display_identity=False)
        ann.append({
            **{k: r[k] for k in ("mechanism", "level", "variant", "truth_kind", "cause",
                                 "correct", "expected_index", "parsed_index", "raw_output",
                                 "probe_id", "family_id", "prompt_tokens", "prompt_chars",
                                 "completion_tokens", "done_reason", "error", "prompt_hash")},
            "preds": preds,
            "rule_correct": {k: (v == r["expected_index"]) for k, v in preds.items()},
            "options": list(_names(p)),
            "n_objects": len(sd.get("objects", [])),
            "state_bytes": len(_text(p)),
            "features": p.oracle_record.get("features") or {},
        })
    rep = {}

    math_rows = [r for r in ann if r["truth_kind"] == "MATHEMATICAL"]
    posr = [r for r in math_rows if r["variant"] in POS]
    swpr = [r for r in math_rows if r["variant"] not in POS]

    # -------------------------------------------------- 1. naive vs corrected shortcut test
    tests = {}
    for scope, rows in (("all_mathematical", math_rows), ("positive_arms", posr),
                        ("swapped_arms", swpr)):
        per_rule = {}
        wrong = [r for r in rows if not r["correct"]]
        for rule in RULES:
            a, b, c, d = contingency(rows, rule)
            naive = sum(1 for r in wrong if r["parsed_index"] == r["preds"][rule])
            per_rule[rule] = {
                "NAIVE_answer_equals_rule_on_wrong_rows": f"{naive}/{len(wrong)}",
                "NAIVE_rate": naive / len(wrong) if wrong else None,
                "rule_accuracy_overall": (a + c) / len(rows),
                "rule_accuracy_on_model_CORRECT_rows": a / (a + b) if a + b else None,
                "rule_accuracy_on_model_WRONG_rows": c / (c + d) if c + d else None,
                "table_[mc_rc,mc_rw,mw_rc,mw_rw]": [a, b, c, d],
                "phi": phi(a, b, c, d),
                "fisher_two_sided_p": fisher_two_sided(a, b, c, d),
            }
        tests[scope] = per_rule
    rep["shortcut_following_tests"] = tests
    rep["shortcut_following_note"] = (
        "On a binary task, NAIVE_rate == (rule error rate on model-wrong rows). Shortcut-"
        "FOLLOWING predicts model errors concentrate where the rule is WRONG, i.e. "
        "rule_accuracy_on_model_WRONG_rows << rule_accuracy_on_model_CORRECT_rows (phi > 0). "
        "The opposite ordering REFUTES following."
    )

    # test restricted to each level's OWN best shortcut feature (the gated one)
    own = {}
    for mech in v7.MECHANISMS:
        for lvl in range(4):
            feat = art["shortcut_audit_by_level"][mech][str(lvl)]["best_shortcut_feature"]
            cell = [r for r in posr if r["mechanism"] == mech and r["level"] == lvl]
            a, b, c, d = contingency(cell, feat)
            own[f"{mech}|L{lvl}"] = {
                "gated_feature": feat, "n_positive": len(cell),
                "model_wrong": c + d,
                "of_those_rule_ALSO_wrong": d,
                "rule_acc_model_correct": a / (a + b) if a + b else None,
                "rule_acc_model_wrong": c / (c + d) if c + d else None,
                "phi": phi(a, b, c, d), "fisher_p": fisher_two_sided(a, b, c, d),
            }
    rep["per_cell_gated_feature_test"] = own

    # -------------------------------------------------- 2. position anchoring (swap consistency)
    fam = defaultdict(dict)
    for r in math_rows:
        fam[(r["family_id"], "O" if "COUNTERFACTUAL" in r["variant"] else "X")][r["variant"]] = r
    anchor = defaultdict(lambda: {"pairs": 0, "same_letter": 0, "both_wrong": 0,
                                  "flipped_and_both_right": 0, "flipped_one_wrong": 0})
    pairs_detail = []
    for key, d2 in fam.items():
        for base, swapped in (("ORIGINAL", "SWAPPED_ORIGINAL"),
                              ("COUNTERFACTUAL", "SWAPPED_COUNTERFACTUAL")):
            a, b = d2.get(base), d2.get(swapped)
            if not (a and b):
                continue
            k = f"{a['mechanism']}|L{a['level']}"
            anchor[k]["pairs"] += 1
            same = a["parsed_index"] == b["parsed_index"]
            anchor[k]["same_letter"] += same
            if not a["correct"] and not b["correct"]:
                anchor[k]["both_wrong"] += 1
            if not same and a["correct"] and b["correct"]:
                anchor[k]["flipped_and_both_right"] += 1
            if not same and (not a["correct"] or not b["correct"]):
                anchor[k]["flipped_one_wrong"] += 1
            pairs_detail.append({"cell": k, "family": a["family_id"], "arm": base,
                                 "base_answer": a["parsed_index"], "swap_answer": b["parsed_index"],
                                 "base_correct": a["correct"], "swap_correct": b["correct"],
                                 "same_letter_despite_swap": same})
    rep["position_anchoring_by_cell"] = {k: dict(v) for k, v in sorted(anchor.items())}
    tot_pairs = sum(v["pairs"] for v in anchor.values())
    tot_same = sum(v["same_letter"] for v in anchor.values())
    rep["position_anchoring_total"] = {
        "swap_pairs": tot_pairs, "same_letter_despite_option_swap": tot_same,
        "rate": tot_same / tot_pairs,
        "meaning": ("the option order was reversed; a content-driven answer must change letter. "
                    "Same letter == the answer was determined by POSITION, not content."),
    }

    # -------------------------------------------------- 3. taxonomy assignment
    wrong_all = [r for r in math_rows if not r["correct"]]
    swap_same = {(d["family"], d["arm"]) for d in pairs_detail if d["same_letter_despite_swap"]}
    tax = Counter(); assign = []
    for r in wrong_all:
        arm = r["variant"].replace("SWAPPED_", "")
        feat = art["shortcut_audit_by_level"][r["mechanism"]][str(r["level"])]["best_shortcut_feature"]
        if r["parsed_index"] is None or r["done_reason"] != "stop" or r["error"] is not None:
            cat = "output_format_failure"
        elif r["prompt_tokens"] >= 0.9 * art["runtime"]["num_ctx"]:
            cat = "context_loss"
        elif (r["family_id"], arm) in swap_same:
            cat = "position_anchoring(content_independent)"
        elif r["parsed_index"] == r["preds"][feat]:
            cat = "shortcut_consistent(gated_feature)"
        else:
            cat = "reasoning_failure(residual)"
        tax[cat] += 1
        assign.append({**{k: r[k] for k in ("mechanism", "level", "variant", "probe_id",
                                            "expected_index", "parsed_index", "raw_output",
                                            "prompt_tokens", "options")},
                       "category": cat, "gated_feature": feat,
                       "gated_feature_prediction": r["preds"][feat],
                       "depth_lead": r["features"].get("depth_lead")})
    rep["taxonomy_counts"] = dict(tax)
    rep["taxonomy_by_cell"] = {}
    for mech in v7.MECHANISMS:
        for lvl in range(4):
            sub = [a for a in assign if a["mechanism"] == mech and a["level"] == lvl]
            if sub:
                rep["taxonomy_by_cell"][f"{mech}|L{lvl}"] = dict(Counter(a["category"] for a in sub))

    # -------------------------------------------------- 4. ambiguity proxy (FED depth_lead)
    fed = [r for r in posr if r["mechanism"] == "formal_expression_depth"]
    dl = defaultdict(lambda: [0, 0])
    for r in fed:
        k = r["features"].get("depth_lead")
        dl[k][0] += 1
        dl[k][1] += r["correct"]
    rep["fed_depth_lead_vs_accuracy"] = {
        str(k): {"n": v[0], "correct": v[1], "acc": v[1] / v[0]} for k, v in sorted(dl.items(), key=lambda x: (x[0] is None, x[0]))
    }
    dl_lvl = defaultdict(Counter)
    for r in fed:
        dl_lvl[r["level"]][r["features"].get("depth_lead")] += 1
    rep["fed_depth_lead_by_level"] = {str(k): dict(v) for k, v in sorted(dl_lvl.items())}

    # -------------------------------------------------- 5. context-loss check
    rep["context"] = {
        "num_ctx": art["runtime"]["num_ctx"],
        "max_prompt_tokens": max(r["prompt_tokens"] for r in ann),
        "min_prompt_tokens": min(r["prompt_tokens"] for r in ann),
        "rows_over_50pct_ctx": sum(1 for r in ann if r["prompt_tokens"] > 0.5 * art["runtime"]["num_ctx"]),
        "mean_tokens_correct": sum(r["prompt_tokens"] for r in math_rows if r["correct"]) / sum(1 for r in math_rows if r["correct"]),
        "mean_tokens_wrong": sum(r["prompt_tokens"] for r in wrong_all) / len(wrong_all),
        "completion_tokens": dict(Counter(r["completion_tokens"] for r in ann)),
    }

    # -------------------------------------------------- 6. example raw outputs per cell
    ex = {}
    for mech in v7.MECHANISMS:
        for lvl in range(4):
            sub = [a for a in assign if a["mechanism"] == mech and a["level"] == lvl]
            if sub:
                ex[f"{mech}|L{lvl}"] = sub[:4]
    rep["error_examples"] = ex

    (OUT / "a5_errors.json").write_text(json.dumps(rep, indent=1, default=str))
    (OUT / "a5_error_assignments.json").write_text(json.dumps(assign, indent=1, default=str))
    (OUT / "a5_swap_pairs.json").write_text(json.dumps(pairs_detail, indent=0, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k != "error_examples"}, indent=1, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
