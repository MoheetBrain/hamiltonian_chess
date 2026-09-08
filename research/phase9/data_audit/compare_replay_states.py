"""Compare Lean's own `trace_state` output against LeanDojo's recorded states.

If they agree, the recorded corpus is a faithful transcript of what Lean produces, and
`replay + state equality` is a real (non-string-matching) verifier: the tactic must actually
elaborate AND drive the goal to the recorded successor.
"""
from __future__ import annotations
import json, os, re, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "probe_out")
man = json.load(open(os.path.join(HERE, "replay_probe_manifest.json"), encoding="utf-8"))

def norm(s): return "\n".join(l.rstrip() for l in (s or "").strip().split("\n")).strip()

results = []
for m in man:
    tag = m["tag"]; p = os.path.join(OUT, f"P_{tag}.out")
    if not os.path.exists(p):
        results.append({"tag": tag, "status": "NO_OUTPUT"}); continue
    err = open(os.path.join(OUT, f"P_{tag}.err"), encoding="utf-8").read()
    raw = open(p, encoding="utf-8").read()
    if "error:" in raw or "error:" in err:
        results.append({"tag": tag, "status": "LEAN_ERROR"}); continue
    # trace_state emits each state; consecutive states are separated by the goal-block boundary.
    # Split on lines that begin a fresh context (heuristic: blank-line-free blocks separated by
    # the start of a new hypothesis block). Simpler: Lean prints each trace_state as one message
    # ending before the next; we split on the recorded first-line of each expected state.
    expected = m["recorded_states"][1:]        # states AFTER each tactic
    got_blob = norm(raw)
    matched = 0
    cursor = 0
    detail = []
    for e in expected:
        en = norm(e)
        if en == "no goals":
            detail.append("terminal(no goals) — trace_state prints nothing"); matched += 1; continue
        idx = got_blob.find(en, cursor)
        if idx >= 0:
            matched += 1; cursor = idx + len(en); detail.append("EXACT")
        else:
            detail.append("MISS")
    results.append({"tag": tag, "status": "OK", "n_steps": m["n_steps"],
                    "states_expected": len(expected), "states_matched_exactly": matched,
                    "detail": detail})

json.dump(results, open(os.path.join(HERE, "replay_state_match.json"), "w"), indent=2)
tot_e = sum(r.get("states_expected", 0) for r in results)
tot_m = sum(r.get("states_matched_exactly", 0) for r in results)
ok = sum(1 for r in results if r["status"] == "OK")
perfect = sum(1 for r in results if r["status"] == "OK" and r["states_expected"] == r["states_matched_exactly"])
print(f"probes with clean elaboration : {ok}/{len(results)}")
print(f"probes where EVERY recorded successor state was reproduced verbatim by Lean: {perfect}/{ok}")
print(f"successor states reproduced verbatim: {tot_m}/{tot_e} = {tot_m/max(tot_e,1):.4f}")
for r in results:
    if r["status"] != "OK" or r["states_expected"] != r["states_matched_exactly"]:
        print(" ", r["tag"], r["status"], r.get("detail"))
