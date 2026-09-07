"""AUDITOR 3 (A3) DIAGNOSTIC -- is `first_mentioned_in_state` an accidental string cue,
or a faithful readout of Lean's own term structure?

For every `formal_expression_depth` DEV probe this script recomputes, from the transcribed
Lean tree (not from the JSON string):

  * the ORACLE quantity            : max nesting depth of each candidate identifier
  * the PREORDER RANK              : index of the identifier's first occurrence in a preorder
                                     walk of the goal term, using the transcriber's own child
                                     order (`application` -> ("function", "argument"))
  * the HEAD-SPINE flag            : whether that first occurrence is reached by taking only
                                     `function` children of `lean.application` nodes, i.e. is
                                     the identifier the head of a curried application spine
  * agreement between `first_mentioned_in_state` (the JSON-string rule) and preorder rank

Curried application `f a b` transcribes as `app(app(f, a), b)`.  The head `f` is therefore
simultaneously the DEEPEST leaf on the spine and the FIRST leaf in preorder.  If that identity
holds on this bank, `first_mentioned_in_state` is not a string accident: it is Lean's
application encoding, read in a different order.

DIAGNOSTIC ONLY.  Not a re-scoring of V7.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from arena.canonical.schema import CanonicalExpression, canonical_json
from arena.experiments.fitness_v5 import POSITIVE_VARIANTS, build_dev_pool

HERE = Path(__file__).resolve().parent
OUT = HERE / "first_mention_probe.json"


def goal_term(state) -> CanonicalExpression:
    """The transcribed Lean target: `goal = deepest_local_reference(target)`."""
    return state.goal.args[0]


def walk(e: CanonicalExpression, depth=0, path=(), counter=None):
    if counter is None:
        counter = [0]
    idx = counter[0]
    counter[0] += 1
    yield e, depth, path, idx
    for i, child in enumerate(e.args):
        yield from walk(child, depth + 1, path + ((e.op, i),), counter)


def analyse(term: CanonicalExpression):
    depths, ranks, spine = defaultdict(list), {}, {}
    for node, d, path, idx in walk(term):
        if node.op == "lean.local_reference" and isinstance(node.value, str):
            depths[node.value].append(d)
            if node.value not in ranks:
                ranks[node.value] = idx
                spine[node.value] = all(
                    (op == "lean.application" and i == 0) for op, i in path
                )
    return {k: max(v) for k, v in depths.items()}, ranks, spine


def main() -> int:
    probes = [
        p
        for p in build_dev_pool(Path.cwd())
        if p.mechanism == "formal_expression_depth" and p.variant.value in POSITIVE_VARIANTS
    ]
    per_level = defaultdict(list)
    examples = []
    for p in probes:
        n0 = str(p.options[0].arguments[0].value)
        n1 = str(p.options[1].arguments[0].value)
        term = goal_term(p.state)
        maxd, ranks, spine = analyse(term)
        text = canonical_json(p.state.to_dict(include_display_identity=False))
        json_rule = 0 if text.find(f'"{n0}"') <= text.find(f'"{n1}"') else 1
        preorder_rule = (
            0 if ranks.get(n0, 10**9) <= ranks.get(n1, 10**9) else 1
        )
        depth_rule = 0 if maxd.get(n0, -1) >= maxd.get(n1, -1) else 1
        rec = {
            "level": p.level,
            "expected_index": p.expected_index,
            "json_first_mention_pred": json_rule,
            "preorder_rank_pred": preorder_rule,
            "depth_oracle_pred": depth_rule,
            "depth_0": maxd.get(n0), "depth_1": maxd.get(n1),
            "rank_0": ranks.get(n0), "rank_1": ranks.get(n1),
            "head_spine_0": spine.get(n0), "head_spine_1": spine.get(n1),
            "answer_is_head_of_spine": spine.get(n0 if p.expected_index == 0 else n1),
            "n_nodes": sum(1 for _ in walk(term)),
        }
        per_level[p.level].append(rec)
        if len(examples) < 6 and p.level in (1, 2, 3):
            examples.append(
                {**rec, "name_0": n0, "name_1": n1, "variant": p.variant.value,
                 "probe_id": p.probe_id}
            )

    summary = {}
    for lvl, recs in sorted(per_level.items()):
        n = len(recs)
        summary[f"L{lvl}"] = {
            "n": n,
            "json_rule_accuracy": sum(r["json_first_mention_pred"] == r["expected_index"] for r in recs) / n,
            "preorder_rule_accuracy": sum(r["preorder_rank_pred"] == r["expected_index"] for r in recs) / n,
            "depth_oracle_accuracy": sum(r["depth_oracle_pred"] == r["expected_index"] for r in recs) / n,
            "json_rule_equals_preorder_rule": sum(
                r["json_first_mention_pred"] == r["preorder_rank_pred"] for r in recs) / n,
            "preorder_rule_equals_depth_oracle": sum(
                r["preorder_rank_pred"] == r["depth_oracle_pred"] for r in recs) / n,
            "answer_is_head_of_application_spine": sum(
                bool(r["answer_is_head_of_spine"]) for r in recs) / n,
            "mean_nodes": sum(r["n_nodes"] for r in recs) / n,
            "depth_gap_distribution": dict(
                Counter(abs((r["depth_0"] or 0) - (r["depth_1"] or 0)) for r in recs)),
        }

    out = {
        "_disclaimer": "A3 DIAGNOSTIC. Not a re-scoring of V7.",
        "explanation": (
            "L0 asserts both depths in `established_facts`, and `established_facts` sorts BEFORE "
            "`goal` in the canonical JSON, so at L0 the JSON first-mention rule reads the "
            "explicit fact block (fixed order) rather than the term -- which is why it is pinned "
            "at 0.500 there while the preorder rule, which reads the term, is not."
        ),
        "by_level": summary,
        "examples": examples,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    for k, v in summary.items():
        print(f"{k}: json={v['json_rule_accuracy']:.3f} preorder={v['preorder_rule_accuracy']:.3f} "
              f"oracle={v['depth_oracle_accuracy']:.3f} "
              f"json==preorder {v['json_rule_equals_preorder_rule']:.3f} "
              f"preorder==oracle {v['preorder_rule_equals_depth_oracle']:.3f} "
              f"head_spine {v['answer_is_head_of_application_spine']:.3f} "
              f"nodes {v['mean_nodes']:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
