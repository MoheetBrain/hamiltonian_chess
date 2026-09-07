"""What V7 would conclude if a fresh run reproduced the frozen Phase-6 qwen ladder.

EXPLORATORY AND POST-HOC. This is a PREDICTION, not a result. It applies V7's derived selector
and per-level shortcut gate to accuracies that were collected under V5, purely so the integrator
knows what to expect before spending the Solver budget, and so that V7 cannot later be accused of
having been tuned after seeing an outcome.

It MUST NOT be used to re-score V5 or Phase 6, to reinterpret any recorded sentinel, to select a
level for any mechanism, or to promote any representation. It makes ZERO model calls, opens the
frozen artifact read-only, and writes only inside research/v7/.

Why the prediction is expected to be tight rather than speculative: V7 inherits V5's probes,
prompts and decoding byte for byte, and the solver is deterministic at temperature 0. A fresh V7
run therefore sends identical bytes and should return identical answers; only the cache namespace
differs. The prediction's real uncertainty is whether the Phase-6 rows are admissible at all
(docs/PHASE6_INTEGRATION_MAP.md section 0b records 61 cache hits against a "cache hits > 0"
invalidation rule), not whether the arithmetic below is right.

Run:  python -m research.v7.predict_v7_from_frozen_ladders
"""

from __future__ import annotations

import json
from pathlib import Path

from arena.experiments import fitness_v5 as v5
from arena.experiments import fitness_v7 as v7

ROOT = Path(__file__).resolve().parents[2]
FROZEN_QWEN = ROOT / "artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json"
OUT = Path(__file__).resolve().parent / "v7_prediction.json"


def frozen_ladders() -> dict[str, dict[int, float]]:
    """Read the frozen Phase-6 qwen ladder. READ ONLY: nothing is written back."""

    payload = json.loads(FROZEN_QWEN.read_text())
    ladders: dict[str, dict[int, float]] = {}
    for mechanism, report in payload["mechanisms"].items():
        ladders[mechanism] = {
            int(entry["level"]): float(entry["positive_accuracy"]) for entry in report["ladder"]
        }
    return ladders


def main() -> int:
    probes = v5.build_dev_pool(ROOT)
    audits = v7.per_level_shortcut_audit(probes)
    ladders = frozen_ladders()

    prediction: dict[str, object] = {
        "analysis_class": "EXPLORATORY_PREDICTION_NOT_A_RESULT",
        "disclaimer": (
            "Applies V7's selector and gates to accuracies collected under V5/Phase 6. It may "
            "not be used to re-score V5 or Phase 6, to reinterpret a sentinel, or to promote "
            "anything. Zero model calls were made. The frozen artifact was opened read-only."
        ),
        "frozen_input": str(FROZEN_QWEN.relative_to(ROOT)),
        "frozen_input_caveat": (
            "docs/PHASE6_INTEGRATION_MAP.md section 0b records 61 cache hits in this artifact "
            "against a preregistered 'cache hits > 0' invalidation rule. If Phase 6 is classified "
            "PHASE6_INVALID these accuracies are descriptive only and the prediction is void."
        ),
        "model_calls_made": 0,
        "frontier": v7.FRONTIER,
        "shortcut_margin": v7.SHORTCUT_MARGIN,
        "mechanisms": {},
    }

    qualified: list[str] = []
    for mechanism in v5.MECHANISMS:
        ladder = ladders[mechanism]
        v5_selection = v5.select_frontier_level(ladder)
        v7_selection = v7.select_frontier_level(ladder)
        per_level = {
            str(level): {
                "positive_accuracy": ladder[level],
                "best_shortcut_accuracy": audits[mechanism][str(level)]["best_shortcut_accuracy"],
                "best_shortcut_feature": audits[mechanism][str(level)]["best_shortcut_feature"],
                "shortcut_margin": (
                    ladder[level] - audits[mechanism][str(level)]["best_shortcut_accuracy"]
                ),
                "inside_v7_window": (
                    v7.FRONTIER["window_low"] <= ladder[level] <= v7.FRONTIER["window_high"]
                ),
            }
            for level in sorted(ladder)
        }
        entry: dict[str, object] = {
            "ladder": ladder,
            "per_level": per_level,
            "v5_selected_level": v5_selection.get("selected_level"),
            "v5_candidate_level": v5_selection.get("candidate_level"),
            "v7_selected_level": v7_selection.get("selected_level"),
            "v7_selection_verdict": v7_selection["verdict"],
        }
        level = v7_selection.get("selected_level")
        if level is None:
            entry["predicted_verdict"] = v7_selection["verdict"]
        else:
            audit = audits[mechanism][str(int(level))]
            margin = ladder[int(level)] - float(audit["best_shortcut_accuracy"])
            failures = []
            if float(audit["best_shortcut_accuracy"]) > float(
                v7.QUALIFICATION_RULE_V7["shortcut_rule_max"]
            ):
                failures.append("shortcut_absolute")
            if margin < v7.SHORTCUT_MARGIN - v7.GATE_EPSILON:
                failures.append("shortcut_margin")
            if ladder[int(level)] - v7.DESTROYED_EXPECTED < float(
                v7.QUALIFICATION_RULE_V7["positive_negative_gap_min"]
            ):
                failures.insert(0, "negative_collapse")
            entry["shortcut_margin_at_selected_level"] = margin
            entry["predicted_shortcut_failures"] = failures
            entry["predicted_verdict"] = (
                "VOID_NEGATIVE_CONTROL"
                if failures and failures[0] == "negative_collapse"
                else "VOID_SHORTCUT"
                if failures
                else "QUALIFIED (subject to share, invariance and validity gates)"
            )
            if not failures:
                qualified.append(mechanism)
        prediction["mechanisms"][mechanism] = entry  # type: ignore[index]

    # Cross-check of docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md section 11, which states:
    # "Under fix (1) alone, formal_expression_depth would have selected L2 (.792) and passed the
    # gap and share gates - giving 2 qualified mechanisms and authorising the founder tournament."
    # The gap and share claims hold. The claim about the OUTCOME does not: V5's own frozen
    # shortcut gate (worst_score <= 0.75) already voids L2 at 0.8333, with no V7 gate involved.
    fed_l2_shortcut = float(audits["formal_expression_depth"]["2"]["best_shortcut_accuracy"])
    prediction["v6_section_11_cross_check"] = {
        "claim": (
            "under a selector fix alone, formal_expression_depth L2 qualifies and the instrument "
            "reaches 2 qualified mechanisms"
        ),
        "formal_expression_depth_L2_positive_accuracy": ladders["formal_expression_depth"][2],
        "formal_expression_depth_L2_best_shortcut_accuracy": fed_l2_shortcut,
        "v5_frozen_shortcut_rule_max": float(v5.QUALIFICATION_RULE["shortcut_rule_max"]),
        "voided_by_v5s_own_shortcut_gate": fed_l2_shortcut
        > float(v5.QUALIFICATION_RULE["shortcut_rule_max"]),
        "finding": (
            "REFUTED, and not by anything V7 adds. V5's own shortcut gate voids L2 because "
            "first_mentioned_in_state scores 0.8333 there against a 0.75 ceiling. Section 11 "
            "checked the gap and share gates and did not check the shortcut gate, which V5 runs "
            "only at the selected frontier and therefore never evaluated at L2."
        ),
    }

    prediction["predicted_qualified_mechanisms"] = sorted(qualified)
    prediction["predicted_instrument_qualified"] = len(qualified) >= int(
        v7.QUALIFICATION_RULE_V7["minimum_qualified_mechanisms"]
    )
    OUT.write_text(json.dumps(prediction, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(prediction, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
