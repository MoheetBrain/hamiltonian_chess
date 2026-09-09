"""Anchored real Lean states — the HC-V0.6 evaluation universe (``docs/HC_V0_6_DESIGN_BRIEF.md`` §1).

An **anchored state** is a real :class:`~arena.trajectory.schema.BackendStateEnvelope` reached by
replaying a *prefix* of a recorded mathlib proof inside a live Lean REPL session, at which goals
are still **open**.  It is *anchored* because it is **re-derivable**: the recipe

``(theorem_full_name, prefix_tactics, toolchain, mathlib commit)``

reaches a state with the same :attr:`KernelStateIdentity.reelaboration_key` in every fresh
session.  The live ``sid`` is not the anchor; the recipe plus the re-elaboration key is.  This
module therefore never stores a live ``sid`` as an identity, and
:func:`verify_rederivability` *measures* the claim rather than asserting it.

Three separations this module exists to make mechanical
-------------------------------------------------------

**1. Oracle side vs Solver side.**  Building an anchor replays recorded tactics.  That is
oracle-side work — ``actor=REFERENCE``, exactly like
:class:`~arena.trajectory.arena_v0.ReplayDriver` — and the Solver must never see it.  Every
:class:`Anchor` therefore carries two disjoint sub-objects:

``solver_visible``
    the goal state the Solver is shown: backend kind, pretty-printed goals, goal count, the
    pretty-printing scope, and the content hash of the goal text.  Nothing else.
``oracle``
    the recipe: the prefix tactics, the full recorded proof, the declaration span, the toolchain
    and the mathlib commit.

:func:`solver_visible_payload` is the **only** function a downstream assay should call to build a
prompt, and :func:`assert_no_oracle_leak` is the tripwire that says so mechanically.  A bank whose
prefix tactics could reach a prompt would silently answer a different question from the one
HC-V0.6 asks.

**2. Sampling proxy vs reasoning difficulty.**  :attr:`AnchorSampling.prefix_length` and
:attr:`AnchorSampling.observed_trace_length` are **sampling proxies and nothing else** (manual
§6.34, §17.6).  A prefix of length 3 is not "three steps of required reasoning" and a recorded
proof of length 9 is not a nine-step task: a shorter proof may always exist.  The five horizon
names stay distinct and are carried side by side in :meth:`AnchorSampling.to_dict`:

===========================  ==================================================================
``ObservedTraceLength``      transitions in the stored demonstration — here, the recorded proof
``EpisodeLength``            model-facing decisions in an actual run — **0** at an anchor, which
                             is a state and not an episode
``KernelStepCount``          post-lowering cost — not measured at derivation time, ``0``
``DependencyDepth``          ``UNKNOWN`` for this backend
``MinimalProofLength``       ``UNKNOWN``, always, and nothing here could establish it
===========================  ==================================================================

**3. One session per theorem, many branches.**  :meth:`LeanReplSession.step` applies a tactic to
*any* state the session has produced, so every anchor of one theorem is derived in **one** Lean
process: startup costs seconds and a step costs milliseconds.  :func:`open_anchor_session` is the
API the downstream assay uses to exploit this — it re-derives every anchor of one theorem in one
session and yields a :class:`LiveAnchorSet` whose ``step()`` branches a candidate tactic from any
of them without a restart.  Do **not** open one session per cell.

What this module does not claim
-------------------------------

Nothing here separates a solved goal from a recalled one: mathlib4 is ``HISTORICALLY_EXPOSED``
and exposure is transitive.  The defensible phrasing stays *execution under kernel verification*.
Anchor selection is a pure function of ``(train_json, scan_limit, seed, filters)`` and never
touches anything downstream of Solver performance — this module does not call a model at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from arena.canonical.schema import stable_hash
from arena.storage.artifacts import ArtifactStore, StoredArtifact
from arena.trajectory.arena_v0 import (
    CONTAMINATION_NOTE,
    DEFAULT_TRAIN_JSON,
    AnswerLeakageError,
    LeakageFilter,
    LeakReason,
    derive_session_id,
    select_candidates,
)
from arena.trajectory.lean_backend import (
    SEALED_SPLIT_PATHS,
    LeanReplSession,
    LeanTheoremProbe,
    LeanToolchainConfig,
    TacticPolicy,
    ToolchainReport,
    assert_not_sealed,
    build_probe,
    check_toolchain,
    count_oleans,
    is_no_goals,
    require_toolchain,
)
from arena.trajectory.schema import Actor, BackendStateEnvelope, PPScope, content_sha256
from arena.trajectory.state_identity import BackendSessionRef, KernelStateIdentity

#: Schema id of the artefact this module writes.  Distinct from the trajectory bank's.
ANCHOR_SCHEMA = "arena-anchored-state-bank-v0"
ANCHOR_GENERATOR_ID = "arena/trajectory/anchor.py@v0"

#: Where the built bank lands, relative to the :class:`ArtifactStore` root.
DEFAULT_ANCHOR_BANK_RELPATH = Path("trajectory/hc_v0_6_anchor_bank.json")

#: Carried verbatim in the artefact so a reader of the JSON cannot mistake a sampling proxy for a
#: difficulty claim without first reading the prohibition (manual §6.34, §17.6).
SAMPLING_PROXY_NOTE = (
    "prefix_length and observed_trace_length are SAMPLING PROXIES, never reasoning difficulty. "
    "MinimalProofLength is UNKNOWN and nothing in this arena could establish it; a shorter proof "
    "may always exist. EpisodeLength is 0 at an anchor because an anchor is a state, not an "
    "episode. DependencyDepth is UNKNOWN for this backend. KernelStepCount is not measured at "
    "derivation time."
)

#: Why the Solver-visible payload is a separate object from the recipe.
SEGREGATION_NOTE = (
    "solver_visible is the ONLY sub-object a prompt may be built from; oracle holds the recipe "
    "(prefix tactics, the whole recorded proof, the declaration span) and is REFERENCE-actor "
    "material. Use solver_visible_payload(anchor); assert_no_oracle_leak() is the tripwire."
)


# ---------------------------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------------------------


class AnchorDepthClass(StrEnum):
    """Where along the recorded proof an anchor sits.  Descriptive; never a difficulty label."""

    #: ``prefix_length == 0`` — the theorem's own initial goal, no recorded tactic applied.
    INITIAL = "INITIAL"
    #: ``prefix_length >= 1`` — reached after replaying that many recorded tactics.
    MID_PROOF = "MID_PROOF"


class AnchorDiscardReason(StrEnum):
    """Every way a candidate state failed to become an anchor.  Counted, never silent."""

    #: The backend reported ``no goals``: there is nothing for a Solver to do here.
    NO_OPEN_GOALS = "NO_OPEN_GOALS"
    #: The backend returned an empty pretty-printed state.
    EMPTY_STATE = "EMPTY_STATE"
    #: Another anchor of the same theorem already has this re-elaboration key (a no-op tactic).
    DUPLICATE_REELABORATION_KEY = "DUPLICATE_REELABORATION_KEY"
    #: A not-yet-played reference tactic appears in the state the Solver would see.
    LEAKS_TACTIC_IN_STATE = "LEAKS_TACTIC_IN_STATE"
    #: The theorem's own name appears in the state the Solver would see.
    LEAKS_FULL_NAME_IN_STATE = "LEAKS_FULL_NAME_IN_STATE"
    #: An already-played *prefix* tactic appears in the state the Solver would see.  A
    #: conservative extra filter beyond the two measured ones, so that the segregation property
    #: ("a solver-visible payload contains no prefix tactic text") holds bank-wide.
    LEAKS_PREFIX_TACTIC_IN_STATE = "LEAKS_PREFIX_TACTIC_IN_STATE"
    #: The depth-selection rule did not keep this depth.
    DEPTH_NOT_SELECTED = "DEPTH_NOT_SELECTED"
    #: Lean refused the reference tactic, so no deeper state exists on this chain.
    PREFIX_REJECTED_BY_LEAN = "PREFIX_REJECTED_BY_LEAN"
    #: The Lean session never reached the REPL banner.
    SESSION_FAILED_TO_START = "SESSION_FAILED_TO_START"


def count_open_goals(pp: str) -> int:
    """Count ``⊢`` markers in a pretty-printed tactic state.

    Display metadata only; nothing is verified against it.  Mirrors the rule
    ``arena.trajectory.arena_v0`` applies when it builds an envelope, and is duplicated rather
    than imported because that name is private to a module this one does not own.
    """

    if not pp.strip():
        return 0
    if is_no_goals(pp):
        return 0
    return max(pp.count("⊢"), 1)


# ---------------------------------------------------------------------------------------------
# Leakage, on the live state rather than on the record
# ---------------------------------------------------------------------------------------------


def scan_anchor_state(
    leakage_filter: LeakageFilter,
    *,
    payload: Mapping[str, Any],
    full_name: str,
    remaining_reference: Sequence[str],
    prefix_tactics: Sequence[str],
) -> tuple[str, ...]:
    """Reasons the Solver-visible payload of a candidate anchor must be dropped.

    Runs the *existing* :class:`~arena.trajectory.arena_v0.LeakageFilter` machinery against the
    **live** state rather than against the recorded ``state_before`` fields, so the two figures
    stay comparable but distinguishable:

    * :attr:`LeakReason.TACTIC_IN_STATE_BEFORE` — a not-yet-played reference tactic appears in the
      state it is supposed to be chosen from.  Checked with
      :meth:`LeakageFilter.assert_observation_clean`, so the filter's own
      ``min_runtime_secret_len`` tripwire (short tactics such as ``rfl`` occur in goal text by
      coincidence) applies unchanged;
    * :attr:`LeakReason.FULL_NAME_IN_STATE` — the theorem's own name appears in the state.  Plain
      substring, exactly as :meth:`LeakageFilter.scan_record` tests it;
    * :attr:`AnchorDiscardReason.LEAKS_PREFIX_TACTIC_IN_STATE` — an *already-played* prefix tactic
      appears in the state.  Not one of the two measured criteria: it is the conservative extra
      filter that makes the prefix-segregation property hold for every anchor in the bank.

    Returns the reasons as strings so record-level and anchor-level counts can share a ledger.
    """

    reasons: list[str] = []
    try:
        leakage_filter.assert_observation_clean(payload, remaining_reference)
    except AnswerLeakageError:
        reasons.append(LeakReason.TACTIC_IN_STATE_BEFORE.value)
    text = json.dumps(payload, ensure_ascii=False)
    if full_name and full_name in text:
        reasons.append(LeakReason.FULL_NAME_IN_STATE.value)
    try:
        leakage_filter.assert_observation_clean(payload, prefix_tactics)
    except AnswerLeakageError:
        reasons.append(AnchorDiscardReason.LEAKS_PREFIX_TACTIC_IN_STATE.value)
    return tuple(reasons)


# ---------------------------------------------------------------------------------------------
# The anchor record
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SolverVisibleState:
    """Exactly what a Solver may be shown at an anchor: the goal state, and nothing else.

    No theorem name, no file path, no prefix, no recorded proof, no depth.  Everything that would
    identify *which* mathlib declaration this is lives in :class:`AnchorCluster` (bank-level
    statistics, manual §30.6) or in :class:`AnchorRecipe` (oracle), both outside this object.
    """

    backend_kind: str
    goals_pp: str
    n_goals: int
    pp_scope: PPScope

    @property
    def pp_sha256(self) -> str:
        return content_sha256(self.goals_pp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_kind": self.backend_kind,
            "goals_pp": self.goals_pp,
            "n_goals": self.n_goals,
            "pp_scope": self.pp_scope.to_dict(),
            "pp_sha256": self.pp_sha256,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            backend_kind=str(payload["backend_kind"]),
            goals_pp=str(payload["goals_pp"]),
            n_goals=int(payload["n_goals"]),
            pp_scope=PPScope.from_dict(dict(payload.get("pp_scope", {}) or {})),
        )

    def envelope(self, *, state_id: str, session_id: str, problem_id: str) -> BackendStateEnvelope:
        """Rebuild the backend envelope this state came from, for identity computation."""

        return BackendStateEnvelope(
            index=0,
            state_id=state_id,
            pp=self.goals_pp,
            backend_kind=self.backend_kind,
            pp_scope=self.pp_scope,
            n_goals=self.n_goals,
            session_id=session_id,
            problem_id=problem_id,
        )


@dataclass(frozen=True, slots=True)
class AnchorRecipe:
    """The oracle-side recipe: how this state is re-derived.  **Never shown to a Solver.**

    Deliberately compact.  ``LeanTheoremProbe.prefix_text`` — everything in the mathlib file
    before the declaration — runs to tens of kilobytes per theorem, so the bank stores the
    *declaration span* and rebuilds the probe from the pinned checkout instead
    (:meth:`leandojo_record`, :meth:`build`).  ``probe_source_sha256`` is the check that the
    rebuild produced byte-identical Lean source; a mismatch means the checkout moved and the
    anchor is not re-derivable there, which is reported rather than papered over.
    """

    problem_id: str
    theorem_full_name: str
    file_path: str
    #: The recorded tactics replayed to reach this state.  Empty for a depth-0 anchor.
    prefix_tactics: tuple[str, ...]
    #: The whole recorded proof, needed to rebuild the probe and to know what comes next.
    reference_tactics: tuple[str, ...]
    #: The declaration span in the source file, as LeanDojo records it.
    decl_start: tuple[int, int]
    decl_end: tuple[int, int]
    mathlib_commit: str
    mathlib_url: str
    toolchain: str
    lean_version_string: str
    probe_source_sha256: str
    max_heartbeats: int = 1_000_000
    #: ``REFERENCE``: every tactic in :attr:`prefix_tactics` came from the recorded proof.
    actor: str = Actor.REFERENCE.value

    @property
    def prefix_length(self) -> int:
        return len(self.prefix_tactics)

    @property
    def remaining_reference(self) -> tuple[str, ...]:
        """The recorded tactics not yet played.  The first of them is this state's gold move."""

        return self.reference_tactics[self.prefix_length :]

    def leandojo_record(self) -> dict[str, Any]:
        """The minimal LeanDojo-shaped record :func:`build_probe` needs.

        Only the keys ``build_probe`` actually reads are reproduced, and each of them is the
        source's own value carried through unchanged.  Nothing is invented.
        """

        return {
            "url": self.mathlib_url,
            "commit": self.mathlib_commit,
            "file_path": self.file_path,
            "full_name": self.theorem_full_name,
            "start": list(self.decl_start),
            "end": list(self.decl_end),
            "traced_tactics": [{"tactic": tactic} for tactic in self.reference_tactics],
        }

    def build(self, *, mathlib_root: Path, policy: TacticPolicy | None = None) -> LeanTheoremProbe:
        """Rebuild the probe from the pinned checkout, or raise saying exactly why not."""

        built = build_probe(
            self.leandojo_record(),
            mathlib_root=mathlib_root,
            policy=policy or TacticPolicy.record_only(),
            min_reference_horizon=0,
            allow_multiline_tactics=True,
            max_heartbeats=self.max_heartbeats,
        )
        if built.probe is None:
            raise AnchorRederivationError(
                f"cannot rebuild the probe for {self.problem_id!r} from {mathlib_root}: "
                f"{built.discard_reason} {built.detail}"
            )
        return built.probe

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "problem_id": self.problem_id,
            "theorem_full_name": self.theorem_full_name,
            "file_path": self.file_path,
            "prefix_tactics": list(self.prefix_tactics),
            "prefix_length": self.prefix_length,
            "reference_tactics": list(self.reference_tactics),
            "decl_start": list(self.decl_start),
            "decl_end": list(self.decl_end),
            "mathlib_commit": self.mathlib_commit,
            "mathlib_url": self.mathlib_url,
            "toolchain": self.toolchain,
            "lean_version_string": self.lean_version_string,
            "probe_source_sha256": self.probe_source_sha256,
            "max_heartbeats": self.max_heartbeats,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        start = list(payload["decl_start"])
        end = list(payload["decl_end"])
        return cls(
            problem_id=str(payload["problem_id"]),
            theorem_full_name=str(payload["theorem_full_name"]),
            file_path=str(payload["file_path"]),
            prefix_tactics=tuple(str(item) for item in payload["prefix_tactics"]),
            reference_tactics=tuple(str(item) for item in payload["reference_tactics"]),
            decl_start=(int(start[0]), int(start[1])),
            decl_end=(int(end[0]), int(end[1])),
            mathlib_commit=str(payload["mathlib_commit"]),
            mathlib_url=str(payload.get("mathlib_url", "")),
            toolchain=str(payload["toolchain"]),
            lean_version_string=str(payload.get("lean_version_string", "")),
            probe_source_sha256=str(payload["probe_source_sha256"]),
            max_heartbeats=int(payload.get("max_heartbeats", 1_000_000)),
            actor=str(payload.get("actor", Actor.REFERENCE.value)),
        )


@dataclass(frozen=True, slots=True)
class AnchorSampling:
    """Sampling proxies.  Read :data:`SAMPLING_PROXY_NOTE` before using any number here."""

    prefix_length: int
    observed_trace_length: int
    depth_class: AnchorDepthClass

    def to_dict(self) -> dict[str, Any]:
        return {
            "prefix_length": self.prefix_length,
            "depth_class": self.depth_class.value,
            # Manual §6.30-6.34 / §17.6: the five names stay distinct and are carried together so
            # no reader can borrow one number for another's meaning.
            "observed_trace_length": self.observed_trace_length,
            "episode_length": 0,
            "kernel_step_count": 0,
            "dependency_depth": "UNKNOWN",
            "minimal_proof_length": "UNKNOWN",
            "note": SAMPLING_PROXY_NOTE,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            prefix_length=int(payload["prefix_length"]),
            observed_trace_length=int(payload["observed_trace_length"]),
            depth_class=AnchorDepthClass(str(payload["depth_class"])),
        )


@dataclass(frozen=True, slots=True)
class AnchorCluster:
    """The grouping unit for the statistics: theorems in one mathlib file are not independent.

    Manual §30.6.  Bank-level metadata, not Solver-visible: the theorem's own name in a prompt
    would be exactly the leak :attr:`LeakReason.FULL_NAME_IN_STATE` exists to catch.
    """

    file_path: str
    theorem_full_name: str
    problem_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "theorem_full_name": self.theorem_full_name,
            "problem_id": self.problem_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            file_path=str(payload["file_path"]),
            theorem_full_name=str(payload["theorem_full_name"]),
            problem_id=str(payload["problem_id"]),
        )


class AnchorRederivationError(RuntimeError):
    """An anchor could not be re-derived.  Reported as a measurement, never swallowed."""


@dataclass(frozen=True, slots=True)
class Anchor:
    """One re-derivable open Lean state, with the recipe and the goal state kept apart.

    :attr:`anchor_id` is a function of the **recipe alone** — not of the state that was derived.
    That is deliberate: the anchor *is* the recipe, so a re-derivation keeps the same id and the
    two runs' :attr:`reelaboration_key` values can be compared under it.  If the id were a
    function of the derived state, a divergence would look like a different anchor instead of a
    failure of the anchoring claim.
    """

    oracle: AnchorRecipe
    solver_visible: SolverVisibleState
    sampling: AnchorSampling
    cluster: AnchorCluster
    #: The state identity this recipe is expected to reach in any fresh session.
    reelaboration_key: str
    goal_digest: str
    scope_digest: str
    normalization: str
    #: The live ``sid`` at derivation time.  Oracle bookkeeping; excluded from
    #: :attr:`content_core` because it names a process that no longer exists.
    derivation_state_id: str = ""

    @property
    def anchor_id(self) -> str:
        return (
            "anchor:"
            + stable_hash(
                {
                    "schema": ANCHOR_SCHEMA,
                    "problem_id": self.oracle.problem_id,
                    "prefix_tactics": list(self.oracle.prefix_tactics),
                    "toolchain": self.oracle.toolchain,
                    "mathlib_commit": self.oracle.mathlib_commit,
                    "probe_source_sha256": self.oracle.probe_source_sha256,
                }
            )[:24]
        )

    @property
    def content_core(self) -> dict[str, Any]:
        """Everything the bank's content hash is taken over.  No wall clock, no live handle."""

        return {
            "anchor_id": self.anchor_id,
            "oracle": self.oracle.to_dict(),
            "solver_visible": self.solver_visible.to_dict(),
            "sampling": {
                "prefix_length": self.sampling.prefix_length,
                "observed_trace_length": self.sampling.observed_trace_length,
                "depth_class": self.sampling.depth_class.value,
            },
            "cluster": self.cluster.to_dict(),
            "reelaboration_key": self.reelaboration_key,
            "goal_digest": self.goal_digest,
            "scope_digest": self.scope_digest,
            "normalization": self.normalization,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.content_core
        payload["sampling"] = self.sampling.to_dict()
        payload["derivation_state_id"] = self.derivation_state_id
        payload["segregation"] = SEGREGATION_NOTE
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            oracle=AnchorRecipe.from_dict(payload["oracle"]),
            solver_visible=SolverVisibleState.from_dict(payload["solver_visible"]),
            sampling=AnchorSampling.from_dict(payload["sampling"]),
            cluster=AnchorCluster.from_dict(payload["cluster"]),
            reelaboration_key=str(payload["reelaboration_key"]),
            goal_digest=str(payload["goal_digest"]),
            scope_digest=str(payload["scope_digest"]),
            normalization=str(payload["normalization"]),
            derivation_state_id=str(payload.get("derivation_state_id", "")),
        )


def solver_visible_payload(anchor: Anchor) -> dict[str, Any]:
    """The **only** thing a downstream assay may build a prompt from.

    Returns the goal state and its display metadata.  It does not return — and cannot be made to
    return — the prefix, the recorded proof, the theorem name, the file path, or the depth: those
    live on :attr:`Anchor.oracle`, :attr:`Anchor.cluster` and :attr:`Anchor.sampling`, which this
    function never reads.  ``anchor_id`` is included so a cell can be joined back to its anchor;
    it is a hash and carries no readable oracle text.
    """

    payload = anchor.solver_visible.to_dict()
    payload["anchor_id"] = anchor.anchor_id
    return payload


def assert_no_oracle_leak(payload: Mapping[str, Any], anchor: Anchor) -> None:
    """Raise if anything oracle-side reached ``payload``.  The tripwire, not a suggestion.

    Checks the prefix tactics, the not-yet-played reference tactics and the theorem's full name
    against whatever is about to be shown.  Short tactics are exempt via the leakage filter's own
    ``min_runtime_secret_len``, because ``rfl`` occurring inside goal text is a coincidence and
    not a leak — the same rule the measured figures were produced under.
    """

    reasons = scan_anchor_state(
        LeakageFilter(),
        payload=payload,
        full_name=anchor.cluster.theorem_full_name,
        remaining_reference=anchor.oracle.remaining_reference,
        prefix_tactics=anchor.oracle.prefix_tactics,
    )
    if reasons:
        raise AnswerLeakageError(
            f"oracle material reached a Solver-visible payload for {anchor.anchor_id}: "
            f"{sorted(reasons)}"
        )


# ---------------------------------------------------------------------------------------------
# Depth selection — a fixed rule, not a random draw
# ---------------------------------------------------------------------------------------------


def select_depths(open_depths: Sequence[int], *, max_per_theorem: int) -> tuple[int, ...]:
    """Which of a theorem's open depths become anchors.

    A fixed, seed-free rule so that the bank's depth profile is auditable rather than a draw:
    depth 0 is always kept when it is open (the theorem's own initial goal, required by the
    design brief), and the remaining slots are filled by **evenly spaced quantiles** of the
    surviving mid-proof depths.  Even spacing is chosen over a random subset so the bank spans
    early, middle and late states of every theorem instead of clustering wherever chance put it.

    Deterministic and independent of anything a Solver did — this function cannot see a Solver.
    """

    if max_per_theorem <= 0 or not open_depths:
        return ()
    ordered = sorted(set(open_depths))
    kept: list[int] = []
    rest = list(ordered)
    if rest and rest[0] == 0:
        kept.append(rest.pop(0))
    slots = max_per_theorem - len(kept)
    if slots > 0 and rest:
        if len(rest) <= slots:
            kept.extend(rest)
        else:
            # Evenly spaced positions across the mid-proof depths, endpoints included.
            step = (len(rest) - 1) / (slots - 1) if slots > 1 else 0.0
            picked = {int(round(index * step)) for index in range(slots)}
            kept.extend(rest[position] for position in sorted(picked))
    return tuple(sorted(kept))


# ---------------------------------------------------------------------------------------------
# Derivation: one Lean session per theorem
# ---------------------------------------------------------------------------------------------


@dataclass(slots=True)
class AnchorLedger:
    """Counts of everything discarded on the way to a bank.  Reported with every build."""

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, reason: str | AnchorDiscardReason, times: int = 1) -> None:
        key = reason.value if isinstance(reason, AnchorDiscardReason) else str(reason)
        self.counts[key] = self.counts.get(key, 0) + times

    def merge(self, other: AnchorLedger) -> None:
        for key, value in other.counts.items():
            self.record(key, value)

    def total(self) -> int:
        return sum(self.counts.values())

    def to_dict(self) -> dict[str, int]:
        return dict(sorted(self.counts.items()))


@dataclass(frozen=True, slots=True)
class TheoremAnchorResult:
    """What one theorem contributed, and what it cost."""

    problem_id: str
    anchors: tuple[Anchor, ...]
    discards: AnchorLedger
    prefix_steps_accepted: int
    prefix_steps_rejected: int
    startup_s: float
    wall_s: float
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "anchors": len(self.anchors),
            "prefix_steps_accepted": self.prefix_steps_accepted,
            "prefix_steps_rejected": self.prefix_steps_rejected,
            "startup_s": round(self.startup_s, 3),
            "wall_s": round(self.wall_s, 3),
            "discards": self.discards.to_dict(),
            "error": self.error[:400],
        }


def _live_session_ref(
    probe: LeanTheoremProbe, *, policy: TacticPolicy, seed: int
) -> BackendSessionRef:
    """A reference naming **this live process**, never a stored identity.

    ``derive_session_id`` is content-addressed on the session's opening conditions, so two
    different live sessions of the same probe share it — correct for a *record* binding and wrong
    for a *live* handle namespace, since ``sid=3`` in one process is not ``sid=3`` in another.  A
    per-process token is appended so :attr:`KernelStateIdentity.kernel_key` cannot accidentally
    equate two processes' handles.  Nothing built from this is ever written to the bank.
    """

    record_id = derive_session_id(probe, policy=policy, seed=seed)
    return BackendSessionRef(session_id=f"{record_id}:live-{uuid.uuid4().hex[:12]}")


def _identity_of(
    pp: str, probe: LeanTheoremProbe, state_id: str, session: BackendSessionRef, *, seed: int
) -> KernelStateIdentity:
    envelope = BackendStateEnvelope(
        index=0,
        state_id=state_id,
        pp=pp,
        pp_scope=probe.pp_scope,
        n_goals=count_open_goals(pp),
        session_id=derive_session_id(probe, policy=TacticPolicy.record_only(), seed=seed),
        problem_id=probe.problem_id,
    )
    return KernelStateIdentity.from_envelope(envelope, session=session)


def derive_theorem_anchors(
    record: Mapping[str, Any],
    probe: LeanTheoremProbe,
    *,
    report: ToolchainReport,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
    leakage_filter: LeakageFilter | None = None,
    max_anchors_per_theorem: int = 3,
    max_prefix_length: int | None = None,
    seed: int = 0,
) -> TheoremAnchorResult:
    """Derive every anchor of one theorem in **one** Lean session.

    Oracle-side work throughout (``actor=REFERENCE``): the recorded proof is replayed as a flat
    tactic script, exactly as :class:`~arena.trajectory.arena_v0.ReplayDriver` does, and each open
    state along the chain is a candidate anchor.  A recorded proof is a traversal of a proof
    *tree*, so a flat replay does not always run to the end; when Lean refuses a reference tactic
    the chain simply stops and the anchors already derived are kept.  That is counted
    (:attr:`AnchorDiscardReason.PREFIX_REJECTED_BY_LEAN`), not treated as a failure.

    Startup costs seconds and a step costs milliseconds, so opening one session per depth would
    multiply the cost of the bank by its depth and buy nothing.
    """

    config = config or LeanToolchainConfig.from_env()
    policy = policy or TacticPolicy.record_only()
    leakage_filter = leakage_filter or LeakageFilter()
    discards = AnchorLedger()
    started = time.monotonic()
    full_name = probe.full_name
    reference = probe.reference_tactics
    commit = str(record.get("commit", ""))
    url = str(record.get("url", ""))
    decl_start = record.get("start") or (0, 0)
    decl_end = record.get("end") or (0, 0)
    probe_sha = content_sha256(probe.repl_source())

    # depth -> (pretty-printed state, live sid).  Derived once, filtered afterwards, so the
    # filters never change which Lean states were visited.
    chain: dict[int, tuple[str, str]] = {}
    accepted = 0
    rejected = 0
    error = ""
    startup_s = 0.0

    session = LeanReplSession(probe, config=config, policy=policy)
    session_ref = _live_session_ref(probe, policy=policy, seed=seed)
    try:
        start = session.start()
        startup_s = session.startup_wall_s
        if not start.ok or start.to_state_id is None:
            discards.record(AnchorDiscardReason.SESSION_FAILED_TO_START)
            return TheoremAnchorResult(
                problem_id=probe.problem_id,
                anchors=(),
                discards=discards,
                prefix_steps_accepted=0,
                prefix_steps_rejected=0,
                startup_s=startup_s,
                wall_s=time.monotonic() - started,
                error=start.error or "session failed to start",
            )
        chain[0] = (start.tactic_state or "", start.to_state_id)
        current = start.to_state_id
        depth_cap = (
            len(reference) if max_prefix_length is None else min(len(reference), max_prefix_length)
        )
        for index in range(depth_cap):
            step = session.step(current, reference[index])
            if not step.ok or step.to_state_id is None:
                rejected += 1
                discards.record(AnchorDiscardReason.PREFIX_REJECTED_BY_LEAN)
                error = step.error or step.outcome.value
                break
            accepted += 1
            current = step.to_state_id
            chain[index + 1] = (step.tactic_state or "", current)
            if step.closed:
                break
    finally:
        session.close()

    # -- filter the derived chain down to anchors -----------------------------------
    open_depths: list[int] = []
    for depth, (pp, _sid) in sorted(chain.items()):
        if not pp.strip():
            discards.record(AnchorDiscardReason.EMPTY_STATE)
            continue
        if is_no_goals(pp):
            discards.record(AnchorDiscardReason.NO_OPEN_GOALS)
            continue
        open_depths.append(depth)

    kept_depths = select_depths(open_depths, max_per_theorem=max_anchors_per_theorem)
    for depth in open_depths:
        if depth not in kept_depths:
            discards.record(AnchorDiscardReason.DEPTH_NOT_SELECTED)

    anchors: list[Anchor] = []
    seen_keys: set[str] = set()
    for depth in kept_depths:
        pp, sid = chain[depth]
        prefix = tuple(reference[:depth])
        recipe = AnchorRecipe(
            problem_id=probe.problem_id,
            theorem_full_name=full_name,
            file_path=probe.file_path,
            prefix_tactics=prefix,
            reference_tactics=tuple(reference),
            decl_start=(int(decl_start[0]), int(decl_start[1])),
            decl_end=(int(decl_end[0]), int(decl_end[1])),
            mathlib_commit=commit,
            mathlib_url=url,
            toolchain=report.toolchain,
            lean_version_string=report.lean_version_string,
            probe_source_sha256=probe_sha,
            max_heartbeats=probe.max_heartbeats,
        )
        visible = SolverVisibleState(
            backend_kind="LEAN4_TACTIC_STATE_PP",
            goals_pp=pp,
            n_goals=count_open_goals(pp),
            pp_scope=probe.pp_scope,
        )
        payload = visible.to_dict()
        reasons = scan_anchor_state(
            leakage_filter,
            payload=payload,
            full_name=full_name,
            remaining_reference=recipe.remaining_reference,
            prefix_tactics=prefix,
        )
        if reasons:
            mapping = {
                LeakReason.TACTIC_IN_STATE_BEFORE.value: (
                    AnchorDiscardReason.LEAKS_TACTIC_IN_STATE
                ),
                LeakReason.FULL_NAME_IN_STATE.value: (AnchorDiscardReason.LEAKS_FULL_NAME_IN_STATE),
            }
            for reason in reasons:
                discards.record(mapping.get(reason, reason))
            continue
        identity = _identity_of(pp, probe, sid, session_ref, seed=seed)
        if identity.reelaboration_key in seen_keys:
            discards.record(AnchorDiscardReason.DUPLICATE_REELABORATION_KEY)
            continue
        seen_keys.add(identity.reelaboration_key)
        anchors.append(
            Anchor(
                oracle=recipe,
                solver_visible=visible,
                sampling=AnchorSampling(
                    prefix_length=depth,
                    observed_trace_length=len(reference),
                    depth_class=(
                        AnchorDepthClass.INITIAL if depth == 0 else AnchorDepthClass.MID_PROOF
                    ),
                ),
                cluster=AnchorCluster(
                    file_path=probe.file_path,
                    theorem_full_name=full_name,
                    problem_id=probe.problem_id,
                ),
                reelaboration_key=identity.reelaboration_key,
                goal_digest=identity.goal_digest,
                scope_digest=identity.scope_digest,
                normalization=identity.normalization,
                derivation_state_id=sid,
            )
        )

    return TheoremAnchorResult(
        problem_id=probe.problem_id,
        anchors=tuple(anchors),
        discards=discards,
        prefix_steps_accepted=accepted,
        prefix_steps_rejected=rejected,
        startup_s=startup_s,
        wall_s=time.monotonic() - started,
        error=error,
    )


# ---------------------------------------------------------------------------------------------
# Re-derivation: the API the downstream assay branches from
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LiveAnchor:
    """One anchor, re-derived, with the live handle a tactic can be applied to."""

    anchor: Anchor
    live_state_id: str
    identity: KernelStateIdentity
    #: ``True`` when the fresh session reproduced the stored re-elaboration key.
    matched: bool

    @property
    def anchor_id(self) -> str:
        return self.anchor.anchor_id


@dataclass(slots=True)
class LiveAnchorSet:
    """One open Lean session holding every anchor of one theorem, ready to be stepped from.

    This is the object the HC-V0.6 assay drives.  ``step(anchor_id, tactic)`` applies a candidate
    tactic **at** an anchor without restarting Lean, so every renderer arm and every replicate at
    every anchor of a theorem costs one startup in total rather than one each: at the measured
    ~0.8-4 s startup and ~5 ms step, that is the difference between minutes and hours.
    """

    session: LeanReplSession
    probe: LeanTheoremProbe
    live: tuple[LiveAnchor, ...]
    missing: tuple[tuple[str, str], ...] = ()

    @property
    def anchors(self) -> tuple[Anchor, ...]:
        return tuple(item.anchor for item in self.live)

    @property
    def matched(self) -> tuple[LiveAnchor, ...]:
        return tuple(item for item in self.live if item.matched)

    def by_id(self, anchor_id: str) -> LiveAnchor:
        for item in self.live:
            if item.anchor_id == anchor_id:
                return item
        raise KeyError(f"{anchor_id!r} was not re-derived in this session")

    def solver_payload(self, anchor_id: str) -> dict[str, Any]:
        """The Solver-visible payload of a re-derived anchor, with the tripwire already run."""

        item = self.by_id(anchor_id)
        payload = solver_visible_payload(item.anchor)
        assert_no_oracle_leak(payload, item.anchor)
        return payload

    def step(self, anchor_id: str, tactic: str) -> Any:
        """Apply one candidate tactic **at** the anchor.  Branching, not restarting."""

        return self.session.step(self.by_id(anchor_id).live_state_id, tactic)

    def parent_state_text(self, anchor_id: str) -> str | None:
        """The pretty-printed state THIS session holds at the anchor, or ``None`` if unknown.

        An assay asking "did the action change the state" must compare against the state the action
        was actually applied to, not the one the bank recorded -- otherwise a silent re-derivation
        drift would be scored as a change of mathematics.
        """

        return self.session.state_text(self.by_id(anchor_id).live_state_id)


@contextmanager
def open_anchor_session(
    anchors: Sequence[Anchor],
    *,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
    seed: int = 0,
    require_probe_match: bool = True,
) -> Iterator[LiveAnchorSet]:
    """Re-derive every anchor of **one theorem** in one fresh Lean session and yield it open.

    All ``anchors`` must share a ``problem_id``: the session is opened on that theorem's probe.
    Because the prefixes are nested (depth 0 ⊂ depth 1 ⊂ …) the whole chain is replayed **once**
    and every anchored depth is picked off it, so re-deriving *n* anchors costs one startup and
    ``max(prefix_length)`` steps rather than *n* startups.

    Each re-derived state's :attr:`KernelStateIdentity.reelaboration_key` is compared against the
    stored one and the result is reported on :attr:`LiveAnchor.matched`.  A mismatch is **not**
    raised: it is the measurement the anchoring claim rests on, and hiding it would turn a finding
    into a filter.  An anchor whose prefix Lean now refuses appears in
    :attr:`LiveAnchorSet.missing` with the reason.
    """

    if not anchors:
        raise ValueError("open_anchor_session needs at least one anchor")
    problem_ids = {anchor.oracle.problem_id for anchor in anchors}
    if len(problem_ids) != 1:
        raise ValueError(
            "open_anchor_session opens ONE session on ONE theorem; got "
            f"{sorted(problem_ids)!r}. Group by cluster.problem_id first."
        )
    config = config or LeanToolchainConfig.from_env()
    policy = policy or TacticPolicy.record_only()
    recipe = anchors[0].oracle
    probe = recipe.build(mathlib_root=config.mathlib_root, policy=policy)
    rebuilt_sha = content_sha256(probe.repl_source())
    if require_probe_match and rebuilt_sha != recipe.probe_source_sha256:
        raise AnchorRederivationError(
            f"the checkout at {config.mathlib_root} no longer produces the probe this anchor was "
            f"derived from ({rebuilt_sha[:16]} != {recipe.probe_source_sha256[:16]}); the anchor "
            "is not re-derivable here"
        )

    ordered = sorted(anchors, key=lambda item: item.sampling.prefix_length)
    wanted = {anchor.sampling.prefix_length: anchor for anchor in ordered}
    deepest = max(wanted)
    session = LeanReplSession(probe, config=config, policy=policy)
    session_ref = _live_session_ref(probe, policy=policy, seed=seed)
    live: list[LiveAnchor] = []
    missing: list[tuple[str, str]] = []
    try:
        start = session.start()
        if not start.ok or start.to_state_id is None:
            raise AnchorRederivationError(
                f"fresh session for {recipe.problem_id!r} failed to start: {start.error}"
            )
        reached: dict[int, tuple[str, str]] = {0: (start.tactic_state or "", start.to_state_id)}
        current = start.to_state_id
        stop_reason = ""
        for index in range(deepest):
            step = session.step(current, recipe.reference_tactics[index])
            if not step.ok or step.to_state_id is None:
                stop_reason = step.error or step.outcome.value
                break
            current = step.to_state_id
            reached[index + 1] = (step.tactic_state or "", current)
            if step.closed:
                stop_reason = "the chain closed before this depth"
                break
        for depth, anchor in sorted(wanted.items()):
            if depth not in reached:
                missing.append((anchor.anchor_id, stop_reason or "depth not reached"))
                continue
            pp, sid = reached[depth]
            identity = _identity_of(pp, probe, sid, session_ref, seed=seed)
            live.append(
                LiveAnchor(
                    anchor=anchor,
                    live_state_id=sid,
                    identity=identity,
                    matched=identity.reelaboration_key == anchor.reelaboration_key,
                )
            )
        yield LiveAnchorSet(session=session, probe=probe, live=tuple(live), missing=tuple(missing))
    finally:
        session.close()


@dataclass(frozen=True, slots=True)
class RederivationReport:
    """The measured re-derivability of a sample of anchors.  A finding, not a gate."""

    anchors_checked: int
    matched: int
    mismatched: tuple[str, ...]
    not_reached: tuple[tuple[str, str], ...]
    theorems_checked: int
    errors: tuple[tuple[str, str], ...]
    wall_s: float

    @property
    def rate(self) -> float:
        return self.matched / self.anchors_checked if self.anchors_checked else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "theorems_checked": self.theorems_checked,
            "anchors_checked": self.anchors_checked,
            "matched": self.matched,
            "rate": round(self.rate, 6),
            "mismatched_anchor_ids": list(self.mismatched),
            "not_reached": [list(pair) for pair in self.not_reached],
            "errors": [list(pair) for pair in self.errors],
            "wall_s": round(self.wall_s, 2),
            "method": (
                "each sampled theorem is re-derived in a SECOND, independent Lean process; the "
                "fresh KernelStateIdentity.reelaboration_key is compared with the stored one. "
                "Mismatches are reported, never filtered out of the bank."
            ),
        }


def verify_rederivability(
    anchors: Sequence[Anchor],
    *,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
    every: int = 1,
    seed: int = 0,
    verbose: bool = False,
) -> RederivationReport:
    """Re-derive a deterministic sample of theorems in fresh sessions and measure the match rate.

    ``every=1`` checks every theorem; ``every=n`` checks every *n*-th theorem in ``problem_id``
    order — a fixed stride rather than a draw, so the sample is reproducible and is not a function
    of anything observed.
    """

    started = time.monotonic()
    grouped: dict[str, list[Anchor]] = {}
    for anchor in anchors:
        grouped.setdefault(anchor.oracle.problem_id, []).append(anchor)
    problems = sorted(grouped)
    sampled = problems[:: max(1, every)]

    checked = 0
    matched = 0
    mismatched: list[str] = []
    not_reached: list[tuple[str, str]] = []
    errors: list[tuple[str, str]] = []
    for problem_id in sampled:
        group = grouped[problem_id]
        try:
            with open_anchor_session(group, config=config, policy=policy, seed=seed) as live_set:
                for item in live_set.live:
                    checked += 1
                    if item.matched:
                        matched += 1
                    else:
                        mismatched.append(item.anchor_id)
                not_reached.extend(live_set.missing)
        except (AnchorRederivationError, RuntimeError, ValueError) as exc:
            errors.append((problem_id, str(exc)[:400]))
        if verbose:
            print(f"  re-derived {problem_id[:80]}: {matched}/{checked} matched", flush=True)
    return RederivationReport(
        anchors_checked=checked,
        matched=matched,
        mismatched=tuple(mismatched),
        not_reached=tuple(not_reached),
        theorems_checked=len(sampled),
        errors=tuple(errors),
        wall_s=time.monotonic() - started,
    )


# ---------------------------------------------------------------------------------------------
# The bank
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnchorBankStats:
    """Everything a reader needs to judge coverage without re-reading the anchors."""

    anchors: int
    distinct_theorems: int
    distinct_files: int
    prefix_length_histogram: dict[str, int]
    depth_class_counts: dict[str, int]
    anchors_per_theorem: dict[str, int]
    observed_trace_length_histogram: dict[str, int]
    n_goals_histogram: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchors": self.anchors,
            "distinct_theorems": self.distinct_theorems,
            "distinct_files": self.distinct_files,
            "prefix_length_histogram": self.prefix_length_histogram,
            "depth_class_counts": self.depth_class_counts,
            "anchors_per_theorem_histogram": self.anchors_per_theorem,
            "observed_trace_length_histogram": self.observed_trace_length_histogram,
            "n_goals_histogram": self.n_goals_histogram,
            "note": SAMPLING_PROXY_NOTE,
        }


def summarise_anchors(anchors: Sequence[Anchor]) -> AnchorBankStats:
    """Coverage statistics.  Clusters on the mathlib file, per manual §30.6."""

    def histogram(values: Sequence[int]) -> dict[str, int]:
        counts: dict[int, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return {str(key): counts[key] for key in sorted(counts)}

    per_theorem: dict[str, int] = {}
    for anchor in anchors:
        key = anchor.cluster.problem_id
        per_theorem[key] = per_theorem.get(key, 0) + 1
    depth_classes: dict[str, int] = {}
    for anchor in anchors:
        key = anchor.sampling.depth_class.value
        depth_classes[key] = depth_classes.get(key, 0) + 1
    return AnchorBankStats(
        anchors=len(anchors),
        distinct_theorems=len({anchor.cluster.problem_id for anchor in anchors}),
        distinct_files=len({anchor.cluster.file_path for anchor in anchors}),
        prefix_length_histogram=histogram([a.sampling.prefix_length for a in anchors]),
        depth_class_counts=dict(sorted(depth_classes.items())),
        anchors_per_theorem=histogram(sorted(per_theorem.values())),
        observed_trace_length_histogram=histogram(
            [a.sampling.observed_trace_length for a in anchors]
        ),
        n_goals_histogram=histogram([a.solver_visible.n_goals for a in anchors]),
    )


@dataclass(frozen=True, slots=True)
class AnchorBank:
    """A bank of anchored states plus everything needed to judge and reproduce it."""

    anchors: tuple[Anchor, ...]
    selection: dict[str, Any]
    toolchain: dict[str, Any]
    leakage: dict[str, Any]
    discards: dict[str, int]
    rederivation: dict[str, Any]
    cost: dict[str, Any]
    theorems: tuple[dict[str, Any], ...] = ()
    generated_utc: str = ""

    @property
    def stats(self) -> AnchorBankStats:
        return summarise_anchors(self.anchors)

    @property
    def content_hash(self) -> str:
        """The **evaluation-universe hash** of design brief §6.

        A pure function of the anchors and of the selection that produced them.  Wall-clock
        timestamps, measured durations, live ``sid`` values and the re-derivability measurement
        are all excluded, so two builds of the same universe hash the same however long they
        took and whatever a second session happened to report.
        """

        return stable_hash(
            {
                "schema": ANCHOR_SCHEMA,
                "generator": ANCHOR_GENERATOR_ID,
                "selection": self.selection,
                "toolchain": {
                    key: value
                    for key, value in sorted(self.toolchain.items())
                    if key not in {"olean_count"}
                },
                "anchors": [anchor.content_core for anchor in self.anchors],
            }
        )

    def by_theorem(self) -> dict[str, tuple[Anchor, ...]]:
        """Anchors grouped for :func:`open_anchor_session` — one session per group."""

        grouped: dict[str, list[Anchor]] = {}
        for anchor in self.anchors:
            grouped.setdefault(anchor.cluster.problem_id, []).append(anchor)
        return {key: tuple(value) for key, value in sorted(grouped.items())}

    def solver_visible_payloads(self) -> tuple[dict[str, Any], ...]:
        """Every Solver-visible payload, tripwire-checked.  The assay's whole view of the bank."""

        payloads: list[dict[str, Any]] = []
        for anchor in self.anchors:
            payload = solver_visible_payload(anchor)
            assert_no_oracle_leak(payload, anchor)
            payloads.append(payload)
        return tuple(payloads)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ANCHOR_SCHEMA,
            "generator": ANCHOR_GENERATOR_ID,
            "generated_utc": self.generated_utc,
            "content_hash": self.content_hash,
            "segregation": SEGREGATION_NOTE,
            "sampling_proxy_note": SAMPLING_PROXY_NOTE,
            "contamination": CONTAMINATION_NOTE,
            "sealed_splits_not_read": list(SEALED_SPLIT_PATHS),
            "selection": self.selection,
            "toolchain": self.toolchain,
            "stats": self.stats.to_dict(),
            "leakage": self.leakage,
            "discards": self.discards,
            "rederivation": self.rederivation,
            "cost": self.cost,
            "theorems": [dict(item) for item in self.theorems],
            "anchors": [anchor.to_dict() for anchor in self.anchors],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            anchors=tuple(Anchor.from_dict(item) for item in payload["anchors"]),
            selection=dict(payload.get("selection", {}) or {}),
            toolchain=dict(payload.get("toolchain", {}) or {}),
            leakage=dict(payload.get("leakage", {}) or {}),
            discards=dict(payload.get("discards", {}) or {}),
            rederivation=dict(payload.get("rederivation", {}) or {}),
            cost=dict(payload.get("cost", {}) or {}),
            theorems=tuple(dict(item) for item in payload.get("theorems", ()) or ()),
            generated_utc=str(payload.get("generated_utc", "")),
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def write(
        self,
        *,
        store: ArtifactStore | None = None,
        relative: Path = DEFAULT_ANCHOR_BANK_RELPATH,
    ) -> StoredArtifact:
        return (store or ArtifactStore()).write_json(relative, self.to_dict())


def build_anchor_bank(
    *,
    train_json: Path = DEFAULT_TRAIN_JSON,
    seed: int = 0,
    scan_limit: int = 40_000,
    theorem_limit: int = 80,
    min_reference_length: int = 3,
    max_reference_length: int | None = 24,
    max_anchors_per_theorem: int = 3,
    max_prefix_length: int | None = 12,
    rederive_every: int = 1,
    policy: TacticPolicy | None = None,
    config: LeanToolchainConfig | None = None,
    allow_multiline_tactics: bool = False,
    verbose: bool = True,
) -> AnchorBank:
    """Build the HC-V0.6 anchored bank.  Requires a live Lean toolchain; never degrades silently.

    Selection is a pure function of ``(train_json, scan_limit, seed, filters)``.  It runs before
    any Lean process starts and cannot see a Solver — this module imports no model client.  The
    four sealed splits are refused by :func:`assert_not_sealed` before any I/O.
    """

    assert_not_sealed(train_json)
    config = config or LeanToolchainConfig.from_env()
    policy = policy or TacticPolicy.record_only()
    report = require_toolchain(config)
    oleans = count_oleans(config)

    started = time.monotonic()
    selection = select_candidates(
        train_json=train_json,
        min_horizon=min_reference_length,
        limit=theorem_limit,
        seed=seed,
        scan_limit=scan_limit,
        policy=policy,
        mathlib_root=config.mathlib_root,
        max_horizon=max_reference_length,
        allow_multiline_tactics=allow_multiline_tactics,
    )
    selection_s = time.monotonic() - started
    if verbose:
        print(
            f"selected {len(selection.probes)} theorems from {selection.scanned} records in "
            f"{selection_s:.1f}s; record-level leakage={selection.leakage.to_dict()}",
            flush=True,
        )

    discards = AnchorLedger()
    for key, value in selection.discards.to_dict().items():
        discards.record(f"SELECTION_{key}", value)
    anchors: list[Anchor] = []
    theorems: list[dict[str, Any]] = []
    derive_started = time.monotonic()
    for record, probe in zip(selection.records, selection.probes, strict=True):
        result = derive_theorem_anchors(
            record,
            probe,
            report=report,
            config=config,
            policy=policy,
            max_anchors_per_theorem=max_anchors_per_theorem,
            max_prefix_length=max_prefix_length,
            seed=seed,
        )
        anchors.extend(result.anchors)
        discards.merge(result.discards)
        theorems.append(result.to_dict())
        if verbose:
            print(
                f"  {len(result.anchors)} anchors  {result.wall_s:5.1f}s  "
                f"(+{result.prefix_steps_accepted}/-{result.prefix_steps_rejected} steps)  "
                f"{result.problem_id[:76]}",
                flush=True,
            )
    derive_s = time.monotonic() - derive_started

    rederivation = verify_rederivability(
        anchors, config=config, policy=policy, every=rederive_every, seed=seed, verbose=False
    )
    if verbose:
        print(
            f"re-derivability: {rederivation.matched}/{rederivation.anchors_checked} "
            f"({rederivation.rate:.4f}) over {rederivation.theorems_checked} theorems "
            f"in {rederivation.wall_s:.1f}s",
            flush=True,
        )

    total_s = time.monotonic() - started
    return AnchorBank(
        anchors=tuple(anchors),
        selection={
            "train_json": str(train_json),
            "split": "train",
            "seed": seed,
            "scan_limit": scan_limit,
            "theorem_limit": theorem_limit,
            "min_reference_length": min_reference_length,
            "max_reference_length": max_reference_length,
            "max_anchors_per_theorem": max_anchors_per_theorem,
            "max_prefix_length": max_prefix_length,
            "allow_multiline_tactics": allow_multiline_tactics,
            "tactic_policy": f"{policy.name}:{policy.policy_id}",
            "records_scanned": selection.scanned,
            "theorems_selected": len(selection.probes),
            "depth_rule": (
                "depth 0 when open, then evenly spaced quantiles of the remaining open depths; "
                "fixed rule, no RNG, independent of any Solver outcome"
            ),
        },
        toolchain={
            "lean_version_string": report.lean_version_string,
            "toolchain": report.toolchain,
            "mathlib_root": str(config.mathlib_root),
            "olean_count": oleans,
            "max_heartbeats": config.max_heartbeats,
        },
        leakage={
            "record_level": selection.leakage.to_dict(),
            "anchor_level": {
                key: value for key, value in discards.to_dict().items() if key.startswith("LEAKS_")
            },
            "criteria": [
                LeakReason.TACTIC_IN_STATE_BEFORE.value,
                LeakReason.FULL_NAME_IN_STATE.value,
                AnchorDiscardReason.LEAKS_PREFIX_TACTIC_IN_STATE.value,
            ],
            "baseline_note": (
                "record-level figures are directly comparable with the audit's measured baseline "
                "(92 leaking steps of 250,814; 2 leaking proofs of 59,557) because the criterion "
                "is unchanged: LeakageFilter.scan_record. The anchor-level figures are a "
                "different measurement -- the same criteria applied to the LIVE state a Solver "
                "would see -- plus one conservative extra filter on already-played prefix "
                "tactics, and must not be pooled with them."
            ),
        },
        discards=discards.to_dict(),
        rederivation=rederivation.to_dict(),
        cost={
            "selection_s": round(selection_s, 2),
            "derivation_s": round(derive_s, 2),
            "rederivation_s": round(rederivation.wall_s, 2),
            "total_s": round(total_s, 2),
            "seconds_per_anchor_derivation": round(derive_s / max(1, len(anchors)), 4),
            "seconds_per_anchor_including_rederivation": round(total_s / max(1, len(anchors)), 4),
            "seconds_per_theorem_derivation": round(derive_s / max(1, len(selection.probes)), 4),
        },
        theorems=tuple(theorems),
        generated_utc=datetime.now(UTC).isoformat(timespec="seconds"),
    )


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--train-json", type=Path, default=DEFAULT_TRAIN_JSON)
    parser.add_argument("--artifacts-root", type=Path, default=Path("artifacts"))
    parser.add_argument("--out", type=Path, default=DEFAULT_ANCHOR_BANK_RELPATH)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scan-limit", type=int, default=40_000)
    parser.add_argument("--theorem-limit", type=int, default=80)
    parser.add_argument("--min-reference-length", type=int, default=3)
    parser.add_argument("--max-reference-length", type=int, default=24)
    parser.add_argument("--max-anchors-per-theorem", type=int, default=3)
    parser.add_argument("--max-prefix-length", type=int, default=12)
    parser.add_argument(
        "--rederive-every",
        type=int,
        default=1,
        help="re-derive every Nth theorem in a second independent session (1 = all)",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = check_toolchain(LeanToolchainConfig.from_env())
    if not report.available:
        print(report.describe(), file=sys.stderr)
        return 2

    bank = build_anchor_bank(
        train_json=args.train_json,
        seed=args.seed,
        scan_limit=args.scan_limit,
        theorem_limit=args.theorem_limit,
        min_reference_length=args.min_reference_length,
        max_reference_length=args.max_reference_length,
        max_anchors_per_theorem=args.max_anchors_per_theorem,
        max_prefix_length=args.max_prefix_length,
        rederive_every=args.rederive_every,
        verbose=not args.quiet,
    )
    stored = bank.write(store=ArtifactStore(args.artifacts_root), relative=args.out)
    stats = bank.stats
    print(
        f"\nwrote {stored.path} ({stats.anchors} anchors, "
        f"{stats.distinct_theorems} theorems, {stats.distinct_files} files)\n"
        f"  evaluation-universe hash : {bank.content_hash}\n"
        f"  artefact sha256          : {stored.sha256}\n"
        f"  re-derivability          : {bank.rederivation['matched']}/"
        f"{bank.rederivation['anchors_checked']} ({bank.rederivation['rate']})\n"
        f"  seconds per anchor       : {bank.cost['seconds_per_anchor_derivation']} "
        f"(derivation) / {bank.cost['seconds_per_anchor_including_rederivation']} (total)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
