#!/usr/bin/env python
"""Render the matched NEXT_ACTION datasets for the GPU sprint. No GPU, no model, no network.

`docs/ARENA_PROTOCOL.md` requires that every arm see identical canonical trajectories in the
identical order with identical targets, and that no arm receive private mathematical
information. That is checked here, before anything is uploaded, so a matching defect cannot
be discovered halfway through a paid GPU hour.

The split is disjoint by trajectory and stratified by domain, so no canonical world appears in
both training and evaluation for any arm, and every arm gets the same split.

    python -m arena.training.prepare_matched_data --out artifacts/tmp/gpu_sprint

``token_proxy_mean_input_chars`` is a count of CHARACTERS, not tokens.  It is not a token
budget and must never be used as one: characters-per-token differs by surface, so the arm
with the fewest characters is not necessarily the arm with the fewest tokens.  The field
keeps its historical name because a Tier-2 artefact already records it under that name; the
name is the misleading part, and this note is the correction.

Everything added after the Tier-2 sprint is opt-in and defaults to the historical behaviour,
so a historical invocation reproduces ``matched_next_action.json`` byte-for-byte.  The single
deliberate exception is stdout, which always gains one line restating the units of
``token_proxy_mean_input_chars``: stdout is guidance for a human reader, not a stored artefact,
and the whole point of that line is that the number stops being misread.

    --manifest-out PATH   also freeze a nested Route B budget manifest (default: off)
    --budgets 16,32,...   the budget ladder for that manifest
    --min-quality GOLD    quality floor for manifest train budgets (default: ANY = no filter)
    --split-mode seeded   use the genuinely seeded splitter (default: legacy)
"""

from __future__ import annotations

import argparse
import collections
import json
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from arena.canonical.schema import GoldStatus
from arena.languages.registry import SEED_LANGUAGES
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.render_dataset import (
    StateRenderer,
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
    """Disjoint, domain-stratified split over task indices. Deterministic.

    DEFECT (known, deliberately preserved): the ``seed`` parameter is INERT.  It appears in
    the signature but is never read in the body, so ``seed=0`` and ``seed=999`` return the
    identical split.  Any claim of "two seeds" resting on this function is a claim about one
    split reported twice.

    The defect is not fixed in place because the split it produces is baked into
    ``artifacts/experiments/tier2_sprint/`` and that artefact must stay reproducible.  This
    function is therefore the frozen legacy path, and :func:`seeded_stratified_split` is the
    genuinely seeded replacement.  New designs that want independent seeds must call that one;
    ``tests/training/test_route_b_data.py`` pins this function's exact output and fails if the
    seeded path ever degenerates back into ignoring its seed.

    The split fills dev, then fresh, then train, so the train ordering depends on ``dev_n``
    and ``fresh_n`` but not on ``train_n``: growing ``train_n`` only appends.  That is what
    makes nested budget subsets possible, and it holds for the seeded path too.
    """

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


def seeded_stratified_split(
    tasks, train_n: int, dev_n: int, fresh_n: int, *, seed: int
) -> tuple[list[int], list[int], list[int]]:
    """Domain-stratified split whose seed is actually used.  Different seeds differ.

    Identical in shape to :func:`stratified_split` -- same round-robin over sorted domains,
    same dev/fresh/train fill order, same disjointness and the same nesting property -- but
    each domain's index list is shuffled by a seeded RNG first, so the *membership* of every
    bucket genuinely depends on ``seed``.  Domain balance is unchanged, because shuffling
    within a domain cannot move an example between domains.

    ``seed`` is keyword-only on purpose: no existing positional call site can reach this
    function by accident, so nothing that reproduces the Tier-2 sprint can silently change
    meaning.
    """

    by_domain: dict[str, list[int]] = collections.defaultdict(list)
    for index, task in enumerate(tasks):
        by_domain[task.dimensions.domain].append(index)
    domains = sorted(by_domain)
    for domain in domains:
        indices = by_domain[domain]
        indices.sort()
        # One RNG stream per (seed, domain) so adding a domain cannot reshuffle the others.
        # A string seed is used deliberately: `random.Random` derives its state from the
        # string's bytes, so it is stable across processes, unlike `hash()` under
        # PYTHONHASHSEED randomisation.
        random.Random(f"{seed}:{domain}").shuffle(indices)

    train: list[int] = []
    dev: list[int] = []
    fresh: list[int] = []
    cursors = {domain: 0 for domain in domains}
    for bucket, size in ((dev, dev_n), (fresh, fresh_n), (train, train_n)):
        while len(bucket) < size:
            progressed = False
            for domain in domains:
                if len(bucket) >= size:
                    break
                position_in_domain = cursors[domain]
                if position_in_domain < len(by_domain[domain]):
                    bucket.append(by_domain[domain][position_in_domain])
                    cursors[domain] = position_in_domain + 1
                    progressed = True
            if not progressed:
                break
    if set(train) & set(dev):
        raise ValueError("train and dev overlap")
    if set(train) & set(fresh):
        raise ValueError("train and fresh overlap")
    if set(dev) & set(fresh):
        raise ValueError("dev and fresh overlap")
    return train, dev, fresh


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("artifacts/tmp/gpu_sprint"))
    parser.add_argument("--world", type=int, default=676)
    parser.add_argument("--train", type=int, default=600)
    parser.add_argument("--dev", type=int, default=48)
    parser.add_argument("--fresh", type=int, default=48)
    parser.add_argument("--seed", type=int, default=0)
    # --- Post-sprint additions. Every one of these defaults to the historical behaviour, so
    # --- a historical invocation still writes matched_next_action.json byte-for-byte.
    parser.add_argument(
        "--split-mode",
        choices=("legacy", "seeded"),
        default="legacy",
        help=(
            "legacy: the frozen Tier-2 splitter, whose --seed is inert (see the "
            "stratified_split docstring). seeded: the genuinely seeded splitter."
        ),
    )
    parser.add_argument(
        "--min-quality",
        choices=("ANY", "REJECT", "SILVER", "GOLD"),
        default="ANY",
        help=(
            "Quality floor for TRAIN examples. ANY (default) keeps the historical behaviour "
            "of training on GOLD, SILVER and REJECT alike. GOLD refuses everything weaker."
        ),
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Also freeze a nested Route B budget manifest at this path. Off by default.",
    )
    parser.add_argument(
        "--budgets",
        type=str,
        default="16,32,64,128,224",
        help="Comma-separated budget ladder for --manifest-out. Ignored without it.",
    )
    args = parser.parse_args(argv)

    # Imported here rather than at module scope: route_b_data imports the splitters from this
    # module, so a top-level import would be circular.
    from arena.training.route_b_data import (
        BudgetManifest,
        ManifestError,
        SplitMode,
        build_budget_manifest,
        filter_indices_by_quality,
        verify_manifest,
    )

    min_quality = None if args.min_quality == "ANY" else GoldStatus(args.min_quality)
    split_mode = SplitMode.LEGACY_DETERMINISTIC if args.split_mode == "legacy" else SplitMode.SEEDED
    extended = (
        args.manifest_out is not None or args.split_mode != "legacy" or min_quality is not None
    )

    tasks = generate_tasks(total=args.world, seed=args.seed)
    trajectories = tuple(task.trajectory for task in tasks)
    if split_mode is SplitMode.SEEDED:
        train_ix, dev_ix, fresh_ix = seeded_stratified_split(
            tasks, args.train, args.dev, args.fresh, seed=args.seed
        )
    else:
        train_ix, dev_ix, fresh_ix = stratified_split(
            tasks, args.train, args.dev, args.fresh, args.seed
        )
    if min_quality is not None:
        train_ix = list(filter_indices_by_quality(tasks, train_ix, min_quality))
        if not train_ix:
            raise SystemExit(
                f"no train example meets --min-quality {min_quality.value} in a "
                f"{args.world}-task world"
            )

    languages = {language.candidate_id: language for language in SEED_LANGUAGES}
    missing = [arm for arm in ARMS if arm not in languages]
    if missing:
        raise SystemExit(f"unknown candidate surfaces: {missing}")
    selected = tuple(cast(StateRenderer, languages[arm]) for arm in ARMS)

    datasets = render_matched_datasets(trajectories, selected)
    assert_matched_semantics(datasets)
    # assert_matched_semantics is vacuously true on an empty mapping, so the arm count is
    # asserted here rather than trusted to the guard.
    if len(datasets) != len(ARMS):
        raise SystemExit(f"expected {len(ARMS)} arms, rendered {len(datasets)}")

    payload: dict[str, Any] = {
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
        input_sets = {arm: tuple(datasets[arm][i].input_hash for i in indices) for arm in ARMS}
        if len(set(input_sets.values())) != len(ARMS):
            raise SystemExit(f"{name}: two arms produced identical inputs")

    payload["token_proxy_mean_input_chars"] = {
        arm: round(sum(len(datasets[arm][i].input_text) for i in train_ix) / len(train_ix))
        for arm in ARMS
    }

    manifest: BudgetManifest | None = None
    if extended:
        # Only reached when a post-sprint flag was passed, so the historical artefact keeps
        # its exact historical key set and byte length.
        payload["split_mode"] = split_mode.value
        payload["min_quality"] = None if min_quality is None else min_quality.value
        payload["token_proxy_units"] = "characters_not_tokens"
        payload["token_proxy_note"] = (
            "token_proxy_mean_input_chars counts CHARACTERS, not tokens. It is not a token "
            "budget and must not be used as one: characters per token differ by surface."
        )
    if args.manifest_out is not None:
        budgets = tuple(int(item) for item in str(args.budgets).split(",") if item.strip())
        try:
            manifest = build_budget_manifest(
                world_size=args.world,
                budgets=budgets,
                arms=ARMS,
                min_quality=min_quality,
                generator_seed=args.seed,
                split_mode=split_mode,
                split_seed=args.seed,
                dev_size=args.dev,
                fresh_size=args.fresh,
            )
        except ManifestError as error:
            raise SystemExit(f"budget manifest refused: {error}") from error
        verify_manifest(manifest)
        payload["manifest_hash"] = manifest.manifest_hash

    args.out.mkdir(parents=True, exist_ok=True)
    destination = args.out / "matched_next_action.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {destination} ({destination.stat().st_size / 1e6:.1f} MB)")
    print(f"arms {list(ARMS)}")
    print(
        f"split train {len(train_ix)}  dev {len(dev_ix)}  fresh {len(fresh_ix)}  "
        f"(disjoint, domain-stratified)"
    )
    print("identical targets across arms: YES; identical inputs across arms: NO (as required)")
    for arm, chars in payload["token_proxy_mean_input_chars"].items():
        print(f"  {arm:<24}mean train input {chars} chars")
    print("token_proxy_mean_input_chars is CHARACTERS, not tokens; it is not a token budget")
    if manifest is not None:
        manifest_path = Path(args.manifest_out)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {manifest_path} (manifest_hash {manifest.manifest_hash})")
        print(
            f"budgets {list(manifest.budgets)} nested, pool {manifest.available_pool} at "
            f"{'any quality' if min_quality is None else min_quality.value}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
