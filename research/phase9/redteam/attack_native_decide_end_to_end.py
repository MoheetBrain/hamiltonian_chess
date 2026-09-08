"""RED TEAM: the flagship exploit, end to end.

`native_decide` is ALLOWED by the default `record_only` tactic policy.  It closes a decidable
goal in one step by compiling the proposition to native code and running it, and the resulting
declaration depends on `Lean.ofReduceBool` -- an axiom the Lean KERNEL never checks, whose trust
base is the Lean compiler and the machine's C toolchain.

`verify_closed_script` computes `contains_of_reduce_bool` and then does not use it:

    verified=(completed.returncode == 0 and not has_sorry and not errors)

This script carries that all the way to a written bank and runs the project's own
`verify_bank` over it.

Run:  .venv/bin/python research/phase9/redteam/attack_native_decide_end_to_end.py
Out:  research/phase9/redteam/out/native_decide.json
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory import arena_v0  # noqa: E402
from arena.trajectory.arena_v0 import (  # noqa: E402
    LeanTrajectoryArena,
    load_bank,
    verify_bank,
)
from arena.trajectory.lean_backend import (  # noqa: E402
    HEAVY_AUTOMATION,
    LeanTheoremProbe,
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.schema import Actor, PPScope, SourceVersion, TerminalStatus  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    report: dict[str, Any] = {}
    toolchain = check_toolchain()
    if not toolchain.available:
        (OUT / "native_decide.json").write_text(json.dumps({"skipped": toolchain.describe()}))
        return 1
    config = LeanToolchainConfig.from_env()

    default = TacticPolicy.record_only()
    hardened = TacticPolicy.no_heavy_automation()
    report["policy"] = {
        "default_policy_name": default.name,
        "native_decide_under_default": list(default.classify("native_decide")),
        "native_decide_under_no_heavy_automation": list(hardened.classify("native_decide")),
        "native_decide_in_HEAVY_AUTOMATION": "native_decide" in HEAVY_AUTOMATION,
        "bank_manifest_policy": "record_only (artifacts/trajectory_bank_v0/*/manifest.json)",
    }

    probe = LeanTheoremProbe(
        problem_id="redteam::ofReduceBool",
        full_name="redteam.of_reduce_bool",
        safe_name="redteam_of_reduce_bool",
        file_path="<synthetic>",
        statement="theorem probe_redteam_of_reduce_bool : (List.range 200).sum = 19900",
        prefix_text="import Mathlib.Tactic",
        pp_scope=PPScope(),
        reference_tactics=("native_decide",),
    )
    arena = LeanTrajectoryArena(config=config, policy=default, toolchain_report=toolchain)
    arena.reset(probe, hide_reference=probe.reference_tactics)
    step = arena.step("native_decide")
    trajectory = arena.build_trajectory(
        actor=Actor.SOLVER,
        source_version=SourceVersion(
            dataset="redteam",
            license="n/a",
            split="train",
            file_path="<synthetic>",
            full_name="redteam.of_reduce_bool",
        ),
        reference_horizon=1,
    )
    arena.close()

    directory = OUT / "bank_native_decide"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "bank.jsonl").write_text(trajectory.to_json() + "\n", encoding="utf-8")

    reloaded = load_bank(directory / "bank.jsonl")[0]
    structural = verify_bank(directory, relive=False)

    source = inspect.getsource(arena_v0._structural_problems)  # noqa: SLF001
    report["exploit"] = {
        "tactic": "native_decide",
        "terminal_status": step.terminal_status.value,
        "reward": step.reward,
        "kernel_evidence": step.info.get("kernel"),
        "trajectory_terminal": reloaded.terminal_status.value,
        "trajectory_kernel_verified_property": reloaded.kernel_verified,
        "horizon": reloaded.horizon.to_dict(),
        "trust_tier_claimed": reloaded.provenance.trust_tier,
        "bank_verify_passed": structural.passed,
        "bank_verify_failures": structural.failures,
        "bank_horizon_histogram": structural.horizon_histogram,
        "CLOSED_VERIFIED": reloaded.terminal_status is TerminalStatus.CLOSED_VERIFIED,
    }
    report["why_it_gets_through"] = {
        "verify_closed_script_verified_expression": (
            "verified=(completed.returncode == 0 and not has_sorry and not errors)"
        ),
        "contains_of_reduce_bool_used_in_that_expression": False,
        "_structural_problems_mentions_of_reduce_bool": "of_reduce_bool" in source
        or "ofReduceBool" in source,
        "_structural_problems_mentions_sorry_ax": "contains_sorry_ax" in source,
    }
    (OUT / "native_decide.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
