"""Target 5: the RT-02 fix is bypassed by OMITTING the optional session binding.

`BackendStateEnvelope.session_id`/`problem_id` default to `""` and the schema documents that as
"an absent field is an absent claim" -- so records written before the binding existed keep their
hashes.  `semantic_core()` includes those keys ONLY when they are non-empty, so deleting them is
not a hash violation: it is a *different, older-shaped record* that reseals cleanly.

With the binding gone, `_assert_one_episode` falls back to the scope invariant alone, and two
theorems declared in ONE mathlib file share their scope byte for byte.
"""

from __future__ import annotations

import copy
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import OUT, emit  # noqa: E402

from arena.trajectory.arena_v0 import (  # noqa: E402
    DEFAULT_TRAIN_JSON,
    ReplayDriver,
    build_probe,
    iter_leandojo_records,
    verify_bank,
)
from arena.trajectory.lean_backend import LeanToolchainConfig, TacticPolicy  # noqa: E402
from arena.trajectory.schema import VerifiedTrajectory, derive_trajectory_id  # noqa: E402

RESULTS: dict[str, Any] = {}


def reseal(payload: dict[str, Any]) -> dict[str, Any]:
    t = VerifiedTrajectory.from_dict(payload, check_hashes=False)
    payload = copy.deepcopy(payload)
    payload["content_hash"] = t.content_hash
    payload["states_hash"] = t.states_hash
    payload["actions_hash"] = t.actions_hash
    payload["horizon"] = t.horizon.to_dict()
    payload["trajectory_id"] = derive_trajectory_id(t.problem_id, t.content_hash)
    return payload


def delegitimise(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn a modern record into a legacy-shaped one by dropping the optional bindings."""

    payload = copy.deepcopy(payload)
    for state in payload["states"]:
        state["session_id"] = ""
        state["problem_id"] = ""
        state["envelope_id"] = (
            f"{state['backend_native']['kind']}:{state['state_id']}:"
            f"{state['backend_native']['pp_sha256'][:32]}"
        )
    return payload


def main() -> None:
    started = time.monotonic()
    config = LeanToolchainConfig.from_env()
    policy = TacticPolicy.record_only()
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in iter_leandojo_records(DEFAULT_TRAIN_JSON, limit=3000):
        tactics = record.get("traced_tactics") or []
        if 1 <= len(tactics) <= 4:
            by_file[str(record.get("file_path"))].append(record)

    built = None
    for group in (v for v in by_file.values() if len(v) >= 2):
        driver = ReplayDriver(config=config, policy=policy)
        made = []
        for record in group[:5]:
            result = build_probe(record, mathlib_root=config.mathlib_root, policy=policy)
            if not result.ok or result.probe is None:
                continue
            probe = result.probe
            outcome = driver.run(dict(record), probe)
            if outcome.trajectory is not None and len(outcome.trajectory.actions) >= 1:
                made.append((probe, outcome.trajectory))
            if len(made) == 2:
                break
        if len(made) == 2:
            scopes = {
                json.dumps(t.states[0].pp_scope.to_dict(), sort_keys=True) for _, t in made
            }
            if len(scopes) == 1:
                built = made
                break
    if built is None:
        RESULTS["verdict"] = "NOT_CONSTRUCTED"
        emit("legacy_splice", RESULTS)
        return

    a_payload = delegitimise(built[0][1].to_dict())
    b_payload = delegitimise(built[1][1].to_dict())
    RESULTS["pair"] = {
        "file_path": built[0][0].file_path,
        "theorem_a": built[0][1].problem_id,
        "theorem_b": built[1][1].problem_id,
        "horizon_a": len(built[0][1].actions),
        "horizon_b": len(built[1][1].actions),
        "terminal_a": built[0][1].terminal_status.value,
        "terminal_b": built[1][1].terminal_status.value,
        "scopes_identical": True,
    }

    spliced = copy.deepcopy(a_payload)
    next_sid = len(a_payload["states"])
    for state in b_payload["states"][1:]:
        state = copy.deepcopy(state)
        state["index"] = next_sid
        state["state_id"] = str(next_sid)
        state["envelope_id"] = (
            f"{state['backend_native']['kind']}:{next_sid}:"
            f"{state['backend_native']['pp_sha256'][:32]}"
        )
        spliced["states"].append(state)
        next_sid += 1
    prev = a_payload["states"][-1]["state_id"]
    aid = len(a_payload["actions"])
    step_ev = [
        e for e in b_payload["verifier_evidence"]
        if e["kind"] == "STEP" and e["verdict"] == "ACCEPTED"
    ]
    for offset, action in enumerate(copy.deepcopy(b_payload["actions"])):
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
        loaded, error = True, ""
    except Exception as exc:  # noqa: BLE001
        loaded, error = False, f"{type(exc).__name__}: {exc}"[:250]
    RESULTS["splice"] = {
        "loads_without_error": loaded,
        "load_error": error,
        "claimed_horizon": spliced.get("horizon") if loaded else None,
    }
    if loaded:
        directory = OUT / "v05_forged_legacy_shaped_concat"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bank.jsonl").write_text(
            json.dumps(spliced, sort_keys=True) + "\n", encoding="utf-8"
        )
        structural = verify_bank(directory, relive=False)
        lived = verify_bank(directory, relive=True, config=config, policy=policy)
        RESULTS["verify"] = {
            "structural_passed": structural.passed,
            "structural_failures": structural.failures[:2],
            "relive_passed": lived.passed,
            "relive_failures": [f[:200] for f in lived.failures[:2]],
        }
        RESULTS["verdict"] = "DEFECT" if structural.passed else "HELD_AT_STRUCTURAL"
    else:
        RESULTS["verdict"] = "HELD_AT_LOAD"
    RESULTS["note"] = (
        "the session binding is OPTIONAL; dropping it is legal by the schema's own rule that an "
        "absent field is an absent claim, and it downgrades _assert_one_episode to the scope "
        "invariant, which two theorems in one file satisfy"
    )
    RESULTS["wall_s"] = round(time.monotonic() - started, 1)
    emit("legacy_splice", RESULTS)


if __name__ == "__main__":
    main()
