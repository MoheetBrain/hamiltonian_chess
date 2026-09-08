# GAME_R_PRECONDITION_FOUNDER_V1 — Preregistration

> ## STATUS: SUSPENDED, NEVER FROZEN — 2026-09-08
>
> This document is a **draft skeleton that was never enacted**. It was superseded mid-build when
> the project owner reset the mission: the controlled representation experiment is now a *local
> fitness assay* inside the open-ended language-discovery system defined in
> `docs/HAMILTONIAN_CHESS_META_GOAL.md`.
>
> **No founder model call was ever made under this spec. No threshold in it has ever governed a
> result. Every `TBD` below is still `TBD`.** Its roster, shortcut gate, band and endpoints are a
> *design*, not a commitment, and must not be cited as a preregistration.
>
> The Solver it names, `qwen38-rvn:latest`, was deleted from the local runtime on 2026-09-08 and
> is unrecoverable, so this spec could not be executed as written even if it were reinstated.
>
> Salvage record: `docs/PHASE8_SALVAGE_HANDOFF.md`.

**Original header follows.**

**STATUS: DRAFT SKELETON — not yet frozen. Every `TBD` below is filled from committed artifacts
before the first founder model call, and this header is replaced by the freezing commit SHA.**

Experiment `arena-game-r-precondition-founder-v1.0.0`. Module
`arena/experiments/game_r_precondition_founder_v1.py`. Harness
`arena/experiments/game_r_formal_v1.py` (`arena-game-r-formal-harness-v1.0.0`, unchanged).
Generator `arena/environments/precondition_ladder.py` (`arena-precondition-ladder-v2.0.0`).
Adversary family `arena/experiments/rendered_prompt_adversary.py`
(`arena-rendered-prompt-adversary-v1.0.0`). Power module `arena/experiments/precondition_power.py`.

---

## 0. What this experiment is, and is not

This is the programme's **first mechanism-specific representation pilot**. It computes, for the
first time in project history, the paired quantity

    Δ(R_A, R_B) = Acc(Solver | R_A) − Acc(Solver | R_B)

on **identical mathematical tasks** for a fixed Solver, on **one** clean mechanism
(`precondition_conjunction`). It is admissible under V7's own `VOID_CEILING` verdict because the
only variable class it changes relative to V7 is **D** (task difficulty), and it changes
representation **R** only inside the tournament, which is what Game R is.

It is **not** sufficient for `RSTAR`, `ROBUST_CANDIDATE`, or any universal representation claim.
The two-qualified-mechanism gate for broad Game-R fitness (`GOAL.md` §16 evidence levels; V5/V7
`minimum_qualified_mechanisms = 2`) is **not** weakened here; this pilot sits below it by design.

## 1. Scientific question

> Given exactly the same precondition-conjunction mathematics — same objects, same
> `requires(answer, premise)` propositions, same `holds(premise)` assumptions, same candidate
> actions, same option order, same visible information — does changing **only** the
> representation R cause a reproducible change in Solver success?

Allowed final sentinels (exactly one will be recorded):

| Sentinel | Condition |
|---|---|
| `REPRESENTATION_EFFECT_ON_PRECONDITION_FOUND` | ≥1 baseline comparison rejects H0 at Holm-adjusted α = 0.05 **and** the family-clustered 95% CI for Δ excludes the practical-equivalence region boundary in the same direction (§10) |
| `REPRESENTATION_PARITY_ON_PRECONDITION` | every baseline comparison's clustered 95% CI lies inside the practical-equivalence region (§10), i.e. equivalence is established, not merely non-significance |
| `PRECONDITION_INSTRUMENT_NOT_QUALIFIED` | no stratum lands in the frozen band on the control arm, or the rendered-prompt shortcut gate fails on any founder arm, or the explicit-positive control fails on any arm |
| `EXPERIMENT_INVALID` | any invalidation rule in §13 fires |

A result that is neither equivalence nor a rejection (an inconclusive CI) is recorded as
`REPRESENTATION_PARITY_ON_PRECONDITION` **only if** the equivalence test passes; otherwise it is
reported verbatim as **INCONCLUSIVE** under the parity sentinel with the CI, and is not called
parity in prose. This is stated now so an inconclusive result cannot be dressed as either outcome.

## 2. Variables held fixed (GOAL.md §3, §13)

| Variable | Frozen value |
|---|---|
| Σ | `arena-canonical-v0.1.0`; states from `precondition_ladder` |
| P | Track E, `ContentGenome()` default, `assert_game_r_genome` on every arm |
| **R** | **VARIES — the founder roster of §7** |
| τ | the Solver's own tokenizer through Ollama; exact counts by `num_predict=1` preflight |
| π | `qwen38-rvn:latest`, digest `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`, family qwen35, 27.3B, Q4_K_M, template passthrough, Ollama 0.33.2, Apple M5 Max 48 GB, 100% GPU |
| C | one greedy grammar-constrained answer; no reasoning tokens; `think` off |
| D | ONE frozen stratum of the precondition ladder (§5), fresh `TOURNAMENT` pool |
| U | none |
| V | `NativeVerifier` + `precondition_ladder.independent_truth` (independent subset check) |
| B | `num_ctx` 32768, `num_predict` 64, temperature 0.0, seed 20260905, `top_k` 64, `top_p` 0.95, bare (`raw: true`) |

Decoding bytes are asserted equal to V5/V7's frozen values by test.

## 3. Output protocol (fixed for every arm)

Grammar-constrained JSON, `{"answer":"OPTION_A"}` / `{"answer":"OPTION_B"}`; schema
`game_r_formal_v1.response_schema(2)`, hash `TBD`. Envelope: `_assemble` with
`SyntaxGuidePolicy.SHARED_CONSTANT` (one guide string shared by every arm; the per-arm
`acquisition_guide` of V5 is **not** used). Envelope signature and answer-protocol hash must be
identical across arms on every task (harness parity check).

## 4. Generator and invariants

`precondition_ladder.build_family(stratum, pool, index)`; salts include the environment version,
stratum, pool and index; pools `DEV`, `ADV_DEV`, `SHORTCUT_EVAL`, `TOURNAMENT`, `SMOKE` are
disjoint by construction. Every family: `objects`, `propositions`, `goal` and the `options` tuple
are built **once** and shared by ORIGINAL / COUNTERFACTUAL / DESTROYED; only `assumptions` differ,
and their symmetric difference is exactly the two missing premises and their near-misses
(`family_invariants` raises otherwise; property-tested). Answer identifiers never move. The
truth is re-derived by an independent subset check.

Counterfactual rule: the COUNTERFACTUAL twin removes one required premise of the originally
licensed answer, restores the missing premise of the other, and swaps the near-miss; identifiers,
option order, proposition block and length (number of `holds`) are preserved. The Solver must
respond to the relation; a surface heuristic sees an identical page.

## 5. Difficulty ladder and stratum selection (Stage A)

Ladder `precondition_ladder.LADDER` (strata `TBD` — table inserted from the module). Primary axis:
required premises per answer. Calibration runs the **control arm only** (`L3_JSON_AST`) on the
`DEV` pool, positives only, with the rotated-option twin of every item.

**Frozen band and target (derived, §5.1):** band `[TBD_low, TBD_high]`, target `TBD` (midpoint).
Selector: among strata whose control accuracy lies inside the band, minimise |acc − target|; ties
to the easier stratum. If no stratum is inside the band: (i) if every stratum is above the band,
extend once along the predeclared continuation (`TBD` next strata) and re-run the selector; (ii)
otherwise `PRECONDITION_INSTRUMENT_NOT_QUALIFIED`. No other adjustment is permitted.

### 5.1 Derivation of the band

chance = 0.5 (two options; destroyed control is the constant 0.5 by the twin theorem, V7-verified
144/144). Rendered-prompt shortcut baseline on this mechanism ≈ 0.5 by construction (§6). Practical
effect Δ* = `TBD` (§10). The band must keep both a +Δ* and a −Δ* effect measurable without ceiling
or chance compression: `low = 0.5 + shortcut_margin`, `high = 1 − Δ* − headroom`. Numbers `TBD`
from `docs/PRECONDITION_POWER_ANALYSIS.md`.

## 6. Rendered-prompt shortcut gate

Adversaries receive **exactly** the candidate prompt string and the option count — no canonical
state, no metadata. Family: `rendered_prompt_adversary.RULES` (`TBD` list) + shallow models. Split:
develop and freeze on `ADV_DEV`; evaluate frozen adversaries on `SHORTCUT_EVAL` (fresh) **and** on
the `TOURNAMENT` pool (fresh w.r.t. selection), **per founder arm**. Multiplicity: Holm across the
frozen family; exact Clopper–Pearson intervals; within-family permutation null for the max.

**Gate (frozen):** for every founder arm, best frozen adversary accuracy ≤ `TBD` with Bonferroni
upper bound ≤ `TBD` at n ≥ `TBD`; and control accuracy − best adversary ≥ `TBD`. Failure on any
arm → `PRECONDITION_INSTRUMENT_NOT_QUALIFIED` (kill condition; no founder calls).

Frozen adversary hash: `TBD`.

## 7. Founder roster (frozen before any founder call)

| Arm | Surface | Role |
|---|---|---|
| `GRF_L3_JSON_AST` | Typed JSON AST | **baseline** |
| `GRF_L0_STRUCTURED_ENGLISH` | Structured English | founder |
| `GRF_L1_CURRENT_HML` | HML | founder |
| `GRF_L2_SEXPR` | S-expression | founder |
| `GRF_L5_COMPACT_SYMBOLIC` | Compact Symbolic | founder |

Roster hash `TBD`. `L4_TYPED_PREFIX`, `L6_GRAPH_TRIPLES`, `L7_HYBRID_ROLE_LABELLED` are excluded
for budget only; they may be run later on the identical frozen tasks (the cache identity permits
it) but are not part of this preregistered comparison. No new founder is invented during the run.

Representation parity definition (all mechanised in `assert_arena_parity`): Game-R genome; exact
canonical recovery (`mathematical_hash`); identical surface information inventory; identical
option content and order; identical envelope and answer protocol; distinct rendered bytes. Reported
additionally: longest shared ≥40-char span between every arm pair and per-arm prompt tokens.

## 8. Sample size (from `docs/PRECONDITION_POWER_ANALYSIS.md`)

`TBD` families → `TBD` positive items per arm (ORIGINAL + COUNTERFACTUAL), plus one rotated-option
twin per item for the position audit (§11). Power `TBD` for Δ = `TBD` at Holm-worst α, ICC `TBD`.
Model-call budget: `TBD` fresh calls (hard cap enforced by `CallBudget`).

## 9. Cache semantics (preregistered)

Identity = harness `cache_identity` (experiment version, model digest, model revision = served
template hash | tokenizer id (which embeds digest and template), runtime condition, decoding+schema
hash, qualified task id, candidate id, prompt bytes sha256). `FRESH` and `SAME_CONDITION_REUSE`
rows are both valid — reuse is the same Solver answering byte-identical bytes under an identical
condition at temperature 0, and is required for resume. `CROSS_CONDITION` is impossible by
construction and raises. Namespaces are Phase-8-only; every frozen instrument namespace is refused
by `assert_phase8_namespace`. A sentinel file guards the live cache; its disappearance aborts the
run (`CacheVanished`).

## 10. Endpoints

**Primary.** For each founder F vs baseline B on the common scored base rows (rotated rows are
**not** primary): paired accuracy difference Δ(F, B), discordant counts n10/n01, exact McNemar
two-sided p, family-clustered paired bootstrap 95% CI (4000 resamples, seed 20260907), Holm across
the four baseline comparisons. Practical-effect threshold Δ* = `TBD`; practical-equivalence region
±`TBD` (project precedent: `practical_effect_min` 0.10, `smallest_effect_of_interest` 0.15,
`practical_equivalence_region` 0.125 in `fitness_v5.PROMOTION_RULE`). Equivalence is a paired TOST
(`precondition_power.equivalence_test`). p < .05 alone is **not** an effect.

**Secondary.** All-pairs comparisons (10, Holm k = 10, reported descriptive); per-arm accuracy with
Wilson CI; rotated-row accuracy; position invariance and position-anchoring rate per arm; prompt
tokens / latency / context share per arm (Pareto axis only, never compensating accuracy);
explicit-positive control accuracy per arm (must be ≥ 0.90, else that arm is unreadable and the
run is `PRECONDITION_INSTRUMENT_NOT_QUALIFIED` for that arm — reported, not silently dropped).

## 11. Position audit

Every item is run as base and as its option-rotated twin (`rotate_options(item, 1)`), on every arm,
immediately after the base (prefix cache makes this cheap). Per arm: position invariance =
fraction of pairs selecting the same **content**; anchoring rate = fraction selecting the same
**letter**. Gate: position invariance ≥ `TBD` on every arm (derived from the harness floor 0.50 and
the calibration; frozen before founder calls). Credit for aligning the correct answer with a
preferred position is impossible by construction: targets are balanced within every family.

## 12. Budget, stopping and replication

One tournament run on the frozen pool; resume allowed; no second run under altered thresholds. If
an effect appears, the predeclared replication path is (A) a fresh `TOURNAMENT` pool with a new
start index, (B) a second option-order schedule (`rotate_options(item, 1)` as base), (C) a second
mechanism (`docs/TRANSITIVE_DEPENDENCY_V2_SPEC_DRAFT.md`). None of these is run inside this
preregistration.

## 13. Invalidation rules

`EXPERIMENT_INVALID` if any of: served digest ≠ frozen digest; any `CROSS_CONDITION` row; any
`PROMPT_OVER_BUDGET` row on any arm (a task over budget for one arm is void for **all** arms);
any token-count mismatch row; any `SOLVER_ERROR` row after resume; valid-response rate < 0.95 on
any arm; the tournament pool's task hashes differ from the frozen manifest; any threshold in this
document changed after the freezing commit.

## 14. Freezing record

| Item | Value |
|---|---|
| Freezing commit | `TBD` |
| Generator version | `arena-precondition-ladder-v2.0.0` |
| Stratum | `TBD` |
| Tournament pool | `TBD` families, start `TBD`, task-set hash `TBD` |
| Adversary family hash | `TBD` |
| Roster hash | `TBD` |
| Solver digest | `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae` |
| Served template hash | `TBD` |
| Decoding hash | `TBD` |
| Prompt sha256 per (task, arm) | `artifacts/experiments/game_r_precondition_founder_v1/tournament/manifest-*.json` |
