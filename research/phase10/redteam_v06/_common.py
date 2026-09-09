"""Shared plumbing for the HC-V0.6 red-team attacks.

Every attack is a standalone script that writes one JSON verdict into ``out/``.  Nothing here
imports the live Lean or Ollama stack; the attacks are offline by construction so that they can
run while the primary assay owns the machine.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "out"
BANK_PATH = ROOT / "artifacts" / "trajectory" / "hc_v0_6_anchor_bank.json"


def emit(name: str, payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"attack": name, "verdict": payload.get("verdict")}, ensure_ascii=False))


def load_bank_dict() -> dict[str, Any]:
    """The frozen bank as raw JSON.  Read-only; the attacks never write to artifacts/."""

    return json.loads(BANK_PATH.read_text(encoding="utf-8"))
