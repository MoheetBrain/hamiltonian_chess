"""A5: how many single row flips separate the V7 headline verdict from a different one?

READ-ONLY.   python -m research.audit.a5_sel.fragility
"""
from __future__ import annotations
import json, math, pathlib, sys, random
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from arena.experiments import fitness_v7 as v7   # noqa: E402

ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = ROOT / "research/audit/a5_sel"
N = 24


def main() -> int:
    art = json.loads(ART.read_text())
    rep = {"GATE_EPSILON": v7.GATE_EPSILON, "SHORTCUT_MARGIN": v7.SHORTCUT_MARGIN,
           "FRONTIER_TARGET": v7.FRONTIER_TARGET, "window": [v7.FRONTIER["window_low"],
                                                             v7.FRONTIER["window_high"]]}

    # ---- 1. exact k-of-24 thresholds for every gate at every level
    grid = []
    for mech in v7.MECHANISMS:
        for rung in art["mechanisms"][mech]["ladder"]:
            lvl, acc, sc = rung["level"], rung["positive_accuracy"], rung["best_shortcut_accuracy"]
            k = round(acc * N)
            need_margin = math.ceil((sc + v7.SHORTCUT_MARGIN - v7.GATE_EPSILON) * N - 1e-9)
            need_gap = math.ceil((0.5 + 0.20) * N - 1e-9)     # positive_negative_gap_min
            max_band = math.floor(0.85 * N + 1e-9)
            grid.append({
                "cell": f"{mech}|L{lvl}", "k_correct_of_24": k, "accuracy": acc,
                "best_shortcut": sc, "shortcut_k_of_24": round(sc * N),
                "k_needed_for_margin_gate": need_margin,
                "rows_short_of_margin_gate": max(0, need_margin - k),
                "k_needed_for_gap_gate": need_gap,
                "rows_short_of_gap_gate": max(0, need_gap - k),
                "k_max_under_ceiling_0.85": max_band,
                "rows_over_ceiling": max(0, k - max_band),
                "shortcut_absolute_pass(<=0.75)": sc <= 0.75,
            })
    rep["gate_distance_in_rows"] = grid

    # ---- 2. probability the selected mechanism's verdict flips under binomial resampling
    rng = random.Random(4242)
    flip = {}
    for mech in v7.MECHANISMS:
        rungs = {r["level"]: r for r in art["mechanisms"][mech]["ladder"]}
        accs = {l: r["positive_accuracy"] for l, r in rungs.items()}
        ITER = 200_000
        verdicts = Counter()
        for _ in range(ITER):
            draw = {l: sum(rng.random() < a for _ in range(N)) / N for l, a in accs.items()}
            cands = [(l, x) for l, x in sorted(draw.items()) if l >= 1]
            lvl, a = min(cands, key=lambda it: (abs(it[1] - v7.FRONTIER_TARGET), it[0]))
            if a > 0.85:
                verdicts["VOID_CEILING"] += 1; continue
            if a < 0.35:
                verdicts["VOID_FLOOR"] += 1; continue
            sc = rungs[lvl]["best_shortcut_accuracy"]
            if a - 0.5 < 0.20:
                verdicts[f"VOID_NEGATIVE_CONTROL@L{lvl}"] += 1; continue
            if sc > 0.75 or (a - sc) < v7.SHORTCUT_MARGIN - v7.GATE_EPSILON:
                verdicts[f"VOID_SHORTCUT@L{lvl}"] += 1; continue
            verdicts[f"QUALIFIED@L{lvl}"] += 1
        flip[mech] = {k: round(v / ITER, 5) for k, v in verdicts.most_common()}
        flip[mech]["P(QUALIFIED any level)"] = round(
            sum(v for k, v in verdicts.items() if k.startswith("QUALIFIED")) / ITER, 5)
    rep["verdict_distribution_under_resampling"] = flip
    rep["note"] = ("best_shortcut_accuracy is a fixed property of the probe bank (no model "
                   "sampling noise); all the noise enters through the 24-item accuracy.")

    (OUT / "a5_fragility.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
