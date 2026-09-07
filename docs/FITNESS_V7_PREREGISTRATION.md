# Fitness V7 Preregistration — corrected frontier target, per-level shortcut audit

**Committed BEFORE any V7 model call.** Experiment `arena-representation-fitness-v7`.
Module `arena/experiments/fitness_v7.py`. Probe bank unchanged:
`arena/environments/formal_structural.py`.

**V7 is a strictly STRICTER instrument than V5.** It removes one degree of freedom and adds one
gate. It is entirely possible that it qualifies *fewer* mechanisms than Phase 6 did. That outcome
is preregistered as acceptable and must be reported as such.

---

## 1. Why a new version is admissible

`docs/GAME_R_STATUS.md` permits a new instrument version only when a frozen variable class named in
the failure analysis changes, or when the instrument is shown defective. Two defects are now
**measured, not argued**, and both are properties of the instrument rather than of any solver or
representation.

### Defect 1 — the frontier target is stranded outside its own qualifying window

The destroyed-twin negative control is a **mathematical constant at 0.5000** for any deterministic
solver: twins are information-identical with opposite targets. Verified on frozen rows — 24/24 twin
pairs had identical `prompt_hash` **and** byte-identical `raw_output`, 24 correct of 48.

Therefore, with `gap_min = 0.20` and `band_high = 0.85`:

```
qualifying window = [destroyed_expected + gap_min , band_high] = [0.70 , 0.85]
frontier selector = argmin |accuracy − 0.625|
```

The selector aims **0.075 below its own floor**, and `destroyed ≤ 0.60` is a **dead gate**
(an invalid parse pushes destroyed below 0.5, never above).

*Provenance.* V3 (`fitness_v3.py:56,61`) and V4 (`fitness_v4.py:143,148,152`) used
`gap_min = 0.10`, giving a window of [0.60, 0.85] in which 0.625 sat comfortably. V5 raised the gap
to 0.20 on simulation evidence and left the target untouched. One uncoordinated constant edit.

*Measured cost.* In Phase 6, qwen's `formal_expression_depth` scored L1 **.833** and L2 **.792** —
both inside the window — while the selector chose L3 at exactly **.625** and voided the mechanism.

### Defect 2 — the shortcut audit runs only at the selected frontier

A mechanism's shortcut exposure at every other level is **unmeasured**. This is decisive here: an
independent audit measured `first_mentioned_in_state` on `formal_expression_depth` at **1.000** on
the shallow stratum, **0.9167** at deep L3 and **0.8125** pooled over the four-level bank. Qwen
scores **.792** at L2.

**Correcting Defect 1 without also correcting Defect 2 would manufacture a qualification.** The two
corrections are a package and are registered together; neither may be applied alone.

---

## 2. What changes — exhaustively

1. **`frontier_target` becomes a derived quantity**, never a declared constant:
   ```
   window_low      = destroyed_expected + gap_min      = 0.500 + 0.20 = 0.70
   window_high     = band_high                          = 0.85
   frontier_target = (window_low + window_high) / 2     = 0.775
   ```
   A test asserts the target lies strictly inside the window and moves automatically when
   `gap_min` moves. The constants can no longer drift apart.
2. **The dead `destroyed ≤ 0.60` gate is removed** (unreachable by construction).
3. **The shortcut audit runs at every level L0..L3**, and the full per-level table — best shortcut
   accuracy and which feature achieved it — is written into the artifact.
4. **A new qualification gate:** at the selected level,
   `positive_accuracy − best_shortcut_accuracy ≥ SHORTCUT_MARGIN`, with
   **`SHORTCUT_MARGIN = 0.10`**, else `VOID_SHORTCUT`.

**`SHORTCUT_MARGIN = 0.10` is frozen here and may not be changed after seeing any V7 result.**
Its justification is preregistered and independent of outcome: at n = 24 the binomial standard
error near 0.8 is ≈ 0.082, so a margin below one standard error could not distinguish a solver from
its own shortcut.

---

## 3. What stays frozen — everything else

Probe bank and DEV pool hash `f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b` ·
the three mechanisms and their family builders · the four-level ladder · explicit-positive,
counterfactual, destroyed and swap arms · prompt template · answer options · `RESPONSE_SCHEMA` ·
`num_ctx` 32768, temperature 0, seed 20260905, `num_predict` 64, `top_k` 64, `top_p` 0.95, think
off, grammar-constrained `format` · context guard · scoring · failure taxonomy · validity gates
(Q0 ≥ 0.95, valid-response ≥ 0.95, zero input truncation) · `largest_answer_share ≤ 0.75` ·
position invariance ≥ 0.50 · the ≥ 2-mechanisms instrument rule.

**No probe, prompt byte, option or decoding setting changes.** V7 is a scoring-and-selection change
only.

---

## 4. Solver

`qwen38-rvn:latest`, digest
`25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`, family `qwen35`, 27.3B,
Q4_K_M, capabilities `["completion"]`, bare condition (`raw: true`).

`verify_served_model` must confirm the live digest before any call, and refuse otherwise.

**Why this solver.** Phase 6 established descriptively that it escapes gemma's degeneracy. Adopting
it here is a **design choice**, not a result inherited from Phase 6 — whose formal validity is
contested (§6).

---

## 5. Cache identity — defined before the run

A cached row may be reused **only** when *all* of these match: model digest · tokenizer/model
revision · prompt bytes · runtime/framing condition · experiment version · task ID · candidate ID ·
decoding settings.

Every row records `cache_hit` **and** `cache_scope` ∈ {`FRESH`, `SAME_CONDITION_REUSE`,
`CROSS_CONDITION`}.

- `SAME_CONDITION_REUSE` is **legitimate** — it is the same solver answering a byte-identical
  prompt under an identical condition, and it is deterministic at temperature 0.
- `CROSS_CONDITION` reuse is **impossible by construction** and asserted in code.

V7 writes to its own cache namespace and artifact path. It **cannot** read or overwrite any V5 or
Phase-6 artifact; this is asserted by test.

*Rationale, registered in advance.* Phase 6's rule said `PHASE6_INVALID` if "cache hits > 0",
which fired on 61 rows that were all same-solver, same-condition reuse (13 from a documented
relaunch, 48 within-run). A rule that cannot distinguish benign reuse from contamination is a
defective rule; V7 replaces the count with the scope distinction. **This is a correction of a rule
that was wrong on its own stated rationale, registered before V7 runs — not a relaxation adopted
after seeing a result.**

---

## 6. Phase-6 status assumed here

Formally **contested**. Phase 6 published `SOLVER_SPECIFIC_FAILURE_SUPPORTED` while its artifact
carries 61 `cache_hit == true` rows against its own "cache hits > 0" invalidation rule, verified
independently by two audits.

V7 therefore **uses no Phase-6 number as confirmatory input**. Phase-6 ladders are cited only as
the descriptive motivation for changing the selector, and V7 re-measures everything from fresh
model calls.

---

## 7. Endpoints and decision rule

**Primary (confirmatory).** Per-mechanism qualification under the V5 gates as amended by §2. The
instrument qualifies if **≥ 2 of 3 mechanisms qualify**. This threshold is unchanged and will not
be lowered.

**Secondary (descriptive, no p-values).** The full L0..L3 grid: accuracy, largest-answer share,
answer entropy, valid rate, destroyed accuracy, and per-level best shortcut with the responsible
feature.

**Power, stated honestly.** n = 24 per cell. Per-cell accuracy differences are underpowered; no
per-cell significance claim will be made. The qualifying window is only ≈ 1.76 standard errors
wide at this n, and both real ladders step across it in one move — so **sample size and ladder
granularity, not the aim point, are the dominant limitation.** V7 fixes the aim point; it does not
fix the granularity.

---

## 8. Preregistered outcomes

| Sentinel | Condition |
|---|---|
| `V7_INSTRUMENT_QUALIFIED` | ≥ 2 mechanisms qualify → founder tournament authorised |
| `V7_ONE_MECHANISM_QUALIFIED` | exactly 1 qualifies → **no** founder tournament |
| `V7_SHORTCUT_DOMINATED` | a mechanism's selected level fails only the new shortcut margin |
| `V7_CEILING_LIMITED` | a mechanism is ≥ 0.85 at every level; the ladder does not reach this solver |
| `V7_INVALID` | digest mismatch · any `CROSS_CONDITION` row · any input truncation · output truncation > 5% · Q0 < 0.95 |

**The honest expectation, recorded before the run.** `transitive_dependency` qualified in Phase 6
at L3 (.750) and is expected to qualify again. `precondition_conjunction` is at ≥ .958 on every
level and is expected to return `VOID_CEILING`. `formal_expression_depth` is the live question: the
corrected selector should choose L2 (.792) or L1 (.833), but the measured shortcut on this
mechanism is 0.8125 pooled, so **it may well void on the new shortcut gate.** If it does, the
result is `V7_ONE_MECHANISM_QUALIFIED`, there is no founder tournament, and that is a legitimate
and fully reportable outcome.

---

## 9. Budget and stopping

392 calls, budget cap 900, one run, one solver. No search over decoding settings. No second run
under altered thresholds. If V7 returns `V7_ONE_MECHANISM_QUALIFIED`, the next move is a **task
family with a reachable frontier** (see `docs/FUTURE_ENVIRONMENT_FAMILIES.md`), **not** a V8.

**No threshold in this document may be reinterpreted after the run.**
