# Fitness V7 Result — the mechanisms are shortcut-dominated

**Sentinel: `V7_SHORTCUT_DOMINATED`** · **`instrument_qualified: false`** ·
**qualified mechanisms: 0 of 3**

Preregistration: `docs/FITNESS_V7_PREREGISTRATION.md`, committed at `e66bab1` **before** the first
call. No threshold was changed after the run.

Artifact: `artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json`.
Instrument `arena-game-r-derived-frontier-instrument-v7.0.0`. Solver `qwen38-rvn:latest`, digest
`25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`, bare condition. 864 rows,
**all `FRESH` — zero cache hits, zero `CROSS_CONDITION`**. Q0 1.000. Run 12:38:56–14:21:12.

---

## 1. The result

| Mechanism | selected | accuracy | best shortcut | feature | margin | verdict |
|---|---|---|---|---|---|---|
| `formal_expression_depth` | **L2** | 0.7917 | **0.8333** | `first_mentioned_in_state` | **−0.0417** | `VOID_SHORTCUT` |
| `transitive_dependency` | **L3** | 0.7500 | 0.6667 | `first_mentioned_in_state` | **+0.0833** | `VOID_SHORTCUT` |
| `precondition_conjunction` | — | ≥0.958 at every level | 0.500 | `always_first_option` | — | `VOID_CEILING` |

Full ladders (each cell n = 24; every value reproduces Phase 6 exactly, confirming determinism):

| Mechanism | L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| `formal_expression_depth` | 1.000 | 0.833 | 0.792 | 0.625 |
| `transitive_dependency` | 0.958 | 1.000 | 0.958 | 0.750 |
| `precondition_conjunction` | 1.000 | 0.958 | 1.000 | 1.000 |

Per-level shortcut accuracy — **the measurement V5 never made**:

| Mechanism | L0 | L1 | L2 | L3 |
|---|---|---|---|---|
| `formal_expression_depth` | 0.667 | **1.000** | **0.833** | 0.917 |
| `transitive_dependency` | 1.000 | 0.833 | 0.625 | 0.667 |
| `precondition_conjunction` | 1.000 | 0.500 | 0.500 | 0.500 |

## 2. The instrument is sound; the mechanisms are not

Every other gate passed on both selected cells: `q0`, `valid_response`, `context`, `answer_share`,
`position_invariance`, `negative_collapse`, `sample_size` — all **PASS**. There is no protocol
failure here. The two corrections did exactly what they were registered to do:

- **The derived target worked.** `frontier_target = (0.50 + 0.20 + 0.85)/2 = 0.775` moved
  `formal_expression_depth` from L3 (0.625, unqualifiable under any gate) onto L2 (0.792, inside
  the [0.70, 0.85] window) — precisely as `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` §11
  anticipated.
- **The per-level shortcut audit then killed it.** At L2 a single surface rule,
  `first_mentioned_in_state`, scores **0.8333** — it **outscores the solver's 0.7917**.

## 3. Phase-6 §11 is refuted, by measurement

That document states a corrected target would have given L2 "and passed, giving 2 qualified
mechanisms and authorising the founder tournament." It would not have.

`formal_expression_depth` at L2 fails **`shortcut_absolute`** — 0.8333 exceeds **V5's own frozen**
`QUALIFICATION_RULE["shortcut_rule_max"] = 0.75` (`arena/experiments/fitness_v5.py:225`). L2 was
already unqualifiable under V5's unmodified rules. V5 never revealed this because it audits
shortcuts **only at the selected frontier**, and reported only `failures[0]`. V7 reports
`all_failures`, and for this mechanism that list is `['shortcut_absolute', 'shortcut_margin']`.

The same holds at L1 (shortcut **1.000**). **Every in-window level of this mechanism is
shortcut-dominated.** It is not rescuable by selection.

## 4. The harder finding: `transitive_dependency`

This is the only mechanism ever to qualify in the programme's history (Phase 6, L3). Under V7 it
scores 0.750 against a shortcut of 0.667 — a margin of **0.0833**, missing the preregistered 0.10
gate by **0.017**.

It passes `shortcut_absolute` (0.667 ≤ 0.75). It fails only the new margin. So the honest statement
is precise and two-sided:

- **Under V5's frozen rules it qualifies.** Phase 6's finding stands on its own terms.
- **Under V7's stricter rule it does not.** A solver that beats a first-mention heuristic by 8.3
  points on 24 items is not demonstrating mechanism-specific reading; at n = 24 that gap is
  ≈ 1.0 standard error.

`SHORTCUT_MARGIN = 0.10` was fixed in the preregistration before any V7 number existed, and was not
moved. Lowering it to 0.08 would qualify this mechanism. That would be protocol shopping and is
refused.

## 5. `precondition_conjunction` is a ceiling problem, not a shortcut problem

Its best shortcut is 0.500 — chance. The mechanism is clean. The solver simply answers it perfectly
(1.000 at L2 and L3, 0.958 at L1). **The ladder does not reach this solver's frontier.** This is the
one mechanism worth extending upward rather than abandoning.

## 6. What this does and does not establish

**Does:** on this probe bank and this solver, no mechanism supports a Game-R comparison. Two are
beaten or near-matched by a one-line string heuristic; the third is saturated. `RSTAR_NOT_IDENTIFIED`
stands and **no founder tournament is authorised** — the gate needs 2 qualified mechanisms and got 0.

**Does not:** say representation does not matter. **No representation was scored at any point.**
V7, like every instrument before it, measured only the control surface. It also says nothing about
the three new formal task families, which were not run.

**Limits.** n = 24 per cell; the qualifying window is ≈1.76 SE wide and both real ladders step
across it in one move. Granularity, not the aim point, is now the binding constraint — as the
preregistration stated in advance. The shortcut rules are V5's inherited set; a richer adversary
would only lower these margins further.

## 7. Consequence

Do **not** build a V8 on this probe bank. The preregistration's stopping rule already says so: the
next move is a task family with a **reachable frontier and audited shortcuts**, not another
instrument version. Three such families now exist
(`docs/GAME_R_FORMAL_ARENA_V1_SPEC.md`), and a canonical premise-selection bridge exists as a
research prototype (`docs/astra/`) — but see that spec's §2 for why neither is yet a Game-R
instrument.
