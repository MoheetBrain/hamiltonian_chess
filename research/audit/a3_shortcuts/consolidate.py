"""AUDITOR 3 (A3) -- consolidated evidence table for the report. DIAGNOSTIC ONLY."""
from __future__ import annotations
import json
from pathlib import Path

H = Path(__file__).resolve().parent
inv = json.loads((H / "predictor_inventory.json").read_text())
sel = json.loads((H / "selection_bias.json").read_text())
exp = json.loads((H / "expanded_family.json").read_text())
anc = json.loads((H / "ancestor_procedure.json").read_text())
syn = json.loads((H / "synthetic_population.json").read_text())
sc = json.loads((H / "synthetic_classifiers.json").read_text())
fp = json.loads((H / "formal_pool_classifiers.json").read_text())

rows = {}
for key, cell in anc["cells"].items():
    r = {
        "dev_n": cell["items"],
        "V5_reported_best_shortcut_DEV24": cell["observed_worst_score"],
        "V5_reported_best_feature": cell["observed_worst_rule"],
        "live_rules_in_family": cell["live_rules_in_family"],
        "randomisation_null_mean_no_leakage": sel["cells"][key]["randomisation"]["null_mean"],
        "randomisation_p": cell["randomisation_p"],
        "split_half_heldout_DEV": cell["split_sample_heldout"],
        "ancestor_bonferroni_verdict": cell["ancestor_verdict_neff12_bonf_live"],
        "flat_threshold_verdict": cell["flat_threshold_verdict_ACTUALLY_USED"],
        "expanded30_in_sample": exp["cells"][key]["expanded_threshold_family"]["in_sample_best"],
        "expanded30_split_half": exp["cells"][key]["expanded_threshold_family"]["split_half_heldout"],
        "best_model_split_half_DEV": exp["cells"][key]["best_model_split_value"],
    }
    if key in syn["cells"]:
        r["population_best_single_rule_n800"] = syn["cells"][key]["population_best_folded"]
        r["population_best_rule"] = syn["cells"][key]["population_best_rule"]
        r["population_best_COMBINED_groupedCV_n800"] = sc["cells"][key]["best_grouped_cv"]
        r["combination_gain_at_population_n"] = round(
            sc["cells"][key]["best_grouped_cv"] - syn["cells"][key]["population_best_folded"], 4)
    if key in fp["cells"]:
        r["population_best_single_rule_fullpool"] = fp["cells"][key]["v5_best_on_full_pool"]
        r["population_best_rule"] = fp["cells"][key]["v5_best_rule_on_full_pool"]
        r["population_best_COMBINED_groupedCV_fullpool"] = fp["cells"][key]["best_grouped_cv"]
        r["combination_gain_at_population_n"] = round(
            fp["cells"][key]["combination_gain_over_v5_best"], 4)
        r["population_n"] = fp["cells"][key]["n_positives"]
    rows[key] = r

out = {
    "_disclaimer": (
        "A3 CONSOLIDATED DIAGNOSTIC. Every number here is a measurement of the shortcut "
        "INSTRUMENT. None of it re-scores, promotes or reinterprets any recorded V7 sentinel."
    ),
    "cells": rows,
    "exact_null_max_of_k_twin_paired_neff12": sel["exact_nulls"]["null_B_twin_paired"][
        "max_of_k_independent"],
    "exact_null_single_rule": {
        "twin_paired_neff12": {k: v for k, v in sel["exact_nulls"]["null_B_twin_paired"].items()
                               if k.startswith("single") or k == "effective_n"},
        "item_level_n24": {k: v for k, v in sel["exact_nulls"]["null_A_item_level"].items()
                           if k.startswith("single") or k == "effective_n"},
    },
    "live_rule_count_per_cell": inv["live_rule_count_per_cell"],
    "reproduction_of_recorded_scan_exact": inv["reproduction_exact"],
}
(H / "CONSOLIDATED.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
hdr = (f"{'cell':32s} {'DEV24':>6s} {'nullE':>6s} {'randp':>6s} {'split':>6s} "
       f"{'POP1':>6s} {'POPcomb':>7s} {'gain':>7s}")
print(hdr)
for k, r in rows.items():
    p1 = r.get("population_best_single_rule_n800", r.get("population_best_single_rule_fullpool"))
    pc = r.get("population_best_COMBINED_groupedCV_n800",
               r.get("population_best_COMBINED_groupedCV_fullpool"))
    print(f"{k:32s} {r['V5_reported_best_shortcut_DEV24']:6.3f} "
          f"{r['randomisation_null_mean_no_leakage']:6.3f} {r['randomisation_p']:6.3f} "
          f"{r['split_half_heldout_DEV']:6.3f} {p1:6.3f} {pc:7.3f} "
          f"{r['combination_gain_at_population_n']:+7.3f}")
