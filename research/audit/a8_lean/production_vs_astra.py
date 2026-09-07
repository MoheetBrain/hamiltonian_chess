"""A8: is Astra's 0.4167 lexical shortcut consistent with the production
measurement of the same rule on the same sampler (L3) at 290x the sample size?"""
from __future__ import annotations

import json
import math
from pathlib import Path

MAN = Path("artifacts/manifests/premise_selection_manifest.json")
AST = Path("research/astra/artifacts/shortcut_results.json")


def two_prop(p1, n1, p2, n2):
    k1, k2 = round(p1 * n1), round(p2 * n2)
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se
    pv = math.erfc(abs(z) / math.sqrt(2))
    return {"z": z, "two_sided_p": pv, "pooled_p": p, "se": se}


def main() -> None:
    man = json.loads(MAN.read_text())
    ast = json.loads(AST.read_text())
    out = {}
    for level in ("L2_standard", "L3_same_module_freq_matched", "L4_high_similarity"):
        sg = man["difficulty_ladder"][level]["shortcut_gate"]
        out[level] = {
            "n_dev_holdout": sg["n_dev_holdout_items"],
            "lexical_overlap_name_vs_goal": sg["per_shortcut_dev_holdout"]["lexical_overlap_name_vs_goal"],
            "best_shortcut": sg["best_shortcut"],
            "best_shortcut_accuracy": sg["best_shortcut_accuracy"],
        }
    a_acc = ast["strongest_visible_rule"]["accuracy"]
    a_n = ast["strongest_visible_rule"]["evaluated"]
    l3 = out["L3_same_module_freq_matched"]
    report = {
        "astra": {"rule": ast["strongest_visible_rule"]["name"], "accuracy": a_acc, "n": a_n,
                  "sampler": "arena L3_same_module_freq_matched (source_adapter.py:21)"},
        "production": out,
        "astra_vs_production_L3_same_rule_family": two_prop(a_acc, a_n,
                                                            l3["lexical_overlap_name_vs_goal"],
                                                            l3["n_dev_holdout"]),
        "astra_vs_production_L3_best_combined": two_prop(a_acc, a_n,
                                                         l3["best_shortcut_accuracy"],
                                                         l3["n_dev_holdout"]),
        "note": "Astra draws from the same sampler but adds three admission filters "
                "(explicit theorem/lemma header for gold AND all six candidates, single goal, "
                "import+declaration-order scope). The production L3 lexical rule is measured on "
                "17,513 grouped-holdout items.",
    }
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/production_vs_astra.json").write_text(
        json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
