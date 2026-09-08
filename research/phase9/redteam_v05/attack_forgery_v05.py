"""Targets 5 and 11: a forgery STRONGER than the previous suite's, and an attack on the fix.

The previous suite's action swap is now caught before Lean runs, by `_structural_problems`'s
evidence <-> action cross-check.  That check compares the actions with `verifier_evidence`, and
`verifier_evidence` is still OUTSIDE `content_hash` (RT-05, never fixed).  So the obvious next
forgery rewrites both, in step, and reseals.  This measures whether `relive` -- the only remaining
net -- actually catches it.

Read-only on artifacts/: the committed bank is opened, never written.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import OUT, emit  # noqa: E402

from arena.trajectory.arena_v0 import verify_bank  # noqa: E402
from arena.trajectory.lean_backend import check_toolchain  # noqa: E402
from arena.trajectory.schema import VerifiedTrajectory, derive_trajectory_id  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "artifacts/trajectory_bank_v0/h5/bank.jsonl"
RESULTS: dict[str, Any] = {}


def note(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {str(detail)[:500]}")


def reseal(payload: dict[str, Any]) -> dict[str, Any]:
    t = VerifiedTrajectory.from_dict(payload, check_hashes=False)
    payload = copy.deepcopy(payload)
    payload["content_hash"] = t.content_hash
    payload["states_hash"] = t.states_hash
    payload["actions_hash"] = t.actions_hash
    payload["horizon"] = t.horizon.to_dict()
    payload["trajectory_id"] = derive_trajectory_id(t.problem_id, t.content_hash)
    return payload


def write_bank(name: str, payloads: list[dict[str, Any]]) -> Path:
    directory = OUT / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bank.jsonl").write_text(
        "".join(json.dumps(p, sort_keys=True) + "\n" for p in payloads), encoding="utf-8"
    )
    return directory


def load_rows() -> list[dict[str, Any]]:
    return [json.loads(line) for line in BANK.read_text().splitlines() if line.strip()]


def main() -> int:
    rows = load_rows()
    verified = [r for r in rows if r["terminal_status"] == "CLOSED_VERIFIED"]
    RESULTS["bank"] = {
        "path": str(BANK.relative_to(ROOT)),
        "rows": len(rows),
        "closed_verified": len(verified),
        "states_carry_session_binding": sorted(
            {bool(s.get("session_id")) for r in rows for s in r["states"]}
        ),
        "states_carry_problem_binding": sorted(
            {bool(s.get("problem_id")) for r in rows for s in r["states"]}
        ),
    }
    honest = copy.deepcopy(verified[0])

    # ------------------------------------------------------------------ G1: the honest control
    write_bank("v05_honest_control", [copy.deepcopy(honest)])

    # ------------------------------------------------- G2: coordinated action + evidence swap
    swapped = copy.deepcopy(honest)
    original_tactics = [a["tactic"] for a in swapped["actions"]]
    for action in swapped["actions"]:
        action["tactic"] = "aesop"
    accepted = [
        e for e in swapped["verifier_evidence"]
        if e["kind"] == "STEP" and e["verdict"] == "ACCEPTED"
    ]
    for evidence in accepted:
        evidence["tactic"] = "aesop"          # verifier_evidence is OUTSIDE content_hash
    swapped = reseal(swapped)
    loaded, load_error = True, ""
    try:
        VerifiedTrajectory.from_dict(swapped)
    except Exception as exc:  # noqa: BLE001
        loaded, load_error = False, f"{type(exc).__name__}: {exc}"[:200]
    write_bank("v05_forged_action_and_evidence", [swapped])
    RESULTS["G2_setup"] = {
        "original_tactics": original_tactics,
        "forged_tactic": "aesop",
        "evidence_rewritten_in_step": len(accepted),
        "loads_without_error": loaded,
        "load_error": load_error,
        "new_trajectory_id": swapped["trajectory_id"],
    }

    # -------------------------------------------------- G3: actor relabel (RT-04 carry-over)
    relabelled = copy.deepcopy(honest)
    for action in relabelled["actions"]:
        action["actor"] = "SOLVER"
    relabelled = reseal(relabelled)
    write_bank("v05_forged_solver_actor", [relabelled])
    RESULTS["G3_setup"] = {
        "horizon_after": relabelled["horizon"],
        "claim": "a flat replay of a recorded mathlib proof, reported as a SOLVER horizon",
    }

    # --------------------------------- G4: same-scope splice (defeat the scope invariant)
    by_scope: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = json.dumps(row["states"][0]["backend_native"]["pp_scope"], sort_keys=True)
        by_scope.setdefault(key, []).append(row)
    pair = next((v for v in by_scope.values() if len(v) > 1), None)
    RESULTS["G4_setup"] = {
        "distinct_scopes_in_bank": len(by_scope),
        "largest_scope_group": max(len(v) for v in by_scope.values()),
        "same_scope_pair_available": pair is not None,
    }
    if pair is not None:
        a, b = copy.deepcopy(pair[0]), copy.deepcopy(pair[1])
        spliced = copy.deepcopy(a)
        next_sid = len(a["states"])
        for state in b["states"][1:]:
            state = copy.deepcopy(state)
            state["index"] = next_sid
            state["state_id"] = str(next_sid)
            state["envelope_id"] = (
                f"{state['backend_native']['kind']}:{next_sid}:"
                f"{state['backend_native']['pp_sha256'][:32]}"
            )
            spliced["states"].append(state)
            next_sid += 1
        prev = a["states"][-1]["state_id"]
        aid = len(a["actions"])
        step_ev = [
            e for e in b["verifier_evidence"]
            if e["kind"] == "STEP" and e["verdict"] == "ACCEPTED"
        ]
        for offset, action in enumerate(copy.deepcopy(b["actions"])):
            action["index"] = aid
            action["from_state_id"] = prev
            prev = str(int(prev) + 1)
            action["to_state_id"] = prev
            spliced["actions"].append(action)
            if offset < len(step_ev):
                ev = copy.deepcopy(step_ev[offset])
                ev["step"] = aid
                ev["from_state_id"] = action["from_state_id"]
                ev["to_state_id"] = action["to_state_id"]
                spliced["verifier_evidence"].insert(-1, ev)
            aid += 1
        try:
            spliced = reseal(spliced)
            write_bank("v05_forged_same_scope_concat", [spliced])
            RESULTS["G4_setup"].update(
                {
                    "source_a": a["problem_id"],
                    "source_b": b["problem_id"],
                    "spliced_horizon_claimed": spliced["horizon"],
                    "loads_without_error": True,
                }
            )
        except Exception as exc:  # noqa: BLE001
            RESULTS["G4_setup"].update(
                {"loads_without_error": False, "error": f"{type(exc).__name__}: {exc}"[:220]}
            )

    # ------------------------------------------------------------------- run the verifier
    toolchain = check_toolchain().available
    RESULTS["toolchain"] = toolchain
    banks = [
        "v05_honest_control",
        "v05_forged_action_and_evidence",
        "v05_forged_solver_actor",
    ]
    if (OUT / "v05_forged_same_scope_concat" / "bank.jsonl").exists():
        banks.append("v05_forged_same_scope_concat")
    for name in banks:
        directory = OUT / name
        started = time.monotonic()
        structural = verify_bank(directory, relive=False)
        result: dict[str, Any] = {
            "structural_passed": structural.passed,
            "structural_failures": structural.failures[:3],
        }
        if toolchain:
            lived = verify_bank(directory, relive=True)
            result.update(
                {
                    "relive_passed": lived.passed,
                    "relived": lived.relived,
                    "relive_matches": lived.relive_matches,
                    "relive_failures": [f[:220] for f in lived.failures[:3]],
                }
            )
        result["wall_s"] = round(time.monotonic() - started, 1)
        RESULTS[f"verdict_{name}"] = result
        print(name, json.dumps(result)[:400])

    caught_by_structural = not RESULTS["verdict_v05_forged_action_and_evidence"][
        "structural_passed"
    ]
    caught_by_relive = not RESULTS["verdict_v05_forged_action_and_evidence"].get(
        "relive_passed", True
    )
    note(
        "G2_coordinated_action_and_evidence_swap",
        not (caught_by_structural or caught_by_relive),
        caught_by_structural_check=caught_by_structural,
        caught_by_relive=caught_by_relive,
        detail=RESULTS["verdict_v05_forged_action_and_evidence"],
        note="the previous suite's swap was caught by the evidence cross-check alone; this one "
        "rewrites the evidence too, so only the re-execution can catch it",
    )
    note(
        "G3_actor_relabel_still_verifies",
        RESULTS["verdict_v05_forged_solver_actor"].get("relive_passed", False),
        detail=RESULTS["verdict_v05_forged_solver_actor"],
        horizon_claimed=RESULTS["G3_setup"]["horizon_after"],
        note="RT-04 carry-over: a flat replay of mathlib's own proof, relabelled, passes "
        "verify_bank(relive=True) claiming solver_actions == achieved",
    )
    if "verdict_v05_forged_same_scope_concat" in RESULTS:
        note(
            "G4_same_scope_splice",
            RESULTS["verdict_v05_forged_same_scope_concat"].get("relive_passed", False),
            detail=RESULTS["verdict_v05_forged_same_scope_concat"],
            setup=RESULTS["G4_setup"],
        )
    else:
        note("G4_same_scope_splice", False, setup=RESULTS["G4_setup"],
             note="no two trajectories in the committed h5 bank share an elaboration scope")
    emit("forgery_v05", RESULTS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
