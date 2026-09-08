# Long-Horizon Fitness V0 — specification

**Status: `DESIGN_ONLY`. Nothing here has been executed. No number in this document is a result.**

This is a specification for the fitness signal of the outer evolutionary loop described in
`docs/HAMILTONIAN_CHESS_META_GOAL.md` §5–§6. It is written against code that exists and was read;
every measured number cites its file or artifact. Where a number is a *proposal* rather than a
measurement it is marked **[PROPOSED]** and the assumption behind it is stated.

It replaces nothing that is running, because nothing is running: the programme has never computed
Δ(R_A, R_B) (`docs/PHASE8_SALVAGE_HANDOFF.md` §5), and the standing sentinels
`RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and `TRAINING_LANGUAGE_V0_BASELINE` are unchanged by it.

---

## 0. The one-sentence design

Fitness is a **seven-dimensional vector behind two non-compensatory gates**, estimated on
**trajectories as the unit of analysis**, promoted through a **six-level successive-halving
ladder** whose cheap levels cost zero model calls, with `J_horizon` — how the parent-vs-child
advantage changes as reasoning horizon grows — as the dimension the project exists to measure and
the only one that is expensive enough to be rationed.

---

## 1. What already exists, and what state it is in

Read before designing. This section is a finding, not a plan.

| Module | LOC | Tests | Verdict |
|---|---|---|---|
| `arena/fitness/metrics.py` | 260 | shared 51-line file | **Real, used, thin.** `wilson_interval`, `proportion_metric`, `mean_metric` are correct and used by `arena/league/registry.py` and `arena/evaluation/static.py`. **No clustered estimator anywhere.** |
| `arena/fitness/gates.py` | 146 | yes | **Real, used.** `evaluate_gate_zero` fails closed when `required_roundtrip_total <= 0` — the right default. Consumed only by `arena/evaluation/static.py`. |
| `arena/fitness/pareto.py` | 133 | yes | **Real, used.** `pareto_fronts`, `pareto_ranks`, NSGA-II `crowding_distance`. Consumed by `arena/league/selection.py`, `arena/pipeline.py`, `arena/reporting.py`. |
| `arena/fitness/search_metrics.py` | 30 | none found | **Dead.** No importer outside the package. Its `1/(1+expanded+verifier_calls)` scalarisation is also a bad estimator (see §2, `J_search`). |
| `arena/evaluation/landscape.py` | 202 | yes | **Real, used, and the only clustered machinery in the repo.** `paired_comparison` does exact McNemar + a family-clustered paired bootstrap; consumed by `game_r_formal_v1.compare_arms` and `precondition_power`. |
| `arena/experiments/precondition_power.py` | 1,573 | 31 | **Real, complete, unused by any pipeline.** Exact McNemar power, FFT-exact clustered power, TOST, shortcut-gate operating characteristic, budget tables. This design *calls* it; it does not reimplement it. |
| `arena/experiments/rendered_prompt_adversary.py` | 1,620 | 21 | **Real, complete.** 19 features × 2 polarities + 26 constant rules = **64 rules** (verified by import), plus 2 shallow models; DEV/EVAL family-disjoint split, Holm, Clopper–Pearson, permutation null, AST import ban. |
| `arena/experiments/game_r_formal_v1.py` | 1,773 | 67 | **Real, dry-run green, never run live.** `cache_identity` (8 components), `CacheScope.CROSS_CONDITION` refusal, `assert_arena_parity`, `score_mechanism`, `gate_mechanism`, `compare_arms`, `GATE_CONSTANTS`. |
| `arena/league/registry.py` | 262 | yes | **Real but inert.** Multi-axis ratings with CIs, no scalar Elo (good). **No archive, no niching, no behavioural descriptors** — `grep` for `archive`/`MAP-Elites`/`behavioural descriptor` across `arena/` returns nothing but an unrelated `game_r_mutant_audit` string. |
| `arena/surrogate/*` | 367 | 43-line file | **Real but unfed.** `CalibratedSurrogate` predicts *hard-gate survival probability*, not ΔJ. `extract_features` flattens a genome only — it has **no slot for mutation operator, environment, model, or horizon**. Consumed by nothing outside its own tests. |
| `arena/genome/mutation.py` | 439 | yes | **Real.** 24 typed operators with `OPERATOR_GENE_SCOPE`, `MutationProposal`, `MutationRecord`, `apply_mutation` with stale-proposal detection. |
| `arena/storage/db.py` | 388 | yes | **Real, thin, and the right skeleton** — see `docs/LANGUAGE_FITNESS_MEMORY.md`. |

Two measured facts about the population this fitness will act on:

- `artifacts/reports/game-r-mutant-audit.json`: **120 of 120 mutants classified `GAME_R_COMPATIBLE`**,
  `structural_near_duplicate_pairs: []`. The semantic gate as currently constituted **never
  eliminates anything**, because —
- `artifacts/reports/genome-content-audit.json`: the audited genome has **7 SURFACE + 7 STRUCTURAL
  genes and 0 CONTENT_BEARING, 0 REASONING_PROTOCOL genes** —
  *"zero existing content-bearing or reasoning-protocol genes"*.

**Consequence for this design:** L0's elimination rate is currently 0.00 by construction. It only
becomes a real gate once the meta-genome widens into Layer B/C (`HAMILTONIAN_CHESS_META_GOAL.md`
§4). Every survivor count in §5 that assumes L0 removes anything is **[PROPOSED]** and unverified.

---

## 2. The fitness vector

Seven dimensions. **No scalarisation.** The estimand is stated first because the recurring
programme failure — named in `research/audit/a7_phase6_retrospective.md` §"a statistic was computed
at a coarser or different granularity than the claim made from it" and elevated to a binding rule in
`HAMILTONIAN_CHESS_META_GOAL.md` §7 — is *granularity substitution*. Every dimension below therefore
names its population and its unit of analysis explicitly, and the estimator is clustered at that
unit.

### 2.1 Summary table

| Dim | Estimand (population) | Unit of analysis | Estimator | Uncertainty | Min n for a useful reading | Primary gaming mode |
|---|---|---|---|---|---|---|
| `J_solve` | P(verifier accepts a complete solution) over the sealed problem distribution `D`, given language `L`, Solver `M`, budget `B` | **problem** (one binary outcome per problem, whatever its length) | paired proportion vs parent on the identical problem set | exact McNemar + problem-clustered bootstrap (`landscape.paired_comparison`) | **249 problems** for Δ=0.10 at α=.05, π_d=.30; **344** at α=.0125 (Holm k=4) — `precondition_power.required_n_pairs` | solve easy problems only; drop hard ones via a "cannot proceed" escape that is scored as abstention |
| `J_horizon` | The **change in Δ(child−parent) across horizon buckets**: γ = Δ(long) − Δ(short) | **trajectory** (nested in problem) | difference-in-differences of two paired proportions on disjoint bucket pools | independent-bucket paired SE; CI from the two clustered bootstraps combined | **≈470 problems per bucket** for γ=0.10, **≈210** for γ=0.15, **≈1,900** for γ=0.05 (seeded simulation, §4.4) | build "long" tasks by concatenation; let horizon correlate with prompt length; report only the bucket that won |
| `J_learn` | Verified success after a matched adaptation budget, minus the same before it | **problem**, paired pre/post within candidate; matched budget across arms | paired difference-in-differences (pre/post × arm) | trajectory-clustered bootstrap; budget parity asserted, not assumed | ≥ the `J_solve` n **per pass**; budget parity contract from `arena/training/matched_adaptation.validate_matched_configs` | give one arm more effective tokens/steps under an equal nominal budget |
| `J_ood` | `J_solve` on a **sealed** structural/domain shift pool, never used for selection or adaptation | **problem** in the shifted pool | same as `J_solve`, computed separately per shift axis, never pooled across axes | per-axis clustered CI; **no pooling** | `J_solve` n **per axis** | seal leakage (V7 C10: declared exposure 8,766 steps, real 21,632); shifting on an axis the language was tuned for |
| `J_search` | Expected verifier calls / node expansions / tool calls **conditional on solving** | **trajectory**, with the unsolved arm handled explicitly | median and IQR of counts on the **commonly-solved** subset; separately, the solve rate | rank-based paired test on the common subset; bootstrap over trajectories | ≥60 commonly-solved trajectories per arm for a stable median | solve fewer problems and look efficient; the dead `search_metrics.search_efficiency` scalarisation scores unsolved runs 0.0 and hides exactly this |
| `J_repair` | P(a trajectory that has taken a verifier-rejected step still reaches a verified solution) | **trajectory that actually failed a step** (a conditional population) | conditional proportion; denominator is *only* trajectories with ≥1 rejected step | Wilson on the conditional denominator, clustered by problem | ≥100 trajectories **with a failure** — this is the tightest sample constraint in the vector | never fail (denominator 0 ⇒ undefined, must not be scored as 1.0); or fail deliberately on easy steps to inflate the denominator |
| `J_cost` | Prompt+completion tokens, wall-clock, and verifier CPU per **solved** problem, and per **attempted** problem | **trajectory** | mean and 90th percentile of both normalisations, reported together | trajectory bootstrap | any n ≥ 30 for a usable point estimate; it is deterministic given the transcript | report only per-attempted (a language that gives up fast looks cheap) or only per-solved (a language that solves only easy problems looks cheap) |

### 2.2 Notes that make the table honest

**Trajectories are the cluster, steps are not.** A 20-step trajectory yields 20 step outcomes that
are not 20 independent observations — a wrong step at depth 3 determines the next 17. Every
step-level statistic in this design is either (a) collapsed to one trajectory-level number before it
reaches an estimator, or (b) estimated with the trajectory as the bootstrap resampling unit. The
V7 audit's L4 measured this cost concretely on a much weaker dependence structure — twin pairs,
ICC **+0.511**, design effect **1.61**, **effective n 14.9** where the instrument's own
`min_positives_for_gates` was 24. Step-within-trajectory dependence is far stronger than
twin-within-family dependence.

**The existing interval machinery is not clustered and must not be used at the item level.**
`arena/fitness/metrics.wilson_interval` assumes independent trials. At the *measured* twin ICC of
0.511 the design effect is 1.511 and the correct SE is **1.229×** the Wilson SE — Wilson intervals
on twin-clustered item data are about **19% too narrow**. On trajectory-nested step data the factor
is larger and unknown. V0 therefore uses `landscape.paired_comparison` for every comparative claim
and `wilson_interval` only for genuinely independent per-problem proportions.

**Direction and units are declared per dimension, not inferred.** `J_search` and `J_cost` are
MINIMIZE; the rest are MAXIMIZE. This matters because `fitness/pareto.Objective` already carries a
`Direction` and a `tolerance`, and a sign error there silently inverts the front.

---

## 3. Gates versus Pareto dimensions

### 3.1 Non-compensatory gates (elimination; never traded off)

A candidate failing either gate is **eliminated**, not down-weighted. This is `GOAL.md` §15's
`critical semantic failure ⇒ elimination` and `HAMILTONIAN_CHESS_META_GOAL.md` §4's invariant.

**Gate S — semantic survival.** Reuse `arena/fitness/gates.evaluate_gate_zero` unchanged. It
eliminates on any of: critical false accepts, canonical collisions, unresolved scope corruptions,
proof cycles, untracked definedness escapes, silent semantic losses, or **absent** roundtrip
evidence (`required_roundtrip_total <= 0` eliminates — fail-closed, already implemented).

*Known limitation, stated:* on the current genome this gate has an elimination rate of **0/120**
(§1). It is a live gate only for a genome that can express Layer B/C changes.

**Gate A — answer leakage.** The rendered-prompt adversary, non-compensatory, per candidate, on the
exact bytes the Solver receives.

The operating point below is **derived from `precondition_power.shortcut_gate_operating_characteristic`
and `shortcut_gate_min_n_eval`**, run in-process. The multiplicity that matters at EVAL is **5**
(`develop_and_freeze(top_k=3)` + 2 shallow models), not 64 — selection multiplicity is absorbed on
the family-disjoint DEV pool.

| n_EVAL | threshold | P(void a truly-clean language) | P(detect a true 0.60 leaker) | max observed accuracy that still clears |
|---|---|---|---|---|
| 200 | 0.55 | **0.9998** | 1.000 | 0.465 |
| 400 | 0.55 | **0.9937** | 1.000 | 0.490 |
| 400 | 0.60 | 0.2238 | 1.000 | 0.540 |
| **800** | **0.60** | **0.0019** | **1.000** | **0.559** |
| 800 | 0.55 | 0.8577 | 1.000 | 0.5075 |
| 1,600 | 0.55 | 0.2137 | 1.000 | 0.5206 |

**Two things this table says, both load-bearing:**

1. **A 0.55 leakage gate at n=400 is a dead gate in the opposite direction** — it eliminates a
   perfectly clean language with probability 0.9937, because the Bonferroni Clopper–Pearson upper
   bound on the best of 5 adversaries cannot get below 0.55 at that n. This is the *mirror image*
   of the V7 C3e failure (a threshold below its own statistic's null mean); the fix is the same
   discipline, applied in the other direction. The Phase 8 audit's headline "best frozen adversary
   anywhere **0.5625**" (`artifacts/reports/precondition_rendered_shortcut_audit.json`, 45 cells,
   EVAL 400 items / 200 families) is therefore *not* a pass of a 0.55 gate at n=400 and must never
   be reported as one.
2. **The V0 operating point is n_EVAL = 800, threshold 0.60, α = 0.05 Bonferroni over 5 frozen
   adversaries.** False-void 0.0019 per candidate; over a 44-candidate generation the family-wise
   false-void rate is 1 − 0.9981^44 = **0.080**, which is an acceptable search loss and is recorded,
   not hidden. Detection of a genuine 0.60 leak is 1.000.

Gate A costs **zero model calls**: every adversary is a deterministic function of `(prompt,
n_options)`.

### 3.2 Pareto dimensions

The surviving seven dimensions enter `arena/fitness/pareto.pareto_fronts` with explicit
`Objective(name, direction, tolerance)`. **No weights, no scalar.** Tolerance is set to one
estimator quantum (1/n) per dimension so that differences the estimator cannot represent do not
create spurious dominance — the direct fix for V7 C4 (*"the 0.10 threshold is unrepresentable at
n=24; the executed gate was 0.125"*).

Within-front selection uses the existing NSGA-II `crowding_distance`, which is already implemented
and tested.

### 3.3 The quality-diversity archive — behavioural descriptors

**None of this exists yet** (§1). V0 specifies the descriptors, not the implementation.

The archive is a MAP-Elites grid. Descriptors must describe **what the language does to the
Solver's behaviour**, not what the genome says about itself, because the seed population has already
been measured to be far less diverse than its gene values imply:
`artifacts/reports/precondition_parity_audit.json` gives
`e1_coverage_max_direction = 0.9860` for `L3_JSON_AST | L6_GRAPH_TRIPLES` at P20 (98.6% of state
bytes shared via ≥40-character spans) and `seqmatch_ratio = 0.8227` for
`L0_STRUCTURED_ENGLISH | L3_JSON_AST` at P09. **A genome-space archive would file two nearly
identical strings in two different niches.**

Four descriptors, each a measured behavioural quantity, each binned into 4 cells (256 niches):

| Descriptor | Definition | Why behavioural |
|---|---|---|
| **D1 — horizon profile shape** | sign and magnitude of the fitted slope of per-bucket completion rate against `log(horizon)` | the dimension the mission is about; two languages with the same `J_solve` and different slopes are genuinely different organisms |
| **D2 — failure locus** | median first-error depth ÷ median solution length | *where* the language breaks down, not how often |
| **D3 — search shape** | median branch count per solved trajectory | a language that solves by one long chain and one that solves by wide search occupy different niches |
| **D4 — surface distance from the incumbent** | 1 − `e1_coverage_max_direction` against `L0_STRUCTURED_ENGLISH`, computed by the existing span audit | the direct antidote to re-skinning; a candidate at 98.6% overlap with an archived elite **cannot** claim a new niche |

**Archive admission rule.** A candidate may occupy a niche only if it (a) passes Gates S and A, and
(b) has D4 ≥ 0.10 against every archived elite whose other three descriptors it shares. A candidate
that fails (b) *replaces* the incumbent elite only if it Pareto-dominates it; otherwise it is
recorded as a re-skin and discarded. **This rule exists specifically because the 98.6% measurement
says the failure it prevents has already happened once, in the seed population, undetected.**

---

## 4. How `J_horizon` is actually measured

### 4.1 Buckets, and the honest rule about them

Declared buckets: **H ∈ {1, 5, 10, 20, 50, full}**, where H is the number of *verified reasoning
steps in the reference solution*, not the number of tokens and not the number of model calls.

**The honest rule, binding:** *report only the buckets the data supports.* A bucket is reportable
only if it satisfies **all** of:

1. **n_solved ≥ 20 in both arms** — otherwise the completion rate has no usable interval.
2. **The bucket is not at a floor or a ceiling.** If either arm's completion rate is 0.00 or 1.00,
   the bucket carries no comparative information and is reported as `VOID_FLOOR` / `VOID_CEILING`.
   This reuses the logic and the vocabulary already in
   `game_r_formal_v1.select_frontier_level`, which returns exactly those verdicts.
3. **The threshold is representable at the bucket's n.** `precondition_power.representability`
   is called per bucket and its `all_thresholds_representable` flag is recorded. Measured: n=24 is
   **not** representable at 0.10 (the V7 C4 failure); n=40, 120, 200, 240, 400 **are** representable
   at all of 0.10 / 0.125 / 0.15; n=60 and n=100 are **not** representable at 0.125.
   **V0 therefore sizes every bucket at a multiple of 40.**

An unreportable bucket is recorded as unreportable. It is never silently dropped, never pooled into
a neighbour, and never replaced by a curve fitted through the buckets that survived. *Pooling two
buckets to reach n is granularity substitution and is forbidden.*

### 4.2 The five things measured per bucket

Per bucket, per arm, on the identical problem set:

1. **Completion rate** — P(verifier accepts a complete solution). Unit: problem. Paired McNemar
   vs the parent arm.
2. **First-error depth** — the index of the first step the verifier rejects, right-censored at the
   trajectory's end for trajectories that never err. Unit: trajectory. Compared by a paired
   sign/rank test on within-problem depth differences, **not** by a t-test on means (the
   distribution is censored and heavily skewed).
3. **Verified-step survival curve** — S(k) = P(the first k steps are all verifier-accepted),
   k = 1..H. Kaplan–Meier with problems as the unit; CI bands by problem-clustered bootstrap. This
   is the object the whole `J_horizon` claim is about, and it is *descriptive* — no significance is
   claimed from the curve itself.
4. **Branch count** — number of distinct explored continuations per trajectory (feeds `J_search`
   and descriptor D3).
5. **Repair rate** — `J_repair`, conditional on having erred, per bucket.

### 4.3 The primary `J_horizon` statistic

γ = Δ_long − Δ_short, where Δ_b = (completion rate of child) − (completion rate of parent) in
bucket b, computed on **disjoint problem pools**.

Because the pools are disjoint, Δ_long and Δ_short are independent, so
Var(γ) = Var(Δ_long) + Var(Δ_short), and the paired SE of each Δ_b follows the McNemar form
√(n10+n01)/n_b. The test is a two-sided z-test on γ with that SE, Holm-corrected across the
generation.

**γ > 0 with a CI excluding 0 is the mission's central claim.** γ ≈ 0 is the "advantage is flat"
outcome and γ < 0 the "advantage shrinks" outcome; `GOAL.md` §20 already declares both to be valid
scientific answers, and this design reports them identically.

### 4.4 What it costs to test γ — the numbers

Seeded simulation (40,000 replicates, `numpy` default_rng(20260908), discordance π_d = 0.30,
α = 0.05 two-sided, no clustering), cross-checked against
`precondition_power.required_n_pairs(0.80, p10, p01, 0.05) = 249` for the corresponding
single-difference at Δ=0.10:

| γ (interaction) | n per bucket | simulated power |
|---|---|---|
| 0.15 | 200 / **210** / 240 | 0.790 / **0.810** / 0.857 |
| 0.10 | 440 / 460 / **470** / 500 | 0.778 / 0.796 / **0.806** / 0.828 |
| 0.05 | 1,800 / **1,900** / 2,000 | 0.781 / **0.804** / 0.823 |

The simulation reproduces the analytic expectation exactly: **an interaction needs ≈2× the
per-bucket n of a main effect of the same size** (249 → ≈470), hence **≈4× the total sample**.

**This is the single most important cost fact in the design.** It is why `J_horizon` is measured
*descriptively with CIs* at L4 every generation, and tested *confirmatorily* only at L5, on a
champion, at a declared cadence — never on every candidate.

### 4.5 The test that detects a fake long-horizon task

The owner forbids manufacturing long-horizon tasks by concatenating unrelated micro-probes. A
prohibition without a detector is a policy; this is the detector. It runs on the **task generator's
output**, at zero model cost, before any Solver sees the pool, and it is a **precondition on the
pool**, not a diagnosis after the fact.

**The dependency-density test.** For a reference solution of H verified steps, build the
step-dependency DAG: an edge `i → j` exists iff step j's premises include an object, hypothesis or
fact *introduced or modified* by step i. This is computable from the verifier's own transition
record — it is exactly the information `arena/verifier` already produces to check a step, and it
requires no model.

Three statistics, all with hard preconditions:

| Statistic | Definition | Pass condition | What it catches |
|---|---|---|---|
| **T1 — reachability** | fraction of steps reachable from step 1 in the undirected dependency graph | **= 1.000** | k concatenated independent probes produce **k** connected components; a genuine derivation produces one. This alone kills naive concatenation. |
| **T2 — long-range dependency fraction** | fraction of edges with span (j − i) > 3 | **≥ 0.20** [PROPOSED] | a "chain" that is really H independent 1-step probes glued end to end has *all* edges of span 1 |
| **T3 — prefix-truncation damage** | P(a Solver-independent oracle that is given only steps 1..⌊H/2⌋ can still verify step H) | **≤ 0.10** [PROPOSED] | if the second half does not need the first half, the task is not long-horizon regardless of how it was built |

T1's threshold is exact and non-negotiable. T2 and T3 are **[PROPOSED]** thresholds and must be
calibrated on the first real trajectory world before they can void anything — calibrated on
*generator* output only, never on Solver results, so calibration cannot be tuned to a desired
answer.

**A fourth check, on the other confound.** Record ρ(H, prompt tokens) per pool. V7's L3 measured
ρ(level, prompt tokens) = **+1.0** and ρ(accuracy, tokens) = **−1.0**, i.e. its difficulty ladder
was perfectly confounded with length and *"accuracy-versus-level cannot be read as a
reasoning-difficulty curve"*. If ρ(H, tokens) > 0.9 in a pool, the pool is marked
`HORIZON_LENGTH_CONFOUNDED` and `J_horizon` from it is reported as descriptive only. §7.1 gives the
design that breaks the confound.

---

## 5. The multi-fidelity evaluation ladder

Successive halving. Generation size **N = 64 proposals** [PROPOSED].

### 5.1 Cost model, and its provenance

All model-call costs are priced from
`precondition_power.latency_fit()`, a least-squares fit over the **nine measured calls** in
`MEASURED_ARM_PROFILES`:

```
seconds ≈ −2.922 + 2.105 × (prompt_tokens / 1000)     max |residual| 1.26 s, 1.62–1.99 ms/token
```

Anchor points from that fit against the measurements it was fitted to:
5,183 tok → 8.0 s modelled vs **8.4 s measured**; 12,093 tok → 22.5 s modelled vs **21.9 s
measured**; the measured range is 8.4 s @ 5,183 tok to 36.0 s @ 18,147 tok.

**Three caveats, all binding:**

1. **The Solver these were measured on no longer exists.** `qwen38-rvn` (digest `25eb57cb…`) was
   deleted from the local Ollama at 11:43 on 2026-09-08 and replaced by `qwen3.6:27b-mlx`
   (`docs/PHASE8_SALVAGE_HANDOFF.md` §1). Every hour figure below is an **order-of-magnitude
   planning number and must be re-measured** before any budget is authorised.
2. **Two costings are given for every trajectory level.** *Conservative* re-prices the full prompt
   at every step. *Prefix-cached* charges the measured `ROTATED_CALL_SECONDS = 2.0 s` for every step
   after the first, which is the measured cost of a call that hits Ollama's KV-cached prefix. Real
   append-only rollouts sit between them; which one holds is **unverified** for multi-step rollouts.
3. Trajectory prompts are modelled as **3,000 base tokens + 250 per step** [PROPOSED]. Under that
   model: H=5 → 22.2 s (11.4 s cached); H=10 → 57.6 s (21.4 s); H=20 → **167.9 s (41.4 s)**;
   H=50 → 814.4 s (101.4 s). **H=50 costs 4.9× H=20 conservatively and 2.5× cached** — this is why
   the H=50 bucket is not in the routine ladder.

### 5.2 The ladder

Survivor counts are **[PROPOSED]**; every cost figure is arithmetic on the numbers above. The parent
arm is **shared across the whole generation** — every child is compared against the same parent rows
on the same task ids, which is legitimate reuse under `game_r_formal_v1.cache_identity` and is
recorded as `CacheScope.SAME_CONDITION_REUSE`, the scope that exists precisely to distinguish this
from contamination.

| Level | in → out | model calls | hours (sequential) | hours (prefix-cached) | What it can rule out | What it **cannot** rule out |
|---|---|---|---|---|---|---|
| **L0** static semantic / conformance | 64 → 45 | **0** | ~0 (≈2 min CPU each) | — | truth-altering genes, roundtrip loss, canonical collisions | anything about a Solver |
| **L1** cheap deterministic diagnostics | 45 → 44 | **0** | ~0 (string statistics) | — | answer leakage at 0.60 with false-void 0.0019 (§3.1); degenerate renderers | whether the language helps; whether it helps *more* at depth |
| **L2** zero/few-shot Solver scout | 44 → 16 | **1,800** | **4.0** | 4.0 | gross Solver-facing breakage: invalid-response rate, answer-share collapse, position anchoring | any horizon claim; any effect smaller than ~0.15 at n=40 |
| **L3** short matched adaptation | 16 → 8 | **1,360** | **3.0** | 3.0 | languages that cannot be learned at all under a matched budget | matched *training* effects; long-horizon behaviour |
| **L4** long-horizon trajectory arena | 8 → 4 | **9,360** | **19.3** | **5.6** | the descriptive horizon profile: survival curves, first-error depth, repair, branch counts, with CIs | any γ claim — at n=40/bucket the power is **0.133** for γ=0.10 and **0.236** for γ=0.15 (§4.4 simulation). Descriptive only; **no significance may be claimed here** |
| **L5** full matched training + fresh promotion pool | 4 → 2 | **26,250** | **55.4** | **15.4** | γ ≥ 0.15 at power 0.81; `J_learn` under matched training; performance on a pool never used for selection | model-specificity; domain transfer |
| **L6** cross-model / cross-domain replication | 2 → 1 | **31,500** | **66.5** | **18.5** | "the effect is an artefact of one Solver" — `GOAL.md` §16's `ROBUST_CANDIDATE` bar | `RSTAR_0_1`, which needs *multiple meaningfully distinct* Solver families and a declared universe |
| **Total (all levels)** | 64 → 1 | **70,270** | **148.4** | **46.5** | | |

### 5.3 The arithmetic, spelled out

- **L2**: 44 children × 40 items + 40 parent items = **1,800 calls** × 8.0 s = **4.0 h**.
  n=40 is chosen because `representability(40)` reports **all of 0.10 / 0.125 / 0.15 representable**,
  quantum 0.025 — unlike n=24 (quantum 0.0417, 0.10 unrepresentable), which is the exact V7 C4 trap.
- **L3**: 16 × 40 × 2 passes + 40 × 2 = **1,360 calls** × 8.0 s = **3.0 h** (eval calls only;
  adaptation compute is accounted separately and must be matched via
  `matched_adaptation.validate_matched_configs`).
- **L4**: buckets H ∈ {1, 5, 20}, n = 40 problems each, 8 children + 1 shared parent = 9 arms:
  9 × 40 × (1 + 5 + 20) = **9,360 calls**; 9 × 40 trajectories at each H costs
  360 × (3.4 + 22.2 + 167.9) s = **19.3 h**, or 360 × (3.4 + 11.4 + 41.4) s = **5.6 h** prefix-cached.
- **L5**: buckets H ∈ {5, 20}, n = **210** per bucket (the γ=0.15 power point from §4.4),
  4 children + 1 shared parent = 5 arms: 5 × 210 × (5 + 20) = **26,250 calls**; **55.4 h** /
  **15.4 h** cached.
- **L6**: 2 survivors × 2 further Solver families on the identical frozen pool = **31,500 calls**.

### 5.4 Promotion rules

- **L0 → L1**: Gate S pass. Binary, non-compensatory.
- **L1 → L2**: Gate A pass at (n_EVAL=800, threshold 0.60). Binary, non-compensatory.
- **L2 → L3**: keep ⌈m/2⌉ ranked by the composite screen, **plus every candidate whose screen CI
  overlaps the retained set's minimum**. The screen is validity rate, answer-share, position
  invariance and single-step accuracy — and it is **explicitly a screen, never a fitness claim**.
- **L3 → L4**, **L4 → L5**: halve, same overlap rule, ranked on the Pareto front rank then
  crowding distance (both already implemented).
- **L5 → L6**: only a candidate whose Holm-adjusted γ test rejects, on the fresh promotion pool.

**The screen-validity audit, mandatory and recurring.** Every generation, record Spearman ρ between
the L2 ranking and the L4 ranking of the candidates that reached L4, using the existing
`landscape.spearman`. This is the same `rank_stability_spearman` quantity `landscape_summary`
already computes. **If ρ is not distinguishable from 0 over three consecutive generations, the L2
screen is retired and its budget moves to L4.** A cheap screen that does not predict the expensive
level is not a cheap screen; it is noise with a schedule. Stating this in advance is what stops it
becoming a post-hoc excuse.

### 5.5 What a generation actually costs

L5 and L6 are **not** run every generation. A routine generation is L0–L4:

**12,520 model calls, 26.4 h sequential, 12.7 h prefix-cached, ≈6.6 h at four concurrent workers.**

A promotion event (L5+L6) adds **57,750 calls / 122 h sequential / 34 h cached** and is triggered by
a declared rule — [PROPOSED]: a candidate that has held an L4 Pareto-front position for three
consecutive generations — not by a per-generation schedule and never by an interesting-looking L4
result. *Choosing when to run the confirmatory level after seeing the exploratory one is the
mechanism by which a search loop manufactures a false positive.*

---

## 6. Game R as the local causal assay

When a mutation looks good, the question is not "is the child good" but **"did μ cause the
improvement"**. `HAMILTONIAN_CHESS_META_GOAL.md` §3 demotes Game R to exactly this role. The
machinery already exists and is dry-run green; V0 specifies its use, not a rewrite.

**Design.**

- **Matched by construction.** `game_r_formal_v1.assert_arena_parity` on every arm pair before any
  call: one envelope signature, one answer protocol, exact canonical recovery per arm, distinct
  rendered bytes. It raises `ParityViolation` both when arms disagree on content **and when they
  agree on bytes** — the second condition is what catches a "mutation" that changed nothing, and it
  is the enforcement point for the 98.6%-overlap problem at assay time.
- **Paired.** Parent and child answer the **same task ids** — `paired_outcomes` intersects on
  `task_id` and returns `(outcomes_a, outcomes_b, family_ids)`.
- **Clustered by trajectory.** `compare_arms` → `landscape.paired_comparison`, whose bootstrap
  resamples **clusters**, not items. For trajectory data the cluster key is the *problem*, and
  `family_id` carries it.
- **Exact.** McNemar exact on the discordant pairs (`landscape.mcnemar_exact`), not a χ² with a
  continuity correction.
- **Corrected.** Holm across the generation's k comparisons. Holm is valid under arbitrary
  dependence, which matters because all k children share one parent arm and their comparisons are
  therefore positively correlated.
- **Equivalence, not just difference.** When the test does not reject, run
  `precondition_power.equivalence_test(n10, n01, n, region=0.125)` — the project's own declared
  practical-equivalence region. A non-rejection is reported as `NO_EFFECT_DETECTED` or
  `PRACTICALLY_EQUIVALENT`, never as "no difference". Note the module's own warning: when
  `d/n < region` the region is conditionally unattainable and the verdict is "parity given the
  observed discordance", not an unconditional claim.
- **Fail-closed.** `compare_arms` returns `NO_COMMON_SET` on an empty intersection and reports no
  number, so nothing can be read as equivalence.

**The n needed** (all from `precondition_power`, run in-process, target power 0.80, π_d = 0.30):

| Effect Δ on `J_solve` | α = 0.05 (single assay) | α = 0.0125 (Holm, k=4) | α = 0.005 (Holm, k=10) |
|---|---|---|---|
| 0.05 | 975 | 1,369 | 1,628 |
| 0.075 | 438 | 612 | 725 |
| **0.10** | **249** | **344** | **408** |
| 0.15 | 112 | 153 | 180 |
| 0.20 | 61 | 84 | 98 |

If the pool has twin structure (two items per family), use the clustered numbers instead — at
Δ=0.10, ICC=0.5, α=0.0125 the requirement is **191 families = 382 items**, versus 172 families = 344
items at ICC=0.

**Consequence, stated plainly:** at L4's n=40 per bucket, a per-mutation causal claim on `J_solve`
is impossible for any effect below ≈0.30. **L4 produces effect estimates with intervals, not
verdicts.** A causal verdict about μ requires L5's n. The temptation to read a verdict off L4 is the
single largest threat to this design, and §7 says why.

---

## 7. HOW THIS FITNESS COULD LIE TO US

Seven failure modes, each with the detector that is supposed to catch it and — honestly — whether
that detector actually exists.

### 7.1 Horizon confounded with prompt length

**The lie:** "advantage grows with horizon" when what grows is prompt length, and the winning
language is simply the one that stays inside the model's effective context.

**Why it is the top risk:** it has already happened here. V7's L3: ρ(level, prompt tokens) = **+1.0**,
ρ(accuracy, tokens) = **−1.0** across all three levels. And the compression ratios are enormous —
`MEASURED_ARM_PROFILES` shows Compact Symbolic at 5,183 tokens where JSON AST needs 12,093 for the
*same mathematics*, a 2.33× difference.

**Detectors:**
- ρ(H, prompt tokens) per pool, with a `HORIZON_LENGTH_CONFOUNDED` mark above 0.9 (§4.5). *Exists as
  a specification; the measurement is trivial.*
- **A token-matched horizon contrast** [PROPOSED, not built]: construct short-horizon problems whose
  prompts are padded with verified-but-irrelevant context to the token length of the long-horizon
  problems. If the advantage tracks tokens rather than steps, it survives the padding. This is the
  only design here that actually separates the two, and it is not implemented.
- Report `J_horizon` **jointly with** the token profile per bucket, always. Never alone.

### 7.2 A language that wins by being shorter

**The lie:** a compression gene wins on `J_solve` because it fits more problem into the budget, and
this is reported as a reasoning-representation finding.

**Detectors:**
- `J_cost` is a first-class Pareto dimension, so a shorter language does not get to hide its
  mechanism — but Pareto membership does not *explain*, and a shorter-and-better candidate will sit
  on the front regardless.
- **The real control is a token-matched arm** [PROPOSED, not built]: re-run the child at the
  parent's token budget by truncating the child's *context window*, not its content. If the
  advantage vanishes, it was budget.
- `game_r_formal_v1` already **refuses to truncate** (`TokenAccountingRefusal`: *"V3 truncated its
  inputs and V4 voided rows on a character heuristic; this harness will not guess a token count"*).
  A budget-matched arm therefore has to be built as a first-class condition, not improvised.

### 7.3 Selection noise across a generation

**The lie:** the generation's best candidate is genuinely best, when max-over-64 of a noisy statistic
has an expectation well above the null mean.

**Precedent:** V7 C3e — a max over 7 rules × 2 polarities with the ancestor's Bonferroni and
Clopper–Pearson correction deleted, giving E[max] = 0.744 against a 0.75 threshold, *crossed by
pure noise 67% of the time*. And C3 — an observed "best" of 0.6667 that was **below** the clustered
null mean of 0.659–0.723.

**Detectors:**
- Holm across the generation, always, k = number of children compared.
- **Selection and qualification never share rows.** L4 selects; L5 qualifies on a fresh pool. This is
  V7's L1 defect (*"selection and qualification share the same 24 rows"*; level choice flipped 55.4%
  under resampling) and V3's abandoned SCOUT pool, reinstated.
- **Publish the null.** Every generation, record the max-over-children Δ obtained by permuting the
  child labels within problems — the empirical null for the generation's own max statistic. The
  permutation machinery exists (`rendered_prompt_adversary._permutation_null`,
  `_permute_within_families`) and needs porting to the trajectory setting.

### 7.4 The archive rewarding diversity that is only re-skinning

**The lie:** the archive fills, diversity metrics rise, and the population is one serialisation
wearing 256 hats.

**Precedent, measured:** 98.6% shared state bytes between `L3_JSON_AST` and `L6_GRAPH_TRIPLES`;
0.8227 sequence-similarity between `L0_STRUCTURED_ENGLISH` and `L3_JSON_AST`
(`artifacts/reports/precondition_parity_audit.json`). The Phase 8 handoff states the consequence:
*"the eight seed 'languages' are not eight independent points in design space; several are one
serialisation behind different key names."*

**Detectors:**
- Descriptor D4 and the archive admission rule (§3.3) — behavioural descriptors plus a hard surface
  distance floor.
- `assert_arena_parity`'s "arms agree on bytes ⇒ `ParityViolation`" check at assay time.
- `game_r_mutant_audit.structural_near_duplicate_pairs`, which currently reports `[]` over 120
  mutants and should be run every generation as a population-level sentinel.

### 7.5 Reward hacking of the verifier

**The lie:** the language finds a way to say something the verifier accepts that is not a proof.

**Why the risk is structural, not hypothetical:** `HAMILTONIAN_CHESS_META_GOAL.md` §4 grants Layer C
genuine freedom to make derivable relations explicit, and the boundary — *"may expose only what is
deterministically derivable … never the solution label, a future proof step, an oracle value, or an
unverified inference"* — is a semantic line, not a syntactic one.

**Detectors:**
- `arena/training/verified_eval.FailureClass.CONTENT_MISMATCH` exists for exactly this: *"legal,
  well-formed id, but the action's mathematical content differs from the legal action bearing that
  id. This is where the hollow-action attack lands."*
- `arena/assurance/mutations.py` and `arena/assurance/side_channels.py` (a mutation-testing suite and
  a side-channel audit) are the existing machinery.
- **Weakest link, stated:** a *trajectory* verifier that accepts a multi-step solution has a far
  larger attack surface than a single-step transition checker, and none of the above has been run
  against one, because no trajectory world exists. `J_solve` is exactly as trustworthy as that
  verifier, and V0 cannot bound how trustworthy that is.

### 7.6 `J_repair`'s conditional denominator

**The lie:** a language that never errs on the easy pool gets an undefined or vacuous `J_repair`,
which is silently read as good.

**Detector:** the denominator is reported with the numerator, always. `J_repair` on fewer than 30
erring trajectories is reported as `INSUFFICIENT_FAILURES`, never as a number, and never as 1.0.
The same rule applies to `J_search`, whose common-solved subset can shrink to nothing when the arms
diverge.

### 7.7 Reading a verdict off the exploratory level

**The lie:** L4 shows a large γ, the run is stopped there, and the number is reported.

**Why it is likely:** L4 costs 19.3 h and L5 costs 55.4 h, and L4 already produces a
publishable-looking curve. Measured power of the L4 design (200,000-replicate simulation, π_d=0.30,
α=0.05):

| n per bucket | γ=0.10 | γ=0.15 | γ=0.20 |
|---|---|---|---|
| **40 (L4)** | **0.133** | **0.236** | **0.384** |
| 60 | 0.166 | 0.321 | 0.523 |
| 120 | 0.293 | 0.572 | 0.823 |
| **210 (L5)** | 0.464 | **0.811** | 0.969 |
| 470 | 0.803 | 0.989 | 1.000 |

An L4 γ that "looks big" is what a 0.13-power estimator produces when it happens to be right —
and, more often, what it produces when it is wrong in the other direction. L4 rejects at γ=0.10 in
about one run in eight; the sign of the estimate it reports is close to a coin flip.

**Detector:** L4 output carries a machine-readable `confirmatory: false` flag and a
`power_at_declared_effect` field computed by `precondition_power`. Any report that quotes an L4 γ
without both is malformed. This is a convention, and conventions are the weakest kind of detector —
which is why the promotion rule in §5.5 is stated in advance and tied to generations survived, not
to effect size observed.

---

## 8. V0 scope — what is deliberately excluded

Being ruthless about scope is more useful than being complete.

**In V0:** the vector's definitions; the two gates and their operating points; the bucket rule and
the fake-horizon detector's T1 (exact); the ladder and its arithmetic; the Game R assay design; the
archive's descriptors.

**Explicitly not in V0:**

- **Any implementation.** No code is written by this document.
- **The trajectory world itself.** It does not exist. `HAMILTONIAN_CHESS_META_GOAL.md` §6 names it
  the highest-priority missing substrate, and this fitness is unmeasurable without it.
- **A trained surrogate.** The schema for its training data is `docs/LANGUAGE_FITNESS_MEMORY.md`;
  nothing is fitted.
- **Calibrated T2/T3 thresholds**, the token-matched horizon contrast, and the budget-matched arm.
  All three are named as [PROPOSED] and are the highest-value things to build after the world.
- **The H=50 and "full solution" buckets.** Priced (4.9× H=20 conservatively) and deferred.
- **`GOAL.md` §15's `E_invalid` and `R_robust` as separate dimensions.** `E_invalid` is folded into
  L2's validity screen and into `J_solve`'s fail-closed scoring (`SCORED_STATUSES` counts every
  solver-caused failure as incorrect rather than dropping it). `R_robust` is not a dimension but a
  **level** — L6.

## 9. Before this may govern anything

1. Re-measure the latency and token profile on the current Solver. Every hour in §5 is priced on a
   model that was deleted on 2026-09-08.
2. Build the trajectory world, then calibrate T2/T3 on generator output only.
3. Run L1's Gate A at n_EVAL=800 against the *actual* renderers to confirm the false-void rate.
4. Measure, do not assume, L0's elimination rate on the widened meta-genome. It is currently 0/120.
5. Preregister before any confirmatory claim. `HAMILTONIAN_CHESS_META_GOAL.md` §7:
   exploratory search inside the loop is expected; a *claim* requires a frozen protocol.
