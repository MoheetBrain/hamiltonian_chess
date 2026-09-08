"""Verify the V7 forensic audit's claims about HML_V3 lean_runtime_v2_full and measure
whether that corpus contains TRAJECTORIES (multi-step chains) or only isolated transitions.

Sealed shard sealed_final_v2.part-*.jsonl.gz is NOT opened.
"""
from __future__ import annotations
import gzip, json, glob, collections, os

ROOT = "/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus"
GLOB = "lean_runtime_v2_full.canonical.part-*.jsonl.gz"
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    files = sorted(glob.glob(os.path.join(ROOT, GLOB)))
    assert not any("sealed" in f for f in files)
    recs = []
    for f in files:
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            recs += [json.loads(l) for l in fh]
    n = len(recs)
    per_thm = collections.Counter()
    for r in recs:
        per_thm[r["source_specific_reference"]["theorem_id"]] += 1
    lengths = list(per_thm.values())
    def atleast(k): return sum(1 for v in lengths if v >= k)

    # chaining: does state_after.state_id of transition i equal state_before.state_id of i+1?
    by_thm = collections.defaultdict(list)
    for r in recs:
        by_thm[r["source_specific_reference"]["theorem_id"]].append(r)
    chained_pairs = total_pairs = 0
    fully = 0
    for tid, rs in by_thm.items():
        rs.sort(key=lambda r: r["source_specific_reference"]["transition_index"])
        ok = len(rs) >= 2
        for i in range(len(rs)-1):
            total_pairs += 1
            if rs[i]["state_after"]["state_id"] == rs[i+1]["state_before"]["state_id"]:
                chained_pairs += 1
            else:
                ok = False
        if ok: fully += 1

    single_premise_single_goal = sum(
        1 for r in recs
        if len(r["action"]["external_premise_refs"]) == 1 and len(r["state_before"]["goals"]) == 1)
    has_imports = sum(1 for r in recs
                      if r["provenance"]["lean_runtime_snapshot"]["transitive_import_modules"])
    has_prem = sum(1 for r in recs if r["action"]["external_premise_refs"])
    kinds = collections.Counter(r["action"]["kind"] for r in recs)
    refcomp = collections.Counter(r["action"]["reference_completeness"] for r in recs)
    # is the TACTIC NAME recorded anywhere?
    a0 = recs[0]["action"]
    goal0 = recs[0]["state_before"]["goals"][0]
    res = {
        "files": [os.path.basename(f) for f in files],
        "bytes": sum(os.path.getsize(f) for f in files),
        "records": n,
        "distinct_theorem_ids": len(per_thm),
        "horizon_at_least": {str(k): atleast(k) for k in (1,2,3,5,10,15,20)},
        "horizon_hist_1_to_20": {str(k): sum(1 for v in lengths if v==k) for k in range(1,21)},
        "max_horizon": max(lengths), "mean_horizon": sum(lengths)/len(lengths),
        "adjacent_pairs": total_pairs, "adjacent_pairs_state_id_chained": chained_pairs,
        "theorems_fully_chained_len_ge2": fully,
        "records_single_premise_single_goal": single_premise_single_goal,
        "records_with_transitive_imports": has_imports,
        "records_with_external_premise_refs": has_prem,
        "action_kinds": dict(kinds),
        "reference_completeness": dict(refcomp),
        "action_keys": sorted(a0.keys()),
        "goal_object_keys": sorted(goal0.keys()) if isinstance(goal0, dict) else str(type(goal0)),
        "example_action": a0,
        "sealed_shard_opened": False,
    }
    json.dump(res, open(os.path.join(HERE, "hml_v3_corpus.json"), "w"), indent=2)
    slim = {k:v for k,v in res.items() if k not in ("example_action","horizon_hist_1_to_20")}
    print(json.dumps(slim, indent=2))
    print("HIST:", res["horizon_hist_1_to_20"])
    print("\nEXAMPLE action:", json.dumps(a0, indent=2)[:900])
    print("\nEXAMPLE goal keys:", res["goal_object_keys"])
main()
