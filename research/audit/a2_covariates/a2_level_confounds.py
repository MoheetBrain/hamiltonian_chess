"""A2: what ELSE changes when the level changes, and how tightly is depth tied to order?

(1) Per mechanism, the level curve of every cell covariate alongside the frozen solver
    accuracy, plus Spearman rho between level and covariate over L1..L3 and L0..L3.
(2) The question TEXT per (mechanism, level) -- a cue that changes with level for one
    mechanism.
(3) On the real Lean source states: how strongly is an identifier's maximum AST depth
    rank tied to its pre-order first-occurrence rank?  This is the structural reason the
    positional shortcut works.
(4) Source-state reuse across levels for formal_expression_depth.

NO model call.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from scipy.stats import spearmanr

from arena.environments.formal_structural import identifier_depths
from arena.experiments.fitness_v5 import _formal_pool, build_dev_pool

OUT = Path(__file__).resolve().parent
ART = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")
POSITIVE = {"ORIGINAL", "COUNTERFACTUAL"}


def preorder_first(expr, name: str, counter=None, out=None):
    """Index of the first pre-order node carrying ``name``."""
    if out is None:
        out, counter = {}, [0]
    idx = counter[0]
    counter[0] += 1
    if isinstance(expr.value, str) and expr.value not in out:
        out[expr.value] = idx
    for child in expr.args:
        preorder_first(child, name, counter, out)
    return out


def main() -> int:
    art = json.loads(ART.read_text())
    acc: dict[str, list[int]] = defaultdict(list)
    for row in art["rows"]:
        if row["variant"] in POSITIVE:
            acc[f"{row['mechanism']}|L{row['level']}"].append(int(row["correct"]))
    solver = {k: sum(v) / len(v) for k, v in acc.items()}
    cells = json.loads((OUT / "cell_features.json").read_text())

    fields = [
        "prompt_tokens_real_mean",
        "prompt_chars_mean",
        "state_chars_mean",
        "goal_nodes_mean",
        "goal_max_depth_mean",
        "goal_leaf_identifiers_mean",
        "goal_identifier_mean_depth",
        "state_objects_mean",
        "state_assumptions_mean",
        "state_propositions_mean",
        "state_facts_mean",
        "state_evidence_nodes_mean",
        "delimiter_total_mean",
        "answer_share_index0",
        "target_first_mention_norm_mean",
    ]
    confounds: dict[str, dict] = {}
    for mech in ("formal_expression_depth", "transitive_dependency", "precondition_conjunction"):
        levels = [0, 1, 2, 3]
        entry: dict[str, object] = {
            "solver_accuracy": {f"L{l}": round(solver[f"{mech}|L{l}"], 4) for l in levels}
        }
        for f in fields:
            vals = [cells[f"{mech}|L{l}"][f] for l in levels]
            entry[f] = {
                "by_level": {f"L{l}": v for l, v in zip(levels, vals, strict=True)},
                "rho_vs_level_L0toL3": round(float(spearmanr(levels, vals).statistic), 4)
                if len(set(vals)) > 1
                else None,
                "rho_vs_level_L1toL3": round(
                    float(spearmanr(levels[1:], vals[1:]).statistic), 4
                )
                if len(set(vals[1:])) > 1
                else None,
                "rho_vs_solver_accuracy_L1toL3": round(
                    float(
                        spearmanr(
                            [solver[f"{mech}|L{l}"] for l in levels[1:]], vals[1:]
                        ).statistic
                    ),
                    4,
                )
                if len(set(vals[1:])) > 1
                else None,
            }
        confounds[mech] = entry

    # ---- question text per (mechanism, level) ----
    probes = build_dev_pool(Path.cwd())
    questions: dict[str, str] = {}
    sources: dict[str, list[str]] = defaultdict(list)
    for p in probes:
        questions[f"{p.mechanism}|L{p.level}"] = p.question
        if p.mechanism == "formal_expression_depth" and p.variant.value == "ORIGINAL":
            sources[f"L{p.level}"].append(p.family_id.rsplit(":", 2)[-2] + ":" + p.family_id.rsplit(":", 1)[-1])
    reuse = {
        f"{a} vs {b}": len(set(sources[a]) & set(sources[b]))
        for a, b in (("L0", "L1"), ("L0", "L2"), ("L0", "L3"), ("L1", "L2"), ("L1", "L3"), ("L2", "L3"))
    }

    # ---- depth rank vs pre-order rank on the real Lean states ----
    pool = _formal_pool(Path.cwd())
    rhos, top1 = [], []
    strata = {k: len(v) for k, v in pool.items()}
    for bucket in pool.values():
        for st in bucket:
            depths = {n: max(v) for n, v in identifier_depths(st.target).items()}
            order = preorder_first(st.target, "")
            common = [n for n in depths if n in order]
            if len(common) < 3:
                continue
            r = spearmanr([depths[n] for n in common], [order[n] for n in common]).statistic
            if r == r:
                rhos.append(float(r))
            deepest = max(common, key=lambda n: (depths[n], -order[n]))
            earliest = min(common, key=lambda n: order[n])
            top1.append(int(deepest == earliest))
    struct = {
        "length_fair_states": sum(strata.values()),
        "stratum_sizes": strata,
        "states_scored": len(rhos),
        "mean_spearman_depth_vs_preorder_rank": round(sum(rhos) / len(rhos), 4) if rhos else None,
        "share_negative_rho": round(sum(r < 0 for r in rhos) / len(rhos), 4) if rhos else None,
        "share_deepest_identifier_is_also_first_in_preorder": round(sum(top1) / len(top1), 4)
        if top1
        else None,
        "note": (
            "negative rho means deeper identifiers occur EARLIER in pre-order, which is what "
            "makes 'answer with the first identifier you see' a working rule"
        ),
    }

    payload = {
        "level_confounds": confounds,
        "question_text_by_cell": questions,
        "formal_source_state_reuse_across_levels": reuse,
        "depth_vs_traversal_order_on_real_lean_states": struct,
    }
    (OUT / "level_confounds.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({k: payload[k] for k in ("question_text_by_cell",
                                              "formal_source_state_reuse_across_levels",
                                              "depth_vs_traversal_order_on_real_lean_states")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
