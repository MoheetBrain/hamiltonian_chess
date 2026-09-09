# HC-V0.6 — independent red team

Written by an independent red team **while the primary four-arm pass was still executing** and
**without reading the outcome distribution**. No `step_result`, `kernel_accepted_state_change` or
event count from `artifacts/trajectory/hc_v0_6_primary_gemma4_e4b_cells.jsonl` was read or
tallied. The only fields taken from that file were `anchor_id`, `arm`, `replicate_index`,
`renderer_id`, `intervention_class`, `prompt_sha256` and `solver_digest` — used to verify, against
the frozen bank, that each arm was actually shown its own bytes (RT06 below).

Contract audited: `docs/HC_V0_6_SPEC.md` (the freeze at `2624be5`).
Attacks: `research/phase10/redteam_v06/`. Raw output: `research/phase10/redteam_v06/out/`.

**Headline: no CRITICAL defect. The cells being collected are sound.** Every defect found is in
the *analysis, gate and provenance* layers, all downstream of the data, and all fixable without
re-collecting a single cell. The run is **not** `RESULT_INVALID`. It is also **not yet
interpretable**: the preregistered analysis path does not currently execute on the design that is
running, and two of the three control gates test something weaker than the frozen spec declares.

---

## Findings

| id | class | severity | status | one line | reproduce |
|---|---|---|---|---|---|
| RT-V06-01 | endpoint / analysis | **HIGH** | CONFIRMED | Harness failures are scored as mathematical zeros: `drop_harness_failures` and `.analysable` are never called anywhere in `arena/`; 20 injected `ENVIRONMENT_ERROR`s on one arm moved Δ̂ from 0.000 to −0.333 | `.venv/bin/python research/phase10/redteam_v06/attack_14_harness_failures.py` |
| RT-V06-02 | control gate | **HIGH** | CONFIRMED | The C2 gate is a bare significance test with no magnitude term: spec §10a's `T_ablate = 0.067` appears nowhere in `arena/`, and an ablation costing 0.8 points certifies | `.venv/bin/python research/phase10/redteam_v06/attack_11b_gates.py` |
| RT-V06-03 | control gate | **HIGH** | CONFIRMED | The C1b gate is a failure-to-reject, not spec §10's equivalence band: a null control with a 95% CI of [−0.15, +0.19] certifies as "practically small" | `.venv/bin/python research/phase10/redteam_v06/attack_11b_gates.py` |
| RT-V06-04 | analysis path | **HIGH** | CONFIRMED | `hc_v0_6_report.build_report` crashes with `IdentityControlUnavailable` on the frozen `k = 1` design — the analysis driver cannot process the run that is executing | `.venv/bin/python research/phase10/redteam_v06/attack_13_report_driver.py` |
| RT-V06-05 | control gate | **HIGH** | CONFIRMED | The C1 stand-in carries C1b's permutation p-value into the C1 gate, so a significant *byte* control is reported as a broken *identity* control with `Δ=+0.0000` beside a p-value from another contrast | `.venv/bin/python research/phase10/redteam_v06/attack_13_report_driver.py` |
| RT-V06-06 | control gate | **HIGH** | CONFIRMED | `calibrate` is called with no `missingness=`, so spec §10's missingness gate (outcome O7) can never fire; nothing calls `validate_balanced` either | `.venv/bin/python research/phase10/redteam_v06/attack_13_report_driver.py` |
| RT-V06-07 | endpoint | **HIGH** | CONFIRMED (scoring) / PLAUSIBLE (end-to-end) | `rotate_left`, `rename_i`, `clear` are policy-allowed, change the printed state, do no mathematics, and score `ACCEPTED_TRANSITION`; 152/1127 anchors (13.5%) carry ≥2 goals and are exposed to the goal-permutation form | `.venv/bin/python research/phase10/redteam_v06/attack_12_endpoint.py` |
| RT-V06-08 | reproducibility | **HIGH** | CONFIRMED | `result_hash` is not stable: `latency_ms` reaches it through `cell_table_content_hash`, which `_strip` cannot see; per-session Lean scratch paths re-enter through `skipped[].reason` and `theorem_errors[].error` | `.venv/bin/python research/phase10/redteam_v06/attack_09_result_hash.py` |
| RT-V06-09 | contract | MEDIUM | CONFIRMED | Two renderers pass the full bijection + parity contract and are typed `R_ONLY` while one shows a computed tactic hint and the other hides a third of the goal from the model | `.venv/bin/python research/phase10/redteam_v06/attack_02_bijection.py` |
| RT-V06-10 | provenance | MEDIUM | CONFIRMED | A hand-written cell can claim an event with no tactic, an arbitrary `solver_digest`, and another arm's `prompt_sha256`; nothing re-derives the prompt hash from the bank | `.venv/bin/python research/phase10/redteam_v06/attack_06_provenance.py` |
| RT-V06-11 | freeze integrity | MEDIUM | CONFIRMED | The freeze moved after the run began: `hc_v0_6_assay.py` +9 lines, `HC_V0_6_SPEC.md` +86 lines, and an untracked analysis driver `arena/experiments/hc_v0_6_report.py` written at 05:14 against a pass that started at 04:59 | `.venv/bin/python research/phase10/redteam_v06/attack_15_manifest_and_freeze.py` |
| RT-V06-12 | invalidation | MEDIUM | CONFIRMED | A served-digest mismatch — spec §13's first `RESULT_INVALID` condition — is written into a 200-character string field and nothing reads it; the manifest still ships `PREREGISTERED_ASSAY_RESULT_SET` and a `result_hash` | `.venv/bin/python research/phase10/redteam_v06/attack_15_manifest_and_freeze.py` |
| RT-V06-13 | resolution reporting | MEDIUM | CONFIRMED | The MDE's `ClusterProfile` comes from the **bank**, not from the table that was played: a 60-anchor table reported an MDE for 1,127 anchors / 330 clusters | `.venv/bin/python research/phase10/redteam_v06/attack_13_report_driver.py` |
| RT-V06-14 | control design | MEDIUM | CONFIRMED | `R_ABLATED` sends only **5 distinct prompts** across all 1,127 anchors (975 anchors share one), so C2 measures a constant policy, not "the same policy with less information" | `.venv/bin/python research/phase10/redteam_v06/attack_06_provenance.py` |
| RT-V06-15 | endpoint | MEDIUM | CONFIRMED | The assay never runs `verify_closed_script` and never checks `TRUSTED_AXIOMS`: a `native_decide` closure would score an event with `Lean.ofReduceBool` in its trust base — RT-01's hole, re-opened by omission | `.venv/bin/python research/phase10/redteam_v06/attack_12_endpoint.py` |
| RT-V06-16 | missingness | MEDIUM | CONFIRMED | `run_assay`'s per-theorem `except Exception` leaves a partially played anchor in the table and abandons the theorem's remaining anchors, recording only a `problem_id`; `extract_pair` then drops the half-anchor silently | `.venv/bin/python research/phase10/redteam_v06/attack_08_clusters.py` |
| RT-V06-17 | endpoint | LOW | CONFIRMED | An `OK` step whose `tactic_state` the backend did not report is scored `ACCEPTED_NO_OP` — a genuine advance recorded as a zero rather than as a harness failure | `.venv/bin/python research/phase10/redteam_v06/attack_12_endpoint.py` |
| RT-V06-18 | leakage | LOW | CONFIRMED | The 6-character floor leaves 458 reference-tactic occurrences unchecked (`simp` ×135, `rfl` ×85, `congr` ×32 …). On this bank it costs nothing — 0 reach any model-visible payload — but it is a latent hole for any future renderer | `.venv/bin/python research/phase10/redteam_v06/attack_03_leakage.py` |
| RT-V06-19 | provenance | LOW | CONFIRMED | `CellOutcome.renderer_id` is documented as "the renderer that produced this arm's bytes" but `Arm.renderer_id` returns the arm id; the real renderer id lives only in the manifest | `attack_06_provenance.py` output, field `cells_by_arm` / schema read |
| RT-V06-20 | runtime | LOW | PLAUSIBLE | Ollama's keep-alive (`expires_at` observed ~5 min ahead) will unload and reload the model on any inter-call gap longer than it, contradicting spec §6's "No model is reloaded mid-pass" | `curl -s http://127.0.0.1:11434/api/ps` |
| RT-V06-21 | budget | LOW | CONFIRMED | `budget.timeout_seconds` is recorded in the proposal provenance but never passed to the transport, which keeps its own 900 s default — the recorded value is not the value in force | `.venv/bin/python research/phase10/redteam_v06/attack_04_model_conditions.py` |
| RT-V06-22 | clustering | LOW | CONFIRMED | 3 of the 330 "mathlib file" clusters (12 anchors) are `.lake/packages/batteries/…` files, so the cluster unit is "source file", not strictly "mathlib file" | `.venv/bin/python research/phase10/redteam_v06/attack_08_clusters.py` |

Counts: **0 CRITICAL, 8 HIGH, 7 MEDIUM, 7 LOW.**

---

## RT-V06-01 — harness failures are scored as mathematical zeros

**Observed.** `arena/experiments/hc_v0_6/schema.py` defines `CellOutcome.analysable` and
`CellTable.drop_harness_failures()`, and its docstring says `ENVIRONMENT_ERROR` and `TOOL_TIMEOUT`
"are excluded by `CellOutcome.analysable`, not scored as failures". Grep over `arena/`:
`drop_harness_failures` appears twice — its own definition and one docstring reference — and
`.analysable` appears once, inside its own definition. **Neither is ever called.**
`extract_pair` iterates `table.rows` unfiltered, and `arm_marginal` counts every row.
`hc_v0_6_report.build_report` does not call either.

Measured: a 60-anchor / 30-cluster table with identical arms gives Δ̂ = 0.000. Attaching 20
`ENVIRONMENT_ERROR` cells to `R_B` at the 20 anchors that would have scored gives
**Δ̂ = −0.3333**. After `drop_harness_failures()` it returns to 0.000.

**Expected.** Spec §4: "`ENVIRONMENT_ERROR` is separately typed and is **never** a mathematical
zero."

**Why it matters.** Every harness-decided cell currently enters Δ̂ as a failure for the arm it is
attached to. Arm order is randomised, so the expectation is unbiased — but the realised sample is
not, and a session that dies mid-anchor kills exactly the arms scheduled after it. This is the one
finding that can move the headline number by itself.

**Minimal fix.** In `build_report`, analyse `table.drop_harness_failures()` and report the count
dropped per arm; feed that same per-arm count to `calibrate(..., missingness=…)` (see RT-V06-06).

---

## RT-V06-02 — the degraded control gate has no magnitude term

**Observed.** Spec §10 states the degraded control as `Δ(R_A, R_ABLATED) ≤ −T_ablate`, and §10a
fixes `T_ablate = 0.5 × p̂_A = 0.5 × 0.133 = 0.0665` from preflight alone. `grep -rn "T_ablate"
arena/` returns **nothing**. `calibration.calibrate` implements C2 as
`c2.significant(alpha_sensitivity) and c2.delta < 0.0` — significance and sign, no magnitude.

Measured: a C2 effect of `Δ = −0.008` with `p = 0.0001` yields `AssayStatus.USABLE` and
`certified = True`, against a frozen requirement of at least 6.65 points.

**Expected.** The gate that certifies sensitivity should require the ablation to cost at least
`T_ablate`, and — per §10a — should report `cannot be certified at this resolution` when
`T_ablate` falls below the achieved MDE.

**Why it matters.** C2 is the **only** `REJECT_TO_CERTIFY` gate, i.e. the only one whose α bounds
the false-certification rate at all (`false_certification_bound() == 0.05`). Weakening it is
weakening the entire IUT argument. With n = 1,127 anchors a one-point ablation effect is easily
significant, so the gate as coded can certify "the assay is sensitive" on an effect an order of
magnitude below the declared floor.

**Minimal fix.** Add `t_ablate: float` to `calibrate`, require
`c2.delta <= -t_ablate and c2.significant(alpha_sensitivity)`, and add a third status for
`T_ablate < mde` → contributes to `INCONCLUSIVE`.

---

## RT-V06-03 — the null control gate is a failure to reject, not the frozen equivalence band

**Observed.** Spec §10 states the null control as "`Δ(R_A, R_A′)` inside the equivalence band
**±0.05**". `calibrate` implements it as `c1b.significant(alpha_byte_null)` — i.e. block iff
`p ≤ 0.10`. `PairedEffect.equivalent_within(bound)` exists and does the right thing, but is called
only for the *primary's* O3 decision; **no gate calls it**.

Measured: a C1b reading with `Δ = +0.02`, `p = 0.55`, 95% CI `[−0.15, +0.19]` certifies
(`AssayStatus.USABLE`, attribution `STRUCTURE` permitted). `equivalent_within(0.05)` on that same
effect returns `False`.

**Expected.** Equivalence is not the complement of significance. A non-significant control with a
CI four times wider than the band is uninformative, not "practically small".

**Why it matters.** This is the gate that licenses the word *structure*. It currently passes on
absence of evidence.

**Minimal fix.** `c1b_passes = byte_null.equivalent_within(EQUIVALENCE_BOUND)`, keeping the
significance test as an additional (not alternative) blocker.

---

## RT-V06-04 — the analysis driver cannot run on the design that is running

**Observed.** `build_report` computes
`available = [c for c in PREREGISTERED_FAMILY if set(_arms_of(c)) <= set(arms)]`. For
`C1_IDENTITY`, `_arms_of` is `(R_A, R_A)`, so `set(...) == {R_A}` is a subset of the played arms
and C1 is always "available". It then calls `estimate_pair(table, C1_IDENTITY)` →
`split_half_identity` → `IdentityControlUnavailable` at `k = 1`.

Measured on a 60-anchor, four-arm, `k = 1` table:
`CRASHED -- IdentityControlUnavailable: R_A carries fewer than 2 replicates at 60 anchor(s)`.

`unavailable_identity_control` — the function written to handle exactly this — is defined but is
never reached, because the crash happens two lines earlier.

**Expected.** `k = 1` is frozen in spec §5. The preregistered analysis must execute on it.

**Why it matters.** It is fail-loud, which is the right direction, but it means the analysis code
must be edited again *after* outcomes exist. That is the precise thing preregistration buys, and
it is being spent.

**Minimal fix.** Exclude `C1_IDENTITY` from `available` (it is not extractable by `extract_pair`
and has its own constructor), and build the degenerate stand-in unconditionally at `k = 1`.

---

## RT-V06-05 — the C1 stand-in inherits C1b's p-value

**Observed.** `unavailable_identity_control(reference)` is
`dataclasses.replace(reference, comparison=C1_IDENTITY, arm_a=R_A, arm_b=R_A, n_anchors=0,
delta=0.0, delta_ci95=(0.0, 0.0))` — and it is called with `effects[C1B_WHITESPACE]` as the
reference. `permutation` is **not** replaced, and `ControlReading.from_effect` reads
`effect.p_value`, which is `effect.permutation.p_value`.

Measured: with a C1b effect of `Δ = +0.06, p = 0.004`, the C1 gate reads `p = 0.004`, `calibrate`
returns `BROKEN_IDENTITY_CONTROL`, and the recorded reason is

> "C1 identity control is significant (Delta=+0.0000, p=0.0040 <= alpha_identity=0.1)"

— a Δ of exactly zero sitting beside a p-value from a different contrast.

**Expected.** A control that was not measured must not decide a gate. The degenerate reading
should carry `p = 1.0` (or be routed round the C1 branch entirely), with
`identity_informative = False` already doing the honest reporting.

**Why it matters.** The direction happens to be conservative — a significant C1b escalates from
`USABLE_ATTRIBUTION_BLOCKED` to "nothing may be reported" — but the *reason string that will be
published* names the wrong control and quotes a number that is not that control's. And with a
benign C1b the C1 gate silently reads `p = 0.9`, which is equally meaningless.

**Minimal fix.** `replace(..., permutation=replace(reference.permutation, delta=0.0, p_value=1.0))`.

---

## RT-V06-06 — the missingness gate can never fire

**Observed.** `hc_v0_6_report.build_report` calls `calibrate(c1_standin, c1b, c2)` with no
`missingness=` argument. `_missingness_reason(None)` returns `None`, so the check short-circuits
and `AssayStatus.ARM_DEPENDENT_MISSINGNESS` / `Outcome.O7_ARM_DEPENDENT_MISSINGNESS` are
unreachable from the report path. `CellTable.validate_balanced` is likewise never called.

Measured: a table with 60 anchors, `R_B` absent at 10 of them, produced a report whose primary
contrast used 50 anchors, with **no field anywhere in the payload naming the loss**.

**Expected.** Spec §10 lists missingness as a control gate whose failure makes the run invalid,
and §13 repeats it as an invalidation condition.

**Why it matters.** Combined with RT-V06-16 (the per-theorem `except` that manufactures
half-populated anchors) this is a gate that exists in the vocabulary and nowhere in the execution.

**Minimal fix.** Compute per-arm unanalysable counts from the table and pass them; add
`anchors_dropped_from_each_contrast` to the report payload.

---

## RT-V06-07 — the next cheapest fake after `skip`

**Observed.** The endpoint fires when `normalize_goal_text(after) != normalize_goal_text(before)`.
Three tactics are `ALLOWED` by `TacticPolicy.record_only()` (which refuses only
`sorry`/`sorryAx`/`admit`/`stop`), change the printed state, and do no mathematics:

| tactic | what it does | endpoint | cell |
|---|---|---|---|
| `rotate_left` | permutes the goal list | fires | `ACCEPTED_TRANSITION` |
| `rename_i fresh` | renames an inaccessible hypothesis | fires | `ACCEPTED_TRANSITION` |
| `clear h` | deletes an unused hypothesis | fires | `ACCEPTED_TRANSITION` |

152 of 1,127 anchors (13.5%) carry ≥ 2 goals, which is the exposure for the permutation form; the
other two need no multi-goal state at all.

**Expected.** "That action either closes the task or changes the declared backend state" is meant
to be a proxy for *did mathematics*. Reordering and renaming are changes to the declared state
that are mathematically null.

**Why it matters.** Not because the model will deliberately game it — because a representation
that makes structural-bookkeeping tactics *more likely* (`R_B` labels goals `[GOAL 1 OF 2]` and
hypotheses `(1)`, `(2)`, …, which is exactly the vocabulary `rotate_left` / `clear h` live in)
would produce a positive Δ for a non-mathematical reason. That is a live confound for this
specific intervention, not a generic worry.

**Cheap mitigation, no re-run needed.** `proposed_tactic` is recorded on every row. Count the
head of the proposed tactic by arm against a small no-op list (`skip`, `rotate_left`, `rotate_right`,
`swap`, `pick_goal`, `on_goal`, `rename_i`, `clear`, `case`, `next`, `all_goals skip`) and report it
beside Δ̂. If the rates are equal across arms the confound is measured away.

**Minimal fix.** Add a `MATHEMATICALLY_NULL_HEADS` set and a `step_result` of
`ACCEPTED_BOOKKEEPING`, scored 0.

---

## RT-V06-08 — the result hash still moves when nothing mathematical changed

**Observed.** `NON_DETERMINISTIC_FIELDS` contains `latency_ms`, and `_strip` removes it from every
dict in the manifest — but `cell_table_content_hash` is computed *inside* `CellTable` from
`row.to_dict()`, which carries `latency_ms`, and by the time `_strip` runs it is an opaque digest.

Measured, on two manifests differing only in one row's `latency_ms` (7 vs 9001):
`result_hash` `422f6bb0076271be…` vs `2b7ccc86285ae34e…`.

Two further routes: `skipped[].reason` and `theorem_errors[].error` carry backend text, and Lean's
diagnostics name the per-session temporary probe file
(`/var/folders/…/hamiltonian-lean-<random>/probe_X.lean:12:4: error: …`). Both were confirmed to
move the hash. That is the *same* class as the per-session scratch-path defect already fixed —
re-entering through free text rather than through a field name.

Controls held: pure timing (`solver_seconds` / `lean_seconds` / `wall_clock_s`) does not move the
hash, and a changed `step_result` does. The existing regression test
(`test_the_result_hash_ignores_wall_clock`) passes because it hashes an **empty** table, which is
exactly why the latency route survived.

**Minimal fix.** Give `CellOutcome` a `content_core` (everything except `latency_ms`,
`prompt_tokens`, `response_tokens`) and hash that in `CellTable.content_hash`; normalise scratch
paths out of `SkippedAnchor.reason` and `theorem_errors` before they reach the manifest.

---

## RT-V06-09 — the bijection contract does not constrain what the model sees

**Observed.** `arena/trajectory/representation.py` states: "A bijection cannot add information —
there is nothing to add it from — and cannot remove information, or it could not be inverted."
Two counterexamples were built, both subclassing `DeclarationDerivedRenderer`, both declaring
exactly `_declare_full` (so `derive_intervention_class` types them `R_ONLY`), both satisfying
`isinstance(r, BijectiveRenderer)` and `bijection_report(...).holds_everywhere == True`:

* **`R_HINT`** appends `\n[SUGGESTED TACTIC] rfl` — a tactic computed from the declared goal text.
  Round-trips perfectly (the inverse strips the line). Shows the model 49 characters where the
  baseline shows 25.
* **`R_HALF`** moves the first half of the goal text into a sibling key `context_appendix` and
  emits only the remainder as `goals_pp`. Round-trips perfectly (the inverse re-joins them).
  Shows the model 17 characters where the baseline shows 25 — and `goals_pp` is
  `arena.trajectory.solver.OBSERVED_FIELD`, **the only key the Solver ever reads**.

**Expected.** The contract is stated as a guarantee about what the arm shows. It is actually a
guarantee about what the rendered *mapping* contains in aggregate.

**Why it matters for this run: it does not.** `R_A_PRIME` and `R_B` are frozen, are visibly not
doing either of these, and RT-V06-06's independent prompt-hash re-derivation confirms what was
actually sent. What is wrong is the **claim**, and the claim is load-bearing for the next
representation anyone proposes: a bijection is not a bound on computational advantage, and it says
nothing about the single field the model reads.

**Minimal fix.** Add two checks to `check_bijection`: (a) the rendered mapping's keys must be a
subset of a declared per-arm key roster, and (b) `render(s)[OBSERVED_FIELD]` must be a permutation
of the baseline's `goals_pp` under a declared character-preserving relation (both current arms
satisfy the stronger property that they are equal as multisets of non-markup characters).

---

## RT-V06-10 — a hand-written cell can claim what it did not earn

**Observed.** Seven forgeries were pushed through `CellOutcome.from_dict`. Four were rejected:
an event with a parse status that never reached Lean; `closed_all_goals` against a non-event;
a stored endpoint boolean contradicting `step_result`; an arm wearing another arm's `renderer_id`
or `intervention_class`. Three were **accepted**:

* `step_result = ACCEPTED_TRANSITION`, `parse_status = OK`, `proposed_tactic = null`;
* an arbitrary `solver_digest` (`"not-a-model"`);
* an `R_B` row carrying `R_A`'s `prompt_sha256`.

**Expected.** The schema's own framing is that a cell cannot claim an outcome it did not earn.

**Why it matters.** The runner cannot produce these rows, so this is an audit-completeness gap
rather than a live defect. But it is closeable for free: `prompt_sha256` is a pure function of
(bank goal text, arm renderer, frozen prompt template). The verifier was built as part of this
red team and applied to the in-flight file.

**Result of applying it (RT06 evidence).** 4,508 expected hashes were re-derived from the frozen
bank for all four arms at all 1,127 anchors. The four arms produce four distinct prompt hashes at
**every** anchor (0 within-anchor collisions). Of the 1,402 rows present when the check ran
(351 `R_A`, 351 `R_A_PRIME`, 350 `R_B`, 350 `R_ABLATED`): **0 prompt-hash mismatches and 0
intervention-class mismatches.** Each arm demonstrably received its own bytes.

**Minimal fix.** Ship that re-derivation as a post-run structural check, and reject a row whose
`parse_status` is `OK`, `step_result` is in `_KERNEL_ACCEPTED`, and `proposed_tactic` is `None`.

---

## RT-V06-11 — the freeze moved after the run began

**Observed.** Against `2624be5` and with the primary process started `Wed Sep 9 04:59:35 2026`:

| file | lines changed since the freeze |
|---|---|
| `arena/experiments/hc_v0_6_assay.py` | 9 (mtime 04:58:50) |
| `docs/HC_V0_6_SPEC.md` | 86 (§8a added, §9(A) rewritten) |
| `docs/HC_V0_6_ANALYSIS_PLAN.md`, `HC_V0_6_DESIGN_BRIEF.md`, `HC_V0_6_PREREGISTRATION.md` | modified |
| `arena/experiments/hc_v0_6_report.py` | **untracked**, created 05:14 — after the pass began |
| `arena/experiments/hc_v0_6/{schema,estimators,calibration,power}.py`, `arena/trajectory/{anchor,representation,solver}.py` | 0 |

The assay edit is scientifically inert — it write-throughs already-computed rows to the stream file
(the streaming was documented and not implemented; the runner reported cells to a 0-byte file) —
and it landed 45 seconds *before* the process started, so the running code is the edited code.
The `SPEC.md` edits are a power analysis and a corrected multiplicity justification, neither of
which is downstream of an outcome.

**Why it matters anyway.** The document that opens "This document is the freeze… committed before
any outcome exists" is not the document on disk, and the analysis driver that will produce the
result was written while outcomes existed. Nothing observed is dishonest; the audit trail is.

**Minimal fix.** Commit the current state as an explicit amendment commit that says what changed
and when relative to the run, rather than leaving the freeze as a dirty working tree.

---

## RT-V06-12 — a served-digest mismatch does not stop anything

**Observed.** `build_manifest` wraps `solver.verify_served()` in `try/except`, truncates the error
to 200 characters into `solver_served_verification`, and continues. With a solver that raises
`SolverIdentityMismatch("model_digest: recorded='aaa' served='bbb'")` the manifest was still built,
still carries `scientific_status = "PREREGISTERED_ASSAY_RESULT_SET"`, still carries a
`result_hash`, and contains **no** field whose name signals validity.

**Expected.** Spec §13: "A run is `RESULT_INVALID` … if: a served model digest does not match the
manifest".

**Minimal fix.** Set `payload["invalidation"] = ["SERVED_DIGEST_MISMATCH", …]` and have the report
driver refuse a manifest carrying a non-empty `invalidation`.

---

## RT-V06-13 — the reported MDE describes a design that may not have been run

**Observed.** `build_report` computes `profile = ClusterProfile.from_anchor_bank(bank_path)` and
feeds it to `minimum_detectable_effect`. On a table with 60 anchors over 30 clusters the reported
MDE carried `n_anchors = 1127`, `n_clusters = 330`.

**Why it matters.** Spec §8 requires every null to be reported beside the MDE actually achieved,
and `release()` writes the caveat "informative null is scoped to |Δ| < {mde.points} points". If
anchors were lost, that caveat overstates the resolution.

**Minimal fix.** Build the profile from the contrast that was analysed
(`pair.n_anchors`, `pair.n_clusters`, and the realised cluster sizes), not from the bank.

---

## RT-V06-14 — `R_ABLATED` sends five prompts, not 1,127

**Observed.** Distinct prompt hashes across the whole bank: `R_A` 1,127, `R_A_PRIME` 1,127,
`R_B` 1,127, **`R_ABLATED` 5**. Its rendering is
`[GOAL TEXT WITHHELD BY R_ABLATED]\n[GOALS REMAINING n]`, and the bank's goal-count histogram is
{1: 975, 2: 129, 3: 17, 4: 5, 5: 1}. So 975 anchors receive a byte-identical prompt, and at
`temperature = 0` with a fixed seed the arm emits at most five distinct tactics in total.

**Why it matters.** C2 is not "the same policy shown less information" — it is a constant policy.
It still demonstrates the pipeline is causally connected to the outcome (the arm's Δ is real and
its variance comes from Lean's verdict on a fixed tactic at 1,127 different states), but it does
not demonstrate sensitivity of a *state-dependent* policy, which is what a representation effect
would need. The C2 gate should not be read as "the assay can detect an information change of the
scale a representation makes"; nothing in this design establishes that, and RT-V06-02's missing
`T_ablate` removes the only quantitative handle on it.

**Minimal fix.** Report the distinct-prompt count per arm in the manifest, and state this limit
beside the C2 reading.

---

## RT-V06-15 — closure is not axiom-checked

**Observed.** `_play_cell` sets `closed = bool(outcome.closed)`, which is `lean_backend`'s
`is_no_goals(tactic_state)` sentinel. The assay never calls `verify_closed_script` and never
consults `TRUSTED_AXIOMS` / `untrusted_axioms` (grep over `hc_v0_6_assay.py`, `hc_v0_6/`,
`anchor.py` returns nothing). `TacticPolicy.record_only()` allows `native_decide`.

**Why it matters.** RT-01 (the 2026-09-08 red team) closed exactly this hole for HC-V0 by adding
the `TRUSTED_AXIOMS` allow-list. The fix lives in a function this assay does not call, so a
`native_decide` closure scores a `KERNEL_ACCEPTED_STATE_CHANGE` with `Lean.ofReduceBool` in its
trust base and nothing records it. One-step closures are the minority of events, and the endpoint
also fires on a state change without closure, so the exposure is bounded — but the exposure is
unmeasured, which is the objection.

**Cheap mitigation, no re-run needed.** Count rows with `closed_all_goals = True` whose
`proposed_tactic` head is in `{native_decide, decide, norm_num, simp_arith}` and report it.

**Minimal fix.** For any cell with `closed_all_goals`, run `verify_closed_script` on the anchor's
prefix plus the proposed tactic and record `untrusted_axioms`.

---

## RT-V06-16 — a crashed theorem leaves a half-played anchor with no record

**Observed.** `run_assay` wraps a whole theorem in `try/except Exception`. An exception raised at
cell 3 of 4 leaves the anchor's first two arms in `run.rows` and abandons every remaining anchor of
that theorem; only `(problem_id, error_string)` is appended to `theorem_errors`. The abandoned
anchors do **not** appear in `run.skipped`, so `counts.skipped_anchors` does not see them.
`extract_pair` then drops the half-populated anchor silently (measured: 40 anchors in the table,
39 in the `R_A` vs `R_B` pair, 1 dropped without a record).

The exception routes that can do this are arm-correlated in principle: `UnrenderableStateError`
from `R_B`'s layout, `OracleLeakInPrompt` from the tripwire, `DesignViolation` from a class
mismatch.

**Expected.** Missingness must be recorded per arm and gated (spec §10, §13).

**Minimal fix.** Catch per-anchor rather than per-theorem; record every unplayed
`(anchor_id, arm)` in `run.skipped`; and emit the per-arm missing count into the manifest.

---

## RT-V06-17 — a genuine advance scored as a no-op

**Observed.** In `_play_cell`, an `OK` step with `outcome.tactic_state is None` yields
`changed_the_declared_state(parent, None) == False` → `ACCEPTED_NO_OP`. Confirmed end-to-end: the
cell's `step_result` is `ACCEPTED_NO_OP`, and `analysable` is `True`, so it counts as a
mathematical zero.

A second, milder route: `parent = live.parent_state_text(...) or anchor.solver_visible.goals_pp`
falls back to the **bank's** text when the session returns `None` *or* `""`. `matched` only
guarantees agreement of the *normalised* text, so a live/bank divergence inside the normalisation
would pass unnoticed. Both texts are normalised again in the comparison, so this is benign today.

**Minimal fix.** Treat `ok and to_state_id is not None and tactic_state is None` as
`ENVIRONMENT_ERROR`, not as a no-op.

---

## RT-V06-18 — what the 6-character floor actually lets through

**Observed and quantified over the whole frozen bank.** 6,158 reference-tactic occurrences,
**458 below the floor** across 35 distinct strings — `simp` ×135, `rfl` ×85, `congr` ×32,
`ext x` ×21, `dsimp` ×18, `intro` ×14, `right` ×14, `ring` ×12, `left` ×9, `tauto` ×8, `ext` ×29,
`aesop` ×6, `symm` ×6, `omega` ×4, and twenty more.

Every anchor was then rendered under every arm and scanned with the floor **removed** (length ≥ 1):

| surface | R_A | R_A_PRIME | R_B | R_ABLATED |
|---|---|---|---|---|
| full JSON payload (what the tripwire scans) | 0 | 0 | 29 | 29 |
| `goals_pp` (what the model actually reads) | **0** | **0** | **0** | **0** |

The 29 payload hits are `"ext"` inside the renderers' own metadata — `R_B`'s
`layout_id = "enumerated-**context**-headed-target-v1"` and `R_ABLATED`'s `goal_t**ext**_status`.
They are not model-visible, and they are precisely why the floor exists: at floor 1 the tripwire
would abort the run 58 times on its own markup.

**Verdict.** On this bank the floor costs **nothing**: zero reference tactics of any length reach
any model-visible payload. The finding is latent, not live — a renderer that ever surfaced a
derived tactic ≤ 5 characters (`rfl`, `simp`, `ring`, `omega`, `aesop`, `intro`) would pass the
tripwire, and 458 occurrences are in that class.

**Minimal fix.** Scan `rendered[OBSERVED_FIELD]` at floor 1 (the model-visible surface) *and* the
full payload at floor 6, rather than only the payload at floor 6.

---

## RT-V06-20 — model reload during the pass

**Observed.** `curl http://127.0.0.1:11434/api/ps` reported `gemma4:e4b` with
`"expires_at": "2026-09-09T05:25:24"` — a rolling keep-alive roughly five minutes ahead. The
serving process (`llama-server`, pid 76073, started 04:57) has been continuous so far, and a second
runner (`qwen3.6:27b-mlx`, started 04:59) was observed alive concurrently and has since exited.

**Why it matters.** Spec §6 forbids a mid-pass reload because the measured instability is
state-dependent (8/8 post-reload calls returned the variant warm calls return 1-in-14). A theorem
whose Lean probe elaboration exceeds the keep-alive would trigger exactly that. The randomised
within-anchor order converts a reload into noise rather than an arm-aligned bias, which is the
design working — but the run cannot currently *evidence* that no reload happened.

**Minimal fix.** Pass `keep_alive: -1` in the `/api/generate` payload for the duration of a pass,
and record `/api/ps` `expires_at` at the start and end in the manifest.

---

## Defences that held

Nine attacks failed. The three attacked hardest, in order of how much of the result rests on them:

**1. Anchor branching — every arm at an anchor acts on one Lean state.**
`LiveAnchor` is a frozen slotted dataclass, so `live_state_id` cannot be reassigned
(`FrozenInstanceError` on the attempt). All four arms were played through a session that records
the sid of every step: `["sid-parent", "sid-parent", "sid-parent", "sid-parent"]`, four children
created, and the parent's text byte-identical afterwards. `parent_state_text` reads a dict entry
written when the state was produced, and a later step writes a new key, so an earlier arm cannot
rewrite the parent a later arm compares against. The one latent hazard found is structural, not
live: `open_anchor_session` keys anchors by `prefix_length`, so two anchors of one theorem at the
same depth would silently collapse to one — the frozen bank has **zero** such collisions across all
393 theorems.

**2. No reference tactic reaches a rendered prompt.** Scanned at floor 1 — the floor removed
entirely — over all 1,127 anchors × 4 arms: **0** verbatim reference-tactic occurrences in the
model-visible `goals_pp` for any arm. This is a stronger statement than the bank's declared
"0/1,127 in the solver-visible payload", because it is measured on the *rendered* bytes after
`R_B`'s re-layout, which is where a derived leak would appear.

**3. The preregistered clustered test holds its level, and the anchor unit does not.**
Simulated on the frozen bank's exact cluster profile (330 clusters, 1,127 anchors, sizes 1–12,
mean 3.415), 400 nulls per cell, through the real `permutation_null` and `paired_bootstrap_ci`.
Monte-Carlo SE at nominal 5% is 0.011.

*Null with independent arms inside a cluster* — type-I of the cluster permutation:
0.050 / 0.045 / 0.048 at ICC 0 / 0.2 / 0.5 (baseline 0.133), 0.048 at baseline 0.25 / ICC 0.2,
0.035 at 0.40 / 0.5. Every cell within two SE of nominal.

*Null with clustered paired differences* — the case the cluster unit exists for:

| within-cluster discordance | cluster permutation | anchor permutation | cluster bootstrap | anchor bootstrap |
|---|---|---|---|---|
| 0.02 | 0.020 | 0.020 | 0.025 | 0.030 |
| 0.05 | 0.015 | 0.020 | 0.020 | 0.028 |
| 0.10 | **0.035** | **0.075** | **0.045** | **0.083** |
| 0.50 | **0.053** | **0.223** | **0.060** | **0.228** |
| 1.00 (maximal) | **0.068** | **0.345** | **0.068** | **0.363** |

The preregistered cluster test never exceeded nominal by more than Monte-Carlo noise anywhere on
this grid — 0.053 at half the anchors discordant, 0.068 at maximal clustering (1.6 MC-SE above
0.05, inside two SE). The anchor-level negative control reaches **0.223** and **0.345** on the same
data, 4.5× and 6.9× nominal, and the anchor bootstrap tracks it (0.228, 0.363). That is the
measured justification for the frozen choice, on this bank rather than on a generic one. Two
caveats worth recording: the design effect is modest at realistic discordance because the mean
cluster is only 3.4 anchors, and at low discordance **both** tests are conservative (0.015–0.02)
from discreteness, which means realised power is below the analytic MDE table of spec §8a — the
"true MDE is larger" reading the spec itself already flags.

The other six that held:

* **Model condition equality (A4).** The `/api/generate` payload was rebuilt for all four arms and
  all five preflight models. Every arm shares one non-prompt payload; every model shares one
  non-model payload. `num_ctx=32768, num_predict=128, temperature=0.0, seed=20260908, top_k=20,
  top_p=0.95, min_p=0.0, repeat_penalty=1.0, presence_penalty=0.0`, `raw/think/stream = false`,
  one grammar. Nothing is per-arm or per-model because `OllamaTacticSolver.payload` reads module
  constants and the prompt, nothing else. The longest prompt in the entire bank is 2,953 characters
  (`R_B`), so context truncation cannot differ by arm even at one token per character.
* **Arm interleaving (A5).** Over the real 1,127 anchor ids in the runner's own execution order:
  all 24 permutations used; position × arm χ² = 13.86 on 9 df (critical 16.92); Pearson correlation
  of arm position with execution index ≤ |0.050| and with anchor prefix depth ≤ |0.014|; identical
  under `PYTHONHASHSEED` 0, 1 and 12345 in separate processes; unchanged after 100,000 draws from
  the global `random` state. The schedule is a pure function of `(seed, anchor_id, arms-tuple)` —
  note the third argument: a three-arm secondary gets a different permutation from the four-arm
  primary, which is declared behaviour but means position effects are not paired across models.
* **No free redraws (A7).** One solver call per cell for an unparseable proposal, one solver call
  and one Lean step for a rejected tactic. No retry construct on any live path;
  `urllib_transport` has no `except`; `LeanReplSession.step` never restarts a session; a duplicate
  `(anchor, arm, replicate)` is rejected by `CellTable`; the stream file opens `"w"`, so a re-run
  truncates rather than accumulating draws. `k = 1` is structural.
* **Cluster unit (A8).** 1,127 anchors, 330 distinct source files, 393 theorems; every
  `cluster.file_path` ends `.lean` and none equals its theorem name; 51 files carry more than one
  theorem, so the file is genuinely coarser. `PairedEffect.p_value` returns the cluster permutation;
  the anchor-level variants are computed but carry `reportable = False`.
* **Control exclusion (A10).** `R_ABLATED` is absent from `REPRESENTATION_ARM_IDS`,
  `BIJECTIVE_ARM_IDS` and `NULL_PERTURBATION_ARM_IDS`; has no `invert` and fails
  `isinstance(..., BijectiveRenderer)`; is derived `P_CHANGE` with
  `permits_representation_claim = False`; a `CellOutcome` claiming it as `R_ONLY` is rejected;
  `classify_intervention(["goal_visibility"])` fails closed with `UnclassifiedGeneError` rather
  than defaulting to `R_ONLY`; and no module mentioning `R_ABLATED` overlaps with any league,
  archive or promotion module.
* **The IU gate logic blocks (A11b).** C1 firing → `BROKEN_IDENTITY_CONTROL`, release raises
  `AssayBroken`. Arm-dependent missingness → `ARM_DEPENDENT_MISSINGNESS`, blocked. Fewer than 30
  clusters → `INSUFFICIENT_CLUSTERS`, blocked, and re-checked separately for the primary contrast.
  `false_certification_bound()` correctly returns 0.05 from the single `REJECT_TO_CERTIFY` gate and
  refuses to fold the two `BLOCK_ON_REJECTION` gates in. One gap, reported above rather than here:
  a **failed C2** does not block — the run continues as `INSENSITIVE` and a significant primary is
  released as `O4_FAVOURS_R_B` with `attribution = UNDETERMINED`, where spec §10 says
  "interpretation of `R_B` stops".

---

## Is the result interpretable?

**Not yet — but the data are sound and nothing needs re-collecting.**

What was attacked and held is the part that cannot be repaired after the fact: the arms saw the
same Lean state, saw their own bytes (verified against the frozen bank for every row present), saw
no reference tactic, were played in a balanced arm-independent order, got one draw each under a
byte-identical model configuration, and are clustered by a unit whose test holds its nominal level
on this bank's real cluster profile.

What is broken is everything between those cells and a claim: harness failures are being scored as
mathematical zeros, the missingness gate cannot fire, the sensitivity and null-control gates test
something weaker than the freeze declares, the analysis driver crashes on `k = 1`, and the C1
stand-in decides its gate on another contrast's p-value. Those are six edits to two files, and
until they are made no number this assay prints means what the spec says it means.
