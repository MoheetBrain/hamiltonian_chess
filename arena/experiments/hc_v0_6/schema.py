"""The tidy result schema for HC-V0.6: one row per ``(anchor, arm, replicate)`` cell.

This is the **contract** between the runner (which writes it) and the analysis (which reads it).
It is written before any assay data exists so that the runner cannot quietly change what an
outcome means, and so that no analysis choice can be made after seeing an outcome.

Manual §30.7 requires raw per-task outcomes to be stored, not only means.  :class:`CellOutcome`
is therefore the *atom*: every mean, interval and p-value HC-V0.6 reports is a function of a
:class:`CellTable` of these rows and of nothing else.

Design vocabulary (``docs/HC_V0_6_DESIGN_BRIEF.md`` §1-§4)
---------------------------------------------------------
* **anchor** — a re-derivable open Lean goal state, identified by
  ``(theorem_full_name, prefix_tactics, toolchain, mathlib commit)``.  The live ``sid`` is not the
  anchor; the recipe plus the re-elaboration key is, so ``reelaboration_key`` is carried on every
  row and is what :meth:`CellTable.anchor_universe_hash` binds.
* **cluster** — the mathlib **file**.  Theorems in one file are not independent (§30.6), so the
  cluster, not the row, is the resampling unit.
* **arm** — the label a comparison contrasts, and (except for the C1 identity control, which is
  built inside ``R_A``) also the renderer that produced the bytes.  ``R_A_PRIME`` is the design
  brief's §9.4 byte-perturbation control: a *distinct* renderer whose output differs from ``R_A``
  in whitespace only.  It is bijective and semantically null, and it sits between the
  byte-identical C1 control and the restructured ``R_B``.
* **replicate** — a repeated draw within a cell.  ``k`` is frozen from the runtime-noise
  measurement and the power analysis before the assay runs.  It is *not* automatically an
  independent draw: if the Solver is call-for-call deterministic under the frozen decoding, the
  replicates of a cell are byte-identical copies and ``k = 1`` is the honest design
  (``arena.experiments.hc_v0_6.power.ReplicateModel``).

The primary endpoint: ``KERNEL_ACCEPTED_STATE_CHANGE``
------------------------------------------------------
A cell scores **1** iff Lean accepted the Solver's *first* action **and** that action either
closed the task or changed the backend mathematical state.  A **no-op scores 0**: a tactic the
elaborator tolerates without moving the mathematics (``skip``, a vacuous ``simp only []``) is not
progress, and an endpoint that counted it would be maximised by emitting one
(``docs/HC_V0_5_REDTEAM.md`` measured exactly that: ``skip`` elaborates, leaves ``goal_digest``
unchanged, and would have scored under the old ``ACCEPTED_TRANSITION`` endpoint).

The endpoint is carried by the :class:`StepResult` vocabulary rather than by a separate boolean,
so it cannot drift apart from what the runner recorded: ``ACCEPTED_TRANSITION`` means *accepted
and the declared state moved (or closed)*, ``ACCEPTED_NO_OP`` means *accepted and nothing moved*,
and only the former is in :data:`ENDPOINT_EVENT_RESULTS`.  ``ENVIRONMENT_ERROR`` and
``TOOL_TIMEOUT`` stay separately typed and are **never** mathematical zeros: they are excluded by
:attr:`CellOutcome.analysable`, not scored as failures.

Nothing in this module imports the live Lean or Solver stack.  The analysis must be runnable, and
testable, with no model and no REPL.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from arena.canonical.schema import stable_hash
from arena.evolution.record import InterventionClass

__all__ = [
    "ACCEPTING_RESULTS",
    "ENDPOINT_EVENT_RESULTS",
    "NON_REPRODUCIBLE_CELL_FIELDS",
    "PRIMARY_ENDPOINT",
    "Arm",
    "CellOutcome",
    "CellTable",
    "DesignViolation",
    "PairedCells",
    "ParseStatus",
    "SCHEMA_VERSION",
    "StepResult",
    "extract_pair",
]

#: Bumped from ``v1.0.0`` when the owner redefined the primary endpoint from
#: ``ACCEPTED_TRANSITION`` (any elaborator acceptance) to ``KERNEL_ACCEPTED_STATE_CHANGE``
#: (acceptance that closed the task or moved the backend state).  The version is part of the
#: content hash, so a table written under the old endpoint cannot be silently pooled with one
#: written under the new one.
SCHEMA_VERSION: Final = "hc-v0.6-cell-outcome-v1.1.0"

#: The name of the primary endpoint, so that reports quote it rather than paraphrase it.
PRIMARY_ENDPOINT: Final = "KERNEL_ACCEPTED_STATE_CHANGE"

#: Row fields that vary between two replays of the *same* cell without changing what happened
#: mathematically, and are therefore outside :attr:`CellOutcome.content_core` and outside every
#: hash built from it.  They are excluded at the ROW level on purpose: the run manifest strips
#: non-deterministic keys from its own payload, but the cell table reaches it as a single digest,
#: so a field left in here is a field the manifest can no longer remove
#: (``docs/HC_V0_6_REDTEAM.md`` RT-V06-08).
NON_REPRODUCIBLE_CELL_FIELDS: Final[frozenset[str]] = frozenset(
    {"latency_ms", "prompt_tokens", "response_tokens"}
)


class Arm(StrEnum):
    """The four arms of the design brief §9.4 roster.

    The ordering below is the ordering of the intervention ladder, and it is the reason there are
    four rather than two: ``R_A`` vs ``R_A`` changes nothing, ``R_A_PRIME`` changes bytes but not
    structure, ``R_B`` changes structure but not information, ``R_ABLATED`` changes information.
    An effect can only be attributed to *structure* if the rung below it is silent (§9.4).
    """

    #: Baseline: Lean's native pretty-printed tactic state (`BackendNativeRenderer`).  The C1
    #: identity control is built inside this arm from its own replicates (design brief §9.2).
    R_A = "R_A"
    #: `R_ONLY`, bijective, semantically null: the baseline bytes perturbed in **whitespace only**
    #: (design brief §9.4).  Compared against ``R_A`` this is C1b, the byte-perturbation control.
    R_A_PRIME = "R_A_PRIME"
    #: The `R_ONLY` variant under test: the same characters re-laid-out (design brief §2).
    R_B = "R_B"
    #: Goal text withheld, goal count and metadata retained.  A `P_CHANGE` positive control (C2).
    #: It is not a representation and must never be reported as one.
    R_ABLATED = "R_ABLATED"

    @property
    def renderer_id(self) -> str:
        """The renderer that produced this arm's bytes.  Every arm has its own."""

        return str(self.value)

    @property
    def intervention_class(self) -> InterventionClass:
        """Manual §6.26 class of the intervention this arm represents against ``R_A``."""

        return InterventionClass.P_CHANGE if self is Arm.R_ABLATED else InterventionClass.R_ONLY


class ParseStatus(StrEnum):
    """How the Solver's emission ended, before Lean ever saw it.

    The vocabulary mirrors :class:`arena.trajectory.solver.ProposalStatus` but is **declared
    locally on purpose**: the analysis contract must not break when the live solver module
    changes, and the analysis must be importable without the Lean/Ollama stack.  Any new member
    there must be added here deliberately, which is the point.
    """

    OK = "OK"
    PARSE_FAILURE = "PARSE_FAILURE"
    TRUNCATED = "TRUNCATED"
    PROMPT_OVER_BUDGET = "PROMPT_OVER_BUDGET"
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"

    @property
    def reached_lean(self) -> bool:
        return self is ParseStatus.OK


class StepResult(StrEnum):
    """What Lean did with the proposed tactic (mirrors §14.4 / ``ActionResult``).

    ``ENVIRONMENT_ERROR`` and ``TOOL_TIMEOUT`` are the harness failing and are **never**
    mathematical failures; they are recorded so that a cell lost to the harness can be excluded
    explicitly rather than silently counted as a rejection.
    """

    ACCEPTED_TRANSITION = "ACCEPTED_TRANSITION"
    #: Lean accepted the action and it changed nothing: the goal state after is the same declared
    #: state as before, and no goal closed.  Accepted, but NOT an event under the primary endpoint
    #: ``KERNEL_ACCEPTED_STATE_CHANGE`` -- a tactic that the elaborator tolerates without moving
    #: the mathematics is not progress, and counting it would let a policy score by emitting
    #: ``skip``.  It is a Solver outcome, not a harness failure.
    ACCEPTED_NO_OP = "ACCEPTED_NO_OP"
    REJECTED_INVALID_ACTION = "REJECTED_INVALID_ACTION"
    PARSE_FAILURE = "PARSE_FAILURE"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    UNSUPPORTED = "UNSUPPORTED"
    #: The cell was never run (prompt refused before sending, transport dead).
    NOT_ATTEMPTED = "NOT_ATTEMPTED"

    @property
    def harness_failure(self) -> bool:
        return self in {
            StepResult.TOOL_TIMEOUT,
            StepResult.ENVIRONMENT_ERROR,
            StepResult.NOT_ATTEMPTED,
        }


#: The only step result that is an event under the primary endpoint
#: ``KERNEL_ACCEPTED_STATE_CHANGE``: Lean accepted the first action AND that action either
#: closed the task or changed the declared backend state.  ``ACCEPTED_NO_OP`` is deliberately
#: absent -- that absence *is* the endpoint definition, and the set is frozen so it cannot be
#: widened by a later edit without changing this line.
ENDPOINT_EVENT_RESULTS: Final[frozenset[StepResult]] = frozenset({StepResult.ACCEPTED_TRANSITION})

#: Legacy spelling, kept because ``arena/experiments/hc_v0_6/__init__.py`` re-exports it.  It is
#: the SAME set: "accepting" now means "an event under ``KERNEL_ACCEPTED_STATE_CHANGE``", not
#: "the elaborator did not complain".  New code should read
#: :data:`ENDPOINT_EVENT_RESULTS`.
ACCEPTING_RESULTS: Final[frozenset[StepResult]] = ENDPOINT_EVENT_RESULTS

#: What Lean *accepted*, which is strictly larger than what the endpoint counts.  Private, and
#: descriptive only: the difference between the two sets is the no-op rate, and reporting it is
#: how the endpoint change stays auditable instead of merely asserted.
_KERNEL_ACCEPTED: Final[frozenset[StepResult]] = frozenset(
    {StepResult.ACCEPTED_TRANSITION, StepResult.ACCEPTED_NO_OP}
)


class DesignViolation(ValueError):
    """The table does not have the shape the preregistered design requires."""


@dataclass(frozen=True, slots=True)
class CellOutcome:
    """One ``(anchor, arm, replicate)`` cell: the atom of the HC-V0.6 result set.

    The primary endpoint :attr:`kernel_accepted_state_change` is *derived* from ``step_result``,
    never supplied, so that a writer cannot claim an event the kernel did not give -- and, since
    ``ACCEPTED_NO_OP`` is a distinct ``step_result``, cannot claim one for an action that moved
    nothing either.
    """

    anchor_id: str
    #: The mathlib **file** the theorem lives in.  The clustering / resampling unit (§30.6).
    cluster_id: str
    theorem: str
    #: The re-derivability key of the anchored state (`KernelStateIdentity.reelaboration_key`).
    reelaboration_key: str
    arm: Arm
    renderer_id: str
    intervention_class: InterventionClass
    replicate_index: int
    step_result: StepResult
    parse_status: ParseStatus
    closed_all_goals: bool
    prompt_sha256: str
    prompt_tokens: int
    response_tokens: int
    latency_ms: int
    solver_digest: str
    proposed_tactic: str | None = None

    def __post_init__(self) -> None:
        if not self.anchor_id or not self.cluster_id or not self.theorem:
            raise DesignViolation("anchor_id, cluster_id and theorem must all be non-empty")
        if not self.reelaboration_key:
            raise DesignViolation(f"{self.anchor_id}: reelaboration_key must be non-empty")
        if self.replicate_index < 0:
            raise DesignViolation(f"{self.anchor_id}: replicate_index must be non-negative")
        if self.renderer_id != self.arm.renderer_id:
            raise DesignViolation(
                f"{self.anchor_id}: arm {self.arm} renders with {self.arm.renderer_id}, "
                f"not {self.renderer_id!r}"
            )
        if self.intervention_class is not self.arm.intervention_class:
            raise DesignViolation(
                f"{self.anchor_id}: arm {self.arm} is {self.arm.intervention_class}, "
                f"not {self.intervention_class}"
            )
        if not self.parse_status.reached_lean and self.step_result in _KERNEL_ACCEPTED:
            raise DesignViolation(
                f"{self.anchor_id}: parse status {self.parse_status} never reached Lean, "
                "so Lean cannot have accepted it"
            )
        if self.closed_all_goals and self.step_result not in ENDPOINT_EVENT_RESULTS:
            raise DesignViolation(
                f"{self.anchor_id}: closed_all_goals is an endpoint event "
                f"({PRIMARY_ENDPOINT}), so it cannot be recorded against "
                f"{self.step_result.value}; an action that closed the task changed the state"
            )
        if min(self.prompt_tokens, self.response_tokens, self.latency_ms) < 0:
            raise DesignViolation(f"{self.anchor_id}: token and latency counts must be >= 0")

    @property
    def kernel_accepted_state_change(self) -> bool:
        """The primary endpoint: ``KERNEL_ACCEPTED_STATE_CHANGE`` for this cell.

        1 iff Lean accepted the Solver's first action **and** that action closed the task or
        changed the backend mathematical state.  ``ACCEPTED_NO_OP`` -- accepted, moved nothing --
        is 0, and so is every harness failure (which :attr:`analysable` excludes rather than
        scores).
        """

        return self.step_result in ENDPOINT_EVENT_RESULTS

    @property
    def accepted(self) -> bool:
        """Legacy spelling of :attr:`kernel_accepted_state_change`.

        Kept because the runner's own tests read it.  It is **not** "the elaborator did not
        complain": an ``ACCEPTED_NO_OP`` cell reads ``False`` here.  Use
        :attr:`kernel_accepted_state_change` in new code, and :attr:`kernel_accepted` when what
        is wanted really is Lean's raw verdict.
        """

        return self.kernel_accepted_state_change

    @property
    def kernel_accepted(self) -> bool:
        """Lean's raw verdict, which is **not** the endpoint: a no-op is accepted and scores 0.

        Descriptive only.  It exists so that the gap between "Lean accepted" and "the endpoint
        fired" is measurable -- the no-op rate is exactly the difference -- rather than invisible.
        """

        return self.step_result in _KERNEL_ACCEPTED

    @property
    def analysable(self) -> bool:
        """False when the harness, not the Solver, decided the cell (§14.4)."""

        return not self.step_result.harness_failure

    @property
    def cell_key(self) -> tuple[str, Arm, int]:
        return (self.anchor_id, self.arm, self.replicate_index)

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "cluster_id": self.cluster_id,
            "theorem": self.theorem,
            "reelaboration_key": self.reelaboration_key,
            "arm": str(self.arm.value),
            "renderer_id": self.renderer_id,
            "intervention_class": str(self.intervention_class.value),
            "replicate_index": self.replicate_index,
            "step_result": str(self.step_result.value),
            "parse_status": str(self.parse_status.value),
            "kernel_accepted_state_change": self.kernel_accepted_state_change,
            "kernel_accepted": self.kernel_accepted,
            "accepted": self.accepted,
            "closed_all_goals": self.closed_all_goals,
            "prompt_sha256": self.prompt_sha256,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "latency_ms": self.latency_ms,
            "solver_digest": self.solver_digest,
            "proposed_tactic": self.proposed_tactic,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CellOutcome:
        row = cls(
            anchor_id=str(payload["anchor_id"]),
            cluster_id=str(payload["cluster_id"]),
            theorem=str(payload["theorem"]),
            reelaboration_key=str(payload["reelaboration_key"]),
            arm=Arm(payload["arm"]),
            renderer_id=str(payload["renderer_id"]),
            intervention_class=InterventionClass(payload["intervention_class"]),
            replicate_index=int(payload["replicate_index"]),
            step_result=StepResult(payload["step_result"]),
            parse_status=ParseStatus(payload["parse_status"]),
            closed_all_goals=bool(payload["closed_all_goals"]),
            prompt_sha256=str(payload["prompt_sha256"]),
            prompt_tokens=int(payload["prompt_tokens"]),
            response_tokens=int(payload["response_tokens"]),
            latency_ms=int(payload["latency_ms"]),
            solver_digest=str(payload["solver_digest"]),
            proposed_tactic=(
                None if payload.get("proposed_tactic") is None else str(payload["proposed_tactic"])
            ),
        )
        for key, derived in (
            ("kernel_accepted_state_change", row.kernel_accepted_state_change),
            ("accepted", row.accepted),
            ("kernel_accepted", row.kernel_accepted),
        ):
            declared = payload.get(key)
            if declared is not None and bool(declared) != derived:
                raise DesignViolation(
                    f"{row.anchor_id}: stored {key}={declared!r} contradicts "
                    f"step_result={row.step_result}"
                )
        return row

    @property
    def content_core(self) -> dict[str, Any]:
        """:meth:`to_dict` minus the fields that vary run to run without changing the outcome.

        ``latency_ms`` and the two token counts are machine load and tokeniser bookkeeping: two
        replays of one cell that produced the same tactic and the same Lean verdict differ in
        them and in nothing that matters.  The manifest's own ``_strip`` cannot reach them,
        because by the time it runs the whole table has already been reduced to one opaque
        digest -- so the exclusion has to happen **here**, before the digest is taken, or it does
        not happen at all (``docs/HC_V0_6_REDTEAM.md`` RT-V06-08).

        Everything that decides an endpoint stays in: ``step_result``, ``parse_status``,
        ``closed_all_goals``, ``proposed_tactic``, the prompt hash and the solver digest.
        """

        volatile = frozenset(NON_REPRODUCIBLE_CELL_FIELDS)
        return {key: value for key, value in self.to_dict().items() if key not in volatile}

    @property
    def content_hash(self) -> str:
        """The reproducible identity of this cell: :attr:`content_core`, not :meth:`to_dict`."""

        return stable_hash(self.content_core)


@dataclass(frozen=True, slots=True)
class CellTable:
    """An immutable, canonically ordered set of :class:`CellOutcome` rows.

    Construction sorts the rows and rejects duplicate ``(anchor, arm, replicate)`` keys, so the
    content hash of a result set is a function of its content and not of write order.
    """

    rows: tuple[CellOutcome, ...]

    def __init__(self, rows: Iterable[CellOutcome]) -> None:
        ordered = tuple(
            sorted(rows, key=lambda row: (row.anchor_id, str(row.arm.value), row.replicate_index))
        )
        duplicates = [
            key for key, count in Counter(r.cell_key for r in ordered).items() if count > 1
        ]
        if duplicates:
            raise DesignViolation(f"duplicate cells: {sorted(map(str, duplicates))[:5]}")
        object.__setattr__(self, "rows", ordered)
        self._check_anchor_metadata_is_constant()

    def _check_anchor_metadata_is_constant(self) -> None:
        """One anchor is one state: its cluster, theorem and key may not vary between rows."""

        seen: dict[str, tuple[str, str, str]] = {}
        for row in self.rows:
            identity = (row.cluster_id, row.theorem, row.reelaboration_key)
            previous = seen.setdefault(row.anchor_id, identity)
            if previous != identity:
                raise DesignViolation(
                    f"anchor {row.anchor_id} carries two identities: {previous} vs {identity}"
                )

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[CellOutcome]:
        return iter(self.rows)

    # ------------------------------------------------------------------ shape

    @property
    def arms(self) -> tuple[Arm, ...]:
        return tuple(sorted({row.arm for row in self.rows}, key=lambda arm: str(arm.value)))

    @property
    def anchor_ids(self) -> tuple[str, ...]:
        return tuple(sorted({row.anchor_id for row in self.rows}))

    @property
    def cluster_ids(self) -> tuple[str, ...]:
        return tuple(sorted({row.cluster_id for row in self.rows}))

    @property
    def cluster_of(self) -> Mapping[str, str]:
        return {row.anchor_id: row.cluster_id for row in self.rows}

    def rows_for(self, arm: Arm) -> tuple[CellOutcome, ...]:
        return tuple(row for row in self.rows if row.arm is arm)

    def replicate_counts(self, arm: Arm) -> Mapping[str, int]:
        counts: Counter[str] = Counter()
        for row in self.rows_for(arm):
            counts[row.anchor_id] += 1
        return dict(counts)

    # ------------------------------------------------------------------ identity

    @property
    def anchor_universe_hash(self) -> str:
        """The manifest's ``evaluation-universe hash`` (§30.3): the anchored bank, not the run.

        Depends only on which anchored states were played -- their ids, clusters, theorems and
        re-elaboration keys.  Two runs of the same bank share it; a bank with one anchor added or
        removed does not.
        """

        universe = sorted(
            {
                (row.anchor_id, row.cluster_id, row.theorem, row.reelaboration_key)
                for row in self.rows
            }
        )
        return stable_hash({"schema": SCHEMA_VERSION, "anchors": [list(a) for a in universe]})

    @property
    def content_hash(self) -> str:
        """Hash of every raw outcome's :attr:`CellOutcome.content_core`.

        Changes if a single cell's *mathematics* changes -- its Lean verdict, its parse status,
        the tactic proposed, the prompt it was shown, the model that answered.  Does **not**
        change when only latency or token counts differ, because two runs that produced the same
        outcomes are the same result and must hash the same
        (``docs/HC_V0_6_REDTEAM.md`` RT-V06-08).
        """

        return stable_hash(
            {"schema": SCHEMA_VERSION, "rows": [row.content_core for row in self.rows]}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "anchor_universe_hash": self.anchor_universe_hash,
            "rows": [row.to_dict() for row in self.rows],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CellTable:
        table = cls(CellOutcome.from_dict(row) for row in payload["rows"])
        declared = payload.get("anchor_universe_hash")
        if declared is not None and declared != table.anchor_universe_hash:
            raise DesignViolation(
                f"anchor_universe_hash mismatch: stored {declared}, recomputed "
                f"{table.anchor_universe_hash}"
            )
        return table

    # ------------------------------------------------------------------ storage

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for row in self.rows:
                handle.write(json.dumps(row.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")

    @classmethod
    def read_jsonl(cls, path: Path) -> CellTable:
        with path.open(encoding="utf-8") as handle:
            return cls(CellOutcome.from_dict(json.loads(line)) for line in handle if line.strip())

    # ------------------------------------------------------------------ validation

    def validate_balanced(self, arms: Sequence[Arm], *, replicates: int) -> None:
        """Every anchor carries every named arm with exactly ``replicates`` replicates.

        The preregistered design is balanced, so an unbalanced table means cells were lost.
        Callers that intend to analyse an unbalanced table must say so explicitly by not calling
        this -- the estimators handle unequal ``k`` correctly, but silence about it is a defect.
        """

        if replicates < 1:
            raise DesignViolation("replicates must be at least 1")
        wanted = tuple(arms)
        if not wanted:
            raise DesignViolation("at least one arm is required")
        present: dict[tuple[str, Arm], int] = defaultdict(int)
        for row in self.rows:
            present[(row.anchor_id, row.arm)] += 1
        problems: list[str] = []
        for anchor in self.anchor_ids:
            for arm in wanted:
                count = present.get((anchor, arm), 0)
                if count != replicates:
                    problems.append(f"{anchor}/{arm.value}: {count} != {replicates}")
        if problems:
            raise DesignViolation(f"unbalanced design ({len(problems)}): {problems[:5]}")

    def drop_harness_failures(self) -> CellTable:
        """A table with harness-decided cells removed (§14.4: never a mathematical failure)."""

        return CellTable(row for row in self.rows if row.analysable)

    def harness_failures_by_arm(self) -> dict[Arm, int]:
        """Per arm, how many rows the harness decided -- the count :func:`extract_pair` drops.

        Reported beside every contrast so that a reader can see what was excluded rather than
        having to infer it from a shrunken ``n_anchors``.
        """

        counts = dict.fromkeys(self.arms, 0)
        for row in self.rows:
            if not row.analysable:
                counts[row.arm] += 1
        return counts

    def unanalysable_by_arm(self, arms: Sequence[Arm] | None = None) -> dict[Arm, int]:
        """Per arm, how many of this table's anchors carry **no** analysable cell for that arm.

        This is the quantity the missingness gate is about (spec §10, §13), and it is deliberately
        anchor-counted rather than row-counted: an anchor loses its pairing whether the arm's cell
        came back ``ENVIRONMENT_ERROR`` or never appeared in the table at all.  Both routes are
        real -- the runner records harness failures as rows, and a theorem that died mid-anchor
        leaves the remaining arms absent -- and only the anchor count sees both.

        Equal counts across arms mean the loss was arm-independent, which is what the gate
        requires; any difference is outcome O7 and invalidates the run.
        """

        wanted = tuple(self.arms if arms is None else arms)
        analysable: set[tuple[str, Arm]] = {
            (row.anchor_id, row.arm) for row in self.rows if row.analysable
        }
        anchors = self.anchor_ids
        return {
            arm: sum(1 for anchor in anchors if (anchor, arm) not in analysable) for arm in wanted
        }


@dataclass(frozen=True, slots=True)
class PairedCells:
    """The paired structure of one two-arm comparison, extracted from a :class:`CellTable`.

    Every estimator in :mod:`arena.experiments.hc_v0_6.estimators` consumes this and nothing else,
    so the pairing rule lives in exactly one place.  Arrays are parallel and anchor-ordered, and
    the **raw replicate outcomes are retained** (§30.7) rather than only their counts: the
    replicate-collapse question is a live design choice and cannot be settled from means.
    """

    arm_a: Arm
    arm_b: Arm
    anchor_ids: tuple[str, ...]
    cluster_ids: tuple[str, ...]
    #: Per anchor, the arm's replicate ``KERNEL_ACCEPTED_STATE_CHANGE`` outcomes, in
    #: replicate-index order.  A no-op is ``False`` here, never ``True``.
    a_outcomes: tuple[tuple[bool, ...], ...]
    b_outcomes: tuple[tuple[bool, ...], ...]

    def __post_init__(self) -> None:
        lengths = {
            len(self.anchor_ids),
            len(self.cluster_ids),
            len(self.a_outcomes),
            len(self.b_outcomes),
        }
        if len(lengths) != 1:
            raise DesignViolation("PairedCells arrays must be parallel")
        if not self.anchor_ids:
            raise DesignViolation("PairedCells needs at least one anchor")
        if any(not draws for draws in self.a_outcomes + self.b_outcomes):
            raise DesignViolation("every paired anchor needs at least one replicate in each arm")

    @property
    def n_anchors(self) -> int:
        return len(self.anchor_ids)

    @property
    def n_clusters(self) -> int:
        return len(set(self.cluster_ids))

    @property
    def a_success(self) -> tuple[int, ...]:
        return tuple(sum(draws) for draws in self.a_outcomes)

    @property
    def b_success(self) -> tuple[int, ...]:
        return tuple(sum(draws) for draws in self.b_outcomes)

    @property
    def a_trials(self) -> tuple[int, ...]:
        return tuple(len(draws) for draws in self.a_outcomes)

    @property
    def b_trials(self) -> tuple[int, ...]:
        return tuple(len(draws) for draws in self.b_outcomes)

    @property
    def a_first(self) -> tuple[bool, ...]:
        return tuple(draws[0] for draws in self.a_outcomes)

    @property
    def b_first(self) -> tuple[bool, ...]:
        return tuple(draws[0] for draws in self.b_outcomes)

    @property
    def balanced_replicates(self) -> int | None:
        """``k`` when every cell has the same replicate count, else ``None``."""

        counts = set(self.a_trials) | set(self.b_trials)
        return counts.pop() if len(counts) == 1 else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_a": str(self.arm_a.value),
            "arm_b": str(self.arm_b.value),
            "n_anchors": self.n_anchors,
            "n_clusters": self.n_clusters,
            "balanced_replicates": self.balanced_replicates,
            "anchor_ids": list(self.anchor_ids),
        }


def extract_pair(table: CellTable, arm_a: Arm, arm_b: Arm) -> PairedCells:
    """Pair ``arm_b`` against ``arm_a`` within anchor, keeping only anchors that carry both.

    Dropping half-populated anchors is the only defensible pairing rule: an anchor observed under
    one arm only carries no paired information, and imputing it would invent one.  The number
    dropped is recoverable by comparing ``PairedCells.n_anchors`` with ``len(table.anchor_ids)``.

    **Harness-decided cells are excluded here**, not by the caller.  Spec §4 says
    ``ENVIRONMENT_ERROR`` is separately typed and is *never* a mathematical zero, and this is the
    single place every contrast passes through, so it is the only place the rule can be made
    structural rather than optional.  It used to live in
    :meth:`CellTable.drop_harness_failures`, which nothing called: 20 injected
    ``ENVIRONMENT_ERROR``s on one arm moved a true ``Delta`` of 0.000 to -0.333
    (``docs/HC_V0_6_REDTEAM.md`` RT-V06-01).  An anchor whose cell for one arm was decided by the
    harness therefore loses its *pair* -- it becomes missing, which the missingness gate counts
    (:meth:`CellTable.unanalysable_by_arm`) -- rather than scoring a zero for that arm.
    """

    if arm_a is arm_b:
        raise DesignViolation("a comparison needs two distinct arms")
    by_anchor: dict[str, dict[Arm, list[CellOutcome]]] = defaultdict(lambda: defaultdict(list))
    for row in table.rows:
        if row.arm in (arm_a, arm_b) and row.analysable:
            by_anchor[row.anchor_id][row.arm].append(row)
    cluster_of = table.cluster_of
    anchors: list[str] = []
    clusters: list[str] = []
    a_outcomes: list[tuple[bool, ...]] = []
    b_outcomes: list[tuple[bool, ...]] = []
    for anchor in sorted(by_anchor):
        arms = by_anchor[anchor]
        left, right = arms.get(arm_a, []), arms.get(arm_b, [])
        if not left or not right:
            continue
        anchors.append(anchor)
        clusters.append(cluster_of[anchor])
        a_outcomes.append(
            tuple(
                row.kernel_accepted_state_change
                for row in sorted(left, key=lambda row: row.replicate_index)
            )
        )
        b_outcomes.append(
            tuple(
                row.kernel_accepted_state_change
                for row in sorted(right, key=lambda row: row.replicate_index)
            )
        )
    if not anchors:
        raise DesignViolation(f"no anchor carries both {arm_a.value} and {arm_b.value}")
    return PairedCells(
        arm_a=arm_a,
        arm_b=arm_b,
        anchor_ids=tuple(anchors),
        cluster_ids=tuple(clusters),
        a_outcomes=tuple(a_outcomes),
        b_outcomes=tuple(b_outcomes),
    )
