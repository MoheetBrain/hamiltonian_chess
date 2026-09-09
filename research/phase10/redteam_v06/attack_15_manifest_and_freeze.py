"""A15 -- the manifest's own guarantees, and whether the running code is the frozen code.

M1  spec §13: "a served model digest does not match the manifest" -> RESULT_INVALID.  What does
    ``build_manifest`` do when ``verify_served()`` raises?
M2  what happens to the manifest and the cell file when the table itself is invalid?
M3  is the code that is executing the run the code that was frozen at 2624be5?
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import ROOT, emit  # noqa: E402

from arena.experiments.hc_v0_6.schema import Arm  # noqa: E402
from arena.experiments.hc_v0_6_assay import AssayRun, build_manifest  # noqa: E402
from arena.trajectory.solver import ScriptedSolver, SolverIdentityMismatch  # noqa: E402
from tests.trajectory.test_anchor import make_anchor, make_bank  # noqa: E402

FROZEN_COMMIT = "2624be5"
FROZEN_FILES = (
    "arena/experiments/hc_v0_6_assay.py",
    "arena/experiments/hc_v0_6/schema.py",
    "arena/experiments/hc_v0_6/estimators.py",
    "arena/experiments/hc_v0_6/calibration.py",
    "arena/experiments/hc_v0_6/power.py",
    "arena/trajectory/anchor.py",
    "arena/trajectory/representation.py",
    "arena/trajectory/solver.py",
    "docs/HC_V0_6_SPEC.md",
)


class MismatchingSolver(ScriptedSolver):
    def verify_served(self):  # noqa: ANN201
        raise SolverIdentityMismatch(
            "the served model does not match the recorded solver identity; refusing to run "
            "(model_digest: recorded='aaa' served='bbb')"
        )


def main() -> int:
    findings: dict[str, Any] = {}
    bank = make_bank([make_anchor()])

    # --- M1 ------------------------------------------------------------------------------------
    manifest = build_manifest(
        AssayRun(),
        bank=bank,
        solver=MismatchingSolver(default="skip"),
        arms=tuple(Arm),
        replicates=1,
        seed=1,
    )
    findings["M1_manifest_built_despite_digest_mismatch"] = True
    findings["M1_served_verification_field"] = manifest["solver_served_verification"]
    findings["M1_field_is_truncated_to"] = 200
    findings["M1_any_status_flag_saying_invalid"] = [
        k for k in manifest if "invalid" in k.lower() or "valid" in k.lower()
    ]
    findings["M1_scientific_status"] = manifest["scientific_status"]

    # --- M2 ------------------------------------------------------------------------------------
    findings["M2_note"] = (
        "main() calls build_manifest(run, ...) and then run.table.write_jsonl(). Both go through "
        "AssayRun.table = CellTable(rows), which raises DesignViolation on a duplicate cell or an "
        "anchor carrying two identities. The streamed file survives (it is written per row), but "
        "the manifest is never written, so a structurally invalid run leaves cells with no "
        "manifest and no result_hash."
    )

    # --- M3 ------------------------------------------------------------------------------------
    diffs: dict[str, int] = {}
    for path in FROZEN_FILES:
        out = subprocess.run(
            ["git", "diff", "--numstat", FROZEN_COMMIT, "--", path],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        line = out.stdout.strip()
        diffs[path] = int(line.split("\t")[0]) + int(line.split("\t")[1]) if line else 0
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "arena", "docs"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    ).stdout.split()
    findings["M3_lines_changed_since_the_freeze"] = diffs
    findings["M3_untracked_modules_under_arena_or_docs"] = untracked
    findings["M3_running_process"] = subprocess.run(
        ["bash", "-c", "ps -o lstart=,command= -p $(pgrep -f hc_v0_6_assay | head -1) 2>/dev/null"],
        capture_output=True,
        text=True,
    ).stdout.strip()

    emit(
        "attack_15_manifest_and_freeze",
        {
            "attack": "A15 manifest guarantees and freeze integrity",
            "verdict": "BROKEN",
            "findings": findings,
            "note": (
                "A digest mismatch is recorded as a 200-character string in a field named "
                "solver_served_verification and nothing reads it; the manifest still carries "
                "scientific_status PREREGISTERED_ASSAY_RESULT_SET and a result_hash. Spec §13 "
                "makes that condition RESULT_INVALID, and no code enforces it."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
