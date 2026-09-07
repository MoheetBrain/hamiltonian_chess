"""A5: rebuild the V7 DEV probe pool offline and verify it against the artifact hash.

Read-only. No model calls. Run:
  python -m research.audit.a5_sel.rebuild_pool
"""
from __future__ import annotations
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.experiments import fitness_v7 as v7            # noqa: E402
from arena.experiments.fitness_v5 import build_dev_pool   # noqa: E402
from arena.canonical.schema import stable_hash                # noqa: E402

ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"

def main() -> int:
    art = json.loads(ART.read_text())
    probes = build_dev_pool(ROOT)
    got = stable_hash([p.to_dict() for p in probes])
    want = art["dev_pool_hash"]
    print(f"rebuilt probes: {len(probes)}  artifact dev_pool_probes: {art['dev_pool_probes']}")
    print(f"rebuilt dev_pool_hash: {got}")
    print(f"artifact dev_pool_hash: {want}")
    print("MATCH" if got == want else "MISMATCH")
    ids = {p.probe_id for p in probes}
    row_ids = {r["probe_id"] for r in art["rows"]}
    print(f"row probe_ids not in rebuilt pool: {len(row_ids - ids)}")
    return 0 if got == want else 1

if __name__ == "__main__":
    raise SystemExit(main())
