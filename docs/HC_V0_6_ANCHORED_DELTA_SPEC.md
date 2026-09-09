# HC-V0.6 — the anchored paired Δ(R_A, R_B) specification

**Status: SPECIFICATION. No data exists. Nothing here is a result.**

Governing authority: `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`
(unchanged, §47 Step 2). Design source: `docs/HC_V0_6_DESIGN_BRIEF.md`. Predecessors:
`docs/HC_V0_5_HANDOFF.md`, `docs/HC_V0_5_REDTEAM.md`, `docs/HC_V0_5_RESULT.md`.
Compliance audit of this document against the manual: `docs/HC_V0_6_MANUAL_COMPLIANCE.md`.
Frozen statistical contract: `docs/HC_V0_6_PREREGISTRATION.md`.

This document is written for a reader with zero context. It says what the experiment is, what its
numbers may and may not be used for, and where it is required to say `UNKNOWN`.

Where a value is not yet measured, this document writes `PENDING: <what determines it>` and names
the work item that fills it. A `PENDING` slot is a hole with a shape. Filling one later is a
**completion**; changing a filled one after exposure is a **violation** (§3.2, §44.4).

---

## 1. What HC-V0.6 is, and what it is not

### 1.1 Is

HC-V0.6 is **one paired comparison of two renderings of the same Lean proof state, at a single
anchored state, one action deep, adjudicated by Lean.**

The unit of observation is an **anchored state**: a real `BackendStateEnvelope` reached by
replaying a prefix of a recorded mathlib4 proof inside a live Lean REPL session, at which goals
are still open. Every arm at one anchor is stepped from the *same live `state_id` in the same
session* by branching (`LeanReplSession.step(state_id, tactic)` accepts any state the session has
produced). The arms therefore see one identical mathematical object; they differ only in the bytes
that describe it.

Within this project this is the first comparison of two representations under kernel-backed
verification with the truth state held identical by construction. That is a statement about this
programme's own history, not about the field: `docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md` returns
`NOVEL_ONLY_IN_COMBINATION`, and searching over how state is rendered to an LLM agent, scored by
that agent's downstream success, is already published. **No novelty claim is available here.**

### 1.2 Is not

* **Not a language-evolution result.** One hand-specified interface variant is not a search. No
  generation is run, no archive is updated, no parent–child landscape is estimated. §31's
  searchability metrics are undefined at n=1 candidate and MUST NOT be reported.
* **Not a horizon result.** The endpoint is one action deep. §23's central prediction —
  `Δ_L(20) > Δ_L(1)` — is *not addressed*. HC-V0.6 supplies `Δ_L(1)` and nothing else. A `Δ_L(1)`
  cannot support, refute, or bound a horizon interaction (`docs/HAMILTONIAN_CHESS_META_GOAL.md`
  §5.1: the absolute gap `p^H − q^H` is unimodal in `H` under a *constant* per-step edge, so any
  horizon inference from a single-step number is arithmetic dressed as a finding).
* **Not a capability result.** mathlib4 is publicly available and predates this Solver; nothing
  here separates a goal that was solved from one that was recalled. The defensible phrasing is
  **execution under kernel verification**, never *reasoning*, *discovery*, or *capability*.
* **Not a claim about `RSTAR` or `LSTAR`.** §6.36 reserves `RSTAR` for a representation-only
  *search*; Appendix D requires strong controls, holdout confirmation and **at least two
  meaningfully distinct Solver families**. HC-V0.6 has one candidate, one Solver, one prompt, no
  holdout. The maximum claim tier reachable is `VALID_CANDIDATE` (Appendix D: "0 known blocking
  defects under the declared gate").
* **Not the global language reward.** §35 demotes small next-action probes to *diagnostic*: they
  "may validate instrumentation or isolate local causal effects" and "SHALL NOT define the global
  language reward." `p_accept` at one action is exactly such a probe. It is admitted here as a
  **diagnostic-tier local causal assay** and is barred from becoming a fitness objective for any
  later search. §48's prohibition on building "another micro-benchmark as the global objective"
  binds this experiment specifically.

### 1.3 Where it sits on the §25 ladder, stated honestly

§25's rungs are defined by **adaptation**, not by statistical care. Gate 0 is deterministic
validity with *"no model calls"*; Gate 1 is the *"cheap scout"*; Gate 2 is *"short matched
adaptation"*. HC-V0.6 makes model calls, so it is past Gate 0, and it runs **zero** adaptation
(§2.7), so it cannot be Gate 2 or above.

**HC-V0.6 sits at Gate 1.** It is more statistically disciplined than Gate 1 demands — preregistered
endpoint, cluster-aware intervals, four arms, an identity floor and a sensitivity floor — but
discipline does not promote a rung. Gate 1's binding constraint therefore applies verbatim:

> Gate 1 — cheap scout. Catastrophic unreadability and gross failure detection. **MUST NOT crown a
> language.**

Anyone quoting a Δ from this experiment as though it settled which rendering is better is quoting
a Gate 1 number at Gate 5. §25 Gate 5 requires fresh project-hidden confirmation data, strong
incumbent controls, example-matched adaptation, selection-bias protection and an independent rerun.
HC-V0.6 has none of the five.

### 1.4 The evaluation mode

`INTERACTIVE_TASK` (§14.6): the Solver acts in a `VerifiedTask` and may take a path different from
the recorded one. §17.3 governs the interpretation — a Solver action different from the recorded
action is **not** mathematically wrong unless the verifier establishes that, and Lean is the only
thing here that establishes anything. Measured separately at HC-V0.5: across 14 theorems Lean
accepted a non-reference tactic in 10, and in 2 an alternative closed a goal mathlib proves
differently (`research/phase9/interactive_probe/`).

**The bank builder reads the reference proof; the assay does not.** Constructing an anchor replays
recorded tactics — oracle-side work, `actor=REFERENCE`, exactly like `ReplayDriver`. The Solver is
shown the resulting goal state and never the prefix that produced it, and never the suffix. This
separation MUST be visible in the code and in the artefact, not only in prose (open defects
V05-01/V05-03 are precisely the failure of that visibility; see §8.7).

---

## 2. The §26.1 universal declaration

§26.1: *"Every comparison MUST declare"* the following twelve items. Each is filled with the
actual value for HC-V0.6, or marked `PENDING` with the work item that fills it.

### 2.1 Tasks / distribution

| field | value |
|---|---|
| source | LeanDojo `benchmark_4`, `random/train.json` (373 MB, CC BY 2.0) |
| path | `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json` |
| split admitted | **TRAIN only.** `random/{val,test}.json` and `novel_premises/{val,test}.json` sit in the same tree, are SEALED, were never opened, and MUST NOT be opened by HC-V0.6 |
| population | 118,517 records · 59,557 with `traced_tactics` · 250,814 steps |
| unit | the **anchored state**, not the episode and not the theorem |
| `ProjectHidden` (§6.28) | **NO.** TRAIN was inspected by this project. HC-V0.6 is developmental evidence, never confirmation (§30.4) |
| `ModelExposureStatus` (§6.29) | **`KNOWN_PRE_CUTOFF_PUBLIC`**, and by transitivity `LIKELY_PRETRAINING_EXPOSURE` for derived states. (The project term `HISTORICALLY_EXPOSED` used in the brief is not in §6.29's controlled vocabulary; these two values are its glossary equivalents and are what MUST appear in the artefact) |
| grouping unit (§18.2, §30.6) | **theorem file** — strictly coarser than theorem, and theorems in one mathlib file are not independent |
| anchor selection rule | **REALISED.** `depth 0 when open, then evenly spaced quantiles of the remaining open depths; fixed rule, no RNG, independent of any Solver outcome`; `seed=0`, `scan_limit=40000` records, `theorem_limit=80`, `max_anchors_per_theorem=3`, `min/max_reference_length=3/24`, `max_prefix_length=12`, `allow_multiline_tactics=false`, `tactic_policy=record_only:54954a450e6c9c5b`. Nothing downstream of Solver performance is read (design brief §7) |
| bank size | **REALISED: `n` = 223 anchors · 78 theorems · `n_clusters` = 75 distinct files.** `n_clusters`, not `n`, is the effective sample size — see §8.6 |

**The bank is built.** `artifacts/trajectory/hc_v0_6_anchor_bank.json`, schema
`arena-anchored-state-bank-v0`, generator `arena/trajectory/anchor.py@v0`, generated
2026-09-08T21:43:14Z, **content hash
`9fa6b6da12e237a3d8b682aad4346f1416bbe14689298a3cfb8bac805e4605dc`**. What it records, and what
each fact does or does not license:

| fact | value | reading |
|---|---|---|
| anchors / theorems / files | 223 / 78 / **75** | 75 is the number that enters every interval (§8.6) |
| anchors per theorem | 3 (×69), 2 (×7), 1 (×2) | near-maximal within-theorem clustering; the design effect is real |
| re-derivation | **223 / 223 matched**, 0 errors, in a *second independent Lean process* | the recipe reaches the same `reelaboration_key`; this buys **re-runnability**, not internal validity (§8.5) |
| depth class | `INITIAL` 78 · `MID_PROOF` 145 | a sampling label. **Not** difficulty — see §4 |
| goals per anchor | 1 (×201), 2 (×21), 4 (×1) | |
| discards | `SELECTION_BELOW_MIN_HORIZON` 31,210 · `SELECTION_MULTILINE_TACTIC` 3,646 · `SELECTION_NO_BY_BLOCK` 387 · `SELECTION_ABOVE_MAX_HORIZON` 328 · `SELECTION_NOT_THEOREM_OR_LEMMA` 286 · `DEPTH_NOT_SELECTED` 99 · `NO_OPEN_GOALS` 62 · `SELECTION_LEAKAGE_FILTER` 29 · `PREFIX_REJECTED_BY_LEAN` 16 · `SESSION_FAILED_TO_START` 2 | every discard is a *pre-Solver* filter; none reads an outcome |
| leakage, record level | 139 leaking steps of 69,561 scanned; 29 problems dropped of 8,790 (`FULL_NAME_IN_STATE` 104, `TACTIC_IN_STATE_BEFORE` 35) | criterion `LeakageFilter.scan_record`, unchanged from the audit's baseline |
| leakage, anchor level | **`{}` — none found** under `TACTIC_IN_STATE_BEFORE`, `FULL_NAME_IN_STATE`, `LEAKS_PREFIX_TACTIC_IN_STATE` on the live state a Solver would see | the bank's own note is explicit that anchor-level and record-level figures **must not be pooled**; see §5 for the residual V05-14 hole this does *not* close |
| cost | 417.34 s total (222.76 s derivation, 192.35 s re-derivation, 2.23 s selection); 1.00 s/anchor derivation, 1.87 s/anchor including re-derivation, 2.78 s/theorem | this is the *bank* cost, not the assay cost; the assay's per-cell cost is dominated by the Solver and is `PENDING` |
| sealed splits | `random/{val,test}.json`, `novel_premises/{val,test}.json` — recorded as **not read** | |
| segregation | `solver_visible` is the only sub-object a prompt may be built from; `oracle` holds prefix tactics, the whole recorded proof and the declaration span, `actor=REFERENCE`; `assert_no_oracle_leak()` is the tripwire | this is §1.4's separation made structural rather than promised |

The bank carries its own `sampling_proxy_note`, and it is repeated here because it is the single
most abusable line in the artefact: *"prefix_length and observed_trace_length are SAMPLING PROXIES,
never reasoning difficulty. MinimalProofLength is UNKNOWN and nothing in this arena could establish
it; a shorter proof may always exist. EpisodeLength is 0 at an anchor because an anchor is a state,
not an episode. DependencyDepth is UNKNOWN for this backend."* See §4.

**What the bank does not settle.** `n = 223` and `n_clusters = 75` are *realised*, not *justified*:
the power analysis has not been run, so whether 75 clusters suffice for the `delta_min` that will
be chosen is `PENDING: the power analysis`. A bank that exists is not a bank that is adequate, and
outcome **O6** (§9.6, underpowered) remains reachable.

### 2.2 Truth-kernel / backend versions (§6.24 `BackendKernelContract`)

| field | value |
|---|---|
| backend | Lean 4 via `Lean4Repl.lean`, one REPL process per theorem |
| toolchain | `leanprover/lean4:v4.10.0-rc1`, **always invoked as `env -C $MB`** (the bare binary reports 4.33.1; elan resolves per directory) |
| mathlib4 | commit `29dcec074de168ac2bf835a77ef68bbe069194c5`, built, 5,680 `.olean` |
| root | `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4` |
| state identity | `KernelStateIdentity` (`arena/trajectory/state_identity.py`), normalisation `goal-text-nfc-linewise-rstrip-v0`, schema `arena-backend-state-identity-v0` |
| caps | `startup_timeout_s=180.0`, `step_timeout_s=60.0`, `session_lifetime_s=900.0`, `kernel_timeout_s=300.0`, `max_heartbeats=1_000_000` |

Truth is backend-native (§17.4). The canonical schema is **not** used: `docs/CANONICAL_VNEXT_PILOT.md`
mapped 0 of 368 real Lean states losslessly, and raw pretty-printed state equality scored 40.6%
where real semantic agreement was 98.1%. Nothing in HC-V0.6 compares states by text.

### 2.3 Solver initialization / checkpoint (`π`, §6.14)

| field | value |
|---|---|
| model | `qwen3.6:27b-mlx` served by Ollama 0.33.2 |
| digest | `d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7` |
| shape | 27.8B, `nvfp4`, family `qwen3_5`, context 262144 |
| lineage | **`UNKNOWN`, and not inferred.** This is not the Phase 6/8 Solver (`qwen38-rvn`, `25eb57cb…`), which was deleted and is unrecoverable. §1: `UNKNOWN` is not permission to guess |
| identity binding | `verify_served()` MUST be called and its result recorded per run (V05-02 was a module constant nothing verified; fixed at HC-V0.5) |
| `think` | **`False`, frozen.** With `think` omitted or `true` the answer is diverted to a separate field and `response` returns empty — every proposal would read as a parse failure and the run would read as "the model cannot do Lean" |

One Solver. §25 Gate 6 and Appendix D require ≥2 meaningfully distinct Solver families for any
robustness claim; HC-V0.6 makes none. Any effect measured here is, until replicated,
**model-specific** — §43's `REPRESENTATION_EFFECT_MODEL_SPECIFIC` is a live outcome, not a caveat.

### 2.4 Tokenizer (`τ`, §6.13)

The model's own tokenizer as served by Ollama; renderer/parser `qwen3.5`. **Identical function in
both arms; frozen; not a treatment.** No tokenizer training, no vocabulary change, no
`TAU_CHANGE`. §10.10 defers candidate-specific tokenizer training; §48 forbids optimizing
tokenizer and language simultaneously in V0. Neither happens.

The token *sequence* necessarily differs between arms because the bytes differ. That is a property
of every `R_ONLY` comparison ever run and is analysed in §8.2, not hidden here.

### 2.5 Controller (`C`, §6.15)

**No controller.** One Solver call per cell, greedy decode, no beam, no tree, no backtracking, no
retrieval policy, no branch manager.

`controller_id = "NULL_CONTROLLER_SINGLE_CALL_V0"`.

**No retry.** HC-V0.5 declared `ONE_DIAGNOSTIC_RETRY / max_retries=1`; HC-V0.6 sets `max_retries=0`.
Rationale: a retry makes `p_accept` a best-of-2 statistic, and V05-07 showed the declared retry
budget absorbing 6 live rejections when `skip` is interleaved. At one action depth there is no
diagnostic to feed back and no reason to keep the mechanism. This MUST be enforced in the runner,
not by convention.

### 2.6 Tools / libraries (`U`, §6.17)

**None.** No retrieval, no premise selection, no calculator, no SMT, no web. mathlib4 is the
*environment* the Lean process elaborates against — it is not a Solver-facing tool and the Solver
cannot query it. Identical in both arms.

`toolset_id = "NONE_V0"`.

### 2.7 Adaptation examples / order

**None. Zero-shot.** No fine-tuning, no in-context examples, no ordering to match.

This places HC-V0.6 squarely and only in §24's **Q-A regime** — *"Which language best exploits a
fixed pretrained model with minimal/no adaptation?"* — where the manual itself warns that
*"Controlled English may dominate because of pretraining familiarity."* Read §8.1 before
interpreting any number produced here. **No Q-B (matched-adaptation) claim of any kind is
available.**

### 2.8 Adaptation / inference budgets (`B`, §6.19)

| field | value |
|---|---|
| adaptation budget | 0 |
| Solver calls per cell | exactly 1 |
| retries | 0 |
| decode | candidate `FROZEN_DECODING`, as already exercised by the noise study: `temperature=0.0`, `seed=20260908`, `top_k=20`, `top_p=0.95`, `min_p=0.0`, `repeat_penalty=1.0`, `presence_penalty=0.0`, `num_ctx=32768`, `num_predict=128`, `think=False`, `stream=False`, `raw=False`. `PENDING: docs/HC_V0_6_RUNTIME_NOISE.md` — the noise study may narrow `top_k`, and whatever it returns is frozen before the assay runs |
| max output tokens | `num_predict=128` in the noise study; `PENDING: frozen with the decode options`; identical across arms |
| Lean step budget per cell | 1 tactic, `step_timeout_s=60.0` |
| replicates `k` per (anchor, arm) | `PENDING: docs/HC_V0_6_RUNTIME_NOISE.md and the power analysis jointly.` See §8.4: if determinism holds, `k = 1` |
| **prompt-token parity** | **not held fixed, and this is a real asymmetry.** §26.2 lists "compute regime" among the quantities `R_ONLY` holds fixed, and a re-layout changes prompt length. HC-V0.6 does not equalise prompt tokens — it **measures and reports them per arm as a mandatory mediator** (§8.3). `docs/HAMILTONIAN_CHESS_META_GOAL.md` §7a requires a compute- and sampling-matched control and warns that *"a language that merely says less is not a better language"*; the sampling half is matched exactly (1 call, no retry), the token half is measured, not matched |

### 2.9 Verifier (`V`, §6.18) — see §7 for the full trust contract

Lean's elaborator adjudicates **acceptance**. Lean's kernel plus a `#print axioms` allow-list
adjudicates **closure**. These are different adjudicators and the spec keeps them separate.

### 2.10 Seeds

| purpose | value |
|---|---|
| anchor selection | **`0`** — the bank builder's realised seed, recorded in `selection.seed` of the bank manifest. (The depth rule is deterministic and uses no RNG; the seed governs theorem sampling only) |
| Solver decode | `20260908` |
| arm-order permutation within anchor | recorded per run; the permutation is a pure function of `(seed, anchor_id)` (design brief §9.1) |
| C3 permutation null | drawn from a recorded seed; the number of permutations is frozen in the preregistration |

### 2.11 Output / action protocol (`A`, §6.11; §26.7)

**Identical in all arms.** Prompt template `hc-v0.5-tactic-json-v1` (sha256 `95a4e049…`), output
grammar `{"tactic": "..."}` (sha256 `9b25cba2…`), one JSON object, strict parse.

`GOAL.md` §13 requires that candidate-specific output syntax not contaminate an input-representation
experiment; §26.7 prefers universal action IDs where feasible. A tactic string is not a universal
action ID — it is the action space Lean actually has — but it is **the same** action space and the
same grammar in every arm, so no output-protocol difference exists to contaminate anything. The
parse-failure rate is nonetheless a mandatory per-arm secondary endpoint (§8.4): a re-layout that
nudges the model's output format is a real, reportable effect and must not hide inside `p_accept`.

**Tactic policy.** `PENDING: frozen in the preregistration.` `TacticPolicy` defaults to
`record_only` (restricts nothing). `docs/HAMILTONIAN_CHESS_META_GOAL.md` §8a.3 warns that a single
heavy tactic can close many steps at once, so under an unrestricted set `p_close` measures
mathlib's automation rather than anything about the representation. Either policy is defensible;
the choice must be made **before** the run, stamped as `policy_id`, and reported. Whichever is
chosen, the tactic head of every proposal and `kernel_step_count` per accepted step are recorded
(§13.1 macro accounting; V05-09 showed `constructor <;> simp <;> omega` costing
`kernel_step_count=1`).

**One constraint the realised bank places on this choice.** The bank was *built* under
`tactic_policy = record_only:54954a450e6c9c5b` — that is the policy that decided which recorded
prefix tactics were replayable, and it restricted nothing. Selecting a stricter policy for the
assay is permitted, but it would mean the anchors were selected under one policy and played under
another; that asymmetry is not a leak (selection read no Solver outcome) but it MUST be stated in
the artefact if it is chosen, not discovered later.

### 2.12 Intervention class (§6.26) — see §3

**Four arms** (design brief §9.4, §9.6): `R_A`, `R_A_PRIME`, `R_B`, `R_ABLATED`.

| arm | renderer | class | role |
|---|---|---|---|
| `R_A` | baseline: Lean's native pretty-printed tactic state | **`R_ONLY`** | reference arm |
| `R_A_PRIME` | **whitespace-perturbed baseline**, bijective, semantically null | **`R_ONLY`** | **C1b**, the byte-perturbation null (§3.4) |
| `R_B` | the same characters re-laid-out (an `I` gene, §10.9) | **`R_ONLY`** | **primary** comparison |
| `R_ABLATED` | goal text withheld, goal count and metadata retained | **`P_CHANGE`** | **C2**, the sensitivity control (§3.3) |

| comparison | contrast | class | is it a hypothesis or a gate? |
|---|---|---|---|
| primary | `R_B` vs `R_A` | `R_ONLY` | hypothesis |
| **C1b** | `R_A_PRIME` vs `R_A` | `R_ONLY` | gate on the *interpretation* of the primary (§3.4) |
| **C2** | `R_ABLATED` vs `R_A` | `P_CHANGE` | gate: sensitivity floor |
| **C1** | `R_A` against itself, replicates split in half | `R_ONLY`, degenerate | gate: noise floor. **Not an arm** — it is computed inside `R_A` (design brief §9.2, §9.6) |
| C3 | arm labels permuted within anchor | n/a | descriptive empirical null |

`R_A_PRIME` is **not** "the baseline drawn a second time". That reading was current for part of
2026-09-08 and is retired by design brief §9.6; `Arm.R_A_PRIME.renderer_id` is `"R_A_PRIME"`. See
§11 for the one place where code still carries the retired meaning.

### 2.13 EvaluationUniverse (§6.27) and its hash

The thirteen components of §6.27 are: task distribution (§2.1), backend/kernel versions (§2.2),
Solver checkpoint (§2.3), tokenizer (§2.4), controller (§2.5), tools (§2.6), adaptation data
(§2.7), adaptation budget (§2.7), inference budget (§2.8), verifier (§2.9), seeds (§2.10),
evaluation split (§2.1), code/manifest versions (git commit + `harness_version`).

`evaluation_universe_hash` is the stable hash of all thirteen, and is the
`evaluation-universe hash` §30.3 requires. **Fitness outside this universe is `UNKNOWN` until
replicated** (§6.27). Note V05-16: `harness_version` is an identity component and not a condition
component, so a harness bump silently buys a second `FRESH` draw of the same edge — the assay must
either close that or record that it ran under a single fixed `harness_version`.

---

## 3. Intervention-class analysis

### 3.1 Why `R_B` vs `R_A` is `R_ONLY`, and exactly what that licenses

§26.2 requires an `R_ONLY` comparison to hold fixed: truth state; visible mathematical information;
action semantics/cardinality; tokenizer; Solver; controller; tools; training examples; evaluation
tasks; verifier; compute regime. *"Only approved representation/morphology/interface structure
differs."*

| §26.2 quantity | how HC-V0.6 holds it |
|---|---|
| truth state | **by construction** — all four arms branch from the same live `state_id` in the same session (design brief §9.3), which `research/phase10/branching/README.md` measured: two successful steps from one parent gave distinct children 6/6, the parent's text was unchanged after all branches, and a branch from a child also succeeded 6/6. Not by re-derivation, not by hash comparison: it is literally one object |
| visible mathematical information | by the contract in §3.2 below, plus `check_projection_parity(..., R_ONLY)` on `WorkspaceProjectionIdentity` |
| action semantics / cardinality | identical: one free-form Lean tactic string, same grammar, same parser, same Lean |
| tokenizer | identical function (§2.4) |
| Solver | identical digest, `verify_served()` checked (§2.3) |
| controller | identical null controller, `max_retries=0` (§2.5) |
| tools | none, in both (§2.6) |
| training examples | none, in both (§2.7) |
| evaluation tasks | the same anchor, in the same session, in the same run (§2.1) |
| verifier | identical (§7) |
| compute regime | sampling matched exactly; **prompt tokens not matched, measured** (§2.8, §8.3) |

§12.3 additionally requires an `R_ONLY` candidate to *prove* — not assert — same visible semantic
inventory, same candidate alternatives/action semantics, same truth state, and that only approved
representational structure differs.

`R_B`'s changed gene is a single **interface / serialization (`I`)** gene per §10.9 — *field
ordering*, *explicit labels*, *goal position*. One gene family, which is what §20.2 prescribes for
early causal reconnaissance: *"Early generations SHOULD prefer one gene family per child so
parent-child effects are interpretable."*

**What `R_ONLY` licenses.** A statement of the form: *under the declared EvaluationUniverse, moving
from rendering `R_A` to rendering `R_B` changed / did not change the probability that Lean accepts
the Solver's next tactic at an anchored mathlib state, by Δ with interval I.* That is the whole
licence. `R_ONLY` is also the only class for which `RSTAR` is even the right vocabulary (§6.36) —
and HC-V0.6 does not come close to earning it (§1.2).

**What it does not license.** Any statement about horizon, capability, reasoning, learnability,
other models, other domains, or the *intrinsic* merit of either layout independent of pretraining
familiarity (§8.1).

### 3.2 The `R_ONLY` contract — and a hole in it that must be closed

The design brief's contract is: every `R_ONLY` renderer ships `render(envelope) -> Mapping` and
`invert(rendered) -> Mapping`, and the bank-wide test `invert(R.render(s)) == R_A.render(s)` must
pass for every state. The brief argues: *"A bijection cannot add information (nothing to add it
from) and cannot remove information (it could not be inverted). That is what `R_ONLY` means,
checked rather than asserted."*

**Half of that is checked and half is still asserted.** The test establishes
`invert ∘ render = R_A.render`, i.e. `render` is injective *relative to* the baseline rendering:
**nothing is lost**. It does not establish that nothing is *added*. `render` takes the *envelope*,
so there is something to add from. The counterexample is one line:

```python
def render(self, envelope):  # passes the brief's test, and leaks
    return {**relayout(R_A.render(envelope)), "hint": oracle_ish(envelope)}


def invert(self, rendered):
    return baseline_from(rendered)  # simply ignores "hint"
```

`invert ∘ render == R_A.render` holds. A left inverse (a retraction) is not a bijection, and a
retraction is exactly what permits addition. This is the shape of the already-confirmed defect
**V05-15**: *"a renderer implementing `declare_information` is believed: it can render an extra key
and still pass `check_projection_parity` as `R_ONLY`."*

**The corrected contract, which HC-V0.6 SHALL use.** Three conditions, all mechanically checkable:

1. **No addition — structural.** `R_B`'s rendering function takes the *baseline rendering* as its
   only input: `R_B.render(envelope) := layout_B(R_A.render(envelope))`, where `layout_B` has no
   access to the envelope. Then "nothing to add it from" is true by signature rather than by
   argument. If the code must instead be declaration-derived (`render = layout_B(declare_information(envelope))`),
   the same discipline applies: `layout_B` receives the declaration and nothing else, and that must
   be enforced by construction, since V05-15 proves a declaration alone is believed rather than
   checked.
2. **No removal — tested.** `invert(R_B.render(s)) == R_A.render(s)` for **every** state in the
   bank. Any failure is `DEAD_INFORMATION_PARITY` (§12.4) and the candidate receives no Solver
   compute (§12.4: *"No dead candidate receives Solver compute."*).
3. **Slot parity — tested.** `check_projection_parity(P(R_A, s), P(R_B, s), R_ONLY)` returns
   `parity_holds=True, bytes_differ=True` for every state, with the undeclared-key fold-in
   (`UNDECLARED_SLOT_PREFIX`) active so that any key not accounted for by a declared slot becomes
   its own opaque slot and *changes* the identity.

Conditions 1+2 together are the bijection the brief intended. Condition 1 alone is what forbids
addition; the brief's stated test alone does not.

**Condition 1 is implemented, and implemented in the stronger of the two permitted ways.**
`arena/trajectory/representation.py` supplies `DeclarationDerivedRenderer`, whose `render` is
`self.present(self.declare_information(envelope))` and which **forbids subclasses from overriding
`render`** (`__init_subclass__` raises). `present` never receives the envelope, so a renderer
physically cannot show what it did not declare — the V05-15 counterexample above is not merely
untrue of these renderers, it is unwriteable within the base class. `R_ABLATED` deliberately has no
`invert`, so `isinstance(R_ABLATED, BijectiveRenderer)` is `False` as a structural fact rather than
a comment, and `derive_intervention_class` returns `P_CHANGE` for it from the declared slot set
(a strict subset of the baseline's) rather than from a hand-written label — which is what design
brief §2 and precondition B5 require.

**`R_A_PRIME` satisfies the same contract, on the same terms.** `WhitespacePerturbedNative` is
declaration-derived (`present` receives only the declaration), declares the baseline's slots with
the baseline's values, and ships `invert`; `docs/HC_V0_6_REPRESENTATIONS.md` reports **223/223**
bijection over the bank and `R_ONLY` typing on all three checks. One subtlety it records and this
spec adopts: `R_A_PRIME` declares the **envelope's** text, not the perturbed text, so `R_A` /
`R_A_PRIME` parity is exact rather than contingent on how `normalize_goal_text` treats a trailing
space. An identity computed from the *rendered* bytes would differ — nothing does that today, and
nothing may start to without saying so.

### 3.3 Why `R_ABLATED` is `P_CHANGE`, and what it may be used for

`R_ABLATED` withholds the goal text and retains the goal count and metadata. §6.6 defines `P` as
*"Which truth-grounded facts or deterministic derived relations from `K` and permitted history are
made explicit to the Solver."* Removing `GOAL_TEXT` from the exposed slot set is a change to
exactly that policy. It is therefore `P_CHANGE`, and the `InterventionClass` machinery MUST derive
that label from the genes. **If it has to be labelled by hand, that is a defect** (and V05-17
records that `intervention_class` is currently derived from a declaration and `gene_changes` is
never checked against the genomes).

§12.3 requires, for a `P_CHANGE`: a machine-readable parent delta; an admissibility audit; no
hidden answer/future-state information; and *"a claim label matching the intervention class."*
Removal cannot introduce answer or future-state information, so the admissibility audit is
trivially satisfied in the safe direction — but the parent delta and the claim label are still
mandatory artefacts.

§26.3, quoted exactly:

> `P_CHANGE`, `O_CHANGE`, `T_CHANGE`, and `A_CHANGE` intentionally alter the cognitive interface.
> They estimate system-level value of that intervention and **MUST NOT be reported as pure
> representation effects.**

**What C2 may be used for.** Exactly one thing: to establish the assay's **sensitivity floor** —
the size of an effect this instrument can detect at this `n`, `k` and cluster count. It answers
*"if there were a difference, would we see it?"*, which is the only thing that makes a null
`Δ(R_A,R_B)` interpretable (§9.2).

**What C2 may not be used for.** It is not a representation comparison, it is not a data point on
any representation landscape, it does not enter any leaderboard, it produces no fitness record for
a candidate, and its Δ is never quoted as "the effect of representation." `R_ABLATED` is not a
representation and must never be reported as one.

### 3.4 `R_A_PRIME` (C1b) — the arm that decides whether "structure" is sayable at all

`R_ABLATED` is a very large effect: the goal text is gone. Detecting it proves the rendering
pipeline is causally connected to the outcome **at all**. It does not prove sensitivity at the scale
a re-layout plausibly operates, and it says nothing about *why* a re-layout would move the outcome.

`R_A_PRIME` is a **whitespace-only, bijective, semantically null** perturbation of the baseline
bytes. It carries the same `R_ONLY` contract as `R_B` (§3.2, conditions 1–3), and its declared slot
set and declared values are identical to `R_A`'s, so `derive_intervention_class` returns `R_ONLY`
from the declaration rather than from a label.

It sits between C1 (byte-identical) and `R_B` (restructured), and it is the arm that decides which
sentences may be written about the primary result (design brief §9.4):

| `Δ(R_A, R_A′)` | `Δ(R_A, R_B)` | what may be said |
|---|---|---|
| inside `±δ_eq` | beyond `delta_min` | the effect survives a null byte change, so it is attributable to **the structure of the re-layout** rather than to the bare fact that bytes moved |
| beyond `delta_min` | beyond `delta_min` | the Solver is sensitive to byte perturbation **as such**. `R_B`'s effect **cannot** be attributed to its structure. This is a finding about the assay and it **blocks the representation claim** (outcome O9, §9.9) |
| beyond `delta_min` | inside `±δ_eq` | incoherent: a null byte change moved the endpoint and a structural one did not. Treat as `INSTRUMENT_INVALID`, not as a subtle result |
| inside `±δ_eq` | inside `±δ_eq` | O3, subject to C2 and the MDE (§9.3, §9.10) |

**C1b is a gate on interpretation, not a hypothesis about representation.** No one is proposing
whitespace as a language. Its Δ is never reported as a representation effect and never enters a
fitness record, exactly as C2's is not (§26.3's prohibition is about class, and C1b's class is
`R_ONLY`, so the prohibition that binds here is §1.2's instead: this is a diagnostic-tier local
assay and none of its numbers is a language reward).

**Two things C1b does not fix.** It does not separate *familiarity* from *structure* — `R_A_PRIME`
is also less familiar than `R_A`, so a non-null C1b is equally consistent with "the model is
brittle to bytes" and "the model prefers the exact mathlib surface" (§8.1). And it does not make
`R_B` interpretable if C1b is null but underpowered: a C1b whose interval is wider than
`delta_min` establishes nothing, and §9.10's MDE rule applies to it as to every other null here.

---

## 4. Horizon vocabulary — the paragraph that prevents granularity substitution

Granularity substitution is this programme's named recurring failure mode
(`docs/HAMILTONIAN_CHESS_META_GOAL.md` §7: *"A statistic computed on a coarser population than the
claim drawn from it is invalid. This was the programme's recurring failure mode; it recurs more
easily in a search loop, not less."*). The manual separates four horizon quantities precisely so
that one cannot be silently substituted for another (v0.2 correction 4; §6.30–§6.34; §17.6).

| term | §  | definition | HC-V0.6 |
|---|---|---|---|
| `ObservedTraceLength` | 6.30 | transitions in one *stored demonstration* | **known but not measured by this experiment.** It is the LeanDojo record's length and it enters only the bank builder's prefix rule. It is *not* difficulty (§6.30: "Not automatically the minimum reasoning horizon required by the task") |
| `EpisodeLength` | 6.31 | model-facing decisions in an *actual interactive run* | **= 1, by design and in every cell.** This is the only horizon quantity HC-V0.6 instantiates |
| `KernelStepCount` | 6.32 | trusted backend operations *after action lowering* | **recorded per accepted step, never used as a horizon.** §13.1 requires it so a macro cannot buy a fake efficiency win; V05-09 confirms `constructor <;> simp <;> omega` costs 1 |
| `DependencyDepth` | 6.33 | task-family-specific structural dependency measure | **`UNKNOWN`.** No such measure is defined for Lean tactic states in this repository. Not estimated, not proxied |
| `MinimalProofLength` | 6.34 | shortest proof under a declared action system, *"only when independently established"* | **`UNKNOWN`, for every anchor.** Nothing here establishes minimality |

**The paragraph.**

> HC-V0.6 measures `EpisodeLength = 1` and nothing else. It does not measure difficulty, depth,
> necessity, or minimality, and no number it produces may be re-described as any of those. In
> particular: the recorded proofs behind the anchored bank have an `ObservedTraceLength`, and that
> number MUST NOT appear anywhere near the result, because §17.6 is explicit — *"Do not call a
> 50-step recorded proof a '50-step required reasoning task' without evidence of
> necessity/minimality."* An anchor drawn at prefix position 7 of a 12-tactic recorded proof is
> **not** "a step 7 of 12 in difficulty"; it is one open goal state, and the only thing known about
> it is that mathlib closed it *somehow*. Selecting anchors deeper into recorded proofs does not
> make the assay "longer horizon"; it makes it a different sample of `EpisodeLength = 1` states.
> Any statement of the form "representation matters more at depth" requires a design in which
> `EpisodeLength` varies and the estimand is defined on the **per-step log-odds hazard**
> (`docs/HAMILTONIAN_CHESS_META_GOAL.md` §5.1 and `docs/LONG_HORIZON_FITNESS_V0.md`'s `β`), with
> the metric fixed in advance. HC-V0.6 is not that design and cannot be converted into one after
> the fact.

---

## 5. Projection admissibility (§27)

§27 requires every projection feature to declare `projection_id`, `source_fields`,
`derivation_algorithm`, `maximum derivation budget`, and five explicit negatives.

Every slot exposed by every HC-V0.6 renderer is read directly from the `BackendStateEnvelope` the
live Lean session produced. **No slot is derived, summarised, or computed.** The derivation
algorithm is projection, and the derivation budget is O(1) field access.

| slot | class | source | derived? |
|---|---|---|---|
| `GOAL_TEXT` | **P0** | Lean's own pretty-printed tactic state | no — verbatim from the backend |
| `GOAL_COUNT` | **P0** | goal count in the same state | no |
| `BACKEND_KIND` | **P0** | environment constant | no |
| `BACKEND_STATE_ID` | **P0** | the live session's `sid` | no |
| `PP_SCOPE` | **P0** | the elaboration scope the state was rendered under | no |
| `STEP_INDEX` | **P0** | 0 in every cell (`EpisodeLength = 1`) | no |
| `ATTEMPTS_REMAINING` | **P0** | budget constant, identical in every arm | no |
| `TERMINAL_STATUS` | **P0** | `OPEN` at every anchor by the anchor predicate | no |

**P1 (local deterministic structure): not used.** No binder/use links, no dependency edges, no
precondition status. **P2 (bounded derived summaries): not used.** No summaries of any kind.

**P3 (solution-dependent / future-dependent): NOT REACHED, and here is the argument.** §27 forbids
P3 in candidate input. The five §27 negatives, each answered:

| §27 field | HC-V0.6 |
|---|---|
| `uses_answer_label?` | **false.** `VerifiedTask.__init__` raises `ReferenceProofExposureError` if the probe still carries `reference_tactics`; `seal_reference_proof()` retains only counts, byte-lengths and digests; `__slots__` blocks attachment; `HashedLeakageGuard` can recognise a secret and can never produce one |
| `uses_future_state?` | **false in the Solver's input.** The bank builder replays a recorded prefix (`actor=REFERENCE`) and the Solver sees only the resulting state. The suffix is never rendered |
| `uses_hidden_solution?` | **false** |
| `uses_minimum_proof_path?` | **false** — `MinimalProofLength` is `UNKNOWN` and nothing consults it |
| `uses_candidate_correctness?` | **false** — no arm is told whether the other arm succeeded, and no cell sees any outcome |

Two honest qualifications, neither of which is a P3 breach:

* **`PP_SCOPE` carries the theorem's namespace.** That is P0 — it is directly present in the state
  Lean rendered — but under `LIKELY_PRETRAINING_EXPOSURE` a namespace is a recall cue. It is
  identical in both arms, so it cannot confound Δ; it inflates both arms' absolute `p_accept` and
  is therefore a threat to the *level*, not to the *contrast* (§8.1).
* **V05-14 is partly answered by the bank, and partly still open.** The defect: `HashedLeakageGuard`
  has a 6-byte floor and never registers `full_name`, `file_path` or `pp_scope.current_namespace`.
  The bank's own leakage pass **was** run at the anchor level — the same criteria applied to the
  *live state a Solver would see*, plus one conservative extra filter on already-played prefix
  tactics — under `TACTIC_IN_STATE_BEFORE`, `FULL_NAME_IN_STATE` and `LEAKS_PREFIX_TACTIC_IN_STATE`,
  and returned **`{}` — no anchor-level leak in any of the 223 anchors**. At the record level 139 of
  69,561 steps leaked and 29 problems were dropped before any anchor was derived
  (`SELECTION_LEAKAGE_FILTER` 29). `full_name` is therefore now checked, which is the larger half of
  V05-14. What is **not** closed: the 6-byte floor, and `pp_scope.current_namespace`, which is
  deliberately exposed (see the qualification above) and so cannot be filtered without changing the
  projection. The bank's own note forbids pooling the anchor-level and record-level figures; they
  are different measurements.

Anchors whose goal state would render the reference tactic verbatim are the only P3-adjacent risk.
The control for it is the bank's anchor-level pass above, and precondition B7 is **discharged for
the `full_name` / verbatim-tactic channel and still open for the byte-floor channel**.

---

## 6. The measurement

One **cell** is `(anchor s, renderer R, replicate j)`:

1. branch to `s` in the theorem's open session (one session per theorem, many branches);
2. `R.render(s)` → prompt → one Solver call (`think=False`, frozen decode);
3. parse `{"tactic": "..."}`, strictly;
4. `session.step(s.state_id, tactic)` — Lean decides;
5. record: `StepOutcome`, all-goals-closed, tactic head, `kernel_step_count`, prompt tokens,
   completion tokens, latency, `prompt_sha256`, `policy_id`, `state_id`, arm-order position.

**Primary endpoint.** `p_accept(R)` = P(the elaborator accepts the proposed tactic at an anchored
state). Binary, paired by anchor, clustered by theorem file.

**Secondary.** `p_close` (the single action closed all goals — axiom-checked, §7.2); parse-failure
rate; prompt-token count; completion-token count; latency; tactic-head distribution.

**Effect.** `Δ(R_A, R_B) = p_accept(R_B) − p_accept(R_A)`, paired within anchor, clustered by
theorem file (§30.6). The same estimator, cluster unit and collapsing rule produce `Δ(R_A, R_A′)`
(C1b), `Δ(R_A, R_ABLATED)` (C2), and the within-`R_A` split (C1).

**Arm order within each anchor is randomised** from a recorded seed, as a pure function of
`(seed, anchor_id)` (design brief §9.1). HC-V0.5 measured that a fixed prompt's answer can change
once other calls have passed through the same server process; with four arms a fixed order
`R_A, R_A_PRIME, R_B, R_ABLATED` would give every arm a fixed position in the server's call
history, confounding position with arm. Randomisation converts that confound into noise the paired
design absorbs. The realised permutation is recorded per anchor, and each cell carries its
arm-order position so that a position effect can be *tested* rather than assumed away.

**The four arms are played at one anchor from one branched `state_id`, in one session.** One
session per theorem serves every arm and every replicate at every anchor in that theorem; the total
cell count is `n × k × 4 = 223 × k × 4`.

**Every null is reported beside its MDE** (design brief §9.5). See §9.10 — this is a reporting
rule that binds every outcome, not a property of one of them.

---

## 7. Verifier trust contract (§28)

§28: every verifier backend SHALL declare `verifier_id`, version/domain, trust assumptions,
accepted constructs, unsupported constructs, timeout semantics, `UNKNOWN` semantics, error
semantics, and replay/rechecking method. **All nine, filled:**

```text
verifier_id          LEAN4_ELABORATOR_PLUS_KERNEL_AXIOM_ALLOWLIST_V0
version              Lean 4.10.0-rc1 (arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)
                     via leanprover/lean4:v4.10.0-rc1, always invoked as `env -C $MB`
domain               Lean 4 tactic proofs elaborated against mathlib4
                     @29dcec074de168ac2bf835a77ef68bbe069194c5 (5,681 .olean),
                     max_heartbeats = 1_000_000
trust assumptions    (a) the elaborator is correct about whether a tactic applies at a state;
                     (b) the kernel plus `#print axioms` reports the complete axiom dependency of
                     a finished declaration.  Nothing here trusts the pretty-printer, the
                     harness, or the Solver.
accepted constructs  any tactic string the elaborator accepts at the anchored state, subject to
                     the frozen `TacticPolicy` (PENDING, §2.11) and to the three unconditional
                     refusals below
unsupported          `sorry`, `sorryAx`, `admit`, `stop` — refused at three independent layers,
constructs           reward 0, verified live.  Axioms outside
                     {Classical.choice, Quot.sound, propext} — a *closure* is refused, not an
                     acceptance (see §7.1); `native_decide` fails this way via
                     `Lean.ofReduceBool`.  Multi-line tactics were excluded at bank build
                     (3,646 discards), so no anchor requires one
timeout semantics    `step_timeout_s = 60.0`, `kernel_timeout_s = 300.0`,
                     `session_lifetime_s = 900.0`, `startup_timeout_s = 180.0`.
                     TIMEOUT != FALSE — a timeout is a VOID cell (§7.3), never a non-accept
UNKNOWN semantics    UNKNOWN != FALSE.  A cell whose outcome is not attributable to the Solver
                     is VOID and enters neither numerator nor denominator (§7.3)
error semantics      TOOL_ERROR != MATHEMATICAL_INVALID.  `BACKEND_DEAD`, `SESSION_EXPIRED`,
                     `UNKNOWN_STATE_ID` and Solver transport failure are all VOID.  V05-13 is
                     the open defect that breaks this and is blocking (§7.3, precondition B2)
replay / rechecking  every cell records `prompt_sha256`, `state_id`, the tactic string and the
                     `StepResult`; the bank replays from
                     `(theorem_full_name, prefix_tactics, toolchain, mathlib commit)` via
                     `KernelStateIdentity.reelaboration_key` — measured at 223/223 in a second,
                     independent Lean process.  Closure is rechecked by a *separate*
                     re-elaboration of the finished script, never in-session
```

### 7.1 Two adjudicators, not one

| | adjudicates | mechanism | trust assumption |
|---|---|---|---|
| **`V_accept`** | the primary endpoint | Lean's **elaborator** returns a new tactic state for the proposed tactic | the elaborator is correct about whether a tactic applies |
| **`V_close`** | `p_close` only | the finished script is **re-elaborated separately** with `#print axioms <probe>`, and the axiom set must be a subset of the allow-list | the Lean **kernel** plus the allow-list |

**This distinction is load-bearing and the brief blurs it.** Calling `p_accept` "kernel-decided" is
an overstatement: an accepted-but-not-closing step is *elaborator*-decided, and no axiom check
exists to run on it because nothing has been proved yet. The defensible phrasing for the primary
endpoint is **"accepted by the Lean elaborator"**; only `p_close` is kernel-verified.

### 7.2 The axiom allow-list that closed RT-01

```
ALLOWED = { Classical.choice, Quot.sound, propext }
```

RT-01 was the previous suite's CRITICAL: `native_decide` produced `terminal_status:
CLOSED_VERIFIED, reward: 1.0, verified: true`. After the fix the same attack produces
`terminal_status: FAILED, reward: 0.0, verified: false, untrusted_axioms: ["Lean.ofReduceBool"]`
against that allow-list. The check is a **separate re-elaboration** of the finished script —
`#print axioms` inside the live session would be meaningless — with `kernel_timeout_s=300.0`.
An allow-list fails closed on the next exotic axiom; a deny-list would have to anticipate it.

`sorry` and friends (`sorry`, `sorryAx`, `admit`, `stop`) are refused unconditionally at three
independent layers, verified live, with reward 0 in every case. `rfl /-` (unterminated comment)
comments out the `#print axioms` line and the kernel check therefore **fails closed**.

### 7.3 Outcome disposition — the rule the primary endpoint requires

§28: `UNKNOWN != FALSE`; `TIMEOUT != FALSE`; `TOOL_ERROR != MATHEMATICAL_INVALID`; *"candidate
success is never awarded because the verifier crashed"*; *"candidate failure is never assigned
merely because infrastructure failed."* §14.4: *"`ENVIRONMENT_ERROR` SHALL NOT count as
mathematical failure."*

`p_accept` is a ratio, and **the design brief does not define its denominator.** Without the table
below, every timeout and every dead REPL silently becomes a mathematical non-accept, which is a
direct §28 violation. This table is normative for HC-V0.6 and MUST be frozen in the preregistration.

| observed | source | attributable to Solver? | disposition |
|---|---|---|---|
| `StepOutcome.OK` | Lean | yes | **numerator + denominator** |
| `StepOutcome.TACTIC_ERROR` | Lean | yes | **denominator only** — a real mathematical non-accept |
| `StepOutcome.SORRY_REFUSED` | policy | yes — the Solver proposed it | **denominator only** |
| `StepOutcome.POLICY_REJECTED` | frozen `TacticPolicy` | yes | **denominator only**, and reported separately per arm |
| parse failure (non-conforming JSON) | Solver | yes | **denominator only**, and a mandatory per-arm secondary endpoint |
| `StepOutcome.TIMEOUT` | Lean, 60 s | **no** — `TIMEOUT != FALSE` | **VOID cell.** Excluded from both; count reported per arm; arm-dependence tested |
| `StepOutcome.BACKEND_DEAD` | Lean process | no | **VOID cell** (`ENVIRONMENT_ERROR`) |
| `StepOutcome.SESSION_EXPIRED` | 900 s cap | no | **VOID cell** (`ENVIRONMENT_ERROR`) |
| `StepOutcome.UNKNOWN_STATE_ID` | harness | no | **VOID cell**, and a harness defect that must be investigated, not absorbed |
| Solver transport failure (runtime dead) | Ollama | no | **VOID cell** (`ENVIRONMENT_ERROR`) |

**Three mandatory consequences.**

1. A VOID cell is re-run once at the end of the run under the identical condition, and if it VOIDs
   again the anchor's whole pair is dropped **for all arms symmetrically** — never for one arm.
2. The VOID rate is reported **per arm**, and arm-dependence is tested. A re-layout that produces
   longer prompts could plausibly raise the timeout rate; if VOIDs are arm-dependent, the missingness
   is informative and `Δ` is biased. That is a finding, not a footnote.
3. **V05-13 is an open blocking defect against this table**: *"a dead model runtime is counted in
   `parse_failures` (the Solver's) and in **neither** `environment_errors`."* Under that behaviour a
   transport failure lands in the Solver's column and corrupts the denominator directly. It MUST be
   closed before the assay runs.

### 7.4 Replay / recheck method

Every cell records `prompt_sha256`, `state_id`, the tactic string, and the `StepResult`. The bank
is re-runnable from `(theorem_full_name, prefix_tactics, toolchain, mathlib commit)` via the
`KernelStateIdentity.reelaboration_key`. Note the standing caveat: `KernelStateIdentity.rendered_under()`
and `.from_dict()` mint an identity for any goal text with the kernel key intact (V05-25), so
re-elaboration equality is evidence of the recipe reaching the same state, not proof of it.

---

## 8. Threats to validity

Enumerated honestly. Where a threat is fatal to a class of claim, that is stated, not softened.

### 8.1 Contamination — and why it is the dominant threat, not a footnote

mathlib4 is public, predates this Solver, and exposure is transitive: a state reached by replaying
a prefix of a mathlib proof is a *derivative* of exposed text, so `LIKELY_PRETRAINING_EXPOSURE`
propagates to every anchor. Nothing in HC-V0.6 separates a solved goal from a recalled one.

The usual reassurance is that contamination is shared across arms and therefore cancels in a paired
contrast. **That reassurance does not hold here, and this is the sharpest threat in the document.**

`R_A` is *Lean's own pretty-printed tactic state* — byte-for-byte the surface form that appears in
mathlib, in LeanDojo, in every Lean tutorial and in every proof-assistant paper the model has read.
`R_B` is a re-layout of that surface that no corpus contains. So the arms differ not only in
"representation" but in **distance from the pretraining distribution**, and a negative `Δ` is the
*prediction of pure familiarity*, with no representation-quality content whatever. §24 Q-A states
the general form of this warning — *"Controlled English may dominate because of pretraining
familiarity"* — and §26.6 states its mechanism.

**Consequence, binding:** HC-V0.6 **cannot** distinguish "`R_B` is a worse representation" from
"`R_B` is less familiar". A negative Δ is consistent with both and discriminates neither. The
manual's own remedy is matched adaptation (§24 Q-B, §26.6: *"claims about intrinsic morphology
require matched-adaptation and tokenization/frequency controls"*), which HC-V0.6 does not run. This
asymmetry MUST appear in the result document beside the headline number, not in an appendix.

**The partial mitigation is now in the design, and its limit must be stated with it.**
`R_A_PRIME` (§3.4) is a whitespace-only perturbation: near-zero representational content, non-zero
unfamiliarity. It separates *"bytes moved"* from *"structure changed"*. It does **not** separate
*"less familiar"* from *"worse representation"*, because a whitespace perturbation is itself
unfamiliar. Concretely: if `Δ(R_A, R_A′)` and `Δ(R_A, R_B)` are both negative and similar in size,
the parsimonious reading is *the model is tuned to the exact mathlib surface*, and no
representation-quality statement survives. If `Δ(R_A, R_A′)` is null and `Δ(R_A, R_B)` is not,
familiarity-as-brittleness is ruled out but familiarity-as-*structural*-priming is not — `R_B`
restructures, and restructuring is exactly what pretraining has never shown this model. **The
irreducible residue is that only matched adaptation (§24 Q-B, §26.6) can settle it, and HC-V0.6
does not run it.**

### 8.2 Tokenizer confound (§26.6) — is this still `R_ONLY`? Argued explicitly

§26.6: *"A fixed pretrained tokenizer gives different segmentation/frequency priors to English
words and invented symbols."* `R_B` changes the byte layout, which changes segmentation. Does that
make it a `TAU_CHANGE`?

**No, and the reason is definitional.** §6.13 defines `τ` as *the tokenizer or low-level model
encoder* — a **function**. §26.2 requires that function to be held fixed; §26.6 says *"changing the
tokenizer is `TAU_CHANGE` or `JOINT`."* HC-V0.6 changes no vocabulary, no merge table, no encoder.
The same `τ` is applied to both arms. What differs is `τ(R_B(s))` versus `τ(R_A(s))` — the token
*sequence*, which is the image of the treatment under a fixed map. Calling that a `TAU_CHANGE`
would make every `R_ONLY` comparison in the manual impossible, since any change of bytes changes
the sequence.

**But the honest statement is stronger than "no confound", and it is a finding, not a formality.**
The causal path from `R` to the outcome runs *through* `τ`:

```
R  ──►  bytes  ──►  τ  ──►  token sequence  ──►  π  ──►  tactic  ──►  Lean
```

There is no path from `R` to the outcome that avoids `τ`. Therefore `Δ(R_A,R_B)` estimates the
**total effect of the rendering, tokenization consequences included** — not a tokenization-free
"representation effect". Segmentation is a *mediator*, not a confounder: it is on the causal path
and must not be adjusted away. The mediator is measured (prompt tokens per arm, §2.8) and reported,
which is the most that can be said at this design.

Two claims are therefore forbidden: (i) *"the effect is due to structure, not tokenization"* —
unidentifiable here; (ii) *"the effect is intrinsic to the representation"* — §26.6 explicitly
requires matched adaptation and frequency controls for that, which HC-V0.6 does not have. The
class remains `R_ONLY`; the *interpretation* is bounded by §26.6.

### 8.3 Prompt length and compute asymmetry

Not a confounder in the causal sense (it is downstream of `R`, like segmentation), but it is the
half of §26.2's "compute regime" that HC-V0.6 does not equalise, and `docs/HAMILTONIAN_CHESS_META_GOAL.md`
§7a names *"a language that merely says less is not a better language"* as a control the nearest
prior work fails. Mandatory reporting: mean and distribution of prompt tokens per arm, and `Δ` on
tokens beside `Δ` on `p_accept`. If `R_B` wins while spending materially more tokens, that is a
different result from winning at parity and must be stated as such.

### 8.4 Prompt-position and runtime non-reproducibility

HC-V0.5 measured: two identical runs gave different `result_hash`; every Lean state, `pp_sha256`
and kernel receipt was identical; divergence was entirely in Solver output on retries, with
**identical `prompt_sha256` and identical prompt token counts**; the same prompt asked six times in
isolation returned the byte-identical answer six times. The conclusion recorded there: *"the model
is deterministic for a repeated prompt in isolation, and non-deterministic for the same prompt once
other calls have passed through the same server process"* — server-side batching / KV-cache state,
not sampling. Temperature 0 and a fixed seed do not remove it.

A paired design assumes exactly the reproducibility this runtime lacks. Three mitigations, all
already in the design: arm-order randomisation within anchor (§6); `k` replicates chosen from the
measured noise model; and C1 as the empirical noise floor (§9.1).

**Provisional counter-evidence, 2026-09-08 — treat as PROVISIONAL, not settled.** Under the
candidate `FROZEN_DECODING` of §2.8, `research/phase10/noise/` measured on fresh Lean-REPL goals:

| probe | measurement | result |
|---|---|---|
| E1 back-to-back, one server process | 40 calls each at 3 prompt lengths (172 / 303 / 1072 chars) | **1 distinct response, 1 distinct tactic, modal rate 1.0 at every length** — 120/120 byte-identical |
| E2 interleaving | a fixed prompt repeated 30 times with 17 other prompts interleaved | **1 distinct response, modal rate 1.0**, and `solo_modal_equals_interleaved_modal = True` |

**And the HC-V0.5 divergence has been reproduced and localised.** Four repeat runs of one 6-episode
configuration (`artifacts/trajectory/noise_repro_{A,B,C,D}.json`) gave **four different
`result_hash` values** — HC-V0.5's finding (a), reproduced exactly — while:

* all **13 proposed tactics were identical** across all four runs;
* all four summaries were identical (5 accepted Solver transitions, 8 rejected, 1 solved,
  1 environment error, 0 parse failures);
* the **only** fields that differed were `latency_ms`, `wall_ms`, `wall_clock_s`, `generated_utc`,
  a `backend_error` string differing solely in a temp-directory name — and `completion_tokens`,
  which differed on **1 of 13 calls** (16 in run A, 12 in B/C/D) *for the same parsed tactic*.

So the honest three-level statement is: **`result_hash` is not reproducible; the response is
reproducible on 12 of 13 calls; the tactic, and therefore the endpoint, was reproducible on 13 of
13.** HC-V0.5's "the runtime is not reproducible" was true and was measuring the hash, not the
decision. That is reassuring for a paired design whose outcome is the decision — and it is not
proof, because 13 calls in one configuration is a small sample and the one divergent call shows the
response layer is not strictly deterministic.

Until `docs/HC_V0_6_RUNTIME_NOISE.md` exists, **this spec assumes nothing**. What it commits to is
the conditional:

* **If call-for-call determinism holds**, then `k = 1` is correct, replicates add nothing,
  `Δ(R_A, R_A)` is **exactly zero by construction** rather than estimated, and C1 must then be
  *reported as a construction*, not as a passed test (design brief §9.6). The only remaining
  randomness in the whole assay is the anchor sample — which makes the cluster bootstrap over the
  75 files (§8.6) the *sole* source of the interval, and makes `n_clusters` the only lever on power.
  The §4.1 replicate-collapsing question in the preregistration then dissolves, and option (b)
  degenerates to a plain paired comparison.
* **If it does not hold**, `k ≥ 2` is forced by the measured within-cell variance and C1 becomes a
  real test as originally designed.

`PENDING: docs/HC_V0_6_RUNTIME_NOISE.md` must answer all five questions of design brief §5.
**Three are still unanswered**: whether the knobs (`options.seed`, `top_k=1`) matter (`e3_knobs.py`,
no output), whether divergence depends on position in the call history (`e4_context_position.py`,
no output), and — the one that actually sets `k` — **the within-cell *acceptance* variance**
(`e5_cell_variance.py`, no output). E1 and E2 measure response identity, not acceptance variance;
a runtime that returns identical bytes has zero acceptance variance by implication, but that
implication is only as good as E1/E2's coverage, which is 4 prompts. The study is a **gate**, not a
preliminary, and `k` is frozen before the assay runs.

### 8.5 Anchor re-derivability, and what "anchored" actually buys

Design brief §9.3 is correct and worth restating: the truth state is shared by **branching within
one live session**, not by re-derivation, so validity does not depend on the measured
re-derivability rate. What re-derivability buys is *re-runnability later* — the bank can be replayed
from its recipe.

**Both halves are now measured, and neither is assumed.**

* *Branching* (`research/phase10/branching/README.md`): two successful steps from one parent gave
  distinct children **6/6**; the first child's text survived further steps from the parent; the
  parent's text was unchanged after all branches; a branch from a child also succeeded **6/6**. The
  README also records that an earlier version of the probe proved nothing — 26 of 28 tactics were
  `TACTIC_ERROR`, so no theorem ever produced two children — and that "the parent survived seven
  rejected steps" is not evidence. The rewrite uses `skip`, which succeeds on any open goal, so
  both branches are real. **This is what makes "the same truth state for both arms" true by
  construction rather than by hope.**
* *Re-derivation* (bank manifest): **223 / 223** anchors matched their stored `reelaboration_key`
  when re-derived in a **second, independent Lean process**; 0 errors, 0 not reached, 78 theorems,
  192.35 s. Mismatches were to be reported, never filtered out of the bank; there were none.

So the re-runnability limitation anticipated here did not materialise. The caveat that survives is
V05-25 below: a matching `reelaboration_key` is evidence the recipe reached the same state, not
proof of it.

**Open defects this design depends on**, all against the branching mechanism it uses:

* **V05-04 (HIGH, open)** — two concurrent live Lean sessions of one task carry the *same*
  `kernel_key` **and** `record_key`, one still `OPEN` on a 127-byte goal, one `CLOSED_VERIFIED` on
  `no goals`. HC-V0.6 opens one session per theorem; if theorems run concurrently, this is live.
* **V05-19 (LOW, open)** — a failed `reset()` leaves the previous episode's state attributed to the
  new session; `observe()` after `close()` returns a projection of a dead session reporting
  `TERMINAL_STATUS=OPEN`.
* **V05-25 (LOW, open)** — `KernelStateIdentity.rendered_under()` / `.from_dict()` mint an identity
  for any goal text with the kernel key intact.

These are not hypothetical: the assay's central mechanism is "one session, many branches", and
these three are defects in session-scoped state identity.

### 8.6 Cluster dependence and the effective sample size

§30.6: *"Steps from the same theorem/module/problem family are not independent."* Anchors drawn
from prefixes of the *same* theorem are strongly dependent (same goal lineage, same lemma
vocabulary, same author). Theorems in one mathlib file are dependent for the same reasons a step
lower down. The cluster unit is the **theorem file**, which subsumes theorem and is the more
conservative choice.

**The consequence that must not be lost:** the effective sample size is the number of *files*, not
the number of anchors. The realised bank is **223 anchors from 78 theorems in 75 files**, with 69
of the 78 theorems contributing the maximum 3 anchors. So the design effect has two layers — 223 → 78
by theorem, 78 → 75 by file — and the honest headline denominator is **75**, not 223. Reporting a
per-anchor interval as if anchors were independent is the granularity substitution of §4, in its
cheapest form; the estimator therefore reports the cluster interval as primary and may report an
anchor-naive interval only as an explicitly labelled diagnostic.

The 75-file structure is close to one theorem per file (78 theorems, 75 files), so file-level and
theorem-level clustering will be numerically similar here. That is a fact about *this* bank, not a
licence to use the theorem: the file remains the declared unit because it is the coarser one, and
because a bank that happened to draw several theorems from one file would silently inflate
precision under the theorem unit.

**The power analysis has now been run on clusters, and the answer is sobering.**
`docs/HC_V0_6_ANALYSIS_PLAN.md` §3.3, at α = 0.05 two-sided, power 0.80, baseline `p_accept ≈ 0.25`,
223 anchors in 75 files: the MDE is **12.2 / 14.7 / 17.8 percentage points** at ICC 0 / 0.2 / 0.5.
This study can see a 12–18 point swing in single-action acceptance and **nothing smaller**.
Detecting 10 points needs roughly twice this bank; detecting 5 points, about eight times it.

That is the single most important number for reading any null this experiment produces, and it is
why §9.10's MDE rule is normative rather than advisory. It also makes **O6 a live outcome before
the run**, not only after it: if the `delta_min` the Experimentalist can defend is smaller than the
MDE, the bank must be widened *before* freezing or O6 accepted in advance.

### 8.7 Attribution — open red-team defects that bear on HC-V0.6

`docs/HC_V0_5_REDTEAM.md`: 25 confirmed defects, 0 CRITICAL, 7 HIGH, under
`attack_suite_version hc-v0.5-redteam-2026-09-08`. §29's required wording is *"0 known critical
exploits under attack_suite_version X"*, never "shortcut-free". The following bear directly on this
experiment and are the ones to close or explicitly carry:

| id | sev | why it bears on HC-V0.6 |
|---|---|---|
| **V05-13** | MED | corrupts the primary endpoint's denominator (§7.3) — **blocking** |
| **V05-01 / V05-03** | HIGH | an oracle-fed cell would be byte-shaped like an autonomous one; `actor=SOLVER` is a string literal. The bank builder legitimately holds the reference proof in the same process, which is exactly the configuration the defect describes — **blocking for the artefact's credibility** |
| **V05-14 / V05-15** | MED | the leakage guard's floor and the believed declaration; §3.2 and §5 |
| **V05-04 / V05-19 / V05-25** | HIGH / LOW | session-scoped state identity, the branching mechanism (§8.5) |
| **V05-16** | MED | `harness_version` buys a silent re-draw (§2.13) |
| **V05-09** | MED | macro-cost hiding; `kernel_step_count` and tactic head must be recorded (§2.11) |

### 8.8 Single model, single prompt, single domain

One Solver checkpoint of `UNKNOWN` lineage, one prompt template, one tactic grammar, one formal
system, one library, one split. §25 Gate 6 requires ≥2 meaningfully distinct Solver families before
robustness may be claimed; §43 supplies the honest sentinel
`REPRESENTATION_EFFECT_MODEL_SPECIFIC`. Whatever HC-V0.6 finds, the correct default reading is
*this model, this prompt, this library* until replicated.

### 8.9 Statistical granularity of the replicate

With `k > 1` replicates per `(anchor, arm)`, "paired by anchor" and "exact McNemar on discordant
pairs" are not simultaneously well-defined: McNemar needs one binary outcome per side per pair, and
the data are `k` binary cells per side. The collapsing rule (per-anchor proportion, majority vote,
or per-replicate pairing) changes both the estimate and its variance, and choosing it after seeing
the data is the failure §20's discipline and §30.3's stopping rule exist to prevent. **The rule is
frozen in the preregistration, before any assay data exists.**

---

## 9. The exhaustive list of allowed outcomes

Every outcome below is declared **before** any data exists. No outcome licenses a design change
(§3.2, §44.4). Each carries a §43 sentinel.

The outcomes are evaluated **in order**. An earlier gate failing forecloses the later rows —
that is the point of ordering them. The order is: **O1 (noise floor) → O2 (sensitivity floor) →
O9 (byte sensitivity) → O3/O4/O5 (the reading)**, with O6, O7 and O8 as operational exits that can
fire at any point.

§9.10's MDE rule binds **every** row below that contains a null, without exception.

### 9.1 O1 — the assay is broken (C1 significant)

**Trigger.** `R_A` against `R_A` yields a Δ that trips the preregistered test.

**Licenses.** One statement: *the instrument does not measure what it claims to measure under this
runtime.* Sentinel `INSTRUMENT_INVALID` (§43); candidate lifecycle state `VOID_INSTRUMENT` (§21).
The measured C1 magnitude is itself a real, publishable engineering measurement of the runtime's
noise floor.

**Forbids.** **Everything else.** `Δ(R_A,R_B)` MUST NOT be reported, not even descriptively, not
even "for completeness". C2 MUST NOT be reported as a sensitivity floor, because a broken assay's
sensitivity is undefined. §10 of the Experimentalist's contract (§16.5) applies: *"A broken
instrument produces `VOID / INSTRUMENT_INVALID`, not a language ranking."*

**Note on the test's direction.** C1 is a *safety gate*, not a hypothesis. It must be evaluated in
the direction that makes tripping it **easy**, never with a multiplicity correction that makes it
harder — see the preregistration, which sets C1's α uncorrected and liberal precisely because a
conservative C1 would protect the headline result from its own instrument.

**If the runtime proves call-for-call deterministic** (§8.4), C1 is not a test at all: with `k = 1`
and byte-identical prompts, `Δ(R_A, R_A)` is identically zero. O1 then becomes unreachable, and
what is *reported* is the construction plus the determinism measurement that licenses it — never
"C1 passed", which would imply a test that was not run.

### 9.2 O2 — null with insufficient sensitivity (C2 weak)

**Trigger.** C1 passes; `Δ(R_A,R_B)` is not distinguishable from zero; **and** C2 fails to detect
the removal of the goal text at the preregistered threshold, or detects it only with an interval
wider than `delta_min`.

**Licenses.** *The assay could not detect the removal of the goal text, therefore it could not have
detected a representation effect of the size we care about.* Report the detectable effect size the
control establishes **and, separately, the realised MDE** (§9.10) — they are different quantities
and only the second bounds the null. Sentinel: `LANDSCAPE_NOT_ESTABLISHED` (§43).

**Forbids.** Any statement that resembles "no effect", "representation does not matter", or
"equivalent". §26 and §30 both make this explicit and `docs/HAMILTONIAN_CHESS_META_MDP.md` §4
requires an equivalence region *"so that 'no significant difference' can be distinguished from 'no
difference'"*. **A null under a blind instrument is uninformative, not negative evidence.**

### 9.3 O3 — informative null (C1 at zero, C2 strong, MDE ≤ `delta_min`, Δ within the equivalence region)

**Trigger.** C1 at zero (or zero by construction, §9.1); C2 detects the ablation with an interval
tighter than `delta_min`; the realised MDE is **≤ `delta_min`** (§9.10); and `Δ(R_A,R_B)`'s interval
lies inside the preregistered equivalence region `[−δ_eq, +δ_eq]`.

**Licenses.** *Under this EvaluationUniverse, this interface re-layout produced no effect on
single-action acceptance larger than `delta_min`.* This is a genuine scientific answer and §4.3
lists it as a valid outcome (*"no practically useful language effect is found under bounded
search"*). Sentinel: `NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND` (§43), scoped to **this gene,
this model, this endpoint** and nothing wider.

**Forbids.** Generalisation to other genes, other models, other endpoints, or to horizon. It says
nothing about representation in general — it says one interface gene did not move one one-step
endpoint on one model.

### 9.4 O4 — Δ favours `R_B` beyond `delta_min`

**Trigger.** C1 at zero; C2 strong; **C1b null and adequately powered** (§3.4, §9.9); `Δ` positive,
beyond `delta_min`, interval excluding it after the multiplicity policy.

**Licenses.** *Under this EvaluationUniverse, re-laying-out the same information raised the
probability that Lean accepts the next tactic by Δ [interval].* Claim tier: `VALID_CANDIDATE` plus
**one developmental local-assay reading**, on TRAIN, which is not `ProjectHidden` — §30.4 is
explicit that *"scout/search evidence is developmental"* and confirmation must be fresh. Sentinel:
none of §43's positive sentinels applies at this tier; report the effect with its universe.

**Forbids.** `FITNESS_CANDIDATE` (Appendix D requires fresh or selection-adjusted evidence, and
TRAIN is neither). `RSTAR`/`LSTAR`. Any horizon claim (§4). Any promotion, archive update, or use of
`Δ` as a fitness objective (§1.2, §35). And — the distinction that C1b makes and does not make —
a null C1b licenses *"the effect is not merely that bytes changed"*; it does **not** license
*"the effect is due to structure rather than familiarity or tokenization"*, which §8.1 and §8.2
show is unidentifiable at this design whatever C1b does.

### 9.5 O5 — Δ favours `R_A` beyond `delta_min`

**Trigger.** as O4, sign reversed.

**Licenses.** *The re-layout cost acceptance.* Because `R_A` is the pretraining-native surface,
this is **the outcome pure familiarity predicts** (§8.1) and it is therefore the *least*
informative significant result the design can produce. Report it as: an effect was measured, and
the design cannot attribute it to representation rather than familiarity. Sentinel: none; the
honest label is the §8.1 non-identification.

**Forbids.** *"Lean's native layout is a better representation."* That claim requires separating
representation from familiarity, which §24 Q-B and §26.6 say needs matched adaptation. HC-V0.6 has
none.

### 9.6 O6 — underpowered / insufficient clusters

**Trigger.** The bank yields fewer independent clusters than the frozen power analysis requires, or
the VOID rate (§7.3) removes enough cells to drop below it.

**Licenses.** A report of measured cost, variance, VOID rate and achieved `n_clusters` — which is
exactly what §47 Step 10 asks a V0 stage to hand off (*"Report measured V0 costs, variance, and
blockers so the scientific pilot can be designed from evidence"*). Sentinel:
`LANDSCAPE_NOT_ESTABLISHED`.

**Forbids.** Extending `n` after seeing the result (§30.3 stopping rule, design brief §7: *"No
design choice may be made after seeing an outcome"*). A run that lands here is **restarted under a
new manifest version** or abandoned — never topped up.

### 9.7 O7 — arm-dependent missingness

**Trigger.** C1 passes but the VOID rate differs by arm (§7.3 consequence 2).

**Licenses.** *The instrument's failure modes are arm-dependent, so `Δ` is biased by informative
missingness.* This is a finding about the instrument. Sentinel: `INSTRUMENT_INVALID`.

**Forbids.** Reporting `Δ` as an unbiased effect. Complete-case `Δ` may be shown only alongside the
missingness table and a bound on its direction.

### 9.8 O8 — environment blocked

**Trigger.** The Lean toolchain, the mathlib build, the Ollama runtime, or the branching mechanism
fails such that the bank cannot be played.

**Licenses.** A blocked-state report. Sentinel: `META_GAME_BLOCKED_BY_INTERACTIVE_TRAJECTORY_WORLD`
(§40.6) or `META_GAME_BLOCKED_BY_SEMANTIC_SUBSTRATE`, whichever the diagnosis supports.

**Forbids.** Substituting a stub, a cached response, or a smaller bank to produce a number anyway.
§43: *"The system MUST prefer explicit negative/blocked states over optimistic prose."*

### 9.9 O9 — the Solver is sensitive to byte perturbation as such (C1b non-null)

**Trigger.** C1 passes; C2 is strong; and `Δ(R_A, R_A_PRIME)` — a whitespace-only, information-
identical, bijective perturbation — lies beyond `delta_min` (§3.4).

**Licenses.** *Under this EvaluationUniverse, the Solver's single-action acceptance moved when the
bytes moved and nothing else did.* That is a genuine and reportable measurement about the Solver's
brittleness, and it is arguably more useful than the primary comparison. It also bounds every
`R_ONLY` assay this programme can run on this model: if a null perturbation moves the endpoint, no
byte-level intervention on this model can be attributed to what it *means* rather than to what it
*is*.

**Forbids.** **Attributing `Δ(R_A, R_B)` to structure.** The primary Δ may still be reported as a
measured total effect of the rendering, with its interval, but the sentence *"the re-layout helped
/ hurt because of how it organises the information"* is unavailable: a null change produced an
effect of comparable kind, so structure is not identified. Sentinel: `INSTRUMENT_INVALID` is **too
strong** here — the instrument works; it is the *claim* that is blocked — so the honest label is
`REPRESENTATION_EFFECT_MODEL_SPECIFIC` (§43) plus the explicit non-identification. Also forbids any
`RSTAR` vocabulary, which was already forbidden (§1.2).

### 9.10 The MDE rule — binding on every null in this document

Design brief §9.5, restated as a normative reporting requirement:

> **A null without a minimum detectable effect is not a result.** Every Δ reported as null MUST be
> accompanied by the MDE actually achieved at the **realised** `n`, `k` and `n_clusters` — not the
> planned ones — in the form: *"we could detect ≥ X points at the preregistered α and power; we
> observed Δ = … , CI […]."*

Three consequences that are easy to lose:

1. **C2 is not the MDE.** `R_ABLATED` establishing detectability of a 40-point drop says nothing
   about a 5-point one. C2 answers *"is the pipeline causally connected at all?"*; the MDE answers
   *"how small an effect could this run have seen?"*. Reporting C2 in the MDE's place is the most
   likely way this experiment produces a misleading null, and it is forbidden.
2. **The MDE is computed on clusters** (75 files, §8.6), on the realised non-VOID cell count, and
   under the frozen collapsing rule — not on 223 anchors and not on `n × k` cells.
3. **The MDE applies to C1b and C2 as well as to the primary.** A null C1b with an MDE wider than
   `delta_min` licenses nothing about structure; §3.4's first row requires C1b to be null *and*
   adequately powered.

If the realised MDE is larger than `delta_min`, the run is **O2** (or **O6**), whatever the point
estimate looks like.

---

## 10. What HC-V0.6 hands to whatever comes next

Whatever the outcome, the deliverables are: the measured runtime noise model and the `k` it forces;
the measured cost per cell and per anchor; the measured VOID rate by type; the achieved
`n_clusters` and the realised MDE; the anchored bank and its content hash; and the raw per-cell
outcomes (§30.7 — *"Keep raw task outcomes, intervals/posteriors, and paired effects—not only
means"*).

Three of those are already in hand and can be handed off even if the assay never runs:

| deliverable | value |
|---|---|
| anchored bank + content hash | 223 anchors / 78 theorems / **75 files**, `9fa6b6da…` |
| bank cost | 417.34 s total; 1.87 s per anchor including independent re-derivation |
| re-derivation rate | **223/223** in a second Lean process |
| branching correctness | 6/6 distinct children, parent intact |
| runtime determinism | **PROVISIONAL** — 120/120 and 30/30 byte-identical (§8.4); three of design brief §5's five questions still unanswered |

Those measurements, not `Δ`, are what a subsequent scientific pilot is designed from (§18.4,
§32.2, §41.2). `Δ` is one developmental reading on TRAIN under one model, at §25 Gate 1.

**Then stop and inspect.** Design brief §0: each arrow is a gate, and a later stage MUST NOT be run
on the strength of an earlier stage that did not pass. No HC-V0.7, no Pilot 1, no generation, no
fine-tuning, no RL Architect.

---

## 11. Known divergences between this specification and the code as it stands

Recorded here rather than left to be discovered at analysis time. All four were open when this
revision began on 2026-09-08; three closed while it was in progress, and the record is kept because
D1 is the shape of failure this design is most exposed to and will be exposed to again.

| # | divergence | status | detail |
|---|---|---|---|
| **D1** | `Arm.R_A_PRIME` meant *"the same renderer drawn twice"*, with `renderer_id` returning `"R_A"` | **CLOSED** | `arena/experiments/hc_v0_6/schema.py` now documents the four-arm intervention ladder and `Arm.renderer_id` returns `str(self.value)` — every arm has its own renderer |
| **D2** | the renderer registry had three entries and no whitespace perturbation | **CLOSED** | `arena/trajectory/representation.py`'s `ARMS` now registers `R_A_PRIME: WhitespacePerturbedNative()` alongside `R_A`, `R_B`, `R_ABLATED` |
| **D3** | `PREREGISTERED_FAMILY` Holm-corrected `{primary, C1, C2}`, which would move the *"assay is broken"* verdict in the direction that protects the headline | **REDUCED to a labelling question** | `arena/experiments/hc_v0_6/calibration.py` now makes every gate read the **raw, uncorrected** cluster-permutation p-value, with C1's α deliberately above the primary α. The Holm family remains the brief's four members and governs *effect claims* only. Preregistration §5 adopts this two-layer form |
| **D4** | `Comparison` declared *"the only three hypotheses"* | **CLOSED** | four members, including `C1B_WHITESPACE`; `C1_IDENTITY` correctly contrasts `R_A` with itself and is extracted by a split-half rather than by arm pairing |

**Why D1 is worth remembering after it is closed.** It was the one defect that would have failed
*silently and flatteringly*. A run against the old code would have produced four well-formed arms
and three well-formed comparisons; the arm labelled `R_A_PRIME` would have measured the runtime
noise floor — ≈ 0, and *exactly* 0 under determinism — and a result document written from design
brief §9.4 would have read that ≈ 0 as *"a null byte perturbation did not move the endpoint,
therefore `Δ(R_A, R_B)` is attributable to structure."* That is the strongest sentence this
experiment can produce, and it would have been licensed by a control that was never run. The
general form — **an arm whose name in the document and whose behaviour in the code disagree** — is
not detectable from the output, only from reading both. Preconditions B11 and B12 exist to force
that reading before every freeze, not only this one.

**One residual naming hazard, recorded so nobody has to rediscover it.** `renderer_id` now means
two different things in two places: `Arm.renderer_id` (`arena/experiments/hc_v0_6/schema.py`)
returns the **arm** id — `"R_A_PRIME"` — while the renderer object's own `renderer_id`
(`arena/trajectory/representation.py`) is `"hc-v0.6-R_A_PRIME-whitespace-v1"`. Both are correct in
their own namespace and neither is wrong; an artefact that carries both under one key would be.
Whichever the cell rows record, the artefact must say which.
