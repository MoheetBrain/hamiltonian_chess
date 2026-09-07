"""A6 / Q7 -- does module-identifying content reach the V7 prompt?

Measures the global mathlib symbol names carried in the 104 length-fair states, and whether a
state's symbol-set determines its originating mathlib source file. Also checks directly whether
the theorem name or Lean path appears in a rendered prompt. No model call.
"""
from __future__ import annotations
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from arena.experiments import fitness_v5 as v5  # noqa: E402

pool = v5._formal_pool(Path("artifacts"))
states = [s for b in pool.values() for s in b]
print(f"length-fair states: {len(states)}")


def walk(e, out: set[str], kind: str) -> None:
    if getattr(e, "op", None) == f"lean.{kind}" and getattr(e, "value", None) is not None:
        out.add(str(e.value))
    for c in getattr(e, "args", ()) or ():
        walk(c, out, kind)


sym_sets: dict[str, frozenset[str]] = {}
allsym: Counter[str] = Counter()
loc: Counter[str] = Counter()
for st in states:
    o: set[str] = set()
    walk(st.target, o, "symbol")
    sym_sets[st.item_id] = frozenset(o)
    allsym.update(o)
    l: set[str] = set()
    walk(st.target, l, "local_reference")
    loc.update(l)

print(f"distinct GLOBAL mathlib symbols across the bank : {len(allsym)}")
print(f"mean distinct symbols per state                 : "
      f"{sum(len(v) for v in sym_sets.values()) / len(sym_sets):.2f}")
print(f"top symbols: {allsym.most_common(10)}")
print(f"distinct LOCAL reference names (pseudonymised?) : {len(loc)} "
      f"e.g. {sorted(loc)[:8]}")

src = {st.item_id: st.source_file for st in states}
byset: dict[frozenset[str], set[str]] = defaultdict(set)
for k, v in sym_sets.items():
    byset[v].add(src[k])
uniq = sum(1 for v in byset.values() if len(v) == 1)
print(f"\ndistinct symbol-sets: {len(byset)}; mapping to exactly ONE source file: {uniq}"
      f"  ({uniq / len(byset):.1%})")
empty = sum(1 for v in sym_sets.values() if not v)
print(f"states whose target carries NO global symbol: {empty}")

# does any identifying string reach the prompt?
probes = v5.build_dev_pool(Path("artifacts"))
fed = [p for p in probes if p.mechanism == "formal_expression_depth"]
founders = {g.candidate_id: g for g in v5.v5_founders()}
g = founders.get("V5E_L3_JSON_AST") or list(founders.values())[0]
bad_name = bad_path = bad_mathlib = 0
for p in fed:
    pr = v5.build_prompt(g, p)
    oc = getattr(p, "oracle_record", None) or {}
    tid = oc.get("theorem_id")
    if tid and tid in pr:
        bad_name += 1
    if ".lean" in pr:
        bad_path += 1
    if "Mathlib" in pr:
        bad_mathlib += 1
print(f"\nover {len(fed)} formal_expression_depth prompts:")
print(f"  theorem_id appears in prompt : {bad_name}")
print(f"  '.lean' appears in prompt    : {bad_path}")
print(f"  'Mathlib' appears in prompt  : {bad_mathlib}")
