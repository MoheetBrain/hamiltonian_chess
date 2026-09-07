# Parallel Next-Stage Handoff — zero-context

**Branch** `claude/phase-6-parallel-setup-9c6068` · **base** `b82f8ed` (the pushed tip of
`codex/arena-v0-fitness` when Phase 6 started) · written 2026-09-07.

**What this branch is.** Preparatory work carried out *alongside* the live Phase-6 experiment,
deliberately off its critical path. It runs **no experiment**, makes **no model call**, spends
**no GPU minute**, and changes **no frozen scientific artifact**. Its purpose is that whatever
Phase 6 concludes, the next scientifically correct step can start immediately.

**What it is not.** It is not a Phase-6 result, does not reinterpret one, and does not promote any
representation. `RSTAR_NOT_IDENTIFIED` stands.

---

## 1. If you read only one section

Four measured findings change what the project should do next. Each was produced without a model
call, and each is reproducible from the scripts in `research/`.

1. **The Route-B task family is degenerate.** A model-free predictor reproduces the *entire* gold
   `NEXT_ACTION` target on **676/676** tasks (held-out **96/96**), and **0.8195** of it with zero
   arithmetic. Seven of eight target fields are fully mechanical. Obfuscation does not repair it.
   → The historical `exact ≈ 1.000` is **not evidence of mathematical learning**, and this family
   cannot serve a learning-curve experiment. `artifacts/reports/next_action_leakage.json`.
2. **The five Route-B arms do not test genes.** `L0/L1/L2/L3/L5` are hand-written codecs whose
   `_encode_payload` never reads `self.genome`. Only `GenomePhenotypeLanguage` is genome-driven.
   Changing a gene changes nothing for those arms. → Route B must declare which question it asks.
   `docs/ROUTE_B_PARITY_AUDIT.md` §1.
3. **The V5 frontier selector aims at a value that cannot qualify** — but it cost Phase 5 nothing,
   and the naive fix is worse than the defect (both re-aimed selectors score *above* an oracle that
   knows the true accuracy, i.e. they convert noise into passes).
   `artifacts/reports/v5_selector_analysis.json`.
4. **The best next corpus is already on disk.** A full LeanDojo Benchmark 4 trace — 259,580 tactic
   transitions with premise annotations, at the *same pinned mathlib commit already built locally* —
   sits unused at `~/Projects/Hamiltonian-Labs/hml_research_artifacts/`. The top-ranked external
   source needs **zero download**. `docs/CORPUS_STRATEGY.md`.

---

## 2. Deliverables

| Document | What it settles |
|---|---|
| `docs/PHASE6_INTEGRATION_MAP.md` | What to do under each of the four legal Phase-6 outcomes; the merge-conflict rule |
| `docs/ROUTE_B_V1_SPEC.md` | Preregistered matched-learning design (866 lines). **Not authorised to run** |
| `docs/ROUTE_B_PARITY_AUDIT.md` | Six measured defects that would silently bias Route B; the 27-axis parity checklist |
| `docs/CORPUS_STRATEGY.md` | Ingestion decisions, the seal-now list, the firewall, the honest OOD position |
| `docs/REASONING_OPERATION_DISCOVERY.md` | Which reasoning operations actually recur across humans, models and formal proofs |
| `docs/FUTURE_ENVIRONMENT_FAMILIES.md` | Ranked candidate task families; the fail-fast shortcut check |
| `docs/CANONICAL_VNEXT_PILOT.md` | Measured schema gaps against 368 real Lean states. No schema change made |

Machine-readable: `artifacts/reports/{parallel-work-safety,v5_selector_analysis,next_action_leakage,canonical_vnext_gap_verification}.json`,
`artifacts/corpus/{source_registry,user_reasoning_chain_inventory,local_formal_inventory,operation_inventory}.json`.
Reproduction scripts: `research/{selector_analysis,leakage,canonical_vnext,operations}/`.

**New code** (all additive, none wired into any experiment):
`arena/training/route_b_data.py` (frozen hashed nested budget manifests),
`arena/training/verified_eval.py` (the verifier-backed metric that did not exist),
`arena/training/gpu_authorisation.py` (fail-closed spend gate),
`arena/corpus/{trace,contamination,provenance}.py` (trace contract, transitive-exposure firewall,
ingestion provenance), plus additive flags on `arena/training/prepare_matched_data.py`.

---

## 3. Answers to the questions that prompted this workstream

### "What reasoning operations recur across human, model and formal solutions?"

**Nine families are attested in all three**, reported per-source and never pooled (A = 769
gold-labelled MATH steps, B = 42,963 human reference-solution sentences, C = 81,908 PRM800K model
steps, D = 8,766 LeanDojo tactics): APPLY_THEOREM · SUBSTITUTE/REWRITE · INTRODUCE · CASE_SPLIT ·
TRANSFORM · CONSTRUCT · APPLY_DEFINITION · DISCHARGE · INDUCT.

**But the alignment verdict is mostly negative, and that is the finding.** Only **2 of 9** align
strongly (INDUCT, CASE_SPLIT); **4 are same-name-different-operation**. The clearest failure is
DISCHARGE: informal it means "final answer" (once per trajectory, 89/90 containing `\boxed`);
formal `CLOSE` means "this branch finished" (44.4% of all steps). Matching by name *manufactures*
the recurrence.

The genuinely useful split is **canonical vs controller**, and it is stable across corpora:
77.87% / 22.11% on representative LeanDojo, 76.91% / 23.09% on the 241k census, and — on an
orthogonal axis — 22.11% controller in the annotated corpus. That agreement of proportion is
worth more than the shared vocabulary.

### "Are the owner's granular reasoning chains a major asset?"

**Partly, and the honest number is much smaller than assumed.** The richly-annotated corpus is
**792 steps** (769 Gold-125/Gold-25 + 23 hand-authored Gold-10), not hundreds of thousands; the
~260k figure refers to LeanDojo tactic transitions. Independently confirmed by the Codex audit at
the same 792.

The binding constraint is structural: **verification and richness are anti-correlated.** Everything
`VERIFIED_FORMAL` is single-operation Lean data with no warrants; everything richly annotated is
unverified and MATH-contaminated. **Nothing on disk is both.** Only 32 transitions anywhere have
been freshly replayed in Lean. There is **no large corpus of owner-authored chains** and **no
exported conversation logs** — 10 hand-authored problems is the whole set.

That does not make them worthless: 792 well-annotated steps are enough to *propose* an operation
vocabulary, and Gold-10 is the only contamination-free asset in the estate. They are not enough to
*establish* one. The cheapest fix is a second annotator on the existing 769 (there is currently no
error bar at all), then annotating aligned formal steps on miniF2F/ProofNet — both already local.

---

## 4. Do not repeat these mistakes

- **`assert_no_answer_leakage` cannot detect answer leakage.** Its signature is
  `(observation, kind)` — it never receives the gold target, so it is structurally incapable of
  testing an observation→answer relation. It is also never called on the training path.
- **`verified` in the historical sprint means "the JSON has three keys".** It read 1.000
  everywhere. `NativeVerifier` has never been run on a model prediction.
- **`stratified_split`'s `seed` is inert** — declared and never used. Preserved deliberately as the
  legacy path (a historical artifact depends on its exact ordering); real seeding is a separate,
  keyword-only function.
- **Two mathlib checkouts of the same commit exist**, one built (18 GB, 5,680 `.olean`, at
  `external/runtime_work/…`) and one source-only (349 MB, 38 `.olean`, at `external/checkouts/…`).
  Two careful audits reached opposite conclusions about whether mathlib is built purely by looking
  at different paths. **Name the path.**
- **The shared venv's editable `.pth` points at the main checkout.** `python -m pytest` resolves to
  the worktree; the bare `pytest` console script does **not**. Always use `python -m`.

---

## 5. Verification

Run from the worktree with `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python`,
always via `python -m` (§4). Final state of this branch:

```
python -m pytest              470 passed in 13.77s   (baseline before this branch: 190)
python -m mypy arena          Success: no issues found in 125 source files
python -m ruff check .        All checks passed!
python -m ruff format --check .   223 files already formatted
```

280 tests were added and nothing regressed. `research/` is excluded from the lint gate
(`pyproject.toml`) — those are one-off analysis scripts kept for reproducibility of a
measurement, not library code; anything promoted into `arena/` must pass.

Frozen-artifact integrity re-verified at the end of this session: `GOAL.md`
`43d8fcdb…0117b` and Phase-5 `result.json` `0c5b3271…97579` both match their declared hashes.

---

## 6. Concurrency discipline that was actually followed

Phase 6 was live for this entire session. Every agent operated under: no model call, no Ollama
workload, no process signals, writes confined to this worktree, read-only everywhere else.
Contamination was shown to be structurally impossible — every Arena output path resolves from CWD,
and the only hardcoded absolute path in the package is a read-only glob into `HML_V3`
(`arena/environments/formal_structural.py:49`). Empirically confirmed: across a full
pytest/ruff/mypy run the live `result.json` stayed byte-identical and the live cache stayed at 716
files. Details and the eleven standing conditions: `artifacts/reports/parallel-work-safety.json`.

---

## 7. Highest-EV next action

**Do not launch the founder tournament.** The frozen gate requires ≥ 2 qualified mechanisms and
nothing has met it. Do not lower the threshold.

In order:

1. **Let the Phase-6 session publish its own classification.** If the cache-hit finding holds, that
   is `PHASE6_INVALID`, and the solver-effect observation is descriptive, not confirmatory.
2. **Do not run Route B as specified for the historical task family.** §1.1 retires it. Route B v1
   already names a replacement slice and a headroom gate that must pass *before* a GPU minute.
3. **Build the fail-fast shortcut check first** (`docs/FUTURE_ENVIRONMENT_FAMILIES.md` §5). It is
   minutes of CPU, needs no model, and would have killed the degenerate family before the
   historical GPU sprint. Adopt it as a precondition on every future family.
4. **Then build premise selection from the local LeanDojo trace** — ~163,300 items, real
   distractors, a purpose-built `novel_premises` OOD split, zero download. **Seal
   `novel_premises/{val,test}.json` before touching anything**; use `random/train.json` for
   adapter work.
5. **Pin `gemma4:12b`'s training cutoff.** It is the cheapest high-value record in the project:
   without it, every temporal-holdout OOD claim is a hypothesis.

---

## 8. Related work by other sessions

`codex/forensic-audit-20260907` ran an independent forensic audit in parallel
(`docs/codex_audit/`, `research/codex_audit/`). It **independently reproduces** several findings
here — the inert split seed, the GOLD/SILVER/REJECT training mix, the 21/48 answer recurrence at
budget 224, the key-presence `verified` metric, the codec-not-gene problem, the 1,536-token
truncation, the 676/676 World-v0 solvability, and the 792-step chain count — and corrects the
`first_mentioned_in_state` figure to its stratified form (1.000 shallow / 0.9167 deep-L3 / 0.8125
pooled), which has been applied here. It is labelled `DO_NOT_MERGE` by its author and contains no
production patch. The mathlib-checkout disagreement between the two audits is resolved in §4.
