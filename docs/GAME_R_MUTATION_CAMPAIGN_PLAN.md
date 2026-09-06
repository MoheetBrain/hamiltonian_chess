# Game-R Mutation Campaign — Conditional Plan (NOT EXECUTED)

```text
AUTHORIZED = founder_promoted OR founder_penalised
```

This plan executes only if a frozen V4-family founder tournament reports at least one
promoted founder or at least one founder whose clustered paired interval lies entirely below
the JSON control. At the time of writing that condition is **false** (no founder tournament
has run). Nothing below has been executed.

## 1. Candidate pool

`artifacts/reports/game-r-mutant-audit.json` (schema `arena-game-r-mutant-audit-v2`):
120 historical one-gene mutants, all `GAME_R_COMPATIBLE` on five checks (semantic recovery,
visible-information inventory, derived-relation inventory, option expression content, and
behavioural duplication), zero behavioural duplicates, zero structural near-duplicates. Changed genes: grammar, binders,
types, state, actions, serialization, morphology (16 each) and redundancy (8). Every parent
seed has 15 children.

## 2. Options compared (information per model call)

| Design | Calls (48 probes/mechanism × qualified mechanisms m) | What it estimates | Verdict |
|---|---|---|---|
| Exhaustive 120 | 120 × 48m | everything, once | wasteful: 15 children of a parent that is itself at parity with JSON tell little; no replication budget left |
| Successive halving over 120 | ≈ 120 × 16m + 40 × 32m + 12 × 48m | ranking of survivors | ranks noise at the first stage (16 positives per candidate cannot separate ±0.1) |
| Quality-diversity sampling | ≈ 40 × 48m | coverage of R dimensions | good coverage, weak causal attribution (one child per cell) |
| Mutation-family stratification | 8 genes × ≥ 4 parents × 48m ≈ 32–48 × 48m | gene main effects across parents | best for "does gene G help regardless of parent?" |
| Local-neighbour tests | parents with signal × 15 children | parent–child correlation, ruggedness | best for searchability; only around founders that showed signal |

## 3. Chosen first campaign (≈ 40 mutants)

Stratified-plus-local, fixed before any mutant call:

1. **Local neighbourhoods** (24 mutants): all 15 children of the single strongest founder
   signal (promoted or penalised, chosen by the frozen tournament outcome, not by raw
   accuracy) plus the 9 available children of the JSON control, which span all **8** mutated genes
   (grammar, binders, types, state, actions, serialization, morphology, redundancy;
   `token_policy` has no mutants in the historical population).
2. **Gene replication across parents** (16 mutants): for the four genes with the largest
   |Δ| inside the local neighbourhood, the same gene change applied to four other parents
   (one child per parent), so every gene effect has ≥ 4 parent contexts.
3. Total 40 mutants × 48m probes; with m = 2 that is 3,840 calls (≈ 5 h locally), with
   m = 4 it is 7,680 calls (≈ 10 h). Successive halving is applied *inside* the campaign:
   every mutant gets the full SCOUT once; no second stage without fresh PROMOTION salts.

## 4. Landscape statistics (preregistered)

Computed with `arena/evaluation/landscape.py` on paired task-level outcomes against each
mutant's own parent:

- valid-neighbour rate (Gate 0 survivors / proposals) — expected 1.0 from the audit;
- beneficial-mutation rate: child beats parent by ≥ 0.10 paired delta with interval
  excluding zero and token ratio ≤ 1.25;
- parent–child Pearson correlation of positive accuracy;
- same-gene directional consistency across ≥ 4 parents;
- ruggedness: mean/median/max |child − parent|;
- rank stability: Spearman between SCOUT and a fresh 4-family PROMOTION replication for the
  top 8 and bottom 4 mutants.

## 5. Decision rule

- beneficial rate ≥ 0.10 and parent–child r ≥ 0.5 and same-gene consistency ≥ 0.75 on
  at least two genes → `GAME_R_SEARCHABLE_SIGNAL_FOUND`; controlled local evolution may start
  (ACCEL-style edits around survivors, population ≤ 16, generations ≤ 5, fresh PROMOTION
  every generation).
- founder signal exists but the above fails → `GAME_R_SIGNAL_FOUND_LOCAL_SEARCH_WEAK`; the
  next operator is Architect-proposed larger R mechanisms and quality-diversity islands, not
  more one-gene hill climbing.
- no founder signal → this plan never runs.
