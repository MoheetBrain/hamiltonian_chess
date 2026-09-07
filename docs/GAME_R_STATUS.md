# Game R Status

Game R (`GOAL.md` §5): freeze Σ, P, τ, π, C, D, U, V, B; vary only R. Updated only from
committed artifacts.

## Current sentinel

**`SOLVER_SPECIFIC_FAILURE_SUPPORTED`** (Phase 6). The Phase-5 blocker was the Solver.

Substituting `qwen38-rvn` for `gemma4:12b` on the frozen instrument escapes the degeneracy
completely (paired exact McNemar p = 2.9e-11 on the preregistered endpoint), qualifies
`transitive_dependency` — the first mechanism ever to qualify — and inverts the failure mode
from floor to ceiling. See `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md`.

The frozen code still emits `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`
for qwen, because its abort clause fires on "<2 qualified while >=2 explicit arms pass". That
label is wrong for this solver and is retained only because the rule is frozen; the clause was
written for a floor failure and cannot recognise a ceiling one.

## Gate tracker

| Gate | Status | Evidence |
|---|---|---|
| Valid Game-R instrument preregistered | DONE (V4, V5) | `docs/FITNESS_V4_SPEC.md`, `docs/FITNESS_V5_SPEC.md` |
| Response protocol qualified | **DONE** | V5: 0 malformed / 432 rows; V4: 89 / 348 |
| Context accounting sound | **DONE** | true token counts; V4's char guard shown to be an artifact |
| Solver requalified | **PASSED for qwen38-rvn** | 3 of 3 explicit arms pass; 1 of 3 mechanisms qualifies (gemma: 2/3 and 0/3) |
| Per-mechanism DEV qualification | **1 of 3 (qwen)**, 0 of 3 (gemma) | `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` |
| Frozen SCOUT manifest | NOT REACHED | — |
| Founder tournament | **NOT RUN** — gate needs 2 qualified mechanisms, got 1 | `GAME_R_NOT_RUN` |
| R-only mutation campaign | NOT AUTHORISED | plan: `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md` |
| Fresh PROMOTION / structural OOD | NOT AUTHORISED | — |
| Matched short adaptation (Route B) | NOT AUTHORISED | audit: `docs/ROUTE_B_HISTORICAL_AUDIT.md` |
| Second Solver family | **DONE** | `qwen38-rvn` run under the frozen instrument, 392 calls |

## Instrument history

| Version | Sentinel | Root cause |
|---|---|---|
| V1 | `MODEL_FITNESS_BENCHMARK_INVALID` | solver chose by option position |
| V2 | `FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM` | 12.5-point control range (later shown to be a noise-floor reading) |
| V3 | `EXPERIMENT_INVALID` | input truncation at `num_ctx=8192` + lookup-only mechanisms |
| V4 | `FITNESS_V4_NOT_QUALIFIED` | 64-token output cap + representation-specific char guard |
| V5 | `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` | instrument sound; that Solver had no measurable band |
| **V6** | **`SOLVER_SPECIFIC_FAILURE_SUPPORTED`** | **different solver escapes the collapse; 1 mechanism qualifies; failure inverts to ceiling** |

Programme budget remaining: after Phase 6 roughly 23,800 model calls of the preregistered
25,000 cap. Phase 6 changed π (the Solver), a frozen variable class named in the V5 failure
analysis, so it was admissible without a new instrument. The next version *is* now justified,
because the frontier selector is demonstrably miscalibrated against the gap gate.

## Mutant audit

`artifacts/reports/game-r-mutant-audit.json`: 120 of 120 historical one-gene mutants are
`GAME_R_COMPATIBLE`; 0 behavioural duplicates; 0 structural near-duplicates; 8 mutated genes
(`token_policy` has none).

**Correction applied in Phase 5.** The first version of this audit compared inventories of the
*recovered* canonical state. Two independent reviews showed that check is a strict coarsening
of `mathematical_hash` and therefore vacuous, making `GAME_P_ONLY` unreachable. The audit now
inventories the rendered surface decoded through the base codec, and a regression test proves
it fires on a candidate that emits a derived relation and drops it on parse. The 120/120
result is a meaningful finding under the corrected check, not the old vacuous one.

## Candidate hierarchy

| Level | Candidates |
|---|---|
| VALID_CANDIDATE | the eight seeds; the 120 one-gene mutants |
| FITNESS_CANDIDATE | none |
| LEARNABILITY_CANDIDATE | none |
| ROBUST_CANDIDATE | none |
| RSTAR_0_1 | none — `RSTAR_NOT_IDENTIFIED` |

## Game P

Not started. The six Track-C content genes remain excluded from Game R by
`assert_game_r_genome`.

## Next decision

1. **Fix the frontier selector and re-run qwen only (~400 calls).** With the negative control
   pinned at 0.500 and `gap >= 0.20`, only `positive` in [0.70, 0.85] can qualify, yet the
   selector targets 0.625 and therefore prefers unqualifiable levels. Under a corrected target
   `formal_expression_depth` would have selected L2 (.792) and passed, giving 2 qualified
   mechanisms and authorising the founder tournament.
2. Extend the ladder upward: `precondition_conjunction` is at 1.000 for qwen at every level.
3. Do not run a third solver; the Phase-6 question is answered.
