"""How much structure does a premise-selection item actually contain?

A task family can only discriminate between REPRESENTATIONS if the decision
depends on structure a representation can reorganise.  If an item is a
one-line goal with no hypotheses, every representation renders it the same way
and the family measures nothing about representation.

Run:  python -m research.environments.measure_representation_surface
"""

from __future__ import annotations

import json
import statistics

from research.environments import common as C


def context_lines(state: str) -> list[str]:
    body = state.split("⊢", 1)[0]
    return [line for line in body.split("\n") if line.strip()]


def main() -> None:
    report = {"populations": {}}
    for split in ("random", "novel_premises"):
        steps = []
        for part in ("val", "test"):
            steps.extend(C.iter_steps(iter(C.load_theorems(split, part))))
        single = [s for s in steps if len(s["premises"]) == 1]
        rows = []
        for step in single:
            state = step["state_before"]
            goal = C.goal_target(state)
            ctx = context_lines(state)
            goal_tokens = C.tokens_symbolic(goal)
            state_toks = C.tokens_symbolic(state)
            rows.append(
                {
                    "n_hypotheses": len(ctx),
                    "goal_tokens": goal_tokens,
                    "context_tokens": state_toks - goal_tokens,
                    "context_share": (state_toks - goal_tokens) / state_toks
                    if state_toks
                    else 0.0,
                    "goal_nesting_depth": max_paren_depth(goal),
                }
            )

        def summary(key):
            values = sorted(r[key] for r in rows)
            return {
                "p10": round(values[int(0.1 * len(values))], 3),
                "p50": round(values[int(0.5 * len(values))], 3),
                "p90": round(values[int(0.9 * len(values))], 3),
                "mean": round(statistics.fmean(values), 3),
            }

        report["populations"][split] = {
            "items": len(rows),
            "n_hypotheses": summary("n_hypotheses"),
            "goal_symbolic_tokens": summary("goal_tokens"),
            "context_symbolic_tokens": summary("context_tokens"),
            "context_share_of_state": summary("context_share"),
            "goal_parenthesis_nesting_depth": summary("goal_nesting_depth"),
            "items_with_zero_hypotheses": sum(1 for r in rows if r["n_hypotheses"] == 0),
            "items_with_ge5_hypotheses": sum(1 for r in rows if r["n_hypotheses"] >= 5),
        }
    print(C.write_json("representation_surface.json", report))
    print(json.dumps(report, indent=1))


def max_paren_depth(text: str) -> int:
    depth = best = 0
    for char in text:
        if char in "([{⟨":
            depth += 1
            best = max(best, depth)
        elif char in ")]}⟩":
            depth = max(0, depth - 1)
    return best


if __name__ == "__main__":
    main()
