"""POST-HOC / EXPLORATORY re-analysis of the FROZEN Fitness-V5 DEV artifact.

============================== READ THIS FIRST ==============================
THIS IS AN EXPLORATORY, POST-HOC INSTRUMENT-PROPERTY ANALYSIS.

It MUST NOT be used to re-score V5, to reinterpret any V5 verdict, or to
promote any representation. V5's recorded sentinel
(`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`) stands
exactly as recorded. Nothing here is a representation result: only the frozen
JSON/typed-AST control candidate (`V5E_L3_JSON_AST`) was ever measured.

The object of study is the INSTRUMENT, not the Solver and not any language.
=============================================================================

The script:
  1. Reads the frozen artifact read-only and checks its sha256.
  2. Verifies, from the frozen ROWS, that the destroyed-twin negative control
     is a structural constant (identical prompts, identical outputs, opposite
     targets, exactly 0.5000).
  3. Rebuilds the per-mechanism x per-level (L0..L3) grid of every statistic
     that the frozen rows actually contain, and marks the statistics that were
     never measured off-frontier as UNMEASURED (they would need model calls).
  4. Applies each gate to every cell and emits a PASS/FAIL matrix.

No model call of any kind is made. `arena.experiments.fitness_v5` is NOT
imported; the constants below were transcribed by reading its source as text
and each carries its file:line provenance.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
ARTIFACT = REPO / "artifacts/experiments/fitness_v5/development/result.json"
FROZEN_SHA256 = "0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579"

# --- constants transcribed from arena/experiments/fitness_v5.py (read as text) ---
# QUALIFICATION_RULE, arena/experiments/fitness_v5.py:208-247
RULE = {
    "explicit_positive_level": 0,  # :211
    "explicit_positive_min": 0.90,  # :212
    "frontier_target": 0.625,  # :213
    "frontier_band": (0.35, 0.85),  # :214
    "q0_valid_rate_min": 0.95,  # :216
    "valid_response_rate_min": 0.95,  # :217
    "context_truncated_rows_max": 0,  # :218
    "positive_negative_gap_min": 0.20,  # :219
    "negative_target_accuracy_max": 0.60,  # :220
    "largest_answer_share_max": 0.75,  # :221
    "min_positives_for_gates": 24,  # :222
    "position_invariance_min": 0.50,  # :224
    "shortcut_rule_max": 0.75,  # :225
    "minimum_qualified_mechanisms": 2,  # :226
}
# POSITIVE_VARIANTS, fitness_v5.py:271
POSITIVE_VARIANTS = {"ORIGINAL", "COUNTERFACTUAL"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ selector


def select_frontier_level(level_accuracies: dict[int, float]) -> dict[str, Any]:
    """Faithful re-implementation of fitness_v5.select_frontier_level (:915-948).

    Transcribed, not imported. The `min(..., key=(|acc-target|, level))` tuple
    reproduces "ties to the lower level" because `sorted()` feeds levels in
    ascending order and `min` keeps the first minimum.
    """
    explicit = level_accuracies.get(RULE["explicit_positive_level"], 0.0)
    if explicit < RULE["explicit_positive_min"]:
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
        }
    candidates = [(lvl, acc) for lvl, acc in sorted(level_accuracies.items()) if lvl >= 1]
    if not candidates:
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
        }
    level, accuracy = min(
        candidates, key=lambda item: (abs(item[1] - RULE["frontier_target"]), item[0])
    )
    low, high = RULE["frontier_band"]
    verdict = "VOID_CEILING" if accuracy > high else "VOID_FLOOR" if accuracy < low else "FRONTIER_SELECTED"
    return {
        "selected_level": level if verdict == "FRONTIER_SELECTED" else None,
        "candidate_level": level,
        "candidate_accuracy": accuracy,
        "verdict": verdict,
        "explicit_positive_accuracy": explicit,
    }


# ------------------------------------------------- per-level statistic rebuild


def cell_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Statistics computable from POSITIVE rows only (what the ladder scan ran).

    Mirrors fitness_v5.summarize (:664-720) restricted to the positive arms.
    """
    base = [r for r in rows if r["variant"] in POSITIVE_VARIANTS]
    n = len(base)
    parsed = [r["parsed_index"] for r in base if r["parsed_index"] is not None]
    share = max(Counter(parsed).values()) / len(parsed) if parsed else 1.0
    return {
        "n_positive": n,
        "positive_correct": sum(bool(r["correct"]) for r in base),
        "positive_accuracy": sum(bool(r["correct"]) for r in base) / n if n else 0.0,
        "largest_answer_share": share,
        "valid_response_rate": len(parsed) / n if n else 0.0,
        "context_truncated_rows": sum(r["cause"] == "INPUT_CONTEXT_TRUNCATION" for r in base),
        "output_truncated_rows": sum(r["cause"] == "OUTPUT_TRUNCATION" for r in base),
        "mean_prompt_tokens": sum(r["prompt_tokens"] for r in base) / n if n else 0.0,
        "cause_totals": dict(Counter(r["cause"] for r in base)),
    }


def verify_destroyed_constant(payload: dict[str, Any]) -> dict[str, Any]:
    """Check the destroyed-twin negative control against the frozen rows."""
    per_mech: dict[str, Any] = {}
    for mechanism, report in payload["mechanisms"].items():
        rows = report.get("rows")
        if not rows:
            per_mech[mechanism] = {"status": "NO_FULL_FAMILY_ROWS_IN_ARTIFACT"}
            continue
        by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            by_family[row["family_id"]][row["variant"]] = row
        pairs = same_prompt = same_output = opposite_target = 0
        correct = total = 0
        for variants in by_family.values():
            a = variants.get("DESTROYED_ORIGINAL")
            b = variants.get("DESTROYED_COUNTERFACTUAL")
            if not (a and b):
                continue
            pairs += 1
            same_prompt += a["prompt_hash"] == b["prompt_hash"]
            same_output += a["raw_output"] == b["raw_output"]
            opposite_target += a["expected_index"] != b["expected_index"]
            correct += bool(a["correct"]) + bool(b["correct"])
            total += 2
        per_mech[mechanism] = {
            "level": report["selected_level"],
            "twin_pairs": pairs,
            "identical_prompt_hash": same_prompt,
            "identical_raw_output": same_output,
            "opposite_expected_index": opposite_target,
            "destroyed_correct": correct,
            "destroyed_rows": total,
            "destroyed_accuracy": correct / total if total else None,
            "is_exactly_half": total > 0 and abs(correct / total - 0.5) < 1e-12,
        }
    measured = [v for v in per_mech.values() if v.get("twin_pairs")]
    return {
        "per_mechanism": per_mech,
        "all_twin_prompts_identical": all(
            v["identical_prompt_hash"] == v["twin_pairs"] for v in measured
        ),
        "all_twin_outputs_identical": all(
            v["identical_raw_output"] == v["twin_pairs"] for v in measured
        ),
        "all_targets_opposite": all(v["opposite_expected_index"] == v["twin_pairs"] for v in measured),
        "all_exactly_half": all(v["is_exactly_half"] for v in measured),
        "measured_cells": len(measured),
    }


# ------------------------------------------------------------------ gate matrix

UNMEASURED = "UNMEASURED_OFF_FRONTIER"


def gate_cell(
    stats: dict[str, Any],
    destroyed_accuracy: float | None,
    destroyed_source: str,
    position_invariance: float | None,
    shortcut_status: str | None,
    q0_rate: float,
) -> dict[str, Any]:
    """Apply every V5 gate to one (mechanism, level) cell.

    `frontier_band` is applied here as a gate on the cell itself, which is what
    the implementation does once a level has been selected (fitness_v5.py:934-940).
    """
    acc = stats["positive_accuracy"]
    low, high = RULE["frontier_band"]
    gap = None if destroyed_accuracy is None else acc - destroyed_accuracy
    checks = {
        "frontier_floor(acc >= 0.35)": "PASS" if acc >= low else "VOID_FLOOR",
        "frontier_ceiling(acc <= 0.85)": "PASS" if acc <= high else "VOID_CEILING",
        "sample_size(n >= 24)": "PASS"
        if stats["n_positive"] >= RULE["min_positives_for_gates"]
        else "VOID_VALIDITY",
        "valid_response(>= 0.95)": "PASS"
        if stats["valid_response_rate"] >= RULE["valid_response_rate_min"]
        else "VOID_VALIDITY",
        "q0(>= 0.95)": "PASS" if q0_rate >= RULE["q0_valid_rate_min"] else "VOID_VALIDITY",
        "context_truncation(== 0)": "PASS"
        if stats["context_truncated_rows"] <= RULE["context_truncated_rows_max"]
        else "VOID_CONTEXT",
        "negative_collapse(gap >= 0.20 and destroyed <= 0.60)": (
            UNMEASURED
            if destroyed_accuracy is None
            else "PASS"
            if gap >= RULE["positive_negative_gap_min"]
            and destroyed_accuracy <= RULE["negative_target_accuracy_max"]
            else "VOID_NEGATIVE_CONTROL"
        ),
        "answer_share(<= 0.75)": "PASS"
        if stats["largest_answer_share"] <= RULE["largest_answer_share_max"]
        else "VOID_POSITION_SHARE",
        "position_invariance(>= 0.50)": (
            UNMEASURED
            if position_invariance is None
            else "PASS"
            if position_invariance >= RULE["position_invariance_min"]
            else "VOID_POSITION"
        ),
        "shortcut(CLEAN)": (
            UNMEASURED
            if shortcut_status is None
            else "PASS"
            if shortcut_status == "CLEAN"
            else "VOID_SHORTCUT"
        ),
    }
    failures = [k for k, v in checks.items() if v not in ("PASS", UNMEASURED)]
    unknown = [k for k, v in checks.items() if v == UNMEASURED]
    return {
        "positive_accuracy": acc,
        "destroyed_accuracy": destroyed_accuracy,
        "destroyed_accuracy_source": destroyed_source,
        "positive_negative_gap": gap,
        "largest_answer_share": stats["largest_answer_share"],
        "position_invariance": position_invariance,
        "shortcut_status": shortcut_status,
        "valid_response_rate": stats["valid_response_rate"],
        "n_positive": stats["n_positive"],
        "mean_prompt_tokens": round(stats["mean_prompt_tokens"], 1),
        "checks": checks,
        "binding_failures": failures,
        "unmeasured_gates": unknown,
        "status": (
            "FAIL"
            if failures
            else "PASS_ON_MEASURED_GATES_ONLY"
            if unknown
            else "PASS_ALL_GATES"
        ),
    }


def main() -> dict[str, Any]:
    digest = sha256(ARTIFACT)
    payload = json.loads(ARTIFACT.read_text())
    q0_rate = float(payload["q0"]["rate"])

    destroyed_check = verify_destroyed_constant(payload)

    # per-cell positive statistics from the frozen ladder scan
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in payload["ladder_rows"]:
        by_cell[(row["mechanism"], row["level"])].append(row)

    mechanisms = list(payload["ladders"].keys())
    grid: dict[str, Any] = {}
    for mechanism in mechanisms:
        report = payload["mechanisms"][mechanism]
        selected = report["selected_level"]
        full = report.get("full_family_summary") or {}
        shortcut = (report.get("shortcut_audit") or {}).get("status")

        levels: dict[str, Any] = {}
        accuracies: dict[int, float] = {}
        for level in range(len(payload["ladders"][mechanism])):
            rows = by_cell[(mechanism, level)]
            if not rows:
                continue
            stats = cell_statistics(rows)
            accuracies[level] = stats["positive_accuracy"]
            on_frontier = selected is not None and level == selected
            if on_frontier:
                destroyed = full.get("negative_target_accuracy")
                destroyed_source = "MEASURED_IN_FROZEN_ARTIFACT"
                invariance = full.get("position_invariance")
                sc = shortcut
            else:
                # Off the selected frontier the run never evaluated the
                # destroyed or swapped arms, so these were never measured.
                # Destroyed is imputed at the structural constant 0.5000,
                # which is verified above at every cell where it WAS measured.
                destroyed = 0.5
                destroyed_source = "IMPUTED_STRUCTURAL_CONSTANT_0.5000"
                invariance = None
                sc = None
            levels[str(level)] = {
                "parameters": payload["ladders"][mechanism][level],
                **gate_cell(stats, destroyed, destroyed_source, invariance, sc, q0_rate),
            }

        selection = select_frontier_level(accuracies)
        grid[mechanism] = {
            "explicit_positive_accuracy_L0": accuracies.get(0),
            "explicit_positive_gate": "PASS"
            if accuracies.get(0, 0.0) >= RULE["explicit_positive_min"]
            else "VOID_INSTRUMENT_LIMIT",
            "reproduced_selection": selection,
            "recorded_selection": report["selection"],
            "selection_reproduced": (
                selection["selected_level"] == report["selection"]["selected_level"]
                and selection["verdict"] == report["selection"]["verdict"]
            ),
            "recorded_verdict": report["qualification"]["verdict"],
            "levels": levels,
            "levels_passing_every_measured_gate": [
                lvl
                for lvl, cell in levels.items()
                if int(lvl) >= 1 and not cell["binding_failures"]
            ],
        }

    return {
        "ANALYSIS_CLASS": "EXPLORATORY_POST_HOC_INSTRUMENT_PROPERTY",
        "NOT_A_RESCORING": (
            "V5's recorded sentinel and artifact are unchanged. This analysis may not be "
            "used to re-score V5, to reinterpret any V5 verdict, or to promote anything."
        ),
        "artifact": str(ARTIFACT.relative_to(REPO)),
        "artifact_sha256": digest,
        "artifact_sha256_matches_frozen": digest == FROZEN_SHA256,
        "model_calls_made_by_this_analysis": 0,
        "q0_valid_rate": q0_rate,
        "destroyed_control_verification": destroyed_check,
        "grid": grid,
    }


if __name__ == "__main__":
    out = main()
    dest = Path(__file__).with_name("frozen_ladder_analysis.json")
    dest.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {dest}")
    print(f"sha256 matches frozen: {out['artifact_sha256_matches_frozen']}")
    dc = out["destroyed_control_verification"]
    print(
        "destroyed control: cells={measured_cells} prompts_identical={all_twin_prompts_identical} "
        "outputs_identical={all_twin_outputs_identical} targets_opposite={all_targets_opposite} "
        "exactly_0.5={all_exactly_half}".format(**dc)
    )
    for mechanism, block in out["grid"].items():
        print(f"\n=== {mechanism}")
        print(
            f"  L0 explicit {block['explicit_positive_accuracy_L0']:.4f} "
            f"-> {block['explicit_positive_gate']}"
        )
        print(
            f"  selector reproduced: {block['selection_reproduced']} "
            f"({block['reproduced_selection']['verdict']}, "
            f"level={block['reproduced_selection']['selected_level']})"
        )
        for lvl in sorted(block["levels"]):
            cell = block["levels"][lvl]
            print(
                f"  L{lvl}: acc={cell['positive_accuracy']:.4f} "
                f"dest={cell['destroyed_accuracy']} gap={cell['positive_negative_gap']:.4f} "
                f"share={cell['largest_answer_share']:.4f} "
                f"inv={cell['position_invariance']} sc={cell['shortcut_status']} "
                f"-> {cell['status']}"
            )
            if cell["binding_failures"]:
                print(f"        binding: {', '.join(cell['binding_failures'])}")
        print(f"  levels passing every MEASURED gate: {block['levels_passing_every_measured_gate']}")
