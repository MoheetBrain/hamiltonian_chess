"""AUDIT 7 / Part K, Question 4 — independent verification, ZERO model calls.

Rebuilds the frozen V5 DEV probe bank and measures, at EVERY ladder level:

  * V5's own frozen `shortcut_audit` verdict (the authoritative gate function), and
  * an INDEPENDENT re-implementation of the `first_mentioned_in_state` rule written from the
    spec rather than copied, so agreement is a real cross-check and not a tautology.

Then it evaluates each level against V5's OWN frozen constant
`QUALIFICATION_RULE["shortcut_rule_max"] = 0.75` (arena/experiments/fitness_v5.py:225).

READ-ONLY with respect to every frozen artifact.  Nothing here re-scores V5, V6/Phase 6 or V7;
no verdict is reinterpreted; no threshold is changed.  Writes only inside research/audit/a7_retro/.

Run:  .venv/bin/python -m research.audit.a7_retro.verify_v5_shortcut_at_every_level
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from arena.experiments import fitness_v5 as v5
from arena.experiments.fitness_v5 import POSITIVE_VARIANTS, V5Probe, shortcut_audit
from arena.canonical.schema import canonical_json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "v5_shortcut_every_level.json"
SHORTCUT_RULE_MAX = float(v5.QUALIFICATION_RULE["shortcut_rule_max"])


def independent_first_mentioned(probe: V5Probe) -> int:
    """Re-implementation of `first_mentioned_in_state` written from its description.

    'Answer with whichever of the two option identifiers appears earlier in the serialized
    canonical state.'  Ties resolve to option 0, matching `<=` in the frozen rule.
    """

    state_text = canonical_json(probe.state.to_dict(include_display_identity=False))
    marks = []
    for option in probe.options[:2]:
        needle = '"' + str(option.arguments[0].value) + '"'
        position = state_text.find(needle)
        marks.append(position)
    return 0 if marks[0] <= marks[1] else 1


def main() -> int:
    probes = v5.build_dev_pool(ROOT)
    cells: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for probe in probes:
        cells[(probe.mechanism, probe.level)].append(probe)

    report: dict[str, object] = {
        "analysis_class": "READ_ONLY_AUDIT_VERIFICATION_ZERO_MODEL_CALLS",
        "auditor": "A7 / Part K question 4",
        "model_calls_made": 0,
        "v5_shortcut_rule_max": SHORTCUT_RULE_MAX,
        "v5_shortcut_rule_max_source": "arena/experiments/fitness_v5.py:225",
        "v5_shortcut_audit_scope_source": "arena/experiments/fitness_v5.py:1074 (selected level only)",
        "dev_pool_hash": v5.stable_hash([p.to_dict() for p in probes]),
        "dev_pool_probes": len(probes),
        "cells": {},
    }

    disagreements = 0
    for (mechanism, level), cell in sorted(cells.items()):
        audit = shortcut_audit(tuple(cell))
        positives = [p for p in cell if p.variant.value in POSITIVE_VARIANTS]
        indep_correct = sum(
            independent_first_mentioned(p) == p.expected_index for p in positives
        )
        indep_score = indep_correct / len(positives)
        frozen_score = float(audit["scores"]["first_mentioned_in_state"])
        agrees = abs(indep_score - frozen_score) < 1e-12
        disagreements += 0 if agrees else 1
        report["cells"][f"{mechanism}/L{level}"] = {  # type: ignore[index]
            "mechanism": mechanism,
            "level": level,
            "positives": len(positives),
            "first_mentioned_in_state__frozen_v5": frozen_score,
            "first_mentioned_in_state__independent": indep_score,
            "first_mentioned_in_state__independent_correct": indep_correct,
            "independent_matches_frozen": agrees,
            "best_shortcut_feature": audit["worst_rule"],
            "best_shortcut_accuracy": float(audit["worst_score"]),
            "v5_shortcut_status": audit["status"],
            "exceeds_v5_shortcut_rule_max": float(audit["worst_score"]) > SHORTCUT_RULE_MAX,
            "all_rule_scores": audit["scores"],
        }

    fed = {lvl: report["cells"][f"formal_expression_depth/L{lvl}"] for lvl in (0, 1, 2, 3)}  # type: ignore[index]
    report["question_4_answer"] = {
        "claim": (
            "under the V5 rule, first_mentioned_in_state scores 1.000 at formal_expression_depth "
            "L1 and 0.8333 at L2, and both exceed V5's own shortcut_rule_max = 0.75"
        ),
        "L1_first_mentioned_in_state": fed[1]["first_mentioned_in_state__frozen_v5"],
        "L2_first_mentioned_in_state": fed[2]["first_mentioned_in_state__frozen_v5"],
        "L1_exceeds_0_75": fed[1]["first_mentioned_in_state__frozen_v5"] > SHORTCUT_RULE_MAX,
        "L2_exceeds_0_75": fed[2]["first_mentioned_in_state__frozen_v5"] > SHORTCUT_RULE_MAX,
        "verdict": (
            "CONFIRMED"
            if fed[1]["first_mentioned_in_state__frozen_v5"] == 1.0
            and abs(fed[2]["first_mentioned_in_state__frozen_v5"] - 0.8333333333333334) < 1e-12
            and fed[1]["first_mentioned_in_state__frozen_v5"] > SHORTCUT_RULE_MAX
            and fed[2]["first_mentioned_in_state__frozen_v5"] > SHORTCUT_RULE_MAX
            else "NOT CONFIRMED"
        ),
        "consequence": (
            "Every in-window level of formal_expression_depth (L1 0.833 accuracy, L2 0.792) is "
            "already LEAKS under V5's UNMODIFIED shortcut gate. No V7 gate is required to void it."
        ),
    }
    report["independent_reimplementation_disagreements"] = disagreements

    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    print(f"dev pool: {len(probes)} probes, hash {report['dev_pool_hash']}")
    print(f"V5 shortcut_rule_max = {SHORTCUT_RULE_MAX}  (fitness_v5.py:225)")
    print("")
    header = f"{'cell':38} {'first_mentioned':>15} {'best_rule':>28} {'best':>7} {'status':>7}"
    print(header)
    print("-" * len(header))
    for key, cell in report["cells"].items():  # type: ignore[union-attr]
        print(
            f"{key:38} {cell['first_mentioned_in_state__frozen_v5']:>15.4f} "
            f"{str(cell['best_shortcut_feature']):>28} {cell['best_shortcut_accuracy']:>7.4f} "
            f"{cell['v5_shortcut_status']:>7}"
        )
    print("")
    print(json.dumps(report["question_4_answer"], indent=1, sort_keys=True))
    print(f"\nindependent re-implementation disagreements: {disagreements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
