"""``VerifiedTask`` — the **interactive** environment of manual §6.25 / §17.1.

The difference this module exists to make real (manual §14.6):

``TRAJECTORY_REPLAY``
    The Solver consumes transitions from a recorded trajectory.  Everything in
    ``arena/trajectory/arena_v0.py``'s ``ReplayDriver`` is this, and **it does not demonstrate
    autonomous problem solving**.  All 120 actions in the HC-V0 bank are ``actor=REFERENCE``.

``INTERACTIVE_TASK``
    The Solver acts in a ``VerifiedTask`` and **may take alternative paths**.  Required for any
    claim about search, repair, or autonomous long-horizon capability.

The defining property, and the whole point of the file: *the Solver may propose an action that is
not the reference proof action, and Lean decides.*  Manual §17.3 -- a Solver action different from
the recorded action is not mathematically wrong unless the verifier establishes that.  A task
therefore must never expose, consult, or fall back to the reference proof during play, and here
that is **structural, not conventional**:

* the reference tactics are read exactly once, by :func:`seal_reference_proof`, which returns only
  digests and lengths and keeps no plaintext anywhere;
* the probe stored on the task is required to carry ``reference_tactics == ()`` and the
  constructor refuses otherwise;
* :class:`VerifiedTask` declares ``__slots__``, so no reference text can be attached to a live
  task afterwards;
* answer-leakage is still detected at runtime by :class:`HashedLeakageGuard`, which slides a
  window over the observation bytes and compares **digests** -- it can recognise the answer
  without containing it.

This module composes ``LeanTrajectoryArena``; it does not modify or reimplement it.

Where the task's status and the arena's status can differ
--------------------------------------------------------

``LeanTrajectoryArena`` reserves ``TerminalStatus.FAILED`` for its own ``fail_fast`` mode and has
no public "terminate with this status" hook, so when the *task's* failure policy or wall-clock
budget ends an episode the task calls ``arena.abandon(reason)`` and the emitted
``VerifiedTrajectory`` records ``ABANDONED`` with a ``REFUSED`` evidence record whose reason names
the policy.  The task's own :meth:`VerifiedTask.terminal_status` is authoritative for the task.
Exactly two cases diverge, both recorded in the reason string:

* ``FAILED`` (``UNRECOVERABLE_INVALID_ACTION``) after the failure policy is exhausted;
* ``BUDGET_EXHAUSTED`` (``SEARCH_BUDGET_EXHAUSTED``) when the *wall-clock* cap trips.

The model-action budget does **not** diverge: the arena's ``attempt_budget`` is set equal to it,
so the arena reaches ``BUDGET_EXHAUSTED`` on the same action the task does.

Nothing here calls a model.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Self

from arena.canonical.schema import canonical_json, stable_hash
from arena.evolution.record import InterventionClass
from arena.trajectory.arena_v0 import (
    CONTAMINATION_NOTE,
    DEFAULT_TRAIN_JSON,
    ActionSpaceSpec,
    AnswerLeakageError,
    ArenaObservation,
    ArenaStep,
    BackendNativeRenderer,
    LeakageFilter,
    LeanTrajectoryArena,
    ReplayDriver,
    StateRenderer,
    select_candidates,
    source_version_from_record,
)
from arena.trajectory.lean_backend import (
    SEALED_SPLIT_PATHS,
    TRUSTED_AXIOMS,
    LeanTheoremProbe,
    LeanToolchainConfig,
    StepOutcome,
    TacticPolicy,
    ToolchainReport,
    assert_not_sealed,
    check_toolchain,
)
from arena.trajectory.schema import (
    Actor,
    BackendStateEnvelope,
    SourceVersion,
    TerminalStatus,
    VerifiedTrajectory,
)
from arena.trajectory.state_identity import (
    LEAN_TACTIC_WORKSPACE,
    BackendSessionRef,
    KernelStateIdentity,
    WorkspaceProjection,
    goal_digest_of,
    project_workspace,
)

TASK_SCHEMA_VERSION = "arena-verified-task-v0"
TASK_GENERATOR_ID = "arena/trajectory/task.py@v0"


class TaskStateError(RuntimeError):
    """The caller drove the task out of order (stepped before reset, or after a terminal)."""


class ReferenceProofExposureError(RuntimeError):
    """A task was constructed with reference-proof text still attached.  Never downgrade this."""


class BackendOutcomeError(RuntimeError):
    """The backend reported an outcome that cannot be lowered into the manual's vocabulary."""


# =============================================================================================
# Terminal vocabulary: manual §14.4 names over the EXISTING TerminalStatus enum
# =============================================================================================

#: Manual §14.4's terminal outcome names, mapped onto the enum
#: ``arena.trajectory.schema.TerminalStatus`` that already exists.  The enum is **not** forked:
#: this table is the translation, and it is one-way on purpose -- ``ERROR_BACKEND`` covers both
#: ``TOOL_TIMEOUT`` and ``ENVIRONMENT_ERROR``, which the task tells apart with the
#: :class:`ActionResult` that caused the termination.
TERMINAL_OUTCOME_NAMES: dict[TerminalStatus, str] = {
    TerminalStatus.OPEN: "OPEN",
    TerminalStatus.CLOSED_VERIFIED: "VERIFIED_SOLVED",
    TerminalStatus.FAILED: "UNRECOVERABLE_INVALID_ACTION",
    TerminalStatus.BUDGET_EXHAUSTED: "SEARCH_BUDGET_EXHAUSTED",
    TerminalStatus.ERROR_BACKEND: "ENVIRONMENT_ERROR",
    TerminalStatus.ABANDONED: "EPISODE_ABANDONED",
}


class ActionResult(StrEnum):
    """The typed result of one attempted action.  There is no untyped outcome.

    ``ENVIRONMENT_ERROR`` **is never a mathematical failure** (manual §14.4, §28).  Neither is
    ``TOOL_TIMEOUT`` or ``UNSUPPORTED``: the first two are the harness failing, the third is the
    action interface declining before any mathematics was asserted.  Only
    ``REJECTED_INVALID_ACTION`` is Lean saying "no" to a mathematical move.
    """

    #: Lean accepted the action; the state advanced.
    ACCEPTED_TRANSITION = "ACCEPTED_TRANSITION"
    #: Lean's elaborator rejected the tactic at this goal.  The only mathematical failure.
    REJECTED_INVALID_ACTION = "REJECTED_INVALID_ACTION"
    #: The action could not be decoded into a backend action at all; it never reached Lean.
    PARSE_FAILURE = "PARSE_FAILURE"
    #: The backend exceeded its per-step wall-clock cap.
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    #: The backend process died, expired, or produced something unparseable.
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    #: Outside the declared action interface: refused by the tactic policy, or ``sorry``.
    UNSUPPORTED = "UNSUPPORTED"

    @property
    def advanced_state(self) -> bool:
        return self is ActionResult.ACCEPTED_TRANSITION

    @property
    def is_mathematical_failure(self) -> bool:
        """Only a verifier rejection of a well-formed action is a mathematical failure."""

        return self is ActionResult.REJECTED_INVALID_ACTION

    @property
    def attributable_to_solver(self) -> bool:
        """Whether the failure policy should count this against the Solver.

        A malformed emission and an out-of-interface action are the Solver's; a dead backend and a
        timeout are the harness's and must never be charged to the policy under measurement.
        """

        return self in {
            ActionResult.REJECTED_INVALID_ACTION,
            ActionResult.PARSE_FAILURE,
            ActionResult.UNSUPPORTED,
        }


#: How the backend's own :class:`~arena.trajectory.lean_backend.StepOutcome` lowers into the
#: §14.4 vocabulary.  Every member of ``StepOutcome`` appears exactly once; a new backend outcome
#: that is not in this table raises rather than defaulting to something reassuring.
_OUTCOME_TO_RESULT: dict[StepOutcome, ActionResult] = {
    StepOutcome.OK: ActionResult.ACCEPTED_TRANSITION,
    StepOutcome.TACTIC_ERROR: ActionResult.REJECTED_INVALID_ACTION,
    StepOutcome.POLICY_REJECTED: ActionResult.UNSUPPORTED,
    StepOutcome.SORRY_REFUSED: ActionResult.UNSUPPORTED,
    StepOutcome.TIMEOUT: ActionResult.TOOL_TIMEOUT,
    StepOutcome.BACKEND_DEAD: ActionResult.ENVIRONMENT_ERROR,
    StepOutcome.SESSION_EXPIRED: ActionResult.ENVIRONMENT_ERROR,
    StepOutcome.UNKNOWN_STATE_ID: ActionResult.ENVIRONMENT_ERROR,
}


def classify_backend_outcome(outcome: str) -> ActionResult:
    """Lower a backend outcome name into the manual's action-result vocabulary."""

    try:
        return _OUTCOME_TO_RESULT[StepOutcome(outcome)]
    except (KeyError, ValueError) as exc:
        raise BackendOutcomeError(
            f"unmapped backend outcome {outcome!r}: refusing to guess a terminal class"
        ) from exc


# =============================================================================================
# Failure policy — declared BEFORE any performance was observed
# =============================================================================================


class FailurePolicy(StrEnum):
    """What happens after an action the Solver is answerable for.

    Declared and committed **before any Solver performance was observed** (2026-09-08, this
    commit), so the choice cannot be a post-hoc accommodation of a result.
    """

    #: (a) One invalid action ends the episode.  Harsh, and the cleanest read of "long-horizon".
    TERMINATE_ON_FIRST_INVALID = "TERMINATE_ON_FIRST_INVALID"
    #: (b) The Solver gets one minimal backend diagnostic and ``max_retries`` further attempts.
    #: Recommended for the first smoke with ``max_retries=1``: an environment that terminates on
    #: the first parse slip measures formatting, not mathematics.
    ONE_DIAGNOSTIC_RETRY = "ONE_DIAGNOSTIC_RETRY"


class RetryScope(StrEnum):
    """What ``max_retries`` is counted against."""

    #: Counted per unbroken run of failures; an accepted transition resets it.  Default.
    PER_CONSECUTIVE_RUN = "PER_CONSECUTIVE_RUN"
    #: Counted once for the whole episode.
    PER_EPISODE = "PER_EPISODE"


@dataclass(frozen=True, slots=True)
class FailurePolicySpec:
    """The failure policy, as a value that travels in provenance."""

    policy: FailurePolicy = FailurePolicy.ONE_DIAGNOSTIC_RETRY
    max_retries: int = 1
    scope: RetryScope = RetryScope.PER_CONSECUTIVE_RUN
    diagnostic_max_chars: int = 400
    declared_before_measurement: bool = True

    @property
    def effective_retries(self) -> int:
        if self.policy is FailurePolicy.TERMINATE_ON_FIRST_INVALID:
            return 0
        return max(0, self.max_retries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.value,
            "max_retries": self.max_retries,
            "effective_retries": self.effective_retries,
            "scope": self.scope.value,
            "diagnostic_max_chars": self.diagnostic_max_chars,
            "declared_before_measurement": self.declared_before_measurement,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            policy=FailurePolicy(payload.get("policy", FailurePolicy.ONE_DIAGNOSTIC_RETRY.value)),
            max_retries=int(payload.get("max_retries", 1)),
            scope=RetryScope(payload.get("scope", RetryScope.PER_CONSECUTIVE_RUN.value)),
            diagnostic_max_chars=int(payload.get("diagnostic_max_chars", 400)),
            declared_before_measurement=bool(payload.get("declared_before_measurement", True)),
        )


# =============================================================================================
# Budget and cost (manual §13.1) — six counters, never flattened into "steps"
# =============================================================================================


@dataclass(frozen=True, slots=True)
class TaskBudget:
    """Per-episode caps.  ``0`` means "not capped" for the count-based fields."""

    model_actions: int = 32
    wall_clock_s: float = 900.0
    kernel_steps: int = 0
    verifier_calls: int = 0
    tool_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_actions": self.model_actions,
            "wall_clock_s": self.wall_clock_s,
            "kernel_steps": self.kernel_steps,
            "verifier_calls": self.verifier_calls,
            "tool_calls": self.tool_calls,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            model_actions=int(payload.get("model_actions", 32)),
            wall_clock_s=float(payload.get("wall_clock_s", 900.0)),
            kernel_steps=int(payload.get("kernel_steps", 0)),
            verifier_calls=int(payload.get("verifier_calls", 0)),
            tool_calls=int(payload.get("tool_calls", 0)),
        )


@dataclass(frozen=True, slots=True)
class ActionCost:
    """What one attempted action cost, manual §13.1, kept as six separate numbers.

    They are **not** summarised into "steps".  ``model_action_count`` is what the policy emitted;
    ``lowered_action_count`` is what that lowered to at the backend boundary; ``kernel_step_count``
    is the post-lowering cost that a future action macro must not be able to hide.  At V0's
    granularity one accepted tactic is one lowered action and one kernel step, so the three
    coincide -- they are computed separately because the moment a macro lands they must diverge.

    The three token slots are typed and left ``None``: counting tokens is the Solver adapter's
    job, and a zero here would be a measurement this environment did not make.
    """

    model_action_count: int = 1
    lowered_action_count: int = 0
    kernel_step_count: int = 0
    verifier_call_count: int = 0
    tool_call_count: int = 0
    wall_clock_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_action_count": self.model_action_count,
            "lowered_action_count": self.lowered_action_count,
            "kernel_step_count": self.kernel_step_count,
            "verifier_call_count": self.verifier_call_count,
            "tool_call_count": self.tool_call_count,
            "wall_clock_s": round(self.wall_clock_s, 6),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(slots=True)
class CostLedger:
    """Per-episode totals plus the per-action record they were summed from."""

    model_action_count: int = 0
    lowered_action_count: int = 0
    kernel_step_count: int = 0
    verifier_call_count: int = 0
    tool_call_count: int = 0
    wall_clock_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    per_action: list[ActionCost] = field(default_factory=list)

    def add(self, cost: ActionCost) -> None:
        self.model_action_count += cost.model_action_count
        self.lowered_action_count += cost.lowered_action_count
        self.kernel_step_count += cost.kernel_step_count
        self.verifier_call_count += cost.verifier_call_count
        self.tool_call_count += cost.tool_call_count
        self.wall_clock_s += cost.wall_clock_s
        for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = getattr(cost, name)
            if value is not None:
                setattr(self, name, (getattr(self, name) or 0) + value)
        self.per_action.append(cost)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_action_count": self.model_action_count,
            "lowered_action_count": self.lowered_action_count,
            "kernel_step_count": self.kernel_step_count,
            "verifier_call_count": self.verifier_call_count,
            "tool_call_count": self.tool_call_count,
            "wall_clock_s": round(self.wall_clock_s, 3),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "per_action": [cost.to_dict() for cost in self.per_action],
        }


# =============================================================================================
# The sealed reference proof: digests in, no plaintext anywhere
# =============================================================================================


class SolvabilityAttestation(StrEnum):
    """How we know the task is solvable at all.  ``UNATTESTED`` is a valid, honest answer."""

    UNATTESTED = "UNATTESTED"
    #: The source says mathlib proves it.  Not re-run here; the flat replay closes only ~42%.
    ASSERTED_BY_SOURCE = "ASSERTED_BY_SOURCE"
    #: The reference proof was replayed live and the kernel accepted the finished declaration.
    REFERENCE_REPLAY_CLOSED_VERIFIED = "REFERENCE_REPLAY_CLOSED_VERIFIED"
    #: The reference proof was replayed live and did not close.  The task may still be solvable.
    REFERENCE_REPLAY_DID_NOT_CLOSE = "REFERENCE_REPLAY_DID_NOT_CLOSE"


@dataclass(frozen=True, slots=True)
class ReferenceProofSeal:
    """Everything the task is allowed to keep about the reference proof.

    Digests, byte lengths and a count.  **No tactic text, and no field from which text could be
    recovered**: SHA-256 is not invertible and a length is not a hint.  This is what makes the
    structural claim checkable -- a test can walk every object reachable from a task and assert
    that no reference tactic string is present, and it passes because none exists.
    """

    tactic_count: int
    script_digest: str
    tactic_digests: tuple[str, ...] = ()
    tactic_byte_lengths: tuple[int, ...] = ()
    solvability: SolvabilityAttestation = SolvabilityAttestation.UNATTESTED
    attestation_detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tactic_count": self.tactic_count,
            "script_digest": self.script_digest,
            "tactic_digests": list(self.tactic_digests),
            "tactic_byte_lengths": list(self.tactic_byte_lengths),
            "solvability": self.solvability.value,
            "attestation_detail": self.attestation_detail,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tactic_count=int(payload["tactic_count"]),
            script_digest=str(payload["script_digest"]),
            tactic_digests=tuple(str(item) for item in payload.get("tactic_digests", ())),
            tactic_byte_lengths=tuple(int(item) for item in payload.get("tactic_byte_lengths", ())),
            solvability=SolvabilityAttestation(payload.get("solvability", "UNATTESTED")),
            attestation_detail=str(payload.get("attestation_detail", "")),
        )


@dataclass(frozen=True, slots=True)
class HashedLeakageGuard:
    """Detects the answer in an observation **without holding the answer**.

    It keeps ``(utf-8 byte length, sha256)`` pairs.  To check a payload it encodes it once and,
    for each distinct secret length, slides a window of that length over the bytes and hashes it.
    That is an exact verbatim-substring test using only digests, so the guard can say "the
    reference tactic is visible here" and can never say what it is.

    Secrets shorter than ``min_secret_len`` bytes are not registered: short tactics such as
    ``rfl`` occur inside ordinary goal text by coincidence, and the existing
    :class:`~arena.trajectory.arena_v0.LeakageFilter` uses the same threshold, so the two remain
    directly comparable.
    """

    secrets: tuple[tuple[int, str], ...] = ()
    min_secret_len: int = 6

    @property
    def armed(self) -> bool:
        return bool(self.secrets)

    def _lengths(self) -> dict[int, set[str]]:
        by_length: dict[int, set[str]] = {}
        for length, digest in self.secrets:
            by_length.setdefault(length, set()).add(digest)
        return by_length

    def find_leak(self, payload: str) -> str | None:
        """Return the digest of a leaked secret, or ``None``.  Never returns the secret."""

        data = payload.encode("utf-8")
        for length, digests in self._lengths().items():
            if length > len(data):
                continue
            for start in range(len(data) - length + 1):
                candidate = hashlib.sha256(data[start : start + length]).hexdigest()
                if candidate in digests:
                    return candidate
        return None

    def assert_clean(self, payload: str, *, where: str) -> None:
        digest = self.find_leak(payload)
        if digest is not None:
            raise AnswerLeakageError(
                f"{where} contains a sealed reference tactic (digest {digest[:16]}...); "
                "refusing to show it. The guard holds only digests, so the tactic itself is "
                "not recoverable from this message."
            )


def seal_reference_proof(
    tactics: Sequence[str],
    *,
    solvability: SolvabilityAttestation = SolvabilityAttestation.ASSERTED_BY_SOURCE,
    attestation_detail: str = "",
    min_secret_len: int = 6,
) -> tuple[ReferenceProofSeal, HashedLeakageGuard]:
    """The **only** function in this module that touches reference-proof text.

    It consumes the tactic strings and returns objects made entirely of digests, counts and byte
    lengths.  The caller must not retain the input; :meth:`VerifiedTask.from_probe` does not.
    """

    encoded = [tactic.encode("utf-8") for tactic in tactics]
    digests = tuple(hashlib.sha256(item).hexdigest() for item in encoded)
    lengths = tuple(len(item) for item in encoded)
    script_digest = hashlib.sha256("\n".join(tactics).encode("utf-8")).hexdigest()
    seal = ReferenceProofSeal(
        tactic_count=len(tactics),
        script_digest=script_digest,
        tactic_digests=digests,
        tactic_byte_lengths=lengths,
        solvability=solvability,
        attestation_detail=attestation_detail,
    )
    guard = HashedLeakageGuard(
        secrets=tuple(
            (length, digest)
            for length, digest in zip(lengths, digests, strict=True)
            if length >= min_secret_len
        ),
        min_secret_len=min_secret_len,
    )
    return seal, guard


def strip_reference(probe: LeanTheoremProbe) -> LeanTheoremProbe:
    """A probe that can start a session but carries no reference proof."""

    return replace(probe, reference_tactics=())


def attest_solvable_by_replay(
    record: Mapping[str, Any],
    probe: LeanTheoremProbe,
    *,
    config: LeanToolchainConfig | None = None,
    policy: TacticPolicy | None = None,
    seed: int = 0,
) -> tuple[SolvabilityAttestation, str]:
    """Run the recorded reference proof once, live, **only** to learn whether the task closes.

    This is construction-time reason (a) of the directive: knowing the task is solvable.  It costs
    one Lean session (~1-4 s) and it is the only place the reference proof is ever *executed*.
    The tactics are not returned and not retained -- the caller receives an enum and a sentence.

    A ``REFERENCE_REPLAY_DID_NOT_CLOSE`` verdict does **not** mean the task is unsolvable: a
    recorded LeanDojo proof is a traversal of a proof *tree* and a flat replay of it closed 42% of
    the time in the HC-V0 bank (20% at reference length >= 12).  It means "not attested", and it
    says so.
    """

    outcome = ReplayDriver(config=config, policy=policy, seed=seed).run(dict(record), probe)
    if outcome.terminal_status is TerminalStatus.CLOSED_VERIFIED:
        return (
            SolvabilityAttestation.REFERENCE_REPLAY_CLOSED_VERIFIED,
            f"a flat live replay of the {len(probe.reference_tactics)}-tactic reference proof "
            "closed the goals and the kernel accepted the finished declaration",
        )
    return (
        SolvabilityAttestation.REFERENCE_REPLAY_DID_NOT_CLOSE,
        f"a flat live replay ended {outcome.terminal_status.value} at "
        f"{outcome.achieved_horizon}/{len(probe.reference_tactics)} tactics; a recorded proof is "
        "a traversal of a TREE and a flat replay closes ~42% of the time, so this is NOT evidence "
        "that the task is unsolvable",
    )


# =============================================================================================
# Task descriptors (manual §17.1 field list)
# =============================================================================================


@dataclass(frozen=True, slots=True)
class BackendKernelContract:
    """Which kernel decides truth, at which version, with which trusted base."""

    system: str = "lean4"
    toolchain: str = ""
    lean_version_string: str = ""
    mathlib_commit: str = ""
    mathlib_build_root: str = ""
    repl: str = "Lean4Repl.lean :: lean_dojo_repl"
    olean_count: int | None = None
    trusted_axioms: tuple[str, ...] = tuple(sorted(TRUSTED_AXIOMS))
    closure_check: str = "re-elaborate the accepted script and read `#print axioms` (allow-list)"

    @classmethod
    def from_report(
        cls, report: ToolchainReport, *, mathlib_commit: str = "", olean_count: int | None = None
    ) -> BackendKernelContract:
        return cls(
            toolchain=report.toolchain,
            lean_version_string=report.lean_version_string,
            mathlib_commit=mathlib_commit,
            mathlib_build_root=str(report.mathlib_root),
            olean_count=olean_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "toolchain": self.toolchain,
            "lean_version_string": self.lean_version_string,
            "mathlib_commit": self.mathlib_commit,
            "mathlib_build_root": self.mathlib_build_root,
            "repl": self.repl,
            "olean_count": self.olean_count,
            "trusted_axioms": list(self.trusted_axioms),
            "closure_check": self.closure_check,
        }


@dataclass(frozen=True, slots=True)
class InitialStateRef:
    """A reference to the start state that can be computed **without starting Lean**.

    It names the declaration and digests the exact text that will be elaborated, so two tasks
    built from the same source on the same checkout are provably the same task, and a task whose
    source file changed underneath it is provably not.
    """

    problem_id: str
    full_name: str
    file_path: str
    statement_digest: str
    prefix_digest: str
    scope_digest: str
    probe_name: str = ""

    @classmethod
    def from_probe(cls, probe: LeanTheoremProbe) -> InitialStateRef:
        _, scope_digest = goal_digest_of("", probe.pp_scope)
        return cls(
            problem_id=probe.problem_id,
            full_name=probe.full_name,
            file_path=probe.file_path,
            statement_digest=hashlib.sha256(probe.statement.encode("utf-8")).hexdigest(),
            prefix_digest=hashlib.sha256(probe.prefix_text.encode("utf-8")).hexdigest(),
            scope_digest=scope_digest,
            probe_name=probe.probe_name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "full_name": self.full_name,
            "file_path": self.file_path,
            "statement_digest": self.statement_digest,
            "prefix_digest": self.prefix_digest,
            "scope_digest": self.scope_digest,
            "probe_name": self.probe_name,
        }


@dataclass(frozen=True, slots=True)
class VerifierAdapterSpec:
    """Which verifier answers, and what trusting it commits us to (manual §28)."""

    verifier_id: str = "lean4-repl+lean4-kernel@v0"
    step_verifier: str = "Lean 4 elaborator, driven through Lean4Repl.lean :: lean_dojo_repl"
    terminal_verifier: str = "separate re-elaboration of the accepted script plus `#print axioms`"
    trusted_axioms: tuple[str, ...] = tuple(sorted(TRUSTED_AXIOMS))
    trust_assumptions: tuple[str, ...] = (
        "the Lean 4 kernel is sound at the pinned toolchain",
        "the built mathlib oleans at the recorded root are the ones that were elaborated",
        "`#print axioms` reports the complete axiom dependency of the finished declaration",
        "the axiom ALLOW-list fails closed: anything outside it, including Lean.ofReduceBool, "
        "is untrusted (RT-01)",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "step_verifier": self.step_verifier,
            "terminal_verifier": self.terminal_verifier,
            "trusted_axioms": list(self.trusted_axioms),
            "trust_assumptions": list(self.trust_assumptions),
        }


@dataclass(frozen=True, slots=True)
class TerminalPredicateSpec:
    """When the episode is over, and what "solved" requires."""

    solved_requires_kernel_evidence: bool = True
    no_goals_alone_is_sufficient: bool = False
    description: str = (
        "VERIFIED_SOLVED requires BOTH the session reporting `no goals` AND a separate "
        "re-elaboration of the whole accepted script whose `#print axioms` output lies inside the "
        "trusted allow-list. `no goals` alone is necessary and never sufficient."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "solved_requires_kernel_evidence": self.solved_requires_kernel_evidence,
            "no_goals_alone_is_sufficient": self.no_goals_alone_is_sufficient,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class TaskProvenance:
    """What must travel with any number this task produces."""

    generator: str = TASK_GENERATOR_ID
    trust_tier: str = "A_NATIVE_VERIFIED"
    mode: str = "INTERACTIVE_TASK"
    created_utc: str = ""
    seed: int = 0
    sealed_splits_not_read: tuple[str, ...] = SEALED_SPLIT_PATHS
    contamination: str = CONTAMINATION_NOTE
    static_leakage_filters: tuple[str, ...] = ()
    runtime_leakage_guard: str = "hashed-window-v0"
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "generator": self.generator,
            "trust_tier": self.trust_tier,
            "mode": self.mode,
            "created_utc": self.created_utc,
            "seed": self.seed,
            "sealed_splits_not_read": list(self.sealed_splits_not_read),
            "contamination": self.contamination,
            "static_leakage_filters": list(self.static_leakage_filters),
            "runtime_leakage_guard": self.runtime_leakage_guard,
            "notes": list(self.notes),
        }

    def semantic_core(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("created_utc")
        return payload


# =============================================================================================
# Step and episode results
# =============================================================================================


@dataclass(frozen=True, slots=True)
class TaskStepResult:
    """One verified transition attempt.  Every field is typed; nothing is implicit."""

    result: ActionResult
    observation: WorkspaceProjection
    state_identity: KernelStateIdentity
    reward: float
    terminal_status: TerminalStatus
    terminal_outcome: str
    diagnostic: str
    retries_remaining: int
    cost: ActionCost
    backend_outcome: str
    info: Mapping[str, Any] = field(default_factory=dict)

    @property
    def done(self) -> bool:
        return self.terminal_status.is_terminal

    @property
    def advanced(self) -> bool:
        return self.result.advanced_state

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "is_mathematical_failure": self.result.is_mathematical_failure,
            "state_identity": self.state_identity.to_dict(),
            "projection": self.observation.identity.to_dict(),
            "reward": self.reward,
            "terminal_status": self.terminal_status.value,
            "terminal_outcome": self.terminal_outcome,
            "diagnostic": self.diagnostic,
            "retries_remaining": self.retries_remaining,
            "cost": self.cost.to_dict(),
            "backend_outcome": self.backend_outcome,
            "info": dict(self.info),
        }


@dataclass(frozen=True, slots=True)
class TaskEpisodeReport:
    """The episode, as it will be reported.  Costs are the six §13.1 counters, unflattened."""

    task_id: str
    problem_id: str
    episode_index: int
    session_id: str
    terminal_status: TerminalStatus
    terminal_outcome: str
    reward: float
    actions_attempted: int
    actions_accepted: int
    reference_tactic_count: int
    cost: dict[str, Any]
    failure_policy: dict[str, Any]
    budget: dict[str, Any]
    renderer_id: str
    start_state_identity: dict[str, Any] | None
    final_state_identity: dict[str, Any] | None
    action_log: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "problem_id": self.problem_id,
            "episode_index": self.episode_index,
            "session_id": self.session_id,
            "terminal_status": self.terminal_status.value,
            "terminal_outcome": self.terminal_outcome,
            "reward": self.reward,
            "actions_attempted": self.actions_attempted,
            "actions_accepted": self.actions_accepted,
            "reference_tactic_count": self.reference_tactic_count,
            "cost": self.cost,
            "failure_policy": self.failure_policy,
            "budget": self.budget,
            "renderer_id": self.renderer_id,
            "start_state_identity": self.start_state_identity,
            "final_state_identity": self.final_state_identity,
            "action_log": list(self.action_log),
        }


# =============================================================================================
# The arena seam
# =============================================================================================


class TaskArena(Protocol):
    """The subset of ``LeanTrajectoryArena`` a task drives.

    Declared as a protocol so a test can inject a deterministic scripted backend and exercise the
    failure policy, the budget and the terminal vocabulary on a machine with no Lean, while the
    real backend remains the only thing that ever decides mathematics.
    """

    @property
    def terminal_status(self) -> TerminalStatus: ...

    @property
    def states(self) -> tuple[BackendStateEnvelope, ...]: ...

    @property
    def legal_action_space(self) -> ActionSpaceSpec: ...

    def reset(
        self, probe: LeanTheoremProbe, *, hide_reference: Sequence[str] | None = None
    ) -> ArenaObservation: ...

    def step(self, tactic: str) -> ArenaStep: ...

    def abandon(self, reason: str) -> TerminalStatus: ...

    def close(self) -> None: ...


ArenaFactory = Callable[[], TaskArena]


# =============================================================================================
# VerifiedTask
# =============================================================================================


class VerifiedTask:
    """An interactive, verifier-backed task over one Lean declaration (manual §6.25, §17.1).

    ::

        task = VerifiedTask.from_probe(probe, contract=contract)   # seals the reference proof
        projection = task.reset()
        while not task.is_terminal():
            outcome = task.step(my_policy(projection))
            projection = outcome.observation

    The Solver may play anything; Lean decides.  ``task.reference_seal`` reports how long the
    recorded proof was and whether it is known to close, and contains no tactic text.
    """

    __slots__ = (
        "_accepted_tactics",
        "_action_log",
        "_arena",
        "_arena_factory",
        "_cost",
        "_current",
        "_episode_index",
        "_episode_retries_used",
        "_probe",
        "_run_failures",
        "_session",
        "_start_identity",
        "_started_monotonic",
        "_terminal",
        "_terminal_cause",
        "action_interface",
        "backend_kernel_contract",
        "budget",
        "failure_policy",
        "initial_state_ref",
        "intervention_class",
        "leakage_guard",
        "problem_id",
        "provenance",
        "reference_seal",
        "renderer",
        "source_hash",
        "source_system",
        "source_version",
        "task_id",
        "terminal_predicate",
        "verifier_adapter",
        "workspace_kind",
    )

    def __init__(
        self,
        *,
        probe: LeanTheoremProbe,
        reference_seal: ReferenceProofSeal,
        leakage_guard: HashedLeakageGuard,
        source_system: str = "LeanDojo Benchmark 4",
        source_version: SourceVersion | None = None,
        backend_kernel_contract: BackendKernelContract | None = None,
        action_interface: ActionSpaceSpec | None = None,
        verifier_adapter: VerifierAdapterSpec | None = None,
        terminal_predicate: TerminalPredicateSpec | None = None,
        budget: TaskBudget | None = None,
        failure_policy: FailurePolicySpec | None = None,
        provenance: TaskProvenance | None = None,
        renderer: StateRenderer | None = None,
        workspace_kind: str = LEAN_TACTIC_WORKSPACE,
        intervention_class: InterventionClass = InterventionClass.R_ONLY,
        arena_factory: ArenaFactory | None = None,
        config: LeanToolchainConfig | None = None,
        policy: TacticPolicy | None = None,
    ) -> None:
        if probe.reference_tactics:
            raise ReferenceProofExposureError(
                "VerifiedTask refuses a probe that still carries reference_tactics: the task "
                "must be structurally unable to read the answer during play. Use "
                "VerifiedTask.from_probe(), which seals the reference proof into digests."
            )
        self._probe = probe
        self.reference_seal = reference_seal
        self.leakage_guard = leakage_guard
        self.problem_id = probe.problem_id
        self.source_system = source_system
        self.source_version = source_version
        self.backend_kernel_contract = backend_kernel_contract or BackendKernelContract()
        tactic_policy = policy or TacticPolicy.record_only()
        self.action_interface = action_interface or ActionSpaceSpec.from_policy(tactic_policy)
        self.verifier_adapter = verifier_adapter or VerifierAdapterSpec()
        self.terminal_predicate = terminal_predicate or TerminalPredicateSpec()
        self.budget = budget or TaskBudget()
        self.failure_policy = failure_policy or FailurePolicySpec()
        self.provenance = provenance or TaskProvenance(
            created_utc=datetime.now(UTC).isoformat(timespec="seconds")
        )
        self.renderer = renderer or BackendNativeRenderer()
        self.workspace_kind = workspace_kind
        self.intervention_class = intervention_class
        self.initial_state_ref = InitialStateRef.from_probe(probe)
        self.source_hash = _source_hash(self.initial_state_ref, source_version, reference_seal)
        self.task_id = _derive_task_id(self)
        self._arena_factory: ArenaFactory = arena_factory or _lean_arena_factory(
            config=config, policy=tactic_policy, renderer=self.renderer, budget=self.budget
        )
        self._arena: TaskArena | None = None
        self._session = BackendSessionRef(session_id="")
        self._episode_index = 0
        self._terminal = TerminalStatus.OPEN
        self._terminal_cause: ActionResult | None = None
        self._current: BackendStateEnvelope | None = None
        self._start_identity: KernelStateIdentity | None = None
        self._cost = CostLedger()
        self._run_failures = 0
        self._episode_retries_used = 0
        self._accepted_tactics = 0
        self._action_log: list[dict[str, Any]] = []
        self._started_monotonic = 0.0

    # -- construction ---------------------------------------------------------------

    @classmethod
    def from_probe(
        cls,
        probe: LeanTheoremProbe,
        *,
        solvability: SolvabilityAttestation = SolvabilityAttestation.ASSERTED_BY_SOURCE,
        attestation_detail: str = "",
        **kwargs: Any,
    ) -> VerifiedTask:
        """Build a task from a probe, **consuming** its reference proof into a seal.

        This is the construction path the directive requires: the reference proof is read exactly
        here, exactly twice -- once to know the task is solvable and once for provenance -- and is
        then unreachable.  The probe handed to the task has ``reference_tactics == ()``.
        """

        seal, guard = seal_reference_proof(
            probe.reference_tactics,
            solvability=solvability,
            attestation_detail=attestation_detail,
        )
        return cls(
            probe=strip_reference(probe),
            reference_seal=seal,
            leakage_guard=guard,
            **kwargs,
        )

    @classmethod
    def from_leandojo_record(
        cls,
        record: Mapping[str, Any],
        probe: LeanTheoremProbe,
        *,
        static_leakage_filter: LeakageFilter | None = None,
        attest_by_replay: bool = False,
        **kwargs: Any,
    ) -> VerifiedTask:
        """Build a task from a LeanDojo record plus the probe built from it.

        The static leakage filter runs here, on the *source record*, and its verdict is recorded
        in provenance.  It is the filter that was measured (92 leaking steps of 250,814; 2 leaking
        proofs of 59,557), so drop counts stay comparable with the bank's.
        """

        scanner = static_leakage_filter or LeakageFilter()
        reasons = scanner.scan_record(record)
        provenance = kwargs.pop("provenance", None) or TaskProvenance(
            created_utc=datetime.now(UTC).isoformat(timespec="seconds")
        )
        provenance = replace(
            provenance,
            static_leakage_filters=tuple(sorted({reason.value for reason in reasons}))
            or ("NONE_TRIPPED",),
        )
        if attest_by_replay:
            attestation, detail = attest_solvable_by_replay(
                record,
                probe,
                config=kwargs.get("config"),
                policy=kwargs.get("policy"),
            )
            kwargs["solvability"] = attestation
            kwargs["attestation_detail"] = detail
        return cls.from_probe(
            probe,
            source_version=kwargs.pop("source_version", None) or source_version_from_record(record),
            provenance=provenance,
            **kwargs,
        )

    # -- descriptor -----------------------------------------------------------------

    @property
    def schema_version(self) -> str:
        return TASK_SCHEMA_VERSION

    @property
    def theorem_full_name(self) -> str:
        return self.initial_state_ref.full_name

    @property
    def episode_index(self) -> int:
        return self._episode_index

    @property
    def session(self) -> BackendSessionRef:
        return self._session

    def descriptor(self) -> dict[str, Any]:
        """The manual §17.1 record for this task.  Contains no reference-proof text."""

        return {
            "schema": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "problem_id": self.problem_id,
            "theorem_full_name": self.theorem_full_name,
            "source_system": self.source_system,
            "source_version": (
                None if self.source_version is None else self.source_version.to_dict()
            ),
            "source_hash": self.source_hash,
            "backend_kernel_contract": self.backend_kernel_contract.to_dict(),
            "initial_state_ref": self.initial_state_ref.to_dict(),
            "state_identity_scheme": {
                "kernel": "arena.trajectory.state_identity.KernelStateIdentity",
                "workspace_projection": (
                    "arena.trajectory.state_identity.WorkspaceProjectionIdentity"
                ),
                "canonical_projection": "NOT_ATTEMPTED (0/368 lossless)",
            },
            "action_interface": self.action_interface.to_dict(),
            "verifier_adapter": self.verifier_adapter.to_dict(),
            "terminal_predicate": self.terminal_predicate.to_dict(),
            "terminal_outcome_names": {
                status.value: name for status, name in TERMINAL_OUTCOME_NAMES.items()
            },
            "budget": self.budget.to_dict(),
            "failure_policy": self.failure_policy.to_dict(),
            "reference_seal": self.reference_seal.to_dict(),
            "workspace_kind": self.workspace_kind,
            "intervention_class": self.intervention_class.value,
            "renderer_id": self.renderer.renderer_id,
            "mode": "INTERACTIVE_TASK",
            "provenance": self.provenance.to_dict(),
        }

    def semantic_core(self) -> dict[str, Any]:
        """The part of a task that fixes its identity.  Excludes ``Ω_L`` and wall-clock stamps.

        The renderer is deliberately **not** here: two candidate languages must be able to play
        the same task, and they can only be compared if the task is the same object for both.
        """

        return {
            "schema": TASK_SCHEMA_VERSION,
            "problem_id": self.problem_id,
            "source_system": self.source_system,
            "source_hash": self.source_hash,
            "backend_kernel_contract": self.backend_kernel_contract.to_dict(),
            "initial_state_ref": self.initial_state_ref.to_dict(),
            "action_interface": self.action_interface.to_dict(),
            "verifier_adapter": self.verifier_adapter.to_dict(),
            "terminal_predicate": self.terminal_predicate.to_dict(),
            "budget": self.budget.to_dict(),
            "failure_policy": self.failure_policy.to_dict(),
            "reference_seal": self.reference_seal.to_dict(),
            "provenance": self.provenance.semantic_core(),
        }

    # -- interaction ----------------------------------------------------------------

    def reset(self) -> WorkspaceProjection:
        """Start a fresh episode and return the initial workspace.

        Deterministic for a given task: the same task on the same checkout reaches an initial
        state whose :attr:`~...KernelStateIdentity.reelaboration_key` is the same on every reset.
        The *kernel* key is not, and must not be -- a new session's handles address new live
        states and cannot be branched to from the old one.
        """

        self.close()
        self._episode_index += 1
        self._session = BackendSessionRef(session_id=f"{self.task_id}#ep{self._episode_index:04d}")
        self._terminal = TerminalStatus.OPEN
        self._terminal_cause = None
        self._cost = CostLedger()
        self._run_failures = 0
        self._episode_retries_used = 0
        self._accepted_tactics = 0
        self._action_log = []
        self._started_monotonic = time.monotonic()

        arena = self._arena_factory()
        self._arena = arena
        arena.reset(self._probe)
        self._terminal = arena.terminal_status
        if self._terminal is TerminalStatus.ERROR_BACKEND:
            self._terminal_cause = ActionResult.ENVIRONMENT_ERROR
        self._current = arena.states[-1]
        self._start_identity = self._identity(self._current)
        return self.observe()

    def observe(self) -> WorkspaceProjection:
        """``Ω_L``'s input and output: the current workspace, and what it declares."""

        envelope = self._require_state()
        projection = project_workspace(
            self.renderer,
            envelope,
            extra={
                "STEP_INDEX": self._accepted_tactics,
                "ATTEMPTS_REMAINING": self.attempts_remaining,
                "TERMINAL_STATUS": self._terminal.value,
            },
            workspace_kind=self.workspace_kind,
            intervention_class=self.intervention_class,
        )
        self.leakage_guard.assert_clean(
            canonical_json(dict(projection.rendered)), where="the observation"
        )
        return projection

    def state_identity(self) -> KernelStateIdentity:
        """Identity of the state the Solver is currently acting on."""

        return self._identity(self._require_state())

    def step(self, action: str) -> TaskStepResult:
        """Apply one model-facing action.  Lean decides; this method never consults the answer.

        Nothing reachable from ``self`` holds reference-proof text (see the module docstring), so
        there is no fallback path to take even by accident.
        """

        arena = self._require_arena()
        if self._terminal.is_terminal:
            raise TaskStateError(
                f"episode is already terminal ({self._terminal.value}); call reset() to start a "
                "new one rather than stepping a finished episode"
            )
        started = time.monotonic()

        decoded, decode_error = decode_action(action)
        if decoded is None:
            return self._finish_attempt(
                result=ActionResult.PARSE_FAILURE,
                backend_outcome="NOT_LOWERED",
                diagnostic=decode_error,
                reached_backend=False,
                started=started,
                info={"decode_error": decode_error},
            )

        outcome: ArenaStep = arena.step(decoded)
        backend_outcome = str(outcome.info.get("outcome", StepOutcome.BACKEND_DEAD.value))
        result = classify_backend_outcome(backend_outcome)
        if result.advanced_state:
            self._current = arena.states[-1]
            self._accepted_tactics += 1
        was_open = not self._terminal.is_terminal
        self._terminal = _absorb(self._terminal, arena.terminal_status)
        if was_open and self._terminal.is_terminal and self._terminal_cause is None:
            # The backend, not the failure policy, ended the episode: remember which action
            # result did it so TOOL_TIMEOUT is not reported as a generic ENVIRONMENT_ERROR.
            self._terminal_cause = result
        diagnostic = self._diagnostic(outcome)
        return self._finish_attempt(
            result=result,
            backend_outcome=backend_outcome,
            diagnostic=diagnostic,
            reached_backend=True,
            started=started,
            info={
                key: value
                for key, value in outcome.info.items()
                if key in {"tactic_head", "no_op_suspected", "n_goals", "wall_ms", "kernel"}
            },
        )

    def is_terminal(self) -> bool:
        return self._terminal.is_terminal

    def terminal_status(self) -> TerminalStatus:
        """The existing :class:`~arena.trajectory.schema.TerminalStatus`, never a fork of it."""

        return self._terminal

    def terminal_outcome(self) -> str:
        """The manual §14.4 name for the current terminal, e.g. ``VERIFIED_SOLVED``."""

        return self._outcome_name(self._terminal)

    @property
    def attempts_remaining(self) -> int:
        if self.budget.model_actions <= 0:
            return -1
        return max(0, self.budget.model_actions - self._cost.model_action_count)

    @property
    def retries_remaining(self) -> int:
        """How many **further** solver-attributable failures this episode can absorb.

        With the default ``ONE_DIAGNOSTIC_RETRY``/``max_retries=1`` this is ``1`` before any
        failure and ``0`` after the first one -- the first failure is the one the retry is *for*,
        so the episode is still open and the Solver has exactly one more attempt.
        """

        allowed = self.failure_policy.effective_retries
        return max(0, allowed - self._failures_charged())

    def _failures_charged(self) -> int:
        if self.failure_policy.scope is RetryScope.PER_EPISODE:
            return self._episode_retries_used
        return self._run_failures

    @property
    def cost(self) -> CostLedger:
        return self._cost

    def abandon(self, reason: str) -> TerminalStatus:
        """End an open episode deliberately.  Not a failure and never filed as one."""

        if self._terminal.is_terminal:
            return self._terminal
        arena = self._arena
        if arena is not None:
            arena.abandon(reason)
        self._terminal = TerminalStatus.ABANDONED
        return self._terminal

    def close(self) -> None:
        if self._arena is not None:
            self._arena.close()
            self._arena = None

    def __enter__(self) -> VerifiedTask:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- reporting ------------------------------------------------------------------

    def episode_report(self) -> TaskEpisodeReport:
        return TaskEpisodeReport(
            task_id=self.task_id,
            problem_id=self.problem_id,
            episode_index=self._episode_index,
            session_id=self._session.session_id,
            terminal_status=self._terminal,
            terminal_outcome=self.terminal_outcome(),
            reward=self.reward(),
            actions_attempted=self._cost.model_action_count,
            actions_accepted=self._accepted_tactics,
            reference_tactic_count=self.reference_seal.tactic_count,
            cost=self._cost.to_dict(),
            failure_policy=self.failure_policy.to_dict(),
            budget=self.budget.to_dict(),
            renderer_id=self.renderer.renderer_id,
            start_state_identity=(
                None if self._start_identity is None else self._start_identity.to_dict()
            ),
            final_state_identity=(
                None if self._current is None else self._identity(self._current).to_dict()
            ),
            action_log=tuple(self._action_log),
        )

    def reward(self) -> float:
        """``r``: ``+1`` exactly on ``VERIFIED_SOLVED``, ``0`` otherwise.  No shaping (§14.5)."""

        return 1.0 if self._terminal is TerminalStatus.CLOSED_VERIFIED else 0.0

    def emit_trajectory(self, *, reason: str = "") -> VerifiedTrajectory:
        """Emit the episode as a ``VerifiedTrajectory`` with ``actor=SOLVER``.

        See the module docstring: when the task terminated for its own reason the arena is still
        ``OPEN``, so it is abandoned here with a reason naming the task's terminal, and the
        emitted record says ``ABANDONED``.  The task's own terminal stays authoritative and is
        written into the provenance notes so the two can never be confused.
        """

        arena = self._require_arena()
        if not isinstance(arena, LeanTrajectoryArena):  # pragma: no cover - injected test arena
            raise TaskStateError("emit_trajectory() requires the real LeanTrajectoryArena")
        if arena.terminal_status is TerminalStatus.OPEN:
            arena.abandon(
                reason or f"task terminal {self._terminal.value} ({self.terminal_outcome()})"
            )
        source = self.source_version or _placeholder_source_version(self.initial_state_ref)
        return arena.build_trajectory(
            actor=Actor.SOLVER,
            source_version=source,
            reference_horizon=self.reference_seal.tactic_count,
            provenance_notes=(
                f"INTERACTIVE_TASK task_id={self.task_id}",
                f"task_terminal_status={self._terminal.value}",
                f"task_terminal_outcome={self.terminal_outcome()}",
                f"failure_policy={self.failure_policy.policy.value}",
            ),
        )

    # -- internals -------------------------------------------------------------------

    def _require_arena(self) -> TaskArena:
        if self._arena is None:
            raise TaskStateError("reset() must be called before the task can be driven")
        return self._arena

    def _require_state(self) -> BackendStateEnvelope:
        if self._current is None:
            raise TaskStateError("reset() must be called before observe()")
        return self._current

    def _identity(self, envelope: BackendStateEnvelope) -> KernelStateIdentity:
        return KernelStateIdentity.from_envelope(envelope, session=self._session)

    def _outcome_name(self, status: TerminalStatus) -> str:
        if status is TerminalStatus.ERROR_BACKEND and (
            self._terminal_cause is ActionResult.TOOL_TIMEOUT
        ):
            return "TOOL_TIMEOUT"
        if status is TerminalStatus.FAILED and self._terminal_cause is ActionResult.UNSUPPORTED:
            return "UNSUPPORTED"
        return TERMINAL_OUTCOME_NAMES[status]

    def _diagnostic(self, outcome: ArenaStep) -> str:
        """One minimal backend diagnostic: the first non-empty line, truncated, leak-checked."""

        raw = str(outcome.info.get("error") or "")
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        text = lines[0] if lines else ""
        limit = self.failure_policy.diagnostic_max_chars
        if len(text) > limit:
            text = text[:limit] + "…"
        if text:
            self.leakage_guard.assert_clean(text, where="the backend diagnostic")
        return text

    def _finish_attempt(
        self,
        *,
        result: ActionResult,
        backend_outcome: str,
        diagnostic: str,
        reached_backend: bool,
        started: float,
        info: Mapping[str, Any],
    ) -> TaskStepResult:
        elapsed = time.monotonic() - started
        accepted = result.advanced_state
        cost = ActionCost(
            model_action_count=1,
            lowered_action_count=1 if reached_backend else 0,
            kernel_step_count=1 if accepted else 0,
            # Every attempt that reached Lean is one verifier utterance; closing the goals costs
            # a second one, the separate `#print axioms` re-elaboration.
            verifier_call_count=(1 if reached_backend else 0) + (1 if "kernel" in info else 0),
            tool_call_count=(1 if reached_backend else 0) + (1 if "kernel" in info else 0),
            wall_clock_s=elapsed,
        )
        self._cost.add(cost)

        if accepted:
            self._run_failures = 0
        elif result.attributable_to_solver:
            self._run_failures += 1
            self._episode_retries_used += 1

        self._apply_failure_policy(result)
        self._apply_wall_clock_budget()

        identity = self._identity(self._require_state())
        projection = self.observe()
        outcome_name = self.terminal_outcome()
        entry = {
            "attempt": self._cost.model_action_count,
            "result": result.value,
            "backend_outcome": backend_outcome,
            "accepted": accepted,
            "state_id": identity.state_id,
            "terminal_status": self._terminal.value,
            "terminal_outcome": outcome_name,
            "diagnostic": diagnostic,
            "cost": cost.to_dict(),
        }
        self._action_log.append(entry)
        return TaskStepResult(
            result=result,
            observation=projection,
            state_identity=identity,
            reward=self.reward(),
            terminal_status=self._terminal,
            terminal_outcome=outcome_name,
            diagnostic=diagnostic,
            retries_remaining=self.retries_remaining,
            cost=cost,
            backend_outcome=backend_outcome,
            info=dict(info),
        )

    def _apply_failure_policy(self, result: ActionResult) -> None:
        """Terminate on an exhausted retry allowance.  Never on a harness fault."""

        if self._terminal.is_terminal or not result.attributable_to_solver:
            return
        if self._failures_charged() <= self.failure_policy.effective_retries:
            return
        arena = self._arena
        if arena is not None and arena.terminal_status is TerminalStatus.OPEN:
            arena.abandon(
                f"UNRECOVERABLE_INVALID_ACTION under failure policy "
                f"{self.failure_policy.policy.value} (max_retries="
                f"{self.failure_policy.max_retries}, scope={self.failure_policy.scope.value}); "
                f"last result {result.value}"
            )
        self._terminal = TerminalStatus.FAILED
        self._terminal_cause = result

    def _apply_wall_clock_budget(self) -> None:
        if self._terminal.is_terminal or self.budget.wall_clock_s <= 0:
            return
        if time.monotonic() - self._started_monotonic < self.budget.wall_clock_s:
            return
        arena = self._arena
        if arena is not None and arena.terminal_status is TerminalStatus.OPEN:
            arena.abandon(
                f"SEARCH_BUDGET_EXHAUSTED: wall clock cap {self.budget.wall_clock_s}s reached"
            )
        self._terminal = TerminalStatus.BUDGET_EXHAUSTED


def decode_action(action: object) -> tuple[str | None, str]:
    """Decode a model-facing action into a backend action (manual §14.3, the lowering step).

    Deliberately minimal: it rejects what is not an action at all and passes everything else to
    Lean.  Guessing at Lean's syntax here would move the verdict out of the verifier, which is
    exactly what §28 forbids.
    """

    if not isinstance(action, str):
        return None, f"action must be a string, got {type(action).__name__}"
    if not action.strip():
        return None, "action is empty"
    if "\x00" in action:
        return None, "action contains a NUL byte"
    return action, ""


def _absorb(current: TerminalStatus, proposed: TerminalStatus) -> TerminalStatus:
    """Adopt the backend's terminal only while ours is still ``OPEN``."""

    if current.is_terminal:
        return current
    return proposed


def _lean_arena_factory(
    *,
    config: LeanToolchainConfig | None,
    policy: TacticPolicy,
    renderer: StateRenderer,
    budget: TaskBudget,
) -> ArenaFactory:
    """Build a fresh ``LeanTrajectoryArena`` per episode.

    ``attempt_budget`` is set to the task's model-action budget so the two agree on
    ``BUDGET_EXHAUSTED``; ``fail_fast`` is off because the task, not the arena, owns the failure
    policy.
    """

    def factory() -> TaskArena:
        return LeanTrajectoryArena(
            config=config,
            policy=policy,
            renderer=renderer,
            attempt_budget=max(1, budget.model_actions),
            fail_fast=False,
        )

    return factory


def _placeholder_source_version(ref: InitialStateRef) -> SourceVersion:
    return SourceVersion(
        dataset="UNRECORDED",
        license="UNRECORDED",
        split="UNRECORDED",
        file_path=ref.file_path,
        full_name=ref.full_name,
    )


def _source_hash(
    ref: InitialStateRef, source_version: SourceVersion | None, seal: ReferenceProofSeal
) -> str:
    """Digest of everything that fixes which problem this is, including the sealed proof."""

    return stable_hash(
        {
            "initial_state_ref": ref.to_dict(),
            "source_version": None if source_version is None else source_version.to_dict(),
            "reference_script_digest": seal.script_digest,
            "reference_tactic_count": seal.tactic_count,
        }
    )


def _derive_task_id(task: VerifiedTask) -> str:
    digest = stable_hash(task.semantic_core())
    return f"vtask-{digest[:24]}"


# =============================================================================================
# Task selection (deterministic, seeded, sealed splits refused)
# =============================================================================================


@dataclass(frozen=True, slots=True)
class TaskSelection:
    """Which tasks a seed produced, and everything discarded on the way."""

    tasks: tuple[VerifiedTask, ...]
    scanned: int
    discards: dict[str, int]
    leakage: dict[str, Any]
    seed: int
    scan_limit: int
    min_reference_length: int
    max_reference_length: int | None
    train_json: str

    def __iter__(self) -> Iterator[VerifiedTask]:
        return iter(self.tasks)

    def __len__(self) -> int:
        return len(self.tasks)

    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "arena-verified-task-selection-v0",
            "generator": TASK_GENERATOR_ID,
            "train_json": self.train_json,
            "seed": self.seed,
            "scan_limit": self.scan_limit,
            "min_reference_length": self.min_reference_length,
            "max_reference_length": self.max_reference_length,
            "records_scanned": self.scanned,
            "tasks_selected": len(self.tasks),
            "discards": self.discards,
            "leakage": self.leakage,
            "sealed_splits_not_read": list(SEALED_SPLIT_PATHS),
            "contamination": CONTAMINATION_NOTE,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "problem_id": task.problem_id,
                    "reference_tactic_count": task.reference_seal.tactic_count,
                    "source_hash": task.source_hash,
                }
                for task in self.tasks
            ],
        }


def select_verified_tasks(
    *,
    train_json: Path = DEFAULT_TRAIN_JSON,
    min_reference_length: int = 1,
    max_reference_length: int | None = None,
    limit: int = 8,
    seed: int = 0,
    scan_limit: int = 20_000,
    policy: TacticPolicy | None = None,
    config: LeanToolchainConfig | None = None,
    mathlib_root: Path | None = None,
    renderer: StateRenderer | None = None,
    budget: TaskBudget | None = None,
    failure_policy: FailurePolicySpec | None = None,
    backend_kernel_contract: BackendKernelContract | None = None,
    allow_multiline_tactics: bool = False,
    solvability: SolvabilityAttestation = SolvabilityAttestation.ASSERTED_BY_SOURCE,
    attest_by_replay: bool = False,
) -> TaskSelection:
    """Build ``limit`` interactive tasks from the LeanDojo **train** split, deterministically.

    Determinism is a pure function of ``(train_json, scan_limit, min/max reference length, policy,
    seed)``: the head of the file is read in file order, filtered, then permuted by
    ``random.Random(seed)``.  ``scan_limit`` is part of the sample's identity, not a convenience.

    ``min_reference_length`` / ``max_reference_length`` filter on the length of the **recorded**
    proof.  That is a difficulty *proxy* for sampling and nothing else -- manual §6.34 and §17.6:
    a recorded length is not a required reasoning depth, and ``MinimalProofLength`` is ``UNKNOWN``.
    Filtering on anything downstream of a Solver's performance would make the sample a function of
    the result; this function cannot do that because it never runs a Solver.

    The four sealed splits are refused up front, before any I/O.
    """

    assert_not_sealed(train_json)
    policy = policy or TacticPolicy.record_only()
    config = config or LeanToolchainConfig.from_env()
    root = mathlib_root or config.mathlib_root
    selection = select_candidates(
        train_json=train_json,
        min_horizon=min_reference_length,
        limit=limit,
        seed=seed,
        scan_limit=scan_limit,
        policy=policy,
        mathlib_root=root,
        max_horizon=max_reference_length,
        allow_multiline_tactics=allow_multiline_tactics,
    )
    contract = backend_kernel_contract
    if contract is None:
        report = check_toolchain(config)
        contract = BackendKernelContract.from_report(report)
    tasks = tuple(
        VerifiedTask.from_leandojo_record(
            record,
            probe,
            attest_by_replay=attest_by_replay,
            solvability=solvability,
            attestation_detail=(
                "the source records a mathlib proof for this declaration; it was NOT re-run here "
                "(flat replay of a recorded proof tree closes ~42% of the time)"
            ),
            backend_kernel_contract=contract,
            renderer=renderer,
            budget=budget,
            failure_policy=failure_policy,
            policy=policy,
            config=config,
            provenance=TaskProvenance(
                created_utc=datetime.now(UTC).isoformat(timespec="seconds"), seed=seed
            ),
        )
        for record, probe in zip(selection.records, selection.probes, strict=True)
    )
    return TaskSelection(
        tasks=tasks,
        scanned=selection.scanned,
        discards=selection.discards.to_dict(),
        leakage=selection.leakage.to_dict(),
        seed=seed,
        scan_limit=scan_limit,
        min_reference_length=min_reference_length,
        max_reference_length=max_reference_length,
        train_json=str(train_json),
    )
