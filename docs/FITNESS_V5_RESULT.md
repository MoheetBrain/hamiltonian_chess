# Fitness V5 Result — the protocol was the artifact; the Solver is the limit

Sentinel: **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`**

Artifact: `artifacts/experiments/fitness_v5/development/result.json`, sha256
`0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`. 392 model calls (budget
900), Q0 1.000, DEV pool 864 probes / 144 families, hash `f804e0d998f1cfac…`. No founder call
was made. Rules were frozen in `docs/FITNESS_V5_SPEC.md` before the run and none was changed.

## 1. The protocol repair worked completely

| | V4 | V5 |
|---|---|---|
| rows scored | 348 | 432 |
| malformed / unusable | **89 (25.6%)** | **0 (0.0%)** |
| response schema errors | 59 reasoning overflows | 0 |
| input truncation / unsent | 30 | 0 |
| valid-response rate at every level | .53–1.00 | **1.000 everywhere** |

Grammar-constrained decoding removed the entire V4 failure class, and measurement confirmed
it is answer-neutral: on rows where V4 produced a parseable answer, the constrained answer
agreed 1.000 of the time. Raising `num_predict` instead fixes none of them. V4's context
heuristic was likewise an artifact: true token counts for the rows it voided were 7,396,
9,498 and 23,215 against a 32,448 limit.

**Conclusion: V4's `FITNESS_V4_NOT_QUALIFIED` measured its own instrument, not the Solver and
not any representation.** That verdict stands as recorded; V5 is a separate version.

## 2. What V5 then measured

| Mechanism | L0 explicit | L1 | L2 | L3 | Frontier | Verdict |
|---|---|---|---|---|---|---|
| `formal_expression_depth` (real Lean) | **0.917** | 0.875 | 0.542 | 0.542 | L2 | `VOID_NEGATIVE_CONTROL` (+ `VOID_SHORTCUT`) |
| `transitive_dependency` | 0.875 | 0.917 | 0.667 | 0.500 | — | `VOID_INSTRUMENT_LIMIT` |
| `precondition_conjunction` | **1.000** | 0.708 | 0.500 | 0.500 | L1 | `VOID_POSITION_SHARE` |

Qualified mechanisms: **0 of 3**. Explicit-positive arms passing ≥ 0.90: **2 of 3**.

### The dominant finding: answer collapse, not partial reading

Largest single-answer share, by level:

| Mechanism | L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| formal depth | 0.58 | 0.54 | 0.62 | 0.71 |
| transitive dependency | 0.62 | 0.58 | **0.83** | **1.00** |
| precondition conjunction | 0.50 | **0.79** | **1.00** | **1.00** |

Every cell reading ≈ 0.500 accuracy is not "half right". It is the Solver answering the same
option every time while balanced targets make that look like chance. This is the V1 failure
mode (`22cab97`) returning whenever the task exceeds one-step lookup — and it is now visible
only because the protocol repair stopped hiding it behind malformed output.

The `largest_answer_share ≤ 0.75` gate, adopted on simulation evidence in place of V4's
choice-flip gate, is what caught it. The old gate would have passed a coin-flipper 65.6% of
the time at six families.

### Per-mechanism reading

- **`transitive_dependency`** fails its explicit arm at 0.875. Three hops with the answer
  asserted outright scores *below* two hops with no help (0.917). The Solver does not
  reliably use a stated fact embedded in a large state.
- **`precondition_conjunction`** is perfect when told the answer (1.000, share 0.50) and
  collapses to a constant answer as soon as two premises must be conjoined (share 0.79 at
  L1, 1.00 at L2+). Its negative-control gap is real (0.208) but the answer distribution
  disqualifies it.
- **`formal_expression_depth`** on real Lean states has the cleanest ladder (0.92 → 0.88 →
  0.54) but at the frontier the Solver is only **0.042** above its relation-destroyed control.
  It also **leaks**: `first_mentioned_in_state` reaches 0.833 at that stratum, because in real
  Lean terms the deeper identifier is usually mentioned first. That is a genuine construction
  defect of this mechanism, predicted as a risk in the spec (§4) at 0.72 pool-wide and
  realised at 0.833 in the selected cell.

## 3. Why the abort clause fired rather than V6

The preregistered clause (`docs/FITNESS_V5_SPEC.md` §9): fewer than two qualified mechanisms
**while** at least two explicit-positive arms pass ≥ 0.90 means the defect is the Solver or
the task family, not the protocol.

Both conditions hold. The Solver demonstrably *can* do two of the three mechanisms when the
decisive relation is stated outright (0.917 and 1.000). It cannot do any of them when the
relation must be derived, and it fails by answering constantly rather than by reasoning
imperfectly. No change to `R` can fix that, and no further instrument version would be
measuring representation.

Building a V6 here would be protocol shopping. The programme budget (two further versions,
25,000 cumulative calls) is preserved, not spent.

## 4. What this does and does not say

- It does **not** say representation does not matter. No candidate representation was ever
  scored under V5; the control alone was measured.
- It does **not** say the mechanisms are unmeasurable in principle. It says `gemma4:12b`
  under a single greedy constrained answer has no usable band between "told the answer" and
  "constant guess" on these three mechanisms.
- It **does** establish, with 432 clean rows, that the previous two invalidations (V3
  truncation, V4 output-cap) were instrument defects and are now fixed and regression-tested.
- The formal-state route is validated as *infrastructure* (461 eligible states, 104
  length-fair, Tier A provenance) but its first mechanism needs an identifier-obfuscation arm
  and an ordering control before it can be trusted.

## 5. Exact next actions

1. **Change the Solver, not the instrument.** Re-run this identical V5 DEV against a larger
   or different-family local model (`gemma4:31b`, `qwen38-rvn`, `qwen36-huihui` are installed).
   The instrument, probes and gates are frozen and reusable; cost is ~400 calls per model.
   Two readers also address the cross-reader replication failure that closed HML_V3's thesis.
2. **If no installed Solver shows a band**, switch to Route B: low-budget matched learning
   curves, where the historical signal actually lived
   (`docs/ROUTE_B_HISTORICAL_AUDIT.md` §4). Requires GPU authorisation.
3. **Before reusing `formal_expression_depth`**, add the ordering control (randomise which
   option is mentioned first) and an identifier-obfuscation arm to quantify mathlib
   memorisation.
