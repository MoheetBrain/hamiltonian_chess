"""Build a deterministic research bank from random/train only; never run a Solver.

Run with the worktree at the front of PYTHONPATH to avoid the shared venv's
editable install accidentally resolving another worktree.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from arena.environments import premise_selection as ps
from .source_adapter import (ADAPTER_VERSION, DEFAULT_SOURCE, LEVEL, ScopeCheckedGenerator,
                             adapt_item, load_source_headers, sha256_file, split_state,
                             validate_source_pin)


def stable_rank(seed: int, *parts: object) -> str:
    return hashlib.sha256("|".join(map(str, (seed,) + parts)).encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def seal_sources(source: Path, out: Path) -> None:
    """Only hash bytes and stat held-out files; never decode their contents."""
    files = []
    for relpath in sorted(ps.SEALED_RELPATHS):
        path = source / relpath
        files.append({"path": str(path), "relpath": relpath,
                      "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                      "inspection": "bytes hashed only; no semantic parsing or display"})
    write_json(out / "source_seal.json", {
        "seal_version": "astra-source-seal-v1", "files": files,
        "historical_exposure": {
            "novel_premises/val.json": "HISTORICALLY_EXPOSED",
            "novel_premises/test.json": "HISTORICALLY_EXPOSED",
            "random/val.json": "HISTORICALLY_EXPOSED",
            "random/test.json": "HISTORICALLY_EXPOSED",
        },
        "historical_evidence": ["research/environments/measurements/census_leandojo_heldout.json",
                                "research/environments/measurements/premise_selection_shortcuts.json"],
        "historical_evidence_handling": "Existing exposure identified by repository audit; adapter never opens these reports.",
        "future_promotion_partition": "Fresh externally controlled, never-inspected source theorem/repository partition required; current partitions are not certified hidden.",
    })


def build_bank(source: Path, out: Path, count: int = 300, seed: int = 20260907,
               limit_theorems: int = 5000) -> dict:
    if not 1 <= count <= 500:
        raise ValueError("research bank count must be between 1 and 500")
    if limit_theorems < count:
        raise ValueError("theorem pool must be at least the requested item count")
    out.mkdir(parents=True, exist_ok=True)
    seal_sources(source, out)  # Deliberately before parsing any development content.
    source_pin = validate_source_pin(source)
    train = ps.require_permitted_train(source / "random/train.json")
    corpus = source / "corpus.jsonl"
    theorems = list(ps.stream_traced_theorems(train, limit=limit_theorems))
    usage: Counter[str] = Counter()
    def_paths: dict[str, str] = {}
    proof_premises: dict[str, set[str]] = defaultdict(set)
    proof_counts: dict[str, Counter[str]] = defaultdict(Counter)
    stats: Counter[str] = Counter()
    for theorem in theorems:
        stats["source_theorems_scanned"] += 1
        for step in ps.raw_steps(theorem):
            stats["source_steps_scanned"] += 1
            proof_premises[step.proof_id].update(p.full_name for p in step.premises)
            proof_counts[step.proof_id].update(p.full_name for p in step.premises)
            if ps.is_usable(step):
                stats["production_usable_steps"] += 1
                premise = step.premises[0]
                usage[premise.full_name] += 1
                def_paths.setdefault(premise.full_name, premise.def_path)
    decls, imports = ps.load_corpus(corpus)
    headers, header_stats = load_source_headers(corpus)
    index = ps.build_index(usage, def_paths, dict(proof_premises), decls, imports)
    generator = ScopeCheckedGenerator(index, headers, seed)
    # Hash ordering within a fixed source prefix makes the selection reproducible;
    # it does not claim a random sample of the full train split.
    theorems.sort(key=lambda row: stable_rank(seed, row["file_path"], row["full_name"]))
    admitted = []
    for theorem in theorems:
        stats["theorems_attempted"] += 1
        steps = sorted(ps.raw_steps(theorem), key=lambda step: stable_rank(seed, step.proof_id, step.step_index))
        for step in steps:
            if not ps.is_usable(step):
                stats["excluded_production_not_usable"] += 1
                continue
            try:
                split_state(step.state_before)
            except ValueError:
                stats["excluded_non_single_goal"] += 1
                continue
            transition = ps.sanitise(theorem, step)
            if not generator.accepts(transition, step.premises[0].full_name):
                stats["excluded_gold_signature_or_scope"] += 1
                continue
            item = generator.generate(transition)
            if item is None:
                stats["excluded_insufficient_matched_distractors"] += 1
                continue
            problems = ps.audit_item_leaks(item, step)
            if problems:
                stats["excluded_production_leak_check"] += 1
                continue
            state = adapt_item(theorem, step, item, index, headers, seed, proof_counts[step.proof_id])
            admitted.append(state)
            break  # One item per theorem group.
        if len(admitted) >= count:
            break
    # Exactly 80/20, grouped by theorem identity. Split ranking independent of labels.
    partition_order = sorted(admitted, key=lambda item: stable_rank(seed, "dev-partition", item.provenance["theorem_id"]))
    fit_count = len(partition_order) * 4 // 5
    fit_ids = {item.task_id for item in partition_order[:fit_count]}
    admitted = [replace(item, audit_metadata={**item.audit_metadata,
                "dev_partition": "train" if item.task_id in fit_ids else "heldout"}) for item in admitted]
    admitted.sort(key=lambda item: item.task_id)
    bank_path = out / "dev_bank.jsonl"
    bank_path.write_text("".join(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                                 for item in admitted), encoding="utf-8")
    tiers = Counter()
    labels = Counter()
    for item in admitted:
        labels[next(str(i) for i, candidate in enumerate(item.candidate_premises) if candidate.premise_id == item.target_choice_id)] += 1
        tiers.update(meta["tier"] for meta in item.audit_metadata["candidate_metadata"].values() if meta["tier"] != "gold")
    coverage = {
        "requested_items": count, "admitted_items": len(admitted), "unique_theorem_groups": len(admitted),
        "development_train_items": fit_count, "development_heldout_items": len(admitted) - fit_count,
        "choices_per_item": LEVEL.k, "candidate_total": sum(len(item.candidate_premises) for item in admitted),
        "all_candidates_have_full_source_headers": True,
        "all_candidates_import_and_declaration_order_checked": True,
        "all_raw_states_losslessly_preserved": all(item.context.text + item.goal.text == item.source_raw_state for item in admitted),
        "kernel_replays": 0, "elaborated_kernel_types": 0,
        "source_statistics": dict(stats), "source_header_statistics": header_stats,
        "distractor_tiers": dict(tiers), "answer_position_counts_zero_based": dict(labels),
        "admission_limitations": ["Single-goal source-text envelope only, not elaborated Lean semantics.",
                                  "Source declaration headers omit ambient section variables, namespaces and notation context.",
                                  "Recorded citation identifies the observed premise, not all mathematically valid next actions.",
                                  "Bounded first-N source theorem pool; no population representativeness claim."],
    }
    write_json(out / "coverage_report.json", coverage)
    manifest = {
        "adapter_version": ADAPTER_VERSION, "schema_version": "astra-premise-v1", "seed": seed,
        "bank_path": "research/astra/artifacts/dev_bank.jsonl", "bank_sha256": sha256_file(bank_path),
        "admitted_items": len(admitted), "requested_items": count,
        "source_theorem_limit": limit_theorems,
        "source_files": [{"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
                         for path in [train, corpus, source / "metadata.json"]],
        "source_commit": ps.DATASET_COMMIT, "source_pin": source_pin,
        "sampler": {"production_generator": ps.GENERATOR_VERSION, "level": LEVEL.name,
                    "extra_filters": ["explicit full theorem/lemma source header", "single goal", "all candidate import scope",
                                      "no self/future same-file declarations"],
                    "ordering": "sha256(seed|task_id|premise_id); identical across representations",
                    "frequency_source": "first N random/train theorems, used for sampling only",
                    "same_proof_source": "recorded citations anywhere in source proof; sampling metadata never visible",
                    "fallback": "same-module frequency-matched only; no random-global fallback"},
        "development_split": {"train": fit_count, "heldout": len(admitted) - fit_count,
                              "unit": "theorem group", "method": "independent seeded hash rank, 80/20",
                              "purpose": "shortcut fitting/evaluation only; not sealed scientific promotion"},
        "no_model_calls": True, "kernel_replay": False,
    }
    write_json(out / "development_manifest.json", manifest)
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=Path("research/astra/artifacts"))
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--limit-theorems", type=int, default=5000)
    args = parser.parse_args()
    print(json.dumps(build_bank(args.source, args.out, args.count, args.seed, args.limit_theorems), indent=2))


if __name__ == "__main__":
    main()
