"""Stage 3: consistent obfuscation, held-out generalisation, and residual characterisation."""
from __future__ import annotations
import copy, json
from collections import Counter, defaultdict

from arena.training.prepare_matched_data import stratified_split
from research.leakage.measure import (
    FIELDS, build_records, evaluate, fit_all, obfuscate, opaque, case_prefix, sub_strings,
)

tasks, records = build_records(676, 0, with_inputs=False)
train_ix, dev_ix, fresh_ix = stratified_split(tasks, 600, 48, 48, 0)
out = {}

# --- consistent obfuscation: the SAME opaque token replaces the case prefix on BOTH sides.
consistent = []
for rec in records:
    rec = copy.deepcopy(rec)
    pre = case_prefix(rec["state_id"]); tok = opaque(pre)
    rec["obs"] = sub_strings(rec["obs"], [(pre, tok)])
    rec["target"] = sub_strings(rec["target"], [(pre, tok)])
    consistent.append(rec)

variants = {
    "none": records,
    "state_id_only": obfuscate(records, "state_id_only"),
    "all_ids_observation_only": obfuscate(records, "all_ids"),
    "all_ids_consistent_both_sides": consistent,
}
for name, recs in variants.items():
    tr = [recs[i] for i in train_ix]
    held = [recs[i] for i in dev_ix + fresh_ix]
    entry = {}
    for tier, allow in (("TIER_B_no_arithmetic", False), ("TIER_C_with_arithmetic", True)):
        rules, desc, _ = fit_all(tr, allow_arith=allow)
        h = evaluate(rules, held); a = evaluate(rules, recs)
        hd = evaluate(rules, held, drop_action_id=True)
        entry[tier] = {
            "rule_for_action_id": desc["action_id"],
            "heldout96_per_field": h["per_field_exact"],
            "heldout96_whole_target": h["whole_target_exact"],
            "heldout96_target_minus_action_id": hd["whole_target_exact"],
            "all676_whole_target": a["whole_target_exact"],
        }
        print(f"{name:<32}{tier:<24}heldout whole={h['whole_target_exact']:.4f}  "
              f"heldout action_id={h['per_field_exact']['action_id']:.4f}  "
              f"heldout minus-action_id={hd['whole_target_exact']:.4f}  "
              f"[{desc['action_id']}]")
    out[name] = entry

# --- residual: which items does the zero-mathematics rule miss, and why?
rules_b, _, _ = fit_all([records[i] for i in train_ix], allow_arith=False)
miss = defaultdict(list)
for r in records:
    if rules_b["arguments"].predict(r["obs"]) != r["target"]["arguments"]:
        miss[(r["domain"], r["obs"]["goal"]["op"])].append(r["index"])
print("\nRESIDUAL AFTER THE ZERO-MATHEMATICS RULE (Tier B) -- what it cannot derive:")
tot = 0
res = {}
for k, v in sorted(miss.items()):
    tot += len(v)
    res[f"{k[0]}/{k[1]}"] = len(v)
    print(f"  domain={k[0]:<22} goal.op={k[1]:<8} n={len(v):<4}")
print(f"  TOTAL residual = {tot}/676 = {tot/676:.4f}; derivable without arithmetic = {1-tot/676:.4f}")
out["tier_b_residual"] = {"by_group": res, "total": tot, "fraction": round(tot / 676, 6)}

# --- magnitude of the arithmetic actually required
mags = defaultdict(list)
for r in records:
    op = r["obs"]["goal"]["op"]
    if op in ("add", "eq", "div", "sqrt"):
        v = r["target"]["arguments"][0]
        mags[op].append(v.get("value") if "value" in v else v["args"][1]["value"])
print("\nMAGNITUDE OF THE REQUIRED ARITHMETIC (value of the computed answer):")
for op, vals in sorted(mags.items()):
    print(f"  goal.op={op:<8} n={len(vals):<4} min={min(vals)} max={max(vals)} distinct={len(set(vals))}")
out["arithmetic_magnitude"] = {k: {"n": len(v), "min": min(v), "max": max(v),
                                   "distinct": len(set(v))} for k, v in mags.items()}

# --- concrete examples
def show(idx, label):
    r = records[idx]
    print(f"\n--- {label} (index {idx}, domain {r['domain']})")
    print("    state_id :", r["obs"]["state_id"])
    print("    goal     :", json.dumps(r["obs"]["goal"], sort_keys=True, separators=(",", ":")))
    print("    GOLD     :", json.dumps(r["target"], sort_keys=True, separators=(",", ":")))
    pb = {f: rules_b[f].predict(r["obs"]) for f in FIELDS}
    print("    TierB pred:", json.dumps(pb, sort_keys=True, separators=(",", ":")))
    print("    TierB whole-target correct:", pb == r["target"])
    return {"index": idx, "domain": r["domain"], "state_id": r["obs"]["state_id"],
            "goal": r["obs"]["goal"], "gold_target": r["target"],
            "tier_b_prediction": pb, "tier_b_correct": pb == r["target"]}

leaked = next(i for i, r in enumerate(records) if r["domain"] == "reasoning_evidence")
resid = next(i for i, r in enumerate(records) if r["domain"] == "arithmetic")
out["example_fully_leaked"] = show(leaked, "FULLY DERIVABLE WITH ZERO MATHEMATICS")
out["example_residual"] = show(resid, "RESIDUAL: needs one integer addition")

with open("research/leakage/residual_raw.json", "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("\nwrote research/leakage/residual_raw.json")
