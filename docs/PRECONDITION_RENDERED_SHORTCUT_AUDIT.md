# Precondition Rendered-Prompt Shortcut Audit

**Phase 8 · zero model calls · adversaries read ONLY the rendered prompt string and the option count.**

Artifact: `artifacts/reports/precondition_rendered_shortcut_audit.json` (audit `phase8-rendered-shortcut-audit-v1`, adversary family `arena-rendered-prompt-adversary-v1.0.0`, generator `arena-precondition-ladder-v2.0.0`, guide policy `SHARED_CONSTANT`). Frozen adversaries per (stratum, arm): `artifacts/manifests/phase8_frozen_adversaries/`. Script: `research/phase8/shortcut/rendered_shortcut_audit.py`.

## 1. Why this audit exists

V1–V7's shortcut audit scored its rules on `canonical_json(state)` — a string the Solver never receives (`docs/V7_TOTAL_FORENSIC_AUDIT.md` C1). It also took a max over 7 rules × 2 polarities on the same 24 items it selected on, after deleting the ancestor's Bonferroni + Clopper–Pearson correction (C3e). This audit closes both defects prospectively:

- **Input:** every adversary is a function of `(prompt: str, n_options: int)` and nothing else. The module is forbidden by test (AST scan) from importing the canonical schema, the generator, the frozen instruments, the model-view compiler or the language surfaces.
- **Split:** adversaries are developed and frozen on the `ADV_DEV` pool and evaluated on the disjoint `SHORTCUT_EVAL` pool; `evaluate_frozen` raises if any evaluation family was seen in development. The frozen set will be re-evaluated on the exact `TOURNAMENT` pool (§6) before any founder call.
- **Multiplicity:** Holm across the frozen adversaries, exact Clopper–Pearson intervals, a Bonferroni-adjusted upper bound on the best adversary, and — for the full 64-rule family on fresh data — a within-family label-permutation null for the max-over-family statistic.
- **Per arm:** cue availability can differ by representation (F1b), so every founder surface is audited separately on its own rendered bytes.

## 2. The adversary family

64 rules = 19 surface features × 2 polarities + 26 constant-position rules, plus a logistic regression and a depth-≤3 decision tree on per-option feature differences (18 non-positional features). Features: option text length and token count; candidate identifier token count; candidate first/last mention position, mention count and spread; lexical rank; digit sum; identifier length; first-mention line index; bracket depth at first mention; 32-char window 3-gram overlap with the state; window punctuation density; shared prefix/suffix with the other option; gzip delta (compressed-length change when the candidate token is deleted from the state text); option position; state text length. Ties **abstain** (credit 1/n) and are never broken by position.

**Boundary rule.** No adversary may pair `requires(answer, premise)` with `holds(premise)` — that is the task. Excluded by design: any premise↔answer pairing, subtree delimiter depth (the C2 leak), and any canonical field.

## 3. Design

Development: `ADV_DEV`, 100 families (200 twin items) per (stratum, arm). Evaluation: `SHORTCUT_EVAL`, 200 families (400 items). Top-3 rules by development accuracy + 2 models are frozen per cell (hash recorded). Bootstrap 300 family resamples; permutation null 1000 draws.

## 4. Frozen adversaries on fresh evaluation data (n = 400 items per cell)

Best frozen adversary per (stratum, arm): credited accuracy · Bonferroni-adjusted 95% upper bound · Holm-adjusted one-sided p vs chance.

| stratum | L3 JSON AST | L0 STRUCTURED ENGLISH | L1 CURRENT HML | L2 SEXPR | L5 COMPACT SYMBOLIC |
|---|---|---|---|---|---|
| `P05` | 0.5275 · ≤0.592 · p=0.69 | 0.5188 · ≤0.647 · p=0.68 | 0.5250 · ≤0.598 · p=0.78 | 0.5475 · ≤0.612 · p=0.14 | 0.5625 · ≤0.627 · p=0.04 **†** |
| `P07` | 0.5000 · ≤0.565 · p=1.00 | 0.5212 · ≤0.589 · p=1.00 | 0.5162 · ≤0.589 · p=1.00 | 0.5275 · ≤0.602 · p=0.51 | 0.5400 · ≤0.605 · p=0.29 |
| `P09` | 0.5200 · ≤0.585 · p=1.00 | 0.5175 · ≤0.611 · p=1.00 | 0.5025 · ≤0.572 · p=1.00 | 0.5212 · ≤0.717 · p=0.25 | 0.5000 · ≤0.565 · p=1.00 |
| `P12` | 0.5100 · ≤0.575 · p=1.00 | 0.5225 · ≤0.587 · p=0.99 | 0.5200 · ≤0.585 · p=1.00 | 0.5038 · ≤0.572 · p=1.00 | 0.5125 · ≤0.578 · p=1.00 |
| `P16` | 0.5125 · ≤0.585 · p=1.00 | 0.5375 · ≤0.602 · p=0.29 | 0.5212 · ≤0.591 · p=1.00 | 0.5000 · ≤0.565 · p=1.00 | 0.5025 · ≤0.568 · p=1.00 |
| `P20` | 0.5000 · ≤0.565 · p=1.00 | 0.5200 · ≤0.585 · p=0.91 | 0.5250 · ≤0.619 · p=0.59 | 0.5150 · ≤0.580 · p=1.00 | 0.5325 · ≤0.597 · p=0.53 |
| `P05_M2_D2` | 0.5000 · ≤0.565 · p=1.00 | 0.5162 · ≤0.583 · p=1.00 | 0.5275 · ≤0.592 · p=0.70 | 0.5375 · ≤0.745 · p=0.02 **†** | 0.5600 · ≤0.624 · p=0.05 **†** |
| `P05_M3_D4` | 0.5250 · ≤0.620 · p=0.59 | 0.5150 · ≤0.583 · p=1.00 | 0.5100 · ≤0.575 · p=1.00 | 0.5375 · ≤0.602 · p=0.37 | 0.5250 · ≤0.611 · p=0.66 |
| `P12_M2_D2` | 0.5000 · ≤0.565 · p=1.00 | 0.5250 · ≤0.594 · p=0.81 | 0.5025 · ≤0.572 · p=1.00 | 0.5125 · ≤0.584 · p=1.00 | 0.5038 · ≤0.578 · p=1.00 |

† Holm-adjusted p < 0.05 within the cell. Across 45 cells at α = 0.05 the expected number of such cells under a global null is ≈ 2; the three observed are all at premises = 5 strata, none is a candidate stratum, and the largest is 0.5625.

## 5. The full 64-rule family on fresh data, against its own selection null

Max-over-family accuracy on `SHORTCUT_EVAL` vs the expected max under within-family label permutation (what pure selection noise produces):

| stratum | L3 JSON AST | L0 STRUCTURED ENGLISH | L1 CURRENT HML | L2 SEXPR | L5 COMPACT SYMBOLIC |
|---|---|---|---|---|---|
| `P05` | 0.526 (null 0.512) `gzip_delta:-` | 0.512 (null 0.505) `gzip_delta:+` | 0.525 (null 0.510) `gzip_delta:-` | 0.545 (null 0.509) `gzip_delta:-` | 0.549 (null 0.510) `gzip_delta:-` |
| `P07` | 0.506 (null 0.512) `gzip_delta:+` | 0.521 (null 0.505) `gzip_delta:+` | 0.516 (null 0.510) `gzip_delta:-` | 0.527 (null 0.506) `gzip_delta:-` | 0.535 (null 0.510) `gzip_delta:-` |
| `P09` | 0.509 (null 0.509) `gzip_delta:-` | 0.516 (null 0.508) `gzip_delta:+` | 0.502 (null 0.509) `gzip_delta:+` | 0.507 (null 0.509) `gzip_delta:-` | 0.521 (null 0.510) `gzip_delta:-` |
| `P12` | 0.506 (null 0.509) `gzip_delta:+` | 0.521 (null 0.505) `gzip_delta:+` | 0.516 (null 0.509) `gzip_delta:+` | 0.504 (null 0.509) `gzip_delta:-` | 0.502 (null 0.509) `gzip_delta:-` |
| `P16` | 0.512 (null 0.508) `gzip_delta:-` | 0.531 (null 0.508) `gzip_delta:+` | 0.519 (null 0.509) `gzip_delta:+` | 0.501 (null 0.507) `gzip_delta:+` | 0.500 (null 0.508) `always_option_0` |
| `P20` | 0.500 (null 0.507) `always_option_0` | 0.515 (null 0.506) `gzip_delta:+` | 0.510 (null 0.507) `gzip_delta:+` | 0.506 (null 0.509) `gzip_delta:+` | 0.512 (null 0.508) `gzip_delta:+` |
| `P05_M2_D2` | 0.505 (null 0.512) `gzip_delta:-` | 0.516 (null 0.504) `gzip_delta:+` | 0.526 (null 0.509) `gzip_delta:-` | 0.510 (null 0.507) `gzip_delta:-` | 0.535 (null 0.510) `gzip_delta:-` |
| `P05_M3_D4` | 0.507 (null 0.512) `gzip_delta:-` | 0.515 (null 0.506) `gzip_delta:+` | 0.506 (null 0.510) `gzip_delta:-` | 0.524 (null 0.509) `gzip_delta:-` | 0.525 (null 0.509) `gzip_delta:-` |
| `P12_M2_D2` | 0.501 (null 0.508) `gzip_delta:+` | 0.525 (null 0.507) `gzip_delta:+` | 0.502 (null 0.508) `gzip_delta:+` | 0.512 (null 0.511) `gzip_delta:-` | 0.504 (null 0.508) `gzip_delta:-` |

The best rule is almost always `gzip_delta` (one polarity or the other, varying by cell — a sign of noise, not of a stable cue) and its excess over the selection null is ≤ 0.04 everywhere.

## 6. Twin invariance — balance by construction, measured on the rendered prompt

For every (stratum, arm) cell, every candidate-mention and option-text feature has an **identical per-option score vector on 100% of twin pairs** while the truth flips, so each such rule scores exactly 0.5 per family by construction. Pinned on every cell: `candidate_digit_sum`, `candidate_first_mention_pos`, `candidate_id_length`, `candidate_last_mention_pos`, `candidate_lexical_rank`, `candidate_mention_count`, `candidate_mention_spread`, `candidate_prefix_shared`, `candidate_suffix_shared`, `candidate_token_count`, `first_mention_line_index`, `mention_bracket_depth`, `option_text_length`, `option_token_count`, `position_of_option_in_prompt`, `state_text_length`, `window_punctuation_density`. The only features that ever differ across a twin are the two whole-state-text features `gzip_delta`, `window_ngram_overlap`, because the twins differ in the near-miss slots of the assumptions block; those two features carry the ≤0.55 residual seen above.

This is the rendered-prompt confirmation of the forensic audit's Q11 (`research/audit/a9_causal_isolation.md`): the mechanism's cleanliness is structural, not a property of any particular adversary family's blindness.

## 7. Proposed gate — NEVER ENACTED

> **2026-09-08:** the tournament this section was written for was stood down by the owner's
> mission reset before any founder call, and the preregistration was never frozen
> (`docs/PHASE8_SALVAGE_HANDOFF.md`). The thresholds below are a **design proposal**, not a
> preregistered commitment, and they have never governed any result. Sections 1–6 above are
> measurements and stand on their own.

_Original text follows._

### Proposed gate for the tournament (would have been evaluated on the exact TOURNAMENT pool before any founder call)

Per founder arm, using the frozen adversary set of the selected stratum: (a) best frozen adversary credited accuracy ≤ **0.60** and Bonferroni-adjusted 95% upper bound ≤ **0.70**; (b) after the run, the arm's own base-row accuracy minus its best frozen adversary ≥ **0.10**, else that arm is flagged `SHORTCUT_CONFOUNDED` and excluded from any effect claim. (a) failing on any arm halts the tournament (`PRECONDITION_INSTRUMENT_NOT_QUALIFIED`). The thresholds are set from the chance level (0.50), the observed fresh-data ceiling of the family (0.5625 at n = 400), and the Clopper–Pearson width at the planned n; they are recorded in `docs/GAME_R_PRECONDITION_FOUNDER_V1_SPEC.md` and are not moved after the run.

## 8. Tournament-pool evaluation

_Appended after the pool is frozen._
