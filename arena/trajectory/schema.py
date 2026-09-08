"""The ``VerifiedTrajectory`` record: backend-native states, kernel-backed verdicts.

Design constraints, each taken from a measurement rather than from taste
(``docs/VERIFIED_TRAJECTORY_ARENA_V0.md``):

1. **The Arena canonical schema cannot hold a Lean state.**  ``docs/CANONICAL_VNEXT_PILOT.md``
   measured **0 of 368** real Lean states mapping losslessly into ``arena-canonical-v0.1.0``
   (20.7% outright unmappable).  So a state here is a *backend-native envelope*:
   :class:`BackendStateEnvelope` carries the backend's own state identifier plus its
   pretty-printed goals, and :attr:`DerivedView.canonical_state` is typed ``None`` — not
   ``dict | None`` — because the honest value is always absent.

2. **String equality of pretty-printed states is not semantic equality.**  Measured: raw
   pretty-printed state equality scored **40.6%** where real semantic agreement was **98.1%**
   (``univ`` under ``open Finset`` vs ``Finset.univ`` without it).  A verifier comparing state
   strings would have rejected 59.4% of mathematically correct steps.  Therefore state identity
   here is the **backend's own state id**; the ``pp_sha256`` content hash exists for
   reproducibility and diffing, and is *never* an authority on whether two states are the same
   mathematics.  :meth:`BackendStateEnvelope.same_backend_state_as` compares the backend's own
   handle — kind, session, id — and never the rendered text.

3. **A chain must actually chain, inside one episode.**  ``action[i].to_state_id`` must equal
   ``action[i+1].from_state_id`` and must name the envelope the backend actually produced.  That
   alone was *not* enough and this docstring used to claim it was: Lean's state ids are
   per-session integers, so RT-02 renumbered one theorem's states into another's chain and the
   record loaded clean.  Every state must therefore also agree on backend, session, elaboration
   scope and theorem — see :meth:`VerifiedTrajectory._assert_one_episode`, which is enforced in
   ``__post_init__`` rather than documented and hoped for.

4. **Closure requires kernel evidence.**  A trajectory may not be constructed with
   ``terminal_status=CLOSED_VERIFIED`` unless it carries a ``TERMINAL_KERNEL`` evidence record
   whose verdict is ``KERNEL_VERIFIED`` and which reports no ``sorryAx``.

Nothing in this module talks to Lean; it is pure data and validation, so its tests run anywhere.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

from arena.canonical.schema import canonical_json, stable_hash

#: Schema identity of the record defined in this module.  Distinct from ``arena-canonical-v0.1.0``
#: on purpose: this schema refuses to claim a canonical form for a Lean goal.
TRAJECTORY_SCHEMA_VERSION = "arena-verified-trajectory-v0"


def content_sha256(text: str) -> str:
    """SHA-256 of a UTF-8 string.

    Used for ``pp_sha256``.  It identifies *bytes*, which is what makes a run reproducible; it
    says nothing about mathematical identity.  See the module docstring, point 2.
    """

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TerminalStatus(StrEnum):
    """How an episode ended.  ``OPEN`` is the only non-absorbing value."""

    #: Still running; more actions are legal.
    OPEN = "OPEN"
    #: Goals closed AND the completed script re-elaborated with no ``sorryAx`` in ``#print axioms``.
    CLOSED_VERIFIED = "CLOSED_VERIFIED"
    #: The backend rejected an action and the episode was not continued (typed error recorded).
    FAILED = "FAILED"
    #: Stopped by the driver or the caller for a reason that is not a backend failure
    #: (policy refusal, session lifetime cap, deliberate abort).
    ABANDONED = "ABANDONED"
    #: The step budget ran out with goals still open.
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    #: The backend process died, timed out, or produced unparseable output.
    ERROR_BACKEND = "ERROR_BACKEND"

    @property
    def is_terminal(self) -> bool:
        return self is not TerminalStatus.OPEN

    def can_transition_to(self, other: TerminalStatus) -> bool:
        """Only ``OPEN`` may change.  Every other status is absorbing.

        This is what stops a driver from quietly upgrading a ``FAILED`` episode to
        ``CLOSED_VERIFIED`` after retrying from an earlier state id (audit §7.8).
        """

        if self is TerminalStatus.OPEN:
            return True
        return other is self


#: Every status other than ``OPEN``.
TERMINAL_STATUSES = frozenset(s for s in TerminalStatus if s.is_terminal)


class Actor(StrEnum):
    """Who chose the action.  Never mix the two in one reported trajectory (audit §7.2)."""

    #: A policy under measurement chose this tactic from the observation alone.
    SOLVER = "SOLVER"
    #: The tactic came from the recorded reference proof.  Ground truth, not a solver result.
    REFERENCE = "REFERENCE"


class Verdict(StrEnum):
    """A verifier's answer about one attempt or one terminal."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    #: Refused before reaching the backend (tactic policy, ``sorry`` guard, expired session).
    REFUSED = "REFUSED"
    KERNEL_VERIFIED = "KERNEL_VERIFIED"
    KERNEL_REJECTED = "KERNEL_REJECTED"
    KERNEL_NOT_RUN = "KERNEL_NOT_RUN"


class EvidenceKind(StrEnum):
    STEP = "STEP"
    TERMINAL_KERNEL = "TERMINAL_KERNEL"


class CanonicalProjectionStatus(StrEnum):
    """Whether the state could be projected into ``arena-canonical-v0.1.0``."""

    #: Measured on real Lean states: 0/368 lossless.  This is the expected value.
    UNMAPPABLE = "UNMAPPABLE"
    #: No projection was attempted (the arena never attempts one).
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


@dataclass(frozen=True, slots=True)
class PPScope:
    """The elaboration scope a pretty-printed state was rendered under.

    Recorded because the rendering is scope-dependent: the same goal prints as ``univ`` under
    ``open Finset`` and ``Finset.univ`` without it.  Two envelopes with different ``pp`` may be
    the same mathematics; two with the same ``pp`` under different scopes may not be.
    """

    current_namespace: str = ""
    open_declarations: tuple[str, ...] = ()
    options: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_namespace": self.current_namespace,
            "open_declarations": list(self.open_declarations),
            "options": [list(pair) for pair in self.options],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        return cls(
            current_namespace=str(payload.get("current_namespace", "")),
            open_declarations=tuple(payload.get("open_declarations", ()) or ()),
            options=tuple(
                (str(pair[0]), str(pair[1])) for pair in (payload.get("options", ()) or ())
            ),
        )


@dataclass(frozen=True, slots=True)
class DerivedView:
    """Advisory decomposition of a state.  **Never** consulted by any verifier.

    ``canonical_state`` is typed ``None`` rather than ``dict | None``.  That is not an oversight:
    the pilot measured no Lean state projecting losslessly into ``arena-canonical-v0.1.0``, so a
    non-null value would be a claim this project cannot support, and the type system refuses it.
    """

    hypotheses: tuple[tuple[str, str], ...] = ()
    target: str | None = None
    canonical_state: None = None
    canonical_projection_status: CanonicalProjectionStatus = CanonicalProjectionStatus.UNMAPPABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypotheses": [list(pair) for pair in self.hypotheses],
            "target": self.target,
            "canonical_state": None,
            "canonical_projection_status": self.canonical_projection_status.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        if payload.get("canonical_state") is not None:
            raise ValueError(
                "derived.canonical_state must be null: no Lean state maps losslessly into "
                "arena-canonical-v0.1.0 (0/368 measured in docs/CANONICAL_VNEXT_PILOT.md)"
            )
        return cls(
            hypotheses=tuple(
                (str(pair[0]), str(pair[1])) for pair in (payload.get("hypotheses", ()) or ())
            ),
            target=payload.get("target"),
            canonical_state=None,
            canonical_projection_status=CanonicalProjectionStatus(
                payload.get("canonical_projection_status", "UNMAPPABLE")
            ),
        )


@dataclass(frozen=True, slots=True)
class BackendStateEnvelope:
    """One state of the inner MDP, as the formal backend itself names it.

    Identity is ``(backend_kind, session_id, state_id, pp_sha256)``:

    * ``state_id`` is the backend's own handle (for Lean it is the ``lean_dojo_repl`` ``sid``).
      It is persistent and addressable — an episode can return to an earlier ``sid`` — and it is
      the **only** thing that decides whether two envelopes are the same backend state *within
      one session*.
    * ``session_id`` says **which session** that handle belongs to.  Lean's sids are per-session
      small integers (``"0"``, ``"1"``, …), so without it a state from one session can be
      renumbered into another and nothing notices: RT-02 spliced two unrelated mathlib theorems
      into one "ten-step trajectory" by renumbering ``state_id`` alone.  It is stamped by the
      arena at ``reset()`` and is a function of what the session was opened on (the probe file,
      the tactic policy and the seed), so a byte-identical re-run reproduces it.
    * ``problem_id`` is the theorem the session was opened on.  A state may not travel into a
      trajectory that claims a different theorem.
    * ``pp_sha256`` is a content hash of the rendered goal text.  It makes a run byte-reproducible
      and makes tampering visible.  It is **not** a semantic identity: scope-dependent rendering
      means equal mathematics can hash differently (measured 40.6% vs 98.1%).

    ``session_id`` and ``problem_id`` default to ``""``.  Records written before the binding
    existed carry neither, keep their original ``content_hash`` byte-for-byte, and are checked by
    the weaker scope invariant in :meth:`VerifiedTrajectory.__post_init__` instead.
    """

    index: int
    state_id: str
    pp: str
    backend_kind: str = "LEAN4_TACTIC_STATE_PP"
    pp_scope: PPScope = PPScope()
    n_goals: int = 1
    derived: DerivedView = DerivedView()
    #: Which backend session produced this state.  ``""`` in records written before the binding.
    session_id: str = ""
    #: Which theorem that session was opened on.  ``""`` in records written before the binding.
    problem_id: str = ""

    @property
    def pp_sha256(self) -> str:
        """Content hash of the rendered goal text.  Reproducibility, not semantics."""

        return content_sha256(self.pp)

    @property
    def envelope_id(self) -> str:
        """Stable identity: backend kind, session, backend state id, goal-text content hash.

        The session segment is omitted when the state carries no session binding, so the ids of
        records written before the binding existed — and therefore their ``states_hash`` — are
        unchanged.
        """

        if self.session_id:
            return f"{self.backend_kind}:{self.session_id}:{self.state_id}:{self.pp_sha256[:32]}"
        return f"{self.backend_kind}:{self.state_id}:{self.pp_sha256[:32]}"

    def same_backend_state_as(self, other: BackendStateEnvelope) -> bool:
        """True iff the backend says these are the same saved state.

        Compares ``backend_kind``, ``session_id`` and ``state_id`` and nothing else.  It
        deliberately does not look at ``pp``: the pretty-printer is not a canonical form.  It does
        look at the session, because a Lean ``sid`` means nothing outside the session that issued
        it — that is precisely what let RT-02 renumber one theorem's states into another's.
        """

        return (
            self.backend_kind == other.backend_kind
            and self.session_id == other.session_id
            and self.state_id == other.state_id
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "state_id": self.state_id,
            "session_id": self.session_id,
            "problem_id": self.problem_id,
            "backend_native": {
                "kind": self.backend_kind,
                "pp": self.pp,
                "pp_scope": self.pp_scope.to_dict(),
                "pp_sha256": self.pp_sha256,
                "n_goals": self.n_goals,
            },
            "derived": self.derived.to_dict(),
            "envelope_id": self.envelope_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        native = payload["backend_native"]
        envelope = cls(
            index=int(payload["index"]),
            state_id=str(payload["state_id"]),
            pp=str(native["pp"]),
            backend_kind=str(native.get("kind", "LEAN4_TACTIC_STATE_PP")),
            pp_scope=PPScope.from_dict(native.get("pp_scope", {}) or {}),
            n_goals=int(native.get("n_goals", 1)),
            derived=DerivedView.from_dict(payload.get("derived", {}) or {}),
            session_id=str(payload.get("session_id", "") or ""),
            problem_id=str(payload.get("problem_id", "") or ""),
        )
        recorded = native.get("pp_sha256")
        if recorded is not None and recorded != envelope.pp_sha256:
            raise ValueError(
                f"pp_sha256 mismatch for state_id={envelope.state_id}: "
                f"recorded {recorded}, recomputed {envelope.pp_sha256}"
            )
        return envelope


@dataclass(frozen=True, slots=True)
class TrajectoryAction:
    """One attempted-and-accepted transition.  Rejected attempts live in ``verifier_evidence``."""

    index: int
    from_state_id: str
    to_state_id: str
    actor: Actor
    tactic: str
    #: LeanDojo ``traced_tactics[i].annotated_tactic`` when the action came from a reference proof.
    annotated_tactic: tuple[str, tuple[Any, ...]] | None = None
    premises_used: tuple[str, ...] = ()
    #: Trusted backend operations this action lowered to (manual sections 6.32, 13.1).
    #: One tactic is one elaborator step at V0's granularity; an action MACRO would lower to
    #: many, and reporting only the model-facing count would then hide the real cost.
    kernel_steps: int = 1
    #: Wall time.  Excluded from every content hash: it is machine load, not content.
    wall_ms: int = 0

    @property
    def tactic_head(self) -> str:
        """First whitespace-delimited token, used for allow/deny accounting and reporting."""

        stripped = self.tactic.strip()
        if not stripped:
            return ""
        head = stripped.split()[0]
        return head.rstrip(";").rstrip("[")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kernel_steps": self.kernel_steps,
            "index": self.index,
            "from_state_id": self.from_state_id,
            "to_state_id": self.to_state_id,
            "actor": self.actor.value,
            "tactic": self.tactic,
            "tactic_head": self.tactic_head,
            "premises_used": list(self.premises_used),
            "wall_ms": self.wall_ms,
        }
        if self.annotated_tactic is not None:
            payload["annotated_tactic"] = [self.annotated_tactic[0], list(self.annotated_tactic[1])]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        annotated = payload.get("annotated_tactic")
        return cls(
            index=int(payload["index"]),
            from_state_id=str(payload["from_state_id"]),
            to_state_id=str(payload["to_state_id"]),
            actor=Actor(payload["actor"]),
            tactic=str(payload["tactic"]),
            annotated_tactic=(
                (str(annotated[0]), tuple(annotated[1])) if annotated is not None else None
            ),
            premises_used=tuple(payload.get("premises_used", ()) or ()),
            wall_ms=int(payload.get("wall_ms", 0)),
        )

    def semantic_core(self) -> dict[str, Any]:
        """The part of an action that a re-run must reproduce.  Timing is excluded."""

        return {
            "index": self.index,
            "from_state_id": self.from_state_id,
            "to_state_id": self.to_state_id,
            "actor": self.actor.value,
            "tactic": self.tactic,
        }


@dataclass(frozen=True, slots=True)
class VerifierEvidence:
    """One verifier utterance.

    Every attempt belongs here, including refused and rejected ones: a driver that silently
    retries from an earlier state id after a rejection would otherwise turn a failed episode into
    a successful one (audit §7.8).
    """

    kind: EvidenceKind
    verifier: str
    verdict: Verdict
    step: int | None = None
    from_state_id: str | None = None
    to_state_id: str | None = None
    tactic: str | None = None
    backend_error: str | None = None
    rejected_reason: str | None = None
    print_axioms: str | None = None
    contains_sorry_ax: bool | None = None
    contains_of_reduce_bool: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "verifier": self.verifier,
            "verdict": self.verdict.value,
            "step": self.step,
            "from_state_id": self.from_state_id,
            "to_state_id": self.to_state_id,
            "tactic": self.tactic,
            "backend_error": self.backend_error,
            "rejected_reason": self.rejected_reason,
            "print_axioms": self.print_axioms,
            "contains_sorry_ax": self.contains_sorry_ax,
            "contains_of_reduce_bool": self.contains_of_reduce_bool,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        return cls(
            kind=EvidenceKind(payload["kind"]),
            verifier=str(payload["verifier"]),
            verdict=Verdict(payload["verdict"]),
            step=payload.get("step"),
            from_state_id=payload.get("from_state_id"),
            to_state_id=payload.get("to_state_id"),
            tactic=payload.get("tactic"),
            backend_error=payload.get("backend_error"),
            rejected_reason=payload.get("rejected_reason"),
            print_axioms=payload.get("print_axioms"),
            contains_sorry_ax=payload.get("contains_sorry_ax"),
            contains_of_reduce_bool=payload.get("contains_of_reduce_bool"),
        )


@dataclass(frozen=True, slots=True)
class FormalBackend:
    """Which proof assistant, built where, at which commit.

    ``mathlib_build_root`` is recorded verbatim because two checkouts of the same commit exist on
    the audit machine and only one is built; two prior audits reached opposite conclusions by
    confusing them.  A result that does not name its path is not reproducible.
    """

    system: str
    toolchain: str
    lean_version_string: str
    mathlib_commit: str
    mathlib_build_root: str
    repl: str = "Lean4Repl.lean :: lean_dojo_repl"
    olean_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "toolchain": self.toolchain,
            "lean_version_string": self.lean_version_string,
            "mathlib_commit": self.mathlib_commit,
            "mathlib_build_root": self.mathlib_build_root,
            "repl": self.repl,
            "olean_count": self.olean_count,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        return cls(
            system=str(payload["system"]),
            toolchain=str(payload["toolchain"]),
            lean_version_string=str(payload["lean_version_string"]),
            mathlib_commit=str(payload["mathlib_commit"]),
            mathlib_build_root=str(payload["mathlib_build_root"]),
            repl=str(payload.get("repl", "Lean4Repl.lean :: lean_dojo_repl")),
            olean_count=payload.get("olean_count"),
        )


@dataclass(frozen=True, slots=True)
class SourceVersion:
    """Where the problem statement came from.  Field names are the source's own."""

    dataset: str
    license: str
    split: str
    file_path: str
    full_name: str
    url: str = ""
    commit: str = ""
    leandojo_version: str = ""
    creation_time: str = ""
    start: tuple[int, int] | None = None
    end: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "license": self.license,
            "split": self.split,
            "file_path": self.file_path,
            "full_name": self.full_name,
            "url": self.url,
            "commit": self.commit,
            "leandojo_version": self.leandojo_version,
            "creation_time": self.creation_time,
            "start": list(self.start) if self.start is not None else None,
            "end": list(self.end) if self.end is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        start = payload.get("start")
        end = payload.get("end")
        return cls(
            dataset=str(payload["dataset"]),
            license=str(payload["license"]),
            split=str(payload["split"]),
            file_path=str(payload["file_path"]),
            full_name=str(payload["full_name"]),
            url=str(payload.get("url", "")),
            commit=str(payload.get("commit", "")),
            leandojo_version=str(payload.get("leandojo_version", "")),
            creation_time=str(payload.get("creation_time", "")),
            start=(int(start[0]), int(start[1])) if start else None,
            end=(int(end[0]), int(end[1])) if end else None,
        )


@dataclass(frozen=True, slots=True)
class TrajectoryProvenance:
    """What must travel with the number so a reader can discount it correctly."""

    trust_tier: str
    generator: str
    #: Excluded from the content hash: two identical runs differ here and are still identical runs.
    generated_utc: str = ""
    seed: int = 0
    sealed_splits_not_read: tuple[str, ...] = ()
    contamination: str = ""
    tactic_policy_id: str = ""
    tactic_budget: int = 0
    max_heartbeats: int = 0
    leakage_filters: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "trust_tier": self.trust_tier,
            "generator": self.generator,
            "generated_utc": self.generated_utc,
            "seed": self.seed,
            "sealed_splits_not_read": list(self.sealed_splits_not_read),
            "contamination": self.contamination,
            "tactic_policy_id": self.tactic_policy_id,
            "tactic_budget": self.tactic_budget,
            "max_heartbeats": self.max_heartbeats,
            "leakage_filters": list(self.leakage_filters),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Self:
        return cls(
            trust_tier=str(payload["trust_tier"]),
            generator=str(payload["generator"]),
            generated_utc=str(payload.get("generated_utc", "")),
            seed=int(payload.get("seed", 0)),
            sealed_splits_not_read=tuple(payload.get("sealed_splits_not_read", ()) or ()),
            contamination=str(payload.get("contamination", "")),
            tactic_policy_id=str(payload.get("tactic_policy_id", "")),
            tactic_budget=int(payload.get("tactic_budget", 0)),
            max_heartbeats=int(payload.get("max_heartbeats", 0)),
            leakage_filters=tuple(payload.get("leakage_filters", ()) or ()),
            notes=tuple(payload.get("notes", ()) or ()),
        )

    def semantic_core(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("generated_utc")
        return payload


@dataclass(frozen=True, slots=True)
class Horizon:
    """Horizon accounting, kept apart so the three numbers cannot be confused.

    ``achieved``
        Number of state-advancing actions in this episode.  This is *the* horizon.
    ``verified``
        ``achieved`` if the episode closed with kernel evidence, otherwise ``0``.  Reporting a
        horizon for an episode that never closed is the commonest way to inflate one.
    ``reference``
        Length of the recorded reference proof.  A difficulty proxy for sampling.  **Never the
        model's horizon** — a solver may close a 20-tactic proof in one ``aesop``.
    """

    achieved: int
    verified: int
    reference: int
    solver_actions: int
    reference_actions: int
    kernel_step_count: int = 0

    def __int__(self) -> int:
        return self.achieved

    @property
    def episode_length(self) -> int:
        """Manual section 6.31: model-facing decisions in an actual interactive run."""

        return self.achieved

    @property
    def observed_trace_length(self) -> int:
        """Manual section 6.30: transitions in one stored demonstration.

        Explicitly NOT the reasoning difficulty of the task (manual correction 4).
        """

        return self.reference

    @property
    def minimal_proof_length(self) -> str:
        """Manual section 6.34: ``UNKNOWN`` unless independently established.

        It never has been here, and nothing in this arena could establish it: a shorter proof may
        always exist. Returning the literal string keeps the manual's prohibition mechanical --
        a reader cannot mistake a 14-tactic replay for a "14-step required reasoning task"
        (manual section 17.6), because the field that would license that claim says UNKNOWN.
        """

        return "UNKNOWN"

    @property
    def dependency_depth(self) -> str:
        """Manual section 6.33: task-family-specific structural measure. Not defined for Lean here."""

        return "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "achieved": self.achieved,
            "verified": self.verified,
            "reference": self.reference,
            "solver_actions": self.solver_actions,
            "reference_actions": self.reference_actions,
            # Manual sections 6.30-6.34 / 17.6: these four names are mandatory and must stay
            # distinct.  KernelStepCount is the post-lowering cost (section 6.32, 13.1) so a
            # macro that bundles many kernel operations cannot look cheap.
            "episode_length": self.episode_length,
            "observed_trace_length": self.observed_trace_length,
            "kernel_step_count": self.kernel_step_count,
            "dependency_depth": self.dependency_depth,
            "minimal_proof_length": self.minimal_proof_length,
        }


class TrajectoryIntegrityError(ValueError):
    """Raised when a record would misrepresent what actually happened."""


@dataclass(frozen=True, slots=True)
class VerifiedTrajectory:
    """A sequence of backend-verified transitions over one persistent state.

    Constructing one asserts, mechanically:

    * ``len(states) == len(actions) + 1``, indices sequential from zero;
    * every action's endpoints name the adjacent envelopes' backend state ids;
    * every state belongs to **one** episode: one ``backend_kind``, one ``session_id``, one
      ``pp_scope``, and one ``problem_id`` which must be the trajectory's own;
    * ``CLOSED_VERIFIED`` carries ``TERMINAL_KERNEL`` evidence with ``contains_sorry_ax=False``.

    The endpoint chaining alone was **not** enough, and the docstring that said it was is the
    defect RT-02 exploited: Lean's ``sid``s are per-session small integers, so a red team spliced
    the states and actions of ``MvPolynomial.IsHomogeneous.rename_isHomogeneous_iff`` onto
    ``MeasureTheory.weightedSMul_add_measure``, renumbered ``index`` and ``state_id``, and got a
    record claiming ``{"achieved": 10, "verified": 10}`` that loaded clean.  The episode
    invariants above are what refuse it now, and they refuse it **without** Lean.

    What they do *not* refuse: two episodes of the *same* theorem under the same policy and seed
    share a ``session_id``, and two theorems that happen to be declared in byte-identical scopes
    are indistinguishable to a record that carries no binding at all (everything written before
    this fix).  Splicing those is caught by ``verify_bank(relive=True)``, which re-executes the
    stored actions, and by nothing cheaper.

    Re-entering an earlier state of the same session (legitimate search: ``arena.branch``) stays
    legal — repeated ``state_id``s are never refused, only ids from a *different* session are.
    """

    trajectory_id: str
    problem_id: str
    formal_backend: FormalBackend
    source_version: SourceVersion
    states: tuple[BackendStateEnvelope, ...]
    actions: tuple[TrajectoryAction, ...]
    verifier_evidence: tuple[VerifierEvidence, ...]
    terminal_status: TerminalStatus
    provenance: TrajectoryProvenance
    reference_horizon: int = 0
    schema_version: str = TRAJECTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.states:
            raise TrajectoryIntegrityError("a trajectory needs at least the initial state")
        if len(self.states) != len(self.actions) + 1:
            raise TrajectoryIntegrityError(
                f"len(states)={len(self.states)} must equal len(actions)+1={len(self.actions) + 1}"
            )
        for position, state in enumerate(self.states):
            if state.index != position:
                raise TrajectoryIntegrityError(
                    f"state at position {position} declares index {state.index}"
                )
        for position, action in enumerate(self.actions):
            if action.index != position:
                raise TrajectoryIntegrityError(
                    f"action at position {position} declares index {action.index}"
                )
            if action.from_state_id != self.states[position].state_id:
                raise TrajectoryIntegrityError(
                    f"action {position} starts at state_id {action.from_state_id!r} but the "
                    f"trajectory's state {position} is {self.states[position].state_id!r}: "
                    "the chain is broken"
                )
            if action.to_state_id != self.states[position + 1].state_id:
                raise TrajectoryIntegrityError(
                    f"action {position} ends at state_id {action.to_state_id!r} but the "
                    f"trajectory's state {position + 1} is "
                    f"{self.states[position + 1].state_id!r}: the chain is broken"
                )
        self._assert_one_episode()
        if self.terminal_status is TerminalStatus.CLOSED_VERIFIED and not self.kernel_verified:
            raise TrajectoryIntegrityError(
                "CLOSED_VERIFIED requires a TERMINAL_KERNEL evidence record with verdict "
                "KERNEL_VERIFIED and contains_sorry_ax=False"
            )

    def _assert_one_episode(self) -> None:
        """RT-02: every state must come from the same session, on this trajectory's theorem.

        Four separate claims, each raising with the index of the first state that breaks it:

        1. one backend;
        2. one session — Lean ``sid``s are per-session integers, so this is the check that stops
           a state from another session being renumbered into this chain;
        3. one elaboration scope — a session runs inside one file's namespace and ``open``s, so
           two states rendered under different scopes were produced by two different sessions.
           This is the only one of the four that legacy records (which carry no session binding)
           can be checked by, and it is what catches the published RT-02 splice;
        4. one theorem, and it is the theorem this record claims.

        Repeated ``state_id``s are deliberately *not* refused: re-entering an earlier state of the
        same session is legitimate search (``arena.branch``), and a uniqueness rule would forbid
        it while catching nothing a session check does not already catch.
        """

        anchor = self.states[0]
        for position, state in enumerate(self.states[1:], start=1):
            if state.backend_kind != anchor.backend_kind:
                raise TrajectoryIntegrityError(
                    f"state {position} was produced by backend {state.backend_kind!r} but state 0 "
                    f"by {anchor.backend_kind!r}: one trajectory is one backend session"
                )
            if state.session_id != anchor.session_id:
                raise TrajectoryIntegrityError(
                    f"state {position} carries session id {state.session_id!r} but the "
                    f"trajectory's session is {anchor.session_id!r}: states from two sessions "
                    "cannot be spliced into one trajectory"
                )
            if state.pp_scope != anchor.pp_scope:
                raise TrajectoryIntegrityError(
                    f"state {position} was rendered under a different elaboration scope than "
                    f"state 0 ({canonical_json(state.pp_scope.to_dict())[:200]} vs "
                    f"{canonical_json(anchor.pp_scope.to_dict())[:200]}): one episode runs in one "
                    "file scope, so these two states are from two different theorems"
                )
            if state.problem_id != anchor.problem_id:
                raise TrajectoryIntegrityError(
                    f"state {position} was produced on theorem {state.problem_id!r} but state 0 "
                    f"on {anchor.problem_id!r}: states from two theorems cannot be spliced into "
                    "one trajectory"
                )
        if anchor.problem_id and anchor.problem_id != self.problem_id:
            raise TrajectoryIntegrityError(
                f"state 0 was produced on theorem {anchor.problem_id!r} but the trajectory claims "
                f"{self.problem_id!r}"
            )

    # -- accessors -----------------------------------------------------------------

    @property
    def horizon(self) -> Horizon:
        """The :class:`Horizon` accessor.  Derived, never stored, so it cannot drift."""

        achieved = len(self.actions)
        solver = sum(1 for action in self.actions if action.actor is Actor.SOLVER)
        # RT-14: KernelStepCount must be ASSIGNED, not left at its default.  Manual sections 6.32
        # and 13.1 require cost to be accounted AFTER lowering, so that bundling many kernel
        # operations into one model-facing action cannot look cheap.  At V0's granularity one
        # action lowers to exactly one elaborator step, so the two coincide -- but they are
        # computed separately here, because the moment an action macro lands they must diverge.
        kernel_steps = sum(action.kernel_steps for action in self.actions)
        return Horizon(
            achieved=achieved,
            verified=achieved if self.terminal_status is TerminalStatus.CLOSED_VERIFIED else 0,
            reference=self.reference_horizon,
            solver_actions=solver,
            reference_actions=achieved - solver,
            kernel_step_count=kernel_steps,
        )

    @property
    def kernel_verified(self) -> bool:
        """True iff a kernel record says the finished declaration is ``sorryAx``-free."""

        return any(
            evidence.kind is EvidenceKind.TERMINAL_KERNEL
            and evidence.verdict is Verdict.KERNEL_VERIFIED
            and evidence.contains_sorry_ax is False
            for evidence in self.verifier_evidence
        )

    @property
    def actors(self) -> frozenset[Actor]:
        return frozenset(action.actor for action in self.actions)

    @property
    def is_single_actor(self) -> bool:
        """A trajectory mixing SOLVER and REFERENCE actions is not a solver result."""

        return len(self.actors) <= 1

    def require_single_actor(self, actor: Actor) -> None:
        if self.actors - {actor}:
            raise TrajectoryIntegrityError(
                f"trajectory {self.trajectory_id} contains actions by "
                f"{sorted(a.value for a in self.actors)}; it cannot be reported as a "
                f"{actor.value} result"
            )

    def tactic_head_counts(self) -> dict[str, int]:
        """How often each tactic family was used — the automation-confound report (audit §7.4)."""

        counts: dict[str, int] = {}
        for action in self.actions:
            counts[action.tactic_head] = counts.get(action.tactic_head, 0) + 1
        return dict(sorted(counts.items()))

    # -- hashing and serialization -------------------------------------------------

    def semantic_core(self) -> dict[str, Any]:
        """Everything a re-run must reproduce; wall-clock timings and stamps excluded."""

        return {
            "schema_version": self.schema_version,
            "problem_id": self.problem_id,
            "formal_backend": self.formal_backend.to_dict(),
            "source_version": self.source_version.to_dict(),
            "states": [
                {
                    "index": state.index,
                    "state_id": state.state_id,
                    "backend_kind": state.backend_kind,
                    "pp_sha256": state.pp_sha256,
                    "n_goals": state.n_goals,
                    # The session binding is part of the content — a state is only meaningful in
                    # the session that issued its id.  It is written only when the producing
                    # arena stamped one, so records made before the binding existed keep their
                    # original content_hash byte-for-byte: an absent field is an absent claim.
                    **({"session_id": state.session_id} if state.session_id else {}),
                    **({"problem_id": state.problem_id} if state.problem_id else {}),
                }
                for state in self.states
            ],
            "actions": [action.semantic_core() for action in self.actions],
            "terminal_status": self.terminal_status.value,
            "reference_horizon": self.reference_horizon,
            "provenance": self.provenance.semantic_core(),
        }

    @property
    def content_hash(self) -> str:
        return stable_hash(self.semantic_core())

    @property
    def states_hash(self) -> str:
        return stable_hash([state.envelope_id for state in self.states])

    @property
    def actions_hash(self) -> str:
        return stable_hash([action.semantic_core() for action in self.actions])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema_version,
            "trajectory_id": self.trajectory_id,
            "problem_id": self.problem_id,
            "formal_backend": self.formal_backend.to_dict(),
            "source_version": self.source_version.to_dict(),
            "states": [state.to_dict() for state in self.states],
            "actions": [action.to_dict() for action in self.actions],
            "verifier_evidence": [item.to_dict() for item in self.verifier_evidence],
            "terminal_status": self.terminal_status.value,
            "horizon": self.horizon.to_dict(),
            "reference_horizon": self.reference_horizon,
            "provenance": self.provenance.to_dict(),
            "content_hash": self.content_hash,
            "states_hash": self.states_hash,
            "actions_hash": self.actions_hash,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, check_hashes: bool = True) -> Self:
        trajectory = cls(
            trajectory_id=str(payload["trajectory_id"]),
            problem_id=str(payload["problem_id"]),
            formal_backend=FormalBackend.from_dict(payload["formal_backend"]),
            source_version=SourceVersion.from_dict(payload["source_version"]),
            states=tuple(BackendStateEnvelope.from_dict(item) for item in payload["states"]),
            actions=tuple(TrajectoryAction.from_dict(item) for item in payload["actions"]),
            verifier_evidence=tuple(
                VerifierEvidence.from_dict(item) for item in payload.get("verifier_evidence", ())
            ),
            terminal_status=TerminalStatus(payload["terminal_status"]),
            provenance=TrajectoryProvenance.from_dict(payload["provenance"]),
            reference_horizon=int(payload.get("reference_horizon", 0)),
            schema_version=str(payload.get("schema", TRAJECTORY_SCHEMA_VERSION)),
        )
        recorded = payload.get("content_hash")
        if check_hashes and recorded is not None and recorded != trajectory.content_hash:
            raise TrajectoryIntegrityError(
                f"content_hash mismatch for {trajectory.trajectory_id}: "
                f"recorded {recorded}, recomputed {trajectory.content_hash}"
            )
        return trajectory


def derive_trajectory_id(problem_id: str, content_hash: str) -> str:
    """Deterministic id: the same episode re-run byte-identically gets the same id."""

    digest = hashlib.sha256(f"{problem_id}|{content_hash}".encode()).hexdigest()
    return f"vt-{digest[:24]}"
