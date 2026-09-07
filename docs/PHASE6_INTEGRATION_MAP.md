# Phase 6 Integration Map

**Purpose.** This document tells the next session exactly what to do with the
`claude/phase-6-parallel-setup-9c6068` branch (the "parallel next-stage" branch) once Phase 6
reports, under every outcome Phase 6 can legally produce.

**Written by.** The parallel workstream, while Phase 6 was still running. It therefore contains
**no Phase-6 result**. Where a Phase-6 number would go, this document names the file to read
instead.

**Status of this branch.** Additive only. It changes no frozen scientific artifact, no
canonical schema, no verifier, no probe bank, and no experiment module. It can be abandoned
without affecting any recorded result.

---

## 0a. Status when this branch was finalised (2026-09-07 ~07:10 BST)

- **The Phase-6 run has FINISHED executing.** `=== QWEN BARE DONE 07:07:17 BST ===`. Both bare
  conditions completed; the gemma-bare artifact and the qwen-bare artifact exist.
- **No Phase-6 result document existed yet**, and this branch does not write one. Classification
  is the Phase-6 session's to make under its own preregistration.
- **A third, independent forensic audit** (Codex, branch `codex/forensic-audit-20260907`, writes
  confined to `docs/codex_audit/` and `research/codex_audit/`) reports that the qwen artifact
  contains **cache hits — 13 ladder resume hits plus 48 within-run full-family reuse hits** — which
  fires the literal `INVALIDATION_RULE` in `docs/PHASE6_PREREGISTRATION.md` ("cache hits > 0 for
  the alternate solver"). On that reading the outcome is **Branch D, `PHASE6_INVALID`**, with the
  solver-effect observation retained descriptively rather than confirmatorily.
- **This branch does not adjudicate that.** It is recorded here because it changes which branch of
  this map a reader should follow first, and because §5 (Branch D) is explicit that **every
  deliverable on this branch remains independently valid** under it — nothing here depends on any
  Phase-6 number.
- **Do not merge the Codex audit branch from here.** It is labelled `REPORT_ONLY` /
  `DO_NOT_MERGE` by its own author and contains no production patch.

## 0. Read this first — provenance and the non-duplication rule

Phase 6 (branch `claude/hamiltonian-arena-takeover-caa2eb`, pushed to `codex/arena-v0-fitness`)
substituted the Solver while holding the frozen V5 instrument fixed. This branch did **not**
duplicate, touch, or depend on that experiment. Nothing here was validated against a Phase-6
number, and nothing here presumes a Phase-6 outcome.

Authoritative Phase-6 sources, in order:

1. `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` — the result document (written by the
   Phase-6 session; may not exist yet).
2. `artifacts/experiments/fitness_v5/development/result-gemma4_12b-bare.json` and
   `result-qwen38-rvn_latest-bare.json` — the artifacts.
3. `docs/PHASE6_PREREGISTRATION.md` — the frozen design, its primary endpoint and its
   invalidation rule.

**Do not read a conclusion out of `artifacts/tmp/phase6*.log`.** Those are progress logs and the
Phase-6 preregistration explicitly forbids per-cell significance claims.

---

## 1. The four legal Phase-6 outcomes

`docs/PHASE6_PREREGISTRATION.md` (STOPPING_RULE) fixes the outcome classes. There are four, not
two, and this branch is useful under all of them.

| # | Sentinel | Plain meaning |
|---|---|---|
| A | `SOLVER_SPECIFIC_FAILURE_SUPPORTED` | The alternate solver escapes the collapse. Zero-shot Game R is measurable with a different π. |
| B | `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET` | The alternate solver differs, but not enough to qualify ≥ 2 mechanisms. |
| C | `FAILURE_REPLICATES_ACROSS_SOLVERS` | Both solvers collapse. The task family, not the solver, is the limit. |
| D | `PHASE6_INVALID` | An invalidation condition fired (cache hits > 0, digest mismatch, truncation, Q0 < 0.95, …). |

---

## 2. Branch A — `SOLVER_SPECIFIC_FAILURE_SUPPORTED`

**Meaning.** A second Solver family qualifies ≥ 2 V5 mechanisms. Game R becomes measurable
zero-shot. This is the branch where the existing Arena pipeline resumes on its own critical path.

**Use immediately from this branch:** nothing on the critical path. Phase 6 hands straight to
the frozen SCOUT → founder tournament → mutation campaign sequence, which already exists
(`docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md`). Do not divert to Route B.

**Sequence (unchanged from `docs/CLAUDE_FINAL_HANDOFF.md` §24):**

1. Freeze the SCOUT manifest and commit it before any founder call.
2. Run the 8-founder Game-R tournament against the `V5E_L3_JSON_AST` baseline.
3. Only if `founder_tournament_authorized` is true under the unmodified frozen gate, run the
   40-mutant campaign, then the landscape verdict.

**Two cautions this branch established that Branch A must respect:**

- `assert_information_parity` has been implemented and unit-tested but **never exercised on real
  probes**, because the frozen manifest holds zero SCOUT probes
  (`docs/CLAUDE_FINAL_HANDOFF.md` §8). The founder tournament is the first time it runs for
  real. Treat its first execution as a live test of the control, not as a formality.
- Before `formal_expression_depth` is reused for promotion it needs the ordering control and the
  identifier-obfuscation arm named in `docs/FITNESS_V5_RESULT.md` §5.3. Its Phase-5 shortcut leak
  (`first_mentioned_in_state` = 0.833 at the frontier stratum) is a construction defect, not noise.

**Hold for later:** everything else on this branch. Route B becomes the *learnability* gate
(`GOAL.md` names learnability as the principal causal object), which is downstream of a
FITNESS_CANDIDATE existing at all. The corpus and canonical-vNext work stays parked.

---

## 3. Branch C — `FAILURE_REPLICATES_ACROSS_SOLVERS`

**Meaning.** The failure is the task family. No local zero-shot instrument will expose R.
This is the branch this parallel workstream was built for.

**Use immediately from this branch:** Route B, in full. See §6 for the launch sequence and §7
for the authorisation gate that deliberately blocks it until the owner says go.

**Do not** build Fitness V6. `docs/GAME_R_STATUS.md` and the Phase-5 abort clause both forbid it
on this evidence: a new instrument version is admissible only when it changes a frozen variable
class named in the failure analysis. Under C the indicated change is **D** (the task family) or
the whole measurement modality (zero-shot → learning curve), and Route B *is* that change.

---

## 4. Branch B — `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET`

**Meaning.** The most likely and most awkward outcome: the solver matters, but not enough to
pass the gate. Treat this as **C for planning purposes and A for evidence**.

- Proceed as in Branch C (launch Route B) — there is still no FITNESS_CANDIDATE and no R*, so
  the founder tournament remains ungated.
- But record the solver effect as evidence that π is a live moderator of any future R claim.
  That has a direct consequence: **no representation result may ever be claimed on a single
  Solver family.** This was already the standing guard (`docs/CLAUDE_FINAL_HANDOFF.md` §14,
  "single-reader effects"); Branch B converts it from a precaution into a measured finding.
- A third Solver (`gemma4:31b`) is *recommended, never automatic*
  (`docs/PHASE6_PREREGISTRATION.md`, STOPPING_RULE). Deciding between "one more solver" and
  "switch to Route B" is a cost question, and Route B is now the cheaper prepared path.

---

## 5. Branch D — `PHASE6_INVALID`

**Meaning.** The comparison invalidated itself. No solver claim may be made.

**What from this branch remains independently valid?** All of it. Nothing in this branch depends
on any Phase-6 number, by construction:

- Route B's design and machinery depend on the *historical* matched-learning audit and on
  static code facts, not on Phase 6.
- The corpus inventory, the dataset registry and the contamination firewall are measurements of
  what exists on disk.
- The canonical-vNext pilot pressure-tests the schema against real formal data.
- The instrument-property analysis in §8 is computed from the **frozen Phase-5** artifact, which
  Phase 6 does not touch.

**Action under D:** repair and re-run Phase 6 per its own invalidation rule, and run Route B
preparation in parallel — they are independent.

---

## 6. Route B launch sequence (Branches B and C)

Preregistration: `docs/ROUTE_B_V1_SPEC.md`. **Read it before running anything**; it names the
frozen variables, the gates, the abort sentinels and the honest power analysis.

The single most important design risk, recorded here so it cannot be skipped: **the historical
676-world NEXT_ACTION slice saturates** (both finalists reach 1.000 at 576 examples). A learning
curve on a saturated task measures nothing. The spec therefore requires a headroom check to pass
*before* any GPU minute is spent, and names an abort sentinel for the case where no available
slice has headroom. Do not "proceed anyway and see".

---

## 7. The GPU authorisation gate — read before spending money

Route B is **NOT AUTHORISED**. No GPU minute may be spent until the project owner authorises it
explicitly. This branch adds a mechanical, fail-closed gate so that an accidental invocation
cannot start spending; see `arena/training/gpu_authorisation.py`.

The gate is deliberately annoying. Do not weaken it to make a run convenient.

---

## 8. Instrument property measured from frozen Phase-5 data (applies under every branch)

While Phase 6 ran, this branch re-examined the **frozen** V5 artifact (read-only, zero model
calls; `fitness_v5.py` was read as text, never imported) for an inconsistency between frontier
selection and the qualification gate.

**The defect is real, and its provenance is traceable.** The selector minimises
`|accuracy − 0.625|` (`arena/experiments/fitness_v5.py:915-948`, target constant at `:213`).
The destroyed twins are confirmed information-identical — same state object, same options tuple,
differing only in `expected_index` (`:485-486`, asserted `:505-509`), and `build_prompt`
(`:550-565`) never sees `variant` or `expected_index`. Verified in the frozen rows: **24/24 twin
pairs had identical `prompt_hash` AND byte-identical `raw_output`, opposite targets, 24 of 48
correct — exactly 0.5000.** So `gap ≥ 0.20` reduces to `positive ≥ 0.70`, `destroyed ≤ 0.60` is a
**dead gate**, and the effective window is **[0.70, 0.85]** with the selector aiming 0.075 below
its own floor.

*How it happened:* V3 (`fitness_v3.py:56,61`) and V4 (`fitness_v4.py:143,148,152`) used
`gap_min = 0.10`, giving a window of [0.60, 0.85] in which 0.625 sat comfortably. V5 raised the
gap to 0.20 on simulation evidence and left the target untouched. One uncoordinated constant edit
stranded the aim point.

**It changed nothing about the Phase-5 result.** Exactly one of the nine (mechanism × L1..L3)
cells falls inside [0.70, 0.85] — `precondition_conjunction` L1 at 0.7083 — and **the frozen
selector already chose it**; it failed on `largest_answer_share` 0.7917 > 0.75, not on the gap.
Every other cell is above the 0.85 ceiling or below 0.70. Re-running the frozen ladder under
three alternative selectors yields **0 of 3 qualified in every case**, identical to the record.
`FITNESS_V5_RESULT` stands unchanged.

**The naive fix is worse than the defect.** 44 profiles × 20k replicates at n = 24:

| selector | sensitivity | coin-flipper FP | true-0.65 reader FP |
|---|---|---|---|
| current (0.625) | 0.257 | 0.021 | 0.074 |
| window midpoint (0.775) | 0.707 | 0.054 | **0.533** |
| highest-qualifying | 0.734 | 0.055 | **0.587** |
| **oracle (knows true p)** | **0.564** | 0.018 | 0.254 |

Both naive fixes score *above the oracle* — proof they convert sampling noise into passes rather
than selecting better. The dominant limitation is not the aim point at all: the window is only
**1.76 SE wide at n = 24**, and both real ladders step straight over it (0.875 → 0.542;
0.917 → 0.667). **Sample size and ladder granularity dominate.**

Full operating characteristics: `artifacts/reports/v5_selector_analysis.json`.

### Consequences for Phase 6

- **The primary endpoint is immune.** The McNemar degeneracy test is computed at three
  prespecified fixed cells and never reads `positive_accuracy`, the gap, the band or any verdict.
  The preregistration's own "compare at FIXED levels" clause is exactly the right immunisation and
  predates any Phase-6 call. Secondary ladder accuracy and the descriptive grid are also immune.
- **Not immune:** any claim of the form "mechanism M did not qualify", and any cross-solver
  comparison of *verdicts* — those are joint properties of the ladder **and** the selector.
- **Free recommendation, costs nothing, rows already collected:** report the full L0..L3 ladder
  for both solvers alongside the verdicts.

### If a future instrument version is ever built

Minimal legitimate correction: make `frontier_target` a **derived** quantity
(`(gap_min + destroyed_expected + band_high)/2`) so the constants cannot drift apart again; drop
the dead `destroyed ≤ 0.60` gate; state the effective window arithmetically. This is legitimate
because it is derivable from frozen definitions *before* seeing outcomes, moves *where* you
measure rather than *whether* anything passes, removes a degree of freedom, and **changes nothing
on the frozen data**.

It becomes protocol shopping if instead you lower `gap_min` back toward 0.10, raise the 0.85
ceiling, adopt "highest qualifying" (selection on the qualification statistic itself), or re-score
V5 under any new selector. Note also that under `docs/FITNESS_V5_SPEC.md` §9 a selector repair
alone is threshold re-tuning and does **not** by itself license a new instrument version.

**Under no circumstances** may this analysis be used to re-score V5, promote a candidate, or
reinterpret a recorded sentinel.

## 9. Merge and cherry-pick guidance

**Do not merge this branch into the Phase-6 branch from this branch.** The Phase-6 session owns
its own branch and its own result document.

Base of this branch: `b82f8ed` (`docs: Phase 6 concurrency notice`), i.e. the pushed tip of
`codex/arena-v0-fitness` at the time Phase 6 started. It is therefore a clean descendant and
merges forward without rewriting history.

**Known conflict, and how to resolve it.** Both branches must, under the project's commit
protocol, update:

- `docs/PROJECT_LEDGER.md` — **append-only**. Both branches append at the tail, so the tail will
  conflict. Resolution: **keep both entries, ordered by their recorded timestamps.** Never delete
  or rewrite either entry; the ledger's value is that it is not rewritten.
- `docs/PROJECT_STATUS.md` — a full current snapshot. Resolution: take the **Phase-6 session's**
  scientific sections (it owns the experimental state) and merge in this branch's
  additive sections (next-stage readiness, corpus assets, Route B status).

`docs/PHASE6_IN_PROGRESS.md` is owned by the Phase-6 session and should be deleted by it, not by
this branch, once the result document exists.

---

## 10. What this branch deliberately did NOT do

- Did not run any model call, GPU job, or training run.
- Did not modify `GOAL.md`, the canonical schema, the Gold set, the verifier, the language
  surfaces, the probe bank, or any experiment module.
- Did not create Fitness V6.
- Did not adopt a Typed E-Graph core, MMT/OMDoc, a Lean-native IR, a Metamath-native IR, or a
  universal micro-action ontology. These remain **unproven hypotheses**; see
  `docs/CANONICAL_VNEXT_PILOT.md` for what the evidence actually supports.
- Did not import historical model scores as new evidence.
