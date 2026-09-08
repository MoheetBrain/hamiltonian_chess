# HC-V0 red-team attack suite

`attack_suite_version = hc-v0-redteam-2026-09-08`

Executable attacks against the HC-V0 loop, written for manual §47 Step 9 and §29. Every script
either **succeeds** (a defect, with a reproduction) or **fails** (a defence, recorded as such).
Findings are written up in `docs/HC_V0_RED_TEAM.md`.

## Discipline observed

* Nothing under `arena/`, `tests/`, `spec/` or `artifacts/` was edited, deleted or moved.
  `git status` after the run shows exactly one untracked path: `research/phase9/redteam/`.
* Where a library guard had to be removed to reach the layer behind it, the bypass is a **local
  subclass inside the attack script** (`NullPolicy`, `LeakyRenderer`, `AmnesiacRenderer`,
  `ExplodingRenderer`), never a patch to the package.
* Forged banks and forged fitness records are written to `research/phase9/redteam/out/`.
  The committed bank at `artifacts/trajectory_bank_v0/` is opened read-only.
* No model call of any kind. The Lean toolchain was invoked directly (not a model call).
* The four sealed LeanDojo splits were never opened. Only the guard that refuses them was tested.

## Scripts

| script | attack classes (manual §47 Step 9 / §29) | output |
|---|---|---|
| `attack_lean_kernel.py` | the Lean kernel path: `sorry` variants, `native_decide`, forged `sid`, branch semantics, `#print axioms` identity | `out/lean_kernel.json` |
| `attack_native_decide_end_to_end.py` | the flagship exploit carried to a written bank and through `verify_bank` | `out/native_decide.json` |
| `attack_trajectory_integrity.py` | lineage, truth mutation, horizon inflation, concatenation, evidence tamper | `out/trajectory_integrity.json` |
| `attack_relive.py` | does `verify_bank(relive=True)` catch the forgeries? (needs Lean + the 373 MB split) | `out/relive.json` |
| `attack_leakage.py` | oracle/answer leakage; **independent recount** of the builder's 7 / 9 drop claim | `out/leakage.json` |
| `attack_evolution_record.py` | lineage/provenance, cache identity, fitness-memory immutability, determinism | `out/evolution_record.json` |
| `attack_gate_and_reporting.py` | the semantic gate's blind spot, dead-candidate enforcement, reporting surfaces, `PYTHONHASHSEED` | `out/gate_and_reporting.json` |
| `attack_followups.py` | gate object vs prompt object, forced dead candidate, axiom-free proof, actor/horizon assertions, tripwire inertness | `out/followups.json` |
| `attack_contract_classes.py` | sealed-split guard, §28 trust contract (TIMEOUT ≠ FALSE), macro-cost hiding, alpha-equivalence surface | `out/contract_classes.json` |

## Run everything

```bash
cd /Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/hamiltonian-phase-8-experiment-691d22
for s in lean_kernel native_decide_end_to_end trajectory_integrity leakage \
         evolution_record gate_and_reporting followups contract_classes; do
  .venv/bin/python research/phase9/redteam/attack_$s.py
done
.venv/bin/python research/phase9/redteam/attack_relive.py   # after attack_trajectory_integrity.py
```

Total wall time on the target machine: ≈ 6 minutes, of which ≈ 60 s is Lean.

## Environment used

* `Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)`,
  `leanprover/lean4:v4.10.0-rc1`, built mathlib4 at
  `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4`
* `.venv/bin/python` 3.14.7
* Baseline before and after the suite: `.venv/bin/python -m pytest` → `1275 passed, 1 skipped`
