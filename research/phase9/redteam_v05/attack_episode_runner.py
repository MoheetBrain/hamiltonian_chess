"""Target 7 (model-identity / condition) plus what the emitted HC-V0.5 artefact does and does
not bind.  Offline except one optional read-only /api/tags + /api/show pair."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import ScriptedArena, ScriptedStep, emit, make_probe  # noqa: E402

from arena.trajectory import episode as episode_mod  # noqa: E402
from arena.trajectory.lean_backend import StepOutcome  # noqa: E402
from arena.trajectory.solver import (  # noqa: E402
    RECORDED_SOLVER,
    OllamaTacticSolver,
    ScriptedSolver,
    SolverIdentityMismatch,
    identity_from_live,
)
from arena.trajectory.task import TaskSelection, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}
ARTIFACT = Path(__file__).resolve().parents[3] / "artifacts/trajectory/hc_v0_5_smoke.json"


def record(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {detail}")


def _run(script_default="simp", plan=None, max_steps=8):
    probe = make_probe()
    plan = plan or [ScriptedStep(StepOutcome.OK, pp="no goals", closed=True)]
    arena = ScriptedArena(plan, probe=probe)
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    solver = ScriptedSolver(default=script_default)
    return task, episode_mod.run_episode(task, solver, max_steps=max_steps), solver


# ------------------------- E1: the whole selection manifest is silently dropped
def e1() -> None:
    probe = make_probe()
    task = VerifiedTask.from_probe(probe)
    selection = TaskSelection(
        tasks=(task,), scanned=12000, discards={"BELOW_MIN_HORIZON": 11000},
        leakage={"problems_dropped": 6}, seed=20260908, scan_limit=12000,
        min_reference_length=1, max_reference_length=4,
        train_json="/…/random/train.json",
    )
    _, result, solver = _run()
    manifest = episode_mod.build_manifest([result], solver=solver, selection=selection)
    record(
        "E1_selection_provenance_silently_dropped",
        manifest["selection"] == {},
        selection_in_manifest=manifest["selection"],
        selection_has_to_dict=hasattr(selection, "to_dict"),
        selection_has_manifest=hasattr(selection, "manifest"),
        manifest_keys_available=sorted(selection.manifest()),
        committed_artefact_selection=json.loads(ARTIFACT.read_text())["selection"]
        if ARTIFACT.exists() else "artefact absent",
        call_site='getattr(selection, "to_dict", lambda: {})()',
        note="TaskSelection exposes manifest(), never to_dict(); the getattr default swallows "
        "the seed, scan_limit, train_json, per-task ids, discard ledger and leakage ledger",
    )


# ------------------------- E2/E3: what identifies a step and an episode in the artefact
def e2_e3() -> None:
    _, result, _ = _run()
    d = result.to_dict()
    committed = json.loads(ARTIFACT.read_text()) if ARTIFACT.exists() else {"episodes": []}
    ids = {s["state_id"] for e in committed["episodes"] for s in e["steps"]}
    record(
        "E2_step_state_id_is_always_unknown",
        all(s["state_id"] == "?" for s in d["steps"]),
        rendered_keys_the_renderer_emits=["state_id", "goals_pp", "..."],
        key_the_runner_reads="backend_state_id",
        state_ids_in_fresh_run=[s["state_id"] for s in d["steps"]],
        state_ids_in_committed_artefact=sorted(ids),
        note="run_episode reads projection.rendered['backend_state_id']; BackendNativeRenderer "
        "emits 'state_id'.  Every recorded action is therefore unbound to a state",
    )
    task = VerifiedTask.from_probe(make_probe())
    record(
        "E3_task_id_in_the_artefact_is_the_problem_id",
        d["task_id"] == d["problem_id"],
        artefact_task_id=d["task_id"],
        artefact_problem_id=d["problem_id"],
        real_task_id=task.task_id,
        committed_all_equal=all(e["task_id"] == e["problem_id"] for e in committed["episodes"]),
        note="EpisodeResult(task_id=task.problem_id, ...); the vtask- identity that covers the "
        "budget, failure policy, seal and source hash appears nowhere in the artefact",
    )


# ------------------------- E4: the solver digest is asserted, never verified
def e4() -> None:
    src = inspect.getsource(episode_mod)
    calls_verify = "verify_served" in src
    live: dict[str, Any] = {}
    try:
        served = identity_from_live()
        live = {
            "served_digest": served.model_digest,
            "recorded_digest": RECORDED_SOLVER.model_digest,
            "digests_match": served.model_digest == RECORDED_SOLVER.model_digest,
        }
        try:
            RECORDED_SOLVER.assert_matches(served)
            live["assert_matches"] = "passes"
        except SolverIdentityMismatch as exc:
            live["assert_matches"] = f"RAISES: {exc}"[:300]
    except Exception as exc:  # noqa: BLE001
        live = {"live_probe_failed": f"{type(exc).__name__}: {exc}"[:160]}

    # a transport that serves something else entirely: the run still stamps RECORDED_SOLVER
    def liar(url, payload):
        if url.endswith("/api/generate"):
            return {"response": '{"tactic": "simp"}', "prompt_eval_count": 1, "eval_count": 1,
                    "done_reason": "stop"}
        if url.endswith("/api/tags"):
            return {"models": [{"model": "qwen3.6:27b-mlx", "digest": "deadbeef" * 8}]}
        if url.endswith("/api/version"):
            return {"version": "9.9.9"}
        return {"details": {}, "model_info": {}, "modelfile": "", "template": "",
                "capabilities": []}

    probe = make_probe()
    arena = ScriptedArena([ScriptedStep(StepOutcome.OK, pp="no goals", closed=True)], probe=probe)
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    solver = OllamaTacticSolver(transport=liar)
    result = episode_mod.run_episode(task, solver, max_steps=4)
    manifest = episode_mod.build_manifest([result], solver=solver, selection=object())
    record(
        "E4_solver_digest_asserted_not_verified",
        not calls_verify and manifest["solver"]["model_digest"] == RECORDED_SOLVER.model_digest,
        episode_module_calls_verify_served=calls_verify,
        manifest_digest=manifest["solver"]["model_digest"][:24],
        digest_actually_served_by_this_transport="deadbeef" * 3,
        episode_solved=result.solved,
        live_runtime_check=live,
        note="run_episode() and episode.main() never call OllamaTacticSolver.verify_served(); "
        "the digest in the manifest is a module constant",
    )


# ---------------- E5/E6/E7: how the runner attributes a harness fault and a malformed emission
def e5_e6_e7() -> None:
    class DeadTransport:
        def __call__(self, url, payload):
            raise ConnectionRefusedError("ollama is down")

    probe = make_probe()
    arena = ScriptedArena([ScriptedStep(StepOutcome.OK, pp="⊢ x")], probe=probe)
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    solver = OllamaTacticSolver(transport=DeadTransport())
    result = episode_mod.run_episode(task, solver, max_steps=4)
    summary = episode_mod.summarise([result])
    record(
        "E5_transport_failure_counted_as_a_solver_parse_failure",
        summary["parse_failures"] > 0 and summary["environment_errors"] == 0,
        step_proposal_status=[s.proposal_status for s in result.steps],
        summary=summary,
        episode_terminal=result.terminal_status,
        note="EpisodeResult.parse_failures counts every proposal_status != OK, so "
        "TRANSPORT_FAILURE and PROMPT_OVER_BUDGET are charged to the Solver; summarise()'s "
        "environment_errors counts neither",
    )

    # E6: an exception inside the episode leaves terminal_status at its initial "OPEN"
    class ExplodingArena(ScriptedArena):
        def step(self, tactic):
            raise RuntimeError("backend exploded mid-episode")

    probe2 = make_probe()
    task2 = VerifiedTask.from_probe(probe2, arena_factory=lambda: ExplodingArena(probe=probe2))
    result2 = episode_mod.run_episode(task2, ScriptedSolver(default="simp"), max_steps=4)
    record(
        "E6_crashed_episode_reported_as_open",
        result2.terminal_status == "OPEN",
        terminal_status=result2.terminal_status,
        terminal_outcome=result2.terminal_outcome,
        error=result2.error,
        dead_line='result.terminal_status = result.terminal_status or "ENVIRONMENT_ERROR"',
        note='terminal_status is initialised to the truthy string "OPEN", so the `or` fallback '
        "can never fire",
    )

    # E7: a malformed proposal never reaches the declared failure policy
    probe3 = make_probe()
    arena3 = ScriptedArena([ScriptedStep(StepOutcome.OK, pp="⊢ y")], probe=probe3)
    task3 = VerifiedTask.from_probe(probe3, arena_factory=lambda: arena3)
    result3 = episode_mod.run_episode(task3, ScriptedSolver(default=None), max_steps=4)
    record(
        "E7_solver_parse_failure_bypasses_the_failure_policy",
        result3.terminal_status == "OPEN" and task3.retries_remaining
        == task3.failure_policy.effective_retries,
        declared_policy=task3.failure_policy.to_dict(),
        steps=[s.to_dict()["proposal_status"] for s in result3.steps],
        episode_terminal=result3.terminal_status,
        retries_remaining_after=task3.retries_remaining,
        arena_saw_tactics=arena3.tactics,
        note="the runner `break`s on a non-OK proposal without stepping the task, so "
        "ONE_DIAGNOSTIC_RETRY never applies to the single most likely solver-attributable "
        "failure, and the episode is filed OPEN rather than FAILED",
    )


# ------------------------- E8: the actor label in the artefact is a literal
def e8() -> None:
    src = inspect.getsource(episode_mod.EpisodeResult.to_dict)
    _, result, _ = _run()
    record(
        "E8_actor_label_is_a_literal",
        '"actor": "SOLVER"' in src.replace("'", '"'),
        artefact_actor=result.to_dict()["actor"],
        source_line=[line.strip() for line in src.splitlines() if "actor" in line],
        note="nothing in the artefact binds an action to the Solver that produced it beyond "
        "the per-step prompt_sha256",
    )


# ------------------------- E9: determinism of result_hash, and what it separates
def e9() -> None:
    _, r1, s1 = _run()
    _, r2, s2 = _run()
    m1 = episode_mod.build_manifest([r1], solver=s1, selection=object())
    m2 = episode_mod.build_manifest([r2], solver=s2, selection=object())
    _, r3, _ = _run(script_default="ring")
    m3 = episode_mod.build_manifest([r3], solver=ScriptedSolver(default="ring"),
                                    selection=object())
    record(
        "E9_result_hash_not_deterministic",
        m1["result_hash"] != m2["result_hash"],
        identical_runs_hash_equal=m1["result_hash"] == m2["result_hash"],
        different_tactic_hash_differs=m1["result_hash"] != m3["result_hash"],
        hash=m1["result_hash"][:24],
    )
    record(
        "E10_manifest_carries_no_condition_identity",
        not any(k in m1 for k in ("condition_id", "actor", "replicate_id", "evaluation_mode")),
        manifest_keys=sorted(m1),
        note="the interactive path emits no condition_id, EvidenceActor or ReplicateAuthorisation, "
        "so two HC-V0.5 runs cannot be pooled, deduplicated or refused as duplicate draws by "
        "arena/evolution/record.py's machinery",
    )


if __name__ == "__main__":
    for fn in (e1, e2_e3, e4, e5_e6_e7, e8, e9):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(f"{fn.__name__}_CRASHED", False, error=f"{type(exc).__name__}: {exc}")
    emit("episode_runner", RESULTS)
