"""Census of the LeanDojo Benchmark 4 v10 local trace: exact item counts per
candidate family.  Read-only; no model call.

Run:  python -m research.environments.measure_census
"""

from __future__ import annotations

import re
from collections import Counter

from research.environments import common as C

REVERSE_RE = re.compile(r"(?:^|[\[\s,])←|(?:^|[\[\s,])<-")


def head_of(tactic: str) -> str:
    stripped = tactic.strip()
    match = re.match(r"[A-Za-z_][A-Za-z0-9_'!?]*", stripped)
    return match.group(0) if match else stripped[:12]


def census(steps) -> dict:
    out = {
        "steps": 0,
        "theorems": set(),
        "with_premise_ge1": 0,
        "with_premise_eq1": 0,
        "with_premise_ge2": 0,
        "distinct_premises": set(),
        "closing_steps": 0,
        "multi_goal_before": 0,
        "multi_goal_after": 0,
        "rw_steps": 0,
        "rw_reverse": 0,
        "rw_multi_lemma": 0,
        "use_steps": 0,
        "obtain_steps": 0,
        "refine_hole_steps": 0,
        "no_op_steps": 0,
        "heads": Counter(),
    }
    for step in steps:
        out["steps"] += 1
        out["theorems"].add(step["theorem_key"])
        premises = step["premises"]
        if premises:
            out["with_premise_ge1"] += 1
            if len(premises) == 1:
                out["with_premise_eq1"] += 1
            else:
                out["with_premise_ge2"] += 1
            for premise in premises:
                out["distinct_premises"].add(premise["full_name"])
        after = step["state_after"]
        before = step["state_before"]
        if after.strip() == "no goals":
            out["closing_steps"] += 1
        if before.count("⊢") > 1:
            out["multi_goal_before"] += 1
        if after.count("⊢") > 1:
            out["multi_goal_after"] += 1
        if after == before:
            out["no_op_steps"] += 1
        head = head_of(step["tactic"])
        out["heads"][head] += 1
        if head in {"rw", "rwa", "simp_rw", "erw"}:
            out["rw_steps"] += 1
            if REVERSE_RE.search(step["tactic"]):
                out["rw_reverse"] += 1
            body = step["tactic"]
            if "[" in body and "," in body.split("[", 1)[1]:
                out["rw_multi_lemma"] += 1
        if head == "use":
            out["use_steps"] += 1
        if head in {"obtain", "rcases"}:
            out["obtain_steps"] += 1
        if head == "refine" and ("?_" in step["tactic"] or "?" in step["tactic"]):
            out["refine_hole_steps"] += 1
    out["theorems"] = len(out["theorems"])
    out["distinct_premises"] = len(out["distinct_premises"])
    out["heads"] = C.summarise_counter(out["heads"], 30)
    return out


def main() -> None:
    report = {
        "source": C.LEANDOJO_ROOT,
        "note": (
            "Exact counts, computed by parsing the local LeanDojo Benchmark 4 v10 "
            "JSON files.  No model call, no Lean, no network."
        ),
        "splits": {},
    }
    for split in ("random", "novel_premises"):
        for part in ("val", "test"):
            steps = list(C.iter_steps(iter(C.load_theorems(split, part))))
            report["splits"][f"{split}/{part}"] = census(steps)
    combined = []
    for part in ("val", "test"):
        combined.extend(C.iter_steps(iter(C.load_theorems("random", part))))
    report["splits"]["random/val+test"] = census(combined)
    print(C.write_json("census_leandojo_heldout.json", report))
    for key, value in report["splits"].items():
        print(
            key,
            "steps=%d" % value["steps"],
            "prem>=1=%d" % value["with_premise_ge1"],
            "prem==1=%d" % value["with_premise_eq1"],
            "close=%d" % value["closing_steps"],
            "rw=%d rev=%d" % (value["rw_steps"], value["rw_reverse"]),
            "multigoal_before=%d" % value["multi_goal_before"],
        )


if __name__ == "__main__":
    main()
