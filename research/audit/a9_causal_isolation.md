# A9 — Representation causal isolation and counterfactual balancing

**Auditor 9 of 9 · V7 total forensic audit, Part H.**
Read-only static + arithmetic analysis. **Zero model calls, zero GPU, laptop only.** No existing
file was modified; all new files are under `research/audit/a9_causal_isolation.md` and
`research/audit/a9_causal/`. V7 was not re-run and no threshold was changed.

Environment: worktree
`/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/phase-6-parallel-setup-9c6068`,
interpreter `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`,
`import arena` resolves to
`/Users/moheet/…/phase-6-parallel-setup-9c6068/arena/__init__.py` (verified).

## Reproduction

```
P=/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python
S=<scratchpad>
$P -m research.audit.a9_causal.build_bank            $S/bank.pkl
$P -m research.audit.a9_causal.pairs                 $S/bank.pkl research/audit/a9_causal/pairs_report.json
$P -m research.audit.a9_causal.surface_shortcut      $S/bank.pkl research/audit/a9_causal/surface_shortcut.json
$P -m research.audit.a9_causal.generator_diff        $S/bank.pkl research/audit/a9_causal/generator_diff.json
$P -m research.audit.a9_causal.pool_feasibility      $S/bank.pkl research/audit/a9_causal/pool_feasibility.json
$P -m research.audit.a9_causal.prompt_visible_audit  $S/bank.pkl \
      artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json \
      research/audit/a9_causal/prompt_visible_audit.json
$P -m research.audit.a9_causal.margin_calibration
```

`build_bank` materialises the frozen DEV pool by calling `fitness_v5.build_dev_pool` unmodified:
**864 probes in 5.2 s**, exactly matching the 864 rows in the V7 artifact.

---

# Q1 — Does V7 vary representation? **No. One representation. `CONFIRMED`.**

**EVIDENCE (code).** `arena/experiments/fitness_v7.py:946`

```python
control = equal_information_genome()
```

`equal_information_genome` (`arena/experiments/fitness_v5.py:532-543`) defaults to
`surface_id = CONTROL_SURFACE = "L3_JSON_AST"` (`fitness_v5.py:70`). `control` is the **only**
genome ever constructed in V7 and is passed to both `evaluate` call sites
(`fitness_v7.py:1012`, `fitness_v7.py:1074`). `grep -n "genome\|surface"` over
`arena/experiments/fitness_v7.py` returns exactly one genome construction (line 946); the module
never imports or calls `v5_founders()` (which would give the eight founders,
`fitness_v5.py:544-548`).

**EVIDENCE (artifact).** `artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json`

```
control_candidate = "V5E_L3_JSON_AST"
rows              = 864
candidate_id      = Counter({'V5E_L3_JSON_AST': 864})
genome_hash       = Counter({'a81adb9692f6da2eeb6db74447ea28534923371dd06e575fc4b6e680383fa697': 864})
```

**Definitive answer: V7 renders and scores exactly ONE candidate representation, on 100 % of its
864 rows.** The number of representations *compared* is **1**; the number of representation
*contrasts* is **0**. Semantics, visible information, action alternatives, ordering, tokenizer,
prompt, Solver and controller are all held fixed — trivially, because there is nothing to hold them
fixed *against*. `assert_information_parity` (`fitness_v4.py:1167`) is never called from V5 or V7
(`grep`: only `fitness_v4.py`, `fitness_v4_preflight.py`, `game_r_formal_v1.py`, tests) — with one
candidate it would be vacuous anyway.

V7's own docstring is candid about this: it describes itself as a change to "scoring and
selection", inheriting "probe bank, mechanisms, ladders, arms, prompt template … " from V5. It
never claims to vary R. The defect is not in V7's self-description; it is in how V7's verdict has
been read.

---

# Q2 — If nothing varies, why is V7 blocking Game R?

**Trace** (`fitness_v7.py:1000-1145`):

1. For each `mechanism ∈ MECHANISMS` and each `level ∈ 0..3`, `evaluate(root, control, cell, …)`
   is run — 72 probes per mechanism, one candidate.
2. `select_frontier_level(accuracies)` (`:677-713`) requires `L0 ≥ 0.90`, then picks the level in
   1..3 minimising `|acc − FRONTIER_TARGET|` (0.775, derived), and voids on the `[0.35, 0.85]`
   band.
3. `qualify_mechanism(summary, audit, q0)` (`:714-770`) applies nine gates at that level, two of
   them shortcut gates: `shortcut_absolute` (`best_shortcut ≤ 0.75`, V5's
   `QUALIFICATION_RULE["shortcut_rule_max"]`, `fitness_v5.py:225`) and `shortcut_margin`
   (`positive − best_shortcut ≥ 0.10`, `fitness_v7.py:175`).
4. `instrument_qualified = len(selected) >= QUALIFICATION_RULE_V7["minimum_qualified_mechanisms"]`
   (= 2, `fitness_v5.py:226`) — `fitness_v7.py:1170-1171`.

**The blocked object is `instrument_qualified`, which is a property of the TASK BANK, not of any
representation.** The founder tournament is gated on it by the programme's own rule
(`docs/FITNESS_V7_RESULT.md` §6: "the gate needs 2 qualified mechanisms and got 0").

**The assumption it rests on:** *a mechanism whose shortcut-vs-solver margin is small under the
control representation cannot support a between-representation comparison under any
representation.* That assumption is (a) never stated as a premise anywhere in the code or specs,
and (b) **false as measured** — see Q9/F1: the leading shortcut is itself representation-dependent
(0.5000 in six founder surfaces, 0.8333 in two, on the same cell).

---

# Q3 — Is V7 a pre-test for task usability rather than evidence about R? **Yes. `CONFIRMED`.**

Every quantity V7 gates on is a function of `(mechanism, level, solver, canonical serialization)`
with the representation held at a constant. `positive_accuracy`, `best_shortcut_accuracy`,
`destroyed_accuracy`, `position_invariance`, `largest_answer_share` are all measured at
`V5E_L3_JSON_AST` and nowhere else. There is no representational factor in the design, hence no
representational contrast, hence no term in the analysis that could carry a representation effect.

The honest description of the V7 result is therefore: **"under the L3_JSON_AST control surface and
the qwen38-rvn solver, 0 of 3 candidate task mechanisms met the preregistered usability criteria."**
That is a screening result about *tasks*. Any statement of the form "Game R is blocked" /
"`RSTAR_NOT_IDENTIFIED` stands" is a statement about the representation hypothesis that this
experiment contains no data on. `docs/FITNESS_V7_RESULT.md` §6 comes close to the right framing —
"on this probe bank and this solver, no mechanism supports a Game-R comparison" — but
`docs/PROJECT_STATUS.md:290, 323` and the `V7_SHORTCUT_DOMINATED` sentinel are read downstream as
evidence about R. They are not.

---

# Q4 — Is the 10-point rule derived from the objective? **No. Instrument-local. `CONFIRMED`.**

**GOAL.md.** `grep -in "shortcut|margin|10 point|0\.10"` over `GOAL.md` returns exactly two hits:
line 455 (`shortcut audits`, one item in the Experimentalist's checklist) and line 887
(`known shortcuts`, an item in the historical-memory list). **`GOAL.md` contains no threshold, no
margin, and no requirement that a Solver outperform all shallow shortcuts by any amount.** The
nearest normative text is `GOAL.md:446-460`:

> Determines whether a proposed measurement actually measures the intended mathematical capability.
> … `positive controls / relation-destroyed negative controls / counterfactual tests /
> position/order invariance / shortcut audits / ceiling/floor analysis / response-validity
> analysis`

That mandates *that* a shortcut audit exist, not *what* it must show. Nothing derives "beat ALL
shallow shortcuts by 10 points".

**Where 0.10 actually comes from.** `docs/FITNESS_V7_PREREGISTRATION.md:71-74`:

> at n = 24 the binomial standard error near 0.8 is ≈ 0.082, so a margin below one standard error
> could not distinguish a solver from its own shortcut.

That is (i) instrument-local, (ii) preregistered before the result — to its credit — and (iii)
**mis-specified for the statistic it gates**. `best_shortcut_accuracy` is `worst_score` =
`max` over seven rules *and their negations* (`fitness_v5.py:828-829`). The quoted 0.082 is the SE
of the *solver's* accuracy, not the sampling distribution of a maximum of 14 correlated estimates.

**Measured null (`research/audit/a9_causal/margin_calibration.json`).** For a cell with 12 families
whose polarity is *perfectly unbiased* (each family lands 0-of-2 or 2-of-2 with p = ½ — the
structure `relabel` forces, see Q11):

| rules maximised over | E[best-of-rule-or-negation] | P(best > 0.6667) | P(best > 0.75) |
|---|---|---|---|
| 1 | **0.6128** | 0.146 | 0.039 |
| 2 | 0.6612 | 0.271 | 0.076 |
| 3 | 0.6890 | 0.377 | 0.111 |
| 5 | 0.7226 | 0.546 | 0.179 |

A generator with **zero** shortcut bias produces `best_shortcut_accuracy ≈ 0.61–0.72` on this bank
size. `shortcut_rule_max = 0.75` therefore sits barely above the null mean, and requiring a fixed
+0.10 above a statistic whose null mean is itself 0.61–0.72 is not a one-standard-error test of
anything: it is a test whose null hypothesis was never characterised. `transitive_dependency` L3
failing by 0.017 (`docs/FITNESS_V7_RESULT.md` §4) is inside this uncharacterised bias.

**Verdict:** the 10-point rule is **instrument-local, not derived from the scientific objective**,
and its stated justification does not match the statistic it is applied to.

---

# Q5 — Could the design REMOVE or BALANCE the cue while keeping the mathematics?

Assessed per mechanism against the actual generator code. Short answer: **yes for two of the three
leaks, and one of them requires no code change at all — only measuring the right text.**

## (a) `formal_expression_depth` — `first_mentioned_in_state`: the cue is *not in the prompt*

`_formal_family` (`fitness_v5.py:376-397`) builds the counterfactual with
`relabel(formal.target, left, right)` (`:382`). `relabel`
(`arena/environments/formal_structural.py:181-203`) swaps the two identities **everywhere in the
target**. Any *antisymmetric* surface statistic therefore flips exactly with the answer.

But `build_state` (`formal_structural.py:339-352`) also emits an `objects` block built from
`sorted(set(identifiers))` — answer-independent, byte-identical across the twin. Whether
`first_mentioned_in_state` leaks depends entirely on **which block the serializer emits first**:

* `canonical_json(state.to_dict(...))` sorts keys, so `"goal"` (offset 106) precedes `"objects"`
  (offset 2289) — first mentions land inside the goal and swap.
* Every phenotype renderer that emits `objects` before `goal` pins the first mentions to the sorted
  object list.

**Measured (`research/audit/a9_causal/generator_diff.json`), one family of `formal_expression_depth`
L2, offsets in the actual prompt bytes:**

```
ORIGINAL        expected 0 | first "f12"=2564  first "f13"=2944
COUNTERFACTUAL  expected 1 | first "f12"=2564  first "f13"=2944     ← identical
canonical record:  "goal" at 106, "objects" at 2289, first "f12"=468, first "f13"=1408  ← swapped
```

Across all 12 cells, `prompt_first_offsets_invariant = 12/12 families` — **in the representation
V7 actually shipped, `first_mentioned_in_state` is constant across every twin, in every cell.**

So the cue is already removed. Nothing needs to be built; the audit needs to read
`build_prompt(genome, probe)` instead of `canonical_json(probe.state.to_dict(...))`
(`fitness_v5.py:798`). See Q9/F1 for the consequence.

## (b) `formal_expression_depth` — `more_frequent_in_state`: a real leak, balanceable by filter

This one *is* in the prompt (0.8750 at L1/L3, 0.6667 at L0/L2, identical in canonical and prompt).
`relabel` preserves the token *multiset* but swaps the *per-identifier* counts, and in real Lean
goals the deepest identifier tends to recur more.

The cue vanishes on any source state where the two identities occur **equally often** — then the
rule predicts the same option for both twins and the family scores exactly 1 of 2. Those counts are
already computed inside `structural_features` (`formal_structural.py:161-183`), so this is a
one-predicate eligibility filter in `load_formal_states`, not a redesign.

**Measured over the whole eligible source pool (`pool_feasibility.json`), 104 length-eligible
states:**

| stratum (level) | states | ties (`n_deep == n_runner`) | deeper-more | deeper-fewer | balanced families constructible | need |
|---|---|---|---|---|---|---|
| shallow (L1) | 34 | 4 | 29 | 1 | 4 + 2·1 = **6** | 12 |
| medium (L2) | 34 | 10 | 19 | 5 | 10 + 2·5 = **20** | 12 |
| deep (L3) | 36 | 8 | 24 | 4 | 8 + 2·4 = **16** | 12 |

**At L2 — the level V7 actually selected — and at L3, a generator constraint that drives
`more_frequent_in_state` to exactly 0.5000 is feasible from the existing corpus with families to
spare. Only L1 is short.** The mathematics is untouched: these are real Lean goals with a unique
deepest identifier either way.

## (c) `transitive_dependency`

Prompt-visible leaks: `first_mentioned_in_state` 0.5000 (invariant offsets), `more_frequent_in_state`
0.8333 / 0.6250 / 0.5417 at L1/L2/L3. The count asymmetry comes from `build(attached, other, …)`
(`fitness_v4.py:527-540`) laying the attached chain out first and then re-shuffling with the same
salt (`_shuffled`, `fitness_v4.py:260-262`), so the two chains are not exchangeable. Balancing here
means making `build` symmetric in the two chains — a local change, not a mechanism discard.
Family-level polarity is already near-balanced: `more_frequent_in_state` is 1-of-2 in **11 of 12**
families at L3 (`pool_feasibility.json`), so the residual 0.5417 is one family's worth of noise.

## (d) `precondition_conjunction`

Nothing to remove — already 0.5000. See Q11.

---

# Q6 — Balancing vs discarding

**Case for discarding.** A mechanism whose truth is *inherently* correlated with a surface
statistic is not measuring reading; balancing by filtering shrinks the pool and can select an
unrepresentative slice of real mathematics (here: keeping only Lean goals where the deepest and
runner-up identifiers recur equally often is a real distributional restriction, and it is on the
task-generation side of the sealed-holdout boundary, so it must be preregistered).

**Case for balancing.** Discarding is only warranted if the confound is a property of the
*mathematics*. Here it demonstrably is not:

* the largest leak (`first_mentioned_in_state`, the feature named in **both** VOID_SHORTCUT
  verdicts in `docs/FITNESS_V7_RESULT.md` §1) is a property of the **serializer used by the audit**,
  and is absent from the shipped prompt (Q5a);
* the residual leak (`more_frequent_in_state`) is balanceable from the existing corpus at the
  selected level (Q5b);
* a third mechanism in the same bank is already balanced by construction (Q11).

**Position.** Discarding is not justified on the current evidence. The correct order of operations
is: (1) fix the audit to measure the Solver's own bytes and re-read the existing frozen rows —
**this costs zero model calls**; (2) apply a preregistered balancing constraint to the two
generators; (3) only then, if a mechanism still cannot be balanced, discard it. Discarding all three
mechanisms on a measurement taken from a text nobody was shown is the largest single error in the
V7 chain.

---

# Q7 — Matched pairs where the MATHEMATICS changes and the shortcut is held constant

Operationalised exactly as V5's audit arithmetic implies: a pair of positive probes `(p, q)` with
`rule(p) == rule(q)` and `expected_index(p) != expected_index(q)`. Such a pair contributes exactly
1 correct of 2 — the feature is uninformative on it. Counted over the materialised 864-probe bank
(`research/audit/a9_causal/pairs_report.json`); positives per cell = 24 (12 families × ORIGINAL +
COUNTERFACTUAL).

## Counts for `first_mentioned_in_state` on `formal_expression_depth` (the brief's target)

| cell | within-family Direction-A pairs | across-family Direction-A pairs | rule score |
|---|---|---|---|
| L0 (explicit) | **12** | 132 | 0.5000 |
| L1 | **0** | **0** | 1.0000 |
| L2 | **0** | 40 | 0.8333 |
| L3 | **0** | 22 | 0.9167 |

**At L1 the existing probe bank supplies ZERO such pairs, of either kind.** At L2 and L3 it supplies
none within a family and 40 / 22 across families.

**Why zero within a family is structural, not accidental.** `relabel` is an antisymmetric involution
on the two candidate identities, so for any antisymmetric statistic `f`,
`pred(counter) = 1 − pred(original)` while `truth(counter) = 1 − truth(original)`. The family hit
count is therefore **always 0 or 2, never 1**. Confirmed in the histograms: `formal_expression_depth`
L1 `{2: 12}`, L2 `{0: 2, 2: 10}`, L3 `{0: 1, 2: 11}` — **no family ever scores 1**. The
generator cannot emit a within-family Direction-A pair for `first_mentioned_in_state`, at any level,
by construction.

## Full-bank counts, all informative rules, within-family Direction-A pairs

| cell | `first_mentioned` | `last_mentioned` | `more_frequent` | `alphabetically_first` | `shorter_option_text` |
|---|---|---|---|---|---|
| `formal_expression_depth` L0 | 12 | 12 | 4 | 12 | 12 |
| `formal_expression_depth` L1 | **0** | 12 | 3 | 12 | 12 |
| `formal_expression_depth` L2 | **0** | 12 | 4 | 12 | 12 |
| `formal_expression_depth` L3 | **0** | 12 | 3 | 12 | 12 |
| `transitive_dependency` L0 | **0** | 12 | **0** | 12 | 12 |
| `transitive_dependency` L1 | **0** | 12 | 4 | 12 | 12 |
| `transitive_dependency` L2 | **0** | 12 | 9 | 12 | 12 |
| `transitive_dependency` L3 | **0** | 12 | 11 | 12 | 12 |
| `precondition_conjunction` L0 | **0** | 12 | **0** | 12 | 12 |
| `precondition_conjunction` L1 | **12** | 12 | **12** | 12 | 12 |
| `precondition_conjunction` L2 | **12** | 12 | **12** | 12 | 12 |
| `precondition_conjunction` L3 | **12** | 12 | **12** | 12 | 12 |

`precondition_conjunction` L1–L3 supplies a within-family Direction-A pair for **every rule, in
every family — 12 of 12, three times over**. That is the maximum possible. The other two mechanisms
supply zero on their leading feature.

## Cross-family balancing primitive: opposite-polarity family pairs

A 2-of-2 family plus a 0-of-2 family average to exactly 0.5. Counted in `pool_feasibility.json`:

| cell | rule | 2-of-2 | 1-of-2 | 0-of-2 | opposite pairs | max balanced families (of 12 needed) |
|---|---|---|---|---|---|---|
| `formal_expression_depth` L1 | `first_mentioned` | 12 | 0 | 0 | **0** | **0/12** |
| `formal_expression_depth` L2 | `first_mentioned` | 10 | 0 | 2 | 2 | 4/12 |
| `formal_expression_depth` L3 | `first_mentioned` | 11 | 0 | 1 | 1 | 2/12 |
| `transitive_dependency` L3 | `first_mentioned` | 4 | 0 | 8 | 4 | 8/12 |
| `transitive_dependency` L3 | `more_frequent` | 1 | 11 | 0 | 0 | 11/12 |

`DEV_FAMILIES = 12` and `min_positives_for_gates = 24` (`fitness_v5.py:205, 222`) means each cell
carries **exactly** the minimum sample: the full 12 families is the *only* admissible subset.
Exhaustive search over all 2¹² subsets (`pairs.py::subset_feasibility`) confirms it — for every cell,
`feasible_subsets ∈ {0, 1}`, the 1 being the whole cell. **There is zero slack for balancing by
selection at development scale.** (`SCOUT_FAMILIES = 16` would give 4 families of slack.)

---

# Q8 — Matched pairs where the SHORTCUT changes and the mathematics is held constant

`rule(p) != rule(q)` and `expected_index(p) == expected_index(q)`. Within-family this is impossible
by construction for **every cell and every rule**: a V5 family's two positives have opposite
`expected_index` by design (`fitness_v5.py:483-484`, asserted at `:524-528`), so no within-family
pair can share a target. Measured: `direction_B_pairs_within_family = 0` in **all 60 (cell, rule)
combinations**.

Across families, within a cell, Direction-B pairs are plentiful wherever the rule is not constant:
e.g. `formal_expression_depth` L2 `first_mentioned` 40, L3 22; `transitive_dependency` L3
`first_mentioned` 64, `more_frequent` 11; `precondition_conjunction` L1–L3 `first_mentioned` **0**
(the rule's prediction is constant across the whole cell, so it never varies).

**Reading.** Direction B is the weaker of the two directions here, because the confound is carried
by the *twin* construction, and the twin is precisely where Direction B cannot exist. The design's
own atom — the family — is the wrong grain for Direction-B balancing; it would need a **four-probe
family** (original / relabelled / cue-flipped-original / cue-flipped-relabelled), which no generator
in the codebase emits.

---

# Q9 — Confounds per mechanism

## F1 — `CONFIRMED`, severity **CRITICAL** — V7 audits a serialization the Solver never sees

`fitness_v5.shortcut_audit` computes every state rule on
`canonical_json(p.state.to_dict(include_display_identity=False))` (`fitness_v5.py:798`). The Solver
receives `build_prompt(genome, probe)` (`fitness_v5.py:550-565`), whose state block is
`GenomePhenotypeLanguage(genome.surface).render(state)` via `ModelViewCompiler`
(`arena/model_view/compiler.py:66, 75`). These are different serializations with different field
order.

**Measured (`surface_shortcut.json`), `first_mentioned_in_state`, full prompt bytes:**

| cell | V5 audit (canonical) | L0_SE | L1_HML | L2_SEXPR | **L3_JSON_AST (V7's only candidate)** | L4 | L5_SYMBOLIC | L6_TRIPLES | L7 |
|---|---|---|---|---|---|---|---|---|---|
| `formal_expression_depth` L1 | **1.0000** | 0.5 | 0.5 | 0.5 | **0.5000** | 0.5 | 1.0000 | 1.0000 | 0.5 |
| `formal_expression_depth` L2 | **0.8333** | 0.5 | 0.5 | 0.5 | **0.5000** | 0.5 | 0.8333 | 0.8333 | 0.5 |
| `formal_expression_depth` L3 | **0.9167** | 0.5 | 0.5 | 0.5 | **0.5000** | 0.5 | 0.8750 | 0.8750 | 0.5 |
| `transitive_dependency` L3 | 0.3333 (→0.6667) | 0.5 | 0.5 | 0.5 | **0.5000** | 0.5 | 0.3333 | 0.3333 | 0.5 |

Two consequences, both first-order:

1. **The shortcut that voided `formal_expression_depth` does not exist in its own prompt.** V7
   reported `best_shortcut_accuracy = 0.8333` with `best_shortcut_feature =
   first_mentioned_in_state` at the selected L2 (`FITNESS_V7_RESULT.md` §1). In the L3_JSON_AST
   prompt that rule is exactly **0.5000**.
2. **Shortcut availability is representation-dependent**, so a single canonical number cannot serve
   a Game-R comparison. Had the founder tournament run, `L5_COMPACT_SYMBOLIC` and
   `L6_GRAPH_TRIPLES` would have carried a 0.83–1.00 cue that the other six surfaces do not — a
   textbook confound of exactly the effect Game R is meant to isolate, and V7 measures none of it.

**Counterfactual recomputation** (`prompt_visible_audit.json`; frozen accuracies read verbatim from
the V7 artifact, V5's own seven rules and V7's own unmodified `select_frontier_level` /
`qualify_mechanism` / `SHORTCUT_MARGIN`, with only the audit's *observation text* corrected to
`build_prompt(V5E_L3_JSON_AST, probe)`):

| cell | accuracy | shipped best shortcut | prompt-visible best shortcut | shipped margin | prompt-visible margin |
|---|---|---|---|---|---|
| `formal_expression_depth` L2 (selected) | 0.7917 | 0.8333 `first_mentioned` | **0.6667** `more_frequent` | −0.0417 | **+0.1250** |
| `transitive_dependency` L3 (selected) | 0.7500 | 0.6667 `first_mentioned` | **0.5417** `more_frequent` | +0.0833 | **+0.2083** |

```
formal_expression_depth   L2  as_shipped=VOID_SHORTCUT  counterfactual=QUALIFIED (margin +0.1250)
transitive_dependency     L3  as_shipped=VOID_SHORTCUT  counterfactual=QUALIFIED (margin +0.2083)
precondition_conjunction      selector -> VOID_CEILING
counterfactually qualified mechanisms: 2 (instrument rule needs 2)
```

**Both mechanisms pass `shortcut_absolute` (≤ 0.75) and `shortcut_margin` (≥ 0.10) on the bytes the
Solver actually read. All other gates already passed (`FITNESS_V7_RESULT.md` §2). Two qualified
mechanisms meets `minimum_qualified_mechanisms = 2`, so `instrument_qualified` would be `true` and
the founder tournament would be authorised.**

Scope of this claim, stated precisely: it is a claim about *what V7's own gates compute*, not a
claim that the Solver did or did not use a heuristic. A prompt-visible audit with a richer rule set
could find leaks V5's seven rules miss (`more_frequent_in_state` at 0.8750 on L1/L3 is a real one).
The finding is that the number V7 gated on is not a property of the experiment it ran.

## F2 — `CONFIRMED`, severity **HIGH** — `relabel()`'s docstring claim is false

`formal_structural.py:181-190`:

> It preserves the tree shape and the token multiset exactly and inverts the answer, so a model that
> reads structure must flip its choice **while a model that reads surface statistics cannot.**

The second clause is false for every *per-identifier* statistic. Measured (`generator_diff.json`),
canonical record, `formal_expression_depth`: the (first-offset, count) pair of the two answer
identities is **swapped** across the twin in 8/12 (L1), 12/12 (L2), 11/12 (L3) families. In the
prompt the offsets are pinned but the counts still swap in 9/12 (L1), 8/12 (L2), 9/12 (L3) —
`more_frequent_in_state` = 0.8750 / 0.6667 / 0.8750. A surface-statistics reader flips perfectly
with the answer on up to 87.5 % of items. `relabel` is multiset-preserving *globally* and
antisymmetric *per identifier*; only the first property is in the docstring.

## F3 — `CONFIRMED`, severity **HIGH** — the confound is structurally irremovable within a family

For `formal_expression_depth` and `transitive_dependency`, the counterfactual is an antisymmetric
swap (`fitness_v5.py:382`; `fitness_v4.py:547-548`), so every family scores 0-of-2 or 2-of-2 on
every antisymmetric rule and **never 1-of-2** (Q7 histograms). Balancing is possible only across
families, and `DEV_FAMILIES = 12` against `min_positives_for_gates = 24` leaves **zero** selection
slack (exhaustive 2¹² search: `feasible_subsets ≤ 1`, and the 1 is the full cell).

## F4 — `CONFIRMED`, severity **MEDIUM** — the gated statistic is an uncalibrated maximum

`best_shortcut_accuracy` is `max` over 7 rules × 2 polarities. Under a *perfectly* unbiased
generator at this bank size, E[best] = 0.6128 (1 informative rule) to 0.7226 (5). Both
`shortcut_rule_max = 0.75` and `SHORTCUT_MARGIN = 0.10` are set against an uncharacterised null.
`transitive_dependency` L3's 0.017 shortfall is far inside that bias.

## F5 — `CONFIRMED`, severity **MEDIUM** — the L0 shortcut audit is meaningless but reported

At L0 the explicit arm states the answer (`_with_explicit_depths`, `fitness_v5.py:350-374`;
`assert_answer`, `fitness_v5.py:410-416`), so the audit necessarily reads 1.000 for
`precondition_conjunction` and `transitive_dependency`. It is reported in
`shortcut_audit_by_level` and in `FITNESS_V7_RESULT.md` §1's per-level table alongside gated
numbers, with no marking that it is uninterpretable. `select_frontier_level` excludes L0 from
selection (`fitness_v7.py:687`), so no gate is affected — a presentation defect only.

## F6 — `CONFIRMED`, severity **MEDIUM** — Direction-B pairs are impossible by family design

Every family's two positives have opposite targets, so no within-family pair can hold the
mathematics constant. `direction_B_pairs_within_family = 0` in all 60 (cell, rule) combinations. A
cue-varying / truth-constant arm would require a four-probe family; no generator in the codebase
emits one.

## F7 — `REFUTED` (candidate confound, checked and cleared)

`docs/ROUTE_B_PARITY_AUDIT.md` §1's blocking finding — that the five historical arms are
hand-written codecs whose `_encode_payload` never reads `self.genome` — does **not** apply to the
V5/V7 prompt path. `build_prompt` renders through `ModelViewCompiler` →
`GenomePhenotypeLanguage(genome.surface)` (`model_view/compiler.py:66`), the genome-driven surface.
The hand-written codecs in `arena/languages/*/__init__.py` are not on this path. (The finding
remains live for Route B training, which is out of my scope.)

---

# Q10 — Destroyed twins and `relabel()` as balancing primitives

**Yes — the destroyed twin is the perfect Direction-A construction, and it is used only as a
negative control.**

A destroyed pair shares **the same `CanonicalState` object and the same `options` tuple**, differing
only in `expected_index` (`fitness_v5.py:485-486`, asserted at `:505-509`), and `build_prompt` never
sees `variant` or `expected_index` (`:550-565`). So the two siblings produce **byte-identical
prompts** with opposite targets. For *any* deterministic function of the observation — a shortcut
rule, a heuristic, the Solver itself — accuracy on such a pair is exactly 0.5. This is the strongest
possible Direction-A pair: the cue is not merely "constant", it is the same bytes.

**Measured:** `destroyed_accuracy = 0.5000` at **all 12 cells** of the V7 artifact — exactly the
theorem V7's own docstring proves and then uses to delete the dead `destroyed ≤ 0.60` gate.

The programme therefore already knows, and has proved in its own module docstring, that *holding the
observation fixed while flipping the target forces any surface reader to chance*. It applies that
insight **only** to a control arm it then discards as information-free, and never as a constraint on
the positive arms.

`relabel()` is the weaker primitive: it is multiset-preserving but antisymmetric per identifier
(F2), so as a *generator constraint* it produces the **opposite** of balance — it guarantees the
family is 0-of-2 or 2-of-2 on every antisymmetric rule (F3). `relabel` is the right operator for a
*semantic* counterfactual and the wrong operator for a *cue-balanced* one. The needed pair is:
same cue statistics, different truth — which is the destroyed twin's construction applied to a
target that is still well-defined.

**This is the key structural insight of the audit.** The primitives were built, proved correct,
measured at 0.5000 twelve times over, and then confined to a control arm. Promoted to a generator
constraint, they are exactly what `_premise_family` already does — see Q11.

---

# Q11 — What `precondition_conjunction`'s generator does differently. **Headline.**

**It is balanced BY CONSTRUCTION, not by accident of content. `CONFIRMED`.**

Line-by-line, `_premise_family` (`arena/experiments/fitness_v4.py:742-830`) versus the other two:

| | `_formal_family` (`fitness_v5.py:376-397`) | `_dependency_family` (`fitness_v4.py:517-573`) | `_premise_family` (`fitness_v4.py:742-830`) |
|---|---|---|---|
| answer identifiers | `left`, `right` = the two Lean identities **inside the target** | `a = p_chain[hops-1]`, `b = q_chain[hops-1]` — inside the evidence graph | `a, b = f"answer:{_hex(salt\|A)}", f"answer:{_hex(salt\|B)}"` (`:769`) — **synthetic, outside the varying structure** |
| how the counterfactual is made | `relabel(target, left, right)` (`:382`) — **swaps the identities** | `build(q_chain, p_chain, True)` (`:548`) — **swaps the chains** | `held(False, True)` vs `held(True, False)` (`:792-797`) — **swaps which premise is missing** |
| block naming `a`/`b` | the goal target — **rebuilt per variant** | the evidence list — **rebuilt per variant** | `propositions` (`:766-774`) — **built once, passed unchanged to original, counter and destroyed** |
| what the answer identity depends on | which identity sits deepest → moves with the swap | which chain is attached → moves with the swap | which `holds(premise)` assumption is absent → **`a` and `b` never move** |

The decisive line is `fitness_v4.py:766-774`: `propositions` is constructed **once**, and
`fitness_v4.py:792-799` passes the *same object* to all three states. `a` and `b` appear only there
and in `objects` — both invariant. The truth is carried entirely by the `assumptions` block, which
mentions **premise** ids (`p:NNNN`), never `a` or `b`.

**Measured consequence (`generator_diff.json`).** For each family, comparing ORIGINAL vs
COUNTERFACTUAL on the two quantities every V5 state rule is a function of — first-occurrence offset
and occurrence count of each answer identifier:

| cell | families | canonical stats **invariant** | canonical stats **swapped** | prompt stats **invariant** |
|---|---|---|---|---|
| `formal_expression_depth` L1 | 12 | 0 | **8** | 3 |
| `formal_expression_depth` L2 | 12 | 0 | **12** | 4 |
| `formal_expression_depth` L3 | 12 | 0 | **11** | 3 |
| `transitive_dependency` L1 | 12 | 0 | **12** | 4 |
| `transitive_dependency` L2 | 12 | 0 | **12** | 9 |
| `transitive_dependency` L3 | 12 | 0 | **12** | 11 |
| **`precondition_conjunction` L1** | 12 | **12** | 0 | **12** |
| **`precondition_conjunction` L2** | 12 | **12** | 0 | **12** |
| **`precondition_conjunction` L3** | 12 | **12** | 0 | **12** |

12 of 12 families, at every non-explicit level, in **both** the canonical record and the prompt.
Every state rule therefore predicts the *same* option for both siblings while the target flips, so
it is right on exactly one of the two — hit histogram `{1: 12}` for **every informative rule at
every level** (`pairs_report.json`), giving `0.5000` **deterministically, independent of content**.

**Is it clean by construction or by accident of content?** By construction, and this is testable
three ways:

1. It is 0.5000 at L1, L2 **and** L3 — three different `premises` counts (2, 3, 5). An accident of
   content would wobble; `transitive_dependency`'s `first_mentioned` (0.5000 / 0.5833 / 0.3333
   across L1/L2/L3) is what an accident looks like.
2. Every family is exactly 1-of-2. Accidental balance shows up as a mix of 0-of-2 and 2-of-2 —
   which is precisely `transitive_dependency` L1's `{0: 6, 2: 6}`, a cell that reads 0.5000 while
   containing zero balanced families.
3. It breaks in exactly the predicted place. `precondition_conjunction` **L0** adds
   `the_answer_is(a)` / `the_answer_is(b)` (`fitness_v5.py:410-416`), the one edit that makes `a`
   and `b` differ across the twin — and the audit immediately jumps to 1.0000 on both
   `first_mentioned` and `more_frequent`, with `canonical_stats_invariant = 0/12`. The invariance is
   causal, not incidental.

**Therefore the other two mechanisms' shortcut exposure is a GENERATOR property, not a fact about
mathematics.** `precondition_conjunction` proves, inside this very probe bank, that a Game-R
mechanism can be generated with every V5 shortcut pinned at exactly chance. The recipe is explicit
and short: *give the two options stable synthetic identities that live outside the structure you
vary; build the block that names them once and share it across the twin; carry the truth in a
block that never mentions them.* Nothing about `formal_expression_depth` or
`transitive_dependency` forbids it — `formal_expression_depth` would need the two candidate
identities named through a shared, sorted index (which `build_state`'s `objects` block **already
does**, and which is exactly why the prompt-visible `first_mentioned` is 0.5000 — F1) and the
recurrence counts equalised by an eligibility filter (feasible at L2 and L3 from the existing pool,
Q5b).

`precondition_conjunction`'s failure is `VOID_CEILING`, not `VOID_SHORTCUT`
(`FITNESS_V7_RESULT.md` §5): the one mechanism built the right way is the one the ladder is too easy
for. The programme's response was to keep the two shortcut-confounded generators and extend the
clean one's ladder. The evidence supports the opposite: **the clean generator is the template, and
the ladder extension is the cheap part.**

---

# Classified flaw list

| # | Finding | Class | Severity | Effect |
|---|---|---|---|---|
| **F1** | V7's shortcut audit reads `canonical_json(state.to_dict())`, not the Solver's prompt. `first_mentioned_in_state` = 0.5000 in the shipped L3_JSON_AST prompt vs 0.8333/1.0000/0.9167 in the canonical record. Recomputing V7's own gates on the prompt qualifies **both** selected mechanisms (margins +0.1250 and +0.2083) → 2 of 3 → `instrument_qualified` true. | `CONFIRMED` | **CRITICAL** | The `V7_SHORTCUT_DOMINATED` verdict, `RSTAR_NOT_IDENTIFIED`, and the tournament block rest on a text no Solver received. Fixable by re-reading the frozen rows: **zero model calls.** |
| **F1b** | Shortcut availability is representation-dependent (0.5000 in 6 founder surfaces, 0.8333–1.0000 in `L5_COMPACT_SYMBOLIC` and `L6_GRAPH_TRIPLES`). V7 records one number for all. | `CONFIRMED` | **HIGH** | A founder tournament would compare surfaces with unequal cue availability — a direct confound of the Game-R effect. The audit must be per-candidate. |
| **F2** | `relabel()` docstring claims a surface-statistics reader "cannot" flip. False: per-identifier offsets and counts swap with the answer; `more_frequent_in_state` = 0.8750. | `CONFIRMED` | **HIGH** | The counterfactual arm's soundness argument is wrong in code comments and inherited by every downstream doc. |
| **F3** | Antisymmetric counterfactual ⇒ every family is 0-of-2 or 2-of-2, never 1-of-2. Within-family Direction-A pairs for the leading feature: **0** at `formal_expression_depth` L1/L2/L3 and `transitive_dependency` L0–L3. With `DEV_FAMILIES = 12` = `min_positives 24 / 2`, exhaustive 2¹² search finds **no** balancing subset. | `CONFIRMED` | **HIGH** | The two leaking mechanisms are causally confounded as generated and cannot be rescued by selection at dev scale. |
| **F4** | `best_shortcut_accuracy` is a max over 14 correlated estimates; null E[best] = 0.6128–0.7226 at this bank size. `shortcut_rule_max = 0.75` and `SHORTCUT_MARGIN = 0.10` are set against an uncharacterised null; the prereg's 0.082 is the *solver's* SE. | `CONFIRMED` | **MEDIUM** | `transitive_dependency` L3's 0.017 shortfall is inside the bias. Both thresholds need a null calibration. |
| **F5** | L0's shortcut audit is 1.000 by design (the explicit arm states the answer) and is reported next to gated numbers unmarked. | `CONFIRMED` | **MEDIUM** | Presentation only — L0 is excluded from selection. Reads as three leaking mechanisms when one is an artefact of the control arm. |
| **F6** | Direction-B pairs (cue varies, truth fixed) are **0** within family in all 60 (cell, rule) combinations, because a family's two positives have opposite targets by design. | `CONFIRMED` | **MEDIUM** | Cue-varying/truth-constant balancing needs a four-probe family; no generator emits one. |
| **F7** | `ROUTE_B_PARITY_AUDIT` §1's "hand-written codecs ignore the genome" finding applied to the V5/V7 prompt path. | `REFUTED` | — | `build_prompt` renders via `GenomePhenotypeLanguage`, the genome-driven surface. The §1 finding stands for Route B training only. |
| **F8** | 10-point rule not derived from the objective: `GOAL.md` mandates that a shortcut audit exist (line 455) and sets no threshold. | `CONFIRMED` | **MEDIUM** | Instrument-local. It may be a good rule, but it cannot be cited as a scientific requirement. |
| **F9** | V7 varies zero representations; its verdict is a task-usability screen presented and consumed as evidence about R. | `CONFIRMED` | **HIGH** | The whole downstream "Game R is blocked" chain is a category error about what V7 measured. |

## Artifacts

* `research/audit/a9_causal/pairs_report.json` — per-cell, per-rule scores, family hit histograms, Direction-A/B pair counts, exhaustive subset feasibility.
* `research/audit/a9_causal/surface_shortcut.json` — the three state rules recomputed on the canonical record, on each of the 8 founders' rendered states, and on each founder's full prompt.
* `research/audit/a9_causal/generator_diff.json` — twin-invariance of (first offset, count) per family, canonical and prompt.
* `research/audit/a9_causal/pool_feasibility.json` — 104-state source-pool polarity/tie census and per-cell opposite-polarity pair counts.
* `research/audit/a9_causal/prompt_visible_audit.json` — the counterfactual gate recomputation.
* `research/audit/a9_causal/margin_calibration.json` — exact null distribution of the gated max-statistic.
