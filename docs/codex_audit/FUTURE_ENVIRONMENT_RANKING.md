# Future Environment Family Ranking

This is a design ranking, not Fitness V6/V7. The criterion is expected information gain per
engineering hour using existing local traces and cheap deterministic verification.

## Ranked families

| Rank | Family | Capability | Existing support | Verifier / controls / shortcuts | R sensitivity and risk |
|---:|---|---|---:|---|---|
| 1 | Rewrite direction and target selection | choose a semantics-preserving rewrite and site | ≥58k LeanDojo rewrite-family steps | Lean replay; reverse-direction and wrong-site negatives; balance theorem name, site order and expression size | high structural-R plausibility; moderate theorem memorization |
| 2 | Premise selection | select minimal premises that license a step | 167,779 rows with premises / 418,704 refs | replay tactic with selected premises; remove/replace-one negatives; majority/frequency/retrieval baselines | high dependency-visibility sensitivity; library-frequency contamination |
| 3 | Proof-state progress | distinguish valid progress from no-op/dead end | 259,580 transitions plus PRM process labels | Lean before/after plus goal/effect delta; matched valid-no-progress controls | high value for P/R/C separation; progress metric must be preregistered |
| 4 | Obligation discharge / goal closure | choose action that closes a specified goal | 107,006 closing LeanDojo rows | Lean kernel; matched nonclosing applicable tactics; closure is cheap and clear | moderate-high R sensitivity; avoid tactic-name leakage |
| 5 | Subgoal selection | select which open goal to work on | 1,592 rows have >1 goal before the step; 125,608 change goal count | replay action against goal ID; permute goal order and IDs; wrong-goal negative | directly pressures multi-goal vNext; moderate adapter cost |
| 6 | Witness selection | instantiate existential/constructor argument | 46,314 `use`/`refine`/`exact`-family rows (broad upper bound) | Lean checks witness; matched type-correct wrong witnesses | strong semantic task; synthesis difficulty can create floor |
| 7 | Case split / induction choice | select a useful branching variable/principle | 14,769 case/induction-family transitions | Lean accepts split; progress and usefulness need separate gates | useful for R and C, but branch-order/search confound is high |
| 8 | Quantifier instantiation | choose term for a quantified premise | 13,762 introduction-family rows plus theorem applications; requires argument extraction | Lean type check and downstream closure; opaque identifiers/order balancing | strong R plausibility; dependent-type adapter cost |
| 9 | Dependency tracing | identify transitive premise/evidence dependency | V5 synthetic family plus 418,704 refs | exact graph oracle and destroyed edges | cheap, already shows one Qwen-qualified cell; synthetic shortcut risk |
| 10 | Minimal sufficient premise set | find irredundant supporting subset | premise-rich rows | repeated replay under deletion; expensive combinatorics | high information, higher engineering/search cost |
| 11 | Contradiction identification | identify incompatible assumptions | sparse explicit contradiction/by_contra traces | Lean closure under selected pair; relation-destroyed negatives | potentially clean but likely small/floor-prone |
| 12 | Generic legal transformation | select any accepted next tactic | all traces | Lean acceptance | too easy to confound with tactic frequency; low causal value unless narrowed |

`[VERIFIED_BY_SOURCE_DATA] [HYPOTHESIS]`

## Pilot recommendation

Start with a 2×2 pilot: rewrite direction/site and premise selection, each with an explicit
positive, a relation-changing counterfactual, a relation-destroyed negative, and a surface-only
swap. Select source-file-disjoint families, replace identifiers with opaque per-family tokens,
and require every zero-model heuristic to remain within a preregistered band. The same semantic
items must be rendered through R-only candidates.

Do not start with generic next-tactic prediction: tactic frequency and library retrieval dominate
too easily. Do not start with minimal sufficient premise sets: exhaustive replay cost is high.

## Required gates for any family

1. Executable oracle on all rows.
2. Positive control ≥0.95 for the chosen solver/runtime.
3. No deterministic metadata/order/frequency baseline above the shortcut ceiling.
4. Counterfactual consistency and option/order invariance.
5. Smooth difficulty ladder measured before R comparison.
6. Source theorem/file group isolation and contamination report.
7. At least two mechanisms before a general Game-R instrument; a single mechanism may support
   only a mechanism-specific study with a new preregistration.
