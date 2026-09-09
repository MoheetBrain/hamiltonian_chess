"""HC-V0.6: play four renderings of the *same* anchored Lean state and record what Lean says.

This is the runner that produces the first Δ(R_A,R_B).  Its whole job is to hold everything fixed
except the bytes the Solver reads, and the design that makes that true is not statistical -- it is
mechanical:

* **One truth state per anchor, shared by every arm.**  All arms are stepped from the *same* live
  ``state_id`` in the *same* Lean session, by branching (`research/phase10/branching/README.md`
  measures that two successful steps from one parent give distinct children and leave the parent
  intact).  The arms cannot have seen different mathematics.
* **Arm order is randomised within each anchor**, from a recorded seed.  HC-V0.5 observed that a
  prompt's answer *might* depend on what else had passed through the server process; randomising
  converts any such position effect into noise the paired design already absorbs rather than a
  confound aligned with the arm.
* **The intervention class is derived, never passed in.**  ``project_arm`` computes it from the
  arm's own declaration against the baseline's at that state, so ``R_ABLATED`` cannot be recorded
  as a representation change even by mistake.
* **The oracle is fenced off at runtime.**  Every rendered payload is scanned for the theorem's own
  recorded tactics before it can become a prompt.  The bank already segregates them; this is the
  second check, on the exact bytes the model sees (the audit's F5).

What this runner does NOT do: it never reads the reference proof to *play*, it never retries a
rejected tactic, and it makes no claim.  One action per cell, kernel-decided.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash
from arena.evolution.record import InterventionClass
from arena.experiments.hc_v0_6.schema import Arm, CellOutcome, CellTable, ParseStatus, StepResult
from arena.storage.artifacts import ArtifactStore
from arena.trajectory.anchor import (
    Anchor,
    AnchorBank,
    LiveAnchorSet,
    open_anchor_session,
)
from arena.trajectory.arena_v0 import normalise_backend_diagnostic
from arena.trajectory.episode import SolverObservation
from arena.trajectory.lean_backend import StepOutcome
from arena.trajectory.representation import ARMS, project_arm
from arena.trajectory.solver import ProposalStatus, Solver, TacticProposal
from arena.trajectory.state_identity import GOAL_TEXT_NORMALIZATION, normalize_goal_text

ASSAY_VERSION = "arena-hc-v0.6-anchored-delta-assay-v1"

#: Keys excluded from the deterministic result hash: they vary run to run without changing what
#: happened mathematically.  ``cost`` is excluded whole -- every value in it is machine load, and
#: an earlier version listed the timing fields individually and silently missed three of them.
NON_DETERMINISTIC_FIELDS = frozenset(
    {
        "cost",
        "generated_utc",
        "lean_seconds",
        "latency_ms",
        "seconds_per_solver_call",
        "solver_seconds",
        "wall_clock_s",
    }
)

#: Lean's own step outcomes, mapped onto the analysis vocabulary.  ``POLICY_REJECTED`` and
#: ``SORRY_REFUSED`` are **Solver** failures, not harness failures: the policy refused an action the
#: Solver chose, and pretending otherwise would quietly delete the cheapest way to fake a proof.
_OUTCOME_TO_RESULT: Mapping[str, StepResult] = {
    StepOutcome.OK.value: StepResult.ACCEPTED_TRANSITION,
    StepOutcome.TACTIC_ERROR.value: StepResult.REJECTED_INVALID_ACTION,
    StepOutcome.POLICY_REJECTED.value: StepResult.UNSUPPORTED,
    StepOutcome.SORRY_REFUSED.value: StepResult.UNSUPPORTED,
    StepOutcome.TIMEOUT.value: StepResult.TOOL_TIMEOUT,
    StepOutcome.BACKEND_DEAD.value: StepResult.ENVIRONMENT_ERROR,
    StepOutcome.SESSION_EXPIRED.value: StepResult.ENVIRONMENT_ERROR,
    StepOutcome.UNKNOWN_STATE_ID.value: StepResult.ENVIRONMENT_ERROR,
}


def changed_the_declared_state(before: str, after: str | None) -> bool:
    """Did the action move the mathematics, or merely survive the elaborator?

    The primary endpoint is ``KERNEL_ACCEPTED_STATE_CHANGE``: acceptance alone is not progress.
    ``skip`` is accepted by Lean at every open goal, so an endpoint that counted acceptance would
    be maximised by a policy that never attempts mathematics -- and HC-V0.5's own branching probe
    used exactly that property of ``skip``, so this is a demonstrated hole, not a hypothetical one.

    "The state changed" is decided by the project's own declared state identity: the normalised
    goal text under a fixed elaboration scope, which is what
    :attr:`~arena.trajectory.state_identity.KernelStateIdentity.reelaboration_key` is built from
    and what the anchor bank re-derives against.  This is NOT string equality standing in for
    semantic equality -- it never decides whether a proof is correct, only whether the declared
    workspace the Solver is shown is the same one it was shown a moment ago.
    """

    if after is None:
        return False
    return normalize_goal_text(after) != normalize_goal_text(before)


_PROPOSAL_TO_PARSE: Mapping[str, ParseStatus] = {
    ProposalStatus.OK.value: ParseStatus.OK,
    ProposalStatus.PARSE_FAILURE.value: ParseStatus.PARSE_FAILURE,
    ProposalStatus.TRUNCATED.value: ParseStatus.TRUNCATED,
    ProposalStatus.PROMPT_OVER_BUDGET.value: ParseStatus.PROMPT_OVER_BUDGET,
    ProposalStatus.TRANSPORT_FAILURE.value: ParseStatus.TRANSPORT_FAILURE,
}


class OracleLeakInPrompt(RuntimeError):
    """A rendered payload contained one of the theorem's own recorded tactics.

    Raised, never counted: a single leaked prompt invalidates the cell it produced *and* every
    conclusion drawn beside it, so the run stops rather than annotating itself.
    """


def assert_prompt_is_oracle_free(rendered: Mapping[str, Any], anchor: Anchor) -> None:
    """Scan the exact bytes the model will read for the theorem's recorded tactics.

    The bank already segregates ``oracle`` from ``solver_visible`` and checks the latter.  This is
    the same check one level later, on the *rendered* payload -- the surface manual §29 actually
    names.  A renderer that derived something from the state could in principle surface a recorded
    tactic that the raw goal text did not contain; nothing in the current arms can, and this is how
    that stays true rather than being assumed.
    """

    payload = json.dumps(dict(rendered), ensure_ascii=False)
    for tactic in anchor.oracle.reference_tactics:
        needle = tactic.strip()
        if len(needle) >= 6 and needle in payload:
            raise OracleLeakInPrompt(
                f"{anchor.anchor_id}: the rendered payload contains the recorded tactic "
                f"{needle[:60]!r}; this prompt may not be sent"
            )


@dataclass(frozen=True, slots=True)
class CellPlan:
    """One scheduled call: which arm, which replicate.  Order is decided before any call is made."""

    arm: Arm
    replicate_index: int


def plan_cells(
    arms: Sequence[Arm], *, replicates: int, seed: int, anchor_id: str
) -> list[CellPlan]:
    """The randomised within-anchor order.  A pure function of ``(seed, anchor_id)``.

    Deterministic so the schedule is part of the record and can be re-derived by an auditor, and
    per-anchor so no two anchors share a running order.
    """

    cells = [CellPlan(arm, index) for arm in arms for index in range(replicates)]
    random.Random(f"{seed}:{anchor_id}").shuffle(cells)
    return cells


@dataclass(slots=True)
class SkippedAnchor:
    anchor_id: str
    reason: str


@dataclass(slots=True)
class AssayRun:
    rows: list[CellOutcome] = field(default_factory=list)
    skipped: list[SkippedAnchor] = field(default_factory=list)
    theorem_errors: list[tuple[str, str]] = field(default_factory=list)
    solver_seconds: float = 0.0
    lean_seconds: float = 0.0
    wall_clock_s: float = 0.0
    calls: int = 0

    @property
    def table(self) -> CellTable:
        return CellTable(self.rows)


def _play_cell(
    live: LiveAnchorSet,
    anchor: Anchor,
    plan: CellPlan,
    *,
    solver: Solver,
    run: AssayRun,
) -> CellOutcome:
    renderer = ARMS[plan.arm.value]
    item = live.by_id(anchor.anchor_id)
    envelope = anchor.solver_visible.envelope(
        state_id=item.live_state_id,
        session_id=item.identity.record_session_id,
        problem_id=anchor.oracle.problem_id,
    )
    projection = project_arm(renderer, envelope)
    assert_prompt_is_oracle_free(projection.rendered, anchor)

    started = time.monotonic()
    proposal: TacticProposal = solver.propose(
        SolverObservation(step_index=0, state_id=item.live_state_id, rendered=projection.rendered)
    )
    run.solver_seconds += time.monotonic() - started
    run.calls += 1

    parse_status = _PROPOSAL_TO_PARSE[str(proposal.status)]
    step_result = StepResult.PARSE_FAILURE
    closed = False
    if parse_status is ParseStatus.OK and proposal.tactic:
        started = time.monotonic()
        outcome = live.step(anchor.anchor_id, proposal.tactic)
        run.lean_seconds += time.monotonic() - started
        step_result = _OUTCOME_TO_RESULT.get(
            str(outcome.outcome.value), StepResult.ENVIRONMENT_ERROR
        )
        closed = bool(outcome.closed) and step_result is StepResult.ACCEPTED_TRANSITION
        if step_result is StepResult.ACCEPTED_TRANSITION and not closed:
            # Compare against the state THIS session is actually holding, not the one the bank
            # recorded.  The two agree whenever the anchor re-derived (that is what `matched`
            # asserts), but making the endpoint depend on that invariant would mean a silent
            # re-derivation drift showed up as a change of mathematics.
            parent = live.parent_state_text(anchor.anchor_id) or anchor.solver_visible.goals_pp
            if not changed_the_declared_state(parent, outcome.tactic_state):
                step_result = StepResult.ACCEPTED_NO_OP

    return CellOutcome(
        anchor_id=anchor.anchor_id,
        cluster_id=anchor.cluster.file_path,
        theorem=anchor.cluster.theorem_full_name,
        reelaboration_key=anchor.reelaboration_key,
        arm=plan.arm,
        renderer_id=plan.arm.renderer_id,
        intervention_class=InterventionClass(projection.identity.intervention_class),
        replicate_index=plan.replicate_index,
        step_result=step_result,
        parse_status=parse_status,
        closed_all_goals=closed,
        prompt_sha256=proposal.prompt_sha256,
        prompt_tokens=int(proposal.prompt_tokens or 0),
        response_tokens=int(proposal.completion_tokens or 0),
        latency_ms=int(proposal.latency_ms or 0),
        solver_digest=proposal.solver_digest,
        proposed_tactic=proposal.tactic,
    )


def run_assay(
    bank: AnchorBank,
    solver: Solver,
    *,
    arms: Sequence[Arm] = tuple(Arm),
    replicates: int = 1,
    seed: int = 20260909,
    theorem_limit: int | None = None,
    theorem_sample_seed: int | None = None,
    stream_to: Path | None = None,
    progress: bool = True,
) -> AssayRun:
    """Play every arm at every anchor of every theorem in ``bank``.

    One Lean session per theorem; every arm and replicate at every anchor of that theorem branches
    from its own anchored state inside it.  An anchor whose re-elaboration key does not reproduce
    is **skipped and reported**, never silently played: the paired comparison is only meaningful
    when both arms acted on the state the bank says they did.
    """

    run = AssayRun()
    started_run = time.monotonic()
    # A full pass is thousands of live calls over hours.  Rows are appended as they are produced
    # so that a crash, a killed process or a dead Lean session costs the remaining work and not the
    # work already done -- and so that a partial run is still auditable rather than lost.  The
    # format is exactly `CellTable.write_jsonl`'s, so `CellTable.read_jsonl` reads it unchanged.
    sink = None
    if stream_to is not None:
        stream_to.parent.mkdir(parents=True, exist_ok=True)
        sink = stream_to.open("w", encoding="utf-8")
    groups = sorted(bank.by_theorem().items())
    if theorem_limit is not None:
        if theorem_sample_seed is not None:
            # Truncating the sorted list would take an alphabetical slice of mathlib -- every
            # theorem from `Mathlib/Algebra/...` and none from `Mathlib/Topology/...`.  A seeded
            # sample keeps the domain mix of the bank, and being seeded it is still a recorded,
            # re-derivable choice rather than a convenience.
            picked = random.Random(theorem_sample_seed).sample(
                groups, min(theorem_limit, len(groups))
            )
            groups = sorted(picked)
        else:
            groups = groups[:theorem_limit]
    for position, (problem_id, anchors) in enumerate(groups, start=1):
        try:
            with open_anchor_session(list(anchors), seed=seed) as live:
                for anchor_id, reason in live.missing:
                    run.skipped.append(SkippedAnchor(anchor_id, reason or "not re-derived"))
                for item in live.live:
                    if not item.matched:
                        run.skipped.append(
                            SkippedAnchor(item.anchor_id, "reelaboration_key did not reproduce")
                        )
                        continue
                    for plan in plan_cells(
                        arms, replicates=replicates, seed=seed, anchor_id=item.anchor_id
                    ):
                        cell = _play_cell(live, item.anchor, plan, solver=solver, run=run)
                        run.rows.append(cell)
                        if sink is not None:
                            sink.write(
                                json.dumps(cell.to_dict(), sort_keys=True, ensure_ascii=False)
                                + "\n"
                            )
                            sink.flush()
        except Exception as error:  # pragma: no cover - live backend
            run.theorem_errors.append((problem_id, f"{type(error).__name__}: {error}"[:300]))
        if progress:
            print(
                f"[{position}/{len(groups)}] {problem_id[:64]:64} "
                f"cells={len(run.rows)} skipped={len(run.skipped)} "
                f"solver_s={run.solver_seconds:.0f} lean_s={run.lean_seconds:.0f}",
                flush=True,
            )
    if sink is not None:
        sink.close()
    run.wall_clock_s = time.monotonic() - started_run
    return run


def _strip(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in NON_DETERMINISTIC_FIELDS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def build_manifest(
    run: AssayRun,
    *,
    bank: AnchorBank,
    solver: Solver,
    arms: Sequence[Arm],
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    """The run's machine-readable record, in the manual §26.1 declaration shape."""

    identity = solver.identity
    served_note = ""
    verify = getattr(solver, "verify_served", None)
    if callable(verify):
        try:
            identity = verify()
        except Exception as error:
            served_note = f"{type(error).__name__}: {error}"[:200]
    else:
        served_note = "SOLVER_HAS_NO_LIVE_RUNTIME_TO_VERIFY"

    table = run.table
    payload: dict[str, Any] = {
        "schema": ASSAY_VERSION,
        "scientific_status": "PREREGISTERED_ASSAY_RESULT_SET (no analysis in this file)",
        "contamination": (
            "mathlib4 is HISTORICALLY_EXPOSED and exposure is transitive. This records EXECUTION "
            "UNDER KERNEL VERIFICATION at a single anchored state, not reasoning or discovery."
        ),
        "evaluation_universe_hash": bank.content_hash,
        "anchor_bank": {
            "content_hash": bank.content_hash,
            "anchors": bank.stats.anchors,
            "theorems": bank.stats.distinct_theorems,
            "files": bank.stats.distinct_files,
        },
        "design": {
            "arms": [str(arm.value) for arm in arms],
            "replicates": replicates,
            "seed": seed,
            "arm_order": "randomised within each anchor, from a pure function of (seed, anchor_id)",
            "unit": "one anchored Lean state; one action per cell",
            "primary_endpoint": "KERNEL_ACCEPTED_STATE_CHANGE",
            "primary_endpoint_definition": (
                "1 iff Lean accepted the Solver's single first action AND that action either "
                "closed the task or changed the declared backend state; a no-op scores 0. "
                "ENVIRONMENT_ERROR is separately typed and is never a mathematical zero."
            ),
            "state_change_normalization": GOAL_TEXT_NORMALIZATION,
            "cluster_unit": "mathlib file",
        },
        # The arm id and the renderer's own id are DIFFERENT strings and are recorded together
        # here on purpose: `CellOutcome.renderer_id` carries the arm id, and a reader who assumed
        # it named the implementation would be wrong.
        "renderers": {
            str(arm.value): {
                "arm_id": str(arm.value),
                "renderer_id": ARMS[arm.value].renderer_id,
                "declared_intervention_class": str(arm.intervention_class.value),
            }
            for arm in arms
        },
        "solver": identity.to_dict() if hasattr(identity, "to_dict") else str(identity),
        "solver_served_verification": served_note or "VERIFIED_AGAINST_LIVE_RUNTIME",
        "toolchain": bank.to_dict()["toolchain"],
        "counts": {
            "cells": len(table),
            "anchors_played": len(table.anchor_ids),
            "clusters_played": len(table.cluster_ids),
            "skipped_anchors": len(run.skipped),
            "theorem_errors": len(run.theorem_errors),
            "solver_calls": run.calls,
        },
        # RT-V06-08, second route: Lean writes its per-session scratch directory into these two
        # free-text fields, and they are inside `result_hash`.  Left raw, a manifest would differ
        # between two runs of identical mathematics -- the same defect that made HC-V0.5 conclude
        # the runtime was not reproducible.  The message and the probe name survive; only the
        # directory that changes per run is replaced.
        "skipped": [
            {"anchor_id": s.anchor_id, "reason": normalise_backend_diagnostic(s.reason)}
            for s in run.skipped
        ],
        "theorem_errors": [
            {"problem_id": p, "error": normalise_backend_diagnostic(e)}
            for p, e in run.theorem_errors
        ],
        "cost": {
            "solver_seconds": round(run.solver_seconds, 1),
            "lean_seconds": round(run.lean_seconds, 1),
            "wall_clock_s": round(run.wall_clock_s, 1),
            "seconds_per_solver_call": (
                round(run.solver_seconds / run.calls, 3) if run.calls else None
            ),
        },
        "cell_table_content_hash": table.content_hash,
    }
    payload["result_hash"] = stable_hash(_strip(dict(payload)))
    return payload


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - live runtime
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bank", type=Path, default=Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
    )
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--theorem-limit", type=int, default=None)
    parser.add_argument("--theorem-sample-seed", type=int, default=None)
    parser.add_argument("--model", default="qwen3.6:27b-mlx")
    parser.add_argument("--arms", default="", help="comma-separated Arm names; default all four")
    parser.add_argument("--out", default="trajectory/hc_v0_6_assay")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--live", action="store_true", help="required: this makes real model calls")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; this runner makes real Solver calls")

    from arena.trajectory.solver import solver_for

    bank = AnchorBank.load(args.bank)
    solver = solver_for(args.model)
    solver.verify_served()
    arms = tuple(Arm[name] for name in args.arms.split(",")) if args.arms else tuple(Arm)
    cells_path = Path(args.root) / "artifacts" / f"{args.out}_cells.jsonl"
    run = run_assay(
        bank,
        solver,
        arms=arms,
        replicates=args.replicates,
        seed=args.seed,
        theorem_limit=args.theorem_limit,
        theorem_sample_seed=args.theorem_sample_seed,
        stream_to=cells_path,
    )
    manifest = build_manifest(
        run, bank=bank, solver=solver, arms=arms, replicates=args.replicates, seed=args.seed
    )
    store = ArtifactStore(Path(args.root) / "artifacts")
    store.write_json(f"{args.out}_manifest.json", manifest)
    run.table.write_jsonl(cells_path)
    print(
        json.dumps(
            {**manifest["counts"], **manifest["cost"], "result_hash": manifest["result_hash"]},
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
