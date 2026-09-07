# Game R Status

Game R (`GOAL.md` §5): freeze Σ, P, τ, π, C, D, U, V, B; vary only R. Updated only from
committed artifacts.

## Current sentinel

**`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`**

The response protocol is now proven sound. The blocker moved from the instrument to the
Solver: `gemma4:12b` under one greedy constrained answer has no usable band between "told the
answer outright" and "answers the same option every time".

## Gate tracker

| Gate | Status | Evidence |
|---|---|---|
| Valid Game-R instrument preregistered | DONE (V4, V5) | `docs/FITNESS_V4_SPEC.md`, `docs/FITNESS_V5_SPEC.md` |
| Response protocol qualified | **DONE** | V5: 0 malformed / 432 rows; V4: 89 / 348 |
| Context accounting sound | **DONE** | true token counts; V4's char guard shown to be an artifact |
| Solver requalified | **PARTIAL / FAILED** | 2 of 3 explicit-positive arms pass ≥ .90; 0 of 3 mechanisms qualify |
| Per-mechanism DEV qualification | **FAILED (0 of 3)** | `docs/FITNESS_V5_RESULT.md` |
| Frozen SCOUT manifest | NOT REACHED | — |
| Founder tournament | **NOT RUN** (gate not satisfied) | — |
| R-only mutation campaign | NOT AUTHORISED | plan: `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md` |
| Fresh PROMOTION / structural OOD | NOT AUTHORISED | — |
| Matched short adaptation (Route B) | NOT AUTHORISED | audit: `docs/ROUTE_B_HISTORICAL_AUDIT.md` |
| Second Solver family | **NEXT ACTION** | instrument frozen and reusable, ~400 calls per model |

## Instrument history

| Version | Sentinel | Root cause |
|---|---|---|
| V1 | `MODEL_FITNESS_BENCHMARK_INVALID` | solver chose by option position |
| V2 | `FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM` | 12.5-point control range (later shown to be a noise-floor reading) |
| V3 | `EXPERIMENT_INVALID` | input truncation at `num_ctx=8192` + lookup-only mechanisms |
| V4 | `FITNESS_V4_NOT_QUALIFIED` | 64-token output cap + representation-specific char guard |
| **V5** | **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`** | **instrument sound; Solver has no measurable band** |

Programme budget remaining: two instrument versions and ~24,600 model calls of the
preregistered 25,000 cap. V6 is explicitly *not* authorised — a new version is admissible only
if it changes a frozen variable class named in the failure analysis, and the indicated change
is π (the Solver), which does not require a new instrument.

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

1. Re-run the frozen V5 DEV against a second and third installed Solver family
   (`gemma4:31b`, `qwen38-rvn`). If any shows a band, resume at the founder tournament.
2. If none does, switch to Route B matched learning curves (GPU authorisation required).
3. Do not build V6 on this evidence.
