"""Target 5, stronger than the previous suite: splice two theorems that share an elaboration scope.

`_assert_one_episode`'s scope invariant is the check that refuses the published RT-02 splice.
Its own docstring names the residue: *"two theorems that happen to be declared in byte-identical
scopes are indistinguishable to a record that carries no binding at all"* -- which is every
record in the committed bank (`session_id == "" and problem_id == ""` for all 120 states).

Two theorems in ONE mathlib file are exactly that case.  This builds the pair from the train
split, produces two real trajectories, splices them, and asks each layer in turn.
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
    source_version_from_record,
    verify_bank,
)
from arena.trajectory.lean_backend import LeanToolchainConfig, TacticPolicy  # noqa: E402
from arena.trajectory.schema import VerifiedTrajectory, derive_trajectory_id  # noqa: E402

RESULTS: dict[str, Any] = {}
SCAN = 3000


def reseal(payload: dict[str, Any]) -> dict[str, Any]:
    t = VerifiedTrajectory.from_dict(payload, check_hashes=False)
    payload = copy.deepcopy(payload)
    payload["content_hash"] = t.content_hash
    payload["states_hash"] = t.states_hash
    payload["actions_hash"] = t.actions_hash
    payload["horizon"] = t.horizon.to_dict()
    payload["trajectory_id"] = derive_trajectory_id(t.problem_id, t.content_hash)
    return payload


def main() -> None:
    started = time.monotonic()
    config = LeanToolchainConfig.from_env()
    policy = TacticPolicy.record_only()
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in iter_leandojo_records(DEFAULT_TRAIN_JSON, limit=SCAN):
        tactics = record.get("traced_tactics") or []
        if 1 <= len(tactics) <= 4:
            by_file[str(record.get("file_path"))].append(record)
    pairs = [v for v in by_file.values() if len(v) >= 2]
    RESULTS["scan"] = {
        "records_scanned": SCAN,
        "files_with_two_or_more_short_theorems": len(pairs),
    }
    print(RESULTS["scan"])

    built: list[tuple[dict[str, Any], Any, Any]] = []
    for group in pairs:
        candidates = []
        for record in group[:6]:
            probe = build_probe(record, mathlib_root=config.mathlib_root, policy=policy)
            if probe.ok and probe.probe is not None:
                candidates.append((record, probe.probe))
            if len(candidates) == 2:
                break
        if len(candidates) < 2:
            continue
        driver = ReplayDriver(config=config, policy=policy)
        outcomes = []
        for record, probe in candidates:
            outcome = driver.run(dict(record), probe)
            outcomes.append((record, probe, outcome))
        usable = [o for o in outcomes if o[2].trajectory is not None
                  and len(o[2].trajectory.actions) >= 1]
        if len(usable) == 2:
            scopes = {
                json.dumps(o[2].trajectory.states[0].pp_scope.to_dict(), sort_keys=True)
                for o in usable
            }
            RESULTS["pair"] = {
                "file_path": usable[0][1].file_path,
                "theorems": [o[1].problem_id for o in usable],
                "horizons": [len(o[2].trajectory.actions) for o in usable],
                "terminals": [o[2].terminal_status.value for o in usable],
                "scopes_identical": len(scopes) == 1,
            }
            print(RESULTS["pair"])
            if len(scopes) == 1:
                built = [(o[0], o[1], o[2].trajectory) for o in usable]
                break
    if not built:
        RESULTS["verdict"] = "NOT_CONSTRUCTED"
        RESULTS["note"] = "no same-file pair with identical scopes and >=1 action was built"
        emit("same_file_splice", RESULTS)
        return

    a_payload = built[0][2].to_dict()
    b_payload = built[1][2].to_dict()
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
    # keep A's terminal (its own) so no CLOSED_VERIFIED claim has to be forged
    try:
        spliced = reseal(spliced)
        loaded, error = True, ""
    except Exception as exc:  # noqa: BLE001
        loaded, error = False, f"{type(exc).__name__}: {exc}"[:250]
    RESULTS["splice"] = {
        "loads_without_error": loaded,
        "load_error": error,
        "claimed_horizon": spliced.get("horizon") if loaded else None,
        "component_horizons": [len(a_payload["actions"]), len(b_payload["actions"])],
        "problem_id_kept": spliced["problem_id"],
    }
    print(RESULTS["splice"])
    if loaded:
        directory = OUT / "v05_forged_same_file_concat"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bank.jsonl").write_text(json.dumps(spliced, sort_keys=True) + "\n",
                                              encoding="utf-8")
        structural = verify_bank(directory, relive=False)
        lived = verify_bank(directory, relive=True, config=config, policy=policy)
        RESULTS["verify"] = {
            "structural_passed": structural.passed,
            "structural_failures": structural.failures[:3],
            "relive_passed": lived.passed,
            "relive_failures": [f[:220] for f in lived.failures[:3]],
        }
        RESULTS["verdict"] = (
            "DEFECT" if structural.passed else "HELD_AT_STRUCTURAL"
        )
        print(RESULTS["verify"])
    else:
        RESULTS["verdict"] = "HELD_AT_LOAD"
    RESULTS["wall_s"] = round(time.monotonic() - started, 1)
    emit("same_file_splice", RESULTS)


if __name__ == "__main__":
    main()
