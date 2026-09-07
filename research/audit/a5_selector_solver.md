# Auditor 5 of 9 — Selector / Calibration + Solver Validity

**Scope:** V7 total forensic audit, Parts E (selector / adaptive calibration) and G (solver validity).
**Posture:** adversarial. The brief is to try to destroy the argument; `REFUTED` is recorded wherever the
instrument holds.
**Constraints honoured:** read-only; **zero model calls** (no Ollama, no `localhost:11434`); no existing
file modified; no threshold changed; nothing re-scored. All new bytes live under
`research/audit/a5_selector_solver.md` and `research/audit/a5_sel/`.

**Environment.** Worktree
`/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/phase-6-parallel-setup-9c6068`;
interpreter `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python` (3.14.7); `import arena`
resolves to `<worktree>/arena/__init__.py` (verified). Every script invoked as `python -m`.

## 0. Reproduction seal

The DEV probe bank is regenerable offline. `research/audit/a5_sel/rebuild_pool.py` rebuilds it and
matches the artifact byte-for-byte:

```
$ python -m research.audit.a5_sel.rebuild_pool
rebuilt probes: 864  artifact dev_pool_probes: 864
rebuilt dev_pool_hash: f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b
artifact dev_pool_hash: f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b
MATCH
row probe_ids not in rebuilt pool: 0
```

This is what makes Q20 answerable at all: every probe's shortcut-rule prediction can be recomputed
without touching a model.

Scripts (all read-only, all zero-model-call):

| script | produces | answers |
|---|---|---|
| `research/audit/a5_sel/rebuild_pool.py` | stdout seal | reproduction |
| `research/audit/a5_sel/analyse.py` | `a5_analysis.json`, `a5_rows_annotated.json` | E4, E5, E9, E10 |
| `research/audit/a5_sel/errors.py` | `a5_errors.json`, `a5_error_assignments.json`, `a5_swap_pairs.json` | **G20**, G16 |
| `research/audit/a5_sel/replication.py` | `a5_replication.json` | G16, G17, E5 |
| `research/audit/a5_sel/fragility.py` | `a5_fragility.json` | E5, verdict stability |

---

# PART E — SELECTOR / ADAPTIVE CALIBRATION

## E1. Genealogy of the difficulty selector, V3 → V7, with exact constants

**EVIDENCE.**

| Version | File · line | Ladder? | Selector fn | `frontier_target` | Band | `gap_min` | Independent pool after selection? |
|---|---|---|---|---|---|---|---|
| **V1** | `arena/experiments/fitness_v1.py` | no | none | — | — | — | — |
| **V2** | `arena/experiments/fitness_v2.py` | no | none | — | — | — | — |
| **V3** | `fitness_v3.py:52-63` | **no `level` field at all** (grep `level\b` → 0 hits) | **none — a narrative string only** | `0.625` (inside `QUALIFICATION_RULE["selection"]`, prose) | `positive_accuracy_min 0.40` / `_max 0.85` | `0.10` | **YES** — `"then freeze independent SCOUT families with the same mechanism/complexity"`; built at `fitness_v3.py:829-831` via `build_pool(V3Slice.SCOUT)` |
| **V4** | `fitness_v4.py:139-158`, selector `:1477-1505` | yes, L0..L4 | `select_frontier_level` | `0.625` (`:143`) | `[0.35, 0.85]` (`:148`) | `0.10` (`:152`) | **NO** — SCOUT step dropped |
| **V5** | `fitness_v5.py:208-236`, selector `:915-948` | yes, L0..L3 | `select_frontier_level` | `0.625` (`:213`) | `[0.35, 0.85]` (`:214`) | **`0.20`** (`:219`) | NO. `SCOUT_FAMILIES = 16` (`:206`) and `V5Slice.SCOUT` (`:259`) are **dead constants** — one occurrence each, never read |
| **V6** | *no `fitness_v6.py` exists* | — | V5's, frozen | `0.625` | `[0.35, 0.85]` | `0.20` | NO |
| **V7** | `fitness_v7.py:217-257` (`derive_frontier`), rule `:260-287`, selector `:677-711` | yes, L0..L3 | `select_frontier_level` (docstring: *"V5's selector (`fitness_v5.py:915-948`) with the DERIVED target"*) | **`0.7749999999999999`**, derived | `[0.35, 0.85]` | `0.20` (inherited) | NO |

V6 is not a code version. `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` §2 states the V5 instrument was
frozen and only the solver was substituted; the artifact
`artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json` carries
`instrument_version: "arena-game-r-constrained-formal-instrument-v5.0.0"`.

**The constant's real provenance — the genealogy's load-bearing fact.**

```
V3 band midpoint : (0.40 + 0.85) / 2 = 0.625   <-- 0.625 WAS a derived midpoint
V4/V5 band midpt : (0.35 + 0.85) / 2 = 0.600   <-- 0.625 no longer matched anything
V7 window midpt  : (0.50 + 0.20 + 0.85) / 2 = 0.775
```

`0.625` was **originally** the midpoint of V3's own qualifying band. V4 moved the band floor
0.40 → 0.35 and kept `0.625`; V5 then raised `gap_min` 0.10 → 0.20 and again kept `0.625`. So V7's
framing ("the constant drifted") is correct, and understates it: the constant was a *derived* quantity
that silently became a *declared* one across two version bumps.

**CONFIRMED · severity: informational (history), but it grounds E7/E8.**

## E2. Why V5 selected L3 and V7 selects L2 — the arithmetic

Both runs share the identical ladder. `research/audit/a5_sel/a5_replication.json` proves it: the V5-qwen
and V7-qwen `positive_accuracy` vectors are `identical: true` for all three mechanisms.

`formal_expression_depth` accuracies: L1 = 0.8333, L2 = 0.7917, L3 = 0.6250.

```
V5 (target 0.625):  |0.8333-0.625| = 0.2083   |0.7917-0.625| = 0.1667   |0.6250-0.625| = 0.0000  -> L3
V7 (target 0.775):  |0.8333-0.775| = 0.0583   |0.7917-0.775| = 0.0167   |0.6250-0.775| = 0.1500  -> L2
```

The artifact agrees: V7 `selection.distance_to_target = 0.01666666666666672`, `selected_level = 2`.
`transitive_dependency` picks L3 under both (0.75; distances 0.125 and 0.025).
`precondition_conjunction` picks L1 (0.9583) under both and voids `VOID_CEILING`.

**The switch point.** `a5_replication.json → target_sensitivity_grid` sweeps the target on a 0.025 grid:
`formal_expression_depth` flips L3 → L2 between target 0.70 and 0.73 — exactly at
(0.625 + 0.7917)/2 = 0.7083. **One mechanism's entire frontier changed because a constant moved across a
single midpoint 0.067 away.** Nothing about the task, the solver or the data changed.

**CONFIRMED.**

## E3. Is selection made on the same rows later used for qualification? — DEFINITIVELY YES

**EVIDENCE — the code path, `fitness_v7.py:998-1099`.**

1. `:1014` `result = evaluate(root, control, measured, ...)` — one call per (mechanism, level).
2. `:1024` `summaries[level] = summary`
3. `:1025` `accuracies[level] = float(summary["positive_accuracy"])`
4. `:1063` `selection = select_frontier_level(accuracies)` ← **selection reads `summaries`**
5. `:1092` `qualification = qualify_mechanism(summaries[level], audits[...], q0["rate"])` ← **gating reads
   the same `summaries` object**

The artifact confirms `arm_schedule: "full"`, so the `arms == "positives"` top-up branch at `:1069-1086`
never ran; **no** row was collected after selection. The *same 24 positive rows per cell* produce the
statistic that chooses the level and the statistic that is then compared to the gates.

The rule's own field is misleading. `fitness_v5.py:209` / V7's inherited
`selection_source: "DEV only; permanent JSON/typed-AST control only; no candidate outcome"` guarantees
only that selection does not peek at a *candidate genome's* outcome. It says nothing about — and reads
as though it excludes — reuse of the same rows for gating. **V3 had the guarantee the phrase implies**
(`fitness_v3.py:60-62`, independent SCOUT families frozen after DEV selection) and it was dropped at V4
without the phrase being updated.

**CONFIRMED · severity: HIGH.** This is textbook selection-then-inference on one sample. Effect: the
selected level's accuracy is a biased (variance-inflated toward the target) estimator, and every gate
that reads `positive_accuracy` — `negative_collapse` (gap), `shortcut_margin`, the band — inherits that
bias. Magnitude quantified in E4.

## E4. Quantifying the bias at n = 24

`research/audit/a5_sel/analyse.py → selection_bias_simulation` (100,000 binomial replicates per cell;
true accuracy set to each level's observed value; the **actual** selector re-run on each draw).

| mechanism | target | `E[observed − true]` at the selected level | sd | P(the selected level's observed accuracy is a target-**favourable** noise draw) |
|---|---|---|---|---|
| formal_expression_depth | 0.775 | −0.0063 | 0.065 | 0.349 |
| formal_expression_depth | 0.625 | −0.0311 | 0.084 | 0.278 |
| transitive_dependency | 0.775 | +0.0031 | 0.074 | 0.237 |
| transitive_dependency | 0.625 | −0.0050 | 0.086 | 0.404 |
| precondition_conjunction | 0.775 | +0.00003 | 0.041 | 0.266 |

**Two findings, and they point opposite ways.**

(a) **The point bias is small** — |E[observed − true]| ≤ 0.031, well under one row (1/24 = 0.042). The
selector is *argmin |x − target|*, not *argmax*, so it is not a winner's-curse maximiser; it pulls the
selected estimate **toward the target from both sides**, which partly cancels. That is a genuine
mitigating structural property and I record it as such.

(b) **But the variance is the whole story.** sd ≈ 0.065–0.086 at the selected level, against a qualifying
window `[0.70, 0.85]` only 0.15 wide. The prior analysis
(`artifacts/reports/v5_selector_analysis.json → 3_simulated_operating_characteristics`) puts it exactly:
`window_width_in_standard_errors_at_n24 = 1.76`. **The instrument's entire acceptance region is under two
standard errors wide.**

**LIKELY (bias) / CONFIRMED (variance) · severity: HIGH for the variance limb.**

## E5. Does the level *choice* itself carry material uncertainty? — YES

`analyse.py → selector_resampling`, 100,000 replicates, the real selector.

| mechanism | target | actual pick | pick distribution | **P(a different level)** |
|---|---|---|---|---|
| formal_expression_depth | **0.775** | L2 | L1 0.463 · **L2 0.446** · L3 0.091 | **0.554** |
| formal_expression_depth | 0.625 | L3 | L1 0.101 · L2 0.201 · L3 0.698 | 0.302 |
| transitive_dependency | **0.775** | L3 | L1 0.008 · L2 0.086 · **L3 0.905** | **0.095** |
| precondition_conjunction | **0.775** | L1 | L1 1.000 | 0.000 |

**`formal_expression_depth`'s frontier is a coin toss.** Under resampling at its own observed accuracies,
the V7 selector picks a *different* level than the one it reported **55.4% of the time**, and L1 (0.463)
is marginally more likely than the reported L2 (0.446). The published frontier for that mechanism is not
a stable property of the instrument.

**And the verdict inherits it.** `research/audit/a5_sel/fragility.py → verdict_distribution_under_resampling`
re-runs selection *and* every gate:

| mechanism | reported verdict | P(QUALIFIED) under resampling |
|---|---|---|
| formal_expression_depth | VOID_SHORTCUT @ L2 | **0.000** |
| **transitive_dependency** | VOID_SHORTCUT @ L3 | **0.316** |
| precondition_conjunction | VOID_CEILING | 0.016 |

**The single most consequential number in this audit.** `transitive_dependency` fails the shortcut-margin
gate by **one row**: `a5_fragility.json → gate_distance_in_rows` gives k = 18/24 correct, shortcut
= 16/24 fixed, margin = 2/24 = 0.0833, required ≥ 0.10 (`SHORTCUT_MARGIN = 0.10`,
`GATE_EPSILON = 1e-9`, `fitness_v7.py:175, 184, 752-754`), i.e. **19/24 needed**. `rows_short_of_margin_gate: 1`.

One additional correct answer out of 864 flips V7's headline from *0 of 3 qualified /
SHORTCUT_DOMINATED* to *1 of 3 qualified*. Note also that `best_shortcut_accuracy` is a **fixed property
of the probe bank** and carries no sampling noise — all the uncertainty sits in the 24-item accuracy,
which is precisely the quantity the selector also optimised over.

**CONFIRMED · severity: CRITICAL.** V7's central claim is one row deep.

## E6. Should selection be on DEV and qualification on an independent SCOUT pool? — YES, and it used to be

**EVIDENCE.** `fitness_v3.py:60-62` prescribes it; `fitness_v3.py:829-831` implements it
(`build_pool(V3Slice.SCOUT)`). In V5, `SCOUT_FAMILIES = 16` (`:206`, comment: *"32 positives per mechanism
per candidate"*) and `V5Slice.SCOUT` (`:259`) each occur exactly once — definitions with no readers.
`MODEL_CALL_BUDGET` still reserves `scout_max: 3000` (`fitness_v5.py:254`) for a pool nothing builds.
V7 does not mention SCOUT at all.

**What would change.** Splitting the sample removes the selection–inference coupling in E3 and makes the
gate statistic unconditionally unbiased, at the cost of either halving n per cell (12 positives — worse,
the window is already 1.76 SE wide) or doubling model calls to 1,728. Given the observed compute
(864 fresh calls) and that the budget already reserves 3,000 scout calls, **the honest fix is a fresh
SCOUT pool at the selected level, not a split** — exactly V3's design. The unused budget line is
evidence the affordance was planned and abandoned.

**CONFIRMED · severity: HIGH · effect: recoverable at ~+288 model calls (24 positives × 3 mechanisms ×
[selected level, full arms]).**

## E7. Is 0.775 justified? — the derivation is internally sound

`fitness_v7.py:217-257`:

```
window_low      = destroyed_expected + gap_min = 0.50 + 0.20 = 0.70
window_high     = frontier_band[1]             = 0.85
frontier_target = (window_low + window_high)/2 = 0.775
```

Verified live: `derive_frontier()` → `{'window_low': 0.7, 'window_high': 0.85,
'frontier_target': 0.7749999999999999}`; the artifact's `frontier` block matches.

The premise `destroyed_expected = 0.50` (`:189`) is not an assumption but a theorem *on this bank*: the
destroyed twins are information-identical with opposite targets, so any deterministic solver scores
exactly 0.5. **Verified empirically, not merely asserted** — `a5_errors.json → destroyed_twin_pairs`:
**144/144 pairs** with identical `prompt_hash`, identical `raw_output`, opposite `expected_index`; every
`destroyed_accuracy` in the ladder is exactly 0.5.

So the gap gate really is `positive_accuracy ≥ 0.70`, the window really is `[0.70, 0.85]`, and its
midpoint really is 0.775. **The arithmetic is REFUTED as a flaw. It is correct.**

**REFUTED (the instrument holds) · the derivation is sound and the `DESTROYED_EXPECTED` premise is
empirically confirmed.**

## E8. Why 0.775 rather than a broad 30–80% headroom interval? — the *choice* is not justified, and its cost was measured in advance

This is where the instrument does not hold.

A point target is not required by anything. The gates only need `accuracy ∈ [0.70, 0.85]`; *any*
in-window level qualifies identically. The point target does one thing the gates do not: it **breaks ties
among in-window levels** — and it does so by a statistic with sd ≈ 0.07 on a window 0.15 wide.

**The decisive evidence is that the cost was already quantified, in this repository, before V7 was
written.** `artifacts/reports/v5_selector_analysis.json → 3_simulated_operating_characteristics`:

| selector | sensitivity (true-in-window) | **P(qualified when NO level is truly in-window)** | coin-flipper FP |
|---|---|---|---|
| `current_target_0.625` | 0.257 | **0.081** | 0.021 |
| **`window_midpoint_0.775`** — *what V7 adopted* | 0.706 | **0.262** | 0.054 |
| `midpoint_0.80_gap0.25_calibrated` | 0.591 | 0.159 | 0.020 |
| `oracle_knows_true_p` (**ceiling**) | 0.564 | 0.170 | 0.018 |

and its verdict, verbatim from `5_verdict`:

> *"Re-aiming at the window midpoint raises that to 0.707 — above the ceiling — while raising acceptance
> of a true-0.65 reader from 0.074 to 0.533. The sensitivity is real; the naive fix does not deliver it
> honestly."*

and from `3_...sensitivity_loss_attributable_to_the_selector`:

> *"The naive fixes recover MORE than the ceiling, which is the tell that they are buying sensitivity
> from noise."*

**V7 adopted the naive fix.** It took the midpoint re-aim (0.625 → 0.775) and **omitted the paired
gap calibration** that made the calibrated variant honest: `positive_negative_gap_min` remains `0.20`
in `QUALIFICATION_RULE_V7` (inherited unchanged from `fitness_v5.py:219`). The measured price is
**a 3.2× increase in the false-qualification rate when no level is genuinely in the window
(0.081 → 0.262)** and a rate that **exceeds the oracle ceiling (0.170)** — the analysis's own stated
diagnostic for noise-harvesting.

`docs/FITNESS_V7_PREREGISTRATION.md` derives 0.775 (lines 26–64) and **never mentions the false-positive
cost, the 0.262 figure, the oracle ceiling, or the calibrated alternative**; a grep for
`false.positive|coin|0\.25|selector_analysis` over that document returns only the derivation lines.

**CONFIRMED · severity: HIGH.** A known, measured, in-repository operating-characteristic cost was
adopted without being disclosed in the preregistration. Note the mitigating direction of travel: because
V7 returned *zero* qualifications, the inflated false-positive rate did not manifest as a false positive
**in this run** — it is a latent defect in the instrument, not a corrupted result.

## E9. Does aiming at a narrow target select levels with unusually strong shortcuts? — **REFUTED**

This was flagged in the brief as a key hypothesis. It does not survive contact with the data.

**Test 1 — cell-level correlation** (`a5_analysis.json → closeness_vs_shortcut`; 200,000-permutation
two-sided p):

| scope | target | Pearson r | perm p | Spearman ρ | perm p |
|---|---|---|---|---|---|
| all 12 cells | 0.775 | −0.262 | 0.400 | −0.308 | 0.324 |
| **L1–L3 only (9 selectable cells)** | **0.775** | **−0.519** | **0.148** | **−0.565** | **0.118** |
| L1–L3 only | 0.625 | −0.621 | 0.077 | −0.600 | 0.092 |

Negative r means *closer to target ↔ stronger shortcut*, i.e. the hypothesis's direction. The effect is
moderate but **not significant at n = 9**, and it is *weaker* for V7's target than for V5's.

**Test 2 — the decisive one: what did the selector actually pick?** The selector operates *within* each
mechanism, so cell-level correlation is the wrong unit. Exact enumeration over all 3³ = 27 possible
level-triples:

| | mean best-shortcut at the chosen levels |
|---|---|
| V7 target 0.775 (actual picks: FED L2, TD L3, PC L1) | **0.6667** |
| V5 target 0.625 (FED L3, TD L3, PC L1) | 0.6944 |
| uniform-random L1–L3 triple (exact null over 27) | 0.7083 |

One-sided **P(random triple ≥ observed) = 0.889**. Per mechanism the deltas versus the within-mechanism
mean are −0.083 (FED), −0.042 (TD), 0.000 (PC) — **every one non-positive**.

**REFUTED · the V7 target selected levels with *weaker*-than-random shortcuts.** The mechanism is that
in `formal_expression_depth` the shortcut is essentially level-invariant (0.667 / 1.000 / 0.833 / 0.917)
while accuracy falls monotonically — so shortcut strength carries almost no information about which level
is near the target.

**The real problem is adjacent and worse.** `first_mentioned_in_state` scores 0.833–1.000 at *every*
non-explicit FED level. **No FED level is clean.** That is a generator defect in the
`formal_expression_depth` probe bank — the deepest identifier in a canonicalised Lean term tends to be
serialised first — and no choice of target can escape it. The selector is not steering into shortcuts;
the bank is uniformly contaminated for that mechanism.

## E10. Master per-(mechanism, level) table

`a5_analysis.json → per_level_table`. Chance baseline is 0.500 in every cell (forced binary choice,
balanced key: `answer_share_index_0` ∈ {0.500, 0.5417}). "state bytes" = length of
`canonical_json(state)`; tokens = mean `prompt_tokens` over the 24 positives.

```
mechanism                  L    acc  |d-.775|  shortcut  margin  status  share    H  posinv   tok  st.bytes  best_feature
-------------------------------------------------------------------------------------------------------------------------
formal_expression_depth    0  1.000     0.225     0.667  +0.333  CLEAN   0.500 1.00   0.958  5520      4385  more_frequent_in_state
formal_expression_depth    1  0.833     0.058     1.000  -0.167  LEAKS   0.667 0.92   0.667  4283      3670  first_mentioned_in_state
formal_expression_depth  * 2  0.792     0.017     0.833  -0.042  LEAKS   0.542 0.99   0.583  5078      4090  first_mentioned_in_state
formal_expression_depth    3  0.625     0.150     0.917  -0.292  LEAKS   0.542 0.99   0.542  5271      4327  first_mentioned_in_state
transitive_dependency      0  0.958     0.183     1.000  -0.042  LEAKS   0.542 0.99   0.958  3125      2873  first_mentioned_in_state
transitive_dependency      1  1.000     0.225     0.833  +0.167  LEAKS   0.500 1.00   1.000  2796      2519  more_frequent_in_state
transitive_dependency      2  0.958     0.183     0.625  +0.333  CLEAN   0.542 0.99   0.917  2968      2767  more_frequent_in_state
transitive_dependency    * 3  0.750     0.025     0.667  +0.083  CLEAN   0.500 1.00   0.833  3322      3263  first_mentioned_in_state
precondition_conjunction   0  1.000     0.225     1.000   0.000  LEAKS   0.500 1.00   1.000  5507      3923  first_mentioned_in_state
precondition_conjunction † 1  0.958     0.183     0.500  +0.458  CLEAN   0.542 0.99   0.958  4602      3296  always_first_option
precondition_conjunction   2  1.000     0.225     0.500  +0.500  CLEAN   0.500 1.00   1.000  5350      3812  always_first_option
precondition_conjunction   3  1.000     0.225     0.500  +0.500  CLEAN   0.500 1.00   0.958  6858      4844  always_first_option

  * = selected by V7        † = candidate, voided VOID_CEILING
```

Reading it adversarially:

- **The ladders are not monotone in difficulty.** `transitive_dependency` runs 0.958 → 1.000 → 0.958 →
  0.750; `precondition_conjunction` runs 1.000 → 0.958 → 1.000 → 1.000. Only
  `formal_expression_depth` is monotone. A "difficulty ladder" whose accuracy is flat or rising is not
  measuring difficulty.
- **Length is not the driver.** `precondition_conjunction` L3 has the *longest* prompts on the board
  (6,858 tokens) and scores 1.000; `transitive_dependency` L1 has the shortest (2,796) and also scores
  1.000. Within `formal_expression_depth`, L1 is the *shortest* (4,283) and scores 0.833 while L0 is
  longer (5,520) and scores 1.000. Length and accuracy are uncoupled here.
- **8 of 12 cells sit at ≥ 0.958.** The ladder mostly fails to bite (see G13).
- **`shortcut_margin` and `distance_to_target` disagree systematically** (see E11).

## E11. Is the best level for HEADROOM also the best for REPRESENTATION DISCRIMINATION? — no, and the instrument conflates them

**HYPOTHESIS.** These are different objectives. Headroom asks *"is the solver in the sensitive region of
its own competence curve?"* Discrimination asks *"can a difference between two representations of the
same information show up here?"*

**EVIDENCE — they select different levels.** Rank the L1–L3 candidates by each objective:

| mechanism | argmin \|acc − 0.775\| (headroom) | argmax shortcut_margin (discrimination) | agree? |
|---|---|---|---|
| formal_expression_depth | **L2** (0.017) | **L2** (−0.042) | yes, but *every* candidate is negative — no discriminating level exists |
| transitive_dependency | **L3** (0.025) | **L2** (+0.333) | **NO** |
| precondition_conjunction | L1 (0.183) | L2/L3 (+0.500) | **NO** |

For `transitive_dependency` the headroom objective picks L3 (margin +0.083, one row short of the gate)
while the discrimination objective picks L2 (margin +0.333, comfortably clean). **The instrument selected
the level with the *weakest* shortcut margin among that mechanism's clean candidates, and then voided the
mechanism for having a weak shortcut margin.** That is the conflation firing in the reported data.

The defence is that L2 could not have qualified either — 0.958 > the 0.85 ceiling → `VOID_CEILING`. True,
and I record it. But that only relocates the problem: for this solver, **there is no level that is both
in the headroom band and shortcut-clean**, and the instrument has no vocabulary to say so. It reports
`VOID_SHORTCUT` — a statement about the probe bank — when the situation is *"headroom and discrimination
are not simultaneously achievable on this ladder."*

There is also a deeper conflation the instrument never addresses: it selects a level by the **solver's**
accuracy, then uses that level to compare **representations**. The optimal operating point for
discriminating representation A from representation B is a property of the A/B pair, not of the control
genome's competence — yet the frontier is frozen from a single control candidate (`V5E_L3_JSON_AST`,
per the artifact's `control_candidate`) before any representation is measured. Whether the control's
frontier transfers to a candidate pair is **assumed, never tested**.

**CONFIRMED · severity: HIGH · effect: the selected frontier is optimised for a quantity the experiment
does not ultimately care about.**

---

# PART G — SOLVER VALIDITY

## G12. Why `qwen38-rvn:latest`? — the justification is unusually good, with one gap

`docs/PHASE6_PREREGISTRATION.md:21-48` gives four grounds: (1) materially different family
(`qwen35` vs `gemma4`); (2) prompt path equalisable — its default and `raw:true` token counts are already
identical; (3) **no thinking-mode hazard** — `capabilities: ["completion"]` only, which matters because
`num_predict = 64` counts thinking tokens and V5 scores an unparsed row *wrong* rather than voiding it;
(4) quantisation matched at Q4_K_M.

**Independently verified from the artifact:** `served_model.capabilities == ["completion"]`,
`template == "{{ .Prompt }}"`, `template_is_passthrough == true`, `quantization_level == "Q4_K_M"`,
`family == "qwen35"`, `digest 25eb57cb…24ae` matching between the V5-qwen and V7 artifacts.

Ground (3) is genuinely excellent reasoning — it identifies a failure mode (thinking tokens consuming the
64-token budget, producing an unparsed row scored as a *wrong answer*) that would have silently corrupted
the result. The preregistration also **declares its own confound** (`:44-48`): a fine-tuned "rvn"
checkpoint at 27.3B vs gemma's 11.9B, so family and scale move together, and it states that a null result
would therefore be weak.

**The gap.** Ground (4)'s supporting claim — *"the most sensitive reader tested: 0.3047 → 0.8750
(+0.5703) on a structural re-rendering"* (`:39-42`) — is **selection on the outcome variable**. The solver
was chosen *because* it is maximally sensitive to representational re-rendering, and the experiment's
purpose is to measure sensitivity to representational re-rendering. That is not fatal (it is a
power-maximising choice, and it is declared), but it means the solver is not a random draw from
"competent solvers" and no result here generalises beyond it.

**LIKELY · severity: MEDIUM (external validity only) · the justification is otherwise the strongest
document in the programme.**

## G13. Is it too capable? — YES, demonstrably

- `precondition_conjunction`: **1.000 / 0.958 / 1.000 / 1.000** across L0–L3. The ladder has no effect
  whatsoever; L3 (5 premises, 6,858 tokens) is as easy as L0. Verdict `VOID_CEILING`.
- **8 of the 12 cells are at ≥ 0.958.** Pooled positive-arm accuracy over all 864-row positives:
  **0.9062** (n = 288).
- Under resampling, `precondition_conjunction` returns `VOID_CEILING` **98.4%** of the time
  (`a5_fragility.json`).

Only 3 of 12 cells land inside the qualifying window `[0.70, 0.85]` at all
(`inside_qualifying_window: true` for FED L1, FED L2, TD L3). The ladder's dynamic range is exhausted
before it reaches this solver's frontier for two of three mechanisms.

**CONFIRMED · severity: HIGH.** `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` §6 already says this
("The ladder never reaches this solver's frontier"); it remains true and unaddressed in V7.

## G14. Is it too weak? — **REFUTED**

Pooled 0.9062; all three explicit-positive L0 arms pass the 0.90 gate (1.000 / 0.958 / 1.000); zero
parse failures; zero truncations. This solver is not too weak. The failure direction is the opposite one.

## G15. Tokenizer favourability — what is knowable without a model call

Computed from recorded `prompt_chars / prompt_tokens`:

| mechanism | chars/token | range |
|---|---|---|
| formal_expression_depth | **3.884** | 2.83 – 5.41 |
| transitive_dependency | 2.930 | 2.89 – 2.96 |
| precondition_conjunction | 2.994 | 2.99 – 3.01 |
| all | 3.269 | — |

**Assessment.** ~3.3 chars/token is poor — English prose typically runs ~4. The encodings are
canonicalised JSON: every `{`, `"`, `:`, `,` costs a token. That is a property of the *encoding*, not of
this tokenizer, and it applies equally to any BPE tokenizer, so it does not favour or disfavour this
solver specifically.

What *is* differential: `formal_expression_depth` compresses 33% better and, crucially, has **20× the
variance** of the other two (2.83–5.41 vs 2.89–2.96). Its prompts are Lean terms with repeated
sub-expressions that merge into single tokens; the other two are synthetic and near-constant in shape.
Since `formal_expression_depth` is also the only mechanism whose accuracy varies across the ladder, a
tokenization-driven confound cannot be excluded from the recorded data alone.

**What cannot be known without model calls:** whether identifiers like `f12`/`f13` or `e:5d4ac` split
into per-character tokens, and whether that split is asymmetric between the two options in a way that
correlates with the answer key. That would be the mechanism behind a tokenizer-level shortcut, and it is
**untested**. It is testable offline with the tokenizer alone (no generation) — a gap worth closing.

**POSSIBLE · severity: MEDIUM · status: UNTESTED, and cheaply testable.**

## G16. Deterministic because temperature = 0, or because the task is deterministic? — **the former, and the twin-pair evidence proves it is not the latter**

The two are cleanly separable here, and the twin pairs do it.

**Fact 1 — the twins are information-identical with opposite targets.**
`a5_errors.json → destroyed_twin_pairs`: **144/144** `DESTROYED_ORIGINAL`/`DESTROYED_COUNTERFACTUAL`
pairs have `identical_prompt_hash: 144`, `identical_raw_output: 144`, `opposite_expected: 144`.
(The brief's "24/24" is per cell; pooled it is 144/144.)

**Fact 2 — this is a statement about the serving stack, not the task.** The two members are the *same
prompt bytes*. Identical output is what any deterministic decoder must produce; it carries **zero**
information about whether the task has a determinate answer. Indeed the pair is constructed so the task
is *maximally indeterminate* — the same evidence supports opposite targets, which is exactly why
`destroyed_accuracy = 0.5000` exactly, in all 12 cells.

**Fact 3 — the determinism is decode-level, and it is broad.**
`a5_analysis.json → repeated_prompt_determinism`: of 717 distinct prompts, 141 appear more than once
(288 rows); **141/141 give an identical answer**, with `cache_scope_totals: {"FRESH": 864}` — no cache
served any of them. Plus: `completion_tokens == 6` for **all 864 rows**, and only two distinct outputs
exist in the entire artifact (`{"choice":"A"}` × 525, `{"choice":"B"}` × 339).

**Conclusion.** Outputs are deterministic because `temperature = 0.0` with a grammar-constrained
`json_schema:choice_ab` decode (`runtime`: `temperature 0.0, seed 20260905, top_k 64, top_p 0.95,
raw true, think false`). **The task is demonstrably NOT deterministic** — 288 of the 864 rows are
constructed to have no determinate answer. Conflating the two would be the error; the artifact's own
twin design prevents it.

**CONFIRMED (distinction is sound and the evidence separates the two cleanly).**

## G17. Has run-to-run stability under multiple seeds ever been measured? — **NO. Plainly, no.**

I searched every artifact. Every run uses `seed: 20260905`. There is **no multi-seed experiment anywhere
in this repository.**

What *has* been measured, and is worth stating precisely because it is stronger than expected:
`a5_replication.json` compares the Phase-6 V5-qwen run against the V7 run — two separate executions, two
different arm schedules (432 vs 864 rows), both `FRESH`:

```
shared_prompts:                     360
identical_raw_output_on_shared:     360
disagreements:                        0
agreement_rate:                     1.0
ladders identical for all 3 mechanisms: true
```

**360/360 byte-identical across two independent runs.** That establishes the serving stack is reproducible
**at a fixed seed** — which rules out nondeterministic-kernel drift, a real hazard on quantised GPU/Metal
backends. It does **not** establish stability *across* seeds.

**What that leaves unknown, stated plainly.** With `temperature = 0.0` the seed should be inert for
greedy decoding — but under Q4_K_M quantisation with `top_k = 64` / `top_p = 0.95` still set in the
options, near-ties in the logits can resolve differently under different sampling-state initialisation,
and the margin gate turns on **one row in 24**. Nobody has checked whether a different seed moves that
row. Given E5 (TD is one row from qualifying), **an unmeasured seed sensitivity of even 1–2 rows in 864
would be enough to flip V7's headline verdict.** This is the single cheapest high-value experiment
outstanding: 24 rows × 3 seeds at the `transitive_dependency` L3 positive cell = 72 calls.

**CONFIRMED as a gap · severity: HIGH · cost to close: ~72 model calls.**

## G18. Could a single deterministic model create a misleadingly stable benchmark? — YES, and this one does

The mechanism is precise. Determinism converts *every* measurement into a **point** with no measurable
dispersion, and the instrument then treats that point as if it were the parameter.

1. **Zero measurable variance is reported.** No cell carries a confidence interval anywhere in the
   artifact. `positive_accuracy: 0.7916666666666666` is printed to 16 significant figures for a
   statistic that is `19/24` with a binomial SE of **0.083**.
2. **Re-running does not detect the fragility** — it reproduces it exactly (360/360, G17). Replication at
   a fixed seed is *unfalsifiable* here: it is guaranteed by construction and yet reads as corroboration.
3. **The gates are knife-edges on that point.** E5: TD is one row from `QUALIFIED`; FED's *level choice*
   flips 55% of the time under resampling.
4. **The stability is contagious.** V7 made 864 fresh calls and recovered the V5-qwen numbers exactly.
   The 864 calls added **no new information about the solver**. V7's genuinely new content — the
   per-level shortcut audit — costs **zero** model calls by construction (`fitness_v7.py:636-660`:
   *"This costs zero model calls: the audit is a property of the probe bank"*). V7 is best described as
   **a re-analysis of Phase-6 data under a changed constant plus a free audit**, not an independent
   replication.

**CONFIRMED · severity: HIGH.** The instrument's apparent stability is an artifact of greedy decoding at
a fixed seed, not evidence that the measured quantities are stable.

## G19. Does the model understand the instructions equally well across mechanisms? — yes at L0, but L0 does not test what is claimed

Explicit-positive L0 arms: `formal_expression_depth` **1.000**, `precondition_conjunction` **1.000**,
`transitive_dependency` **0.958**. All clear the 0.90 `explicit_positive_min` gate. Combined with zero
parse failures, zero truncations, `Q0 rate 1.000` and answer entropy ≈ 1.00 bit at L0 in all three, there
is no evidence of differential *instruction* comprehension.

**The adversarial caveat.** L0 asserts the decisive relation outright in the state
(`explicit_positive_meaning: "the decisive relation is asserted outright in the state"`), so a 1.000 at L0
proves the model can **locate an asserted fact and emit the right letter**. It does not prove the model
understands the *question* at L1–L3, where the relation must be computed. And the one L0 cell that is not
perfect (TD, 23/24) fails by a **position-anchored** row — `a5_errors.json → position_anchoring_by_cell`
gives `transitive_dependency|L0: {pairs: 24, same_letter: 1}`. Even the comprehension control is
contaminated by the bias documented in G20.

**REFUTED as a differential-comprehension flaw; CONFIRMED as an insufficient control.**

## G20. Error taxonomy — the empirical heart

**n = 69 wrong rows** out of 576 `MATHEMATICAL` rows (the other 288 are destroyed twins, scored
`NEGATIVE_CONTROL_RESPONSE` and structurally 0.5).

### G20.1 The statistical correction that changes the answer

The brief asks: *on wrong rows, how often does the model's answer coincide with what
`first_mentioned_in_state` would have predicted?* **Naive answer: 9/69 = 13.0%.**

But on a **binary** forced choice this statistic is algebraically degenerate. A wrong row has
`answer = 1 − expected`. So `answer == rule_prediction` **iff** `rule_prediction ≠ expected`, i.e. **iff
the rule is also wrong on that row.** The naive rate is therefore *not* a measure of following — it is
`1 − (rule accuracy on the model's error rows)`, and it is mechanically driven low whenever the rule is
accurate.

The sound test is the 2×2 contingency of *(model correct) × (rule correct)*. Shortcut-following predicts
model errors **concentrate where the rule is wrong** → rule accuracy on wrong rows ≪ on correct rows,
φ > 0. Both statistics are reported (`a5_errors.json → shortcut_following_tests`).

### G20.2 The direct answer, on the gated arms (n = 288 positives, 27 wrong)

| rule | naive rate on wrong rows | rule acc \| model CORRECT | rule acc \| model WRONG | φ | Fisher p |
|---|---|---|---|---|---|
| **`first_mentioned_in_state`** | **4/27 = 0.148** | 0.663 | **0.852** | **−0.118** | 0.051 |
| `more_frequent_in_state` | 0.259 | 0.713 | 0.741 | −0.018 | 0.827 |
| `always_first_option` | 0.481 | 0.498 | 0.519 | −0.012 | 1.000 |
| `alphabetically_first` | 0.444 | 0.494 | 0.556 | −0.036 | 0.687 |
| `shorter_option_text` | 0.370 | 0.487 | 0.630 | −0.083 | 0.225 |

**The model does not follow `first_mentioned_in_state`. It follows it *less* than chance, and the
association runs the wrong way.** The rule is **85.2%** accurate on the rows where the model is wrong and
only **66.3%** accurate where the model is right — i.e. the model errs *precisely where the shortcut
would have saved it*. φ = −0.118 (negative = anti-following), Fisher p = 0.051.

**Per gated cell** (`per_cell_gated_feature_test`), the level's own audited feature:

| cell | gated feature | model wrong | of those, rule ALSO wrong |
|---|---|---|---|
| formal_expression_depth L1 | first_mentioned_in_state | 4 | **0** |
| **formal_expression_depth L2** (selected) | first_mentioned_in_state | 5 | **1** |
| formal_expression_depth L3 | first_mentioned_in_state | 9 | **1** |
| **transitive_dependency L3** (selected) | first_mentioned_in_state | 6 | **1** (φ = −0.612, p = 0.007) |
| precondition_conjunction L1 | always_first_option | 1 | 1 |

**At the two selected frontiers, 2 of 11 wrong positive rows are shortcut-consistent.** If the model were
executing the shortcut, that number would be 11 of 11.

*(Bookkeeping note: this "2" counts wrong **positive-arm** rows where the gated rule is also wrong — one
in `formal_expression_depth` L2, one in `transitive_dependency` L3. The identically-sized "2" in the
G20.4 taxonomy counts something different: rows over **all** arms that survive the priority ordering to
reach the `shortcut_consistent` bucket, both of which fall in `transitive_dependency` L3. The FED L2 row
is absorbed earlier by `position_anchoring`. Neither count exceeds 2 under any ordering.)*

**REFUTED — decisively.** V7's `VOID_SHORTCUT` verdicts are correct as statements about the *probe bank*
(`best_shortcut_accuracy` is a bank property, and 0.833 / 0.667 are real). They are **not** evidence that
the solver used the shortcut. The artifact never claims otherwise, but the verdict name invites the
inference, and the inference is false. **This is the single most important thing in this audit that
vindicates the instrument's honesty while indicting its labelling.**

### G20.3 What the errors ARE: a position bias the audit is structurally blind to

Restricting to the swapped arms (n = 288, 42 wrong):

| rule | naive rate | rule acc \| model CORRECT | rule acc \| model WRONG | φ | Fisher p |
|---|---|---|---|---|---|
| **`always_first_option`** | **40/42 = 0.952** | 0.577 | 0.048 | **+0.374** | **< 1e-4** |
| `last_mentioned_in_state` | 0.881 | 0.565 | 0.119 | +0.315 | < 1e-4 |

**95.2% of swapped-arm errors are the model answering "A".** And the cleanest possible evidence — the
destroyed twins, where the content carries *no* signal by construction:

| row set | share answering "A" |
|---|---|
| positive arms (balanced key, mostly correct) | 0.497 |
| swapped arms | 0.632 |
| **destroyed twins (no information)** | **0.694** |
| all 864 rows | 0.608 |

**When the content cannot decide, the model picks A about 69% of the time.**

**Why the audit cannot see this.** `always_first_option` *is* in the 7-rule battery
(`fitness_v5.py:802`), but `shortcut_audit` scores every rule against `expected_index` **on the positive
arms only** (`fitness_v5.py:791, 818-821`), where the key is balanced by construction
(`answer_share_index_0` = 0.500 or 0.542). So `always_first_option` **cannot score above ≈0.54 there, no
matter how strongly the model exhibits it.** The battery measures *whether the bank is guessable*; it has
no rule that measures *whether the solver is biased*. Those are different questions and the instrument
only asks the first.

The `position_invariance` gate is the intended catch, and its floor is `0.50` — **exactly the value a
solver that anchors on half its items produces.** `formal_expression_depth` L2 (the selected frontier)
scores **0.583** and **PASSES**. Decoded: 41.7% of its swap pairs were answered by position, not content.

**CONFIRMED · severity: CRITICAL.**

### G20.4 The taxonomy

Assignment is priority-ordered (`research/audit/a5_sel/errors.py`), each row to exactly one category:
format → context → position-anchoring → shortcut-consistent → residual.

| category | operationalisation | n | % of 69 |
|---|---|---|---|
| **position anchoring (content-independent)** | the probe **and its option-swapped twin** received the same letter — a content-driven answer must flip | **39** | **56.5%** |
| **reasoning failure (residual)** | answer flipped correctly under swap (content was read) but the wrong option was chosen, and it is not the gated shortcut | **28** | **40.6%** |
| **shortcut-consistent (gated feature)** | answer equals the level's own audited best-shortcut prediction | **2** | **2.9%** |
| **output-format failure** | `parsed_index is None` ∨ `done_reason ≠ stop` ∨ `error ≠ None` | **0** | 0% |
| **context loss** | `prompt_tokens ≥ 0.9 × num_ctx` | **0** | 0% |
| **task misunderstanding** | — | see note | — |
| **ambiguity** | — | see note | — |

**Per (mechanism, level)** (`taxonomy_by_cell`; `anchor` = position anchoring, `reason` = residual,
`short` = shortcut-consistent):

| cell | anchor | reason | short | total |
|---|---|---|---|---|
| formal_expression_depth L0 | 1 | 0 | 0 | 1 |
| formal_expression_depth L1 | 8 | 8 | 0 | 16 |
| **formal_expression_depth L2** | **10** | 6 | 0 | 16 |
| formal_expression_depth L3 | 11 | 8 | 0 | 19 |
| transitive_dependency L0 | 1 | 0 | 0 | 1 |
| transitive_dependency L2 | 2 | 0 | 0 | 2 |
| **transitive_dependency L3** | 4 | 6 | **2** | 12 |
| precondition_conjunction L1 | 1 | 0 | 0 | 1 |
| precondition_conjunction L3 | 1 | 0 | 0 | 1 |

**Errors are overwhelmingly concentrated in `formal_expression_depth` — 52 of 69 (75%).**

**Example `raw_output` strings** (`a5_error_assignments.json`):

- *position anchoring* — `formal_expression_depth|L1`, `SWAPPED_ORIGINAL`, options `['f34','f33']`,
  expected 1, got 0, `{"choice":"A"}`. Its unswapped twin also answered `A`. Same content, same letter,
  reversed options ⇒ position decided it.
- *reasoning failure* — `formal_expression_depth|L1`, `ORIGINAL`, options `['f0','f15']`, expected 0, got
  1, `{"choice":"B"}`; and its swap, options `['f15','f0']`, expected 1, got 0, `{"choice":"A"}`. The
  model **consistently chose `f15`** both times — it read the content and computed the wrong answer. A
  genuine depth-reasoning error.
- *shortcut-consistent* — `transitive_dependency|L3`, options `['e:5d4ac','e:20c87']`, expected 0, got 1,
  `{"choice":"B"}`; swap: expected 1, got 0, `{"choice":"A"}`. Consistently chose `e:20c87`, which is
  also `first_mentioned_in_state`'s prediction. **These 2 rows are the entire empirical basis for reading
  `transitive_dependency`'s `VOID_SHORTCUT` as solver behaviour.**

**Notes on the two categories I did not populate, stated honestly.**

- **Output-format failure is *vacuously* zero.** `format: json_schema:choice_ab` with
  `enum ["A","B"]` makes any other output *impossible*; `completion_tokens == 6` for all 864 rows. This is
  not a competence finding and must not be read as one. It also means one of V7's inherited design
  worries — "V5 scores an unparsed row as wrong rather than voiding it"
  (`docs/PHASE6_PREREGISTRATION.md:34-36`) — is moot under grammar-constrained decoding.
- **Context loss is *genuinely* zero.** `max_prompt_tokens = 7,960` against `num_ctx = 32,768` (24.3%);
  zero rows above 50%; mean tokens on correct rows 4,555 vs wrong rows 4,566 — a 0.2% difference.
  **REFUTED as a factor.**
- **Task misunderstanding** is not separately identifiable from a single letter with no chain of thought.
  Its best available proxy is position anchoring (a model that anchors is not engaging the task), which is
  why that category is large. Recorded as **UNRESOLVABLE with this response protocol.**
- **Ambiguity**: only `formal_expression_depth` exposes an oracle margin (`oracle_record.features
  .depth_lead`). Accuracy by depth lead: lead 1 → 54/66 = 0.818; lead 2 → 18/20 = 0.900; lead 3 →
  4/8 = **0.500**; lead 4 → 2/2 = 1.000. **Non-monotone** — larger margins are not easier. That refutes
  "the errors are near-tie ambiguity" and points back at anchoring. No tied-oracle probe was found. The
  other two mechanisms carry `features: null`, so **ambiguity is unmeasurable there**.

### G20.5 The headline, stated once

**Wrong answers do NOT match the shortcut's prediction. They match option A.**
2/69 (2.9%) are shortcut-consistent at the gated feature; **39/69 (56.5%) are position-anchored**, and
the model's content-free A-prior is measured at **0.694** on the information-destroyed twins.

## G21. Were prompts tuned after seeing earlier failures? — YES, twice, and one line is a debiasing patch

`build_prompt`, `fitness_v5.py:550-565` (V7 inherits it verbatim —
`inherits_from.unchanged` includes `"prompt template"`):

```python
'Answer with the JSON object {"choice":"A"} or {"choice":"B"}.\n'
"Read identifiers exactly. Do not choose by option position.\n"
```

**Change 1 — the anti-position instruction, added at V3.** `git log -S "Do not choose by option position"`
returns `9616654 Freeze qualified representation fitness v3 instrument` as the earliest commit. It is
absent from `fitness_v1.py:348` and `fitness_v2.py:913`, and present identically in
`fitness_v3.py:551` and `fitness_v4.py:1159`.

**Change 2 — the response-format instruction, rewritten at V5.** V2/V3/V4 all use
`'Return exactly {"choice":"A"} or {"choice":"B"}; no explanation.'`; V5 changes it to
`'Answer with the JSON object …'` under commit `2c61fdb feat: Fitness V5 -- protocol repaired and proven`.
The commit subject states the motivation: the V4 protocol failed and was repaired.
`docs/FITNESS_V4_FAILURE_ANALYSIS.md:33` names the failure —
*"a constant-position policy under uncertainty"* — and `:71` records *"Too hard from L1 on: constant 'A'."*

**Assessment.**

`"Do not choose by option position."` is a **debiasing patch aimed at the exact failure mode this audit
finds still dominant.** Its presence has three consequences:

1. **It did not work.** With the instruction in the prompt, 56.5% of errors are still position-anchored
   and the destroyed-twin A-prior is still 0.694.
2. **It confounds the shortcut audit.** The prompt actively instructs *against* `always_first_option` and
   *for* reading identifiers exactly. Any measured shortcut accuracy is therefore conditioned on an
   anti-shortcut instruction. A clean measurement of "does this solver use shortcuts" would need the
   instruction removed — an experiment never run.
3. **It fixes a per-prompt token cost** on every one of the 864 rows for a bias it does not remove.

**Which results are engineering diagnostics rather than science?** Being precise about the boundary:

- **V1–V4 are engineering diagnostics.** The protocol was demonstrably broken (V4 failure analysis) and
  the prompt was changed in response.
- **V5 onward is defensible science on this axis.** The prompt has been frozen since commit `2c61fdb`;
  `docs/FITNESS_V7_PREREGISTRATION.md` predates the run (`e66bab1` precedes `cf1b07f "Fitness V7
  launched"`); V7's artifact declares `prompt template` unchanged; and the pre-run `BUG_FOUND` disclosure
  about the non-neutral prompt path (`docs/PHASE6_PREREGISTRATION.md:50-61`) was found *before* the run,
  declared, and corrected by running both solvers bare rather than patched silently. **That is
  well-conducted work and I record it as such.**
- **The residual problem is not tuning but inheritance.** V5+ inherits a prompt shaped by V2–V4 failures
  against a *different* solver (`gemma4:12b`). No one has asked whether the anti-position instruction —
  tuned on gemma's constant-A collapse — helps, hurts, or is inert for `qwen38-rvn`.

**CONFIRMED (tuning occurred) · severity: MEDIUM · scope limited to V1–V4; V5–V7 are frozen and
preregistered.**

---

# Classified flaw list

| # | Finding | Class | Severity | Effect |
|---|---|---|---|---|
| **F1** | Selection and qualification read the **same 24 rows per cell**; `arms == "full"` so nothing is measured after selection (`fitness_v7.py:1024, 1063, 1092`). The `selection_source: "DEV only"` phrasing implies an independence V3 had and V4+ silently dropped | **CONFIRMED** | HIGH | every gate reading `positive_accuracy` is conditioned on the selection |
| **F2** | **`transitive_dependency` is ONE row from `QUALIFIED`** (18/24; needs 19/24 for the 0.10 margin). P(QUALIFIED) under resampling = **0.316** | **CONFIRMED** | **CRITICAL** | V7's "0 of 3 / SHORTCUT_DOMINATED" headline is one row deep |
| **F3** | `formal_expression_depth`'s level choice flips under resampling **55.4%** of the time; L1 (0.463) is marginally likelier than the reported L2 (0.446) | **CONFIRMED** | HIGH | the published frontier is not a stable property |
| **F4** | **56.5% of errors are position-anchored** (39/69); destroyed-twin A-prior **0.694**; `always_first_option` φ = +0.374, p < 1e-4 on swapped arms. The shortcut battery **cannot detect it** — it scores rules against a balanced key, capping `always_first_option` at ≈0.54; the `position_invariance` floor of 0.50 is at chance, and the selected FED L2 passes at 0.583 | **CONFIRMED** | **CRITICAL** | the dominant failure mode is invisible to the gates designed to catch it |
| **F5** | V7 adopted the `window_midpoint_0.775` selector **without** the paired gap calibration, tripling the measured no-true-in-window qualification rate **0.081 → 0.262** (above the 0.170 oracle ceiling). Measured in-repo *before* V7 (`v5_selector_analysis.json §3, §5`) and absent from `docs/FITNESS_V7_PREREGISTRATION.md` | **CONFIRMED** | HIGH | latent FP inflation; did not manifest in this run (0 qualifications) |
| **F6** | Solver is **too capable**: `precondition_conjunction` 1.000/0.958/1.000/1.000; 8/12 cells ≥ 0.958; only 3/12 inside `[0.70, 0.85]`; `VOID_CEILING` 98.4% under resampling | **CONFIRMED** | HIGH | two of three mechanisms are unmeasurable with this ladder |
| **F7** | **No multi-seed experiment exists anywhere.** All runs `seed: 20260905`. Cross-run reproduction is 360/360 but *at a fixed seed*, so it is guaranteed, not corroborative | **CONFIRMED** | HIGH | with F2 at one row, unmeasured seed sensitivity could flip the verdict; ~72 calls to close |
| **F8** | Headroom and shortcut-margin objectives **disagree**: TD headroom → L3 (margin +0.083, fails), discrimination → L2 (+0.333, clean). The frontier is also frozen from one control genome before any representation is measured | **CONFIRMED** | HIGH | the frontier optimises a quantity the experiment does not care about |
| **F9** | V7's 864 fresh calls reproduced Phase-6 exactly (identical ladders, 360/360 rows); its new content (per-level shortcut audit) costs **zero** model calls. V7 is a re-analysis under a changed constant, not an independent replication | **CONFIRMED** | MEDIUM | affects how V7's evidential weight should be described |
| **F10** | `formal_expression_depth`'s bank is **uniformly shortcut-contaminated**: `first_mentioned_in_state` ≥ 0.833 at every non-explicit level. No target can select a clean level | **CONFIRMED** | HIGH | generator defect, not a selector defect |
| **F11** | The prompt carries a debiasing patch (`"Do not choose by option position."`, added at V3 in response to gemma's constant-A collapse) that **does not work** on this solver and **confounds** any shortcut measurement | **CONFIRMED** | MEDIUM | shortcut audit is conditioned on an anti-shortcut instruction |
| **F12** | `SCOUT_FAMILIES = 16`, `V5Slice.SCOUT` and `scout_max: 3000` are **dead** in V5/V7 (one occurrence each, no readers), while V3 built the pool at `fitness_v3.py:829` | **CONFIRMED** | MEDIUM | the fix for F1 was designed, built once, then abandoned |
| **F13** | Tokenizer sensitivity **untested**; `formal_expression_depth` has 20× the chars/token variance of the other mechanisms and is the only one whose accuracy moves | **POSSIBLE** | MEDIUM | testable offline with the tokenizer alone, no generation |
| **F14** | Solver chosen *because* maximally sensitive to representational re-rendering (`PHASE6_PREREGISTRATION.md:39-42`) — selection on the outcome variable, though declared | **LIKELY** | MEDIUM | external validity only |
| **F15** | Ladders are **non-monotone** in accuracy for 2 of 3 mechanisms (TD 0.958→1.000→0.958→0.750; PC 1.000→0.958→1.000→1.000) | **CONFIRMED** | MEDIUM | "difficulty ladder" is a misnomer for those two |
| **R1** | **Wrong answers do NOT follow the shortcut.** `first_mentioned_in_state` is 85.2% accurate where the model is wrong vs 66.3% where right (φ = −0.118). 2/11 error rows at the selected frontiers are shortcut-consistent | **REFUTED** | — | `VOID_SHORTCUT` is sound about the bank, false about the solver |
| **R2** | The 0.775 derivation is arithmetically correct and `DESTROYED_EXPECTED = 0.50` is empirically confirmed 144/144 | **REFUTED** | — | instrument holds |
| **R3** | Aiming at a narrow target does **not** steer toward strong-shortcut levels: chosen-level mean shortcut 0.667 vs uniform-random 0.708, exact one-sided p = 0.889 | **REFUTED** | — | brief's key hypothesis does not survive |
| **R4** | Context loss is not a factor: max 7,960 / 32,768 tokens; correct 4,555 vs wrong 4,566 mean tokens | **REFUTED** | — | instrument holds |
| **R5** | Solver is not too weak (pooled 0.906; all L0 arms ≥ 0.958; zero parse/truncation failures) | **REFUTED** | — | instrument holds |
| **R6** | V5–V7 prompts are frozen and preregistered; the `BUG_FOUND` non-neutral-prompt-path defect was found pre-run, declared, and corrected rather than silently patched | **REFUTED** | — | well-conducted; tuning is confined to V1–V4 |

## Cheapest experiments that would resolve the most

1. **~72 calls** — `transitive_dependency` L3 positives under 3 alternative seeds. Closes F7; directly
   tests whether F2's one-row margin is seed-stable.
2. **0 calls** — score `always_first_option` against the **model's answers** rather than the answer key,
   and re-derive `position_invariance_min` from a null model instead of leaving it at chance. Closes the
   detection half of F4.
3. **0 calls** — tokenize both options per probe and test for answer-key-correlated splitting. Closes F13.
4. **~288 calls** — a fresh SCOUT pool at each selected level. Closes F1; the budget line already exists.
