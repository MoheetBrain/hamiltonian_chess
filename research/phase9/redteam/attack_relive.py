"""RED TEAM: does `verify_bank(relive=True)` actually catch the forgeries?

`verify_bank`'s docstring calls relive "the only check that can catch a bank whose evidence was
fabricated wholesale".  This runs it against the four forged banks written by
`attack_trajectory_integrity.py` plus an honest control, with the real Lean toolchain.

Run:  .venv/bin/python research/phase9/redteam/attack_relive.py
Out:  research/phase9/redteam/out/relive.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, verify_bank  # noqa: E402
from arena.trajectory.lean_backend import check_toolchain  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"


def main() -> int:
    report: dict[str, Any] = {"toolchain": check_toolchain().available}
    if not report["toolchain"]:
        (OUT / "relive.json").write_text(json.dumps(report, indent=2) + "\n")
        return 1
    for name in (
        "honest_control",
        "forged_action_swap",
        "forged_solver_actor",
        "forged_concat",
        "forged_closed_verified",
    ):
        directory = OUT / name
        if not (directory / "bank.jsonl").is_file():
            report[name] = {"skipped": "bank not built; run attack_trajectory_integrity.py first"}
            continue
        started = time.monotonic()
        result = verify_bank(directory, relive=True, train_json=DEFAULT_TRAIN_JSON)
        report[name] = {
            "passed": result.passed,
            "checked": result.checked,
            "relived": result.relived,
            "relive_matches": result.relive_matches,
            "failures": [f[:300] for f in result.failures[:4]],
            "wall_s": round(time.monotonic() - started, 1),
        }
        print(name, json.dumps(report[name])[:400], flush=True)
    (OUT / "relive.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
