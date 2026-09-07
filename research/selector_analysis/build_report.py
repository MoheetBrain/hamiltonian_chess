"""Assemble artifacts/reports/v5_selector_analysis.json.

EXPLORATORY / POST-HOC INSTRUMENT-PROPERTY ANALYSIS. Not a re-scoring of V5.
No model call is made. No frozen artifact is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "artifacts/reports/v5_selector_analysis.json"

LABEL = "EXPLORATORY_POST_HOC_INSTRUMENT_PROPERTY_ANALYSIS"
DISCLAIMER = (
    "EXPLORATORY AND POST-HOC. This analysis measures a property of the FROZEN V5 "
    "instrument's frontier-selection rule. It MUST NOT be used to re-score V5, to "
    "reinterpret any V5 verdict, to select a different level for any mechanism, or to "
    "promote any representation. V5's recorded sentinel "
    "CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT and its artifact "
    "(sha256 0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579) stand "
    "unchanged. No representation was ever scored under V5; only the control candidate "
    "V5E_L3_JSON_AST was measured. Zero model calls were made by this analysis."
)


def implementation_verification(frozen: dict[str, Any]) -> dict[str, Any]:
    dc = frozen["destroyed_control_verification"]
    return {
        "method": "source read as TEXT; arena.experiments.fitness_v5 was never imported or executed",
        "selector_as_implemented": {
            "file": "arena/experiments/fitness_v5.py",
            "function": "select_frontier_level",
            "lines": "915-948",
            "evidence": [
                {
                    "line": 213,
                    "code": '"frontier_target": 0.625,',
                },
                {
                    "line": 214,
                    "code": '"frontier_band": [0.35, 0.85],',
                },
                {
                    "lines": "931-933",
                    "code": (
                        "level, accuracy = min(\n"
                        "    candidates, key=lambda item: "
                        "(abs(item[1] - float(rule['frontier_target'])), item[0])\n)"
                    ),
                    "note": (
                        "candidates are the sorted levels >= 1; the (distance, level) key with "
                        "min() over an ascending list reproduces 'ties to the lower level'."
                    ),
                },
                {
                    "lines": "934-940",
                    "code": (
                        "verdict = ('VOID_CEILING' if accuracy > high else "
                        "'VOID_FLOOR' if accuracy < low else 'FRONTIER_SELECTED')"
                    ),
                },
            ],
            "matches_spec_section_5_2": True,
            "reproduced_on_frozen_data_for_all_3_mechanisms": all(
                block["selection_reproduced"] for block in frozen["grid"].values()
            ),
        },
        "qualification_gate_as_implemented": {
            "file": "arena/experiments/fitness_v5.py",
            "function": "qualify_mechanism",
            "lines": "951-985",
            "evidence": [
                {
                    "lines": "966-971",
                    "code": (
                        '"negative_collapse": ("PASS"\n'
                        "    if summary['positive_negative_gap'] >= "
                        "float(rule['positive_negative_gap_min'])\n"
                        "    and summary['negative_target_accuracy'] <= "
                        "float(rule['negative_target_accuracy_max'])\n"
                        "    else 'VOID_NEGATIVE_CONTROL')"
                    ),
                },
                {"line": 219, "code": '"positive_negative_gap_min": 0.20,'},
                {"line": 220, "code": '"negative_target_accuracy_max": 0.60,'},
                {
                    "line": 701,
                    "code": '"positive_negative_gap": positive - negative_acc,',
                    "note": "in summarize(); the gap is a plain difference of the two accuracies",
                },
            ],
            "matches_spec_section_5_3": True,
        },
        "destroyed_control_is_a_structural_constant": {
            "claim": "CONFIRMED",
            "construction_evidence": [
                {
                    "file": "arena/experiments/fitness_v5.py",
                    "lines": "485-486",
                    "code": (
                        "make(V5Variant.DESTROYED_ORIGINAL, destroyed, 0, 'NEGATIVE_CONTROL_TARGET'),\n"
                        "make(V5Variant.DESTROYED_COUNTERFACTUAL, destroyed, 1, "
                        "'NEGATIVE_CONTROL_TARGET'),"
                    ),
                    "note": (
                        "the SAME `destroyed` CanonicalState object and the SAME default `options` "
                        "tuple are passed to both siblings; only expected_index differs (0 vs 1)."
                    ),
                },
                {
                    "file": "arena/experiments/fitness_v5.py",
                    "lines": "505-509",
                    "code": (
                        "if a.state.mathematical_hash != b.state.mathematical_hash or "
                        "a.options != b.options:\n"
                        "    raise ValueError('V5 negative siblings are not information-identical')\n"
                        "if a.expected_index == b.expected_index:\n"
                        "    raise ValueError('V5 negative targets are not balanced')"
                    ),
                    "note": "identity and opposite-target are ASSERTED at construction, per family.",
                },
                {
                    "file": "arena/experiments/fitness_v5.py",
                    "lines": "550-565",
                    "function": "build_prompt",
                    "note": (
                        "the prompt is a pure function of (genome, probe.question, probe.state, "
                        "probe.options). Neither `variant` nor `expected_index` reaches the prompt, "
                        "so the two destroyed siblings send byte-identical prompts."
                    ),
                },
                {
                    "file": "arena/environments/formal_structural.py",
                    "lines": "204-219",
                    "function": "destroy_depth_relation",
                    "note": (
                        "both identifiers are placed at identical depth, so the question has no "
                        "structural answer: content preserved, relation removed."
                    ),
                },
            ],
            "empirical_verification_on_frozen_rows": dc,
            "arithmetic": (
                "A deterministic solver returns one answer to the shared prompt. That answer "
                "matches exactly one of the two opposite targets, so each twin pair contributes "
                "exactly 1 correct of 2. Over any number of families the destroyed accuracy is "
                "exactly 0.5000."
            ),
            "contingencies": [
                "Requires solver determinism (temperature 0, fixed seed). Held: all 24 twin "
                "pairs across the two measured cells (12 + 12) produced byte-identical prompt "
                "hashes AND byte-identical raw output, 24 correct of 48 rows.",
                "Requires a valid parse on both twins. An unparsed row scores INCORRECT rather "
                "than voiding, so an invalid destroyed row pushes destroyed accuracy BELOW 0.5, "
                "never above. Held: valid_response_rate 1.000 everywhere in Phase 5.",
                "Therefore destroyed <= 0.5 always, with equality under determinism + validity.",
            ],
        },
        "effective_qualifying_window": {
            "derivation": (
                "gap = positive - destroyed >= 0.20 with destroyed == 0.5000 <=> positive >= 0.70. "
                "The frontier ceiling caps positive at 0.85. Hence the qualifying window on "
                "positive accuracy is [0.70, 0.85], not the documented band [0.35, 0.85]."
            ),
            "window": [0.70, 0.85],
            "window_midpoint": 0.775,
            "selector_target": 0.625,
            "selector_target_inside_window": False,
            "selector_target_distance_below_window_floor": 0.075,
            "dead_gate": (
                "`negative_target_accuracy <= 0.60` is unconditionally satisfied because "
                "destroyed <= 0.5000 always. It carries zero information and cannot fire."
            ),
        },
        "defect_provenance": {
            "finding": (
                "The incoherence was introduced by a single uncoordinated constant edit between "
                "V4 and V5, not by a deliberate design choice."
            ),
            "v3": {
                "file": "arena/experiments/fitness_v3.py",
                "lines": "56, 61",
                "positive_negative_gap_min": 0.10,
                "frontier_target": 0.625,
            },
            "v4": {
                "file": "arena/experiments/fitness_v4.py",
                "lines": "143, 148, 152",
                "positive_negative_gap_min": 0.10,
                "frontier_target": 0.625,
                "frontier_band": [0.35, 0.85],
                "destroyed_twins_information_identical": "asserted at fitness_v4.py:1001-1013",
            },
            "v5": {
                "file": "arena/experiments/fitness_v5.py",
                "lines": "213, 214, 219",
                "positive_negative_gap_min": 0.20,
                "frontier_target": 0.625,
                "frontier_band": [0.35, 0.85],
            },
            "implication": (
                "Under V3/V4 the gap threshold of 0.10 implied a window of [0.60, 0.85] and the "
                "0.625 target sat INSIDE it (0.025 above the floor), so the selector was coherent. "
                "V5 raised the gap to 0.20 (justified in FITNESS_V5_SPEC.md section 5 by the gap's "
                "standard error of 0.142) and left the frontier target at 0.625. That single edit "
                "moved the window floor from 0.60 to 0.70 and stranded the selector's aim point "
                "0.075 below the region it must land in."
            ),
        },
        "verdict": (
            "The premise is CONFIRMED as an arithmetic and design fact. The frozen selector "
            "targets 0.625, which the implementation's own gates make unqualifiable. A mechanism "
            "whose ladder happens to contain a level near 0.625 is voided with probability "
            "approaching 1, by construction."
        ),
    }


def main() -> dict[str, Any]:
    frozen = json.loads((HERE / "frozen_ladder_analysis.json").read_text())
    sim = json.loads((HERE / "selector_simulation.json").read_text())

    # ---- compact per-mechanism x per-level gate matrix
    matrix: dict[str, Any] = {}
    any_level_passes = False
    for mechanism, block in frozen["grid"].items():
        levels = {}
        for lvl, cell in sorted(block["levels"].items()):
            levels[f"L{lvl}"] = {
                "parameters": cell["parameters"],
                "n_positive": cell["n_positive"],
                "positive_accuracy": cell["positive_accuracy"],
                "destroyed_accuracy": cell["destroyed_accuracy"],
                "destroyed_accuracy_source": cell["destroyed_accuracy_source"],
                "positive_negative_gap": cell["positive_negative_gap"],
                "largest_answer_share": cell["largest_answer_share"],
                "position_invariance": cell["position_invariance"],
                "shortcut_status": cell["shortcut_status"],
                "valid_response_rate": cell["valid_response_rate"],
                "mean_prompt_tokens": cell["mean_prompt_tokens"],
                "checks": cell["checks"],
                "binding_failures": cell["binding_failures"],
                "unmeasured_gates": cell["unmeasured_gates"],
                "status": cell["status"],
            }
        passing = block["levels_passing_every_measured_gate"]
        any_level_passes = any_level_passes or bool(passing)
        matrix[mechanism] = {
            "explicit_positive_L0": block["explicit_positive_accuracy_L0"],
            "explicit_positive_gate": block["explicit_positive_gate"],
            "frozen_selector_choice": block["recorded_selection"],
            "frozen_selector_reproduced_by_this_analysis": block["selection_reproduced"],
            "frozen_recorded_verdict": block["recorded_verdict"],
            "levels": levels,
            "levels_L1_L3_passing_every_measured_gate": passing,
        }

    cf = sim["frozen_phase5_counterfactual"]
    sens = sim["sensitivity_summary"]

    return {
        "analysis_class": LABEL,
        "disclaimer": DISCLAIMER,
        "generated_by": [
            "research/selector_analysis/frozen_ladder_analysis.py",
            "research/selector_analysis/selector_simulation.py",
            "research/selector_analysis/build_report.py",
        ],
        "model_calls_made": 0,
        "frozen_inputs": {
            "artifact": frozen["artifact"],
            "artifact_sha256": frozen["artifact_sha256"],
            "artifact_sha256_matches_frozen_value": frozen["artifact_sha256_matches_frozen"],
            "artifacts_modified": [],
        },
        "1_implementation_verification": implementation_verification(frozen),
        "2_frozen_phase5_gate_matrix": {
            "framing": (
                "POST-HOC re-analysis of already-collected rows. The ladder scan evaluated only "
                "the ORIGINAL and COUNTERFACTUAL (positive) arms at every level; the destroyed "
                "and swapped arms and the shortcut audit ran ONLY at the selected frontier "
                "(fitness_v5.py:1050 for the ladder scan; :1070-1075 for the single full-family evaluation at the selected level). Off-frontier destroyed accuracy is therefore IMPUTED "
                "at the structural constant 0.5000 and off-frontier position invariance and "
                "shortcut status are UNMEASURED. They cannot be recovered without new model "
                "calls, which were not made."
            ),
            "matrix": matrix,
            "central_question": (
                "Is there ANY level in the frozen ladder that satisfies every gate simultaneously?"
            ),
            "answer": "NO",
            "answer_detail": (
                "No level of any mechanism passes. Only ONE of the nine (mechanism x L1..L3) cells "
                "in the entire frozen ladder has a positive accuracy inside the effective window "
                "[0.70, 0.85]: precondition_conjunction L1 at 0.7083 - and the frozen selector "
                "already chose exactly that cell, where the binding failure was the answer-share "
                "gate (0.7917 > 0.75), not the gap. Every other cell is either above the 0.85 "
                "ceiling (formal_expression_depth L1 = 0.8750, transitive_dependency L1 = 0.9167) "
                "or below the 0.70 floor (0.5417, 0.5417, 0.5000, 0.5000, 0.6667, 0.5000). "
                "transitive_dependency is additionally dead at L0 (0.8750 < 0.90). Because the "
                "positive-accuracy gate alone excludes every non-selected level, the unmeasured "
                "off-frontier gates cannot change this answer."
            ),
            "cells_inside_effective_window": [
                {"mechanism": "precondition_conjunction", "level": 1, "positive_accuracy": 0.7083333333333334}
            ],
            "any_level_passes_every_measured_gate": any_level_passes,
            "selector_cost_in_phase_5": 0.0,
            "selector_cost_note": (
                "The selector's theoretical defect cost Phase 5 NOTHING. The only in-window cell "
                "that existed was the one the frozen selector picked."
            ),
        },
        "3_simulated_operating_characteristics": {
            "framing": (
                "Explicit generative model, described in research/selector_analysis/"
                "selector_simulation.py. n = 24 positives per level (12 ORIGINAL + 12 "
                "COUNTERFACTUAL, balanced targets), independent-error binary forced choice, "
                "destroyed control fixed at the structural constant 0.5000, 20,000 replicates "
                "per profile (200,000 per null), 44 profiles sweeping (p at L1) x (decay rate). "
                "Q0, valid rate, truncation and the shortcut audit are assumed PASS and are not "
                "simulated; the shortcut audit is a probe-set property and is identical across "
                "selectors."
            ),
            "selectors": {
                "current_target_0.625": "the frozen rule: argmin |acc - 0.625| over L1..L3",
                "window_midpoint_0.775": "same rule aimed at the midpoint of the effective window",
                "highest_qualifying": "deepest level that passes every gate; selects on the outcome",
                "midpoint_0.80_gap0.25_calibrated": (
                    "aims at 0.80 and raises the gap to 0.25 (i.e. accuracy >= 0.75) so that its "
                    "coin-flipper false-positive rate matches the current selector's"
                ),
                "oracle_knows_true_p": (
                    "SENSITIVITY CEILING, not a proposal: picks the level whose TRUE accuracy is "
                    "nearest the window midpoint, then applies the ordinary observed-data gates. "
                    "Any real selector scoring above this is harvesting sampling noise."
                ),
            },
            "effective_window": sim["effective_positive_accuracy_window"],
            "window_width_in_standard_errors_at_n24": sim["window_width_in_standard_errors_at_n24"],
            "sensitivity_mean_P_qualified_given_a_true_in_window_level": sens[
                "mean_p_qualified_given_true_band"
            ],
            "P_qualified_when_no_true_in_window_level_exists": sens[
                "mean_p_qualified_no_true_band"
            ],
            "sensitivity_loss_attributable_to_the_selector": {
                "current_vs_window_midpoint": round(
                    sens["mean_p_qualified_given_true_band"]["window_midpoint_0.775"]
                    - sens["mean_p_qualified_given_true_band"]["current_target_0.625"],
                    4,
                ),
                "current_vs_oracle_ceiling": round(
                    sens["mean_p_qualified_given_true_band"]["oracle_knows_true_p"]
                    - sens["mean_p_qualified_given_true_band"]["current_target_0.625"],
                    4,
                ),
                "interpretation": (
                    "Against the achievable ceiling (a selector with perfect knowledge of the true "
                    "profile) the frozen selector forfeits about 0.31 of absolute sensitivity - "
                    "roughly 55% of the detectable cases. The naive fixes recover MORE than the "
                    "ceiling, which is the tell that they are buying sensitivity from noise."
                ),
            },
            "worst_single_profile_for_the_current_selector": sens[
                "max_sensitivity_gain_over_current"
            ],
            "false_positive_rates": {
                label: row["p_qualified"] for label, row in sim["false_positive_nulls"].items()
            },
            "false_positive_reading": (
                "Strict nulls are well controlled by every selector: a constant answerer is "
                "rejected with probability 1 by the answer-share gate at every selector (share "
                "1.000 > 0.75), and a coin-flipper that can still pass the explicit L0 arm is "
                "accepted 0.021 (current), 0.054 (window midpoint), 0.055 (highest-qualifying), "
                "0.020 (calibrated). The decisive case is the NEAR-null: a genuine reader whose "
                "true accuracy is 0.65 flat - below the window floor - is accepted 0.074 "
                "(current), 0.533 (window midpoint), 0.587 (highest-qualifying), 0.360 "
                "(calibrated), 0.254 (oracle). Simply re-aiming the selector at 0.775 therefore "
                "buys 0.45 of sensitivity at the price of a 7x increase in near-threshold false "
                "positives. That is not an acceptable trade at n = 24."
            ),
            "where_the_selectors_agree": (
                "Per-profile agreement between the current and window-midpoint selectors is "
                "recorded in research/selector_analysis/selector_simulation.json under "
                "sweep[].selector_agreement_same_level / _same_verdict. They agree exactly when "
                "the ladder has no level between 0.625 and the window, which is the common case "
                "for steeply declining profiles and for profiles entirely below 0.625."
            ),
            "deeper_finding": (
                "The effective window [0.70, 0.85] is only "
                f"{sim['window_width_in_standard_errors_at_n24']} standard errors wide at n = 24. "
                "No selection rule can be simultaneously sensitive and specific against a target "
                "that narrow. Even a selector with perfect knowledge of the true profile qualifies "
                "a genuinely-in-band mechanism only 0.564 of the time and accepts a true-0.65 "
                "reader 0.254 of the time. The sample size, not the aim point, is the dominant "
                "limitation; the aim point is a real but second-order defect on top of it."
            ),
            "frozen_phase5_counterfactual": cf,
        },
        "4_phase_6_implications": {
            "status": "ANALYSIS ONLY. No Phase-6 artifact was read for modification or written.",
            "primary_endpoint": (
                "paired exact McNemar on a degeneracy indicator (does the solver's answer equal "
                "solver A's modal answer) pooled over three FIXED cells - precondition_conjunction "
                "L2 and L3, transitive_dependency L3 - n = 72 "
                "(docs/PHASE6_PREREGISTRATION.md, PRIMARY ENDPOINT AND DECISION_RULE)."
            ),
            "does_the_selector_defect_affect_the_primary_endpoint": "NO",
            "reasoning": [
                "The three cells are named in advance by (mechanism, level). They are not "
                "produced by select_frontier_level, so no property of that function enters the "
                "primary statistic.",
                "The endpoint is a paired McNemar over discordant pairs on a per-probe indicator. "
                "It never reads positive_accuracy, positive_negative_gap, the frontier band or "
                "any qualification verdict.",
                "The destroyed arms are not in the endpoint at all, so the 0.5000 constant is "
                "irrelevant to it.",
                "The preregistration's own clause - 'Comparisons are made at FIXED levels, never "
                "at each solver's own selected frontier, since frontier selection on a statistic "
                "with SE ~ 0.10 could otherwise compare different tasks' - is precisely the "
                "immunisation this defect calls for, and it was written before any Phase-6 call.",
            ],
            "could_a_no_band_conclusion_be_a_selector_artifact": {
                "answer": "Not for the fixed-level comparison; PARTLY for any per-mechanism 'qualified' claim.",
                "immune": [
                    "the primary McNemar endpoint (fixed cells)",
                    "the secondary per-mechanism ladder accuracy pooled over levels (all four "
                    "levels enter; no selection)",
                    "the descriptive 12-cell accuracy grid, per-cell share and entropy",
                ],
                "not_immune": [
                    "any statement of the form 'mechanism M did not qualify under V5', which is a "
                    "joint property of the ladder AND the selector",
                    "any comparison of QUALIFICATION VERDICTS between solvers, since two solvers "
                    "with different ladders can be routed to different levels",
                ],
                "empirical_bound_from_phase_5": (
                    "For the Phase-5 solver the selector cost was exactly zero: re-running the "
                    "frozen ladder under the window-midpoint, highest-qualifying and calibrated "
                    "selectors yields 0 qualified mechanisms in every case, identical to the "
                    "recorded result. A different solver's ladder could differ, so this bounds "
                    "Phase 5, not Phase 6."
                ),
                "recommendation": (
                    "Phase 6 should report per-mechanism qualification verdicts as DESCRIPTIVE "
                    "ONLY (which its preregistration already does) and should additionally report "
                    "the full L0..L3 positive-accuracy ladder for both solvers, so that a reader "
                    "can see whether any level fell inside [0.70, 0.85] regardless of what the "
                    "selector chose. That adds no calls: the ladder rows are already collected."
                ),
            },
            "minimal_legitimate_future_correction": {
                "the_correction": (
                    "In a FUTURE instrument version (V6+), make the frontier target a DERIVED "
                    "quantity rather than a free constant: frontier_target = "
                    "(positive_negative_gap_min + destroyed_expected + frontier_band_high) / 2, "
                    "so that raising the gap threshold automatically moves the aim point and the "
                    "two constants can never again drift apart. Additionally: delete "
                    "negative_target_accuracy_max as a gate (it is unconditionally satisfied and "
                    "carries no information), and state the effective window explicitly in the "
                    "spec so the incoherence is visible on the page."
                ),
                "why_this_is_a_correction_and_not_protocol_shopping": [
                    "It is derivable from the instrument's own definitions before seeing any "
                    "outcome: the window [0.70, 0.85] follows from gap >= 0.20 and destroyed = "
                    "0.5000, both of which are frozen constants, and the 0.5000 is a theorem about "
                    "the probe construction, not a measurement.",
                    "It changes WHERE the instrument measures, not WHETHER anything passes. The "
                    "pass/fail thresholds are untouched.",
                    "Applied to the frozen Phase-5 data it changes NOTHING: 0 mechanisms qualify "
                    "under every selector tested. A correction that cannot flip the existing "
                    "result cannot be motivated by the existing result.",
                    "It removes a degree of freedom rather than adding one.",
                ],
                "what_would_make_it_protocol_shopping": [
                    "Lowering positive_negative_gap_min back toward 0.10, or raising "
                    "frontier_band_high above 0.85, to make an already-observed cell pass. Those "
                    "move a THRESHOLD in the direction of the observed data.",
                    "Adopting the 'highest level satisfying all gates' selector. It is selection "
                    "on the qualification statistic itself; simulation shows it exceeds even the "
                    "perfect-knowledge oracle's sensitivity (0.734 vs 0.564), which is proof it is "
                    "converting noise into passes, and it raises near-threshold false positives "
                    "from 0.074 to 0.587.",
                    "Re-running V5 or re-scoring the frozen artifact under any new selector. The "
                    "V5 verdict is spent; a corrected selector may only be used on fresh probes.",
                    "Choosing the correction after inspecting which choice would let a favoured "
                    "mechanism through.",
                ],
                "what_must_be_preregistered_before_any_such_version": [
                    "The derived frontier target and the explicit effective window, written out "
                    "arithmetically in the spec.",
                    "That the destroyed control is a mathematical constant at 0.5000, with the "
                    "consequence that the gap gate IS an absolute accuracy threshold, and a "
                    "decision on whether to keep the destroyed arm at all - it currently consumes "
                    "24 of 72 calls per selected cell to measure a constant. Retaining it as an "
                    "ASSERTION (that the solver is deterministic and the twins are identical) is "
                    "defensible; retaining it as a negative control is not.",
                    "A power statement for the new window at the chosen n, including the "
                    "simulated false-positive rate against a coin-flipper AND against a "
                    "near-threshold reader below the window floor.",
                    "A ladder-granularity commitment. Phase 5's real limitation is that the "
                    "ladders jump straight over the window (0.875 -> 0.542 and 0.917 -> 0.667); "
                    "a finer ladder, or a per-mechanism difficulty knob, is needed before any "
                    "selector can find an in-window level.",
                    "That the change is admissible under FITNESS_V5_SPEC.md section 9 only if it "
                    "accompanies a change to a frozen variable class named in the prior failure "
                    "analysis. A selector repair alone is explicitly 're-tuning thresholds' and "
                    "does NOT license a new version on its own.",
                ],
            },
        },
        "5_verdict": {
            "is_the_defect_real": "YES - confirmed in the implementation, with traceable provenance",
            "summary": (
                "The frozen V5 selector aims at 0.625 while its own gates make [0.70, 0.85] the "
                "only qualifying region. The destroyed-twin negative control is a mathematical "
                "constant at exactly 0.5000 (structurally, and verified 24/24 in the frozen rows), "
                "so the gap gate is an absolute threshold of positive_accuracy >= 0.70 and the "
                "destroyed <= 0.60 gate is dead. The incoherence entered when V5 raised the gap "
                "from V4's 0.10 to 0.20 without moving the target that V4's 0.10 had made "
                "coherent."
            ),
            "did_it_cost_phase_5_anything": (
                "NO. Exactly one of the nine candidate cells in the frozen ladder lies inside the "
                "effective window, and the frozen selector chose it. Under three alternative "
                "selectors the Phase-5 result is unchanged: 0 of 3 mechanisms qualify."
            ),
            "simulated_cost_in_general": (
                "Substantial but not cheaply recoverable. Against an achievable ceiling of 0.564, "
                "the frozen selector qualifies a genuinely-in-band mechanism 0.257 of the time. "
                "Re-aiming at the window midpoint raises that to 0.707 - above the ceiling - "
                "while raising acceptance of a true-0.65 reader from 0.074 to 0.533. The "
                "sensitivity is real; the naive fix does not deliver it honestly."
            ),
            "dominant_limitation": (
                "The effective window is 1.76 standard errors wide at n = 24, and both measured "
                "ladders step straight across it. Sample size and ladder granularity dominate the "
                "selector defect."
            ),
            "phase_6_impact": "NONE on the primary endpoint; the fixed-level design is immune.",
            "action_authorised_by_this_analysis": "NONE. Reported for a future instrument version only.",
        },
    }


if __name__ == "__main__":
    report = main()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"bytes: {OUT.stat().st_size}")
