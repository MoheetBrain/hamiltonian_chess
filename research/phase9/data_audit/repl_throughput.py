"""Throughput + anti-cheat measurement for the lean_dojo_repl arena backend."""
from __future__ import annotations
import json, subprocess, time, os, re, sys

MB="/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4"
HERE=os.path.dirname(os.path.abspath(__file__))
man=json.load(open(os.path.join(HERE,"replay_probe_manifest.json")))
ok_tags=[m for m in man if os.path.exists(os.path.join(HERE,"probe_out",f"P_{m['tag']}.out"))
         and "error:" not in open(os.path.join(HERE,"probe_out",f"P_{m['tag']}.err"),encoding="utf-8").read()]

def make_repl_probe(tag):
    src=open(os.path.join(HERE,"probes",f"P_{tag}.lean"),encoding="utf-8").read()
    head,rest=src.split("set_option maxHeartbeats 1000000 in\n",1)
    stmt=rest.split(":= by\n",1)[0]
    return "import Lean4Repl\n"+head+"\nset_option maxHeartbeats 1000000 in\n"+stmt+":= by\n  lean_dojo_repl\n  sorry\n"

def run(tag, tactics, extra=None):
    path=os.path.join(HERE,"repl_tmp.lean"); open(path,"w",encoding="utf-8").write(make_repl_probe(tag))
    t0=time.time()
    p=subprocess.Popen(["/Users/moheet/.elan/bin/lake","env","/Users/moheet/.elan/bin/lean",path],cwd=MB,
                       stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    def rd():
        while True:
            l=p.stdout.readline()
            if not l: return None
            if l.startswith("REPL> "): return json.loads(l[6:])
    first=rd()
    if first is None:
        p.kill(); return {"tag":tag,"status":"REPL_START_FAIL"}
    t_start=time.time()-t0
    sid=first["sid"]; steps=[]; err=None
    tt0=time.time()
    for tac in tactics:
        p.stdin.write(json.dumps({"sid":sid,"cmd":tac})+"\n"); p.stdin.flush()
        r=rd()
        if r is None or r.get("error"): err=(r or {}).get("error","(dead)"); break
        sid=r["sid"]; steps.append(r.get("tacticState"))
    t_steps=time.time()-tt0
    cheat=None
    if extra:
        p.stdin.write(json.dumps({"sid":0,"cmd":extra})+"\n"); p.stdin.flush()
        r=rd(); cheat={"cmd":extra,"error":(r or {}).get("error"),"state":(r or {}).get("tacticState")}
    try:
        p.stdin.write("exit\n"); p.stdin.flush(); p.wait(timeout=20)
    except Exception: p.kill()
    return {"tag":tag,"status":"OK" if err is None else "STEP_ERROR","error":err,
            "startup_s":round(t_start,2),"steps_s":round(t_steps,3),"n_steps":len(steps),
            "terminal":(steps[-1] or "").strip() if steps else None,"cheat":cheat}

res=[]
for m in ok_tags[:6]:
    r=run(m["tag"], m["tactics"], extra="sorry" if m is ok_tags[0] else None)
    r["file"]=m["file_path"]; r["prefix_lines"]=m["prefix_lines"]
    res.append(r); print(json.dumps({k:v for k,v in r.items() if k!="cheat"}))
    if r.get("cheat"): print("  SORRY-CHEAT PROBE ->", json.dumps(r["cheat"])[:300])
json.dump(res,open(os.path.join(HERE,"repl_throughput.json"),"w"),indent=2)
oks=[r for r in res if r["status"]=="OK"]
if oks:
    print(f"\nstartup: min={min(r['startup_s'] for r in oks)}s max={max(r['startup_s'] for r in oks)}s "
          f"mean={sum(r['startup_s'] for r in oks)/len(oks):.2f}s")
    tot=sum(r['n_steps'] for r in oks); tsec=sum(r['steps_s'] for r in oks)
    print(f"tactic steps: {tot} in {tsec:.3f}s -> {tot/max(tsec,1e-9):.1f} steps/s once the process is warm")
