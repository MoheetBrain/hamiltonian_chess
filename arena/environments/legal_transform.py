"""Legal vs illegal transformation family v1: is this proposed proof step the real one?

The decision.  An item shows a real Lean 4 proof state, a proposed action, and a proposed
result state.  The reader answers ``VALID`` (this is a transition that actually occurred) or
``INVALID`` (it is not).

The central danger.  It is trivially easy to build this task so that the negatives are
detectable by surface pattern -- a longer action, a novel identifier, a length delta -- rather
than by mathematics.  A family like that measures string statistics and calls it reasoning.
Every corruption operator here is therefore built to preserve the surface properties it can
preserve, is *paired* with the positive it was derived from so that every state-only feature is
balanced by construction, and declares in :data:`AXIS_PROPERTIES` exactly which invariants it
claims.  ``research/env_legal`` measures whether the claim survives contact with a shortcut.

Ground-truth tiers.  Every negative carries a :class:`GroundTruthTier`.

``TIER_B_CONSTRUCTED``
    Invalid by construction: a fact recorded in the source transition itself makes the proposed
    triple impossible.  Free, mechanical, and weaker than a kernel check.  The argument for each
    axis is spelled out in :data:`AXIS_INVALIDITY`, and each axis records its own residual risk
    in :data:`AXIS_RESIDUAL_RISK`.  Where invalidity could not be argued, the item is *discarded*
    rather than guessed at; :class:`BuildReport` counts every discard by reason.

``TIER_A_VERIFIED``
    Validity confirmed by Lean replay.  :data:`LEAN_TIER_A_REPLAY` specifies exactly what would
    run.  **Nothing in this module executes Lean.**  No item is emitted at Tier A by this
    generator; promotion is a separate, integrator-authorised job.

Sealed-split discipline.  Only ``random/train.json`` and ``corpus.jsonl`` are permitted inputs.
:func:`iter_proof_steps` stamps every step with its split and :func:`build_family` refuses any
step not marked ``train``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from random import Random
from typing import Any

from arena.canonical.schema import stable_hash
from arena.provenance import SourceProvenance, TrustTier

ENVIRONMENT_VERSION = "arena-legal-transform-v1.0.0"
ADAPTER_VERSION = "arena-leandojo-transition-adapter-v1.0.0"
GENERATOR_SEED = 20260907

#: The only permitted development split.  Anything else is a sealed-split violation.
PERMITTED_SPLIT = "train"

DONOR_DATASET = "LeanDojo Benchmark 4"
DONOR_REF = "leandojo_version=2.0.0"
DONOR_SHA = "29dcec074de168ac2bf835a77ef68bbe069194c5"
DONOR_LICENSE = "mathlib4 Apache-2.0; LeanDojo Benchmark 4 CC-BY-4.0"
EXTRACTION_PATH = "Lean 4 v4.10.0-rc1 elaborator via LeanDojo tracing (recorded transition)"
DONOR_CAVEATS = (
    "LeanDojo annotates only premises named in the tactic SYNTAX; simp sets, typeclass "
    "instances and definitional unfolding are invisible, so premise lists are lower bounds",
    "states are pretty-printed text, not elaborated terms; all parsing here is textual",
    "no item in this family has been replayed in Lean; every negative is TIER_B_CONSTRUCTED",
)


class CorruptionAxis(StrEnum):
    """Which operator produced a negative.  Positives carry no axis."""

    WRONG_PREMISE_UNIFORM = "wrong_premise_uniform"
    WRONG_PREMISE_MATCHED = "wrong_premise_matched"
    WRONG_REWRITE_DIRECTION = "wrong_rewrite_direction"
    WRONG_REWRITE_TARGET = "wrong_rewrite_target"
    WRONG_BINDER = "wrong_binder"
    VIOLATED_PRECONDITION = "violated_precondition"
    TYPE_INCOMPATIBLE_ARGUMENT = "type_incompatible_argument"
    WRONG_SUCCESSOR = "wrong_successor"


class DifficultyLevel(StrEnum):
    """Ladder by corruption subtlety, not by mathematical depth."""

    #: Control arm.  The corruption is deliberately blatant; this level is EXPECTED to be
    #: shortcut-solvable and exists so the ladder has a visible floor.  It is reported
    #: separately and never counted in the graded family's headline number.
    L0_EXPLICIT_CONTROL = "L0_EXPLICIT_CONTROL"
    L1_COARSE = "L1_COARSE"
    L2_MODERATE = "L2_MODERATE"
    L3_SUBTLE = "L3_SUBTLE"


class GroundTruthTier(StrEnum):
    A_VERIFIED = "TIER_A_VERIFIED"
    B_CONSTRUCTED = "TIER_B_CONSTRUCTED"


AXIS_LEVEL: Mapping[CorruptionAxis, DifficultyLevel] = {
    CorruptionAxis.WRONG_PREMISE_UNIFORM: DifficultyLevel.L0_EXPLICIT_CONTROL,
    # Demoted from L1 after measurement.  The only violated-precondition corruption that is
    # checkable from the recorded text alone -- naming a hypothesis absent from this state's
    # local context -- raises the action's novel-identifier count by ~0.9 on average, and a
    # shallow model over that feature separated it at 0.82 on held-out data.  That is a
    # property of the axis, not of a tunable, so it is reclassified as an explicit control
    # rather than repaired: a non-detectable precondition violation needs Lean adjudication.
    CorruptionAxis.VIOLATED_PRECONDITION: DifficultyLevel.L0_EXPLICIT_CONTROL,
    # Demoted from L1 after measurement, under the preregistered protocol's one repair.  The
    # repair (a within-proof successor derangement, replacing nearest-donor sampling) removed the
    # length tell and took the axis from 0.70 to 0.664, but the remaining shortcut is the
    # before/after token Jaccard at 0.644: a state one tactic-step from the goal state simply
    # resembles it more than a state two or more steps away.  That is intrinsic to substituting a
    # real state, and no textual donor policy can remove it -- only a generator that produces
    # states exactly one step away, which needs Lean.  Kept as an explicit control, not graded.
    CorruptionAxis.WRONG_SUCCESSOR: DifficultyLevel.L0_EXPLICIT_CONTROL,
    CorruptionAxis.WRONG_PREMISE_MATCHED: DifficultyLevel.L2_MODERATE,
    CorruptionAxis.WRONG_REWRITE_DIRECTION: DifficultyLevel.L2_MODERATE,
    CorruptionAxis.WRONG_REWRITE_TARGET: DifficultyLevel.L3_SUBTLE,
    CorruptionAxis.WRONG_BINDER: DifficultyLevel.L3_SUBTLE,
    CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT: DifficultyLevel.L3_SUBTLE,
}

AXIS_INVALIDITY: Mapping[CorruptionAxis, str] = {
    CorruptionAxis.WRONG_PREMISE_UNIFORM: (
        "the cited declaration was replaced by an unrelated library declaration with a "
        "different full name; the recorded successor is the result of applying the original"
    ),
    CorruptionAxis.WRONG_PREMISE_MATCHED: (
        "the cited declaration was replaced by a different real declaration (distinct full "
        "name and distinct final name component, so not a namespace alias); the recorded "
        "successor is the result of applying the original"
    ),
    CorruptionAxis.WRONG_REWRITE_DIRECTION: (
        "the recorded step rewrote the equation in one orientation, replacing occurrences of "
        "one side by the other; the opposite orientation replaces occurrences of the other "
        "side, so it cannot produce the recorded successor unless the two sides coincide"
    ),
    CorruptionAxis.WRONG_REWRITE_TARGET: (
        "in the recorded transition the original `at` target's hypothesis text changed and the "
        "substituted target's hypothesis text is byte-identical before and after; a tactic "
        "retargeted at an unchanged hypothesis cannot produce the recorded successor, and a "
        "rewrite that changes nothing is an error in Lean"
    ),
    CorruptionAxis.WRONG_BINDER: (
        "the recorded successor binds the introduced names to specific, textually distinct "
        "types in order; transposing two binder names would bind each to the other's type, "
        "which contradicts the recorded successor"
    ),
    CorruptionAxis.VIOLATED_PRECONDITION: (
        "the `at` clause names a hypothesis that does not occur in the recorded before-state's "
        "local context, so the tactic cannot elaborate"
    ),
    CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT: (
        "two explicit arguments whose recorded local-context types are textually distinct and "
        "mention disjoint identifiers were transposed, so the application is ill-typed"
    ),
    CorruptionAxis.WRONG_SUCCESSOR: (
        "tactic application is deterministic for a fixed environment; the recorded successor of "
        "this action at this state is a specific state, and the substituted state differs from "
        "it, so the triple is not the transition that occurred"
    ),
}

AXIS_RESIDUAL_RISK: Mapping[CorruptionAxis, str] = {
    CorruptionAxis.WRONG_PREMISE_UNIFORM: "none material; the substitute is unrelated",
    CorruptionAxis.WRONG_PREMISE_MATCHED: (
        "the substitute could be definitionally interchangeable at this site; the distinct "
        "final-name-component guard removes namespace aliases but not `simp`-equivalent lemmas"
    ),
    CorruptionAxis.WRONG_REWRITE_DIRECTION: (
        "if the equation's two sides are syntactically identical the flip is a no-op; guarded "
        "by requiring the successor to differ from the predecessor and by discarding lemmas "
        "whose final name component is a commutativity/symmetry marker, but not eliminated"
    ),
    CorruptionAxis.WRONG_REWRITE_TARGET: "none identified beyond textual parsing error",
    CorruptionAxis.WRONG_BINDER: "none identified beyond textual parsing error",
    CorruptionAxis.VIOLATED_PRECONDITION: "none identified beyond textual parsing error",
    CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT: (
        "the two recorded types could be definitionally equal despite textual difference and "
        "disjoint identifiers; this cannot be excluded without Lean"
    ),
    CorruptionAxis.WRONG_SUCCESSOR: (
        "assumes tactic determinism for a fixed environment, which holds for the tactics kept "
        "here but is an assumption rather than a check"
    ),
}


@dataclass(frozen=True, slots=True)
class AxisProperties:
    """What a corruption operator claims about the surface it leaves behind.

    ``tests/environments/test_legal_transform.py`` asserts each claim mechanically, so an
    operator cannot quietly acquire a surface tell.
    """

    #: The corrupted field is the action (otherwise the successor state).
    corrupts_action: bool
    #: The symbolic token multiset of the corrupted field is exactly preserved.
    preserves_token_multiset: bool
    #: The character length of the corrupted field is exactly preserved.
    preserves_length: bool
    #: The operator is only balanced in aggregate (equal numbers of each source polarity).
    balanced_by_design: bool
    #: The corrupted field is a permutation of the positives' fields across the whole axis, so
    #: every marginal statistic of that field is identical between the two labels by
    #: construction and no global threshold on it can carry information.
    permutes_within_axis: bool = False


AXIS_PROPERTIES: Mapping[CorruptionAxis, AxisProperties] = {
    CorruptionAxis.WRONG_PREMISE_UNIFORM: AxisProperties(True, False, False, False),
    CorruptionAxis.WRONG_PREMISE_MATCHED: AxisProperties(True, False, True, False),
    CorruptionAxis.WRONG_REWRITE_DIRECTION: AxisProperties(True, False, False, True),
    CorruptionAxis.WRONG_REWRITE_TARGET: AxisProperties(True, False, True, False),
    CorruptionAxis.WRONG_BINDER: AxisProperties(True, True, True, False),
    CorruptionAxis.VIOLATED_PRECONDITION: AxisProperties(True, False, True, False),
    CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT: AxisProperties(True, True, True, False),
    CorruptionAxis.WRONG_SUCCESSOR: AxisProperties(False, False, False, False, True),
}

#: Exactly what a Tier-A promotion would run.  NOT executed here.
LEAN_TIER_A_REPLAY: Mapping[str, Any] = {
    "status": "DESIGNED_NOT_RUN",
    "authorisation": "integrator-authorised job only; this module never invokes Lean",
    "mathlib_root": (
        "/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/"
        "leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
    ),
    "toolchain": "leanprover/lean4:v4.10.0-rc1",
    "mathlib_commit": DONOR_SHA,
    "harness": "LeanDojo Dojo replay, one Dojo per theorem, tactics fed in recorded order",
    "command": (
        "cd <mathlib_root> && "
        "CONTAINER=native "
        "LEAN_PATH=<mathlib_root>/.lake/build/lib:<mathlib_root>/.lake/packages/*/.lake/build/lib "
        "<venv>/bin/python -m arena.cli replay-legal-transform "
        "--manifest artifacts/manifests/legal_transform_manifest.json "
        "--mathlib-root <mathlib_root> "
        "--timeout-seconds 60 --max-theorems 300 --jobs 4 "
        "--out research/env_legal/tier_a_replay.jsonl"
    ),
    "per_item_procedure": [
        "open a Dojo at (file_path, full_name) from the item's provenance",
        "replay steps 0..step_index-1 with their recorded tactics to reach state_before",
        "assert the reached state's pretty-print equals the item's state_before verbatim; "
        "on mismatch record REPLAY_DESYNC and do not promote the item",
        "for a POSITIVE: run the item's action; promote to TIER_A_VERIFIED iff the run "
        "succeeds and the resulting pretty-print equals the item's state_after verbatim",
        "for a NEGATIVE: run the item's action; promote to TIER_A_VERIFIED iff the run "
        "raises a LeanError/TimeoutError, or succeeds with a pretty-print differing from the "
        "item's state_after; if it succeeds and matches, the constructed negative was WRONG "
        "-- record CONSTRUCTED_NEGATIVE_REFUTED and drop the item and audit its axis",
    ],
    "budget": {
        "historical_replay_yield": "32/100 transitions replayed successfully",
        "implication": "expect ~32% of attempted items to reach TIER_A; a 1,000-item Tier-A "
        "tier therefore needs ~3,100 attempted replays",
        "wall_clock_estimate": "at ~20 s/theorem with 4 workers, ~3,100 items across ~900 "
        "theorems is roughly 1.3 h; this is why it is a separate job",
    },
    "what_tier_a_would_and_would_not_establish": (
        "It would establish that the positive transition really replays and that the negative "
        "really fails or diverges.  It would NOT establish that the negative is mathematically "
        "meaningless, nor that the theorem is true, nor anything about a different Lean version."
    ),
}


# ---------------------------------------------------------------------------
# text primitives
# ---------------------------------------------------------------------------

_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?]*|\d+|[^\sA-Za-z0-9_]")
#: A Lean local-hypothesis name: no dots, may carry the inaccessible marker and subscripts.
_ATOM_RE = re.compile(r"[A-Za-z_α-ωΑ-Ω][^\s:(){}\[\],.]*")
#: A dotted library name as it appears inside a tactic.
_DOTTED_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?₀-₉¹²³⁰-ⁿ.]*")
_TAG_RE = re.compile(r"<a>(.*?)</a>", re.DOTALL)
_TURNSTILE = "⊢"
_INACCESSIBLE = "✝"
_LEFT_ARROW = "←"

#: Lemma final-name components that suggest the equation's two sides are interchangeable.
#: Used only to DISCARD conservatively, never to declare something invalid.
_SYMMETRIC_MARKERS = ("comm", "symm", "swap", "rev", "flip")


def symbolic_tokens(text: str) -> list[str]:
    """Deterministic token proxy: identifiers, numerals and single punctuation."""

    return _SYMBOL_RE.findall(text)


def token_multiset(text: str) -> Counter[str]:
    return Counter(symbolic_tokens(text))


def strip_premise_tags(annotated: str) -> str:
    """Remove LeanDojo's ``<a>``/``</a>`` premise markers, leaving the tactic surface."""

    return _TAG_RE.sub(lambda match: match.group(1), annotated)


def premise_span_texts(annotated: str) -> list[str]:
    """The surface text of each premise mention, in citation order."""

    return _TAG_RE.findall(annotated)


def swap_identifiers(text: str, left: str, right: str) -> str:
    """Swap two whole-token identities everywhere in ``text``.

    This is the text-domain counterpart of
    :func:`arena.environments.formal_structural.relabel`, which performs the same swap on a
    :class:`~arena.canonical.schema.CanonicalExpression`.  Both preserve the token multiset and
    the character length exactly when ``left`` and ``right`` have equal length, which is why a
    reader that keys on surface statistics cannot see the change.
    """

    if left == right:
        return text
    pattern = re.compile(
        r"(?<![A-Za-z0-9_'₀-₉.])(" + re.escape(left) + "|" + re.escape(right) + r")"
        r"(?![A-Za-z0-9_'₀-₉])"
    )
    return pattern.sub(lambda m: right if m.group(1) == left else left, text)


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """One local-context entry of a pretty-printed goal."""

    names: tuple[str, ...]
    type_text: str


def goal_blocks(state: str) -> tuple[str, ...]:
    """Split a pretty-printed state into its goals.  LeanDojo joins goals with a blank line."""

    return tuple(block for block in state.split("\n\n") if block.strip())


def parse_hypotheses(goal_block: str) -> tuple[Hypothesis, ...]:
    """Parse the local context of a single goal block.

    A hypothesis starts at column 0 with ``names : type``; continuation lines are indented.  The
    ``⊢`` line ends the context.  Anything that does not parse is simply not returned, so a
    caller that needs a name to exist will discard the item rather than assume.
    """

    entries: list[Hypothesis] = []
    pending_names: tuple[str, ...] | None = None
    pending_type: list[str] = []
    for line in goal_block.split("\n"):
        if line.startswith(_TURNSTILE):
            break
        if line[:1].isspace():
            if pending_names is not None:
                pending_type.append(line.strip())
            continue
        head, separator, tail = line.partition(" : ")
        if not separator or not head.strip():
            continue
        names = tuple(head.split())
        if not all(_ATOM_RE.fullmatch(name) for name in names):
            continue
        if pending_names is not None:
            entries.append(Hypothesis(pending_names, "\n".join(pending_type)))
        pending_names = names
        pending_type = [tail.strip()]
    if pending_names is not None:
        entries.append(Hypothesis(pending_names, "\n".join(pending_type)))
    return tuple(entries)


def hypothesis_types(state: str) -> dict[str, str]:
    """Map every local-context name in every goal to its recorded type text."""

    found: dict[str, str] = {}
    for block in goal_blocks(state):
        for entry in parse_hypotheses(block):
            for name in entry.names:
                found.setdefault(name, entry.type_text)
    return found


def goal_text(state: str) -> str:
    """The text after the last turnstile."""

    return state.rsplit(_TURNSTILE, 1)[1].strip() if _TURNSTILE in state else state.strip()


# ---------------------------------------------------------------------------
# source records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProofStep:
    """One recorded LeanDojo transition, carrying enough identity to be excluded or audited."""

    split: str
    file_path: str
    full_name: str
    step_index: int
    n_steps: int
    tactic: str
    annotated: str
    premises: tuple[str, ...]
    state_before: str
    state_after: str

    @property
    def theorem_key(self) -> str:
        return f"{self.file_path}::{self.full_name}"


def iter_proof_steps(theorems: Iterable[Mapping[str, Any]], *, split: str) -> Iterator[ProofStep]:
    """Flatten raw LeanDojo theorem records into steps, stamping the split on every one."""

    for theorem in theorems:
        tactics = theorem.get("traced_tactics") or []
        for position, tactic in enumerate(tactics):
            annotated_pair = tactic.get("annotated_tactic") or [tactic.get("tactic", ""), []]
            premises = tuple(
                str(entry.get("full_name", ""))
                for entry in annotated_pair[1]
                if entry.get("full_name")
            )
            yield ProofStep(
                split=split,
                file_path=str(theorem["file_path"]),
                full_name=str(theorem["full_name"]),
                step_index=position,
                n_steps=len(tactics),
                tactic=str(tactic["tactic"]),
                annotated=str(annotated_pair[0]),
                premises=premises,
                state_before=str(tactic["state_before"]),
                state_after=str(tactic["state_after"]),
            )


def group_proofs(steps: Iterable[ProofStep]) -> dict[str, list[ProofStep]]:
    proofs: dict[str, list[ProofStep]] = {}
    for step in steps:
        proofs.setdefault(step.theorem_key, []).append(step)
    for bucket in proofs.values():
        bucket.sort(key=lambda item: item.step_index)
    return proofs


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransformItem:
    """One rendered decision.  ``axis`` is ``None`` exactly when ``valid`` is true."""

    item_id: str
    pair_id: str
    theorem_key: str
    valid: bool
    state_before: str
    action: str
    state_after: str
    level: DifficultyLevel
    tier: GroundTruthTier
    axis: CorruptionAxis | None
    constructed_invalidity: str
    provenance: SourceProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "pair_id": self.pair_id,
            "theorem_key": self.theorem_key,
            "valid": self.valid,
            "level": self.level.value,
            "tier": self.tier.value,
            "axis": self.axis.value if self.axis is not None else None,
            "constructed_invalidity": self.constructed_invalidity,
            "provenance": self.provenance.to_dict(),
        }


ITEM_TEMPLATE = "PROOF STATE:\n{before}\n\nPROPOSED ACTION:\n{action}\n\nPROPOSED RESULT:\n{after}"


def render(item: TransformItem) -> str:
    """The only text a reader may see.  No label, tier, axis, provenance or source identity."""

    return ITEM_TEMPLATE.format(
        before=item.state_before, action=item.action, after=item.state_after
    )


# ---------------------------------------------------------------------------
# corruption operators
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Corruption:
    """A successful corruption: the negative's action and successor, plus its axis."""

    axis: CorruptionAxis
    action: str
    state_after: str


class DiscardKind(StrEnum):
    """Why a step produced no item.  The three kinds mean very different things.

    ``ELIGIBILITY``
        The step's shape does not match this axis at all -- an ``intro`` operator meeting an
        ``exact``.  Not a refusal; it is simply the wrong population.

    ``INVALIDITY``
        The step is shape-eligible, but the recorded transition does not support an argument
        that the corrupted triple would be invalid.  These are the discards the family's honesty
        depends on: the item is thrown away rather than labelled on a guess.

    ``SURFACE``
        The step is shape-eligible and invalidity is arguable, but no donor existed that keeps
        the surface statistics matched.  Discarded to protect the shortcut ceiling, not because
        the mathematics was unclear.
    """

    ELIGIBILITY = "eligibility"
    INVALIDITY = "invalidity"
    SURFACE = "surface"


@dataclass(frozen=True, slots=True)
class Discard:
    """A refused corruption.  Every one is counted, none is silently swallowed."""

    kind: DiscardKind
    reason: str

    @property
    def label(self) -> str:
        return f"{self.kind.value}:{self.reason}"


CorruptionResult = Corruption | Discard


@dataclass(frozen=True, slots=True)
class PremiseIndex:
    """Read-only view of ``corpus.jsonl`` plus a train-only citation-frequency prior."""

    by_file: Mapping[str, tuple[str, ...]]
    all_names: tuple[str, ...]
    train_citation_frequency: Mapping[str, int]

    def frequency(self, name: str) -> int:
        return self.train_citation_frequency.get(name, 0)


def _final_component(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _frequency_bucket(count: int) -> int:
    return count.bit_length()


def _name_words(name: str) -> set[str]:
    words: set[str] = set()
    for chunk in re.split(r"[._]+", name):
        for piece in re.findall(r"[A-Z]?[a-z0-9']+|[A-Z]+(?![a-z])", chunk):
            words.add(piece.lower())
    return words


def _pick(rng: Random, options: Sequence[str]) -> str:
    return options[rng.randrange(len(options))]


def corrupt_wrong_premise(
    step: ProofStep,
    proof: Sequence[ProofStep],
    index: PremiseIndex,
    rng: Random,
    *,
    matched: bool,
) -> CorruptionResult:
    """Replace one cited declaration with a different real one.

    ``matched=True`` is the graded operator: the substitute must come from the same proof or the
    same source file, and must have exactly the same surface length, the same train-citation
    frequency bucket, and the same lexical overlap with the state as the original.  Those three
    constraints are precisely the shortcuts a prior audit found solve premise choice at 0.65-0.86
    when the distractor is drawn uniformly.  ``matched=False`` is the L0 control that deliberately
    drops them, and is expected to be shortcut-solvable.
    """

    axis = CorruptionAxis.WRONG_PREMISE_MATCHED if matched else CorruptionAxis.WRONG_PREMISE_UNIFORM
    if "\n" in step.tactic:
        return Discard(DiscardKind.ELIGIBILITY, "multiline_tactic")
    spans = premise_span_texts(step.annotated)
    if len(spans) != len(step.premises) or not spans:
        return Discard(DiscardKind.ELIGIBILITY, "premise_span_misalignment")
    surface = strip_premise_tags(step.annotated)
    if surface != step.tactic:
        return Discard(DiscardKind.ELIGIBILITY, "annotation_surface_mismatch")
    candidates = [
        position
        for position, span in enumerate(spans)
        if span == step.premises[position] and surface.count(span) == 1
    ]
    if not candidates:
        return Discard(DiscardKind.ELIGIBILITY, "no_unambiguous_full_name_span")
    position = candidates[rng.randrange(len(candidates))]
    original = step.premises[position]
    state_words = _name_words(step.state_before)
    original_overlap = len(_name_words(original) & state_words)
    original_bucket = _frequency_bucket(index.frequency(original))

    if matched:
        pool: list[str] = []
        for other in proof:
            if other.step_index != step.step_index:
                pool.extend(other.premises)
        pool.extend(index.by_file.get(step.file_path, ()))
        distinct: list[str] = []
        seen: set[str] = set()
        for name in pool:
            if name in seen:
                continue
            seen.add(name)
            if name == original or _final_component(name) == _final_component(original):
                continue
            distinct.append(name)
        if not distinct:
            return Discard(DiscardKind.INVALIDITY, "no_donor_with_a_distinct_final_component")
        donors = sorted(
            name
            for name in distinct
            if len(name) == len(original)
            and _frequency_bucket(index.frequency(name)) == original_bucket
            and len(_name_words(name) & state_words) == original_overlap
        )
        if not donors:
            return Discard(DiscardKind.SURFACE, "no_length_frequency_overlap_matched_donor")
    else:
        donors = sorted(
            {index.all_names[rng.randrange(len(index.all_names))] for _ in range(32)} - {original}
        )
        donors = [name for name in donors if _final_component(name) != _final_component(original)]
        if not donors:
            return Discard(DiscardKind.INVALIDITY, "no_uniform_donor_with_a_distinct_name")

    substitute = _pick(rng, donors)
    action = surface.replace(original, substitute, 1)
    if action == surface:
        return Discard(DiscardKind.INVALIDITY, "substitution_was_a_no_op")
    return Corruption(axis, action, step.state_after)


_AT_RE = re.compile(r"\bat\s+(?P<target>[^\s\[\]]+)\s*$")


def _at_target(tactic: str) -> str | None:
    if "\n" in tactic:
        return None
    match = _AT_RE.search(tactic)
    if match is None:
        return None
    target = match.group("target")
    if target in {"*", "\u22a2"} or not _ATOM_RE.fullmatch(target):
        return None
    return target


def corrupt_wrong_rewrite_target(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Retarget an ``at h`` clause to a hypothesis the recorded transition left untouched.

    The invalidity is read straight out of the transition: ``h``'s recorded type text changed and
    the substitute's did not.  A tactic aimed at an unchanged hypothesis cannot produce a
    successor in which that hypothesis is unchanged and a *different* one is rewritten, and a
    rewrite that changes nothing is an error in Lean rather than a no-op.
    """

    target = _at_target(step.tactic)
    if target is None:
        return Discard(DiscardKind.ELIGIBILITY, "no_single_at_target")
    before_types = hypothesis_types(step.state_before)
    after_types = hypothesis_types(step.state_after)
    if target not in before_types or target not in after_types:
        return Discard(DiscardKind.ELIGIBILITY, "at_target_absent_from_a_parsed_context")
    if before_types[target] == after_types[target]:
        return Discard(DiscardKind.INVALIDITY, "at_target_text_unchanged_by_the_step")
    untouched = [
        name
        for name, text in before_types.items()
        if name != target
        and _INACCESSIBLE not in name
        and name in after_types
        and after_types[name] == text
    ]
    if not untouched:
        return Discard(DiscardKind.INVALIDITY, "no_provably_untouched_hypothesis")
    donors = sorted(name for name in untouched if len(name) == len(target))
    if not donors:
        return Discard(DiscardKind.SURFACE, "no_length_matched_untouched_hypothesis")
    substitute = _pick(rng, donors)
    action = step.tactic[: -len(target)] + substitute
    if action == step.tactic:
        return Discard(DiscardKind.INVALIDITY, "substitution_was_a_no_op")
    return Corruption(CorruptionAxis.WRONG_REWRITE_TARGET, action, step.state_after)


def corrupt_violated_precondition(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Aim an ``at`` clause at a hypothesis that exists elsewhere in the proof but not here.

    The name is real and same-proof, so it is not lexical nonsense; it is simply absent from this
    state's local context, which makes the tactic unelaborable.  This is the coarsest axis in the
    family and is the one most exposed to an identifier-novelty predictor, which is exactly why
    it is placed at L1 and measured separately.
    """

    target = _at_target(step.tactic)
    if target is None:
        return Discard(DiscardKind.ELIGIBILITY, "no_single_at_target")
    present = set(hypothesis_types(step.state_before))
    if target not in present:
        return Discard(DiscardKind.ELIGIBILITY, "at_target_absent_from_a_parsed_context")
    absent: set[str] = set()
    for other in proof:
        if other.step_index == step.step_index:
            continue
        for name in hypothesis_types(other.state_before):
            if name not in present and _INACCESSIBLE not in name and name != target:
                absent.add(name)
    if not absent:
        return Discard(DiscardKind.INVALIDITY, "no_same_proof_name_absent_from_this_context")
    donors = sorted(name for name in absent if len(name) == len(target))
    if not donors:
        return Discard(DiscardKind.SURFACE, "no_length_matched_absent_hypothesis")
    substitute = _pick(rng, donors)
    action = step.tactic[: -len(target)] + substitute
    return Corruption(CorruptionAxis.VIOLATED_PRECONDITION, action, step.state_after)


_RW_RE = re.compile(
    r"^(?P<head>rw|rwa|erw|simp_rw)\s*\[\s*(?P<arrow>\u2190\s*)?(?P<lemma>[^\[\],]+?)\s*\]$"
)


def corrupt_wrong_rewrite_direction(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Flip the orientation of a single-lemma rewrite.

    The ``\u2190`` token is itself a surface cue, so this operator is only sound in aggregate:
    :func:`build_family` keeps equal numbers of forward-sourced and reverse-sourced pairs, which
    makes "the action contains an arrow" exactly uninformative.  :data:`AXIS_PROPERTIES` records
    that this axis is ``balanced_by_design`` rather than surface-preserving.
    """

    match = _RW_RE.match(step.tactic.strip())
    if match is None:
        return Discard(DiscardKind.ELIGIBILITY, "not_a_single_lemma_rewrite")
    if step.state_before == step.state_after:
        return Discard(DiscardKind.INVALIDITY, "no_op_transition")
    lemma = match.group("lemma").strip()
    final = _final_component(lemma).lower()
    if any(marker in final for marker in _SYMMETRIC_MARKERS):
        return Discard(DiscardKind.INVALIDITY, "symmetry_suspicious_lemma")
    head = match.group("head")
    flipped = f"[{lemma}]" if match.group("arrow") else f"[{_LEFT_ARROW} {lemma}]"
    action = f"{head} {flipped}"
    return Corruption(CorruptionAxis.WRONG_REWRITE_DIRECTION, action, step.state_after)


_BINDER_RE = re.compile(r"^(?P<head>intro|intros|rintro)\s+(?P<binders>[^\n]+)$")


def corrupt_wrong_binder(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Transpose two introduced binder names whose recorded types differ.

    Token-multiset preserving and length preserving: the action's characters are a permutation of
    the original's.  The recorded successor pins each name to a specific type, so the transposed
    action contradicts it outright.
    """

    match = _BINDER_RE.match(step.tactic.strip())
    if match is None:
        return Discard(DiscardKind.ELIGIBILITY, "not_a_simple_intro")
    binders = match.group("binders").split()
    if len(binders) < 2 or not all(_ATOM_RE.fullmatch(name) for name in binders):
        return Discard(DiscardKind.ELIGIBILITY, "binder_pattern_not_simple_names")
    before_names = set(hypothesis_types(step.state_before))
    after_types = hypothesis_types(step.state_after)
    introduced = [
        name
        for name in binders
        if name in after_types and name not in before_names and _INACCESSIBLE not in name
    ]
    typed = [
        (left, right)
        for position, left in enumerate(introduced)
        for right in introduced[position + 1 :]
        if after_types[left] != after_types[right]
    ]
    if not typed:
        return Discard(DiscardKind.INVALIDITY, "no_binder_pair_with_distinct_recorded_types")
    pairs = sorted({pair for pair in typed if len(pair[0]) == len(pair[1])})
    if not pairs:
        return Discard(DiscardKind.SURFACE, "no_length_matched_binder_pair")
    left, right = pairs[rng.randrange(len(pairs))]
    action = swap_identifiers(step.tactic, left, right)
    if action == step.tactic:
        return Discard(DiscardKind.INVALIDITY, "swap_was_a_no_op")
    return Corruption(CorruptionAxis.WRONG_BINDER, action, step.state_after)


_APPLY_RE = re.compile(r"^(?P<head>exact|apply|refine)\s+(?P<body>[^\n]+)$")


def corrupt_type_incompatible_argument(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Transpose two explicit arguments whose recorded local types are textually disjoint.

    Also token-multiset and length preserving.  Requiring the two type texts to mention disjoint
    identifier sets is what turns "probably ill-typed" into an argument worth making: two types
    with no identifier in common are not plausibly definitionally equal.  Only Lean can settle
    it, which is why :data:`AXIS_RESIDUAL_RISK` records the gap rather than waving it away.
    """

    match = _APPLY_RE.match(step.tactic.strip())
    if match is None:
        return Discard(DiscardKind.ELIGIBILITY, "not_an_application_head")
    atoms = match.group("body").split()
    types = hypothesis_types(step.state_before)
    usable = [
        atom
        for atom in atoms
        if atom in types and _INACCESSIBLE not in atom and _ATOM_RE.fullmatch(atom)
    ]
    if len(set(usable)) < 2:
        return Discard(DiscardKind.ELIGIBILITY, "fewer_than_two_context_arguments")
    disjoint: list[tuple[str, str]] = []
    for position, left in enumerate(usable):
        for right in usable[position + 1 :]:
            if left == right:
                continue
            left_type, right_type = types[left], types[right]
            if left_type == right_type:
                continue
            if set(_DOTTED_RE.findall(left_type)) & set(_DOTTED_RE.findall(right_type)):
                continue
            disjoint.append((left, right))
    if not disjoint:
        return Discard(DiscardKind.INVALIDITY, "no_argument_pair_with_disjoint_recorded_types")
    pairs = sorted({pair for pair in disjoint if len(pair[0]) == len(pair[1])})
    if not pairs:
        return Discard(DiscardKind.SURFACE, "no_length_matched_argument_pair")
    left, right = pairs[rng.randrange(len(pairs))]
    action = swap_identifiers(step.tactic, left, right)
    if action == step.tactic:
        return Discard(DiscardKind.INVALIDITY, "swap_was_a_no_op")
    return Corruption(CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT, action, step.state_after)


def successor_derangement(proof: Sequence[ProofStep]) -> dict[int, str]:
    """Map each step of a proof to a *different* step's recorded successor.

    Sampling a donor state is not good enough.  Proof states accumulate hypotheses, so any
    nearest-by-length donor is systematically the *longer* neighbour: a development run measured
    donors longer than the truth 128 times against 71 shorter, a median of +80 characters, and a
    single fitted threshold on the result-state length separated the labels at 0.70.

    A derangement removes that by construction rather than by tuning.  The successors are sorted
    by length and cyclically shifted by one, so the multiset of result states shown with the
    negatives is *exactly* the multiset shown with the positives, and every marginal statistic of
    the result state -- length, token count, hypothesis count, anything -- is identical between
    the two labels.  The shift is by one position in length order, so each donor is also a
    nearest available neighbour, which keeps the item hard rather than merely fair.
    """

    successors = {step.step_index: step.state_after for step in proof if step.state_after.strip()}
    distinct: dict[str, int] = {}
    for index in sorted(successors):
        distinct.setdefault(successors[index], index)
    order = sorted(distinct.values(), key=lambda index: (len(successors[index]), index))
    if len(order) < 2:
        return {}
    return {
        order[position]: successors[order[(position + 1) % len(order)]]
        for position in range(len(order))
    }


def corrupt_wrong_successor(
    step: ProofStep, proof: Sequence[ProofStep], index: PremiseIndex, rng: Random
) -> CorruptionResult:
    """Show a real successor from a *different* step of the same proof.

    A prior audit measured token overlap with the before-state solving 4-way successor choice at
    0.61 with same-proof distractors and 0.99 with foreign ones, so the donor must be same-proof.
    :func:`successor_derangement` then decides *which* same-proof state, permuting rather than
    sampling so that no marginal statistic of the result state can carry the label.
    """

    mapping = successor_derangement(proof)
    substitute = mapping.get(step.step_index)
    if substitute is None:
        return Discard(DiscardKind.ELIGIBILITY, "no_same_proof_successor_derangement")
    if substitute == step.state_after:
        return Discard(DiscardKind.INVALIDITY, "derangement_returned_the_true_successor")
    if substitute == step.state_before:
        return Discard(DiscardKind.SURFACE, "donor_equals_the_before_state")
    return Corruption(CorruptionAxis.WRONG_SUCCESSOR, step.tactic, substitute)


CORRUPTORS: Mapping[CorruptionAxis, Any] = {
    CorruptionAxis.WRONG_PREMISE_UNIFORM: lambda s, p, i, r: corrupt_wrong_premise(
        s, p, i, r, matched=False
    ),
    CorruptionAxis.WRONG_PREMISE_MATCHED: lambda s, p, i, r: corrupt_wrong_premise(
        s, p, i, r, matched=True
    ),
    CorruptionAxis.WRONG_REWRITE_DIRECTION: corrupt_wrong_rewrite_direction,
    CorruptionAxis.WRONG_REWRITE_TARGET: corrupt_wrong_rewrite_target,
    CorruptionAxis.WRONG_BINDER: corrupt_wrong_binder,
    CorruptionAxis.VIOLATED_PRECONDITION: corrupt_violated_precondition,
    CorruptionAxis.TYPE_INCOMPATIBLE_ARGUMENT: corrupt_type_incompatible_argument,
    CorruptionAxis.WRONG_SUCCESSOR: corrupt_wrong_successor,
}


# ---------------------------------------------------------------------------
# family construction
# ---------------------------------------------------------------------------


class SealedSplitViolation(RuntimeError):
    """Raised if a step from anything but ``random/train.json`` reaches the generator."""


@dataclass(slots=True)
class BuildReport:
    """Everything an auditor needs to see that nothing was quietly dropped or guessed."""

    steps_considered: int = 0
    attempts: Counter[str] = field(default_factory=Counter)
    candidates: Counter[str] = field(default_factory=Counter)
    accepted: Counter[str] = field(default_factory=Counter)
    discards: Counter[str] = field(default_factory=Counter)
    truncated_axes: set[str] = field(default_factory=set)
    dropped_for_polarity_balance: int = 0

    @property
    def total_attempts(self) -> int:
        return sum(self.attempts.values())

    @property
    def total_candidates(self) -> int:
        return sum(self.candidates.values())

    @property
    def total_accepted(self) -> int:
        return sum(self.accepted.values())

    @property
    def discard_rate(self) -> float:
        """Share of attempted corruptions refused because invalidity could not be argued.

        Measured against ``candidates``, not ``accepted``: a candidate dropped later by the
        per-axis cap or the polarity balance was a sound item, not a failed construction.
        """

        if not self.total_attempts:
            return float("nan")
        return 1.0 - self.total_candidates / self.total_attempts

    def axis_discard_rate(self, axis: str) -> float:
        attempted = self.attempts.get(axis, 0)
        if not attempted:
            return float("nan")
        return 1.0 - self.candidates.get(axis, 0) / attempted

    def discards_of_kind(self, axis: str, kind: DiscardKind) -> int:
        prefix = f"{axis}|{kind.value}:"
        return sum(count for label, count in self.discards.items() if label.startswith(prefix))

    def eligible_attempts(self, axis: str) -> int:
        """Attempts whose step actually had the shape this axis operates on."""

        return self.attempts.get(axis, 0) - self.discards_of_kind(axis, DiscardKind.ELIGIBILITY)

    def invalidity_discard_rate(self, axis: str) -> float:
        """The number that matters: eligible steps thrown away rather than guessed at."""

        eligible = self.eligible_attempts(axis)
        if eligible <= 0:
            return float("nan")
        return self.discards_of_kind(axis, DiscardKind.INVALIDITY) / eligible

    def surface_discard_rate(self, axis: str) -> float:
        eligible = self.eligible_attempts(axis)
        if eligible <= 0:
            return float("nan")
        return self.discards_of_kind(axis, DiscardKind.SURFACE) / eligible

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps_considered": self.steps_considered,
            "attempts_per_axis": dict(sorted(self.attempts.items())),
            "candidates_per_axis": dict(sorted(self.candidates.items())),
            "accepted_per_axis": dict(sorted(self.accepted.items())),
            "eligible_attempts_per_axis": {
                axis: self.eligible_attempts(axis) for axis in sorted(self.attempts)
            },
            "discard_rate_per_axis_over_all_attempts": {
                axis: round(self.axis_discard_rate(axis), 6) for axis in sorted(self.attempts)
            },
            "invalidity_discard_rate_per_axis": {
                axis: round(self.invalidity_discard_rate(axis), 6) for axis in sorted(self.attempts)
            },
            "surface_discard_rate_per_axis": {
                axis: round(self.surface_discard_rate(axis), 6) for axis in sorted(self.attempts)
            },
            "axes_whose_attempt_window_was_truncated_by_the_cap": sorted(self.truncated_axes),
            "discards_by_reason": dict(sorted(self.discards.items())),
            "dropped_for_polarity_balance": self.dropped_for_polarity_balance,
            "total_attempts": self.total_attempts,
            "total_eligible_attempts": sum(self.eligible_attempts(axis) for axis in self.attempts),
            "total_invalidity_discards": sum(
                self.discards_of_kind(axis, DiscardKind.INVALIDITY) for axis in self.attempts
            ),
            "total_surface_discards": sum(
                self.discards_of_kind(axis, DiscardKind.SURFACE) for axis in self.attempts
            ),
            "total_candidates": self.total_candidates,
            "total_accepted": self.total_accepted,
            "discard_rate": round(self.discard_rate, 6) if self.total_attempts else None,
        }


def _provenance(
    step: ProofStep, canonical: str, tier: GroundTruthTier, verifier: str
) -> SourceProvenance:
    record = stable_hash(
        {
            "file_path": step.file_path,
            "full_name": step.full_name,
            "step_index": step.step_index,
            "tactic": step.tactic,
            "state_before": step.state_before,
            "state_after": step.state_after,
        }
    )
    return SourceProvenance(
        source_repo=DONOR_DATASET,
        source_ref=DONOR_REF,
        source_sha=DONOR_SHA,
        source_path=f"{PERMITTED_SPLIT}:{step.file_path}",
        source_item_id=f"{step.theorem_key}#{step.step_index}",
        source_record_sha256=record,
        license=DONOR_LICENSE,
        trust_tier=(
            TrustTier.A_NATIVE_VERIFIED
            if tier is GroundTruthTier.A_VERIFIED
            else TrustTier.B_INDEPENDENTLY_REVERIFIED
        ),
        extraction_path=EXTRACTION_PATH,
        verifier=verifier,
        adapter_version=ADAPTER_VERSION,
        canonicalization_sha256=canonical,
        caveats=DONOR_CAVEATS,
    )


def _make_pair(step: ProofStep, corruption: Corruption) -> tuple[TransformItem, TransformItem]:
    axis = corruption.axis
    level = AXIS_LEVEL[axis]
    pair_id = (
        "lt-pair:"
        + stable_hash(
            {
                "k": step.theorem_key,
                "i": step.step_index,
                "a": axis.value,
                "action": corruption.action,
                "after": corruption.state_after,
            }
        )[:16]
    )
    tier = GroundTruthTier.B_CONSTRUCTED
    positive_canonical = stable_hash(
        {"b": step.state_before, "a": step.tactic, "s": step.state_after, "v": True}
    )
    negative_canonical = stable_hash(
        {"b": step.state_before, "a": corruption.action, "s": corruption.state_after, "v": False}
    )
    positive = TransformItem(
        item_id="lt:" + positive_canonical[:16],
        pair_id=pair_id,
        theorem_key=step.theorem_key,
        valid=True,
        state_before=step.state_before,
        action=step.tactic,
        state_after=step.state_after,
        level=level,
        tier=tier,
        axis=None,
        constructed_invalidity="",
        provenance=_provenance(
            step,
            positive_canonical,
            tier,
            "LeanDojo traced transition (recorded, not replayed by Arena)",
        ),
    )
    negative = TransformItem(
        item_id="lt:" + negative_canonical[:16],
        pair_id=pair_id,
        theorem_key=step.theorem_key,
        valid=False,
        state_before=step.state_before,
        action=corruption.action,
        state_after=corruption.state_after,
        level=level,
        tier=tier,
        axis=axis,
        constructed_invalidity=AXIS_INVALIDITY[axis],
        provenance=_provenance(
            step,
            negative_canonical,
            tier,
            f"arena constructed-invalidity argument ({axis.value})",
        ),
    )
    return positive, negative


def build_family(
    proofs: Mapping[str, Sequence[ProofStep]],
    index: PremiseIndex,
    *,
    seed: int = GENERATOR_SEED,
    per_axis_cap: int | None = None,
    axes: Sequence[CorruptionAxis] | None = None,
) -> tuple[tuple[TransformItem, ...], BuildReport]:
    """Emit matched (positive, negative) pairs, one pair per accepted corruption.

    Pairing is the family's main structural defence: both members share a state, so every
    predictor that reads only the state -- length, hypothesis count, goal shape -- is at exactly
    0.5 by construction and cannot contribute.  Labels are therefore exactly balanced, and
    ``label_position`` is defeated by the final deterministic shuffle.
    """

    report = BuildReport()
    selected = tuple(axes) if axes is not None else tuple(CorruptionAxis)
    per_axis: dict[CorruptionAxis, list[tuple[ProofStep, Corruption]]] = {a: [] for a in selected}
    for key in sorted(proofs):
        proof = proofs[key]
        for step in proof:
            if step.split != PERMITTED_SPLIT:
                raise SealedSplitViolation(
                    f"{step.theorem_key}#{step.step_index} is split={step.split!r}; only "
                    f"{PERMITTED_SPLIT!r} may be used to build this family"
                )
            report.steps_considered += 1
            for axis in selected:
                if per_axis_cap is not None and len(per_axis[axis]) >= per_axis_cap * 3:
                    report.truncated_axes.add(axis.value)
                    continue
                rng = Random(f"{seed}|{axis.value}|{step.theorem_key}|{step.step_index}")
                report.attempts[axis.value] += 1
                outcome: CorruptionResult = CORRUPTORS[axis](step, proof, index, rng)
                if isinstance(outcome, Discard):
                    report.discards[f"{axis.value}|{outcome.label}"] += 1
                    continue
                report.candidates[axis.value] += 1
                per_axis[axis].append((step, outcome))

    items: list[TransformItem] = []
    for axis in selected:
        chosen = _balance_axis(axis, per_axis[axis], report)
        if per_axis_cap is not None and len(chosen) > per_axis_cap:
            chosen = chosen[:per_axis_cap]
        for step, corruption in chosen:
            positive, negative = _make_pair(step, corruption)
            items.append(positive)
            items.append(negative)
        report.accepted[axis.value] = len(chosen)

    shuffler = Random(f"{seed}|shuffle")
    ordered = sorted(items, key=lambda item: item.item_id)
    shuffler.shuffle(ordered)
    return tuple(ordered), report


def _balance_axis(
    axis: CorruptionAxis,
    candidates: list[tuple[ProofStep, Corruption]],
    report: BuildReport,
) -> list[tuple[ProofStep, Corruption]]:
    """Enforce the per-axis polarity balance that a surface-visible operator needs.

    Only :attr:`CorruptionAxis.WRONG_REWRITE_DIRECTION` needs it today: the ``←`` token is
    visible, so forward-sourced and reverse-sourced pairs must be equinumerous or the token
    predicts the label.
    """

    ordered = sorted(candidates, key=lambda pair: (pair[0].theorem_key, pair[0].step_index))
    if not AXIS_PROPERTIES[axis].balanced_by_design:
        return ordered
    forward = [pair for pair in ordered if _LEFT_ARROW not in pair[0].tactic]
    reverse = [pair for pair in ordered if _LEFT_ARROW in pair[0].tactic]
    size = min(len(forward), len(reverse))
    report.dropped_for_polarity_balance += len(ordered) - 2 * size
    merged: list[tuple[ProofStep, Corruption]] = []
    for position in range(size):
        merged.append(forward[position])
        merged.append(reverse[position])
    return merged


# ---------------------------------------------------------------------------
# audit helpers
# ---------------------------------------------------------------------------


def axis_subset(items: Sequence[TransformItem], axis: CorruptionAxis) -> tuple[TransformItem, ...]:
    """The balanced binary problem for one axis: its negatives and their paired positives."""

    pairs = {item.pair_id for item in items if item.axis is axis}
    return tuple(item for item in items if item.pair_id in pairs)


def level_subset(
    items: Sequence[TransformItem], levels: Sequence[DifficultyLevel]
) -> tuple[TransformItem, ...]:
    wanted = set(levels)
    return tuple(item for item in items if item.level in wanted)


def group_split(
    items: Sequence[TransformItem], *, seed: int = GENERATOR_SEED, heldout_fraction: float = 0.5
) -> tuple[tuple[TransformItem, ...], tuple[TransformItem, ...]]:
    """Split by theorem, never by item, so a pair can never straddle the two sides."""

    keys = sorted({item.theorem_key for item in items})
    rng = Random(f"{seed}|group-split")
    rng.shuffle(keys)
    cut = int(len(keys) * (1.0 - heldout_fraction))
    train_keys = set(keys[:cut])
    train = tuple(item for item in items if item.theorem_key in train_keys)
    heldout = tuple(item for item in items if item.theorem_key not in train_keys)
    return train, heldout


def label_balance(items: Sequence[TransformItem]) -> float:
    return sum(1 for item in items if item.valid) / len(items) if items else float("nan")


__all__ = [
    "ADAPTER_VERSION",
    "AXIS_INVALIDITY",
    "AXIS_LEVEL",
    "AXIS_PROPERTIES",
    "AXIS_RESIDUAL_RISK",
    "AxisProperties",
    "BuildReport",
    "CORRUPTORS",
    "Corruption",
    "CorruptionAxis",
    "DifficultyLevel",
    "Discard",
    "DiscardKind",
    "ENVIRONMENT_VERSION",
    "GENERATOR_SEED",
    "GroundTruthTier",
    "Hypothesis",
    "ITEM_TEMPLATE",
    "LEAN_TIER_A_REPLAY",
    "PERMITTED_SPLIT",
    "PremiseIndex",
    "ProofStep",
    "SealedSplitViolation",
    "TransformItem",
    "axis_subset",
    "build_family",
    "goal_blocks",
    "goal_text",
    "group_proofs",
    "group_split",
    "hypothesis_types",
    "iter_proof_steps",
    "label_balance",
    "level_subset",
    "parse_hypotheses",
    "premise_span_texts",
    "render",
    "strip_premise_tags",
    "successor_derangement",
    "swap_identifiers",
    "symbolic_tokens",
    "token_multiset",
]
