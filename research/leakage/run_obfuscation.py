"""Stage 2: identifier-obfuscation counterfactual + leak-redundancy + byte-share analysis."""
from __future__ import annotations
import json
from collections import Counter

from arena.training.prepare_matched_data import stratified_split
from research.leakage.measure import (
    FIELDS, build_records, evaluate, fit_all, obfuscate, case_prefix,
)
from research.leakage.lib import induce_affix, apply_affix
from research.leakage.predictors import scalars

tasks, records = build_records(676, 0, with_inputs=False)
train_ix, dev_ix, fresh_ix = stratified_split(tasks, 600, 48, 48, 0)

out = {}

# ---- A. how many DISTINCT visible scalars independently reconstruct action_id?
train = [records[i] for i in train_ix]
common = set.intersection(*[set(scalars(r["obs"])) for r in train])
redundant = []
for k in sorted(common, key=repr):
    src = [scalars(r["obs"])[k] for r in train]
    if not all(isinstance(s, str) for s in src):
        continue
    rule = induce_affix(src, [r["target"]["action_id"] for r in train])
    if rule is None:
        continue
    acc = sum(apply_affix(rule, scalars(r["obs"])[k]) == r["target"]["action_id"]
              for r in records if k in scalars(r["obs"])) / len(records)
    if acc == 1.0:
        redundant.append({"source": str(k), "affix_rule": list(rule)})
print("VISIBLE SCALARS THAT EACH ALONE RECONSTRUCT action_id AT 676/676:")
for item in redundant:
    print("   ", item["source"], "->", item["affix_rule"])
out["action_id_redundant_sources"] = redundant

# ---- B. obfuscation variants
for mode in ("none", "state_id_only", "all_ids"):
    recs = obfuscate(records, mode)
    tr = [recs[i] for i in train_ix]
    held = [recs[i] for i in dev_ix + fresh_ix]
    entry = {}
    for tier, allow in (("TIER_B_no_arithmetic", False), ("TIER_C_with_arithmetic", True)):
        rules, desc, arg_info = fit_all(tr, allow_arith=allow)
        full = evaluate(rules, recs)
        nodrop = evaluate(rules, recs, drop_action_id=True)
        heldr = evaluate(rules, held)
        entry[tier] = {
            "rules": desc,
            "per_field_exact_all676": full["per_field_exact"],
            "whole_target_exact_all676": full["whole_target_exact"],
            "whole_target_exact_heldout96": heldr["whole_target_exact"],
            "target_minus_action_id_all676": nodrop["whole_target_exact"],
        }
        print(f"\n--- obfuscation={mode}  {tier}")
        for f in FIELDS:
            print(f"    {f:<24}{full['per_field_exact'][f]:.4f}   {desc[f]}")
        print(f"    {'WHOLE TARGET':<24}{full['whole_target_exact']:.4f}"
              f"   (minus action_id: {nodrop['whole_target_exact']:.4f})")
    out[f"obfuscation_{mode}"] = entry

# ---- C. character share of the target occupied by each field
shares = Counter(); totals = 0
for r in records:
    text = json.dumps(r["target"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    totals += len(text)
    for f in FIELDS:
        shares[f] += len(json.dumps({f: r["target"][f]}, ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":"))) - 2
print("\nMEAN CHARACTER SHARE OF THE TARGET STRING, BY FIELD")
byte = {}
for f in FIELDS:
    byte[f] = round(shares[f] / totals, 4)
    print(f"  {f:<24}{byte[f]:.4f}")
zero_math = round(sum(byte[f] for f in FIELDS if f != "arguments"), 4)
print(f"  zero-mathematics fields (all but `arguments`): {zero_math:.4f} of target characters")
out["target_character_share"] = byte
out["zero_math_character_share"] = zero_math

with open("research/leakage/obfuscation_raw.json", "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("\nwrote research/leakage/obfuscation_raw.json")
