# Fitness V5 Preregistration — Constrained-Protocol, Formally Grounded Game-R Instrument

Experiment: `arena-representation-fitness-v5`.
Instrument: `arena-game-r-constrained-formal-instrument-v5.0.0`.
Environment: `arena-formal-structural-v1.0.0`.
Module: `arena/experiments/fitness_v5.py`. Probe bank: `arena/environments/formal_structural.py`.

Committed before any founder or evolved-candidate call. The constants below are frozen in
code; changing any of them requires a new instrument version, not an edit.

## 1. Why V5 exists, and what V4 actually proved

V4 returned `FITNESS_V4_NOT_QUALIFIED` with 0 of 5 mechanisms. Phase-5 forensics showed both
of its failure modes were **instrument defects**, not results about representations:

1. **Response protocol.** 59 rows began a prose derivation and hit the 64-token cap without
   emitting JSON. Measured directly: schema-constrained decoding recovers **9 of 9** of those
   rows, parse rate goes from 15/24 to **24/24**, and the answers are **unchanged** on every
   row where a baseline answer existed (agreement 1.000). Raising `num_predict` to 512 fixes
   **0 of 9** and destabilises two rows that previously parsed.
2. **Context accounting.** V4's `chars/2.0` and `chars/6.0` heuristics voided 30 rows.
   Measured true token counts: binder scope L3 = 7,396 tokens, L4 = 9,498, state delta L4 =
   23,215 — all inside the 32,448-token budget. The heuristic is representation-specific
   (measured chars/token spans **2.74 to 7.43**), and at binder L3 it deleted **exactly the
   counterfactual arm**, so that mechanism's reported `.500` is "all originals correct, all
   counterfactuals deleted by a rounding constant".

V4's verdict stands as recorded: it applied its own frozen rule correctly. V5 is a new version
with a new runtime hash; V4 is not re-scored.

## 2. Frozen variables

| Symbol | Value |
|---|---|
| Σ | `arena-canonical-v0.1.0`; probe states verified by `NativeVerifier`; per-mechanism independent truth re-derivation |
| P | `ContentGenome()` default, Track E only; `assert_game_r_genome` rejects any content-projection candidate |
| τ | Gemma 4 tokenizer via Ollama |
| π | `gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` |
| C | one greedy grammar-constrained answer; no reasoning, no search, no retries |
| D | the three mechanisms below |
| U | none |
| V | `NativeVerifier` + independent re-derivation (tree walk, ancestor closure, subset check) |
| B | `num_ctx` 32768, `num_predict` 64, temperature 0, seed 20260905, `top_k` 64, `top_p` 0.95, think off, **`format` = JSON schema `{choice: enum[A,B]}`** |

`num_predict` stays at 64 deliberately. Under grammar constraint the answer is ~8 tokens, and
a larger budget was measured to be unstable. Only `format` changes versus V4.

## 3. Evolvable variable

`R` only: the eight seed surfaces as Track-E `ModelViewGenome`s. Information parity is
asserted mechanically, and the mutant audit's surface check
(`arena/experiments/game_r_mutant_audit.py`) now inventories what the renderer actually put on
the page rather than what the parser handed back, so a candidate that emits a derived relation
and drops it on parse is detected.

## 4. Mechanisms

| Mechanism | Question | Truth re-derived by | Ladder L0..L3 |
|---|---|---|---|
| `formal_expression_depth` | which identifier occurs at the greatest nesting depth in the goal term | walking the transcribed tree | explicit / shallow / medium / deep strata |
| `transitive_dependency` | which evidence ID is an ancestor of `e:leaf` k steps away | independent ancestor closure | explicit / 2 / 3 / 5 hops |
| `precondition_conjunction` | which answer has every required premise held | independent subset check | explicit / 2 / 3 / 5 premises |

**Level 0 is a true explicit-positive arm**, not a smaller structure: the decisive relation is
asserted outright in the state (`occurs_at_depth(id, n)` for both options, or `the_answer_is`),
applied identically to every representation. A Solver that fails it cannot do the mechanism at
any readability, which is an instrument limit rather than a language result.

### Formal grounding and its limits

`formal_expression_depth` uses **real elaborated Lean 4 goal states** from mathlib and
Batteries (donor `MoheetBrain/HML_V3` @ `95e8a26`, 1,150 transitions). 461 states pass the
structural eligibility filter (unique deepest identifier, depth ≥ 4, recurrence ≥ 2). The
donor's 126 sealed source files are excluded by name and never read.

Trust tiering is explicit: the **states** are Tier A (Lean's own elaborator produced them);
the **structural answers** are Tier B (Arena recomputes them). Nothing claims the tactic step
was replayed — the donor's own attestation gate reports `passed=false` — and a depth question
does not need that guarantee.

**Length fairness is a first-class constraint.** On unrestricted real states the eight
surfaces differ in rendered length by a median factor of **6.5** and a maximum of **23.7**,
which would confound organisation with token cost. Probes are therefore restricted to states
where every surface renders under 30,000 characters, bounding the ratio to about **4.6** and
leaving 104 states across 95 mathlib files, still hard (75% have a one-level lead). At the
measured floor of 2.74 chars/token this also makes input truncation structurally unreachable,
so it is asserted post hoc rather than preflighted.

**Known residual risk.** The strongest dumb rule on the DEV pool is `more_frequent_in_state`
at **0.72** against a 0.75 threshold: in real Lean terms the deeper identifier does tend to
recur more. This is reported, not hidden. If a mechanism qualifies on the strength of that
correlation the finding is weak, and an identifier-obfuscation arm is required before any
promotion.

## 5. Qualification, per mechanism, DEV only, JSON control only

1. Explicit positive (L0) ≥ 0.90, else `VOID_INSTRUMENT_LIMIT`.
2. Frontier: among L1..L3 minimise |accuracy − 0.625|, ties to the lower level; > 0.85
   `VOID_CEILING`, < 0.35 `VOID_FLOOR`.
3. At the frontier, on ≥ 24 positives (12 families):
   - Q0 ≥ 0.95 and valid-response ≥ 0.95, else `VOID_VALIDITY`;
   - zero input-truncated rows, else `VOID_CONTEXT`;
   - positive − destroyed ≥ **0.20** and destroyed ≤ 0.60, else `VOID_NEGATIVE_CONTROL`;
   - **largest single-answer share ≤ 0.75**, else `VOID_POSITION_SHARE`;
   - position invariance ≥ 0.50, else `VOID_POSITION`;
   - shortcut audit CLEAN, else `VOID_SHORTCUT`.
4. The instrument qualifies if ≥ 2 mechanisms qualify. Void mechanisms are never pooled into
   a score.

Two gate changes are corrections, each justified by simulation rather than taste. The
**choice-flip gate is dropped as a gate**: at 6 families a coin-flipper passes it 65.6% of the
time and an honest reader at the 0.625 frontier has expected flip 0.531, so it cannot separate
reading from guessing. It is replaced by the **largest-answer-share** statistic, which has a
1.9% false-void rate against an honest reader at the frontier and catches constant-position
behaviour with probability 1. The **gap threshold rises from 0.10 to 0.20** because at 24+24
rows the gap's standard error is 0.142, so 0.10 was inside one standard error.

## 6. Promotion (founders), if V5 qualifies

Baseline `V5E_L3_JSON_AST`. Per candidate on the common in-budget positive set: valid ≥ 0.95;
one-sided exact sign test, Holm-corrected across seven founders, p ≤ 0.05; net wins ≥
max(4, ⌈0.075·positives⌉); paired delta ≥ 0.10; semantic-flip non-inferiority ≥ −0.05.
Reported alongside, never gating: clustered family bootstrap 95% interval, per-mechanism
win/loss/tie, and **mean rendered prompt tokens per candidate** — compactness is a Pareto axis
under `GOAL.md` §15, not a defect to be hidden.

`paired_against` fails closed: an empty common set can no longer report practical equivalence.

## 7. Power and the equivalence region

Simulated (one-sided sign test, Holm over 7, p0 = 0.625, 20k replicates): at N = 128 positives
power is 0.185 at δ = 0.10 and 0.511 at δ = 0.15. Eighty-percent power needs N ≈ 496 at
δ = 0.10 and N ≈ 224 at δ = 0.15. Holm's smallest threshold (0.00714) requires **≥ 8 all-win
discordances**, so a one-stage design is underpowered by construction.

SCOUT is therefore a **large-effect scout** and, if a leader emerges, it must replicate on
fresh probes before any `FITNESS_CANDIDATE` claim.

The practical-equivalence region is **±0.125**, not V4's ±0.05. V4's region could never fire:
it needs N > 600, while the achievable 95% half-width at N = 128 is 0.113–0.139. The value is
anchored to evidence: V2's 12.5-point control range is *below* the median null range for its
sample size (p = 0.886, i.e. a noise-floor reading), and the only historical spread exceeding
chance is the A100 sprint's 0.146 (p = 0.035, one seed).

## 8. Failure taxonomy and denominators

| Code | Accuracy | Validity | Rule |
|---|---|---|---|
| `MODEL_SEMANTIC_ERROR` | incorrect | valid | scored |
| `RESPONSE_SCHEMA_ERROR` | incorrect | invalid | scored; emitting the contract is part of what R must support |
| `OUTPUT_TRUNCATION` | void | void | property of frozen C/B; void for every arm; reported as token cost |
| `INPUT_CONTEXT_TRUNCATION` | void | void | harness defect; void for every arm |
| `PARSER_ERROR` | void | void | our bug; any non-zero count trips `VOID_PARSER` and the run is redone |

Voiding is outcome-independent for input truncation and parser error. For output truncation it
is not, so a preregistered `output_truncation_void_rate ≤ 0.05` per arm applies, and accuracy
is reported both void-excluded and worst-case, with the promotion sign required to agree under
both. Under grammar constraint all three void codes should be unreachable; they are retained
as assertions that the constraint is still being applied.

## 9. Budgets and stopping rules

DEV ≤ 900 calls; SCOUT ≤ 3,000. Local Apple M5 Max, Ollama; no GPU rental; no training.

**Programme-level stop, preregistered here:** at most two further instrument versions
(V6, V7) and 25,000 cumulative model calls. A version counts as spent once its DEV run
completes. A new version is admissible only if it changes a frozen variable class (C/B, D or
π) named in the prior failure analysis; re-tuning thresholds is not a new attempt.

**Immediate abort clause:** if V5 yields fewer than 2 qualified mechanisms **while ≥ 2
explicit-positive arms pass ≥ 0.90**, the defect is the task family or the Solver, not the
protocol. Emit `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` and move to
Route B or a second Solver family without building V6.

## 10. Allowed sentinels

`FITNESS_V5_NOT_QUALIFIED`, `FITNESS_V5_QUALIFIED`,
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`,
`GAME_R_NO_MEASURABLE_SIGNAL`, `GAME_R_SIGNAL_FOUND_LOCAL_SEARCH_WEAK`,
`GAME_R_SEARCHABLE_SIGNAL_FOUND`, `EXPERIMENT_INVALID`.

No founder result creates a `FITNESS_CANDIDATE` without fresh replication, and nothing in V5
authorises matched learning or any R* naming.
