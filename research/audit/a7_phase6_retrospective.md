# Audit Part K — Phase-5/6 Retrospective and Process Failure

**Auditor 7 of 9 · V7 Total Forensic Audit · adversarial brief: destroy the argument, not defend it.**

Scope: how the programme reached "`transitive_dependency` qualified" in Phase 6 and zero in V7,
and what process failure allowed `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` to recommend a
founder tournament on an un-audited level.

**Method.** Read-only. **Zero model/LLM calls, no GPU, no network, laptop only.** No existing file
was modified. New files are confined to `research/audit/a7_phase6_retrospective.md` and
`research/audit/a7_retro/`. Nothing here re-scores V5, V6/Phase 6 or V7, changes a threshold, or
reinterprets a recorded sentinel. Every number below is either (a) a field the run itself wrote
into its own artifact, or (b) a pure probe-bank computation reproduced independently by this audit.

Scripts and outputs:

| File | Purpose |
|---|---|
| `research/audit/a7_retro/verify_v5_shortcut_at_every_level.py` | Q4. Rebuilds the frozen V5 DEV pool; runs V5's own `shortcut_audit` at every level; cross-checks with an independent re-implementation of `first_mentioned_in_state`. |
| `research/audit/a7_retro/v5_shortcut_every_level.json` | Its output. |
| `research/audit/a7_retro/gate_by_gate_diff.py` | Q1, Q9. Extracts the recorded gate results from the three frozen artifacts; recounts Phase-6 cache hits. |
| `research/audit/a7_retro/gate_by_gate_diff.json` | Its output. |

Commands actually executed (venv `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`):

```
python -m research.audit.a7_retro.verify_v5_shortcut_at_every_level
python -m research.audit.a7_retro.gate_by_gate_diff
```

Artifact identities verified in this audit (sha256, recomputed):

| Artifact | sha256 |
|---|---|
| `artifacts/experiments/fitness_v5/development/result.json` (V5 / Phase 5, gemma framed) | `0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579` |
| `.../result-qwen38-rvn_latest-bare.json` (Phase 6, qwen bare) | `e753de987dab6c3a95fc07581e85b93a7812cc77b4905a086dd2d6848be4916a` |
| `artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json` | `ecdefc4f8399f82160e577050312781c2899d1f48e9a157a157c661b67fc13db` |

DEV pool hash reproduced by this audit: `f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b`
— identical in all three artifacts. **The probe bank is byte-identical across V5, Phase 6 and V7,
so every shortcut number in this report is solver-independent and was computable at zero cost from
the moment V5 was written.**

---

## Q1. The exact gate-by-gate difference between Phase 6 and V7

`CONFIRMED`. Source: `research/audit/a7_retro/gate_by_gate_diff.json`, extracted from the two
artifacts' own `mechanisms.<m>.qualification.checks` fields.

### `transitive_dependency` — the only mechanism that ever qualified

Both versions **selected the same level (L3)** with the **same accuracy (0.7500)** and the **same
best-shortcut value (0.6667, `first_mentioned_in_state`)**. Every gate that exists in both versions
returns the same answer.

| Gate | Phase 6 (V5 rule) | V7 rule | Value seen | Phase 6 | V7 |
|---|---|---|---|---|---|
| `q0` ≥ 0.95 | yes | yes | 1.000 | PASS | PASS |
| `valid_response` ≥ 0.95 | yes | yes | 1.000 | PASS | PASS |
| `context` truncated ≤ 0 | yes | yes | 0 | PASS | PASS |
| `sample_size` ≥ 24 | yes | yes | 24 | PASS | PASS |
| `negative_collapse` gap ≥ 0.20 | yes | yes | 0.250 | PASS | PASS |
| `destroyed ≤ 0.60` | yes | **dropped** | 0.500 | PASS | n/a |
| `answer_share` ≤ 0.75 | yes | yes | 0.500 | PASS | PASS |
| `position_invariance` ≥ 0.50 | yes | yes | 0.8333 | PASS | PASS |
| `shortcut_absolute` ≤ 0.75 | yes (as `shortcut`) | yes | 0.6667 | PASS | PASS |
| **`shortcut_margin` ≥ 0.10** | **does not exist** | **new** | **+0.08333** | — | **VOID_SHORTCUT** |

**Exactly one gate changed the answer: `shortcut_margin`, which did not exist in V5.** It is
defined at `arena/experiments/fitness_v7.py:175` (`SHORTCUT_MARGIN = 0.10`) and evaluated at
`fitness_v7.py:752-755`. Observed margin `0.08333`; required `0.10`; shortfall `0.01667`
(`gate_by_gate_diff.json → mechanisms.transitive_dependency.v7.qualification.shortcut_margin_observed`).

The dropped `destroyed ≤ 0.60` gate is not load-bearing: destroyed accuracy is 0.5000, so the gate
passed under V5 too.

### `formal_expression_depth` — where the selector moved

| | Phase 6 | V7 |
|---|---|---|
| `frontier_target` | **0.625** (`fitness_v5.py:213`, declared constant) | **0.775** (`fitness_v7.py:256`, derived: `(0.50 + 0.20 + 0.85)/2`) |
| selected level | **L3** | **L2** |
| positive accuracy | 0.6250 | 0.7917 |
| `negative_collapse` (gap ≥ 0.20) | 0.125 → **VOID_NEGATIVE_CONTROL** | 0.2917 → PASS |
| `shortcut_absolute` (≤ **0.75**, unchanged) | 0.9167 → **VOID_SHORTCUT** | 0.8333 → **VOID_SHORTCUT** |
| `shortcut_margin` (≥ 0.10) | gate absent | −0.0417 → **VOID_SHORTCUT** |
| published `verdict` | `VOID_NEGATIVE_CONTROL` | `VOID_SHORTCUT` |
| `all_failures` | **field does not exist in V5** | `['shortcut_absolute','shortcut_margin']` |

**The critical row is `shortcut_absolute`.** Its threshold is *identical* in both versions
(`shortcut_rule_max = 0.75`, `fitness_v5.py:225`, inherited unchanged into
`QUALIFICATION_RULE_V7` at `fitness_v7.py:260`). It **failed in Phase 6 too** — the Phase-6
artifact's own `checks` dict records `"shortcut": "VOID_SHORTCUT"` at L3 with
`worst_score = 0.9166666666666666`. It was invisible only because `verdict` reports `failures[0]`
(§Q5).

### `precondition_conjunction`

Identical in both: `VOID_CEILING`, selector never reaches a level, no gates evaluated. Ladder
1.000 / 0.958 / 1.000 / 1.000 in both.

### Summary — the gate-by-gate answer

- **Phase 6 → 1 qualified.** `transitive_dependency` passed all eight V5 gates at L3.
- **V7 → 0 qualified.** `transitive_dependency` lost to **one new gate** (`shortcut_margin`, by
  0.0167); `formal_expression_depth` lost to a gate that had **already failed under V5** but had
  been masked; `precondition_conjunction` was unchanged.
- **Nothing about the solver, probes, prompts or decoding changed.** V7 reproduced every Phase-6
  ladder value exactly (verified: `gate_by_gate_diff.json`, all three ladders identical; and for
  `transitive_dependency`, the entire `full_family_summary` is identical field-for-field), from
  864 fresh calls with **zero** cache hits.

---

## Q2. Was Phase 6 scientifically wrong, or applying a weaker preregistered criterion?

The brief's three-way distinction is the right frame, and Phase 6 sits in **all three boxes for
different claims**. Grading them together would be unfair and would also let the worst one hide.

### (a) Phase 6's per-mechanism verdicts: **NOT WRONG.** `CONFIRMED`.

Phase 6 ran the frozen V5 code, on the frozen probe bank, and reported what it emitted.
`transitive_dependency` genuinely passes every gate V5 defines. V7 reproduced the numbers exactly
from fresh calls. A later, stricter rule reaching a different answer is not misconduct, and the V7
result document says so itself (`docs/FITNESS_V7_RESULT.md:78-79`: "Under V5's frozen rules it
qualifies. Phase 6's finding stands on its own terms."). **Severity: none. Effect: none.**

### (b) Phase 6's *sentinel choice*: **WEAKER CRITERION, AND THE CRITERION WAS NEVER WRITTEN DOWN.** `CONFIRMED`. Severity: MEDIUM.

`docs/PHASE6_PREREGISTRATION.md` (STOPPING_RULE) lists four legal sentinels but **defines the data
condition for none of them**. The mapping from result to label was therefore completed *after*
seeing the result, in `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:126` ("qwen materially escapes
gemma's collapse **and** one preregistered mechanism qualified").

The only written gloss of Branch A anywhere is `docs/PHASE6_INTEGRATION_MAP.md:119`: "**A second
Solver family qualifies ≥ 2 V5 mechanisms.**" Phase 6 qualified **1**. On the plain reading of the
two candidate labels, `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET` fits the data better than
`SOLVER_SPECIFIC_FAILURE_SUPPORTED` — Phase 6's own §9 records
`founder_tournament_authorized = false`. **Effect:** the headline label overstates by one
qualification-tier; the underlying measurements are unaffected.

### (c) Phase 6 §11: **REPORTED A COUNTERFACTUAL IT HAD NOT MEASURED — and that was already refuted in writing.** `CONFIRMED`. Severity: **HIGH**.

`docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:174-175`:

> "Under fix (1) alone, `formal_expression_depth` would have selected L2 (.792) and passed the gap
> and share gates — giving 2 qualified mechanisms and authorising the founder tournament."

The two *named* gates (gap, share) do pass at L2 — that part is true. The **conclusion** does not
follow, and is false under V5's own unmodified rules (§Q4). This is not "a weaker criterion"; it is
an outcome claim about an arm that was never gated, published as the basis for the single
highest-value next experiment, in a document whose own §9 correctly refuses to authorise a
tournament.

**Verdict on Q2:** Phase 6 was *not* scientifically wrong about what it measured. It was wrong
about what it had not measured, and it recommended acting on that.

---

## Q3. The exact V5 flaw — shortcut auditing only at the selected frontier

`CONFIRMED`. Three distinct defects, not one. All in `arena/experiments/fitness_v5.py`.

### Defect 3a — the in-run audit sees exactly one level

```python
1070:        if selection["selected_level"] is not None:
1071:            level = int(selection["selected_level"])
1072:            full = by_cell[(mechanism, level)]
1073:            result = evaluate(root, control, full, solver=solver, bare=bare)
1074:            audit = shortcut_audit(tuple(full))
1075:            qualification = qualify_mechanism(result["summary"], audit, q0["rate"])
```

`shortcut_audit` is invoked **once per mechanism**, over `full = by_cell[(mechanism, level)]` — the
72 probes of the **single selected level** (`shortcut_audit` then filters to the 24
`POSITIVE_VARIANTS` at `:791`). `level` comes from `select_frontier_level(accuracies)` at `:1062`.
Every non-selected level is never audited.

### Defect 3b — when no level is selected, no shortcut audit runs at all

The call sits inside `if selection["selected_level"] is not None:` (`:1070`). Whenever the selector
returns `VOID_CEILING`, `VOID_FLOOR` or `VOID_INSTRUMENT_LIMIT`, the mechanism is voided with **zero
shortcut information**. Verified in the artifacts: `result-gemma4_12b-bare.json` has **no
`shortcut_audit` key for any of its three mechanisms**; the Phase-6 qwen artifact has none for
`precondition_conjunction`.

### Defect 3c — the only *pre-run* audit pools across mechanisms **and** levels, and reports CLEAN

`fitness_v5.py:1184`, inside `main()`'s `materialize` command:

```python
1184:                    "shortcut_audit": shortcut_audit(probes),
```

`probes` is the **entire 864-probe DEV pool**. Reproduced by this audit:

```
WHOLE-POOL audit (what fitness_v5.py:1184 materialize prints):
  items 288  worst more_frequent_in_state  0.7153  status CLEAN
```

**This is the number the V5 preregistration reports.** `docs/FITNESS_V5_SPEC.md:89` (§4):

> "The strongest dumb rule on the DEV pool is `more_frequent_in_state` at **0.72** against a 0.75
> threshold … This is reported, not hidden."

0.7153 rounds to 0.72. **The provenance of the spec's headline residual-risk figure is now
established: it is the cross-mechanism, cross-level pooled statistic, and it is CLEAN.** The
per-mechanism, per-level truth for `formal_expression_depth` is 0.500 / **1.000** / **0.833** /
**0.917** with `first_mentioned_in_state` — a different rule, and above the ceiling at three of four
levels. **Pooling diluted a 1.000 leak into a 0.7153 pass.**

**Consequence:** V5 possessed *no* code path that could ever compute a per-mechanism, per-level
shortcut number. The leak was not merely unreported — it was structurally uncomputable at every
point where a decision was made. This is one level deeper than "the audit ran only at the frontier".

---

## Q4. Direct verification — `first_mentioned_in_state` at L1 and L2

`CONFIRMED`. Command and output:

```
$ /Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python \
    -m research.audit.a7_retro.verify_v5_shortcut_at_every_level

dev pool: 864 probes, hash f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b
V5 shortcut_rule_max = 0.75  (fitness_v5.py:225)

cell                                   first_mentioned                    best_rule    best  status
---------------------------------------------------------------------------------------------------
formal_expression_depth/L0                      0.5000       more_frequent_in_state  0.6667   CLEAN
formal_expression_depth/L1                      1.0000     first_mentioned_in_state  1.0000   LEAKS
formal_expression_depth/L2                      0.8333     first_mentioned_in_state  0.8333   LEAKS
formal_expression_depth/L3                      0.9167     first_mentioned_in_state  0.9167   LEAKS
precondition_conjunction/L0                     1.0000     first_mentioned_in_state  1.0000   LEAKS
precondition_conjunction/L1                     0.5000          always_first_option  0.5000   CLEAN
precondition_conjunction/L2                     0.5000          always_first_option  0.5000   CLEAN
precondition_conjunction/L3                     0.5000          always_first_option  0.5000   CLEAN
transitive_dependency/L0                        1.0000     first_mentioned_in_state  1.0000   LEAKS
transitive_dependency/L1                        0.5000       more_frequent_in_state  0.8333   LEAKS
transitive_dependency/L2                        0.5833       more_frequent_in_state  0.6250   CLEAN
transitive_dependency/L3                        0.3333     first_mentioned_in_state  0.6667   CLEAN

{
 "L1_exceeds_0_75": true,
 "L1_first_mentioned_in_state": 1.0,
 "L2_exceeds_0_75": true,
 "L2_first_mentioned_in_state": 0.8333333333333334,
 "verdict": "CONFIRMED"
}

independent re-implementation disagreements: 0
```

**Calculation:** `1.0000 > 0.75` and `0.8333 > 0.75`. Both exceed V5's own frozen
`QUALIFICATION_RULE["shortcut_rule_max"] = 0.75` at `arena/experiments/fitness_v5.py:225`.

**Triple-independent agreement.** These values are reproduced by three separately written code
paths: (1) this audit's re-implementation (0 disagreements against V5's frozen rule);
(2) `research/codex_audit/formal_depth_shortcuts.json` (committed `8caeaa0`, **2026-09-07
08:24:50**, rule named `first_mentioned_in_serialized_state`: L1 24/24 = 1.000, L2 20/24 = 0.8333,
L3 22/24 = 0.9167); (3) the V7 run's own
`mechanisms.formal_expression_depth.shortcut_audit_by_level` in the frozen V7 artifact.

**Consequence.** `formal_expression_depth` has **no** level ≥ 1 that clears V5's own shortcut
ceiling. L1 = 1.000, L2 = 0.8333, L3 = 0.9167, all > 0.75. **It was unqualifiable under V5's
unmodified rules at every level the selector could ever pick.** No V7 gate is needed to void it, and
no selector fix could have rescued it. Phase 6 §11 is `REFUTED` by V5's own frozen constant.

---

## Q5. Why it was not detected before the recommendation was written

`CONFIRMED`. Four compounding mechanisms; the brief's hypothesis (`failures[0]`) is correct but is
only the third of them.

### 5.1 The gate could not be computed off-frontier (Q3a/3b/3c). Root cause.

### 5.2 The gates are evaluated as an ordered dict, and `shortcut` is **last**

`fitness_v5.py:955-979` builds `checks` in this insertion order:
`q0 · valid_response · context · sample_size · negative_collapse · answer_share ·
position_invariance · shortcut`.

### 5.3 `verdict` reports **only the first** failure

```python
980:    failures = [code for code in checks.values() if code != "PASS"]
981:    return {
982:        "checks": checks,
983:        "qualified": not failures,
984:        "verdict": failures[0] if failures else "QUALIFIED",
985:    }
```

`fitness_v5.py:984`. Because `shortcut` is last in the dict, **any** earlier failure hides it. V7
fixes exactly this by adding `all_failures` at `fitness_v7.py:766`.

**Measured blast radius.** Sweeping all three V5-era artifacts for
`checks["shortcut"] != "PASS" AND verdict != "VOID_SHORTCUT"`:

| Artifact | Mechanism | Level | `checks.shortcut` | `worst_score` | published `verdict` | masked? |
|---|---|---|---|---|---|---|
| `result.json` (Phase 5, gemma framed) | `formal_expression_depth` | **L2** | `VOID_SHORTCUT` | **0.8333** | `VOID_NEGATIVE_CONTROL` | **YES** |
| `result-qwen38-rvn_latest-bare.json` (Phase 6) | `formal_expression_depth` | L3 | `VOID_SHORTCUT` | 0.9167 | `VOID_NEGATIVE_CONTROL` | **YES** |

Two of the two mechanisms that ever reached the gates with a shortcut failure had that failure
masked. **The masking rate on the population where it could fire is 2/2.**

### 5.4 …but the number was published anyway, and the recommendation still ignored it

This is the part that defeats the "we could not have known" defence, and it is `CONFIRMED`:

**`docs/FITNESS_V5_RESULT.md:32`** (commit `2c61fdb`, **2026-09-07 02:16:31**) — the per-mechanism
table's Verdict column reads, in full:

> `VOID_NEGATIVE_CONTROL` (+ `VOID_SHORTCUT`)

The Phase-5 author **manually surfaced the masked co-failure**. And **`docs/FITNESS_V5_RESULT.md:69-72`**:

> "It also **leaks**: `first_mentioned_in_state` reaches **0.833** at that stratum … That is a
> genuine construction defect of this mechanism, predicted as a risk in the spec (§4) at 0.72
> pool-wide and realised at 0.833 in the selected cell."

Phase 5's selected stratum **was L2** (`result.json → mechanisms.formal_expression_depth.selected_level = 2`).
The shortcut audit is a pure function of the probe bank, which is byte-identical across V5, Phase 6
and V7 (same `dev_pool_hash`). **Therefore the number 0.833, for the exact cell §11 proposed to
select, was published in the programme's own preceding result document 9 hours 18 minutes before
§11 was written** — and independently again by the Codex audit at 08:24:50, 3 hours 10 minutes
before.

**Mechanism of the miss, stated precisely:** §11 reasoned from the *ladder accuracies* and the two
gates it happened to name, never opening either the `checks` dict in the artifact it was describing
or the preceding result document's own table for the same mechanism. The `failures[0]` defect made
the failure invisible in the *machine* verdict; it did **not** make it invisible in the *prose*
record. The miss was a failure to re-check, not a failure of instrumentation alone.

*Fairness note, `CONFIRMED`:* the Codex audit branch was **not** an ancestor of the Phase-6 result
commit (`git merge-base --is-ancestor 8caeaa0 b3717c3` → NO; it merged only at `4da1d00`,
12:19:19). So that file was plausibly not in the Phase-6 working tree. `docs/FITNESS_V5_RESULT.md`
and the artifacts unambiguously were.

---

## Q6. The process failure that allowed the founder-tournament recommendation

`CONFIRMED`. Reconstruction:

**Who computed what.**

| Step | Actor | Computed | Artifact |
|---|---|---|---|
| 02:16 | Phase 5 | L2 shortcut = 0.833, flagged `(+ VOID_SHORTCUT)` in prose | `docs/FITNESS_V5_RESULT.md:32,69-72` |
| 05:42 | Phase 6 prereg | selector/gap arithmetic; window [0.70,0.85] | `docs/PHASE6_PREREGISTRATION.md` |
| 08:24 | Codex audit (separate branch) | full per-level shortcut table; "**Do not patch the current Phase 6 protocol**" | `docs/codex_audit/FORMAL_DEPTH_SHORTCUT_AUDIT.md`, `research/codex_audit/formal_depth_shortcuts.json` |
| 11:34 | Phase 6 result | ladders, verdicts, §11 counterfactual | `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` |
| 11:38 | Parallel branch | selector operating characteristics; "**the naive fix is worse than the defect**"; midpoint selector FP 0.533 vs oracle 0.254 | `docs/PHASE6_INTEGRATION_MAP.md` §8, `artifacts/reports/v5_selector_analysis.json` |

**What was NOT computed before §11 was written.** The shortcut audit at L1 or L2 for
`formal_expression_depth` under Phase 6's own hand — a **zero-cost, zero-model, sub-second
computation** on a probe bank already loaded in memory (`shortcut_audit(by_cell[(m, 1)])`). Also
never computed at L2: `position_invariance` and the swap arms (Phase 6 evaluated full-family rows at
the selected level **only** — verified: `mechanisms.formal_expression_depth.rows` contains 72 rows,
all `level == 3`). So §11's "would have … passed" rested on **two** of the eight gates, with three
others (`shortcut`, `position_invariance`, `valid_response` at L2) simply not evaluated.

**Two further reporting failures in the same document.**

1. **`CONFIRMED`, severity HIGH.** `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:138` reports
   "`cache hits on the alternate solver | 0`". This audit counts **61** independently
   (`gate_by_gate_diff.json → phase6_cache_census`: `ladder_rows` 13 + `formal_expression_depth`
   24 + `transitive_dependency` 24 = 61), matching two prior audits. **The artifact contains no
   top-level cache-hit field at all** — `run_development` computes `cache_hits` per `evaluate()`
   call (`fitness_v5.py:786`) but never aggregates it into the payload (verified: zero keys matching
   `cache` in the Phase-6 payload's top level). The "0" was therefore **not transcribed from any
   recorded field; it was asserted.** *The preregistered invalidation rule keyed on a quantity the
   pipeline never wrote.* A rule that cannot be evaluated from the artifact is unenforceable by
   construction — a deeper defect than "the rule was too strict".
2. **`CONFIRMED`, severity MEDIUM.** `docs/GAME_R_STATUS.md` was edited by the Phase-6 session
   (commit `b3717c3`) to add, at `:49-50`, "The next version *is* now justified, because the
   frontier selector is demonstrably miscalibrated" — thereby authorising, in a mutable status
   document, the very follow-up the same session had just recommended. The frozen
   `docs/FITNESS_V5_SPEC.md:167-168` says the opposite: "A new version is admissible only if it
   changes a frozen variable class (C/B, D or π) named in the prior failure analysis; **re-tuning
   thresholds is not a new attempt.**" The parallel branch flagged this conflict at
   `docs/PHASE6_INTEGRATION_MAP.md` §8 ("under `docs/FITNESS_V5_SPEC.md` §9 a selector repair alone
   is threshold re-tuning and does **not** by itself license a new instrument version").

**The same error then recurs in the document written to fix it.** `CONFIRMED`, severity MEDIUM.
`docs/FITNESS_V7_PREREGISTRATION.md:15` states: "`docs/GAME_R_STATUS.md` permits a new instrument
version only when a frozen variable class named in the failure analysis changes, **or when the
instrument is shown defective**." The words "or when the instrument is shown defective" **do not
appear in `docs/GAME_R_STATUS.md`** (verified by grep: no occurrence of "defective" or "admissible"
in that file). V7 cited a permission clause that does not exist in the document it cited. *Effect:
none on the result* — V7 was strictly stricter and returned zero, so the breach could not
manufacture a pass — *but the failure mode is identical to §11's: an assertion about a source that
was never re-opened.*

**The review step that would have caught it — precisely.** One line, before writing §11:

```python
shortcut_audit(tuple(by_cell[("formal_expression_depth", 2)]))
# -> {'worst_rule': 'first_mentioned_in_state', 'worst_score': 0.8333, 'status': 'LEAKS'}
```

Zero model calls, milliseconds. Equivalently: re-reading `docs/FITNESS_V5_RESULT.md:32` — the
immediately preceding result document, for the same mechanism, in the same programme.

**Root process failure, named:** *the programme has no rule requiring that a proposed level be
gated before it is described as passing.* Every gate function in V5 is reachable only through
`run_development`'s single selected level; there is no API for "score this hypothetical level", and
therefore no habit of doing so. The counterfactual was cheap, decisive, and nobody was required to
run it.

---

## Q7. Proposed regression rule — *never infer qualification of an un-audited level*

Specification only; **not implemented here.**

### Rule R-K1 (normative)

> No document, artifact or log may assert or imply that a (mechanism, level) cell would qualify,
> pass, or authorise any downstream action unless **every gate in the active `QUALIFICATION_RULE`
> has been evaluated on that exact cell** and the full result is recorded. A statement naming a
> proper subset of the gates is a **gate-subset statement** and must be labelled as such.

### Enforcement in code — five mechanisms, none prose

**E1. Make the audit total, not frontier-local.** Move the per-level shortcut audit out of the
`if selection["selected_level"] is not None:` branch. Every run writes
`mechanisms.<m>.shortcut_audit_by_level` for **all** L0..L3 regardless of the selector's verdict,
including `VOID_CEILING` / `VOID_FLOOR` / `VOID_INSTRUMENT_LIMIT`. (V7 already does this at
`fitness_v7.py:636`; the rule is that it becomes *mandatory and unconditional*, and that a run whose
artifact omits any cell fails a schema assertion.)

**E2. Make the verdict a set, never a scalar — and forbid the scalar.** Delete
`verdict = failures[0]`. `qualify_mechanism` returns `all_failures: frozenset[str]` and a derived
`verdict` that is either `"QUALIFIED"` or the **sorted join of every failing gate**
(`"VOID_NEGATIVE_CONTROL+VOID_SHORTCUT"`). A test asserts
`len(all_failures) != 1 or verdict == single_failure`, and a lint rule bans indexing `failures`.
*Rationale: 2/2 of the historical shortcut failures were masked by the scalar.*

**E3. A first-class `CounterfactualCell` type with no silent construction.** Add

```python
@dataclass(frozen=True)
class GatedCell:
    mechanism: str
    level: int
    gates_evaluated: frozenset[str]   # must equal set(QUALIFICATION_RULE gate names)
    all_failures: frozenset[str]
    qualified: bool
```

`GatedCell.__post_init__` raises `IncompleteGateSet` unless `gates_evaluated` equals the full gate
name set for the active rule version. `qualified` is a **computed property**, not a settable field.
There is no constructor that accepts a partial gate set — so a cell scored on "gap and share" cannot
be represented at all, let alone described as passing.

**E4. Ban the counterfactual sentence class at commit time.** A repository check (pre-commit hook +
CI) scans changed Markdown for the regex family
`would have (qualified|passed|selected .* and passed)|would qualify|giving \d+ qualified` and fails
unless the same paragraph cites a machine-readable `GatedCell` record by
`(artifact_sha256, mechanism, level)` whose `qualified` is `true` and whose `gates_evaluated` is
complete. The programme already runs a forbidden-token guard of exactly this shape
(`tests/releases/test_release_claims.py:14`), so the machinery exists.

**E5. Make invalidation rules mechanically evaluable.** Every quantity named in an
`INVALIDATION_RULE` must be a **named top-level field of the artifact schema**, asserted present by
a schema test. `cache_hits` was the rule's trigger and was never written (Q6.1). A rule whose
trigger is absent from the artifact is a **latent unenforceable rule**; CI should fail on one.

**Ordering note:** E1 without E2 is insufficient (the audit would run but the verdict would still
report one failure); E2 without E1 is insufficient (nothing would be measured off-frontier); E3 is
what actually blocks the §11 sentence from being writable; E4 catches prose that escapes E3;
E5 closes the reporting gap. **They are a package, exactly as V7 correctly argued its own two
corrections were.**

---

## Q8. Sweep — every conclusion resting on an untested counterfactual

**Highest-value section.** Method: `grep -rniE "would (have|be|pass|qualify|fail|show|give|select|yield|return|score|produce|reach|make|need)|would qualify|had (it|we) (been|not)"` over `docs/` and
`research/` (`*.md`, `PROJECT_LEDGER.md` excluded as append-only history), then per-hit
adjudication against artifacts. 32 raw hits; 17 are counterfactual *claims* rather than design
prose. Below: every claim, its status, and whether it has since been verified, refuted, or remains
untested.

| # | Claim (abbrev.) | file:line | Status | Severity | Notes |
|---|---|---|---|---|---|
| 1 | "`formal_expression_depth` **would have selected L2 (.792) and passed**, giving 2 qualified mechanisms and authorising the founder tournament" | `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:174-175` | **REFUTED** by measurement (Q4) | **HIGH** | Refuted by V5's *own* 0.75 gate, not by anything V7 added. |
| 2 | Same claim, restated as the programme's **live next action** | `docs/GAME_R_STATUS.md:85` | **REFUTED but STILL PRESENT** — this document has **not** been updated for V7 | **HIGH** | See Q10.1. `GAME_R_STATUS.md` still declares the current sentinel `SOLVER_SPECIFIC_FAILURE_SUPPORTED` (`:8`), has no V7 row in its instrument-history table (`:38-45`), and states a stale call budget (`:47`). It is the document V7's prereg cites as the admissibility authority. |
| 3 | Same claim, restated | `docs/PROJECT_STATUS.md:248` | REFUTED; **corrected in the same file** at `:322` | MEDIUM | Both the claim and its refutation coexist; a reader hitting `:248` first is misled. |
| 4 | V5 spec §4: "The strongest dumb rule on the DEV pool is `more_frequent_in_state` at **0.72** against a 0.75 threshold" | `docs/FITNESS_V5_SPEC.md` §4 | **REFUTED** — the pooled statistic is 0.7153 for that rule, but the *strongest* rule is `first_mentioned_in_state` at 0.8125 pooled and 1.000 at L1 | **HIGH** | Provenance traced to `fitness_v5.py:1184` (Q3c). The preregistration's own residual-risk clause was calibrated on the **wrong rule at a diluted value**, and its promised remedy ("an identifier-obfuscation arm is required before any promotion") was scoped to a correlation that was not the binding one. Codex audit (`docs/codex_audit/FORMAL_DEPTH_SHORTCUT_AUDIT.md`) independently finds obfuscation **insufficient**. |
| 5 | Phase 6 §6: qwen's "L1 (.833) and L2 (.792) **would both have passed the gap and share gates**" | `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:114` | **VERIFIED as stated** (gap: 0.333/0.292 ≥ 0.20; share: 0.67/0.54 ≤ 0.75) | LOW | True, but it is a **gate-subset statement** (2 of 8) presented adjacent to an outcome claim. This is the exact sentence R-K1/E3 targets. |
| 6 | Phase 6 §7: the frozen sentinel "is now **demonstrably wrong** for this solver" | `:121` | **UNTESTED as phrased** | MEDIUM | The abort clause is a *frozen rule*; "wrong" is an interpretation of intent, not a measurement. V7's result (0 of 3) makes the frozen label's plain reading defensible again. |
| 7 | Phase 6 §10: "gemma-bare is a **lower bound** on gemma" | `:158` | **UNTESTED** | LOW | Plausible, unmeasured; no bound was computed. Compounding: `result-gemma4_12b-bare.json` is **288/288 cache hits** (this audit) — one of the three headline conditions was regenerated, not freshly executed, in the published artifact. Disclosed at `:51-56`; the rows themselves derive from a real earlier run. |
| 8 | Phase 6 §5: "36/72 is exactly what a balanced answerer produces by chance … so qwen shows **no residual degeneracy at all**" | `:82` | **PARTIALLY UNTESTED** | MEDIUM | "Consistent with zero residual degeneracy" ≠ "no residual degeneracy". No equivalence test was run and the prereg forbade equivalence claims at cell level. |
| 9 | Phase 6 §3: framing "would have invalidated the headline claim" if uncorrected | `docs/PHASE6_PREREGISTRATION.md:62` | **VERIFIED** (67/72 measured before deciding) | none | Model example of a counterfactual done correctly: measured *before* acting. |
| 10 | Phase 6: name-only edit "would have made every Phase-6 identity collide" | `docs/PHASE6_PREREGISTRATION.md:111` | **VERIFIED** ("Verified: default-solver identities still hash to existing Phase-5 filenames") | none | Correctly done. |
| 11 | V5 §5: the dropped choice-flip gate "would have passed a coin-flipper **65.6%** of the time" | `docs/FITNESS_V5_RESULT.md:55` | **VERIFIED by simulation** (`research/selector_analysis/selector_simulation.json`) | none | Simulation, correctly labelled. |
| 12 | "a per-level shortcut scan … **would have killed** the `NEXT_ACTION` family before the sprint" | `docs/FUTURE_ENVIRONMENT_FAMILIES.md:147`, `docs/PARALLEL_NEXT_STAGE_HANDOFF.md:170` | **VERIFIED** — `artifacts/reports/next_action_leakage.json` measures 676/676 and 96/96 held-out model-free exact match, verdict `TASK_FAMILY_DEGENERATE_FOR_LEARNING_CURVES` | none | Counterfactual actually executed. |
| 13 | V5 §1: V4's voided rows "**would have fit**" the context budget | `docs/CLAUDE_FINAL_HANDOFF.md:199`; `docs/FITNESS_V5_SPEC.md` §1 | **VERIFIED** — true token counts 7,396 / 9,498 / 23,215 vs 32,448 | none | Measured. |
| 14 | V7 §4: "Lowering it to 0.08 **would qualify** this mechanism" | `docs/FITNESS_V7_RESULT.md:82` | **VERIFIED** (0.0833 ≥ 0.08) and **explicitly refused** | none | Arithmetically checkable; refused as protocol shopping. Correct conduct. |
| 15 | Route B: cross-arm per-token loss ranks representation learnability | `docs/ROUTE_B_HISTORICAL_AUDIT.md:27-51` | **REFUTED** by `research/codex_audit/route_b_audit.json` (`cross_arm_loss_is_comparable: false`; token exposure 94,080–130,507 unmatched) | HIGH | Also: the 16/32/64/128 curve is a **reconstruction** — "held-out accuracy exists only at 224 and 576" (`:19-20`). The low-budget curve is an untested counterfactual by construction. |
| 16 | Route B: "the split seed randomised membership" | `research/codex_audit/route_b_audit.json` `invalid_claims` | **REFUTED** — `stratified_split` never reads `seed`; seeds 0/1/17 give identical split hashes | HIGH | |
| 17 | World-v0 `verified == 1.0` for every arm at every stage indicates verification | `docs/ROUTE_B_PARITY_AUDIT.md:98-100` | **REFUTED** — a wrong action scores `verified 1` (`research/codex_audit/route_b_audit.json:69-75`) | HIGH | Degenerate endpoint. |

**Cross-cutting pattern (`CONFIRMED`).** Every high-severity entry — #1, #2, #4, #15, #16, #17 —
shares one shape: **a statistic was computed at a coarser or different granularity than the claim
made from it**, and nobody recomputed at the claim's granularity.

- #4: pooled across mechanisms × levels → per-level claim.
- #1/#2: gated at one level → claim about another level.
- #15: per-token loss across arms with unmatched token exposure → per-representation ranking.
- #16: seed parameter accepted but unread → claim of randomisation.
- #17: three-key presence check → claim of mathematical verification.

**This is the load-bearing generalisation of the brief's question 8: the recurring error is not
"counterfactual reasoning" — it is granularity substitution.** R-K1/E3 addresses the level case;
the same discipline (a typed record naming the exact population a statistic was computed over,
refusing construction otherwise) generalises to all five.

---

## Q9. Is `SOLVER_SPECIFIC_FAILURE_SUPPORTED` still defensible?

Two-sided, as the brief requires. **Phase 6 asked a *solver* question; V7 asks an *instrument*
question. They are not in contradiction.**

### The case FOR retaining it — and it is stronger than it was in September

1. **V7 independently replicates Phase 6's entire descriptive substrate.** All three ladders are
   identical field-for-field, and `transitive_dependency`'s full-family summary is identical in
   every field — from **864 fresh calls, zero cache hits, zero `CROSS_CONDITION`**, same digest
   `25eb57cb…`, Q0 1.000. (Verified: `gate_by_gate_diff.json`, `v7_cache_census.total_cache_hit_true = 0`;
   V7 artifact `cache_scope_totals = {'FRESH': 864}`.) **This retrospectively neutralises the
   contested 61 cache-hit rows for every qwen number Phase 6 reported.** Whatever the rows'
   provenance, the values are now confirmed by a clean run.
2. **The primary endpoint is structurally immune to the selector defect.** The McNemar degeneracy
   test is computed at three prespecified fixed cells and never reads `positive_accuracy`, the gap,
   the band, or any verdict (`docs/PHASE6_INTEGRATION_MAP.md` §8). p = 2.9e-11 with b=36, c=0.
3. **The solver effect is real and large.** Answer entropy 0.00 → 1.00 bits on the three collapsed
   cells; pooled positive accuracy .7118 → .9062. V7 does not touch gemma and does not contradict
   this.
4. **V7 does not refute the solver claim; it refutes the *mechanisms*.** V7's own §6: "no mechanism
   supports a Game-R comparison" — a statement about the probe bank, not about qwen.

### The case AGAINST — three independent problems, and the label overstates

1. **The literal invalidation rule fired, and the reported field was asserted rather than measured.**
   61 > 0 (independently recounted here, third agreeing count). `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:138`
   reports 0. The artifact has **no top-level cache field** (Q6.1) — so the certification that the
   invalidation rule did not fire was not derived from the artifact at all. Even under the benign
   reading, "the rule was stricter than its rationale" is a defence of the *rule*; it is not a
   defence of the *reported number*. `docs/codex_audit/EXPERIMENT_EVIDENCE_LEDGER.md:23` classifies
   Phase 6 Qwen bare as `INVALIDATED`.
2. **The label was chosen under an undefined criterion (Q2b)**, and the only written gloss requires
   ≥2 mechanisms while Phase 6 delivered 1.
3. **The one mechanism that carried the label no longer qualifies** under a stricter, preregistered
   rule — by 0.0167. The claim "the first mechanism ever to qualify" is now
   version-relative in a way the sentinel's plain reading does not convey.

### Verdict

**`SOLVER_SPECIFIC_FAILURE_SUPPORTED` should be narrowed, not voided.**

- **DEFENSIBLE and now independently replicated:** "a materially different solver escapes gemma's
  answer-collapse on this frozen probe bank" (the degeneracy/entropy/accuracy finding).
- **NOT DEFENSIBLE:** the implication carried by the label and by
  `docs/GAME_R_STATUS.md:6-13` that Game R is thereby measurable. It is not — V7 shows the
  mechanisms are shortcut-dominated for *any* solver, because the shortcut is a property of the
  probe bank.
- **Recommended relabel:** `SOLVER_EFFECT_CONFIRMED_INSTRUMENT_STILL_NOT_QUALIFIED`, or the
  preregistration's own `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET`, with the validity table's
  cache-hit row corrected to 61 and the benign-reading argument retained as a stated interpretation.
  **Do not silently delete the label** — the correction should be additive, as the programme's own
  ledger discipline requires.

---

## Q10. Valid vs downgraded — V1 → V7

| Conclusion (with file:line) | REMAINS VALID | MUST BE DOWNGRADED / VOIDED |
|---|---|---|
| **V1** `MODEL_FITNESS_BENCHMARK_INVALID` — solver answered by option position; `artifacts/reports/experiment-decision.json` (`decision`), defined `arena/experiments/model_fitness.py:363`; `docs/MODEL_FITNESS_EXPERIMENT.md:22` | **VALID.** Measured on 64 real rows; `INSTRUMENT_INVALID_POSITION_ONLY` (`model_fitness.py:329`) verified by raw-output inspection. The lesson (option-swap + counterfactual controls mandatory) is load-bearing and has held. | — |
| **V1** `USEFUL_HEADROOM` (`model_fitness.py:196`; `artifacts/reports/fitness-calibration.json`) | — | **DOWNGRADE.** A nominal-accuracy heuristic that was overridden by the position audit in the same run. Not evidence of anything. |
| **V2** `FITNESS_V2_INSTRUMENT_QUALIFIED` (`arena/experiments/fitness_v2.py:1634`; `artifacts/experiments/fitness_v2/experiment_decision.json`) | **VALID as scoped** — 192 fresh calls; 3 of 4 permanent controls pass. | **Scope must be stated:** "instrument qualified" here means protocol/Q0 only. No representation was ranked. |
| **V2** `FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM` (`fitness_v2.py:1393`; `docs/MODEL_FITNESS_EXPERIMENT_V2.md:164-165`) | **VALID** — 0.125 range vs frozen 0.150 requirement, measured. | **The interpretation is downgraded** by V5 spec §7: the 12.5-pt range is *below* the median null range for its n (p = 0.886) — i.e. a noise-floor reading, not a small real effect. `docs/GAME_R_STATUS.md:40` records this. |
| **V3** `EXPERIMENT_INVALID` (`artifacts/experiments/fitness_v3/invalidity.json:31`) | **VALID.** Aggregate gate pooled five ceiling mechanisms with one floor mechanism (`:10-18`). The lesson — mechanism-level qualification must precede pooling — is directly vindicated by Q3c (V5 repeated the same pooling error one layer down, in the shortcut audit). | **Root-cause attribution downgraded.** `docs/GAME_R_STATUS.md:42` and `docs/CURRENT_STATE.md:39` add "input truncation at `num_ctx=8192`" as root cause; the frozen artifact says only ceiling/floor pooling. The truncation diagnosis is a later inference (`docs/PROJECT_LEDGER.md:141`). |
| **V4** `FITNESS_V4_NOT_QUALIFIED` (`artifacts/experiments/fitness_v4/not_qualified.json`; `arena/experiments/fitness_v4.py:1743`) | **VALID as a record.** | **VOIDED as a result about representations or the Solver.** `docs/FITNESS_V5_RESULT.md:26-27`: it "measured its own instrument". Both failure modes were instrument defects, measured in V5 (`docs/FITNESS_V5_SPEC.md` §1). |
| **V5** `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` (`docs/FITNESS_V5_RESULT.md:3`; `fitness_v5.py:1152`) | **VALID and, in hindsight, correct** — the disjunction's second limb ("or task family") is exactly what V7 confirmed. | **Nuance:** V5's prose emphasised the Solver limb; Phase 6 then read it as solver-only. V7 shows the task-family limb was the operative one. |
| **V5 spec §4** "strongest dumb rule … `more_frequent_in_state` at 0.72 against a 0.75 threshold" (`docs/FITNESS_V5_SPEC.md:89`, §4) | — | **REFUTED (this audit, Q3c/Q4).** Wrong rule and diluted value; the binding rule is `first_mentioned_in_state` at 1.000 (L1) / 0.833 (L2) / 0.917 (L3). **HIGH severity: the preregistration's only shortcut safeguard was mis-calibrated.** |
| **V5** per-mechanism verdicts incl. `formal_expression_depth → VOID_NEGATIVE_CONTROL (+ VOID_SHORTCUT)` (`docs/FITNESS_V5_RESULT.md:32`) | **VALID, and the prose disclosure was exemplary** — it surfaced a co-failure the code hid. | — |
| **Phase 6** solver-escape / degeneracy finding (p = 2.9e-11; entropy 0.00→1.00; `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` §5) | **VALID and STRENGTHENED** — V7 replicated the ladders exactly from 864 fresh, zero-cache calls. | — |
| **Phase 6** `transitive_dependency` **QUALIFIED** (`:101`; artifact `qualification.verdict = "QUALIFIED"`) | **VALID under V5's frozen rules** — every gate passes; V7 reproduced the numbers. | **DOWNGRADE the framing.** "The first mechanism ever to qualify" is version-relative: under V7's preregistered `SHORTCUT_MARGIN = 0.10` it fails by 0.0167 (`docs/FITNESS_V7_RESULT.md:76-83`). It should never again be cited without the margin. |
| **Phase 6** sentinel `SOLVER_SPECIFIC_FAILURE_SUPPORTED` (`docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md:3`) | Its **factual core** is valid (see Q9). | **DOWNGRADE to `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET`.** Criterion undefined in the prereg; the only written gloss requires ≥2 mechanisms and got 1; the validity table's cache-hit row is wrong. |
| **Phase 6** validity table "cache hits on the alternate solver = 0" (`:138`) | — | **VOID. It is 61** (three independent counts). The field was never computed by the pipeline. |
| **Phase 6 §6** "selector miscalibration, **not a reading failure**" (`:110-111`) | Half valid — the miscalibration is real and independently confirmed. | **DOWNGRADE.** The same artifact records `checks.shortcut = VOID_SHORTCUT` at that level (0.9167). The mechanism failed for *both* reasons; the exculpatory clause is unsupported. |
| **Phase 6 §11 / `docs/GAME_R_STATUS.md:85`** "would have … giving 2 qualified mechanisms and authorising the founder tournament" | — | **REFUTED (Q4).** `formal_expression_depth` exceeds V5's own 0.75 ceiling at **every** level ≥ 1. **`docs/GAME_R_STATUS.md` still carries this uncorrected and still declares the current sentinel to be Phase 6's — the single highest-priority documentation fix in the programme.** |
| **V7** `V7_SHORTCUT_DOMINATED`, 0 of 3 (`docs/FITNESS_V7_RESULT.md:3`) | **VALID.** Preregistered at `e66bab1` before the first call; 864 rows all `FRESH`; thresholds unmoved; the qualifying outcome would have been *easier* to reach under the prior rule, so no protocol shopping. | **One governance caveat:** V7's admissibility rests on a clause it attributes to `docs/GAME_R_STATUS.md` that **is not in that file** (Q6), and the frozen `FITNESS_V5_SPEC.md:167-168` arguably forbids a scoring-only version. **Effect on the result: none** (V7 was strictly stricter and returned zero). |
| **V7** "the instrument is sound; the mechanisms are not" (`docs/FITNESS_V7_RESULT.md:40`) | **VALID** — all non-shortcut gates PASS on both selected cells, verified here from the artifact's own `checks`. | — |
| **Route B** loss-curve ranking of representations (`docs/ROUTE_B_HISTORICAL_AUDIT.md:27-51`) | The *timing* observation (curves separate early, collapse by 128) is retained as `HISTORICAL_GUIDANCE`. | **VOID as a ranking.** `research/codex_audit/route_b_audit.json` (`cross_arm_loss_is_comparable: false`); token exposure 94,080–130,507 unmatched; the 16/32/64/128 points are reconstructed, not measured (`:19-20`). |
| **Route B** "the split seed randomised membership" | — | **REFUTED.** `stratified_split` never reads `seed`; seeds 0/1/17 produce identical split hashes (`docs/codex_audit/ROUTE_B_CAUSAL_AUDIT.md:13-18`). |
| **Route B** `verified` accuracy = 1.0 for every arm at every stage | — | **VOID.** A wrong action scores `verified 1` (`research/codex_audit/route_b_audit.json:69-75`; `docs/ROUTE_B_PARITY_AUDIT.md:98-100`). Degenerate endpoint. |
| **Route B** gene-level attribution of arm differences | — | **DOWNGRADE.** "A legitimate comparison of five concrete codecs, not a causal factorial study of genome genes" (`docs/codex_audit/ROUTE_B_CAUSAL_AUDIT.md:62-70` (§8E)). Five of fourteen gene families are inert (`docs/ROUTE_B_PARITY_AUDIT.md:41-44`). |
| **Route B** "21 leaked problems" | — | **DOWNGRADED by its own audit** to five exact problem recurrences; operation overlap 48/48 (`docs/codex_audit/ROUTE_B_CAUSAL_AUDIT.md:38-52`). |
| **World-v0** materialisation: 676 tasks, 520/104/52, `world_hash ac16014c…` (`artifacts/worlds/arena-world-v0-summary.json`) | **VALID** as an infrastructure result (`INSTRUMENT_RESULT_ONLY`). | — |
| **World-v0** `NEXT_ACTION` as a learning-curve substrate (`docs/MATHEMATICAL_WORLD.md`) | — | **VOID.** `TASK_FAMILY_DEGENERATE_FOR_LEARNING_CURVES` — a model-free rule set reproduces the gold target on **676/676**, held-out **96/96** (`artifacts/reports/next_action_leakage.json:3-8`). Note `docs/MATHEMATICAL_WORLD.md` carries **no** annotation of this. |
| **Mutant audit** 120/120 `GAME_R_COMPATIBLE` (`artifacts/reports/game-r-mutant-audit.json`) | **VALID under the corrected v2 check** (renders the surface, not the recovered state; regression test proves it can fire). | The **v1** result is void (vacuous check) — already recorded at `docs/GAME_R_STATUS.md:58-62`. |
| **`RSTAR_NOT_IDENTIFIED`** (`docs/CURRENT_STATE.md:8`) | **VALID and unambiguous.** No representation has been scored under any instrument, at any point, V1→V7. Every experiment measured the control surface only. | — |

### Two documentation defects found while building this table

1. **`docs/GAME_R_STATUS.md` is stale and misleading.** `CONFIRMED`, severity **HIGH**. It declares
   the current sentinel to be Phase 6's (`:8`), has no V7 row in its instrument-history table
   (`:38-45`), states a call budget that predates V7's 864 calls (`:47`), and repeats the refuted
   counterfactual as the programme's next action (`:85`). It was last written by the Phase-6 session
   (`b3717c3`). It is also the document `docs/FITNESS_V7_PREREGISTRATION.md:15` cites as the
   authority on version admissibility. `docs/CURRENT_STATE.md`, `docs/PROJECT_STATUS.md` and
   `docs/72_HOUR_SPRINT_HANDOFF.md` are all correct and current; this one file is the outlier.
2. **`docs/CURRENT_STATE.md:7` emits `GAME_R_INSTRUMENT_NOT_QUALIFIED`.** `CONFIRMED`, severity LOW.
   That string appears in no preregistration's allowed-sentinel list — not
   `docs/FITNESS_V5_SPEC.md:175` (§10), not `docs/FITNESS_V7_PREREGISTRATION.md:163` (§8) (whose emitted
   sentinel is `V7_SHORTCUT_DOMINATED`). Minor sentinel drift; should be reconciled to a
   preregistered token.

---

## Adversarial summary — the strongest case against the programme

1. The programme's **only shortcut safeguard was mis-calibrated from the preregistration onward**
   (Q3c/Q4/#4), because the single audit it ran pooled across mechanisms and levels and returned
   CLEAN at 0.7153.
2. When that safeguard *did* fire, the code **reported only the first failure** (`fitness_v5.py:984`),
   masking it in 2 of 2 opportunities.
3. A published result document then **recommended selecting a level that its own predecessor
   document had already flagged as leaking at exactly the reported value**, and described that
   recommendation as authorising a founder tournament.
4. The invalidation rule protecting that result **keyed on a quantity the pipeline never wrote**,
   and the certifying table asserted a value of 0 against a true value of 61.
5. The follow-up version, written specifically to correct all this, **cited a permission clause that
   does not exist** in the document it named.
6. The status document that carries the refuted claim as the programme's next action **remains
   uncorrected today**.

**And the strongest case for it.** Every one of the six was found by the programme's own artifacts,
prose and audits — not by anything external. V5's result document voluntarily surfaced a failure its
code had hidden. V7 preregistered a strictly stricter rule, refused to move it when it cost the
programme its only qualification, and reported zero. `RSTAR_NOT_IDENTIFIED` has never once been
weakened. The failure mode here is **granularity substitution under time pressure**, not
result-shopping — and the fix (Q7) is five small, testable code changes, not a change of culture.

---

*Auditor 7 of 9. Zero model calls. No existing file modified. Read-only throughout.*
