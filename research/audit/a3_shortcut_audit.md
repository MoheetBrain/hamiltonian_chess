# A3 — The Shortcut Audit, Audited

**Auditor 3 of 9 · V7 Total Forensic Audit, Part C · read-only, zero model calls**

---

## 0. Integrity statement — read this before any number below

Every classifier, permutation test, population estimate and split-sample figure in this document
is a **diagnostic of the instrument**. None of it is a re-scoring of Fitness V7.

> **No number in this document, or in `research/audit/a3_shortcuts/`, may be used to re-score,
> promote, re-qualify or reinterpret any recorded sentinel.** `V7_SHORTCUT_DOMINATED`,
> `instrument_qualified: false` and `qualified mechanisms: 0 of 3` stand exactly as recorded in
> `docs/FITNESS_V7_RESULT.md`. Where this audit shows a preregistered statistic to be biased, the
> correct consequence is a **future instrument**, never a retrospective re-read of a frozen run.
> `SHORTCUT_MARGIN = 0.10` and `shortcut_rule_max = 0.75` are untouched.

Nothing in this audit modified an existing file. New paths only:
`research/audit/a3_shortcut_audit.md` and `research/audit/a3_shortcuts/`.
(Note: other audit agents are writing into `research/audit/` concurrently; `git status` during this
run showed staged edits to `docs/PROJECT_STATUS.md` and `docs/PROJECT_LEDGER.md` made by another
process. A3 did not author them.)

Environment: `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python` (3.14.7);
`import arena` resolves to
`/Users/moheet/…/worktrees/phase-6-parallel-setup-9c6068/arena/__init__.py`.
`numpy 2.5.2`, `scikit-learn 1.9.0`, `scipy 1.18.1` present; `pandas`, `xgboost`, `lightgbm`,
`statsmodels`, and every tokenizer package absent (checked, and worked around explicitly).

**Reproduction check.** `predictor_inventory.py` re-derives the whole per-level audit and compares
it field-by-field against the recorded scan `research/v7/per_level_shortcut_scan.json`:
`reproduction_exact: True`, `mismatches: 0`. Everything below rests on a bank that reproduces the
recorded one byte-for-byte.

---

## 1. Q1 — Every shortcut predictor currently implemented

Single implementation, one function: `arena/experiments/fitness_v5.py:790-834`
(`shortcut_audit`). V7 does not add any rule; `arena/experiments/fitness_v7.py:636-662`
(`per_level_shortcut_audit`) merely calls V5's function once per `(mechanism, level)` cell.

Two helpers fix what the rules can see:

| helper | line | value |
|---|---|---|
| `names(p)` | `fitness_v5.py:795-796` | `(options[0].arguments[0].value, options[1].arguments[0].value)` — the two identifier strings |
| `text(p)` | `fitness_v5.py:798-799` | `canonical_json(p.state.to_dict(include_display_identity=False))` — the serialized state, **`sort_keys=True`** (`arena/canonical/schema.py:30-35`) |

| # | rule | line | exact predicate |
|---|---|---|---|
| 1 | `always_first_option` | `:802` | constant `0` |
| 2 | `always_second_option` | `:803` | constant `1` |
| 3 | `first_mentioned_in_state` | `:804-806` | `0 if text.find('"n0"') <= text.find('"n1"') else 1` |
| 4 | `last_mentioned_in_state` | `:807-809` | `0 if text.rfind('"n0"') >= text.rfind('"n1"') else 1` |
| 5 | `more_frequent_in_state` | `:810-812` | `0 if text.count('"n0"') >= text.count('"n1"') else 1` |
| 6 | `shorter_option_text` | `:813-815` | `0 if (len(n0), n0) <= (len(n1), n1) else 1` |
| 7 | `alphabetically_first` | `:816` | `0 if n0 <= n1 else 1` |

Aggregation, `fitness_v5.py:818-833`:

```
scores      = {name: mean(rule(p) == p.expected_index for p in positives)}
worst       = argmax_name |scores[name] - 0.5|        # :822   SELECTION
worst_score = max(scores[worst], 1 - scores[worst])   # :823   negation fold
status      = "CLEAN" if worst_score <= 0.75 else "LEAKS"   # :831-833, threshold at :225
```

V7 consumes `worst_score` as `best_shortcut_accuracy` (`fitness_v7.py:655`) and gates twice on it
(`fitness_v7.py:749-754`): `shortcut_absolute` (`<= 0.75`) and `shortcut_margin`
(`positive − best_shortcut >= 0.10 − GATE_EPSILON`).

### 1.1 The family is not seven rules. It is at most two. `CONFIRMED`

The bank is built in twin pairs: `derive_probe_family` (`fitness_v5.py:422-491`) emits
`ORIGINAL` (`expected_index = 0`) and `COUNTERFACTUAL` (`expected_index = 1`) that share the
**same option tuple** (`:449`), the counterfactual being the original with the two identifiers
`relabel`-swapped (`arena/environments/formal_structural.py:181-201`). Therefore **any rule that
returns the same index for both twins scores exactly 0.5, always, with zero variance.**

`predictor_inventory.py` counts, per cell, how many families a rule's output varies across:

| cell | live rules (can ever deviate from 0.500) |
|---|---|
| `formal_expression_depth` L0 | 1 — `more_frequent_in_state` |
| `formal_expression_depth` L1/L2/L3 | 2 — `first_mentioned_in_state`, `more_frequent_in_state` |
| `transitive_dependency` L0–L3 | 2 — same two |
| `precondition_conjunction` L0 | 2 — same two |
| **`precondition_conjunction` L1/L2/L3** | **0 — nothing in the family can deviate from chance** |

Rules 1, 2, 6 and 7 are **structurally pinned at 0.5000** on every cell of this bank: 1 and 2
because the twin targets are balanced by construction (`validate_probe_family`,
`fitness_v5.py:526-530`); 6 and 7 because `names(p)` is identical across the twin.
`last_mentioned_in_state` is pinned too, for a subtler reason: `canonical_json` sorts keys, and
`"objects"` sorts **after** `"goal"`, so `rfind` always lands in the alphabetically sorted object
declaration block (`formal_structural.py:344-351`), which is twin-invariant.

So the "family of seven" that V5's threshold and V7's margin are calibrated against is, on the
cells that decide anything, **two correlated string statistics over the same serialized term**.

---

## 2. Q2 — Why these rules? The justification, and the regression

**A justification exists, in the ancestor, and Arena's port dropped its two most important parts.**

`fitness_v4.py:1396-1402` states outright: *"Adapted from HML_V3
`src/hml_v3/micromath/shortcut_v2.py`. Rules read the option strings and the canonical state text
only; any rule that beats chance measures a construction defect, not a representation."*

The ancestor file exists at
`/Users/moheet/Documents/ChatGPT/HML_V3/src/hml_v3/micromath/shortcut_v2.py`. Its rule list
(`:77-86`) is **seven purely option-string rules** — `always_first_option`,
`always_second_option`, `always_last_option`, `shortest_option`, `longest_option`,
`alphabetically_first`, `alphabetically_last`. It contains **no state-text rule at all**. And its
decision procedure (`:24-28`, `:108-131`) is:

```
RULES_TESTED = 7 ; FAMILY_CONFIDENCE = 0.90
per_rule = 1 - (1 - FAMILY_CONFIDENCE) / RULES_TESTED     # Bonferroni
lower, _ = clopper_pearson(worst * n, n, per_rule)
status = "LEAKS" if lower > chance else "CLEAN"
```

with an explicit rationale in the docstring (`:23-28`): *"A rule is judged … by an exact binomial
lower bound, not by a fixed margin. A flat tolerance made the verdict a function of sample size —
at n=14 one rule landing 0.43 against chance 0.25 is ordinary noise, and the first version called
that a leak on one split and clean on another from the same construction."*

The ancestor also **separates a key-aware rule as reported-not-gating** (`:100-104`), because it is
"fitted to the answer key of the very cell it is scored on".

The Arena port (`fitness_v4.py:1443-1469`, inherited verbatim by V5 and V7):

1. swapped three option-string rules for three **state-text** rules (defensible: at k = 2 options
   the dropped three are exact negations of ones that remain);
2. **added a negation fold** (`worst = argmax|s−0.5|`, `worst_score = max(s, 1−s)`), which
   **doubles the number of hypotheses actually searched** from 7 to 14;
3. **deleted the Bonferroni correction and the exact interval**, replacing them with the flat
   constant `shortcut_rule_max = 0.75` (`fitness_v5.py:225`);
4. dropped the reported-not-gating distinction.

Steps 2 and 3 move in opposite directions and were made together. The result is precisely the
design the ancestor's own docstring records as a bug it had already fixed.

V5's spec does record the residual risk honestly (`docs/FITNESS_V5_SPEC.md:88-93`): *"The strongest
dumb rule on the DEV pool is `more_frequent_in_state` at 0.72 against a 0.75 threshold … If a
mechanism qualifies on the strength of that correlation the finding is weak."* What is missing is
any justification for **0.75 itself**, for the family size, or for the sampling model.

V7's preregistration justifies its margin (`docs/FITNESS_V7_PREREGISTRATION.md:76-79`): *"at n = 24
the binomial standard error near 0.8 is ≈ 0.082, so a margin below one standard error could not
distinguish a solver from its own shortcut."* That SE is computed for **24 independent items**. The
bank has **12 independent families** (§1.1), so the SE near 0.8 is ≈ 0.115, and the statistic being
compared is a **maximum over a searched family**, whose null mean is 0.61–0.65 rather than 0.50
(§8). The margin is calibrated against the wrong sampling distribution.

---

## 3. Q3 — What is not tested

Measured on the **enlarged** bank (whole 34/34/36-state length-filtered formal pool; 200 generated
families per synthetic cell) by `untested_classes.py` → `untested_classes.json`. Folded with V5's
own `max(s, 1−s)` convention.

| class | in V5 family? | A3 result |
|---|---|---|
| first mention | **yes** | the decisive rule on `formal_expression_depth` |
| last mention | **yes** | structurally pinned at .500 (§1.1) |
| identifier frequency | **yes** | the decisive rule on `transitive_dependency` |
| length | **yes** | pinned at .500 |
| option position / candidate rank / prompt position | **yes** (rules 1–2) | pinned at .500 by construction |
| nearest to goal | no | .8824 / .8611 on formal L2/L3 — a monotone re-reading of first mention |
| farthest from goal | no | identical values; same statistic |
| punctuation before first occurrence | no | .8824 / .8611 — same statistic |
| delimiter count before first occurrence | no | .8824 / .8611 — same statistic |
| local dependency degree (occurrence count) | no | .7059 / .7778 formal; **.7750 / .5950** transitive L1/L3 — same statistic as frequency |
| span between first and last mention | no | .6765 / .6528 formal |
| lexical overlap · token overlap · character (3-gram) overlap | no | **.5000 everywhere** — identifiers are opaque `f33`/`e:…` strings |
| identifier name (lexical, digit suffix) | no | **.5000** — twin-invariant |
| regex / affix cues | no | **.5000** |
| tokenizer length | no | no tokenizer package installed; character-class **proxy** = .5000, labelled as a proxy |
| n-grams (char 2–5 TF-IDF + logistic, grouped 6-fold CV) | no | **.5000 on every cell** |
| **AST depth** | no | **this is the ORACLE, not a shortcut** — see §12 |
| **textual depth** (JSON bracket nesting at the occurrence) | no | **1.0000 on every formal cell — because it *reconstructs* the oracle** |
| module identity · theorem identity · source file · tactic family | no | **not computable**: those fields live in `provenance` / `oracle_record`, never in `CanonicalState`, and are never rendered to the model |
| global dependency degree | no | **undefined**: each probe is a standalone state; there is no cross-item graph |
| **combinations** | **no** | §5–§6 |

**The important finding is not that classes are missing — it is that almost every missing class is
either (a) a re-parameterisation of one of the two live rules, (b) exactly .500, or (c) the oracle
in disguise.** Adding `textual_bracket_depth_max` to the family would score 1.000 on every formal
cell and void the mechanism unconditionally — not because a reader can cheat, but because the
audit's frame cannot tell a leak from the answer.

---

## 4. Q4 — What "best shortcut" means, from the code

**It is the best of a small hand-written family, not the best obtainable non-semantic predictor.**
`fitness_v5.py:801-817` enumerates seven closures literally; `:822` takes an argmax over that dict
and nothing else. There is no search over feature space, no fitted model, no threshold selection,
no combination. `fitness_v7.py:643-645` re-states this in its own docstring, and
`docs/FITNESS_V7_RESULT.md:103` concedes it: *"The shortcut rules are V5's inherited set; a richer
adversary would only lower these margins further."* This audit tests that concession in both
directions and finds it **partly wrong** (§6, §8).

---

## 5. Q5 — Model-free classifiers on surface-only features

`build_bank.py` extracts, per positive probe and per option, ~30 surface statistics: occurrence
offsets (absolute and fractional), quoted and raw counts, occurrence span, punctuation/bracket/
brace/colon/quote counts before the first occurrence, identifier character classes, deterministic
identifier-identity hash bucket, name↔state 3-gram overlap, name↔name token overlap, plus nine
symmetric global statistics. Features are formed **antisymmetrically** (`option0 − option1`), so
the label is the answer index.

Two features that reconstruct nesting depth from the JSON string are prefixed `SEMANTIC_` and are
**excluded from every fitted model**, held aside as an oracle reference.

Learners: `LogisticRegression`, decision stumps and trees (depth 1/3/5/unbounded),
`RandomForestClassifier(300)`, `HistGradientBoostingClassifier`, plus a `DummyClassifier` floor.
scikit-learn 1.9.0 is present, so nothing had to be hand-implemented.

Evaluation is reported three ways, because the difference **is** the audit:

* `in_sample` — fit and score on the same 24 items. This is **exactly V5's protocol** and is the
  only like-for-like comparison with `worst_score`.
* `loso_cv` / grouped k-fold — leave-one-**family**-out, so no twin straddles the split.
* `split_half` — select/fit on 6 families, evaluate on the other 6, averaged over **all 462**
  balanced splits (exhaustive; no sampling error).

Per-cell, per-model accuracies: `combined_classifiers.json`, `expanded_family.json`.

---

## 6. Q6 — How much better are combinations? — the false-negative headline

The honest answer depends entirely on **n**, and the DEV cells are far too small to answer at
n = 24. So the question was re-asked where it can be answered: the two synthetic mechanisms were
regenerated at **400 families (800 positives) per cell** from the frozen generator, and the formal
mechanism was rebuilt on the **whole length-filtered pool** (68–72 positives per level, vs the 24
that `build_dev_pool` uses). Grouped CV throughout.

| cell | V5 best single (population) | best combined surface, grouped CV | gain |
|---|---|---|---|
| `formal_expression_depth` L1 | 1.0000 | 1.0000 | **+0.000** |
| `formal_expression_depth` L2 | 0.8824 | 0.8824 | **+0.000** |
| `formal_expression_depth` L3 | 0.8611 | 0.8611 | **+0.000** |
| `transitive_dependency` L1 | 0.7588 | **0.8825** (RF) | **+0.124** |
| `transitive_dependency` L2 | 0.6813 | 0.7025 (LR) | +0.021 |
| `transitive_dependency` L3 | 0.6012 | 0.6400 (RF) | +0.039 |
| `precondition_conjunction` L1–L3 | 0.5000 | 0.5000 | **+0.000** |

**Verdict, split:**

* For `formal_expression_depth`, the combination gain is **exactly zero at every level**: the best
  surface classifier a random forest can build ties a one-line `str.find` comparison. Hypothesis
  "the family is too weak here" is **`REFUTED`**.
* For `precondition_conjunction` L1–L3, a 30-feature unbounded tree and a 300-tree forest both
  return **0.5000 in-sample and out**. The family is **`REFUTED` as too weak**; the cell is clean.
* For `transitive_dependency` the family **is** too weak, but modestly: **+0.124** at L1 and
  **+0.039** at L3. `LIKELY`, severity **medium**, effect `FALSE_NEGATIVE_RISK`.

There is one catch, and it is the whole methodological point. Under **V5's own in-sample
protocol**, an unbounded decision tree reaches **1.000 in-sample** on `transitive_dependency` L1,
L2 and L3 (`combined_classifiers.json`), against V5's reported 0.833 / 0.625 / 0.667. Judged by
the audit's own evaluation rule, every cell would be `VOID_SHORTCUT`. That number is worthless —
30 features on 24 points — and its worthlessness is the diagnosis: **the audit's evaluation
protocol cannot be strengthened by enlarging the family, because it has no defence against
overfitting.** Family strength and evaluation protocol have to be fixed together.

---

## 7. Q7 — Are selection and evaluation on the same items? Definitively yes. `CONFIRMED`

`fitness_v5.py:818-823`:

```python
scores = {n: sum(r(p) == p.expected_index for p in positives) / len(positives) ...}
worst  = max(scores, key=lambda n: abs(scores[n] - 0.5))   # selects on `positives`
worst_score = max(scores[worst], 1.0 - scores[worst])      # reports on `positives`
```

`positives` (`:791`) is bound once. There is no split, no holdout, no penalty term, no correction
anywhere in the function or in `per_level_shortcut_audit` (`fitness_v7.py:636-662`).
`worst_score` is a **maximum of 14 correlated in-sample statistics** (7 rules × 2 polarities)
reported as if it were one pre-specified statistic. Severity **high**, effect
`FALSE_POSITIVE_RISK`.

---

## 8. Q8 — How large is the upward bias? — the false-positive headline

Three independent estimates, in increasing order of authority.

### 8.1 Exact binomial nulls (`selection_bias.json → exact_nulls`)

The right null is **twin-paired**: a relabel-sensitive surface rule is right on both twins of a
family or neither, so it has **12** independent trials, not 24.

| | E[`worst_score`] for one rule | P(`worst_score` ≥ 0.75) |
|---|---|---|
| item-level null, n = 24 | 0.5806 | 0.0227 |
| **twin-paired null, n_eff = 12** | **0.6128** | **0.1460** |

Max over k independent rules, twin-paired null:

| k | 1 | 2 | 3 | 6 | **7** | 12 | 30 |
|---|---|---|---|---|---|---|---|
| E[max] | .613 | .661 | .689 | .734 | **.744** | .775 | .823 |
| P(max ≥ .75) | .146 | .271 | .377 | .612 | **.669** | .850 | .991 |

**V5's threshold of 0.75 sits below the null mean of a max over seven live rules (0.744), and would
be crossed by pure noise 67% of the time.** The family is saved from that only by its own
degeneracy: it has 2 live rules, not 7 (§1.1), giving a null mean of ≈0.66.

### 8.2 Exact randomisation on the real bank (`selection_bias.py`, 50,000 permutations)

Labels permuted **within twin pairs** — the only degree of freedom the construction leaves — and
the full audit recomputed. This is exact and accounts for the real correlation and degeneracy.

| cell | observed | null mean **(= what the audit reports with zero leakage)** | p | split-half held-out |
|---|---|---|---|---|
| `formal_expression_depth` L1 | 1.000 | 0.636 | **0.0004** | 1.000 |
| `formal_expression_depth` L2 | **0.833** | 0.641 | **0.0441** | 0.816 |
| `formal_expression_depth` L3 | 0.917 | 0.647 | **0.0061** | 0.884 |
| `transitive_dependency` L1 | 0.833 | 0.647 | 0.0446 | 0.786 |
| `transitive_dependency` L2 | 0.625 | 0.629 | 0.506 | 0.484 |
| **`transitive_dependency` L3** | **0.667** | **0.622** | **0.3865** | **0.545** |
| `precondition_conjunction` L1–L3 | 0.500 | 0.500 | 1.000 | 0.500 |

**Answering the brief's question directly:** of the observed .667–.833 band, roughly **0.62–0.65 is
the null expectation of the statistic itself.** A reported 0.667 is +0.045 above what a bank with
no leakage whatsoever reports.

### 8.3 Population estimates — decisive, because they need no simulation

The synthetic generators can be sampled without limit; the formal pool is 3× the DEV draw.

| cell | V5 reported (n = 24) | population value | population n |
|---|---|---|---|
| `formal_expression_depth` L1 | 1.000 | **1.000** (`first_mentioned`) | 68 |
| `formal_expression_depth` L2 | 0.833 | **0.8824** | 68 |
| `formal_expression_depth` L3 | 0.917 | **0.8611** | 72 |
| `transitive_dependency` L1 | 0.833 (`first_mentioned`) | 0.759 (`more_frequent`) | 800 |
| `transitive_dependency` L2 | 0.625 | 0.681 | 800 |
| **`transitive_dependency` L3** | **0.667 (`first_mentioned`)** | **0.601 (`more_frequent`)** — and `first_mentioned` itself is **0.5175** | 800 |
| `precondition_conjunction` L1–L3 | 0.500 | **0.5000 exactly** | 800 |

**This is the single most important line in the audit.** The rule that carried
`transitive_dependency` L3 to `VOID_SHORTCUT` — `first_mentioned_in_state` at 0.667 — has a
population value of **0.5175**, i.e. chance. It was selected because it happened to be the largest
deviation on those particular 24 items. The mechanism's *true* best single shortcut at L3 is
`more_frequent_in_state` at **0.601**, and its true best obtainable non-semantic predictor
(random forest, grouped CV, n = 800) is **0.640**.

`docs/FITNESS_V7_RESULT.md` §4 records that mechanism as failing the margin gate by 0.017
(0.750 − 0.667 = 0.0833 against 0.10). Against the population shortcut the same arithmetic gives
0.750 − 0.601 = **0.149**; against the best obtainable surface predictor, 0.750 − 0.640 =
**0.110**. **Both clear the preregistered 0.10 margin.**

> **This does not change the V7 verdict and must not be used to.** The preregistration bound the
> gate to the frozen statistic on the frozen bank, and that is what was recorded. What it does
> establish is that the recorded verdict for this one cell rests on a statistic whose sampling
> distribution the preregistration mis-specified.

By contrast `formal_expression_depth` L1/L2/L3 sit at population values of 1.000 / 0.882 / 0.861,
all above `shortcut_rule_max = 0.75`. **Its `VOID_SHORTCUT` is robust and correct**, and is if
anything understated at L2.

---

## 9. Q9 — Should selection and evaluation be split? What would the numbers be?

Yes — but on this bank splitting is necessary and **not sufficient**, because 12 families cannot
support both halves.

Exhaustive 6/6 family splits (all 462), select on one half, evaluate the negation-folded rule on
the other:

| cell | selection-half `worst_score` | **held-out** | optimism | held-out 5–95% |
|---|---|---|---|---|
| `formal_expression_depth` L2 | 0.849 | **0.816** | 0.033 | [0.667, 1.000] |
| `formal_expression_depth` L3 | 0.937 | **0.884** | 0.053 | [0.833, 1.000] |
| `transitive_dependency` L1 | 0.849 | **0.786** | 0.064 | [0.667, 0.917] |
| **`transitive_dependency` L3** | 0.638 | **0.545** | **0.092** | **[0.000, 0.667]** |

Split-sample removes 0.03–0.09 of optimism and correctly collapses `transitive_dependency` L3 from
0.667 to 0.545 — but its 5–95% interval there spans **the entire range from 0.000 to 0.667**. At
n = 12 items per half, an honest estimator is unusable. The real recommendation is therefore not
"split the 24" but **"select the predictor family on a disjoint pool and freeze it before the
evaluation bank is drawn"** — which is possible for both mechanism types here, since the formal
pool holds 104 states of which DEV uses 36, and the synthetic generators are unbounded.

Applying the ancestor's own procedure (`ancestor_procedure.json`) is instructive: with the
Bonferroni correction and Clopper–Pearson lower bound restored at n_eff = 12, `formal L2` (0.833)
would read **CLEAN** (LB 0.475), and only L1, L3 and the L0 explicit arms would read `LEAKS`. That
is the opposite failure — a procedure so underpowered at n = 12 that it misses a leak the
population data confirms is real (0.882). **Neither the flat threshold nor the corrected interval
is usable at n = 24. The binding defect is sample size, not the decision rule.**

---

## 10. Q10 — Could the family be too weak? Partly. `LIKELY`, medium

From §6: at population n the best obtainable surface predictor exceeds V5's best single rule by
**+0.000** on `formal_expression_depth` (all levels), **+0.000** on `precondition_conjunction`,
and **+0.124 / +0.021 / +0.039** on `transitive_dependency` L1/L2/L3.

So the family is adequate for two of three mechanisms and mildly too weak for the third — and
`docs/FITNESS_V7_RESULT.md:103`'s claim that *"a richer adversary would only lower these margins
further"* is **`REFUTED` as stated**: at `transitive_dependency` L3 a richer adversary reaches
0.640 while the *reported* shortcut was 0.667. The reported statistic **overstates** the true best
obtainable non-semantic predictor. Enrichment and de-biasing pull in opposite directions here, and
de-biasing is the larger term.

---

## 11. Q11 — Is `first_mentioned_in_state` genuinely non-semantic? **No.** `CONFIRMED`

`first_mention_probe.py` walks the transcribed Lean trees directly.

| level | JSON `first_mention` | preorder-rank rule | depth oracle | JSON == preorder | preorder == oracle |
|---|---|---|---|---|---|
| L0 (explicit) | 0.500 | 0.833 | 1.000 | 0.500 | 0.833 |
| L1 shallow | 1.000 | 1.000 | 1.000 | **1.000** | **1.000** |
| L2 medium | 0.833 | 0.833 | 1.000 | **1.000** | 0.833 |
| L3 deep | 0.917 | 0.917 | 1.000 | **1.000** | 0.917 |

At L1–L3 the JSON string rule and a preorder walk of the term agree on **100%** of probes. So
`first_mentioned_in_state` is not reading the JSON — it is reading **the term's own traversal
order**. (At L0 they diverge exactly as predicted: `established_facts` sorts before `goal`, so
`find` lands in the fixed-order explicit-depth block and the rule is pinned at 0.500.)

The mechanism, from the path patterns of the answer identifier's first occurrence (all
`[('application',0) × m, ('application',1)]`): Lean curries, `f a b` transcribes as
`app(app(f,a),b)` (`formal_structural.py:61-72`, child order `("function","argument")`). Along a
left-nested application spine, **earlier arguments are simultaneously deeper and earlier in
preorder**. Mean Spearman correlation between preorder rank and depth rank across all identifiers
in a term: **ρ = 0.735**.

**"Which identifier occurs at the greatest nesting depth" and "which identifier is the earlier
argument of the curried application" are the same question.** The cue is not an accidental string
artifact; it is the encoding of currying, read in a different order. Depth is derived structure and
first-mention is presentation order, and on this corpus they are the same fact.

`more_frequent_in_state` is different in kind: across the full 461-state eligible pool the deepest
identifier recurs more often than the runner-up **74.8%** of the time (16.5% ties, 8.7% less;
Pearson r between occurrence count and max depth = **0.445**). That is a genuine statistical
regularity of mathlib goal states — not part of the question, and not an artifact of construction.

---

## 12. Q12 — Should a surface cue that correlates with real structure automatically void a task?

**No, and the current rule is unsound as a matter of logic, not only of statistics.** `CONFIRMED`,
severity high, effect `BOTH`.

Any faithful serialization of a term exposes statistics that correlate with the term's structure —
that is what "faithful" means. A rule that voids on *any* above-threshold surface correlate is
therefore a rule that voids on faithfulness. The reductio is already in the measurements:
`textual_bracket_depth_max`, a pure string statistic over the serialized state, scores **1.000 on
every formal cell** (§3), because JSON bracket nesting *is* AST depth. If "a non-semantic function
of the rendered text scores high ⇒ void" were the criterion, `formal_expression_depth` would be
voided by a feature that computes the answer correctly.

The audit's own outputs already contain the same category error in the opposite direction: at
`transitive_dependency` L0 and `precondition_conjunction` L0 the recorded scan reports
`status: LEAKS` with `first_mentioned_in_state` at **1.000**. Those are the **explicit-positive
control arms**, where `_synthetic_family` (`fitness_v5.py:407-418`) deliberately writes
`the_answer_is(X)` into `established_facts`. The arm is *supposed* to be answerable from the state
— that is its entire purpose (`fitness_v5.py:18-22`). The audit cannot distinguish a designed-in
answer statement from an accidental leak. It does no damage only because the gate applies at the
selected level ≥ 1.

What should void a task is narrower and checkable:

1. the cue predicts the answer **without** the reader recovering the relation the task names, **and**
2. the cue is **an artifact of construction or serialization order**, i.e. it would not survive an
   information-preserving re-presentation of the same mathematics, **and**
3. it is significant **out of sample**, against a null that accounts for the family searched and
   the true unit of independence.

`shortcut_audit` tests none of these three. It tests "some member of a small in-sample family
exceeds 0.75."

---

## 13. Q13 — Three categories, with concrete examples from this bank

**(a) Accidental answer leakage — void it.**
`transitive_dependency` L0 / `precondition_conjunction` L0: `first_mentioned_in_state` = **1.000**
because the literal token `the_answer_is` precedes everything else in the sorted
`established_facts` block. Population value over 400 families: **1.0000**, exactly. The cue does
not encode the dependency chain in any way — it reads a sentence that states the answer. (Here it
is *designed*, and correct; an undesigned instance of the same pattern is what a shortcut audit is
for.)

**(b) Useful representational structure — do not void; this is what a representation is.**
`first_mentioned_in_state` on `formal_expression_depth` L1–L3. §11 shows the cue is a preorder
readout of the same currying that defines the depth relation. A candidate surface that presents
arguments in application order is being penalised for presenting the mathematics faithfully.

**(c) Legitimate compression of mathematical information — do not void; measure it as a prior.**
`more_frequent_in_state`. In real mathlib goal states the identifier that sits deepest recurs more
often (74.8% over 461 states; r = 0.445). A reader using that is exploiting a true regularity of
mathematical text, exactly as a working mathematician does when they guess which variable a goal is
"about". It is a **prior over mathematics**, not a construction defect. V5's spec already sensed
this (`FITNESS_V5_SPEC.md:88-93`) and prescribed the right remedy — an identifier-obfuscation arm
— then gated on the correlation anyway.

The clean control that proves the categories are separable: `precondition_conjunction` L1–L3, where
every implemented rule, every unimplemented class in §3, a char 2–5-gram logistic model, and a
300-tree random forest all return **exactly 0.5000** at n = 800.

---

## 14. Q14 — **The critical question**

> *Are we discarding good representations precisely because they expose mathematical structure in
> an easy-to-read order?*

### The case for "yes"

The gate is a function of the **serialized control surface only** (`text(p)` reads
`p.state.to_dict()`, never a rendered candidate). Its two live rules are (i) traversal order and
(ii) symbol recurrence — the two things any faithful, well-organised presentation of a term makes
legible. A representation that *scrambled* argument order would score lower on `first_mention` and
would sail through the gate. The instrument therefore contains a real gradient **towards
disorganised representations**, and `docs/FITNESS_V7_RESULT.md` §6 concedes that no representation
was ever scored — so the mechanism was killed before the thing it exists to measure was measured
even once.

### The case for "no"

The gate did not discard a representation. It discarded a **mechanism**, and for
`formal_expression_depth` it was right to, for a reason the audit never states. The question asked
is *"Which identifier occurs at the greatest nesting depth?"* On curried Lean applications that is
**definitionally** the same question as *"which identifier appears first"* (§11: 100% agreement,
population accuracy 0.861–1.000). All eight founder surfaces are information-equal by construction
(`assert_game_r_genome`), so all eight expose argument order, so all eight expose the answer at
0.86–1.00. **A mechanism whose answer is equally legible from every candidate cannot discriminate
between candidates.** Its variance across representations is bounded near zero before a single
model call. Voiding it is not a false positive — it is the correct verdict reached through a
statistic that happens to correlate with the real reason.

### Position

**Both, in different cells, and the audit cannot tell them apart — which is the defect.**

* `formal_expression_depth`: `VOID_SHORTCUT` is **correct and robust** (population 0.861–1.000,
  randomisation p ≤ 0.006 at L1/L3, split-half held-out 0.82–1.00). But it is correct *by
  coincidence*. The right verdict is `MECHANISM_DEGENERATE_WITH_READING_ORDER` — the task's
  relation is a restatement of presentation order — and that is a **task-design** finding, not a
  leakage finding. It should have been derivable from `formal_structural.py:61-72` before any
  probe was built.
* `transitive_dependency`: this **is** the feared failure. The voiding statistic
  (`first_mentioned_in_state`, 0.667) has population value **0.5175**; it was selected out of a
  searched family on 12 independent units, and the true surface ceiling is 0.640. The mechanism was
  voided by selection noise dressed as a leak.
* `precondition_conjunction`: shortcut-clean at 0.5000 under every adversary tested. It voided on
  `VOID_CEILING`, which this audit does not touch, and it is the one mechanism worth extending.

So the answer to the critical question is **not** "yes, the shortcut audit is destroying good
representations" — no representation was ever in scope. It is sharper and worse: **the shortcut
audit is a task-design diagnostic being run as a statistical gate.** When the task really is
degenerate with reading order it fires for the wrong reason and stops anyone asking the right
question; when the task is fine it fires anyway, 15–27% of the time, on noise. Both errors follow
from the same root: a maximum over a searched family, evaluated in-sample, against a fixed
threshold, on 12 independent units.

**Constructive consequence (for a future instrument, not for V7).** Replace the single
`worst_score ≤ 0.75` gate with three separate, separately-reported quantities:

1. **Degeneracy** — is the target relation recoverable from presentation order *by construction*?
   Answerable analytically from the environment adapter, at zero cost, before any probe is drawn.
   `formal_expression_depth` fails this and should never have reached a solver.
2. **Leakage** — best obtainable non-semantic predictor, family **frozen on a disjoint pool**,
   evaluated out of sample, reported with its randomisation null and interval.
3. **Prior** — corpus regularities (`more_frequent_in_state`) reported as covariates and controlled
   by an obfuscation arm, never gated.

---

## 15. Classified flaw list

| # | flaw | file:line | class | severity | effect |
|---|---|---|---|---|---|
| A3-1 | `worst_rule` is selected and `worst_score` reported on the **same** items; no split, no penalty | `fitness_v5.py:818-823` | `CONFIRMED` | high | `FALSE_POSITIVE_RISK` |
| A3-2 | 4 of 7 rules are **structurally pinned at 0.5000**; 2 live rules on the decisive cells, 0 on `precondition_conjunction` L1–L3 | `fitness_v5.py:802-816` + `:449`, `:526-530` | `CONFIRMED` | high | `BOTH` |
| A3-3 | Negation fold **doubles** the hypotheses searched (7→14) while the ancestor's Bonferroni correction and exact interval were **deleted** and replaced by a flat 0.75 | `fitness_v4.py:1457-1469` vs `HML_V3/.../shortcut_v2.py:23-28,108-131` | `CONFIRMED` | high | `FALSE_POSITIVE_RISK` |
| A3-4 | `shortcut_rule_max = 0.75` sits **below** the null mean of a max-over-7 at the true unit of independence (0.744); noise crosses it 67% of the time | `fitness_v5.py:225`; `selection_bias.json` | `CONFIRMED` | high | `FALSE_POSITIVE_RISK` |
| A3-5 | `SHORTCUT_MARGIN` justified by a **single-proportion SE at n = 24**; the bank has 12 independent families and the statistic is a searched maximum | `FITNESS_V7_PREREGISTRATION.md:76-79`; `fitness_v7.py:175` | `CONFIRMED` | high | `FALSE_POSITIVE_RISK` |
| A3-6 | `transitive_dependency` L3 voided on a rule whose **population value is 0.5175**; true best surface predictor 0.640, reported 0.667 | `synthetic_population.json`, `synthetic_classifiers.json` | `CONFIRMED` | high | `FALSE_POSITIVE_RISK` |
| A3-7 | Family is genuinely too weak on `transitive_dependency` (+0.124 L1, +0.039 L3 at n = 800) — but **not** on the other two mechanisms | `synthetic_classifiers.json`, `formal_pool_classifiers.json` | `LIKELY` | medium | `FALSE_NEGATIVE_RISK` |
| A3-8 | The audit cannot distinguish designed-in answer statements from leaks: L0 explicit arms report `LEAKS` at 1.000 | `per_level_shortcut_scan.json`; `fitness_v5.py:407-418` | `CONFIRMED` | medium | `HYGIENE_ONLY` (gate applies at level ≥ 1) |
| A3-9 | The audit cannot distinguish a leak from the **oracle**: `textual_bracket_depth_max` = 1.000 on every formal cell | `untested_classes.json` | `CONFIRMED` | medium | `BOTH` |
| A3-10 | `first_mentioned_in_state` is **not non-semantic**: 100% agreement with preorder rank; ρ(rank, depth) = 0.735; the depth question *is* the argument-order question | `first_mention_probe.json`; `formal_structural.py:61-72` | `CONFIRMED` | high | `BOTH` |
| A3-11 | `docs/FITNESS_V7_RESULT.md:103` — *"a richer adversary would only lower these margins further"* — is false at `transitive_dependency` L3, where a richer adversary **raises** the margin | `FITNESS_V7_RESULT.md:103`; `synthetic_classifiers.json` | `REFUTED` (the claim) | medium | `FALSE_POSITIVE_RISK` |
| A3-12 | Hypothesis "the hand-written family is too weak on `formal_expression_depth` / `precondition_conjunction`" | `formal_pool_classifiers.json`, `synthetic_classifiers.json` | **`REFUTED`** | — | — |
| A3-13 | No shortcut audit anywhere in V5/V7 is computed on a **holdout**, though the formal pool holds 104 states of which DEV uses 36, and the synthetic generators are unbounded | `fitness_v5.py:893-912` | `CONFIRMED` | medium | `FALSE_POSITIVE_RISK` |
| A3-14 | `last_mentioned_in_state` is dead because `canonical_json` sorts `"objects"` after `"goal"`; a rule intended to probe the term probes a sorted declaration block | `fitness_v5.py:807-809`; `schema.py:30-35`; `formal_structural.py:344-351` | `CONFIRMED` | low | `FALSE_NEGATIVE_RISK` |

---

## 16. Reproduction

All commands from
`/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/phase-6-parallel-setup-9c6068`,
with `PYTHONPATH=.` and
`PY=/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`. Zero model calls; no
network; no GPU.

```
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.build_bank
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.predictor_inventory
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.combined_classifiers
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.selection_bias
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.expanded_family          # ~15 min
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.ancestor_procedure
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.synthetic_population
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.synthetic_classifiers
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.formal_pool_classifiers
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.untested_classes
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.first_mention_probe
PYTHONPATH=. $PY -m research.audit.a3_shortcuts.consolidate
```

Artifacts (all carry an inline `_disclaimer`): `bank_features.jsonl`, `bank_meta.json`,
`predictor_inventory.json`, `combined_classifiers.json`, `selection_bias.json`,
`expanded_family.json`, `ancestor_procedure.json`, `synthetic_population.json`,
`synthetic_classifiers.json`, `formal_pool_classifiers.json`, `untested_classes.json`,
`first_mention_probe.json`, `corpus_recurrence.json`, `population_shortcut_rates.json`,
`CONSOLIDATED.json`.

**Final restatement.** Every diagnostic here measures the instrument. The V7 sentinel
`V7_SHORTCUT_DOMINATED` stands as recorded, `instrument_qualified` remains `false`, and no
mechanism is re-qualified, re-scored or reinterpreted by anything in this document.
