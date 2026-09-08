"""RED TEAM / attack class 7: the Lean kernel path.

Everything downstream trusts `TerminalStatus.CLOSED_VERIFIED`.  This script attacks the two
things that produce it: `TacticPolicy.classify` (the pre-backend refusal) and
`verify_closed_script` (the "closure authority", a fresh `lake env lean` process).

Each probe is a SYNTHETIC `LeanTheoremProbe` built here, so the attacks are reproducible without
reading the 373 MB split.  Nothing under `arena/` is edited; where a library guard must be
bypassed to test the layer behind it, the bypass is a local subclass in this file.

Run:  .venv/bin/python research/phase9/redteam/attack_lean_kernel.py
Out:  research/phase9/redteam/out/lean_kernel.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory.arena_v0 import LeanTrajectoryArena  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanReplSession,
    LeanTheoremProbe,
    LeanToolchainConfig,
    TacticDecision,
    TacticPolicy,
    check_toolchain,
    verify_closed_script,
)
from arena.trajectory.schema import PPScope, TerminalStatus  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

MATHLIB_IMPORT = "import Mathlib.Tactic"


class NullPolicy(TacticPolicy):
    """A policy that refuses NOTHING.

    Exists only to reach the layer *behind* `ALWAYS_REFUSED`: if the Python guard is the only
    thing stopping `sorry`, that is a very different security story from the backend refusing it
    too.  This is a local subclass, not an edit to the package.
    """

    def classify(self, tactic: str) -> tuple[TacticDecision, str]:
        return TacticDecision.ALLOWED, ""


def probe(name: str, statement_body: str, *, imports: str = MATHLIB_IMPORT) -> LeanTheoremProbe:
    return LeanTheoremProbe(
        problem_id=f"redteam::{name}",
        full_name=f"redteam.{name}",
        safe_name=f"redteam_{name}",
        file_path="<synthetic-redteam-probe>",
        statement=f"theorem probe_redteam_{name} {statement_body}",
        prefix_text=imports,
        pp_scope=PPScope(),
        reference_tactics=(),
    )


def kv(config: LeanToolchainConfig, p: LeanTheoremProbe, tactics: list[str]) -> dict[str, Any]:
    started = time.monotonic()
    result = verify_closed_script(p, tactics, config=config)
    payload = result.to_dict()
    payload["wall_s"] = round(time.monotonic() - started, 1)
    payload["errors"] = payload["errors"][:400]
    payload["tactics"] = tactics
    return payload


def main() -> int:
    report: dict[str, Any] = {
        "attack_suite_version": "hc-v0-redteam-2026-09-08",
        "target": "arena/trajectory/lean_backend.py",
        "findings": {},
    }
    toolchain = check_toolchain()
    report["toolchain"] = {
        "available": toolchain.available,
        "lean": toolchain.lean_version_string,
        "toolchain": toolchain.toolchain,
    }
    if not toolchain.available:
        report["findings"]["ABORTED"] = toolchain.describe()
        (OUT / "lean_kernel.json").write_text(json.dumps(report, indent=2) + "\n")
        return 1
    config = LeanToolchainConfig.from_env()

    # ---- K1: does TacticPolicy actually stop every sorry spelling? (static, no Lean) ----
    policy = TacticPolicy.record_only()
    spellings = [
        "sorry",
        "admit",
        "stop",
        "exact sorryAx _ _",
        "exact @sorryAx _ _ true",
        "all_goals sorry",
        "first | rfl | sorry",
        "exact (by sorry : True)",
        "«sorry»",
        "have h : True := by sorry",
        # near-misses that must NOT be refused (over-blocking check)
        "exact hsorry",
        "simp [Nat.stop_eq]",
        "exact admitted_lemma",
        # the interesting ones: unsound-ish but not spelled `sorry`
        "native_decide",
        "decide",
        "exact?",
        "apply?",
        "aesop",
    ]
    report["findings"]["K1_policy_classify"] = {
        tactic: list(policy.classify(tactic)) for tactic in spellings
    }

    # ---- K2/K3: sorry through the REAL backend, with the Python guard removed ----
    triv = probe("triv", ": (2 : Nat) + 2 = 4")
    behind_guard: dict[str, Any] = {}
    for tactic in ("sorry", "admit", "stop"):
        session = LeanReplSession(triv, config=config, policy=NullPolicy())
        start = session.start()
        if not start.ok:
            behind_guard[tactic] = {"start_failed": (start.error or "")[:300]}
            session.close()
            continue
        result = session.step(session.root_state_id, tactic)
        behind_guard[tactic] = {
            "outcome": result.outcome.value,
            "error": (result.error or "")[:200],
            "tactic_state": (result.tactic_state or "")[:120],
            "closed_flag": result.closed,
        }
        session.close()
    report["findings"]["K2_repl_behind_the_python_guard"] = behind_guard

    # kernel authority handed the forbidden tactics directly (no policy in the path at all)
    report["findings"]["K3_verify_closed_script_with_sorry"] = kv(config, triv, ["sorry"])

    # ---- K4: native_decide -> Lean.ofReduceBool.  Is `verified` still True? ----
    nd = probe("nd", ": (List.range 20).sum = 190")
    report["findings"]["K4a_native_decide_kernel"] = kv(config, nd, ["native_decide"])
    report["findings"]["K4b_decide_kernel"] = kv(config, nd, ["decide"])
    report["findings"]["K4c_honest_kernel"] = kv(config, nd, ["rfl"])

    # ---- K4d: the same through the WHOLE arena, which is what sets CLOSED_VERIFIED ----
    arena = LeanTrajectoryArena(config=config, policy=TacticPolicy.record_only())
    arena.reset(nd)
    step = arena.step("native_decide")
    report["findings"]["K4d_arena_native_decide"] = {
        "terminal_status": step.terminal_status.value,
        "reward": step.reward,
        "kernel": step.info.get("kernel", {}),
        "CLOSED_VERIFIED": step.terminal_status is TerminalStatus.CLOSED_VERIFIED,
    }
    arena.close()

    # ---- K5: does the kernel check notice a proof of a DIFFERENT theorem? ----
    # `#print axioms` is emitted for probe.probe_name.  Build a probe whose *statement* is
    # trivial while the problem_id claims a hard theorem: nothing binds the two.
    liar = LeanTheoremProbe(
        problem_id="Mathlib/Analysis/Hard.lean::Hard.deep_theorem",
        full_name="Hard.deep_theorem",
        safe_name="redteam_liar",
        file_path="Mathlib/Analysis/Hard.lean",
        statement="theorem probe_redteam_liar : True",
        prefix_text=MATHLIB_IMPORT,
        pp_scope=PPScope(),
        reference_tactics=(),
    )
    report["findings"]["K5_statement_not_bound_to_problem_id"] = kv(config, liar, ["trivial"])

    # ---- K6: forged / replayed session state ids ----
    session = LeanReplSession(triv, config=config, policy=TacticPolicy.record_only())
    start = session.start()
    sid_probe: dict[str, Any] = {"start_ok": start.ok}
    if start.ok:
        forged = session.step("31337", "rfl")
        sid_probe["forged_sid"] = {
            "outcome": forged.outcome.value,
            "error": (forged.error or "")[:160],
        }
        first = session.step(session.root_state_id, "norm_num")
        sid_probe["first_step"] = {"outcome": first.outcome.value, "to": first.to_state_id}
        # replay the ROOT after advancing: legal branching, but is it recorded?
        replayed = session.step(session.root_state_id, "rfl")
        sid_probe["replay_root_after_advance"] = {
            "outcome": replayed.outcome.value,
            "to": replayed.to_state_id,
            "note": "a second child of the root; the session allows out-of-order re-entry by design",
        }
        sid_probe["step_log_len"] = len(session.step_log)
    session.close()
    report["findings"]["K6_sid_chain"] = sid_probe

    # ---- K7: does arena.branch() actually rewind where the next step lands? ----
    arena2 = LeanTrajectoryArena(
        config=config, policy=TacticPolicy.record_only(), attempt_budget=10
    )
    obs0 = arena2.reset(probe("branch", ": 1 + 1 = 2 ∧ 2 + 2 = 4"))
    s1 = arena2.step("constructor")
    root_id = obs0.state_id
    branch_obs = arena2.branch(root_id)
    s2 = arena2.step("norm_num")
    report["findings"]["K7_branch_semantics"] = {
        "root_state_id": root_id,
        "after_step1_state_id": s1.observation.state_id,
        "branch_returned_state_id": branch_obs.state_id,
        "next_step_applied_from": arena2.states[-2].state_id if len(arena2.states) >= 2 else None,
        "next_step_outcome": s2.info.get("outcome"),
        "expected_if_branch_rewound": root_id,
        "branch_is_cosmetic": branch_obs.state_id == root_id
        and (arena2.states[-2].state_id != root_id if len(arena2.states) >= 2 else False),
    }
    arena2.close()

    (OUT / "lean_kernel.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["findings"], indent=2, ensure_ascii=False)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
