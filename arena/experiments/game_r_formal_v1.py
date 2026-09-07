"""Game-R founder-parity tournament harness for the formal task families (v1).

This module is a **harness**, not an experiment.  It builds prompts, enforces parity,
addresses a cache, spends a budget and scores rows.  It never chooses a scientific
threshold that is derivable, and it never runs itself: :func:`main` refuses to make a
model call unless the operator passes ``--live --confirm-model-calls`` explicitly.

Every guarantee below exists because a *specific* prior defect made a result unusable.
The comment on each is the defect it closes, so that removing the guarantee is visibly a
regression rather than a simplification.

V3 — input truncation.
    Token budgets are decided from an exact :class:`TokenCounter`, never from characters.
    The harness *refuses* an over-budget prompt (:data:`RowStatus.PROMPT_OVER_BUDGET`) so
    that truncation is unreachable rather than detected after the fact.  There is no
    chars-per-token constant anywhere in this file, and the run additionally cross-checks
    the counted token total against the solver's own reported count.

V4 — a 64-token cap ate the answer, and a character context guard voided rows
    representation-specifically (measured chars/token spans 2.74-7.43 across surfaces).
    The answer alphabet is grammar-constrained by :func:`response_schema`, and the answer
    identifiers are candidate-neutral, so the response syntax cannot become a second
    representation variable.

V5 — the frontier selector aimed at a declared constant 0.625 while the gate floor was
    ``gap_min + destroyed_control``= 0.70, because ``gap_min`` was raised 0.10 -> 0.20
    without moving the target.  Here the target is **derived** by
    :func:`derived_frontier_target` from the gate arithmetic, there is no frontier-target
    constant to drift, and the derivation is asserted in the test module.  Note honestly:
    the derived midpoint is *not* claimed to improve operating characteristics.  The
    measured trade-off (``docs/PHASE6_INTEGRATION_MAP.md`` section 8) is that a midpoint
    selector raises the false-pass rate against a genuinely-0.65 reader; what the
    derivation buys is the removal of a degree of freedom, not power.

Phase 6 — the artifact carried 61 ``cache_hit == true`` rows against an invalidation rule
    of "cache hits > 0", because the rule could not distinguish legitimate same-condition
    reuse from cross-condition contamination.  Here every row records both ``cache_hit``
    and :class:`CacheScope`; a hit is only ever served when the *entire*
    :func:`cache_identity` record matches byte for byte, so
    :data:`CacheScope.CROSS_CONDITION` is impossible by construction and is asserted
    against at run time.

Route B — five "representations" were hand-written codecs whose ``_encode_payload`` never
    read the genome, so gene changes did nothing.  :func:`assert_arena_parity` refuses to
    run unless the arms both **agree** on recovered content and **differ** in rendered
    bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    canonical_json,
    stable_hash,
)
from arena.environments.formal_structural import build_state
from arena.evaluation.landscape import mcnemar_exact, paired_comparison
from arena.experiments.fitness_v4 import (
    V4Probe,
    V4Slice,
    V4Variant,
    assert_game_r_genome,
    assert_information_parity,
)
from arena.experiments.game_r_mutant_audit import _expressions, prompt_information_inventory
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.storage.artifacts import ArtifactStore
from arena.training.evaluation import wilson_interval

HARNESS_VERSION = "arena-game-r-formal-harness-v1.0.0"
ENVELOPE_VERSION = "arena-game-r-formal-envelope-v1.0.0"
ANSWER_PROTOCOL_VERSION = "arena-game-r-canonical-answer-id-v1.0.0"


# --------------------------------------------------------------------------- exceptions


class HarnessRefusal(RuntimeError):
    """Base class for every fail-closed refusal.  A refusal is never a skipped row."""


class ParityViolation(HarnessRefusal):
    """Two arms disagree on content, or agree on bytes.  Either voids the comparison."""


class CacheIdentityViolation(HarnessRefusal):
    """A cache record was found whose identity is not the identity that was asked for."""


class BudgetExceeded(HarnessRefusal):
    """The run would have made more model calls than the operator authorised."""


class TokenAccountingRefusal(HarnessRefusal):
    """No exact token counter was supplied, so no prompt may be sent."""


# ------------------------------------------------------------------- gate arithmetic
#
# Nothing below declares an aim point.  ``destroyed_control_accuracy`` is a mathematical
# consequence of the negative control's construction, the floor is a consequence of the
# gap gate, and the target is the midpoint of the resulting window.  Change ``gap_min``
# and the target moves with it; that is the whole point.

#: Declared thresholds.  These are the *only* free numbers in the gate, and the frontier
#: target is deliberately absent: it is computed, never stated.
GATE_CONSTANTS: dict[str, Any] = {
    "explicit_positive_level": 0,
    "explicit_positive_min": 0.90,
    "gap_min": 0.20,
    "band_high": 0.85,
    "valid_response_rate_min": 0.95,
    "largest_answer_share_max": 0.75,
    "position_invariance_min": 0.50,
    "min_positives_for_gates": 24,
    "over_budget_rows_max": 0,
    "token_mismatch_rows_max": 0,
    "solver_error_rows_max": 0,
    "minimum_qualified_mechanisms": 2,
}


def destroyed_control_accuracy(n_options: int) -> float:
    """Accuracy of *any* deterministic solver on the destroyed negative control.

    The destroyed twins of a family are information-identical - same rendered bytes, same
    option order - and differ only in which index is correct.  A solver that is
    deterministic in its inputs therefore emits the same answer on all ``n_options`` twins
    and is correct on exactly one of them.  The value is ``1 / n_options`` exactly; it is
    not an estimate and costs no model call to obtain.  Phase 5 verified the binary case
    empirically (24/24 twin pairs byte-identical, 24 of 48 correct, i.e. 0.5000).

    Consequence: a gate of the form ``destroyed <= c`` for any ``c >= 1 / n_options`` is a
    dead gate and is not implemented here.  Use :func:`verify_destroyed_determinism` if
    destroyed rows are collected anyway and the determinism premise must be checked.
    """

    if n_options < 2:
        raise ValueError("a choice task needs at least two options")
    return 1.0 / float(n_options)


def effective_frontier_floor(*, gap_min: float, n_options: int) -> float:
    """The accuracy below which the gap gate cannot pass, derived from the gap gate.

    ``positive - destroyed >= gap_min`` with ``destroyed`` a constant reduces to
    ``positive >= gap_min + destroyed``.  V5 raised ``gap_min`` to 0.20 and left a
    hand-written target at 0.625, i.e. 0.075 below its own floor.
    """

    return gap_min + destroyed_control_accuracy(n_options)


def derived_frontier_target(*, gap_min: float, band_high: float, n_options: int) -> float:
    """Midpoint of the window the gate actually admits.  Never a declared constant."""

    floor = effective_frontier_floor(gap_min=gap_min, n_options=n_options)
    if floor >= band_high:
        raise ValueError(
            f"gate arithmetic admits no accuracy: floor {floor:.4f} >= ceiling {band_high:.4f}"
        )
    return (floor + band_high) / 2.0


def gate_arithmetic(
    *,
    n_options: int,
    gap_min: float = float(GATE_CONSTANTS["gap_min"]),
    band_high: float = float(GATE_CONSTANTS["band_high"]),
) -> dict[str, Any]:
    """The full derivation, recorded in every report so a reader can re-check it."""

    destroyed = destroyed_control_accuracy(n_options)
    floor = effective_frontier_floor(gap_min=gap_min, n_options=n_options)
    target = derived_frontier_target(gap_min=gap_min, band_high=band_high, n_options=n_options)
    return {
        "n_options": n_options,
        "gap_min": gap_min,
        "band_high": band_high,
        "destroyed_control_accuracy": destroyed,
        "destroyed_control_basis": "1 / n_options, exact for a deterministic solver",
        "effective_floor": floor,
        "effective_window": [floor, band_high],
        "frontier_target": target,
        "frontier_target_formula": "(gap_min + destroyed_control_accuracy + band_high) / 2",
        "dead_gates_dropped": ["destroyed_accuracy_max"],
        "caveat": (
            "the derivation removes a degree of freedom; it is not claimed to improve "
            "power. A midpoint selector has a higher false-pass rate against a genuinely "
            "0.65 reader than the stranded constant did."
        ),
    }


def select_frontier_level(
    accuracy_by_level: Mapping[int, float],
    *,
    n_options: int,
    gap_min: float = float(GATE_CONSTANTS["gap_min"]),
    band_high: float = float(GATE_CONSTANTS["band_high"]),
) -> dict[str, Any]:
    """Pick the level closest to the derived target; ties to the lower level."""

    arithmetic = gate_arithmetic(n_options=n_options, gap_min=gap_min, band_high=band_high)
    target = float(arithmetic["frontier_target"])
    floor = float(arithmetic["effective_floor"])
    explicit_level = int(GATE_CONSTANTS["explicit_positive_level"])
    explicit = accuracy_by_level.get(explicit_level)
    if explicit is None or explicit < float(GATE_CONSTANTS["explicit_positive_min"]):
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
            "arithmetic": arithmetic,
        }
    candidates = [
        (level, accuracy)
        for level, accuracy in sorted(accuracy_by_level.items())
        if level > explicit_level
    ]
    if not candidates:
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
            "arithmetic": arithmetic,
        }
    level, accuracy = min(candidates, key=lambda item: (abs(item[1] - target), item[0]))
    verdict = (
        "VOID_CEILING" if accuracy > band_high else "VOID_FLOOR" if accuracy < floor else "SELECTED"
    )
    return {
        "selected_level": level if verdict == "SELECTED" else None,
        "candidate_level": level,
        "candidate_accuracy": accuracy,
        "verdict": verdict,
        "explicit_positive_accuracy": explicit,
        "arithmetic": arithmetic,
    }


# ------------------------------------------------------------------- answer protocol
#
# Candidate-neutral by construction: the identifiers are a pure function of the option
# *count*.  Nothing about the surface, the genome or the option content can reach them,
# so the response syntax cannot become a second representation variable.

ANSWER_KEY = "answer"
_MAX_OPTIONS = 26


def canonical_answer_ids(n_options: int) -> tuple[str, ...]:
    if not 2 <= n_options <= _MAX_OPTIONS:
        raise ValueError(f"n_options must be in [2, {_MAX_OPTIONS}], got {n_options}")
    return tuple(f"OPTION_{chr(ord('A') + index)}" for index in range(n_options))


def response_schema(n_options: int) -> dict[str, Any]:
    """The grammar constraint.  No prose can be emitted, so no cap can eat the answer."""

    return {
        "type": "object",
        "properties": {
            ANSWER_KEY: {"type": "string", "enum": list(canonical_answer_ids(n_options))}
        },
        "required": [ANSWER_KEY],
        "additionalProperties": False,
    }


def answer_protocol_hash(n_options: int) -> str:
    return stable_hash(
        {
            "version": ANSWER_PROTOCOL_VERSION,
            "answer_key": ANSWER_KEY,
            "ids": list(canonical_answer_ids(n_options)),
            "schema": response_schema(n_options),
        }
    )


def parse_answer(output: str, n_options: int) -> int | None:
    """Return the selected index, or ``None``.  ``None`` is scored wrong, never skipped."""

    try:
        value = json.loads(output.strip())
    except (json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(value, dict) or set(value) != {ANSWER_KEY}:
        return None
    ids = canonical_answer_ids(n_options)
    answer = value[ANSWER_KEY]
    return ids.index(answer) if answer in ids else None


# ------------------------------------------------------------------ environment interface
#
# The three task families (premise_selection, rewrite_direction, legal_transform) are
# being written concurrently by other agents.  Nothing here imports them.  A conforming
# environment only has to produce objects with these members.


class TaskItem(Protocol):
    """One decidable choice item, in canonical form, before any rendering."""

    @property
    def task_id(self) -> str:
        """Unique within the environment.  Qualified with the environment version by the
        runner before it reaches the cache identity."""

    @property
    def family_id(self) -> str:
        """Cluster identifier.  Paired statistics resample families, not rows."""

    @property
    def level(self) -> int:
        """Difficulty level.  Level 0 must be the explicit-positive arm."""

    @property
    def variant(self) -> str:
        """``ORIGINAL`` or a harness-generated variant such as ``ORDER_ROTATED``."""

    @property
    def question(self) -> str:
        """Rendering-neutral question text.  Identical for every arm."""

    @property
    def canonical_state(self) -> CanonicalState:
        """The rendering-neutral canonical state.  Arms render this; none may alter it."""

    @property
    def options(self) -> tuple[CanonicalAction, ...]:
        """Canonical options in canonical order.  Every arm renders this exact order."""

    @property
    def correct_index(self) -> int:
        """Index into :attr:`options`.  Truth must be derived by the environment, not here."""

    @property
    def provenance(self) -> Mapping[str, Any]:
        """Donor, extraction path, trust tier, and anything else a reader needs."""


class TaskEnvironment(Protocol):
    """A mechanism's item source."""

    @property
    def environment_version(self) -> str: ...

    @property
    def mechanism(self) -> str: ...

    def items(self, *, families: int, levels: Sequence[int]) -> tuple[TaskItem, ...]: ...


@dataclass(frozen=True, slots=True)
class MaterialisedItem:
    """A concrete :class:`TaskItem`.  Also what :func:`rotate_options` returns."""

    task_id: str
    family_id: str
    level: int
    variant: str
    question: str
    canonical_state: CanonicalState
    options: tuple[CanonicalAction, ...]
    correct_index: int
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "family_id": self.family_id,
            "level": self.level,
            "variant": self.variant,
            "question": self.question,
            "state_hash": self.canonical_state.mathematical_hash,
            "options": [item.to_dict() for item in self.options],
            "correct_index": self.correct_index,
            "provenance": dict(self.provenance),
        }


class ItemVariant(StrEnum):
    ORIGINAL = "ORIGINAL"
    ORDER_ROTATED = "ORDER_ROTATED"


def rotate_options(item: TaskItem, shift: int = 1) -> MaterialisedItem:
    """Order-invariance arm: the same mathematics with the option order rotated.

    Position and content are separable only if both are observed.  Phase 6 could not tell
    "position-locked" from "content-locked but wrong" precisely because the swap arms of
    the collapsed cells were never run.
    """

    count = len(item.options)
    if count < 2:
        raise ValueError("cannot rotate fewer than two options")
    shift %= count
    if shift == 0:
        raise ValueError("a rotation of zero is not an order-invariance arm")
    rotated = tuple(item.options[(index - shift) % count] for index in range(count))
    return MaterialisedItem(
        task_id=f"{item.task_id}#rot{shift}",
        family_id=item.family_id,
        level=item.level,
        variant=str(ItemVariant.ORDER_ROTATED),
        question=item.question,
        canonical_state=item.canonical_state,
        options=rotated,
        correct_index=(item.correct_index + shift) % count,
        provenance={**dict(item.provenance), "rotated_from": item.task_id, "shift": shift},
    )


# ------------------------------------------------------------------------ prompt envelope


class SyntaxGuidePolicy(StrEnum):
    """``GenomePhenotypeLanguage.acquisition_guide`` names the arm's own gene values, so a
    per-arm guide would encode one surface's advantages into the prompt.  It is therefore
    never used here: the guide is omitted, or it is one shared constant."""

    OMITTED = "OMITTED"
    SHARED_CONSTANT = "SHARED_CONSTANT"


SHARED_SYNTAX_GUIDE = (
    "The state below is a lossless record of one mathematical situation. Read its goal, "
    "assumptions, bindings, obligations, evidence dependencies and propositions. Each "
    "option contains only a proposed mathematical result. Select the option that "
    "correctly answers the question about the displayed state."
)

_STATE_PLACEHOLDER = "\x00STATE\x00"
_OPTION_PLACEHOLDER = "\x00OPTION{index}\x00"


def _protocol_header(n_options: int) -> str:
    ids = canonical_answer_ids(n_options)
    example = json.dumps({ANSWER_KEY: ids[0]}, separators=(",", ":"))
    return (
        f"Answer with exactly one JSON object, for example {example}.\n"
        f"The only valid values are: {', '.join(ids)}.\n"
        "Read identifiers exactly. Do not choose by option position."
    )


def _guide_block(policy: SyntaxGuidePolicy) -> str:
    if policy is SyntaxGuidePolicy.OMITTED:
        return ""
    return f"GUIDE:\n{SHARED_SYNTAX_GUIDE}\n"


def _assemble(
    *, n_options: int, question: str, guide: str, state_text: str, option_texts: Sequence[str]
) -> str:
    ids = canonical_answer_ids(n_options)
    options = "\n".join(f"{label}: {text}" for label, text in zip(ids, option_texts, strict=True))
    return (
        f"{_protocol_header(n_options)}\n"
        f"{guide}"
        f"QUESTION: {question}\n"
        f"CURRENT STATE:\n{state_text}\n"
        f"OPTIONS:\n{options}\n"
        "ANSWER:"
    )


def build_prompt(
    genome: ModelViewGenome,
    item: TaskItem,
    *,
    guide_policy: SyntaxGuidePolicy = SyntaxGuidePolicy.OMITTED,
) -> str:
    """One envelope for every arm; only the state and the option renderings vary."""

    assert_game_r_genome(genome)
    compiler = ModelViewCompiler(genome)
    language = GenomePhenotypeLanguage(genome.surface)
    view = compiler.compile(item.canonical_state, options=tuple(item.options))
    return _assemble(
        n_options=len(item.options),
        question=item.question,
        guide=_guide_block(guide_policy),
        state_text=view.text,
        option_texts=[language.render_action_choice(option) for option in item.options],
    )


def envelope_signature(
    item: TaskItem, *, guide_policy: SyntaxGuidePolicy = SyntaxGuidePolicy.OMITTED
) -> str:
    """Hash of the envelope with every arm-dependent slot replaced by a placeholder.

    Equal across arms iff the arms share one envelope.  It is deliberately blind to the
    rendered state and option bytes, which are exactly what is *allowed* to differ.
    """

    n_options = len(item.options)
    skeleton = _assemble(
        n_options=n_options,
        question=item.question,
        guide=_guide_block(guide_policy),
        state_text=_STATE_PLACEHOLDER,
        option_texts=[_OPTION_PLACEHOLDER.format(index=i) for i in range(n_options)],
    )
    return stable_hash({"version": ENVELOPE_VERSION, "skeleton": skeleton})


def prompt_bytes_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------- parity


def founder_genome(surface_id: str) -> ModelViewGenome:
    """A Track-E founder: reversible surface only, content genome pinned at its default."""

    return ModelViewGenome(
        f"GRF_{surface_id}",
        (),
        SearchTrack.EQUAL_INFORMATION,
        SEED_GENOME_BY_ID[surface_id],
        ContentGenome(),
    )


def founder_genomes() -> tuple[ModelViewGenome, ...]:
    return tuple(founder_genome(surface_id) for surface_id in SEED_GENOME_BY_ID)


def rendered_option_inventory(
    language: GenomePhenotypeLanguage, options: Sequence[CanonicalAction]
) -> str:
    """Inventory of the mathematics each rendered option carries, **in option order**.

    Decoded through the *unbound* base codec for the same reason
    :func:`arena.experiments.game_r_mutant_audit.prompt_information_inventory` does: a
    candidate that filters on parse must not be able to hide what it emitted.

    GUARANTEES: the arms present the same mathematical content under the same canonical
    answer identifier, so ``OPTION_B`` means the same proposal for every arm.  A renderer
    that permuted the options would change this hash and be refused.

    DOES NOT GUARANTEE: that the argument order *inside* one option is identical across
    arms.  Expression records are sorted within an option, exactly as the frozen
    :func:`arena.experiments.game_r_mutant_audit.option_inventory` does, because the
    action-policy gene legitimately chooses the envelope keys (``candidate_result``,
    ``apply/target_role``, ...) and different grammars can decode a record's keys in a
    different order.  Those envelope labels carry no mathematics and are part of R.
    """

    decoded = [
        GenomePhenotypeLanguage._decode_value(language, language.render_action_choice(option))
        for option in options
    ]
    return stable_hash([sorted(_expressions(item)) for item in decoded])


def _as_v4_probe(item: TaskItem) -> V4Probe:
    """Adapt a two-option item so V4's own parity assertion can be reused verbatim."""

    options = tuple(item.options)
    return V4Probe(
        probe_id=item.task_id,
        family_id=item.family_id,
        slice_name=V4Slice.DEV,
        mechanism="game_r_formal_v1",
        level=item.level,
        parameters={},
        variant=V4Variant.ORIGINAL,
        state=item.canonical_state,
        previous_state=None,
        question=item.question,
        options=(options[0], options[1]),
        expected_index=item.correct_index,
        truth_kind="STRUCTURAL",
        oracle_record={},
    )


@dataclass(frozen=True, slots=True)
class ParityReport:
    task_id: str
    mathematical_hash: str
    envelope_signature: str
    answer_protocol_hash: str
    surface_information_hash: str
    option_inventory_hash: str
    prompt_hashes: dict[str, str]
    checks: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mathematical_hash": self.mathematical_hash,
            "envelope_signature": self.envelope_signature,
            "answer_protocol_hash": self.answer_protocol_hash,
            "surface_information_hash": self.surface_information_hash,
            "option_inventory_hash": self.option_inventory_hash,
            "prompt_hashes": dict(self.prompt_hashes),
            "checks": dict(self.checks),
        }


def assert_arena_parity(
    item: TaskItem,
    genomes: Sequence[ModelViewGenome],
    *,
    guide_policy: SyntaxGuidePolicy = SyntaxGuidePolicy.OMITTED,
) -> ParityReport:
    """Refuse to run this (task, arm-set) unless every parity property holds.

    Guaranteed, per arm and per pair of arms:

    1. the arm is a Game-R candidate (``assert_game_r_genome``: no content projection);
    2. the arm's surface round-trips to the identical ``mathematical_hash``, and the
       compiler's own ``validate`` reproduces the compiled view independently;
    3. the information *on the page* is identical across arms, decoded through the
       unbound base codec (``prompt_information_inventory``), so a renderer cannot hide
       content behind a filtering parser;
    4. the decoded option renderings carry the same content in the same order;
    5. the answer protocol and the prompt envelope are byte-identical across arms;
    6. the arms differ in rendered prompt bytes - a byte-identical pair is a refusal, not
       a pass, because it would silently make two "representations" one.

    NOT guaranteed, and deliberately so: that two arms are equally *readable*, equally
    *long*, or equally *familiar* to the solver.  Those are the things the experiment is
    trying to measure.  Nor is truth checked here - ``correct_index`` is the environment's
    responsibility and this harness never re-derives it.
    """

    if not genomes:
        raise ParityViolation("parity needs at least one arm")
    options = tuple(item.options)
    if not 2 <= len(options) <= _MAX_OPTIONS:
        raise ParityViolation(f"item {item.task_id} has an unusable option count")
    if not 0 <= item.correct_index < len(options):
        raise ParityViolation(f"item {item.task_id} has a correct_index outside its options")

    expected_hash = item.canonical_state.mathematical_hash
    prompts: dict[str, str] = {}
    surfaces: set[str] = set()
    option_hashes: set[str] = set()
    for genome in genomes:
        assert_game_r_genome(genome)
        compiler = ModelViewCompiler(genome)
        compiled = compiler.compile(item.canonical_state, options=options)
        try:
            compiler.validate(compiled, item.canonical_state, options=options)
            recovered = compiler.recover_canonical_state(compiled)
        except ValueError as error:
            raise ParityViolation(
                f"{genome.candidate_id} failed model-view validation on {item.task_id}: {error}"
            ) from error
        if recovered.mathematical_hash != expected_hash:
            raise ParityViolation(
                f"{genome.candidate_id} does not recover the canonical state of {item.task_id}"
            )
        language = GenomePhenotypeLanguage(genome.surface)
        surfaces.add(prompt_information_inventory(language, item.canonical_state))
        option_hashes.add(rendered_option_inventory(language, options))
        prompts[genome.candidate_id] = build_prompt(genome, item, guide_policy=guide_policy)

    if len(surfaces) != 1:
        raise ParityViolation(
            f"arms put different information on the page for {item.task_id}: {len(surfaces)} "
            "distinct surface inventories"
        )
    if len(option_hashes) != 1:
        raise ParityViolation(
            f"arms rendered different option content or option order for {item.task_id}"
        )
    if len(set(prompts.values())) != len(prompts):
        collisions = sorted(
            candidate
            for candidate, text in prompts.items()
            if list(prompts.values()).count(text) > 1
        )
        raise ParityViolation(
            f"arms rendered byte-identical prompts for {item.task_id}: {collisions}"
        )

    # A single-arm run is legal (a baseline-only or resume run), but it proves nothing about
    # parity.  The cross-arm checks are recorded as NOT_APPLICABLE so that such a report can
    # never be mistaken for a parity-verified comparison.
    cross_arm = "PASS" if len(genomes) > 1 else "NOT_APPLICABLE_SINGLE_ARM"
    checks = {
        "game_r_genome": "PASS",
        "semantic_recovery": "PASS",
        "surface_information_identical": cross_arm,
        "option_content_and_order_identical": cross_arm,
        "envelope_identical": cross_arm,
        "answer_protocol_identical": cross_arm,
        "rendered_bytes_distinct": cross_arm,
    }
    if len(options) == 2 and len(genomes) > 1:
        # Corroborating, never authoritative: V4's assertion uses V4's own envelope, which
        # embeds a per-arm acquisition guide and can therefore separate two arms whose
        # state renderings are identical.  This harness's own byte check above is the one
        # that decides.
        assert_information_parity(_as_v4_probe(item), list(genomes))
        checks["v4_cross_check"] = "APPLIED"
    else:
        checks["v4_cross_check"] = "NOT_APPLICABLE"

    return ParityReport(
        task_id=item.task_id,
        mathematical_hash=expected_hash,
        envelope_signature=envelope_signature(item, guide_policy=guide_policy),
        answer_protocol_hash=answer_protocol_hash(len(options)),
        surface_information_hash=next(iter(surfaces)),
        option_inventory_hash=next(iter(option_hashes)),
        prompt_hashes={key: prompt_bytes_hash(text) for key, text in prompts.items()},
        checks=checks,
    )


# ------------------------------------------------------------------------ cache identity
#
# A cache entry is valid to reuse only when ALL eight components match.  ``task_id`` is
# the *qualified* id (environment version + mechanism + item id), so an item re-issued by
# a new environment version can never collide with an old row.


CACHE_IDENTITY_COMPONENTS = (
    "experiment_version",
    "model_digest",
    "model_revision",
    "runtime_condition",
    "decoding_hash",
    "task_id",
    "candidate_id",
    "prompt_hash",
)


def decoding_hash(decoding: Mapping[str, Any], schema: Mapping[str, Any]) -> str:
    return stable_hash({"decoding": dict(decoding), "response_schema": dict(schema)})


def cache_identity(
    *,
    experiment_version: str,
    model_digest: str,
    model_revision: str,
    runtime_condition: str,
    decoding: Mapping[str, Any],
    schema: Mapping[str, Any],
    task_id: str,
    candidate_id: str,
    prompt: str,
) -> dict[str, str]:
    """The single explicit key function.  Every consumer goes through this."""

    identity = {
        "experiment_version": experiment_version,
        "model_digest": model_digest,
        "model_revision": model_revision,
        "runtime_condition": runtime_condition,
        "decoding_hash": decoding_hash(decoding, schema),
        "task_id": task_id,
        "candidate_id": candidate_id,
        "prompt_hash": prompt_bytes_hash(prompt),
    }
    missing = [name for name in CACHE_IDENTITY_COMPONENTS if not identity.get(name)]
    if missing:
        raise CacheIdentityViolation(f"cache identity is missing components: {missing}")
    return identity


def cache_key(identity: Mapping[str, str]) -> str:
    if tuple(sorted(identity)) != tuple(sorted(CACHE_IDENTITY_COMPONENTS)):
        raise CacheIdentityViolation(f"cache identity has the wrong components: {sorted(identity)}")
    return stable_hash(dict(identity))


class CacheScope(StrEnum):
    """Recorded on every row so a later invalidation rule can tell reuse from contamination.

    Phase 6's rule said "cache hits > 0" and fired on 61 rows that were, on inspection, the
    same solver resuming its own work under the same condition.  A rule cannot separate
    those cases unless the rows say which they are.
    """

    FRESH = "FRESH"
    SAME_CONDITION_REUSE = "SAME_CONDITION_REUSE"
    CROSS_CONDITION = "CROSS_CONDITION"


def classify_cache_scope(
    *, hit: bool, stored_identity: Mapping[str, str] | None, requested_identity: Mapping[str, str]
) -> CacheScope:
    if not hit:
        return CacheScope.FRESH
    if stored_identity is not None and dict(stored_identity) == dict(requested_identity):
        return CacheScope.SAME_CONDITION_REUSE
    return CacheScope.CROSS_CONDITION


class ResponseCache:
    """Content-addressed, resumable, and incapable of serving a cross-condition row.

    Errors are never cached.  V5 cached transport failures, which freezes a transient
    outage into the record and makes a resumed run reproduce it forever.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, identity: Mapping[str, str]) -> Path:
        return self.root / f"{cache_key(identity)}.json"

    def load(self, identity: Mapping[str, str]) -> tuple[dict[str, Any] | None, CacheScope]:
        path = self.path_for(identity)
        if not path.exists():
            return None, CacheScope.FRESH
        record = json.loads(path.read_text(encoding="utf-8"))
        stored = record.get("identity")
        result = record.get("result")
        scope = classify_cache_scope(
            hit=True,
            stored_identity=stored if isinstance(stored, dict) else None,
            requested_identity=identity,
        )
        if scope is CacheScope.CROSS_CONDITION:
            raise CacheIdentityViolation(
                f"cache record {path} does not carry the identity it was asked for; refusing to "
                "serve a cross-condition row"
            )
        if not isinstance(result, dict):
            raise CacheIdentityViolation(f"cache record {path} has no usable result payload")
        return result, scope

    def store(self, identity: Mapping[str, str], result: Mapping[str, Any]) -> None:
        if result.get("error"):
            return
        path = self.path_for(identity)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            canonical_json({"identity": dict(identity), "result": dict(result)}), encoding="utf-8"
        )


# ------------------------------------------------------------------------ token accounting


class TokenCounter(Protocol):
    """Exact token counting.  There is no character fallback anywhere in this module."""

    @property
    def tokenizer_id(self) -> str: ...

    @property
    def exact(self) -> bool: ...

    def count_tokens(self, text: str) -> int: ...


@dataclass(frozen=True, slots=True)
class ContextBudget:
    num_ctx: int
    max_output_tokens: int
    reserve_tokens: int = 256

    @property
    def prompt_token_limit(self) -> int:
        return self.num_ctx - self.max_output_tokens - self.reserve_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_ctx": self.num_ctx,
            "max_output_tokens": self.max_output_tokens,
            "reserve_tokens": self.reserve_tokens,
            "prompt_token_limit": self.prompt_token_limit,
            "method": "exact tokenizer count, pre-call; refusal, not truncation",
        }


@dataclass(frozen=True, slots=True)
class StubTokenCounter:
    """Deterministic counter for tests and ``--dry-run``.

    It reports a *constant* number of tokens per whitespace-delimited word so that the
    tests can decouple token count from character count entirely.
    """

    tokens_per_word: int = 1
    tokenizer_id: str = "stub-token-counter-v1"
    exact: bool = True

    def count_tokens(self, text: str) -> int:
        return self.tokens_per_word * max(1, len(text.split()))


@dataclass(frozen=True, slots=True)
class FixedTokenCounter:
    """Reports a fixed count regardless of input.  Used to prove refusal is token-driven."""

    tokens: int
    tokenizer_id: str = "fixed-token-counter-v1"
    exact: bool = True

    def count_tokens(self, text: str) -> int:
        return self.tokens


# ------------------------------------------------------------------------------- solvers


@dataclass(frozen=True, slots=True)
class SolverResponse:
    text: str
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    done_reason: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "done_reason": self.done_reason,
            "error": self.error,
        }


class Solver(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def digest(self) -> str: ...

    @property
    def revision(self) -> str: ...

    def generate(
        self, prompt: str, *, schema: Mapping[str, Any], decoding: Mapping[str, Any]
    ) -> SolverResponse: ...


class StubSolverPolicy(StrEnum):
    ORACLE = "ORACLE"
    CONSTANT_FIRST = "CONSTANT_FIRST"
    UNPARSEABLE = "UNPARSEABLE"
    OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    DETERMINISTIC_MIX = "DETERMINISTIC_MIX"


@dataclass
class StubSolver:
    """Makes no network call.  Exercises every scoring and failure path.

    ``ORACLE`` needs the correct index, which the runner supplies out of band via
    :meth:`prime`; a solver may not see truth, so the stub is primed per prompt hash and
    the priming table is never consulted by any other policy.
    """

    policy: StubSolverPolicy = StubSolverPolicy.DETERMINISTIC_MIX
    n_options: int = 2
    name: str = "stub-solver"
    digest: str = "stub-digest-0000000000000000000000000000000000000000000000000000000000"
    revision: str = "stub-revision-v1"
    calls: int = 0
    _truth: dict[str, int] = field(default_factory=dict)

    def prime(self, prompt: str, correct_index: int) -> None:
        self._truth[prompt_bytes_hash(prompt)] = correct_index

    def generate(
        self, prompt: str, *, schema: Mapping[str, Any], decoding: Mapping[str, Any]
    ) -> SolverResponse:
        self.calls += 1
        ids = canonical_answer_ids(self.n_options)
        digest = prompt_bytes_hash(prompt)
        tokens = max(1, len(prompt.split()))
        if self.policy is StubSolverPolicy.TRANSPORT_ERROR:
            return SolverResponse("", None, None, "", "stub transport failure")
        if self.policy is StubSolverPolicy.UNPARSEABLE:
            return SolverResponse("I think it is the first one.", tokens, 8, "stop")
        if self.policy is StubSolverPolicy.OUTPUT_TRUNCATED:
            return SolverResponse('{"answer":"OPT', tokens, int(decoding["num_predict"]), "length")
        if self.policy is StubSolverPolicy.CONSTANT_FIRST:
            index = 0
        elif self.policy is StubSolverPolicy.ORACLE:
            index = self._truth.get(digest, 0)
        else:
            index = int(digest[:8], 16) % self.n_options
        return SolverResponse(
            json.dumps({ANSWER_KEY: ids[index]}, separators=(",", ":")), tokens, 8, "stop"
        )


@dataclass(frozen=True, slots=True)
class OllamaSolver:
    """The real solver.  **Never executed by this module's tests or by ``--dry-run``.**

    It is written so the integrator can wire it after the spec is frozen; the guard in
    :func:`main` is what keeps it from being invoked accidentally.
    """

    name: str
    digest: str
    revision: str
    endpoint: str = "http://127.0.0.1:11434/api/generate"
    bare: bool = True
    timeout_seconds: int = 900

    def generate(  # pragma: no cover - requires a live local runtime
        self, prompt: str, *, schema: Mapping[str, Any], decoding: Mapping[str, Any]
    ) -> SolverResponse:
        payload: dict[str, Any] = {
            "model": self.name,
            "prompt": prompt,
            "stream": False,
            "format": dict(schema),
            "options": {k: v for k, v in decoding.items() if k not in {"engine", "think", "raw"}},
        }
        if self.bare:
            payload["raw"] = True
        else:
            payload["think"] = decoding.get("think", False)
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = json.loads(response.read().decode())
        except Exception as error:
            return SolverResponse("", None, None, "", repr(error))
        return SolverResponse(
            text=str(raw.get("response", "")),
            prompt_tokens=int(raw.get("prompt_eval_count", 0)) or None,
            output_tokens=int(raw.get("eval_count", 0)) or None,
            done_reason=str(raw.get("done_reason", "")),
        )


# -------------------------------------------------------------------------------- budget


@dataclass
class CallBudget:
    """A hard ceiling.  Cache hits are free; every fresh call reserves one unit first."""

    max_calls: int
    spent: int = 0

    def reserve(self) -> None:
        if self.spent >= self.max_calls:
            raise BudgetExceeded(
                f"model-call budget of {self.max_calls} is exhausted; rerun with a larger "
                "budget to resume - completed rows are already cached"
            )
        self.spent += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.spent)


# ------------------------------------------------------------------------------ run rows


class RowStatus(StrEnum):
    CORRECT = "CORRECT"
    MODEL_SEMANTIC_ERROR = "MODEL_SEMANTIC_ERROR"
    RESPONSE_SCHEMA_ERROR = "RESPONSE_SCHEMA_ERROR"
    OUTPUT_TRUNCATION = "OUTPUT_TRUNCATION"
    PROMPT_OVER_BUDGET = "PROMPT_OVER_BUDGET"
    SOLVER_ERROR = "SOLVER_ERROR"


#: Statuses that are scored as an incorrect answer rather than dropped from the denominator.
#: Every failure mode the solver can cause is in here: fail closed, never skip.
SCORED_STATUSES = frozenset(
    {
        RowStatus.CORRECT,
        RowStatus.MODEL_SEMANTIC_ERROR,
        RowStatus.RESPONSE_SCHEMA_ERROR,
        RowStatus.OUTPUT_TRUNCATION,
    }
)


@dataclass(frozen=True, slots=True)
class RunConfig:
    experiment_version: str
    runtime_condition: str
    decoding: Mapping[str, Any]
    context: ContextBudget
    cache_root: Path
    guide_policy: SyntaxGuidePolicy = SyntaxGuidePolicy.OMITTED
    gap_min: float = float(GATE_CONSTANTS["gap_min"])
    band_high: float = float(GATE_CONSTANTS["band_high"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness_version": HARNESS_VERSION,
            "experiment_version": self.experiment_version,
            "runtime_condition": self.runtime_condition,
            "decoding": dict(self.decoding),
            "context": self.context.to_dict(),
            "guide_policy": str(self.guide_policy),
            "gap_min": self.gap_min,
            "band_high": self.band_high,
        }


def qualified_task_id(environment_version: str, mechanism: str, task_id: str) -> str:
    return f"{environment_version}::{mechanism}::{task_id}"


def run_item(
    item: TaskItem,
    genome: ModelViewGenome,
    *,
    mechanism: str,
    environment_version: str,
    config: RunConfig,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    cache: ResponseCache,
) -> dict[str, Any]:
    """Render, budget-check, call or replay, parse, and score exactly one row."""

    if not counter.exact:
        raise TokenAccountingRefusal(
            f"token counter {counter.tokenizer_id} is not exact; refusing to send any prompt. "
            "V3 truncated its inputs and V4 voided rows on a character heuristic; this harness "
            "will not guess a token count."
        )
    n_options = len(item.options)
    schema = response_schema(n_options)
    prompt = build_prompt(genome, item, guide_policy=config.guide_policy)
    counted = counter.count_tokens(prompt)
    task = qualified_task_id(environment_version, mechanism, item.task_id)
    identity = cache_identity(
        experiment_version=config.experiment_version,
        model_digest=solver.digest,
        model_revision=f"{solver.revision}|{counter.tokenizer_id}",
        runtime_condition=config.runtime_condition,
        decoding=config.decoding,
        schema=schema,
        task_id=task,
        candidate_id=genome.candidate_id,
        prompt=prompt,
    )
    row: dict[str, Any] = {
        "mechanism": mechanism,
        "environment_version": environment_version,
        "task_id": task,
        # Pairs an order-rotated row with the row it was derived from, without parsing the
        # task id: an environment may supply its own rotated items and set the provenance.
        "pairing_key": qualified_task_id(
            environment_version, mechanism, str(item.provenance.get("rotated_from", item.task_id))
        ),
        "family_id": item.family_id,
        "level": item.level,
        "variant": item.variant,
        "candidate_id": genome.candidate_id,
        "prompt_hash": identity["prompt_hash"],
        "cache_key": cache_key(identity),
        "prompt_tokens_counted": counted,
        "prompt_token_limit": config.context.prompt_token_limit,
        "n_options": n_options,
        "correct_index": item.correct_index,
    }

    if counted > config.context.prompt_token_limit:
        # Refusal, not truncation.  The prompt is never sent and the row is never dropped.
        row.update(
            {
                "cache_hit": False,
                "cache_scope": str(CacheScope.FRESH),
                "status": str(RowStatus.PROMPT_OVER_BUDGET),
                "selected_index": None,
                "selected_answer_id": None,
                "selected_content_hash": None,
                "correct": False,
                "valid": False,
                "prompt_tokens_reported": None,
                "token_count_mismatch": False,
                "raw_output": "",
            }
        )
        return row

    cached, scope = cache.load(identity)
    if scope is CacheScope.CROSS_CONDITION:  # pragma: no cover - ResponseCache already raised
        raise CacheIdentityViolation("cross-condition cache reuse is impossible by construction")
    if cached is None:
        budget.reserve()
        response = solver.generate(prompt, schema=schema, decoding=config.decoding)
        result = response.to_dict()
        cache.store(identity, result)
    else:
        result = cached

    raw_reported = result.get("prompt_tokens")
    reported = int(raw_reported) if raw_reported else None
    mismatch = reported is not None and reported != counted
    selected = parse_answer(str(result.get("text", "")), n_options)
    if result.get("error"):
        status = RowStatus.SOLVER_ERROR
    elif selected is None:
        output_tokens = result.get("output_tokens") or 0
        cap = int(config.decoding.get("num_predict", 0) or 0)
        status = (
            RowStatus.OUTPUT_TRUNCATION
            if cap and int(output_tokens) >= cap
            else RowStatus.RESPONSE_SCHEMA_ERROR
        )
    else:
        status = (
            RowStatus.CORRECT if selected == item.correct_index else RowStatus.MODEL_SEMANTIC_ERROR
        )
    ids = canonical_answer_ids(n_options)
    row.update(
        {
            "cache_hit": cached is not None,
            "cache_scope": str(scope),
            "status": str(status),
            "selected_index": selected,
            "selected_answer_id": ids[selected] if selected is not None else None,
            "selected_content_hash": stable_hash(item.options[selected].to_dict())
            if selected is not None
            else None,
            "correct": status is RowStatus.CORRECT,
            "valid": selected is not None,
            "prompt_tokens_reported": reported,
            "token_count_mismatch": mismatch,
            "raw_output": str(result.get("text", "")),
        }
    )
    return row


def run_mechanism(
    items: Sequence[TaskItem],
    genomes: Sequence[ModelViewGenome],
    *,
    mechanism: str,
    environment_version: str,
    config: RunConfig,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    cache: ResponseCache,
) -> dict[str, Any]:
    """Parity first, then rows.  Parity failure refuses the whole mechanism."""

    if not items:
        raise HarnessRefusal(f"mechanism {mechanism} produced no items")
    parity = [
        assert_arena_parity(item, genomes, guide_policy=config.guide_policy).to_dict()
        for item in items
    ]
    envelopes = {report["envelope_signature"] for report in parity}
    protocols = {report["answer_protocol_hash"] for report in parity}
    rows = [
        run_item(
            item,
            genome,
            mechanism=mechanism,
            environment_version=environment_version,
            config=config,
            solver=solver,
            counter=counter,
            budget=budget,
            cache=cache,
        )
        for item in items
        for genome in genomes
    ]
    return {
        "mechanism": mechanism,
        "environment_version": environment_version,
        "parity": parity,
        "distinct_envelope_signatures": sorted(envelopes),
        "distinct_answer_protocols": sorted(protocols),
        "rows": rows,
    }


# ------------------------------------------------------------------------------- scoring


def _require_single_mechanism(rows: Sequence[Mapping[str, Any]]) -> str:
    mechanisms = {str(row["mechanism"]) for row in rows}
    if len(mechanisms) != 1:
        raise HarnessRefusal(f"scoring is per mechanism and never pooled; got {sorted(mechanisms)}")
    return mechanisms.pop()


def score_mechanism(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-mechanism, per-candidate statistics.  Never pooled across mechanisms."""

    if not rows:
        raise HarnessRefusal("cannot score an empty row set")
    mechanism = _require_single_mechanism(rows)
    candidates = {str(row["candidate_id"]) for row in rows}
    if len(candidates) != 1:
        raise HarnessRefusal(f"score one candidate at a time; got {sorted(candidates)}")
    scored = [row for row in rows if RowStatus(str(row["status"])) in SCORED_STATUSES]
    by_level: dict[int, list[Mapping[str, Any]]] = {}
    for row in scored:
        by_level.setdefault(int(row["level"]), []).append(row)
    accuracy_by_level = {
        level: sum(bool(r["correct"]) for r in values) / len(values)
        for level, values in sorted(by_level.items())
    }
    n_by_level = {level: len(values) for level, values in sorted(by_level.items())}
    answers = Counter(
        str(row["selected_answer_id"]) for row in scored if row["selected_answer_id"] is not None
    )
    selections = sum(answers.values())
    n_options = int(rows[0]["n_options"])

    originals = {
        str(row["pairing_key"]): row
        for row in scored
        if str(row["variant"]) == str(ItemVariant.ORIGINAL)
    }
    invariant = pairs = 0
    for row in scored:
        if str(row.get("variant")) != str(ItemVariant.ORDER_ROTATED):
            continue
        base = originals.get(str(row["pairing_key"]))
        if base is None:
            continue
        pairs += 1
        invariant += bool(
            base["selected_content_hash"] is not None
            and base["selected_content_hash"] == row["selected_content_hash"]
        )

    valid_rate = sum(bool(r["valid"]) for r in scored) / len(scored) if scored else 0.0
    return {
        "mechanism": mechanism,
        "candidate_id": next(iter(candidates)),
        "n_options": n_options,
        "rows_total": len(rows),
        "rows_scored": len(scored),
        "valid_response_rate": valid_rate,
        "accuracy_by_level": accuracy_by_level,
        "n_by_level": n_by_level,
        "answer_counts": dict(sorted(answers.items())),
        "largest_answer_share": (max(answers.values()) / selections) if selections else 1.0,
        "chance_answer_share": 1.0 / n_options,
        "position_invariance": (invariant / pairs) if pairs else None,
        "position_invariance_pairs": pairs,
        "over_budget_rows": sum(
            str(r["status"]) == str(RowStatus.PROMPT_OVER_BUDGET) for r in rows
        ),
        "solver_error_rows": sum(str(r["status"]) == str(RowStatus.SOLVER_ERROR) for r in rows),
        "output_truncation_rows": sum(
            str(r["status"]) == str(RowStatus.OUTPUT_TRUNCATION) for r in rows
        ),
        "schema_error_rows": sum(
            str(r["status"]) == str(RowStatus.RESPONSE_SCHEMA_ERROR) for r in rows
        ),
        "token_mismatch_rows": sum(bool(r["token_count_mismatch"]) for r in rows),
        "cache_hits": sum(bool(r["cache_hit"]) for r in rows),
        "cache_scopes": dict(sorted(Counter(str(r["cache_scope"]) for r in rows).items())),
        "mean_prompt_tokens": sum(int(r["prompt_tokens_counted"]) for r in rows) / len(rows),
    }


def gate_mechanism(
    score: Mapping[str, Any],
    *,
    gap_min: float = float(GATE_CONSTANTS["gap_min"]),
    band_high: float = float(GATE_CONSTANTS["band_high"]),
) -> dict[str, Any]:
    """Apply the gate.  Every void code names the property that failed."""

    n_options = int(score["n_options"])
    frontier = select_frontier_level(
        {int(k): float(v) for k, v in score["accuracy_by_level"].items()},
        n_options=n_options,
        gap_min=gap_min,
        band_high=band_high,
    )
    level = frontier["selected_level"]
    positives = int(score["n_by_level"].get(level, 0)) if level is not None else 0
    invariance = score["position_invariance"]
    checks = {
        "explicit_positive": "PASS"
        if frontier["verdict"] != "VOID_INSTRUMENT_LIMIT"
        else "VOID_INSTRUMENT_LIMIT",
        "frontier": "PASS" if frontier["verdict"] == "SELECTED" else str(frontier["verdict"]),
        "valid_response": "PASS"
        if float(score["valid_response_rate"]) >= float(GATE_CONSTANTS["valid_response_rate_min"])
        else "VOID_VALIDITY",
        "sample_size": "PASS"
        if positives >= int(GATE_CONSTANTS["min_positives_for_gates"])
        else "VOID_SAMPLE_SIZE",
        "context": "PASS"
        if int(score["over_budget_rows"]) <= int(GATE_CONSTANTS["over_budget_rows_max"])
        else "VOID_CONTEXT",
        "token_accounting": "PASS"
        if int(score["token_mismatch_rows"]) <= int(GATE_CONSTANTS["token_mismatch_rows_max"])
        else "VOID_TOKEN_ACCOUNTING",
        "transport": "PASS"
        if int(score["solver_error_rows"]) <= int(GATE_CONSTANTS["solver_error_rows_max"])
        else "VOID_TRANSPORT",
        "answer_share": "PASS"
        if float(score["largest_answer_share"]) <= float(GATE_CONSTANTS["largest_answer_share_max"])
        else "VOID_ANSWER_SHARE",
        "position_invariance": "PASS"
        if invariance is not None
        and float(invariance) >= float(GATE_CONSTANTS["position_invariance_min"])
        else "VOID_POSITION",
    }
    # "VOID_INSTRUMENT_LIMIT" would otherwise be reported twice.
    if checks["explicit_positive"] != "PASS":
        checks["frontier"] = "PASS"
    failures = [code for code in checks.values() if code != "PASS"]
    return {
        "checks": checks,
        "frontier": frontier,
        "qualified": not failures,
        "verdict": failures[0] if failures else "QUALIFIED",
    }


def paired_outcomes(
    rows_a: Sequence[Mapping[str, Any]], rows_b: Sequence[Mapping[str, Any]]
) -> tuple[list[bool], list[bool], list[str]]:
    """Per-task paired outcomes on the common scored set, clustered by family."""

    def index(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
        return {
            str(row["task_id"]): row
            for row in rows
            if RowStatus(str(row["status"])) in SCORED_STATUSES
        }

    left, right = index(rows_a), index(rows_b)
    common = sorted(set(left) & set(right))
    return (
        [bool(left[task]["correct"]) for task in common],
        [bool(right[task]["correct"]) for task in common],
        [str(left[task]["family_id"]) for task in common],
    )


def compare_arms(
    rows_a: Sequence[Mapping[str, Any]],
    rows_b: Sequence[Mapping[str, Any]],
    *,
    seed: int = 20260907,
    resamples: int = 4000,
) -> dict[str, Any]:
    """Exact McNemar plus a family-clustered paired bootstrap.  Both reused, not rewritten.

    Fails closed on an empty common set: no number is reported, so nothing can be read as
    practical equivalence.
    """

    outcomes_a, outcomes_b, clusters = paired_outcomes(rows_a, rows_b)
    if not outcomes_a:
        return {"status": "NO_COMMON_SET", "n": 0}
    comparison = paired_comparison(outcomes_a, outcomes_b, clusters, seed=seed, resamples=resamples)
    wilson_a = wilson_interval(sum(outcomes_a), len(outcomes_a))
    wilson_b = wilson_interval(sum(outcomes_b), len(outcomes_b))
    return {
        "status": "COMPARED",
        **comparison.to_dict(),
        "mcnemar_exact_p_recomputed": mcnemar_exact(comparison.n10, comparison.n01),
        "wilson_a": [wilson_a.lower, wilson_a.upper],
        "wilson_b": [wilson_b.lower, wilson_b.upper],
    }


def verify_destroyed_determinism(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """If destroyed-control rows are collected anyway, check the premise behind ``1/k``.

    Twins share a prompt hash; a deterministic solver must therefore have produced
    byte-identical output.  A failure means the solver is not deterministic and the
    derived destroyed constant does not apply to it.
    """

    groups: dict[str, set[str]] = {}
    for row in rows:
        groups.setdefault(str(row["prompt_hash"]), set()).add(str(row["raw_output"]))
    violations = sorted(key for key, values in groups.items() if len(values) > 1)
    return {
        "twin_groups": len(groups),
        "nondeterministic_prompt_hashes": violations,
        "deterministic": not violations,
    }


# ---------------------------------------------------------------------------- stub world


def _stub_state(tag: str) -> CanonicalState:
    """A small verifier-clean canonical state, built by the existing environment helper."""

    target = CanonicalExpression(
        "app",
        (
            CanonicalExpression("symbol", value=f"f_{tag}", sort="Identifier"),
            CanonicalExpression("symbol", value=f"x_{tag}", sort="Identifier"),
        ),
        sort="Term",
    )
    return build_state(target, (f"f_{tag}", f"x_{tag}"), "holds")


@dataclass(frozen=True, slots=True)
class StubEnvironment:
    """A minimal conforming :class:`TaskEnvironment`.  Used by ``--dry-run`` and the tests.

    It is *not* a task family.  The real ones are being built as
    ``arena/environments/{premise_selection,rewrite_direction,legal_transform}.py``; the
    integrator wires those against the Protocol and deletes nothing here.
    """

    mechanism: str = "stub_mechanism"
    environment_version: str = "arena-stub-environment-v0"
    n_options: int = 2
    shared_state: bool = True

    def items(
        self, *, families: int = 12, levels: Sequence[int] = (0, 1, 2, 3)
    ) -> tuple[TaskItem, ...]:
        built: list[TaskItem] = []
        for level in levels:
            for family in range(families):
                family_id = f"stub:L{level}:F{family:03d}"
                tag = "shared" if self.shared_state else f"{level}_{family}"
                options = tuple(
                    CanonicalAction(
                        action_id=f"a:{family_id}:{index}",
                        operation="propose",
                        target_ids=("goal",),
                        arguments=(
                            CanonicalExpression(
                                "symbol",
                                value=f"c{level}_{family}_{index}",
                                sort="Identifier",
                            ),
                        ),
                        warrant="stub",
                    )
                    for index in range(self.n_options)
                )
                base = MaterialisedItem(
                    task_id=f"{family_id}:original",
                    family_id=family_id,
                    level=level,
                    variant=str(ItemVariant.ORIGINAL),
                    question=f"Which option answers the question at level {level}?",
                    canonical_state=_stub_state(tag),
                    options=options,
                    correct_index=(family + level) % self.n_options,
                    provenance={"source": "stub", "trust_tier": "NONE"},
                )
                built.append(base)
                built.append(rotate_options(base))
        return tuple(built)


# ------------------------------------------------------------------------------ reporting


def run_tournament(
    mechanism_items: Mapping[str, tuple[str, Sequence[TaskItem]]],
    genomes: Sequence[ModelViewGenome],
    *,
    config: RunConfig,
    solver: Solver,
    counter: TokenCounter,
    budget: CallBudget,
    baseline_candidate: str,
) -> dict[str, Any]:
    """Run every mechanism, score per mechanism per arm, compare arms against a baseline."""

    cache = ResponseCache(config.cache_root)
    mechanisms: dict[str, Any] = {}
    for mechanism, (environment_version, items) in sorted(mechanism_items.items()):
        run = run_mechanism(
            items,
            genomes,
            mechanism=mechanism,
            environment_version=environment_version,
            config=config,
            solver=solver,
            counter=counter,
            budget=budget,
            cache=cache,
        )
        rows = run["rows"]
        by_candidate = {
            genome.candidate_id: [r for r in rows if r["candidate_id"] == genome.candidate_id]
            for genome in genomes
        }
        scores = {
            candidate: score_mechanism(candidate_rows)
            for candidate, candidate_rows in by_candidate.items()
        }
        gates = {
            candidate: gate_mechanism(score, gap_min=config.gap_min, band_high=config.band_high)
            for candidate, score in scores.items()
        }
        baseline_rows = by_candidate.get(baseline_candidate, [])
        comparisons = {
            candidate: compare_arms(candidate_rows, baseline_rows)
            for candidate, candidate_rows in by_candidate.items()
            if candidate != baseline_candidate and baseline_rows
        }
        mechanisms[mechanism] = {
            "environment_version": environment_version,
            "parity": run["parity"],
            "distinct_envelope_signatures": run["distinct_envelope_signatures"],
            "distinct_answer_protocols": run["distinct_answer_protocols"],
            "scores": scores,
            "gates": gates,
            "comparisons_against_baseline": comparisons,
            "rows": rows,
        }
    qualified = sorted(
        mechanism
        for mechanism, data in mechanisms.items()
        if data["gates"].get(baseline_candidate, {}).get("qualified")
    )
    n_options = next((len(items[0].options) for _, items in mechanism_items.values() if items), 2)
    return {
        "harness_version": HARNESS_VERSION,
        "config": config.to_dict(),
        "solver": {"name": solver.name, "digest": solver.digest, "revision": solver.revision},
        "tokenizer": {"id": counter.tokenizer_id, "exact": counter.exact},
        "baseline_candidate": baseline_candidate,
        "gate_constants": dict(GATE_CONSTANTS),
        "gate_arithmetic": gate_arithmetic(
            n_options=n_options, gap_min=config.gap_min, band_high=config.band_high
        ),
        "budget": {"max_calls": budget.max_calls, "spent": budget.spent},
        "qualified_mechanisms_for_baseline": qualified,
        "instrument_qualified": len(qualified)
        >= int(GATE_CONSTANTS["minimum_qualified_mechanisms"]),
        "mechanisms": mechanisms,
    }


DRY_RUN_DECODING: dict[str, Any] = {
    "engine": "stub",
    "num_ctx": 32768,
    "num_predict": 64,
    "temperature": 0.0,
    "seed": 20260907,
    "top_k": 64,
    "top_p": 0.95,
    "think": False,
}


def dry_run(
    *,
    root: Path,
    families: int = 12,
    levels: Sequence[int] = (0, 1, 2, 3),
    surfaces: Sequence[str] = ("L3_JSON_AST", "L1_CURRENT_HML", "L5_COMPACT_SYMBOLIC"),
    policy: StubSolverPolicy = StubSolverPolicy.DETERMINISTIC_MIX,
    budget_max: int = 100_000,
    environment: StubEnvironment | None = None,
) -> dict[str, Any]:
    """Exercise every code path with a stub solver.  Makes no network call of any kind."""

    env = environment or StubEnvironment()
    items = env.items(families=families, levels=levels)
    genomes = tuple(founder_genome(surface) for surface in surfaces)
    config = RunConfig(
        experiment_version="arena-game-r-formal-dry-run",
        runtime_condition="bare",
        decoding=DRY_RUN_DECODING,
        context=ContextBudget(num_ctx=32768, max_output_tokens=64),
        cache_root=Path(root) / "artifacts/cache/game_r_formal_v1_dry_run",
        guide_policy=SyntaxGuidePolicy.OMITTED,
    )
    solver = StubSolver(policy=policy, n_options=env.n_options)
    return run_tournament(
        {env.mechanism: (env.environment_version, items)},
        genomes,
        config=config,
        solver=solver,
        counter=StubTokenCounter(),
        budget=CallBudget(budget_max),
        baseline_candidate=genomes[0].candidate_id,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="stub solver; no network call")
    parser.add_argument("--live", action="store_true", help="use a real solver")
    parser.add_argument(
        "--confirm-model-calls",
        action="store_true",
        help="required alongside --live; the harness refuses to spend budget without it",
    )
    parser.add_argument("--families", type=int, default=12)
    parser.add_argument("--budget", type=int, default=900)
    parser.add_argument("--out", type=str, default="")
    args = parser.parse_args(argv)

    if args.live:
        if not args.confirm_model_calls:
            parser.error(
                "--live requires --confirm-model-calls. The Solver budget belongs to the "
                "integrator; this harness never spends it implicitly."
            )
        parser.error(
            "no live solver is wired in this version. Construct an OllamaSolver and a real "
            "TokenCounter, then call run_tournament directly."
        )
    if not args.dry_run:
        parser.error("pass --dry-run (stub solver) or --live --confirm-model-calls")

    report = dry_run(root=args.root, families=args.families, budget_max=args.budget)
    if args.out:
        ArtifactStore(Path(args.root) / "artifacts").write_json(args.out, report)
    print(
        canonical_json(
            {
                "budget": report["budget"],
                "gate_arithmetic": report["gate_arithmetic"],
                "qualified_mechanisms_for_baseline": report["qualified_mechanisms_for_baseline"],
                "cache_scopes": {
                    mechanism: {
                        candidate: score["cache_scopes"]
                        for candidate, score in data["scores"].items()
                    }
                    for mechanism, data in report["mechanisms"].items()
                },
            }
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
