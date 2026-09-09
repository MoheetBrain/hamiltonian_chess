# HC-V0.6 — preregistration

**Manifest:** `hc-v0.6-anchored-delta`
**Manifest version:** `v0.2-DRAFT` — **NOT YET FROZEN**
**Shape:** manual §30.3 (`Confirmatory manifests SHALL specify`)
**Companion:** `docs/HC_V0_6_ANCHORED_DELTA_SPEC.md` (the experiment), `docs/HC_V0_6_DESIGN_BRIEF.md`
(the design), `docs/HC_V0_6_MANUAL_COMPLIANCE.md` (the audit)

---

## 0. Status, freezing, and the rule that governs this file

This manifest is **DRAFT** while any `PENDING` slot below is open. It becomes **FROZEN** when every
`PENDING` slot is filled by the named work item, the freeze is recorded with a timestamp and a
content hash, and the `evaluation_universe_hash` is written.

**Scientific exposure begins at the first Solver call against the anchored bank.** From that
moment, manual §3.2 governs:

> Once an experiment crosses its declared scientific exposure boundary: its frozen manifest governs
> that experiment; the owner MAY abort it; a replacement requires a new experiment/manifest version;
> thresholds, endpoints, samples, promotion rules, or invalidation rules **MUST NOT be edited while
> continuing to call it the same confirmatory experiment.**

And §44.4:

> Experiment-manifest change after scientific exposure: **Forbidden** unless the experiment is
> marked invalid and restarted under a new manifest version.

**Stated plainly: once frozen and exposed, this document may be aborted but never edited.** There
is no amendment path, no clarification path, and no "we always meant". A run that needs a different
threshold, a different `n`, a different endpoint or a different collapsing rule is a *different
experiment*, is marked `INSTRUMENT_INVALID` or aborted, and is restarted under the **next**
manifest version after whichever one was exposed. Corrections are additive only (§3.3).

**Pre-freeze revision is not the same thing.** This file is at `v0.2-DRAFT` because it was revised
on 2026-09-08 to carry four arms, the realised anchored bank and the MDE rule. **No Solver call has
been made against the bank**, so no exposure boundary has been crossed and the revision is
permitted by §3.2 in full. Once frozen and exposed, the same edit would be forbidden.

**Filling a `PENDING` slot before freezing is a completion. Changing a filled slot after exposure
is a violation.** Each `PENDING` names the work item that fills it and the role that decides, so
that the difference is visible on the page rather than reconstructible from git.

**Epistemic typing (§1, §37).** `EXPERIMENT_DECISION` = resolvable by this frozen manifest.
`ENGINEERING_DECISION` = resolvable by engineering judgment within declared constraints.
`OWNER_DECISION_REQUIRED` = cannot be resolved by an implementation agent.

**Deciding roles (§16).** *Experimentalist* — §16.5 owns instrument validity, controls, power,
leakage audits and preregistration checks; it decides every statistical slot below. *Owner* — §45,
decides scientific boundaries and claims. *Architect* — §16.1 MUST NOT modify evaluation thresholds
after results and MUST NOT approve its own semantic gate; it decides nothing in this file.

### 0.1 §30.3 conformance — every required field, and where it is

§30.3 lists nine fields a confirmatory manifest SHALL specify. None may be absent, and a `PENDING`
is an *identified hole with a named filler*, not an absence.

| §30.3 field | this manifest | status |
|---|---|---|
| primary endpoint | §1 | **filled** |
| minimum practical effect `delta_min` | §2 | `PENDING: P1` |
| sample size / precision target | §3 | `n = 223`, `n_clusters = 75` **filled from the realised bank**; `k`, precision target `PENDING: P5` |
| paired method | §4 | collapsing rule `PENDING: P6`; estimator, cluster bootstrap and permutation **filled** |
| multiplicity policy | §5 | **filled** (α values `PENDING: P8`) |
| cluster / grouping unit | §6 | **filled** — theorem file, 75 clusters |
| stopping rule | §7 | **filled** |
| allowed outcomes | §8 | **filled** — O1–O9, exhaustive, each with licence and prohibition |
| evaluation-universe hash | §9 | `PENDING: P14`, computed at freeze |

### 0.2 The arms this manifest governs

Four arms, per design brief §9.6 and spec §2.12: `R_A`, `R_A_PRIME` (whitespace-perturbed
baseline), `R_B`, `R_ABLATED`. Four comparisons: **primary** (`R_B` vs `R_A`), **C1b** (`R_A_PRIME`
vs `R_A`, the byte-perturbation null), **C2** (`R_ABLATED` vs `R_A`, the sensitivity floor), and
**C1** (the noise floor, computed by splitting `R_A`'s own replicates — not an arm).

`R_A_PRIME` does **not** mean "the baseline drawn a second time". That reading was current in code
for part of 2026-09-08; design brief §9.6 retired it and the code now matches (§11, B11), which is
re-verified at freeze rather than assumed.

---

## 1. Primary endpoint

`p_accept(R)` — the probability that the Lean **elaborator** accepts the Solver's single proposed
tactic at an anchored state, under rendering `R`.

**Estimand:** `Δ(R_A, R_B) = p_accept(R_B) − p_accept(R_A)`, paired within anchor, clustered by
theorem file.

Binary per cell. Elaborator-adjudicated, **not** kernel-adjudicated — the axiom check applies only
to closure (spec §7.1). Cell disposition (numerator / denominator / VOID) is governed by the table
in spec §7.3, which is part of this manifest by reference and is frozen with it.

**Direction:** two-sided. No directional hypothesis is preregistered, because §8.1 of the spec
shows familiarity predicts a negative sign for reasons unrelated to representation quality.

**The same endpoint, estimator and pairing are used for C1b, C2 and C1.** `Δ(R_A, R_A_PRIME)`,
`Δ(R_A, R_ABLATED)` and the within-`R_A` split are all `p_accept` differences paired within anchor
and clustered by file. A control computed under a different analysis from the headline is not a
control for the headline.

**Secondary endpoints, all reported per arm:** `p_close` (axiom-checked, spec §7.2), parse-failure
rate, prompt tokens, completion tokens, latency, tactic-head distribution, VOID rate by type, and
arm-order position. None of these is a hypothesis; all are reported for every arm whatever the
primary result, and the token counts are mandatory because prompt length is the half of §26.2's
"compute regime" this design does not equalise (spec §2.8, §8.3).

---

## 2. Minimum practical effect `delta_min`

`PENDING`: the power analysis work item — `docs/HC_V0_6_ANALYSIS_PLAN.md` §2, informed by
`docs/HC_V0_6_RUNTIME_NOISE.md`.
**Decided by:** Experimentalist (§16.5). **Type:** `EXPERIMENT_DECISION`.

**Constraints binding whoever fills it** (these are frozen now, and filling `delta_min` may not
violate them):

1. `delta_min` MUST be justified, not conventional. Design brief §6 says *"justified, not
   conventional"*; a value chosen because it is round, or because it is what the study can detect,
   is not justified.
2. `delta_min` MUST be **representable** by the estimator at the planned `n_clusters`
   (`docs/HAMILTONIAN_CHESS_META_GOAL.md` §7: *"A gate must be a value the estimator can actually
   take at the planned n"*). A threshold finer than the estimator's granularity is not a threshold.
3. `delta_min` MUST be set **before** the C2 sensitivity floor is measured, so that the floor can
   be compared against it rather than becoming it. Setting `delta_min` equal to whatever C2 turns
   out to detect is circular and is forbidden.
4. `delta_min` MUST be stated on the `p_accept` scale (probability difference), matching the
   estimand in §1.

**Equivalence region.** `PENDING: same work item.` A two-one-sided-test region `[−δ_eq, +δ_eq]`
MUST be declared alongside `delta_min`, because `docs/HAMILTONIAN_CHESS_META_MDP.md` §4 requires
*"an equivalence region so that 'no significant difference' can be distinguished from 'no
difference'"*. Without it, outcome O3 (informative null) in spec §9.3 is not reachable and every
null collapses into O2.

### 2.1 The MDE reporting rule — frozen now, not derived later

Design brief §9.5, binding on this manifest and on every document that reports its numbers:

> **A null without a minimum detectable effect is not a result.** Every Δ reported as null carries
> the MDE achieved at the **realised** `n`, `n_clusters`, `k` and non-VOID cell count — never the
> planned ones — stated as *"detectable ≥ X points at α = …, power = …; observed Δ = …, CI […]."*

Frozen consequences (spec §9.10):

1. **C2 is not the MDE.** C2 answers *"is the pipeline causally connected at all?"*. The MDE answers
   *"how small an effect could this run have seen?"*. Substituting one for the other is the most
   likely route to a misleading null here and is forbidden.
2. The MDE is computed **on clusters** (75 files), under the frozen collapsing rule — never on 223
   anchors and never on `n × k` cells.
3. The rule applies to **C1b and C2** as well as to the primary. A null C1b whose MDE exceeds
   `delta_min` licenses nothing (spec §3.4).
4. If the realised MDE exceeds `delta_min`, the run is **O2 or O6** regardless of the point estimate.
   `power` for this statement is `PENDING: P8`.

---

## 3. Sample size / precision target

| slot | value |
|---|---|
| `n` anchored states | **223** — realised. `artifacts/trajectory/hc_v0_6_anchor_bank.json`, content hash `9fa6b6da12e237a3d8b682aad4346f1416bbe14689298a3cfb8bac805e4605dc` |
| distinct theorems | **78** |
| `n_clusters` (theorem files) | **75** — realised. **This is the effective sample size** (spec §8.6); the power analysis MUST be run on it, not on `n` |
| anchors per theorem | 3 (×69), 2 (×7), 1 (×2) — realised; drives the design effect |
| `k` replicates per (anchor, arm) | `PENDING: docs/HC_V0_6_RUNTIME_NOISE.md jointly with the power analysis.` If the runtime is call-for-call deterministic, `k = 1` (see §4.3) |
| arms | **4** (`R_A`, `R_A_PRIME`, `R_B`, `R_ABLATED`) |
| total Solver calls | `= 223 × k × 4` (= 892 at `k = 1`), reported as a budget before the run |
| precision target | `PENDING: P1/P8 — the power analysis, expressed as the MDE of §2.1 at 75 clusters` |

**Decided by:** Experimentalist. **Type:** `EXPERIMENT_DECISION`.

**The bank is realised; `delta_min` is not — and the power analysis has now bounded what the bank
can see.** `docs/HC_V0_6_ANALYSIS_PLAN.md` §3.3, at α = 0.05 two-sided and power 0.80, baseline
`p_accept(R_A) ≈ 0.25` (HC-V0.5's rate), 223 anchors in 75 files with `m_A = 3.16`:

| MDE at the realised bank | ICC = 0 | ICC = 0.2 | ICC = 0.5 |
|---|---|---|---|
| percentage points | 12.2 | **14.7** | 17.8 |

**Read that honestly: this study can see a 12–18 point swing in acceptance and nothing smaller.**
Detecting 10 points at a plausible ICC needs roughly **twice** the bank that exists (≈ 467 anchors
in ≈ 158 files at ICC 0.2); detecting 5 points needs about eight times it. `ρ_D` is a design
parameter here, not a measurement — the V7 audit measured +0.51 for a paired difference in a
comparable twin design — and the *reported* MDE must be recomputed at the realised ICC after the
run (§2.1).

Two consequences bind whoever fills `delta_min` (P1):

1. A `delta_min` below ≈ 15 points would be a gate the estimator cannot reach at this bank, which
   `docs/HAMILTONIAN_CHESS_META_GOAL.md` §7 forbids: *"A gate must be a value the estimator can
   actually take at the planned n."*
2. A `delta_min` set *at* the MDE would be circular in the same way constraint 3 forbids for C2.
   If the scientifically defensible `delta_min` is smaller than the MDE, the honest responses are to
   **widen the bank before freezing** — permitted, since no assay data exists — or to accept
   outcome **O6** in advance. Widening after the first Solver call is forbidden (§7).

§30.2's four inputs are therefore now *partly* discharged: minimum practical effect is still open;
power/precision and dependence are computed; multiplicity is settled in §5.

**Constraints binding now:**

* §30.2: *"Tiny samples are smoke only. Small `n` such as 24 may calibrate engineering. Scientific
  sample size is justified by minimum practical effect, power/precision, dependence, and
  multiplicity."* All four inputs MUST be shown, not asserted.
* §18.4: sample counts SHALL be chosen after task variance, episode cost, minimum practical effect,
  and power/precision are measured. HC-V0.6 measures them first; that ordering is the reason the
  noise study is a gate and not a preliminary.
* `docs/HAMILTONIAN_CHESS_META_GOAL.md` §7: *"Sample size is designed, never inherited."* The
  HC-V0.5 smoke's 30 tasks are not an input to this number.
* The power analysis MUST account for the **design effect** from clustering and from `k`
  replicates. Powering on `n × k` cells as if independent is the granularity substitution named in
  spec §4 and forbidden here explicitly.

---

## 4. Paired method

### 4.1 The replicate-collapsing rule — frozen before any data

`PENDING`: `docs/HC_V0_6_RUNTIME_NOISE.md`.
**Decided by:** Experimentalist. **Type:** `EXPERIMENT_DECISION`.

With `k > 1` cells per `(anchor, arm)`, "paired by anchor" and "exact McNemar on discordant pairs"
are not simultaneously well-defined: McNemar needs one binary outcome per side per pair; the data
are `k` binary cells per side (spec §8.9). Exactly one of the following is chosen, **before any
assay data exists**, and the choice is justified by the measured noise structure:

* **(a) proportion pairing** — collapse to `p̂(anchor, arm) = (accepts)/(non-VOID cells)`; the
  paired difference is a real number per anchor; McNemar does not apply and the primary test is the
  paired cluster bootstrap alone;
* **(b) per-replicate pairing** — pair cell `j` of `R_A` with cell `j` of `R_B` at each anchor, with
  the variance estimated by the cluster bootstrap over *files* (never over cells), so the
  within-anchor dependence is absorbed by the cluster unit;
* **(c) mixed model** — a binomial GLMM with random intercepts for file and anchor, the arm as a
  fixed effect, and the estimand read as a marginal risk difference.

If (a) is chosen, "exact McNemar" is dropped from this manifest rather than applied to a statistic
it does not fit. **Choosing after seeing the data is forbidden** and is the exact failure §30.3's
stopping rule exists to prevent.

**The `k = 1` branch, preregistered so it is not invented later.** If the noise study returns a
call-for-call reproducible configuration (spec §8.4 records the provisional evidence: 120/120 and
30/30 byte-identical), then `k = 1`, there is nothing to collapse, and this whole section
degenerates: (b) becomes a plain paired comparison of one cell per side per anchor, exact McNemar
on discordant anchor pairs is well-defined and is used, and the paired cluster bootstrap over the
75 files supplies the interval. In that branch the **only** stochastic element left in the assay is
the anchor sample, so the cluster bootstrap is not one uncertainty source among several — it is the
whole of the uncertainty, and `n_clusters = 75` is the only lever on precision. That must be stated
in the result, because a reader who assumes replicate noise is being absorbed would misread the
interval.

### 4.2 Tests and intervals

| comparison | contrast | test | interval |
|---|---|---|---|
| **primary** | `R_B` vs `R_A` | per §4.1 | **paired cluster bootstrap over theorem files**, `PENDING: B resamples, frozen with §4.1` |
| **C1b** | `R_A_PRIME` vs `R_A` | the **identical** estimator, cluster unit and collapsing rule | same |
| **C2** | `R_ABLATED` vs `R_A` | same estimator, cluster unit and collapsing rule | same |
| **C1** | `R_A` replicates split in half — **not an arm** | same, but see the `k = 1` degeneracy in §4.3 | same |
| C3 | arm labels permuted **within anchor**, resampling clusters; `PENDING: number of permutations, frozen with §4.1` | descriptive | empirical null distribution for `Δ` |

**C1b is analysed in both directions, and the directions are not symmetric.** Its *blocking* use —
"is the model sensitive to a null byte change?" — is a significance test, evaluated liberally
(§5). Its *licensing* use — "is the byte-change effect negligible, so the primary can be attributed
to structure?" — is a **TOST against `[−δ_eq, +δ_eq]`**, not a failure to reject. Reading a
non-significant C1b as "no byte sensitivity" is the absence-of-evidence error the equivalence
region exists to prevent, and it is forbidden here explicitly.

The cluster bootstrap resamples **files with replacement**, carrying all their anchors and all their
cells. Resampling anchors or cells would understate the variance by exactly the dependence §30.6
names.

### 4.3 C1's construction and its known asymmetry

C1 is built inside `R_A`: with `k ≥ 2`, `R_A`'s replicates are split into two halves and compared
by the identical estimator, cluster unit and test as the headline (design brief §9.2).

**One correction to the brief's wording, recorded here rather than silently.** The brief calls this
*"the identical estimator"*. The estimator, cluster unit, collapsing rule and test are identical;
the **number of replicates per side is not** — C1 uses `k/2` per side where the headline uses `k`.
C1's variance is therefore roughly twice the headline's, so C1 **over-states** the noise floor. That
is the conservative direction — it makes the assay easier to declare broken — and it is why the
construction is acceptable. It MUST be reported as an upper bound on the noise floor, not as the
noise floor.

**If the runtime-noise study returns `k = 1`** — a call-for-call reproducible configuration — C1
cannot be built by splitting replicates, and the correct response is **not** to add cells to
manufacture a test. Under call-for-call determinism, two draws of `R_A` at one anchor are the same
prompt to the same deterministic function: `Δ(R_A, R_A) = 0` **identically, by construction**, and a
"test" of it would measure nothing. In that branch (design brief §9.6):

* C1 is **reported as a construction plus its licence** — the determinism measurement from
  `docs/HC_V0_6_RUNTIME_NOISE.md`, with its coverage stated (how many prompts, how many calls,
  which lengths, whether interleaved) — and never as "C1 passed", which would imply a test that was
  not run;
* outcome **O1 becomes unreachable**, and the manifest says so in advance rather than discovering it;
* the determinism measurement itself becomes a **blocking precondition of the same kind as C1**: if
  it is weak or narrow, the noise floor is unestablished and the design is back to needing `k ≥ 2`.

Both branches are preregistered here so that neither is invented after the fact.

---

## 5. Multiplicity policy

The policy has **two layers**, and conflating them is the error this section exists to prevent.

**Layer 1 — the Holm family, for effect claims.** The four comparisons of design brief §9.6:
`{ primary, C1b, C2, C1 }`. Any Δ *published as an effect* is reported with its Holm-corrected
p-value across that family. Widening the family (a second renderer, a second endpoint) is visibly a
new manifest version, never a silent addition.

**Layer 2 — the gates, which read the UNCORRECTED p-value.** Every gate that can *block* a claim —
C1 (is the assay broken?), C1b in its blocking direction (is the model byte-sensitive?), C2 (is the
assay sensitive at all?) — is evaluated against the **raw cluster-permutation p-value**, uncorrected,
with `α_C1` and `α_C1b` set **at or above** the primary α.

Both numbers are reported for every comparison, explicitly labelled `p_value_uncorrected` and
`p_holm`. Two p-values for one comparison is acceptable only because they answer two different
questions; presenting either without its label is not.

**Why layer 2 exists, on a specific and non-negotiable ground:**

> **C1 is a safety gate, not a hypothesis. Holm-correcting it moves the threshold in the direction
> that protects the headline result from its own instrument.**

Under Holm, C1 needs a *smaller* p-value to be declared significant, i.e. to trip the
"assay is broken" verdict of spec §9.1. Multiplicity control exists to suppress false *positives*
about the science; applying it to an instrument-validity check suppresses true *negatives* about
the instrument. That is backwards, and it is precisely the shape of failure §29 (fail closed) and
§43 (*"The system MUST prefer explicit negative/blocked states over optimistic prose"*) legislate
against.

**The same argument extends to C1b in its blocking direction.** C1b looks like a hypothesis — it has
an arm, an estimator and a Δ — but that direction of it decides which sentences may be written about
the primary, never what the primary is. Holm-correcting it would mean `Δ(R_A, R_A′)` needs a
*smaller* p-value to be declared non-null, i.e. to trip spec §9.9's block on attributing the primary
effect to structure. That moves a gate in the protective direction. So C1b's blocking direction reads
the uncorrected p-value, and its licensing direction is a TOST against `δ_eq` (§4.2), where
multiplicity is not the relevant risk.

**This two-layer reading reconciles the manifest with design brief §9.6 rather than departing from
it.** The brief's four-member family is layer 1 and is adopted in full; layer 2 is about the gates,
which the brief does not legislate. `arena/experiments/hc_v0_6/calibration.py` implements exactly
this split and says so in its own words — *"these gates read the raw permutation p-value, and C1's α
is set above the primary α on purpose"*. An earlier draft of this manifest (`v0.1-DRAFT`) rejected
the brief's family outright; that was stronger than necessary, and the two-layer form is what is
frozen. **The Experimentalist (§16.5) owns it and it is signed off before freeze** (P16).

Therefore:

| test | used as | α | correction | direction of conservatism |
|---|---|---|---|---|
| **primary** `Δ(R_A, R_B)` | effect claim | `PENDING: frozen with §2` (default 0.05, two-sided) | **Holm over the four-member family** | conservative about claiming an effect — correct |
| **C1** (assay broken?) | gate | **uncorrected, deliberately liberal**: `PENDING: α_C1, frozen with §2; MUST be ≥ the primary α` | **none** | conservative about *trusting the instrument* — correct |
| **C1b** (byte-sensitive?) | gate, blocking direction | **uncorrected, liberal**: `PENDING: α_C1b, frozen with §2; MUST be ≥ the primary α` | **none** | conservative about *attributing the effect to structure* — correct |
| **C1b** (bytes inert?) | licensing direction | TOST at `δ_eq` | n/a | an equivalence claim needs an equivalence test, not a failure to reject |
| **C2** (sensitivity floor) | gate | `PENDING: frozen with §2` | **none** | failing to establish sensitivity already blocks the null reading (spec §9.2), so no correction is needed to make it safe |
| C1, C1b, C2 **as reported Δs** | effect claims, if quoted as such | primary α | **Holm over the four-member family** | correct — a control's Δ quoted as a finding is a finding |
| C3 (permutation null) | descriptive | — | n/a | reported as a distribution, not a test |

C2's threshold is uncorrected but its *failure* is what matters, and failure is the conservative
outcome — a weak C2 forces outcome O2 (uninformative null), never a stronger claim. C1's and C1b's
uncorrected, liberal α are the only places in this manifest where a threshold is deliberately set
to make a negative verdict easier to reach.

---

## 6. Cluster / grouping unit

**Theorem file** (the mathlib `.lean` file the theorem is defined in).

§30.6: *"Steps from the same theorem/module/problem family are not independent. Split/group and
estimate uncertainty accordingly."* §18.2: *"Where possible, split by theorem/module/repository/problem
family, not random steps from the same proof family."*

The file subsumes the theorem: anchors drawn from prefixes of one theorem are maximally dependent,
theorems in one file share author, notation, imported lemma vocabulary and subject matter. The file
is the coarser and therefore the safer unit, and it is the unit for **every** interval, bootstrap
and permutation in §4.

**Realised: 75 clusters** carrying 223 anchors from 78 theorems. The bank is close to one theorem
per file, so file-level and theorem-level clustering will be numerically similar *here*; the file
remains the declared unit because it is the coarser one and because the rule must not depend on a
property this particular bank happens to have.

**Reported alongside every interval:** `n_clusters`, the anchors-per-cluster distribution, and the
number of clusters contributing at least one discordant pair. An interval computed over fewer than
`PENDING: minimum n_clusters, frozen with §3` clusters triggers outcome O6 (underpowered) and no
effect is reported. Note that 75 is the number *before* VOID cells (spec §7.3) are removed; a
cluster whose every anchor VOIDs contributes nothing, so the reported `n_clusters` is the realised
one, not 75 by default.

---

## 7. Stopping rule

**Fixed `n`. No interim looks. No extension after seeing the result.**

* `n`, `n_clusters` and `k` are frozen in §3 before the first Solver call against the bank.
* There is **no interim analysis**. Nobody looks at `Δ`, at C1, or at C2 until the last cell is
  recorded. Monitoring is limited to operational health: VOID rate, wall-clock, cost — quantities
  that appear in the disposition table and never in the estimand.
* **The bank is not extended, topped up, re-drawn, or filtered after the result.** Design brief §7:
  *"No design choice may be made after seeing an outcome."* §41.5: *"Stop at the preregistered
  search/evaluation budget. Do not continue until a custom language wins."*
* If the run lands in outcome O6 (insufficient clusters) or O7 (arm-dependent missingness), the
  response is a **new manifest version** or abandonment, never a continuation of this one.
* Anchors are never selected, dropped or re-weighted on anything downstream of Solver performance —
  before, during, or after the run (design brief §7).
* A VOID cell is re-run **once**, under the identical condition, per the disposition table (spec
  §7.3). That is a fixed operational rule declared in advance, not an interim look, and it is
  applied identically to every arm.

### 7.1 No subgroup analyses — and the specific one that will be tempting

**No subgroup, stratified or interaction analysis of `Δ` is preregistered, and none may be reported
as a result.** The bank carries several fields that invite one, and the temptation is foreseeable
enough to name in advance:

| tempting split | why it will be reached for | why it is forbidden here |
|---|---|---|
| `depth_class` = `INITIAL` (78) vs `MID_PROOF` (145) | it looks like "does representation matter more later in a proof?" | it is not a horizon comparison. `depth_class` is a **sampling proxy** derived from `prefix_length`; the bank's own note says so; spec §4 says selecting anchors deeper into a recorded proof *"makes it a different sample of `EpisodeLength = 1` states"*, not a longer horizon. Reporting an `INITIAL`/`MID_PROOF` interaction as evidence about depth is granularity substitution **and** a §23 horizon claim, both forbidden |
| `n_goals` = 1 (201) vs ≥2 (22) | it looks like "does layout matter more with more goals?" | 22 anchors across an unknown number of clusters; the design was never powered for it |
| `observed_trace_length` bins | same shape as the first row | §17.6 forbids treating a recorded proof's length as a required reasoning length |
| by mathlib subject area | it looks like a generalisation check | the cluster count per area is tiny; this is the winner's-curse surface of §30.4 in miniature |

These quantities are **reported descriptively** — the anchor composition must be visible so a reader
can judge what the sample is — and are **never** used to compute a Δ, a p-value, an interval or a
claim. If a later experiment wants any of them, it is a new manifest with its own power analysis,
which is exactly what §30.5's discovery/evaluation separation requires.

---

## 8. Allowed outcomes

The exhaustive list, with what each licenses and forbids, is `docs/HC_V0_6_ANCHORED_DELTA_SPEC.md`
§9, and is part of this manifest by reference:

| id | outcome | sentinel (§43) |
|---|---|---|
| **O1** | the assay is broken (C1 significant) | `INSTRUMENT_INVALID` |
| **O2** | null with insufficient sensitivity (C2 weak) | `LANDSCAPE_NOT_ESTABLISHED` |
| **O3** | informative null (C1 at zero, C2 strong, Δ inside the equivalence region) | `NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND`, scoped to this gene / model / endpoint |
| **O4** | Δ favours `R_B` beyond `delta_min` | none; developmental reading, `VALID_CANDIDATE` tier only |
| **O5** | Δ favours `R_A` beyond `delta_min` | none; report the §8.1 familiarity non-identification |
| **O6** | underpowered / insufficient clusters | `LANDSCAPE_NOT_ESTABLISHED` |
| **O7** | arm-dependent missingness | `INSTRUMENT_INVALID` |
| **O8** | environment blocked | `META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD` or `META_GAME_BLOCKED_BY_SEMANTIC_SUBSTRATE` |
| **O9** | the Solver is sensitive to byte perturbation as such (C1b non-null) | `REPRESENTATION_EFFECT_MODEL_SPECIFIC` + explicit non-identification |

The outcomes are evaluated **in order**: O1 (noise floor) forecloses everything; O2 (sensitivity
floor) forecloses O3; O9 (byte sensitivity) forecloses the structural attribution in O4/O5 without
foreclosing the Δ itself. O6, O7 and O8 are operational exits and may fire at any point.

**§2.1's MDE rule binds every outcome above that contains a null**, without exception.

**Forbidden in every outcome, without exception:** any `RSTAR` or `LSTAR` claim; any horizon claim;
any capability or reasoning claim; any `FITNESS_CANDIDATE` or higher tier; any claim that the
effect is intrinsic to the representation rather than to familiarity or tokenization; any use of
`Δ` as a fitness objective or global language reward; any promotion or archive update; any
generation, fine-tuning, or RL Architect; any subgroup or interaction analysis of `Δ` (§7.1); and
any presentation of a §25 **Gate 1** number as though it settled which rendering is better
(spec §1.3 — Gate 1 *"MUST NOT crown a language"*).

---

## 9. Evaluation-universe hash

`evaluation_universe_hash = PENDING: computed at freeze time`
**Decided by:** deterministic computation, not judgment. **Type:** `ENGINEERING_DECISION`.

The stable hash of the thirteen §6.27 components enumerated in spec §2.13: task distribution,
backend/kernel versions, Solver checkpoint, tokenizer, controller, tools, adaptation data,
adaptation budget, inference budget, verifier, seeds, evaluation split, code/manifest versions.

Additionally frozen and hashed at the same moment:

| artefact | hash |
|---|---|
| anchored bank content hash | **`9fa6b6da12e237a3d8b682aad4346f1416bbe14689298a3cfb8bac805e4605dc`** — realised; schema `arena-anchored-state-bank-v0`, generator `arena/trajectory/anchor.py@v0`, generated 2026-09-08T21:43:14Z |
| `prompt_template_id` / sha256 | `hc-v0.5-tactic-json-v1` / `95a4e049fca802876995f8b235573ddaa22e55964d74f4efb14579f4f5cee6ef` |
| output grammar sha256 | `9b25cba2450affa8cae91c864b059aeadc3bb0ed5ab2766a962495e2ed4f3e0b` |
| `FROZEN_DECODING` | `PENDING: docs/HC_V0_6_RUNTIME_NOISE.md.` Candidate, as exercised by the noise study: `temperature=0.0, seed=20260908, top_k=20, top_p=0.95, min_p=0.0, repeat_penalty=1.0, presence_penalty=0.0, num_ctx=32768, num_predict=128, think=False, stream=False, raw=False` |
| Solver digest | `d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`, `qwen3.6:27b-mlx`, Ollama 0.33.2, `verify_served()` recorded per run |
| toolchain | `leanprover/lean4:v4.10.0-rc1`; mathlib4 `29dcec074de168ac2bf835a77ef68bbe069194c5`; 5,681 `.olean`; `max_heartbeats=1000000` |
| `TacticPolicy.policy_id` | `PENDING: EXPERIMENT_DECISION, frozen before the run` (spec §2.11) |
| `attack_suite_version` | `PENDING`; the re-run against the HC-V0.6 bank, not the HC-V0.5 value inherited |
| `harness_version` + git commit | `PENDING: at freeze` — single value for the whole run (V05-16) |
| this manifest's own content hash | `PENDING: at freeze` |

§6.27: **fitness outside this universe is `UNKNOWN` until replicated.**

---

## 10. The complete `PENDING` register

Every open slot, what fills it, and who decides. Nothing else may be added to this list after
freeze; anything discovered later that would need a new slot is a new manifest version.

| # | slot | filled by | decided by | type | status |
|---|---|---|---|---|---|
| P1 | `delta_min` | power analysis | Experimentalist | `EXPERIMENT_DECISION` | open |
| P2 | equivalence region `δ_eq` | power analysis | Experimentalist | `EXPERIMENT_DECISION` | open |
| P3 | `n` anchors | anchored-bank builder | Experimentalist | `EXPERIMENT_DECISION` | **FILLED: 223** |
| P4 | `n_clusters` | anchored-bank builder | Experimentalist | `EXPERIMENT_DECISION` | **FILLED: 75** |
| P4b | *minimum* `n_clusters` for a reportable interval | power analysis | Experimentalist | `EXPERIMENT_DECISION` | open |
| P5 | `k` replicates | `docs/HC_V0_6_RUNTIME_NOISE.md` + power analysis | Experimentalist | `EXPERIMENT_DECISION` | open |
| P6 | replicate-collapsing rule (a/b/c, or the `k = 1` degeneracy) | `docs/HC_V0_6_RUNTIME_NOISE.md` | Experimentalist | `EXPERIMENT_DECISION` | open |
| P7 | bootstrap resamples `B`, permutation count | Experimentalist | Experimentalist | `ENGINEERING_DECISION` within §4 | open |
| P8 | primary α, `α_C1`, `α_C1b`, `α_C2`, power for the MDE | power analysis | Experimentalist | `EXPERIMENT_DECISION` | open |
| P9 | `FROZEN_DECODING` | `docs/HC_V0_6_RUNTIME_NOISE.md` | Experimentalist | `EXPERIMENT_DECISION` | open; candidate recorded in §9 |
| P10 | `TacticPolicy` (`record_only` vs `no_heavy_automation`) | pre-run decision | Experimentalist | `EXPERIMENT_DECISION` | open; the **bank** was built under `record_only:54954a450e6c9c5b` (spec §2.11) |
| P11 | anchor selection rule + seed | anchored-bank builder | Experimentalist | `EXPERIMENT_DECISION` | **FILLED** — quantile depth rule, `seed=0`, recorded in the bank manifest |
| P12 | anchored bank content hash | anchored-bank builder | deterministic | `ENGINEERING_DECISION` | **FILLED: `9fa6b6da…`** |
| P13 | `attack_suite_version` re-run on the HC-V0.6 bank | Refuter (§16.3) | Refuter | `ENGINEERING_DECISION` | open; the bank's own leakage pass is **not** a red-team suite |
| P14 | `evaluation_universe_hash`, `harness_version`, manifest hash | freeze-time computation | deterministic | `ENGINEERING_DECISION` | open |
| P15 | ~~optional `R_A′` unfamiliarity control~~ | — | — | — | **CLOSED, and no longer optional.** Design brief §9.4 makes `R_A_PRIME` a required fourth arm. The residual owner decision is §5's multiplicity deviation, not the arm's existence |
| P16 | the §5 two-layer multiplicity policy (Holm over the brief's four-member family for effect claims; uncorrected liberal α for the gates) | Experimentalist proposal, owner sign-off | **Owner** (§3.1 rank 1) | `OWNER_DECISION_REQUIRED` | open — but no longer a *conflict* with the brief; §5 now adopts the brief's family and legislates only the gates, which the brief does not cover |

**Five slots are now filled and four of the five came from the realised bank.** Filling them is a
completion, not a revision (§0). Nothing filled here may move after exposure.

---

## 11. Blocking preconditions — this manifest may not be frozen until these are true

Not statistical slots; gates. Each is a `PENDING` of a different kind: a defect that must close.

| # | precondition | source |
|---|---|---|
| B1 | the runtime-noise study has returned either a call-for-call reproducible configuration or a measured noise model with the `k` it forces | design brief §5; HC-V0.5 finding (a) |
| B2 | **V05-13 closed** — a dead model runtime must not be counted in `parse_failures`; it corrupts the primary endpoint's denominator | spec §7.3 |
| B3 | **V05-01 / V05-03 closed** — the action is bound to the policy that produced it (prompt hash + solver digest inside `semantic_core`), and `build_trajectory`'s actor is an assertion, not a rewrite. The bank builder holds the reference proof in the same process, which is exactly the configuration these defects describe | `docs/HC_V0_5_REDTEAM.md` §7; spec §8.7 |
| B4 | the `R_ONLY` contract is enforced structurally, not asserted: `R_B.render` receives only the baseline rendering (or only the declaration), so addition is impossible by signature — the brief's `invert` test alone forbids removal only | spec §3.2; V05-15 |
| B5 | `R_ABLATED` is labelled `P_CHANGE` by the `InterventionClass` machinery, with no hand-labelling. **DISCHARGED, but by a different mechanism from the one the brief names, and the difference is recorded rather than glossed.** Design brief §2 asks for the label to be derived *"from its genes"*. It is not: `arena/trajectory/representation.py` states that the gene table cannot express goal visibility today (`GOAL_VISIBILITY_GENE`), and `derive_intervention_class` therefore derives the class from the renderer's **declared slot set** — `R_ABLATED`'s is a strict subset of the baseline's — which the module argues is stronger, since it cannot be mislabelled by writing a different gene name. Two consequences that must not be lost: (a) no `LanguageCandidate` genome (§12.1) exists for any HC-V0.6 arm, so §12.1's eighteen required outputs are **not** produced; (b) V05-17's underlying defect — `gene_changes` is never checked against the genomes — is *bypassed* here, not closed | design brief §2; V05-17; manual §12.1, §12.3 |
| B6 | branching correctness measured | **DISCHARGED for the branching property**: `research/phase10/branching/README.md` — 6/6 distinct children from one parent, parent text intact, branch-from-child 6/6. **Still open**: the concurrent-session identity collision V05-04 must be closed or excluded by running one session at a time |
| B7 | the leakage guard re-measured **on the HC-V0.6 bank** | **PARTLY DISCHARGED**: the bank's anchor-level pass found **0 leaks in 223 anchors** under `TACTIC_IN_STATE_BEFORE`, `FULL_NAME_IN_STATE`, `LEAKS_PREFIX_TACTIC_IN_STATE`; 29 problems dropped by `SELECTION_LEAKAGE_FILTER` before derivation. **Still open**: V05-14's 6-byte floor, and `pp_scope.current_namespace`, which is deliberately exposed (spec §5) |
| B8 | `verify_served()` called and recorded, so the Solver digest is verified rather than asserted | V05-02; spec §2.3 |
| B9 | `max_retries = 0` enforced in the runner | spec §2.5 |
| B10 | the cell-disposition table (spec §7.3) implemented and unit-tested, including the symmetric-drop and re-run-once rules | spec §7.3 |
| **B11** | `R_A_PRIME` exists as a whitespace-perturbed, bijective, declaration-derived renderer, registered as a fourth arm, with `renderer_id == "R_A_PRIME"`. **DISCHARGED 2026-09-08**: `arena/trajectory/representation.py`'s `ARMS` registers `WhitespacePerturbedNative`, and `Arm.renderer_id` returns each arm's own id. **Re-verify at freeze**: this is the divergence that fails silently and flatteringly (spec §11 D1), so it is checked again rather than assumed to stay closed | spec §11 D1/D2; design brief §9.6 |
| **B12** | the estimator's comparison family matches §5, and `Comparison` covers primary, C1b, C2 and C1. **DISCHARGED 2026-09-08**: four members including `C1B_WHITESPACE`; `arena/experiments/hc_v0_6/calibration.py` makes every gate read the raw uncorrected permutation p-value with C1's α above the primary α, which is §5 layer 2 | spec §11 D3/D4 |
| **B13** | the arm-order permutation is implemented as a pure function of `(seed, anchor_id)` over **four** arms, and each cell records its realised position so a position effect can be tested | design brief §9.1; spec §6 |
| **B14** | the MDE of §2.1 is computed by the analysis code and emitted with every null, on clusters and on realised counts | design brief §9.5; spec §9.10 |

A manifest frozen with any of B1–B14 open is not a preregistration; it is a plan. The distinction
matters because §30.3's whole purpose is that the analysis cannot move after the data arrives, and
an unclosed B2, B4, B11 or B12 means the analysis is already undefined. **B11 and B12 are the two
that would fail silently**: a run against the current code would produce four numbers, three of
them correctly named, and one — labelled `R_A_PRIME` — that measured the noise floor while the
result document said it measured byte sensitivity.

---

## 12. Signature block

| field | value |
|---|---|
| manifest id | `hc-v0.6-anchored-delta` |
| manifest version | `v0.2-DRAFT` (supersedes `v0.1-DRAFT` prospectively; no exposure has occurred, so this is a permitted pre-freeze revision, §3.2) |
| arms | 4 — `R_A`, `R_A_PRIME`, `R_B`, `R_ABLATED` |
| comparisons | 4 — primary, C1b, C2, C1 (C1 is not an arm) |
| status | **DRAFT — 12 `PENDING` slots open (5 filled); 14 blocking preconditions, of which 3 discharged (B6 in part, B11, B12), 2 partly discharged (B5, B7), 9 open** |
| frozen at | `PENDING` |
| manifest content hash | `PENDING` |
| exposure boundary | the first Solver call against the anchored bank |
| after exposure | **abort or complete. Never edit.** (§3.2, §44.4) |

**The rule this table exists to make unmissable.** Before the first Solver call, this document may
be revised freely and a `PENDING` may be filled — that is what §0 calls a completion. After that
call, §3.2 and §44.4 permit exactly two moves: **run it to the end as written, or abort it and
start a new manifest version.** There is no third move. An analysis that "clarifies" the collapsing
rule, an `n` that grows because the interval was wide, an α that softens because C1 tripped, a
`delta_min` set to whatever C2 turned out to detect — each is the same violation wearing different
clothes, and each converts a confirmatory experiment into an uncontrolled one that merely looks
preregistered.
