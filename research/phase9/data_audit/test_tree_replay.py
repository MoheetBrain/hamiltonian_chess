"""Can a NON-linear (tree-shaped) recorded proof be replayed as a flat tactic script?

Selects proofs where state_after[i] != state_before[i+1] for some i (i.e. the recorded list is a
traversal of a proof TREE, not a chain) and feeds the flat list to the live Lean REPL in order.
"""
from __future__ import annotations
import json, os, re, subprocess, time

MB="/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
TRAIN="/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json"
HERE=os.path.dirname(os.path.abspath(__file__))

def build(t):
    fp=t["file_path"]; full=os.path.join(MB,fp)
    if not os.path.exists(full): return None
    lines=open(full,encoding="utf-8").read().split("\n")
    r0,c0=t["start"]; r1,c1=t["end"]
    if r0<2 or r1>len(lines): return None
    decl=lines[r0-1:r1]; decl[-1]=decl[-1][:c1]; decl[0]=decl[0][c0-1:]
    decl="\n".join(decl)
    if ":= by" not in decl: return None
    stmt=decl.split(":= by",1)[0].rstrip()
    if not re.match(r"^(theorem|lemma)\s",stmt): return None
    safe=re.sub(r"[^A-Za-z0-9_]","_",t["full_name"])
    stmt=re.sub(r"^(theorem|lemma)\s+\S+","theorem probe_"+safe,stmt,count=1)
    pre=lines[:r0-1]
    while pre and (pre[-1].strip()=="" or pre[-1].strip().startswith("@[")
                   or pre[-1].rstrip().endswith(" in") or pre[-1].strip().startswith("/--")
                   or pre[-1].strip().endswith("-/") or pre[-1].strip().startswith("--")):
        if pre[-1].strip().endswith("-/"):
            while pre and not pre[-1].lstrip().startswith("/-"): pre.pop()
            if pre: pre.pop()
            continue
        pre.pop()
    return "import Lean4Repl\n"+"\n".join(pre)+"\n\nset_option maxHeartbeats 1000000 in\n"+stmt+" := by\n  lean_dojo_repl\n  sorry\n", safe

def replay(probe, tactics):
    p=os.path.join(HERE,"tree_tmp.lean"); open(p,"w",encoding="utf-8").write(probe)
    proc=subprocess.Popen(["/Users/moheet/.elan/bin/lake","env","/Users/moheet/.elan/bin/lean",p],cwd=MB,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    def rd():
        while True:
            l=proc.stdout.readline()
            if not l: return None
            if l.startswith("REPL> "): return json.loads(l[6:])
    first=rd()
    if first is None: proc.kill(); return {"status":"START_FAIL"}
    sid=first["sid"]; done=0; err=None; last=None
    for tac in tactics:
        proc.stdin.write(json.dumps({"sid":sid,"cmd":tac})+"\n"); proc.stdin.flush()
        r=rd()
        if r is None or r.get("error"): err=(r or {}).get("error","(dead)"); break
        sid=r["sid"]; last=r.get("tacticState"); done+=1
    try: proc.stdin.write("exit\n"); proc.stdin.flush(); proc.wait(timeout=20)
    except Exception: proc.kill()
    return {"status":"OK" if err is None else "STEP_ERROR","steps_done":done,
            "n_tactics":len(tactics),"error":(err or "")[:160],"final":(last or "").strip()[:40]}

data=json.load(open(TRAIN,encoding="utf-8"))
cands=[]
for t in data:
    tt=t.get("traced_tactics") or []
    L=len(tt)
    if not (5<=L<=14): continue
    if all(tt[i]["state_after"]==tt[i+1]["state_before"] for i in range(L-1)): continue  # want TREE
    if any("\n" in s["tactic"] for s in tt): continue
    cands.append(t)
    if len(cands)>=8: break

out=[]
for t in cands:
    b=build(t)
    if b is None: continue
    probe,safe=b
    r=replay(probe,[s["tactic"] for s in t["traced_tactics"]])
    r.update({"thm":t["full_name"],"file":t["file_path"]})
    out.append(r); print(json.dumps(r))
json.dump(out,open(os.path.join(HERE,"tree_replay.json"),"w"),indent=2)
ok=sum(1 for r in out if r["status"]=="OK" and r["final"]=="no goals")
print(f"\nTREE-SHAPED proofs replayed as a FLAT tactic script and closed: {ok}/{len(out)}")
