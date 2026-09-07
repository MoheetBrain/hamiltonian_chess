# Formal Arena V1 — specification for three real mathematical task families

**Status: BUILT AND SHORTCUT-GATED. Not yet run against a Solver.**

**Read §2 first.** These families, as built, **cannot carry Game R**. They are a *solver
capability* instrument on real mathematical decisions. The name "Game-R Formal Arena" was the
sprint's working title and is retained only so cross-references resolve; §2 states precisely what
would have to change for Game R to become possible here.

Frozen before any Solver call. Sources, counts, gates and ceilings below were fixed and measured
first; no threshold may be moved after a Solver result.

---

## 1. Why these families exist

The V1–V7 mechanisms (`formal_expression_depth`, `transitive_dependency`,
`precondition_conjunction`) are synthetic probes over canonical states. Two of them are now known
to be shortcut-dominated: `first_mentioned_in_state` scores **1.0000** at `formal_expression_depth`
L1 and **0.8333** at L2, above V5's own frozen `shortcut_rule_max = 0.75`.

These three families instead pose decisions taken from **250,814 real Lean tactic transitions**
(LeanDojo Benchmark 4, mathlib4 `29dcec074de168ac2bf835a77ef68bbe069194c5`, train split only).

---

## 2. THE BLOCKING CONSTRAINT — why this is not Game R

Game R requires holding Σ, P, τ, π, C, D, U, V, B fixed and varying **only** R: the *same
canonical content* re-rendered through different representations.

All three families carry **raw Lean pretty-printed strings** (`state: str`,
`options: tuple[str, ...]`) and contain **zero** references to `CanonicalState` or
`CanonicalAction` — verified by grep; `formal_structural` has 3. A pre-rendered string **fixes R**
at "Lean's pretty-printer". Eight representation arms fed such an item would receive byte-identical
inputs, so no representation effect is even expressible.

**What these families do measure:** solver capability on genuine mathematical decisions, with real
distractors and audited shortcuts. That is a legitimate and currently more tractable question than
Game R, and it is the right instrument for choosing a scout Solver or a difficulty frontier.

**What would make them Game-R capable.** A canonical projection per family: parse the Lean
pretty-printed state into `CanonicalState` and each option into `CanonicalAction`, then render
through `ModelViewCompiler` under `assert_game_r_genome`. This is a substantial, separable task and
is **lossy** — `docs/CANONICAL_VNEXT_PILOT.md` measured **0 of 368** real Lean states mapping
losslessly into `arena-canonical-v0.1.0`, with 20.7% unmappable. `releases/TRAINING_LANGUAGE_V0/`
is the natural target instead of the frozen canonical schema, since it handles the REQUIRED gaps
natively. Until that exists, Game R runs only on `formal_structural`.

---

## 3. Frozen sources

| Item | Value |
|---|---|
| Dataset | LeanDojo Benchmark 4, leandojo 2.0.0 |
| mathlib4 commit | `29dcec074de168ac2bf835a77ef68bbe069194c5` |
| Development source | `random/train.json` (373,077,058 B), `corpus.jsonl` (60,420,959 B) |
| Train steps | 250,814 over 118,517 theorems (independently reproduced by two agents) |
| **Sealed, never opened** | `novel_premises/{val,test}.json`, `random/{val,test}.json` — see `artifacts/manifests/SEALED_SPLITS.json` |

Every environment raises `SealedSplitViolation` on the four sealed paths. `steps.jsonl` covers all
splits and must be filtered to `split == "train"`; `random/train.json` has **no** `split` field —
the split is a property of the file.

---

## 4. The three families, as measured

### A. Premise selection — the primary family

Given a proof state, choose the premise used by the valid next transition among K candidates.

- **63,831 usable items**, 24,718 distinct gold premises, K = 6 (8 at L4).
- Distractor tiers, in priority order: (a) premises used elsewhere in the **same proof**;
  (b) frequency-matched premises from the same module; (c) scope-valid premises by transitive
  import closure, restricted to declarations actually used as a premise in train;
  (d) lexical-overlap-matched. **No random-corpus negatives survive.**
- **6,877 transitions excluded** because the gold premise name is already printed in
  `state_before` — a real leak, not hygiene.
- 91,554 multi-premise steps excluded: no single correct answer.

| level | K | items | axis |
|---|---|---|---|
| L0_explicit_positive | 6 | 56,847 | gold's statement given verbatim, name redacted |
| L2_standard | 6 | 63,831 | full tier priority |
| L3_same_module_freq_matched | 6 | 58,686 | tiers a+b, frequency slack 1 |
| L4_high_similarity | 8 | 58,925 | similarity slack 0, goal-only context |
| ~~L1_cross_module~~ | 4 | — | **REJECTED_SHORTCUT** |

### B. Rewrite direction

Given a state, a rewrite equation and a target, choose FORWARD or REVERSE.

- **Measured direction distribution refutes the prior estimate:** reverse is **19.42%** per rewrite
  element (n = 135,792) and **25.12%** per tactic first-element (n = 56,292) — *not* 36.9%. The
  binary is **not** naturally balanced.
- Population rule, fixed before any accuracy was measured: one item per rewrite tactic from the
  **first bracket element** only, because only that element acts on the recorded `state_before`.
  Mixed-direction brackets (23.17%) contribute one item each. `simp_rw`/`nth_rw` censused but
  excluded (different operational semantics).
- `state_after` is **withheld** — showing it would make the task a diff.
- **Control required:** within-lemma direction balancing, so every lemma contributes equally many
  forward and reverse items. Controlled pool **3,466** (1,733/1,733) over 758 lemmas.

### C. Legal vs illegal transformation

Given a state and a proposed action plus result, classify VALID or INVALID.

- **24,000 items as 12,000 matched pairs** sharing the before-state, so every state-only predictor
  sits at 0.5 **by construction**.
- **100% `TIER_B_CONSTRUCTED`; zero Lean-verified items.** The Tier-A replay is specified but not
  run (≈3,100 attempted replays for 1,000 items at the historical 32/100 yield).
- 7.1% of shape-eligible attempts discarded because invalidity could not be argued; a further
  62.7% discarded to keep surface statistics matched.

---

## 5. The shortcut gate — the governing rule

**Fitted on development-train only, evaluated on a grouped held-out split** (by `proof_id` /
theorem / source file, never a random row split). Predictor classes: constants and label frequency,
option position, string length and length delta, lexical and token-multiset overlap, premise and
lemma frequency priors, name affixes and char-n-grams, declaration order, same-file/same-module
indicators, identifier novelty, edit distance, plus shallow logistic and decision trees at depth
2/4/8 over the combined features.

| family | chance | ceiling | best shortcut | verdict |
|---|---|---|---|---|
| premise selection | 0.167 | **0.45** | **0.327** (depth-6 tree) | PASS |
| rewrite direction | 0.500 | **0.65** | **0.6026** (GB depth-3), controlled | PASS *under control* |
| legal transformation | 0.500 | **0.65** | **0.5197** graded pooled | PASS |

### What the gate rejected — recorded because it matters more than the passes

- **Rewrite direction, uncontrolled: 0.7085 — BREACHED.** Carried entirely by lemma-identity
  features (char-n-gram logistic 0.6748 alone; per-lemma direction prior 0.6376). Under the
  within-lemma control every lemma-constant feature collapses to **exactly 0.5000**.
- **Premise selection `L1_cross_module`: 0.866 — REJECTED.** One named control reached 0.644, still
  breached, so the rung was **removed rather than tuned**. Retained in `REJECTED_LEVELS` so the
  rejection is reproducible.
- **Legal transformation `violated_precondition`: 0.777 — killed.** The only textually checkable
  precondition violation raises the action's novel-identifier count by +0.92 on average. Structural,
  not tunable; a non-detectable version needs Lean.
- **Legal transformation `wrong_successor`: 0.700 → 0.664 after one repair — killed.** Residual is
  before/after Jaccard at 0.644: a state one step from the goal simply resembles it more.
- **`wrong_rewrite_direction` is AT RISK at 0.6472** — under ceiling by 0.003 with SE ≈ 0.013.
  Recommendation: exclude it, or defer to the rewrite-direction family which controls for lemma
  identity properly.

**Protocol, fixed in advance:** at most **one** named control per breached axis, re-measured
**once**. If it still breaches, the axis or rung is dropped. No iterating until a number passes.

---

## 6. Leakage guarantees

- Premise selection: **297,520 items audited, zero leak problems**; checks are token-anchored and
  redaction shares one pattern with the auditor so the two cannot disagree. Three audit false
  positives were found and fixed en route.
- Rewrite direction: `leakage_violations()` re-derives from the **actual rendered string**; 0
  violations; 200 assembled items dropped by a last-line-of-defence guard; a deliberately planted
  leak must be caught, so the test cannot fail open. Two real bugs found: `corpus.jsonl` sometimes
  stores whole proof bodies containing other proofs' `rw [...]` text, and `↔`/`=` precedence was
  mis-slicing iff-lemmas.
- Legal transformation: negatives are matched pairs, so provenance cannot separate the classes.

**Determinism:** two independent full runs produced byte-identical item files
(splitmix64 seeded per item by `blake2b(seed|proof_id|step_index|level)`).

---

## 7. What running this would and would not establish

**Would:** whether a given Solver can make real mathematical decisions above a measured
surface-heuristic floor, and where its frontier sits — the difficulty ladder needed before any
representation comparison is meaningful.

**Would not:** anything about representation. See §2.

**Would not, either:** anything Lean-verified for family C, which is entirely
`TIER_B_CONSTRUCTED`. A negative there means "constructed to be invalid", not "the kernel rejects
it".
