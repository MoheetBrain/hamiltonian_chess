# 72-Hour Sprint Handoff

**Assume zero context.** Branch `claude/phase-6-parallel-setup-9c6068`.
Base `b3717c3` (Phase-6 result) · this sprint's first commit `02bd86d` · final SHA: `git rev-parse HEAD`.

**Two deliverables. One met, one resolved as a negative result.**

| Deliverable | Outcome |
|---|---|
| **A — `TRAINING_LANGUAGE_V0`** | **SHIPPED.** `releases/TRAINING_LANGUAGE_V0/`, `package_hash` `443c8f7950147b82…`, evidence level `TRAINING_LANGUAGE_V0_BASELINE` |
| **B — Game-R result** | **`GAME_R_INSTRUMENT_NOT_QUALIFIED`.** V7: 0 of 3 mechanisms. No founder tournament. `RSTAR_NOT_IDENTIFIED` |

---

## 1. The permanent goal

`GOAL.md`, sha256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b` — **verified at
sprint start and end, unmodified.** It asks whether the way mathematics is *represented* to an AI
causally changes its verified mathematical capability. Variables Σ P R τ π C D U V B are held
separate; Game R varies **only R**.

## 2. The headline scientific result

**Fitness V7 (`docs/FITNESS_V7_RESULT.md`): `V7_SHORTCUT_DOMINATED`, 0 of 3 mechanisms qualified.**
864 rows, all `FRESH`, Q0 1.000, every ladder value reproducing Phase 6 exactly.

| Mechanism | selected | accuracy | best shortcut | margin | verdict |
|---|---|---|---|---|---|
| `formal_expression_depth` | L2 | 0.7917 | **0.8333** | −0.0417 | `VOID_SHORTCUT` |
| `transitive_dependency` | L3 | 0.7500 | 0.6667 | +0.0833 | `VOID_SHORTCUT` |
| `precondition_conjunction` | — | ≥0.958 | 0.500 | — | `VOID_CEILING` |

**The instrument is sound; the mechanisms are not.** Every non-shortcut gate passes.

Two corrections were preregistered *together*, and this is why:
- The **derived frontier target** (0.775, computed from the gate arithmetic rather than declared)
  moved `formal_expression_depth` from L3 onto L2 — exactly as Phase 6 predicted it would.
- The **per-level shortcut audit** then killed it, because at L2 a one-line string rule
  (`first_mentioned_in_state`) scores 0.8333 and **outscores the solver's 0.7917**.

Shipping the selector fix alone — which the Phase-6 document recommended — would have recorded a
qualification and authorised a founder tournament on a mechanism a dumb heuristic solves better.

**Phase-6 §11 is refuted by measurement.** That mechanism at L2 also fails **V5's own frozen**
`shortcut_rule_max = 0.75` (`fitness_v5.py:225`). L2 was never qualifiable; V5 audits shortcuts
only at the selected frontier and reported only `failures[0]`.

**The uncomfortable one.** `transitive_dependency`, the only mechanism ever to qualify, misses the
0.10 margin by **0.017**. Under V5's frozen rules it qualifies; under V7's stricter rule it does
not. `SHORTCUT_MARGIN = 0.10` was frozen before any V7 number existed. **Lowering it to 0.08 would
qualify it. That is protocol shopping and was refused.**

## 3. What was built

**Three real formal task families**, from 250,814 real Lean transitions (LeanDojo Benchmark 4,
mathlib4 `29dcec07…`, train split only), each gated on a model-free shortcut attack **before** any
Solver call — `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md`:

| family | items | best shortcut | chance | ceiling |
|---|---|---|---|---|
| premise selection | 63,831 | 0.327 | 0.167 | 0.45 |
| rewrite direction | 3,466 controlled | 0.6026 | 0.50 | 0.65 |
| legal transformation | 24,000 (12k pairs) | 0.5197 | 0.50 | 0.65 |

**None has been run against a Solver.**

**⚠ THE CONSTRAINT THAT WILL BITE THE NEXT ENGINEER.** All three carry **raw Lean pretty-printed
strings** (`state: str`) and contain **zero** `CanonicalState`/`CanonicalAction` references —
verified by grep. **A pre-rendered string fixes R**, so eight representation arms would receive
byte-identical input. **They cannot carry Game R.** They measure *solver capability*. Making them
Game-R capable needs a canonical projection that is known to be lossy: 0 of 368 real Lean states
map losslessly into `arena-canonical-v0.1.0` (`docs/CANONICAL_VNEXT_PILOT.md`).

**`TRAINING_LANGUAGE_V0`** — small extensible core (ten record kinds + an action block); domains are
library *values*, not grammar. Every REQUIRED canonical-vNext gap handled natively (multi-goal with
per-goal context, obligation scope, metavariable/substitution, structured types, let-values); G7
explicitly deferred. **Targets render through the same surface as inputs**, removing parity defect
D3 (JSON's input-grammar = output-grammar advantage) by construction. Determinism *measured*: AST
scan, attribute-order rotation, `PYTHONHASHSEED` variation, exact round-trip.

**Astra canonical premise bridge** (`docs/astra/`, `research/astra/`), merged **research-only**.
Independently re-verified here: 37 tests, `GAME_R_SOURCE_PROJECTION_PARITY_PASS`, 300 items ×
5 representations, 1,500 renderings, 1,800 option permutations. Parity holds at the
**source-projection** layer only; its own scope says *"not Lean kernel semantics"*.

## 4. Data and sealing

**Sealed before any agent was spawned** — `artifacts/manifests/SEALED_SPLITS.json`:
`novel_premises/{val,test}.json` (PROMOTION/OOD), `random/{val,test}.json` (RESERVED_EVAL), hashed
without parsing. Permitted development sources: `random/train.json`, `corpus.jsonl`, and
`steps.jsonl` **filtered to `split == "train"`** — that file covers all splits (250,814 / 4,260 /
4,506), so an unfiltered consumer leaks the promotion pool.

**No OOD claim is available.** mathlib is HISTORICALLY_EXPOSED and exposure is transitive; both
Solvers' training cutoffs are **unrecorded**.

## 5. Compute

**Zero cloud spend.** Three GCP instances exist (`h3-standard-88`, `a2-ultragpu-1g`,
`a2-highgpu-1g`) — **all still TERMINATED**. Nothing was started: the work was CPU-and-Ollama
bound, the 16 GB Solver was already resident locally, and inference is latency-bound at ~8 s/call.
V7 was the only serialised resource: 864 calls, 12:38:56–14:21:12 (~1.7 h). Ledger:
`docs/SPRINT_COMPUTE_LEDGER.md`. **An A100 is required for matched fine-tuning — no `torch` is
installed anywhere locally and the machine is Apple Silicon.**

## 6. Verification

```
python -m pytest              904 passed, 1 skipped   (190 at sprint start)
python -m ruff check .        All checks passed!
python -m mypy arena          Success: 129 source files
research/astra/tests          37 passed
```
Always `python -m`: a shared editable `.pth` points at a different checkout, so a bare `pytest`
console script silently tests the wrong tree.

## 7. Incidents recorded

- **A subagent deleted `artifacts/cache/` three times while V7 was running**, destroying ~55 live
  rows. No scientific corruption — each identity is visited once per run — but resume capability
  was lost. Recorded rather than quietly regenerated.
- A 2.4 MB regenerable derived dump was swept in by `git add -A` and removed the next commit.

## 8. Next actions, in order

1. **Do NOT build a V8 on this probe bank.** The preregistered stopping rule forbids it and the
   evidence supports it.
2. **`precondition_conjunction` is the one clean mechanism** — its best shortcut is *chance*
   (0.500). It fails only on ceiling (≥0.958 everywhere). **Extend its ladder upward.** This is the
   cheapest credible route to a qualified mechanism.
3. **Run the three families against the Solver** for a capability curve. They are built, gated and
   unused. This tells you where the frontier is before any representation work.
4. **Build the canonical projection** if Game R on real Lean data is wanted. Target
   `TRAINING_LANGUAGE_V0`, not the frozen canonical schema, since it handles the REQUIRED gaps
   natively. Accept and measure the loss.
5. **Record both Solvers' training cutoffs.** Cheapest high-value record in the project; without it
   no temporal-holdout OOD claim is available.
6. **Promote family C off `TIER_B_CONSTRUCTED`** via the specified Lean replay (~3,100 replays per
   1,000 items at the historical 32/100 yield).

## 9. Do not repeat these

- `assert_no_answer_leakage` **cannot** detect answer leakage — its signature never receives the
  gold target — and is never called on the training path.
- The historical `verified` metric is a three-key presence check that read 1.000 everywhere.
- `stratified_split`'s `seed` is inert; the legacy path is preserved deliberately.
- Two mathlib checkouts of the same commit exist: **built** (18 GB, 5,680 `.olean`,
  `external/runtime_work/…`) and source-only (349 MB, 38 `.olean`, `external/checkouts/…`). Two
  careful audits reached opposite conclusions from this. **Name the path.**
