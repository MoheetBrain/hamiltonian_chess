"""Assemble artifacts/corpus/operation_inventory.json from the measurements.

Consumes the three scratch dumps written by:
    research.operations.measure_annotated
    research.operations.measure_formal
    research.operations.measure_informal_proxy

Adds:
  * the CANONICAL / CONTROLLER split, per corpus, computed from
    research.operations.classify.TACTIC_CLASS
  * the operation x source recurrence matrix (per-source, never pooled)
  * alignment-confidence verdicts

Run:  python -m research.operations.build_inventory
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime

from research.operations import classify as C
from research.operations import paths as P


def layer_split(head_counts: dict[str, int]) -> dict:
    layers = Counter()
    ops = Counter()
    unclassified = Counter()
    for h, n in head_counts.items():
        layer, op, _ = C.classify_head(h)
        layers[layer] += n
        ops[f"{layer}:{op}"] += n
        if layer == "UNCLASSIFIED":
            unclassified[h] += n
    total = sum(head_counts.values())
    return {
        "total_steps": total,
        "by_layer": dict(layers.most_common()),
        "by_layer_pct": {
            k: round(100 * v / total, 2) for k, v in layers.most_common()
        },
        "by_operation": dict(ops.most_common()),
        "unclassified_heads": dict(unclassified.most_common(25)),
    }


def main() -> None:
    ann = json.loads((P.SCRATCH / "measure_annotated.json").read_text())
    frm = json.loads((P.SCRATCH / "measure_formal.json").read_text())
    inf = json.loads((P.SCRATCH / "measure_informal.json").read_text())

    g125 = ann["gold125_ontology_v1"]
    ld = frm["leandojo_random_val_test"]
    l241 = frm["lean_canonical_241k"]
    cal = inf["calibration_gold125"]
    math_ref = inf["math_reference_solutions_human"]
    prm = inf["prm800k_completions"]

    # ---- canonical vs controller, per formal corpus ------------------------
    hmlv3_heads = {
        "rw": 189, "simp": 108, "exacts": 88, "exact": 80, "have": 77,
        "all_goals": 51, "rintro": 41, "swap": 39, "obtain": 35, "refine": 34,
        "intro": 32, "apply": 30, "subst": 25, "revert": 22, "simpa": 21,
        "case": 18, "clear": 18, "rcases": 17, "simp_rw": 16, "ext": 15,
        "cases": 14, "suffices": 13, "on_goal": 11, "induction": 11,
        "convert": 10,
    }
    split = {
        "leandojo_random_val_test_8766": layer_split(ld["tactic_head_all"]),
        "lean_canonical_241k_top60_heads": layer_split(l241["tactic_head_top60"]),
        "hmlv3_1150_top25_heads_PRIOR_AGENT_MEASUREMENT": layer_split(hmlv3_heads),
    }
    # informal side: gold core_operation -> layer
    informal_layer = Counter()
    canonical_ops = {
        "TRANSFORM", "DISCHARGE", "EVALUATE", "APPLY_THEOREM", "VERIFY",
        "COUNT", "BOUND", "APPLY_DEFINITION", "CASE_SPLIT", "CONSTRUCT",
        "MODEL", "SUBSTITUTE", "INDUCT", "CONTRADICTION", "DECLARE",
        "SELECT", "ENUMERATE", "RECORD",
    }
    for op, n in g125["axes"]["core_operation"].items():
        informal_layer[
            "CANONICAL" if op in canonical_ops else "UNRESOLVED"
        ] += n
    tot_g = sum(informal_layer.values())
    split["gold125_769_annotated_MATH"] = {
        "total_steps": tot_g,
        "by_layer": dict(informal_layer),
        "by_layer_pct": {
            k: round(100 * v / tot_g, 2) for k, v in informal_layer.items()
        },
        "note": "The core_operation axis contains no controller value at all. "
                "Controller behaviour is carried on the ORTHOGONAL "
                "reasoning_mode axis: "
                + json.dumps(g125["axes"]["reasoning_mode"]),
    }

    # ---- recurrence matrix -------------------------------------------------
    def ld_n(*heads: str) -> int:
        return sum(ld["tactic_head_all"].get(h, 0) for h in heads)

    ldT = ld["n_tactics"]
    gT = g125["n_step_records"]
    mT = math_ref["n_steps"]
    pT = prm["n_model_steps_total"]
    gc = g125["axes"]["core_operation"]
    mr = math_ref["cue_fired"]
    pm = Counter()
    for v in prm["model_cue_fired_by_rating"].values():
        pm.update(v)

    def row(op, gold_key, cue_key, heads, note, formal_status="present"):
        g = gc.get(gold_key, 0) if gold_key else 0
        m = mr.get(cue_key, 0) if cue_key else 0
        p = pm.get(cue_key, 0) if cue_key else 0
        f = ld_n(*heads) if heads else 0
        return {
            "operation": op,
            "A_human_MATH_annotated_gold125": {
                "n": g, "of": gT, "pct": round(100 * g / gT, 2),
                "evidence": "gold core_operation label",
            },
            "B_human_MATH_reference_solutions": {
                "n": m, "of": mT, "pct": round(100 * m / mT, 2),
                "evidence": "LEXICAL PROXY (see calibration)",
            },
            "C_model_generated_PRM800K": {
                "n": p, "of": pT, "pct": round(100 * p / pT, 2),
                "evidence": "LEXICAL PROXY (see calibration)",
            },
            "D_formal_LeanDojo_representative": {
                "n": f, "of": ldT, "pct": round(100 * f / ldT, 2),
                "heads": list(heads), "status": formal_status,
            },
            "note": note,
        }

    matrix = [
        row("APPLY_THEOREM", "APPLY_THEOREM", "APPLY_THEOREM",
            ("exact", "exacts", "apply", "refine", "refine'",
             "exact_mod_cast", "apply_mod_cast", "specialize"),
            "Present in all four. The strongest genuine recurrence."),
        row("CASE_SPLIT", "CASE_SPLIT", "CASE_SPLIT",
            ("cases", "cases'", "rcases", "by_cases", "split", "split_ifs",
             "fin_cases", "match"),
            "Present in all four."),
        row("INTRODUCE (declare/binder/witness)", "DECLARE", "DECLARE",
            ("intro", "intros", "rintro", "introv", "obtain", "use", "set",
             "let", "choose", "existsi", "exists", "lift", "ext", "ext1",
             "funext"),
            "Present in all four, but the informal side splits it into "
            "DECLARE + CONSTRUCT and the formal side collapses it to one "
            "INTRODUCE effect."),
        row("SUBSTITUTE / REWRITE", "SUBSTITUTE", "SUBSTITUTE",
            ("rw", "rewrite", "erw", "rwa", "simp_rw", "nth_rw", "subst",
             "substs", "subst_vars"),
            "Present in all four. The largest formal category (rw+subst families = 22.64% of "
            "LeanDojo) and one of the smallest annotated ones (0.9%): the "
            "informal scheme folds rewriting into TRANSFORM."),
        row("INDUCT", "INDUCT", "INDUCT", ("induction", "induction'"),
            "Present in all four. The only operation whose lexical proxy is "
            "exact (precision 1.00, recall 1.00 on the 769 gold spans)."),
        row("CONTRADICTION", "CONTRADICTION", "CONTRADICTION",
            ("by_contra", "by_contra!", "exfalso", "contradiction",
             "contrapose", "contrapose!", "push_neg"),
            "Present in all four, everywhere rare (0.4-1.0%)."),
        row("DISCHARGE", "DISCHARGE", "DISCHARGE",
            ("rfl", "ac_rfl", "assumption", "assumption'", "trivial"),
            "Present in all four but MEANS DIFFERENT THINGS: informal "
            "DISCHARGE = 'state the final answer'; formal CLOSE = 'this "
            "branch is finished' (107,006 times in the 241k census)."),
        row("APPLY_DEFINITION", "APPLY_DEFINITION", "APPLY_DEFINITION",
            ("unfold", "delta", "change", "show", "dsimp"),
            "Present in all four, but the formal count is a severe "
            "undercount: definitional unfolding mostly happens inside simp "
            "and rfl and is never recorded as a step."),
        row("TRANSFORM", "TRANSFORM", "TRANSFORM",
            ("conv", "conv_lhs", "conv_rhs", "slice_lhs", "slice_rhs",
             "apply_fun", "convert", "convert_to", "congr", "congr!",
             "calc", "trans", "symm"),
            "Present in all four but is a sink category: 39.7% of the gold "
            "corpus and 77.3% of the synthetic corpus. Low information."),
        row("VERIFY", "VERIFY", "VERIFY", (),
            "ABSENT FROM FORMAL BY CONSTRUCTION. The kernel verifies, so "
            "verification is never a proof step. Genuine domain difference.",
            "absent_by_construction"),
        row("COUNT", "COUNT", "COUNT", (),
            "No canonical formal counterpart; absorbed by decide/norm_num "
            "automation. Domain difference (competition combinatorics) plus "
            "annotation-scheme artifact.", "absorbed_by_automation"),
        row("BOUND", "BOUND", "BOUND", (),
            "No canonical formal counterpart; absorbed by "
            "linarith/positivity/gcongr automation.",
            "absorbed_by_automation"),
        row("EVALUATE", "EVALUATE", "EVALUATE", (),
            "No canonical formal counterpart; absorbed by norm_num/decide.",
            "absorbed_by_automation"),
        row("SELECT", "SELECT", "SELECT", (),
            "No canonical formal counterpart.", "absent"),
        row("ENUMERATE", "ENUMERATE", "ENUMERATE", ("fin_cases", "interval_cases"),
            "Near-absent everywhere.", "near_absent"),
        row("CONSTRUCT", "CONSTRUCT", "CONSTRUCT",
            ("obtain", "choose", "use", "existsi", "exists", "lift"),
            "Present in all four; overlaps INTRODUCE on the formal side."),
        row("ASSERT_SUBGOAL", None, None, ("have", "suffices", "replace"),
            "PRESENT FORMALLY (have/suffices/replace = 654/8,766 = 7.46% of "
            "LeanDojo; `have` alone is the 4th most frequent head at 6.61%), "
            "ABSENT from the "
            "core_operation axis of the informal ontology (it lives on the "
            "goal_effect axis as CREATE_SUBGOAL), and DELETED from the "
            "241,265-record Lean corpus, which drops all goal-creating "
            "transitions. Not a domain difference: a schema decision."),
        row("PLAN / SEARCH_META", None, "PLAN", (),
            "11.8% of model-generated steps, 3.6% of human MATH reference "
            "sentences, 0 of the formal corpus. Model-specific.", "absent"),
        row("BACKTRACK", None, "BACKTRACK", (),
            "0.39% of model steps overall; 0.51% of steps rated -1 vs 0.23% "
            "of steps rated +1 (2.2x). ZERO in every formal corpus: a Lean "
            "trace holds only steps that were kept.",
            "absent_by_construction"),
        row("GOAL_MANAGEMENT", None, None,
            ("all_goals", "any_goals", "swap", "on_goal", "case", "focus",
             "next", "iterate", "repeat", "repeat'", "rotate_left",
             "pick_goal", "first", "try"),
            "Formal only. 0.44% of LeanDojo vs 11.72% of the HML_V3 1,150 "
            "corpus -- a 27x sampling artifact, not a fact about proofs.",
            "formal_only"),
        row("AUTOMATION", None, None,
            ("simp", "simpa", "dsimp", "simp_all", "simp?", "norm_num",
             "norm_num1", "norm_cast", "push_cast", "ring", "ring1",
             "ring_nf", "linarith", "nlinarith", "positivity", "omega",
             "decide", "tauto", "aesop", "aesop_cat", "field_simp", "abel",
             "abel1", "group", "gcongr", "filter_upwards", "mfld_set_tac",
             "fun_prop", "coherence", "solve_by_elim", "apply_rules"),
            "Formal only, and large. The single largest block of the formal "
            "corpus after rw/exact.", "formal_only"),
    ]

    out = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "schema_version": "operation-inventory-v1",
        "question": "Which reasoning operations recur across human solutions, "
                    "informal model solutions, and formal proof states?",
        "headline": HEADLINE,
        "limits_read_first": LIMITS,
        "method": METHOD,
        "sources": SOURCES(g125, ld, l241, math_ref, prm, ann, frm),
        "canonical_vs_controller": {
            "definition": {
                "CANONICAL": "changes the mathematics; a mathematician would "
                             "name it as a proof step",
                "CONTROLLER": "drives the prover: search, automation, goal "
                              "management, environment plumbing",
            },
            "judgement_not_measurement": "This split is a stated judgement. "
                                         "Every contested call is listed in "
                                         "contested_calls.",
            "contested_calls": C.AMBIGUOUS_CALLS,
            "per_corpus": split,
        },
        "recurrence_matrix": matrix,
        "reconciled_operations": C.RECONCILED,
        "taxonomy_reconciliation_summary": TAXONOMY_SUMMARY,
        "alignment_confidence": ALIGNMENT(cal),
        "lexical_proxy_calibration": cal,
        "raw_measurements": {
            "annotated": ann,
            "formal": frm,
            "informal_proxy": inf,
        },
        "what_would_settle_it": NEXT_MEASUREMENTS,
    }
    P.OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    P.OUT_JSON.write_text(json.dumps(out, indent=1))
    print("written", P.OUT_JSON, P.OUT_JSON.stat().st_size, "bytes")
    for k, v in split.items():
        print(f"{k:<52}", v["by_layer_pct"])


# ---------------------------------------------------------------------------
# Prose blocks (kept at the bottom so the measurement code reads cleanly)
# ---------------------------------------------------------------------------

HEADLINE = (
    "Nine operations are attested in all three source kinds -- human "
    "solutions, model-generated solutions, and formal proof states: "
    "APPLY_THEOREM, CASE_SPLIT, INTRODUCE (declare/binder/witness), "
    "SUBSTITUTE/REWRITE, INDUCT, CONTRADICTION, DISCHARGE, APPLY_DEFINITION "
    "and TRANSFORM. Only two of the nine survive an adversarial alignment "
    "check with high confidence (INDUCT, CASE_SPLIT); three more are "
    "medium (APPLY_THEOREM, CONTRADICTION, INTRODUCE); and four are "
    "same-name-different-operation (DISCHARGE, TRANSFORM, APPLY_DEFINITION, "
    "SUBSTITUTE/REWRITE). Five informal operations (VERIFY, COUNT, BOUND, "
    "EVALUATE, SELECT) have no canonical formal counterpart at all, and two "
    "formal categories (AUTOMATION 20.5%, GOAL_MANAGEMENT 0.4%) have no "
    "informal counterpart. The recurrence result is REAL BUT WEAK: it rests "
    "on 769 annotated human steps, and on a lexical proxy whose measured "
    "precision on those same 769 steps ranges from 0.08 to 1.00."
)

LIMITS = [
    "1. SAMPLE SIZE. The only corpus with per-step operation labels, warrants, "
    "preconditions, obligations and typed dependencies is 769 Gold-125/Gold-25 "
    "transitions plus 23 hand-authored Gold-10 actions = 792 steps. Everything "
    "else in this study is either unlabelled text or single-operation formal "
    "traces.",
    "2. 17.7% OF THE ANNOTATED CORPUS HAS NO OPERATION. 136/769 gold steps are "
    "core_operation=UNRESOLVED, 125 of them from observed_operation=OTHER. The "
    "richest corpus in the estate declines to name the operation for one step "
    "in six.",
    "3. ONE OPERATION DOMINATES. TRANSFORM is 305/769 (39.7%) of the gold "
    "corpus and 3,074/3,978 (77.3%) of the synthetic corpus. Recurrence of a "
    "sink category is close to uninformative.",
    "4. SINGLE DOMAIN, AND CONTAMINATED. Every richly-annotated step is "
    "Hendrycks MATH competition mathematics, and MATH is in the training data "
    "of every model this project evaluates. No held-out claim can be made from "
    "it.",
    "5. GOLD-10 SHOWS NO RECURRENCE AT ALL. 23 hand-authored actions carry 22 "
    "distinct operation names. It is a near-bijection between steps and "
    "operation names, so it provides zero evidence that operations recur; it "
    "is a specification exercise, not a sample.",
    "6. THE FORMAL CORPORA HAVE ONE OPERATION LABEL. action.operation == "
    "'LEAN_TACTIC' on all 56,000 hml_50k_final records and all vnext_10k "
    "records, with all five effect maps empty. Tactic text is recoverable, "
    "operation semantics are not.",
    "7. NO NEGATIVE EXAMPLES IN ANY FORMAL CORPUS. A Lean trace holds only the "
    "steps that were kept. PRM800K's 262,146 -1-rated steps are the only large "
    "source of failed reasoning on disk, and they are unverified and "
    "MATH-contaminated.",
    "8. THE 1,150-TRANSITION HML_V3 CORPUS IS DELIBERATELY UNREPRESENTATIVE. "
    "The goal-management block is over-sampled 27x versus LeanDojo (11.72% vs "
    "0.44%); individual combinators run 38-49x (exacts 7.7% vs 0.18%, all_goals "
    "4.4% vs 0.09%, swap 3.4% vs 0.09%). Its "
    "tactic mix must never be quoted as a fact about mathematics.",
    "9. THE MODEL ARM IS A LEXICAL PROXY, NOT AN OPERATION COUNT. Nothing on "
    "disk labels operations on model-generated steps. The detector used here "
    "was calibrated on the 769 gold spans and its precision ranges from 0.077 "
    "(EVALUATE) to 1.000 (INDUCT); 334/769 = 43.4% of gold spans fire no cue "
    "at all. Treat every column-B and column-C number as an upper-bounded "
    "surface statistic.",
    "10. ANNOTATION IS NOT VERIFICATION. Every operation label in this study "
    "was asserted by a human or by a deterministic extractor over human text. "
    "To promote any of it, each labelled step would need (a) an independent "
    "second annotator with a measured inter-annotator agreement, and (b) for "
    "the mathematical content, a machine check -- a SymPy equivalence, or a "
    "Lean replay of the corresponding formal step. Neither exists today for "
    "any of the 769.",
    "11. THE TWO FORMAL SOURCES ARE NOT INDEPENDENT. lean_canonical_records "
    "(241,265) is BUILT FROM LeanDojo Benchmark 4 v10 "
    "(source_family=LEANDOJO_BENCHMARK_4_V10). The 8-class replication "
    "reported here therefore validates the labelling function, not the "
    "generality of the vocabulary.",
]

METHOD = {
    "mode": "Read-only measurement over local artifacts. No model call, no "
            "network, no Lean, no GPU. Every count below was produced by a "
            "script in research/operations/ and can be re-run.",
    "commands": [
        "python -m research.operations.measure_annotated",
        "python -m research.operations.measure_formal",
        "python -m research.operations.measure_informal_proxy",
        "python -m research.operations.build_inventory",
    ],
    "sampling": {
        "gold125_ontology_v1": "EXACT -- all 769 s*.json records.",
        "gold_10": "EXACT -- all 23 actions in 10 files.",
        "synthetic_math": "EXACT -- all 3,978 lines.",
        "lean_canonical_241k": "EXACT -- all 241,265 lines, scanned by "
                               "line-local regex, validated against full "
                               "json.loads on the first 2,000 lines "
                               "(0 mismatches).",
        "leandojo": "random/val.json + random/test.json = 4,000 theorems, "
                    "8,766 traced tactics. These are LeanDojo's own uniformly "
                    "random theorem-level splits from the same pool as train, "
                    "so this is a random sample, not a prefix.",
        "math_reference_solutions": "EXACT -- all 12,500 problems of "
                                    "prm800k/math_splits, sentence-segmented "
                                    "into 42,963 steps.",
        "prm800k_model_steps": "SUBSAMPLE -- phase1_train + phase1_test + "
                               "phase2_test = 3,817 records, 1,359 distinct "
                               "problems, 81,908 rated model steps, 2,598 "
                               "human-written steps. phase2_train (456 MB, "
                               "97,782 records) was NOT scanned, to keep load "
                               "low during a concurrent live experiment. The "
                               "sample is therefore ~11% of the corpus and is "
                               "split-biased toward phase 1 / test.",
        "micromath_lab_v2": "EXACT -- all 611 items.",
        "hmlv3_1150": "Row count and null-field claims re-verified here "
                      "(918+232=1,150, tactic_family null in all, "
                      "recorded_effect_class null in all). The tactic-head "
                      "counts are the PRIOR AGENT's measurement, recovered "
                      "from source spans against a built mathlib tree; NOT "
                      "re-derived here.",
    },
    "effect_class_rule_recovery": "The 8-class Lean effect vocabulary is "
        "documented nowhere as a rule. It was recovered here by tabulating "
        "effect_signature -> effect_class over all 241,265 records: 198 of "
        "199 distinct signature tails map to a single class. The recovered "
        "rule reproduces 179/179 decidable tails with 0 mismatches, and the "
        "one ambiguous tail (dg-1|T0|A0|R0|B0) is resolved by "
        "n_goals_after == 0.",
}


def SOURCES(g125, ld, l241, math_ref, prm, ann, frm):
    return {
        "A_human_solutions_annotated": {
            "id": "gold125_ontology_v1",
            "path": str(P.GOLD125_ONTOLOGY),
            "n": g125["n_step_records"],
            "trust": "ANNOTATION_UNVERIFIED",
            "contamination": "Hendrycks MATH",
            "what_it_gives": "the only per-step operation labels in the estate",
        },
        "A2_hand_authored": {
            "id": "gold_10",
            "path": str(P.GOLD10),
            "n": ann["gold10"]["n_actions"],
            "distinct_operations": len(ann["gold10"]["operations"]),
            "trust": "DETERMINISTICALLY_CHECKED",
            "what_it_gives": "nothing about recurrence: 22 operation names "
                             "for 23 actions",
        },
        "A3_synthetic_informal": {
            "id": "synthetic_math_transitions",
            "path": str(P.SYNTH_TRANSITIONS),
            "n": ann["synthetic_math"]["n_transitions"],
            "trust": "DETERMINISTICALLY_CHECKED (867 SymPy-verified) / "
                     "ANNOTATION_UNVERIFIED (rest)",
            "note": "77.3% TRANSFORM. Vocabulary is a collapsed subset of "
                    "reasoning_ontology_v1.core_operation.",
        },
        "B_human_solutions_raw": {
            "id": "MATH reference solutions",
            "path": str(P.PRM800K / "math_splits"),
            "n_problems": math_ref["n_problems"],
            "n_steps": math_ref["n_steps"],
            "trust": "ANNOTATION_UNVERIFIED (no operation labels at all)",
        },
        "C_model_generated": {
            "id": "PRM800K model completions",
            "path": str(P.PRM800K / "data"),
            "n_model_steps": prm["n_model_steps_total"],
            "by_rating": prm["n_model_steps_by_rating"],
            "n_human_written_steps": prm["n_human_written_steps"],
            "trust": "ANNOTATION_UNVERIFIED; ratings are human step labels, "
                     "not operation labels",
        },
        "D_formal_representative": {
            "id": "LeanDojo Benchmark 4 v10 (random val+test)",
            "path": str(P.LEANDOJO),
            "n_theorems": ld["n_theorems"],
            "n_tactics": ld["n_tactics"],
            "distinct_heads": ld["distinct_tactic_heads"],
            "trust": "VERIFIED_FORMAL",
        },
        "D2_formal_census": {
            "id": "lean_canonical_records (lean_domino_v2)",
            "path": str(P.LEAN_241K),
            "n": l241["n_records"],
            "effect_class": l241["effect_class"],
            "trust": "VERIFIED_FORMAL substrate, deterministic labels",
            "warning": "goal-creating transitions (18,315 of 259,580) were "
                       "EXCLUDED when this corpus was built",
        },
        "D3_formal_biased": {
            "id": "HML_V3 sealed corpus",
            "n": 1150,
            "spotcheck": frm["hmlv3_1150_spotcheck"],
            "trust": "VERIFIED_FORMAL",
            "warning": "deliberately unrepresentative tactic mix",
        },
        "E_relation_probes": {
            "id": "MicroMath lab v2",
            "n": frm["micromath_lab_v2"]["n_items"],
            "stress_axes": frm["micromath_lab_v2"]["stress"],
            "trust": "DETERMINISTICALLY_CHECKED",
            "note": "NOT an operation taxonomy. It probes what a "
                    "representation exposes (TYPE, BINDER, SCOPE, PREMISE, "
                    "DEPENDENCY, ACTION_ARGUMENT, EXPRESSION_DEPTH). "
                    "MULTI_GOAL carries zero items in every split, by design "
                    "(failure-memory lesson FM-044).",
        },
    }


TAXONOMY_SUMMARY = {
    "n_taxonomies_reconciled": 13,
    "only_computed_one": "lean_effect_class_vocabulary (8 classes over "
                         "241,265 verified transitions). Every other "
                         "taxonomy in the estate was asserted, not computed.",
    "no_taxonomy_in_arena_repo": True,
    "three_kinds_of_object_conflated_across_the_13": [
        "OPERATION vocabularies (what the step does): ontology_v1 "
        "core_operation 19, gold125 registry 66, gold25 registry 48, "
        "minilang 10, master_synthetic 15",
        "EFFECT vocabularies (what changed in the state): lean_effect_class "
        "8, hmlv3_effect_class 8 (stratified, not natural)",
        "NEITHER: reasoning_stages 16 (pipeline phases), micromath relations "
        "8 (representational exposure), representation_genome 42 (design "
        "axes, RETIRED), arena_world_dimensions 12 (task difficulty), "
        "gold125_gap_registry 13 (expressibility failures)",
    ],
    "headline_disagreements": [
        "OPERATION COUNT SPREAD IS 8 to 66 with no convergence: 8 (Lean "
        "effect), 10 (minilang), 15 (master synthetic), 19 (ontology v1 "
        "core), 48 (gold25 registry), 66 (gold125 registry). These are not "
        "refinements of one another; they are counts of different things.",
        "ASSERT_SUBGOAL / HAVE: an operation in minilang, an EFFECT axis "
        "value in ontology_v1, and DELETED from the 241k Lean corpus. Yet "
        "`have` is the 4th most frequent LeanDojo tactic (6.6%).",
        "SIMPLIFY: an operation in minilang; a knowledge_layer value "
        "(SYMBOLIC_BACKEND) in ontology_v1; the largest single automation "
        "block in Lean (simp+simpa+dsimp = 1,426/8,766 = 16.27% of LeanDojo).",
        "REWRITE: absent from every informal taxonomy (folded into "
        "TRANSFORM); the single most frequent formal operation (rw family = "
        "22.34% of LeanDojo).",
        "VERIFY: first-class in ontology_v1 and both gold registries; absent "
        "from minilang and structurally impossible in Lean.",
        "The gold25 registry (48 ops) carries typed required_inputs, "
        "allowed_types, a warrant_type and an hml_rule per operation; the "
        "gold125 registry (66 ops) carries none of that but has frequencies "
        "and examples. They are not a v0/v1 pair of the same artifact; the "
        "'older' one is the richer specification.",
    ],
}


def ALIGNMENT(cal):
    return {
        "question": "For an operation that appears to recur, does the same "
                    "name mean the same thing across sources?",
        "verdict_scale": "HIGH / MEDIUM / LOW-SAME-NAME-DIFFERENT-OPERATION",
        "per_operation": [
            {
                "operation": "INDUCT", "confidence": "HIGH",
                "human_MATH": "\"Let's prove by induction that the $n$th term "
                              "of the sequence is $2^{n-2}$ ... The base case "
                              "$n=2$ holds\"",
                "formal_Lean": "`induction n with | zero => .. | succ n ih => ..`",
                "why": "Same schema (base case + step), same obligations "
                       "created, same discharge condition. The lexical proxy "
                       "is exact on the gold set: precision 1.000, recall "
                       "1.000, 7/7.",
            },
            {
                "operation": "CASE_SPLIT", "confidence": "HIGH",
                "human_MATH": "\"We can split the expression $|5x-1|=x+3$ "
                              "into two separate cases.\"",
                "formal_Lean": "`rcases le_or_lt a b with h | h`",
                "why": "Both replace one goal with an exhaustive family. "
                       "CAVEAT: the informal version additionally needs an "
                       "explicit JOIN step to combine branch results "
                       "(gold125_gap_registry MATH-GAP-0001, recurrence 22, "
                       "severity high); Lean needs none, because the goal "
                       "stack joins implicitly. So the operation matches but "
                       "its obligations do not.",
            },
            {
                "operation": "APPLY_THEOREM", "confidence": "MEDIUM",
                "human_MATH": "\"By AM-GM,\"",
                "formal_Lean": "`exact div_add_div_same a b c`",
                "why": "Same move. But in Lean the premise is named, "
                       "type-checked and its hypotheses are discharged; in "
                       "the MATH corpus 'By AM-GM' names no instance and "
                       "checks no side condition. The reasoning_ontology_v1 "
                       "warrant axis exists precisely to record this gap, and "
                       "its UNKNOWN value is used.",
            },
            {
                "operation": "CONTRADICTION", "confidence": "MEDIUM",
                "human_MATH": "\"which cannot be equal to 1, contradiction\"",
                "formal_Lean": "`by_contra h` / `exfalso`",
                "why": "Same logical shape. But the informal instances are "
                       "mostly LOCAL contradictions inside a case analysis, "
                       "while `by_contra` is a GLOBAL goal transformation. "
                       "6 gold instances is too few to separate them.",
            },
            {
                "operation": "INTRODUCE", "confidence": "MEDIUM",
                "human_MATH": "\"Let $k$ be a positive integer.\" / \"Call "
                              "the two integers $x$ and $y$.\"",
                "formal_Lean": "`intro k` / `obtain ⟨x, hx⟩ := h`",
                "why": "The informal side distinguishes DECLARE (name a "
                       "thing) from CONSTRUCT (build a witness); Lean "
                       "distinguishes intro (binder) from obtain (existential "
                       "elimination) from set/let (abbreviation). The two "
                       "three-way splits DO NOT LINE UP. The Lean effect "
                       "vocabulary collapses all of them to INTRODUCE.",
            },
            {
                "operation": "DISCHARGE",
                "confidence": "LOW-SAME-NAME-DIFFERENT-OPERATION",
                "human_MATH": "\"Thus, Brenda is $\\boxed{3}$ years old.\"",
                "formal_Lean": "effect_class CLOSE, 107,006 / 241,265",
                "why": "The informal event is 'the final answer of the whole "
                       "problem' and happens ~once per trajectory (90 times "
                       "in 125 trajectories). The formal event is 'this "
                       "branch of the goal stack is finished' and happens "
                       "44.4% of all steps. Matching them by name would "
                       "manufacture a 44%-vs-12% 'recurrence' out of two "
                       "unrelated events.",
            },
            {
                "operation": "TRANSFORM",
                "confidence": "LOW-SAME-NAME-DIFFERENT-OPERATION",
                "why": "Informal TRANSFORM is a residual sink (39.7% gold, "
                       "77.3% synthetic) covering everything from "
                       "'subtract 7 from both sides' to modular reasoning to "
                       "trig identities. Formal TRANSFORM_TARGET is a "
                       "precisely defined state delta (the focused goal's "
                       "target string changed, nothing else did). Equal "
                       "names, incomparable definitions.",
            },
            {
                "operation": "APPLY_DEFINITION",
                "confidence": "LOW-SAME-NAME-DIFFERENT-OPERATION",
                "why": "Informally an explicit, citable step (19/769). "
                       "Formally, definitional unfolding is mostly invisible: "
                       "it is performed by `simp`, `rfl` and elaboration and "
                       "never recorded. Measured formal frequency "
                       "(unfold+delta = 31/8,766 = 0.35%) is an artifact of "
                       "what Lean logs, not of what proofs do.",
            },
            {
                "operation": "SUBSTITUTE / REWRITE",
                "confidence": "LOW-SAME-NAME-DIFFERENT-OPERATION",
                "why": "Informal SUBSTITUTE (7/769 = 0.9%) means 'put the "
                       "value you derived into the other equation'. Formal "
                       "`rw` (18.91% of LeanDojo alone) means 'replace a "
                       "subterm using a directed equation, anywhere in the "
                       "goal'. The 21x frequency gap is an annotation-scheme "
                       "artifact: the informal scheme has no REWRITE, so "
                       "rewriting is filed as TRANSFORM.",
            },
        ],
        "proxy_calibration_headline": {
            "spans": cal["n_spans"],
            "spans_firing_no_cue": cal["spans_with_no_cue"],
            "spans_firing_no_cue_pct": round(
                100 * cal["spans_with_no_cue"] / cal["n_spans"], 1
            ),
            "precision_range": "0.077 (EVALUATE) to 1.000 (INDUCT)",
            "reading": "Any operation whose only cross-source evidence is the "
                       "lexical proxy, and whose proxy precision is below "
                       "~0.5, should be treated as UNMEASURED rather than as "
                       "recurring. That is: DECLARE (0.098), EVALUATE "
                       "(0.077), COUNT (0.169), SELECT (0.087), CONSTRUCT "
                       "(0.250), CASE_SPLIT (0.220), APPLY_DEFINITION "
                       "(0.333), SUBSTITUTE (0.333), BOUND (0.380).",
        },
    }


NEXT_MEASUREMENTS = [
    {
        "rank": 1,
        "measurement": "Second-annotator agreement on the 769 gold steps.",
        "corpus": "gold125_ontology_v1, all 769 records, core_operation axis.",
        "size": "769 steps; a 200-step stratified subset would already give a "
                "usable Cohen's kappa.",
        "independent_check": "A second annotator (human or a model run "
                             "blind, adjudicated by a human) labels the same "
                             "spans from the 19-value axis. Report kappa per "
                             "operation.",
        "why_it_settles_something": "Every recurrence claim in this document "
                                    "rests on one annotator's labels. Without "
                                    "kappa there is no error bar at all. It "
                                    "is also the cheapest thing on this list.",
        "cost": "hours, no GPU",
    },
    {
        "rank": 2,
        "measurement": "Machine-check the mathematical content of the 769.",
        "corpus": "the 769 gold state_delta pairs.",
        "size": "769, or the ~450 that are algebraic.",
        "independent_check": "SymPy equivalence of state_before -> state_after "
                             "for every step that is an equation "
                             "transformation, exactly as was already done for "
                             "867 of the 3,978 synthetic transitions.",
        "why_it_settles_something": "Promotes part of the corpus from "
                                    "ANNOTATION_UNVERIFIED to "
                                    "DETERMINISTICALLY_CHECKED, which is the "
                                    "only way anything in the rich corpus "
                                    "stops being an assertion. The machinery "
                                    "already exists.",
        "cost": "hours, CPU only",
    },
    {
        "rank": 3,
        "measurement": "Annotate the informal operation on aligned formal "
                       "steps.",
        "corpus": "miniF2F (500) or ProofNet-lean4 (371): both already local, "
                  "and BOTH carry a natural-language statement AND a Lean "
                  "proof of the same theorem.",
        "size": "500 theorem pairs; ~3,000 aligned steps.",
        "independent_check": "Label each Lean step with the informal "
                             "operation vocabulary, then measure how often "
                             "the informal label and the tactic head agree. "
                             "This is the ONLY way to measure alignment "
                             "directly rather than by name-matching.",
        "why_it_settles_something": "It converts every "
                                    "'LOW-SAME-NAME-DIFFERENT-OPERATION' "
                                    "verdict in this document from an "
                                    "argument into a number.",
        "cost": "days; no new data acquisition",
    },
    {
        "rank": 4,
        "measurement": "A negative-example formal corpus.",
        "corpus": "Lean replay with deliberately wrong tactics on the "
                  "existing 1,150 sealed states.",
        "size": "1,150 states x 3 distractors = 3,450 rejected steps.",
        "independent_check": "The Lean kernel itself: a rejected tactic is a "
                             "VERIFIED negative. The counterfactual "
                             "transition factory (stage100, 100 pairs) is "
                             "already a working prototype of exactly this.",
        "why_it_settles_something": "It is the only route to a corpus that is "
                                    "BOTH verified AND contains failure. "
                                    "Today verification and failure are "
                                    "disjoint across the whole estate.",
        "cost": "GPU-free but needs a Lean toolchain and a mathlib build; the "
                "build already exists on this machine.",
    },
    {
        "rank": 5,
        "measurement": "Reweight, do not resample, the 1,150 corpus.",
        "corpus": "HML_V3 sealed corpus, 1,150 transitions.",
        "size": "1,150.",
        "independent_check": "Importance weights w(head) = "
                             "p_LeanDojo(head) / p_1150(head), computed from "
                             "the 8,766-tactic representative sample measured "
                             "here.",
        "why_it_settles_something": "Makes every existing result on that "
                                    "corpus quotable without re-running the "
                                    "campaign. Costs one script.",
        "cost": "minutes",
    },
    {
        "rank": 6,
        "measurement": "Stop expecting PRM800K to yield new operations.",
        "corpus": "n/a -- this is a negative recommendation.",
        "size": "n/a",
        "independent_check": "The prior discovery pilot measured 0/1000 = "
                             "0.00% marginal semantic discovery over 858 "
                             "distinct MATH problems. The cue-firing profile "
                             "measured here is consistent with saturation: "
                             "PRM800K model steps and MATH reference "
                             "sentences fire the same cues in nearly the same "
                             "order.",
        "why_it_settles_something": "It is already settled. Budget spent "
                                    "there buys nothing.",
        "cost": "zero",
    },
]


if __name__ == "__main__":
    main()
