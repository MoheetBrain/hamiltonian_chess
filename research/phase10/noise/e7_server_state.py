"""E7 -- server state: is the residual divergence a *cold model* or a *busy model*?

E1/E2 hammered a warm, idle server and found byte-stability.  The A/B/C/D episode replays found
exactly one genuine Solver divergence, and it occurred on the run that followed a ~55-minute idle
gap -- i.e. the one run whose first calls hit a **freshly (re)loaded** model.  That is a mechanism
hypothesis, and this script is built to falsify it rather than to illustrate it.

Four arms, all on the same two probes (one prompt the recorded run answered two ways, one it
answered one way), so an effect that appears in both is about the server and not about the prompt:

``warm``        ``--repeats`` calls on an already-loaded model.  The reference arm.
``cold``        before **each** call the model is explicitly evicted (``keep_alive=0``) and the
                eviction is *confirmed* against ``/api/ps`` before the probe is sent, so "cold"
                is an observed server state and not an assumption.  If the first call after a load
                differs from the warm answer, model (re)load is the carrier.
``concurrent``  ``--workers`` threads generate simultaneously; the probe's answer is recorded with
                the number of requests actually in flight.  Batched execution changes reduction
                order, which is the standard mechanism for a greedy decode to move.
``idle``        ``--idle-seconds`` of silence between calls, *without* forcing eviction: separates
                "time passed" from "the model was unloaded".

``keep_alive`` is a top-level ``/api/generate`` field rather than an ``options`` key, so it cannot
be expressed through :func:`common.variant_identity`.  :class:`KeepAliveSolver` adds it by
overriding :meth:`OllamaTacticSolver.payload` and changes nothing else -- same identity, same
grammar, same wire flags -- so identity verification still applies.

Run::

    .venv/bin/python -m research.phase10.noise.e7_server_state --repeats 12 --workers 4
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import threading
import time
import urllib.request
from typing import Any

from arena.trajectory.solver import OllamaTacticSolver, ProposalBudget
from research.phase10.noise.common import (
    SMOKE_ARTIFACT,
    Goal,
    JsonlWriter,
    base_parser,
    call,
    environment_record,
    modal_fraction,
    solver_with,
    variant_identity,
    verified_solver,
    write_meta,
)
from research.phase10.noise.common import _recorded_goals as recorded_goals
from research.phase10.noise.e6_divergent_replay import classify, recorded_answers


class KeepAliveSolver(OllamaTacticSolver):
    """The production adapter with one extra wire field: ``keep_alive``.

    ``keep_alive=0`` tells Ollama to drop the model as soon as the request finishes, which is how
    the *next* call is forced to pay a real load.  Nothing else about the request changes.
    """

    def __init__(self, *args: Any, keep_alive: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.keep_alive = keep_alive

    def payload(self, prompt: str, *, budget: ProposalBudget) -> dict[str, Any]:
        body = super().payload(prompt, budget=budget)
        if self.keep_alive is not None:
            body["keep_alive"] = self.keep_alive
        return body


def loaded_models(endpoint: str) -> list[str]:
    """Which models the runtime currently holds in memory, per ``/api/ps``."""

    try:
        with urllib.request.urlopen(f"{endpoint}/api/ps", timeout=30) as handle:  # noqa: S310
            payload = json.loads(handle.read().decode("utf-8"))
    except Exception:
        return []
    return [str(row.get("model", "")) for row in payload.get("models", [])]


def evict(endpoint: str, model: str, *, timeout_s: float = 60.0) -> dict[str, Any]:
    """Ask the runtime to unload ``model`` and **confirm** it is gone before returning."""

    body = json.dumps({"model": model, "keep_alive": 0}).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310
        f"{endpoint}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    requested = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as handle:  # noqa: S310
            handle.read()
    except Exception as error:
        return {"evict_error": repr(error), "confirmed_unloaded": False}
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if model not in loaded_models(endpoint):
            return {
                "confirmed_unloaded": True,
                "evict_wait_s": round(time.time() - requested, 3),
            }
        time.sleep(0.25)
    return {"confirmed_unloaded": False, "evict_wait_s": round(time.time() - requested, 3)}


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e7_server_state.jsonl")
    parser.add_argument("--repeats", type=int, default=12)
    parser.add_argument("--workers", type=int, default=4, help="threads in the concurrent arm")
    parser.add_argument("--idle-seconds", type=float, default=20.0)
    parser.add_argument("--idle-repeats", type=int, default=6)
    parser.add_argument("--cold-repeats", type=int, default=6)
    parser.add_argument(
        "--arms", default="warm,cold,concurrent,idle", help="comma-separated subset"
    )
    args = parser.parse_args(argv)

    _, served = verified_solver(args.endpoint)
    recorded = recorded_answers()
    suspect, control = classify(recorded)
    by_digest = {goal.prompt_sha256: goal for goal in recorded_goals(SMOKE_ARTIFACT)}
    probes: list[tuple[str, Goal]] = []
    for digest in suspect:
        if digest in by_digest:
            probes.append(("suspect", by_digest[digest]))
            break
    for digest in control:
        if digest in by_digest:
            probes.append(("control", by_digest[digest]))
            break
    if len(probes) < 2:
        raise SystemExit("could not recover one suspect and one control prompt")
    others = [
        goal
        for goal in by_digest.values()
        if goal.prompt_sha256 not in {g.prompt_sha256 for _, g in probes}
    ]

    identity = variant_identity()
    budget = ProposalBudget(timeout_seconds=float(args.timeout))
    warm_solver = solver_with(identity, endpoint=args.endpoint)
    arms = [name.strip() for name in args.arms.split(",") if name.strip()]
    started_wall = time.time()

    with JsonlWriter(args.out) as log:
        # -- warm ------------------------------------------------------------------------------
        if "warm" in arms:
            for group, goal in probes:
                for index in range(int(args.repeats)):
                    log.write(
                        call(
                            warm_solver,
                            goal,
                            budget=budget,
                            tags={
                                "experiment": "e7_server_state",
                                "arm": "warm",
                                "group": group,
                                "repeat_index": index,
                                "elapsed_s": round(time.time() - started_wall, 3),
                                "global_index": log.rows,
                            },
                        )
                    )

        # -- cold ------------------------------------------------------------------------------
        if "cold" in arms:
            cold_solver = KeepAliveSolver(identity, endpoint=args.endpoint)
            for group, goal in probes:
                for index in range(int(args.cold_repeats)):
                    state = evict(args.endpoint, identity.model_name)
                    row = call(
                        cold_solver,
                        goal,
                        budget=budget,
                        tags={
                            "experiment": "e7_server_state",
                            "arm": "cold",
                            "group": group,
                            "repeat_index": index,
                            "elapsed_s": round(time.time() - started_wall, 3),
                            "global_index": log.rows,
                            **state,
                        },
                    )
                    log.write(row)

        # -- concurrent ------------------------------------------------------------------------
        if "concurrent" in arms:
            workers = max(2, int(args.workers))
            inflight = threading.BoundedSemaphore(workers)
            counter = {"n": 0}
            lock = threading.Lock()

            def one(goal: Goal, group: str, index: int, role: str) -> dict[str, Any]:
                solver = solver_with(identity, endpoint=args.endpoint)
                with inflight:
                    with lock:
                        counter["n"] += 1
                        peak = counter["n"]
                    try:
                        row = call(
                            solver,
                            goal,
                            budget=budget,
                            tags={
                                "experiment": "e7_server_state",
                                "arm": "concurrent",
                                "group": group,
                                "role": role,
                                "repeat_index": index,
                                "workers_requested": workers,
                                "requests_in_flight_at_start": peak,
                                "global_index": -1,
                            },
                        )
                    finally:
                        with lock:
                            counter["n"] -= 1
                return row

            for group, goal in probes:
                for index in range(int(args.repeats)):
                    jobs: list[tuple[Goal, str, int, str]] = [(goal, group, index, "probe")]
                    for offset in range(workers - 1):
                        jobs.append((others[(index + offset) % len(others)], "load", index, "load"))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                        for row in pool.map(lambda job: one(*job), jobs):
                            row["global_index"] = log.rows
                            log.write(row)

        # -- idle ------------------------------------------------------------------------------
        if "idle" in arms:
            for group, goal in probes:
                for index in range(int(args.idle_repeats)):
                    if index:
                        time.sleep(float(args.idle_seconds))
                    before = identity.model_name in loaded_models(args.endpoint)
                    log.write(
                        call(
                            warm_solver,
                            goal,
                            budget=budget,
                            tags={
                                "experiment": "e7_server_state",
                                "arm": "idle",
                                "group": group,
                                "repeat_index": index,
                                "idle_seconds": float(args.idle_seconds),
                                "loaded_before_call": before,
                                "elapsed_s": round(time.time() - started_wall, 3),
                                "global_index": log.rows,
                            },
                        )
                    )

    rows = [
        row
        for row in (json.loads(line) for line in args.out.read_text("utf-8").splitlines() if line)
        if row.get("role") != "load"
    ]
    cells: dict[str, dict[str, list[Any]]] = {}
    for row in rows:
        key = f"{row['arm']}::{row['group']}"
        cell = cells.setdefault(key, {"raw": [], "tactics": [], "ctok": []})
        cell["raw"].append(row["response_sha256"])
        cell["tactics"].append(str(row["tactic"]))
        cell["ctok"].append(row["completion_tokens"])

    summary: dict[str, Any] = {}
    for key, cell in sorted(cells.items()):
        modal_raw, raw_rate = modal_fraction(cell["raw"])
        summary[key] = {
            "calls": len(cell["raw"]),
            "distinct_raw_responses": len(set(cell["raw"])),
            "distinct_tactics": len(set(cell["tactics"])),
            "distinct_completion_tokens": sorted({t for t in cell["ctok"] if t is not None}),
            "modal_raw_rate": round(raw_rate, 4),
            "modal_raw_sha256": modal_raw,
            "byte_stable": len(set(cell["raw"])) == 1,
        }
    # Does an arm's modal answer differ from the warm arm's, for the same probe group?
    cross: dict[str, Any] = {}
    for group in {row["group"] for row in rows}:
        warm_key = f"warm::{group}"
        if warm_key not in summary:
            continue
        cross[group] = {
            arm.split("::")[0]: summary[arm]["modal_raw_sha256"]
            == summary[warm_key]["modal_raw_sha256"]
            for arm in summary
            if arm.endswith(f"::{group}")
        }

    headline = {
        "arms": arms,
        "per_cell": summary,
        "modal_answer_equals_warm": cross,
        "byte_unstable_cells": sorted(k for k, v in summary.items() if not v["byte_stable"]),
        "wall_seconds": round(time.time() - started_wall, 1),
    }
    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e7_server_state",
            "question": "does model (re)load, concurrency, or idle time move a greedy answer?",
            "environment": environment_record(served),
            "probes": {group: goal.to_dict() for group, goal in probes},
            "summary": headline,
        },
    )
    print(json.dumps(headline, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
