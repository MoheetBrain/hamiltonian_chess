# Fitness V4 Preregistration — Game-R Structural Ladder Instrument

Experiment: `arena-representation-fitness-v4`.
Instrument: `arena-game-r-structural-ladder-instrument-v4.0.0`.
Module: `arena/experiments/fitness_v4.py`. Tests: `tests/experiments/test_fitness_v4.py`.

This document is committed before any DEV model call and before any founder or evolved
candidate is evaluated. The rules below are frozen constants in the module; changing any of
them requires a new instrument version.

## 1. Objective

V4 measures whether, given exactly the same visible mathematical information, the
organisation and encoding of that information (`R`) changes a frozen Solver's ability to read
structural mathematical relations. It is the first clean **Game R** instrument under
`GOAL.md` §5.

It exists because V3 was invalidated, and the invalidation has now been diagnosed precisely
(see §2). V4 is not "V3 made harder"; it is designed around structural mechanisms where
representation plausibly matters and where a prior, replicated-by-construction result exists
(identity recurrence inside deep expressions collapses reading; HML_V3 `REAL_LEAN_GAP_V1`).

## 2. What V3 actually measured (diagnosis, from the committed rows)

Every malformed V3 row has `prompt_eval_count == 4099`. The Ollama server log for the
founder run records `msg="truncating input prompt" limit=4099 prompt=17072 keep=5 new=4099`.
The JSON/typed-AST state-delta prompt is 45,027 characters, about 15,600 tokens, against a
frozen `num_ctx` of 8192. Ollama silently discarded the head of the prompt, including the
response instruction, and the model answered in prose.

Consequences, verified from `artifacts/experiments/fitness_v3/`:

- The state-delta "floor" for seven of eight founders was an input-truncation artifact.
- Compact Symbolic's two "wins" occurred only because its state-delta prompt (about 4,700
  tokens) fit the context. That is a token-cost/budget confound, not a reading effect.
- Every DEV complexity-2 cell was truncated the same way; the "malformed at complexity 2"
  behaviour was never a reasoning result.
- Every mechanism that fit the context was a single-field lookup and scored 100%.

A re-run of one truncated state-delta prompt with `num_ctx=32768` returns a valid JSON
answer in 15 s (`prompt_eval_count=15611`). V3 remains `EXPERIMENT_INVALID`; its artifacts
are untouched.

## 3. Frozen variables

| Symbol | Frozen value |
|---|---|
| Σ | `arena-canonical-v0.1.0` schema; states validated by `NativeVerifier`; generator oracle recorded per probe |
| P | `ContentGenome()` default, Track E only; no truth-derived projection is emitted; `assert_game_r_genome` rejects any Track-C candidate |
| τ | Gemma 4 tokenizer as served by Ollama; not varied |
| π | `gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`, Q4_K_M, 11.9B |
| C | single greedy response; no search, no retries |
| D | the V4 mechanism families below; not Gold; provenance recorded per probe |
| U | none |
| V | `NativeVerifier` structural acceptance plus an independent per-mechanism truth re-derivation (tree walk, ancestor closure, lexical scope resolution, subset check, content-hash set difference) |
| B | Ollama, `num_ctx=32768`, temperature 0, seed 20260905, `num_predict=64`, `top_k=64`, `top_p=0.95`, `think=false`; identical for every candidate |

Only `num_ctx` differs from the qualified V2/V3 runtime. Runtime hash is part of every cache
identity.

## 4. Evolvable variable

`R` only: the fourteen-gene `LanguageGenome` surface, rendered through the lossless
`GenomePhenotypeLanguage` codec. Founders are the eight seeds wrapped as Track-E
`ModelViewGenome`s: Structured English, current HML, S-expression, JSON/typed AST, typed
prefix, compact symbolic, graph triples, role-labelled hybrid.

Information parity is enforced mechanically at freeze: for every SCOUT probe and every
founder, the compiled view must parse back to the identical canonical mathematical hash and
no two founders may render byte-identical prompts.

## 5. Mechanisms and ladders

Each mechanism is a two-option structural reading question over a canonical state. Each
family has six probes: ORIGINAL, COUNTERFACTUAL (truth-changing), two byte-identical
DESTROYED siblings with opposite balanced targets, and position-swapped copies of both
positives. Answer targets are exactly balanced (index 0 for ORIGINAL, 1 for COUNTERFACTUAL).
Distractor objects are held at four per state because HML_V3's 32-cell factorial found
external clutter null; difficulty comes from structure.

| Mechanism | Structural question | Ladder L0..L4 | Provenance |
|---|---|---|---|
| `expression_depth_recurrence` | which identifier occurs at the greatest nesting depth in the goal term, when every identifier recurs at several depths and the runner-up trails by one level | (depth, recurrence) = (3,1), (5,2), (7,3), (10,4), (12,4) | adapted from HML_V3 `src/hml_v3/projection/dense.py` at `95e8a26f6519f226a149f4d7507d47f90bea9932`: hashed association per level, truth re-derived by walk |
| `transitive_dependency` | which evidence ID is an ancestor of `e:leaf` k dependency steps away, against a same-length chain that hangs *off* the ancestor chain (wrong direction) | hops = 1, 2, 3, 5, 7 | new; hashed node ids, shuffled list order, independent closure |
| `binder_scope_resolution` | which binder ID binds the tagged variable occurrence under lexical scoping, with the same variable rebound n times on the path, interleaved decoy binders, and sibling binders of the same name | rebinds = 1, 2, 3, 5, 7 | new; independent scope resolver |
| `precondition_conjunction` | which answer has every `requires(answer, p)` proposition matched by a `holds(p)` assumption, where the loser is missing exactly one premise and a digit-transposed near-miss is held instead | premises = 1, 2, 3, 5, 8 | new; independent subset check |
| `state_delta` | which answer's `holds(answer)` fact is in CURRENT but not PREVIOUS, with both answer facts using the same operator and the added fact inserted at a hashed position | facts = 4, 12, 24, 40, 60 | V3 mechanism repaired (operator-name leak removed, context budget enforced) |

Level 0 of every ladder is the mechanism's **explicit-positive control**: the decisive
relation is present at trivial structural size. A Solver that cannot answer L0 cannot do the
mechanism at any readability, and the mechanism is `VOID_INSTRUMENT_LIMIT`.

DEV pool: 5 mechanisms × 5 levels × 6 families × 6 probes = 900 probes; pool hash
`0a45154c532a1a61ef77cf107d4d6bc957cb0be46f4719912b784605043dba05`. Pre-inference shortcut
audit over all 300 DEV positives: CLEAN (worst dumb rule `first_mentioned_in_state` at 0.567).

## 6. Splits

| Split | Salt space | Use |
|---|---|---|
| DEV | `EXPERIMENT_SEED + mechanism*1000 + level*100 + family` | control-only ladder, frontier selection, qualification |
| SCOUT | DEV salts + 100000 | founder tournament; frozen before any founder call |
| PROMOTION, OOD | not materialised in V4.0 | created only if a founder signal replicates; fresh salts, new version |
| ENGINEERING | none needed: the response protocol is inherited unchanged from qualified V2 | |
| ASSURANCE_ONLY | Gold world v0 (676 tasks) | untouched by V4 |

Nothing from any historical repository is used as hidden data.

## 7. Instrument qualification (per mechanism, DEV only, JSON control only)

Selection uses only the permanent `V4E_L3_JSON_AST` control and never a candidate outcome.

1. **Explicit positive.** L0 positive accuracy ≥ 0.90 (of 12), else `VOID_INSTRUMENT_LIMIT`.
2. **Frontier selection.** Among L1..L4 choose the level minimising |accuracy − 0.625|;
   ties go to the lower level. If that level's accuracy is > 0.85: `VOID_CEILING`; if
   < 0.35: `VOID_FLOOR`.
3. **Full-family checks at the selected level** (6 families, 36 rows):
   - Q0 format validity ≥ 0.95 and valid-response rate ≥ 0.95, else `VOID_VALIDITY`;
   - zero rows with a truncated or over-budget prompt, else `VOID_CONTEXT`;
   - positive − destroyed-target accuracy ≥ 0.10 and destroyed ≤ 0.60, else
     `VOID_NEGATIVE_CONTROL`;
   - semantic flip consistency ≥ 0.25 and choice flip rate ≥ 0.50, else `VOID_FLIP`;
   - position invariance ≥ 0.50, else `VOID_POSITION`;
   - shortcut audit CLEAN (every dumb rule within 0.25 of chance on the 12 positives), else
     `VOID_SHORTCUT`.
4. The instrument qualifies if at least **2** mechanisms qualify. Otherwise the frozen
   manifest records `qualified=false` and the sentinel is `FITNESS_V4_NOT_QUALIFIED`.

Aggregate pooling across mechanisms is never used for qualification. A void mechanism is
excluded from SCOUT entirely.

## 8. Context guard (a V3 defect that must not recur)

`prompt_token_limit = num_ctx − num_predict − 256 = 32448`. A prompt whose characters/2.0
exceeds the limit is never sent. A returned `prompt_eval_count` above the limit, or below
characters/6.0, marks the row `TRUNCATED`. In the founder tournament any probe that is over
budget for **any** candidate is void for **every** candidate and removed from the common
paired set; the count is reported. Over-budget is never scored as a candidate failure.

## 9. Solver requalification

Q0 (8 format calls) is re-run under the V4 runtime. Every mechanism's L0 is its explicit
positive; the destroyed twins are its relation-destroyed negative; the counterfactual is its
sensitivity check; the swapped copies are its order-invariance check. A mechanism the Solver
cannot do when the relation is trivially exposed is `VOID_INSTRUMENT_LIMIT`, never
`LANGUAGE_WEAKNESS`.

## 10. Founder tournament and promotion rule

Roster: the eight Track-E founders. Baseline: `V4E_L3_JSON_AST`. SCOUT: 8 families per
qualified mechanism, 6 probes each; positives per candidate = 16 × qualified mechanisms.

Per candidate, on the common in-budget positive set:

- valid-response rate ≥ 0.95;
- one-sided exact sign test on discordant positive outcomes, Holm-corrected across the seven
  non-baseline founders, p ≤ 0.05;
- net wins ≥ max(4, ⌈0.075 × positives⌉);
- paired accuracy delta ≥ 0.10 (practical effect);
- semantic-flip consistency no worse than −0.05 against the baseline.

All five must hold for promotion. Additionally reported, never used for promotion: clustered
(family) paired bootstrap 95% interval of the delta with 4,000 seeded resamples; per-mechanism
win/loss/tie; candidates whose interval lies entirely below zero (penalised relative to the
control); the practical equivalence flag (interval within ±0.05).

## 11. Power and sensitivity

Under the sign test at α = 0.05 one-sided, five all-win discordances (p = 0.031) is the
minimum unadjusted pattern; under Holm with seven candidates the smallest threshold is
0.0071, which needs eight all-win discordances or roughly ten wins against one loss.

With five qualified mechanisms (80 positives) and a control near 0.65, an independent-error
approximation gives about 33 discordant pairs at a true paired advantage of +0.15 and a
one-sided p near 0.03 — below Holm; at +0.20 the expected pattern is about 24 wins to 8
losses, p ≈ 0.004, which passes. With two qualified mechanisms (32 positives) only very large
effects reach significance. SCOUT is therefore a **large-effect scout**: non-promotion means
"not promoted", never "representations are equivalent". Equivalence may be claimed only if
the 95% interval lies within ±0.05, which this design cannot reach; expect `UNRESOLVED`.

## 12. Budgets and stopping rules

| Budget | Value |
|---|---|
| DEV model calls | ≤ 800 (planned: 8 Q0 + 300 ladder positives + ≤ 120 full-family rows) |
| SCOUT model calls | ≤ 2,400 (planned: 8 founders × 48 × qualified mechanisms) |
| Compute | local Apple M5 Max, Ollama; no GPU rental; no training in V4.0 |
| Stop | fewer than 2 mechanisms qualify → `FITNESS_V4_NOT_QUALIFIED`, no founder calls |
| Stop | founders run, no promotion, no penalised founder → `GAME_R_NO_MEASURABLE_SIGNAL` at this power |
| Continue | any promotion or any penalised founder → landscape is non-flat; an R-only one-gene mutation campaign is authorised for the next version |

## 13. Route decision

Route A (harder verified structures, zero-shot frozen Solver) is chosen for V4.0 because it
is executable locally, cheap, and the failure of V3 is fully explained by instrument defects
that Route A repairs. Route B (low-budget learning curves) requires matched adaptation on GPU
and is deferred to the matched-learning stage, which the founder result must first earn.

## 14. Allowed sentinels

`FITNESS_V4_NOT_QUALIFIED`, `FITNESS_V4_QUALIFIED`, `GAME_R_NO_MEASURABLE_SIGNAL`,
`GAME_R_FOUNDER_SIGNAL_FOUND` (internal: at least one founder promoted),
`GAME_R_FOUNDER_PENALTY_ONLY` (internal: no promotion, at least one founder significantly
below the control), `EXPERIMENT_INVALID`.

No founder result creates a `FITNESS_CANDIDATE` without fresh PROMOTION replication, and
nothing in V4.0 authorises matched learning or any R* naming.
