"""HC-V0.5: drive a real Solver through a real :class:`VerifiedTask`.

This is the module that finally puts a **player** inside the mathematical world.  Everything it
needs already existed separately -- an interactive task (:mod:`arena.trajectory.task`), a live
Lean backend (:mod:`arena.trajectory.lean_backend`) and a real Solver
(:mod:`arena.trajectory.solver`) -- and none of them had ever been connected.  Before this, every
action in the project's trajectory bank carried ``actor=REFERENCE``: the bank replayed mathlib's
own proofs and no policy had ever chosen a move.

What this module does NOT do, stated up front because the distinction is the whole point:

* it never reads the reference proof.  :class:`~arena.trajectory.task.VerifiedTask` seals it and
  raises if it is present, so the runner *cannot* fall back to the recorded tactic when the
  Solver fails.  A failed episode stays failed.
* it never repairs, re-prompts around, or silently retries a malformed proposal.  A parse failure
  is a recorded outcome.
* it never claims autonomy it cannot substantiate.  Every action is stepped with an
  :class:`~arena.trajectory.schema.ActionEvidence` binding it to the Solver identity that served
  the call, the prompt bytes it was given, the decoding parameters in force, and the exact
  projection the task handed out; the task refuses an action whose observation digest does not
  match, and the emitted trajectory carries the binding inside its ``content_hash``.  This is
  V05-01's fix and it is worth being exact about its reach: it **cannot cryptographically prove
  a black-box model emitted a token**.  It binds the action to a specific policy identity and a
  specific observed state, makes the binding re-derivable by a reader, and makes an evidence-free
  ``SOLVER`` claim structurally impossible.
* it makes no scientific claim.  The result is an ``ENGINEERING_SMOKE``: one fixed baseline
  renderer, one Solver, no representation comparison, no language ranking.

The honest framing for anything measured here is **long-horizon execution under kernel
verification**, never "reasoning" or "discovery": mathlib4 is ``HISTORICALLY_EXPOSED`` and
exposure is transitive, so nothing here separates a solved goal from a recalled one.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash
from arena.storage.artifacts import ArtifactStore
from arena.trajectory.schema import ActionEvidence
from arena.trajectory.solver import ProposalStatus, Solver, TacticProposal
from arena.trajectory.state_identity import WorkspaceProjection
from arena.trajectory.task import ActionResult, VerifiedTask, observation_digest_of

EPISODE_RUNNER_VERSION = "arena-hc-v0.5-episode-runner-v1"
RUN_MODE_SMOKE = "ENGINEERING_SMOKE"

#: Fields excluded from the deterministic result hash: they vary run to run without changing
#: what happened mathematically (directive section 28).
#:
#: ``wall_ms`` was missing here and it mattered.  Four runs of the identical six-task
#: configuration on 2026-09-09 produced four different ``result_hash`` values while every prompt,
#: every proposed tactic and every Lean verdict was identical -- and HC-V0.5 read that difference
#: as "the runtime is not reproducible".  It was reading machine load: ``TrajectoryAction`` carries
#: ``wall_ms``, whose own docstring says it is "excluded from every content hash", and this set was
#: the one place that failed to exclude it.
#:
#: ``completion_tokens`` is deliberately NOT excluded.  It genuinely differed once in 13 calls for
#: an identical prompt and an identical parsed tactic, so the response bytes really did differ.
#: That is a fact about the runtime and the hash should keep reporting it.
NON_DETERMINISTIC_FIELDS = frozenset({"wall_clock_s", "latency_ms", "generated_utc", "wall_ms"})


@dataclass(frozen=True, slots=True)
class SolverObservation:
    """Adapter satisfying :class:`~arena.trajectory.solver.RenderedObservation`.

    The task speaks ``WorkspaceProjection``; the Solver speaks a structural protocol.  This is the
    seam, and it deliberately forwards **only** the projection's rendered mapping -- the Solver
    never sees the task, its provenance, or its reference seal.
    """

    step_index: int
    state_id: str
    rendered: Mapping[str, Any]


@dataclass(slots=True)
class EpisodeStep:
    index: int
    proposal_status: str
    tactic: str | None
    action_result: str | None
    terminal_status: str | None
    diagnostic: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    state_id: str
    prompt_sha256: str
    #: The V05-01 binding actually played, or ``""`` when the step never reached the task.
    provenance_digest: str = ""
    #: Digest of the projection this proposal was produced from, as the task itself computed it.
    observation_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "proposal_status": self.proposal_status,
            "tactic": self.tactic,
            "action_result": self.action_result,
            "terminal_status": self.terminal_status,
            "diagnostic": self.diagnostic[:400],
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "latency_ms": self.latency_ms,
            "state_id": self.state_id,
            "prompt_sha256": self.prompt_sha256,
            "provenance_digest": self.provenance_digest,
            "observation_digest": self.observation_digest,
        }


@dataclass(slots=True)
class EpisodeResult:
    """One autonomous episode.  ``actor`` is *read back* from the emitted trajectory, not asserted."""

    task_id: str
    problem_id: str
    terminal_status: str
    terminal_outcome: str
    steps: list[EpisodeStep] = field(default_factory=list)
    error: str = ""
    wall_clock_s: float = 0.0
    #: The re-verifiable artefact.  Without it an episode is an unauditable claim (V05-24).
    trajectory: dict[str, Any] | None = None
    emit_error: str = ""

    @property
    def accepted(self) -> int:
        return sum(1 for s in self.steps if s.action_result == ActionResult.ACCEPTED_TRANSITION)

    @property
    def rejected(self) -> int:
        return sum(1 for s in self.steps if s.action_result == ActionResult.REJECTED_INVALID_ACTION)

    @property
    def parse_failures(self) -> int:
        return sum(1 for s in self.steps if s.proposal_status != ProposalStatus.OK)

    @property
    def solved(self) -> bool:
        return self.terminal_status == "CLOSED_VERIFIED"

    @property
    def actor(self) -> str:
        """Who the *emitted record* says chose the actions — read, never asserted (V05-03).

        This used to be the string literal ``"SOLVER"`` in :meth:`to_dict`, which is precisely
        the defect: the summary asserted autonomy that nothing in it could support.  It is now
        read back out of the trajectory the arena actually emitted, and an episode that emitted
        nothing says so instead of claiming a Solver.
        """

        if not self.trajectory:
            return "NOT_EMITTED"
        actors = sorted({str(a.get("actor", "")) for a in self.trajectory.get("actions", ())})
        if not actors:
            return "NO_ACTIONS"
        return "+".join(actors)

    @property
    def steps_with_provenance(self) -> int:
        """Proposals carrying a V05-01 binding to a policy identity and an observed state."""

        return sum(1 for s in self.steps if s.provenance_digest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "problem_id": self.problem_id,
            "terminal_status": self.terminal_status,
            "terminal_outcome": self.terminal_outcome,
            "actor": self.actor,
            "steps_with_provenance": self.steps_with_provenance,
            "accepted_transitions": self.accepted,
            "rejected_actions": self.rejected,
            "parse_failures": self.parse_failures,
            "solved": self.solved,
            "steps": [s.to_dict() for s in self.steps],
            "error": self.error,
            "emit_error": self.emit_error,
            "trajectory": self.trajectory,
            "trajectory_emitted": self.trajectory is not None,
            "wall_clock_s": round(self.wall_clock_s, 3),
        }


def action_evidence_for(
    proposal: TacticProposal, projection: WorkspaceProjection, solver: Solver
) -> ActionEvidence:
    """Bind one proposal to the policy that produced it and to the state it was produced from.

    ``projection`` must be the one the task handed out immediately before ``proposal`` was asked
    for; :meth:`VerifiedTask.step` re-derives its digest and refuses the action if it disagrees,
    which is what makes this a binding rather than a label.

    ``policy_digest`` comes from the *proposal*, not from ``solver.identity`` read a second time:
    it is the identity that actually served the call.  ``decoding_digest`` is taken from the
    solver's frozen decoding options, so a temperature or seed change produces a different
    binding instead of an invisible one.

    See :class:`~arena.trajectory.schema.ActionEvidence` for what this establishes and — more
    importantly — what it cannot: it does not prove a black-box model emitted these tokens.
    """

    return ActionEvidence(
        policy_digest=proposal.solver_digest or solver.identity.digest,
        prompt_sha256=proposal.prompt_sha256,
        observation_digest=observation_digest_of(projection),
        decoding_digest=stable_hash(dict(solver.identity.decoding_options())),
    )


def run_episode(task: VerifiedTask, solver: Solver, *, max_steps: int = 8) -> EpisodeResult:
    """Play one task to termination.  Every action comes from ``solver``; none from the source.

    Every action is stepped with :func:`action_evidence_for`, so the episode's emitted trajectory
    carries a per-action ``provenance_digest`` inside its ``content_hash``.  A runner that skipped
    this would find ``emit_trajectory()`` refusing the ``SOLVER`` claim rather than producing an
    artefact indistinguishable from a replay (V05-01).
    """

    started = time.monotonic()
    result = EpisodeResult(
        task_id=task.problem_id,
        problem_id=task.problem_id,
        terminal_status="OPEN",
        terminal_outcome="OPEN",
    )
    try:
        with task as active:
            projection = active.reset()
            index = 0
            while not active.is_terminal() and index < max_steps:
                # V05-11: the projection's own identity is authoritative; the rendered mapping
                # is renderer-dependent and a missing key must not silently become "?".
                identity = active.state_identity()
                state_id = str(
                    getattr(identity, "state_id", None)
                    or projection.rendered.get("backend_state_id")
                    or "UNKNOWN_STATE_ID"
                )
                observation = SolverObservation(
                    step_index=index, state_id=state_id, rendered=projection.rendered
                )
                proposal: TacticProposal = solver.propose(observation)
                # V05-01: bound to *this* projection, before the tactic is played.  The task
                # re-derives the digest and refuses anything produced from another state.
                evidence = action_evidence_for(proposal, projection, solver)
                step = EpisodeStep(
                    index=index,
                    proposal_status=str(proposal.status),
                    tactic=proposal.tactic,
                    action_result=None,
                    terminal_status=None,
                    diagnostic="",
                    prompt_tokens=proposal.prompt_tokens,
                    completion_tokens=proposal.completion_tokens,
                    latency_ms=proposal.latency_ms,
                    state_id=observation.state_id,
                    prompt_sha256=proposal.prompt_sha256,
                    provenance_digest=evidence.provenance_digest,
                    observation_digest=evidence.observation_digest,
                )
                if proposal.status is not ProposalStatus.OK or not proposal.tactic:
                    # A malformed proposal is an outcome, never a reason to consult the source.
                    step.diagnostic = str(proposal.failure_detail or "")
                    result.steps.append(step)
                    break
                outcome = active.step(proposal.tactic, evidence=evidence)
                step.action_result = str(outcome.result)
                step.terminal_status = str(outcome.terminal_status)
                step.diagnostic = str(outcome.diagnostic or "")
                result.steps.append(step)
                if active.is_terminal():
                    break
                projection = (
                    outcome.observation if outcome.observation is not None else active.observe()
                )
                index += 1
            result.terminal_status = str(active.terminal_status())
            result.terminal_outcome = str(active.terminal_outcome())
            # V05-24: emit INSIDE the context manager.  Leaving the `with` closes the task and
            # `emit_trajectory()` then raises, which is how the first run produced episode
            # summaries with no states, no `pp_sha256` and no kernel receipt -- nothing an audit
            # could re-verify.  A summary is a claim; the trajectory is the evidence.
            try:
                result.trajectory = active.emit_trajectory().to_dict()
            except Exception as error:  # pragma: no cover - emission is best-effort
                result.emit_error = f"{type(error).__name__}: {error}"[:200]
    except Exception as error:  # pragma: no cover - live backend
        result.error = f"{type(error).__name__}: {error}"[:300]
        result.terminal_status = result.terminal_status or "ENVIRONMENT_ERROR"
    result.wall_clock_s = time.monotonic() - started
    return result


def summarise(episodes: Sequence[EpisodeResult]) -> dict[str, Any]:
    return {
        "episodes": len(episodes),
        "solved": sum(1 for e in episodes if e.solved),
        "episodes_with_an_accepted_solver_transition": sum(1 for e in episodes if e.accepted),
        "accepted_solver_transitions": sum(e.accepted for e in episodes),
        "rejected_actions": sum(e.rejected for e in episodes),
        "parse_failures": sum(e.parse_failures for e in episodes),
        "environment_errors": sum(
            1 for e in episodes if e.error or e.terminal_status == "ERROR_BACKEND"
        ),
        "max_accepted_in_one_episode": max((e.accepted for e in episodes), default=0),
    }


def build_manifest(
    episodes: Sequence[EpisodeResult], *, solver: Solver, selection: Any, mode: str = RUN_MODE_SMOKE
) -> dict[str, Any]:
    """The deterministic machine-readable record (directive section 28).

    ``result_hash`` deliberately excludes wall-clock and latency so two runs of the same
    configuration hash identically when the mathematics did.
    """

    identity = solver.identity
    # V05-02: the recorded digest was a module constant that nothing checked.  It happened to be
    # correct, which is exactly why it went unnoticed.  Verify against the live runtime and store
    # the SERVED identity; a mismatch must be loud, not silent.
    # `verify_served` is on the concrete adapter, not the Solver protocol (a ScriptedSolver has
    # no live runtime to verify against), so it is probed rather than assumed.
    served_note = ""
    verify = getattr(solver, "verify_served", None)
    if callable(verify):
        try:
            identity = verify()
        except Exception as error:
            served_note = f"{type(error).__name__}: {error}"[:200]
    else:
        served_note = "SOLVER_HAS_NO_LIVE_RUNTIME_TO_VERIFY"
    # V05-10: `getattr(selection, "to_dict", lambda: {})()` silently produced `{}`.  Try the real
    # accessors and record which one answered rather than defaulting to empty.
    selection_block: dict[str, Any] = {}
    for accessor in ("manifest", "to_dict"):
        method = getattr(selection, accessor, None)
        if callable(method):
            try:
                candidate = method()
            except Exception:  # pragma: no cover
                continue
            if candidate:
                selection_block = dict(candidate)
                selection_block["_accessor"] = accessor
                break
    payload: dict[str, Any] = {
        "schema": EPISODE_RUNNER_VERSION,
        "run_mode": mode,
        "scientific_status": "ENGINEERING_SMOKE_NOT_A_RESULT",
        "contamination": (
            "mathlib4 is HISTORICALLY_EXPOSED and exposure is transitive. This records "
            "long-horizon EXECUTION UNDER KERNEL VERIFICATION, not reasoning or discovery."
        ),
        "solver": identity.to_dict() if hasattr(identity, "to_dict") else str(identity),
        "solver_served_verification": served_note or "VERIFIED_AGAINST_LIVE_RUNTIME",
        "selection": selection_block,
        "summary": summarise(episodes),
        "episodes": [e.to_dict() for e in episodes],
    }
    payload["result_hash"] = _deterministic_hash(payload)
    return payload


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in NON_DETERMINISTIC_FIELDS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _deterministic_hash(payload: Mapping[str, Any]) -> str:
    return stable_hash(_strip(dict(payload)))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=10)
    parser.add_argument("--min-reference-length", type=int, default=1)
    parser.add_argument("--max-reference-length", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--scan-limit", type=int, default=12000)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--out", default="trajectory/hc_v0_5_smoke.json")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--live", action="store_true", help="required: this makes real model calls")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; this runner makes real Solver calls")

    from arena.trajectory.solver import OllamaTacticSolver
    from arena.trajectory.task import select_verified_tasks

    selection = select_verified_tasks(
        limit=args.tasks,
        min_reference_length=args.min_reference_length,
        max_reference_length=args.max_reference_length,
        seed=args.seed,
        scan_limit=args.scan_limit,
    )
    solver = OllamaTacticSolver()
    episodes = [run_episode(task, solver, max_steps=args.max_steps) for task in selection.tasks]
    manifest = build_manifest(episodes, solver=solver, selection=selection)
    ArtifactStore(Path(args.root) / "artifacts").write_json(args.out, manifest)
    print(json.dumps({**manifest["summary"], "result_hash": manifest["result_hash"]}, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
