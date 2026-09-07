"""A5 Q16/Q17: is V7 an independent measurement, or a byte-replay of the Phase-6 V5 run?

Compares the Phase-6 V5 qwen artifact against the V7 qwen artifact row-by-row on prompt_hash.
READ-ONLY.   python -m research.audit.a5_sel.replication
"""
from __future__ import annotations
import json, pathlib, sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
V5 = ROOT / "artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json"
V7 = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = ROOT / "research/audit/a5_sel"

def main() -> int:
    a, b = json.loads(V5.read_text()), json.loads(V7.read_text())
    rep = {
        "v5_instrument": a["instrument_version"], "v7_instrument": b["instrument_version"],
        "v5_rows": len(a.get("ladder_rows", [])) + sum(len(m.get("rows", [])) for m in a["mechanisms"].values()),
        "v7_rows": len(b["rows"]),
        "v5_arm_schedule": "positives (inferred: ladder_rows are positives only)",
        "v7_arm_schedule": b.get("arm_schedule"),
        "v5_model_digest": a["model"]["digest"], "v7_model_digest": b["model"]["digest"],
        "digests_equal": a["model"]["digest"] == b["model"]["digest"],
        "v5_runtime": a.get("runtime"), "v7_runtime": b.get("runtime"),
        "v5_dev_pool_hash": a.get("dev_pool_hash"), "v7_dev_pool_hash": b.get("dev_pool_hash"),
        "dev_pools_equal": a.get("dev_pool_hash") == b.get("dev_pool_hash"),
        "v5_cache_scopes": a.get("cache_scope_totals"), "v7_cache_scopes": b.get("cache_scope_totals"),
        "v5_fresh_calls": a.get("fresh_calls_made"), "v7_fresh_calls": b.get("fresh_calls_made"),
    }
    a_rows = list(a.get("ladder_rows", []))
    for mv in a.get("mechanisms", {}).values():
        a_rows.extend(mv.get("rows", []))
    ai = {r["prompt_hash"]: r for r in a_rows}
    bi = {r["prompt_hash"]: r for r in b["rows"]}
    common = set(ai) & set(bi)
    same_out = sum(1 for h in common if ai[h]["raw_output"] == bi[h]["raw_output"])
    rep["prompt_overlap"] = {
        "v5_distinct_prompts": len(ai), "v7_distinct_prompts": len(bi),
        "shared_prompts": len(common),
        "identical_raw_output_on_shared": same_out,
        "disagreements": len(common) - same_out,
        "agreement_rate": same_out / len(common) if common else None,
    }
    rep["disagreement_examples"] = [
        {"prompt_hash": h[:16], "v5": ai[h]["raw_output"], "v7": bi[h]["raw_output"],
         "mechanism": ai[h]["mechanism"], "level": ai[h]["level"], "variant": ai[h]["variant"]}
        for h in sorted(common) if ai[h]["raw_output"] != bi[h]["raw_output"]][:20]
    # ladder identity
    lad = {}
    for m in a["mechanisms"]:
        la = {r["level"]: r["positive_accuracy"] for r in a["mechanisms"][m]["ladder"]}
        lb = {r["level"]: r["positive_accuracy"] for r in b["mechanisms"][m]["ladder"]}
        lad[m] = {"v5": la, "v7": lb, "identical": la == lb,
                  "v5_selected": a["mechanisms"][m].get("selected_level"),
                  "v7_selected": b["mechanisms"][m].get("selected_level"),
                  "v5_verdict": a["mechanisms"][m].get("qualification", {}).get("verdict"),
                  "v7_verdict": b["mechanisms"][m].get("qualification", {}).get("verdict")}
    rep["ladders"] = lad
    # what the selector would pick at a grid of targets (sensitivity of the level choice)
    grid = {}
    for m in b["mechanisms"]:
        accs = {r["level"]: r["positive_accuracy"] for r in b["mechanisms"][m]["ladder"]}
        cands = [(l, x) for l, x in sorted(accs.items()) if l >= 1]
        picks = {}
        t = 0.30
        while t <= 1.0001:
            lvl = min(cands, key=lambda it: (abs(it[1] - t), it[0]))[0]
            picks[f"{t:.2f}"] = lvl
            t += 0.025
        # switch points
        sw, prev = [], None
        for k, v in picks.items():
            if prev is not None and v != prev:
                sw.append({"target_at_switch": k, "from_level": prev, "to_level": v})
            prev = v
        grid[m] = {"picks": picks, "switch_points": sw}
    rep["target_sensitivity_grid"] = grid
    (OUT / "a5_replication.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
