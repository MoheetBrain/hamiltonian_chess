"""AUDITOR 3 (A3) DIAGNOSTIC -- inventory + degeneracy analysis of the implemented
shortcut predictors.

(a) Reproduces `arena.experiments.fitness_v5.shortcut_audit` per (mechanism, level) cell and
    checks it byte-for-byte against the recorded scan `research/v7/per_level_shortcut_scan.json`.
(b) Measures, for each rule, how many DISTINCT values it can take within a twin pair
    (ORIGINAL / COUNTERFACTUAL).  A rule that is CONSTANT inside every twin pair scores exactly
    0.5 by construction and carries zero information -- it is a dead slot in the family.

DIAGNOSTIC ONLY.  No threshold is changed and no sentinel is re-scored.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    build_dev_pool,
    shortcut_audit,
)
from arena.canonical.schema import canonical_json

HERE = Path(__file__).resolve().parent
RECORDED = Path("research/v7/per_level_shortcut_scan.json")
OUT = HERE / "predictor_inventory.json"

RULE_NAMES = [
    "always_first_option",
    "always_second_option",
    "first_mentioned_in_state",
    "last_mentioned_in_state",
    "more_frequent_in_state",
    "shorter_option_text",
    "alphabetically_first",
]


def rule_values(p):
    n0 = str(p.options[0].arguments[0].value)
    n1 = str(p.options[1].arguments[0].value)
    t = canonical_json(p.state.to_dict(include_display_identity=False))
    return {
        "always_first_option": 0,
        "always_second_option": 1,
        "first_mentioned_in_state": 0 if t.find(f'"{n0}"') <= t.find(f'"{n1}"') else 1,
        "last_mentioned_in_state": 0 if t.rfind(f'"{n0}"') >= t.rfind(f'"{n1}"') else 1,
        "more_frequent_in_state": 0 if t.count(f'"{n0}"') >= t.count(f'"{n1}"') else 1,
        "shorter_option_text": 0 if (len(n0), n0) <= (len(n1), n1) else 1,
        "alphabetically_first": 0 if n0 <= n1 else 1,
    }


def main() -> int:
    probes = [p for p in build_dev_pool(Path.cwd()) if p.variant.value in POSITIVE_VARIANTS]
    cells = defaultdict(list)
    for p in probes:
        cells[(p.mechanism, p.level)].append(p)

    reproduced = {}
    for (mech, lvl), cell in sorted(cells.items()):
        a = shortcut_audit(tuple(cell))
        reproduced.setdefault(mech, {})[str(lvl)] = {
            "best_shortcut_accuracy": a["worst_score"],
            "best_shortcut_feature": a["worst_rule"],
            "scores": a["scores"],
            "status": a["status"],
            "items": a["items"],
        }

    # --- check against the recorded scan
    rec = json.loads(RECORDED.read_text()) if RECORDED.exists() else {}
    mismatches = []
    for mech, lv in reproduced.items():
        for lvl, got in lv.items():
            want = rec.get(mech, {}).get(lvl)
            if want is None:
                mismatches.append({"cell": [mech, lvl], "issue": "absent from recorded scan"})
                continue
            for key in ("best_shortcut_accuracy", "best_shortcut_feature", "status"):
                if got[key] != want[key]:
                    mismatches.append(
                        {"cell": [mech, lvl], "field": key, "got": got[key], "recorded": want[key]}
                    )
            if got["scores"] != want["scores"]:
                mismatches.append({"cell": [mech, lvl], "field": "scores"})

    # --- degeneracy: does the rule ever differ WITHIN a twin (family) pair?
    degeneracy = {}
    for (mech, lvl), cell in sorted(cells.items()):
        by_family = defaultdict(list)
        for p in cell:
            by_family[p.family_id].append(p)
        per_rule = {}
        for name in RULE_NAMES:
            varying = 0
            for fam, pair in by_family.items():
                vals = {rule_values(p)[name] for p in pair}
                if len(vals) > 1:
                    varying += 1
            per_rule[name] = {
                "families": len(by_family),
                "families_where_rule_varies_within_twin": varying,
                "structurally_pinned_at_0.5": varying == 0,
            }
        degeneracy[f"{mech}|L{lvl}"] = per_rule

    live = {}
    for cellname, per_rule in degeneracy.items():
        live[cellname] = sorted(
            n for n, d in per_rule.items() if not d["structurally_pinned_at_0.5"]
        )

    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC. Reproduction + degeneracy analysis of the FROZEN V5 shortcut family. "
            "Nothing here re-scores, promotes or reinterprets any recorded sentinel."
        ),
        "rule_names": RULE_NAMES,
        "reproduced_audit": reproduced,
        "recorded_scan_path": str(RECORDED),
        "reproduction_mismatches": mismatches,
        "reproduction_exact": not mismatches,
        "twin_pair_degeneracy": degeneracy,
        "live_rules_per_cell": live,
        "live_rule_count_per_cell": {k: len(v) for k, v in live.items()},
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("reproduction_exact:", out["reproduction_exact"], "mismatches:", len(mismatches))
    for k in sorted(live):
        print(f"  {k:38s} live_rules={len(live[k])} -> {live[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
