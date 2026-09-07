"""Exploratory dump: what does the NEXT_ACTION observation contain, and what is the target?"""
from __future__ import annotations
import json
from arena.tasks.generators.world_v0 import generate_tasks
from arena.languages.registry import SEED_LANGUAGES
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.training.render_dataset import render_next_action_example

ARMS = ("L0_STRUCTURED_ENGLISH","L1_CURRENT_HML","L2_SEXPR","L3_JSON_AST","L5_COMPACT_SYMBOLIC")
langs = {l.candidate_id: l for l in SEED_LANGUAGES}
print("registered candidate ids:", sorted(langs))

tasks = generate_tasks(total=676, seed=0)
print("n tasks:", len(tasks))

t = tasks[0]
traj = t.trajectory
tr = traj.transitions[0]
sb = tr.state_before
obs = project_state_for_observation(sb, ObservationKind.NEXT_ACTION)

print("\n=== state_before.state_id ===", sb.state_id)
print("=== action.action_id     ===", tr.action.action_id)
print("\n=== FIELDS STRIPPED BY PROJECTION ===")
import dataclasses
for f in dataclasses.fields(sb):
    a = getattr(sb, f.name); b = getattr(obs, f.name)
    print(f"  {f.name:32s} same={a==b}  before={str(a)[:60]!r} after={str(b)[:60]!r}")

print("\n=== PROJECTED OBSERVATION (canonical dict) ===")
print(json.dumps(obs.to_dict(), indent=1, sort_keys=True)[:3000])

print("\n=== TARGET (action.to_dict) ===")
print(json.dumps(tr.action.to_dict(), indent=1, sort_keys=True))

for arm in ARMS:
    ex = render_next_action_example(traj, langs[arm])
    print(f"\n===== {arm} input_text =====")
    print(ex.input_text[:1400])
    print(f"----- target_text -----")
    print(ex.target_text)
