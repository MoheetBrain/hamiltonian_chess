# Game R Status

Game R (`GOAL.md` §5): freeze Σ, P, τ, π, C, D, U, V, B; vary only R. This file tracks the
gates. Each row is updated only from committed artifacts.

## Gate tracker

| Gate | Status | Evidence |
|---|---|---|
| Valid Game-R instrument preregistered (V4) | DONE | `docs/FITNESS_V4_SPEC.md`, commit `88bacc8` |
| Solver requalified under V4 runtime | PARTIAL | Q0 1.000; explicit positives passed for transitive_dependency and precondition_conjunction only |
| Per-mechanism DEV qualification | **FAILED (0 of 5)** | `artifacts/experiments/fitness_v4/development/result.json`; `docs/FITNESS_V4_FAILURE_ANALYSIS.md` |
| Frozen SCOUT manifest | RECORDED AS NOT QUALIFIED | `artifacts/experiments/fitness_v4/frozen_manifest.json` (`qualified=false`, 0 probes), `not_qualified.json` |
| Founder tournament | NOT RUN (gate not satisfied) | — |
| R-only mutation campaign | NOT AUTHORISED | plan only: `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md` |
| Fresh PROMOTION / structural OOD | NOT AUTHORISED | — |
| Matched short adaptation (Route B) | NOT AUTHORISED | audit only: `docs/ROUTE_B_HISTORICAL_AUDIT.md` |
| Second seed / second Solver family | NOT AUTHORISED | — |

## Per-mechanism verdicts (V4 DEV, JSON control only)

| Mechanism | L0..L4 positive accuracy | Verdict |
|---|---|---|
| expression_depth_recurrence | .833 .583 .417 .667 .750 | VOID_INSTRUMENT_LIMIT |
| transitive_dependency | 1.0 1.0 .583 .333 .417 | VOID_VALIDITY (reasoning overflow at 64 tokens) |
| binder_scope_resolution | .750 .500 .500 .500 unsent | VOID_INSTRUMENT_LIMIT |
| precondition_conjunction | 1.0 .667 .583 .500 .500 | VOID_FLIP (position-driven at k ≥ 2) |
| state_delta | .500 .083 .083 .500 unsent | VOID_INSTRUMENT_LIMIT |

## Mutant audit

`artifacts/reports/game-r-mutant-audit.json`: all 120 historical one-gene mutants are
`GAME_R_COMPATIBLE` on five checks — semantic recovery, visible-information inventory,
derived-relation inventory, option expression content, and behavioural duplication; zero
behavioural duplicates; zero structural near-duplicates over the nine phenotype genes.
Eight genes are actually mutated (`token_policy` has no mutants). They are eligible for a Game-R mutation
campaign, which is not authorised.

## Candidate hierarchy

| Level | Candidates |
|---|---|
| VALID_CANDIDATE (semantic assurance) | the eight seeds; the 120 mutants (Gate 0, V1) |
| FITNESS_CANDIDATE | none |
| LEARNABILITY_CANDIDATE | none |
| ROBUST_CANDIDATE | none |
| RSTAR_0_1 | none — `RSTAR_NOT_IDENTIFIED` |

## Game P

Not started. The six Track-C content genes remain implemented and are excluded from Game R
by `assert_game_r_genome`.

## Current sentinel

`FITNESS_V4_NOT_QUALIFIED`.

## Next decision

1. Run the DEV-only output-budget calibration (`docs/V4_1_PROTOCOL_CALIBRATION_PROPOSAL.md`)
   under a new version after explicit authorisation.
2. If a non-sabotaging budget exists: preregister V5 (`docs/FITNESS_V4_FAILURE_ANALYSIS.md`
   §5), then DEV, then freeze, then founders.
3. If not: switch to Route B low-budget matched learning curves
   (`docs/ROUTE_B_HISTORICAL_AUDIT.md` §4) or a second Solver family.
