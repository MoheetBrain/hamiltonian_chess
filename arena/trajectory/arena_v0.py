"""``M_L`` — the inner MDP over live, kernel-verified Lean state.

``M_L = (S, A, T_K, r, Ω_L)`` from ``docs/HAMILTONIAN_CHESS_META_MDP.md`` §1, with each symbol
placed where the meta-MDP puts it and nowhere else:

``S``
    Owned by the formal backend.  The arena hands out a
    :class:`~arena.trajectory.schema.BackendStateEnvelope`; it never claims a canonical form for
    it (``docs/CANONICAL_VNEXT_PILOT.md``: 0 of 368 Lean states map losslessly into
    ``arena-canonical-v0.1.0``).

``A``
    See :class:`ActionSpaceSpec`.  For V0 the Solver proposes a **Lean 4 tactic string**.  The
    space is not enumerable and the arena proposes no candidates — this is stated rather than
    dressed up as a K-way choice, unlike every other environment in this repository.

``T_K``
    ``arena.trajectory.lean_backend``.  The Lean elaborator executes the transition; the Lean
    kernel decides closure via ``#print axioms``.

``r``
    Verifier-grounded and deliberately thin for V0: ``+1`` exactly when the episode terminates
    ``CLOSED_VERIFIED`` (goals closed **and** the re-elaborated declaration depends on no
    ``sorryAx``), ``0`` otherwise.  ``docs/HAMILTONIAN_CHESS_META_MDP.md`` lists richer reward as
    MISSING; inventing shaping here would be inventing a measurement.

``Ω_L``
    **Injected, not baked in.**  The arena yields the backend-native envelope and a separate
    object implementing :class:`StateRenderer` maps it into a language.  The default renderer is
    the identity on the backend's own fields, so V0 measures capability, not representation; a
    language genome can later supply its own renderer through the same seam.

Also here: a leakage filter with counted drops, a seeded bank builder, and a CLI — plus **two
replays that must never be confused**, because confusing them is what RT-03 was:

:class:`ReplayDriver`
    executes a *recorded reference proof* live.  It is the ground-truth **generator**: it answers
    "is this mathlib proof still reproducible?" and it produces banks.

:func:`relive_trajectory`
    executes *a stored artefact's own actions* live.  It is the **verifier** behind
    ``--relive``: it answers "did this record's actions really do what the record says?".  Until
    RT-03 was fixed, ``--relive`` called the generator, so it re-verified the source and never
    read ``trajectory.actions`` at all.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from arena.trajectory.lean_backend import (
    DEFAULT_MATHLIB_ROOT,
    SEALED_SPLIT_PATHS,
    DiscardLedger,
    KernelVerification,
    LeanReplSession,
    LeanTheoremProbe,
    LeanToolchainConfig,
    ProbeDiscardReason,
    StepOutcome,
    StepResult,
    TacticPolicy,
    ToolchainReport,
    build_probe,
    check_toolchain,
    count_oleans,
    iter_leandojo_records,
    verify_closed_script,
)
from arena.trajectory.schema import (
    Actor,
    BackendStateEnvelope,
    EvidenceKind,
    FormalBackend,
    SourceVersion,
    TerminalStatus,
    TrajectoryAction,
    TrajectoryProvenance,
    Verdict,
    VerifiedTrajectory,
    VerifierEvidence,
    content_sha256,
    derive_trajectory_id,
)

GENERATOR_ID = "arena/trajectory/arena_v0.py@v0"
BANK_SCHEMA = "arena-verified-trajectory-bank-v0"

#: Default problem bank.  ``random/train.json`` is the DEVELOPMENT split; the four sealed splits
#: are refused by ``lean_backend.assert_not_sealed`` and are never opened here.
DEFAULT_TRAIN_JSON = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4/random/train.json"
)

CONTAMINATION_NOTE = (
    "mathlib4 is HISTORICALLY_EXPOSED and exposure is transitive: no LeanDojo split establishes "
    "pretraining-cleanliness. This measures long-horizon EXECUTION under kernel verification, "
    "not long-horizon discovery."
)


# ---------------------------------------------------------------------------------------------
# Omega_L: the renderer seam
# ---------------------------------------------------------------------------------------------


@runtime_checkable
class StateRenderer(Protocol):
    """``Ω_L``: how a backend-native state is shown to a Solver.

    The arena depends on this protocol and on nothing about any particular language.  A language
    genome supplies an implementation; the arena never projects Lean state into
    ``arena-canonical-v0.1.0`` and a renderer must not pretend to either — it renders the
    envelope's own fields.
    """

    @property
    def renderer_id(self) -> str: ...

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class BackendNativeRenderer:
    """The default ``Ω_L``: the backend's own fields, unmodified.

    Using it means the observation is Lean's pretty-printer, so **every language would receive
    byte-identical input**.  That is intentional for V0: this instrument measures capability
    (horizon), not representation.  Running a representation comparison on this arena without
    first supplying genuinely different renderers would compare eight identical inputs.
    """

    renderer_id: str = "backend-native-v0"

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": envelope.backend_kind,
            "state_id": envelope.state_id,
            "goals_pp": envelope.pp,
            "n_goals": envelope.n_goals,
            "pp_scope": envelope.pp_scope.to_dict(),
            "pp_sha256": envelope.pp_sha256,
        }


@dataclass(frozen=True, slots=True)
class GoalTextRenderer:
    """Minimal ``Ω_L``: the goal text alone, no metadata.  Useful as a contrast arm."""

    renderer_id: str = "goal-text-v0"

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"renderer_id": self.renderer_id, "goals_pp": envelope.pp}


# ---------------------------------------------------------------------------------------------
# Answer leakage
# ---------------------------------------------------------------------------------------------


class AnswerLeakageError(RuntimeError):
    """The observation contained something from the reference proof.  Loud, never silent."""


class LeakReason(StrEnum):
    #: The gold tactic text appears verbatim in the state it is supposed to be chosen from.
    #: Measured on the development split: 92 of 250,814 steps.
    TACTIC_IN_STATE_BEFORE = "TACTIC_IN_STATE_BEFORE"
    #: The theorem's own name appears in one of its states.  Measured: 2 of 59,557 proofs.
    FULL_NAME_IN_STATE = "FULL_NAME_IN_STATE"


@dataclass(slots=True)
class LeakageLedger:
    """Counts of what the leakage filter dropped, reported with every bank."""

    problems_scanned: int = 0
    steps_scanned: int = 0
    leaking_steps: int = 0
    problems_dropped: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def record(self, reason: LeakReason) -> None:
        self.reasons[reason.value] = self.reasons.get(reason.value, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "problems_scanned": self.problems_scanned,
            "steps_scanned": self.steps_scanned,
            "leaking_steps": self.leaking_steps,
            "problems_dropped": self.problems_dropped,
            "reasons": dict(sorted(self.reasons.items())),
        }


@dataclass(frozen=True, slots=True)
class LeakageFilter:
    """Drops problems whose recorded states contain their own answer.

    The criterion is the one that was measured, so the drop counts this produces are directly
    comparable to the audit's baseline: a step leaks when its gold ``tactic`` appears verbatim in
    its own ``state_before``; a problem leaks when its ``full_name`` appears in any
    ``state_before``.
    """

    #: Runtime tripwire only: shorter tactics ("rfl") appear inside goal text by coincidence.
    min_runtime_secret_len: int = 6

    def scan_record(self, record: Mapping[str, Any]) -> tuple[LeakReason, ...]:
        reasons: list[LeakReason] = []
        full_name = str(record.get("full_name", ""))
        for step in record.get("traced_tactics") or []:
            state_before = str(step.get("state_before", ""))
            tactic = str(step.get("tactic", ""))
            if tactic and tactic in state_before:
                reasons.append(LeakReason.TACTIC_IN_STATE_BEFORE)
            if full_name and full_name in state_before:
                reasons.append(LeakReason.FULL_NAME_IN_STATE)
        return tuple(reasons)

    def assert_observation_clean(
        self, rendered: Mapping[str, Any], remaining_reference: Sequence[str]
    ) -> None:
        """Raise if any not-yet-played reference tactic appears in what the Solver will see."""

        payload = json.dumps(rendered, ensure_ascii=False)
        for tactic in remaining_reference:
            candidate = tactic.strip()
            if len(candidate) >= self.min_runtime_secret_len and candidate in payload:
                raise AnswerLeakageError(
                    "observation contains a remaining reference tactic "
                    f"({candidate[:60]!r}); refusing to show it"
                )


# ---------------------------------------------------------------------------------------------
# Action space
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ActionSpaceSpec:
    """An honest description of ``A``.

    V0 does not enumerate actions and does not offer a K-way choice.  The Solver emits a tactic
    string; the backend accepts or rejects it.  Saying so plainly is the point: every other
    environment in this repository is a 2-to-8-way single-step choice, and pretending this one is
    comparable would misdescribe both.
    """

    kind: str = "FREE_FORM_TACTIC_STRING"
    enumerable: bool = False
    proposes_candidates: bool = False
    policy_name: str = "record_only"
    policy_id: str = ""
    denied_heads: tuple[str, ...] = ()
    allowed_heads: tuple[str, ...] | None = None
    always_refused: tuple[str, ...] = ()
    description: str = (
        "The Solver proposes one Lean 4 tactic string per step. The arena neither enumerates nor "
        "ranks candidates; legality is decided by the Lean elaborator at the current metavariable "
        "context, after the caller's tactic policy has been applied. `sorry` and `admit` are "
        "refused unconditionally."
    )

    @classmethod
    def from_policy(cls, policy: TacticPolicy) -> ActionSpaceSpec:
        from arena.trajectory.lean_backend import ALWAYS_REFUSED

        return cls(
            policy_name=policy.name,
            policy_id=policy.policy_id,
            denied_heads=tuple(sorted(policy.denied_heads)),
            allowed_heads=(
                None if policy.allowed_heads is None else tuple(sorted(policy.allowed_heads))
            ),
            always_refused=tuple(sorted(ALWAYS_REFUSED)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "enumerable": self.enumerable,
            "proposes_candidates": self.proposes_candidates,
            "policy_name": self.policy_name,
            "policy_id": self.policy_id,
            "denied_heads": list(self.denied_heads),
            "allowed_heads": None if self.allowed_heads is None else list(self.allowed_heads),
            "always_refused": list(self.always_refused),
            "description": self.description,
        }


# ---------------------------------------------------------------------------------------------
# The environment
# ---------------------------------------------------------------------------------------------


def derive_session_id(probe: LeanTheoremProbe, *, policy: TacticPolicy, seed: int) -> str:
    """The identity of what a backend session was opened on (RT-02).

    Lean's ``lean_dojo_repl`` hands out per-session small integers as state ids, so an id alone
    says nothing about which episode produced it: renumbering one theorem's states into another's
    chain is free, which is exactly how RT-02 spliced two mathlib theorems into one "ten-step
    trajectory".  Every envelope this arena emits therefore carries the session id below, and
    :meth:`VerifiedTrajectory.__post_init__` refuses a trajectory whose states disagree on it.

    It is a **function of the session's opening conditions** — the theorem, the exact probe file
    handed to Lean, the tactic policy and the seed — and not a random nonce, so a byte-identical
    re-run of an episode still produces a byte-identical record and the same ``trajectory_id``.
    The cost of that choice is stated rather than hidden: two *different* episodes of the same
    theorem under the same policy and seed share a session id, so splicing those two is caught by
    ``verify_bank(relive=True)`` and not at load time.
    """

    material = "\x00".join(
        (
            probe.problem_id,
            content_sha256(probe.repl_source()),
            f"{policy.name}:{policy.policy_id}",
            str(seed),
        )
    )
    return f"lean4-repl-{content_sha256(material)[:24]}"


@dataclass(frozen=True, slots=True)
class ArenaObservation:
    """What a Solver sees: the rendered state and the episode's bookkeeping, nothing else."""

    step_index: int
    state_id: str
    rendered: Mapping[str, Any]
    n_goals: int
    attempts_remaining: int
    terminal_status: TerminalStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "state_id": self.state_id,
            "rendered": dict(self.rendered),
            "n_goals": self.n_goals,
            "attempts_remaining": self.attempts_remaining,
            "terminal_status": self.terminal_status.value,
        }


@dataclass(frozen=True, slots=True)
class ArenaStep:
    """``(o_{t+1}, r_t, terminal_status, info)``."""

    observation: ArenaObservation
    reward: float
    terminal_status: TerminalStatus
    info: dict[str, Any]

    @property
    def done(self) -> bool:
        return self.terminal_status.is_terminal


class LeanTrajectoryArena:
    """One episode over one theorem, driven through one reused Lean session.

    Usage::

        arena = LeanTrajectoryArena(renderer=BackendNativeRenderer())
        obs = arena.reset(probe)
        while not done:
            result = arena.step(solver_tactic)
        trajectory = arena.build_trajectory(actor=Actor.SOLVER)

    A rejected tactic does **not** end the episode by default (the Solver may try another) and
    does **not** advance the state; it consumes one attempt and is recorded as evidence.  Set
    ``fail_fast=True`` for reference replay, where a rejection is a real failure.
    """

    def __init__(
        self,
        *,
        config: LeanToolchainConfig | None = None,
        policy: TacticPolicy | None = None,
        renderer: StateRenderer | None = None,
        leakage_filter: LeakageFilter | None = None,
        attempt_budget: int = 60,
        fail_fast: bool = False,
        toolchain_report: ToolchainReport | None = None,
        olean_count: int | None = None,
        seed: int = 0,
    ) -> None:
        self.config = config or LeanToolchainConfig.from_env()
        self.policy = policy or TacticPolicy.record_only()
        self.renderer: StateRenderer = renderer or BackendNativeRenderer()
        self.leakage_filter = leakage_filter or LeakageFilter()
        self.attempt_budget = attempt_budget
        self.fail_fast = fail_fast
        self.seed = seed
        self._toolchain_report = toolchain_report
        self._olean_count = olean_count
        self._probe: LeanTheoremProbe | None = None
        self._session: LeanReplSession | None = None
        self._session_id = ""
        self._states: list[BackendStateEnvelope] = []
        self._actions: list[TrajectoryAction] = []
        self._evidence: list[VerifierEvidence] = []
        self._terminal = TerminalStatus.OPEN
        self._attempts = 0
        self._kernel: KernelVerification | None = None
        self._accepted_tactics: list[str] = []
        self._reference_remaining: list[str] = []
        self._wall_s = 0.0

    # -- interface ---------------------------------------------------------------

    @property
    def legal_action_space(self) -> ActionSpaceSpec:
        return ActionSpaceSpec.from_policy(self.policy)

    @property
    def terminal_status(self) -> TerminalStatus:
        return self._terminal

    @property
    def states(self) -> tuple[BackendStateEnvelope, ...]:
        return tuple(self._states)

    def reset(
        self, probe: LeanTheoremProbe, *, hide_reference: Sequence[str] | None = None
    ) -> ArenaObservation:
        """Start a Lean session on ``probe`` and return the initial observation.

        ``hide_reference`` is the reference proof the observation must never reveal; the replay
        driver passes the remaining tactics so the tripwire has something to check.
        """

        self.close()
        started = time.monotonic()
        self._probe = probe
        self._session_id = derive_session_id(probe, policy=self.policy, seed=self.seed)
        self._states = []
        self._actions = []
        self._evidence = []
        self._accepted_tactics = []
        self._attempts = 0
        self._kernel = None
        self._terminal = TerminalStatus.OPEN
        self._reference_remaining = list(hide_reference or ())

        session = LeanReplSession(probe, config=self.config, policy=self.policy)
        start_result = session.start()
        self._session = session
        self._wall_s = time.monotonic() - started
        if not start_result.ok or start_result.to_state_id is None:
            self._set_terminal(TerminalStatus.ERROR_BACKEND)
            self._evidence.append(
                VerifierEvidence(
                    kind=EvidenceKind.STEP,
                    verifier="lean4-repl",
                    verdict=Verdict.REJECTED,
                    step=None,
                    backend_error=start_result.error,
                    rejected_reason="session failed to start",
                )
            )
            envelope = self._envelope(0, "<none>", "")
            self._states.append(envelope)
            return self._observe(envelope)

        envelope = self._envelope(0, start_result.to_state_id, start_result.tactic_state or "")
        self._states.append(envelope)
        return self._observe(envelope)

    def step(self, tactic: str) -> ArenaStep:
        """Apply one action.  Returns the next observation, reward, status and info."""

        if self._terminal.is_terminal:
            return ArenaStep(
                observation=self._observe(self._states[-1]),
                reward=0.0,
                terminal_status=self._terminal,
                info={"refused": "episode already terminal"},
            )
        session = self._session
        probe = self._probe
        if session is None or probe is None:
            raise RuntimeError("reset() must be called before step()")

        self._attempts += 1
        current = self._states[-1]
        result = session.step(current.state_id, tactic)
        self._evidence.append(_step_evidence(len(self._actions), result))

        if not result.ok:
            return self._handle_rejection(result)

        assert result.to_state_id is not None
        envelope = self._envelope(len(self._states), result.to_state_id, result.tactic_state or "")
        action = TrajectoryAction(
            index=len(self._actions),
            from_state_id=current.state_id,
            to_state_id=envelope.state_id,
            actor=Actor.SOLVER,
            tactic=tactic,
            wall_ms=result.wall_ms,
        )
        self._states.append(envelope)
        self._actions.append(action)
        self._accepted_tactics.append(tactic)
        if self._reference_remaining and self._reference_remaining[0] == tactic:
            self._reference_remaining.pop(0)

        info: dict[str, Any] = {
            "outcome": result.outcome.value,
            "wall_ms": result.wall_ms,
            "tactic_head": action.tactic_head,
            # ADVISORY diagnostic, never a verdict: identical rendered text after a step is a
            # sign the move did nothing.  It is reported, and it gates nothing (audit §7.4).
            "no_op_suspected": envelope.pp_sha256 == current.pp_sha256,
            "n_goals": envelope.n_goals,
        }

        if result.closed:
            self._close_with_kernel(probe, info)
        elif self._attempts >= self.attempt_budget:
            self._set_terminal(TerminalStatus.BUDGET_EXHAUSTED)

        reward = 1.0 if self._terminal is TerminalStatus.CLOSED_VERIFIED else 0.0
        return ArenaStep(self._observe(envelope), reward, self._terminal, info)

    def branch(self, state_id: str) -> ArenaObservation:
        """Re-enter an earlier backend state.

        Legitimate search.  It is logged in the session's ``branch_log`` and does not erase any
        rejected attempt already in ``verifier_evidence``, so it cannot be used to launder a
        failed episode into a successful one.
        """

        session = self._session
        if session is None:
            raise RuntimeError("reset() must be called before branch()")
        result = session.branch(state_id)
        if not result.ok:
            raise ValueError(result.error or f"cannot branch to {state_id!r}")
        for envelope in self._states:
            if envelope.state_id == state_id:
                return self._observe(envelope)
        raise ValueError(f"state {state_id!r} is not on this trajectory")

    def abandon(self, reason: str) -> TerminalStatus:
        """End an ``OPEN`` episode deliberately, recording why.

        Used when the driver runs out of actions to play rather than when Lean rejects one: an
        episode that simply stopped is not a failure and must not be filed as one.  Refuses to
        overwrite an already-terminal status.
        """

        if self._terminal.is_terminal:
            return self._terminal
        self._set_terminal(TerminalStatus.ABANDONED)
        self._evidence.append(
            VerifierEvidence(
                kind=EvidenceKind.STEP,
                verifier="arena-v0",
                verdict=Verdict.REFUSED,
                step=len(self._actions),
                from_state_id=self._states[-1].state_id if self._states else None,
                rejected_reason=reason,
            )
        )
        return self._terminal

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    # -- trajectory emission ------------------------------------------------------

    def build_trajectory(
        self,
        *,
        actor: Actor,
        source_version: SourceVersion,
        reference_horizon: int,
        provenance_notes: Sequence[str] = (),
    ) -> VerifiedTrajectory:
        probe = self._probe
        if probe is None:
            raise RuntimeError("no episode to emit")
        actions = tuple(replace(action, actor=actor) for action in self._actions)
        report = self._toolchain_report or check_toolchain(self.config)
        backend = FormalBackend(
            system="lean4",
            toolchain=report.toolchain,
            lean_version_string=report.lean_version_string,
            mathlib_commit=source_version.commit,
            mathlib_build_root=str(self.config.mathlib_root),
            olean_count=self._olean_count,
        )
        provenance = TrajectoryProvenance(
            trust_tier="A_NATIVE_VERIFIED",
            generator=GENERATOR_ID,
            generated_utc=datetime.now(UTC).isoformat(timespec="seconds"),
            seed=self.seed,
            sealed_splits_not_read=SEALED_SPLIT_PATHS,
            contamination=CONTAMINATION_NOTE,
            tactic_policy_id=f"{self.policy.name}:{self.policy.policy_id}",
            tactic_budget=self.attempt_budget,
            max_heartbeats=self.config.max_heartbeats,
            leakage_filters=(
                LeakReason.TACTIC_IN_STATE_BEFORE.value,
                LeakReason.FULL_NAME_IN_STATE.value,
            ),
            notes=tuple(provenance_notes) + (f"renderer={self.renderer.renderer_id}",),
        )
        draft = VerifiedTrajectory(
            trajectory_id="pending",
            problem_id=probe.problem_id,
            formal_backend=backend,
            source_version=source_version,
            states=tuple(self._states),
            actions=actions,
            verifier_evidence=tuple(self._evidence),
            terminal_status=self._terminal,
            provenance=provenance,
            reference_horizon=reference_horizon,
        )
        return replace(
            draft, trajectory_id=derive_trajectory_id(probe.problem_id, draft.content_hash)
        )

    # -- internals ---------------------------------------------------------------

    def _set_terminal(self, status: TerminalStatus) -> None:
        """Terminal statuses are absorbing; this is where that is enforced."""

        if not self._terminal.can_transition_to(status):
            raise RuntimeError(
                f"refusing to change a terminal episode from {self._terminal.value} to "
                f"{status.value}: a finished episode cannot be relabelled"
            )
        self._terminal = status

    def _envelope(self, index: int, state_id: str, pp: str) -> BackendStateEnvelope:
        probe = self._probe
        assert probe is not None
        return BackendStateEnvelope(
            index=index,
            state_id=state_id,
            pp=pp,
            pp_scope=probe.pp_scope,
            n_goals=_count_goals(pp),
            session_id=self._session_id,
            problem_id=probe.problem_id,
        )

    def _observe(self, envelope: BackendStateEnvelope) -> ArenaObservation:
        rendered = self.renderer.render(envelope)
        self.leakage_filter.assert_observation_clean(rendered, self._reference_remaining)
        return ArenaObservation(
            step_index=len(self._actions),
            state_id=envelope.state_id,
            rendered=rendered,
            n_goals=envelope.n_goals,
            attempts_remaining=max(0, self.attempt_budget - self._attempts),
            terminal_status=self._terminal,
        )

    def _handle_rejection(self, result: StepResult) -> ArenaStep:
        info = {
            "outcome": result.outcome.value,
            "error": result.error,
            "wall_ms": result.wall_ms,
        }
        if result.outcome in {StepOutcome.BACKEND_DEAD, StepOutcome.TIMEOUT}:
            self._set_terminal(TerminalStatus.ERROR_BACKEND)
        elif result.outcome is StepOutcome.SESSION_EXPIRED:
            self._set_terminal(TerminalStatus.ABANDONED)
        elif result.outcome in {StepOutcome.SORRY_REFUSED, StepOutcome.POLICY_REJECTED}:
            if self.fail_fast:
                self._set_terminal(TerminalStatus.ABANDONED)
        elif self.fail_fast:
            self._set_terminal(TerminalStatus.FAILED)
        elif self._attempts >= self.attempt_budget:
            self._set_terminal(TerminalStatus.BUDGET_EXHAUSTED)
        return ArenaStep(self._observe(self._states[-1]), 0.0, self._terminal, info)

    def _close_with_kernel(self, probe: LeanTheoremProbe, info: dict[str, Any]) -> None:
        """``no goals`` is necessary; the kernel decides."""

        kernel = verify_closed_script(probe, self._accepted_tactics, config=self.config)
        self._kernel = kernel
        self._evidence.append(
            VerifierEvidence(
                kind=EvidenceKind.TERMINAL_KERNEL,
                verifier="lean4-kernel",
                verdict=Verdict.KERNEL_VERIFIED if kernel.verified else Verdict.KERNEL_REJECTED,
                step=len(self._actions),
                print_axioms=kernel.print_axioms,
                contains_sorry_ax=kernel.contains_sorry_ax,
                contains_of_reduce_bool=kernel.contains_of_reduce_bool,
                rejected_reason=None if kernel.verified else (kernel.errors or "kernel rejected"),
            )
        )
        self._set_terminal(
            TerminalStatus.CLOSED_VERIFIED if kernel.verified else TerminalStatus.FAILED
        )
        info["kernel"] = kernel.to_dict()


def _count_goals(pp: str) -> int:
    """Count ``⊢`` markers.  Display metadata only; nothing is verified against it."""

    if not pp.strip():
        return 0
    from arena.trajectory.lean_backend import is_no_goals

    if is_no_goals(pp):
        return 0
    return max(pp.count("⊢"), 1)


def _step_evidence(step_index: int, result: StepResult) -> VerifierEvidence:
    if result.ok:
        verdict = Verdict.ACCEPTED
    elif result.outcome in {StepOutcome.SORRY_REFUSED, StepOutcome.POLICY_REJECTED}:
        verdict = Verdict.REFUSED
    else:
        verdict = Verdict.REJECTED
    return VerifierEvidence(
        kind=EvidenceKind.STEP,
        verifier="lean4-repl",
        verdict=verdict,
        step=step_index,
        from_state_id=result.from_state_id,
        to_state_id=result.to_state_id,
        tactic=result.tactic,
        backend_error=result.error if verdict is Verdict.REJECTED else None,
        rejected_reason=result.error if verdict is Verdict.REFUSED else None,
    )


# ---------------------------------------------------------------------------------------------
# Replay driver: the ground-truth generator
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    problem_id: str
    trajectory: VerifiedTrajectory | None
    terminal_status: TerminalStatus
    achieved_horizon: int
    reference_horizon: int
    wall_s: float
    startup_s: float
    error: str = ""


class ReplayDriver:
    """Execute a recorded reference proof live, as a **flat** tactic script.

    Recorded LeanDojo proofs are traversals of proof *trees*: only 67.3% of adjacent pairs chain,
    so a recorded-chain arena collapses past 10 steps (6 theorems at ≥20).  Replaying the flat
    list through the live REPL sidesteps that — Lean's goal stack absorbs the structuring — and
    the audit measured 5 of 6 tree-shaped proofs closing this way.  Every action produced here is
    ``actor=REFERENCE``: it is ground truth for building a bank, never a solver result.
    """

    def __init__(
        self,
        *,
        config: LeanToolchainConfig | None = None,
        policy: TacticPolicy | None = None,
        renderer: StateRenderer | None = None,
        leakage_filter: LeakageFilter | None = None,
        toolchain_report: ToolchainReport | None = None,
        olean_count: int | None = None,
        seed: int = 0,
    ) -> None:
        self.config = config or LeanToolchainConfig.from_env()
        self.policy = policy or TacticPolicy.record_only()
        self.renderer = renderer or BackendNativeRenderer()
        self.leakage_filter = leakage_filter or LeakageFilter()
        self.toolchain_report = toolchain_report
        self.olean_count = olean_count
        self.seed = seed

    def run(self, record: Mapping[str, Any], probe: LeanTheoremProbe) -> ReplayOutcome:
        started = time.monotonic()
        arena = LeanTrajectoryArena(
            config=self.config,
            policy=self.policy,
            renderer=self.renderer,
            leakage_filter=self.leakage_filter,
            attempt_budget=max(4 * len(probe.reference_tactics), 8),
            fail_fast=True,
            toolchain_report=self.toolchain_report,
            olean_count=self.olean_count,
            seed=self.seed,
        )
        error = ""
        try:
            arena.reset(probe, hide_reference=probe.reference_tactics)
            for tactic in probe.reference_tactics:
                outcome = arena.step(tactic)
                if outcome.done:
                    break
            arena.abandon(
                "the recorded reference script was exhausted without closing the goals; the "
                "recorded tactic list is a traversal of a proof TREE, and a flat replay of it "
                "does not always close"
            )
            source_version = source_version_from_record(record)
            trajectory = arena.build_trajectory(
                actor=Actor.REFERENCE,
                source_version=source_version,
                reference_horizon=len(probe.reference_tactics),
                provenance_notes=("replay of the recorded reference proof as a flat script",),
            )
        except AnswerLeakageError as exc:
            arena.close()
            return ReplayOutcome(
                problem_id=probe.problem_id,
                trajectory=None,
                terminal_status=TerminalStatus.ABANDONED,
                achieved_horizon=0,
                reference_horizon=len(probe.reference_tactics),
                wall_s=time.monotonic() - started,
                startup_s=0.0,
                error=f"ANSWER_LEAKAGE: {exc}",
            )
        finally:
            startup = arena._session.startup_wall_s if arena._session is not None else 0.0
            arena.close()
        return ReplayOutcome(
            problem_id=probe.problem_id,
            trajectory=trajectory,
            terminal_status=trajectory.terminal_status,
            achieved_horizon=trajectory.horizon.achieved,
            reference_horizon=len(probe.reference_tactics),
            wall_s=time.monotonic() - started,
            startup_s=startup,
            error=error,
        )


def source_version_from_record(record: Mapping[str, Any]) -> SourceVersion:
    """Build the provenance block from the source's own keys, inventing nothing."""

    start = record.get("start")
    end = record.get("end")
    return SourceVersion(
        dataset="LeanDojo Benchmark 4",
        license="CC BY 2.0",
        split="train",
        file_path=str(record.get("file_path", "")),
        full_name=str(record.get("full_name", "")),
        url=str(record.get("url", "")),
        commit=str(record.get("commit", "")),
        leandojo_version="2.0.0",
        creation_time="2024-07-02 13:14:48.804567",
        start=(int(start[0]), int(start[1])) if start else None,
        end=(int(end[0]), int(end[1])) if end else None,
    )


# ---------------------------------------------------------------------------------------------
# Bank construction
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BankSelection:
    """Which problems a seed picked, and everything that was thrown away on the way."""

    records: tuple[dict[str, Any], ...]
    probes: tuple[LeanTheoremProbe, ...]
    discards: DiscardLedger
    leakage: LeakageLedger
    scanned: int


def select_candidates(
    *,
    train_json: Path,
    min_horizon: int,
    limit: int,
    seed: int,
    scan_limit: int,
    policy: TacticPolicy | None = None,
    mathlib_root: Path = DEFAULT_MATHLIB_ROOT,
    max_horizon: int | None = None,
    leakage_filter: LeakageFilter | None = None,
    allow_multiline_tactics: bool = False,
) -> BankSelection:
    """Deterministic, seeded sampling.

    Determinism is a pure function of ``(train_json, scan_limit, min_horizon, max_horizon, policy,
    seed)``: the first ``scan_limit`` records are read in file order, filtered, and then permuted
    by ``random.Random(seed)``.  ``scan_limit`` is part of the identity and is written into the
    manifest — without it "seeded" would be meaningless.
    """

    policy = policy or TacticPolicy.record_only()
    leakage_filter = leakage_filter or LeakageFilter()
    discards = DiscardLedger()
    leakage = LeakageLedger()
    candidates: list[tuple[dict[str, Any], LeanTheoremProbe]] = []
    scanned = 0

    for record in iter_leandojo_records(train_json, limit=scan_limit):
        scanned += 1
        tactics = record.get("traced_tactics") or []
        if len(tactics) < min_horizon:
            discards.record(ProbeDiscardReason.BELOW_MIN_HORIZON)
            continue
        leakage.problems_scanned += 1
        leakage.steps_scanned += len(tactics)
        reasons = leakage_filter.scan_record(record)
        if reasons:
            leakage.leaking_steps += len(reasons)
            leakage.problems_dropped += 1
            for reason in reasons:
                leakage.record(reason)
            discards.record("LEAKAGE_FILTER")
            continue
        built = build_probe(
            record,
            mathlib_root=mathlib_root,
            policy=policy,
            min_reference_horizon=min_horizon,
            max_reference_horizon=max_horizon,
            allow_multiline_tactics=allow_multiline_tactics,
        )
        if not built.ok:
            discards.record(built.discard_reason or ProbeDiscardReason.NO_TACTICS)
            continue
        assert built.probe is not None
        candidates.append((record, built.probe))

    rng = random.Random(seed)
    order = list(range(len(candidates)))
    rng.shuffle(order)
    chosen = [candidates[index] for index in order[:limit]]
    return BankSelection(
        records=tuple(item[0] for item in chosen),
        probes=tuple(item[1] for item in chosen),
        discards=discards,
        leakage=leakage,
        scanned=scanned,
    )


def horizon_histogram(trajectories: Iterable[VerifiedTrajectory]) -> dict[str, int]:
    counts: dict[int, int] = {}
    for trajectory in trajectories:
        value = trajectory.horizon.verified
        counts[value] = counts.get(value, 0) + 1
    return {str(key): counts[key] for key in sorted(counts)}


def build_bank(
    *,
    out_dir: Path,
    train_json: Path = DEFAULT_TRAIN_JSON,
    min_horizon: int = 5,
    limit: int = 8,
    seed: int = 0,
    scan_limit: int = 20_000,
    max_horizon: int | None = None,
    policy: TacticPolicy | None = None,
    config: LeanToolchainConfig | None = None,
    allow_multiline_tactics: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    """Build a bank of verified trajectories and its manifest.  Requires a live Lean."""

    config = config or LeanToolchainConfig.from_env()
    policy = policy or TacticPolicy.record_only()
    report = check_toolchain(config)
    if not report.available:
        raise RuntimeError(report.describe())
    oleans = count_oleans(config)

    started = time.monotonic()
    selection = select_candidates(
        train_json=train_json,
        min_horizon=min_horizon,
        limit=limit,
        seed=seed,
        scan_limit=scan_limit,
        policy=policy,
        mathlib_root=config.mathlib_root,
        max_horizon=max_horizon,
        allow_multiline_tactics=allow_multiline_tactics,
    )
    selection_s = time.monotonic() - started
    if verbose:
        print(
            f"selected {len(selection.probes)} candidates from {selection.scanned} records "
            f"in {selection_s:.1f}s; discards={selection.discards.to_dict()}"
        )

    driver = ReplayDriver(
        config=config, policy=policy, toolchain_report=report, olean_count=oleans, seed=seed
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    bank_path = out_dir / "bank.jsonl"
    trajectories: list[VerifiedTrajectory] = []
    outcomes: list[dict[str, Any]] = []
    replay_started = time.monotonic()
    with bank_path.open("w", encoding="utf-8") as handle:
        for record, probe in zip(selection.records, selection.probes, strict=True):
            outcome = driver.run(record, probe)
            outcomes.append(
                {
                    "problem_id": outcome.problem_id,
                    "terminal_status": outcome.terminal_status.value,
                    "achieved_horizon": outcome.achieved_horizon,
                    "reference_horizon": outcome.reference_horizon,
                    "wall_s": round(outcome.wall_s, 2),
                    "startup_s": round(outcome.startup_s, 2),
                    "error": outcome.error[:400],
                }
            )
            if verbose:
                print(
                    f"  {outcome.terminal_status.value:<18} h={outcome.achieved_horizon:>2}/"
                    f"{outcome.reference_horizon:<3} {outcome.wall_s:5.1f}s  "
                    f"{outcome.problem_id[:80]}"
                )
            if outcome.trajectory is None:
                continue
            trajectories.append(outcome.trajectory)
            handle.write(outcome.trajectory.to_json() + "\n")
    replay_s = time.monotonic() - replay_started

    verified = [t for t in trajectories if t.terminal_status is TerminalStatus.CLOSED_VERIFIED]
    manifest = {
        "schema": BANK_SCHEMA,
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "generator": GENERATOR_ID,
        "bank_file": bank_path.name,
        "selection": {
            "train_json": str(train_json),
            "seed": seed,
            "scan_limit": scan_limit,
            "min_horizon": min_horizon,
            "max_horizon": max_horizon,
            "limit": limit,
            "allow_multiline_tactics": allow_multiline_tactics,
            "records_scanned": selection.scanned,
            "candidates_selected": len(selection.probes),
        },
        "toolchain": {
            "lean_version_string": report.lean_version_string,
            "toolchain": report.toolchain,
            "mathlib_root": str(config.mathlib_root),
            "olean_count": oleans,
            "max_heartbeats": config.max_heartbeats,
        },
        "action_space": ActionSpaceSpec.from_policy(policy).to_dict(),
        "results": {
            "trajectories_written": len(trajectories),
            "closed_verified": len(verified),
            "horizon_histogram_verified": horizon_histogram(verified),
            "max_verified_horizon": max((t.horizon.verified for t in verified), default=0),
            "terminal_status_counts": _status_counts(trajectories),
            "tactic_head_counts": _tactic_head_counts(verified),
        },
        "discards": selection.discards.to_dict(),
        "leakage": selection.leakage.to_dict(),
        "timings_s": {
            "selection": round(selection_s, 2),
            "replay": round(replay_s, 2),
            "total": round(time.monotonic() - started, 2),
            "mean_per_episode": round(replay_s / max(1, len(outcomes)), 2),
        },
        "episodes": outcomes,
        "sealed_splits_not_read": list(SEALED_SPLIT_PATHS),
        "contamination": CONTAMINATION_NOTE,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _status_counts(trajectories: Sequence[VerifiedTrajectory]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trajectory in trajectories:
        key = trajectory.terminal_status.value
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _tactic_head_counts(trajectories: Sequence[VerifiedTrajectory]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trajectory in trajectories:
        for head, times in trajectory.tactic_head_counts().items():
            counts[head] = counts.get(head, 0) + times
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


# ---------------------------------------------------------------------------------------------
# Bank verification
# ---------------------------------------------------------------------------------------------


@dataclass(slots=True)
class BankVerification:
    checked: int = 0
    ok: int = 0
    failures: list[str] = field(default_factory=list)
    horizon_histogram: dict[str, int] = field(default_factory=dict)
    relived: int = 0
    relive_matches: int = 0

    @property
    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked": self.checked,
            "ok": self.ok,
            "passed": self.passed,
            "failures": self.failures,
            "horizon_histogram_verified": self.horizon_histogram,
            "relived": self.relived,
            "relive_matches": self.relive_matches,
        }


def load_bank(path: Path) -> list[VerifiedTrajectory]:
    """Read a bank, re-checking every content hash on the way in."""

    trajectories: list[VerifiedTrajectory] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                trajectories.append(VerifiedTrajectory.from_dict(json.loads(line)))
    return trajectories


def verify_bank(
    path: Path,
    *,
    relive: bool = False,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
    train_json: Path = DEFAULT_TRAIN_JSON,
) -> BankVerification:
    """Re-check a bank: hashes, chain integrity, kernel evidence, actor purity.

    Structural by default.  ``relive=True`` additionally re-executes **the actions stored in each
    trajectory** — ``trajectory.actions``, not the source proof — against a fresh Lean session and
    requires them to reproduce the record's own terminal status, horizon and states.  See
    :func:`relive_trajectory`; RT-03 is why that sentence now says which tactics get run.
    """

    result = BankVerification()
    bank_file = path / "bank.jsonl" if path.is_dir() else path
    trajectories: list[VerifiedTrajectory] = []
    with bank_file.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            result.checked += 1
            try:
                trajectory = VerifiedTrajectory.from_dict(json.loads(line))
            except Exception as exc:  # noqa: BLE001 - the reason is the report
                result.failures.append(f"line {number}: {exc}")
                continue
            problems = _structural_problems(trajectory)
            if problems:
                result.failures.extend(f"line {number}: {item}" for item in problems)
                continue
            trajectories.append(trajectory)
            result.ok += 1
    result.horizon_histogram = horizon_histogram(
        t for t in trajectories if t.terminal_status is TerminalStatus.CLOSED_VERIFIED
    )

    if relive:
        config = config or LeanToolchainConfig.from_env()
        report = check_toolchain(config)
        if not report.available:
            result.failures.append(f"--relive requested but {report.describe()}")
            return result
        wanted = {t.problem_id for t in trajectories}
        records = _collect_source_records(wanted, train_json)
        for trajectory in trajectories:
            match, detail = _relive(
                trajectory, records.get(trajectory.problem_id), config=config, policy=policy
            )
            result.relived += 1
            if match:
                result.relive_matches += 1
            else:
                result.failures.append(f"{trajectory.trajectory_id}: relive mismatch: {detail}")
    return result


def _collect_source_records(problem_ids: set[str], train_json: Path) -> dict[str, dict[str, Any]]:
    """One streaming pass over the 373 MB split, not one pass per trajectory."""

    found: dict[str, dict[str, Any]] = {}
    for record in iter_leandojo_records(train_json):
        key = f"{record.get('file_path')}::{record.get('full_name')}"
        if key in problem_ids:
            found[key] = record
            if len(found) == len(problem_ids):
                break
    return found


def _structural_problems(trajectory: VerifiedTrajectory) -> list[str]:
    problems: list[str] = []
    if not trajectory.is_single_actor:
        problems.append("mixes SOLVER and REFERENCE actions")
    if trajectory.terminal_status is TerminalStatus.OPEN:
        problems.append("OPEN trajectory in a bank: the episode never terminated")
    if trajectory.terminal_status is TerminalStatus.CLOSED_VERIFIED:
        if not trajectory.kernel_verified:
            problems.append("CLOSED_VERIFIED without kernel evidence")
        if trajectory.horizon.verified != trajectory.horizon.achieved:
            problems.append("verified horizon disagrees with achieved horizon")
    else:
        if trajectory.horizon.verified != 0:
            problems.append("non-closed trajectory reports a verified horizon")
    for evidence in trajectory.verifier_evidence:
        if evidence.contains_sorry_ax and (
            trajectory.terminal_status is TerminalStatus.CLOSED_VERIFIED
        ):
            problems.append("CLOSED_VERIFIED while evidence reports sorryAx")
    accepted = [
        evidence
        for evidence in trajectory.verifier_evidence
        if evidence.kind is EvidenceKind.STEP and evidence.verdict is Verdict.ACCEPTED
    ]
    if len(accepted) != len(trajectory.actions):
        problems.append(
            f"{len(accepted)} ACCEPTED step evidence records for {len(trajectory.actions)} actions"
        )
        return problems
    # RT-02/RT-03 hardening: the verifier's own utterances must describe the actions the record
    # claims.  A spliced or rewritten action list leaves the evidence naming the endpoints and the
    # tactic that were really accepted, so this catches both forgeries with no Lean at all.
    for evidence, action in zip(accepted, trajectory.actions, strict=True):
        if (
            evidence.step != action.index
            or evidence.from_state_id != action.from_state_id
            or evidence.to_state_id != action.to_state_id
            or evidence.tactic != action.tactic
        ):
            problems.append(
                f"action {action.index} ({action.from_state_id}->{action.to_state_id} "
                f"{action.tactic!r}) is not the action the verifier recorded accepting "
                f"(evidence: step={evidence.step} {evidence.from_state_id}->"
                f"{evidence.to_state_id} {evidence.tactic!r})"
            )
            break
    return problems


@dataclass(frozen=True, slots=True)
class ReliveOutcome:
    """The result of re-executing one stored trajectory's own actions."""

    problem_id: str
    trajectory_id: str
    matched: bool
    detail: str
    terminal_status: TerminalStatus
    #: Stored actions that the backend accepted on the re-run, in order.
    actions_executed: int
    actions_stored: int
    wall_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "trajectory_id": self.trajectory_id,
            "matched": self.matched,
            "detail": self.detail,
            "terminal_status": self.terminal_status.value,
            "actions_executed": self.actions_executed,
            "actions_stored": self.actions_stored,
            "wall_s": round(self.wall_s, 2),
        }


def _state_hashes_agree(replayed: BackendStateEnvelope, stored: BackendStateEnvelope) -> bool:
    """Did the re-run land on the state the artefact records?

    **Tamper detection, never a mathematical verdict.**  Same category as the ``pp_sha256`` check
    in ``schema.from_dict``: it decides whether the stored record faithfully describes the run it
    claims to describe, and it is never consulted to decide whether a step was mathematically
    correct — the Lean elaborator decides that, by accepting or rejecting the tactic, before this
    function is reached.  Two states that print differently may be the same mathematics (measured
    40.6% vs 98.1%), which is exactly why this is not allowed to be a verifier.
    """

    return replayed.pp_sha256 == stored.pp_sha256


def relive_trajectory(
    trajectory: VerifiedTrajectory,
    probe: LeanTheoremProbe,
    *,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
) -> ReliveOutcome:
    """Re-execute **this artefact's own stored actions** against a fresh backend session.

    RT-03: the previous implementation called ``ReplayDriver.run(record, probe)``, and that driver
    plays ``probe.reference_tactics`` — the tactics of the *LeanDojo source record*.
    ``trajectory.actions`` was never read, so a bank whose every stored tactic had been replaced
    with ``aesop`` relived clean.  The check re-verified the source, not the artefact.

    What runs here is ``tuple(action.tactic for action in trajectory.actions)``, in order, on a
    session opened on ``probe`` — which supplies the *problem* (the theorem statement), never the
    answer.  The re-run must:

    1. have every stored action accepted by the backend, in order — the first one that is not is
       named, with its index and its text;
    2. land on the state the artefact records after each action (``pp_sha256``, see
       :func:`_state_hashes_agree`);
    3. reproduce the stored horizon; and
    4. reproduce closure: a record claiming ``CLOSED_VERIFIED`` must close under the kernel again,
       and a record claiming anything else must **not** close, or it is misreporting its own
       episode.

    An episode that ended for a reason no action records — a rejected tactic, an exhausted
    reference script — cannot have that reason reproduced from ``actions`` alone, because a
    rejected attempt is evidence, not an action.  For those records this establishes exactly
    the claim they make: these actions, in this order, were accepted and produced these states,
    and they did not close the goal.
    """

    started = time.monotonic()
    config = config or LeanToolchainConfig.from_env()
    stored_actions = trajectory.actions

    def outcome(matched: bool, detail: str, status: TerminalStatus, executed: int) -> ReliveOutcome:
        return ReliveOutcome(
            problem_id=trajectory.problem_id,
            trajectory_id=trajectory.trajectory_id,
            matched=matched,
            detail=detail,
            terminal_status=status,
            actions_executed=executed,
            actions_stored=len(stored_actions),
            wall_s=time.monotonic() - started,
        )

    arena = LeanTrajectoryArena(
        config=config,
        policy=policy,
        attempt_budget=len(stored_actions) + 8,
        fail_fast=False,
    )
    try:
        arena.reset(probe)
        if arena.terminal_status is TerminalStatus.ERROR_BACKEND:
            # A record may claim exactly this: an episode that never started, with no actions and
            # no horizon (the committed h12 bank holds one).  Reproducing it is a match — there is
            # nothing there to over-claim.  Any *other* record that cannot even open its session
            # has not been reproduced.
            reproduced = (
                trajectory.terminal_status is TerminalStatus.ERROR_BACKEND and not stored_actions
            )
            return outcome(
                reproduced,
                ""
                if reproduced
                else (
                    "the backend session would not start, but the record claims "
                    f"{trajectory.terminal_status.value} over {len(stored_actions)} actions"
                ),
                arena.terminal_status,
                0,
            )
        if not _state_hashes_agree(arena.states[0], trajectory.states[0]):
            return outcome(
                False,
                "the session's initial goal is not the state this record calls state 0: the "
                f"re-run opened on backend state {arena.states[0].state_id!r} of "
                f"{probe.problem_id}",
                arena.terminal_status,
                0,
            )
        for index, action in enumerate(stored_actions):
            before = len(arena.states)
            step = arena.step(action.tactic)
            if len(arena.states) == before:
                reason = step.info.get("error") or step.info.get("refused") or step.info
                return outcome(
                    False,
                    f"stored action {index} ({action.tactic!r}) was not accepted on the re-run: "
                    f"{str(reason)[:200]}",
                    arena.terminal_status,
                    index,
                )
            if not _state_hashes_agree(arena.states[-1], trajectory.states[index + 1]):
                return outcome(
                    False,
                    f"stored action {index} ({action.tactic!r}) produced a state the artefact "
                    f"does not record: re-run reached backend state "
                    f"{arena.states[-1].state_id!r}, the record claims state {index + 1}",
                    arena.terminal_status,
                    index + 1,
                )
        executed = len(arena.states) - 1
        stored_status = trajectory.terminal_status
        if executed != trajectory.horizon.achieved:
            return outcome(
                False,
                f"horizon {executed} != stored {trajectory.horizon.achieved}",
                arena.terminal_status,
                executed,
            )
        closed = arena.terminal_status is TerminalStatus.CLOSED_VERIFIED
        if stored_status is TerminalStatus.CLOSED_VERIFIED and not closed:
            return outcome(
                False,
                f"the stored actions did not close the goal under the kernel: re-run terminal "
                f"{arena.terminal_status.value} != stored CLOSED_VERIFIED",
                arena.terminal_status,
                executed,
            )
        if stored_status is not TerminalStatus.CLOSED_VERIFIED and closed:
            return outcome(
                False,
                f"the stored actions DID close the goal under the kernel, but the record claims "
                f"{stored_status.value}",
                arena.terminal_status,
                executed,
            )
        return outcome(True, "", arena.terminal_status, executed)
    finally:
        arena.close()


def _relive(
    trajectory: VerifiedTrajectory,
    record: dict[str, Any] | None,
    *,
    config: LeanToolchainConfig,
    policy: TacticPolicy | None,
) -> tuple[bool, str]:
    """Rebuild the theorem's probe from the source record, then relive the stored actions.

    The source record supplies the *problem* — the declaration, its file prefix and its scope —
    and nothing else.  Its ``traced_tactics`` are not read here, which is the whole of RT-03.
    """

    if record is None:
        return False, f"source record for {trajectory.problem_id} not found"
    built = build_probe(record, mathlib_root=config.mathlib_root, policy=policy)
    if not built.ok or built.probe is None:
        return False, f"probe could not be rebuilt: {built.discard_reason}"
    outcome = relive_trajectory(trajectory, built.probe, config=config, policy=policy)
    return outcome.matched, outcome.detail


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------

POLICIES = {
    "record_only": TacticPolicy.record_only,
    "no_heavy_automation": TacticPolicy.no_heavy_automation,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arena.trajectory.arena_v0",
        description="Build and re-verify a bank of kernel-verified Lean trajectories.",
    )
    parser.add_argument("--build-bank", action="store_true", help="build a bank of trajectories")
    parser.add_argument("--verify", type=Path, help="re-check an existing bank (dir or jsonl)")
    parser.add_argument("--relive", action="store_true", help="with --verify: re-run every episode")
    parser.add_argument("--toolchain-check", action="store_true", help="report toolchain status")
    parser.add_argument("--out", type=Path, help="output directory for --build-bank")
    parser.add_argument("--min-horizon", type=int, default=5)
    parser.add_argument("--max-horizon", type=int, default=None)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=20_000,
        help="records read from the head of train.json; part of the sample identity",
    )
    parser.add_argument("--train-json", type=Path, default=DEFAULT_TRAIN_JSON)
    parser.add_argument("--mathlib-root", type=Path, default=None)
    parser.add_argument("--policy", choices=sorted(POLICIES), default="record_only")
    parser.add_argument("--allow-multiline-tactics", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides: dict[str, Any] = {}
    if args.mathlib_root is not None:
        overrides["mathlib_root"] = args.mathlib_root
    config = LeanToolchainConfig.from_env(**overrides)
    policy = POLICIES[args.policy]()

    if args.toolchain_check:
        report = check_toolchain(config)
        print(report.describe())
        return 0 if report.available else 1

    if args.verify is not None:
        result = verify_bank(
            args.verify,
            relive=args.relive,
            config=config,
            policy=policy,
            train_json=args.train_json,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.passed else 1

    if args.build_bank:
        if args.out is None:
            print("--build-bank requires --out", file=sys.stderr)
            return 2
        manifest = build_bank(
            out_dir=args.out,
            train_json=args.train_json,
            min_horizon=args.min_horizon,
            max_horizon=args.max_horizon,
            limit=args.limit,
            seed=args.seed,
            scan_limit=args.scan_limit,
            policy=policy,
            config=config,
            allow_multiline_tactics=args.allow_multiline_tactics,
            verbose=not args.quiet,
        )
        print(json.dumps(manifest["results"], ensure_ascii=False, indent=2))
        print(json.dumps(manifest["timings_s"], ensure_ascii=False, indent=2))
        return 0

    build_parser().print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
