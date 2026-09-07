"""CANONICAL vs CONTROLLER classification, and the Lean-tactic -> operation map.

CANONICAL  = the step changes the mathematics. A mathematician reading the
             proof would name it (introduce a variable, rewrite, apply a
             theorem, split cases, discharge the goal).
CONTROLLER = the step drives the prover. It is a search, automation, goal-
             management or environment move. A mathematician would not write
             it down as a proof step; it exists because a machine is executing
             the proof.
AMBIGUOUS  = defensible either way; every one is listed and argued, not
             silently assigned.

This classification is a JUDGEMENT, not a measurement. It is stated here in
one place so it can be argued with, and every ambiguous call is flagged.
"""

from __future__ import annotations

CANONICAL = "CANONICAL"
CONTROLLER = "CONTROLLER"
AMBIGUOUS = "AMBIGUOUS"

# tactic head -> (layer, operation-or-controller-kind, note)
TACTIC_CLASS: dict[str, tuple[str, str, str]] = {}


def _add(heads: str, layer: str, op: str, note: str = "") -> None:
    for h in heads.split():
        TACTIC_CLASS[h] = (layer, op, note)


# --- canonical: introduce ----------------------------------------------------
_add("intro intros rintro introv ext ext1 funext rename_i", CANONICAL,
     "INTRODUCE_BINDER", "moves a bound variable/hypothesis into scope")
_add("have suffices replace set rsuffices tfae_have", CANONICAL,
     "ASSERT_SUBGOAL", "states a new fact and opens an obligation to prove it")
_add("obtain choose choose! lift existsi exists use", CANONICAL,
     "INTRODUCE_WITNESS", "names an object whose existence is being used or supplied")
_add("let", CANONICAL, "DECLARE",
     "introduces a definitional abbreviation into the context")

# --- canonical: rewrite / substitute ----------------------------------------
_add("rw rewrite erw rwa simp_rw nth_rw nth_rewrite", CANONICAL,
     "REWRITE", "directed equational replacement using a named equation")
_add("subst substs subst_vars", CANONICAL, "SUBSTITUTE",
     "eliminates a variable by an equation")
_add("change show delta unfold refold_let conv conv_lhs conv_rhs "
     "slice_lhs slice_rhs convert_to", CANONICAL, "TRANSFORM_TARGET",
     "restates the goal in an equal or definitionally-equal form")
_add("apply_fun", CANONICAL, "TRANSFORM_TARGET",
     "applies a function to both sides")

# --- canonical: apply --------------------------------------------------------
_add("exact exacts apply refine refine' exact_mod_cast apply_mod_cast "
     "linear_combination specialize trans symm calc", CANONICAL,
     "APPLY_THEOREM", "closes or reduces the goal by a named result")
_add("constructor fconstructor left right injection", CANONICAL,
     "APPLY_CONSTRUCTOR", "structural introduction/elimination of a connective")
_add("congr congr! convert", CANONICAL, "CONGRUENCE",
     "reduces an equality of applications to equalities of arguments")

# --- canonical: case split / induction ---------------------------------------
_add("cases cases' rcases by_cases split split_ifs match fin_cases", CANONICAL,
     "CASE_SPLIT", "replaces one goal by an exhaustive family of goals")
_add("induction induction'", CANONICAL, "INDUCT",
     "structural or well-founded induction")
_add("wlog", CANONICAL, "CASE_SPLIT",
     "symmetry reduction; opens a reduction obligation")

# --- canonical: contradiction ------------------------------------------------
_add("by_contra by_contra! exfalso contradiction contrapose contrapose! "
     "push_neg absurd", CANONICAL, "CONTRADICTION",
     "argues from the negation of the goal")

# --- canonical: scope --------------------------------------------------------
_add("clear revert clear_value generalize", CANONICAL, "SCOPE_CHANGE",
     "removes or re-abstracts something from the local context")

# --- canonical: discharge by evaluation --------------------------------------
_add("rfl ac_rfl trivial assumption assumption'", CANONICAL, "DISCHARGE",
     "closes the goal by definitional equality or a hypothesis already present")

# --- controller: automation / decision procedures ---------------------------
_add("simp simpa dsimp simp_all simp? simp_arith norm_num norm_num1 "
     "norm_cast push_cast field_simp ring ring1 ring_nf linarith nlinarith "
     "positivity omega decide tauto aesop aesop_cat abel abel1 group "
     "polyrith coherence mfld_set_tac fun_prop eval_simp gcongr "
     "witt_truncateFun_tac tfae_finish solve_by_elim apply_rules "
     "filter_upwards subst_hom_lift", CONTROLLER, "AUTOMATION",
     "a search or normalisation procedure; the specific mathematics it does "
     "is not recoverable from the tactic name")

# --- controller: goal management --------------------------------------------
_add("all_goals any_goals swap on_goal focus next case pick_goal rotate_left "
     "iterate repeat repeat' try first", CONTROLLER, "GOAL_MANAGEMENT",
     "reorders, selects or replicates work over the goal stack; changes no "
     "mathematical content")

# --- controller: environment -------------------------------------------------
_add("classical infer_instance haveI letI set_option borelize nontriviality "
     "inhabit isBoundedDefault open", CONTROLLER, "ENVIRONMENT",
     "typeclass / elaborator plumbing")

# --- explicitly contested calls ---------------------------------------------
AMBIGUOUS_CALLS = {
    "simp": "By far the largest single head (13% of LeanDojo). Classified "
            "CONTROLLER because the tactic name does not say which lemmas "
            "fired; but a large fraction of `simp` calls are doing what a "
            "human would call 'simplify' or 'apply a definition'. This one "
            "call moves ~13 points of mass between the two layers.",
    "have": "Classified CANONICAL (ASSERT_SUBGOAL). It is also the main "
            "vehicle for search-driven forward chaining, i.e. controller "
            "behaviour with canonical form.",
    "gcongr": "Congruence automation. CANONICAL content, CONTROLLER form.",
    "filter_upwards": "A Mathlib domain macro that also introduces binders.",
    "haveI letI": "Instance introduction: CANONICAL syntax, plumbing purpose.",
    "linarith positivity omega decide": "These discharge real mathematical "
            "obligations (an inequality, a decidable proposition). Classified "
            "CONTROLLER because the proof object is produced by search, not "
            "named by the author.",
    "rfl": "Classified CANONICAL DISCHARGE, but `rfl` also silently runs "
           "definitional unfolding of unbounded depth.",
}


def classify_head(head: str) -> tuple[str, str, str]:
    return TACTIC_CLASS.get(head, ("UNCLASSIFIED", "UNKNOWN", ""))


# ---------------------------------------------------------------------------
# The reconciled operation inventory.
#
# `sources` names the taxonomies that contain the operation (or an operation
# that plainly denotes the same move). `disagreements` records where two
# taxonomies do NOT agree, rather than merging them silently.
# ---------------------------------------------------------------------------

RECONCILED: list[dict] = [
    {
        "operation": "DECLARE",
        "layer": CANONICAL,
        "definition": "Introduce a new named object or abbreviation into the "
                      "state without asserting anything about it.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "DECLARE",
            "gold125_registry_v1": "INTRODUCE_VARIABLE",
            "gold25_registry_v0": "INTRODUCE_VARIABLE",
            "minilang (arXiv:2507.18885)": "INTRO (partly)",
            "lean_effect_class": "INTRODUCE (partly)",
            "reasoning_stages": "2 symbol/object identification",
        },
        "disagreements": [
            "reasoning_ontology_v1 separates DECLARE (name an object) from "
            "CONSTRUCT (build an object with properties); the gold125 registry "
            "has only INTRODUCE_VARIABLE and does not make the distinction.",
            "The Lean effect vocabulary cannot separate DECLARE from "
            "INTRODUCE_WITNESS or INTRODUCE_BINDER: all three are INTRODUCE.",
        ],
    },
    {
        "operation": "CONSTRUCT",
        "layer": CANONICAL,
        "definition": "Build a new mathematical object, witness or "
                      "configuration and put it in the state.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "CONSTRUCT",
            "gold125_registry_v1": "CONSTRUCT",
            "gold25_registry_v0": "CONSTRUCT",
            "minilang": "CHOOSE / CONSIDER_EXISTS",
            "lean_effect_class": "INTRODUCE",
        },
        "disagreements": [
            "minilang splits witness selection (CHOOSE) from existential "
            "elimination (CONSIDER_EXISTS); no HML taxonomy does.",
        ],
    },
    {
        "operation": "ASSERT_SUBGOAL",
        "layer": CANONICAL,
        "definition": "State a new proposition and open the obligation to "
                      "prove it (forward chaining).",
        "in_taxonomies": {
            "reasoning_ontology_v1": "goal_effect=CREATE_SUBGOAL (an EFFECT "
                                     "axis value, not a core_operation)",
            "gold125_registry_v1": "-- absent",
            "minilang": "HAVE",
            "lean_effect_class": "-- absent (goal-creating transitions were "
                                 "EXCLUDED from the 241,265-record corpus)",
            "reasoning_stages": "9 subgoal decomposition",
        },
        "disagreements": [
            "THIS IS THE CLEAREST TAXONOMY DISAGREEMENT IN THE ESTATE. "
            "minilang makes HAVE one of its 10 operations; "
            "reasoning_ontology_v1 demotes it to an effect on an orthogonal "
            "axis; and the Lean corpus deletes the phenomenon entirely "
            "(18,315 of 259,580 transitions dropped as goal-creating). "
            "`have` is nevertheless the 4th most frequent tactic in LeanDojo.",
        ],
    },
    {
        "operation": "SUBSTITUTE",
        "layer": CANONICAL,
        "definition": "Replace an occurrence by an equal term, or eliminate a "
                      "variable using an equation.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "SUBSTITUTE",
            "gold125_registry_v1": "SUBSTITUTE",
            "gold25_registry_v0": "SUBSTITUTE",
            "lean tactic heads": "subst, substs, subst_vars",
            "master_synthetic": "SUBSTITUTE",
        },
        "disagreements": [
            "Informal SUBSTITUTE covers what Lean splits into `subst` "
            "(variable elimination) and `rw` (directed rewriting). The "
            "informal taxonomies have no REWRITE at all, yet `rw` is the "
            "single most frequent formal operation (rw alone = 18.91% of "
            "LeanDojo).",
        ],
    },
    {
        "operation": "REWRITE",
        "layer": CANONICAL,
        "definition": "Directed replacement of a subterm using a named "
                      "equation or iff, left-to-right or right-to-left.",
        "in_taxonomies": {
            "reasoning_ontology_v1": "-- absent (collapsed into TRANSFORM)",
            "gold125_registry_v1": "APPLY_IDENTITY (partly)",
            "lean tactic heads": "rw, erw, rwa, simp_rw, nth_rw, rewrite",
            "lean_effect_class": "TRANSFORM_TARGET / REWRITE_CONTEXT",
        },
        "disagreements": [
            "A first-class formal operation with no first-class informal "
            "counterpart. This is an annotation-scheme artifact, not a domain "
            "difference: human MATH solutions rewrite constantly, but the "
            "informal registries fold it into TRANSFORM.",
        ],
    },
    {
        "operation": "TRANSFORM",
        "layer": CANONICAL,
        "definition": "Any truth-preserving restatement of the current "
                      "expression or goal.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "TRANSFORM",
            "gold125_registry_v1": "TRANSFORM plus ~20 domain-specific "
                                   "children (EXPAND, FACTOR, CROSS_MULTIPLY, "
                                   "CLEAR_DENOMINATOR, ADD_BOTH_SIDES, ...)",
            "gold25_registry_v0": "family EQUATION_TRANSFORMATION",
            "lean_effect_class": "TRANSFORM_TARGET",
            "master_synthetic": "TRANSFORM (77% of all transitions)",
        },
        "disagreements": [
            "TRANSFORM is a sink. It absorbs 305/769 (39.7%) of the annotated "
            "gold corpus and 3,074/3,978 (77.3%) of the synthetic corpus. Any "
            "claim that it 'recurs' is close to vacuous.",
        ],
    },
    {
        "operation": "APPLY_THEOREM",
        "layer": CANONICAL,
        "definition": "Discharge or reduce the goal by invoking a named "
                      "external result.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "APPLY_THEOREM",
            "gold125_registry_v1": "APPLY_THEOREM",
            "gold25_registry_v0": "APPLY_THEOREM",
            "minilang": "RULE",
            "lean tactic heads": "exact, apply, refine, exacts",
            "master_synthetic": "APPLY_THEOREM",
        },
        "disagreements": [
            "In Lean the premise is always named and machine-checked; in the "
            "informal corpora the warrant field may be UNKNOWN. Same name, "
            "different epistemic status.",
        ],
    },
    {
        "operation": "APPLY_DEFINITION",
        "layer": CANONICAL,
        "definition": "Unfold or invoke a definition.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "APPLY_DEFINITION",
            "gold125_registry_v1": "APPLY_DEFINITION",
            "lean tactic heads": "unfold, delta, change, show, dsimp",
            "master_synthetic": "APPLY_DEFINITION (9 / 3,978)",
        },
        "disagreements": [
            "In Lean, definitional unfolding is mostly INVISIBLE: it happens "
            "inside `simp`, `rfl` and elaboration. Its measured formal "
            "frequency (unfold+delta = 31/8,766 = 0.35%) is therefore a "
            "severe undercount, not a real rarity.",
        ],
    },
    {
        "operation": "CASE_SPLIT",
        "layer": CANONICAL,
        "definition": "Replace one goal by an exhaustive family of goals.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "CASE_SPLIT",
            "gold125_registry_v1": "CASE_SPLIT, SOLVE_CASE, COMBINE_CASES, "
                                   "COUNT_CASES, COMBINE_CASE_COUNTS",
            "gold25_registry_v0": "CASE_SPLIT",
            "minilang": "CASE_SPLIT / CONSIDER_OR",
            "lean tactic heads": "cases, rcases, by_cases, split_ifs",
            "master_synthetic": "CASE_SPLIT",
            "gold125_gap_registry": "MATH-GAP-0001 'Case coverage and branch "
                                    "joins', severity high, recurrence 22",
        },
        "disagreements": [
            "The informal registries also need a JOIN (combine the branch "
            "results); Lean needs no join, because the goal stack does it. "
            "gold125_gap_registry records this as an unrepresentable gap.",
        ],
    },
    {
        "operation": "INDUCT",
        "layer": CANONICAL,
        "definition": "Structural or well-founded induction.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "INDUCT",
            "gold125_registry_v1": "INDUCT",
            "minilang": "INDUCT",
            "lean tactic heads": "induction, induction'",
            "master_synthetic": "INDUCT (4 / 3,978)",
        },
        "disagreements": [],
    },
    {
        "operation": "CONTRADICTION",
        "layer": CANONICAL,
        "definition": "Argue from the negation of the goal, or derive a "
                      "falsehood.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "CONTRADICTION",
            "gold125_registry_v1": "CONTRADICTION",
            "minilang": "-- absent",
            "lean tactic heads": "by_contra, exfalso, contrapose!, push_neg",
            "master_synthetic": "CONTRADICTION (2 / 3,978)",
        },
        "disagreements": [
            "minilang has no contradiction operation at all; it is folded "
            "into RULE.",
        ],
    },
    {
        "operation": "DISCHARGE",
        "layer": CANONICAL,
        "definition": "Close the current goal.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "DISCHARGE",
            "gold125_registry_v1": "DISCHARGE, DISCHARGE_GOAL",
            "minilang": "END_OR_NEXT",
            "lean_effect_class": "CLOSE (44.4% of 241,265)",
            "reasoning_stages": "16 termination/goal discharge",
        },
        "disagreements": [
            "In the informal corpora DISCHARGE means 'here is the final "
            "answer' (90/769, and 89/90 of those contain \\boxed{}). In Lean "
            "CLOSE means 'this branch of the goal stack is finished' and "
            "happens 107,006 times. The two are not the same event.",
        ],
    },
    {
        "operation": "VERIFY",
        "layer": CANONICAL,
        "definition": "Check a candidate result against a constraint already "
                      "in the state.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "VERIFY",
            "gold125_registry_v1": "VERIFY, VERIFY_CANDIDATE",
            "gold25_registry_v0": "VERIFY",
            "minilang": "-- absent",
            "lean tactic heads": "-- ABSENT BY CONSTRUCTION",
        },
        "disagreements": [
            "VERIFY has NO formal counterpart and cannot have one: in a proof "
            "assistant the kernel verifies, so verification never appears as "
            "a step. This is a genuine domain difference, not an artifact.",
        ],
    },
    {
        "operation": "EVALUATE / COUNT / BOUND / ENUMERATE / SELECT",
        "layer": CANONICAL,
        "definition": "Numeric evaluation; cardinality computation; "
                      "establishing an inequality; listing a finite family; "
                      "choosing among candidates.",
        "in_taxonomies": {
            "reasoning_ontology_v1.core_operation": "EVALUATE, COUNT, BOUND, "
                                                    "ENUMERATE, SELECT",
            "gold125_registry_v1": "~25 of the 66 entries",
            "lean tactic heads": "norm_num, decide, positivity, linarith "
                                 "(all CONTROLLER-classified)",
        },
        "disagreements": [
            "These five are first-class in every informal taxonomy and have "
            "no first-class formal counterpart: in Lean they are absorbed by "
            "automation. The clean statement is that they map to CONTROLLER "
            "tactics, not to canonical ones.",
        ],
    },
    {
        "operation": "GOAL_MANAGEMENT",
        "layer": CONTROLLER,
        "definition": "Reorder, select or replicate work across the goal "
                      "stack.",
        "in_taxonomies": {
            "reasoning_ontology_v1": "reasoning_mode=GOAL_MANAGEMENT",
            "lean tactic heads": "all_goals, any_goals, swap, on_goal, case, "
                                 "focus, next, iterate",
        },
        "disagreements": [
            "Present as a MODE in the informal ontology and as concrete "
            "TACTICS in Lean, but never as an operation in either. It is "
            "0.44% of LeanDojo and 11.72% of the HML_V3 1,150 corpus, purely "
            "because that corpus was sampled for multi-goal states.",
        ],
    },
    {
        "operation": "AUTOMATION",
        "layer": CONTROLLER,
        "definition": "Invoke a search or normalisation procedure whose "
                      "internal steps are not recorded.",
        "in_taxonomies": {
            "reasoning_ontology_v1": "knowledge_layer=SYMBOLIC_BACKEND / "
                                     "NUMERIC_BACKEND",
            "minilang": "SIMPLIFY",
            "lean tactic heads": "simp, simpa, dsimp, ring, linarith, "
                                 "norm_num, omega, aesop, field_simp, ...",
        },
        "disagreements": [
            "minilang gives SIMPLIFY operation status; reasoning_ontology_v1 "
            "puts it on the knowledge_layer axis instead. This is the second "
            "clear taxonomy disagreement.",
        ],
    },
    {
        "operation": "SEARCH_META / PLAN",
        "layer": CONTROLLER,
        "definition": "Announce or revise a strategy without changing the "
                      "mathematical state.",
        "in_taxonomies": {
            "reasoning_ontology_v1": "reasoning_mode=SEARCH_META",
            "gold125_registry_v1": "SEARCH_META, BOUND_SEARCH",
            "lean": "-- absent by construction (a trace holds only kept "
                    "steps)",
        },
        "disagreements": [
            "Dominant in model-generated chains (PLAN cue fires on 11.8% of "
            "81,908 PRM800K model steps) and essentially invisible in both "
            "the annotated MATH corpus and every formal corpus.",
        ],
    },
    {
        "operation": "BACKTRACK",
        "layer": CONTROLLER,
        "definition": "Abandon a line of work and resume from an earlier "
                      "state.",
        "in_taxonomies": {
            "reasoning_ontology_v1": "epistemic_effect=REJECT_CANDIDATE",
            "lean": "-- ABSENT BY CONSTRUCTION. A Lean trace records only "
                    "steps that were kept.",
            "PRM800K": "the only large source: 262,146 steps rated -1",
        },
        "disagreements": [
            "No formal corpus on disk contains a single backtracking step. "
            "This is a hard structural limit on any cross-source claim about "
            "failure or revision.",
        ],
    },
]
