"""A8: inventory the already-captured ELABORATED Lean runtime corpus.

Answers Part L Q3/Q5 with counts rather than assertion: which semantic fields exist
today without any new Lean run, and how many premise-selection items the corpus
could support.

Read-only.  Reads only ``lean_runtime_v2_full.canonical.part-*.jsonl.gz`` (the same
files the CANONICAL_VNEXT pilot sampled).  It never touches ``sealed_final_v2*`` and
never touches any file named in artifacts/manifests/SEALED_SPLITS.json.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

CORPUS = Path("/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus")
PARTS = sorted(CORPUS.glob("lean_runtime_v2_full.canonical.part-*.jsonl.gz"))
FORBIDDEN = "sealed_final_v2"


def expr_nodes(value, counter: Counter, depth: int = 0) -> int:
    """Count node kinds and return max depth of an elaborated expression tree."""
    best = depth
    if isinstance(value, dict):
        node = value.get("node")
        if isinstance(node, str):
            counter[node] += 1
        for sub in value.values():
            best = max(best, expr_nodes(sub, counter, depth + 1))
    elif isinstance(value, list):
        for sub in value:
            best = max(best, expr_nodes(sub, counter, depth))
    return best


def main() -> None:
    assert all(FORBIDDEN not in p.name for p in PARTS), "refusing to read a sealed shard"
    stats: Counter[str] = Counter()
    node_kinds: Counter[str] = Counter()
    binder_roles: Counter[str] = Counter()
    decl_roles: Counter[str] = Counter()
    mvar_kinds: Counter[str] = Counter()
    accounting: Counter[str] = Counter()
    premise_hist: Counter[int] = Counter()
    goal_hist: Counter[int] = Counter()
    source_files: set[str] = set()
    theorems: set[str] = set()
    domains: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    depths: list[int] = []
    ctx_sizes: list[int] = []
    single_premise_single_goal = 0
    have_all_seven = 0

    for part in PARTS:
        with gzip.open(part, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                r = json.loads(line)
                stats["transitions"] += 1
                md = r.get("corpus_metadata", {})
                source_files.add(md.get("source_file", ""))
                domains[md.get("domain") or "<none>"] += 1
                splits[str(md.get("official_split"))] += 1
                theorems.add(r.get("source_specific_reference", {}).get("theorem_id", ""))
                action = r.get("action", {})
                prem = action.get("external_premise_refs") or []
                premise_hist[len(prem)] += 1
                before = r.get("state_before", {})
                goals = before.get("goals") or []
                goal_hist[len(goals)] += 1
                if len(prem) == 1 and len(goals) == 1:
                    single_premise_single_goal += 1
                for acc_key, acc_val in (before.get("information_accounting") or {}).items():
                    accounting[f"{acc_key}={acc_val}"] += 1
                for goal in goals:
                    ctx = goal.get("local_context") or []
                    ctx_sizes.append(len(ctx))
                    for decl in ctx:
                        binder_roles[str(decl.get("binder_role"))] += 1
                        decl_roles[str(decl.get("declaration_role"))] += 1
                        if decl.get("value") is not None:
                            stats["let_bound_locals"] += 1
                        if decl.get("user_name_diagnostic") is not None:
                            stats["locals_with_diagnostic_name"] += 1
                        if isinstance(decl.get("identity"), str):
                            stats["locals_with_stable_identity"] += 1
                    depths.append(expr_nodes(goal.get("target"), node_kinds))
                for mvar in before.get("metavariables") or []:
                    mvar_kinds[str(mvar.get("kind"))] += 1
                    if mvar.get("assigned"):
                        stats["metavariables_assigned"] += 1
                sref = before.get("source_reference", {})
                stats["fvar_identity_maps"] += bool(sref.get("raw_fvar_to_canonical"))
                stats["mvar_identity_maps"] += bool(sref.get("raw_mvar_to_canonical"))
                prov = r.get("provenance", {}).get("lean_runtime_snapshot", {})
                stats["with_transitive_imports"] += bool(prov.get("transitive_import_modules"))
                delta = r.get("state_delta", {})
                stats["with_external_premises_used"] += bool(delta.get("external_premises_used"))
                stats["with_local_context_refs"] += bool(delta.get("local_context_refs_used"))
                # the seven items Part L Q5 asks about, per transition
                seven = [
                    bool(goals and goals[0].get("target")),                       # elaborated expr tree
                    bool(r.get("source_specific_reference", {})
                          .get("elaborated_external_constant_refs")),             # resolved constants
                    bool(goals and goals[0].get("local_context")),                # local decl identities
                    bool(goals and any(d.get("binder_role") for d in (goals[0].get("local_context") or []))),
                    bool(goals and any(d.get("type") for d in (goals[0].get("local_context") or []))),
                    bool(prov.get("transitive_import_modules")),                  # dependency edges
                    bool(prem),                                                   # premise identities
                ]
                have_all_seven += all(seven)

    report = {
        "corpus": [str(p) for p in PARTS],
        "sealed_shards_read": 0,
        "transitions": stats["transitions"],
        "distinct_theorems": len(theorems),
        "distinct_source_files": len(source_files),
        "domains": dict(domains.most_common()),
        "official_split_labels": dict(splits),
        "premise_refs_per_transition": dict(sorted(premise_hist.items())),
        "goals_per_state_before": dict(sorted(goal_hist.items())),
        "single_premise_single_goal_transitions": single_premise_single_goal,
        "transitions_with_all_seven_semantic_fields": have_all_seven,
        "counters": dict(stats),
        "binder_roles": dict(binder_roles.most_common()),
        "declaration_roles": dict(decl_roles.most_common()),
        "metavariable_kinds": dict(mvar_kinds.most_common()),
        "information_accounting": dict(accounting.most_common()),
        "expression_node_kinds": dict(node_kinds.most_common()),
        "target_tree_depth": {
            "n": len(depths),
            "mean": sum(depths) / len(depths) if depths else 0,
            "max": max(depths) if depths else 0,
        },
        "local_context_size": {
            "n": len(ctx_sizes),
            "mean": sum(ctx_sizes) / len(ctx_sizes) if ctx_sizes else 0,
            "max": max(ctx_sizes) if ctx_sizes else 0,
        },
    }
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/lean_runtime_inventory.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "expression_node_kinds"}, indent=2))
    print("expression_node_kinds:", json.dumps(report["expression_node_kinds"], indent=1))


if __name__ == "__main__":
    main()
