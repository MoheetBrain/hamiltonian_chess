"""Build premise-selection items from LeanDojo random/train.json (TRAIN ONLY).

Two streaming passes over the 373 MB trace file:

  pass 1  usage frequencies, definition paths, per-proof premise sets, filter counters
  pass 2  item generation for every requested difficulty level

Nothing else is read except ``corpus.jsonl``.  The four sealed splits are refused by
``arena.environments.premise_selection.guard_source_path``; this script never names them.

Usage:
    python -m research.env_premise.build_items --out <dir> [--limit-theorems N]
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

from arena.environments import premise_selection as ps

LD = Path("/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4")
TRAIN = LD / "random" / "train.json"
CORPUS = LD / "corpus.jsonl"


def option_features(
    index: ps.PremiseIndex,
    option: ps.PremiseOption,
    position: int,
    transition_file: str,
    goal_tokens: frozenset[str],
    goal_token_list: list[str],
    n_decls: int,
) -> list[float]:
    """Model-free features a shortcut predictor could exploit.  Order is fixed; see FEATURE_NAMES."""
    name = option.full_name
    toks = index.tokens(name)
    order = index.order(name)
    return [
        float(position),
        float(len(name)),
        index.similarity(name, goal_tokens),
        ps.multiset_overlap(list(toks), goal_token_list),
        math.log1p(index.freq(name)),
        1.0 if option.def_path == transition_file else 0.0,
        1.0 if ps.module_of(option.def_path) == ps.module_of(transition_file) else 0.0,
        (order / n_decls) if order >= 0 else -1.0,
    ]


FEATURE_NAMES = [
    "position",
    "name_length",
    "name_goal_jaccard",
    "name_goal_multiset_overlap",
    "log_global_frequency",
    "same_file",
    "same_module",
    "declaration_order",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit-theorems", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--levels", default=",".join(level.name for level in ps.LADDER))
    parser.add_argument("--sample-prompts", type=int, default=200)
    parser.add_argument("--max-item-file-rows", type=int, default=25000)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    levels = [ps.LEVELS_BY_NAME[name] for name in args.levels.split(",")]

    # ---- pass 1 -----------------------------------------------------------------------------
    t0 = time.time()
    usage: Counter[str] = Counter()
    def_path: dict[str, str] = {}
    proof_premises: dict[str, set[str]] = {}
    stats: Counter[str] = Counter()
    for theorem in ps.stream_traced_theorems(TRAIN, limit=args.limit_theorems):
        stats["theorems"] += 1
        for step in ps.raw_steps(theorem):
            stats["steps"] += 1
            if step.premises:
                stats["steps_with_premise"] += 1
                proof_premises.setdefault(step.proof_id, set()).update(
                    p.full_name for p in step.premises
                )
            if len(step.premises) > 1:
                stats["steps_multi_premise"] += 1
            if len(step.premises) == 1 and step.state_before.strip():
                stats["steps_single_premise"] += 1
                if ps.name_occurs_in(step.state_before, step.premises[0].full_name):
                    stats["dropped_gold_name_in_state"] += 1
            if ps.is_usable(step):
                stats["steps_usable"] += 1
                usage[step.premises[0].full_name] += 1
                def_path.setdefault(step.premises[0].full_name, step.premises[0].def_path)
    pass1 = time.time() - t0
    print(f"[pass1] {pass1:.1f}s {dict(stats)} distinct_gold_premises={len(usage)}", flush=True)

    # ---- index ------------------------------------------------------------------------------
    t0 = time.time()
    decls, imports = ps.load_corpus(CORPUS)
    index = ps.build_index(usage, def_path, proof_premises, decls, imports)
    print(
        f"[index] {time.time() - t0:.1f}s decls={len(decls)} files={len(imports)} "
        f"tokens={len(index.token_index)}",
        flush=True,
    )

    # ---- pass 2 -----------------------------------------------------------------------------
    t0 = time.time()
    n_decls = max(1, len(decls))
    generators = {level.name: ps.PremiseSelectionGenerator(index, ps.GeneratorConfig(seed=args.seed)) for level in levels}
    handles = {level.name: (out / f"items_{level.name}.jsonl").open("w", encoding="utf-8") for level in levels}
    gate = (out / "gate_features.jsonl").open("w", encoding="utf-8")
    prompts = (out / "sample_prompts.jsonl").open("w", encoding="utf-8")
    leak_problems: Counter[str] = Counter()
    attempted: Counter[str] = Counter()
    emitted: Counter[str] = Counter()
    audited = 0
    n_prompts = 0

    for theorem in ps.stream_traced_theorems(TRAIN, limit=args.limit_theorems):
        for step in ps.raw_steps(theorem):
            if not ps.is_usable(step):
                continue
            transition = ps.sanitise(theorem, step)
            goal_token_list = ps.state_tokens(transition.state_before)
            goal_tokens = frozenset(goal_token_list)
            for level in levels:
                attempted[level.name] += 1
                item = generators[level.name].generate(transition, level)
                if item is None:
                    continue
                emitted[level.name] += 1
                if emitted[level.name] <= args.max_item_file_rows:
                    handles[level.name].write(json.dumps(item.to_json(), ensure_ascii=False) + "\n")
                gate.write(
                    json.dumps(
                        {
                            "item_id": item.item_id,
                            "level": item.level,
                            "k": item.k,
                            "proof_id": transition.proof_id,
                            "file_path": transition.file_path,
                            "answer_index": item.answer_index,
                            "gold_similarity_band": item.features["gold_similarity_band"],
                            "opts": [
                                option_features(
                                    index,
                                    option,
                                    position,
                                    transition.file_path,
                                    goal_tokens,
                                    goal_token_list,
                                    n_decls,
                                )
                                for position, option in enumerate(item.options)
                            ],
                        }
                    )
                    + "\n"
                )
                for problem in ps.audit_item_leaks(item, step):
                    leak_problems[f"{level.name}:{problem}"] += 1
                audited += 1
                if n_prompts < args.sample_prompts and level.name in {"L0_explicit_positive", "L2_standard", "L4_high_similarity"}:
                    prompts.write(json.dumps(item.to_json(), ensure_ascii=False) + "\n")
                    n_prompts += 1

    for handle in handles.values():
        handle.close()
    gate.close()
    prompts.close()
    pass2 = time.time() - t0

    summary = {
        "pass1_seconds": round(pass1, 1),
        "pass2_seconds": round(pass2, 1),
        "filter_stats": dict(stats),
        "distinct_gold_premises": len(usage),
        "corpus_decls": len(decls),
        "corpus_files": len(imports),
        "levels": {
            level.name: {
                "k": level.k,
                "attempted": attempted[level.name],
                "emitted": emitted[level.name],
                "items_with_fallback_tier": generators[level.name].items_with_fallback,
                "items_rejected_gold_in_prompt": generators[level.name].items_rejected_gold_in_prompt,
                "distractor_tier_counts": dict(generators[level.name].tier_counts),
            }
            for level in levels
        },
        "items_audited_for_leaks": audited,
        "leak_problems": dict(leak_problems),
        "seed": args.seed,
        "generator_version": ps.GENERATOR_VERSION,
        "spec_version": ps.SPEC_VERSION,
        "feature_names": FEATURE_NAMES,
    }
    (out / "build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
