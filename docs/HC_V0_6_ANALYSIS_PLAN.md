# HC-V0.6 — the analysis plan

**Status: PLAN, written before any assay data exists.** Revised 2026-09-09 for the **rebuilt**
anchor bank (1127 anchors / 330 files) and the owner's redefinition of the primary endpoint to
`KERNEL_ACCEPTED_STATE_CHANGE`. No Solver call has been made against the bank, so no scientific
exposure boundary has been crossed and the revision is permitted in full (preregistration §0).
§6 is **frozen text**: it fixes the multiplicity rule before any `R` outcome exists.

It is the justification layer under
`arena/experiments/hc_v0_6/` and it is organised around the nine fields manual §30.3 requires a
confirmatory manifest to specify. Every choice below is argued, not asserted, and every choice that
is *not* settled is named as open rather than smoothed over.

Governing authority: `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` §30.
Companions: `docs/HC_V0_6_DESIGN_BRIEF.md` (the design), `docs/HC_V0_6_PREREGISTRATION.md` (the
manifest and its `PENDING` register), `docs/HC_V0_6_ANCHORED_DELTA_SPEC.md` (the experiment).

This document does not freeze the manifest. It fills the statistical slots the manifest leaves
`PENDING` and shows the working; the freeze is a separate, dated act.

---

## 0. What exists, in one table

| module | what it fixes |
|---|---|
| `arena/experiments/hc_v0_6/schema.py` | the result contract: one row per `(anchor, arm, replicate)` |
| `arena/experiments/hc_v0_6/power.py` | the design effect, the required `n`, and the MDE (§9.5) |
| `arena/experiments/hc_v0_6/estimators.py` | the paired estimators and the frozen four-member Holm family (effect claims only) |
| `arena/experiments/hc_v0_6/calibration.py` | the certification gates, their IUT composition, and the gate a result must pass to be reported |
| `tests/experiments/test_hc_v0_6_analysis.py` | 65 offline checks, including the type-I, power, resolution and false-certification *measurements* |

Nothing in the package imports Lean, Ollama, or the live trajectory stack. That is deliberate: an
analysis that can only be exercised by re-running the experiment cannot be checked *before* the
experiment runs, which is the only time checking it is worth anything.

---

## 1. Primary endpoint (§30.3)

**`KERNEL_ACCEPTED_STATE_CHANGE`.** A cell scores **1** iff the Lean elaborator accepts the
Solver's single proposed tactic at the anchored state **and** that action either closes the task or
changes the backend mathematical state. A **no-op scores 0**.

`p_event(R)` is the probability of that event under rendering `R`. Binary per cell,
elaborator-adjudicated.

**Why the endpoint moved (owner directive, 2026-09-09).** The earlier endpoint was
`ACCEPTED_TRANSITION` — bare elaborator acceptance. `docs/HC_V0_5_REDTEAM.md` measured that `skip`
is accepted, leaves `goal_digest` unchanged, and costs almost nothing: under the old endpoint a
policy could have maximised the score by emitting a tactic that does no mathematics. The endpoint
is now the conjunction, and the conjunction is carried by the `StepResult` vocabulary rather than
by a side flag, so it cannot drift from what the runner recorded:

| `StepResult` | Lean accepted | state moved | endpoint |
|---|---|---|---|
| `ACCEPTED_TRANSITION` | yes | yes (or closed) | **1** |
| `ACCEPTED_NO_OP` | yes | **no** | **0** |
| `REJECTED_INVALID_ACTION`, `PARSE_FAILURE`, `UNSUPPORTED` | no | — | 0 |
| `ENVIRONMENT_ERROR`, `TOOL_TIMEOUT`, `NOT_ATTEMPTED` | — | — | **excluded, never 0** |

`ENDPOINT_EVENT_RESULTS = {ACCEPTED_TRANSITION}` is the whole definition, and
`CellOutcome.kernel_accepted_state_change` is derived from it, never supplied. `CellOutcome`
additionally exposes `kernel_accepted` — Lean's raw verdict — as a *descriptive* quantity, so the
gap between "the elaborator did not complain" and "the endpoint fired" is measurable (it is exactly
the no-op rate) rather than invisible. `SCHEMA_VERSION` moved to `v1.1.0`, so a table written under
the old endpoint cannot be silently pooled with one written under the new one.

The harness-failure row is not a courtesy: an `ENVIRONMENT_ERROR` is the harness failing, never a
mathematical zero, and `CellOutcome.analysable` excludes it from the estimators instead of scoring
it. Arm-dependent loss of those cells is outcome O7 (§8).

**Estimand.** With `k` replicates per cell, the per-anchor rate is `p̂_i = events_i / k` and

```
Δ̂ = (1/n) Σ_i ( p̂_{i,B} − p̂_{i,A} )
```

the **anchor-averaged** paired difference, not the cell-pooled one.

*Why anchor-averaging.* "Paired within anchor" has a definite meaning: the anchor is the unit that
carries the pairing, so it must also be the unit that carries the weight. Cell-pooling
(`Σ events / Σ cells`) silently re-weights towards anchors that kept more replicates, which makes
the estimand a function of which cells the harness happened to lose. Anchor-averaging is stable
under that loss and is unbiased for the mean per-anchor effect. `PairedCells` keeps the raw
replicate outcomes rather than only their counts (§30.7), so this is checkable rather than trusted.

**Secondary:** `p_close`, the **no-op rate** (`kernel_accepted` minus the endpoint), parse-failure
rate, token counts. Not corrected for multiplicity, not used to decide anything, and reported as
descriptive. The no-op rate is the one that must be published beside every arm: if it is large, the
endpoint change is doing real work and the old numbers were inflated; if it is zero, the change was
free. Either way it is a measurement, not an assumption.

---

## 2. Minimum practical effect `delta_min` and the equivalence region

`delta_min` is the Experimentalist's slot (preregistration §2) and this plan does **not** invent
it, because §2's constraint 3 is binding: `delta_min` must be set before C2's sensitivity floor is
measured, and it must be justified rather than conventional. What this plan supplies is the
*evidence* that slot needs — the MDE curve of §3 — plus the two constraints the number must satisfy
once the owner sets it:

1. **Representability.** At `n = 1127` anchors the anchor-averaged Δ moves in steps of
   `1/(1127·k)` at best, and the *cluster* bootstrap's resolution is coarser still — the interval
   is built from 330 file-level sums. `1/1127 = 0.00089`, so anything at or above a fifth of a
   percentage point is representable; the binding constraint is power, not granularity.
2. **It must not be below the MDE.** A `delta_min` the design cannot see is a gate that can never
   be reached: the run would be structurally incapable of returning O3, and every outcome would
   collapse to O2. That is a design defect, not a conservative choice.

### 2.1 The owner's declared `delta_min = 0.05`, answered honestly

**The bank does not support it across the plausible parameter range.** §3.3 is the evidence; the
verdict is:

* At a baseline event rate of **0.225 or above, 5 points is unreachable at every ICC, including
  ICC = 0** — the MDE at ICC = 0 is already 5.11 points at baseline 0.225 and 5.27 at 0.25.
* Below that the answer depends on the ICC, and the boundary is sharp. The largest ICC at which
  the rebuilt bank still resolves 5 points, by baseline (measured by bisection in
  `test_the_icc_ceiling_for_five_points_is_recorded_baseline_by_baseline`):

  | baseline `p_event(R_A)` | 0.10 | 0.125 | 0.15 | 0.175 | 0.20 | ≥ 0.225 |
  |---|---|---|---|---|---|---|
  | **max ICC that still resolves 5 pts** | **0.215** | 0.137 | 0.082 | 0.042 | 0.011 | **never** |

* The plausible ICC band is **0.2–0.5** (§3.3). Intersecting the two: `delta_min = 0.05` is
  achievable **only** in the corner *baseline ≲ 0.10 **and** ICC ≲ 0.2*, and nowhere else.

**The baseline is not yet known** — a preflight is measuring it, and the endpoint change of §1 can
only move it *down* (no-ops that used to count now do not). So the corner where 5 points is
reachable is the low-baseline corner, which is not implausible; but it is a corner, and it is not
where a 0.25 baseline would put us. Every MDE in §3.3 is a table with the baseline as a free
parameter for exactly this reason.

**What this does and does not license.** It does not license setting `delta_min = 0.05` and hoping.
The three honest options, and only these:

1. Set `delta_min` at or above the MDE at the realised baseline and ICC — on current information
   that is **7 points** at ICC 0.2 / baseline 0.25, **8.5** at ICC 0.5.
2. Keep `delta_min = 0.05` and **grow the bank** to the size §3.3 costs it at — between 1.1× and
   2.8× the current bank depending on the ICC.
3. Keep `delta_min = 0.05`, run anyway, and accept in advance that O3 is unreachable and every
   null is O2. That is a legitimate choice *if declared before the run*, and a defect if
   discovered after it.

This plan does not choose. It refuses to let the choice be made silently.

**Equivalence region.** The two-one-sided-test region `[−δ_eq, +δ_eq]` is what makes outcome O3
(informative null) reachable at all; `ReportableResult` requires it as an argument
(`equivalence_bound`) and `PairedEffect.equivalent_within` implements it as "the preregistered
cluster CI lies entirely inside ±δ_eq". It is a parameter, with no default, precisely so that
nobody can obtain an informative null without having declared one.

---

## 3. Sample size, precision, and the MDE (§30.3, design brief §9.5)

### 3.1 The realised bank — REBUILT 2026-09-08

Read from `artifacts/trajectory/hc_v0_6_anchor_bank.json` (content hash
`f13ffee5aae464d6f4717c4f85cd6ec1091eb19d9ca0ab5cd716094a9b583b40`) by
`ClusterProfile.from_anchor_bank()`, not typed in:

| quantity | rebuilt | previous |
|---|---|---|
| anchors | **1127** | 223 |
| theorems | 393 | 78 |
| **mathlib files (the cluster unit)** | **330** | 75 |
| anchors per file | `{1:10, 2:10, 3:260, 4:3, 5:6, 6:33, 7:1, 9:3, 10:2, 11:1, 12:1}` | `{1:2, 2:7, 3:63, 6:3}` |
| mean cluster size | 3.415 | 2.973 |
| **effective cluster size `m_A = Σm²/Σm`** | **4.022** | 3.161 |
| re-derivation | 1127 / 1127 | — |

`m_A`, not the mean, is what drives the design effect. With unequal clusters the mean understates
it; here by 18%, up from 6% — **the rebuild made the clusters more unequal, so every anchor is
worth less than it was.** The two effects pull in opposite directions and only their ratio matters:

| ICC | DEFF (rebuilt) | effective n (rebuilt) | effective n (previous) | gain |
|---|---|---|---|---|
| 0.0 | 1.000 | 1127.0 | 223.0 | 5.05× |
| 0.2 | 1.604 | 702.4 | 155.7 | 4.51× |
| 0.5 | 2.511 | 448.8 | 107.2 | 4.19× |

So the rebuild bought a little over 4× the effective sample, not the 5.05× the raw anchor count
suggests. `test_the_rebuild_bought_precision_and_paid_for_it_in_design_effect` asserts both halves
of that, so the design effect cannot be quietly dropped from the accounting.

### 3.2 The variance model

```
Var(Δ̂) = Var(D_i)/n × DEFF        Var(D_i) = (π_d − δ²) × f
DEFF    = 1 + (m_A − 1) ρ_D        f = (1 + (k − 1) ρ_rep)/k
```

* `D_i = p̂_{i,B} − p̂_{i,A}`; at `k = 1`, `D_i ∈ {−1, 0, +1}` and `Var(D_i) = π_d − δ²` exactly.
* `ρ_D` is the ICC of `D_i` **within a mathlib file** — the analysis-level quantity the cluster
  bootstrap and the cluster permutation exist to absorb.
* `ρ_rep` is the ICC of replicate outcomes **inside one cell**. See §3.4.
* `π_d` (discordance) is derived from the marginals, because the caller supplies a baseline rate and
  a δ, not a discordance:
  `π_d = (1 − φ)·[p_A(1−p_B) + p_B(1−p_A)] + φ·|δ|`, with `φ = 0` (arms independent given the
  anchor) as the default. `φ = 0` is the **largest** discordance the marginals allow, hence the
  largest variance and the most conservative `n`. Any measured arm concordance shrinks the required
  sample sharply, so `φ` is a parameter and not a constant — a pilot can tighten it without editing
  the module.

The powered test is the **cluster sign-flip permutation test on Δ̂**, which is what actually
decides — not exact McNemar, which is reported but decides nothing. Powering the reported-but-inert
test would be exactly the granularity substitution preregistration §3 forbids. The permutation test
is asymptotically the cluster-robust z-test for Δ̂, so power is computed from the normal
approximation and then **checked against a simulation of the real permutation test**.

### 3.3 The MDE at the REBUILT bank — the number every null is reported beside

`α = 0.05` two-sided, power `0.80`, `k = 1` under a deterministic Solver, arms assumed independent
(`φ = 0`, the conservative choice). MDE in **percentage points**, computed by
`minimum_detectable_effect(baseline, ClusterProfile.from_anchor_bank(), cluster_icc=…)` and frozen
in `test_the_mde_grid_on_the_rebuilt_bank_is_recorded`:

| baseline `p_event(R_A)` | ICC = 0 | ICC = 0.1 | ICC = 0.2 | ICC = 0.3 | ICC = 0.5 |
|---|---|---|---|---|---|
| 0.10 | **3.82** | 4.40 | **4.92** | 5.41 | 6.29 |
| 0.15 | 4.45 | 5.11 | 5.71 | 6.26 | 7.25 |
| 0.20 | 4.92 | 5.64 | 6.29 | 6.88 | 7.95 |
| **0.25** | 5.27 | 6.03 | **6.72** | 7.35 | 8.47 |
| 0.30 | 5.53 | 6.33 | 7.04 | 7.69 | 8.85 |
| 0.40 | 5.83 | 6.66 | 7.39 | 8.06 | 9.26 |
| 0.50 | 5.88 | 6.70 | 7.43 | 8.09 | 9.27 |

**The baseline is a parameter, not a known.** A preflight is measuring `p_event(R_A)`; until it
lands, every cell above is conditional. The endpoint change of §1 can only move the baseline
*down*, which moves the MDE *down* with it — the one direction in which the honest answer improves.

**The k column is degenerate under determinism** (§3.4): with `ρ_rep = 1`, `k = 5` gives exactly
the `k = 1` number, and `test_replicates_cannot_rescue_five_points_under_a_deterministic_solver`
asserts it. Replicates are not a route to 5 points.

Reading this honestly: **the rebuilt bank resolves roughly 5–9 points, depending on the baseline
and the ICC.** That is a real improvement on the 12–18 points the 223-anchor bank managed, and it
is still not 5 points except in the low-baseline / low-ICC corner of §2.1.

**Required sample for `delta_min = 0.05`** (baseline 0.25, `k = 1`, deterministic; anchors /
files), against the 1127 / 330 that exist:

| ICC | anchors needed | files needed | multiple of the current bank |
|---|---|---|---|
| 0.0 | 1248 | 366 | 1.11× |
| 0.1 | 1626 | 477 | 1.44× |
| 0.2 | **2003** | **587** | **1.78×** |
| 0.3 | 2380 | 697 | 2.11× |
| 0.5 | 3134 | 918 | 2.78× |

At a **low** baseline the gap closes: at baseline 0.10 the same requirement is 1096 anchors / 321
files at ICC 0.2 — *below* the bank that exists, which is the same statement as the 0.215 ICC
ceiling in §2.1 read from the other side.

`test_the_bank_needed_for_five_points_is_bigger_than_the_bank_that_exists` asserts the baseline-0.25
row exactly, so the gap cannot be quietly rounded away.

`ρ_D` is **not measured**. It is a design parameter here, and 0.2–0.5 is the plausible band: the V7
audit measured an ICC of +0.51 for a paired difference in a comparable twin design
(`arena/experiments/precondition_power.py` module docstring). Whichever value the data turns out to
support, the *reported* MDE must be recomputed at the realised ICC after the run and published
beside Δ; the analysis plan fixes the method, not the answer.

### 3.4 What determinism changes — and what it does not

Preliminary noise measurement suggests the Solver may be call-for-call deterministic under the
frozen decoding (40/40 byte-identical responses across three prompt lengths). Confirmation is
another work item's. The design must survive both worlds, so both are stated:

**If the Solver is deterministic (`ρ_rep = 1`):**

* `f = (1 + (k−1)·1)/k = 1` for every `k`. **Replicates buy nothing.** A second call on the same
  prompt returns the same bytes; it is a copy, not a draw. `k = 1` is the honest design and the
  budget saved is real.
* `ReplicateModel.effective_replicates` is 1 no matter what `k` is set to. This is enforced in code
  and tested (`test_replicates_buy_nothing_when_the_solver_is_deterministic`) so that a `k` chosen
  for comfort cannot silently appear as power the design does not have.
* The estimators do **not** assume replicate variance exists. `Var(D_i)` is estimated *between
  anchors*, never within a cell; `paired_bootstrap_ci` resamples files, `permutation_null` flips
  file labels. Both are functions of the `n = 1127` per-anchor differences alone. With `k = 1` each
  `D_i ∈ {−1, 0, +1}`; nothing degenerates and no variance component goes to zero.
* **The permutation test stays exactly valid.** Its null is the *sharp* null "the arm label changes
  no cell's outcome", and its randomisation is the experimenter's sign flip, not the Solver's
  randomness. A deterministic Solver removes a nuisance source; it removes nothing the test relies
  on. The bootstrap likewise resamples files, and files remain a random sample regardless of what
  the Solver does inside a cell.
* **The only remaining randomness is the anchor sample itself.** Every inferential statement becomes
  a statement about the population of mathlib goal states the bank was drawn from, and about
  nothing else. There is no "run-to-run" uncertainty left to average over, which also means a
  replication with the same bank and the same Solver would return the *same numbers*, not merely
  compatible ones — a replication in that world tests the pipeline, not the finding.
* **C1 degenerates.** Two byte-identical prompts give byte-identical responses, so `Δ(R_A, R_A) = 0`
  by construction. `ControlReading` detects this (every per-anchor difference exactly zero) and sets
  `degenerate = True`; `CalibrationVerdict.identity_informative` becomes `False` and the released
  result carries a caveat saying so in words. A zero C1 in that world demonstrates that the Solver
  is a function. It is **not** evidence that the analysis pipeline can detect anything, and the null
  control's whole weight then falls on **C1b** (`R_A` vs `R_A_PRIME`), which is precisely why the
  fourth arm exists.

**If the Solver is noisy (`ρ_rep < 1`):** `k ≥ 2`, `f = (1 + (k−1)ρ_rep)/k < 1`, replicates are
worth their cost, and C1 is built by splitting `R_A`'s replicates in half (`split_half_identity`,
design brief §9.2). That split uses `k/2` per side where the headline uses `k`, so C1's variance is
roughly twice the headline's and C1 **over-states** the noise floor — the conservative direction,
and the reason the construction is acceptable (preregistration §4.3).

`split_half_identity` raises `IdentityControlUnavailable` rather than silently returning something
when `k = 1`. That is not an inconvenience to route around: it is the code saying C1 was not run.

---

## 4. Paired method (§30.3)

### 4.1 How replicates are collapsed, and why

The estimand is a real number per anchor (`p̂ = events/k`), so **the bootstrap, the permutation
test and Δ̂ itself use all `k` replicates and collapse nothing.** Collapsing is needed only by
McNemar, which requires one binary outcome per side.

`ReplicateCollapse` enumerates the five options and the choice is frozen at **`FIRST_REPLICATE`**:

| collapse | estimand preserved | independence preserved | verdict |
|---|---|---|---|
| `FIRST_REPLICATE` | yes | yes | **preregistered** |
| `MAJORITY` / `ANY` / `ALL` | **no** — changes `p_event` into a functional of the replicate distribution | yes | diagnostic only |
| `POOLED_REPLICATE_PAIRS` | yes | **no** — `n·k` dependent pairs | anti-conservative; exists only so the size of that error can be measured |

McNemar's exactness rests on the discordant pairs being independent `Bernoulli(½)` under the null.
Pooling `n·k` replicate pairs breaks that badly, because replicates inside one anchor are strongly
dependent — under determinism they are *identical*, which would inflate every discordant count by a
factor of `k` and shrink the p-value accordingly. Majority/any/all keep independence but move the
estimand. Taking the lowest-indexed replicate keeps both and pays `k − 1` wasted draws, which under
determinism costs nothing at all.

`FIRST_REPLICATE` is still anti-conservative **with respect to clustering**, because McNemar treats
anchors as independent. That is exactly why exact McNemar is reported (the design brief names it)
and **decides nothing**.

### 4.2 The tests and intervals actually used

| quantity | method | status |
|---|---|---|
| Δ̂ | anchor-averaged paired difference | point estimate |
| 95% CI for Δ | percentile **cluster** bootstrap over mathlib files, `B = 4000` | **preregistered interval** |
| p-value for Δ | **cluster sign-flip permutation**, `B = 20000` | **preregistered test** |
| — | anchor-level bootstrap and anchor-level permutation | **negative controls**, always reported beside |
| exact McNemar | binomial tail on the discordant pairs | reported, decides nothing |
| per-arm marginal | Clopper–Pearson on cell counts | **descriptive only** — it assumes independent Bernoulli cells, which replicates and same-file anchors are not, so it is too narrow |
| per-arm marginal | cluster bootstrap on the anchor-averaged rate | the inferential interval |

The permutation p-value is `(1 + #{|T*| ≥ |T_obs|}) / (B + 1)`: the observed value is *in* the null,
which is what makes it valid at finite `B` rather than merely approximate.

Under the sharp null "the arm label changes no cell's outcome", swapping arms at an anchor negates
that anchor's paired difference, so the label permutation is a sign flip. Flipping a **whole file**
at once is invariant under arbitrary within-file dependence. Flipping anchors independently — the
literal reading of design brief §4's "arm labels permuted within anchor" — is valid only if the
anchors are independent, and §30.6 says they are not. §5 measures the size of that error.

---

## 5. The cluster unit, and the measurement that justifies it (§30.6)

**The cluster is the mathlib file**, not the theorem and not the anchor.

The file subsumes the theorem: anchors drawn from prefixes of one theorem are maximally dependent,
and theorems in one file share author, notation, imported lemma vocabulary and subject matter. The
file is the coarser and therefore safer unit. At the rebuilt bank it costs a little more than it
used to — at ICC 0.2 / baseline 0.25 the file-clustered MDE is **6.72** points against the
theorem-clustered **6.23** (330 files, `m_A = 4.02`, vs 393 theorems, `m_A = 2.94`) — half a
percentage point for a unit that cannot be wrong. That price is paid.

### 5.1 Measured type-I calibration (`simulate_type_i`, 300 trials, α = 0.05)

Simulated under a **true null** on the **rebuilt 330-file profile**, baseline 0.25, seed 20260908,
399 permutations. These are measurements, reproducible by running
`tests/experiments/test_hc_v0_6_analysis.py`:

| ICC (DEFF) | cluster permutation (preregistered) | cluster bootstrap | anchor permutation | **naive row-level bootstrap** |
|---|---|---|---|---|
| 0.0 (1.00) | 0.0333 | 0.0400 | 0.0300 | 0.0367 |
| 0.2 (1.60) | 0.0500 | 0.0500 | 0.1133 | **0.1167** |
| **0.5 (2.51)** | **0.0467** | 0.0533 | 0.1933 | **0.1867** |

Read it in three lines:

* **At ICC = 0 there is no penalty for ignoring clustering** — the naive analysis is correct when
  there is nothing to correct for, and it measures 0.0367. This is the control that shows the gap
  below is caused by clustering and not by the simulator.
* **At ICC = 0.5 the naive row-level bootstrap rejects a true null 18.7% of the time** at a nominal
  5%: a **3.7-fold** inflation, worse than the 2.75-fold seen at 75 files because `m_A` rose. The
  Monte-Carlo interval `[0.144, 0.235]` excludes 0.05 decisively. That is the empirical case for
  §30.6, and it is the reason the anchor-level statistics are computed and printed as *negative
  controls* rather than quietly omitted.
* **The preregistered cluster test now holds its level essentially exactly** (0.033 / 0.050 / 0.047
  across the three ICCs; all three Monte-Carlo intervals contain 0.05). The 0.0225 conservatism
  measured at 75 clusters was a small-cluster-count artefact of the discrete sign-flip null and has
  largely gone at 330 clusters. That is a real gain from the rebuild and it is worth stating: the
  test is no longer paying for its own exactness.

### 5.2 Measured power against the analytic approximation

Deltas chosen at the rebuilt bank's ≈80% power point; at the old bank's deltas (0.15 / 0.20) the
rebuilt bank has power ≈ 1.0 and the comparison would be vacuous.

| δ | ICC | analytic (normal) | simulated (permutation, 300 trials, seed 11) |
|---|---|---|---|
| 0.067 | 0.2 | 0.798 | 0.777 `[0.725, 0.823]` |
| 0.085 | 0.5 | 0.803 | 0.783 `[0.732, 0.829]` |

The approximation still runs high — about 2 points at seed 11, and 5–6 points at the type-I seed —
in the direction the discreteness of §5.1 predicts. The MDE table in §3.3 should therefore be read
as a **lower bound on the effect the design can see**, not an upper one: the true MDE is slightly
*larger* than the tabulated figure, which makes the §2.1 verdict on `delta_min = 0.05` if anything
stricter than stated. The tests assert both the agreement (±0.07) and the direction (the simulation
must not beat the approximation by more than 0.05), so a future change that made the approximation
optimistic would fail.

---

## 6. Multiplicity policy — FROZEN, written before any R outcome exists

**This section is frozen text.** It is written on 2026-09-09, before any Solver call has been made
against the anchored bank and therefore before any `R_A`/`R_B` contrast exists. Nothing in it may
be revised in the light of an outcome; a run that needs a different rule is a different experiment
under the next manifest version (preregistration §0).

There are **two testing problems** here and they have opposite shapes. Earlier drafts of this plan
and of the preregistration described the difference as "the gates use an uncorrected, deliberately
liberal α". That description is withdrawn: it names a symptom and invites the reading that the
gates are a corner cut for convenience. They are not. The correct statement is below, and it is an
argument, not an assertion.

### 6.A — Assay certification gates: an INTERSECTION–UNION test, no Holm

**Setup.** Certification means *every* required control gate passed. Index the gates `j = 1 … J`
and let `H_j` be the component null "**gate j is unsafe**". Then

```
global null   H = ⋃_j H_j          ("at least one required gate is unsafe")
certification C = ⋂_j R_j          (R_j = "gate j rejected H_j at its own level α_j")
```

The global null is a **union**; the decision is an **intersection of rejections**. That is the
definition of an **intersection–union test** (IUT).

**Proposition.** For any parameter `θ ∈ H` there exists at least one index `j*(θ)` with
`θ ∈ H_{j*}` — that is what membership of a union means. Certification requires `R_{j*}` among the
others, so

```
P_θ(C) ≤ P_θ(R_{j*}) ≤ α_{j*} ≤ max_j α_j.
```

Hence **the false-certification rate is at most `max_j α_j` using separate, uncorrected,
level-`α_j` component tests.** No multiplicity correction is required and the conservatism is
automatic — usually *strict*, because certification additionally demands the other `J − 1`
rejections and the bound uses none of them. This is Berger's IUT: R. L. Berger, *Multiparameter
hypothesis testing and acceptance sampling*, **Technometrics** 24 (1982) 295–300; R. L. Berger and
J. C. Hsu, *Bioequivalence trials, intersection–union tests and equivalence confidence sets*,
**Statistical Science** 11 (1996) 283–319. It is the same argument that makes TOST bioequivalence a
valid level-α procedure built from two uncorrected one-sided tests.

**Why Holm is not merely unnecessary but wrong here.** Holm controls the family-wise error rate of
a **union** decision — "reject if *any* member rejects". Certification is an **intersection**
decision. Inflating each component p-value cannot lower a false-certification rate that is already
`≤ α`; all it can do is lower the *true*-certification rate, i.e. raise the **false-block** rate.
Under the governing philosophy — **false block ≫ false certification** — that trade would be
tolerable if it bought anything, and it buys nothing. Worse: on the gates written as
*non*-rejections (§6.A.2) a Holm-inflated p-value is *less* likely to trip the block, which
**raises** the false-certification rate in the one place the IUT bound does not reach.

#### 6.A.1 Which gates the bound actually covers

Only a gate whose component null is the **unsafe** state, and which must **reject** to certify, is
an IUT component. `GateDirection.REJECT_TO_CERTIFY` in `calibration.py` is that property as a
value, and `false_certification_bound()` is `max_j α_j` over exactly those gates.

| gate | component null `H_j` | direction | α | in the IUT bound? |
|---|---|---|---|---|
| **C2** (sensitivity) | "the assay cannot detect removal of the goal text": `Δ_C2 = 0` | `REJECT_TO_CERTIFY` | 0.05 | **yes** |
| **C1** (identity) | "`Δ_C1 = 0`" — the *safe* state | `BLOCK_ON_REJECTION` | 0.10 | no |
| **C1b** (byte null) | "`Δ_C1b = 0`" — the *safe* state | `BLOCK_ON_REJECTION` | 0.10 | no |

So `false_certification_bound() = 0.05`, contributed by C2 alone.

#### 6.A.2 The part that is a limitation, stated rather than hidden

C1 and C1b **certify by failing to reject**, which is not a level-α statement about anything. What
governs them is **power**: the probability of catching a broken instrument. That is the *entire*
reason their α is set at 0.10, **above** the primary α — raising a blocking gate's α raises its
power, and power is the only knob that lowers false certification through C1. It is not liberality
and it is not convention.

Turning them into genuine IUT components would mean replacing the non-rejection with an
**equivalence test** (TOST against `δ_eq`), whose component null is "`|Δ_C1| ≥ δ_eq`" — the unsafe
state — and which must reject to certify. The design already uses TOST for C1b's *licensing*
direction (§4.2, preregistration §5); adopting it for the blocking direction is a candidate for the
next manifest version and is **not** adopted here, because `δ_eq` is still `PENDING` and a gate
cannot be frozen against an undeclared bound. Until then:

> **C1's and C1b's contribution to the false-certification rate is bounded by their power, not by
> their α, and no report may claim otherwise.**

#### 6.A.3 The measured false-certification rate

`test_false_certification_rate_is_bounded_by_alpha_under_a_global_null` simulates 400 four-arm
tables (30 files × 2 anchors, `k = 2`, seed 606) in which **the global null holds through C2**:
every arm draws from the same Bernoulli rate, so the ablation genuinely changes nothing and the
assay genuinely has no sensitivity. The real `calibrate()` and the real estimators are run;
certification is `AssayStatus.USABLE`.

| quantity | measured |
|---|---|
| certifications | **3 / 400 = 0.0075** |
| 95% Monte-Carlo interval | `[0.0015, 0.0218]` |
| IUT bound `max_j α_j` | **0.05** |
| verdicts | `INSENSITIVE` 367, `BROKEN_IDENTITY_CONTROL` 29, `USABLE` 3, `USABLE_ATTRIBUTION_BLOCKED` 1 |

`0.0075 ≤ 0.05`, with the interval entirely below the bound. The margin is not slack in the
argument, it is the strictness the proposition predicts: certification also needs C1 and C1b to
stay silent, and C2's gate additionally demands the correct **sign**, which halves a two-sided α on
its own.

The complementary measurement,
`test_a_blocking_gate_is_governed_by_power_not_by_alpha`, makes **C1** the unsafe gate instead
(`R_A`'s two replicates drawn at 0.45 and 0.15, a true `Δ_C1 = −0.30`, with C2 made genuinely
sensitive). C1 caught it in **190 / 200** trials and the assay was certified in **10 / 200
= 0.050**. That number sits near α by coincidence, **not** by guarantee — it is a power
measurement against one concrete violation size, and it is recorded here so that nobody quotes it
as a level.

### 6.B — Representation effect claims: Holm across the frozen four-member family

Entirely separate rule, entirely separate code path.

Any Δ **published as an effect** is reported with its Holm-corrected p-value across the frozen
family of design brief §9.6: `{ Δ(R_A,R_B) primary, C1, C1b, C2 }` — four members,
`estimators.PREREGISTERED_FAMILY`. This is the union-decision problem Holm is for: inspecting
several real `R` contrasts and claiming whichever rejects. `family_widening_guard` raises
`FamilyWidened` on a family that is not exactly this set, because adding a fifth member after
seeing the data inflates the FWER and dropping one deflates the survivors' corrected p-values —
both silent, so both made loud.

A control's Δ **quoted as a finding** is a finding, and takes the Holm-corrected p-value like any
other member. The same number therefore appears twice, under two labels, answering two questions:
`p_value_uncorrected` (the gate) and `p_holm` (the claim). Presenting either without its label is
not acceptable.

### 6.C — The separation, mechanically

* `calibrate()` reads **no** Holm-adjusted p-value anywhere; every gate reads
  `PairedEffect.p_value`, the raw cluster-permutation p-value.
* `holm_family()` is **never** consulted by a gate; `CalibrationVerdict.release()` takes `p_holm`
  as an explicit argument supplied by the caller, for the *report*, and uses it for nothing but
  `ReportableResult.significant`.
* `CERTIFICATION_GATES` declares each gate's direction and α, and
  `test_certification_gates_are_the_ones_calibrate_actually_uses` asserts those α values are the
  ones the gate code actually reads, so the roster cannot drift away from the gates.
* `test_holm_can_only_move_a_gate_towards_certifying` records the mechanism exactly: Holm is
  monotone (`p_holm ≥ p_raw`), so a raw C1 p-value of 0.060 trips the "assay is broken" verdict at
  α_C1 = 0.10 while its Holm value of 0.18 does not. That is the concrete failure Holm-correcting a
  gate would produce.

**Resolved:** the disagreement earlier drafts recorded between the design brief (four-member
family) and preregistration v0.1 (one member) is not a disagreement about the gates at all. The
brief's four-member family is layer 6.B and is adopted in full; the gates are layer 6.A and were
never a Holm question. `PREREGISTERED_FAMILY` stays at four.

---

## 7. Stopping rule (§30.3)

Fixed `n`. No interim looks. No extension after seeing the result. `n`, `n_clusters` and `k` are
frozen before the first Solver call against the bank; the bank is not extended, topped up, re-drawn
or filtered afterwards; anchors are never selected, dropped or re-weighted on anything downstream of
Solver performance. A run that lands in O6 or O7 gets a new manifest version or abandonment, never a
continuation. This is preregistration §7 verbatim and this plan adds nothing to it.

One consequence worth stating because it will be tempting: §3.3 shows the bank is between 1.1×
and 2.8× short of what a 5-point `delta_min` needs at a baseline of 0.25. **That is a fact to
publish beside the result, and a decision to take before the run (§2.1), not a reason to grow the
bank after seeing Δ.** The bank was rebuilt on 2026-09-08, before any Solver call against it; a
rebuild after exposure would be a different experiment.

---

## 8. Allowed outcomes (§30.3) — and the gate that enforces them

`Outcome` is the preregistration §8 ladder as an enum, carrying its §43 sentinel. `calibrate()`
evaluates the controls in the ladder's order — and the order is not negotiable, because O1
forecloses everything and O2 forecloses O3:

```
C1 significant?            -> BROKEN_IDENTITY_CONTROL   (O1, INSTRUMENT_INVALID)
arm-dependent missingness? -> ARM_DEPENDENT_MISSINGNESS (O7, INSTRUMENT_INVALID)
< 30 contributing clusters?-> INSUFFICIENT_CLUSTERS     (O6, LANDSCAPE_NOT_ESTABLISHED)
C2 weak or wrong-signed?   -> INSENSITIVE               (O2 for any null)
C1b significant?           -> USABLE_ATTRIBUTION_BLOCKED
otherwise                  -> USABLE
```

### 8.1 The hard rule, made mechanical

Design brief §4: *"If C1 is 'significant' under the preregistered test, the assay is broken and no
other comparison may be reported."*

A rule of that shape written only in a docstring is advice, and advice is ignorable. Here it is a
**typed outcome with a gate**. The primary Δ is not an attribute anyone can read off a verdict; it
is the return value of `CalibrationVerdict.release()`, and `release()` raises `AssayBroken` when C1
fired, when missingness was arm-dependent, or when too few clusters contributed — including when the
primary comparison alone falls below the floor, which is re-checked at release rather than assumed
from the controls. The package offers no other route from a `PairedEffect` to a `ReportableResult`.
Python cannot make the dataclass unconstructible and that is not the claim; the claim is that the
gate cannot be *forgotten*, only bypassed on purpose in a line of code that says so. `ReportableResult` additionally
takes the `MinimumDetectableEffect` as a **required** argument, so design brief §9.5 — *"a null
without an MDE is not a result"* — cannot be violated by omission: `headline()` always prints it.

`MIN_CLUSTERS = 30` is the floor below which cluster-robust inference is not trustworthy at any α;
it is the conventional guidance for cluster-robust methods and the rebuilt bank clears it 11×
(330 files). It is stated here so that it is preregistered rather than chosen after counting.

### 8.2 The §9.4 reading rule, as behaviour

Design brief §9.4: *"`Δ(R_A, R_A′) ≈ 0` and `Δ(R_A, R_B) ≠ 0` → the effect is attributable to
**structure**, not to the mere fact that bytes changed; both non-zero → the model is sensitive to
byte perturbation as such, and `R_B`'s effect cannot be attributed to its structure."*

`Attribution` is that sentence as an enum and `ReportableResult.may_claim_structure` is that sentence
as a boolean:

| C2 | C1b | primary | `Attribution` | `may_claim_structure` |
|---|---|---|---|---|
| passed | null | significant | `STRUCTURE` | **True** |
| passed | **significant** | significant | `BYTE_PERTURBATION` | False |
| passed | either | null | `NO_EFFECT_TO_ATTRIBUTE` | False |
| **failed** | either | either | `UNDETERMINED` | False |

A significant C1b does **not** break the assay — the brief calls it "a finding about the assay"
that "would block a representation claim", and that is what the code does: status
`USABLE_ATTRIBUTION_BLOCKED`, the numbers still reportable, the structural claim refused, and the
reason attached to the released result as a caveat in words.

---

## 9. Evaluation-universe hash (§30.3)

`CellTable.anchor_universe_hash` is the stable hash of the anchored bank actually played — each
anchor's id, cluster, theorem and re-elaboration key, and nothing about the run. Two runs of the
same bank share it; a bank with one anchor added or removed does not. `CellTable.content_hash`
covers every raw cell, so a single changed outcome changes it.

These are the analysis-side components. The full §6.27 thirteen-component universe hash is the
preregistration's §9 slot and is computed at freeze time, not here.

The bank actually to be played is the rebuild of 2026-09-08, content hash
`f13ffee5aae464d6f4717c4f85cd6ec1091eb19d9ca0ab5cd716094a9b583b40` — 1127 anchors, 393 theorems,
330 files, re-derivation 1127/1127. `CellTable.anchor_universe_hash` is computed from the cells
actually played and must be reported beside it; a mismatch means the run did not play the bank the
manifest names.

---

## 10. What a null Δ would license, and what it would not

This is the part that is easiest to get wrong in the write-up, so it is written before the number
exists.

**A null Δ(R_A, R_B) with C1 at zero, C2 strong, and the CI inside the equivalence region would
license, and only license:**

> At 1127 anchored mathlib goal states drawn from 330 files, under one frozen Solver
> (`qwen3.6:27b-mlx`, frozen decoding), one prompt template, and a one-action-deep
> `KERNEL_ACCEPTED_STATE_CHANGE` endpoint, re-laying-out the baseline rendering into `R_B` did not
> change the event rate by as much as the MDE of this design (**5–9 points**, depending on the
> realised baseline and ICC — recomputed at the realised values, never quoted from this plan).
> Effects smaller than that are **not addressed**.

**It would not license any of:**

* *"Representation does not matter."* One `R_ONLY` gene, one model, one endpoint, one bank. §6.27 is
  explicit that fitness outside this evaluation universe is `UNKNOWN` until replicated.
* *"There is no effect."* Absence of evidence at a 5–9 point resolution is not evidence of absence
  at 2 points — nor, at any baseline of 0.225 or above, at 5 (§2.1). This is exactly why
  `ReportableResult` refuses to exist without an MDE attached.
* *Anything about horizons.* The endpoint is one action deep by construction, and HC-V0.5 already
  established that a per-step edge does not imply a horizon effect.
* *Anything about reasoning or capability.* mathlib4 is `HISTORICALLY_EXPOSED` and exposure is
  transitive; nothing in this arena separates a solved goal from a recalled one. The defensible
  phrasing stays **execution under kernel verification**.
* *Any `RSTAR`/`LSTAR` claim, any searchable-landscape claim, any promotion above `VALID_CANDIDATE`,
  any use of Δ as a fitness objective.* Preregistration §8, unconditionally.

**And two further limits specific to what was built here:**

* **If the Solver is deterministic, C1 is a tautology.** It will read exactly zero and it will prove
  only that the Solver is a function of its prompt. The null control's evidential weight rests
  entirely on C1b. If C1b is *also* degenerate — because the whitespace perturbation happens not to
  change the tokenization — then the design has no informative null control at all, and that must be
  reported as a limitation rather than as three passing controls.
* **`ρ_D` is assumed, not measured, and so is the baseline.** Every MDE in §3.3 is conditional on
  an ICC *and* a baseline event rate the design has not yet observed. After the run, both must be
  estimated from the realised data and the MDE recomputed at those values before any null is
  published. A null reported against an ICC = 0 MDE when the realised ICC is 0.5 would understate
  the study's blind spot by about 3 percentage points at baseline 0.25; reporting the baseline-0.10
  MDE when the realised baseline is 0.40 would understate it by a further 3.

---

## 11. Open slots this plan does not close

| slot | why it stays open | who closes it |
|---|---|---|
| `delta_min`, `δ_eq` | must be justified and set before C2's floor is measured (prereg §2). §2.1 shows the declared 0.05 is unreachable at any baseline ≥ 0.225 and, in the plausible ICC band, at any baseline above ~0.10 — the owner picks one of the three options there | Experimentalist / Owner |
| baseline `p_event(R_A)` | a preflight is measuring it; every MDE in §3.3 is conditional on it, and the endpoint change of §1 moves it down | the preflight work item |
| C1/C1b as TOST components | would put the blocking gates inside the IUT bound (§6.A.2); blocked on `δ_eq` | next manifest version |
| `k` | waits on the confirmed noise measurement; `k = 1` if determinism is confirmed | Experimentalist |
| realised `ρ_D` | not measurable before the run | computed after the run, before publication |
| ~~Holm family size~~ | **closed**: §6 resolves it — the brief's four-member family is the effect-claim rule, the gates were never a Holm question | — |
| `R_A_PRIME` renderer | the whitespace-perturbing renderer does not yet exist in `arena/trajectory/representation.py` (`ARMS` holds three) | the representation work item |

The last row matters operationally: `Arm.R_A_PRIME` is declared in the schema with its own
`renderer_id`, and the analysis is ready for it, but until that renderer ships and passes the
bank-wide bijection check of design brief §2, C1b cannot be run and the four-arm design is a plan
rather than an experiment.
