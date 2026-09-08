"""Tests for the verified-trajectory arena.

Two tiers:

* everything that does not need Lean runs anywhere and is the bulk of the suite;
* everything that drives a real Lean process is marked ``@pytest.mark.slow`` and skipped with a
  precise reason (including the paths that were checked) when the toolchain or the built oleans
  are absent.  It is skipped, never faked: there is no mock Lean in this package, because a mock
  kernel would verify nothing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from arena.trajectory.lean_backend import (
    LeanTheoremProbe,
    LeanToolchainConfig,
    ToolchainReport,
    build_probe,
    check_toolchain,
    iter_leandojo_records,
)

#: The LeanDojo DEVELOPMENT split.  ``random/{val,test}.json`` and ``novel_premises/{val,test}.json``
#: are sealed and are never opened by anything in this package or its tests.
TRAIN_JSON = Path(
    os.environ.get(
        "HAMILTONIAN_LEANDOJO_TRAIN",
        "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
        "leandojo_raw/leandojo_benchmark_4/random/train.json",
    )
)


def toolchain() -> ToolchainReport:
    return check_toolchain(LeanToolchainConfig.from_env())


def require_lean() -> ToolchainReport:
    """Skip the calling test with the exact missing paths when Lean is not installed."""

    report = toolchain()
    if not report.available:
        pytest.skip(report.describe())
    return report


def require_train_json() -> Path:
    if not TRAIN_JSON.exists():
        pytest.skip(f"LeanDojo development split not present at {TRAIN_JSON}")
    return TRAIN_JSON


@lru_cache(maxsize=8)
def find_probe(
    min_steps: int, max_steps: int, scan: int = 6000
) -> tuple[dict[str, Any], LeanTheoremProbe]:
    """The first buildable probe in file order whose reference proof has the wanted length.

    Deterministic (file order, fixed scan bound), so a Lean test always exercises the same
    theorem on the same machine.  Skips rather than guessing if none is found.
    """

    config = LeanToolchainConfig.from_env()
    for record in iter_leandojo_records(require_train_json(), limit=scan):
        tactics = record.get("traced_tactics") or []
        if not min_steps <= len(tactics) <= max_steps:
            continue
        built = build_probe(record, mathlib_root=config.mathlib_root)
        if built.ok and built.probe is not None:
            return record, built.probe
    pytest.skip(f"no buildable probe with {min_steps}..{max_steps} tactics in the first {scan}")


def fake_mathlib_root(tmp_path: Path, declarations: int = 12) -> tuple[Path, list[dict[str, Any]]]:
    """A tiny stand-in checkout plus matching LeanDojo-shaped records.

    Enough for the offline probe-builder and sampler tests: ``build_probe`` only reads the source
    file, the declaration span and the tactic list, all of which are reproduced faithfully here.
    """

    root = tmp_path / "fake_mathlib"
    records: list[dict[str, Any]] = []
    for index in range(declarations):
        relative = f"Mathlib/Fake/File{index}.lean"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "import Mathlib.Tactic\n"
            "\n"
            "namespace Fake\n"
            "open Nat\n"
            "\n"
            f"theorem fake_{index} (a b : Nat) : a + b = b + a := by\n"
            "  simp [Nat.add_comm]\n"
            "\n"
            "end Fake\n"
        )
        path.write_text(body, encoding="utf-8")
        records.append(
            {
                "url": "https://github.com/leanprover-community/mathlib4",
                "commit": "29dcec074de168ac2bf835a77ef68bbe069194c5",
                "file_path": relative,
                "full_name": f"Fake.fake_{index}",
                "start": [6, 1],
                "end": [7, 22],
                "traced_tactics": [
                    {
                        "tactic": f"step_{step} h{index}",
                        "annotated_tactic": [f"step_{step} h{index}", []],
                        "state_before": f"a b : Nat\n⊢ goal {index} at {step}",
                        "state_after": f"a b : Nat\n⊢ goal {index} at {step + 1}",
                    }
                    for step in range(6)
                ],
            }
        )
    return root, records
