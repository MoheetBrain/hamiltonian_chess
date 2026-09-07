"""Frozen, hashed, nested budget manifests for the Route B learning-curve experiment.

Route B is a matched learning-curve design: every representation arm is trained on the
*same* canonical examples at a ladder of budgets, so a difference between arms cannot be
an accident of which examples each arm happened to see.  Two properties have to hold
before a single GPU-second is spent, and neither may be assumed:

1. **Nesting.**  The example set at each budget must be a subset (here, a strict prefix)
   of the next budget up.  Otherwise the "learning curve" is five unrelated experiments
   drawn from overlapping pools, and a non-monotone point could be a sampling artefact
   rather than a real effect.  :func:`assert_nested_ids` checks this at runtime and fails
   closed; it is never inferred from the construction.
2. **Quality.**  ``arena.tasks.generators.world_v0`` deliberately emits SILVER and REJECT
   trajectories alongside GOLD ones.  Training on a REJECT trajectory means training on a
   *refuted* action as if it were the right answer.  The default filter here is GOLD-only,
   and a budget larger than the GOLD pool is refused rather than silently topped up with
   weaker material.

Everything that could change what a model sees is hashed.  The per-slice dataset hash is
computed by :func:`dataset_hash`, which is byte-for-byte the same scheme
:func:`arena.training.render_dataset.write_jsonl` returns for the file it writes -- there
is deliberately no second hashing scheme in this codebase, and
``tests/training/test_route_b_data.py`` pins the two together.  :func:`verify_manifest`
re-derives every one of those hashes from the manifest's own recorded parameters, so a
later run can prove it trained on exactly what was frozen.

The manifest hash deliberately excludes ``arena_git_sha``: the per-arm dataset hashes
already commit to the exact bytes every arm is shown, and folding the commit into the
identity would make an unchanged dataset acquire a new identity on every unrelated commit.
The SHA is recorded as provenance, not as part of the dataset's identity.

Nothing in this module performs inference, touches a network, or requires a GPU.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Self, cast

from arena.canonical.schema import GoldStatus, stable_hash
from arena.languages.registry import LANGUAGE_REGISTRY
from arena.tasks.generators.world_v0 import generate_tasks
from arena.tasks.schema import ArenaTask
from arena.training.prepare_matched_data import (
    ARMS,
    seeded_stratified_split,
    stratified_split,
)
from arena.training.render_dataset import (
    RenderedExample,
    StateRenderer,
    assert_matched_semantics,
    render_matched_datasets,
)

ROUTE_B_MANIFEST_SCHEMA_VERSION = "arena-route-b-manifest-v1.0.0"

#: The precommitted Route B budget ladder.  Nested by construction and checked at runtime.
DEFAULT_BUDGETS: tuple[int, ...] = (16, 32, 64, 128, 224)

#: Held-out sizes.  These are fixed across every budget on purpose: the split fills dev and
#: fresh *before* train, so the train ordering -- and therefore the nesting property -- is
#: only stable while these two are held constant.
DEFAULT_DEV_SIZE = 48
DEFAULT_FRESH_SIZE = 48

#: GOLD is strongest.  ``min_quality`` admits everything at or above the requested rank.
QUALITY_RANK: dict[GoldStatus, int] = {
    GoldStatus.REJECT: 0,
    GoldStatus.SILVER: 1,
    GoldStatus.GOLD: 2,
}


class SplitMode(StrEnum):
    """Which splitter produced the ordering.  See :mod:`arena.training.prepare_matched_data`."""

    #: The historical splitter.  Its ``seed`` argument is inert; recorded so a manifest that
    #: reproduces the Tier-2 sprint cannot be mistaken for a genuinely reseeded one.
    LEGACY_DETERMINISTIC = "LEGACY_DETERMINISTIC"
    #: Genuinely seeded.  Different seeds give different splits.
    SEEDED = "SEEDED"


class ManifestError(ValueError):
    """A manifest could not be built from the requested design."""


class ManifestVerificationError(RuntimeError):
    """A manifest does not describe the data it claims to describe."""


def dataset_hash(examples: Sequence[RenderedExample]) -> str:
    """Content hash of an ordered example slice.

    This is exactly the value :func:`arena.training.render_dataset.write_jsonl` returns for
    the file it writes, so a manifest hash and an on-disk shard hash are comparable without
    a second hashing scheme existing anywhere.
    """

    return stable_hash([item.to_dict() for item in examples])


def assert_nested_ids(slices: Sequence[tuple[int, Sequence[str]]]) -> None:
    """Fail closed unless each budget's canonical IDs are a strict prefix of the next.

    ``slices`` is ``(budget, canonical_ids)`` pairs.  Both the prefix property and the
    weaker subset property are checked, and both must hold: a set-subset that is not a
    prefix would still break the "same examples, plus more" reading of a learning curve,
    because the *order* examples are shown in is part of what the budget ladder holds fixed.
    """

    if not slices:
        raise ManifestError("nesting check requires at least one budget slice")
    ordered = sorted(slices, key=lambda item: item[0])
    for (small_budget, small_ids), (large_budget, large_ids) in zip(
        ordered, ordered[1:], strict=False
    ):
        if small_budget >= large_budget:
            raise ManifestError(
                f"budgets must be strictly increasing: {small_budget} >= {large_budget}"
            )
        if len(small_ids) > len(large_ids):
            raise ManifestError(
                f"budget {small_budget} holds {len(small_ids)} examples but budget "
                f"{large_budget} holds only {len(large_ids)}"
            )
        if tuple(large_ids[: len(small_ids)]) != tuple(small_ids):
            raise ManifestError(
                f"nesting broken: budget {small_budget} is not a prefix of budget {large_budget}"
            )
        if not set(small_ids) <= set(large_ids):
            raise ManifestError(
                f"nesting broken: budget {small_budget} is not a subset of budget {large_budget}"
            )
    for budget, ids in ordered:
        if len(set(ids)) != len(ids):
            raise ManifestError(f"budget {budget} repeats a canonical ID")


def filter_indices_by_quality(
    tasks: Sequence[ArenaTask], indices: Sequence[int], min_quality: GoldStatus | None
) -> tuple[int, ...]:
    """Keep, in order, the indices whose trajectory quality is at least ``min_quality``.

    Filtering happens *after* the split rather than before it, so the domain-stratified
    round-robin ordering -- and with it the prefix/nesting property -- is preserved.
    ``None`` disables the filter and is the historical behaviour.
    """

    if min_quality is None:
        return tuple(indices)
    floor = QUALITY_RANK[min_quality]
    return tuple(
        index for index in indices if QUALITY_RANK[tasks[index].trajectory.quality] >= floor
    )


def arena_git_sha(root: Path | None = None) -> str | None:
    """Best-effort commit SHA read straight off the filesystem.  ``None`` when unavailable.

    Deliberately does not shell out to ``git``: this module must stay importable and cheap in
    a sandbox with no git binary, and provenance that is merely *nice to have* must never be
    able to fail a manifest build.  Handles a linked worktree, where ``.git`` is a file
    pointing at the real git directory and refs live in the shared ``commondir``.
    """

    start = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    git_path = start / ".git"
    try:
        if git_path.is_file():
            pointer = git_path.read_text(encoding="utf-8").strip()
            if not pointer.startswith("gitdir:"):
                return None
            git_dir = (start / pointer.split(":", 1)[1].strip()).resolve()
        elif git_path.is_dir():
            git_dir = git_path.resolve()
        else:
            return None
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        return head or None

    ref = head.split(":", 1)[1].strip()
    search_dirs = [git_dir]
    try:
        commondir = git_dir / "commondir"
        if commondir.is_file():
            search_dirs.append((git_dir / commondir.read_text(encoding="utf-8").strip()).resolve())
    except OSError:
        pass
    for directory in search_dirs:
        try:
            loose = directory / ref
            if loose.is_file():
                return loose.read_text(encoding="utf-8").strip() or None
        except OSError:
            continue
    for directory in search_dirs:
        try:
            lines = (directory / "packed-refs").read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if line.endswith(f" {ref}"):
                return line.split(" ", 1)[0]
    return None


@dataclass(frozen=True, slots=True)
class ArmProvenance:
    """Which surface an arm is, and which genome produced it."""

    candidate_id: str
    genome_hash: str | None = None
    candidate_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "genome_hash": self.genome_hash,
            "candidate_hash": self.candidate_hash,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            candidate_id=str(raw["candidate_id"]),
            genome_hash=None if raw.get("genome_hash") is None else str(raw["genome_hash"]),
            candidate_hash=(
                None if raw.get("candidate_hash") is None else str(raw["candidate_hash"])
            ),
        )


@dataclass(frozen=True, slots=True)
class DataSlice:
    """One frozen slice of the world: which examples, in which order, and their hashes."""

    name: str
    budget: int | None
    indices: tuple[int, ...]
    canonical_ids: tuple[str, ...]
    #: ``(arm, dataset_hash)`` sorted by arm.  A tuple rather than a dict so the record stays
    #: frozen and its canonical JSON spelling is order-stable.
    arm_dataset_hashes: tuple[tuple[str, str], ...]

    @property
    def size(self) -> int:
        return len(self.indices)

    def hash_for(self, arm: str) -> str:
        for candidate, digest in self.arm_dataset_hashes:
            if candidate == arm:
                return digest
        raise KeyError(f"slice {self.name} has no dataset hash for arm {arm}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "budget": self.budget,
            "size": self.size,
            "indices": list(self.indices),
            "canonical_ids": list(self.canonical_ids),
            "arm_dataset_hashes": {arm: digest for arm, digest in self.arm_dataset_hashes},
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        hashes = raw["arm_dataset_hashes"]
        return cls(
            name=str(raw["name"]),
            budget=None if raw.get("budget") is None else int(raw["budget"]),
            indices=tuple(int(item) for item in raw["indices"]),
            canonical_ids=tuple(str(item) for item in raw["canonical_ids"]),
            arm_dataset_hashes=tuple(sorted((str(k), str(v)) for k, v in hashes.items())),
        )


@dataclass(frozen=True, slots=True)
class BudgetManifest:
    """Everything that determines what each arm sees at each budget, plus its hash."""

    world_size: int
    generator_seed: int
    split_mode: SplitMode
    split_seed: int
    min_quality: GoldStatus | None
    budgets: tuple[int, ...]
    arms: tuple[ArmProvenance, ...]
    train_slices: tuple[DataSlice, ...]
    dev: DataSlice
    fresh: DataSlice
    dev_size: int
    fresh_size: int
    available_pool: int
    manifest_hash: str
    arena_git_sha: str | None = None
    schema_version: str = ROUTE_B_MANIFEST_SCHEMA_VERSION
    #: Stated here because the field it describes is easy to misread as a token count.
    token_proxy_units: str = "characters_not_tokens"

    @property
    def arm_ids(self) -> tuple[str, ...]:
        return tuple(arm.candidate_id for arm in self.arms)

    def slice_for(self, budget: int) -> DataSlice:
        for item in self.train_slices:
            if item.budget == budget:
                return item
        raise KeyError(f"manifest has no train slice for budget {budget}")

    def identity_payload(self) -> dict[str, Any]:
        """The exact value the manifest hash commits to.  ``arena_git_sha`` is excluded."""

        return {
            "schema_version": self.schema_version,
            "world_size": self.world_size,
            "generator_seed": self.generator_seed,
            "split_mode": self.split_mode.value,
            "split_seed": self.split_seed,
            "min_quality": None if self.min_quality is None else self.min_quality.value,
            "budgets": list(self.budgets),
            "dev_size": self.dev_size,
            "fresh_size": self.fresh_size,
            "arms": [arm.to_dict() for arm in self.arms],
            "train_slices": [item.to_dict() for item in self.train_slices],
            "dev": self.dev.to_dict(),
            "fresh": self.fresh.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "available_pool": self.available_pool,
            "arena_git_sha": self.arena_git_sha,
            "token_proxy_units": self.token_proxy_units,
            "manifest_hash": self.manifest_hash,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        quality = raw.get("min_quality")
        return cls(
            world_size=int(raw["world_size"]),
            generator_seed=int(raw["generator_seed"]),
            split_mode=SplitMode(raw["split_mode"]),
            split_seed=int(raw["split_seed"]),
            min_quality=None if quality is None else GoldStatus(quality),
            budgets=tuple(int(item) for item in raw["budgets"]),
            arms=tuple(ArmProvenance.from_dict(item) for item in raw["arms"]),
            train_slices=tuple(DataSlice.from_dict(item) for item in raw["train_slices"]),
            dev=DataSlice.from_dict(raw["dev"]),
            fresh=DataSlice.from_dict(raw["fresh"]),
            dev_size=int(raw["dev_size"]),
            fresh_size=int(raw["fresh_size"]),
            available_pool=int(raw["available_pool"]),
            manifest_hash=str(raw["manifest_hash"]),
            arena_git_sha=(None if raw.get("arena_git_sha") is None else str(raw["arena_git_sha"])),
            schema_version=str(raw.get("schema_version", ROUTE_B_MANIFEST_SCHEMA_VERSION)),
            token_proxy_units=str(raw.get("token_proxy_units", "characters_not_tokens")),
        )


def _arm_provenance(arms: Sequence[str]) -> tuple[ArmProvenance, ...]:
    records: list[ArmProvenance] = []
    for arm in arms:
        try:
            language = LANGUAGE_REGISTRY.get(arm)
        except KeyError as error:
            raise ManifestError(f"unknown candidate surface: {arm}") from error
        genome = getattr(language, "genome", None)
        records.append(
            ArmProvenance(
                candidate_id=arm,
                genome_hash=None if genome is None else str(genome.genome_hash),
                candidate_hash=None if genome is None else str(genome.candidate_hash),
            )
        )
    return tuple(records)


def _renderers(arms: Sequence[str]) -> tuple[StateRenderer, ...]:
    return tuple(cast(StateRenderer, LANGUAGE_REGISTRY.get(arm)) for arm in arms)


def _build_slice(
    name: str,
    budget: int | None,
    indices: Sequence[int],
    tasks: Sequence[ArenaTask],
    datasets: Mapping[str, tuple[RenderedExample, ...]],
    arms: Sequence[str],
) -> DataSlice:
    return DataSlice(
        name=name,
        budget=budget,
        indices=tuple(indices),
        canonical_ids=tuple(tasks[index].trajectory.trajectory_id for index in indices),
        arm_dataset_hashes=tuple(
            sorted((arm, dataset_hash([datasets[arm][index] for index in indices])) for arm in arms)
        ),
    )


def build_budget_manifest(
    *,
    world_size: int = 676,
    budgets: Sequence[int] = DEFAULT_BUDGETS,
    arms: Sequence[str] = ARMS,
    min_quality: GoldStatus | None = GoldStatus.GOLD,
    generator_seed: int = 0,
    split_mode: SplitMode = SplitMode.LEGACY_DETERMINISTIC,
    split_seed: int = 0,
    dev_size: int = DEFAULT_DEV_SIZE,
    fresh_size: int = DEFAULT_FRESH_SIZE,
    root: Path | None = None,
) -> BudgetManifest:
    """Freeze a nested budget ladder and hash everything that could change what a model sees.

    A single split is computed at the largest budget and every smaller budget takes a prefix
    of it, so nesting is true by construction -- and is then *checked* anyway by
    :func:`assert_nested_ids`, because a construction that is only believed to be correct is
    the kind of thing that quietly stops being correct.
    """

    if world_size <= 0:
        raise ManifestError("world_size must be positive")
    if not budgets:
        raise ManifestError("at least one budget is required")
    ordered_budgets = tuple(sorted(int(item) for item in budgets))
    if len(set(ordered_budgets)) != len(ordered_budgets):
        raise ManifestError(f"budgets must be distinct: {list(budgets)}")
    if ordered_budgets[0] <= 0:
        raise ManifestError(f"budgets must be positive: {list(budgets)}")
    if len(arms) < 2:
        raise ManifestError(f"a matched comparison needs at least two arms, got {list(arms)}")
    if len(set(arms)) != len(arms):
        raise ManifestError(f"arms must be distinct: {list(arms)}")
    if dev_size < 0 or fresh_size < 0:
        raise ManifestError("dev_size and fresh_size must not be negative")

    tasks = generate_tasks(total=world_size, seed=generator_seed)
    largest = ordered_budgets[-1]
    # Ask the splitter for the whole world; the pool it can actually reach is bounded by the
    # world, and the quality filter narrows it further.  Over-requesting here is safe: the
    # splitter stops when a bucket cannot progress.
    if split_mode is SplitMode.LEGACY_DETERMINISTIC:
        train_ix, dev_ix, fresh_ix = stratified_split(tasks, world_size, dev_size, fresh_size)
    elif split_mode is SplitMode.SEEDED:
        # Apply the quality floor BEFORE splitting, so train, dev and fresh are all drawn from
        # the admissible pool and every slice comes out at its requested size.  Filtering only
        # afterwards would silently seed the evaluation slices with sub-GOLD trajectories --
        # measured on the 676-task world at seed 0: 12 of 48 dev and 15 of 48 fresh items.
        # The legacy path deliberately does NOT do this: its ordering is pinned by
        # `artifacts/experiments/tier2_sprint/` and must not move.
        eligible = filter_indices_by_quality(tasks, range(len(tasks)), min_quality)
        subset = [tasks[index] for index in eligible]
        subset_train, subset_dev, subset_fresh = seeded_stratified_split(
            subset, len(subset), dev_size, fresh_size, seed=split_seed
        )
        train_ix = [eligible[position] for position in subset_train]
        dev_ix = [eligible[position] for position in subset_dev]
        fresh_ix = [eligible[position] for position in subset_fresh]
    else:  # pragma: no cover - StrEnum is closed
        raise ManifestError(f"unknown split mode: {split_mode}")

    # The quality floor applies to the held-out sets as well as to train.  Applying it to train
    # only would admit SILVER/REJECT trajectories into the evaluation slices, so the primary
    # endpoint would be measured partly on trajectories the world itself marks unsound.  The
    # legacy split is unaffected (its dev/fresh are already pure GOLD), so this is a no-op there
    # and a genuine repair under SEEDED.
    quality_label = "any quality" if min_quality is None else f"{min_quality.value} or better"
    dev_ix = filter_indices_by_quality(tasks, dev_ix, min_quality)
    fresh_ix = filter_indices_by_quality(tasks, fresh_ix, min_quality)

    # The held-out sets are checked first: an under-supplied dev/fresh is the more fundamental
    # fault, and reporting the train pool instead would send the reader after the wrong knob.
    if len(dev_ix) < dev_size or len(fresh_ix) < fresh_size:
        raise ManifestError(
            f"world of {world_size} tasks cannot supply dev={dev_size} and fresh={fresh_size} "
            f"at {quality_label}; got dev={len(dev_ix)}, fresh={len(fresh_ix)}. "
            f"Enlarge the world, reduce the held-out sizes, or relax min_quality."
        )
    dev_ix = list(dev_ix)[:dev_size]
    fresh_ix = list(fresh_ix)[:fresh_size]
    pool = filter_indices_by_quality(tasks, train_ix, min_quality)
    if largest > len(pool):
        raise ManifestError(
            f"budget {largest} exceeds the available pool: the {world_size}-task world yields "
            f"only {len(pool)} train examples at {quality_label} "
            f"(dev={dev_size}, fresh={fresh_size} are held out first). "
            f"Lower the budget to at most {len(pool)}, enlarge the world, or relax min_quality."
        )

    renderers = _renderers(arms)
    datasets = render_matched_datasets(tuple(task.trajectory for task in tasks), renderers)
    assert_matched_semantics(datasets)
    if len(datasets) != len(arms):
        raise ManifestError(f"expected {len(arms)} arms, rendered {len(datasets)}")

    train_slices = tuple(
        _build_slice(f"train@{budget}", budget, pool[:budget], tasks, datasets, arms)
        for budget in ordered_budgets
    )
    assert_nested_ids([(item.budget or 0, item.canonical_ids) for item in train_slices])

    dev_slice = _build_slice("dev", None, dev_ix, tasks, datasets, arms)
    fresh_slice = _build_slice("fresh", None, fresh_ix, tasks, datasets, arms)
    largest_train = set(train_slices[-1].canonical_ids)
    if largest_train & set(dev_slice.canonical_ids):
        raise ManifestError("train and dev overlap")
    if largest_train & set(fresh_slice.canonical_ids):
        raise ManifestError("train and fresh overlap")
    if set(dev_slice.canonical_ids) & set(fresh_slice.canonical_ids):
        raise ManifestError("dev and fresh overlap")

    draft = BudgetManifest(
        world_size=world_size,
        generator_seed=generator_seed,
        split_mode=split_mode,
        split_seed=split_seed,
        min_quality=min_quality,
        budgets=ordered_budgets,
        arms=_arm_provenance(arms),
        train_slices=train_slices,
        dev=dev_slice,
        fresh=fresh_slice,
        dev_size=dev_size,
        fresh_size=fresh_size,
        available_pool=len(pool),
        manifest_hash="",
        arena_git_sha=arena_git_sha(root),
    )
    # The hash cannot be an argument to the object it commits to, so it is computed from the
    # draft's identity payload -- which excludes the hash field -- and stamped on a copy.
    return replace(draft, manifest_hash=stable_hash(draft.identity_payload()))


def verify_manifest(manifest: BudgetManifest, *, root: Path | None = None) -> BudgetManifest:
    """Re-derive the manifest from its own recorded parameters and confirm every hash.

    Call this immediately before training.  It is the only thing that turns "we wrote down a
    hash" into "this run is provably the frozen design": a manifest whose recorded parameters
    no longer reproduce its recorded hashes means the generator, the renderers, the splitter
    or the manifest file itself has moved underneath the experiment.
    """

    if manifest.schema_version != ROUTE_B_MANIFEST_SCHEMA_VERSION:
        raise ManifestVerificationError(
            f"manifest schema {manifest.schema_version} is not "
            f"{ROUTE_B_MANIFEST_SCHEMA_VERSION}; refusing to verify across schema versions"
        )
    try:
        rebuilt = build_budget_manifest(
            world_size=manifest.world_size,
            budgets=manifest.budgets,
            arms=manifest.arm_ids,
            min_quality=manifest.min_quality,
            generator_seed=manifest.generator_seed,
            split_mode=manifest.split_mode,
            split_seed=manifest.split_seed,
            dev_size=manifest.dev_size,
            fresh_size=manifest.fresh_size,
            root=root,
        )
    except ManifestError as error:
        raise ManifestVerificationError(f"manifest could not be re-derived: {error}") from error

    for recorded, derived in zip(
        (*manifest.train_slices, manifest.dev, manifest.fresh),
        (*rebuilt.train_slices, rebuilt.dev, rebuilt.fresh),
        strict=True,
    ):
        if recorded.indices != derived.indices:
            raise ManifestVerificationError(f"slice {recorded.name}: indices do not re-derive")
        if recorded.canonical_ids != derived.canonical_ids:
            raise ManifestVerificationError(
                f"slice {recorded.name}: canonical IDs do not re-derive"
            )
        if recorded.arm_dataset_hashes != derived.arm_dataset_hashes:
            raise ManifestVerificationError(
                f"slice {recorded.name}: per-arm dataset hashes do not re-derive"
            )
    if manifest.arms != rebuilt.arms:
        raise ManifestVerificationError("arm provenance does not re-derive")
    if manifest.available_pool != rebuilt.available_pool:
        raise ManifestVerificationError("available pool size does not re-derive")

    recomputed = stable_hash(manifest.identity_payload())
    if recomputed != manifest.manifest_hash:
        raise ManifestVerificationError(
            f"manifest hash mismatch: recorded {manifest.manifest_hash}, recomputed {recomputed}"
        )
    if rebuilt.manifest_hash != manifest.manifest_hash:
        raise ManifestVerificationError(
            f"manifest hash mismatch: recorded {manifest.manifest_hash}, "
            f"re-derived {rebuilt.manifest_hash}"
        )
    assert_nested_ids([(item.budget or 0, item.canonical_ids) for item in manifest.train_slices])
    return rebuilt


__all__ = [
    "DEFAULT_BUDGETS",
    "DEFAULT_DEV_SIZE",
    "DEFAULT_FRESH_SIZE",
    "QUALITY_RANK",
    "ROUTE_B_MANIFEST_SCHEMA_VERSION",
    "ArmProvenance",
    "BudgetManifest",
    "DataSlice",
    "ManifestError",
    "ManifestVerificationError",
    "SplitMode",
    "arena_git_sha",
    "assert_nested_ids",
    "build_budget_manifest",
    "dataset_hash",
    "filter_indices_by_quality",
    "verify_manifest",
]
