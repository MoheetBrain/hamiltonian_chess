# Game R Status

Game R (`GOAL.md` §5): freeze Σ, P, τ, π, C, D, U, V, B; vary only R. This file tracks the
gates. Each row is updated only from committed artifacts.

## Gate tracker

| Gate | Status | Evidence |
|---|---|---|
| Valid Game-R instrument (V4) preregistered | DONE | `docs/FITNESS_V4_SPEC.md`, this commit |
| Solver requalified under V4 runtime (Q0 + per-mechanism explicit positives) | NOT RUN | — |
| Per-mechanism DEV qualification | NOT RUN | — |
| Frozen SCOUT manifest with information parity across 8 founders | NOT RUN | — |
| Founder tournament (8 Track-E founders, paired vs JSON) | NOT RUN | — |
| R-only one-gene mutation campaign | NOT AUTHORISED | requires founder signal |
| Fresh PROMOTION | NOT AUTHORISED | — |
| Structural OOD | NOT AUTHORISED | — |
| Matched short adaptation (Route B) | NOT AUTHORISED | — |
| Second seed / second Solver family | NOT AUTHORISED | — |

## Candidate hierarchy

| Level | Candidates |
|---|---|
| VALID_CANDIDATE (semantic assurance) | the eight seeds (v0 assurance, 1,352/1,352 roundtrips) |
| FITNESS_CANDIDATE | none |
| LEARNABILITY_CANDIDATE | none |
| ROBUST_CANDIDATE | none |
| RSTAR_0_1 | none — `RSTAR_NOT_IDENTIFIED` |

## Game P

Not started. The six Track-C content genes (`arena/model_view/genome.py`) are preserved and
excluded from Game R by `assert_game_r_genome`.

## Current sentinel

`FITNESS_V4_NOT_QUALIFIED` (instrument preregistered; DEV not yet run).
