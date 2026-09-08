"""Horizon histogram for LeanDojo Benchmark 4 derived step table.

Reads ONLY the TRAIN split. Sealed splits (novel_premises/{val,test}.json,
random/{val,test}.json) are never opened; steps.jsonl carries a `split` field and
every non-train row is discarded without inspection of its content beyond that field.
"""
from __future__ import annotations
import json, sys, collections, os

STEPS = "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steps_horizons.json")

def main() -> None:
    per_proof: dict[str, int] = collections.Counter()
    split_counts: dict[str, int] = collections.Counter()
    heads: dict[str, int] = collections.Counter()
    closed_last = 0
    n = 0
    files: dict[str, int] = collections.Counter()
    keys_seen: set[str] = set()
    with open(STEPS, "r", encoding="utf-8") as fh:
        for line in fh:
            n += 1
            rec = json.loads(line)
            sp = rec.get("split")
            split_counts[sp] += 1
            if sp != "train":
                continue
            if not keys_seen:
                keys_seen = set(rec.keys())
            pid = rec["proof_id"]
            per_proof[pid] += 1
            heads[rec.get("head")] += 1
            files[rec.get("file_path")] += 1
            if rec.get("last_step") and rec.get("closed"):
                closed_last += 1

    lengths = list(per_proof.values())
    hist = collections.Counter(lengths)
    def atleast(k: int) -> int:
        return sum(1 for v in lengths if v >= k)
    res = {
        "source": STEPS,
        "bytes": os.path.getsize(STEPS),
        "total_rows": n,
        "rows_by_split": dict(split_counts),
        "train_rows": split_counts["train"],
        "train_proofs": len(per_proof),
        "train_files": len(files),
        "record_keys": sorted(keys_seen),
        "horizon_at_least": {str(k): atleast(k) for k in (1,2,3,5,10,15,20,30,50,100)},
        "horizon_hist_1_to_40": {str(k): hist.get(k,0) for k in range(1,41)},
        "max_horizon": max(lengths) if lengths else 0,
        "mean_horizon": sum(lengths)/len(lengths) if lengths else 0.0,
        "median_horizon": sorted(lengths)[len(lengths)//2] if lengths else 0,
        "train_proofs_with_closed_last_step": closed_last,
        "top_30_tactic_heads": heads.most_common(30),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k not in ("horizon_hist_1_to_40","top_30_tactic_heads","record_keys")}, indent=2))
    print("hist:", res["horizon_hist_1_to_40"])

main()
