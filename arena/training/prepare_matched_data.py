#!/usr/bin/env python
"""Render the matched NEXT_ACTION datasets for the GPU sprint. No GPU, no model, no network.

`docs/ARENA_PROTOCOL.md` requires that every arm see identical canonical trajectories in the
identical order with identical targets, and that no arm receive private mathematical
information. That is checked here, before anything is uploaded, so a matching defect cannot
be discovered halfway through a paid GPU hour.

The split is disjoint by trajectory and stratified by domain, so no canonical world appears in
both training and evaluation for any arm, and every arm gets the same split.

    python -m arena.training.prepare_matched_data --out artifacts/tmp/gpu_sprint
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from arena.languages.registry import SEED_LANGUAGES
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.render_dataset import (
    assert_matched_semantics,
    render_matched_datasets,
)

#: The five surfaces the sprint compares. L5 is the static compactness frontier and is given
#: no privilege: it is trained, evaluated and reported exactly like the four controls.
ARMS: tuple[str, ...] = (
    "L0_STRUCTURED_ENGLISH",
    "L1_CURRENT_HML",
    "L2_SEXPR",
    "L3_JSON_AST",
    "L5_COMPACT_SYMBOLIC",
)


def stratified_split(tasks, train_n: int, dev_n: int, fresh_n: int, seed: int = 0):
    """Disjoint, domain-stratified split over task indices. Deterministic."""

    by_domain: dict[str, list[int]] = collections.defaultdict(list)
    for index, task in enumerate(tasks):
        by_domain[task.dimensions.domain].append(index)
    for indices in by_domain.values():
        indices.sort()

    train: list[int] = []
    dev: list[int] = []
    fresh: list[int] = []
    domains = sorted(by_domain)
    # Round-robin across domains so each split is balanced rather than domain-ordered.
    cursors = {domain: 0 for domain in domains}
    for bucket, size in ((dev, dev_n), (fresh, fresh_n), (train, train_n)):
        while len(bucket) < size:
            progressed = False
            for domain in domains:
                if len(bucket) >= size:
                    break
                position = cursors[domain]
                if position < len(by_domain[domain]):
                    bucket.append(by_domain[domain][position])
                    cursors[domain] = position + 1
                    progressed = True
            if not progressed:
                break
    assert not (set(train) & set(dev)), "train and dev overlap"
    assert not (set(train) & set(fresh)), "train and fresh overlap"
    assert not (set(dev) & set(fresh)), "dev and fresh overlap"
    return train, dev, fresh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/tmp/gpu_sprint"))
    parser.add_argument("--world", type=int, default=676)
    parser.add_argument("--train", type=int, default=600)
    parser.add_argument("--dev", type=int, default=48)
    parser.add_argument("--fresh", type=int, default=48)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    tasks = generate_tasks(total=args.world, seed=args.seed)
    trajectories = tuple(task.trajectory for task in tasks)
    train_ix, dev_ix, fresh_ix = stratified_split(
        tasks, args.train, args.dev, args.fresh, args.seed)

    languages = {language.candidate_id: language for language in SEED_LANGUAGES}
    missing = [arm for arm in ARMS if arm not in languages]
    if missing:
        raise SystemExit(f"unknown candidate surfaces: {missing}")
    selected = tuple(languages[arm] for arm in ARMS)

    datasets = render_matched_datasets(trajectories, selected)
    assert_matched_semantics(datasets)
    # assert_matched_semantics is vacuously true on an empty mapping, so the arm count is
    # asserted here rather than trusted to the guard.
    if len(datasets) != len(ARMS):
        raise SystemExit(f"expected {len(ARMS)} arms, rendered {len(datasets)}")

    payload: dict[str, object] = {
        "world_size": args.world,
        "seed": args.seed,
        "arms": list(ARMS),
        "split_sizes": {"train": len(train_ix), "dev": len(dev_ix), "fresh": len(fresh_ix)},
        "domains": {
            "train": dict(collections.Counter(tasks[i].dimensions.domain for i in train_ix)),
            "dev": dict(collections.Counter(tasks[i].dimensions.domain for i in dev_ix)),
            "fresh": dict(collections.Counter(tasks[i].dimensions.domain for i in fresh_ix)),
        },
        "splits": {},
    }
    for arm in ARMS:
        examples = datasets[arm]
        payload["splits"][arm] = {
            name: [examples[i].to_dict() for i in indices]
            for name, indices in (("train", train_ix), ("dev", dev_ix), ("fresh", fresh_ix))
        }

    # Matching evidence, recorded in the artefact rather than asserted in prose.
    def hashes(name: str, indices: list[int]) -> dict[str, tuple[str, ...]]:
        return {arm: tuple(datasets[arm][i].target_hash for i in indices) for arm in ARMS}

    for name, indices in (("train", train_ix), ("dev", dev_ix), ("fresh", fresh_ix)):
        target_sets = set(hashes(name, indices).values())
        if len(target_sets) != 1:
            raise SystemExit(f"{name}: arms do not share identical targets")
        input_sets = {
            arm: tuple(datasets[arm][i].input_hash for i in indices) for arm in ARMS}
        if len(set(input_sets.values())) != len(ARMS):
            raise SystemExit(f"{name}: two arms produced identical inputs")

    payload["token_proxy_mean_input_chars"] = {
        arm: round(sum(len(datasets[arm][i].input_text) for i in train_ix) / len(train_ix))
        for arm in ARMS
    }

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "matched_next_action.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {destination} ({destination.stat().st_size / 1e6:.1f} MB)")
    print(f"arms {list(ARMS)}")
    print(f"split train {len(train_ix)}  dev {len(dev_ix)}  fresh {len(fresh_ix)}  "
          f"(disjoint, domain-stratified)")
    print("identical targets across arms: YES; identical inputs across arms: NO (as required)")
    for arm, chars in payload["token_proxy_mean_input_chars"].items():
        print(f"  {arm:<24}mean train input {chars} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
