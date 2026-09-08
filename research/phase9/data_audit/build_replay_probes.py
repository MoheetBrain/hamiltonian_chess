"""Build Lean replay probes from LeanDojo train.json fully-chained proofs.

Probe construction (read-only w.r.t. the mathlib checkout):
  probe = source_file[1 .. decl_start-1]        # keeps imports, open/namespace/variable/notation
        + declaration statement
        + `by` block = recorded linear tactic list, `trace_state` after each tactic

Because the file prefix stops BEFORE the declaration, the theorem itself is not in scope:
`exact <its own name>` cannot close the goal. Lean's elaborator is the only oracle; no model.
"""
from __future__ import annotations
import json, os, sys, re

MB = "/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
TRAIN = "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json"
HERE = os.path.dirname(os.path.abspath(__file__))
PROBE_DIR = os.path.join(HERE, "probes")
os.makedirs(PROBE_DIR, exist_ok=True)

WANT = int(sys.argv[1]) if len(sys.argv) > 1 else 10
MINSTEPS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
MAXSTEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 12

def main():
    for old in os.listdir(PROBE_DIR):
        if old.endswith(".lean"): os.remove(os.path.join(PROBE_DIR, old))
    data = json.load(open(TRAIN, encoding="utf-8"))
    picked, manifest = 0, []
    for t in data:
        tt = t.get("traced_tactics") or []
        L = len(tt)
        if not (MINSTEPS <= L <= MAXSTEPS): continue
        if any(tt[i]["state_after"] != tt[i+1]["state_before"] for i in range(L-1)): continue
        if tt[-1]["state_after"] != "no goals": continue
        if any("\n" in s["tactic"] for s in tt): continue
        fp = t["file_path"]
        full = os.path.join(MB, fp)
        if not os.path.exists(full): continue
        lines = open(full, encoding="utf-8").read().split("\n")
        r0, c0 = t["start"]; r1, c1 = t["end"]
        if r0 < 2 or r1 > len(lines): continue
        decl = lines[r0-1:r1]
        decl[-1] = decl[-1][:c1]
        decl[0] = decl[0][c0-1:]
        decl = "\n".join(decl)
        if ":= by" not in decl: continue
        stmt = decl.split(":= by", 1)[0].rstrip()
        if not re.match(r"^(theorem|lemma)\s", stmt): continue
        safe = re.sub(r"[^A-Za-z0-9_]", "_", t["full_name"])
        stmt = re.sub(r"^(theorem|lemma)\s+\S+", "theorem probe_" + safe, stmt, count=1)
        pre = lines[:r0-1]
        # the prefix must not end inside a docstring / attribute / `set_option ... in`
        while pre and (pre[-1].strip() == "" or pre[-1].strip().startswith("@[")
                       or pre[-1].rstrip().endswith(" in") or pre[-1].strip().startswith("/--")
                       or pre[-1].strip().endswith("-/") or pre[-1].strip().startswith("--")):
            if pre[-1].strip().endswith("-/"):
                while pre and not pre[-1].lstrip().startswith("/-"):
                    pre.pop()
                if pre: pre.pop()
                continue
            pre.pop()
        prefix = "\n".join(pre)
        body = "\n".join(f"  {s['tactic']}\n  trace_state" for s in tt)
        probe = prefix + "\n\nset_option maxHeartbeats 1000000 in\n" + stmt + " := by\n" + body + "\n"
        tag = f"{picked:02d}_{safe[:55]}"
        open(os.path.join(PROBE_DIR, f"P_{tag}.lean"), "w", encoding="utf-8").write(probe)
        manifest.append({"tag": tag, "full_name": t["full_name"], "file_path": fp, "n_steps": L,
                         "prefix_lines": len(pre),
                         "tactics": [s["tactic"] for s in tt],
                         "recorded_states": [s["state_before"] for s in tt] + [tt[-1]["state_after"]]})
        picked += 1
        if picked >= WANT: break
    json.dump(manifest, open(os.path.join(HERE, "replay_probe_manifest.json"), "w", encoding="utf-8"), indent=2)
    for m in manifest:
        print(f'{m["tag"]}  steps={m["n_steps"]}  prefix_lines={m["prefix_lines"]}  {m["file_path"]}')
main()
