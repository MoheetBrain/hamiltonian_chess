# Route B v1 Preregistration — Matched Learning-Curve Instrument

Experiment: `arena-route-b-matched-learning-v1`.
Instrument: `arena-route-b-learning-curve-v1.0.0`.
Modules: `arena/training/route_b_data.py`, `arena/training/verified_eval.py`,
`arena/training/render_dataset.py`, `arena/training/evaluation.py`, and a runner that does
not yet exist (§5.4).

**NO GPU MINUTE MAY BE SPENT UNDER THIS DOCUMENT.** §15 is the authorisation gate. This
file is written and frozen *before* any training call, in the same discipline as
`docs/PHASE6_PREREGISTRATION.md`. Route B becomes the primary route only if Phase 6 returns
`FAILURE_REPLICATES_ACROSS_SOLVERS` — i.e. no installed Solver has a measurable zero-shot
band.

Every number below marked **[measured]** was computed in this session on CPU, from the
repository, with zero model calls. Every number marked **[UNVERIFIED]** is taken from
another document and was not re-derived here.

---

## 1. Question, hypothesis, falsification

**Question.** Holding the canonical mathematics, the base checkpoint, the optimiser, the
task selection, the targets and the evaluation slice fixed, does the *representation* `R` of
the state change how many training examples the model needs to reach a given held-out
verified accuracy?

`GOAL.md` §14: "The principal causal object is the **learning curve**, not merely final
ceiling performance."

**H0_ROUTE_B (the null, stated precisely).** For every budget
`n ∈ {16, 32, 64, 128, 224}`, the five arms have equal expected held-out VERIFIED accuracy.
Formally: the five per-item outcome vectors at each budget are exchangeable under
permutation of the arm label within an item.

**H1_ROUTE_B.** At least one budget has a between-arm spread in held-out VERIFIED accuracy
that a within-item arm-label permutation test rejects at α = 0.05.

**What falsifies H1.** The omnibus permutation test fails to reject *and* the largest
observed between-arm spread at every budget lies inside the practical-equivalence region
±0.125 (§10.5). That combination — and only that combination — licenses
`NO_MEASURABLE_SAMPLE_EFFICIENCY_DIFFERENCE`. A failure to reject with an observed spread
*outside* the region is `ROUTE_B_UNDERPOWERED_INCONCLUSIVE`, not a null.

**What this experiment is not.** It is not a test of which representation is best. Five
arms at n = 128 held-out items cannot rank five surfaces (§10.4). It is a test of whether
the representation matters *at all* to sample efficiency.

---

## 2. Frozen variables

Game R (`GOAL.md` §5) freezes Σ, P, τ, π, C, D, U, V, B and varies only R. The concrete
values:

| Symbol | Frozen value |
|---|---|
| Σ | `arena-canonical-v0.1.0`. Canonical trajectories from `arena.tasks.generators.world_v0` (`WORLD_ID = "arena-world-v0"`) or, under the contingent slice, transcribed Lean 4 goal states from `arena/environments/formal_structural.py`. The slice is fixed by §4 before training and recorded in the manifest hash. |
| P | `project_state_for_observation(state, ObservationKind.NEXT_ACTION)` (`arena/compiler/projection.py:25`), applied identically to every arm before rendering. `assert_no_answer_leakage` (`:47`) **MUST BUILD** — it exists but is not called on this path (§11). |
| **R** | **THE ONLY VARIABLE.** Five Track-E `ModelViewGenome` surfaces (§3). |
| τ | `Qwen/Qwen2.5-7B-Instruct` tokenizer, revision `a09a35458c702b33eeacc393d103063234e8bc28`. One tokenizer for all arms. Never re-fit, never per-arm. |
| π | Base checkpoint `Qwen/Qwen2.5-7B-Instruct` @ `a09a35458c702b33eeacc393d103063234e8bc28`, bf16, reloaded from a cloned `state_dict` before every arm (`gpu_matched_runner.py:144,:172` — keep this behaviour). |
| C | Adaptation: LoRA r=16, α=32, dropout 0.0, `target_modules=["q_proj","k_proj","v_proj","o_proj"]`, AdamW, lr 1e-4, batch 4, no LR schedule, no gradient accumulation, no early stopping. Inference: greedy (`do_sample=False`), `max_new_tokens=192`, one attempt, no retries, no search. |
| D | One task family, fixed by §4. One task kind. No curriculum, no mixing. |
| U | None. No tools, no retrieval, no external libraries at inference. |
| V | `NativeVerifier` (`arena/verifier/native.py:52`) via `arena/training/verified_eval.py`, plus an independent re-derivation of the answer (§8). |
| B | Context length `max_len` fixed by the §4.5 preflight; identical for every arm; `padding_side="left"`; deadline guard per run. Update count = `ceil(n / 4)` at budget `n`, identical for every arm (EXAMPLE_MATCHED) — see §7. |

Anything in this table that changes requires a new instrument version and a new manifest
hash. It is not an edit.

---

## 3. Arms

Five surfaces, by `candidate_id`, with the genome hash `arena.languages.registry`
currently reports **[measured]**:

| Arm | `genome_hash` | Role |
|---|---|---|
| `L0_STRUCTURED_ENGLISH` | `9823d4955c8416811632af0656518e84a9e23bc513cc9ce7a037e33c955c0d2f` | control |
| `L1_CURRENT_HML` | `d888b38a320d50c2c144d779dfb3aa252621e9add8671788d6d885ef4fb0a84e` | control |
| `L2_SEXPR` | `4e77c1921fd1f7d4a3b982596e3905733c654f19361e9e3a1f241a12e8a080c2` | control |
| **`L3_JSON_AST`** | `18e8dd1e64954dfc3531b6486b10d1f86a03a1c6b00cb0224acd9054ccb8b9db` | **preregistered baseline** for every pairwise comparison and the only arm used for the ceiling gate (§4.5) |
| `L5_COMPACT_SYMBOLIC` | `a2990983e8ae6f8316b21766b198d4422b78ee6bfad5a547826fae096fc880e5` | compactness frontier; no privilege |

`L3_JSON_AST` is the baseline because it led the historical sprint on held-out exact match
(0.979 @ 224, 1.000 @ 576) **[measured]**, so a challenger cannot be flattered by a weak
reference. The choice is made here, before any Route B call, and is not revisited.

`L4_TYPED_PREFIX`, `L6_GRAPH_TRIPLES`, `L7_HYBRID_ROLE_LABELLED` exist in
`SEED_LANGUAGES` and are deliberately **not** arms: five arms already exhaust the power
budget (§10.4).

**Adding a future qualified Game-R candidate.** Permitted only as follows, and only this way:

1. the candidate passes `assert_game_r_genome` (Track E only; no Track-C content gene);
2. `ARMS` is extended and a **new** `BudgetManifest` is built — `manifest_hash` changes, so
   the new design cannot be confused with this one;
3. `assert_matched_semantics` (`render_dataset.py:87`) must pass on the six-arm dict:
   identical canonical-ID sequence, identical target-hash sequence, byte-distinct inputs;
4. **all six arms are retrained from base under the new manifest.** Results from the
   five-arm run may never be reused as the comparison set for a sixth arm: training-run
   noise and the manifest identity both differ, and a sixth arm compared against stale
   numbers is an uncontrolled experiment wearing a controlled experiment's table.

---

## 4. Task family and the SATURATION PROBLEM

This is the decision the experiment lives or dies on. The historical slice does not work,
and the reason is worse than "it saturates".

### 4.1 Why `WORLD_V0_NEXT_ACTION` is retired as a Route B endpoint slice

All **[measured]** this session on the 676-task world, seed 0, legacy split:

| Defect | Measurement |
|---|---|
| Ceiling | dev exact 0.979 (L3) / 0.958 (L5) at 224 examples; **1.000 on dev *and* on the fresh slice** at 576 for both finalists. A saturated task cannot express a learning-curve difference. |
| `verified` carries zero information | 1.000 for every arm in all 10 recorded cells, because `gpu_matched_runner.score_prediction:71` defines `verified` as JSON-key presence. `schema_valid` is also 1.000 in all 10 cells. |
| The answer id is a string rewrite of the visible input | the gold `action_id` stem is a literal substring of the rendered observation on **48/48** dev items for **all five arms**. `state:algebra:0000:0000:initial` → `action:algebra:0000:0000:valid`. |
| The target is mostly constant | 4 of 8 target keys take exactly one value across the 48 dev items (`expected_usefulness`, `generated_obligations`, `target_ids`, `warrant`); `operation` is a deterministic function of the domain, and the domain is a literal substring of the input (13 domains → 13 operations, every one a singleton). Only `arguments` is open (38 distinct values over 48), and **15/48** of those appear verbatim in the input. |
| Held-out contamination | the split is disjoint by `trajectory_id`, **not by problem content**. At budget 576, **8/48 dev** and **7/48 fresh** items share a `problem.content_hash` with a training item, and on all 8 the gold `arguments` are byte-identical; one inspected pair had 0.9979 input-string similarity. At budget 224: 5/48 dev, 3/48 fresh. At budget 16: 2/48 dev. |
| Answer-level leakage | 21/48 dev answers already appear as a training answer at budget 224; 26/48 at 576. |
| `verified` cannot differ from `exact` | every state in Arena World v0 offers exactly one legal action, which is the gold target, so `VERIFIED_NOT_EXACT` is structurally unreachable (documented independently in `arena/training/verified_eval.py`). |
| Non-GOLD training data | the first 576 training examples are **424 GOLD / 104 SILVER / 48 REJECT**. The historical Stage B and Stage C therefore trained on 152 non-GOLD trajectories, 48 of them *refuted*. Budgets 16–224 are 100% GOLD; the first non-GOLD sits at train position **416**. |

`WORLD_V0_NEXT_ACTION` as run in the Tier-2 sprint is therefore permanently ineligible as a
Route B endpoint slice. It remains valid as the reproduction target for
`artifacts/experiments/tier2_sprint/`.

### 4.2 The generator's hard structural limit

The obvious repair — "generate a bigger world" — does not work, and the arithmetic is
decisive **[measured]**:

- de-duplicating by `problem.content_hash` and keeping GOLD only yields 445 tasks at
  world 676, 838 at world 1352, 1511 at world 2600;
- but the per-domain distinct-GOLD counts saturate: at world **2600**, `sets` = 17 and
  `statistics` = 17, while nine other domains reach 154;
- so a **domain-balanced, content-disjoint, GOLD-only** world_v0 pool is capped at
  13 × 17 = **221 items at any world size**, below the 416 this design needs (§5.1).

The only way to a usable world_v0 pool is to drop the two thin domains: 11 domains × 92
(the next smallest, `partial_operations`) = **1012 items**, which clears 416 with margin.

### 4.3 The candidate slices, ranked

| Rank | Slice | Pool | Headroom evidence | Adapter work |
|---|---|---|---|---|
| **1** | **`WORLD_V0_DEIDENTIFIED_NEXT_ACTION`** — world 2600, content-deduplicated, GOLD-only, 11 domains (`sets` and `statistics` excluded), identifiers rewritten to content-free tokens, scored on `operation` + `arguments` only | **1012 [measured]** | unknown; the copy shortcut and the four constant fields are removed, so the historical 0.979 is not a prediction for it | CPU-only: an id-scrubbing pass over `CanonicalState` before rendering, a content-hash de-duplicator and a domain filter in `route_b_data.build_budget_manifest`, and a scored-field restriction in `verified_eval`. No new renderer. |
| 2 | `FORMAL_DEEPEST_IDENTIFIER` — `build_state(target, identifiers, goal_op)` from `arena/environments/formal_structural.py:339` rendered by each arm; target = the uniquely deepest identifier; truth re-derived by `identifier_depths` (`:138`) | 461 eligible, **104** under V5's 30,000-char length-fairness cap **[UNVERIFIED — from `docs/FITNESS_V5_SPEC.md` §4; `load_formal_states` was not run here]** | strongest available: real Lean states, `min_lead ≥ 1` guarantees a well-posed unique answer, and V5 measured 0.542–0.667 for `formal_expression_depth` on the two-way version | a `render_formal_example` mirroring `render_next_action_example` (`render_dataset.py:44`), a target builder, and a slice-specific verifier. Depends on an external donor repo at an absolute path (`DONOR_ROOT`). |
| 3 | `WORLD_V0_NEXT_ACTION` (historical) | — | **fails**, §4.1 | none | 
| 4 | `WORLD_V0_INVALID_ACTION` | — | rejected: two-alternative forced choice, chance 0.5, ceiling reached within one budget step | — |
| 5 | `WORLD_V0_NEXT_STATE` | — | rejected: the target is a full successor state, whose serialisation is representation-dependent, so `assert_matched_semantics`' identical-target-hash requirement cannot hold. Structurally incompatible with matched design. | — |

**DECISION (frozen).** Slice 1 is attempted first. Slice 2 is the designated replacement and
is attempted **only** if slice 1 fails the §4.5 headroom gate. The order is fixed here, so
"which slice was used" is never a choice made after seeing a between-arm contrast. If both
fail, the run aborts (§14).

### 4.4 Content-disjointness requirement (new, mandatory)

`PROBLEM_CONTENT_DISJOINT`: no `problem.content_hash` may appear in more than one of
{train pool, dev, fresh}, and none may appear twice within a slice. Checked at manifest
build, fails closed. **MUST BUILD** — `route_b_data.build_budget_manifest:413` currently
de-duplicates nothing.

`HELD_OUT_QUALITY`: dev and fresh must be **GOLD-only**, not just train.
`build_budget_manifest` applies `filter_indices_by_quality` to the train pool only; under
`SplitMode.SEEDED` this leaves **12/48 non-GOLD dev items at seed 0 and 12/48 at seed 1**
**[measured]**, and a REJECT held-out item scores the model against a *refuted* action.
**MUST BUILD.**

### 4.5 The headroom gate — `ROUTE_B_HEADROOM_PREFLIGHT`

Run **before** the main experiment, on the candidate slice, in this order. Every threshold
is a number and every failure has a name.

| # | Gate | Threshold | On failure |
|---|---|---|---|
| H1 | **Pool** | the slice yields ≥ `224 + 128 + 64 = 416` items after content de-duplication, quality filtering and domain balancing | `ROUTE_B_POOL_INSUFFICIENT` |
| H2 | **Length fairness** | across the five arms, `max(mean rendered input chars) / min(...) ≤ 3.00` on the train pool | `ROUTE_B_LENGTH_UNFAIR` |
| H3 | **Truncation unreachable** | for every arm and every item in train ∪ dev ∪ fresh, `len(tokenize(prompt)) + len(tokenize(target)) + 8 ≤ max_len`, counted with the frozen τ, on CPU, at manifest freeze | `ROUTE_B_CONTEXT_TRUNCATION` |
| H4 | **Floor** (zero-shot) | the *untrained* base checkpoint scores VERIFIED ≤ 0.20 on the dev slice **for every arm** | `ROUTE_B_SLICE_VOID_NO_HEADROOM` |
| H5 | **Ceiling** | the **baseline arm `L3_JSON_AST` only**, trained at the top budget 224, scores VERIFIED ≤ 0.90 on dev | `ROUTE_B_SLICE_VOID_NO_HEADROOM` |
| H6 | **Dynamic range** | the same reference arm improves by ≥ 0.30 absolute from H4 to H5 | `ROUTE_B_SLICE_VOID_NOT_LEARNABLE` |

H5 and H6 use **one designated arm**, never the best arm and never a between-arm contrast,
so passing the gate cannot select for the effect being tested. H4 uses all five arms
because a slice the base model already solves has no learning to measure, in any arm.

Applied retrospectively to the historical slice, H5 rejects it: 0.979 > 0.90 **[measured]**.
The gate is not decorative.

H1–H3 cost zero GPU. H4–H6 are the only GPU spend permitted before the main run and are
capped at 30 minutes per slice (§15).

---

## 5. Budgets, nesting, and the manifest

### 5.1 The ladder

`BUDGETS = (16, 32, 64, 128, 224)`, `DEV_SIZE = 128`, `FRESH_SIZE = 64`. Total pool
requirement 416.

`DEV_SIZE` is 128, not the historical 48, because 48 is unusable: the omnibus test has
power 0.303 at a true spread of 0.20 at n = 48 versus 0.72 at n = 128 (§10.4). The
evaluation slice size is a design parameter, and the historical value was inherited, not
chosen.

**Nesting.** D16 ⊂ D32 ⊂ D64 ⊂ D128 ⊂ D224 as *ordered prefixes*, not merely as sets.
This already holds for the existing splitters — the split fills dev and fresh before train,
so growing `train_n` only appends **[measured: verified for 16⊂32⊂64⊂128⊂224⊂576]** — and
is checked anyway at manifest build by `route_b_data.assert_nested_ids:107`, which requires
both the prefix and the subset property and fails closed.

### 5.2 The manifest

Frozen and hashed **before any GPU minute**. `route_b_data.BudgetManifest:284` already
carries the right shape; the fields that must be present and hashed:

- `world_size`, `generator_seed`, `split_mode`, `split_seed`, `min_quality`;
- `budgets`, `dev_size`, `fresh_size`, `available_pool`;
- per arm: `candidate_id` and `genome_hash`;
- per budget: the ordered `canonical_id` list, the ordered `example_id` list, and a
  **per-arm `dataset_hash`** computed by `route_b_data.dataset_hash:96`, which is
  byte-for-byte the scheme `render_dataset.write_jsonl:131` returns for the file it writes;
- the dev and fresh slices, hashed the same way;
- `manifest_hash` over `identity_payload()` (which excludes `arena_git_sha` — the dataset
  hashes already commit to the bytes);
- `token_proxy_units: "characters_not_tokens"`.

`verify_manifest:538` must re-derive every hash from the manifest's own recorded parameters
and be run **at the start of the training job**, not only at freeze. A run that cannot
reproduce its own manifest hash is `ROUTE_B_INVALID`.

`prepare_matched_data.token_proxy_mean_input_chars:136` counts **characters, not tokens**.
It is forbidden as a token budget anywhere in this experiment. Characters per token differ
by surface (V5 measured 2.74–7.43 **[UNVERIFIED here]**), so the arm with the fewest
characters need not be the arm with the fewest tokens.

### 5.3 Retrain-from-base versus checkpoint-and-continue

**DECISION: retrain from the base checkpoint at every budget.**

One line of justification: with checkpoint-and-continue the optimiser state at budget *n* is
a function of every smaller budget, so the five points are not five independent measurements
of "what *n* examples buy" — and the 5× cost is ~75 minutes of A100 time (§15), which is not
a reason to make the primary object of the experiment uninterpretable.

Mechanically: `base.load_state_dict(base_state)` before every (arm, budget, seed) cell, a
fresh `get_peft_model`, a fresh `AdamW`, and `torch.manual_seed` / `random.seed` reset — the
existing `train_arm` (`gpu_matched_runner.py:169`) already does exactly this per arm and
must do it per cell.

### 5.4 The runner is not the tournament

`gpu_matched_runner.HALVING_RULE:33` and its Stage A/B/C structure **eliminate arms**. A
learning curve needs all five arms at all five budgets. The successive-halving runner is
therefore not the Route B runner and must not be reused as one. The Route B runner is a
50-cell grid (5 arms × 5 budgets × 2 seeds), plus:

- a **GPU authorisation gate** (§15) — none exists today; `gpu_matched_runner.py:129` only
  refuses when CUDA is *absent*, which is not the same thing;
- **resumability** — `resume` appears nowhere in `arena/`, and a 50-cell grid that cannot
  resume will lose hours to one transient failure;
- **adapter persistence** — `save_pretrained` appears nowhere in `arena/`; the historical
  runner calls `unload()` (`:294`) and discards every adapter. Route B must save each cell's
  adapter with its `dataset_hash`, or no result can be re-evaluated without retraining.

All three are **MUST BUILD**.

---

## 6. Seeds

Two seeds, and the distinction matters more than the count.

| Seed | What it controls | Route B value |
|---|---|---|
| **DATA seed** | which items land in train / dev / fresh, and the order of the train prefix, via `seeded_stratified_split` | **fixed at 0**, shared by both training seeds |
| **TRAINING seed** | `torch.manual_seed` and `random.seed`: LoRA A-matrix init (B is zero-init), and batch composition | **varied: {0, 1}** |

**Why only the training seed varies.** The paired analysis already absorbs item-sampling
noise: every arm sees the same items, and the bootstrap resamples items. The variance
component the paired design *cannot* see is training-run noise. Varying the training seed
targets exactly that, and holding the data split fixed keeps the per-item outcome vectors
comparable across seeds, which is what makes seed-averaged per-item scores legal (§10.2).
Data order is **not** reshuffled per training seed.

**The defect that makes any of this meaningful.** `prepare_matched_data.stratified_split`
declares a `seed` parameter and never reads it in the body: seeds 0 and 999 return
byte-identical train, dev and fresh index lists **[measured]**. Any claim of "two seeds"
resting on that function is one split reported twice. Route B **must** use
`seeded_stratified_split` (keyword-only `seed`, per-(seed, domain) `random.Random` stream),
and the manifest must record `split_mode = SEEDED`. A manifest recording
`LEGACY_DETERMINISTIC` with two distinct `split_seed` values is `ROUTE_B_INVALID`.

Two seeds is a *replication* requirement, not extra sample size. Fifty cells at two seeds
does not make n = 256; n is 128 items (§10.4).

---

## 7. The two matching regimes — reported side by side, never pooled

### EXAMPLE_MATCHED (primary)

Every arm sees the same *number of examples* at each budget: 16, 32, 64, 128, 224. Update
count is `ceil(n/4)` and is identical across arms. Training token counts are recorded and
**never equalised**.

Answers: *given the same mathematics, which representation reaches accuracy faster per
example?* This is the deployment-relevant regime and includes representational compactness
as a legitimate advantage (`GOAL.md` §14).

Does **not** answer: whether an arm won because it is easier to learn or because it packed
the same content into fewer tokens and therefore received more gradient signal per token.

### TOKEN_COMPUTE_MATCHED (secondary)

Every arm receives approximately the same number of **training tokens**, so example counts
differ per arm.

**How tokens are counted, exactly:**

- tokenizer: the frozen τ, `Qwen/Qwen2.5-7B-Instruct` @
  `a09a35458c702b33eeacc393d103063234e8bc28` — the *same* tokenizer for every arm;
- unit: `len(tokenizer(build_prompt(input_text))["input_ids"]) + len(tokenizer(target_text + eos)["input_ids"])`,
  i.e. **prompt + target**, matching what `gpu_matched_runner.encode:159` actually feeds the
  model, before the `[-max_len:]` truncation;
- when: at **manifest freeze**, on CPU, before any GPU minute, and written into the
  manifest. Never recomputed at run time, never estimated from characters;
- the token ladder is `T_k = round(mean over the five arms of the token count of that arm's
  first `n_k` examples)` for `n_k ∈ {16,32,64,128,224}`, and each arm then takes the
  shortest prefix of its own ordered train list whose cumulative token count is ≥ `T_k`.
  This keeps nesting (a prefix is still a prefix) and keeps the canonical-ID sets
  overlapping but **not identical across arms** — which is the price of token matching and
  must be stated in the write-up, because the paired per-item analysis of §10 is
  **unavailable** in this regime.

Answers: *is the representation easier, or did it simply use fewer tokens?*

Does **not** answer: anything paired. Under TOKEN_COMPUTE_MATCHED the arms train on
different example sets, so only unpaired accuracy with Wilson intervals is reported.

**The two regimes are never pooled, never averaged, and never combined into one score.** A
disagreement between them is a finding, not a problem to be resolved.

---

## 8. Primary endpoint: held-out VERIFIED accuracy

### 8.1 Three metrics, kept apart, one of them primary

Verifier-backed evaluation **did not exist** before this design:
`gpu_matched_runner.score_prediction:71` computed `verified` as "the parsed JSON is a dict
and contains `action_id`, `operation`, `arguments`", and it read 1.000 for every arm in every
stage **[measured]**. `NativeVerifier` was never imported by `arena/training/`. The
replacement is `arena/training/verified_eval.py` (landed concurrently in the parallel
workstream; its hashes and tests must be confirmed before use).

| Metric | Definition | Status |
|---|---|---|
| `schema_valid` | the completion parses as a JSON object carrying `REQUIRED_ACTION_KEYS`. This is exactly what the old `verified` measured, named honestly. | secondary |
| `exact` | decoded JSON equals the gold target object. Bit-for-bit the historical `exact` predicate, so the Tier-2 numbers remain comparable. | secondary |
| **`verified`** | **PRIMARY.** See §8.2. | **primary confirmatory** |

### 8.2 What "verified" means, per slice

**Slice 1 (`WORLD_V0_DEIDENTIFIED_NEXT_ACTION`).** An output is VERIFIED iff **all** hold:

1. it parses to a JSON object (`parse_completion`) — else `UNPARSEABLE`;
2. it carries `action_id`, `operation`, `arguments` — else `MISSING_KEYS`;
3. `CanonicalAction.from_dict` accepts it — else `UNDECODABLE`;
4. `NativeVerifier.verify_state` on a probe state carrying the decoded action raises no
   CRITICAL issue — this checks operator arity, sort confusion, unbound variables,
   definedness obligations for partial operators, and that `target_ids` name objects that
   exist — else `BAD_ARGUMENTS`;
5. `NativeVerifier.verify_transition` accepts the action, i.e. its `action_id` is a member
   of the reference state's `legal_actions` — else `VERIFIER_REJECTED`;
6. `require_content_match=True`: the decoded action is mathematically identical to the legal
   action bearing that id on every field except `expected_usefulness`
   (`ORACLE_ONLY_ACTION_FIELDS`, the field `scrub_action_labels` defines as evaluation-only)
   — else `CONTENT_MISMATCH`.

Step 6 is not a verifier judgement. It is a guard, and it exists because
`verify_transition` compares `action_id` strings and nothing else: a prediction of
`{"action_id": <any legal id>, "operation": "", "target_ids": [], "arguments": []}` is
accepted by `NativeVerifier` on **676/676** Arena World v0 tasks with zero mathematics in it.
De-identification (§4.3) removes the string rewrite that makes that id free; the content
guard removes the hollow action. Both are required; neither alone suffices.

**Slice 2 (`FORMAL_DEEPEST_IDENTIFIER`).** An output is VERIFIED iff it parses to
`{"deepest_identifier": <string>}`, the string names an identifier that actually occurs in
the rendered observation (the invalid-action analogue), and it equals the argmax of an
**independent** re-derivation of `identifier_depths(target)` computed from the canonical
expression — not from the rendered surface, and not from a stored answer key.

### 8.3 How `verified` differs from `exact` and from `schema_valid`

- `schema_valid` ⊇ `verified`: an output can be well-formed JSON and mathematically wrong.
- `verified` and `exact` are **different predicates but coincide on both candidate slices**,
  and this must be stated in the write-up rather than left for a reader to discover. On
  Arena World v0 every state offers exactly one legal action, which is the gold target, so
  `VERIFIED_NOT_EXACT` is structurally unreachable. On slice 2 the answer is a single
  canonical string. `verified` is nonetheless primary, because it fails closed on
  hollow-but-legal outputs that `exact` would also reject but for accidental reasons, and
  because the class becomes informative the moment a branching world exists. A non-zero
  `VERIFIED_NOT_EXACT` count on either slice is itself a finding about the generator.
- Unadjudicable items (the reference state fails `verify_state`, or carries no
  `legal_actions`) count as **NOT verified and stay in the denominator**. The alternative
  estimate is reported as `verified_rate_excluding_unadjudicated`, and the primary decision
  must hold under **both** conventions or the result is descriptive only.

### 8.4 Per-token training loss is FORBIDDEN as an endpoint

Not primary, not secondary, not a tie-breaker. It is recorded as a diagnostic of *when*
fitting happens and nothing else.

The reason is measured, not stylistic: in the historical sprint the early-budget loss order
was JSON < Structured English < HML ≈ S-expression < Compact Symbolic, while the only
held-out accuracy order at 224 was JSON > Compact Symbolic > Structured English > HML >
S-expression. Compact Symbolic has the **worst** loss at every budget and the **second-best**
accuracy. Per-token loss is computed over sequences whose tokenisation differs by
representation, so a cross-arm loss comparison confounds representation with token density.
Any Route B claim resting on loss ordering is `ROUTE_B_INVALID`.

---

## 9. Secondary metrics

All descriptive unless §10.3 names them confirmatory. All reported per (arm, budget, seed),
with intervals, in both matching regimes where the regime permits.

| Metric | Definition |
|---|---|
| `invalid_action_rate` | share of items in `{VERIFIER_REJECTED, BAD_ARGUMENTS, CONTENT_MISMATCH, UNKNOWN_OPERATION}` |
| `malformed_output_rate` | share in `{UNPARSEABLE, MISSING_KEYS, UNDECODABLE}` |
| `unadjudicated_rate` | share in `{UNADJUDICATED}`; a non-zero value on a slice that passed H1–H3 is a defect, not a datum |
| `ood_structural` | VERIFIED accuracy on the **fresh** slice, evaluated once, at the top budget only, never used for any selection |
| `tokens_per_correct` | mean generated output tokens ÷ VERIFIED accuracy, at each budget |
| `train_tokens_to_threshold` | training tokens to first reach VERIFIED ≥ 0.60 on dev, by linear interpolation between adjacent budgets; `NOT_REACHED` if never |
| `examples_to_threshold` | the same in examples — the direct sample-efficiency statistic |
| `gpu_seconds_to_threshold` | wall-clock training seconds to the same threshold |
| `learning_curve_area` | mean VERIFIED accuracy over the five budgets (trapezoidal in `log2(n)`); the single-number curve summary |
| `mean_prompt_tokens` | per arm, from the manifest; compactness is a Pareto axis under `GOAL.md` §15, not a defect to hide |
| `mean_latency_s`, `mean_output_tokens` | as recorded historically |

`0.60` is the threshold because it sits inside the [floor 0.20, ceiling 0.90] window the
§4.5 gate guarantees, and near the accuracy at which the §10.4 power simulation was run.

---

## 10. Statistics

### 10.1 The design is paired

Every arm sees the same held-out items in the same order, so item *i* is the same
mathematics for every arm. `per_item_exact` vectors are already emitted
(`gpu_matched_runner.py:254`) and consumed (`analyse_sprint.py:73`); `verified_eval` exposes
`verified_vector`, `exact_vector`, `schema_valid_vector` and `adjudicated_vector` as
`tuple[float, ...]`, directly consumable by `evaluation.paired_bootstrap_difference:28` and
`evaluation.wilson_interval:18`. Both are unit-tested. No new statistical machinery is
required for the pairwise layer.

### 10.2 PRIMARY CONFIRMATORY — one test, no multiplicity

**Statistic.** `S = max over budgets of (max arm VERIFIED accuracy − min arm VERIFIED
accuracy)`, computed on the seed-averaged per-item outcome (values in {0, 0.5, 1}) at each
of the five budgets.

**Test.** Exact within-item permutation of the **arm label**, 10,000 permutations. Under
H0_ROUTE_B the five outcomes for item *i* are exchangeable across arms, so this test is
exactly calibrated by construction. Reject at **p ≤ 0.05, one-sided** (the statistic is a
spread; only large values are evidence).

**Why this test.** It answers the actual question ("does R matter anywhere on the curve?")
with a single prespecified statistic, so the multiplicity across 5 budgets × 5 arms is
absorbed into the statistic rather than paid for with a correction. Simulated type-I rate at
the null: **0.051 at n = 48 and 0.043 at n = 96** **[measured, own simulation]** — calibrated.

**Seeds.** The item, not the (item, seed) pair, is the unit. Averaging the two seeds per item
before permuting reduces training-run noise without inflating n. Additionally, the **sign of
the largest observed arm gap must agree across the two seeds**; if it does not, the result is
downgraded to `ROUTE_B_UNDERPOWERED_INCONCLUSIVE` regardless of p.

### 10.3 SECONDARY (Holm across 4)

Four paired comparisons, each non-baseline arm against `L3_JSON_AST`, at the **single
prespecified top budget 224**, on VERIFIED accuracy, exact two-sided McNemar, Holm-corrected
across the four. Run **only if** the primary rejects. These localise an effect; they do not
establish one.

**Everything else is descriptive, with intervals and no p-values:** the 5 × 5 accuracy grid,
per-budget Wilson intervals, per-budget paired bootstrap deltas against the baseline, all of
§9, the loss curves, the token ladder, the fresh-slice numbers, and the entire
TOKEN_COMPUTE_MATCHED regime.

**Comparisons are made at fixed budgets**, never at each arm's own best budget.

### 10.4 HONEST POWER ANALYSIS

Simulated with a shared per-item difficulty effect (logit link, σ = 1.0) at base accuracy
0.60, 5 arms evenly spaced across the stated spread; 10,000-permutation test at α = 0.05
**[measured, own simulation]**:

| held-out n | spread 0.10 | 0.15 | 0.20 | 0.25 | 0.30 |
|---|---|---|---|---|---|
| 48 (historical) | 0.092 | 0.160 | **0.303** | 0.453 | 0.625 |
| 96 | 0.155 | 0.307 | 0.573 | 0.807 | 0.943 |
| **128 (this design)** | ≈0.19 | ≈0.45 | **≈0.72** | ≈0.83 | ≈0.95 |
| 192 | 0.304 | 0.636 | 0.897 | — | — |

Pairwise exact McNemar against the baseline, α = 0.05 uncorrected:

| n | δ = 0.10 | 0.15 | 0.20 |
|---|---|---|---|
| 48 | 0.098 | 0.239 | 0.438 |
| 96 | 0.212 | 0.474 | 0.776 |
| 192 | 0.424 | 0.801 | 0.979 |

Minimum detectable effect, exact sign test, all discordances one way:

| family | α | min all-win discordances | min δ at n = 48 | min δ at n = 128 |
|---|---|---|---|---|
| single test | 0.05 | 6 | 0.125 | 0.047 |
| Holm m = 4 | 0.0125 | 8 | 0.167 | 0.063 |
| Holm m = 20 | 0.0025 | 10 | 0.208 | 0.078 |

**Stated plainly.** At n = 128 this design detects a between-arm spread of 0.20 with
probability ≈ 0.72 and a spread of 0.10 with probability ≈ 0.19. **Route B v1 is a
large-effect instrument.** It cannot detect the kind of 5–10 point difference that would
still be scientifically interesting, and a null result from it is evidence against a *large*
representation effect on sample efficiency, not against any effect. Two seeds do not change
this; n is items, not runs.

At the historical n = 48 the same design has power 0.303 at a 0.20 spread and the minimum
detectable pairwise difference under Holm-4 is 0.167 — i.e. the historical evaluation slice
could not have detected anything short of a landslide. That is why `DEV_SIZE` is 128.

### 10.5 Practical-equivalence region

**±0.125** on the paired difference, matching `docs/FITNESS_V5_SPEC.md` §7.

Anchored to what is achievable, not to taste: the median 95% paired-bootstrap half-width
under the null is **0.177 at n = 48, 0.125 at n = 96, 0.109 at n = 128 and 0.089 at n = 192**
**[measured, own simulation]**. A region tighter than 0.109 could never fire at n = 128, so
±0.125 is the tightest defensible value for this design. Any equivalence claim at n < 96 is
forbidden.

---

## 11. Parity checklist

Every axis along which two arms could accidentally differ. `GUARANTEED BY <file:line>` means
a mechanical check exists today. `MUST BUILD` means it does not.

| Axis | Status |
|---|---|
| Identical canonical trajectories, identical order | GUARANTEED BY `arena/training/render_dataset.py:117` (canonical-ID sequence equality, fails closed) |
| Identical mathematical targets | GUARANTEED BY `arena/training/render_dataset.py:123` (target-hash sequence equality) |
| Arms are genuinely distinct surfaces | GUARANTEED BY `arena/training/render_dataset.py:111` (byte-identical inputs refused) |
| At least two non-empty, equal-length arms | GUARANTEED BY `arena/training/render_dataset.py:100`–`:110` |
| Task selection identical across arms | GUARANTEED BY `arena/training/prepare_matched_data.py` (one split, applied to all arms) |
| Budget nesting (prefix, not just subset) | GUARANTEED BY `arena/training/route_b_data.py:107` |
| Per-arm dataset bytes committed | GUARANTEED BY `arena/training/route_b_data.py:96` + `manifest_hash` |
| Manifest reproducible at run time | GUARANTEED BY `arena/training/route_b_data.py:538` — **but must actually be called by the runner: MUST BUILD** |
| Answer-bearing fields stripped from the observation | `arena/compiler/projection.py:25` strips `legal_actions` / `plausible_invalid_actions` for NEXT_ACTION — but `assert_no_answer_leakage:47` **is never called on this path**. MUST BUILD |
| Prompt scaffolding and instruction text identical | `gpu_matched_runner.SYSTEM:41` and `build_prompt:47` are arm-independent by construction; **MUST BUILD** an assertion that the rendered prompt differs between two arms *only* inside the state block |
| Tokenizer identical | frozen τ, one instance, `AutoTokenizer.from_pretrained(args.model)`; MUST BUILD an assertion that the tokenizer hash is identical across cells |
| Sequence length / truncation | **MUST BUILD — see the box below** |
| Padding | `padding_side="left"`, `pad_token = eos`; labels masked to `-100` over the prompt span (`gpu_matched_runner.py:204`). Identical across arms. Recorded, not asserted: MUST BUILD |
| Example order within a budget | identical canonical-ID order for every arm, from one split; GUARANTEED BY the manifest's per-budget ID list |
| Optimiser state | reset per cell by construction (§5.3); MUST BUILD the per-cell reset (today the reset is per arm) |
| Base checkpoint | `base.load_state_dict(base_state)` per arm, `gpu_matched_runner.py:172` — extend to per cell. MUST BUILD |
| Seed | `torch.manual_seed` / `random.seed` per cell, `gpu_matched_runner.py:170`; and `split_mode = SEEDED`, §6. MUST BUILD the manifest assertion |
| Evaluation slice | one dev slice and one fresh slice, shared by every arm, budget and seed; GUARANTEED BY the manifest |
| Decoding | `do_sample=False`, `max_new_tokens=192`, identical for every arm (`gpu_matched_runner.py:239`) |
| Held-out quality | dev and fresh GOLD-only. **MUST BUILD** (§4.4) |
| Held-out content disjointness | **MUST BUILD** (§4.4) |
| Adapter persisted for re-evaluation | **MUST BUILD** — `save_pretrained` appears nowhere in `arena/` |

### The truncation trap — the single most dangerous parity failure

Representations differ in rendered length. At a fixed context length, a longer surface can be
**truncated where a shorter one is not** — and `gpu_matched_runner.encode:165` truncates with
`ids = (prompt_ids + target_ids)[-max_len:]`, which silently drops the *front* of the state.
If that fires on one arm and not another, the arms no longer receive the same mathematical
information, visible-information parity (`GOAL.md` §13) is broken, and the entire comparison
is void — while every parity check above still passes, because they all run on the rendered
text, before tokenisation.

On the historical 676-world slice this is not reachable: mean rendered input is 828–1,296
characters and the maximum is 1,973, against `max_len = 1536` tokens **[measured]**. On the
formal slice it is very reachable: V5 measured a **6.5× median and 23.7× maximum**
cross-surface length ratio on unrestricted real Lean states **[UNVERIFIED here]**.

Therefore:

- **H3 (§4.5) is a hard preflight gate**, computed with the frozen τ on CPU before any GPU
  minute, over train ∪ dev ∪ fresh, for every arm;
- the runner asserts `len(ids) < max_len` for every training example and every evaluation
  prompt at run time and **aborts** on the first violation rather than truncating;
- `truncation=True` is removed from the evaluation tokenizer call
  (`gpu_matched_runner.py:234`); a prompt that does not fit is an error, not a shorter prompt;
- any recorded truncation, in any arm, at any budget, is `ROUTE_B_CONFOUNDED_BY_LENGTH` and
  voids the run.

---

## 12. Contamination and the experimental firewall

- **Three disjoint slices**: train pool, dev, fresh. Disjoint by `trajectory_id` *and* by
  `problem.content_hash` (§4.4). The historical split satisfied only the first, and
  8/48 dev items at budget 576 were content duplicates of training items **[measured]**.
- **Fresh is reserved.** It is evaluated **once**, at the end, at the top budget only, and
  never used for any selection, gate, threshold or model choice. If a Route B analysis
  touches the fresh slice before the primary test is executed, the run is `ROUTE_B_INVALID`.
- **Dev is the selection surface and nothing else selects.** No budget, arm, threshold,
  decoding setting or slice is chosen after seeing a between-arm contrast.
- **No historical data as hidden data.** The Tier-2 sprint's split, artifacts and cache are
  read-only inputs to this design's *diagnosis* (§4.1) and are never a Route B evaluation
  slice. `artifacts/experiments/tier2_sprint/gpu_sprint_results.json` is not re-scored.
- **Pretraining contamination is not controlled and cannot be.** Arena World v0 states are
  synthetic and unlikely to be in the Qwen2.5 corpus; the formal slice is derived from
  mathlib and Batteries, which almost certainly *are*. This asymmetry is a declared confound
  of slice 2 (§16), and it is one more reason slice 1 is attempted first.
- **Donor sealing (slice 2 only).** `sealed_source_files` excludes the donor's read-once
  holdout by source-file name; no state, target or answer from the sealed shard is loaded
  (`arena/environments/formal_structural.py:245`).
- **Cache identity.** Every cell's artifact is keyed by
  (experiment, instrument version, base-model revision, `manifest_hash`, `dataset_hash`,
  arm `genome_hash`, budget, training seed, budget mode). A cache hit whose key does not
  contain all nine is `ROUTE_B_INVALID` — this is the Phase-6 cache/model decoupling hazard,
  and it must not be reintroduced.

---

## 13. INVALIDATION_RULE

The run is `ROUTE_B_INVALID` if **any** of the following holds:

1. `verify_manifest` fails, or the runtime `manifest_hash` differs from the frozen one;
2. any arm's `dataset_hash` at any budget differs from the manifest's value;
3. `assert_matched_semantics` or `assert_nested_ids` fails at run time;
4. any training example or evaluation prompt is truncated, in any arm, at any budget
   (`ROUTE_B_CONFOUNDED_BY_LENGTH`);
5. the manifest records `split_mode = LEGACY_DETERMINISTIC` together with two distinct
   `split_seed` values, or the two training seeds produce byte-identical adapters;
6. any dev or fresh item is not GOLD, or shares a `problem.content_hash` with the train pool;
7. `malformed_output_rate` exceeds **0.05** for any arm at any budget (the response protocol,
   not the representation, is then what is being measured);
8. `unadjudicated_rate` exceeds **0.02** for any arm at any budget;
9. any cell fails to complete and its absence is not recorded — a partial grid analysed as a
   complete one;
10. the base checkpoint is not reloaded before a cell, or the optimiser is not reset;
11. any claim in the write-up rests on per-token training loss (§8.4);
12. the fresh slice is consulted before the primary test executes;
13. the primary conclusion changes sign under the two `unadjudicated` conventions (§8.3).

`ROUTE_B_INVALID` is not a result. It requires a fix and a re-run under a new manifest hash,
and it consumes one of the §15 authorised attempts.

---

## 14. STOPPING_RULE and DECISION_RULE

### Stopping

- **One slice at a time, in the frozen order of §4.3.** Slice 1; if it fails the §4.5
  headroom gate, slice 2; if slice 2 also fails, stop.
- **One grid per slice**: 5 arms × 5 budgets × 2 seeds = 50 cells, plus preflight.
- **No third seed, no sixth arm, no additional budget** is added after seeing results. Any
  of those is a new experiment under a new instrument version.
- **Hard wall-clock cap**: 6 GPU-hours total for the whole of Route B v1, preflight included
  (§15). Whatever has completed at the cap is persisted; the grid is then either complete or
  the run is `ROUTE_B_INVALID` under rule 9.
- **Programme-level:** Route B v1 is a single authorised attempt. A v2 is admissible only if
  it changes a frozen variable class named in the v1 failure analysis — a different slice, a
  different `π`, or a larger held-out slice. Re-tuning a threshold is not a new attempt.

### Decision — exactly one outcome class

| Sentinel | Fires when |
|---|---|
| `REPRESENTATION_AFFECTS_SAMPLE_EFFICIENCY` | primary permutation test p ≤ 0.05 **and** the sign of the largest arm gap agrees across both seeds **and** no §13 condition holds. Secondary Holm-4 comparisons then localise it. |
| `NO_MEASURABLE_SAMPLE_EFFICIENCY_DIFFERENCE` | primary p > 0.05 **and** the observed between-arm spread is inside ±0.125 at **every** budget. The honest null: at this power, on this slice, no large representation effect on sample efficiency exists. |
| `ROUTE_B_UNDERPOWERED_INCONCLUSIVE` | primary p > 0.05 **and** the observed spread exceeds ±0.125 at any budget, **or** the seed signs disagree. Not a null; the design could not resolve it. |
| `ROUTE_B_SLICE_VOID_NO_HEADROOM` | H4, H5 or H6 fails on a slice |
| `ROUTE_B_SLICE_VOID_NOT_LEARNABLE` | H6 fails specifically |
| `ROUTE_B_POOL_INSUFFICIENT` | H1 fails |
| `ROUTE_B_LENGTH_UNFAIR` | H2 fails |
| `ROUTE_B_CONTEXT_TRUNCATION` | H3 fails at preflight |
| `ROUTE_B_CONFOUNDED_BY_LENGTH` | truncation occurs at run time |
| `NO_TASK_FAMILY_SUPPORTS_MATCHED_LEARNING_MEASUREMENT` | **both** slices fail the §4.5 gate. Route B is exhausted with the current canonical world and the current donor corpus; the blocker is the mathematics available, not the instrument. |
| `GPU_NOT_AUTHORISED` | §15 gate absent or false |
| `ROUTE_B_INVALID` | any §13 condition |

No outcome creates a `LEARNABILITY_CANDIDATE` on its own. Under `GOAL.md` §16 that level
additionally requires replication on the fresh slice and a second base checkpoint, neither of
which is in scope here.

---

## 15. GPU AUTHORISATION

**No GPU minute may be spent under this document. Not one.** The project owner must
authorise it explicitly and in writing before any training call.

### Estimated cost

| Item | Count | Basis |
|---|---|---|
| Preflight H1–H3 | 0 GPU | CPU only |
| Preflight H4 (zero-shot floor) | 5 arms × 128 items | ~5 min |
| Preflight H5/H6 (reference ceiling) | 1 arm × 224 examples, train + eval | ~5 min at the historical context length |
| Main grid | 5 arms × 5 budgets × 2 seeds = **50 cells** | — |
| Cells retrained from base | 50 | §5.3 |
| Total training examples | 2 × 5 × (16+32+64+128+224) = **4,640** | — |
| Total evaluations | 50 × 128 dev + 10 × 64 fresh = **7,040** generations | — |

**Wall clock.** The historical A100-80GB sprint completed 10 train-and-evaluate units
(5×224 + 3×576 + 2×576 = 4,000 training examples, 480 generations) in **930 s** including the
base-model load **[measured]**. Route B's grid is comparable in training examples and ~15×
in generations, at a context length that may be 2–3× larger. Estimate **2.5–5 GPU-hours**;
**budgeted cap 6 GPU-hours** including preflight and one restart.

**Money.** At USD 2–4 per A100-80GB-hour on a spot/rental market **[UNVERIFIED — no price
was checked in this session]**, 6 hours is roughly **USD 12–24**. The cost is not the reason
to be careful; the irreversibility of a badly-designed run is.

### The mechanical gate

An accidental run must be *impossible*, not merely discouraged. The only guard in the
historical runner is `gpu_matched_runner.py:129`, which refuses when CUDA is **absent** — a
capability check, not an authorisation check, and on a rented GPU box it stops nothing.

`arena/training/gpu_authorisation.py` landed in the concurrent workstream and supplies the
first three requirements. **It is not wired into any runner**, which is a deliberate,
separately-reviewed change and is still MUST BUILD.

1. **In-process intent** — `require_gpu_authorisation(authorized=...)`; the runner must
   expose it as an explicit flag with default `False`.
2. **Machine interlock** — `ARENA_GPU_SPEND_AUTHORIZED=1`
   (`gpu_authorisation.GPU_AUTHORISATION_ENV_VAR:52`), so a script copied onto an
   unauthorised box does not spend there.
3. **Preregistration binding** — `expected_preregistration_hash` must equal
   `preregistration_hash(docs/ROUTE_B_V1_SPEC.md)`. The expected hash is a caller parameter,
   never a constant in the gate's own source, so it cannot be edited in the same commit that
   changes the design. Every ambiguity — missing variable, empty file, blank or malformed
   hash — fails closed.
4. **Manifest binding — MUST BUILD.** In addition to (3), the runner must refuse unless the
   `manifest_hash` it was handed equals the one recorded in the authorisation record. A
   preregistration hash pins the *design*; only the manifest hash pins the *data*.
5. **Dry-run default — MUST BUILD.** `--execute` must be passed explicitly. Without it the
   runner builds the manifest, runs H1–H3, prints the cost estimate, and exits 0 having
   touched no GPU.
6. **Per-cell deadline — MUST BUILD.** Checked before every cell, defaulting to the
   authorised cap, with whatever has completed persisted (`persist()` after every cell — the
   existing `gpu_matched_runner.py:259` behaviour, kept).

Any refusal emits `GPU_NOT_AUTHORISED` and exits non-zero. Until all six hold, Route B has
no runner, and this document authorises nothing.

---

## 16. What this experiment cannot establish

1. **It cannot rank five representations.** At n = 128 with power ≈ 0.72 at a 0.20 spread,
   the ordering of five arms is noise unless the spread is enormous. Only "does R matter" is
   in scope.
2. **It cannot detect a small effect.** A 5–10 point sample-efficiency difference — which
   would be scientifically interesting and commercially decisive — is invisible here
   (power ≈ 0.19 at 0.10). A null is evidence against a *large* effect only.
3. **It is conditional on one data split.** The data seed is fixed at 0 (§6), so
   generalisation across splits is untested. This is a deliberate trade: the two seeds buy
   an estimate of training-run noise instead.
4. **It is one base checkpoint, one adaptation method, one scale.** Qwen2.5-7B-Instruct with
   LoRA r=16 on q/k/v/o. Nothing here transfers to full fine-tuning, to a different family,
   or to another scale. `GOAL.md` §13's "single-reader effects" kill gate applies: no
   representation claim survives one reader.
5. **`verified` does not mean "solved".** Nothing in `arena/verifier/` executes an action.
   `NativeVerifier` establishes that the predicted action is structurally well formed and
   legally available. It does not establish that it is correct, useful or optimal.
6. **`VERIFIED_NOT_EXACT` is unreachable on both candidate slices** (§8.3), so the specific
   scientific advantage of a verifier over exact match — crediting valid answers that differ
   from the reference — is not exercised by this experiment. It is preregistered for the
   world that will have branching states, not for this one.
7. **Pretraining familiarity is uncontrolled.** Under slice 2 the underlying mathematics is
   public mathlib, which the base model has plausibly seen; under slice 1 it is synthetic.
   Neither condition is a clean test of "which representation is easier to learn" as opposed
   to "which representation the base model has already seen more of". `GOAL.md` §14 names
   this as precisely the reason matched learning exists, and matched learning does not
   eliminate it — it only holds it equal across arms, which it does, since all five arms
   render the same underlying mathematics.
8. **It says nothing about Game P.** The projection policy `P` is frozen. A representation
   that would win under a different visibility policy is not detectable here.
9. **A positive result is a result about a slice, not about mathematics.** If
   `REPRESENTATION_AFFECTS_SAMPLE_EFFICIENCY` fires on a de-identified synthetic world, the
   next obligation is replication on slice 2, not promotion.

---

## 17. Allowed sentinels

`REPRESENTATION_AFFECTS_SAMPLE_EFFICIENCY`,
`NO_MEASURABLE_SAMPLE_EFFICIENCY_DIFFERENCE`,
`ROUTE_B_UNDERPOWERED_INCONCLUSIVE`,
`ROUTE_B_SLICE_VOID_NO_HEADROOM`,
`ROUTE_B_SLICE_VOID_NOT_LEARNABLE`,
`ROUTE_B_POOL_INSUFFICIENT`,
`ROUTE_B_LENGTH_UNFAIR`,
`ROUTE_B_CONTEXT_TRUNCATION`,
`ROUTE_B_CONFOUNDED_BY_LENGTH`,
`NO_TASK_FAMILY_SUPPORTS_MATCHED_LEARNING_MEASUREMENT`,
`GPU_NOT_AUTHORISED`,
`ROUTE_B_INVALID`.

Nothing in this document authorises a GPU minute, an `R*` naming, a `FITNESS_CANDIDATE`, a
`LEARNABILITY_CANDIDATE`, or an R-only mutation campaign.

---

## Appendix A — measurements made while writing this spec

CPU only, no model call, no GPU, no network. Reproducible from
`arena.tasks.generators.world_v0`, `arena.training.prepare_matched_data`,
`arena.languages.registry` and `arena.training.render_dataset` at the current commit.

| Claim | Value |
|---|---|
| `stratified_split` seed is inert | `stratified_split(tasks, 600, 48, 48, 0)` and `(..., 999)` return identical train, dev and fresh index lists |
| Budget nesting | `train[:16] ⊂ [:32] ⊂ [:64] ⊂ [:128] ⊂ [:224] ⊂ [:576]` as ordered prefixes |
| Train list length | 580, not the requested 600 (the world is exhausted); 424 GOLD / 104 SILVER / 52 REJECT |
| First 576 train examples | 424 GOLD / 104 SILVER / 48 REJECT → 152 non-GOLD in historical Stage B/C |
| First non-GOLD train position | 416 → max GOLD-pure *prefix* is 416; max GOLD budget after filtering is 424 |
| Budgets 16–224 | 100% GOLD under the legacy split |
| Legacy dev / fresh quality | 48/48 GOLD each |
| Seeded dev quality | 36/48 GOLD at split seed 0; 36/48 at seed 1 — the seeded splitter does **not** filter held-out quality |
| World quality | 520 GOLD / 104 SILVER / 52 REJECT of 676; all 520 GOLD consumed by train+dev+fresh |
| Historical saturation | exact 1.000 on dev **and** fresh at 576 for `L3_JSON_AST` and `L5_COMPACT_SYMBOLIC`; 0.979 / 0.958 at 224 |
| Historical `verified` and `schema_valid` | 1.000 in all 10 recorded cells |
| Target uniqueness | 580/580 distinct train targets, 48/48 distinct dev targets, zero dev targets present in train |
| Target constancy | 4 of 8 keys single-valued over dev; `operation` a bijection with the 13 domains |
| `action_id` copyability | the stem is a literal substring of the rendered input on 48/48 dev items for all 5 arms |
| `arguments` copyability | 15/48 dev items' `arguments` appear verbatim in the input |
| Held-out content contamination | dev 8/48 and fresh 7/48 at budget 576; dev 5/48 and fresh 3/48 at 224; dev 2/48 at 16. All 8 collisions have byte-identical `arguments`; one inspected pair had 0.9979 input similarity |
| Answer-level leakage | 21/48 dev answers already seen in train at 224; 26/48 at 576 |
| Rendered length (train[:224], chars, mean / max) | L5 828/1416, L0 1051/1639, L3 1070/1658, L1 1098/1686, L2 1296/1973. Ratio of means 1.57 |
| Target length | 369 chars mean, 709 max |
| World scaling | the 676-world is a strict prefix of the 2600-world by `trajectory_id`; 2600 tasks yield only 1910 distinct problems |
| Content-deduplicated GOLD pool | 445 (world 676), 838 (1352), 1511 (2600) |
| Per-domain distinct-GOLD cap | `sets` 17 and `statistics` 17 at world 2600, against 154 for nine other domains → domain-balanced content-disjoint GOLD pool capped at 221 at any world size |
| 11-domain pool (excluding `sets`, `statistics`) | 11 × 92 = 1012 |
| Power simulations | §10.4 tables; type-I 0.051 (n=48) and 0.043 (n=96) at the null |
| Paired-bootstrap half-width under the null | 0.177 (n=48), 0.125 (96), 0.109 (128), 0.089 (192) |
| `save_pretrained`, `resume` | zero occurrences anywhere in `arena/` or `tests/` |
| `assert_no_answer_leakage` | defined at `arena/compiler/projection.py:47`; called only in `tests/compiler/test_projection.py` |
| `NativeVerifier` in `arena/training/` | zero imports before `verified_eval.py` landed |
| `render_dataset.write_jsonl` | zero callers before `route_b_data.py` landed |

Not verified here, and marked as such throughout: the formal-state pool counts (461 eligible,
104 length-fair), the 2.74–7.43 chars-per-token range, A100 rental pricing, and the test
status of `arena/training/route_b_data.py`, `arena/training/verified_eval.py`,
`arena/training/gpu_authorisation.py` and the `seeded_stratified_split` addition to
`arena/training/prepare_matched_data.py`, all of which landed in concurrent workstreams while
this document was being written. Their contents were read; their tests were not run. Confirm
them, and re-confirm every file:line reference in §11, before treating any `GUARANTEED BY`
row as satisfied.
