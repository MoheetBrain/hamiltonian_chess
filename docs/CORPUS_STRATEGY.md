# Corpus Strategy

**Status:** decision document. Nothing here has been executed. No corpus was downloaded, no
model was called, and no file outside this document was created or modified while writing it.

**Evidence base.** Every claim below traces to one of:
`artifacts/corpus/source_registry.json` (27 external sources, verified 2026-09-07),
`artifacts/corpus/local_formal_inventory.json` (local Lean assets, counts re-derived from the
files on disk), `artifacts/corpus/user_reasoning_chain_inventory.json` (32 local reasoning
assets, 13 taxonomies, 12 NOT-FOUND results),
`artifacts/reports/canonical_vnext_gap_verification.json` (368 real proof states pressure-tested),
`GOAL.md` (the Σ/P/R/τ/π/C/D/U/V/B separation), `docs/CLAUDE_FINAL_HANDOFF.md` §8,
`docs/CANONICAL_VNEXT_GAP_REPORT.md`, `docs/CROSS_REPO_ASSET_AUDIT.md`,
`docs/REUSE_SUMMARY_FOR_CLAUDE.md`, and `/Users/moheet/Documents/ChatGPT/HML_V3/data/registry/datasets.yaml`.
Facts newly checked while writing this document are marked **[checked here]**.
Facts the registry itself records as unresolved are marked **UNVERIFIED** and are not
laundered into decisions.

---

## 1. The decision in one page

**We ingest almost nothing, because the highest-value external source is already on this
machine and no Arena module has ever opened it.**

`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4`
holds the complete LeanDojo Benchmark 4 v10 trace — 259,580 tactic transitions with premise
annotations, plus `corpus.jsonl` with 180,973 declarations over 5,674 files — traced from
mathlib4 at commit `29dcec074de168ac2bf835a77ef68bbe069194c5`, which is the *same commit* as
the locally built mathlib (4,447/4,447 modules, Lean v4.10.0-rc1, `Lean4Repl.olean` compiled,
offline replay path with no download step in the driver). **[checked here]** the directory,
`metadata.json`, both split directories and the 68,141,936-byte tarball all exist as recorded.
The registry's rank-1 recommendation therefore costs **zero bytes of download**.

### Ingest now (in this order)

| # | What | Bytes | Why it is first |
|---|---|---|---|
| 0 | **Nothing.** Build the premise-selection, rewrite-direction and legal/illegal-transformation task families from the LeanDojo trace + local mathlib already on disk. | **0** | Four of the seven candidate task families are constructible with no download at all (§3). |
| 1 | **ProofNetVerif** (`PAug/ProofNetVerif`), whole dataset; use the `valid` split (2,300 items), seal `test` (1,452) on arrival unopened | 406,549 | The only cheap probe that attacks the V5 failure mode directly: semantic equivalence has no surface-frequency proxy, whereas the dumb rule `more_frequent_in_state` already scores 0.798 on the 104 length-fair depth states. Fits the existing controller C (single greedy JSON A/B) with no new machinery. |
| 2 | **miniCTX-v2** `minictx-valid/` **excluding** `mathlib.jsonl` (six non-mathlib configs) | 2,983,046 | The only OOD candidate whose shift axis is nameable. Conditional on step 1 producing a measurable band. |
| 3 | **Lean Workbook** `wkbk_1009.parquet` only (25,200 tactic-state rows) | 4,600,174 | Non-mathlib before/after states — the distributional control that no amount of extra mathlib data can buy. **[checked here]** the local `HML_V3/external/checkouts/Lean-Workbook` copy is an LFS *pointer* (132 bytes), not the payload, so this one genuinely needs fetching. |
| 4 | **Metamath `set.mm`** at a pinned commit SHA, excluding `peano.mm` | 51,367,012 | The second formal system. Deferred behind a Lean-side effect existing; scoped now because it is one CC0 flat file with no toolchain. |

**Authorised total: 59,356,781 bytes = 2.76 % of the 2 GB ceiling.** Waves 1+2 alone are
7,989,769 bytes (0.37 %). This is 70,760,536 bytes *less* than the registry's proposed pilot
(130,117,317 B), a 54.4 % reduction, almost all of it because LeanDojo needs no download.

### Defer

- **PutnamBench** `lean4/` — the Lean/Isabelle/Coq triples are the only naturally occurring
  held-Σ-fixed / varied-R comparison in existence, which is exactly why reading them now
  would burn the asset for an instrument that does not yet qualify. Scope it; do not open it.
- **Isabelle AFP** and **Magnushammer** — strictly dominated by `set.mm` on effort. AFP ships
  no intermediate proof states (a whole second proof assistant to install); Magnushammer is
  11.7 GB and its README warns that its own `step` field leaks premise names into the state.
- **ProofNet-Verified** (`marcusm117`, Apache-2.0) — the only ProofNet variant shipping formal
  *proofs*, hence the only one from which transitions could be replayed. Blocked by a real
  toolchain gap: it needs Lean v4.28.0 against a local v4.10.0-rc1.

### Refuse outright

- **Hendrycks MATH** and **PRM800K** — legal and scientific. An accepted AoPS DMCA
  (2025-01-02) claims >10,000 of the 12,500 problems and *all* solutions with derivative
  removal requested; the canonical HF copy is disabled. PRM800K's training data contains
  4,500 of the 5,000 MATH test problems, and **[checked here]** `prm800k/math_splits/test.jsonl`
  is exactly 500 lines — it *is* MATH-500. Both are already on disk in duplicate; the decision
  is that they stay read-only where they are and never enter Arena.
- **OpenWebMath** (56.7 GB, no verifier, per-document licences uncleared), **NuminaMath**
  (~900k informal items, no states, maximal contamination), **AMPS** (23 GB of templates
  behind a 403ing Drive link), **NaturalProofs** (three copyleft sources plus a
  non-commercial one, and no verifier at all), **FormL4** (no LICENSE file at all).
- **miniF2F as evidence.** Demoted to plumbing: arXiv:2511.03108 finds formal/informal
  discrepancies in more than half its problems (36 % vs 70 % accuracy against a corrected
  version), so it can support neither a capability claim nor an alignment claim. **[checked
  here]** the DeepMind Lean 4 port is already local at
  `HML_V3/external/checkouts/miniF2F` pinned at `f0a20e1`, so even the smoke-test use needs
  no download.

### The one honest caveat on all of it

Nothing here is a plan to *measure* anything yet. Fitness V5 ran with a sound instrument and
**0 of 3 mechanisms qualified**; the preregistered abort clause fired. Corpus is not the
binding constraint — `docs/PROJECT_STATUS.md` names the Solver as the blocker. This document
therefore optimises for *not spending* and *not burning*, not for acquisition.

---

## 2. Roles, not rankings

There is no best dataset. There are nine jobs (`arena_role_definitions` in the registry,
mapping onto GOAL.md §3's `(Σ, P, R, τ, π, C, D, U, V, B)`), and each source can do some of
them and not others. Asking "which corpus is best" is the same category error as asking which
of Σ and D is more important.

**The hard constraint** is `arena/provenance.py`: `ORACLE_GRADE_TIERS` admits only
`A_NATIVE_VERIFIED` and `B_INDEPENDENTLY_REVERIFIED` to ground an oracle. Everything at Tier C
or D may supply D (tasks) and future training material; it may never supply Σ or V.

| Source | Σ | D | U | verified trajectories | NL alignment | operation discovery | development | evaluation OOD | future SFT/RL | Default split |
|---|---|---|---|---|---|---|---|---|---|---|
| mathlib4 (built locally) | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✗ FW-1 | — | HISTORICALLY_EXPOSED |
| LeanDojo Benchmark 4 (on disk) | — | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✗ FW-1 | ✅ | HISTORICALLY_EXPOSED |
| HML_V3 lean_runtime_v2 (1,150) | ✅ | ✅ | — | ✅ | — | ✅ | ✅ | ✗ | — | DEVELOPMENT (232 sealed) |
| Metamath `set.mm` | ✅ | — | ✅ | ✅ | — | ✅ | ✅ | ⚠ formal-system axis only | — | DEVELOPMENT |
| Lean Workbook (`wkbk_1009`) | ✗ FW-6 | ✅ | — | ✅ | ✗ FW-6 | ✅ | ✅ | ✗ | ✅ | DEVELOPMENT |
| ProofNetVerif | ✗ | ✅ | — | — | ✅ | — | ✅ | ⚠ | ✗ never-train | DEVELOPMENT |
| miniCTX-v2 (non-mathlib) | — | ✅ | — | — | — | ✅ | ✗ | ✅ *hypothesis, FW-5* | ✗ never-train | RESERVED_EVAL |
| PutnamBench (`lean4/`) | ✅ | ✅ | — | — | ✗ MAA | — | ✗ | ✅ | ✗ never-train | RESERVED_EVAL |
| PRM800K | ✗ | ✅ | — | ⚠ step labels only | ✅ | ✅ *negative examples* | ✗ | ✗ | ✗ never-train | HISTORICALLY_EXPOSED |
| GSM8K / GSM1K | ✗ | ⚠ | — | — | — | ✗ | ⚠ | GSM1K only | ✗ never-train | ASSURANCE_ONLY / RESERVED_EVAL |
| miniF2F (Lean 4) | ✗ | — | — | — | ✗ broken | — | ✅ smoke test | ✗ | ✗ never-train | ASSURANCE_ONLY |
| NuminaMath / OpenWebMath / AMPS | ✗ | ✅ | — | — | ⚠ | ✗ | ✗ | ✗ | ⚠ | TRAINING_CANDIDATE (not taken) |

Four role assignments are load-bearing and worth stating in words:

1. **Only local Lean can supply Σ.** Not because it is better data, but because Σ requires
   *executable verification of states*, and the only executable verifier this project owns is
   the built mathlib at `29dcec07`. Every NL-to-formal source is capped at Tier C by firewall
   FW-6 even when its Lean side type-checks: verifying a mistranslated statement is not
   semantic equivalence.
2. **The premise corpus is U, not D.** `corpus.jsonl` — 180,973 declarations across 5,674
   files, each with `full_name`, source code, position and kind — is the candidate library the
   Solver draws on. It is the thing that makes premise selection a *real* decision with *real*
   distractors, rather than a synthetic probe with invented wrong answers.
3. **PRM800K's role is to name an absence.** It cannot supply Σ, V, or trajectories. Its
   value, exactly as HML_V3's own registry records, is that its five discovery dimensions
   (progress, valid-but-useless, dead end, alternative branch, attempt outcome) are things the
   formal corpus *structurally cannot express*: a Lean trace records only steps that were kept,
   so it contains no negative examples at all. 262,146 `-1` labels and 106,024 `0` labels are
   the only large source of negative reasoning steps on disk. That is a statement about what
   is missing, not a licence to train on it.
4. **miniCTX-v2's role is fragility.** It is the only asset in the estate whose entire value is
   destroyed by one careless preview. It is assigned `evaluation_OOD` and nothing else.

---

## 3. Use what is already local first

### How much of the plan needs zero download

**Of the 27 registry sources, 7 are already on disk** in whole or in part: LeanDojo Benchmark 4
(full), mathlib4 (built tree), miniF2F (DeepMind Lean 4 port at `f0a20e1`), PRM800K (two
942 MB copies), GSM8K (full clone), Hendrycks MATH (train parquet, 12,500 rows), AMPS (Khan
half, 103,059 rows). An eighth, ProofNet, is present as a *different* artifact — the community
Lean 4 port `kripner/proofnet @ 5da820b` — which is not ProofNet# and not ProofNetVerif.

**Five further public Lean/math sources the registry does not even list are local**, at
`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/hf_sources/` (2.7 GB, **[checked
here]** real parquet payloads, not LFS pointers): `STP_Lean_0320` (3,262,558 rows, MIT),
`Pythagoras_SFT` (126,113), `NuminaMath-LEAN` (104,155, Apache-2.0), `Herald_proofs` (44,553,
Apache-2.0), `state_tactic_pairs` (56,407, Apache-2.0). All five are registered with
`train_allowed: false` and unresolved caveats — `state_tactic_pairs` in particular has *no
after-state* and its retrieved-lemma block leaks an answer lemma in ~35 % of audited
lemma-citing rows. **Decision: none of the five enters the pilot.** They are recorded here so
that no future session re-downloads them, and so that the 35 % leak is not rediscovered the
expensive way.

### The four task families that cost nothing

From `local_formal_inventory.json`, of the seven candidate task families, **four are
constructible with zero download**:

| Rank | Family | Scale available locally | New bytes |
|---|---|---|---|
| 1 | **Premise / theorem selection** | ~163,300 premise-citing transitions across the random split (measured 5,517/8,766 = 62.9 % on val+test); 6,624 distinct premise names in val+test alone; four real distractor sources including the hard one (premises cited at *other* steps of the *same* theorem) | 0 |
| 2 | **Legal vs illegal transformation** | 616 structured Expr pairs, 461 with a changed target, 255 of those with a cited premise; 259,580 text pairs; and the multiset-preserving corruption operator `relabel()` **already exists** in `arena/environments/formal_structural.py` | 0 |
| 3 | **Rewrite-direction selection** | 1,658 `rw` steps exact in val+test, 612 (36.9 %) reverse — a non-degenerate binary; ~49,100 `rw` steps estimated across the full split | 0 |
| 4 | **Effect classification (reduced)** | 1,000 rows balanced across 8 effect classes in `lean_pipeline_v1`; ~105,100 goal-closing steps in LeanDojo for the binary version | 0 |

The registry's own rank-1 justification — that LeanDojo transitions are replayable against the
local kernel and therefore rise from Tier B to locally re-verified Tier A — holds, and needs no
network. What it does *not* buy is a free upgrade: historical fresh-replay yield was
**32/100**, not the "~44 %" the project documentation claims (44 was the count of *supported*
attempts: 32 PASS + 11 STATE_MISMATCH + 1 TACTIC_FAIL). Budget replay at 32 %.

### Do not rebuild the firewall registry

`HML_V3/data/registry/datasets.yaml` (schema `hml-v3-dataset-registry-1.1.0`, 27 datasets)
**already encodes** `trust_tier` (A–E), `train_allowed`, `evaluation_only`,
`contamination_notes`, `sha256`, `source_commit`, `license`, `local_path`,
`verification_status`, `evidence_role` and `not_lean_truth` per dataset, and
`tests/test_registry_and_manifests.py` enforces the rules mechanically. **Decision: extend it,
do not fork it.** Arena's corpus registry is a schema-compatible superset that imports those
rows verbatim, with the tier mapping:

```
datasets.yaml A → TrustTier.A_NATIVE_VERIFIED
              B → TrustTier.B_INDEPENDENTLY_REVERIFIED
              C → TrustTier.C_CANDIDATE_SEMANTICS
              D → TrustTier.D_ANNOTATION
              E → TrustTier.D_ANNOTATION   (internal derived artifacts, evidence_role UNASSIGNED)
```

Building a second, parallel trust scheme would create exactly one guaranteed outcome: two
registries that disagree, and no way to tell which one the firewall enforced.

---

## 4. The contamination firewall

### The eight split categories

Reproduced from the registry because they are the operative vocabulary, with the
one-directional rule made explicit:

| Category | May be | Loses forever |
|---|---|---|
| **DEVELOPMENT** | read, inspected, plotted, tuned against | promotion to OOD or RESERVED_EVAL — *reading is what burns it* |
| **TRAINING_CANDIDATE** | SFT / RL / curriculum, licence permitting | use as evaluation or OOD once actually trained on |
| **SCOUT** | a bounded structural probe under a declared item cap | accuracy measurement; the slice is burned, the remainder keeps its own category |
| **PROMOTION** | one preregistered scoring pass | iteration, repeated scoring, post-hoc filtering |
| **OOD** | one generalisation check at a preregistered point | any prior reading, any instrument tuning |
| **ASSURANCE_ONLY** | smoke tests, round-trips, verifier plumbing | contributing any reported number |
| **HISTORICALLY_EXPOSED** | development, training, assurance | OOD, PROMOTION, RESERVED_EVAL — permanently |
| **RESERVED_EVAL** | *nothing* until a preregistered unsealing condition fires | — unsealing is a one-way door and must be logged in `docs/PROJECT_LEDGER.md` |

**Sources move down the ladder and never back up.** No source is *born* PROMOTION or OOD;
those are derived pools carved out under a preregistered split. Assigning a whole corpus to
OOD wholesale begs the question OOD exists to answer.

### The transitivity rule (FW-1) and why it costs so much

Exposure is transitive through derivation. mathlib4 goal states were read during Fitness V5
instrument design — 461 eligible states filtered to 104 across 95 files, via donor
`MoheetBrain/HML_V3 @ 95e8a26`. Therefore mathlib4 is HISTORICALLY_EXPOSED, **and so is
everything derived from it**: LeanDojo Benchmark 4, miniCTX's `mathlib` config, FormL4, and any
mathlib premise-selection extraction. None of them can ever be clean OOD. This is not a
recoverable situation — there is no procedure that un-reads a goal state.

Two further rules that are routinely conflated and must not be:

- **FW-2, naming ≠ reading.** `docs/CANONICAL_VNEXT_GAP_REPORT.md` names miniF2F, ProofNet,
  FormL4, Lean Workbook, MATH, AMPS, NuminaMath, LeanDojo and the Goedel/Nemotron datasets, but
  states that no corpus was downloaded and its claims are recalled rather than verified. Those
  sources are **design-clean**. They are still pretraining-dirty. Different axis, different
  remedy.
- **FW-3, two axes.** Design contamination is fixed only by never having looked. Pretraining
  contamination is not fixed by holding data out at all — it is only *bounded*, by temporal
  cutoff, novel provenance, or perturbation. mathlib is filthy on both. miniF2F is clean on one
  and filthy on the other.

And **FW-4**: split at the theorem group, never the item. Proof-state corpora emit many rows
per theorem; item-level random splitting leaks the same theorem across pools and silently
inflates every effect. LeanDojo's own splits are already theorem-level (118,517 / 2,000 / 2,000
theorems), and the group-aware splitter in `hml-reasoning-corpus @ claude/max-ev-representation-experiment-v1`
should be reused rather than rewritten.

### SEAL NOW — concrete paths

These are unsealed at this moment and every one of them degrades on first read.

| # | Path / target | Size | Why now |
|---|---|---|---|
| **S1** | `…/leandojo_raw/leandojo_benchmark_4/novel_premises/val.json` | 10,314,569 B | Designated **PROMOTION** pool. **[checked here]** the corpus audit read `random/val` + `random/test` (4,000 theorems, 8,766 transitions) but reports only *byte sizes* for `novel_premises/*` — so its contents are still unread. This is the single most urgent seal in the estate. |
| **S2** | `…/leandojo_raw/leandojo_benchmark_4/novel_premises/test.json` | 11,450,088 B | Same, as RESERVED_EVAL. Its guarantee — every val/test proof uses at least one premise never used in any training proof — is the cleanest defence against solving premise selection by recall, and it is worth nothing once read. |
| **S3** | `l3lab/miniCTX-v2` → `minictx-test/` | not on disk | Seal **by non-acquisition**. The fetch in §8 must carry `--include "minictx-valid/*"`. Do not list, preview or summarise the test split. |
| **S4** | ProofNetVerif `test` split (1,452 items) | within 406,549 B | Sealed on arrival, before any inspection, because the whole dataset arrives in one download. |
| **S5** | `HML_V3/data/micromath_lab_v2/micro_hidden_v2.part-*.jsonl.gz` and `micro_shadow_v2.part-*.jsonl.gz` | 175 + 135 items | **[checked here]** present on disk; the dataset card marks both "Read so far: no". These are genuine unread holdouts — rare, and cheap to preserve. |
| **S6** | `HML_V3/data/corpus/sealed_final_v2.part-000.jsonl.gz` | 232 transitions / 126 mathlib source files | Already sealed by `SEALED_V2_MANIFEST.json`, and the gap-verification audit respected it (it read only `corpus_metadata.source_file` from the sealed shard). Keep it that way; policy is "read once, after convergence, on the reported finalists only". |
| **S7** | `/Users/moheet/Documents/ChatGPT/prm800k/prm800k/math_splits/test.jsonl` | **[checked here]** exactly 500 lines | This file *is* MATH-500. Sealing it does not make it a clean eval for anyone — it is public and already leaked — but it must be sealed against training and against ever being *reported* as held-out. |

**Correction to the registry's own pilot.** The registry proposes extracting
`novel_premises/val.json` for pilot adapter work. That would burn the PROMOTION pool for
debugging. Development should use `random/train.json` (250,814 transitions — nothing like a
shortage), and S1/S2 stay sealed.

### The never-train list

The registry's 12: DeepSeek-ProverBench, GSM1K, GSM8K, Hendrycks MATH, PRM800K,
ProofNet (original), ProofNet# (ProofNetSharp), ProofNet-Verified, ProofNetVerif, PutnamBench,
miniCTX-v2, miniF2F (Lean 4 port).

Five additions, all justified by local evidence rather than by category:

13. **`prm800k/math_splits/test.jsonl` named explicitly.** "PRM800K" does not obviously cover
    OpenAI's MATH re-split shipped alongside it, and that file is the one that matters.
14. **LeanDojo `novel_premises/{val,test}.json`** — never-train because they are the designated
    PROMOTION and RESERVED_EVAL pools (S1, S2).
15. **HML_V3 internal seals** — `sealed_final_v2` (232), `micro_shadow_v2` (135),
    `micro_hidden_v2` (175).
16. **`hmlt-reasoning-corpus/data/gold_10`** (10 problems, 23 hand-authored actions).
    **[checked here]** `G01.json`…`G10.json` present. This is the *only* asset in the entire
    estate with contamination NONE, and at 23 actions it is far too small to be an evaluation
    set. Its correct role is a schema-conformance and expressiveness fixture. Training on it
    would destroy the one clean thing on disk to gain 23 rows.
17. **`state_tactic_pairs`** until the ~35 % retrieved-lemma answer leak is stripped and
    verified stripped — not for contamination reasons but because it would teach the leak.

---

## 5. The OOD problem, stated honestly

### What this project can claim today

**Nothing.** Not "a weak OOD result" — nothing. Three independent reasons, any one of which is
sufficient:

1. **There is no effect to generalise.** Fitness V5 ran with a repaired instrument (0 malformed
   rows in 432, against 89 of 348 in V4) and 0 of 3 mechanisms qualified. OOD is a question
   about the *scope* of an effect; there is no effect.
2. **No OOD pool has been materialised.** PROMOTION and OOD are derived pools; V4's frozen
   manifest holds zero SCOUT probes, so the information-parity control is implemented and
   unit-tested but **was never exercised on real probes**.
3. **Every candidate is disqualified or unproven.** Every mathlib-derived source is
   HISTORICALLY_EXPOSED under FW-1. The one non-mathlib candidate, miniCTX-v2, rests on a
   temporal holdout (theorems committed after 2024-11-28) whose validity for *this* Solver is
   a hypothesis, because **the training cutoff of `gemma4:12b` is UNRECORDED in this
   repository** (firewall FW-5). A temporal holdout against an unknown cutoff is not a holdout;
   it is a hope.

### What would have to be recorded to make a real one

Five things, in order of cost:

1. **Pin the Solver's cutoff.** Record `gemma4:12b`'s training-data cutoff, sourced from a
   citable publisher statement, in `docs/PROJECT_STATUS.md` alongside the existing model digest
   `4eb23ef1…`. This is a one-line fact that currently invalidates every temporal OOD claim the
   project could make. It is the cheapest high-value item in this entire document.
2. **Name the shift axis before looking.** "Different Lean project", "later commit date",
   "different formal system" — stated, not assumed, and recorded in the ledger.
3. **Commit the seal cryptographically.** Hash the sealed pool and record the hash in
   `docs/PROJECT_LEDGER.md` *before* anything is read. A seal that is only a promise is not
   evidence to an adversarial reader.
4. **Split at the theorem group** (FW-4), reusing the existing group-aware splitter.
5. **Run the memorisation control.** This one needs no OOD set at all and is available today:
   the three-arm obfuscation design — REAL names / CONSISTENT-BIJECTION names /
   SHUFFLED-INCONSISTENT names — over the structured corpus. `transcribe()` keeps each symbol's
   name in `CanonicalExpression.value` with tree shape held separately in `.args`, so a salted
   bijection over the 2,240 distinct mathlib constant names rewrites `value` fields only: tree
   shape, node count, depth, arity, binder roles, de Bruijn indices and the token multiset are
   all invariant, and every structural answer is preserved by construction. `relabel()` already
   implements exactly this discipline for local references.

### Two things that must not be conflated

- **Temporal holdout bounds pretraining contamination only.** Even with the cutoff pinned, it
  does nothing about design contamination. Two axes, two remedies (FW-3).
- **A cheaper OOD axis exists and does not depend on any cutoff.** The *formal system* axis.
  Metamath `set.mm` is not mathlib-derived, so FW-1 does not touch it; its text is public and
  therefore pretraining-visible, but the shift is auditable and stated (substitution + modus
  ponens versus Lean tactics) rather than assumed from a date. This is the strongest OOD claim
  actually available to the project — and it is still contingent on a Lean-side effect existing
  to replicate.

**Where the evidence does not support a decision:** whether miniCTX-v2 is genuinely OOD for
`gemma4:12b` is *insufficient evidence*. The measurement that would decide it is item (1)
above — pin the cutoff — plus a memorisation probe on the six non-mathlib configs. Until then
miniCTX-v2 stays RESERVED_EVAL and unread, which costs nothing and preserves the option.

---

## 6. Licence position

**The rule.** Where a licence is UNVERIFIED, the source is **unusable** — not "probably fine",
not "MIT per the paper". A licence inferred from a paper, a badge, or a sibling repository is
not a licence of record.

| Source | What we may do | What we may not do | Safe substitute |
|---|---|---|---|
| **Hendrycks MATH** | Nothing new. The local train parquet (12,500 rows) stays read-only where it is, registered `license: UNKNOWN_IN_LOCAL_ARTIFACT`, `train_allowed: false`. | Train, redistribute, copy into Arena, or publish derivatives. An accepted AoPS DMCA (2025-01-02) claims >10,000/12,500 problems and *all* solutions, requests derivative removal, and disabled the canonical HF copy. A nominal MIT tag does not settle a contested *right to grant*. | For informal task diversity: none needed — the project does not need informal tasks to measure R. |
| **PRM800K** | Cite its five discovery dimensions as evidence of what the formal corpus lacks. | Train, redistribute, or hold out. It inherits the AoPS claim *and* has leaked 4,500/5,000 MATH test problems into the public pool. Two local 942 MB copies exist; that duplication is a redistribution surface, not an asset. | For negative/abandoned steps: nothing on disk substitutes. Record the gap; do not fill it from PRM800K. |
| **NaturalProofs** | Read the ProofWiki portion (CC BY-SA 4.0) for structural understanding. | Treat as MIT — MIT covers *code only*. The data is CC BY-SA 4.0 (ProofWiki) + GFDL v1.2 (Stacks) + **CC BY-NC-SA 4.0 (Trench, non-commercial)**. Any mixed derivative inherits copyleft *and* the NC term permanently. | Nothing — it has no verifier at all, so it could never ground Σ regardless. |
| **Levin, DMOI 4th ed.** | Use the **3rd edition**, which is genuinely CC BY-SA 4.0. | Use the 4th edition unless a permanent non-commercial restriction is acceptable forever. Its colophon and PreTeXt source both say CC BY-NC-SA 4.0; **the repository LICENSE file is stale** on both branches and still says CC BY-SA 4.0. | 3rd edition. |
| **FormL4** | Nothing. | Everything. The repo has **no LICENSE file** and GitHub's licence field is null; "CC BY 4.0" is README prose. It is also mathlib in a costume (FW-1) with a model-written English side (FW-6). | — |
| **GSM1K** | Nothing until the licence exists. | Fetch, even to seal. The released repo has no licence tag and an empty README; MIT is a *paper promise* (arXiv:2405.00332). **This revises the registry's pilot**, which proposed fetching GSM1K unopened — a fetch is still a redistribution-relevant act, and the point of the never-train list is not to acquire things we cannot lawfully hold. | For a contamination-gap control: the obfuscation arm (§5.5), which is free and does not depend on anyone's licence. |
| **PutnamBench** | Sparse-checkout `lean4/` only (Apache-2.0), when a qualified instrument exists. | Pull or redistribute `informal/`. The informal statements are used *by permission of the MAA*, and that permission does not transfer. | — |
| **Metamath `set.mm`** | Everything. CC0 1.0 (LICENSE file verified; the site waives all rights in the `.mm` databases). GitHub's detector reports NOASSERTION — ignore it. | Include `peano.mm` (GPL, Robert Solovay) in a pure-CC0 corpus, or rely on the GPL v2+ `metamath-exe` tooling inside a CC0 pipeline without segregating it. | — |
| **LeanDojo Benchmark 4** | Use it; attribute it. | Confuse the DOIs. **CC-BY-2.0** under the old concept DOI `10.5281/zenodo.8040109` (which is what v10 / `12740403` — the local copy — falls under) and **CC-BY-4.0** under the 2025 concept DOI `10.5281/zenodo.15372179`. Record which. **[checked here]** the local `licenses/` directory preserves the component licences for mathlib4, batteries, aesop, Qq, ProofWidgets4, import-graph, lean4, lean4-cli — that structure must be preserved on any re-export. | Never use the HF mirror: it drops `annotated_tactic` and the premise corpus. |

**Unusable-until-verified** (the registry's `licence_verified: false` set): DeepSeek-Prover-V1
(dataset), DeepSeek-ProverBench, Goedel-LM `Lean-workbook-proofs`, AMPS, GSM1K, FormL4,
Hefferon *Linear Algebra* (primary sources contradict: repo LICENSE and UVM mirror say
CC BY-SA 2.5, `hefferon.net/source.html` says CC BY-SA 3.0 US; GFDL version stated nowhere),
Magnushammer / MagnusData (blanket Apache-2.0 claim sits over per-entry LGPL AFP entries),
PISA extracted corpus, `wellecks/naturalproofs-gen`. None of these may be fetched, held or
used until a licence of record is read from the artifact itself.

---

## 7. Provenance requirements

Every ingested item carries all ten fields. An item missing any of them is not ingested — not
"ingested with a TODO".

| Field | Value shape | Note |
|---|---|---|
| `source` | canonical upstream, never a mirror | mirrors alter content: the LeanDojo HF mirror drops `annotated_tactic` and the premise corpus |
| `version_or_commit` | Zenodo DOI + version, git SHA, or HF revision | rolling databases (`set.mm`, ~17,856 commits, no releases) are unreproducible without a pinned SHA |
| `licence` | licence of record, read from the artifact | plus `licence_verified: true/false`; false blocks ingestion |
| `source_id` | the upstream's own item identifier | preserved verbatim, never renumbered |
| `content_hash` | SHA-256 of the raw bytes | `datasets.yaml` already carries `sha256` for most rows |
| `import_timestamp` | UTC | **new field** — `datasets.yaml` has only a registry-level `generated_at` |
| `extractor_version` | version of the code that produced the normalised record | **new field** — without it, a schema change silently rewrites history |
| `trust_tier` | `arena/provenance.py` `TrustTier`, via the A–E mapping in §3 | only A and B may ground an oracle |
| `contamination_status` | one of the eight split categories, **plus** both axes separately (design / pretraining) per FW-3 | a single flag cannot express "design-clean, pretraining-filthy" |
| `intended_split` | the split category, declared **before** the first read | **new field** — declaring it after reading is not a declaration |

Three fields (`import_timestamp`, `extractor_version`, `intended_split`) are additions to
`hml-v3-dataset-registry-1.1.0`; the other seven already exist. That is the whole delta.

**Losslessness rule.** Never strip original content. Normalised fields are stored *alongside*
the original, never in place of it. The pressure test is unambiguous on why: over 368 real
proof states, **0 were losslessly representable** in the current canonical schema — 292
LOSSY_STRUCTURAL and 76 UNMAPPABLE, with 34,781 symbols carrying universe arguments, 1,968
sort nodes with non-trivial levels, 1,375 metavariables, and 4,288 of 5,071 local-context
entries carrying compound types. Any extractor that normalises first and stores second throws
away information the schema cannot yet name. Store the raw record; derive views.

A worked example of why this is not theoretical: the HML_V3 V2 corpus stores **no tactic name**
— `corpus_metadata.tactic_family` is null in all 1,150 rows. The tactic text was recoverable
only because `action.source_location.start.raw..end.raw` byte offsets into the pinned mathlib
source were preserved. Lossless storage is what made 88 distinct tactic heads recoverable
years later, offline, with zero re-elaboration.

---

## 8. The small pilot (preregistered design — NOT executed)

**Ordering rule:** the cheapest highest-information slice runs first, and each wave is gated on
the previous wave producing a measurable band. A wave that does not produce a band terminates
the pilot; it does not trigger "try a bigger dataset".

### Wave 0 — zero download

No fetch. Build the premise-selection, rewrite-direction and legal/illegal-transformation
adapters against `…/leandojo_raw/leandojo_benchmark_4/random/train.json` (250,814 transitions)
plus `corpus.jsonl` (180,973 declarations) and the local built mathlib. Measure the string-overlap
and frequency-prior baselines **first** — before any Solver call — and match distractors on both.
Cost: **0 bytes.**

> Rationale for baselines-first: on the real depth probes the dumb rule
> `more_frequent_in_state` already scores 0.798 on the 104 length-fair states and
> `first_mentioned_in_state` scores 0.913 (1.000 on the shallow stratum) — worse than the 0.72
> and 0.833 published in `docs/FITNESS_V5_SPEC.md`. Assume a shortcut exists until it is
> measured absent.

### Wave 1 — 406,549 bytes

| Field | Value |
|---|---|
| Source | ProofNetVerif |
| Dataset id | `PAug/ProofNetVerif` |
| Slice | entire dataset (valid 2,300 + test 1,452); **use `valid` only, seal `test` unopened on arrival** |
| Command | `hf download PAug/ProofNetVerif --repo-type dataset --local-dir data/pilot/proofnetverif` |
| Bytes | **406,549** |
| Licence | MIT, verified |
| Purpose | Prove the A/B decision adapter against the existing controller C. Binary, clean 0.5 chance baseline, no new machinery. |
| Gate | If no measurable band appears, **stop**. Do not proceed to Wave 2. |

(`huggingface-cli` is the pre-0.34 name; newer `huggingface_hub` uses `hf download` with the
same arguments.)

### Wave 2 — 7,583,220 bytes (conditional on Wave 1)

| Source | Slice | Command | Bytes |
|---|---|---|---|
| miniCTX-v2 | `minictx-valid/` **excluding** `mathlib.jsonl` (carleson, ConNF, FLT, foundation, HepLean, Seymour) | `hf download l3lab/miniCTX-v2 --repo-type dataset --include "minictx-valid/*" --exclude "minictx-valid/mathlib.jsonl" --local-dir data/pilot/minictx_v2_valid` | 2,983,046 |
| Lean Workbook | `wkbk_1009.parquet` **only** (25,200 tactic-state rows); explicitly *not* `lean_workbook.json` (94.5 MB) | `hf download internlm/Lean-Workbook --repo-type dataset --include "wkbk_1009.parquet" --local-dir data/pilot/lean_workbook` | 4,600,174 |

`minictx-test/` **must not be fetched** (seal S3). Lean Workbook was built at Lean v4.8.0-rc1
against the local v4.10.0-rc1 — budget a version bridge, and note FW-6 caps its NL-formal
alignment at Tier C. Budget truncation-policy work for miniCTX: its contexts span tens of
thousands of tokens and collide directly with the 30,000-rendered-character length-fairness
constraint.

### Wave 3 — 51,367,012 bytes (conditional on a Lean-side effect existing)

| Source | Slice | Command | Bytes |
|---|---|---|---|
| Metamath `set.mm` | `set.mm` only at a pinned commit SHA; **exclude `peano.mm`** (GPL) and all other `.mm` databases | `git clone --filter=blob:none --no-checkout https://github.com/metamath/set.mm data/pilot/setmm && git -C data/pilot/setmm sparse-checkout set --no-cone set.mm LICENSE && git -C data/pilot/setmm checkout develop && git -C data/pilot/setmm rev-parse HEAD` | 51,367,012 |

Purpose: expand a few hundred proofs into Step / Hyp / Ref / Expression tables and check
whether the Arena canonical schema survives a substitution-based state model. Cost is an RPN
decompressor or a shell-out to a verifier. **The `rev-parse HEAD` is not optional** — without a
pinned SHA the corpus is unreproducible.

### Totals

| | Bytes | % of 2 GB ceiling |
|---|---|---|
| Wave 0 | 0 | 0 % |
| Wave 1 | 406,549 | 0.019 % |
| Waves 1+2 | 7,989,769 | 0.372 % |
| **All waves authorised** | **59,356,781** | **2.76 %** |
| (registry's original proposal, for comparison) | 130,117,317 | 6.06 % |

Every slice is a sparse/filtered fetch or a single file. No full-repository clone, no
full-dataset pull. **This pilot is a design. No download is authorised by this document.**

### Explicitly removed from the registry's proposed pilot

| Removed | Bytes saved | Reason |
|---|---|---|
| LeanDojo Benchmark 4 tarball | 68,141,936 | Already on disk, verified byte-for-byte **[checked here]** |
| miniF2F | 225,600 | Already on disk (DeepMind port @ `f0a20e1`) |
| GSM1K | 393,000 | Licence UNVERIFIED — §6's rule forbids fetching, not just using |
| PutnamBench `lean4/` | ~2,000,000 | Deferred: reading burns the only naturally-occurring held-Σ/varied-R comparison, for an instrument that does not yet qualify |
| `novel_premises/val.json` extraction | (local) | Would burn the PROMOTION pool for adapter debugging — use `random/train.json` instead |

---

## 9. What we are deliberately not doing

Each entry has a trigger. A trigger is a *measurement*, not an opinion.

| Not doing | Trigger that would change it |
|---|---|
| **Mass ingestion of any kind** | The block-wise novelty curve (§10) read on **≥2 heterogeneous sources** shows <5 new semantic constructs per 1,000 items across the final third — **and** an instrument has qualified. Both conditions, not either. |
| **AMPS (5M Mathematica problems, 23 GB)** | Someone byte-verifies that the tarball ships the 100 generator scripts (currently **UNVERIFIED** — the paper shows example code but never states they are distributed) **and** an AMPS-specific licence exists. Generator-backing would give *fresh, uncontaminated* items; templates would not. The Khan half (103,059 rows) is already local and already `train_allowed: false`. |
| **NuminaMath (~900k informal rows, 1.7 GB)** | A qualified instrument exists **and** the project has moved to post-R* training (GOAL.md §22). Not before: it has no states, no transitions, and no verifier beyond answer match. Note `NuminaMath-LEAN` (104,155 rows) is already local, and 80.7 % of it lacks formal ground truth. |
| **Downloading a "full mathlib database"** | **Never.** The built tree *is* the database: 4,447/4,447 modules, `Lean4Repl.olean` compiled, every manifest dependency vendored under `.lake/packages`, no download step in the replay driver. |
| **Generating 10K / 100K / 1M new trajectories** | Fresh-replay pass rate measured on a *new* n≥100 sample beats a preregistered threshold (historical: **32/100**), **and** a qualified instrument consumes them. Scale facts to respect: 1,406 file-level jobs produced ~102 GB of raw capture, one file reached 350 MB, and 671 transitions were lost to the 262,144-byte canonical budget. Per-job timing is **NOT FOUND** in the retained logs, so any replay budget must be *measured*, not guessed. |
| **Fine-tuning anything** | An instrument qualifies **and** a representation shows a band that survives the obfuscation control. GOAL.md §3 forbids moving π while measuring R; doing both makes the result uninterpretable by construction. |
| **RL / self-play** | Post-R* only. R* has to be *named* (GOAL.md §16) before there is anything to self-play against. |
| **Renting GPUs** | A logged, measured compute bound on the local machine that blocks a preregistered experiment. No such measurement exists today. |
| **Rebuilding the trust/contamination scheme** | Never. `datasets.yaml` already has it, with mechanical enforcement. Extend by three fields (§7). |
| **Rebuilding the 42-axis representation genome** | Never. HML_V3 decision D-025 records an exhaustive single-axis sweep finding that *no* axis of the 42 removes any relation from the page except `type_explicitness`, and declares the genome "does not transfer". |

---

## 10. Saturation criterion

**The criterion.** Mass ingestion becomes justified only when new semantic constructs per
1,000 items approaches zero **across heterogeneous sources** — sources whose *primitives*
differ, not merely whose content differs. Measured on one source, saturation is close to
tautological: the construct vocabulary is fixed by that source's own type theory.

### Current reading

Measured over 184 records / 368 proof states sampled every 5th eligible record from the
918 non-sealed HML_V3 V2 rows:

| Axis | 1–50 | 51–100 | 101–150 | 151–184 | Total distinct | Verdict |
|---|---|---|---|---|---|---|
| **Semantic constructs** | 54 new (108 / 100) | 1 new (2 / 100) | 0 | 0 | 55 | **Saturated on this source** |
| **Binder × type structures** | 19 new (38.0 / 100) | 5 new (10.0 / 100) | 3 new (6.0 / 100) | 1 new (2.9 / 100) | 28 of a plausible ~64-cell space | **Not saturated even on this source** |

Extrapolated to the criterion's units: the semantic-construct axis reads **0 new per 1,000
items** over the final 84 records. The binder × type axis reads **~29 per 1,000** and is still
climbing.

### Verdict against the criterion: NOT MET, on two independent counts

1. **Heterogeneity fails.** This is one source — the Lean 4.10.0-rc1 elaborator applied to
   mathlib4 and Batteries through one extractor. The registry's own caveat is exact: saturation
   of a node vocabulary fixed by Lean's `Expr` type says nothing about heterogeneous sources.
   **Treat 55 as a lower bound on the universal construct count, not an estimate of it.**
2. **One axis has not saturated at all.** 2.9 new binder × type structures per 100 records at
   record 184, with 28 of ~64 cells observed, is not a curve that has flattened.

Two constructs — `DEFEQ_STEP_TYPE` and `DISTINCT_VARIABLE_CONDITION` — were **never observed**
in 368 Lean states. The second is a Metamath primitive. That is the shape of the problem: a
single-source novelty curve cannot see the constructs its own source lacks.

### The measurement that would decide it

Run the identical block-wise novelty count on a **second source with different primitives**, at
n ≥ 200 records, with the acceptance rule declared before the run. The registry names the
candidates in cost order:

1. **Metamath `set.mm`** proof expansions — the only thing that can test the substitution /
   modus-ponens primitive set at all, and the only one that could observe
   `DISTINCT_VARIABLE_CONDITION`. Cost: 51,367,012 bytes, one CC0 file, no toolchain (Wave 3).
2. The **gold125 trajectory schema** in `hmlt-reasoning-corpus-lean-attestation/schemas/` —
   zero download, but only 769 steps and ANNOTATION_UNVERIFIED.
3. **Arena's own symbolic / numeric domain states** — zero download, fully controlled, but
   generated by the same project whose vocabulary is under test.

Until at least (1) is run, the honest position is: **insufficient evidence for mass ingestion,
and insufficient evidence against it.** The curve looks saturated because we have only looked
through one lens.

---

## Appendix — the asymmetry that shapes every decision above

From `user_reasoning_chain_inventory.json`, stated verbatim in substance because it is the
single most consequential fact about this corpus estate:

> Verification and richness are **anti-correlated**. Everything `VERIFIED_FORMAL` is
> single-operation Lean with no warrants and no negative examples. Everything with a rich
> reasoning-operation annotation is `ANNOTATION_UNVERIFIED` and MATH-contaminated. **No asset
> on disk is both.**

The numbers: the rich schema (per-step operation + warrant + preconditions + obligations with
lifetimes + typed inter-step dependencies + full before/after state) exists for exactly **792
steps** — 769 MATH-derived Gold-125/Gold-25 transitions plus 23 hand-authored Gold-10 actions.
Everything at 10k–300k scale is single-operation: `action.operation == "LEAN_TACTIC"` with
empty preconditions, obligations and all five effect maps, confirmed by direct inspection of
both `vnext_10k/train.jsonl.gz` and `hml_50k_final/canonical/records.jsonl.gz`. Only **32**
transitions anywhere have been freshly replayed in Lean.

Three consequences that no purchase can fix:

- **There is no large corpus of owner-authored reasoning chains.** Only 10 Gold-10 examples
  (23 actions) are marked `provenance.authoring = "hand_authored"`. No exported conversation
  logs exist on this machine; a bounded search returned nothing.
- **Formal corpora are survivorship-biased.** A Lean trace holds only steps that were kept, so
  it contains *no negative examples at all*. Any operation vocabulary learned from it will have
  no vocabulary for failure, backtracking or abandonment. **[registry finding]** the project's
  own PRM800K semantic-discovery pilot found **0/1000 = 0.00 % marginal semantic discovery** —
  so this gap is unlikely to be closed by ingesting more of the same.
- **A tactic name is a weak proxy for what a step does.** Measured over all 259,580 LeanDojo
  steps: `MI(tactic_head; state_effect) / H(tactic_head) = 0.24`. Task families keyed on
  tactic identity are keyed on 24 % of the signal. State-delta-keyed families are strictly
  better grounded — and cost nothing extra.

Buying more data does not change any of this. That is why §1 says: ingest almost nothing.
