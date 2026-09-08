"""RED TEAM / attack classes 1, 2, 5, 8: VerifiedTrajectory integrity and horizon accounting.

Every attack here operates on COPIES written under `research/phase9/redteam/out/`.  Nothing
under `artifacts/` is read-write; the committed bank is opened read-only.

Claims under attack (quoted from the code being attacked):

* `VerifiedTrajectory` docstring: "every action's endpoints name the adjacent envelopes'
  backend state ids (so ten unrelated one-step probes cannot be concatenated into a
  'ten-step trajectory')";
* `verify_bank` docstring: "`relive=True` additionally re-executes every trajectory's action
  sequence against a fresh Lean session ... the only check that can catch a bank whose evidence
  was fabricated wholesale";
* `Actor` docstring: "Never mix the two in one reported trajectory";
* the team's disclosure: "ALL bank actions are actor=REFERENCE".

Run:  .venv/bin/python research/phase9/redteam/attack_trajectory_integrity.py
Out:  research/phase9/redteam/out/trajectory_integrity.json
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory.arena_v0 import load_bank, verify_bank  # noqa: E402
from arena.trajectory.schema import (  # noqa: E402
    TrajectoryIntegrityError,
    VerifiedTrajectory,
    derive_trajectory_id,
)

BANK = ROOT / "artifacts" / "trajectory_bank_v0" / "h5" / "bank.jsonl"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


def rows() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in BANK.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def reseal(payload: dict[str, Any]) -> dict[str, Any]:
    """Recompute every self-referential hash the schema checks, as a forger would."""

    trajectory = VerifiedTrajectory.from_dict(payload, check_hashes=False)
    payload = copy.deepcopy(payload)
    payload["content_hash"] = trajectory.content_hash
    payload["states_hash"] = trajectory.states_hash
    payload["actions_hash"] = trajectory.actions_hash
    payload["horizon"] = trajectory.horizon.to_dict()
    payload["trajectory_id"] = derive_trajectory_id(trajectory.problem_id, trajectory.content_hash)
    return payload


def try_load(payload: dict[str, Any]) -> tuple[bool, str]:
    try:
        VerifiedTrajectory.from_dict(payload)
    except Exception as exc:  # noqa: BLE001 - the exception IS the result
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def write_bank(name: str, payloads: list[dict[str, Any]]) -> Path:
    directory = OUT / name
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "bank.jsonl"
    path.write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in payloads)
    )
    return directory


def main() -> int:
    findings: dict[str, Any] = {}
    bank = rows()
    verified = [r for r in bank if r["terminal_status"] == "CLOSED_VERIFIED"]
    failed = [r for r in bank if r["terminal_status"] == "FAILED"]
    findings["bank"] = {
        "path": str(BANK.relative_to(ROOT)),
        "rows": len(bank),
        "closed_verified": len(verified),
        "failed": len(failed),
        "state_ids_observed": sorted({s["state_id"] for r in bank for s in r["states"]})[:20],
        "note": "state ids are per-session small integers; nothing binds an id to its pp bytes",
    }

    # ---------------------------------------------------------------- T1: concatenation
    # Splice the TAIL of trajectory B (different theorem, different mathematics) onto the HEAD
    # of trajectory A, renumbering only `index` and `state_id` so the chain check is satisfied.
    a, b = copy.deepcopy(verified[0]), copy.deepcopy(verified[1])
    spliced = copy.deepcopy(a)
    next_index = len(a["states"])
    next_sid = next_index
    for state in b["states"][1:]:
        state = copy.deepcopy(state)
        state["index"] = next_index
        state["state_id"] = str(next_sid)
        state["envelope_id"] = (
            f"{state['backend_native']['kind']}:{next_sid}:{state['backend_native']['pp_sha256'][:32]}"
        )
        spliced["states"].append(state)
        next_index += 1
        next_sid += 1
    aid = len(a["actions"])
    prev_sid = a["states"][-1]["state_id"]
    for action in b["actions"]:
        action = copy.deepcopy(action)
        action["index"] = aid
        action["from_state_id"] = prev_sid
        prev_sid = str(int(prev_sid) + 1)
        action["to_state_id"] = prev_sid
        spliced["actions"].append(action)
        aid += 1
    # forge the ACCEPTED step-evidence count that `_structural_problems` audits
    step_ev = [
        e for e in b["verifier_evidence"] if e["kind"] == "STEP" and e["verdict"] == "ACCEPTED"
    ]
    for offset, ev in enumerate(copy.deepcopy(step_ev)):
        ev["step"] = len(a["actions"]) + offset
        spliced["verifier_evidence"].insert(-1, ev)
    spliced = reseal(spliced)
    ok, err = try_load(spliced)
    findings["T1_concatenate_two_theorems"] = {
        "claim_under_attack": "ten unrelated one-step probes cannot be concatenated",
        "source_a": a["problem_id"],
        "source_b": b["problem_id"],
        "a_horizon": a["horizon"]["achieved"],
        "b_horizon": b["horizon"]["achieved"],
        "spliced_horizon_claimed": spliced["horizon"],
        "loads_without_error": ok,
        "error": err,
        "problem_id_kept": spliced["problem_id"],
    }

    # ---------------------------------------------------------------- T2: actor relabel
    relabelled = copy.deepcopy(verified[0])
    for action in relabelled["actions"]:
        action["actor"] = "SOLVER"
    relabelled = reseal(relabelled)
    ok2, err2 = try_load(relabelled)
    findings["T2_reference_relabelled_as_solver"] = {
        "claim_under_attack": "ALL bank actions are actor=REFERENCE (disclosed limitation)",
        "loads_without_error": ok2,
        "error": err2,
        "horizon_after": relabelled["horizon"],
        "note": (
            "solver_actions is DERIVED from the actor field, so relabelling turns a replay of a "
            "recorded mathlib proof into a claimed solver horizon; nothing in the record ties the "
            "actor label to who chose the tactic"
        ),
    }

    # ---------------------------------------------------------------- T3: FAILED -> CLOSED_VERIFIED
    promoted = copy.deepcopy(failed[0])
    promoted["terminal_status"] = "CLOSED_VERIFIED"
    fake_kernel = {
        "kind": "TERMINAL_KERNEL",
        "verifier": "lean4-kernel",
        "verdict": "KERNEL_VERIFIED",
        "step": len(promoted["actions"]),
        "from_state_id": None,
        "to_state_id": None,
        "tactic": None,
        "backend_error": None,
        "rejected_reason": None,
        "print_axioms": "'probe_forged' depends on axioms: [propext, Classical.choice, Quot.sound]",
        "contains_sorry_ax": False,
        "contains_of_reduce_bool": False,
    }
    promoted["verifier_evidence"] = [
        e for e in promoted["verifier_evidence"] if e["verdict"] not in {"REJECTED", "REFUSED"}
    ] + [fake_kernel]
    promoted["actions"] = promoted["actions"][
        : len(
            [
                e
                for e in promoted["verifier_evidence"]
                if e["kind"] == "STEP" and e["verdict"] == "ACCEPTED"
            ]
        )
    ]
    promoted["states"] = promoted["states"][: len(promoted["actions"]) + 1]
    promoted = reseal(promoted)
    ok3, err3 = try_load(promoted)
    findings["T3_failed_promoted_to_closed_verified"] = {
        "loads_without_error": ok3,
        "error": err3,
        "horizon_after": promoted["horizon"],
        "original_status": failed[0]["terminal_status"],
    }

    # ---------------------------------------------------------------- T4: evidence not hashed
    tampered = copy.deepcopy(verified[0])
    original_hash = tampered["content_hash"]
    for ev in tampered["verifier_evidence"]:
        if ev["kind"] == "TERMINAL_KERNEL":
            ev["print_axioms"] = "'probe_ANYTHING_AT_ALL' depends on axioms: [SomeMadeUpAxiom]"
    recomputed = VerifiedTrajectory.from_dict(tampered, check_hashes=False).content_hash
    ok4, err4 = try_load(tampered)
    findings["T4_verifier_evidence_outside_content_hash"] = {
        "content_hash_before": original_hash,
        "content_hash_after_evidence_tamper": recomputed,
        "unchanged": original_hash == recomputed,
        "loads_without_error": ok4,
        "error": err4,
        "note": "semantic_core() omits verifier_evidence entirely, so the kernel receipt is unsealed",
    }

    # ---------------------------------------------------------------- T5: stored side-hashes ignored
    side = copy.deepcopy(verified[0])
    side["states_hash"] = "0" * 64
    side["actions_hash"] = "0" * 64
    ok5, err5 = try_load(side)
    findings["T5_states_actions_hash_never_checked"] = {
        "loads_without_error": ok5,
        "error": err5,
        "note": "from_dict validates content_hash only; states_hash/actions_hash are decorative",
    }

    # ---------------------------------------------------------------- T6: horizon fields
    inflated = copy.deepcopy(verified[0])
    inflated["reference_horizon"] = 999
    inflated = reseal(inflated)
    ok6, err6 = try_load(inflated)
    findings["T6_reference_horizon_unbound"] = {
        "loads_without_error": ok6,
        "error": err6,
        "horizon_after": inflated["horizon"],
        "note": (
            "reference_horizon is a caller-supplied int; build_trajectory never checks it against "
            "len(probe.reference_tactics), and observed_trace_length is derived from it"
        ),
    }

    # ---------------------------------------------------------------- T7: action text swap
    swapped = copy.deepcopy(verified[0])
    for action in swapped["actions"]:
        action["tactic"] = "aesop"
        action["tactic_head"] = "aesop"
    swapped = reseal(swapped)
    ok7, err7 = try_load(swapped)
    findings["T7_action_text_swapped_same_count"] = {
        "loads_without_error": ok7,
        "error": err7,
        "note": (
            "action count and state chain preserved; only the tactic strings changed. "
            "_relive replays probe.reference_tactics from the SOURCE record, never "
            "trajectory.actions, so a relive cannot see this"
        ),
    }

    # ------------------------------------------------------- structural verify_bank on forgeries
    structural: dict[str, Any] = {}
    for name, payloads in (
        ("forged_concat", [spliced]),
        ("forged_solver_actor", [relabelled]),
        ("forged_closed_verified", [promoted]),
        ("forged_action_swap", [swapped]),
        ("honest_control", [verified[0]]),
    ):
        directory = write_bank(name, payloads)
        try:
            result = verify_bank(directory, relive=False)
            structural[name] = {
                "passed": result.passed,
                "ok": result.ok,
                "failures": result.failures[:3],
            }
        except Exception as exc:  # noqa: BLE001
            structural[name] = {"passed": False, "exception": f"{type(exc).__name__}: {exc}"}
    findings["T8_verify_bank_structural_verdicts"] = structural

    # ---------------------------------------------------- load_bank over the whole real bank
    try:
        real = load_bank(BANK)
        findings["T9_real_bank_reloads"] = {
            "loaded": len(real),
            "closed_verified": sum(1 for t in real if t.terminal_status.value == "CLOSED_VERIFIED"),
            "all_reference": sorted({a.actor.value for t in real for a in t.actions}),
        }
    except TrajectoryIntegrityError as exc:
        findings["T9_real_bank_reloads"] = {"error": str(exc)}

    (OUT / "trajectory_integrity.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
