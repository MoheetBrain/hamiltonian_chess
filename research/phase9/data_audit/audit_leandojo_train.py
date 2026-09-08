"""Trajectory audit of LeanDojo Benchmark 4 random/train.json (DEVELOPMENT split only).

SEALED: novel_premises/{val,test}.json and random/{val,test}.json are NEVER opened.
This script hard-refuses any path other than random/train.json + corpus.jsonl.
"""
from __future__ import annotations
import json, os, collections, sys

ROOT = "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4"
SEALED = {"novel_premises/val.json", "novel_premises/test.json", "random/val.json", "random/test.json"}
TRAIN = os.path.join(ROOT, "random/train.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leandojo_train_trajectories.json")

for s in SEALED:
    assert os.path.join(ROOT, s) != TRAIN, "sealed guard"

def main() -> None:
    with open(TRAIN, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    n_thm = len(data)
    thm_keys = collections.Counter()
    tac_keys = collections.Counter()
    lengths = []
    n_with_tactics = 0
    n_steps = 0
    chain_exact = 0          # state_after[i] == state_before[i+1]
    chain_total = 0
    chain_all_ok = 0         # proofs where EVERY adjacent pair chains exactly
    terminal_no_goals = 0
    terminal_other = collections.Counter()
    leak_name_in_state = 0
    dup_states = 0
    distinct_state_before_per_proof = []
    files = collections.Counter()
    example = None
    long_example = None

    for t in data:
        thm_keys.update(t.keys())
        tt = t.get("traced_tactics") or []
        files[t.get("file_path")] += 1
        L = len(tt)
        lengths.append(L)
        if L == 0:
            continue
        n_with_tactics += 1
        n_steps += L
        for st in tt:
            tac_keys.update(st.keys())
        ok = True
        for i in range(L - 1):
            chain_total += 1
            if tt[i].get("state_after") == tt[i + 1].get("state_before"):
                chain_exact += 1
            else:
                ok = False
        if ok and L >= 2:
            chain_all_ok += 1
        last = tt[-1].get("state_after")
        if last == "no goals":
            terminal_no_goals += 1
        else:
            terminal_other[(last or "")[:60]] += 1
        fn = t.get("full_name") or ""
        if fn and any(fn in (st.get("state_before") or "") for st in tt):
            leak_name_in_state += 1
        sb = [st.get("state_before") for st in tt]
        distinct_state_before_per_proof.append(len(set(sb)))
        if L != len(set(sb)):
            dup_states += 1
        if example is None and 5 <= L <= 7:
            example = t
        if long_example is None and L >= 20:
            long_example = {"full_name": t.get("full_name"), "file_path": t.get("file_path"),
                            "n_steps": L,
                            "tactics": [st.get("tactic") for st in tt][:25]}

    hist = collections.Counter(lengths)
    def atleast(k): return sum(1 for v in lengths if v >= k)
    res = {
        "source": TRAIN,
        "bytes": os.path.getsize(TRAIN),
        "n_theorem_records": n_thm,
        "n_theorems_with_traced_tactics": n_with_tactics,
        "n_theorems_with_zero_tactics": n_thm - n_with_tactics,
        "n_traced_tactic_steps": n_steps,
        "n_files": len(files),
        "theorem_record_keys": sorted(thm_keys),
        "traced_tactic_keys": sorted(tac_keys),
        "horizon_at_least": {str(k): atleast(k) for k in (1,2,3,5,10,15,20,30,50,100)},
        "horizon_hist_1_to_40": {str(k): hist.get(k,0) for k in range(1,41)},
        "max_horizon": max(lengths),
        "mean_horizon_over_nonempty": n_steps / max(n_with_tactics,1),
        "chain_adjacent_pairs_total": chain_total,
        "chain_adjacent_pairs_exact_match": chain_exact,
        "chain_exact_fraction": chain_exact / max(chain_total,1),
        "proofs_len_ge2_fully_chained": chain_all_ok,
        "proofs_len_ge2_total": atleast(2),
        "terminal_state_after_is_no_goals": terminal_no_goals,
        "terminal_other_top10": terminal_other.most_common(10),
        "proofs_whose_own_name_appears_in_some_state_before": leak_name_in_state,
        "proofs_with_repeated_state_before": dup_states,
        "example_5_to_7_step": {
            "full_name": example.get("full_name") if example else None,
            "file_path": example.get("file_path") if example else None,
            "steps": [{"tactic": s.get("tactic"),
                       "state_before_head": (s.get("state_before") or "").split("\n")[-1][:160],
                       "state_after_head": (s.get("state_after") or "").split("\n")[-1][:160]}
                      for s in (example.get("traced_tactics") if example else [])],
        },
        "example_ge20_step": long_example,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    slim = {k: v for k, v in res.items() if k not in ("horizon_hist_1_to_40","example_5_to_7_step","example_ge20_step")}
    print(json.dumps(slim, indent=2)[:6000])
    print("HIST:", res["horizon_hist_1_to_40"])

main()
