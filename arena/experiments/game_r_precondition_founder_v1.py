"""Phase 8 experiment: the founder roster on the precondition ladder (v1).

This is an **experiment module**, not a harness.  Every prompt, parity check, cache
identity, budget and score comes from :mod:`arena.experiments.game_r_formal_v1`; this module
only decides *which* items reach the harness, *in which order*, under *which namespace*, and
what is reported.  Three stages, each writing one artifact through
:class:`~arena.storage.artifacts.ArtifactStore`:

``smoke``
    Two families, two arms, base and rotated rows, run twice.  It verifies the live path
    end to end (served digest, grammar, exact token accounting, cache isolation, replay as
    ``SAME_CONDITION_REUSE``) and reports every check rather than asserting silently.

``calibration``
    Control arm only (the baseline surface), positives only, one batch per stratum.  A
    deterministic selector picks the stratum whose control accuracy is closest to a target
    inside a band; band and target are *parameters* recorded in the artifact so the
    preregistration can freeze them.

``tournament``
    Every founder arm on the identical items of one stratum, arm-outer so that a rotated
    twin immediately follows its base item (Ollama's KV-cached prefix makes that pair nearly
    free).  Per-arm reports, all-pairs comparisons, Holm across the baseline comparisons, and
    a manifest that pins task ids, state hashes, per-arm prompt hashes, roster, solver and
    decoding.

Scheduling: every positive item is run as its base then IMMEDIATELY as its
``rotate_options(item, 1)`` variant, and the twins of a family stay together:
``[ORIGINAL, ORIGINAL#rot1, COUNTERFACTUAL, COUNTERFACTUAL#rot1]``.

Cache protection: each stage's cache root carries a sentinel file that is checked before the
stage, every :data:`SENTINEL_CHECK_EVERY` rows, and at the end; if it vanishes the stage
raises :class:`CacheVanished` at once.  Every path used is refused if it touches a frozen
instrument's namespace.  No artifact is ever overwritten except on ``--resume`` with an
identical manifest identity; otherwise a versioned sibling is written.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import shutil
import sys
import time
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from itertools import combinations
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json, stable_hash
from arena.experiments.fitness_v4 import holm_decisions
from arena.experiments.game_r_formal_v1 import (
    HARNESS_VERSION,
    SCORED_STATUSES,
    CallBudget,
    ContextBudget,
    HarnessRefusal,
    ItemVariant,
    MaterialisedItem,
    ResponseCache,
    RowStatus,
    RunConfig,
    Solver,
    StubEnvironment,
    StubSolver,
    StubSolverPolicy,
    StubTokenCounter,
    SyntaxGuidePolicy,
    TaskItem,
    TokenCounter,
    assert_arena_parity,
    build_prompt,
    compare_arms,
    decoding_hash,
    founder_genome,
    prompt_bytes_hash,
    qualified_task_id,
    response_schema,
    rotate_options,
    run_item,
    score_mechanism,
)
from arena.experiments.ollama_live import frozen_decoding
from arena.model_view.genome import ModelViewGenome
from arena.storage.artifacts import ArtifactStore
from arena.training.evaluation import wilson_interval

EXPERIMENT_VERSION = "arena-game-r-precondition-founder-v1.0.0"
LADDER_MODULE = "arena.environments.precondition_ladder"

# ------------------------------------------------------------------------------ namespaces

NAMESPACES: tuple[str, ...] = ("smoke", "dryrun", "calibration", "tournament")
CACHE_NAMESPACES: dict[str, str] = {
    name: f"artifacts/cache/game_r_precondition_founder_v1/{name}" for name in NAMESPACES
}
ARTIFACT_NAMESPACES: dict[str, str] = {
    name: f"experiments/game_r_precondition_founder_v1/{name}" for name in NAMESPACES
}
SMOKE_CACHE_SUFFIX = CACHE_NAMESPACES["smoke"]

#: Namespaces owned by earlier instruments.  Phase 8 must never read or write inside them.
FROZEN_NAMESPACES: tuple[str, ...] = (
    "fitness_v1",
    "fitness_v2",
    "fitness_v3",
    "fitness_v4",
    "fitness_v5",
    "fitness_v6",
    "fitness_v7",
    "model_fitness",
    "game_r_formal_v1_dry_run",
)

SENTINEL_NAME = ".PHASE8_CACHE_DO_NOT_DELETE"
SENTINEL_TEXT = (
    "README: Phase 8 live response cache for game_r_precondition_founder_v1. Every file here "
    "is a paid model call. Do not delete this directory; the only sanctioned deletion is "
    "`--wipe-smoke`, which removes the smoke namespace only.\n"
)
SENTINEL_CHECK_EVERY = 25
PROGRESS_EVERY = 10

# --------------------------------------------------------------------------------- roster

FOUNDER_SURFACES: tuple[str, ...] = (
    "L3_JSON_AST",
    "L0_STRUCTURED_ENGLISH",
    "L1_CURRENT_HML",
    "L2_SEXPR",
    "L5_COMPACT_SYMBOLIC",
)
BASELINE_SURFACE = "L3_JSON_AST"
GUIDE_POLICY = SyntaxGuidePolicy.SHARED_CONSTANT
CONTEXT_BUDGET = ContextBudget(num_ctx=32768, max_output_tokens=64)

#: Calibration selector defaults.  PARAMETERS, recorded in the artifact; the integrator
#: freezes the values in the preregistration and passes them on the command line.
DEFAULT_BAND: tuple[float, float] = (0.65, 0.80)
DEFAULT_TARGET = 0.725
HOLM_ALPHA = 0.05  # fitness_v4.holm_decisions hard-codes 0.05; recorded, never re-derived.

SMOKE_FAMILIES = 2
SMOKE_ARMS = 2
SMOKE_STRATUM = "P05"
#: ``--dry-run`` without ``--strata``: two strata so the selector has something to rank; the
#: dry-run tournament leg runs on the first.
DRY_RUN_STRATA: tuple[str, ...] = ("P05", "P07")
STUB_STRATA: tuple[str, ...] = ("S1", "S2")
POSITIVE_VARIANTS: tuple[str, ...] = ("ORIGINAL", "COUNTERFACTUAL")
_VARIANT_ORDER = {name: index for index, name in enumerate(POSITIVE_VARIANTS)}
MANIFEST_IDENTITY_KEYS: tuple[str, ...] = ("task_hash", "roster_hash", "solver_hash")


# ------------------------------------------------------------------------------ exceptions


class FrozenNamespaceRefusal(HarnessRefusal, ValueError):
    """A path touched a frozen instrument's namespace."""


class CacheVanished(HarnessRefusal):
    """The stage's cache directory or its sentinel disappeared mid-run."""


class LadderUnavailable(HarnessRefusal):
    """The precondition ladder module is absent; no live items can be built."""


class SmokeCacheRefusal(HarnessRefusal):
    """``--wipe-smoke`` was pointed at anything other than the smoke cache."""


# ------------------------------------------------------------------------------ namespaces


def assert_phase8_namespace(path: str | Path) -> str:
    """Refuse any path that belongs to a frozen instrument (mirrors ``assert_v7_namespace``)."""

    text = str(path).replace("\\", "/")
    for namespace in FROZEN_NAMESPACES:
        if namespace in text:
            raise FrozenNamespaceRefusal(
                f"Phase 8 refused a frozen-instrument path: {text!r} contains {namespace!r}. "
                "This experiment owns game_r_precondition_founder_v1 namespaces only."
            )
    return text


def refuse_frozen_paths(*paths: str | Path) -> tuple[str, ...]:
    return tuple(assert_phase8_namespace(path) for path in paths)


def ensure_sentinel(cache_root: Path) -> Path:
    assert_phase8_namespace(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    sentinel = cache_root / SENTINEL_NAME
    if not sentinel.exists():
        sentinel.write_text(SENTINEL_TEXT, encoding="utf-8")
    return sentinel


def assert_sentinel(cache_root: Path, *, context: str = "") -> None:
    where = f" ({context})" if context else ""
    if not cache_root.is_dir():
        raise CacheVanished(f"cache root {cache_root} vanished{where}; stopping immediately")
    if not (cache_root / SENTINEL_NAME).is_file():
        raise CacheVanished(
            f"cache sentinel {cache_root / SENTINEL_NAME} vanished{where}; stopping immediately"
        )


def wipe_smoke_cache(root: str | Path) -> dict[str, Any]:
    """Delete ONLY the smoke cache namespace.  Fails closed on any other path."""

    target = Path(root) / CACHE_NAMESPACES["smoke"]
    text = str(target).replace("\\", "/")
    if not text.endswith(SMOKE_CACHE_SUFFIX):
        raise SmokeCacheRefusal(f"refusing to wipe {text!r}: not the smoke cache namespace")
    assert_phase8_namespace(text)
    if target.is_symlink():
        raise SmokeCacheRefusal(f"refusing to wipe {text!r}: it is a symlink")
    existed = target.exists()
    if existed and not target.is_dir():
        raise SmokeCacheRefusal(f"refusing to wipe {text!r}: not a directory")
    removed = sum(1 for p in target.rglob("*") if p.is_file()) if existed else 0
    if existed:
        shutil.rmtree(target)
    return {"wiped": text, "existed": existed, "files_removed": removed}


# ---------------------------------------------------------------------------------- roster


def founder_roster(surfaces: Sequence[str] = FOUNDER_SURFACES) -> tuple[ModelViewGenome, ...]:
    if len(set(surfaces)) != len(surfaces):
        raise ValueError(f"duplicate surfaces in roster: {list(surfaces)}")
    return tuple(founder_genome(surface) for surface in surfaces)


def baseline_candidate_id() -> str:
    return founder_genome(BASELINE_SURFACE).candidate_id


def roster_record(surfaces: Sequence[str] = FOUNDER_SURFACES) -> dict[str, Any]:
    roster = founder_roster(surfaces)
    return {
        "surfaces": list(surfaces),
        "baseline_surface": BASELINE_SURFACE,
        "baseline_candidate": baseline_candidate_id(),
        "candidates": [genome.candidate_id for genome in roster],
        "genome_hashes": {genome.candidate_id: genome.genome_hash for genome in roster},
        "guide_policy": str(GUIDE_POLICY),
    }


def roster_hash(surfaces: Sequence[str] = FOUNDER_SURFACES) -> str:
    return stable_hash(roster_record(surfaces))


# ----------------------------------------------------------------------------------- stage


class StageKind(StrEnum):
    SMOKE = "smoke"
    CALIBRATION = "calibration"
    TOURNAMENT = "tournament"


@dataclass(frozen=True, slots=True)
class Stage:
    """Where a stage reads, writes and caches.  ``dry_run`` redirects to the dryrun namespace."""

    kind: StageKind
    root: Path
    dry_run: bool = False
    resume: bool = False

    @property
    def namespace(self) -> str:
        return "dryrun" if self.dry_run else str(self.kind)

    @property
    def cache_root(self) -> Path:
        path = Path(self.root) / CACHE_NAMESPACES[self.namespace]
        assert_phase8_namespace(path)
        return path

    @property
    def artifact_root(self) -> Path:
        path = Path(self.root) / "artifacts"
        assert_phase8_namespace(path)
        return path

    @property
    def artifact_store(self) -> ArtifactStore:
        return ArtifactStore(self.artifact_root)

    def artifact_relpath(self, name: str) -> str:
        return assert_phase8_namespace(f"{ARTIFACT_NAMESPACES[self.namespace]}/{name}.json")

    @property
    def runtime_condition(self) -> str:
        return "dryrun-stub" if self.dry_run else "bare"

    def run_config(self) -> RunConfig:
        return RunConfig(
            experiment_version=EXPERIMENT_VERSION,
            runtime_condition=self.runtime_condition,
            decoding=frozen_decoding(),
            context=CONTEXT_BUDGET,
            cache_root=self.cache_root,
            guide_policy=GUIDE_POLICY,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "namespace": self.namespace,
            "dry_run": self.dry_run,
            "resume": self.resume,
            "runtime_condition": self.runtime_condition,
            "cache_namespace": CACHE_NAMESPACES[self.namespace],
            "artifact_namespace": ARTIFACT_NAMESPACES[self.namespace],
        }

    def paths(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "cache_root": str(self.cache_root),
            "artifact_root": str(self.artifact_root),
        }


# ----------------------------------------------------------------------------------- items


def _item_record(item: TaskItem) -> dict[str, Any]:
    return {
        "task_id": item.task_id,
        "family_id": item.family_id,
        "level": item.level,
        "variant": item.variant,
        "question": item.question,
        "state_hash": item.canonical_state.mathematical_hash,
        "n_options": len(item.options),
        "correct_index": item.correct_index,
        "provenance": dict(item.provenance),
    }


@dataclass(frozen=True, slots=True)
class TaskBatch:
    """One stratum's positive items (unscheduled), with the environment identity they need."""

    environment_version: str
    mechanism: str
    stratum: str
    pool: str
    families: int
    items: tuple[TaskItem, ...]
    excluded_variants: Mapping[str, int] = field(default_factory=dict)
    ladder_params: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "environment_version": self.environment_version,
            "mechanism": self.mechanism,
            "stratum": self.stratum,
            "pool": self.pool,
            "families": self.families,
            "n_items_positive": len(self.items),
            "family_ids": sorted({item.family_id for item in self.items}),
            "excluded_variants": dict(self.excluded_variants),
            "ladder_params": dict(self.ladder_params),
        }


def positive_items(items: Iterable[TaskItem]) -> tuple[tuple[TaskItem, ...], dict[str, int]]:
    """Keep ORIGINAL and COUNTERFACTUAL rows; count and drop anything else (destroyed, rotated)."""

    kept: list[TaskItem] = []
    excluded: Counter[str] = Counter()
    for item in items:
        if str(item.variant) in POSITIVE_VARIANTS:
            kept.append(item)
        else:
            excluded[str(item.variant)] += 1
    return tuple(kept), dict(sorted(excluded.items()))


def schedule_items(items: Sequence[TaskItem]) -> tuple[TaskItem, ...]:
    """Family-major, ``[ORIGINAL, ORIGINAL#rot1, COUNTERFACTUAL, COUNTERFACTUAL#rot1]``.

    Every base item is immediately followed by its own ``rotate_options(item, 1)`` so that
    the position audit shares the solver's KV-cached prefix with the base call.
    """

    families: dict[str, list[TaskItem]] = {}
    for item in items:
        if str(item.variant) == str(ItemVariant.ORDER_ROTATED):
            raise HarnessRefusal(
                f"{item.task_id} is already order-rotated; the scheduler builds its own rotations"
            )
        if str(item.variant) not in POSITIVE_VARIANTS:
            raise HarnessRefusal(f"{item.task_id} has non-positive variant {item.variant!r}")
        families.setdefault(str(item.family_id), []).append(item)
    scheduled: list[TaskItem] = []
    seen: set[str] = set()
    for members in families.values():
        ordered = sorted(members, key=lambda item: _VARIANT_ORDER[str(item.variant)])
        for item in ordered:
            if item.task_id in seen:
                raise HarnessRefusal(f"duplicate task id {item.task_id}")
            seen.add(item.task_id)
            scheduled.append(item)
            scheduled.append(rotate_options(item, 1))
    return tuple(scheduled)


def _limit_families(batch: TaskBatch, families: int) -> TaskBatch:
    order: list[str] = []
    for item in batch.items:
        if item.family_id not in order:
            order.append(item.family_id)
    keep = set(order[:families])
    return dataclasses.replace(
        batch,
        families=min(families, len(order)),
        items=tuple(item for item in batch.items if item.family_id in keep),
    )


def ladder_module() -> Any:
    """Import the ladder lazily; it is being written concurrently and may be absent."""

    try:
        return importlib.import_module(LADDER_MODULE)
    except ImportError as error:
        raise LadderUnavailable(
            f"{LADDER_MODULE} is not importable ({error}); live stages need the precondition "
            "ladder. Use --dry-run to exercise the pipeline against the harness stub items."
        ) from error


def _params_record(params: Any) -> dict[str, Any]:
    if params is None:
        return {}
    if dataclasses.is_dataclass(params) and not isinstance(params, type):
        return dict(dataclasses.asdict(params))
    if isinstance(params, Mapping):
        return dict(params)
    to_dict = getattr(params, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return {"repr": repr(params)}


def load_batch(stratum: str, *, pool: str, families: int, start: int = 0) -> TaskBatch:
    """Build one stratum's positives from the precondition ladder."""

    ladder = ladder_module()
    known = dict(ladder.LADDER)
    if stratum not in known:
        raise ValueError(f"unknown stratum {stratum!r}; ladder strata: {sorted(known)}")
    pool_member = ladder.Pool[pool.upper()]
    raw = ladder.build_pool(stratum, pool_member, families, start=start)
    positives, excluded = positive_items(raw)
    if not positives:
        raise HarnessRefusal(f"ladder produced no positive items for {stratum}/{pool}")
    # ``item.level`` is 0 for explicit strata and ``premises`` otherwise, so a batch is bound to
    # its stratum by provenance, never by level.
    foreign = sorted({str(item.provenance.get("stratum")) for item in positives} - {stratum})
    if foreign:
        raise HarnessRefusal(
            f"ladder returned items of strata {foreign} for {stratum!r}; a batch is one stratum"
        )
    return TaskBatch(
        environment_version=str(ladder.ENVIRONMENT_VERSION),
        mechanism=str(ladder.MECHANISM),
        stratum=stratum,
        pool=str(pool_member),
        families=families,
        items=positives,
        excluded_variants=excluded,
        ladder_params={**_params_record(known[stratum]), "start": start},
    )


def stub_batch(stratum: str, *, families: int, level: int, n_options: int = 2) -> TaskBatch:
    """Harness stub items with a flipped-truth counterfactual twin per family."""

    env = StubEnvironment(n_options=n_options)
    originals = [
        item
        for item in env.items(families=families, levels=(level,))
        if str(item.variant) == str(ItemVariant.ORIGINAL)
    ]
    items: list[TaskItem] = []
    for item in originals:
        items.append(item)
        items.append(
            MaterialisedItem(
                task_id=item.task_id.replace(":original", ":counterfactual"),
                family_id=item.family_id,
                level=item.level,
                variant="COUNTERFACTUAL",
                question=item.question,
                canonical_state=item.canonical_state,
                options=tuple(item.options),
                correct_index=(item.correct_index + 1) % n_options,
                provenance={**dict(item.provenance), "counterfactual_of": item.task_id},
            )
        )
    return TaskBatch(
        environment_version=env.environment_version,
        mechanism=env.mechanism,
        stratum=stratum,
        pool="STUB",
        families=families,
        items=tuple(items),
        ladder_params={"stub_level": level},
    )


def stub_batches(strata: Sequence[str] = STUB_STRATA, *, families: int) -> tuple[TaskBatch, ...]:
    return tuple(
        stub_batch(stratum, families=families, level=index + 1)
        for index, stratum in enumerate(strata)
    )


def dry_run_batches(strata: Sequence[str] | None, *, families: int) -> tuple[TaskBatch, ...]:
    """Ladder ``Pool.SMOKE`` items when the ladder exists, harness stub items otherwise."""

    try:
        ladder_module()
    except LadderUnavailable:
        return stub_batches(tuple(strata) if strata else STUB_STRATA, families=families)
    chosen = tuple(strata) if strata else DRY_RUN_STRATA
    return tuple(load_batch(stratum, pool="SMOKE", families=families) for stratum in chosen)


def ladder_order() -> tuple[str, ...]:
    """The ladder's declared stratum order (easy to hard); empty when the ladder is absent."""

    try:
        return tuple(str(name) for name in ladder_module().LADDER)
    except LadderUnavailable:
        return ()


# --------------------------------------------------------------------------- guarded write


def manifest_identity(payload: Mapping[str, Any]) -> dict[str, str] | None:
    manifest = payload.get("manifest")
    if not isinstance(manifest, Mapping):
        return None
    identity = {key: manifest.get(key) for key in MANIFEST_IDENTITY_KEYS}
    if any(not isinstance(value, str) or not value for value in identity.values()):
        return None
    return {key: str(value) for key, value in identity.items()}


def versioned_sibling(path: Path) -> Path:
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}-run{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def guarded_write(
    store: ArtifactStore, relative: str | Path, payload: Mapping[str, Any], *, resume: bool
) -> dict[str, Any]:
    """Never overwrite: resume onto an identical manifest identity, else version the sibling."""

    relative_text = assert_phase8_namespace(relative)
    target = store.root / relative_text
    assert_phase8_namespace(target)
    decision = "WRITTEN_NEW"
    existing_identity: dict[str, str] | None = None
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if isinstance(existing, Mapping):
            existing_identity = manifest_identity(existing)
        requested = manifest_identity(payload)
        if resume and existing_identity is not None and existing_identity == requested:
            decision = "OVERWRITTEN_RESUME_SAME_IDENTITY"
        else:
            sibling = versioned_sibling(target)
            relative_text = str(sibling.relative_to(store.root)).replace("\\", "/")
            decision = "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    stored = store.write_json(relative_text, dict(payload))
    return {
        "path": str(stored.path),
        "relative": relative_text,
        "sha256": stored.sha256,
        "decision": decision,
        "existing_identity": existing_identity,
    }


# ------------------------------------------------------------------------------- run rows


class _Progress:
    def __init__(self, total: int, *, label: str, every: int = PROGRESS_EVERY) -> None:
        self.total = total
        self.label = label
        self.every = max(1, every)
        self.done = 0
        self.fresh = 0
        self.started = time.monotonic()

    def tick(self, *, fresh: bool) -> None:
        self.done += 1
        self.fresh += int(fresh)
        if self.done % self.every == 0 or self.done == self.total:
            elapsed = time.monotonic() - self.started
            eta = (elapsed / self.done) * (self.total - self.done) if self.done else 0.0
            sys.stderr.write(
                f"[{self.label}] rows {self.done}/{self.total} fresh {self.fresh} "
                f"elapsed {elapsed:.1f}s eta {eta:.1f}s\n"
            )
            sys.stderr.flush()


def run_arm_rows(
    scheduled: Sequence[TaskItem],
    genome: ModelViewGenome,
    *,
    stage: Stage,
    batch: TaskBatch,
    config: RunConfig,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    cache: ResponseCache,
    progress: _Progress,
) -> tuple[list[dict[str, Any]], list[float]]:
    """One arm over the scheduled items, checking the sentinel every N rows."""

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for item in scheduled:
        started = time.monotonic()
        row = run_item(
            item,
            genome,
            mechanism=batch.mechanism,
            environment_version=batch.environment_version,
            config=config,
            solver=solver,
            counter=counter,
            budget=budget,
            cache=cache,
        )
        latencies.append(time.monotonic() - started)
        rows.append(row)
        progress.tick(fresh=not bool(row["cache_hit"]))
        if progress.done % SENTINEL_CHECK_EVERY == 0:
            assert_sentinel(stage.cache_root, context=f"after {progress.done} rows")
    return rows, latencies


@dataclass(frozen=True, slots=True)
class ArmsResult:
    scheduled: tuple[TaskItem, ...]
    parity: tuple[dict[str, Any], ...]
    rows_by_arm: dict[str, list[dict[str, Any]]]
    latencies_by_arm: dict[str, list[float]]
    config: RunConfig
    started_at: str
    elapsed_seconds: float

    def timing(self) -> dict[str, Any]:
        return {"started_at": self.started_at, "elapsed_seconds": self.elapsed_seconds}


def run_arms(
    stage: Stage,
    batch: TaskBatch,
    genomes: Sequence[ModelViewGenome],
    *,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    label: str,
) -> ArmsResult:
    """Parity across ALL arms first (before any call), then rows arm-outer."""

    if not genomes:
        raise HarnessRefusal("run_arms needs at least one arm")
    if not batch.items:
        raise HarnessRefusal(f"batch {batch.stratum} has no positive items")
    started_at = datetime.now(UTC).isoformat()
    clock = time.monotonic()
    scheduled = schedule_items(batch.items)
    config = stage.run_config()
    refuse_frozen_paths(stage.cache_root, stage.artifact_root)
    ensure_sentinel(stage.cache_root)
    assert_sentinel(stage.cache_root, context="stage start")
    parity = tuple(
        assert_arena_parity(item, genomes, guide_policy=config.guide_policy).to_dict()
        for item in scheduled
    )
    cache = ResponseCache(stage.cache_root)
    progress = _Progress(len(scheduled) * len(genomes), label=label)
    rows_by_arm: dict[str, list[dict[str, Any]]] = {}
    latencies_by_arm: dict[str, list[float]] = {}
    for genome in genomes:
        rows, latencies = run_arm_rows(
            scheduled,
            genome,
            stage=stage,
            batch=batch,
            config=config,
            solver=solver,
            counter=counter,
            budget=budget,
            cache=cache,
            progress=progress,
        )
        rows_by_arm[genome.candidate_id] = rows
        latencies_by_arm[genome.candidate_id] = latencies
    assert_sentinel(stage.cache_root, context="stage end")
    return ArmsResult(
        scheduled=scheduled,
        parity=parity,
        rows_by_arm=rows_by_arm,
        latencies_by_arm=latencies_by_arm,
        config=config,
        started_at=started_at,
        elapsed_seconds=time.monotonic() - clock,
    )


# ------------------------------------------------------------------------------- manifest


def solver_record(solver: Solver) -> dict[str, str]:
    return {"name": solver.name, "digest": solver.digest, "revision": solver.revision}


def build_manifest(
    batch: TaskBatch,
    scheduled: Sequence[TaskItem],
    genomes: Sequence[ModelViewGenome],
    *,
    solver: Solver,
    counter: TokenCounter,
    config: RunConfig,
    served: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Task ids, state hashes, per-arm prompt hashes, roster, solver, decoding, environment."""

    tasks: list[dict[str, Any]] = []
    prompt_hashes: dict[str, dict[str, str]] = {}
    for item in scheduled:
        qualified = qualified_task_id(batch.environment_version, batch.mechanism, item.task_id)
        pairing = qualified_task_id(
            batch.environment_version,
            batch.mechanism,
            str(item.provenance.get("rotated_from", item.task_id)),
        )
        record = _item_record(item)
        record.pop("question")
        record.pop("provenance")
        tasks.append({**record, "qualified_task_id": qualified, "pairing_key": pairing})
        prompt_hashes[qualified] = {
            genome.candidate_id: prompt_bytes_hash(
                build_prompt(genome, item, guide_policy=config.guide_policy)
            )
            for genome in genomes
        }
    n_options = len(scheduled[0].options) if scheduled else 2
    schema = response_schema(n_options)
    surfaces = [genome.surface.candidate_id for genome in genomes]
    solver_rec = solver_record(solver)
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "harness_version": HARNESS_VERSION,
        "environment_version": batch.environment_version,
        "mechanism": batch.mechanism,
        "stratum": batch.stratum,
        "pool": batch.pool,
        "families": batch.families,
        "n_items_positive": len(batch.items),
        "n_rows_per_arm": len(scheduled),
        "excluded_variants": dict(batch.excluded_variants),
        "ladder_params": dict(batch.ladder_params),
        "tasks": tasks,
        "task_hash": stable_hash(tasks),
        "prompt_hashes": prompt_hashes,
        "roster": roster_record(surfaces),
        "roster_hash": roster_hash(surfaces),
        "solver": solver_rec,
        "solver_hash": stable_hash(solver_rec),
        "served": dict(served) if served is not None else None,
        "tokenizer": {"id": counter.tokenizer_id, "exact": counter.exact},
        "decoding": dict(config.decoding),
        "response_schema": schema,
        "decoding_hash": decoding_hash(config.decoding, schema),
        "context": config.context.to_dict(),
        "runtime_condition": config.runtime_condition,
        "guide_policy": str(config.guide_policy),
        "schedule": "family-major; [ORIGINAL, ORIGINAL#rot1, COUNTERFACTUAL, COUNTERFACTUAL#rot1]",
    }


# -------------------------------------------------------------------------------- metrics


def is_base_row(row: Mapping[str, Any]) -> bool:
    return str(row["variant"]) != str(ItemVariant.ORDER_ROTATED)


def _scored(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if RowStatus(str(row["status"])) in SCORED_STATUSES]


def _accuracy(rows: Sequence[Mapping[str, Any]]) -> float | None:
    scored = _scored(rows)
    return (sum(bool(row["correct"]) for row in scored) / len(scored)) if scored else None


def pair_statistics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Position invariance (same selected CONTENT) and anchoring (same selected LETTER)."""

    scored = _scored(rows)
    base = {str(row["task_id"]): row for row in scored if is_base_row(row)}
    pairs = invariant = anchored = both_valid = 0
    for row in scored:
        if is_base_row(row):
            continue
        partner = base.get(str(row["pairing_key"]))
        if partner is None:
            continue
        pairs += 1
        invariant += int(
            partner["selected_content_hash"] is not None
            and partner["selected_content_hash"] == row["selected_content_hash"]
        )
        anchored += int(
            partner["selected_answer_id"] is not None
            and partner["selected_answer_id"] == row["selected_answer_id"]
        )
        both_valid += int(bool(partner["valid"]) and bool(row["valid"]))
    return {
        "pairs": pairs,
        "invariant_pairs": invariant,
        "anchored_pairs": anchored,
        "both_valid_pairs": both_valid,
        "position_invariance": (invariant / pairs) if pairs else None,
        "position_anchoring_rate": (anchored / pairs) if pairs else None,
    }


def _wilson(rows: Sequence[Mapping[str, Any]]) -> list[float] | None:
    scored = _scored(rows)
    if not scored:
        return None
    interval = wilson_interval(sum(bool(row["correct"]) for row in scored), len(scored))
    return [interval.lower, interval.upper]


def _latency_summary(
    latencies: Sequence[float], rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    fresh = [
        seconds for seconds, row in zip(latencies, rows, strict=True) if not bool(row["cache_hit"])
    ]
    return {
        "fresh_rows": len(fresh),
        "mean": (sum(fresh) / len(fresh)) if fresh else None,
        "max": max(fresh) if fresh else None,
        "total": sum(latencies),
    }


def arm_report(
    rows: Sequence[Mapping[str, Any]], latencies: Sequence[float] | None = None
) -> dict[str, Any]:
    """Primary accuracy on base rows, rotated accuracy, pair statistics, tokens, cache."""

    if not rows:
        raise HarnessRefusal("cannot report an empty arm")
    base = [row for row in rows if is_base_row(row)]
    rotated = [row for row in rows if not is_base_row(row)]
    base_scored = _scored(base)
    answers = Counter(
        str(row["selected_answer_id"])
        for row in base_scored
        if row["selected_answer_id"] is not None
    )
    selections = sum(answers.values())
    tokens = [int(row["prompt_tokens_counted"]) for row in rows]
    variants = sorted({str(row["variant"]) for row in rows})
    return {
        "candidate_id": str(rows[0]["candidate_id"]),
        "rows_total": len(rows),
        "base_rows": len(base),
        "rotated_rows": len(rotated),
        "base_rows_scored": len(base_scored),
        "accuracy_base": _accuracy(base),
        "accuracy_base_wilson95": _wilson(base),
        "accuracy_rotated": _accuracy(rotated),
        "accuracy_by_variant": {
            variant: _accuracy([row for row in rows if str(row["variant"]) == variant])
            for variant in variants
        },
        "largest_answer_share_base": (max(answers.values()) / selections) if selections else None,
        "answer_counts_base": dict(sorted(answers.items())),
        "pairs": pair_statistics(rows),
        "valid_response_rate": (
            sum(bool(row["valid"]) for row in _scored(rows)) / len(_scored(rows))
            if _scored(rows)
            else None
        ),
        "prompt_tokens": {
            "min": min(tokens),
            "mean": sum(tokens) / len(tokens),
            "max": max(tokens),
        },
        "status_counts": dict(sorted(Counter(str(row["status"]) for row in rows).items())),
        "cache_scopes": dict(sorted(Counter(str(row["cache_scope"]) for row in rows).items())),
        "token_mismatch_rows": sum(bool(row["token_count_mismatch"]) for row in rows),
        "solver_error_rows": sum(str(row["status"]) == str(RowStatus.SOLVER_ERROR) for row in rows),
        "over_budget_rows": sum(
            str(row["status"]) == str(RowStatus.PROMPT_OVER_BUDGET) for row in rows
        ),
        "latency_seconds": _latency_summary(latencies, rows) if latencies is not None else None,
        "harness_score": score_mechanism(rows),
    }


def select_stratum(
    stratum_accuracies: Mapping[str, float | None],
    *,
    band: tuple[float, float],
    target: float,
    ladder_order: Sequence[str] | None = None,
) -> dict[str, Any]:
    """argmin |acc - target| among strata inside the band; ties to the easier stratum.

    "Easier" is decided by the data first and by the ladder second: at equal distance the two
    candidates sit symmetrically around the target, so the one with the HIGHER accuracy is
    the easier one; at equal accuracy the stratum that comes first in ``ladder_order`` (the
    generator's easy-to-hard order) wins, and a stratum absent from that order ranks after
    every listed one in the caller's order.  The key is total, so the selection is a pure
    function of its inputs and independent of the mapping's iteration order.
    """

    low, high = float(band[0]), float(band[1])
    if not low <= target <= high:
        raise ValueError(f"target {target} must lie inside band [{low}, {high}]")
    order = list(stratum_accuracies)
    listed = {name: index for index, name in enumerate(ladder_order or ())}

    def rank(name: str) -> int:
        return listed.get(name, len(listed) + order.index(name))

    def distance(accuracy: float) -> float:
        # Accuracies are ratios of small integers and the target is a short decimal, so two
        # strata symmetric about the target differ in float distance by ~1e-17.  Rounding
        # makes that case the tie the rule is written for instead of a coin toss.
        return round(abs(accuracy - target), 12)

    inside = [
        (name, float(accuracy))
        for name, accuracy in stratum_accuracies.items()
        if accuracy is not None and low <= float(accuracy) <= high
    ]
    outside = sorted(set(order) - {name for name, _ in inside})
    record: dict[str, Any] = {
        "band": [low, high],
        "target": target,
        "rule": (
            "argmin |accuracy - target| (rounded to 12 decimals) over strata with "
            "low <= accuracy <= high"
        ),
        "tie_break": "equal distance -> higher accuracy (easier); equal accuracy -> ladder order",
        "ladder_order": list(ladder_order or ()),
        "stratum_accuracies": {name: stratum_accuracies[name] for name in order},
        "inside_band": [name for name, _ in inside],
        "outside_band": outside,
    }
    if not inside:
        return {**record, "selected": None, "reason": "NO_STRATUM_INSIDE_BAND"}
    ranked = sorted(inside, key=lambda pair: (distance(pair[1]), -pair[1], rank(pair[0])))
    return {
        **record,
        "selected": ranked[0][0],
        "selected_accuracy": ranked[0][1],
        "reason": "ARGMIN_ABS_DISTANCE_TO_TARGET",
        "ranking": [
            {"stratum": name, "accuracy": accuracy, "distance": distance(accuracy)}
            for name, accuracy in ranked
        ],
    }


def holm_baseline_comparisons(comparisons: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Holm step-down over the k baseline comparisons via the frozen ``holm_decisions``."""

    compared = {
        candidate: dict(comparison)
        for candidate, comparison in comparisons.items()
        if comparison.get("status") == "COMPARED"
    }
    if compared:
        holm_decisions(compared, key="mcnemar_exact_p")
    return {
        "alpha": HOLM_ALPHA,
        "key": "mcnemar_exact_p",
        "method": "fitness_v4.holm_decisions: sort ascending, threshold alpha/(m-i), step-down",
        "family_size": len(compared),
        "decisions": {
            candidate: {
                "p": comparison["mcnemar_exact_p"],
                "holm_threshold": comparison["holm_threshold"],
                "holm_reject": comparison["holm_reject"],
            }
            for candidate, comparison in sorted(compared.items())
        },
        "rejected": sorted(c for c, v in compared.items() if v["holm_reject"]),
        "not_compared": sorted(set(comparisons) - set(compared)),
    }


def base_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if is_base_row(row)]


# --------------------------------------------------------------------------------- stages


def _counter_record(counter: TokenCounter) -> dict[str, Any]:
    to_dict = getattr(counter, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return {"tokenizer_id": counter.tokenizer_id, "exact": counter.exact}


def _snapshot_files(root: Path) -> frozenset[str]:
    if not root.exists():
        return frozenset()
    return frozenset(str(path) for path in root.rglob("*") if path.is_file())


def _budget_record(budget: CallBudget) -> dict[str, int]:
    return {"max_calls": budget.max_calls, "spent": budget.spent, "remaining": budget.remaining}


def _check(condition: bool) -> str:
    return "PASS" if condition else "FAIL"


def run_smoke(
    root: str | Path,
    *,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    dry_run: bool = False,
    batch: TaskBatch | None = None,
    families: int = SMOKE_FAMILIES,
    surfaces: Sequence[str] = FOUNDER_SURFACES[:SMOKE_ARMS],
    served: Mapping[str, Any] | None = None,
    pool: str = "SMOKE",
    stratum: str = SMOKE_STRATUM,
    resume: bool = False,
) -> dict[str, Any]:
    """Two families, two arms, base and rotated, run twice; every check is REPORTED."""

    stage = Stage(StageKind.SMOKE, Path(root), dry_run=dry_run, resume=resume)
    if batch is None:
        batch = load_batch(stratum, pool=pool, families=families)
    batch = _limit_families(batch, families)
    genomes = founder_roster(surfaces)
    cache_parent = stage.artifact_root / "cache"
    before = _snapshot_files(cache_parent)
    first = run_arms(
        stage, batch, genomes, solver=solver, counter=counter, budget=budget, label="smoke"
    )
    replay = run_arms(
        stage, batch, genomes, solver=solver, counter=counter, budget=budget, label="smoke-replay"
    )
    after = _snapshot_files(cache_parent)
    new_files = sorted(after - before)
    cache_root_text = str(stage.cache_root)
    manifest = build_manifest(
        batch,
        first.scheduled,
        genomes,
        solver=solver,
        counter=counter,
        config=first.config,
        served=served,
    )
    rows = [row for arm_rows in first.rows_by_arm.values() for row in arm_rows]
    replay_rows = [row for arm_rows in replay.rows_by_arm.values() for row in arm_rows]
    replay_identical = len(rows) == len(replay_rows) and all(
        a["task_id"] == b["task_id"]
        and a["candidate_id"] == b["candidate_id"]
        and a["raw_output"] == b["raw_output"]
        and a["prompt_hash"] == b["prompt_hash"]
        for a, b in zip(rows, replay_rows, strict=True)
    )
    artifact_relpath = stage.artifact_relpath("smoke")
    checks = {
        "served_digest_matches": (
            "NOT_APPLICABLE_NO_SERVED_RECORD"
            if served is None
            else _check(str(served.get("digest")) == solver.digest)
        ),
        "grammar_parseable_answers": _check(all(bool(row["valid"]) for row in rows)),
        "token_counts_exact": _check(
            all(
                row["prompt_tokens_reported"] is not None and not row["token_count_mismatch"]
                for row in rows
            )
        ),
        "no_solver_errors": _check(
            all(str(row["status"]) != str(RowStatus.SOLVER_ERROR) for row in rows)
        ),
        "cache_files_under_smoke_namespace_only": _check(
            all(path.startswith(cache_root_text) for path in new_files)
        ),
        "replay_same_condition_reuse": _check(
            all(str(row["cache_scope"]) == "SAME_CONDITION_REUSE" for row in replay_rows)
        ),
        "replay_raw_output_identical": _check(replay_identical),
        "prompt_bytes_match_manifest": _check(
            all(
                manifest["prompt_hashes"].get(str(row["task_id"]), {}).get(str(row["candidate_id"]))
                == row["prompt_hash"]
                for row in rows
            )
        ),
        "rotated_follows_base": _check(
            all(
                not is_base_row(arm_rows[index + 1])
                and arm_rows[index + 1]["pairing_key"] == arm_rows[index]["task_id"]
                for arm_rows in first.rows_by_arm.values()
                for index in range(0, len(arm_rows) - 1, 2)
            )
        ),
        "artifact_path_isolated": _check(
            artifact_relpath.startswith(ARTIFACT_NAMESPACES[stage.namespace])
            and cache_root_text.endswith(CACHE_NAMESPACES[stage.namespace])
        ),
        "sentinel_present": _check((stage.cache_root / SENTINEL_NAME).is_file()),
    }
    passed = all(value == "PASS" or value.startswith("NOT_APPLICABLE") for value in checks.values())
    payload: dict[str, Any] = {
        "experiment_version": EXPERIMENT_VERSION,
        "stage": str(StageKind.SMOKE),
        "stage_config": stage.to_dict(),
        "paths": stage.paths(),
        "passed": passed,
        "checks": checks,
        "arms": [genome.candidate_id for genome in genomes],
        "batch": batch.to_dict(),
        "manifest": manifest,
        "parity": list(first.parity),
        "arm_reports": {
            candidate: arm_report(arm_rows, first.latencies_by_arm[candidate])
            for candidate, arm_rows in first.rows_by_arm.items()
        },
        "rows": rows,
        "replay_rows": replay_rows,
        "new_cache_files": len(new_files),
        "counter": _counter_record(counter),
        "budget": _budget_record(budget),
        "timing": {"first": first.timing(), "replay": replay.timing()},
    }
    written = guarded_write(stage.artifact_store, artifact_relpath, payload, resume=resume)
    return {**payload, "artifact": written}


def run_calibration(
    root: str | Path,
    *,
    strata: Sequence[str],
    families: int,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    dry_run: bool = False,
    band: tuple[float, float] = DEFAULT_BAND,
    target: float = DEFAULT_TARGET,
    batches: Sequence[TaskBatch] | None = None,
    pool: str = "DEV",
    served: Mapping[str, Any] | None = None,
    resume: bool = False,
    start: int = 0,
) -> dict[str, Any]:
    """Control arm only, positives only, one batch per stratum, then the selector."""

    stage = Stage(StageKind.CALIBRATION, Path(root), dry_run=dry_run, resume=resume)
    if batches is None:
        batches = tuple(
            load_batch(stratum, pool=pool, families=families, start=start) for stratum in strata
        )
    if tuple(batch.stratum for batch in batches) != tuple(strata):
        raise HarnessRefusal(
            f"batch strata {[b.stratum for b in batches]} do not match requested {list(strata)}"
        )
    control = founder_roster((BASELINE_SURFACE,))
    control_id = control[0].candidate_id
    per_stratum: dict[str, Any] = {}
    started_at = datetime.now(UTC).isoformat()
    clock = time.monotonic()
    for batch in batches:
        result = run_arms(
            stage,
            batch,
            control,
            solver=solver,
            counter=counter,
            budget=budget,
            label=f"calibration:{batch.stratum}",
        )
        rows = result.rows_by_arm[control_id]
        per_stratum[batch.stratum] = {
            "batch": batch.to_dict(),
            "manifest": build_manifest(
                batch,
                result.scheduled,
                control,
                solver=solver,
                counter=counter,
                config=result.config,
                served=served,
            ),
            "parity": list(result.parity),
            "arm": arm_report(rows, result.latencies_by_arm[control_id]),
            "rows": rows,
            "timing": result.timing(),
        }
    accuracies = {stratum: per_stratum[stratum]["arm"]["accuracy_base"] for stratum in strata}
    selection = select_stratum(
        accuracies, band=band, target=target, ladder_order=ladder_order() or tuple(strata)
    )
    solver_rec = solver_record(solver)
    manifest = {
        "experiment_version": EXPERIMENT_VERSION,
        "strata": list(strata),
        "strata_task_hashes": {
            stratum: per_stratum[stratum]["manifest"]["task_hash"] for stratum in strata
        },
        "task_hash": stable_hash(
            [per_stratum[stratum]["manifest"]["task_hash"] for stratum in strata]
        ),
        "roster": roster_record((BASELINE_SURFACE,)),
        "roster_hash": roster_hash((BASELINE_SURFACE,)),
        "solver": solver_rec,
        "solver_hash": stable_hash(solver_rec),
        "served": dict(served) if served is not None else None,
        "environment_version": batches[0].environment_version,
        "mechanism": batches[0].mechanism,
        "pool": batches[0].pool,
        "families": families,
    }
    payload: dict[str, Any] = {
        "experiment_version": EXPERIMENT_VERSION,
        "stage": str(StageKind.CALIBRATION),
        "stage_config": stage.to_dict(),
        "paths": stage.paths(),
        "control_arm": control_id,
        "band": [float(band[0]), float(band[1])],
        "target": target,
        "families": families,
        "strata": list(strata),
        "per_stratum": per_stratum,
        "stratum_accuracies": accuracies,
        "selection": selection,
        "manifest": manifest,
        "counter": _counter_record(counter),
        "budget": _budget_record(budget),
        "timing": {"started_at": started_at, "elapsed_seconds": time.monotonic() - clock},
    }
    name = "calibration-" + "-".join(strata)
    written = guarded_write(
        stage.artifact_store, stage.artifact_relpath(name), payload, resume=resume
    )
    return {**payload, "artifact": written}


def run_tournament(
    root: str | Path,
    *,
    stratum: str,
    families: int,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    surfaces: Sequence[str] = FOUNDER_SURFACES,
    dry_run: bool = False,
    resume: bool = False,
    batch: TaskBatch | None = None,
    pool: str = "TOURNAMENT",
    served: Mapping[str, Any] | None = None,
    start: int = 0,
) -> dict[str, Any]:
    """All founder arms on identical items; per-arm reports; baseline + all-pairs; Holm."""

    stage = Stage(StageKind.TOURNAMENT, Path(root), dry_run=dry_run, resume=resume)
    if BASELINE_SURFACE not in surfaces:
        raise HarnessRefusal(f"tournament roster must contain the baseline {BASELINE_SURFACE}")
    if batch is None:
        batch = load_batch(stratum, pool=pool, families=families, start=start)
    if batch.stratum != stratum:
        raise HarnessRefusal(f"batch stratum {batch.stratum!r} != requested {stratum!r}")
    genomes = founder_roster(surfaces)
    baseline = baseline_candidate_id()
    result = run_arms(
        stage,
        batch,
        genomes,
        solver=solver,
        counter=counter,
        budget=budget,
        label=f"tournament:{stratum}",
    )
    reports = {
        candidate: arm_report(rows, result.latencies_by_arm[candidate])
        for candidate, rows in result.rows_by_arm.items()
    }
    primary = {candidate: base_rows(rows) for candidate, rows in result.rows_by_arm.items()}
    vs_baseline = {
        candidate: compare_arms(rows, primary[baseline])
        for candidate, rows in primary.items()
        if candidate != baseline
    }
    all_pairs = {
        f"{left}|{right}": compare_arms(primary[left], primary[right])
        for left, right in combinations(sorted(primary), 2)
    }
    payload: dict[str, Any] = {
        "experiment_version": EXPERIMENT_VERSION,
        "stage": str(StageKind.TOURNAMENT),
        "stage_config": stage.to_dict(),
        "paths": stage.paths(),
        "stratum": stratum,
        "families": families,
        "baseline_candidate": baseline,
        "arms": [genome.candidate_id for genome in genomes],
        "batch": batch.to_dict(),
        "manifest": build_manifest(
            batch,
            result.scheduled,
            genomes,
            solver=solver,
            counter=counter,
            config=result.config,
            served=served,
        ),
        "parity": list(result.parity),
        "arm_reports": reports,
        "primary_metric": "accuracy on base rows (ORIGINAL + COUNTERFACTUAL); rotated rows audit position",
        "comparisons_vs_baseline": vs_baseline,
        "holm": holm_baseline_comparisons(vs_baseline),
        "comparisons_all_pairs": all_pairs,
        "rows": result.rows_by_arm,
        "counter": _counter_record(counter),
        "budget": _budget_record(budget),
        "timing": result.timing(),
    }
    written = guarded_write(
        stage.artifact_store,
        stage.artifact_relpath(f"tournament-{stratum}"),
        payload,
        resume=resume,
    )
    return {**payload, "artifact": written}


def run_dry_run(
    root: str | Path,
    *,
    families: int = 4,
    budget_max: int = 100_000,
    batches: Sequence[TaskBatch] | None = None,
) -> dict[str, Any]:
    """Smoke, calibration and tournament with the stub solver under the dryrun namespace."""

    chosen = tuple(batches) if batches is not None else dry_run_batches(None, families=families)
    n_options = len(chosen[0].items[0].options)
    solver = StubSolver(policy=StubSolverPolicy.DETERMINISTIC_MIX, n_options=n_options)
    counter = StubTokenCounter()
    smoke = run_smoke(
        root,
        solver=solver,
        counter=counter,
        budget=CallBudget(budget_max),
        dry_run=True,
        batch=chosen[0],
        families=SMOKE_FAMILIES,
    )
    calibration = run_calibration(
        root,
        strata=[batch.stratum for batch in chosen],
        families=families,
        solver=solver,
        counter=counter,
        budget=CallBudget(budget_max),
        dry_run=True,
        batches=chosen,
    )
    tournament = run_tournament(
        root,
        stratum=chosen[0].stratum,
        families=families,
        solver=solver,
        counter=counter,
        budget=CallBudget(budget_max),
        dry_run=True,
        batch=chosen[0],
    )
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "stage": "dryrun",
        "smoke": smoke,
        "calibration": calibration,
        "tournament": tournament,
    }


# ------------------------------------------------------------------------------ summaries


def _compact(payload: Mapping[str, Any]) -> dict[str, Any]:
    stage = str(payload.get("stage"))
    artifact = payload.get("artifact", {})
    if stage == "dryrun":
        return {
            "stage": stage,
            "smoke": _compact(payload["smoke"]),
            "calibration": _compact(payload["calibration"]),
            "tournament": _compact(payload["tournament"]),
        }
    if stage == str(StageKind.SMOKE):
        return {
            "stage": stage,
            "passed": payload["passed"],
            "checks": payload["checks"],
            "rows": len(payload["rows"]),
            "budget": payload["budget"],
            "artifact": artifact.get("relative"),
            "decision": artifact.get("decision"),
        }
    if stage == str(StageKind.CALIBRATION):
        return {
            "stage": stage,
            "stratum_accuracies": payload["stratum_accuracies"],
            "per_stratum": {
                stratum: _compact_arm(record["arm"])
                for stratum, record in payload["per_stratum"].items()
            },
            "selected": payload["selection"]["selected"],
            "reason": payload["selection"]["reason"],
            "band": payload["band"],
            "target": payload["target"],
            "budget": payload["budget"],
            "artifact": artifact.get("relative"),
            "decision": artifact.get("decision"),
        }
    return {
        "stage": stage,
        "stratum": payload["stratum"],
        "arms": {
            candidate: _compact_arm(report) for candidate, report in payload["arm_reports"].items()
        },
        "holm_rejected": payload["holm"]["rejected"],
        "budget": payload["budget"],
        "artifact": artifact.get("relative"),
        "decision": artifact.get("decision"),
    }


def _compact_arm(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "accuracy_base": report["accuracy_base"],
        "accuracy_rotated": report["accuracy_rotated"],
        "position_invariance": report["pairs"]["position_invariance"],
        "position_anchoring_rate": report["pairs"]["position_anchoring_rate"],
        "prompt_tokens": report["prompt_tokens"],
        "cache_scopes": report["cache_scopes"],
    }


# ------------------------------------------------------------------------------------ CLI


def _parse_band(text: str) -> tuple[float, float]:
    parts = [float(part) for part in text.split(",")]
    if len(parts) != 2 or parts[0] > parts[1]:
        raise argparse.ArgumentTypeError(
            f"--band must be 'low,high' with low <= high, got {text!r}"
        )
    return parts[0], parts[1]


def _parse_csv(text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in text.split(",") if part.strip())


def _live_wiring(stage: Stage) -> tuple[Any, Any, dict[str, Any]]:
    """Construct the live solver and counter.  Only reached after both live flags."""

    from arena.experiments.ollama_live import (
        FROZEN_SOLVER,
        OllamaPreflightTokenCounter,
        live_solver,
        served_model_record,
    )

    served = served_model_record(FROZEN_SOLVER)
    token_dir = stage.cache_root / "token_counts"
    assert_phase8_namespace(token_dir)
    counter = OllamaPreflightTokenCounter(
        FROZEN_SOLVER,
        num_ctx=CONTEXT_BUDGET.num_ctx,
        cache_dir=token_dir,
        template_hash=str(served["template_hash"]),
    )
    solver = live_solver(FROZEN_SOLVER, revision=str(served["template_hash"]), bare=True)
    return solver, counter, served


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="stub solver; no network call")
    parser.add_argument("--live", action="store_true", help="use the frozen Ollama solver")
    parser.add_argument(
        "--confirm-model-calls",
        action="store_true",
        help="required alongside --live; no budget is spent without it",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--tournament", action="store_true")
    parser.add_argument("--wipe-smoke", action="store_true", help="delete ONLY the smoke cache")
    parser.add_argument("--strata", type=str, default="", help="comma-separated, ladder order")
    parser.add_argument("--stratum", type=str, default="")
    parser.add_argument("--families", type=int, default=None)
    parser.add_argument("--band", type=_parse_band, default=DEFAULT_BAND)
    parser.add_argument("--target", type=float, default=DEFAULT_TARGET)
    parser.add_argument("--budget", type=int, default=None, help="max fresh model calls")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pool", type=str, default="", help="override the stage's ladder pool")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--surfaces", type=str, default="", help="comma-separated roster override")
    args = parser.parse_args(argv)

    stages = [name for name in ("smoke", "calibrate", "tournament") if getattr(args, name)]
    if args.wipe_smoke:
        print(canonical_json({"wipe_smoke": wipe_smoke_cache(args.root)}))
        if not stages and not args.dry_run and not args.live:
            return 0
    if args.live and not args.confirm_model_calls:
        parser.error(
            "--live requires --confirm-model-calls. The Solver budget belongs to the "
            "integrator; this experiment never spends it implicitly."
        )
    if args.confirm_model_calls and not args.live:
        parser.error("--confirm-model-calls only means something together with --live")
    if args.dry_run and args.live:
        parser.error("choose exactly one of --dry-run and --live")
    if not args.dry_run and not args.live:
        parser.error("pass --dry-run (stub solver) or --live --confirm-model-calls")
    if len(stages) > 1:
        parser.error("run one stage at a time")

    root = Path(args.root)
    surfaces = _parse_csv(args.surfaces) or FOUNDER_SURFACES
    strata = _parse_csv(args.strata)

    if args.dry_run:
        families = args.families or 4
        budget_max = args.budget if args.budget is not None else 100_000
        if not stages:
            payload = run_dry_run(root, families=families, budget_max=budget_max)
        else:
            batches = dry_run_batches(strata or None, families=families)
            n_options = len(batches[0].items[0].options)
            solver = StubSolver(policy=StubSolverPolicy.DETERMINISTIC_MIX, n_options=n_options)
            counter = StubTokenCounter()
            budget = CallBudget(budget_max)
            if stages[0] == "smoke":
                payload = run_smoke(
                    root,
                    solver=solver,
                    counter=counter,
                    budget=budget,
                    dry_run=True,
                    batch=batches[0],
                    resume=args.resume,
                )
            elif stages[0] == "calibrate":
                payload = run_calibration(
                    root,
                    strata=[batch.stratum for batch in batches],
                    families=families,
                    solver=solver,
                    counter=counter,
                    budget=budget,
                    dry_run=True,
                    band=args.band,
                    target=args.target,
                    batches=batches,
                    resume=args.resume,
                )
            else:
                chosen = args.stratum or batches[0].stratum
                batch = next((b for b in batches if b.stratum == chosen), None)
                if batch is None:
                    parser.error(f"--stratum {chosen!r} not among dry-run strata")
                payload = run_tournament(
                    root,
                    stratum=chosen,
                    families=families,
                    solver=solver,
                    counter=counter,
                    budget=budget,
                    surfaces=surfaces,
                    dry_run=True,
                    resume=args.resume,
                    batch=batch,
                )
        print(canonical_json(_compact(payload)))
        return 0

    # Live path: both flags verified above.
    if not stages:
        parser.error("a live run needs exactly one of --smoke / --calibrate / --tournament")
    if args.budget is None:
        parser.error("--budget is required for a live stage (fail closed)")
    kind = {
        "smoke": StageKind.SMOKE,
        "calibrate": StageKind.CALIBRATION,
        "tournament": StageKind.TOURNAMENT,
    }[stages[0]]
    # Every argument check precedes the served-model verification, so an incomplete command
    # line never opens a connection.
    if kind is StageKind.CALIBRATION and not strata:
        parser.error("--calibrate needs --strata")
    if kind is StageKind.TOURNAMENT and not args.stratum:
        parser.error("--tournament needs --stratum")
    ladder_module()  # clear message if the ladder is absent, before any model call
    stage = Stage(kind, root, dry_run=False, resume=args.resume)
    solver, counter, served = _live_wiring(stage)
    budget = CallBudget(int(args.budget))
    if kind is StageKind.SMOKE:
        payload = run_smoke(
            root,
            solver=solver,
            counter=counter,
            budget=budget,
            served=served,
            pool=args.pool or "SMOKE",
            stratum=args.stratum or SMOKE_STRATUM,
            resume=args.resume,
        )
    elif kind is StageKind.CALIBRATION:
        payload = run_calibration(
            root,
            strata=strata,
            families=args.families or 24,
            solver=solver,
            counter=counter,
            budget=budget,
            band=args.band,
            target=args.target,
            pool=args.pool or "DEV",
            served=served,
            start=args.start,
            resume=args.resume,
        )
    else:
        payload = run_tournament(
            root,
            stratum=args.stratum,
            families=args.families or 24,
            solver=solver,
            counter=counter,
            budget=budget,
            surfaces=surfaces,
            resume=args.resume,
            pool=args.pool or "TOURNAMENT",
            served=served,
            start=args.start,
        )
    print(canonical_json(_compact(payload)))
    return 0


__all__ = [
    "ARTIFACT_NAMESPACES",
    "BASELINE_SURFACE",
    "CACHE_NAMESPACES",
    "CONTEXT_BUDGET",
    "DEFAULT_BAND",
    "DEFAULT_TARGET",
    "EXPERIMENT_VERSION",
    "FOUNDER_SURFACES",
    "FROZEN_NAMESPACES",
    "GUIDE_POLICY",
    "SENTINEL_CHECK_EVERY",
    "SENTINEL_NAME",
    "CacheVanished",
    "FrozenNamespaceRefusal",
    "LadderUnavailable",
    "SmokeCacheRefusal",
    "Stage",
    "StageKind",
    "TaskBatch",
    "arm_report",
    "assert_phase8_namespace",
    "assert_sentinel",
    "build_manifest",
    "ensure_sentinel",
    "founder_roster",
    "guarded_write",
    "holm_baseline_comparisons",
    "ladder_order",
    "load_batch",
    "main",
    "pair_statistics",
    "positive_items",
    "refuse_frozen_paths",
    "roster_hash",
    "run_arms",
    "run_calibration",
    "run_dry_run",
    "run_smoke",
    "run_tournament",
    "schedule_items",
    "select_stratum",
    "stub_batch",
    "stub_batches",
    "wipe_smoke_cache",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
