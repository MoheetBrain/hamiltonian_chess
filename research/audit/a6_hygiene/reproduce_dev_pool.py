"""A6 / Q1+Q18 -- reproduce the V7 DEV probe bank offline and verify dev_pool_hash.

Rebuilds the 864-probe DEV pool from the committed instrument code and the HML_V3 donor
corpus, then compares stable_hash([p.to_dict() ...]) against the dev_pool_hash recorded in
the V7 artifact.  Zero model calls; writes nothing.

Also reports the real provenance funnel (corpus transitions -> eligible -> stratified)
and which mechanisms are backed by real Lean states vs synthesised.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from arena.canonical.schema import stable_hash  # noqa: E402
from arena.environments import formal_structural as fs  # noqa: E402
from arena.experiments import fitness_v5 as v5  # noqa: E402

ART = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")
d = json.load(ART.open())

print("=" * 78)
print("A6  DEV PROBE-BANK REPRODUCTION")
print("=" * 78)

print(f"\nDONOR_REPO = {fs.DONOR_REPO}")
print(f"DONOR_REF  = {fs.DONOR_REF}")
print(f"DONOR_SHA  = {fs.DONOR_SHA}")
print(f"DONOR_ROOT = {fs.DONOR_ROOT}   exists={fs.DONOR_ROOT.exists()}")
print(f"CORPUS_GLOB = {fs.CORPUS_GLOB}")
print(f"SEALED_GLOB = {fs.SEALED_GLOB}  (source_file NAMES only are read)")

sealed_names = fs.sealed_source_files()
print(f"\nHML_V3 sealed holdout source files excluded by name : {len(sealed_names)}")

states = list(fs.load_formal_states())
print(f"formal states loaded from the donor corpus         : {len(states)}")

pool = v5._formal_pool(Path("artifacts"))
print(f"length-fair eligible states after the char budget  : {sum(len(v) for v in pool.values())}")
print(f"  budget = {v5.CONTEXT_GUARD['probe_selection_max_chars_any_surface']} chars, "
      f"max over 8 founder surfaces")
for k in sorted(pool):
    print(f"    stratum {k:8s}: {len(pool[k])} states")

probes = v5.build_dev_pool(Path("artifacts"))
print(f"\nDEV probes rebuilt : {len(probes)}   (artifact records {d['dev_pool_probes']})")

got = stable_hash([p.to_dict() for p in probes])
print(f"\nrecomputed dev_pool_hash : {got}")
print(f"recorded   dev_pool_hash : {d['dev_pool_hash']}")
match = got == d["dev_pool_hash"]
print(f"MATCH: {match}")

# which mechanisms are backed by a real Lean state?
print("\n--- mechanism backing (fitness_v5.py:903-908) ---")
print("  formal_expression_depth : REAL Lean states (pool[stratum][index])")
print("  transitive_dependency   : SYNTHESISED (formal=None, seeded)")
print("  precondition_conjunction: SYNTHESISED (formal=None, seeded)")
by_mech = Counter(p.mechanism for p in probes)
print(f"  probe counts by mechanism: {dict(by_mech)}")

# probe_hash set equality against the artifact
art_hashes = {r["probe_hash"] for r in d["rows"]}
new_hashes = {p.derived_hash for p in probes}
print(f"\nprobe_hash sets identical to the artifact's 864 rows: "
      f"{art_hashes == new_hashes}  "
      f"(rebuilt={len(new_hashes)}, artifact={len(art_hashes)}, "
      f"symmetric difference={len(art_hashes ^ new_hashes)})")

print("\n" + "=" * 78)
print("DEV POOL REPRODUCES BIT-EXACTLY: " + ("YES" if match and art_hashes == new_hashes else "NO"))
print("=" * 78)
sys.exit(0 if match else 1)
