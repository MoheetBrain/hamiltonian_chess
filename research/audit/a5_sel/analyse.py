"""A5 master analysis: selector arithmetic, shortcut-vs-target correlation, error taxonomy.

READ-ONLY. Zero model calls. Rebuilds the DEV probe pool deterministically (hash-verified
against the artifact) so every probe's shortcut prediction can be recomputed offline.

  python -m research.audit.a5_sel.analyse
"""
from __future__ import annotations
import json, math, pathlib, sys, statistics, random
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.experiments import fitness_v7 as v7                      # noqa: E402
from arena.experiments.fitness_v5 import build_dev_pool             # noqa: E402
from arena.canonical.schema import canonical_json, stable_hash      # noqa: E402

ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = ROOT / "research/audit/a5_sel"

POS = v7.POSITIVE_VARIANTS


# ---------------------------------------------------------------- shortcut rules (V5 verbatim)
def _names(p):
    return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))

def _text(p):
    return canonical_json(p.state.to_dict(include_display_identity=False))

RULES = {
    "always_first_option":      lambda p: 0,
    "always_second_option":     lambda p: 1,
    "first_mentioned_in_state": lambda p: 0 if _text(p).find(f'"{_names(p)[0]}"') <= _text(p).find(f'"{_names(p)[1]}"') else 1,
    "last_mentioned_in_state":  lambda p: 0 if _text(p).rfind(f'"{_names(p)[0]}"') >= _text(p).rfind(f'"{_names(p)[1]}"') else 1,
    "more_frequent_in_state":   lambda p: 0 if _text(p).count(f'"{_names(p)[0]}"') >= _text(p).count(f'"{_names(p)[1]}"') else 1,
    "shorter_option_text":      lambda p: 0 if (len(_names(p)[0]), _names(p)[0]) <= (len(_names(p)[1]), _names(p)[1]) else 1,
    "alphabetically_first":     lambda p: 0 if _names(p)[0] <= _names(p)[1] else 1,
}


def pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else float("nan")


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(rank(xs), rank(ys))


def perm_p(xs, ys, stat=pearson, iters=200_000, seed=11):
    obs = stat(xs, ys)
    rng = random.Random(seed)
    ys2 = list(ys)
    hits = 0
    for _ in range(iters):
        rng.shuffle(ys2)
        if abs(stat(xs, ys2)) >= abs(obs) - 1e-12:
            hits += 1
    return obs, (hits + 1) / (iters + 1)


def main() -> int:
    art = json.loads(ART.read_text())
    probes = {p.probe_id: p for p in build_dev_pool(ROOT)}
    assert stable_hash([p.to_dict() for p in build_dev_pool(ROOT)]) == art["dev_pool_hash"]
    rows = art["rows"]
    report: dict = {}

    # ---------------------------------------------------------------- 1. per-level master table
    table = []
    for mech in v7.MECHANISMS:
        m = art["mechanisms"][mech]
        for rung in m["ladder"]:
            lvl = rung["level"]
            cell = [r for r in rows if r["mechanism"] == mech and r["level"] == lvl]
            pos = [r for r in cell if r["variant"] in POS]
            toks = [r["prompt_tokens"] for r in pos]
            chars = [r["prompt_chars"] for r in pos]
            # state complexity proxy: canonical-state byte length & object count
            sizes, objs = [], []
            for r in pos:
                p = probes[r["probe_id"]]
                t = _text(p)
                sizes.append(len(t))
                objs.append(t.count('"identity"'))
            acc = rung["positive_accuracy"]
            table.append({
                "mechanism": mech, "level": lvl,
                "params": rung["parameters"],
                "accuracy": acc,
                "dist_to_target_v7": abs(acc - v7.FRONTIER_TARGET),
                "dist_to_target_v5": abs(acc - 0.625),
                "best_shortcut": rung["best_shortcut_accuracy"],
                "best_shortcut_feature": rung["best_shortcut_feature"],
                "shortcut_margin": rung["shortcut_margin_at_this_level"],
                "shortcut_status": rung["shortcut_status"],
                "chance_baseline": 0.5,
                "largest_answer_share": rung["largest_answer_share"],
                "answer_entropy_bits": rung["answer_entropy_bits"],
                "position_invariance": rung["position_invariance"],
                "destroyed_accuracy": rung["destroyed_accuracy"],
                "mean_prompt_tokens": statistics.mean(toks),
                "mean_prompt_chars": statistics.mean(chars),
                "mean_state_bytes": statistics.mean(sizes),
                "mean_state_objects": statistics.mean(objs),
                "inside_window": rung["inside_qualifying_window"],
                "scores": art["shortcut_audit_by_level"][mech][str(lvl)]["scores"],
            })
    report["per_level_table"] = table

    # ------------------------------------------- 2. closeness-to-target vs shortcut correlation
    corr = {}
    for tag, key in (("v7_target_0.775", "dist_to_target_v7"), ("v5_target_0.625", "dist_to_target_v5")):
        for scope, sel in (("all_12_cells", lambda t: True),
                           ("levels_1_3_only", lambda t: t["level"] >= 1)):
            sub = [t for t in table if sel(t)]
            xs = [t[key] for t in sub]
            ys = [t["best_shortcut"] for t in sub]
            r, p = perm_p(xs, ys, pearson)
            rs, ps = perm_p(xs, ys, spearman)
            corr[f"{tag}|{scope}"] = {
                "n": len(sub), "pearson_r": r, "pearson_perm_p": p,
                "spearman_rho": rs, "spearman_perm_p": ps,
                "note": "negative r => closer to target associates with STRONGER shortcut",
            }
    # also accuracy vs shortcut directly
    xs = [t["accuracy"] for t in table]; ys = [t["best_shortcut"] for t in table]
    r, p = perm_p(xs, ys, pearson)
    corr["accuracy_vs_shortcut|all_12_cells"] = {"n": 12, "pearson_r": r, "pearson_perm_p": p}
    report["closeness_vs_shortcut"] = corr

    # --------------------------------------------------- 3. selector resampling / choice stability
    # Binomial resampling of each level's 24 positives at its observed accuracy, then re-run
    # the ACTUAL selector on the resampled accuracies.
    def selector(accs, target):
        cands = [(l, a) for l, a in sorted(accs.items()) if l >= 1]
        return min(cands, key=lambda it: (abs(it[1] - target), it[0]))

    rng = random.Random(20260905)
    resamp = {}
    for mech in v7.MECHANISMS:
        obs = {t["level"]: t["accuracy"] for t in table if t["mechanism"] == mech}
        for target, tag in ((v7.FRONTIER_TARGET, "v7_0.775"), (0.625, "v5_0.625")):
            picks, verdicts = Counter(), Counter()
            ITER = 100_000
            for _ in range(ITER):
                draw = {l: sum(rng.random() < a for _ in range(24)) / 24 for l, a in obs.items()}
                lvl, acc = selector(draw, target)
                picks[lvl] += 1
                verdicts["VOID_CEILING" if acc > 0.85 else "VOID_FLOOR" if acc < 0.35
                          else "FRONTIER_SELECTED"] += 1
            actual = selector(obs, target)[0]
            resamp[f"{mech}|{tag}"] = {
                "observed_accuracies": obs,
                "actual_pick": actual,
                "pick_distribution": {str(k): v / ITER for k, v in sorted(picks.items())},
                "p_different_level_than_actual": 1 - picks[actual] / ITER,
                "verdict_distribution": {k: v / ITER for k, v in verdicts.items()},
            }
    report["selector_resampling"] = resamp

    # ---- 3b. conditional bias: is the selected level's OBSERVED accuracy a favourable draw?
    #      Simulate: true accuracy = observed; measure E[observed_selected - true_selected].
    bias = {}
    for mech in v7.MECHANISMS:
        truth = {t["level"]: t["accuracy"] for t in table if t["mechanism"] == mech}
        for target, tag in ((v7.FRONTIER_TARGET, "v7_0.775"), (0.625, "v5_0.625")):
            ITER = 100_000
            deltas, in_win, favourable = [], 0, 0
            for _ in range(ITER):
                draw = {l: sum(rng.random() < a for _ in range(24)) / 24 for l, a in truth.items()}
                lvl, acc = selector(draw, target)
                deltas.append(acc - truth[lvl])
                if 0.70 <= acc <= 0.85: in_win += 1
                # "favourable noise draw" = observed pulled TOWARD the target vs its own truth
                if abs(acc - target) < abs(truth[lvl] - target): favourable += 1
            bias[f"{mech}|{tag}"] = {
                "E[observed_minus_true_at_selected]": statistics.mean(deltas),
                "sd": statistics.pstdev(deltas),
                "P(selected level's observed acc is a target-favourable noise draw)": favourable / ITER,
                "P(candidate lands inside [0.70,0.85])": in_win / ITER,
            }
    report["selection_bias_simulation"] = bias

    # -------------------------------------------------------- 4. ERROR TAXONOMY + shortcut match
    tax = []
    for r in rows:
        p = probes[r["probe_id"]]
        preds = {name: fn(p) for name, fn in RULES.items()}
        tax.append({
            "mechanism": r["mechanism"], "level": r["level"], "variant": r["variant"],
            "truth_kind": r["truth_kind"], "cause": r["cause"], "correct": r["correct"],
            "expected_index": r["expected_index"], "parsed_index": r["parsed_index"],
            "raw_output": r["raw_output"], "probe_id": r["probe_id"],
            "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
            "done_reason": r["done_reason"], "error": r["error"],
            "preds": preds,
            "options": list(_names(p)),
        })
    report["_row_count"] = len(tax)

    math_rows = [t for t in tax if t["truth_kind"] == "MATHEMATICAL"]
    wrong = [t for t in math_rows if not t["correct"]]
    report["taxonomy_headline"] = {
        "mathematical_rows": len(math_rows),
        "wrong_rows": len(wrong),
        "format_failures": sum(1 for t in tax if t["parsed_index"] is None),
        "truncations": sum(1 for t in tax if t["done_reason"] != "stop"),
        "adapter_errors": sum(1 for t in tax if t["error"] is not None),
        "distinct_raw_outputs": dict(Counter(t["raw_output"] for t in tax)),
    }

    # shortcut-following on wrong rows, per rule
    def match_stats(subset):
        out = {}
        for name in RULES:
            agree = sum(1 for t in subset if t["parsed_index"] == t["preds"][name])
            out[name] = {"n": len(subset), "answer_equals_rule": agree,
                         "rate": agree / len(subset) if subset else None}
        return out

    report["shortcut_following"] = {
        "ALL_wrong_mathematical_rows": match_stats(wrong),
        "wrong_POSITIVE_arm_rows": match_stats([t for t in wrong if t["variant"] in POS]),
        "wrong_SWAPPED_arm_rows": match_stats([t for t in wrong if t["variant"] not in POS]),
        "correct_mathematical_rows": match_stats([t for t in math_rows if t["correct"]]),
        "all_mathematical_rows": match_stats(math_rows),
        "destroyed_rows": match_stats([t for t in tax if t["truth_kind"] != "MATHEMATICAL"]),
    }

    # per mechanism x level distribution of wrong rows + shortcut match
    per_cell = {}
    for mech in v7.MECHANISMS:
        for lvl in range(4):
            cell = [t for t in math_rows if t["mechanism"] == mech and t["level"] == lvl]
            w = [t for t in cell if not t["correct"]]
            cellpos = [t for t in cell if t["variant"] in POS]
            wpos = [t for t in cellpos if not t["correct"]]
            fm = sum(1 for t in w if t["parsed_index"] == t["preds"]["first_mentioned_in_state"])
            fmpos = sum(1 for t in wpos if t["parsed_index"] == t["preds"]["first_mentioned_in_state"])
            per_cell[f"{mech}|L{lvl}"] = {
                "math_rows": len(cell), "wrong": len(w),
                "positive_rows": len(cellpos), "wrong_positive": len(wpos),
                "wrong_answer_equals_first_mentioned": fm,
                "wrong_positive_answer_equals_first_mentioned": fmpos,
                "rate_all_wrong": fm / len(w) if w else None,
                "answer_A_share_on_wrong": (sum(1 for t in w if t["parsed_index"] == 0) / len(w)) if w else None,
            }
    report["per_cell_errors"] = per_cell

    # ---------------------------------------------------- 5. twin pairs (determinism evidence)
    by_probe = {r["probe_id"]: r for r in rows}
    pairs = defaultdict(dict)
    for r in rows:
        if r["truth_kind"] == "NEGATIVE_CONTROL_TARGET":
            p = probes[r["probe_id"]]
            pairs[(r["mechanism"], r["level"], p.family_id)][r["variant"]] = r
    twin = {"pairs": 0, "identical_prompt_hash": 0, "identical_raw_output": 0,
            "opposite_expected": 0, "examples": []}
    for key, d2 in pairs.items():
        a = d2.get("DESTROYED_ORIGINAL"); b = d2.get("DESTROYED_COUNTERFACTUAL")
        if not (a and b): continue
        twin["pairs"] += 1
        twin["identical_prompt_hash"] += a["prompt_hash"] == b["prompt_hash"]
        twin["identical_raw_output"] += a["raw_output"] == b["raw_output"]
        twin["opposite_expected"] += a["expected_index"] != b["expected_index"]
    report["destroyed_twin_pairs"] = twin

    # cross-arm duplicate prompts (same prompt seen twice anywhere -> determinism check)
    ph = defaultdict(list)
    for r in rows:
        ph[r["prompt_hash"]].append(r)
    dupes = {k: v for k, v in ph.items() if len(v) > 1}
    consistent = sum(1 for v in dupes.values() if len({x["raw_output"] for x in v}) == 1)
    report["repeated_prompt_determinism"] = {
        "distinct_prompts": len(ph), "prompts_seen_more_than_once": len(dupes),
        "of_those_all_answers_identical": consistent,
        "total_rows_in_repeats": sum(len(v) for v in dupes.values()),
        "note": "identical answer to an identical prompt is CACHE-FREE only if cache_scope=FRESH",
        "cache_scope_totals": art["cache_scope_totals"],
    }

    (OUT / "a5_analysis.json").write_text(json.dumps(report, indent=1, default=str))
    (OUT / "a5_rows_annotated.json").write_text(json.dumps(tax, indent=0, default=str))
    print(json.dumps({k: v for k, v in report.items()
                      if k not in {"per_level_table", "_row_count"}}, indent=1, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
