"""A9: materialise the V7/V5 development probe bank once and cache it.

READ-ONLY with respect to the repository: writes only into the scratchpad cache path
given on the command line.  Makes ZERO model calls -- ``build_dev_pool`` is a pure
function of the donor corpus and the frozen generator code.

Usage:
    python -m research.audit.a9_causal.build_bank <cache.pkl>
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

from arena.experiments.fitness_v5 import build_dev_pool


def main() -> int:
    out = Path(sys.argv[1])
    start = time.time()
    probes = build_dev_pool(Path("."))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as handle:
        pickle.dump(probes, handle)
    print(f"probes={len(probes)} elapsed={time.time() - start:.1f}s -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
