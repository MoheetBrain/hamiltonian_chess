"""One generation of the outer loop, executable end to end and entirely offline.

    population -> choose parent -> mutate -> SEMANTIC GATE -> evaluate -> record fitness
                -> archive / promote / kill -> next generation

Every stage reuses machinery that already exists and is tested:

* mutation           ``arena.players.architect.Architect`` over ``arena.genome.mutation``
* semantic gate      ``arena.model_view.compiler.ModelViewCompiler.validate`` (round-trip to the
                     identical ``mathematical_hash``) and
                     ``arena.experiments.game_r_formal_v1.assert_arena_parity`` (which refuses
                     byte-identical arms, i.e. an inert mutation)
* leakage gate       ``arena.experiments.rendered_prompt_adversary.evaluate_rules`` on the exact
                     bytes a Solver would receive; costs zero model calls
* arena              ``arena.environments.precondition_ladder.build_pool``
* archive            ``arena.league.registry.LeagueRegistry.record_match`` +
                     ``arena.league.selection.rank_registry`` / ``select_frontier_diverse``
* record             ``arena.evolution.record`` through ``arena.storage.artifacts.ArtifactStore``

**What this is not.**  The V0 evaluator is :class:`StubSolver`: a deterministic hash over the
rendered prompt.  It cannot reason, so it *has* no ``J_solve``.  It exists so the loop's plumbing
can be exercised, ranked and recorded without a model call.

That last claim used to be enforced by a sentence.  It is now enforced by the schema
(``docs/HC_V0_RED_TEAM.md`` RT-16): :class:`StubLadderEvaluator` declares
``EvaluationMode.EXECUTABILITY_STUB``, and under that mode a
:class:`~arena.evolution.record.FitnessVector` **cannot be constructed** with a number in any
dimension.  The stub's readings go to :class:`~arena.evolution.record.DiagnosticReadings` under
names that may never be a ``J_*`` name; the archive ranks on those, prefixed with the mode that
produced them; and the league observations are written ``verified=False``, so a chance-level hash
cannot acquire a confidence interval in ``league-registry.json``.  A reader who opens any artefact
this module writes and looks for a scientific ``J_solve`` will not find one, because none exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from arena.canonical.schema import stable_hash
from arena.environments.precondition_ladder import (
    ENVIRONMENT_VERSION,
    MECHANISM,
    Pool,
    build_pool,
)
from arena.evolution.record import (
    DIMENSION_DIRECTIONS,
    RECORD_SCHEMA_VERSION,
    SCHEMA_DIVERGENCES,
    Budget,
    DatasetIdentity,
    DiagnosticReadings,
    DimensionStatus,
    EvaluationContext,
    EvaluationMode,
    EvidenceActor,
    EvolutionRecordStore,
    ExperimentalCondition,
    FitnessDimension,
    FitnessRecord,
    FitnessVector,
    GateOutcome,
    GateStatus,
    GeneChangeRecord,
    ModelIdentity,
    MutationDescriptor,
    RecordStatus,
    ReplicateAuthorisation,
    StubFitnessNotRepresentable,
)
from arena.experiments.game_r_formal_v1 import (
    HARNESS_VERSION,
    MaterialisedItem,
    ParityViolation,
    assert_arena_parity,
    build_prompt,
    canonical_answer_ids,
)
from arena.experiments.rendered_prompt_adversary import (
    ADVERSARY_FAMILY_VERSION,
    Example,
    evaluate_rules,
)
from arena.fitness.metrics import Direction, mean_metric, proportion_metric
from arena.fitness.pareto import Objective, ParetoPoint
from arena.genome.genes import GeneFamily
from arena.genome.mutation import MutationProposal
from arena.genome.schema import LanguageGenome
from arena.genome.seeds import SEED_GENOMES
from arena.languages.base import CandidateLanguage
from arena.languages.registry import language_for_genome
from arena.league.matches import LeagueMatch, MatchObservation
from arena.league.registry import LeagueRegistry
from arena.league.selection import rank_registry, select_frontier_diverse
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.players.architect import Architect, ArchitectProposal
from arena.storage.artifacts import ArtifactStore

LOOP_VERSION = "arena-evolution-loop-v0.1.0"
DATASET_SEAL_STATE = "UNSEALED"
STUB_REVISION = "arena-evolution-stub-r1"

#: The declared V0 answer-leakage operating point (``docs/LONG_HORIZON_FITNESS_V0.md`` section
#: 3.1): n_EVAL = 800 with a 0.60 Bonferroni Clopper-Pearson **upper** bound.  At the pool sizes
#: this loop runs, that bound cannot get near 0.60, so applying it as an elimination rule would
#: void clean languages almost surely - the mirror of the V7 C3e failure, and the exact trap the
#: spec's own table (false-void 0.9937 at n=400, threshold 0.55) documents.  V0 therefore
#: eliminates only on **demonstrated** leakage (the lower bound above chance) and reports
#: ``UNDERPOWERED`` whenever the declared upper-bound target is not attained.
LEAKAGE_UPPER_BOUND_TARGET = 0.60
LEAKAGE_TARGET_N_EVAL = 800


class FailureMode(StrEnum):
    TRUTH_ALTERED = "TRUTH_ALTERED"
    MUTATION_INERT = "MUTATION_INERT"
    PARITY_VIOLATION = "PARITY_VIOLATION"
    ANSWER_LEAKAGE = "ANSWER_LEAKAGE"
    RENDER_FAILURE = "RENDER_FAILURE"


class Outcome(StrEnum):
    SCORED = "SCORED"
    KILLED_BY_SEMANTIC_GATE = "KILLED_BY_SEMANTIC_GATE"


class ParentSelection(StrEnum):
    ROUND_ROBIN = "round-robin"
    PARETO_RANK = "pareto-rank"


# ------------------------------------------------------------------------------ arena spec


@dataclass(frozen=True, slots=True)
class ArenaSpec:
    """The diagnostic arena.  Horizon 1 - this is a *diagnostic*, not the trajectory world.

    The solve pool and the adversary pool are different :class:`Pool` values, and the pool name
    enters every family salt, so selection rows and leakage-gate rows are family-disjoint by
    construction rather than by convention.
    """

    stratum: str = "P05"
    solve_pool: Pool = Pool.SMOKE
    solve_families: int = 8
    adversary_pool: Pool = Pool.ADV_DEV
    adversary_families: int = 40

    @property
    def arena_id(self) -> str:
        return f"{ENVIRONMENT_VERSION}|{MECHANISM}|{self.stratum}"

    def solve_items(self) -> tuple[MaterialisedItem, ...]:
        return build_pool(self.stratum, self.solve_pool, self.solve_families)

    def adversary_items(self) -> tuple[MaterialisedItem, ...]:
        return build_pool(self.stratum, self.adversary_pool, self.adversary_families)

    def dataset(self) -> DatasetIdentity:
        return DatasetIdentity(
            version=ENVIRONMENT_VERSION,
            split=f"{self.solve_pool.value}:{self.stratum}:{self.solve_families}",
            seal_state=DATASET_SEAL_STATE,
            generator_version=ENVIRONMENT_VERSION,
            # The pool is generated on demand from a salted SHA-256 seed and is never trained
            # on, so declared and measured exposure are both zero - and both are recorded, so
            # a future non-zero exposure has to reconcile rather than appear.
            declared_exposure_steps=0,
            measured_exposure_steps=0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "arena_id": self.arena_id,
            "stratum": self.stratum,
            "solve_pool": self.solve_pool.value,
            "solve_families": self.solve_families,
            "adversary_pool": self.adversary_pool.value,
            "adversary_families": self.adversary_families,
            "horizon": 1,
        }


def model_view(genome: LanguageGenome, *, candidate_id: str | None = None) -> ModelViewGenome:
    """A Track-E arm: reversible surface only, content genome pinned at its default."""

    return ModelViewGenome(
        candidate_id or genome.candidate_id,
        (),
        SearchTrack.EQUAL_INFORMATION,
        genome,
        ContentGenome(),
    )


def rendered_prompts(genome: LanguageGenome, items: Sequence[MaterialisedItem]) -> tuple[str, ...]:
    view = model_view(genome)
    return tuple(build_prompt(view, item) for item in items)


# -------------------------------------------------------------------------------- evaluator


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    task_id: str
    family_id: str
    level: int
    variant: str
    correct: bool
    prompt_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "family_id": self.family_id,
            "level": self.level,
            "variant": self.variant,
            "correct": self.correct,
            "prompt_bytes": self.prompt_bytes,
        }


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    candidate_id: str
    rows: tuple[EvaluationRow, ...]
    calls: int
    tokens: int
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("an evaluation outcome must contain rows")


class Evaluator(Protocol):
    """The seam a real Solver, and later a trajectory arena, drops into.

    Nothing in :func:`run_generation` knows how an outcome was produced: swapping the stub for
    a live Solver, or a single-step arena for an episodic one, changes only what implements
    this protocol.
    """

    @property
    def evaluator_id(self) -> str: ...

    @property
    def model(self) -> ModelIdentity: ...

    @property
    def fidelity_level(self) -> int: ...

    @property
    def evaluation_mode(self) -> EvaluationMode:
        """Whether this evaluator's readings are admissible as scientific fitness (RT-16).

        Part of the protocol, not of the loop: only the thing that produced a number can say what
        kind of number it is, and a stub that had to declare itself cannot forget to.
        """
        ...

    @property
    def actor(self) -> EvidenceActor:
        """Who chose the actions being scored (RT-04).  Never inferred, never rewritten."""
        ...

    @property
    def condition(self) -> ExperimentalCondition:
        """Controller, toolset, adaptation allowance and inference protocol (RT-13)."""
        ...

    def evaluate(
        self,
        *,
        genome: LanguageGenome,
        language: CandidateLanguage,
        items: Sequence[MaterialisedItem],
    ) -> EvaluationOutcome: ...


@dataclass(frozen=True, slots=True)
class StubSolver:
    """A deterministic chooser that reads the prompt's *bytes* and nothing else.

    It has no reasoning ability and no access to truth: its answer is
    ``sha256(prompt) mod n_options``.  Its accuracy is therefore chance-level up to the hash's
    arbitrary partition of prompt space, and a ``J_solve`` difference between two languages
    under this solver is **noise, not evidence**.  It exists so the loop's every other stage -
    gates, records, archive, ranking - can run with zero model calls.
    """

    identity_string: str = "stub:sha256-prompt-choice-v1"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.identity_string.encode("utf-8")).hexdigest()

    def choose(self, prompt: str, n_options: int) -> int:
        if n_options < 2:
            raise ValueError("a choice needs at least two options")
        return int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16], 16) % n_options

    def identity(self) -> ModelIdentity:
        return ModelIdentity(
            name=self.identity_string,
            digest=self.digest,
            template_hash=stable_hash({"envelope": HARNESS_VERSION}),
            decoding_hash=stable_hash({"decoding": "none", "temperature": 0.0}),
            revision=STUB_REVISION,
            # No tokenizer is bound offline, so no token count is claimed anywhere and
            # ``tokenizer_exact`` stays false; the record refuses a non-zero token count under it.
            tokenizer_id="none:no-tokenizer-bound",
            tokenizer_exact=False,
            response_schema_hash=stable_hash({"schema": "arena-game-r-canonical-answer-id"}),
            runtime_condition="offline-no-network",
            available=True,
            is_stub=True,
        )


@dataclass(frozen=True, slots=True)
class StubLadderEvaluator:
    """Fidelity 0: deterministic, offline, zero model calls, zero tokens.

    Token accounting is deliberately left at zero rather than estimated.
    ``game_r_formal_v1.TokenAccountingRefusal`` exists because two earlier phases guessed token
    counts from characters; with no tokenizer bound there is no honest token number, so
    ``J_cost`` is reported in rendered UTF-8 bytes and ``budget.tokens`` stays 0.
    """

    solver: StubSolver = field(default_factory=StubSolver)

    @property
    def evaluator_id(self) -> str:
        return f"stub-ladder-evaluator-v0|{self.solver.identity_string}"

    @property
    def model(self) -> ModelIdentity:
        return self.solver.identity()

    @property
    def fidelity_level(self) -> int:
        return 0

    @property
    def evaluation_mode(self) -> EvaluationMode:
        """RT-16.  Declared here, enforced by the type system downstream.

        Nothing this evaluator produces can be filed as a ``J_*`` reading:
        :class:`~arena.evolution.record.FitnessVector` refuses to be constructed with a number
        under this mode, so ``league-registry.json`` cannot acquire a scientific-looking
        ``J_solve`` however the loop is wired.
        """

        return EvaluationMode.EXECUTABILITY_STUB

    @property
    def actor(self) -> EvidenceActor:
        """The stub chooses its own answers, so the actor is ``SOLVER`` - a very bad one.

        Not ``REFERENCE``: it has no access to truth.  The two claims it must not be able to make
        are handled separately - "this was a policy" (actor) and "this is a result" (mode).
        """

        return EvidenceActor.SOLVER

    @property
    def condition(self) -> ExperimentalCondition:
        return ExperimentalCondition(
            controller="none:single-shot-choice",
            toolset="none",
            adaptation_condition="NO_ADAPTATION",
            adaptation_budget="0",
            inference_condition="single-pass|deterministic|n=1",
        )

    def evaluate(
        self,
        *,
        genome: LanguageGenome,
        language: CandidateLanguage,
        items: Sequence[MaterialisedItem],
    ) -> EvaluationOutcome:
        del language  # the prompt is built from the genome's model view, not the bare codec
        rows: list[EvaluationRow] = []
        for item, prompt in zip(items, rendered_prompts(genome, items), strict=True):
            n_options = len(item.options)
            choice = self.solver.choose(prompt, n_options)
            rows.append(
                EvaluationRow(
                    task_id=item.task_id,
                    family_id=item.family_id,
                    level=item.level,
                    variant=item.variant,
                    correct=choice == item.correct_index,
                    prompt_bytes=len(prompt.encode("utf-8")),
                )
            )
        return EvaluationOutcome(
            candidate_id=genome.candidate_id,
            rows=tuple(rows),
            calls=0,
            tokens=0,
            notes=(
                "deterministic stub solver; no model call, no network, no tokenizer",
                "J_solve under this evaluator is chance-level by construction",
            ),
        )


# ------------------------------------------------------------------------------------ gates


@dataclass(frozen=True, slots=True)
class GateReport:
    outcomes: tuple[GateOutcome, ...]
    failure_modes: tuple[str, ...]
    inert: bool
    inert_evidence: str

    @property
    def passed(self) -> bool:
        return not any(item.eliminated for item in self.outcomes)


def _prompt_or_none(
    genome: LanguageGenome, items: Sequence[MaterialisedItem]
) -> tuple[str, ...] | str:
    try:
        return rendered_prompts(genome, items)
    except Exception as error:  # noqa: BLE001 - any renderer failure is a gate failure
        return f"{type(error).__name__}: {error}"


def semantic_gate(
    *,
    parent: LanguageGenome,
    child: LanguageGenome,
    items: Sequence[MaterialisedItem],
    child_language: CandidateLanguage | None = None,
) -> GateReport:
    """Fail closed, non-compensatory.  A failure kills; it is never traded against fitness.

    Three checks, in order of what they protect:

    1. **``semantic_roundtrip``** - every state rendered by the child's *executable surface* and
       parsed back must reproduce the backend's own ``mathematical_hash``, and
       ``ModelViewCompiler.validate`` must reproduce the compiled view independently.  This is
       ``HAMILTONIAN_CHESS_META_GOAL.md`` section 4's invariant, and it is what kills a renderer
       that drops a ``holds(...)`` assumption.
    2. **``mutation_effective``** - the child's rendered prompt bytes must differ from the
       parent's somewhere in the pool.  A byte-inert mutation is not a candidate; it is the same
       organism wearing the same skin, and ``assert_arena_parity`` refuses such a pair anyway.
    3. **``arena_parity``** - ``assert_arena_parity`` on every item: same information on the
       page, same option content and order, same envelope and answer protocol, distinct bytes.

    ``child_language`` exists so a hostile or hand-written renderer can be put through check 1.
    In the loop it is always ``language_for_genome(child)``, so checks 1 and 3 see one object.
    """

    outcomes: list[GateOutcome] = []
    failures: list[str] = []
    language = child_language if child_language is not None else language_for_genome(child)
    compiler = ModelViewCompiler(model_view(child))

    roundtrip_failures: list[str] = []
    for item in items:
        state = item.canonical_state
        try:
            recovered = language.parse(language.render(state))
            if recovered.mathematical_hash != state.mathematical_hash:
                roundtrip_failures.append(f"{item.task_id}: mathematical hash not recovered")
                continue
            compiled = compiler.compile(state, options=tuple(item.options))
            compiler.validate(compiled, state, options=tuple(item.options))
        except Exception as error:  # noqa: BLE001 - any failure here is elimination
            roundtrip_failures.append(f"{item.task_id}: {type(error).__name__}: {error}")
    if roundtrip_failures:
        failures.append(FailureMode.TRUTH_ALTERED.value)
        outcomes.append(
            GateOutcome(
                name="semantic_roundtrip",
                status=GateStatus.FAIL,
                detail=roundtrip_failures[0],
                evidence={"checked": len(items), "failures": len(roundtrip_failures)},
            )
        )
        # A candidate that cannot reproduce truth is not asked anything else.
        return GateReport(tuple(outcomes), tuple(failures), inert=False, inert_evidence="")
    outcomes.append(
        GateOutcome(
            name="semantic_roundtrip",
            status=GateStatus.PASS,
            detail="every state recovers its canonical mathematical hash",
            evidence={"checked": len(items), "failures": 0},
        )
    )

    parent_prompts = _prompt_or_none(parent, items)
    child_prompts = _prompt_or_none(child, items)
    if isinstance(parent_prompts, str) or isinstance(child_prompts, str):
        detail = parent_prompts if isinstance(parent_prompts, str) else child_prompts
        failures.append(FailureMode.RENDER_FAILURE.value)
        outcomes.append(
            GateOutcome(name="mutation_effective", status=GateStatus.FAIL, detail=str(detail))
        )
        return GateReport(tuple(outcomes), tuple(failures), inert=False, inert_evidence="")

    differing = sum(1 for a, b in zip(parent_prompts, child_prompts, strict=True) if a != b)
    inert = differing == 0
    clusters = len({item.family_id for item in items})
    inert_evidence = (
        f"{differing}/{len(items)} rendered prompts differ from the parent "
        f"across {clusters} families"
    )
    outcomes.append(
        GateOutcome(
            name="mutation_effective",
            status=GateStatus.FAIL if inert else GateStatus.PASS,
            detail=(
                "mutation is byte-inert on this pool: the gene it changed does not reach the "
                "rendered bytes of this arena's states"
                if inert
                else inert_evidence
            ),
            evidence={"items": len(items), "differing_prompts": differing},
        )
    )
    if inert:
        failures.append(FailureMode.MUTATION_INERT.value)
        return GateReport(
            tuple(outcomes), tuple(failures), inert=True, inert_evidence=inert_evidence
        )

    parity_failure: str | None = None
    for item in items:
        try:
            assert_arena_parity(item, [model_view(parent), model_view(child)])
        except ParityViolation as error:
            parity_failure = f"{item.task_id}: {error}"
            break
    if parity_failure is not None:
        failures.append(FailureMode.PARITY_VIOLATION.value)
        outcomes.append(
            GateOutcome(name="arena_parity", status=GateStatus.FAIL, detail=parity_failure)
        )
    else:
        outcomes.append(
            GateOutcome(
                name="arena_parity",
                status=GateStatus.PASS,
                detail="same information, same options, same envelope, distinct bytes",
                evidence={"items": len(items)},
            )
        )
    return GateReport(tuple(outcomes), tuple(failures), inert=False, inert_evidence=inert_evidence)


def leakage_gate(
    genome: LanguageGenome,
    items: Sequence[MaterialisedItem],
    *,
    seed: int,
    permutations: int = 500,
    bootstrap_samples: int = 300,
) -> GateOutcome:
    """The rendered-prompt adversary on the exact bytes a Solver would receive.

    Non-compensatory, and zero model calls.  Elimination requires *demonstrated* leakage: the
    Bonferroni Clopper-Pearson **lower** bound of the best of 64 rules must exceed chance.  When
    the declared V0 upper-bound target (0.60 at n_EVAL=800) is not attained, the outcome is
    ``UNDERPOWERED`` - recorded, never silently read as a pass, and never used to eliminate,
    because eliminating on an unattainable upper bound is how a gate voids clean languages.
    """

    examples = [
        Example(
            prompt=prompt,
            n_options=len(item.options),
            correct_index=item.correct_index,
            family_id=item.family_id,
            arm_id=genome.candidate_id,
            task_id=item.task_id,
        )
        for item, prompt in zip(items, rendered_prompts(genome, items), strict=True)
    ]
    report = evaluate_rules(
        examples,
        seed=seed,
        permutations=permutations,
        bootstrap_samples=bootstrap_samples,
    )
    chance = 1.0 / len(canonical_answer_ids(examples[0].n_options))
    evidence = {
        "version": ADVERSARY_FAMILY_VERSION,
        "n_examples": report.n_examples,
        "n_families": report.n_families,
        "n_rules": report.n_rules,
        "best_rule": report.best_rule,
        "best_accuracy": report.best_accuracy,
        "bonferroni_lower": report.bonferroni_lower,
        "bonferroni_upper": report.bonferroni_upper,
        "null_expected_max": report.null_expected_max,
        "null_p_value": report.null_p_value,
        "chance": chance,
        "declared_target_upper_bound": LEAKAGE_UPPER_BOUND_TARGET,
        "declared_target_n_eval": LEAKAGE_TARGET_N_EVAL,
        "model_calls": 0,
    }
    if report.bonferroni_lower > chance + 1e-12:
        return GateOutcome(
            name="answer_leakage",
            status=GateStatus.FAIL,
            detail=(
                f"rule {report.bonferroni_lower:.3f} > chance {chance:.3f} at the Bonferroni "
                f"Clopper-Pearson lower bound; best rule {report.best_rule}"
            ),
            evidence=evidence,
        )
    if report.bonferroni_upper >= LEAKAGE_UPPER_BOUND_TARGET:
        return GateOutcome(
            name="answer_leakage",
            status=GateStatus.UNDERPOWERED,
            detail=(
                f"no leakage demonstrated, but the declared {LEAKAGE_UPPER_BOUND_TARGET} upper "
                f"bound is unattainable at n={report.n_examples} (observed upper "
                f"{report.bonferroni_upper:.3f}); target n_EVAL is {LEAKAGE_TARGET_N_EVAL}"
            ),
            evidence=evidence,
        )
    return GateOutcome(
        name="answer_leakage",
        status=GateStatus.PASS,
        detail=f"best adversary upper bound {report.bonferroni_upper:.3f} clears the target",
        evidence=evidence,
    )


# ----------------------------------------------------------------------------------- fitness


#: The two dimensions this loop's evaluator can address at all.  Under a stub they are the two
#: that become ``NOT_REPRESENTABLE`` rather than ``NOT_MEASURED``: a number *was* computed for
#: each, and neither is admissible as fitness.
ADDRESSED_DIMENSIONS: tuple[str, ...] = ("J_solve", "J_cost")


def build_diagnostics(outcome: EvaluationOutcome, *, basis: EvaluationMode) -> DiagnosticReadings:
    """The stub's numbers, under names that are not fitness dimensions (RT-16).

    ``stub_choice_agreement`` is deliberately not called ``J_solve`` and deliberately carries no
    interval: it is the rate at which ``sha256(prompt) mod n_options`` happened to land on the
    key, which is chance up to the hash's arbitrary partition of prompt space.  It exists so the
    loop's Pareto ranking, frontier selection and archive have something to run on, and every key
    that reaches an archive is prefixed with the basis that produced it.
    """

    rows = outcome.rows
    return DiagnosticReadings(
        basis=EvaluationMode(basis).value,
        readings={
            "stub_choice_agreement": sum(1 for row in rows if row.correct) / len(rows),
            "rendered_prompt_bytes_mean": sum(row.prompt_bytes for row in rows) / len(rows),
            "n_items": float(len(rows)),
            "n_clusters": float(len({row.family_id for row in rows})),
        },
        note=(
            "NOT FITNESS. Produced by a deterministic stub with no reasoning ability; a "
            "difference between two languages here is noise. Recorded so the loop's ranking and "
            "archive can be exercised without a model call, and named so it cannot be read as a "
            "J_* result."
        ),
    )


def build_fitness_vector(
    outcome: EvaluationOutcome,
    *,
    evaluation_mode: EvaluationMode,
    actor: EvidenceActor,
) -> FitnessVector:
    """``J_solve`` and ``J_cost`` measured; the other five present and ``NOT_MEASURED``.

    No scalarisation, no weights.  The five unmeasured dimensions are named, not omitted: an
    absent dimension reads as coverage that was never attempted, and this loop must not be able
    to look more complete than it is.

    Under ``EXECUTABILITY_STUB``, or under the ``REFERENCE`` actor, **no** dimension carries a
    number: the two the evaluator addressed become ``NOT_REPRESENTABLE`` and their readings go to
    :func:`build_diagnostics`.  This is not a policy the caller can decline - constructing the
    vector with values under either condition raises (RT-16, RT-04).
    """

    if not (evaluation_mode.permits_scientific_fitness and actor.permits_capability_claim):
        return FitnessVector.inadmissible(
            evaluation_mode=evaluation_mode,
            actor=actor,
            computed=ADDRESSED_DIMENSIONS,
            note=(
                f"a reading was computed under evaluation_mode={evaluation_mode.value}, "
                f"actor={actor.value} and is inadmissible as fitness; see the record's "
                "diagnostics block"
            ),
        )
    correct = sum(1 for row in outcome.rows if row.correct)
    solve = proportion_metric("J_solve", correct, len(outcome.rows))
    cost = mean_metric(
        "J_cost",
        [float(row.prompt_bytes) for row in outcome.rows],
        direction=Direction.MINIMIZE,
        unit="utf8-bytes",
    )
    measured = [
        FitnessDimension(
            name="J_solve",
            status=DimensionStatus.MEASURED,
            direction=Direction.MAXIMIZE,
            value=solve.value,
            lower=solve.interval.lower,
            upper=solve.interval.upper,
            confidence=solve.interval.confidence,
            unit_of_analysis="item",
            estimator="wilson",
            n=len(outcome.rows),
            n_clusters=len({row.family_id for row in outcome.rows}),
            reportable=True,
            note=(
                "items are twins within families; an unclustered Wilson interval is "
                "anti-conservative here and is reported as a diagnostic, not a claim"
            ),
        ),
        FitnessDimension(
            name="J_cost",
            status=DimensionStatus.MEASURED,
            direction=Direction.MINIMIZE,
            value=cost.value,
            lower=cost.interval.lower,
            upper=cost.interval.upper,
            confidence=cost.interval.confidence,
            unit_of_analysis="item",
            estimator="mean_normal",
            n=len(outcome.rows),
            n_clusters=len({row.family_id for row in outcome.rows}),
            reportable=True,
            note="bytes, not tokens: no tokenizer is bound in the offline path",
        ),
    ]
    return FitnessVector.build(
        measured,
        note="requires a verified trajectory world (docs/HAMILTONIAN_CHESS_META_GOAL.md s6.1)",
        evaluation_mode=evaluation_mode,
        actor=actor,
    )


def observations_from_rows(
    outcome: EvaluationOutcome,
    *,
    arena_id: str,
    opponent_id: str | None,
    verified: bool,
) -> tuple[MatchObservation, ...]:
    """The ~30-line adapter the remap names: evaluation rows -> ``MatchObservation`` rows.

    ``arena/league/registry.py`` has carried a complete, tested data model with zero rows ever
    written.  This is what writes them.

    ``verified`` is required rather than defaulted (RT-16).  ``LeagueRegistry._recompute`` builds
    its multi-axis ratings from exactly the observations that carry it, so a stub row marked
    ``verified=True`` is how a chance-level hash acquires a confidence interval in the durable
    archive.  A stub row is recorded and **not** counted.
    """

    return tuple(
        MatchObservation(
            candidate_id=outcome.candidate_id,
            task_id=row.task_id,
            domain=arena_id,
            mechanisms=(MECHANISM, f"level:{row.level}", f"variant:{row.variant}"),
            score=1.0 if row.correct else 0.0,
            opponent_id=opponent_id,
            verified=verified,
        )
        for row in outcome.rows
    )


PARETO_OBJECTIVES: tuple[Objective, ...] = (
    Objective("J_solve", Direction.MAXIMIZE),
    Objective("J_cost", Direction.MINIMIZE),
)

#: What the archive ranks on when the evaluator is a stub (RT-16).  Every name carries the basis
#: that produced it, so no ranking anywhere - front, frontier, ``objective_metrics`` in
#: ``league-registry.json`` - can be read as a ranking on ``J_solve``.
STUB_DIAGNOSTIC_OBJECTIVES: tuple[Objective, ...] = (
    Objective("EXECUTABILITY_STUB::stub_choice_agreement", Direction.MAXIMIZE),
    Objective("EXECUTABILITY_STUB::rendered_prompt_bytes_mean", Direction.MINIMIZE),
)


def objectives_for(mode: EvaluationMode) -> tuple[Objective, ...]:
    """The objectives a run of this mode may rank on.

    Under ``EXECUTABILITY_STUB`` there are no ``J_*`` values in existence to rank on, so the
    archive ranks on the explicitly-named diagnostics instead; the loop's selection machinery is
    exercised, and the ordering it produces claims nothing.
    """

    return PARETO_OBJECTIVES if mode.permits_scientific_fitness else STUB_DIAGNOSTIC_OBJECTIVES


def archive_objectives(record: FitnessRecord) -> dict[str, float]:
    """What may be written into the league archive for one record (RT-16).

    Fails closed: a ``J_*`` key under a non-scientific mode raises rather than being dropped,
    because silently discarding it would leave the archive quietly incomplete instead of loudly
    wrong.
    """

    if record.fitness_vector.admissible_as_fitness:
        return record.fitness_vector.measured()
    if record.diagnostics is None:
        return {}
    metrics = record.diagnostics.archive_metrics()
    # Both spellings: the archive key *and* the raw reading name it was built from, so a
    # diagnostics block that reached the record without passing its own constructor - a
    # hand-edited artefact, a forged object - is still caught here.
    names = set(metrics) | set(record.diagnostics.readings)
    scientific = sorted(names & set(DIMENSION_DIRECTIONS))
    if scientific:
        raise StubFitnessNotRepresentable(
            f"refusing to rank {record.child_genome_id} on {scientific} under "
            f"evaluation_mode={record.evaluation_mode.value}, actor={record.actor.value}"
        )
    return metrics


# -------------------------------------------------------------------------------- selection


def choose_parent(
    population: Sequence[LanguageGenome],
    *,
    strategy: ParentSelection,
    generation: int,
    registry: LeagueRegistry,
    rng: random.Random,
    objectives: Sequence[Objective],
) -> LanguageGenome:
    """Deterministic given (population, strategy, generation, archive, seeded rng, objectives)."""

    if not population:
        raise ValueError("the population is empty")
    if strategy is ParentSelection.ROUND_ROBIN:
        return population[generation % len(population)]
    points = [
        ParetoPoint(genome.candidate_id, registry.candidates[genome.candidate_id].objective_metrics)
        for genome in population
        if genome.candidate_id in registry.candidates
        and {objective.name for objective in objectives}
        <= registry.candidates[genome.candidate_id].objective_metrics.keys()
    ]
    if not points:
        return population[generation % len(population)]
    front = select_frontier_diverse(points, objectives, max(1, len(points) // 2))
    by_id = {genome.candidate_id: genome for genome in population}
    return by_id[front[rng.randrange(len(front))]]


def live_gene_families(
    genome: LanguageGenome, item: MaterialisedItem
) -> tuple[frozenset[GeneFamily], frozenset[GeneFamily]]:
    """(live, inert) gene families, **measured** on one rendered prompt of this arena.

    Which families reach the bytes is a property of the arena's states, not of the genome
    table: ``binders`` is live where a state has bindings and inert where it has none.  The
    result is used as a mutation *preference* only; inertness of the actual child is decided by
    the gate against the whole pool.
    """

    from arena.genome.genes import GENE_ENUMS

    baseline = build_prompt(model_view(genome), item)
    live: set[GeneFamily] = set()
    inert: set[GeneFamily] = set()
    for family in GeneFamily:
        changed = False
        for value in GENE_ENUMS[family]:
            if value.value == genome.gene(family):
                continue
            try:
                probe = genome.with_gene_values(
                    {family: value.value},
                    candidate_id="PROBE",
                    parent_ids=(genome.candidate_id,),
                )
                if build_prompt(model_view(probe), item) != baseline:
                    changed = True
                    break
            except Exception:  # noqa: BLE001, S112 - an unrenderable probe is not evidence
                continue
        (live if changed else inert).add(family)
    return frozenset(live), frozenset(inert)


# ------------------------------------------------------------------------------- generation


@dataclass(frozen=True, slots=True)
class CandidateResult:
    parent_id: str
    child_id: str
    outcome: Outcome
    record: FitnessRecord
    gate: GateReport
    evaluation: EvaluationOutcome | None

    def summary(self) -> dict[str, Any]:
        return {
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "outcome": self.outcome.value,
            "inert": self.gate.inert,
            "failure_modes": list(self.record.failure_modes),
            "gates": {item.name: item.status.value for item in self.record.semantic_gate_results},
            # Empty under a stub, and empty for a reason the next two keys name (RT-16, RT-04).
            "fitness": self.record.fitness_vector.measured(),
            "evaluation_mode": self.record.evaluation_mode.value,
            "actor": self.record.actor.value,
            "fitness_admissible": self.record.fitness_vector.admissible_as_fitness,
            "diagnostics": (
                {} if self.record.diagnostics is None else self.record.diagnostics.archive_metrics()
            ),
            "content_hash": self.record.content_hash,
        }


@dataclass(frozen=True, slots=True)
class GenerationResult:
    generation: int
    parent_id: str
    candidates: tuple[CandidateResult, ...]
    fronts: tuple[tuple[str, ...], ...]
    population_after: tuple[str, ...]
    children_requested: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "parent_id": self.parent_id,
            "children_requested": self.children_requested,
            "children_produced": len(self.candidates),
            "candidates": [item.summary() for item in self.candidates],
            "fronts": [list(front) for front in self.fronts],
            "population_after": list(self.population_after),
        }


@dataclass(frozen=True, slots=True)
class LoopConfig:
    seed: int = 20260908
    generations: int = 1
    population: int = 4
    children_per_generation: int = 1
    strategy: ParentSelection = ParentSelection.ROUND_ROBIN
    arena: ArenaSpec = field(default_factory=ArenaSpec)
    adversary_permutations: int = 500
    adversary_bootstrap: int = 300
    #: Which draw of this experiment the run is taking (RT-13).  The default is the primary draw;
    #: a replicate must be constructed with an authoriser, a reason and a plan, and it changes the
    #: ``run_id`` as well as every ``record_id``, so a second draw is visible in the artefact tree
    #: rather than hidden inside one.
    replicate: ReplicateAuthorisation = field(default_factory=ReplicateAuthorisation.primary)

    def __post_init__(self) -> None:
        if not 1 <= self.population <= len(SEED_GENOMES):
            raise ValueError(f"population must lie in [1, {len(SEED_GENOMES)}]")
        if self.generations < 1 or self.children_per_generation < 1:
            raise ValueError("generations and children_per_generation must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop_version": LOOP_VERSION,
            "seed": self.seed,
            "generations": self.generations,
            "population": self.population,
            "children_per_generation": self.children_per_generation,
            "strategy": self.strategy.value,
            "arena": self.arena.to_dict(),
            "adversary_permutations": self.adversary_permutations,
            "adversary_bootstrap": self.adversary_bootstrap,
            "replicate": self.replicate.to_dict(),
        }

    @property
    def run_id(self) -> str:
        """Deterministic: the whole generation is a pure function of (seed, population, budget).

        Two runs with the same configuration therefore write into the same ``run_id`` and, if
        pointed at the same store, the second is refused as ``SAME_CONDITION_REUSE`` rather than
        appended twice.
        """

        return f"run-{stable_hash(self.to_dict())[:20]}"


def seed_population(count: int) -> tuple[LanguageGenome, ...]:
    return SEED_GENOMES[:count]


class EvolutionLoop:
    """The thin loop.  Everything expensive or clever lives behind an existing module."""

    def __init__(
        self,
        *,
        store: ArtifactStore,
        config: LoopConfig | None = None,
        evaluator: Evaluator | None = None,
    ) -> None:
        self.config = config or LoopConfig()
        self.store = store
        self.evaluator: Evaluator = evaluator or StubLadderEvaluator()
        self.records = EvolutionRecordStore(store, self.config.run_id)
        self.registry = LeagueRegistry(seed_baselines=False)
        self.solve_items = self.config.arena.solve_items()
        self.adversary_items = self.config.arena.adversary_items()
        self.genomes: dict[str, LanguageGenome] = {}
        self.population: list[LanguageGenome] = list(seed_population(self.config.population))
        for genome in self.population:
            self.genomes[genome.candidate_id] = genome
            self.registry.register(genome.candidate_id, parent_ids=genome.parent_ids)

    # ------------------------------------------------------------------ helpers

    def _context(self) -> EvaluationContext:
        adversary_hash = stable_hash(sorted(item.task_id for item in self.adversary_items))
        return EvaluationContext(
            arena_id=self.config.arena.arena_id,
            environment_version=ENVIRONMENT_VERSION,
            mechanism=MECHANISM,
            task_ids=tuple(item.task_id for item in self.solve_items),
            fidelity_level=self.evaluator.fidelity_level,
            pool_id=self.config.arena.solve_pool.value,
            pool_role="SELECTION",
            horizon_bucket="H1",
            n_clusters=len({item.family_id for item in self.solve_items}),
            # The leakage gate runs on a different Pool, whose name enters every family salt,
            # so the two pools are family-disjoint by construction.  Recording the other set's
            # hash is what makes that checkable after the fact rather than merely asserted.
            pool_disjoint_from=(adversary_hash,),
        )

    def _provenance(self, extra: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "loop_version": LOOP_VERSION,
            "harness_version": HARNESS_VERSION,
            "evaluator_id": self.evaluator.evaluator_id,
            "arena": self.config.arena.to_dict(),
            "config": self.config.to_dict(),
            "confirmatory": False,
            "scientific_status": (
                "HAMILTONIAN_CHESS_V0 executability run. The evaluator is a deterministic stub "
                "with no reasoning ability and the arena has horizon 1; no number here is a "
                "scientific result or an evidence-ladder claim."
            ),
            **dict(extra),
        }

    def _descriptor(
        self, proposal: MutationProposal, *, inert: bool | None, evidence: str
    ) -> MutationDescriptor:
        return MutationDescriptor(
            operator=proposal.operator.value,
            proposal_id=proposal.proposal_id,
            mutation_hash=proposal.proposal_hash,
            parameters={
                "impact_class": proposal.impact_class.value,
                "soundness_risk": proposal.soundness_risk.value,
                "required_evaluation_tier": proposal.required_evaluation_tier.value,
                "scope": proposal.scope,
            },
            gene_changes=tuple(
                GeneChangeRecord(change.gene.value, change.from_value, change.to_value)
                for change in proposal.changes
            ),
            evaluation_tier=proposal.required_evaluation_tier.value,
            soundness_risk=proposal.soundness_risk.value,
            # Every gene in the present fourteen-family genome is surface or structural
            # serialisation: Layer D.  There are no Layer B/C genes to reach yet
            # (artifacts/reports/genome-content-audit.json: 0 content-bearing genes).
            layer="D",
            decision="pending",
            inert=inert,
            inert_evidence=evidence,
        )

    def _propose(
        self, parent: LanguageGenome, *, generation: int, index: int
    ) -> tuple[ArchitectProposal, ...]:
        """Architect proposals, live-gene-first.  Deterministic given (parent, seed, position)."""

        proposals = Architect().propose(
            parent, count=24, seed=self.config.seed + 1000 * generation + index
        )
        live, _ = live_gene_families(parent, self.solve_items[0])
        return tuple(
            sorted(
                proposals,
                key=lambda item: (
                    0 if set(item.mutation.proposal.changed_genes) & live else 1,
                    item.genome.candidate_id,
                ),
            )
        )

    # ------------------------------------------------------------------ one candidate

    def _score(
        self,
        parent: LanguageGenome,
        proposal: ArchitectProposal,
        *,
        generation: int,
    ) -> CandidateResult:
        child: LanguageGenome = proposal.genome
        self.genomes[child.candidate_id] = child
        started = time.perf_counter()
        mode = self.evaluator.evaluation_mode
        actor = self.evaluator.actor
        gate = semantic_gate(parent=parent, child=child, items=self.solve_items)
        gates: list[GateOutcome] = list(gate.outcomes)
        failures: list[str] = list(gate.failure_modes)
        evaluation: EvaluationOutcome | None = None
        diagnostics: DiagnosticReadings | None = None
        outcome = Outcome.KILLED_BY_SEMANTIC_GATE
        vector = FitnessVector.build(
            [],
            note="candidate was killed by the semantic gate and was never scored",
            evaluation_mode=mode,
            actor=actor,
        )
        uncertainty: dict[str, Any] = {}
        calls = tokens = 0

        if gate.passed:
            leak = leakage_gate(
                child,
                self.adversary_items,
                seed=self.config.seed,
                permutations=self.config.adversary_permutations,
                bootstrap_samples=self.config.adversary_bootstrap,
            )
            gates.append(leak)
            if leak.eliminated:
                failures.append(FailureMode.ANSWER_LEAKAGE.value)
            else:
                evaluation = self.evaluator.evaluate(
                    genome=child,
                    language=language_for_genome(child),
                    items=self.solve_items,
                )
                vector = build_fitness_vector(evaluation, evaluation_mode=mode, actor=actor)
                calls, tokens = evaluation.calls, evaluation.tokens
                outcome = Outcome.SCORED
                if vector.admissible_as_fitness:
                    uncertainty = {
                        "J_solve": {
                            "interval": [vector["J_solve"].lower, vector["J_solve"].upper],
                            "clustered": False,
                            "cluster_unit_available": "family_id",
                            "note": "unclustered; twins within a family are not independent trials",
                        },
                        "J_cost": {
                            "interval": [vector["J_cost"].lower, vector["J_cost"].upper],
                            "clustered": False,
                        },
                        "power": "NOT_COMPUTED_AT_THIS_N",
                        "confirmatory": False,
                    }
                else:
                    # RT-16: there is no interval to report, because there is no reading to be
                    # uncertain about.  Saying so is not the same as leaving the block empty.
                    diagnostics = build_diagnostics(evaluation, basis=mode)
                    uncertainty = {
                        "power": "NOT_APPLICABLE_NO_ADMISSIBLE_READING",
                        "confirmatory": False,
                        "note": (
                            f"evaluation_mode={mode.value}, actor={actor.value}: no fitness "
                            "dimension carries a value, so no interval is reported. The numbers "
                            "the run produced are in the diagnostics block and are not fitness."
                        ),
                    }

        status = RecordStatus.COMPLETE if outcome is Outcome.SCORED else RecordStatus.REFUSED
        record = FitnessRecord(
            run_id=self.config.run_id,
            generation=generation,
            harness_version=HARNESS_VERSION,
            evaluation_mode=mode,
            actor=actor,
            parent_genome_id=parent.candidate_id,
            parent_genome_hash=parent.genome_hash,
            child_genome_id=child.candidate_id,
            child_genome_hash=child.genome_hash,
            mutation=self._descriptor(
                proposal.mutation.proposal, inert=gate.inert, evidence=gate.inert_evidence
            ),
            evaluation_context=self._context(),
            model=self.evaluator.model,
            condition=self.evaluator.condition,
            # V0 takes one draw per experiment.  A second would need an authorisation naming who
            # asked for it and why (RT-13); re-proposing the same edge does not qualify.
            replicate=self.config.replicate,
            dataset=self.config.arena.dataset(),
            budget=Budget(
                calls=calls,
                tokens=tokens,
                wall_clock_seconds=time.perf_counter() - started,
                fresh_calls=calls,
                verifier_calls=0,
            ),
            fitness_vector=vector,
            diagnostics=diagnostics,
            uncertainty=uncertainty,
            failure_modes=tuple(failures),
            semantic_gate_results=tuple(gates),
            provenance=self._provenance({"parent_candidate_hash": parent.candidate_hash}),
            created_at=datetime.now(UTC).isoformat(timespec="microseconds"),
            status=status,
            outcome=outcome.value,
            # A refusal is a record, and it names what refused it rather than leaving a gap.
            void_code=None if status is RecordStatus.COMPLETE else failures[0],
        )
        self.records.append(
            record,
            rows=[row.to_dict() for row in evaluation.rows] if evaluation is not None else (),
        )
        return CandidateResult(
            parent_id=parent.candidate_id,
            child_id=child.candidate_id,
            outcome=outcome,
            record=record,
            gate=gate,
            evaluation=evaluation,
        )

    # ------------------------------------------------------------------ one generation

    @property
    def objectives(self) -> tuple[Objective, ...]:
        """What this run's archive may rank on - never ``J_*`` under a stub (RT-16)."""

        return objectives_for(self.evaluator.evaluation_mode)

    def run_generation(self, generation: int) -> GenerationResult:
        rng = random.Random(f"{self.config.seed}|{generation}")
        objectives = self.objectives
        parent = choose_parent(
            self.population,
            strategy=self.config.strategy,
            generation=generation,
            registry=self.registry,
            rng=rng,
            objectives=objectives,
        )
        results: list[CandidateResult] = []
        used: set[str] = set(self.genomes)
        proposals = self._propose(parent, generation=generation, index=0)
        for proposal in proposals:
            if len(results) == self.config.children_per_generation:
                break
            if proposal.genome.candidate_id in used:
                continue
            used.add(proposal.genome.candidate_id)
            results.append(self._score(parent, proposal, generation=generation))

        scored = [item for item in results if item.outcome is Outcome.SCORED]
        for item in scored:
            if item.evaluation is None:  # pragma: no cover - guarded by Outcome.SCORED
                raise RuntimeError(f"{item.child_id} is SCORED without an evaluation")
            self.registry.register(item.child_id, parent_ids=(item.parent_id,))
            self.registry.record_match(
                LeagueMatch(
                    match_id=(
                        "match:"
                        + stable_hash(
                            {
                                "run": self.config.run_id,
                                "generation": generation,
                                "candidate": item.child_id,
                                "context": self._context().identity_hash,
                            }
                        )[:20]
                    ),
                    observations=observations_from_rows(
                        item.evaluation,
                        arena_id=self.config.arena.arena_id,
                        opponent_id=item.parent_id,
                        verified=self._observations_are_verified(),
                    ),
                    suite_id=self.config.arena.arena_id,
                )
            )
            self.registry.set_objectives(item.child_id, archive_objectives(item.record))

        self._score_population_baselines(generation)
        ranked = [
            candidate_id
            for candidate_id in self.registry.candidates
            if {objective.name for objective in objectives}
            <= self.registry.candidates[candidate_id].objective_metrics.keys()
        ]
        fronts = rank_registry(self.registry, objectives, candidate_ids=ranked)
        points = [
            ParetoPoint(cid, self.registry.candidates[cid].objective_metrics) for cid in ranked
        ]
        survivors = select_frontier_diverse(points, objectives, self.config.population)
        self.population = [self.genomes[cid] for cid in survivors if cid in self.genomes] or list(
            self.population
        )
        return GenerationResult(
            generation=generation,
            parent_id=parent.candidate_id,
            candidates=tuple(results),
            fronts=fronts,
            population_after=tuple(genome.candidate_id for genome in self.population),
            children_requested=self.config.children_per_generation,
        )

    def _observations_are_verified(self) -> bool:
        """Whether league rows from this evaluator may feed the archive's ratings (RT-16).

        ``LeagueRegistry._recompute`` skips unverified observations, so a stub's rows are stored
        - a refusal to store them would hide that the loop ran - and excluded from every rating.
        Without this, ``league-registry.json`` reports a normal-approximation interval over rows
        produced by ``sha256(prompt) mod n_options``.
        """

        return self.evaluator.evaluation_mode.permits_scientific_fitness

    def _score_population_baselines(self, generation: int) -> None:
        """Every seed in the population is measured on the same rows, once.

        Without this the archive would rank children against nothing, and the front would be
        whichever child happened to be evaluated first.
        """

        for genome in list(self.population):
            record = self.registry.candidates.get(genome.candidate_id)
            if record is not None and record.objective_metrics:
                continue
            outcome = self.evaluator.evaluate(
                genome=genome,
                language=language_for_genome(genome),
                items=self.solve_items,
            )
            self.registry.record_match(
                LeagueMatch(
                    match_id=(
                        "match:"
                        + stable_hash(
                            {
                                "run": self.config.run_id,
                                "generation": generation,
                                "baseline": genome.candidate_id,
                                "context": self._context().identity_hash,
                            }
                        )[:20]
                    ),
                    observations=observations_from_rows(
                        outcome,
                        arena_id=self.config.arena.arena_id,
                        opponent_id=None,
                        verified=self._observations_are_verified(),
                    ),
                    suite_id=self.config.arena.arena_id,
                )
            )
            mode = self.evaluator.evaluation_mode
            actor = self.evaluator.actor
            vector = build_fitness_vector(outcome, evaluation_mode=mode, actor=actor)
            self.registry.set_objectives(
                genome.candidate_id,
                vector.measured()
                if vector.admissible_as_fitness
                else build_diagnostics(outcome, basis=mode).archive_metrics(),
            )

    # ------------------------------------------------------------------ whole run

    def run(self) -> dict[str, Any]:
        generations = [self.run_generation(index) for index in range(self.config.generations)]
        league_path = self.store.root / "evolution" / self.config.run_id / "league-registry.json"
        self.registry.save(league_path)
        summary = {
            "run_id": self.config.run_id,
            "loop_version": LOOP_VERSION,
            "config": self.config.to_dict(),
            "model": self.evaluator.model.to_dict(),
            "evaluation_mode": self.evaluator.evaluation_mode.value,
            "actor": self.evaluator.actor.value,
            "condition": self.evaluator.condition.to_dict(),
            "replicate": self.config.replicate.to_dict(),
            "ranked_on": [objective.name for objective in self.objectives],
            "observations_verified": self._observations_are_verified(),
            "model_calls": 0,
            "generations": [item.summary() for item in generations],
            "records": self.records.summary(),
            "league_registry": str(league_path.relative_to(self.store.root)),
            "archive_observations": len(self.registry.observations),
            "final_front": list(generations[-1].fronts[0]) if generations[-1].fronts else [],
            "schema_version": RECORD_SCHEMA_VERSION,
            "schema_divergences": list(SCHEMA_DIVERGENCES),
            "scientific_status": "EXECUTABILITY_ONLY_NOT_A_RESULT",
        }
        self.store.write_json(f"evolution/{self.config.run_id}/summary.json", summary)
        return summary


# --------------------------------------------------------------------------------------- CLI


def compact_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    """What the CLI prints.  The full record, with every divergence, is on disk."""

    return {
        "run_id": summary["run_id"],
        "loop_version": summary["loop_version"],
        "scientific_status": summary["scientific_status"],
        "evaluation_mode": summary["evaluation_mode"],
        "actor": summary["actor"],
        "ranked_on": summary["ranked_on"],
        "model": summary["model"]["name"],
        "model_calls": summary["model_calls"],
        "generations": [
            {
                "generation": item["generation"],
                "parent_id": item["parent_id"],
                "candidates": [
                    {
                        "child_id": child["child_id"],
                        "outcome": child["outcome"],
                        "inert": child["inert"],
                        "gates": child["gates"],
                        "failure_modes": child["failure_modes"],
                        "fitness": child["fitness"],
                        "fitness_admissible": child["fitness_admissible"],
                        "diagnostics": child["diagnostics"],
                    }
                    for child in item["candidates"]
                ],
                "front": item["fronts"][0] if item["fronts"] else [],
                "population_after": item["population_after"],
            }
            for item in summary["generations"]
        ],
        "records": summary["records"]["records"],
        "record_manifest_hash": summary["records"]["manifest_hash"],
        "archive_observations": summary["archive_observations"],
        "final_front": summary["final_front"],
        "artifacts": summary["records"]["directory"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arena.evolution.loop",
        description="Run the offline outer evolutionary loop (V0: executability, not science).",
    )
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--population", type=int, default=4)
    parser.add_argument("--children", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument(
        "--strategy",
        choices=[item.value for item in ParentSelection],
        default=ParentSelection.ROUND_ROBIN.value,
    )
    parser.add_argument("--stratum", default="P05")
    parser.add_argument("--solve-families", type=int, default=8)
    parser.add_argument("--adversary-families", type=int, default=40)
    parser.add_argument("--out", default="artifacts", help="artifact root for this run")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = LoopConfig(
        seed=args.seed,
        generations=args.generations,
        population=args.population,
        children_per_generation=args.children,
        strategy=ParentSelection(args.strategy),
        arena=ArenaSpec(
            stratum=args.stratum,
            solve_families=args.solve_families,
            adversary_families=args.adversary_families,
        ),
    )
    loop = EvolutionLoop(store=ArtifactStore(Path(args.out)), config=config)
    summary = loop.run()
    print(json.dumps(compact_summary(summary), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())


__all__ = [
    "ADDRESSED_DIMENSIONS",
    "LOOP_VERSION",
    "PARETO_OBJECTIVES",
    "STUB_DIAGNOSTIC_OBJECTIVES",
    "ArenaSpec",
    "CandidateResult",
    "EvaluationOutcome",
    "EvaluationRow",
    "Evaluator",
    "EvolutionLoop",
    "FailureMode",
    "GateReport",
    "GenerationResult",
    "LoopConfig",
    "Outcome",
    "ParentSelection",
    "StubLadderEvaluator",
    "StubSolver",
    "archive_objectives",
    "build_diagnostics",
    "build_fitness_vector",
    "choose_parent",
    "leakage_gate",
    "objectives_for",
    "live_gene_families",
    "main",
    "model_view",
    "observations_from_rows",
    "rendered_prompts",
    "seed_population",
    "semantic_gate",
]
