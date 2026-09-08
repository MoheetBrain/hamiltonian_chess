"""Drive the built LeanDojo `lean_dojo_repl` tactic: real interactive, stateful Lean.

This is the option-(a) feasibility test. Each request is {"sid": <state id>, "cmd": "<tactic>"};
the response carries the NEW state id and the pretty-printed tactic state, or an error.
State is persistent inside the Lean process: sid N can be revisited, so the arena can branch.
"""
from __future__ import annotations
import json, subprocess, sys, time, os

MB = "/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
HERE = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HERE, "repl_probe.lean")
man = {m["tag"]: m for m in json.load(open(os.path.join(HERE, "replay_probe_manifest.json")))}
tactics = man["04_RelSeries_smash_castAdd"]["tactics"]

t0 = time.time()
p = subprocess.Popen(["/Users/moheet/.elan/bin/lake", "env", "/Users/moheet/.elan/bin/lean", PROBE],
                     cwd=MB, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True, bufsize=1)

def read_response():
    buf = []
    while True:
        line = p.stdout.readline()
        if not line: return None
        if line.startswith("REPL> "):
            buf.append(line[len("REPL> "):]); break
    # JSON is pretty-printed on one line (width 99999999999999999)
    return json.loads(buf[0])

first = read_response()
print(f"[{time.time()-t0:5.1f}s] REPL ready. initial sid={first.get('sid')}")
print("INITIAL STATE:\n" + (first.get("tacticState") or "")[-500:])
sid = first["sid"]
log = [{"sid": sid, "state": first.get("tacticState")}]
for i, tac in enumerate(tactics):
    p.stdin.write(json.dumps({"sid": sid, "cmd": tac}) + "\n"); p.stdin.flush()
    r = read_response()
    dt = time.time() - t0
    if r.get("error"):
        print(f"[{dt:5.1f}s] step {i} `{tac}` -> ERROR: {r['error'][:200]}"); break
    sid = r["sid"]
    st = r.get("tacticState") or ""
    print(f"[{dt:5.1f}s] step {i} `{tac[:60]}` -> sid={sid} state={'no goals' if st.strip()=='no goals' else st.strip().split(chr(10))[-1][:90]}")
    log.append({"sid": sid, "tactic": tac, "state": st})
# BRANCH TEST: go back to an earlier sid and send a WRONG tactic
if len(log) > 2:
    p.stdin.write(json.dumps({"sid": log[1]["sid"], "cmd": "exact Nat.zero"}) + "\n"); p.stdin.flush()
    r = read_response()
    print(f"[{time.time()-t0:5.1f}s] BRANCH from sid={log[1]['sid']} with a bogus tactic -> "
          f"{'ERROR: ' + (r.get('error') or '')[:140] if r.get('error') else 'sid=' + str(r.get('sid'))}")
p.stdin.write("exit\n"); p.stdin.flush()
try: p.wait(timeout=30)
except Exception: p.kill()
json.dump(log, open(os.path.join(HERE, "repl_session_log.json"), "w"), indent=2)
print(f"total wall {time.time()-t0:.1f}s")
