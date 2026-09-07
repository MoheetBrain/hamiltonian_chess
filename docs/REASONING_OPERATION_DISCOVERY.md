# Reasoning-Operation Discovery — what actually recurs across human, model and formal steps

**Question.** Which reasoning operations recur across human solutions, informal model
solutions, and formal proof states?

**Method.** Read-only measurement over local artifacts. **No model call, no network, no
Lean, no GPU, no training run.** Every number below was produced by a script in
`research/operations/` and can be re-run:

```
python -m research.operations.measure_annotated        # 769 + 23 + 3,978 annotated steps
python -m research.operations.measure_formal           # 241,265 + 8,766 + 1,150 + 611 formal
python -m research.operations.measure_informal_proxy   # 42,963 human + 81,908 model steps
python -m research.operations.build_inventory          # -> artifacts/corpus/operation_inventory.json
```

Machine-readable output: `artifacts/corpus/operation_inventory.json`.

**Answer in one line.** Nine operation families are attested in all three source kinds, but
only **two** survive an adversarial alignment check with high confidence, **five** informal
operations have no canonical formal counterpart at all, and **two** large formal categories
have no informal counterpart. The recurrence is real and it is weak.

---

## 1. Limits — read these first

**1.1 The rich corpus is 769 steps.** Full schema (per-step operation + warrant +
preconditions + obligations + typed dependencies + before/after state) exists for exactly
769 Gold-125/Gold-25 transitions over 125 Hendrycks MATH trajectories, plus 23 hand-authored
Gold-10 actions. 792 steps total. Everything else in this study is unlabelled text or
single-operation formal traces.

**1.2 One step in six has no operation.** `core_operation = UNRESOLVED` on **136/769
(17.7%)**, of which **125** came from `observed_operation = OTHER`. The most richly annotated
corpus in the estate declines to name the operation for 16.3% of its steps.

**1.3 One operation is 40% of the corpus.** `TRANSFORM` = 305/769 (39.7%) of the gold corpus
and 3,074/3,978 (77.3%) of the synthetic corpus. It is a sink, not a discovery.

**1.4 Most of the schema has no support, on both sides.**

| Axis | Values defined | Values with ≥5 observations in 769 | Zero-support values |
|---|---|---|---|
| `scope_effect` | 7 | 2 (`NONE` 734, `OPEN_BRANCH` 35) | `CLOSE_BRANCH`, `JOIN_BRANCHES`, `INTRODUCE_ASSUMPTION`, `DISCHARGE_ASSUMPTION`, `UNKNOWN` |
| `goal_effect` | 4 | 4 (but `CREATE_SUBGOAL` = 12) | — |
| `epistemic_effect` | 6 | 4 (`PROPOSE_CANDIDATE` 4, `REJECT_CANDIDATE` 6) | — |
| `core_operation` | 19 | 16 (8 of the 19 occur ≤7 times) | — |
| gold125 registry | 66 | **22** | **25 of 66 are singletons; 36 of 66 occur ≤2 times** |

On the formal side the corresponding fact is already known and is confirmed here:
`action.operation == "LEAN_TACTIC"` with all five effect maps empty on every record of
`hml_50k_final` and `vnext_10k`. Four fifths of the action schema has zero corpus support.

**1.5 Gold-10 provides zero evidence about recurrence.** 23 hand-authored actions carry
**22 distinct operation names** (`segment_and_resolve_domain`,
`construct_non_entailment_countermodel`, `differentiate_reciprocal`, …). It is a near-bijection
between steps and names. It is a specification exercise, not a sample.

**1.6 No formal corpus contains a single failed step.** A Lean trace holds only the steps that
were kept. PRM800K's 262,146 `-1`-rated steps are the only large source of failed reasoning on
disk, and they are unverified and MATH-contaminated. Verification and failure are **disjoint**
across the entire estate.

**1.7 The 1,150-transition HML_V3 corpus is deliberately unrepresentative.** Measured here
against a representative LeanDojo sample: the goal-management block is **11.72% vs 0.44%, a
27x over-sample**; individual combinators run 38–49x (`exacts` 7.7% vs 0.18%, `all_goals` 4.4%
vs 0.09%, `swap` 3.4% vs 0.09%). Never quote its tactic mix as a fact about mathematics.

**1.8 The model arm is a lexical proxy, not an operation count.** Nothing on disk labels
operations on model-generated steps. PRM800K has 733,768 steps and 1,085,590 step ratings and
**zero** operation annotations. The detector used here is a regex cue lexicon, calibrated
against the 769 gold spans; its precision ranges from **0.077 to 1.000**, and **334/769
(43.4%)** of gold spans fire no cue at all. See §4.

**1.9 The two formal sources are not independent.** `lean_canonical_records.jsonl` (241,265) is
built from LeanDojo Benchmark 4 v10 (`source_family = LEANDOJO_BENCHMARK_4_V10`). The
replication reported in §5 validates the *labelling function*, not the *generality* of the
vocabulary.

**1.10 Annotation is not verification.** Every operation label in this study was asserted by a
human, or by a deterministic extractor over human text. To promote any of it, each step needs
**(a)** a second independent annotator with a measured κ, and **(b)** a machine check of the
mathematical content — SymPy equivalence, or a Lean replay of the corresponding formal step.
Neither exists today for any of the 769. See §7.

**1.11 Single domain, contaminated.** Every richly-annotated step is Hendrycks MATH. MATH is
in the training data of every model this project evaluates.

---

## 2. The recurrence result

Per-source, never pooled. Column A is a gold label. Columns B and C are the **lexical proxy**
(§4) — read them as surface statistics, not operation counts. Column D is a tactic-head count
over a uniformly random LeanDojo sample.

| Operation | A · gold 769 (human MATH, labelled) | B · 42,963 MATH-solution sentences (human) | C · 81,908 PRM800K steps (model) | D · 8,766 LeanDojo tactics (formal) | Recurs? |
|---|---|---|---|---|---|
| APPLY_THEOREM | 29 · 3.8% | 1,444 · 3.4% | 1,048 · 1.3% | 1,874 · **21.4%** | ✅ all 3 |
| SUBSTITUTE / REWRITE | 7 · 0.9% | 907 · 2.1% | 2,410 · 2.9% | 1,982 · **22.6%** | ✅ all 3 |
| INTRODUCE (declare/binder/witness) | 5 · 0.7% | 2,276 · 5.3% | 933 · 1.1% | 1,102 · 12.6% | ✅ all 3 |
| CASE_SPLIT | 15 · 1.9% | 1,287 · 3.0% | 2,056 · 2.5% | 437 · 5.0% | ✅ all 3 |
| TRANSFORM | 305 · **39.7%** | 3,539 · 8.2% | 6,779 · 8.3% | 265 · 3.0% | ✅ (vacuously) |
| CONSTRUCT | 12 · 1.6% | 1,720 · 4.0% | 725 · 0.9% | 285 · 3.3% | ✅ all 3 |
| APPLY_DEFINITION | 19 · 2.5% | 516 · 1.2% | 1,730 · 2.1% | 161 · 1.8% | ✅ all 3 |
| DISCHARGE | 90 · 11.7% | 12,708 · 29.6% | 1,359 · 1.7% | 141 · 1.6% (CLOSE effect: **44.4%**) | ✅ all 3 |
| INDUCT | 7 · 0.9% | 24 · 0.06% | 34 · 0.04% | 86 · 1.0% | ✅ all 3 |
| CONTRADICTION | 6 · 0.8% | 253 · 0.6% | 215 · 0.3% | 46 · 0.5% | ✅ all 3 |
| EVALUATE | 50 · 6.5% | 2,398 · 5.6% | 7,972 · 9.7% | **0** | ❌ informal only |
| COUNT | 23 · 3.0% | 3,414 · 8.0% | 4,093 · 5.0% | **0** | ❌ informal only |
| BOUND | 23 · 3.0% | 2,029 · 4.7% | 2,435 · 3.0% | **0** | ❌ informal only |
| SELECT | 4 · 0.5% | 2,103 · 4.9% | 2,293 · 2.8% | **0** | ❌ informal only |
| VERIFY | 28 · 3.6% | 489 · 1.1% | 894 · 1.1% | **0** | ❌ informal only |
| ENUMERATE | 2 · 0.3% | 506 · 1.2% | 756 · 0.9% | 1 · 0.01% | ❌ near-absent |
| ASSERT_SUBGOAL (`have`) | **0** (an *effect*, not an operation) | — | — | 654 · **7.5%** | ❌ formal only |
| GOAL_MANAGEMENT | **0** | — | — | 39 · 0.44% | ❌ formal only |
| AUTOMATION (`simp`, `ring`, `linarith`, …) | **0** | — | — | 1,793 · **20.5%** | ❌ formal only |
| PLAN / SEARCH_META | 0 (mode axis: 57 · 7.4%) | 1,563 · 3.6% | 9,672 · **11.8%** | **0** | ❌ informal only |
| BACKTRACK | 0 (`REJECT_CANDIDATE` = 6) | 62 · 0.14% | 323 · 0.39% | **0 by construction** | ❌ informal only |

### 2.1 The headline numbers

- **Nine operation families are attested in all three source kinds** (counting CONSTRUCT
  inside INTRODUCE, because the formal side cannot separate them): APPLY_THEOREM,
  SUBSTITUTE/REWRITE, INTRODUCE, CASE_SPLIT, TRANSFORM, APPLY_DEFINITION, DISCHARGE, INDUCT,
  CONTRADICTION.
- **Five informal operations have no canonical formal counterpart**: EVALUATE, COUNT, BOUND,
  SELECT, VERIFY. Four of the five are *absorbed by automation* — `norm_num`, `decide`,
  `linarith`, `positivity` do them, but the tactic name records that a search succeeded, not
  what was computed. That is an **annotation-scheme artifact**.
  VERIFY is different: it is a **genuine domain difference**. In a proof assistant the kernel
  verifies, so verification can never appear as a step. This is the one clean domain result in
  the study.
- **Three formal categories have no informal counterpart**: AUTOMATION (20.5%),
  ASSERT_SUBGOAL (7.5%), GOAL_MANAGEMENT (0.44%). ASSERT_SUBGOAL is *not* a domain difference —
  see §3.
- **Two informal categories have no formal counterpart at all**: PLAN (11.8% of model steps)
  and BACKTRACK. Both are absent from every formal corpus **by construction**, because a Lean
  trace records only kept steps.

### 2.2 Backtracking, measured

Cue-firing rate on PRM800K model steps, split by the human step rating:

| Cue | rating +1 (n=39,201) | rating 0 (n=13,103) | rating −1 (n=27,706) | −1 / +1 |
|---|---|---|---|---|
| BACKTRACK | 0.23% | 0.65% | 0.51% | **2.2x** |
| CONTRADICTION | 0.18% | 0.21% | 0.40% | 2.2x |
| DISCHARGE | 1.15% | 0.68% | 2.80% | **2.4x** |
| DECLARE | 1.29% | 1.79% | 0.58% | 0.45x |
| APPLY_THEOREM | 1.50% | 1.30% | 0.91% | 0.61x |
| PLAN | 10.67% | **21.96%** | 8.62% | 0.81x |

Reading: bad steps announce answers (`DISCHARGE` 2.4x) and revise (`BACKTRACK` 2.2x); good
steps declare objects and cite theorems. `PLAN` peaks at rating 0 — the neutral label is where
the model is talking about what it will do rather than doing it. This is a *lexical* result;
it says the surface of failure differs, not that the operation does.

---

## 3. CANONICAL vs CONTROLLER

The most useful thing in this document. **CANONICAL** = the step changes the mathematics;
a mathematician would name it. **CONTROLLER** = the step drives the prover: search,
automation, goal management, environment plumbing. The split is a *stated judgement*, not a
measurement; every contested call is listed in `operation_inventory.json`
(`canonical_vs_controller.contested_calls`) and in `research/operations/classify.py`.

| Corpus | n steps | CANONICAL | CONTROLLER | unclassified |
|---|---|---|---|---|
| LeanDojo random val+test (representative) | 8,766 | **77.87%** | **22.11%** | 0.02% |
| lean_canonical_records, top-60 heads | 232,165 | 76.91% | 23.09% | 0 |
| HML_V3 sealed 1,150, top-25 heads | 1,015 | 75.57% | 24.43% | 0 |
| Gold-125 annotated MATH | 769 | 82.31% | **0 — the axis has no controller value** | 17.69% UNRESOLVED |

The ~77/23 split is stable across three formal corpora with very different sampling. **The
interesting result is the last row.** The `core_operation` axis of `reasoning_ontology_v1`
contains no controller value at all; controller behaviour is carried on the *orthogonal*
`reasoning_mode` axis, where it is 113 `GOAL_MANAGEMENT` + 57 `SEARCH_META` = **170/769
(22.1%)** — within a point of the formal figure. That coincidence is the strongest
cross-source signal in this study, and it is a coincidence of *proportion*, not of vocabulary.

Composition of the two layers, on the representative LeanDojo sample:

| | share | main heads |
|---|---|---|
| CANONICAL:REWRITE | 22.34% | `rw` 1,658, `simp_rw` 148, `rwa` 107, `erw` 34 |
| CANONICAL:APPLY_THEOREM | 21.95% | `exact` 1,066, `refine` 478, `apply` 291 |
| **CONTROLLER:AUTOMATION** | **20.52%** | `simp` 1,113, `simpa` 215, `dsimp` 98, `gcongr` 49, `ring` 44 |
| CANONICAL:ASSERT_SUBGOAL | 7.85% | `have` 579, `suffices` 46, `replace` 29 |
| CANONICAL:INTRODUCE_BINDER | 7.67% | `intro` 291, `rintro` 177, `ext` 160 |
| CANONICAL:CASE_SPLIT | 5.01% | `rcases` 174, `by_cases` 90, `cases` 75 |
| CANONICAL:INTRODUCE_WITNESS | 3.26% | `obtain` 215, `use` 52 |
| CONTROLLER:ENVIRONMENT | 1.14% | `haveI` 32, `letI` 29, `classical` 20 |
| CONTROLLER:GOAL_MANAGEMENT | 0.44% | `next` 9, `all_goals` 8, `swap` 8 |
| (11 smaller canonical classes) | 9.8% | |

**The bias, made concrete.** In the HML_V3 1,150 corpus the same table reads
GOAL_MANAGEMENT **11.72%** and AUTOMATION **12.71%**: goal management has displaced automation
almost one-for-one. The corpus is 27x richer in prover bookkeeping and correspondingly poorer
in mathematics than mathlib actually is.

**The single contested call that matters:** `simp` is 12.7% of LeanDojo on its own. It is
classified CONTROLLER because the tactic name does not record which lemmas fired — but a large
share of `simp` calls are doing what a human would call *simplify* or *apply a definition*.
That one decision moves ~13 points between the two layers.

---

## 4. How much do the cross-source numbers deserve to be believed?

Columns B and C of §2 come from a regex cue lexicon. It was calibrated on the 769 gold spans,
where both the text and a human operation label exist. **334/769 = 43.4% of gold spans fire no
cue at all.**

| Cue | gold n | fired n | precision | recall | what actually fires it |
|---|---|---|---|---|---|
| INDUCT | 7 | 7 | **1.000** | **1.000** | INDUCT ×7 |
| VERIFY | 28 | 30 | 0.700 | 0.750 | VERIFY 21, DISCHARGE 6 |
| DISCHARGE | 90 | 128 | 0.695 | 0.989 | DISCHARGE 89, TRANSFORM 17 |
| TRANSFORM | 305 | 58 | 0.672 | **0.128** | TRANSFORM 39, VERIFY 4 |
| CONTRADICTION | 6 | 9 | 0.667 | 1.000 | CONTRADICTION 6, TRANSFORM 2 |
| APPLY_THEOREM | 29 | 18 | 0.611 | 0.379 | APPLY_THEOREM 11, TRANSFORM 6 |
| BOUND | 23 | 50 | 0.380 | 0.826 | BOUND 19, DISCHARGE 9, TRANSFORM 8 |
| APPLY_DEFINITION | 19 | 21 | 0.333 | 0.368 | APPLY_DEFINITION 7, TRANSFORM 5 |
| SUBSTITUTE | 7 | 15 | 0.333 | 0.714 | SUBSTITUTE 5, DISCHARGE 5 |
| CONSTRUCT | 12 | 12 | 0.250 | 0.250 | TRANSFORM 4, CONSTRUCT 3 |
| CASE_SPLIT | 15 | 41 | 0.220 | 0.600 | **TRANSFORM 16**, CASE_SPLIT 9 |
| COUNT | 23 | 77 | 0.169 | 0.565 | **EVALUATE 20, DISCHARGE 17**, COUNT 13 |
| DECLARE | 5 | 51 | **0.098** | 1.000 | **TRANSFORM 21, CONSTRUCT 11** |
| SELECT | 4 | 23 | 0.087 | 0.500 | DISCHARGE 5, VERIFY 3 |
| EVALUATE | 50 | 39 | **0.077** | **0.060** | **TRANSFORM 20, DISCHARGE 8** |
| ENUMERATE | 2 | 4 | 0.000 | 0.000 | — |

**Rule for reading §2.** Any operation whose only cross-source evidence is the proxy, at
precision < 0.5, should be treated as **UNMEASURED**: DECLARE, EVALUATE, COUNT, SELECT,
CONSTRUCT, CASE_SPLIT, APPLY_DEFINITION, SUBSTITUTE, BOUND. Only INDUCT, DISCHARGE, VERIFY,
CONTRADICTION, APPLY_THEOREM and TRANSFORM clear 0.6 precision — and TRANSFORM clears it at
recall 0.128, i.e. it detects one TRANSFORM in eight.

**The most seductive false match, found and separated.** `Let $k$ be a positive integer.`
(DECLARE, a mathematical act) and `Let's convert these numbers to base 10.` (PLAN, a
controller act) share the token `let`. Collapsing them would have produced a spurious
"DECLARE recurs strongly in model chains" result: the PLAN cue alone fires on 11.8% of model
steps. The lexicon separates `let X be …` from `let's <verb>`; the DECLARE cue still runs at
precision 0.098, which is the honest verdict on that operation.

### 4.1 Alignment verdicts — does the same name mean the same thing?

| Operation | Confidence | Human MATH | Formal Lean | Why |
|---|---|---|---|---|
| INDUCT | **HIGH** | "Let's prove by induction that the $n$th term … The base case $n=2$ holds" | `induction n with \| zero => … \| succ n ih => …` | Same schema, same obligations, same discharge condition. Proxy is exact: P=1.00, R=1.00, 7/7. |
| CASE_SPLIT | **HIGH** | "We can split $\|5x-1\|=x+3$ into two separate cases." | `rcases le_or_lt a b with h \| h` | Both replace one goal with an exhaustive family. **Caveat:** the informal version needs an explicit JOIN to combine branches (gap registry `MATH-GAP-0001`, recurrence 22, severity high); Lean's goal stack joins implicitly. The operation matches; its obligations do not. |
| APPLY_THEOREM | MEDIUM | "By AM-GM," | `exact div_add_div_same a b c` | Same move, different epistemic status: Lean names the instance and discharges side conditions; "By AM-GM" names no instance and checks none. The `warrant` axis exists precisely to record this — and its `UNKNOWN` value is used 125/769 times. |
| CONTRADICTION | MEDIUM | "which cannot be equal to 1, contradiction" | `by_contra h` / `exfalso` | Same logical shape, but the informal instances are mostly *local* contradictions inside a case analysis while `by_contra` is a *global* goal transformation. 6 gold instances is too few to separate them. |
| INTRODUCE | MEDIUM | "Let $k$ be a positive integer." / "Call the two integers $x$ and $y$." | `intro k` / `obtain ⟨x, hx⟩ := h` / `set y := …` | The informal side splits DECLARE vs CONSTRUCT; Lean splits binder vs existential-elimination vs abbreviation. **The two three-way splits do not line up**, and the 8-class effect vocabulary collapses all six to `INTRODUCE`. |
| DISCHARGE | **LOW — different operation** | "Thus, Brenda is $\boxed{3}$ years old." (90 steps, in 90 *distinct* trajectories; 89/90 contain `\boxed`) | `effect_class = CLOSE`, 107,006/241,265 = 44.4% | Informal DISCHARGE = *the final answer of the whole problem*, ~once per trajectory. Formal CLOSE = *this branch of the goal stack is finished*. Matching by name manufactures a 44%-vs-12% "recurrence" out of two unrelated events. |
| TRANSFORM | **LOW — different operation** | residual sink: 39.7% gold, 77.3% synthetic; covers "subtract 7 from both sides", modular reasoning, trig identities | `TRANSFORM_TARGET`: the focused goal's target string changed and nothing else did | Equal names, incomparable definitions. |
| APPLY_DEFINITION | **LOW — different operation** | explicit, citable step (19/769) | `unfold` + `delta` = 31/8,766 = **0.35%** | Definitional unfolding in Lean is mostly *invisible* — performed inside `simp`, `rfl` and elaboration, never logged. The formal frequency is an artifact of what Lean records, not of what proofs do. |
| SUBSTITUTE / REWRITE | **LOW — different operation** | SUBSTITUTE 7/769 = 0.9%, meaning "put the value you derived into the other equation" | `rw` alone 18.91%; rw family 22.34% | A **21x** frequency gap produced by the annotation scheme: the informal registries have no REWRITE, so rewriting is filed under TRANSFORM. |

**Verdict: 2 HIGH, 3 MEDIUM, 4 LOW.** Four of the nine "recurring" operations are
same-name-different-operation.

---

## 5. One vocabulary does replicate — and it is the computed one

`lean_effect_class` is the only operation vocabulary in the estate that was **computed** rather
than asserted. Its rule is documented nowhere. It was recovered here by tabulating
`effect_signature → effect_class` over all 241,265 records: 198 of 199 distinct signature tails
map to exactly one class; the recovered rule reproduces **179/179 decidable tails, 0
mismatches**; the one ambiguous tail (`dg-1|T0|A0|R0|B0`) resolves on `n_goals_after == 0`.

```
CLOSE                       if n_goals_after == 0
REWRITE_CONTEXT[_AND_TARGET] elif names_rebound  (and target_changed)
INTRODUCE[_AND_TRANSFORM]    elif names_added    (and target_changed)
ELIMINATE                    elif names_removed
TRANSFORM_TARGET             elif target_changed
NO_VISIBLE_CHANGE            else
```

Applying that rule with an independently written parser to the raw pretty-printed LeanDojo
states reproduces the census:

| effect class | 241,265-record census | recomputed on 8,151 LeanDojo tactics | Δ |
|---|---|---|---|
| CLOSE | 44.4% | 43.6% | 0.8 |
| TRANSFORM_TARGET | 24.3% | 25.3% | 1.0 |
| INTRODUCE | 11.3% | 11.4% | 0.1 |
| INTRODUCE_AND_TRANSFORM | 10.1% | 9.6% | 0.5 |
| REWRITE_CONTEXT | 5.6% | 5.7% | 0.1 |
| REWRITE_CONTEXT_AND_TARGET | 2.9% | 3.2% | 0.3 |
| NO_VISIBLE_CHANGE | 0.9% | 0.5% | 0.4 |
| ELIMINATE | 0.6% | 0.8% | 0.2 |
| *(goal-creating steps dropped)* | 18,315/259,580 = 7.1% | 615/8,766 = **7.0%** | 0.1 |

Max deviation 1.0 point on 8 classes plus an independent match on the exclusion rate.
**But see limit 1.9:** the 241k corpus is *built from* LeanDojo. This replicates the labelling
function, not the vocabulary's generality. It is still the only place in this project where a
reasoning-operation vocabulary has been shown to be reproducible from raw states by a second
implementation.

---

## 6. Reconciling the 13 existing taxonomies

**There is no operation taxonomy in the Arena repo.** Thirteen exist elsewhere in the estate.
Do not build a fourteenth.

### 6.1 They are not counting the same thing

| Taxonomy | n | Kind | Trust | Applied to |
|---|---|---|---|---|
| `lean_effect_class_vocabulary` | 8 | **effect** (state delta) | VERIFIED_FORMAL, **computed** | 241,265 transitions |
| `hmlv3_effect_class_vocabulary` | 8 | effect | VERIFIED_FORMAL | 1,000 rows — **stratified by class, not a natural distribution** |
| `minilang_operation_semantics` (arXiv:2507.18885) | 10 | operation | external, Isabelle-backed | published eval runs |
| `master_synthetic_action_vocabulary` | 15 | operation | ANNOTATION_UNVERIFIED | 3,978 (77.3% TRANSFORM) |
| `reasoning_ontology_v1.core_operation` | 19 | operation (+6 other axes) | ANNOTATION_UNVERIFIED | 769 |
| `reasoning_operation_registry_gold25_v0` | 48 | operation **spec** (typed inputs, families, warrants, HML rule) | ANNOTATION_UNVERIFIED | 25 trajectories |
| `reasoning_operation_registry_gold125_v1` | 66 | observed surface vocabulary | ANNOTATION_UNVERIFIED | 125 trajectories |
| `reasoning_stages` | 16 | **pipeline phases**, not operations | ANNOTATION_UNVERIFIED | 23 Gold-10 actions |
| `hmlv3_micromath_relation_taxonomy` | 8 | **representational exposure**, not operations | DETERMINISTICALLY_CHECKED | 611 probes |
| `gold125_gap_registry_v1` | 13 | **expressibility failures** | ANNOTATION_UNVERIFIED | 125 trajectories |
| `hmlv3_representation_genome_42_axes` | 42 | design axes — **RETIRED** (decision D-025) | ANNOTATION_UNVERIFIED | — |
| `arena_world_dimensions` | 12 | task difficulty | DETERMINISTICALLY_CHECKED | 676 tasks |
| `HML_ACTION_LANGUAGE_SPEC` | 1 | the frozen schema — **and its own refutation** | MEASURED | 400+ transitions |

**Operation counts spread 8 → 66 with no convergence, because three different kinds of object
are being counted:** what the step *does* (8/10/15/19/48/66), what *changed* (8/8), and
neither (16/8/42/12/13).

### 6.2 Where they disagree — stated, not merged

1. **`have` / ASSERT_SUBGOAL.** An *operation* in minilang; an *effect-axis value*
   (`goal_effect = CREATE_SUBGOAL`, used 12/769) in `reasoning_ontology_v1`; and **deleted
   outright** from the 241,265-record Lean corpus, which drops all 18,315 goal-creating
   transitions. Yet `have` is the 4th most frequent LeanDojo tactic at 6.61%, and the
   ASSERT_SUBGOAL family is 7.46%. **This is the clearest taxonomy disagreement in the
   estate, and it is a schema decision, not a domain difference.**
2. **`simp` / SIMPLIFY.** An *operation* in minilang; a `knowledge_layer` value
   (`SYMBOLIC_BACKEND`, used 9/769) in `reasoning_ontology_v1`; the largest automation block
   in Lean (`simp`+`simpa`+`dsimp` = 1,426/8,766 = 16.27%).
3. **REWRITE.** Absent from *every* informal taxonomy — folded into TRANSFORM — while being
   the single most frequent formal operation.
4. **VERIFY.** First-class in `reasoning_ontology_v1` and both gold registries; absent from
   minilang; structurally impossible in Lean.
5. **CONTRADICTION.** Absent from minilang, folded into `RULE`.
6. **v0 is richer than v1.** `gold25_v0` (48 ops) carries `required_inputs`, `allowed_types`,
   `warrant_type`, `family`, `hml_rule`; `gold125_v1` (66 ops) carries none of that but has
   frequencies and examples. They are not a version pair of one artifact; the "older" one is
   the better specification and should be the base for any executable vocabulary.
7. **JOIN.** The informal registries need `COMBINE_CASES` / `COMBINE_CASE_COUNTS` to close a
   case analysis; Lean needs nothing, because the goal stack joins implicitly. Recorded
   independently as `MATH-GAP-0001`, severity high, recurrence 22 across 5 MATH categories.

### 6.3 The two registries reconciled to the 19-value core axis

Measured mapping from the 66 observed operations to `core_operation`, over all 769 steps
(`observed_to_core` in the JSON). Examples:

| core_operation | n | absorbs (observed) |
|---|---|---|
| TRANSFORM | 305 | TRANSFORM 200, MODULAR_REASONING 26, SEQUENCE_RECURRENCE 23, TRIG_IDENTITY 23, SOLVE 6, EXPAND 4, FACTOR 3, +9 more |
| **UNRESOLVED** | **136** | **OTHER 125**, COUNT_CASES 4, SEARCH_META 4, +3 |
| DISCHARGE | 90 | DISCHARGE 87, DISCHARGE_GOAL 3 |

25 of the 66 observed operations are singletons. The bottom-up registry is mostly a list of
things that happened once.

---

## 7. What would settle it

Cheapest first. None of these needs new data acquisition.

| # | Measurement | Corpus & size | Independent check | Cost |
|---|---|---|---|---|
| 1 | **Second-annotator κ on the 769.** Every claim here rests on one annotator; there is currently no error bar at all. | `gold125_ontology_v1`, 769 (a 200-step stratified subset already yields a usable κ) | A second annotator labels the same spans blind from the 19-value axis; report κ per operation. | hours, no GPU |
| 2 | **Machine-check the mathematics of the 769.** | the 769 `state_delta` pairs, or the ~450 algebraic ones | SymPy equivalence `state_before → state_after`, exactly as already done for 867 of the 3,978 synthetic transitions. The machinery exists. | hours, CPU |
| 3 | **Annotate informal operations on *aligned* formal steps.** The only way to measure alignment directly rather than by name-matching. | miniF2F (500) or ProofNet-lean4 (371) — both already local, both carry an NL statement *and* a Lean proof of the same theorem; ~3,000 aligned steps | Label each Lean step with the informal vocabulary; measure agreement between informal label and tactic head. | days |
| 4 | **A negative-example formal corpus.** The only route to data that is both verified *and* contains failure. | Lean replay of deliberately wrong tactics on the existing 1,150 sealed states → 3,450 rejected steps | The Lean kernel: a rejected tactic is a *verified* negative. The counterfactual factory (stage100, 100 pairs) is a working prototype. | needs the mathlib build (already present on this machine) |
| 5 | **Reweight, do not resample, the 1,150.** | HML_V3 sealed corpus | Importance weights `w(head) = p_LeanDojo(head) / p_1150(head)`, from the 8,766-tactic representative sample measured here. Makes every existing result on that corpus quotable. | minutes |
| 6 | **Stop mining PRM800K for new operations.** | — | Already settled: the prior pilot measured **0/1000 = 0.00%** marginal semantic discovery over 858 distinct MATH problems, and the cue profile measured here is consistent with saturation — model steps and MATH reference sentences fire the same cues in nearly the same order. | zero |

---

## 8. If you read nothing else

- Recurrence across human / model / formal **can be established**, for 9 operation families,
  but the evidence is 769 labelled human steps and a proxy with precision 0.08–1.00. Four of
  the nine are same-name-different-operation.
- The **canonical/controller split is the durable finding**: ~77/23 in every formal corpus,
  and 22.1% controller-mode in the annotated human corpus. The large formal corpora are
  dominated by controller *vocabulary* (`simp`, `linarith`, `all_goals`) while the rich
  annotated corpus has no controller vocabulary at all — it puts that behaviour on an
  orthogonal axis.
- **Verification and richness remain anti-correlated.** Nothing on disk is both. This study
  did not change that, and no reconciliation of taxonomies can.
- Do not build a 14th taxonomy. Build measurement #1 and #3 above.

*Generated by `research/operations/build_inventory.py`. Machine-readable:
`artifacts/corpus/operation_inventory.json`.*
