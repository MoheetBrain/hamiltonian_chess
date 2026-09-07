# Future Environment Families — candidate report

**Status: CANDIDATE REPORT ONLY. No instrument was designed, built or preregistered.**
Fitness V6 is explicitly *not* authorised (`docs/GAME_R_STATUS.md`).

**Provenance of the numbers.** Counts and shortcut accuracies come from
`artifacts/corpus/local_formal_inventory.json` (measured), `artifacts/reports/next_action_leakage.json`
(measured), `artifacts/corpus/source_registry.json` (licence/version verified) and
`artifacts/corpus/operation_inventory.json` (measured). Figures marked **~** are the inventory's
own extrapolations from measured proportions, not exact counts. A dedicated ranking agent was
started for this document and terminated early on a session rate limit; its unfinished
measurements are **not** used, and nothing here rests on them.

---

## 1. Why the current probes are suspect

The V5 mechanisms ask which identifier is deepest, whether a dependency is transitive, and whether
two preconditions conjoin. Phase 5 qualified 0 of 3. Two independent measurements now suggest the
problem is the **task family**, not only the solver:

- **`formal_expression_depth` leaks worse than published.** `first_mentioned_in_state` scores
  **24/24 = 1.000** on the shallow stratum, **22/24 = 0.9167** at deep L3, and **78/96 = 0.8125**
  pooled over the four-level bank. (An earlier pass in this workstream quoted a single 0.913
  figure; the stratified decomposition above is the accurate one and supersedes it — it was
  cross-checked by an independent audit.) `more_frequent_in_state` = **0.798**; "earlier in local
  context" = **0.90**. The spec anticipated 0.72 and the V5 result reported 0.833.
  **Filtering cannot rescue this mechanism** — the shortcut is a property of how real Lean terms
  are written, and it is strongest exactly where the ladder is easiest.
- **The other candidate substrate is fully degenerate.** A model-free predictor reproduces the
  entire gold `NEXT_ACTION` target on **676/676** tasks (held-out 96/96), and 0.8195 of it with
  **zero arithmetic**. See §5.

A family that a surface heuristic solves cannot measure representation, no matter which solver
reads it.

---

## 2. Ranking

Ranked by expected scientific value per unit of effort. Effort assumes the local assets in
`docs/CORPUS_STRATEGY.md`, all of which need **zero download**.

| # | Family | Usable items | Ground truth | Lean needed? | Effort | Verdict |
|---|---|---|---|---|---|---|
| **1** | **Premise selection** | **~163,300** (62.9% of steps cite ≥1 premise); 5,517 in held-out val+test | LeanDojo `<a>premise</a>` annotations name the premise *and* where it is defined | No | MED | **BUILD FIRST** |
| **2** | **Rewrite direction** | **~49,100** `rw` steps, **36.9% reverse** | Recorded tactic text | No | LOW | **BUILD** — naturally balanced binary |
| **3** | **Legal vs illegal transformation** | 616 structured pairs (461 target-changing); ~259,580 text pairs | Real successor vs `relabel()`-corrupted successor | Tier B free; Tier A at **32%** replay yield | MED | **BUILD** |
| 4 | Semantic equivalence (ProofNetVerif) | 3,752 (external, 406 KB, MIT) | Human-verified NL↔Lean pairs | No | **LOW** | **BUILD** — see §4 |
| 5 | Progress / goal-closure | 1,000 balanced effect-class items; ~105,100 binary | Recorded effect class | No | LOW | Build reduced form only |
| 6 | Premise-set sufficiency | ~89,700 with ≥2 premises | **Unsound without Lean** — both corpora undercount premises by design | Yes | HIGH | **Ship as attribution, not sufficiency** |
| 7 | Subgoal selection | ~126 genuine | — | Yes | HIGH | **REJECT** — see §3 |
| 8 | Quantifier instantiation | ~1,540 `use` steps | — | Yes | HIGH | **REJECT** — see §3 |

### Why premise selection is first

It is the only family that is simultaneously large, verifier-backed without re-running Lean,
supplied with **real** distractors, and equipped with a purpose-built OOD split.

- Distractors come from the 180,973-declaration corpus, not invention. The hardest and most
  informative class is *premises cited elsewhere in the same proof* — plausible, in-scope, wrong.
- LeanDojo's `novel_premises` split guarantees val/test proofs use at least one premise never seen
  in training. That is the cleanest available defence against solving the task by recall.
- It matches a real capability. Premise selection is the bottleneck in every practical prover.
- **Known leaks, both controllable:** lexical overlap between premise name and goal, and a raw
  frequency prior over `corpus.jsonl`. Both must be *measured and reported*, and a
  frequency-matched distractor sampler is a precondition of use, not a refinement.

### Why rewrite direction is second

Cheapest credible family in the estate. **36.9% of `rw` steps are reverse (`←`)**, so the binary is
naturally balanced without construction — no balancing artefact, and the destroyed-twin control is
not needed to establish a 0.5 baseline. It needs no Lean and no elaborator.

**The one absolute rule: never show the tactic.** The answer is written in the input otherwise.

---

## 3. Rejections — stated plainly

- **Subgoal selection.** Lean's focusing convention makes "the first goal" correct by construction.
  Only **~126** steps involve explicit reordering, and even for those, optimality is unestablished —
  a different order may prove the theorem equally well. A task whose "correct" answer is a
  convention measures convention-following.
- **Quantifier instantiation.** ~1,540 `use` steps, but type-uniqueness collapses most items to a
  single admissible witness, and separating the rest needs the elaborator. High cost, small yield.
- **Full proof-state progress.** Blocked, not merely expensive: **no corpus on disk records a
  second, failed, or alternative action.** A Lean trace holds only the steps that were kept. The
  reduced binary form (does this action close the goal?) is constructible; the interesting form —
  which of these candidate actions makes progress? — has no ground truth available.
- **Premise sufficiency.** Both corpora undercount premises by design, so a "sufficient" label
  would be unsound. Reframe as premise *attribution* (which premise was used) — that is exactly
  family 1, and it is sound.

---

## 4. The non-formal candidate worth keeping

**ProofNetVerif** (MIT, 3,752 items, 406 KB): decide whether a Lean statement is semantically
equivalent to an English statement. It earns its place for three reasons that have nothing to do
with size:

1. **It fits the existing controller unchanged** — one greedy grammar-constrained JSON A/B answer,
   no reasoning, no search. Zero new instrument machinery.
2. **Clean 0.5 baseline** from a balanced binary, so the mathematical-constant negative control
   problem (§6) does not arise.
3. **No comparable surface proxy.** Depth has `first_mentioned_in_state` at 0.913; semantic
   equivalence has no analogous cheap heuristic. That is the whole point.

It is the cheapest test of "can this solver do *any* mathematical decision at all", and it should
run before any expensive formal family is built. Note `ProofNet` itself (371 English↔Lean pairs) is
already local, so a pilot needs no download at all.

---

## 5. Shortcut auditing is the design activity, not a checkbox

The `NEXT_ACTION` leakage study is the template every future family must survive. Measured:

| Field | Model-free exact, zero arithmetic |
|---|---|
| `action_id`, `operation`, `target_ids`, `warrant`, `generated_obligations`, `expected_usefulness`, `preconditions` | **1.000** each |
| `arguments` | 0.8195 |
| **Whole target** | **0.8195** (→ **1.000** with one integer operation) |

Only 122/676 items (18.05%) need arithmetic at all, and that arithmetic is one integer operation on
two operands printed verbatim in the prompt.

**Obfuscation did not repair it.** Scrubbing `state_id` alone changed nothing (`object_id` carries
the same prefix); scrubbing every case identifier consistently in observation *and* target returned
to 1.000. A leak carried by redundant identifiers is not fixed by hiding one of them.

**`assert_no_answer_leakage` would not have caught it, even if called.** Its signature is
`(observation, kind)` — it **never receives the gold target**, so it is structurally incapable of
testing any observation→answer relation. It checks that two containers are empty, which
`project_state_for_observation` already guarantees, making it vacuously true.

### The fail-fast check to adopt

Before any model call is spent on a new family:

> Fit a bounded model-free predictor — constants, MDL lookups, affix rewrites, field copies, and
> anti-unification templates — on the training split only, and evaluate it on a held-out split.
> Preregister a ceiling. If the predictor beats it, the family is rejected before the instrument
> is written.

This costs minutes of CPU, needs no model, and would have killed the `NEXT_ACTION` family before
the historical GPU sprint was run. It is the single highest-value process change in this report.

---

## 6. Design constraints any next instrument inherits

Earned from the V1–V5 failures; not optional.

1. **Count tokens, never characters.** V4's `chars/2.0` guard voided 30 rows that fit; measured
   chars/token spans **2.74–7.43** across surfaces, so any character heuristic is
   representation-specific and silently biases against verbose arms.
2. **Grammar-constrained decoding.** V5: 0 malformed in 432 rows versus V4's 89 in 348, and
   answer-neutral (agreement 1.000). Raising `num_predict` fixes none of it.
3. **L0 must state the relation outright.** A minimal-size control is not an explicit positive;
   that was V4's defect.
4. **The destroyed-twin negative control is a mathematical constant at 0.5000** for any
   deterministic solver — verified 24/24 twin pairs with byte-identical prompts and outputs. Any
   gap gate therefore collapses to an absolute accuracy floor. **Derive the frontier target from
   the gate arithmetic** rather than declaring it separately, or the two drift apart (they did:
   `docs/PHASE6_INTEGRATION_MAP.md` §8).
5. **Largest-answer-share, not choice-flip.** Choice-flip passes a coin-flipper 65.6% of the time
   at six families; answer-share catches constant answering with probability 1.
6. **Per-mechanism verdicts, never pooled.** Pooling hides ceilings and floors.
7. **Identifier obfuscation must be an arm, not an argument.** It is structurally feasible on the
   canonical corpus — `transcribe()` keeps names in `.value` and shape in `.args`, so a salted
   bijection preserves depth, arity, binders and token multiset exactly, with `relabel()` as the
   template. It is **not** cleanly feasible on LeanDojo's pretty-printed states without re-running
   Lean. That asymmetry should drive corpus choice.
8. **Budget the Lean tax.** Historical replay yield was **32/100**, not the ~44% the docs claim.
   Any design needing kernel adjudication must plan for roughly a third.
9. **Use the built mathlib, not the source checkout.** Two checkouts of the same pinned commit
   `29dcec07…` exist and they are easily confused:
   `HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec07…/mathlib4` is **built**
   (18 GB, **5,680** `.olean`, all 4,447 Mathlib modules) and is the one that supports offline
   replay; `HML_V3/external/checkouts/mathlib4-29dcec0` is an **unbuilt source copy**
   (349 MB, 38 `.olean`). Two independent audits reached opposite conclusions about "is mathlib
   built?" purely by looking at different paths. Name the path explicitly in any design.

---

## 7. Contamination position

mathlib is `HISTORICALLY_EXPOSED` (its goal states were read during V5 design) and **exposure is
transitive**: LeanDojo Benchmark 4 and miniCTX's `mathlib` config inherit it. None can serve as
clean OOD. `gemma4:12b`'s training cutoff is **UNRECORDED**, so every temporal-holdout claim is a
hypothesis. The strongest OOD axis actually available is the **formal-system** axis — a second
system such as Metamath — which needs no cutoff at all. Full position in
`docs/CORPUS_STRATEGY.md`.

**Seal before building:** LeanDojo `novel_premises/val.json` and `test.json` are the PROMOTION pool
for family 1 and are still unread. Do not touch them for adapter debugging; use `random/train.json`.
