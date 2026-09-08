"""Measure the LINEARLY-CHAINED trajectory pool inside LeanDojo train.json.

A LeanDojo `traced_tactics` list is a flattened traversal of the proof TREE.
Only when state_after[i] == state_before[i+1] for every adjacent pair does the
list constitute a genuine linear trajectory with persistent evolving state.
This script measures both (a) fully-chained proofs and (b) the maximal chained
prefix of every proof, which is the honest usable pool.
"""
from __future__ import annotations
import json, os, collections

TRAIN = "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leandojo_chained.json")

def atleast(vals, k): return sum(1 for v in vals if v >= k)

def main() -> None:
    data = json.load(open(TRAIN, encoding="utf-8"))
    full_len, prefix_len = [], []
    full_terminal_ok = 0
    tactic_in_state = 0           # leakage probe: does the gold tactic string occur verbatim in state_before?
    goalcount = collections.Counter()
    step_state_growth = []
    ex = None
    for t in data:
        tt = t.get("traced_tactics") or []
        if not tt:
            continue
        L = len(tt)
        # maximal chained prefix
        p = 1
        while p < L and tt[p-1].get("state_after") == tt[p].get("state_before"):
            p += 1
        prefix_len.append(p)
        chained = (p == L)
        if chained:
            full_len.append(L)
            if tt[-1].get("state_after") == "no goals":
                full_terminal_ok += 1
            if L >= 8 and ex is None:
                ex = {"full_name": t["full_name"], "file_path": t["file_path"], "n": L,
                      "tactics": [s["tactic"] for s in tt],
                      "state_0": tt[0]["state_before"][-400:],
                      "state_final": tt[-1]["state_after"]}
        for s in tt:
            sb = s.get("state_before") or ""
            if s.get("tactic") and s["tactic"] in sb:
                tactic_in_state += 1
            goalcount[sb.count("\n⊢ ") + (1 if sb.startswith("⊢ ") else 0)] += 1
    res = {
        "fully_chained_proofs": len(full_len),
        "fully_chained_horizon_at_least": {str(k): atleast(full_len,k) for k in (1,2,3,5,10,15,20,30,50,100)},
        "fully_chained_hist_1_to_30": {str(k): sum(1 for v in full_len if v==k) for k in range(1,31)},
        "fully_chained_max": max(full_len) if full_len else 0,
        "fully_chained_terminal_no_goals": full_terminal_ok,
        "maximal_chained_prefix_at_least": {str(k): atleast(prefix_len,k) for k in (1,2,3,5,10,15,20,30,50,100)},
        "maximal_chained_prefix_max": max(prefix_len) if prefix_len else 0,
        "steps_whose_tactic_text_appears_verbatim_in_state_before": tactic_in_state,
        "total_steps": sum(len(t.get("traced_tactics") or []) for t in data),
        "goal_count_distribution_top10": collections.Counter(goalcount).most_common(10),
        "example_fully_chained_ge8": ex,
    }
    json.dump(res, open(OUT,"w",encoding="utf-8"), indent=2)
    print(json.dumps({k:v for k,v in res.items() if k!="example_fully_chained_ge8"}, indent=2))
    print("\n--- EXAMPLE fully-chained proof ---")
    print(json.dumps(ex, indent=2, ensure_ascii=False)[:2500])

main()
