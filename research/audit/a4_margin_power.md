# A4 — The 0.10 Margin, Uncertainty and Power

**Auditor 4 of 9 · Hamiltonian Arena V7 Total Forensic Audit · Parts D and F**
**Posture: adversarial. The brief was to destroy the argument, not defend it.**

**Scope rule observed throughout.** `SHORTCUT_MARGIN = 0.10` is preregistered and frozen
(`arena/experiments/fitness_v7.py:175`, `docs/FITNESS_V7_PREREGISTRATION.md:70-75`). **Nothing in
this document proposes, recommends, or implies an alternative value.** Every quantity here
characterises the behaviour of the *decision procedure at that fixed threshold*. Where an analysis
would qualify `transitive_dependency` only by moving the threshold, it is labelled OUT OF SCOPE and
excluded. Read-only: no file outside `research/audit/` was modified, and **no model call was made**.

## Artifacts produced

| Path | Contents |
|---|---|
| `research/audit/a4_power/reconstruct_paired.py` | Rebuilds the deterministic probe bank and recomputes all 7 shortcut rules per item; joins to solver rows. Asserts reproduction against the frozen artifact. |
| `research/audit/a4_power/paired_items.json` | Per-item paired outcomes (solver, each rule, best shortcut) for all 12 cells. |
| `research/audit/a4_power/margin_uncertainty.py` / `.json` | SEs, Newcombe/bootstrap/cluster-bootstrap CIs, ICC, design effect, Dirichlet and Bayesian-bootstrap posteriors, McNemar exact. |
| `research/audit/a4_power/power_and_n.py` / `.json` | Estimator resolution, gate operating characteristic, power, required n, shortcut selection-bias simulation. |
| `research/audit/a4_power/clustering_provenance.py` / `.json` | Exact N per cell, provenance, within-family constancy, effective n. |

**Reproduction commands** (venv `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`,
cwd = worktree root):

```
python -m research.audit.a4_power.reconstruct_paired
python -m research.audit.a4_power.margin_uncertainty
python -m research.audit.a4_power.power_and_n
python -m research.audit.a4_power.clustering_provenance
python -m pytest tests/experiments/test_fitness_v7.py -q     # 74 passed
```

**Reproduction is exact.** `reconstruct_paired.py` asserts the rebuilt dev-pool hash equals the
artifact's (`f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b`), and asserts every
one of the 7 rule scores, every `best_shortcut_accuracy`, every `best_shortcut_feature` and every
`positive_accuracy` in all 12 cells matches the frozen artifact to 1e-12. **All assertions pass.**
Every number below is derived from that verified reconstruction.

---

## PART D — THE MARGIN

### D1. Where the `≥ 0.10` rule comes from — traced

| Location | Content |
|---|---|
| `arena/experiments/fitness_v7.py:175` | `SHORTCUT_MARGIN = 0.10` — the constant. |
| `arena/experiments/fitness_v7.py:184` | `GATE_EPSILON = 1e-9`. |
| `arena/experiments/fitness_v7.py:280-281` | Written into `QUALIFICATION_RULE_V7`. |
| `arena/experiments/fitness_v7.py:752-754` | The gate: `"shortcut_margin": "PASS" if margin >= float(rule["shortcut_margin"]) - GATE_EPSILON else "VOID_SHORTCUT"`. |
| `arena/experiments/fitness_v7.py:725-726` | `best_shortcut = float(audit.get("best_shortcut_accuracy", 1.0)); margin = positive - best_shortcut`. |
| `arena/experiments/fitness_v7.py:655` | `best_shortcut_accuracy` is assigned V5's `worst_score`. |
| `arena/experiments/fitness_v5.py:818-823` | `worst_score` is defined as `max(scores[worst], 1.0 - scores[worst])` where `worst = max(scores, key=lambda n: abs(scores[n] - 0.5))`. |
| `docs/FITNESS_V7_PREREGISTRATION.md:70-75` | The declaration and its justification. |
| `tests/experiments/test_fitness_v7.py:777` | `assert v7.SHORTCUT_MARGIN == 0.10`. |
| `docs/PROJECT_LEDGER.md:837` | The same justification, restated at commit time. |

Committed at `e66bab1` ("preregister: Fitness V7"), before the run at `cf1b07f`. **The
preregistration claim is true: the threshold was frozen before any V7 number existed and was not
moved.** Nothing in this audit disputes that.

### D2. Is the threshold justified? — assessing SE ≈ 0.082 on its own terms

The stated justification (`docs/FITNESS_V7_PREREGISTRATION.md:73-75`):

> "at n = 24 the binomial standard error near 0.8 is ≈ 0.082, so a margin below one standard error
> could not distinguish a solver from its own shortcut."

`sqrt(0.8 × 0.2 / 24) = 0.081650`. The arithmetic is right. **The statistic is the wrong one.**
That is the SE of *one* proportion. The gate compares *two* accuracies. Three candidate SEs for the
contrast, all computed at the decision cell (`transitive_dependency` L3):

| Quantity | Value | Comment |
|---|---|---|
| Prereg's quoted single-arm SE (p = 0.8) | **0.08165** | not the SE of a contrast |
| Single-arm SE at the *observed* p = 0.75 | 0.08839 | the prereg guessed p = 0.8; observed is 0.75 |
| Two-sample SE if the arms were **independent** | **0.13066** | correct if unpaired |
| **Paired (McNemar) SE of the difference** | **0.08158** | correct if items are the unit |
| **Cluster-robust SE (family is the unit)** | **0.10360** | correct given the probe construction |

Two findings, in opposite directions, and both must be reported.

**(a) The derivation is wrong and internally inconsistent.** The project's own precedent uses a
*difference* SE for exactly this kind of gate: `docs/FITNESS_V5_SPEC.md:116` raises `gap_min` from
0.10 to 0.20 "because at 24+24 rows the gap's standard error is 0.142". 0.142 ≈ √2 × 0.10 — a
two-arm SE. V7 applied the same house rule ("a threshold must exceed one SE") to a two-arm contrast
using a **one-arm** SE. Had V5's own convention been followed, the quoted SE would have been
≈ 0.131 and 0.10 would have failed the house rule outright.

**(b) The number is nevertheless almost exactly right — by coincidence.** The correct paired SE at
the cell that actually decided the outcome is **0.081579**, versus the quoted **0.081650**: a
difference of 0.00007, or 0.09%. Marked **REFUTED** as an error *in the number*. But the coincidence
is local, not structural: across the 12 cells the correct paired SE ranges 0.0408–0.1128 while the
prereg's formula gives 0.0000–0.0988 (`margin_uncertainty.json`, columns `SE_pair` vs `SE_1arm`).
At `precondition_conjunction` L2 the prereg formula yields **0.0000** and the paired SE **0.1021**.
The agreement at `transitive_dependency` L3 is an accident of that cell's discordance structure.

**(c) The threshold fails its own stated test.** The preregistration's criterion is: *a margin below
one standard error cannot distinguish a solver from its own shortcut.* Using the correct,
cluster-aware SE of **0.10360**:

```
0.10 / 0.10360 = 0.965 standard errors
```

**0.10 is itself below one standard error.** By the very criterion the preregistration invokes to
certify it, the threshold is too small to do the job it is asked to do. It is 1.226 SE only if you
ignore the probe clustering, and 0.765 SE if the arms were independent.

**Classification: `CONFIRMED` · severity HIGH.** The threshold is **heuristic**, not theoretically
derived, not empirically calibrated, and not simulation-derived. The prior simulation work
(`research/selector_analysis/selector_simulation.py`, `artifacts/reports/v5_selector_analysis.json`)
is about the **frontier selector**, not the shortcut margin — grep confirms no simulation of the
margin's operating characteristic exists anywhere in the repository before this audit.

### D3. Why 0.100 passes and 0.083 fails — the boundary's actual behaviour

**This is the single most consequential finding in Part D.**

Both terms of the margin are counts over the same 24 positive items:
`positive_accuracy = k/24` and `best_shortcut_accuracy = m/24` (both computed on
`POSITIVE_VARIANTS`, `fitness_v5.py:271,791`; n = 24 verified in every cell). Therefore

```
margin = (k − m)/24 ∈ {..., 0, 0.041667, 0.083333, 0.125000, ...}
```

**The declared threshold 0.10 is not a representable value of the estimator.**

| | value |
|---|---|
| quantum of the estimator | 0.0416667 |
| largest achievable margin that **fails** | **0.0833333** |
| smallest achievable margin that **passes** | **0.1250000** |
| dead zone in which no result can ever land | (0.0833, 0.1250), width 0.0417 |
| **effective operational threshold at n = 24** | **0.125** |

**`SHORTCUT_MARGIN = 0.10` is operationally identical to `SHORTCUT_MARGIN = 0.125` at this sample
size.** The gate as executed is 25% stricter than the gate as declared, and no reader of the
preregistration could know that. `transitive_dependency` L3 landed at **exactly** the largest
failing representable value — verified programmatically
(`power_and_n.json: estimator_resolution.observed_is_the_largest_failing_value = true`).

The shortfall of 0.0167 is **0.40 of a single quantum**. The question "is the true margin 0.083 or
0.100?" is not merely hard to answer at n = 24; **it is not a question the instrument can pose**.

The codebase came within one line of catching this. `arena/experiments/fitness_v7.py:180-181` and
`tests/experiments/test_fitness_v7.py:261` both compute a resolution floor — and both state it as
`1/72 = 0.0139` ("accuracies are k/24, k/48 or k/72"). For **this** gate both operands are k/24, so
the floor is `1/24 = 0.0417`, three times coarser. The correct arithmetic was performed for
`GATE_EPSILON` and then not applied to `SHORTCUT_MARGIN`.

**Classification: `CONFIRMED` · severity CRITICAL.** The declared decision boundary does not exist.

### D4. Uncertainty on solver, shortcut, and the difference

Per-item outcomes **are** available for both arms — this audit derived them.

- **Solver:** `rows[].correct` in the artifact, joined by `probe_id`.
- **Shortcut:** *not* stored per item, but fully recoverable — the seven rules
  (`fitness_v5.py:801-817`) are deterministic functions of the probe. `reconstruct_paired.py`
  recomputes them and reproduces every published rule score exactly.

The arms are evaluated on **identical items**, so the difference is paired and correlated.
At `transitive_dependency` L3, φ(solver, shortcut) = **0.6124**.

Full 2×2 discordance table at the decision cell (a = both correct, b = solver only, c = shortcut
only, d = neither):

```
                    shortcut correct   shortcut wrong
solver correct            a = 15            b = 3        (solver 18/24 = 0.750)
solver wrong              c = 1             d = 5
                       (shortcut 16/24 = 0.6667)

margin = (b − c)/n = (3 − 1)/24 = 0.083333
DISCORDANT PAIRS = b + c = 4
```

**The entire preregistered decision rests on 4 discordant items and a net difference of 2.**

| Quantity | 95% interval |
|---|---|
| solver accuracy 0.7500 | Wilson [0.5510, 0.8800]; Clopper–Pearson [0.5329, 0.9023] |
| shortcut accuracy 0.6667 | Wilson [0.4671, 0.8203]; Clopper–Pearson [0.4468, 0.8437] |

SEs of the **difference**: paired **0.08158**; independent-arms 0.13066; cluster-robust **0.10360**.
The prereg's formula (0.08165 at p = 0.8) is not any of these, though it numerically matches the
first (§D2).

### D5. Confidence intervals for the margin

| Method | 95% interval | half-width | contains 0? | contains 0.10? |
|---|---|---|---|---|
| Newcombe (1998) method 10, paired score | [−0.0772, +0.2413] | 0.159 | **yes** | **yes** |
| Bootstrap, item-level, 200 000 reps | [−0.0833, +0.2500] | 0.167 | **yes** | **yes** |
| **Bootstrap, cluster (family), 200 000 reps** | **[−0.0833, +0.2917]** | **0.188** | **yes** | **yes** |

McNemar exact two-sided test of `H0: true margin = 0` → **p = 0.6250**
(b = 3, c = 1; `2·P(X ≥ 3 | Bin(4, 0.5)) = 10/16`).

**Every interval contains both 0 and 0.10.** The data cannot reject that the true margin is zero,
and cannot reject that it is exactly the preregistered threshold, and cannot reject 0.24.

### D6. P(true margin > 0.10) and P(true margin > 0)

**Model, stated explicitly.** Multinomial over the four paired cells (a, b, c, d) with a Dirichlet
prior; `margin = p_b − p_c`. The Dirichlet–multinomial is the natural conjugate model for a paired
2×2 and makes no normal approximation — appropriate at 4 discordant pairs. Three priors are
reported so the answer's prior-sensitivity is visible, plus a **cluster-aware Bayesian bootstrap**
(Dirichlet weights over the **12 families**, which is the defensible sampling unit — §F12).
200 000 draws each.

| Model | **P(δ > 0.10)** | **P(δ > 0)** | 95% credible interval |
|---|---|---|---|
| Uniform, Dir(1,1,1,1) | **0.3519** | **0.8125** | [−0.0944, +0.2456] |
| Jeffreys, Dir(0.5⁴) | 0.3673 | 0.8400 | [−0.0831, +0.2505] |
| Haldane, Dir(0.001⁴) | 0.3844 | 0.8747 | [−0.0681, +0.2542] |
| **Bayesian bootstrap over families (preferred)** | **0.3743** | **0.8318** | [−0.0801, +0.3015] |

**Headline: P(true margin > 0.10) ≈ 0.35–0.38. P(true margin > 0) ≈ 0.81–0.87.**

The result is prior-robust to three decimal places of interest. The preferred cluster-aware figure
is **P(δ > 0.10) = 0.374**. The gate voided a mechanism whose true margin has better than a **1 in
3** chance of exceeding the threshold it was voided for missing — while the evidence that it exceeds
*zero* is itself weak (McNemar p = 0.625).

**Classification: `CONFIRMED` · severity CRITICAL.** The decision is close to a coin flip.

### D7. Was the experiment powered to distinguish 0.083 from 0.10? — the number

**No. Power ≈ 0.069.**

| Basis | SE | separation | **power (1-sided, α = 0.05)** | power (2-sided) |
|---|---|---|---|---|
| item-level paired (McNemar) | 0.08158 | 0.204 SE | **0.0749** | 0.0396 |
| **cluster-robust (family unit)** | 0.10360 | 0.161 SE | **0.0689** | 0.0360 |

Against a 5% false-positive floor, power of 6.9% means the test carries **1.9 percentage points of
discriminating information**. The procedure is barely distinguishable from flipping a biased coin.

And the stronger statement supersedes the weaker one: by §D3 the separation is **0.40 of one
quantum of the estimator**. No outcome of an n = 24 experiment can lie strictly between 0.0833 and
0.10. The distinction is not underpowered — **it is unrepresentable**.

### D8. Required n for margins of 0.05 / 0.08 / 0.10 / 0.15

α = 0.05, power = 0.80, discordance fixed at the observed π_d = 4/24 = 0.1667, design effect 1.61
applied (§F13). "× deff" is the honest figure given the ORIGINAL/COUNTERFACTUAL pairing.

| true margin | **A.** items to detect margin > 0 (McNemar, 2-sided) | A × deff | **B.** items to *pass the frozen 0.10 gate* with 80% power (1-sided) | B × deff | **C.** items for a 95% CI half-width below the gap to 0.10 | C × deff |
|---|---|---|---|---|---|---|
| 0.05 | 521 | 841 | 406 | 655 | 253 | 407 |
| **0.08** | 203 | 326 | **2 478** | **3 995** | **1 540** | **2 483** |
| 0.10 | 129 | 208 | n/a | n/a | n/a | n/a |
| 0.15 | 56 | 90 | 357 | 575 | 222 | 358 |
| **actually run** | | | | **24** | | |

Column B is undefined at 0.10 because no finite n separates the boundary from itself; power there is
α by construction. Column B at 0.08 is the operative number: **~4 000 items** (≈ 2 000 families)
would be needed to reliably classify a true margin of 0.08 against a 0.10 gate. V7 ran **24**, a
factor of **166** short.

Even the weakest question — "is the margin greater than zero?" — needs **326** items at δ = 0.08.
V7 ran 24.

### D9. `VOID_SHORTCUT` as an operational decision vs. the scientific interpretation

**These are genuinely different, and V7 gets the first one right.**

**As an operational preregistered decision: APPROPRIATE, and I do not dispute it.** The gate is a
pre-committed policy for spending a 900-call budget under uncertainty: *do not authorise a founder
tournament unless the observed margin clears 0.10.* Committing to a bright line in advance is
exactly what a preregistration is for; it is what stops the analyst choosing the line after seeing
the number. `docs/FITNESS_V7_RESULT.md:80-82` explicitly refuses to lower it to 0.08 and calls that
protocol shopping. **That refusal is correct and this audit endorses it.** With
P(δ > 0.10) = 0.374, a decision rule that declines to spend the budget is defensible on its own
decision-theoretic terms.

**As a scientific interpretation: NOT SUPPORTED.** "`transitive_dependency` is shortcut-dominated"
is a claim about the world, and the evidence for it is:

- McNemar exact p = **0.625** for H0: margin = 0;
- 95% CI [−0.083, +0.292] containing 0, 0.10 and 0.29 alike;
- P(δ > 0) = 0.83, i.e. the *point estimate favours the solver*, not the shortcut;
- a comparator that is a selection artifact at the null noise floor (§F15).

The correct scientific statement is **"evidence inconclusive; the gate did not open."** Not
"the mechanism is shortcut-dominated."

### D10. Are we treating a preregistered administrative threshold as a statement about nature?

**Yes. Directly, in three identifiable places.** This is the crux and the answer is unambiguous.

1. **The sentinel name.** `V7_SHORTCUT_DOMINATED` (`docs/FITNESS_V7_PREREGISTRATION.md:169`,
   `docs/FITNESS_V7_RESULT.md:3`) is a claim about the mechanism's nature. The preregistered
   *condition* is administrative — "fails only the new shortcut margin". The *name* asserts
   domination. For `transitive_dependency` the solver **out**performs the comparator by 0.083 and
   nothing is dominated.
2. **`docs/FITNESS_V7_RESULT.md:79`:** "A solver that beats a first-mention heuristic by 8.3 points
   on 24 items is not demonstrating mechanism-specific reading; at n = 24 that gap is ≈ 1.0 standard
   error." The observation about the SE is fair (and §D2 shows it is numerically right by accident).
   The inference is not: "≈ 1 SE" is a statement that the evidence is **weak in both directions**,
   which licenses *no* conclusion about what the solver is doing. Failure to demonstrate is being
   reported as demonstration of failure.
3. **`docs/FITNESS_V7_RESULT.md`, §6 "Does":** "Two are beaten or near-matched by a one-line string
   heuristic." For `transitive_dependency` the "one-line string heuristic" is
   `first_mentioned_in_state` **inverted** — a rule whose raw accuracy is **0.3333** — and whose
   0.6667 is *below* the null expectation of the max-over-rules statistic (§F15). No such heuristic
   was demonstrated to exist.

**The threshold is an administrative line drawn inside the project's own declared noise floor.**
The same frozen rule set, written into V7's own artifact (`fitness_v5.py:247-249`, echoed at
`artifacts/.../result-qwen38-rvn_latest-bare.json → promotion_rule`), declares:

```
practical_effect_min          = 0.10
practical_equivalence_region  = 0.125     <- effects within ±0.125 are "practically equivalent"
smallest_effect_of_interest   = 0.15
```

**Both the observed margin (0.083) and the required margin (0.10) lie inside the project's own
practical-equivalence region of ±0.125, and both are below its own smallest effect of interest of
0.15.** `docs/FITNESS_V5_SPEC.md:139-141` set ±0.125 precisely because that was the achievable 95%
half-width at N = 128. V7 applies a 0.10 bright line at **N = 24**, where the measured half-width is
**0.159–0.188** — demanding a resolution finer than the project itself certified as achievable at
five times the sample size.

**Classification: `CONFIRMED` · severity CRITICAL.** The threshold is a budget-allocation policy
being reported as a fact about the mechanism.

---

## PART F — SAMPLE SIZE AND STATISTICS

### F11. Exact N per mechanism × level

Identical in all 12 cells (`clustering_provenance.json → Q11`):

```
rows per cell                                        72
ORIGINAL                12  \ POSITIVE_VARIANTS  ->  24  <- the n used for accuracy AND the gate
COUNTERFACTUAL          12  /
DESTROYED_ORIGINAL      12
DESTROYED_COUNTERFACTUAL 12
SWAPPED_ORIGINAL        12
SWAPPED_COUNTERFACTUAL  12
                       ---
total                  864 rows = 3 mechanisms × 4 levels × 72
```

**n = 24 for every gate decision.** The 864-row total is 36× larger than the effective evidence
behind any single qualification verdict.

### F12. Are rows independent? — measured, not assumed

**No.** Every cell is 12 families × 2 items (`fitness_v5.py:205 DEV_FAMILIES = 12`;
`build_dev_pool` at `fitness_v5.py:893-912`; verified `items_per_family = [(2, 12)]` in all 12
cells). The two items in a family are ORIGINAL and its COUNTERFACTUAL — the *same* canonical state
with a minimal edit flipping the target. **They are constructed to be maximally dependent.**

Three nested layers of shared structure, all measured:

**(a) Family (n = 12 clusters of 2).** At the decision cell the best shortcut is **constant within
every one of the 12 families** (`clustering_provenance.json`: `first_mentioned_in_state` constant in
**12/12** families at `transitive_dependency|L3`). The shortcut arm therefore has an effective n of
exactly **12, not 24**. The solver is constant within **10/12**.

**(b) Generator template (n = 1).** All 12 families at `transitive_dependency` L3 come from a single
`_synthetic_family` call shape (`hops = 5`, `LADDERS` at `fitness_v5.py:184`), differing only by an
integer salt (`fitness_v5.py:901`). **There is exactly one template per cell.** Template-level
variance is therefore *unestimable*, and the result generalises to that one generator, not to
"transitive dependency" as a construct.

**(c) Theorem reuse across levels (`formal_expression_depth`).** L0 and L2 both have
`stratum = "medium"` and draw the **identical 12 theorems** (`Finset.prod_of_injOn`,
`Stream'.WSeq.eq_or_mem_iff_mem`, … — verified byte-identical lists). L0 gates validity
(`explicit_positive_min = 0.90`) and L2 was the **selected frontier**. **The validity gate and the
datum it gates are computed on the same 12 source theorems**, differing only in `explicit`.
Each theorem appears exactly twice per cell (multiplicity `[2]×12`), matching the family structure.

**Classification: `CONFIRMED` · severity HIGH.** Rows are not independent, at three levels.

### F13. Cluster-aware recomputation — how much do intervals widen?

Family-level differences at `transitive_dependency` L3 (solver-correct minus shortcut-correct,
per family): `[2, 0, 0, 1, 0, −1, 0, 0, 0, 0, 0, 0]`.

**Nine of twelve families contribute exactly nothing. The entire result is three families:
one at +2, one at +1, one at −1.**

| | item-level | **cluster (family)** | change |
|---|---|---|---|
| SE of the margin | 0.08158 | **0.10360** | **+27.0%** |
| 95% CI | [−0.0772, +0.2413] | **[−0.0833, +0.2917]** | half-width 0.159 → **0.188, +17.9%** |
| ICC of the difference within family | — | **+0.511** | |
| design effect | 1.00 | **1.613** | |
| effective n | 24 | **14.9** | **−38%** |

**Honest nuance, reported because it cuts the other way.** Clustering is **not** uniformly harmful
across cells. The ORIGINAL/COUNTERFACTUAL pairing induces *negative* ICC wherever the shortcut rule
is symmetric under the counterfactual — `always_first_option` is right on exactly one of each pair
by construction, so `precondition_conjunction` L2/L3 have ICC = **−1.00**, design effect **0.00**,
and behave as *more* than 24 independent items. Measured ICCs across all 12 cells: −1.00, −0.83,
−0.33, −0.25, −0.16, −0.16, 0.00, +0.29, +0.32, +0.51 (`clustering_provenance.json → Q13_Q14`).

A blanket "V7 is pseudo-replicated" claim would be **overstated**. The precise claim is: **at the
one cell whose margin decided the outcome, clustering inflates the variance by 61% and cuts the
effective sample size to 14.9.**

### F14. Are repeated variants pseudo-replication? — effective sample size

**Partially, and decisively so at the cell that mattered.**

| cell | nominal n | families | design effect | **effective n** | ICC |
|---|---|---|---|---|---|
| formal_expression_depth L0 | 24 | 12 | 1.36 | 17.6 | +0.29 |
| formal_expression_depth L1 | 24 | 12 | 0.87 | 27.5 | −0.16 |
| **formal_expression_depth L2** (selected) | 24 | 12 | **1.40** | **17.2** | +0.32 |
| formal_expression_depth L3 | 24 | 12 | 0.77 | 31.1 | −0.25 |
| precondition_conjunction L1/L2/L3 | 24 | 12 | 0.17 / 0.00 / 0.00 | 143 / ∞ / ∞ | −0.83 / −1.00 / −1.00 |
| transitive_dependency L0/L1/L2 | 24 | 12 | 1.04 / 0.87 / 0.69 | 23.0 / 27.5 / 34.6 | 0.00 / −0.16 / −0.33 |
| **transitive_dependency L3** (selected, decisive) | 24 | 12 | **1.61** | **14.9** | **+0.51** |

**Both selected cells — the only two where the margin gate was actually evaluated — are the
positively-clustered ones.** Effective n at the decision cell is **14.9**, below `min_positives_for_gates
= 24` (`fitness_v5.py:222`). On an effective-sample basis the cell does not meet the instrument's own
minimum, and the `sample_size` check nevertheless reports PASS because it counts nominal rows.

### F15. Does McNemar apply to the comparison actually being made?

**Not as stated. This is a structural flaw in the comparator, independent of n.**

McNemar's test compares **two fixed, pre-specified** classifiers on paired data. Arm B here is not
fixed. `fitness_v5.py:822-823`:

```python
worst = max(scores, key=lambda n: abs(scores[n] - 0.5))
worst_score = max(scores[worst], 1.0 - scores[worst])
```

`best_shortcut_accuracy` is the **maximum of 14 correlated statistics** (7 rules × 2 polarities)
**selected on the same 24 items** it is then evaluated on. That is textbook selective inference: the
comparator is upward-biased, so the margin is downward-biased, and no nominal paired test is valid
against it without a max-statistic null.

**Quantified** (`power_and_n.json → shortcut_selection_bias`, 400 000 replicates). Under a null in
which no rule carries any signal — note `always_first_option`/`always_second_option` score exactly
0.500 in **all 12 cells** because `answer_share_index_0 = 0.5` exactly, so only 5 rules are
genuinely data-dependent:

| null model | E[best_shortcut] | upward bias | P(best ≥ 0.6667 \| null) |
|---|---|---|---|
| 5 informative rules, items independent | 0.6587 | **+0.159** | 0.559 |
| 7 rules, items independent | 0.6742 | +0.174 | 0.684 |
| **5 rules, resolved at family level** (as observed) | **0.7226** | **+0.223** | **0.914** |

**The observed `best_shortcut_accuracy` at `transitive_dependency` L3 is 0.6667 — *below* the
clustered null expectation of 0.7226, and a value that pure noise reproduces or exceeds 91.4% of the
time.**

And the rule itself: `first_mentioned_in_state` scored **0.3333** — it is *anti*-correlated with the
answer. The 0.6667 is the accuracy of a **post-hoc negation**, chosen because 0.3333 maximised
|s − 0.5|. Nobody proposed "always answer the opposite of whichever identifier is mentioned first"
as a shortcut in advance; the audit rule set manufactured it after the fact.

**`transitive_dependency` L3 exhibits no detectable shortcut at all.** It was voided for failing to
beat a selection artifact by 0.10.

The code documents the inversion honestly — `fitness_v7.py:642-643`: "a rule at 0.333 is a shortcut
at 0.667 for anyone willing to negate it" — which is a fair adversarial stance for the **absolute**
gate (`shortcut_rule_max = 0.75`). It is not sound as the reference point of a **margin** gate,
because the selection bias enters the margin with a minus sign and is never corrected.

**Classification: `CONFIRMED` · severity CRITICAL.** McNemar (or any fixed-comparator paired test)
does not apply to the comparison V7 actually makes.

### F16. Are p-values meaningful given accumulated researcher degrees of freedom?

**There are no p-values.** Confirmed by exhaustive string search of the frozen artifact:
`p_value`, `pvalue`, `p-value`, `mcnemar`, `bootstrap`, `power`, `confidence`, `interval`,
`standard_error`, `ci95` — **0 occurrences of each**. §7 of the preregistration explicitly
states the secondary endpoints carry "no p-values". The question therefore has no direct target.

**But the underlying concern — accumulated researcher degrees of freedom — is real and is not
neutralised by V7's preregistration.**

*Within V7: near zero, and this is to V7's credit.* The preregistration was committed at `e66bab1`
before the run at `cf1b07f`; the selector is deterministic; no threshold was moved; 74/74 tests pass;
the artifact reproduces bit-exactly. `docs/FITNESS_V7_RESULT.md:80-82` refuses a post-hoc move to
0.08 by name. **Marked `REFUTED` for the within-V7 charge.**

*Across generations: substantial, and structurally uncorrectable by V7's own preregistration.*

| axis | count | evidence |
|---|---|---|
| instrument generations | **6** (`fitness_v1…v5`, `v7`) | `arena/experiments/`, distinct `INSTRUMENT_VERSION` strings |
| preregistration / spec documents | 4 | `FITNESS_V3/V4/V5_SPEC.md`, `FITNESS_V7_PREREGISTRATION.md` |
| selector definitions | 2 | fixed `frontier_target = 0.625` (V3–V5) → derived 0.775 (V7) |
| `gap_min` values | 2 | 0.10 (V3/V4) → 0.20 (V5), `FITNESS_V7_PREREGISTRATION.md:36-38` |
| practical-equivalence region values | 2 | 0.05 (`fitness_v4.py:180`) → 0.125 (`fitness_v5.py:249`) |
| thresholds in the qualification rule | 18 | `QUALIFICATION_RULE` / `QUALIFICATION_RULE_V7` |
| cells eligible for the gate | 9 | 3 mechanisms × selectable levels L1–L3 |
| solver substitutions | ≥ 2 | gemma → `qwen38-rvn` (Phase 6 / V6) |

The gate that produced `V7_SHORTCUT_DOMINATED` is **1 of 9 eligible cells, in the 6th instrument
generation, each generation revised in light of the previous outcome.** Each revision was
individually documented and defensible — but the multiplicity is cumulative and the frozen-before-
the-run guarantee applies only within V7. **`LIKELY` · severity MEDIUM** for the accumulated
selection pressure; the honest framing is that V7 is the sixth draw from a garden of forking paths
whose earlier branches were chosen after seeing data.

### F17. Are effect sizes reported alongside p-values? Was practical equivalence defined?

**Effect sizes: yes for the point estimate, no for its uncertainty.** The artifact reports
`shortcut_margin_observed` and `shortcut_margin_at_this_level` for every level — a real effect size,
correctly reported. It reports **no interval, no SE, no discordance count, and no effective n** for
any of them (0 string hits, above). The gate is a bare point estimate against a bare threshold.

This violates the project's own written standard. `docs/CLAUDE_HANDOFF.md:361`: "Report effect size,
interval, discordances, and raw denominators; `p < .05` alone is not a [result]".
`docs/FITNESS.md:21`: "Rates use explicit denominators and confidence intervals where sampling is
involved." **Neither is honoured for the margin gate**, the one number the whole run turns on.

**Practical equivalence: defined, but for a different rule, and it contradicts this one.**
`practical_equivalence_region = 0.125` and `smallest_effect_of_interest = 0.15`
(`fitness_v5.py:248-249`) govern the founder *promotion* comparison, not qualification. But they are
the project's own calibration of what a difference of this kind, on this instrument, at this scale,
is worth taking seriously — and by that calibration **0.10 is inside the noise and 0.083 is inside
the noise**. No equivalence region was ever defined for the shortcut margin itself, so
`VOID_SHORTCUT` cannot distinguish "the solver is no better than the shortcut" from "we could not
tell". **`CONFIRMED` · severity MEDIUM.**

### F18. Could V7 be underpowered for the gate it imposes? — the quantitative answer

**Yes, severely.** The gate's operating characteristic at n = 24 (200 000 replicates per point,
π_d = 0.1667; `power_and_n.json → gate_operating_characteristic`):

| **true** margin | P(gate passes), items independent | P(gate passes), fully clustered |
|---|---|---|
| 0.00 | **0.1013** | **0.1356** |
| 0.05 | 0.2480 | 0.2459 |
| 0.0833 | 0.3897 | 0.3397 |
| **0.10 — exactly the threshold** | **0.4647** | **0.3900** |
| 0.125 | 0.5886 | 0.4740 |
| 0.15 — the project's smallest effect of interest | **0.7110** | **0.5578** |

Read across the whole table:

- A mechanism whose true margin **exactly equals the preregistered threshold** passes **39–46%** of
  the time. A correctly-calibrated gate would pass it ~50%; the shortfall is the quantization of
  §D3 biting.
- A mechanism with **no advantage at all** passes **10–14%** of the time — a false-pass rate 2–3×
  the conventional 5%.
- A mechanism at the project's own **smallest effect of interest (0.15)** is *still missed* **29–44%**
  of the time.

**The gate is close to a fair coin across the entire region it is meant to police.** It neither
protects reliably against a null mechanism nor admits reliably a genuine one. Combined with the
selection-biased comparator (§F15), the clustering (§F13), and the unrepresentable threshold (§D3),
**V7 had no meaningful power to apply the rule it preregistered.**

**Classification: `CONFIRMED` · severity CRITICAL.**

---

## Classified flaw list

| # | Finding | Class | Severity | Effect on the V7 conclusion |
|---|---|---|---|---|
| A4-1 | 0.10 is not a representable margin at n = 24; the effective threshold is **0.125**, with a dead zone (0.0833, 0.125). `transitive_dependency` landed at exactly the largest failing value. | `CONFIRMED` | **CRITICAL** | The executed gate is 25% stricter than the declared gate. Undisclosed. |
| A4-2 | Power to distinguish the observed 0.0833 from 0.10 is **0.069**; the separation is 0.40 of one quantum — unrepresentable, not merely underpowered. | `CONFIRMED` | **CRITICAL** | The decisive comparison carries ~2 points of information over chance. |
| A4-3 | Gate operating characteristic: P(pass \| δ = 0.10) = **0.39–0.46**; P(pass \| δ = 0) = **0.10–0.14**; P(pass \| δ = 0.15) = 0.56–0.71. | `CONFIRMED` | **CRITICAL** | The gate is near-uninformative across its whole operating range. |
| A4-4 | `best_shortcut_accuracy` is a **max over 7 rules × 2 polarities selected on the evaluation data**. Null expectation 0.659–0.723. Observed 0.6667 is *below* the clustered null mean; P(≥ 0.6667 \| null) = **0.914**. The winning rule scores 0.333 raw and is **inverted**. | `CONFIRMED` | **CRITICAL** | `transitive_dependency` L3 shows **no detectable shortcut**. It was voided for failing to beat noise. |
| A4-5 | The decision rests on **4 discordant pairs**, net **2 items**, from **3 of 12 families**. McNemar exact **p = 0.625** for H0: margin = 0. All 95% CIs contain 0 **and** 0.10. | `CONFIRMED` | **CRITICAL** | The evidence does not distinguish any hypothesis of interest. |
| A4-6 | P(δ > 0.10) = **0.374**, P(δ > 0) = **0.832** (cluster-aware; prior-robust across uniform/Jeffreys/Haldane). | `CONFIRMED` | **CRITICAL** | Better than 1 in 3 that the void was wrong on its own terms. |
| A4-7 | An administrative threshold is reported as a fact about nature — sentinel name `V7_SHORTCUT_DOMINATED`; `FITNESS_V7_RESULT.md:79`; §6 "beaten or near-matched by a one-line string heuristic". | `CONFIRMED` | **CRITICAL** | Failure to demonstrate is published as demonstration of failure. |
| A4-8 | The frozen rule set contradicts its own calibration: `practical_equivalence_region = 0.125`, `smallest_effect_of_interest = 0.15`. Both 0.083 and 0.10 sit inside the project's own equivalence region; measured 95% half-width at n = 24 is 0.159–0.188. | `CONFIRMED` | **HIGH** | The gate draws a hard line inside its own declared noise floor. |
| A4-9 | The SE justification uses a **one-arm** SE for a **two-arm paired** contrast, inconsistent with the project's own precedent (`FITNESS_V5_SPEC.md:116` used a difference SE of 0.142 for `gap_min`). | `CONFIRMED` | **HIGH** | Derivation unsound; see A4-13 for the number. |
| A4-10 | By its own stated criterion, using the correct cluster-aware SE, **0.10 = 0.965 SE — below one standard error**. The threshold fails the test the preregistration invokes to certify it. | `CONFIRMED` | **HIGH** | The justification is self-undermining. |
| A4-11 | Rows are not independent at three levels: 12 families × 2 items (shortcut constant in **12/12** families); **1 generator template** per cell (template variance unestimable); `formal_expression_depth` L0 and L2 share the **identical 12 theorems**, so the validity gate and the gated datum share source material. | `CONFIRMED` | **HIGH** | Design effect **1.61** at the decision cell → effective n **14.9**, below the instrument's own `min_positives_for_gates = 24`, while `sample_size` reports PASS on nominal count. |
| A4-12 | Cluster-aware intervals widen: SE **+27%**, CI half-width **+18%**. But ICC is **negative** in 6 of 12 cells (to −1.00) — clustering is not uniformly harmful, and both *selected* cells are the positively-clustered ones. | `CONFIRMED` | MEDIUM | Reported in both directions; a blanket pseudo-replication charge would be overstated. |
| A4-13 | The quoted SE value (0.08165) is nevertheless within **0.09%** of the correct paired SE (0.08158) at the decision cell. | **`REFUTED`** | — | The *number* is right; only the derivation is wrong. Coincidental — across cells the two disagree by up to 0.102. |
| A4-14 | The margin's resolution floor is documented as `1/72 = 0.0139` (`fitness_v7.py:180`, `test_fitness_v7.py:261`). Both gate operands are k/**24**, so it is `1/24 = 0.0417`. | `CONFIRMED` | MEDIUM | The arithmetic that would have exposed A4-1 was performed for `GATE_EPSILON` and not applied to `SHORTCUT_MARGIN`. |
| A4-15 | No interval, SE, discordance count or effective n appears anywhere in the artifact (0 string hits for each), violating `CLAUDE_HANDOFF.md:361` and `FITNESS.md:21`. | `CONFIRMED` | MEDIUM | The gate is a bare point estimate against a bare threshold. |
| A4-16 | Accumulated researcher degrees of freedom **across** generations: 6 instrument versions, 2 selectors, 2 `gap_min` values, 2 equivalence regions, 9 eligible cells. | `LIKELY` | MEDIUM | V7 is the 6th draw; earlier branches were chosen after seeing data. |
| A4-17 | **Within V7** the protocol held: prereg at `e66bab1` before the run, deterministic selector, no threshold moved, post-hoc lowering to 0.08 explicitly refused, 74/74 tests pass, artifact reproduces bit-exactly. | **`REFUTED`** | — | **No protocol violation. The instrument did exactly what it said it would do.** |
| A4-18 | `v7.QUALIFICATION_RULE` is the re-exported V5 dict (stale `frontier_target = 0.625`, no `shortcut_margin`) — a name collision, but `qualify_mechanism` correctly uses `QUALIFICATION_RULE_V7` (`fitness_v7.py:724`). | **`REFUTED`** | — | Cosmetic only. No decision affected. |

---

## Where the instrument holds up

Reported per the integrity requirement.

- **The preregistration was honoured.** Frozen before the run, not moved after; the explicit refusal
  to drop to 0.08 (`FITNESS_V7_RESULT.md:80-82`) is correct, and this audit endorses it.
- **The artifact is fully reproducible.** Dev-pool hash, all 84 rule scores, all 12
  `best_shortcut_accuracy` values and all 12 `positive_accuracy` values reproduce to 1e-12 from an
  independent reimplementation. All 864 rows `FRESH`, Q0 = 1.000.
- **The quoted SE, though wrongly derived, is numerically right at the cell that mattered** (0.09%).
- **The preregistration was candid about power in advance** (`FITNESS_V7_PREREGISTRATION.md:155-159`,
  `FITNESS_V7_RESULT.md:100-104`): "sample size and ladder granularity, not the aim point, are the
  dominant limitation." That warning was correct. This audit quantifies how much more binding it was
  than stated — the limitation is not merely granularity but a threshold the estimator cannot
  express.
- **`precondition_conjunction`'s `VOID_CEILING` is sound.** Its shortcut is 0.500 at L1–L3 with
  margins 0.458–0.500 and McNemar p ≈ 0.0005–0.0010. That verdict is well-supported.
- **The two V7 corrections did what they were registered to do.** The derived target moved
  `formal_expression_depth` into the window; the per-level audit then revealed a real shortcut there
  (L2 = 0.833, L1 = 1.000, both exceeding `shortcut_rule_max = 0.75` on the **absolute** gate,
  which is not selection-biased in the same way). **`formal_expression_depth`'s void is
  well-supported and this audit does not contest it.**

## The single sentence

`transitive_dependency` was voided for missing a threshold that its estimator cannot represent
(effective threshold 0.125, not 0.10), by 0.40 of one quantum, on 4 discordant pairs from 3 of 12
non-independent families, against a comparator that is a post-hoc inverted rule sitting *below* the
noise floor of the max-over-14 statistic that produced it — with McNemar p = 0.625, a 95% interval
of [−0.083, +0.292] containing every hypothesis of interest, P(true margin > 0.10) = 0.374, and gate
power of 0.069. **The operational decision not to spend the founder-tournament budget is defensible.
The scientific claim that the mechanism is shortcut-dominated is not supported by this experiment at
all.**
