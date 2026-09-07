# What Works, What Doesn't

**Written 2026-09-07, after the V7 total forensic audit.** One page of plain statements, each
backed by a file or an artifact. No sentinel is created or reinterpreted here.

**The one-line state:** the machinery is real and mostly sound; the *scientific* question the
project exists to answer has **never been asked**, because no experiment has ever scored two
representations against a Solver.

---

## WORKS — verified, reproducible

| Thing | Evidence |
|---|---|
| **Canonical world and verifier** | 676-task Gold world, deterministic generator, `NativeVerifier` structural checks. `arena/canonical/`, `arena/verifier/` |
| **Representation machinery** | 14-gene `LanguageGenome`, 8 seed surfaces, `GenomePhenotypeLanguage`, lossless codec with round-trip tests. Rendering is a pure function — AST scan finds no `random`/`time`/`uuid`/`os` anywhere on the path |
| **V7's arithmetic** | The entire verdict **recomputes exactly** from the 864 stored rows with no `arena` import: **252 checks, 0 mismatches**. Probe bank rebuilds bit-exact (`dev_pool_hash f804e0d9…`) |
| **Cache and provenance discipline** | 864/864 rows `FRESH`, zero cache hits, zero `CROSS_CONDITION`. 804/804 surviving entries corroborate the artifact; 0 orphans. `872 = 864 + 8 Q0`, proved |
| **Preregistration discipline** | V7 spec committed at `e66bab1` *before* the first call; nothing moved after; the refusal to drop `SHORTCUT_MARGIN` to 0.08 was correct and is endorsed by the audit |
| **Grammar-constrained output protocol** | 0 malformed in 432 (V5) vs 89 in 348 (V4); `completion_tokens == 6` on all 864 V7 rows. This repair is real and permanent |
| **`TRAINING_LANGUAGE_V0`** | `releases/TRAINING_LANGUAGE_V0/`, `package_hash 443c8f79…`, 279 tests. Every REQUIRED canonical-vNext gap native. Determinism *measured* (AST scan, attribute-order rotation, `PYTHONHASHSEED` variation, exact round-trip) |
| **Three real formal task families** | 63,831 / 3,466 / 24,000 items from 250,814 real Lean transitions, each shortcut-gated *before* any Solver call. `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md` |
| **Tournament harness** | `arena/experiments/game_r_formal_v1.py`, 8-component cache identity with a per-component test, `FRESH`/`SAME_CONDITION_REUSE`/`CROSS_CONDITION` scope, fail-closed budget, `--dry-run` |
| **`precondition_conjunction`'s generator** | **Balanced by construction**, verified in source: `_premise_family` builds `objects` and `propositions` once and passes them unchanged to all three arms; answer identifiers never move |
| **Test suite** | 964 passed, 1 skipped; `ruff` clean; `mypy` clean (130 files) |

---

## DOESN'T WORK — confirmed defects

| Thing | Why | Severity |
|---|---|---|
| **The shortcut audit reads the wrong string** | Scores rules on `canonical_json(state)` (`fitness_v5.py:798-799`) while the Solver reads the **rendered** surface (`:550-565`). `first_mentioned_in_state` is **exactly 0.5000 in all twelve cells** on the real input — and it produced *both* `VOID_SHORTCUT` verdicts | CRITICAL |
| **`transitive_dependency`'s void** | The voiding rule is at **chance (0.5175)** at population scale. True margin 0.149, or 0.110 against the strongest adversary — **both clear the 0.10 gate**. REFUTED | CRITICAL |
| **`formal_expression_depth` as a Game-R mechanism** | Solvable at **1.000** by bracket-depth counting on the rendered prompt, on **all eight surfaces**. Under any bracketed serialisation "max AST depth" *is* "max delimiter balance", so the optimal strategy is **representation-invariant**. Unrescuable: deepest == first in 79.3% of donor states | CRITICAL |
| **The 0.10 margin at n=24** | Margins are `k/24`, so 0.10 is **unrepresentable** — the executed gate is 0.125, 25% stricter than declared. Power to distinguish .083 from .10 is **0.069**; ≈4,000 items would be needed | CRITICAL |
| **The shortcut family** | Effectively **two rules, not seven** — four are structurally pinned at 0.5000. Arena's port **deleted the Bonferroni + Clopper–Pearson correction its own cited ancestor used**, leaving 0.75 *below* the null mean of a max-over-7 (0.744), crossed by noise 67% of the time | HIGH |
| **Position-invariance gating** | The dominant error mode is **position anchoring** (56.5% of wrong rows; 95.2% "A" on swapped arms), and `position_invariance_min` is set **at chance** — the selected cell passes it at 0.583 | HIGH |
| **`relabel()`'s counterfactual** | Blind to exactly the rules that matter (`cf_blindness = 1.000` for every order/position/frequency/depth rule). Its docstring claim is refuted by measurement | CRITICAL |
| **The sealed-split manifest** | Under-declares exposure by 60%. `novel_premises/{val,test}` were parsed **5h16m before** the seal; the *shipped* distractor tiers are the *measured* policies, so contamination is **design-level**. The premise-selection promotion pool is spent | HIGH |
| **The three new families as Game-R substrates** | They emit **raw Lean pretty-printed strings** — zero `CanonicalState`/`CanonicalAction`. A pre-rendered string **fixes R**; eight arms would receive byte-identical input | BLOCKING |
| **The Astra bridge as a Game-R arm set** | Fails the cheapest falsifier — *no ≥40-char span of Lean text shared across arms* — at **300/300 × 5/5**. Four of five codecs are 91–98% identical JSON behind a different line prefix | BLOCKING |
| **Route B's historical evidence** | `verified` was a three-key presence check reading 1.000 everywhere; `stratified_split`'s seed is inert; World-v0 `NEXT_ACTION` is model-free solvable **676/676** | VOID |

---

## NEVER TESTED — the honest gap

- **No representation has ever been scored against a Solver.** All 864 V7 rows carry one
  `candidate_id`; V4's frozen manifest has an 8-founder roster with `probes: []`; the 120 mutants
  appear only in a deterministic Gate-0 check. `Δ = Acc(R_A) − Acc(R_B)` has been computed **once**
  (V3) and was ruled invalid.
- **No multi-seed run exists anywhere.** Determinism is asserted from T=0 and identical twin pairs,
  never from a re-run.
- **No OOD claim is available.** mathlib is historically exposed, exposure is transitive, and both
  Solvers' training cutoffs are **unrecorded**.
- **No Lean-verified negatives.** Family C is 100% `TIER_B_CONSTRUCTED`; only 32 transitions
  anywhere have ever been freshly replayed.

---

## The recurring failure mode, named

**Granularity substitution** — computing a statistic on a coarser population than the claim drawn
from it. It is not a one-off:

- V5's only pre-run shortcut safeguard **pooled all 864 probes across mechanisms and levels**,
  diluting a 1.000 leak into `0.7153 CLEAN` — the "0.72" cited in the spec as its sole defence.
- Phase 6 §11 asserted a counterfactual whose refuting number had been published **9h18m earlier**.
- Phase 6's "cache hits = 0" was **asserted, not measured**: `run_development` computes
  `cache_hits` and never writes it.
- Route B's loss ranking compared arms whose token exposure was never matched.

**The enforcement rule that would stop it:** no document may assert a cell would qualify unless
every gate was evaluated on that exact cell — mechanised as a frozen `GatedCell` type that cannot
be *represented* with a partial gate set.

---

## What to do next

**One experiment.** Extend `precondition_conjunction` upward until the control lands in
[0.70, 0.85], then run the programme's **first founder tournament** on it. It is the only clean
mechanism, and clean **by construction** rather than by audit — which matters, because no rule in
the inherited family can leave chance there, so its 0.500 measures the family's blindness.

Preconditions, all at **zero model cost**: audit shortcuts on the **rendered prompt, per
representation**; enforce the ≥40-char cross-arm span check; score `always_first_option` against the
**model's answers**, not the key; separate selection and qualification pools; size n for the
decision. Kill condition: if a stronger adversary finds signal on the extended ladder, halt.

**Not next:** real-Lean premise selection in its current form (fails the span check 300/300 × 5/5,
promotion pool spent). It is the right *second* step — the elaborated object already exists locally
in `lean_runtime_v2_full.canonical.part-*`, but only **190** transitions are
single-premise/single-goal. **Scale, not method, is the gap.**

**Also not next:** a V8 on this probe bank. The preregistered stopping rule forbids it and the
evidence supports the rule.

---

## Standing sentinels

`RSTAR_NOT_IDENTIFIED` · `GAME_R_INSTRUMENT_NOT_QUALIFIED` (operational) ·
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` (scientific) ·
`TRAINING_LANGUAGE_V0_BASELINE`
