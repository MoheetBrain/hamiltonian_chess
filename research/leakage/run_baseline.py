"""Stage 1: reproduce the data path, verify the projection, and fit the baseline predictors."""
from __future__ import annotations
import json
from collections import Counter, defaultdict

from arena.training.prepare_matched_data import ARMS, stratified_split
from research.leakage.measure import FIELDS, build_records, evaluate, fit_all

tasks, records = build_records(676, 0)
print(f"tasks={len(tasks)}  arms={list(ARMS)}")

# --- 1. does state_id survive into every arm's rendered prompt?
leaks = Counter()
for r in records:
    for arm in ARMS:
        leaks[arm] += r["state_id"] in r["inputs"][arm]
print("\nstate_id present verbatim in input_text:")
for arm in ARMS:
    print(f"  {arm:<24}{leaks[arm]}/{len(records)}")

# --- 2. is the gold action_id a pure rewrite of state_id?
rewrite_ok = sum(
    r["target"]["action_id"] == "action:" + r["state_id"][len("state:"):-len(":initial")] + ":valid"
    for r in records)
print(f"\naction_id == state_id rewrite: {rewrite_ok}/{len(records)}")

# --- 3. domain -> operation and goal_op -> operation maps
dom_op = defaultdict(set); gop_op = defaultdict(set); gop_dom = defaultdict(set)
for r in records:
    dom_op[r["domain"]].add(r["target"]["operation"])
    gop_op[r["obs"]["goal"]["op"]].add(r["target"]["operation"])
    gop_dom[r["obs"]["goal"]["op"]].add(r["domain"])
print(f"\ndomains={len(dom_op)}  all singleton operation sets: {all(len(v)==1 for v in dom_op.values())}")
print(f"distinct goal.op={len(gop_op)}  goal.op->operation all singleton: {all(len(v)==1 for v in gop_op.values())}")
print(f"goal.op->domain all singleton: {all(len(v)==1 for v in gop_dom.values())}")

# --- 4. constant fields
for f in ("target_ids", "warrant", "generated_obligations", "expected_usefulness"):
    vals = Counter(json.dumps(r["target"][f]) for r in records)
    print(f"  {f:<24}{len(vals)} distinct  top={vals.most_common(1)[0]}")
prec_eq = sum(r["target"]["preconditions"] == r["obs"]["assumptions"] for r in records)
print(f"  preconditions == observation.assumptions: {prec_eq}/{len(records)}")

# --- 5. split
train_ix, dev_ix, fresh_ix = stratified_split(tasks, 600, 48, 48, 0)
print(f"\nsplit: train={len(train_ix)} dev={len(dev_ix)} fresh={len(fresh_ix)} "
      f"(legacy splitter, exactly as prepare_matched_data uses)")
train = [records[i] for i in train_ix]
held = [records[i] for i in dev_ix + fresh_ix]

out = {}
for tier, allow in (("TIER_B_no_arithmetic", False), ("TIER_C_with_arithmetic", True)):
    rules, desc, arg_info = fit_all(train, allow_arith=allow)
    all_r = evaluate(rules, records)
    held_r = evaluate(rules, held)
    train_r = evaluate(rules, train)
    out[tier] = {"rules": desc, "arguments_groups": arg_info,
                 "all676": all_r, "heldout96": held_r, "train600": train_r}
    print(f"\n================ {tier} ================")
    for f in FIELDS:
        print(f"  {f:<24} all676={all_r['per_field_exact'][f]:.4f}  "
              f"held-out96={held_r['per_field_exact'][f]:.4f}   rule: {desc[f]}")
    print(f"  {'WHOLE TARGET':<24} all676={all_r['whole_target_exact']:.4f}  "
          f"held-out96={held_r['whole_target_exact']:.4f}")
    dropped = evaluate(rules, records, drop_action_id=True)
    print(f"  {'TARGET minus action_id':<24} all676={dropped['whole_target_exact']:.4f}")
    out[tier]["all676_minus_action_id"] = dropped["whole_target_exact"]

with open("research/leakage/baseline_raw.json", "w") as fh:
    json.dump(out, fh, indent=1, default=str)
print("\nwrote research/leakage/baseline_raw.json")
