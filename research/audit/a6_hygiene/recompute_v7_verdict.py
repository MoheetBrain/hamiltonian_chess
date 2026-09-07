"""A6 / Q18 -- offline re-derivation of the Fitness V7 verdict from the stored artifact.

Reimplements, INDEPENDENTLY of arena.experiments.fitness_v7, every quantity the V7 run
recorded, using ONLY the 864 stored rows plus the recorded qualification rule.  Makes NO
model call, imports NO arena module, reads NO sealed split.

Run:  .venv/bin/python research/audit/a6_hygiene/recompute_v7_verdict.py
Exit 0 iff every recomputed value matches the recorded value.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ART = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")

POSITIVE_VARIANTS = {"ORIGINAL", "COUNTERFACTUAL"}

mismatches: list[str] = []
checks = 0


def close(a: Any, b: Any, tol: float = 1e-9) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) <= tol
    return a == b


def check(label: str, got: Any, want: Any, tol: float = 1e-9) -> None:
    global checks
    checks += 1
    if not close(got, want, tol):
        mismatches.append(f"{label}: recomputed={got!r} recorded={want!r}")


# --------------------------------------------------------------- reimplemented primitives


def summarize(rows: list[dict[str, Any]], q0_rate: float) -> dict[str, Any]:
    """Independent reimplementation of arena.experiments.fitness_v5.summarize (v5:664-722)."""
    base = [r for r in rows if r["variant"] in POSITIVE_VARIANTS]
    negative = [r for r in rows if r["truth_kind"] == "NEGATIVE_CONTROL_TARGET"]

    def acc(vals: list[dict[str, Any]]) -> float:
        return sum(r["correct"] for r in vals) / len(vals) if vals else 0.0

    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_family[row["family_id"]][row["variant"]] = row
    flips = choice_flips = invariant = invariant_pairs = 0
    for variants in by_family.values():
        o, c = variants.get("ORIGINAL"), variants.get("COUNTERFACTUAL")
        if o and c:
            flips += bool(o["correct"] and c["correct"])
            choice_flips += bool(
                o["selected_hash"] is not None
                and c["selected_hash"] is not None
                and o["selected_hash"] != c["selected_hash"]
            )
        for name, swap in (
            ("ORIGINAL", "SWAPPED_ORIGINAL"),
            ("COUNTERFACTUAL", "SWAPPED_COUNTERFACTUAL"),
        ):
            left, right = variants.get(name), variants.get(swap)
            if left and right:
                invariant_pairs += 1
                invariant += bool(
                    left["selected_hash"] is not None
                    and left["selected_hash"] == right["selected_hash"]
                )
    families = len(by_family)
    positive, negative_acc = acc(base), acc(negative)
    parsed_base = [r["parsed_index"] for r in base if r["parsed_index"] is not None]
    return {
        "q0_valid_rate": q0_rate,
        "positive_accuracy": positive,
        "negative_target_accuracy": negative_acc,
        "positive_negative_gap": positive - negative_acc,
        "semantic_flip_consistency": flips / families if families else 0.0,
        "choice_flip_rate": choice_flips / families if families else 0.0,
        "position_invariance": invariant / invariant_pairs if invariant_pairs else 0.0,
        "largest_answer_share": (
            max(Counter(parsed_base).values()) / max(1, len(parsed_base)) if parsed_base else 1.0
        ),
        "valid_response_rate": (
            sum(r["parsed_index"] is not None for r in rows) / len(rows) if rows else 0.0
        ),
        "context_truncated_rows": sum(r["cause"] == "INPUT_CONTEXT_TRUNCATION" for r in rows),
        "output_truncated_rows": sum(r["cause"] == "OUTPUT_TRUNCATION" for r in rows),
        "cause_totals": dict(Counter(r["cause"] for r in rows)),
        "mechanisms": sorted({r["mechanism"] for r in rows}),
        "families": families,
        "positive_examples": len(base),
        "mean_prompt_tokens": (
            sum(r["prompt_tokens"] for r in rows) / len(rows) if rows else 0.0
        ),
    }


def answer_entropy_bits(rows: list[dict[str, Any]]) -> float:
    counts = Counter(r["parsed_index"] for r in rows if r["parsed_index"] is not None)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c)


def select_frontier_level(accs: dict[int, float], rule: dict[str, Any], target: float,
                          win_lo: float, win_hi: float) -> dict[str, Any]:
    explicit = float(accs.get(0, 0.0))
    base = {"frontier_target": target, "qualifying_window": [win_lo, win_hi],
            "explicit_positive_accuracy": explicit}
    if explicit < float(rule["explicit_positive_min"]):
        return {**base, "selected_level": None, "verdict": "VOID_INSTRUMENT_LIMIT"}
    cands = [(lvl, a) for lvl, a in sorted(accs.items()) if lvl >= 1]
    if not cands:
        return {**base, "selected_level": None, "verdict": "VOID_INSTRUMENT_LIMIT"}
    level, accuracy = min(cands, key=lambda it: (abs(it[1] - target), it[0]))
    lo, hi = float(rule["frontier_band"][0]), float(rule["frontier_band"][1])
    verdict = ("VOID_CEILING" if accuracy > hi else
               "VOID_FLOOR" if accuracy < lo else "FRONTIER_SELECTED")
    return {**base,
            "selected_level": level if verdict == "FRONTIER_SELECTED" else None,
            "candidate_level": level, "candidate_accuracy": accuracy,
            "distance_to_target": abs(accuracy - target),
            "candidate_inside_qualifying_window": win_lo <= accuracy <= win_hi,
            "verdict": verdict}


def qualify(summary: dict[str, Any], audit: dict[str, Any], q0_rate: float,
            rule: dict[str, Any]) -> dict[str, Any]:
    eps = float(rule["shortcut_margin_gate_epsilon"])
    positive = float(summary["positive_accuracy"])
    best = float(audit.get("best_shortcut_accuracy", 1.0))
    margin = positive - best
    c = {
        "q0": "PASS" if q0_rate >= float(rule["q0_valid_rate_min"]) else "VOID_VALIDITY",
        "valid_response": "PASS" if summary["valid_response_rate"] >= float(
            rule["valid_response_rate_min"]) else "VOID_VALIDITY",
        "context": "PASS" if summary["context_truncated_rows"] <= int(
            rule["context_truncated_rows_max"]) else "VOID_CONTEXT",
        "sample_size": "PASS" if summary["positive_examples"] >= int(
            rule["min_positives_for_gates"]) else "VOID_VALIDITY",
        "negative_collapse": "PASS" if summary["positive_negative_gap"] >= float(
            rule["positive_negative_gap_min"]) else "VOID_NEGATIVE_CONTROL",
        "answer_share": "PASS" if summary["largest_answer_share"] <= float(
            rule["largest_answer_share_max"]) else "VOID_POSITION_SHARE",
        "position_invariance": "PASS" if summary["position_invariance"] >= float(
            rule["position_invariance_min"]) else "VOID_POSITION",
        "shortcut_absolute": "PASS" if best <= float(
            rule["shortcut_rule_max"]) else "VOID_SHORTCUT",
        "shortcut_margin": "PASS" if margin >= float(
            rule["shortcut_margin"]) - eps else "VOID_SHORTCUT",
    }
    fails = [code for code in c.values() if code != "PASS"]
    return {"checks": c, "shortcut_margin_observed": margin,
            "shortcut_margin_required": float(rule["shortcut_margin"]),
            "best_shortcut_accuracy": best,
            "best_shortcut_feature": audit.get("best_shortcut_feature"),
            "positive_accuracy": positive, "qualified": not fails,
            "verdict": fails[0] if fails else "QUALIFIED",
            "all_failures": sorted({n for n, code in c.items() if code != "PASS"})}


# ------------------------------------------------------------------------------- main

d = json.load(ART.open())
rule = d["qualification_rule"]
rows = d["rows"]
q0_rows = d["q0"]["rows"]

print("=" * 78)
print("A6/Q18  OFFLINE RE-DERIVATION OF THE FITNESS V7 VERDICT")
print("=" * 78)

# ---- 0. call accounting (Q11, Q14, Q15) --------------------------------------------
print("\n[0] CALL ACCOUNTING")
q0_scopes = Counter(r["cache_scope"] for r in q0_rows)
row_scopes = Counter(r["cache_scope"] for r in rows)
print(f"    len(rows)                 = {len(rows)}")
print(f"    len(q0.rows)              = {len(q0_rows)}   scopes={dict(q0_scopes)}")
print(f"    rows cache_scope totals   = {dict(row_scopes)}")
print(f"    recorded cache_scope_totals = {d['cache_scope_totals']}")
print(f"    recorded fresh_calls_made   = {d['fresh_calls_made']}")
print(f"    recorded planned_model_calls= {d['planned_model_calls']}")
print(f"    recorded dev_pool_probes    = {d['dev_pool_probes']}")
print(f"    len(rows) + len(q0.rows)    = {len(rows) + len(q0_rows)}")
check("cache_scope_totals", dict(row_scopes), d["cache_scope_totals"])
check("fresh_calls_made", sum(r["cache_scope"] == "FRESH" for r in rows), d["fresh_calls_made"])
check("planned == rows + q0", len(rows) + len(q0_rows), d["planned_model_calls"])
check("dev_pool_probes == len(rows)", len(rows), d["dev_pool_probes"])
check("q0 rate", sum(r["correct"] for r in q0_rows) / len(q0_rows), d["q0"]["rate"])
check("cache_hit False everywhere", sum(r["cache_hit"] for r in rows), 0)

# ---- 1. row identity invariants -----------------------------------------------------
print("\n[1] ROW IDENTITY INVARIANTS (single-condition run?)")
for f in ("experiment_version", "instrument_version", "model_digest", "model_template_hash",
          "runtime_hash", "decoding_hash", "runtime_condition", "solver_kind"):
    vals = {r[f] for r in rows}
    print(f"    rows.{f:22s} distinct={len(vals)}  {sorted(vals) if len(vals) < 3 else ''}")
    check(f"rows.{f} single-valued", len(vals), 1)
for f in ("experiment_version", "instrument_version", "model_digest", "model_template_hash",
          "runtime_hash", "decoding_hash", "solver_kind"):
    a, b = {r[f] for r in rows}, {r[f] for r in q0_rows}
    check(f"q0/rows agree on {f}", a, b)
ph = [r["prompt_hash"] for r in rows]
print(f"    distinct prompt_hash      = {len(set(ph))} / {len(ph)}"
      f"   <-- AUDITOR PROBE (not a recorded value); see section [6]")
pid = [r["probe_id"] for r in rows]
print(f"    distinct probe_id         = {len(set(pid))} / {len(pid)}")
check("probe_id unique per row", len(set(pid)), len(rows))
print(f"    distinct q0 prompt_hash   = {len({r['prompt_hash'] for r in q0_rows})} / {len(q0_rows)}")
errs = [r for r in rows if r.get("error")]
print(f"    rows with error field set = {len(errs)}")
check("no errored rows", len(errs), 0)

# ---- 2. shortcut-audit internal consistency ----------------------------------------
print("\n[2] SHORTCUT AUDIT INTERNAL CONSISTENCY (probe-bank property)")
for mech, per_level in sorted(d["shortcut_audit_by_level"].items()):
    for lvl, a in sorted(per_level.items()):
        sc = a["scores"]
        worst = max(sc, key=lambda n: abs(sc[n] - 0.5))
        worst_score = max(sc[worst], 1.0 - sc[worst])
        status = "CLEAN" if worst_score <= float(rule["shortcut_rule_max"]) else "LEAKS"
        check(f"{mech} L{lvl} best_shortcut_accuracy", worst_score, a["best_shortcut_accuracy"])
        check(f"{mech} L{lvl} shortcut status", status, a["status"])
        # feature name can tie; only assert the score reproduces
        if worst != a["best_shortcut_feature"]:
            print(f"    NOTE {mech} L{lvl}: tie on worst rule "
                  f"(recomputed {worst!r} vs recorded {a['best_shortcut_feature']!r}), "
                  f"same score {worst_score}")
print("    all per-level best_shortcut_accuracy + status reproduce from `scores`")

# ---- 3. per (mechanism, level) recompute -------------------------------------------
print("\n[3] PER-CELL RECOMPUTATION FROM THE 864 STORED ROWS")
by_cell: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
for r in rows:
    by_cell[(r["mechanism"], int(r["level"]))].append(r)

q0_rate = sum(r["correct"] for r in q0_rows) / len(q0_rows)
recomputed_qualified: list[str] = []
report: dict[str, Any] = {}

for mech in sorted(d["mechanisms"]):
    print(f"\n  -- {mech}")
    rec = d["mechanisms"][mech]
    accs: dict[int, float] = {}
    summaries: dict[int, dict[str, Any]] = {}
    for lvl in range(4):
        cell = by_cell[(mech, lvl)]
        s = summarize(cell, q0_rate)
        summaries[lvl] = s
        accs[lvl] = float(s["positive_accuracy"])
        pos = [r for r in cell if r["variant"] in POSITIVE_VARIANTS]
        H = answer_entropy_bits(pos)
        rl = next(x for x in rec["ladder"] if x["level"] == lvl)
        audit = d["shortcut_audit_by_level"][mech][str(lvl)]
        margin = accs[lvl] - float(audit["best_shortcut_accuracy"])
        inside = 0.70 <= accs[lvl] <= 0.85
        for label, got, want in (
            ("positive_accuracy", accs[lvl], rl["positive_accuracy"]),
            ("largest_answer_share", s["largest_answer_share"], rl["largest_answer_share"]),
            ("answer_entropy_bits", H, rl["answer_entropy_bits"]),
            ("valid_response_rate", s["valid_response_rate"], rl["valid_response_rate"]),
            ("destroyed_accuracy", s["negative_target_accuracy"], rl["destroyed_accuracy"]),
            ("positive_negative_gap", s["positive_negative_gap"], rl["positive_negative_gap"]),
            ("position_invariance", s["position_invariance"], rl["position_invariance"]),
            ("positive_examples", s["positive_examples"], rl["positive_examples"]),
            ("shortcut_margin_at_this_level", margin, rl["shortcut_margin_at_this_level"]),
            ("inside_qualifying_window", inside, rl["inside_qualifying_window"]),
            ("cache_scopes", dict(Counter(r["cache_scope"] for r in cell)), rl["cache_scopes"]),
        ):
            check(f"{mech} L{lvl} {label}", got, want)
        print(f"     L{lvl}: n={len(cell):3d} pos={len(pos):2d} acc={accs[lvl]:.4f} "
              f"share={s['largest_answer_share']:.4f} H={H:.4f} "
              f"destroyed={s['negative_target_accuracy']:.4f} "
              f"posinv={s['position_invariance']:.4f} "
              f"shortcut={audit['best_shortcut_accuracy']:.4f} margin={margin:+.4f}")

    sel = select_frontier_level(accs, rule, float(d["frontier"]["frontier_target"]),
                                float(d["frontier"]["window_low"]),
                                float(d["frontier"]["window_high"]))
    rsel = rec["selection"]
    for k in ("verdict", "selected_level", "explicit_positive_accuracy"):
        check(f"{mech} selection.{k}", sel[k], rsel[k])
    for k in ("candidate_level", "candidate_accuracy", "distance_to_target",
              "candidate_inside_qualifying_window"):
        if k in rsel:
            check(f"{mech} selection.{k}", sel[k], rsel[k])
    print(f"     selection: verdict={sel['verdict']} "
          f"candidate_level={sel.get('candidate_level')} "
          f"selected_level={sel['selected_level']} "
          f"(recorded verdict={rsel['verdict']} selected={rsel['selected_level']})")

    lvl = sel["selected_level"]
    if lvl is not None:
        q = qualify(summaries[int(lvl)], d["shortcut_audit_by_level"][mech][str(lvl)],
                    q0_rate, rule)
        rq = rec["qualification"]
        for k in ("verdict", "qualified", "all_failures", "checks",
                  "shortcut_margin_observed", "best_shortcut_accuracy", "positive_accuracy"):
            check(f"{mech} qualification.{k}", q[k], rq[k])
        # full_family_summary must reproduce too
        rfs = rec["full_family_summary"]
        for k in sorted(rfs):
            check(f"{mech} full_family_summary.{k}", summaries[int(lvl)][k], rfs[k])
        print(f"     qualification @L{lvl}: {q['verdict']}  qualified={q['qualified']}  "
              f"failures={q['all_failures']}   (recorded {rq['verdict']})")
        if q["qualified"]:
            recomputed_qualified.append(mech)
        report[mech] = {"selected_level": lvl, "verdict": q["verdict"]}
    else:
        rq = rec["qualification"]
        check(f"{mech} qualification.verdict", sel["verdict"], rq["verdict"])
        print(f"     qualification: {sel['verdict']} (no level selected)  "
              f"(recorded {rq['verdict']})")
        report[mech] = {"selected_level": None, "verdict": sel["verdict"]}

# ---- 4. instrument verdict ----------------------------------------------------------
print("\n[4] INSTRUMENT-LEVEL VERDICT")
min_q = int(rule["minimum_qualified_mechanisms"])
instrument_qualified = len(recomputed_qualified) >= min_q
print(f"    recomputed qualified mechanisms = {recomputed_qualified}")
print(f"    recorded  qualified_mechanisms  = {d['qualified_mechanisms']}")
print(f"    minimum_qualified_mechanisms    = {min_q}")
print(f"    recomputed instrument_qualified = {instrument_qualified}")
print(f"    recorded  instrument_qualified  = {d['instrument_qualified']}")
check("qualified_mechanisms", sorted(recomputed_qualified), sorted(d["qualified_mechanisms"]))
check("instrument_qualified", instrument_qualified, d["instrument_qualified"])
check("selected_levels", {m: v["selected_level"] for m, v in report.items()
                          if m in recomputed_qualified}, d["selected_levels"])

# ---- 5. frontier target derivation --------------------------------------------------
print("\n[5] FRONTIER TARGET DERIVATION")
derived = ((float(rule["destroyed_expected"]) + float(rule["positive_negative_gap_min"]))
           + float(rule["frontier_band"][1])) / 2
print(f"    ((0.5 + 0.2) + 0.85)/2 = {derived!r}   recorded={d['frontier']['frontier_target']!r}")
check("frontier_target", derived, d["frontier"]["frontier_target"])
check("window_low == destroyed+gap", 0.5 + 0.2, d["frontier"]["window_low"])

# ---- 6. AUDITOR PROBE: is the negative-control arm an arithmetic identity? ----------
print("\n[6] AUDITOR PROBE -- NEGATIVE-CONTROL ARM (not a recorded-value check)")
DEST = {"DESTROYED_ORIGINAL", "DESTROYED_COUNTERFACTUAL"}
dest = [r for r in rows if r["variant"] in DEST]
groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
for r in dest:
    groups[r["prompt_hash"]].append(r)
collided = {k: v for k, v in groups.items() if len(v) > 1}
in_group = sum(len(v) for v in collided.values())
half = all(sum(x["correct"] for x in v) * 2 == len(v) for v in collided.values())
same_out = all(len({x["raw_output"] for x in v}) == 1 for v in collided.values())
opposed = all(len({x["expected_index"] for x in v}) > 1 for v in collided.values())
print(f"    destroyed rows              = {len(dest)} / {len(rows)} "
      f"({len(dest) / len(rows):.1%} of the call budget)")
print(f"    identical-prompt groups     = {len(collided)}  covering {in_group}/{len(dest)} rows")
print(f"    every group opposite label  = {opposed}")
print(f"    every group byte-identical output = {same_out}")
print(f"    every group scores exactly half correct = {half}")
print(f"    destroyed_accuracy overall  = {sum(r['correct'] for r in dest) / len(dest)}")
print("    => destroyed_accuracy is an ARITHMETIC IDENTITY (0.5 exactly), not a measurement;")
print("       positive_negative_gap == positive_accuracy - 0.5, so the `negative_collapse`")
print("       gate is a restatement of `positive_accuracy >= window_low` (0.70).")
gap_ok = all(
    abs((float(rl["positive_accuracy"]) - 0.5) - float(rl["positive_negative_gap"])) < 1e-12
    for m in d["mechanisms"].values() for rl in m["ladder"]
)
print(f"    gap == accuracy - 0.5 in all 12 cells: {gap_ok}")

# ---- verdict ------------------------------------------------------------------------
print("\n" + "=" * 78)
print(f"CHECKS RUN: {checks}    MISMATCHES: {len(mismatches)}")
for m in mismatches:
    print("  MISMATCH " + m)
print("VERDICT RECOMPUTES EXACTLY FROM STORED ROWS: "
      + ("YES" if not mismatches else "NO"))
print("=" * 78)
sys.exit(0 if not mismatches else 1)
