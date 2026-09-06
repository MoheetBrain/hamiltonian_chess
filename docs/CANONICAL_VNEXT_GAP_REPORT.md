# Canonical vNext — Gap Report (research only, nothing implemented)

Scope: what external and donor corpora could contribute to a future canonical substrate,
task distribution, library layer, trajectory format and verifier, and where the current
`arena-canonical-v0.1.0` schema falls short. No Gold artifact, generator, verifier or
experiment was modified. No corpus was downloaded. Claims about external datasets are from
general knowledge as of the assistant's training and must be re-verified against the actual
releases before any ingestion.

## 1. Current schema in one paragraph

`CanonicalState` holds typed objects, bindings with scope ids, assumptions, established
facts, propositions, one goal, obligations with status/owner, an evidence DAG with
status/authority/certificate, local scope, legal and plausible-invalid actions, and a
terminal status. `CanonicalExpression` is an op/args/value/sort/attributes tree.
`CanonicalTransition` binds before-state, action, after-state and verification records.
Truth is structural (`NativeVerifier`) plus domain-template replay, SymPy, Z3 and numerics.
It is a single-goal, single-scope, first-order-ish substrate with no universe levels, no
metavariables, no implicit arguments, no definitional unfolding, no tactic-state history.

## 2. Reuse-first: what the donor repositories already hold

| Donor state | Holds | Immediate value for Game R |
|---|---|---|
| HML_V3 `codex/lean-runtime-semantic-capture-v2` (`99475f4f…`) | Lean 4.10 runtime extraction: exact `Expr` trees, FVarId/MVarId identity, local context, InfoTree paths, `CanonicalMathTransition V2` corpus (`data/corpus/lean_runtime_v2.canonical.jsonl.gz`) | the only verified real-Lean state source in the programme; 45 audited EXPRESSION_DEPTH items with a known 0.167 reader accuracy |
| HML_V3 `codex/open-ended-search-v2` at `95e8a26…` | `projection/dense.py`, `realism.py`, 32-cell factorial results, `HARD_REGIME_V1`, 128-item two-reader replication set, MicroMath instruments for type/dependency/binder/scope/premise/action-argument/expression-depth | calibrated positive/negative arms for seven structural components; the depth generator V4 adapted; a second reader family (`gemma4:31b`, `qwen38-rvn`) already exercised |
| hml-reasoning-corpus `claude/max-ev-representation-experiment-v1` (`bf2cd75a…`) | 5,619-row theorem-grouped dataset with structural OOD splits, 16 hard-negative mutation families, group-aware splitter | OOD split machinery; hard-negative families for the Refuter; not Arena-schema compatible without an adapter |
| hml-reasoning-corpus `codex/lean-attestation-v1` (local clone `hmlt-reasoning-corpus-lean-attestation`) | pinned Lean runtime attestation bridge, verifier-certified counterfactual Stage100 harness | a path to Lean-attested truth for imported states |
| hamiltonian-lang `feature/hml-reasoning-kernel-v2` (`3b7fe893…`) | executable claims/goals/actions/evidence/obligations with transition verification | reference for multi-goal and obligation semantics |

Conclusion: for a V5 measurement instrument, the HML_V3 Lean runtime corpus plus its
calibrated instruments already provide real hard structural states (deep expressions with
recurrence, long local contexts, multiple goals, deep binders). They should be adapted through
a proved schema adapter before any external corpus is considered.

## 3. External corpora: contribution map

| Source | Σ semantics | D tasks | U libraries | S_t→a_t→S_t+1 | Verification | NL↔formal |
|---|---|---|---|---|---|---|
| Mathlib4 | full dependent type theory; needs Lean runtime extraction | proof states at every tactic step | the library itself (declarations, simp sets) | tactic-step trajectories via LeanDojo-style tracing | Lean kernel | docstrings only |
| LeanDojo (traced Mathlib, benchmark) | as Mathlib | goal→tactic pairs with premises | premise retrieval corpus | yes, per tactic | Lean | none |
| miniF2F | formal statements only | 488 olympiad-style statements | none | proofs must be generated | Lean/Isabelle | informal statements paired |
| ProofNet (and verified variants) | formal statements | undergraduate statements | none | none | Lean | NL↔formal pairs |
| FormL4 / Lean Workbook | auto-formalised statements, mixed quality | large statement pools | none | partial | Lean, with unverified subsets | NL↔formal, noisy |
| MATH / AMPS | informal only | 12.5K competition problems / millions of synthetic | none | NL solution steps, unverified | final-answer match | informal side only |
| NuminaMath | informal, with CoT/TIR | ≈ 860K problems | none | NL/TIR steps | answer match, code execution for TIR | informal |
| Nemotron-Math-Proofs, Goedel datasets | Lean statements + generated proofs | statement pools with proofs | none | whole proofs, not per-step states | Lean-checked subsets | NL↔formal |

For Game R specifically, only sources with executable verification of *states* (Mathlib via
Lean runtime, LeanDojo traces, the HML_V3 corpus) can supply Σ; the informal corpora supply
D diversity and later curriculum/SFT material, not measurement truth.

## 4. Schema gaps blocking a Lean-backed substrate

1. **Multiple goals / metavariable context.** `CanonicalState.goal` is one expression; Lean
   states carry a goal list with shared metavariables. Needed: `goals: tuple[Goal, ...]` with
   ids and a metavariable assignment map.
2. **Binder identity and de Bruijn / FVarId.** `Binding` has `binder_id`/`variable`/`scope_id`
   but expressions bind through `forall(var x, body)` only; no local-context ordering, no
   dependency between binders' types. Needed: ordered local context entries whose types are
   expressions, and binder nodes referencing entries by id.
3. **Universe levels, implicit/instance arguments, coercions.** Absent. Needed at least as
   attributes so information parity can be audited.
4. **Definitional unfolding / reducibility.** No notion of `defeq`; verification of
   Lean-derived transitions requires the kernel as authority (`VerificationRecord` can carry
   it; the native verifier cannot).
5. **Tactic actions.** `CanonicalAction.operation` is a free string; a Lean adapter needs a
   typed tactic vocabulary and premise references (`external_premise_refs`), which HML_V3's
   `CanonicalMathTransition V2` already models.
6. **Provenance fields for imports.** Required by the takeover directive: source repo, original
   id, source SHA, adapter version, verification path, canonical hash, intended mechanism,
   split. `CanonicalTrajectory.provenance` is a free map; this should become a typed record.
7. **Trajectory richness for post-R* training.** `GOAL.md` §22 lists warrant, preconditions,
   obligations, failed alternatives, counterexamples, repairs, subgoals, search decisions;
   the transition record holds action/verification only.

## 5. Recommendation

- vNext should be `arena-canonical-v1.0.0` with explicit migration and new hashes, adopted
  between experiments, never mid-experiment (`GOAL.md` §4).
- First import target: HML_V3 `lean_runtime_v2.canonical.jsonl.gz` through a proved adapter
  covering gaps 1, 2, 5 and 6, with Lean attestation from the `lean-attestation-v1` bridge.
- External corpora are deferred until a valid Game-R instrument exists; when they enter, they
  enter as D (tasks) with executable verification, and MATH/AMPS/Numina only as curriculum/SFT
  material after `RSTAR_0_1` or an explicit Game-T decision.
