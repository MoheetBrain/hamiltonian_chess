# V7 Total Forensic Audit — Auditor 2 of 9: Task Construct Validity

**Scope.** Part B: does "zero qualified mechanisms" mean the representation hypothesis failed,
or that the measurement system is wrong? This audit tries to destroy the experimental argument.

**Discipline.** Read-only. No model call, no GPU, no network, laptop only. No preregistered
threshold changed, no V7 row re-scored, no existing file modified (`git diff --stat` empty;
`research/audit/` is the only untracked path; `artifacts/cache/fitness_v7` still 804 files,
none written during this audit).

**Reproduction.** Interpreter `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`,
cwd = this worktree, always `python -m`. `import arena` resolves to
`<worktree>/arena/__init__.py` (verified).

```
python -m arena.experiments.fitness_v7 materialize --root .
  -> {"dev_pool_hash":"f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b",
      "families":144,"probes":864,...}
```

This hash is **identical** to `dev_pool_hash` in the frozen artifact
`artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json`, so every
measurement below is on the *exact* bank V7 ran. `materialize` calls only
`fitness_v5.build_dev_pool` -> `_formal_pool` (gzip corpus reads + renderer) ->
`derive_probe_family` -> `validate_probe_family` (`NativeVerifier`). The three `urlopen` sites in
`fitness_v5.py` (`verify_served_model`, `_call_ollama`, `_cached_call`) are not on that path.
Verified before running.

**Scripts / measurements** (all under `research/audit/a2_covariates/`):

| file | what it does |
|---|---|
| `a2_extract.py` | materialises the bank, renders the control-surface prompt, writes every covariate -> `probe_covariates.jsonl`, `cell_features.json` |
| `a2_predictability.py` | scores 40 one-line decision rules per (mechanism, level) -> `predictability_matrix.{json,md}` |
| `a2_solver_vs_covariates.py` | joins the FROZEN V7 solver rows to the covariate matrix -> `solver_vs_covariates.{json,md}` |
| `a2_level_confounds.py` | what else changes with level; depth-vs-traversal coupling on the real Lean states -> `level_confounds.json` |
| `a2_cross_surface.py` | re-measures the leak on all EIGHT candidate surfaces -> `cross_surface_leak_*.{json,md}` |
| `a2_demonstration.py` | worked examples on real probes -> `worked_examples.json` |

**Harness validation (do not skip).** My rule scorer reproduces V7's own frozen
`shortcut_audit_by_level` **exactly in all 12 cells** — FED 0.667/1.000/0.833/0.917,
TD 1.000/0.833/0.625/0.667, PC 1.000/0.500/0.500/0.500 — when restricted to V5's seven rules.
Any number below that exceeds V7's is therefore a new covariate, not a scoring discrepancy.

---

## 1. What `formal_expression_depth` is intended to measure, and what it measures

**Spec (quoted).** `docs/FITNESS_V5_SPEC.md:60`:

> `formal_expression_depth` | which identifier occurs at the greatest nesting depth in the goal term | walking the transcribed tree | explicit / shallow / medium / deep strata

Rendered question (`arena/experiments/fitness_v5.py:389-392`, constant at all four levels —
verified in `level_confounds.json:question_text_by_cell`):

> "Which identifier occurs at the greatest nesting depth inside the goal expression? Depth counts nested argument levels from the goal's root."

Programme intent (`GOAL.md:15`): representation as "a causal determinant of mathematical
capability". The mechanism is presented as a *structural reading* competence on real mathematics.

**What the generator actually measures — EVIDENCE.** Trace:

1. `arena/environments/formal_structural.py:transcribe` maps each Lean AST node to
   `CanonicalExpression("lean.<kind>", ...)`. The docstring is explicit that this is
   "structural, not semantic", and the `lean.` prefix exists so "no Arena verifier rule is
   triggered by them". The node kinds are **opaque labels**.
2. `identifier_depths` (`:138`) walks that tree recording the depth of every
   `lean.local_reference`.
3. `structural_features` (`:160-165`) takes `max()` per identifier, sorts by `(-depth, name)`,
   and returns `deepest_identifier` / `runner_up_identifier`.
4. `fitness_v5.py:378-379` (`_formal_family`) assigns `left = deepest`, `right = runner_up`;
   `:449` builds `options = (_option(0,left,right), _option(1,right,left))`; ORIGINAL expects
   index 0, COUNTERFACTUAL expects index 1.

So the measured competence is: **given two named leaves of an opaque bracketed tree, decide which
one's deepest occurrence is deeper.** No Lean semantics, no typing, no mathematical inference. It
is a maximum-nesting-depth comparison over a serialised tree. Calling this "mathematical
competence" is a category claim the generator does not support.

`VERDICT: intent/implementation mismatch — CONFIRMED · HIGH · FALSE_POSITIVE_RISK`

## 2. What `transitive_dependency` is intended to measure, and what it measures

**Spec (quoted).** `docs/FITNESS_V5_SPEC.md:61`:

> `transitive_dependency` | which evidence ID is an ancestor of `e:leaf` k steps away | independent ancestor closure | explicit / 2 / 3 / 5 hops

Rendered question, `arena/experiments/fitness_v4.py:560-563`: "...reached by following the
dependencies field **{hops} step(s)** from e:leaf?"

**What the generator actually measures — EVIDENCE.** `_dependency_family`
(`fitness_v4.py:517-544`) builds two disjoint chains. `e:leaf` depends on `attached[0]`, so
`a = attached[hops-1]` sits `hops` edges away. `other[0]` depends on `attached[junction]` — the
edge points *from* the distractor chain *into* the answer chain, so the distractor is **never
reachable from `e:leaf` at any distance**. The builder asserts exactly this at `:551-556`.

Measured confirmation: the covariate `dep_is_ancestor` (finite path from `e:leaf`, direction max)
separates the pair **96/96 at every level** (`predictability_matrix.json`). The literal `k` in the
question is therefore **not load-bearing**: "is X reachable at all" is sufficient and complete.
The ladder 2/3/5 hops lengthens the chain, it does not add a counting step.

So the measured competence is: **directed reachability in an adjacency list.** That is a real
traversal operation (and the cleanest of the three), but it is not "k-step arithmetic", and the
level ladder does not manipulate the depth of reasoning the question names.

`VERDICT: ladder does not manipulate the named operation — CONFIRMED · MEDIUM · FALSE_NEGATIVE_RISK`

## 3. Minimum operation genuinely required

| mechanism | minimum sufficient operation | is it mathematical? |
|---|---|---|
| `formal_expression_depth` | one left-to-right scan maintaining a bracket-balance counter; record max balance at each of two literal substrings; compare | no — string/parse counting |
| `transitive_dependency` | BFS/DFS from `e:leaf` over the `dependencies` field; membership test | yes — graph reachability |
| `precondition_conjunction` | build the `holds` set; test `requires(x,·) ⊆ holds` for each candidate | yes — finite subset test |

## 4. Can the answer be obtained without performing that operation? (worked, on real probes)

**YES for `formal_expression_depth`, at 1.000, at every level.** `worked_examples.json`, probe
`probe:e086b42ae2952b5ac3c5` (`v5:dev:formal_expression_depth:l2:fs:26b46d81572a545a`, ORIGINAL,
the cell V7 *selected*). Options A=`f12`, B=`f13`; preregistered answer **A**.

Run one pass over the visible `CURRENT STATE` text, incrementing on `{ [` and decrementing on `} ]`:

| | max bracket depth at an occurrence of the id | first char index in visible state |
|---|---|---|
| A `"f12"` | **28** | 1888 |
| B `"f13"` | 25 | 2268 |

28 > 25 -> answer A. Correct. Its COUNTERFACTUAL sibling `probe:e7ee473d71d4665f5ce0`
(preregistered answer **B**): A `"f12"` -> 25, B `"f13"` -> **28** -> answer B. Correct.
No tree is parsed, no depth semantics used, no Lean read.

Scored over the whole bank (`predictability_matrix.json`), the rule
`view_deepest_bracket_nesting` scores **acc = 1.000, n = 24, tie_rate = 0.000, binomial p = 1.19e-7**
at **each** of FED L0, L1, L2, L3 — **96/96 positives** (exact binomial p = 1.19e-7 per
cell, 2.5e-29 pooled).

A *cheaper* rule needing no counting at all also works: `first_mentioned_in_state` scores
1.000 / 0.833 / 0.917 at L1/L2/L3, and in the text the solver actually reads,
`last_mentioned_in_view` scores 0.833 / 0.917 / 0.833.

**PARTIALLY for `transitive_dependency`**: best cheap surface rule 0.833 (L1), 0.750 (L2),
0.667 (L3) — real traversal is needed for roughly a quarter to a third of items.

**NO for `precondition_conjunction`**: every cheap surface rule is exactly 0.500 at L1–L3.

`VERDICT: FED answerable without the operation — CONFIRMED · CRITICAL · BOTH`

## 5. Are labels mathematically derived, or generated from the rendered string? (decisive)

**Traced to source, and the answer is: mathematically derived. REFUTED.**

* FED: label = `structural_features(transcribe(goal["target"]))` -> `identifier_depths` tree walk
  (`formal_structural.py:138-176`). Input is Lean's own elaborated AST (Tier A), never a string.
  Verified: the AST-depth argmax reproduces the label **96/96**.
* TD: label = `ancestors(state.evidence_dependencies, "e:leaf")` closure
  (`fitness_v4.py:504, 546-556`). Verified: graph reachability reproduces the label **96/96**.
* PC: label = `satisfied_options(state)` subset check (`fitness_v4.py:713-719, 800-802`).
  Verified: the subset test reproduces the label **96/96**.

No label is derived from a property of the rendered string, and the alphabetical tie-break at
`formal_structural.py:165` cannot reach the label because `min_lead = 1` rejects any top-rank tie.

**But this exonerates nothing, and here is why.** The surface is a *lossless bracketed
serialisation of the very tree the label is an extremum of*. Under any such serialisation,
"maximum AST depth" **is** "maximum delimiter balance". The label is not string-*generated*; it is
string-*equivalent*. Measured across **all eight** candidate representations, 96 FED positives:

| surface | mean state chars | first_mentioned | last_mentioned | **max_delimiter_depth** | more_frequent |
|---|---|---|---|---|---|
| `L0_STRUCTURED_ENGLISH` | 19471 | 0.500 | 0.875 | **1.000** | 0.771 |
| `L1_CURRENT_HML` | 7672 | 0.500 | 0.771 | **1.000** | 0.771 |
| `L2_SEXPR` | 6374 | 0.500 | 0.771 | **1.000** | 0.771 |
| `L3_JSON_AST` | 20608 | 0.500 | 0.771 | **1.000** | 0.771 |
| `L4_TYPED_PREFIX` | 8218 | 0.500 | 0.875 | **1.000** | 0.771 |
| `L5_COMPACT_SYMBOLIC` | 4695 | 0.812 | 0.500 | **1.000** | 0.771 |
| `L6_GRAPH_TRIPLES` | 20756 | 0.896 | 0.500 | **1.000** | 0.771 |
| `L7_HYBRID_ROLE_LABELLED` | 8458 | 0.500 | 0.771 | **1.000** | 0.771 |

The optimal strategy on `formal_expression_depth` is **representation-invariant**: one
character-counting rule is perfect under all eight surfaces spanning a 4.4x length range. **A
Game-R founder tournament on this mechanism could not have detected a representation effect,
because there is nothing left for a representation to be better at except being shorter — which
is precisely the axis the design declares a confound** (`fitness_v5.py:867-878`).

`VERDICT: labels string-derived — REFUTED. Labels string-EQUIVALENT — CONFIRMED · CRITICAL · BOTH`

### 5b. The counterfactual control is blind by construction

`arena/environments/formal_structural.py:181-186`, `relabel` docstring:

> "It preserves the tree shape and the token multiset exactly and inverts the answer, so a model that reads structure must flip its choice while a model that reads surface statistics cannot."

**This claim is false as stated, and I measured it.** `relabel` swaps the two identities
*globally*, so any rule that is a function of the **relative** position, order, count or depth of
the two identities flips in exact lockstep with the label.

I define `cf_blindness` = fraction of ORIGINAL/COUNTERFACTUAL family pairs on which the rule is
right on both or wrong on both. 1.000 = the counterfactual has **zero** power against that rule.

| rule | FED L1 | FED L2 | FED L3 | TD L1–L3 |
|---|---|---|---|---|
| `first_mentioned_in_state` | 1.000 | 1.000 | 1.000 | 1.000 |
| `last_mentioned_in_view` | 1.000 | 1.000 | 0.833 | 1.000 |
| `more_frequent_in_state` | 1.000 | 1.000 | 1.000 | 1.000 |
| `view_deepest_bracket_nesting` | 1.000 | 1.000 | 1.000 | — |
| `alphabetically_first`, `shorter_option_text`, `always_first/second`, `first_mentioned_in_view` | 0.000 | 0.000 | 0.000 | 0.000 |

The control partitions rules into "forced to exactly 0.500" and "completely unconstrained". It has
no discriminating power anywhere in between. The worked example in §4 shows both halves flipping
together on a single real family.

`VERDICT: counterfactual control cannot detect a surface reader — CONFIRMED · CRITICAL · FALSE_POSITIVE_RISK`

### 5c. The negative control is also blind

The `VOID_NEGATIVE_CONTROL` gate (`fitness_v5.py:216-217`) needs positive − destroyed ≥ 0.20 and
destroyed ≤ 0.60. The DESTROYED pair is label-balanced by construction
(`validate_probe_family`, `fitness_v5.py:509-512`), so **every label-independent rule scores
exactly 0.500 there**. Measured:

| cell | `first_mentioned_in_state` POS / DEST | `view_deepest_bracket_nesting` POS / DEST |
|---|---|---|
| FED L1 | 1.000 / **0.500** | 1.000 / **0.500** |
| FED L2 | 0.833 / **0.500** | 1.000 / **0.500** |
| FED L3 | 0.917 / **0.500** | 1.000 / **0.500** |

A pure bracket-counter scores 1.000 positive and 0.500 destroyed: gap 0.500 ≥ 0.20, destroyed
0.500 ≤ 0.60. **It passes the negative-control gate with room to spare.**

Additionally, for FED the destroyed state is *not length-matched*: `destroy_depth_relation`
(`formal_structural.py:196-212`) replaces the whole real Lean goal with a 3-node tree, shrinking
the prompt by 1.56x–3.22x (24,683 -> 8,592 chars at L0). TD and PC destroyed states are size-matched
(ratio 1.00).

`VERDICT: negative control blind to shortcuts — CONFIRMED · HIGH · FALSE_POSITIVE_RISK`
`VERDICT: FED negative control length-confounded — CONFIRMED · MEDIUM · BOTH`

### 5d. V7's shortcut audit reads a text the solver never sees

`fitness_v5.py:798` defines the audited text as
`canonical_json(p.state.to_dict(include_display_identity=False))`. `canonical_json` sets
`sort_keys=True` (`arena/canonical/schema.py:35`), so `goal` (g) serialises **before**
`objects` (o) — `first_mentioned_in_state` is effectively "first in the goal's pre-order".

In the **rendered** control surface the order is reversed: `objects` (alphabetically sorted, all
locals) precedes the goal. Consequence, measured: `first_mentioned_in_view` is a **constant**
(0.500 in all 12 cells), while the live positional rule in the visible text is
`last_mentioned_in_view`. At the cell V7 *selected*, FED L2, that rule scores **0.917** against
the **0.833** V7 gated on.

| cell | solver | V7 best shortcut | best CHEAP surface rule in the VISIBLE text | V7 understates by |
|---|---|---|---|---|
| FED L0 | 1.000 | 0.667 | `ast_latest_preorder` 0.917 | +0.250 |
| FED L1 | 0.833 | 1.000 | `first_mentioned_in_state` 1.000 | 0.000 |
| **FED L2 (selected)** | 0.792 | 0.833 | `last_mentioned_in_view` **0.917** | **+0.083** |
| FED L3 | 0.625 | 0.917 | 0.917 | 0.000 |
| TD L2 | 0.958 | 0.625 | `dep_earlier_in_evidence_list` 0.750 | +0.125 |
| TD L3 (selected) | 0.750 | 0.667 | 0.667 | 0.000 |

Including the counting rule, FED L2's true best is **1.000** — V7 understates by 0.167.

`VERDICT: audit measures a proxy text — CONFIRMED · HIGH · FALSE_POSITIVE_RISK`

### 5e. Five of V5's seven shortcut rules are dead on this bank

| V5 rule | cells where `best != 0.500` (of 12) | why |
|---|---|---|
| `first_mentioned_in_state` | 7 | live |
| `more_frequent_in_state` | 9 | live |
| `last_mentioned_in_state` | 0 | last mention is always in the alphabetically sorted `objects` block -> constant |
| `shorter_option_text` | 0 | both ids are the same length (tie rate 0.67–1.00) |
| `alphabetically_first` | 0 | label-independent, and labels are balanced |
| `always_first_option` / `always_second_option` | 0 | same |

The effective adversary V7 gates against is **two rules**, both over the identifier's
position/frequency in a proxy text. `docs/FITNESS_V7_RESULT.md:§6` already concedes "a richer
adversary would only lower these margins further"; this audit quantifies it: at FED L2 the richer
adversary reaches 1.000.

`VERDICT: shortcut rule set is thin — CONFIRMED · MEDIUM · FALSE_POSITIVE_RISK`

## 6. `formal_expression_depth`: correlation of the target with each named axis

Per-covariate accuracy (`best = max(acc, 1-acc)`; chance 0.500; n = 24 per cell, 96 pooled).
Full matrix: `predictability_matrix.md`.

| axis | covariate | L0 | L1 | L2 | L3 |
|---|---|---|---|---|---|
| first mention (audited text) | `first_mentioned_in_state` | 0.500 | **1.000** | 0.833 | 0.917 |
| first mention (visible text) | `first_mentioned_in_view` | 0.500 | 0.500 | 0.500 | 0.500 |
| last mention (visible text) | `last_mentioned_in_view` | 0.500 | 0.833 | **0.917** | 0.833 |
| traversal order | `ast_earliest_preorder` | 0.833 | **1.000** | 0.833 | 0.917 |
| AST order (reverse) | `ast_latest_preorder` | 0.917 | 0.833 | 0.917 | 0.833 |
| option order | `always_first_option` | 0.500 | 0.500 | 0.500 | 0.500 |
| string position (delimiter depth) | `view_deepest_bracket_nesting` | **1.000** | **1.000** | **1.000** | **1.000** |
| variable naming (alphabetical) | `alphabetically_first` | 0.500 | 0.500 | 0.500 | 0.500 |
| variable naming (numeric suffix) | `larger_numeric_suffix` | 0.500 | 0.500 | 0.500 | 0.500 |
| expression / option length | `shorter_option_render` | 0.500 | 0.500 | 0.500 | 0.500 |
| delimiter count before first mention | `view_more_open_braces_before_first` | 0.500 | 0.500 | 0.500 | 0.500 |
| token count | per-item constant across options — cannot predict a 2AFC label; see §8 |
| identifier frequency | `more_frequent_in_state` | 0.667 | 0.875 | 0.667 | 0.875 |
| lexical overlap | `greater_option_state_overlap` | 0.500 | 0.500 | 0.500 | 0.500 |

**Why the positional rules work — the domain reason.** On the 104 length-fair real Lean states
(`level_confounds.json`, 87 with ≥3 identifiers), Spearman rho between an identifier's maximum AST
depth and its pre-order first-occurrence rank is **−0.781 on average**; **91.9%** of states have
negative rho; and in **79.3%** of states the deepest identifier *is literally the first identifier
in pre-order*. In Lean's curried, left-nested application spine, deeper means earlier. The target
is intrinsically confounded with reading order in the donor domain — a property of mathematics as
Lean elaborates it, not a generator bug, and therefore not fixable by regenerating probes.

`VERDICT: target correlated with traversal/position/frequency — CONFIRMED · CRITICAL · BOTH`

## 7. `transitive_dependency`: correlation of the target with each named axis

| axis | covariate | L0 | L1 | L2 | L3 |
|---|---|---|---|---|---|
| textual distance to `e:leaf` | `dep_closer_textually_to_leaf` | 0.667 | 0.500 | 0.583 | 0.500 |
| premise / field order | `dep_earlier_in_evidence_list` | 0.500 | 0.667 | **0.750** | 0.667 |
| dependency order (in-degree) | `dep_higher_in_degree` | 0.542 | 0.833 | 0.625 | 0.542 |
| first occurrence | `first_mentioned_in_state` | 1.000 | 0.500 | 0.583 | 0.667 |
| last occurrence | `last_mentioned_in_view` | 1.000 | 0.583 | 0.583 | 0.583 |
| identifier frequency | `more_frequent_in_state` | 1.000 | **0.833** | 0.625 | 0.542 |
| path length | `dep_is_ancestor` (the truth) | 1.000 | 1.000 | 1.000 | 1.000 |
| lexical overlap | `greater_option_state_overlap` | 0.500 | 0.500 | 0.500 | 0.500 |
| option order / naming / length | all | 0.500 | 0.500 | 0.500 | 0.500 |

At the selected level **L3** the strongest non-truth covariate I could construct is **0.667** —
the same value V7 reported. **I could not beat V7's own audit on this mechanism.** Its
`VOID_SHORTCUT` at margin +0.0833 vs the 0.10 gate is a genuine near-miss on a genuinely
low-leakage cell, not an artefact. The L0 1.000 is the explicit arm asserting `the_answer_is`, which
is what "explicit" means and is not a defect.

`VERDICT: transitive_dependency shortcut-dominated beyond V7's finding — REFUTED (partially exonerated)`

## 8. Do L0..L3 change only reasoning difficulty?

**No.** `cell_features.json` / `level_confounds.json`, with the real qwen38-rvn token counts joined
from the frozen artifact's `prompt_eval_count` (a genuine tokenizer measurement; no tokenizer
library is installed offline, so no proxy is used for this column — character and delimiter counts
are reported separately and labelled as such).

`formal_expression_depth` (solver 1.000 / 0.833 / 0.792 / 0.625):

| feature | L0 | L1 | L2 | L3 | rho vs level (L1–L3) |
|---|---|---|---|---|---|
| real prompt tokens (mean) | 5520 | 4283 | 5079 | 5271 | **+1.0** |
| prompt chars | 24683 | 14851 | 23328 | 24594 | **+1.0** |
| goal nodes | 38.7 | 17.0 | 38.7 | 36.3 | +0.5 |
| goal max depth | 8.0 | 5.7 | 8.0 | 9.6 | **+1.0** |
| distinct goal identifiers | 10.5 | 6.4 | 10.5 | 11.2 | **+1.0** |
| delimiter total | 1525 | 1285 | 1412 | 1499 | **+1.0** |
| target's normalised first-mention position | 0.044 | 0.111 | 0.137 | 0.117 | +0.5 |
| answer prior (share index 0) | 0.500 | 0.500 | 0.500 | 0.500 | flat (clean) |
| option count | 2 | 2 | 2 | 2 | flat (clean) |
| question text | identical at all four levels | | | | clean |

`transitive_dependency` (0.958 / 1.000 / 0.958 / 0.750): tokens 3125/2796/2968/3322 (rho +1.0 over
L1–L3), evidence nodes 9/7/9/13 (rho +1.0), **and the question text itself changes** ("2 / 3 / 5
step(s)"). `precondition_conjunction` (1.000 / 0.958 / 1.000 / 1.000): tokens 5507/4602/5350/6858,
propositions 6/4/6/10 — length rises steeply while accuracy stays pinned at ceiling.

Exonerating detail: **FED L0 and L2 use the same 12 Lean source states** (`L0 vs L2` overlap = 12,
every other pair 0). So the explicit-positive contrast at that mechanism *is* within-item and
length-matched, and L0 = 1.000 vs L2 = 0.792 is a clean effect of removing the asserted relation.

`VERDICT: levels co-vary with length, size, identifier count, delimiters, cue position — CONFIRMED · HIGH · BOTH`

## 9. Can accuracy-versus-level be read as a reasoning-difficulty curve?

**No — answered directly.** For both mechanisms whose accuracy actually moves, level, prompt
length, state size, identifier count and delimiter count are **perfectly rank-correlated across
L1–L3** (rho = +1.0), and solver accuracy is **perfectly rank-anti-correlated with prompt length**
(rho = −1.0) over the same three points. The design provides no cell in which reasoning depth
increases while length is held fixed, so the two explanations are not separable from these data.

Two honest qualifications, because this cuts both ways:

* With three levels, rho = ±1.0 carries essentially no evidential weight on its own (the
  permutation null gives p = 1/6). What is CONFIRMED is the *confound in the design*; that length
  is the *cause* is `HYPOTHESIS`, not measured.
* The FED L0-vs-L2 pair is the one length-matched contrast in the whole bank and it moves
  1.000 -> 0.792. That is genuine evidence that something other than length matters. It is also the
  only such evidence, and it compares "relation asserted" against "relation not asserted", not
  "easier reasoning" against "harder reasoning".

`VERDICT: accuracy-vs-level is not interpretable as a difficulty curve — CONFIRMED · HIGH · BOTH`

## 10. Feature table for every (mechanism, level)

Complete machine-readable table: `research/audit/a2_covariates/cell_features.json` (24 fields x 12
cells). Token counts are **real** (qwen38-rvn `prompt_eval_count`, joined by `probe_id` from the
frozen artifact); no tokenizer library (`tiktoken`, `transformers`, `sentencepiece`) is available
offline, so nothing is estimated. Character, delimiter and node counts are exact.

| cell | tokens (mean / min / max) | prompt chars | state chars | opts | goal nodes | goal max depth | distinct ids | mean id depth | objects | assumptions | props | facts | evidence nodes | delimiters | share idx0 | target 1st-mention (norm) | opt/state overlap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FED L0 | 5520 / 3665 / 7960 | 24683 | 4385 | 2 | 38.7 | 8.0 | 10.5 | 5.98 | 11.7 | 0 | 0 | 2 | 0 | 1525 | 0.500 | 0.044 | 0.891 |
| FED L1 | 4283 / 2421 / 7000 | 14851 | 3670 | 2 | 17.0 | 5.7 | 6.4 | 4.56 | 17.8 | 0 | 0 | 0 | 0 | 1285 | 0.500 | 0.111 | 0.891 |
| FED L2 | 5079 / 3224 / 7517 | 23328 | 4090 | 2 | 38.7 | 8.0 | 10.5 | 5.98 | 11.7 | 0 | 0 | 0 | 0 | 1412 | 0.500 | 0.137 | 0.891 |
| FED L3 | 5271 / 4069 / 6297 | 24594 | 4327 | 2 | 36.3 | 9.6 | 11.2 | 6.72 | 14.3 | 0 | 0 | 0 | 0 | 1499 | 0.500 | 0.117 | 0.891 |
| TD L0 | 3125 / 3109 / 3138 | 9155 | 2873 | 2 | 2 | 1 | 1 | 1.00 | 6 | 0 | 0 | 1 | 9 | 924 | 0.500 | 0.037 | 0.893 |
| TD L1 | 2796 / 2788 / 2805 | 8237 | 2519 | 2 | 2 | 1 | 1 | 1.00 | 6 | 0 | 0 | 0 | 7 | 817 | 0.500 | 0.168 | 0.893 |
| TD L2 | 2968 / 2944 / 2986 | 8707 | 2767 | 2 | 2 | 1 | 1 | 1.00 | 6 | 0 | 0 | 0 | 9 | 885 | 0.500 | 0.124 | 0.893 |
| TD L3 | 3322 / 3314 / 3336 | 9647 | 3263 | 2 | 2 | 1 | 1 | 1.00 | 6 | 0 | 0 | 0 | 13 | 1021 | 0.500 | 0.207 | 0.893 |
| PC L0 | 5507 / 5495 / 5521 | 16482 | 3923 | 2 | 2 | 1 | 1 | 1.00 | 6 | 12 | 6 | 1 | 0 | 1464 | 0.500 | 0.326 | 0.896 |
| PC L1 | 4602 / 4583 / 4611 | 13779 | 3296 | 2 | 2 | 1 | 1 | 1.00 | 6 | 10 | 4 | 0 | 0 | 1223 | 0.500 | 0.448 | 0.896 |
| PC L2 | 5350 / 5339 / 5365 | 16029 | 3812 | 2 | 2 | 1 | 1 | 1.00 | 6 | 12 | 6 | 0 | 0 | 1425 | 0.500 | 0.439 | 0.896 |
| PC L3 | 6858 / 6841 / 6869 | 20529 | 4844 | 2 | 2 | 1 | 1 | 1.00 | 6 | 16 | 10 | 0 | 0 | 1829 | 0.500 | 0.427 | 0.896 |

Target-position distribution is exactly 0.500 in every cell (balanced by construction), and option
count is 2 everywhere. Both are clean.

## 11. Per-covariate predictability matrix (the headline)

`best = max(acc, 1-acc)`, positives only (V7's own audit scope), n = 24 per cell.
Chance = 0.500 exactly. Full 40-row matrix with `acc`, `tie_rate`, binomial p and `cf_blindness`:
`predictability_matrix.{md,json}`. `*` marks V5/V7's inherited rules (all reproduce V7 exactly).

| covariate | family | FED L0 | FED L1 | FED L2 | FED L3 | TD L0 | TD L1 | TD L2 | TD L3 | PC L0 | PC L1 | PC L2 | PC L3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `view_deepest_bracket_nesting` | rendered-string depth | **1.000** | **1.000** | **1.000** | **1.000** | 1.000 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `view_greater_mean_bracket_nesting` | rendered-string depth | 0.917 | 1.000 | 0.917 | 1.000 | 1.000 | 0.500 | 0.500 | 0.500 | 1.000 | 0.500 | 0.500 | 0.500 |
| `first_mentioned_in_state*` | string position | 0.500 | **1.000** | 0.833 | 0.917 | 1.000 | 0.500 | 0.583 | 0.667 | 1.000 | 0.500 | 0.500 | 0.500 |
| `last_mentioned_in_view` | string position | 0.500 | 0.833 | **0.917** | 0.833 | 1.000 | 0.583 | 0.583 | 0.583 | 0.500 | 0.500 | 0.500 | 0.500 |
| `ast_earliest_preorder` | traversal order | 0.833 | 1.000 | 0.833 | 0.917 | — | — | — | — | — | — | — | — |
| `ast_latest_preorder` | traversal order | 0.917 | 0.833 | 0.917 | 0.833 | — | — | — | — | — | — | — | — |
| `more_frequent_in_state*` | frequency | 0.667 | 0.875 | 0.667 | 0.875 | 1.000 | 0.833 | 0.625 | 0.542 | 1.000 | 0.500 | 0.500 | 0.500 |
| `ast_greater_mean_depth` | structural | 0.792 | 0.958 | 0.792 | 0.667 | — | — | — | — | — | — | — | — |
| `ast_greater_min_depth` | structural | 0.708 | 0.875 | 0.708 | 0.542 | — | — | — | — | — | — | — | — |
| `dep_earlier_in_evidence_list` | field order | — | — | — | — | 0.500 | 0.667 | **0.750** | 0.667 | — | — | — | — |
| `dep_higher_in_degree` | frequency | 0.500 | 0.500 | 0.500 | 0.500 | 0.542 | 0.833 | 0.625 | 0.542 | 0.500 | 0.500 | 0.500 | 0.500 |
| `dep_closer_textually_to_leaf` | string position | — | — | — | — | 0.667 | 0.500 | 0.583 | 0.500 | — | — | — | — |
| `first_mentioned_in_view` | string position | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `last_mentioned_in_state*` | string position | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `alphabetically_first*` | naming | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `shorter_option_text*` | naming | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `larger/smaller_numeric_suffix` | naming | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `view_more/fewer_open_braces_before_first` | delimiter count | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `greater_option_state_overlap` | lexical overlap | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `shorter_option_render` | length | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `always_first_option*` / `always_second_option*` | option order | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| `prem_all_matched` / `prem_fewer_unmatched` (**the truth**) | structural | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 | **1.000** | **1.000** | **1.000** | **1.000** |
| `dep_is_ancestor` (**the truth**) | structural | 0.500 | 0.500 | 0.500 | 0.500 | **1.000** | **1.000** | **1.000** | **1.000** | 0.500 | 0.500 | 0.500 | 0.500 |
| `ast_greatest_depth` (**the truth**) | structural | **1.000** | **1.000** | **1.000** | **1.000** | — | — | — | — | — | — | — | — |

**Solver against the best available covariate** (solver accuracy read from the frozen artifact;
`solver_vs_covariates.md`):

| cell | solver | best cheap surface rule | best counting rule | cheap margin |
|---|---|---|---|---|
| FED L0 | 1.000 | 0.917 | 1.000 | +0.083 |
| FED L1 | 0.833 | 1.000 | 1.000 | **−0.167** |
| FED L2 (selected) | 0.792 | 0.917 | 1.000 | **−0.125** |
| FED L3 | 0.625 | 0.917 | 1.000 | **−0.292** |
| TD L0 | 0.958 | 1.000 | — | −0.042 |
| TD L1 | 1.000 | 0.833 | — | +0.167 |
| TD L2 | 0.958 | 0.750 | — | +0.208 |
| TD L3 (selected) | 0.750 | 0.667 | — | +0.083 |
| PC L0 | 1.000 | 1.000 | — | 0.000 |
| PC L1 | 0.958 | 0.500 | 0.500 | +0.458 |
| PC L2 | 1.000 | 0.500 | 0.500 | +0.500 |
| PC L3 | 1.000 | 0.500 | 0.500 | +0.500 |

**The solver never beats the best surface rule on `formal_expression_depth` at any level except
the explicit arm — it is beaten by 0.125–0.292 at every implicit level.**

---

## 12. Classified flaw list

| # | finding | class | severity | effect |
|---|---|---|---|---|
| F1 | FED's target is reproduced **1.000** by a bracket-balance counter over the rendered string, on **all eight** candidate surfaces (96/96, exact binomial p = 2.5e-29). The optimal strategy is representation-invariant, so a Game-R tournament on this mechanism could not detect a representation effect. | CONFIRMED | CRITICAL | BOTH |
| F2 | The `relabel` counterfactual cannot detect a surface reader. Its docstring claim (`formal_structural.py:184-186`) is refuted by measurement: `cf_blindness` = 1.000 for every order/position/frequency/depth rule; the control forces the remaining rules to exactly 0.500 and has no power in between. | CONFIRMED | CRITICAL | FALSE_POSITIVE_RISK |
| F3 | The destroyed negative control is label-balanced, so **every** surface rule scores exactly 0.500 there. A perfect bracket-counter passes `VOID_NEGATIVE_CONTROL` (gap 0.500, destroyed 0.500). | CONFIRMED | HIGH | FALSE_POSITIVE_RISK |
| F4 | V7's shortcut audit is computed on `canonical_json(state)` (sorted keys: `goal` before `objects`), **not** the rendered prompt. `first_mentioned_in_view` is a constant 0.500; the live visible-text rule is `last_mentioned_in_view`, which at the *selected* FED L2 scores 0.917 vs the audited 0.833 (1.000 including the counting rule). | CONFIRMED | HIGH | FALSE_POSITIVE_RISK |
| F5 | FED and TD level ladders confound difficulty with length: rho(level, real prompt tokens) = +1.0 and rho(accuracy, tokens) = −1.0 across L1–L3, plus co-varying goal size, identifier count, delimiter count and cue position. No length-matched difficulty contrast exists. | CONFIRMED (confound); HYPOTHESIS (causation) | HIGH | BOTH |
| F6 | In the donor domain, max AST depth is anti-correlated with pre-order position: mean Spearman rho = **−0.781**, 91.9% of states negative, deepest == first in **79.3%**. The FED target is intrinsically confounded with reading order; regenerating probes cannot fix it. | CONFIRMED | HIGH | FALSE_POSITIVE_RISK |
| F7 | FED's destroyed control is 1.56x–3.22x shorter than its positives (24,683 -> 8,592 chars at L0), so it confounds "relation destroyed" with "state shrunk". TD/PC are size-matched. | CONFIRMED | MEDIUM | BOTH |
| F8 | Only **2 of 7** V5 shortcut rules are ever live on this bank; the other five are exactly 0.500 in all 12 cells. The gated adversary is far weaker than the rule count suggests. | CONFIRMED | MEDIUM | FALSE_POSITIVE_RISK |
| F9 | TD's ladder does not manipulate the named operation: the distractor is unreachable at **every** distance (`dep_is_ancestor` separates 96/96), so the "2/3/5 step(s)" wording — which itself changes the prompt across levels — is decorative. | CONFIRMED | MEDIUM | FALSE_NEGATIVE_RISK |
| F10 | Probe selection is conditioned on a **surface** property: every state must render under 30,000 chars in all eight surfaces (`fitness_v5.py:180, 882-889`), keeping 104 of 461 eligible states (34/34/36). The sample is defined by the very axis the design treats as a confound. | CONFIRMED | MEDIUM | FALSE_NEGATIVE_RISK |
| R1 | **Labels are NOT string-generated.** All three truths are re-derived from the canonical object (AST walk / ancestor closure / subset test) and each reproduces its label 96/96. The alphabetical tie-break at `formal_structural.py:165` cannot reach the label (`min_lead=1`). | REFUTED | — | — |
| R2 | **`precondition_conjunction` is construct-clean.** Every cheap surface covariate = 0.500 at L1–L3, in all eight surfaces; only the truth rule separates. Its `VOID_CEILING` is a difficulty-range problem, not a validity problem. | REFUTED | — | — |
| R3 | **Option position, identifier naming, option length, and option/state lexical overlap carry no signal** — exactly 0.500 in all 12 cells. The position-swap arm and balanced labels work. | REFUTED | — | — |
| R4 | **FED L0 vs L2 is a clean within-item contrast** — the same 12 Lean source states, length-matched, 1.000 -> 0.792 on removing the asserted relation. The explicit-positive arm is well designed. | REFUTED | — | — |
| R5 | **I could not beat V7's own audit on `transitive_dependency` at its selected level.** Best non-truth covariate at TD L3 = 0.667, identical to V7's. Its +0.0833 margin miss is a real near-miss on a genuinely low-leakage cell. | REFUTED | — | — |

## 13. Answer to the central question

The measurement system is wrong in a specific, demonstrable way, and the direction matters.

`formal_expression_depth` — the mechanism carrying the whole "real Lean mathematics" claim — does
not measure a mathematical competence and cannot measure a representation effect. Its label is a
tree-depth extremum, which under any lossless bracketed serialisation *is* a delimiter-balance
extremum; a one-pass character counter reproduces it perfectly under all eight candidate surfaces.
Both of its designed controls (relabel counterfactual, destroyed negative) are provably blind to
exactly that strategy. V7 was right to void it, but voided it for a weaker reason than the true
one, and understated its leakage at the level it selected.

`precondition_conjunction` is clean and only ceiling-limited. `transitive_dependency` is the one
mechanism whose near-miss survives an adversarial re-audit.

So: **"zero qualified mechanisms" is not evidence that representation does not matter.** One
mechanism was never capable of testing the hypothesis, one was saturated, and one came within
0.017 of a preregistered threshold on 24 items. `docs/FITNESS_V7_RESULT.md:§6`'s own statement —
"No representation was scored at any point" — remains the correct reading, and this audit
strengthens it: on the mechanism that dominated the bank, scoring a representation would have been
uninformative even if it had been done.

`docs/FITNESS_V7_RESULT.md:§7`'s conclusion (do not build V8 on this probe bank) is supported and,
on this evidence, understated: any successor task family must be checked for
**serialisation-equivalence of its label** (F1), and must not rely on a global-relabel
counterfactual or a balanced destroyed arm as its shortcut defence (F2, F3).
