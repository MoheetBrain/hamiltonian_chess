"""A6 / Q9-Q11 -- cross-check the 864 artifact rows against the surviving live cache.

For every surviving cache file under artifacts/cache/fitness_v7/:
  * confirm its `identity` hashes to its own filename (the path IS the identity hash);
  * match it to an artifact row by probe_hash / Q0 case;
  * confirm the stored raw response is BYTE-IDENTICAL to the row's recorded raw_output;
  * confirm every identity field agrees with the row.
Then report exactly which rows have no surviving cache entry.

No model call, no arena import beyond the canonical hash primitive.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from arena.canonical.schema import stable_hash  # noqa: E402  (hash primitive only)

ART = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")
CACHE = Path("artifacts/cache/fitness_v7")

d = json.load(ART.open())
rows = d["rows"]
q0_rows = d["q0"]["rows"]

by_probe = {r["probe_hash"]: r for r in rows}
assert len(by_probe) == len(rows), "probe_hash not unique -- join would be ambiguous"

files = sorted(CACHE.glob("*.json"))
print("=" * 78)
print("A6  CACHE <-> ARTIFACT CRYPTOGRAPHIC CROSS-CHECK")
print("=" * 78)
print(f"\nsurviving cache files : {len(files)}")
print(f"artifact rows         : {len(rows)}   q0 rows: {len(q0_rows)}")

path_ok = resp_ok = ident_ok = 0
bad_path: list[str] = []
bad_resp: list[str] = []
bad_ident: list[str] = []
matched_probe: set[str] = set()
q0_seen = 0
orphans: list[str] = []

IDENT_FIELDS = ("experiment_version", "instrument_version", "solver_kind", "model_digest",
                "model_template_hash", "runtime_condition", "runtime_hash", "decoding_hash",
                "candidate_id", "genome_hash", "task_id", "probe_hash", "prompt_hash",
                "prompt_bytes_sha256")

for f in files:
    rec = json.loads(f.read_text())
    ident = rec["identity"]
    # 1. the filename must be the hash of the identity
    if stable_hash(dict(ident)) == f.stem:
        path_ok += 1
    else:
        bad_path.append(f.name)
    if ident.get("kind") == "Q0":
        q0_seen += 1
        continue
    ph = ident.get("probe_hash")
    row = by_probe.get(ph)
    if row is None:
        orphans.append(f.name)
        continue
    matched_probe.add(ph)
    # 2. byte-identical model output
    if rec["result"].get("response") == row["raw_output"]:
        resp_ok += 1
    else:
        bad_resp.append(f.name)
    # 3. every identity field agrees with the row
    if all(ident.get(k) == row.get(k) for k in IDENT_FIELDS):
        ident_ok += 1
    else:
        diff = [k for k in IDENT_FIELDS if ident.get(k) != row.get(k)]
        bad_ident.append(f"{f.name}: {diff}")

print(f"\n[1] filename == stable_hash(identity) : {path_ok}/{len(files)} OK"
      f"   mismatches={len(bad_path)}")
print(f"[2] cached response == row.raw_output : {resp_ok}/{len(matched_probe)} OK"
      f"   mismatches={len(bad_resp)}")
print(f"[3] all identity fields == row fields : {ident_ok}/{len(matched_probe)} OK"
      f"   mismatches={len(bad_ident)}")
print(f"[4] orphan cache entries (no matching row) : {len(orphans)}")
print(f"[5] surviving Q0 cache entries : {q0_seen} (artifact records {len(q0_rows)} Q0 rows)")
for label, lst in (("BAD PATH", bad_path), ("BAD RESPONSE", bad_resp),
                   ("BAD IDENTITY", bad_ident), ("ORPHAN", orphans)):
    for x in lst[:10]:
        print(f"    {label}: {x}")

missing = [r for r in rows if r["probe_hash"] not in matched_probe]
print(f"\n[6] ROWS WITH NO SURVIVING CACHE ENTRY : {len(missing)}")
cells = Counter((r["mechanism"], r["level"]) for r in missing)
for k, v in sorted(cells.items()):
    print(f"      {k[0]} L{k[1]}: {v} of 72 lost")
print(f"      variants of lost rows: {dict(Counter(r['variant'] for r in missing))}")
print(f"      lost rows all FRESH  : {all(r['cache_scope'] == 'FRESH' for r in missing)}")
print(f"      lost rows all cache_hit=False : {all(not r['cache_hit'] for r in missing)}")

print(f"\n[7] ARITHMETIC: {len(files)} cache files"
      f" = {len(matched_probe)} probe entries + {q0_seen} Q0 entries")
print(f"    {len(matched_probe)} matched + {len(missing)} lost = {len(rows)} rows")
print(f"    {len(rows)} rows + {len(q0_rows)} Q0 = {len(rows) + len(q0_rows)}"
      f" = planned_model_calls ({d['planned_model_calls']})")

clean = not (bad_path or bad_resp or bad_ident or orphans)
print("\n" + "=" * 78)
print("SURVIVING CACHE CORROBORATES THE ARTIFACT EXACTLY: " + ("YES" if clean else "NO"))
print("=" * 78)
sys.exit(0 if clean else 1)
