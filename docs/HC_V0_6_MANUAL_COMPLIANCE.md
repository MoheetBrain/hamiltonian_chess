# HC-V0.6 — manual-compliance audit

**Status: AUDIT of a design, not of a result. No assay data exists.**

Subject: the HC-V0.6 design as it stands on 2026-09-08, meaning
`docs/HC_V0_6_DESIGN_BRIEF.md` (including §9.1–§9.6), `docs/HC_V0_6_ANCHORED_DELTA_SPEC.md`,
`docs/HC_V0_6_PREREGISTRATION.md` (`v0.2-DRAFT`), the realised bank
`artifacts/trajectory/hc_v0_6_anchor_bank.json` (`9fa6b6da…`), and the code that implements them.

Authority: `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`, read unchanged as
its own §47 Step 2 requires. Every quotation below is verbatim; every section number is the
manual's unless prefixed with a document name.

## 0. How to read a verdict

| verdict | meaning |
|---|---|
| **COMPLIES** | the requirement is met by something that exists and can be pointed at |
| **VIOLATES** | the requirement is not met, and the gap is present now, not merely possible |
| **NOT APPLICABLE** | the requirement does not bind HC-V0.6 at this milestone |
| **CANNOT DETERMINE YET** | the requirement binds, and whether it is met depends on work that has not happened |

A verdict binds **the design**. A design that complies can still be executed non-compliantly, and
two of the findings below were precisely that — the documents right, the code not yet — and both
closed while this audit was being written.

`CANNOT DETERMINE YET` is not a soft pass. Every one of them is a gate that must close before the
first Solver call, and the preregistration's §11 is where they are enforced.

---

## 1. Verdict summary

**14 of 14 §48 prohibitions: COMPLIES.** The project is not doing any of the things §48 forbids.

Across the wider audit: **1 VIOLATES; 6 CANNOT DETERMINE YET** (F5, F6, F9, §14.4, §18.4, prompt
injection); **2 closed during this audit** (F2, F3); **2 recorded deviations** (universal action
IDs, and prompt-token measurement in place of matching); the remainder COMPLIES or NOT APPLICABLE.

**A note on F2 and F3.** Both were open and blocking when this audit began on 2026-09-08 and both
were closed by parallel work while it was in progress. They are kept in full, marked CLOSED, because
the *reasoning* is what makes the current code correct rather than accidentally correct — and
because F2's failure mode (an arm whose name in the document and whose behaviour in the code
disagree) is invisible in the output and will recur.

Ranked by seriousness — the full argument for each is in §5:

| # | finding | verdict | section |
|---|---|---|---|
| **F0** | **The realised bank can detect a 12–18 point change in acceptance and nothing smaller.** Not a manual violation — §30.2 is doing its job by exposing it — but it is the finding with the largest practical consequence: the effects a layout change plausibly produces are below the instrument's floor, and every choice of `delta_min` open to the Experimentalist is either vacuous, underpowered, or circular | COMPLIES, and the design must act on it | §5.5 |
| **F1** | **No `SourceAdmissionRecord` exists for the LeanDojo TRAIN source HC-V0.6 draws its 223 anchors from.** §18 says every admitted source SHALL have one; the schema exists; `spec/implementation/HC_V0_MANIFEST.yaml` records `source_admission_record: UNKNOWN`; there is no instance anywhere in the repository | **VIOLATES §18** | §4.7 |
| **F2** | `R_A_PRIME` meant two different things in the design and in the code — a second draw of the baseline, versus design brief §9.4/§9.6's whitespace-perturbed arm. A run would have reported a **noise floor** under the name of a **byte-sensitivity control**, and would have looked correct | **CLOSED during this audit** (was blocking) | §5.2 |
| **F3** | The estimator Holm-corrected the safety gates, making the "assay is broken" verdict *harder* to reach — the protective direction | **CLOSED during this audit** (was blocking) | §5.3 |
| **F4** | §26.2 lists "compute regime" among the quantities `R_ONLY` holds fixed. Prompt tokens are **measured, not matched** | COMPLIES, recorded deviation | §3.2 |
| **F5** | §29 requires a shortcut detector to receive *"the exact model-visible surface"*. The bank's leakage pass ran on the Lean state, not on the four rendered prompts | CANNOT DETERMINE YET | §3.5 |
| **F6** | §16 role separation is not enforced: one agent context proposes the candidate, builds it, and writes the manifest that judges it. §16.1: *"MUST NOT approve its own semantic gate"* | CANNOT DETERMINE YET | §4.4 |
| **F7** | No `LanguageCandidate` (§12.1) exists for any arm; `R_ABLATED`'s `P_CHANGE` label is derived from the **declaration**, not from **genes** as design brief §2 asks, because the gene table cannot express goal visibility | COMPLIES by a stronger mechanism; the divergence is now recorded | §3.1 |
| **F8** | §23's central prediction (`Δ_L(20) > Δ_L(1)`) goes untested for a second consecutive milestone. Not a violation — the deviation is recorded — but it is a drift signal about the programme, not about this experiment | NOT APPLICABLE, with a warning | §4.6 |
| **F9** | Five of §30.3's nine fields are incomplete — `delta_min`/`δ_eq`, `k` and the precision target, the replicate-collapsing rule, the α values, and `evaluation_universe_hash`. Legal while DRAFT; freezing with any of them open would violate §30.3 | CANNOT DETERMINE YET | §3.6 |

**Nothing in this audit found a soundness defect.** No design element lets a candidate change truth
conditions, reach a future proof state, or profit from a verifier failure. The failures found are of
*power* (F0), *bookkeeping* (F1), *naming* (F2), *statistical policy in code* (F3) and *process*
(F6).

**If only one thing is read from this audit, read F0 and F1.** F0 decides whether the experiment can
answer anything; F1 is a `SHALL` that takes an hour to satisfy and has been open since the source
was admitted.

---

## 2. §48 — THINGS THE PROJECT MUST NOT DO NEXT, item by item

§48 is fourteen prohibitions. Each is quoted verbatim and given a verdict.

| # | §48 prohibition | verdict | one-line evidence |
|---|---|---|---|
| 1 | *"invent `HML_V4` by hand"* | **COMPLIES** | HC-V0.6 defines no language. `R_B` is a re-layout of Lean's own pretty-printed state with an inverse; there is no new lexicon, grammar, ontology or action set |
| 2 | *"generate 100 hand-designed languages"* | **COMPLIES** | one variant (`R_B`), plus a whitespace null (`R_A_PRIME`) and a non-representation control (`R_ABLATED`). §20.2 asks for one gene family per child in early causal reconnaissance; `R_B` changes exactly one, an interface (`I`) gene (§10.9) |
| 3 | *"run 100 AI agents because 'more agents' sounds evolutionary"* | **COMPLIES** | one Solver, one call per cell, `controller_id = NULL_CONTROLLER_SINGLE_CALL_V0`, `max_retries = 0`. §16.9 requires only three strategic roles and HC-V0.6 uses one |
| 4 | *"train an RL Architect immediately"* | **COMPLIES** | no training of any kind. Adaptation budget 0, zero-shot, no fine-tuning. Design brief §7 and preregistration §8 forbid it explicitly in every outcome |
| 5 | *"resume a scientifically obsolete founder tournament automatically"* | **COMPLIES** | nothing from the founder tournament is invoked. §35's *"DO NOT RUN BY DEFAULT"* is respected: no unfinished tournament is resumed because its code exists |
| 6 | *"build another micro-benchmark as the global objective"* | **COMPLIES — and this is the closest call in §48** | `p_accept` at one action **is** a micro-probe; §35 demotes exactly this class to diagnostic and says such probes *"SHALL NOT define the global language reward."* Spec §1.2 admits it at diagnostic tier and bars it from becoming a fitness objective; preregistration §8 forbids *"any use of `Δ` as a fitness objective or global language reward"* in every outcome. The prohibition is satisfied **by the standing rule, not by the design being immune** — see §5.6 |
| 7 | *"download a million problems before proving the trajectory adapter works"* | **COMPLIES** | nothing was downloaded. 40,000 records were scanned from a corpus already present; 223 anchors were kept. The adapter was proven first — HC-V0.5 ran a live Solver through it, and `research/phase10/branching/` measured the branching property this design rests on |
| 8 | *"optimize tokenizer and language simultaneously in V0"* | **COMPLIES** | `τ` is the served model's own tokenizer, identical in all four arms, never trained, never changed. No `TAU_CHANGE`. §10.10 defers candidate-specific tokenizer training and HC-V0.6 does not touch it |
| 9 | *"co-evolve curriculum and language before local measurement works"* | **COMPLIES** | no curriculum. The anchor set is fixed before the first call, selected by a deterministic depth rule, and §16.8's Curriculum Designer is disabled. HC-V0.6 *is* the local measurement |
| 10 | *"rewrite Lean/OpenMath/MMT/SymPy/Julia/JAX"* | **COMPLIES** | Lean 4.10.0-rc1 is used unmodified via a REPL. §17.4's backend-native truth is used precisely so nothing is forced through a canonical schema — `docs/CANONICAL_VNEXT_PILOT.md` mapped 0 of 368 real Lean states losslessly, and HC-V0.6 compares no states by text |
| 11 | *"let candidates change the verifier"* | **COMPLIES** | a renderer produces a `Mapping` shown to the Solver and touches nothing else. The elaborator adjudicates acceptance; a **separate** re-elaboration plus a three-member axiom allow-list adjudicates closure. `sorry` and friends are refused at three layers; `native_decide` fails the allow-list via `Lean.ofReduceBool` (RT-01, closed with before/after evidence) |
| 12 | *"let candidates access future proof states"* | **COMPLIES** | the bank segregates `solver_visible` from `oracle`; `oracle` holds the prefix tactics, the whole recorded proof and the declaration span at `actor=REFERENCE`; `assert_no_oracle_leak()` is the tripwire; `VerifiedTask.__init__` raises `ReferenceProofExposureError`. The bank's anchor-level leakage pass found **0 leaks in 223 anchors** under `TACTIC_IN_STATE_BEFORE`, `FULL_NAME_IN_STATE`, `LEAKS_PREFIX_TACTIC_IN_STATE`, and 29 problems were dropped before derivation. The residual gap is F5, which is about *where the scan ran*, not about the suffix reaching the Solver |
| 13 | *"use human readability as the winner criterion"* | **COMPLIES** | the criterion is `p_accept` — whether Lean's elaborator accepts the proposed tactic. No human judges any rendering. §4.6 is satisfied for the *criterion*; note honestly that the *candidate* `R_B` was designed by human intuition about layout, which §45 permits at this scale (*"SHOULD NOT hand-design hundreds"*, and this is one) but which means `R_B` is not evidence that search would find it |
| 14 | *"search indefinitely until novelty appears"* | **COMPLIES** | there is no search. Fixed `n`, no interim looks, no extension after seeing the result, and §41.5's stop condition is written into preregistration §7. A run that lands underpowered is restarted under a new manifest or abandoned — never topped up |

**§48 verdict: 14/14 COMPLIES.** The one that deserves ongoing attention is #6, and it is a
prohibition on what happens *next*, which no document can enforce on its own.

---

## 3. The named checks

### 3.1 §6.30–§6.34 and §17.6 — horizon vocabulary, and granularity substitution

**Verdict: COMPLIES, and this is the strongest part of the design.**

§17.6 requires `ObservedTraceLength`, `EpisodeLength`, `DependencyDepth` and `MinimalProofLength`
to be *"reported separately"*, and warns: *"Do not call a 50-step recorded proof a '50-step required
reasoning task' without evidence of necessity/minimality."*

| term | § | HC-V0.6 | evidence |
|---|---|---|---|
| `ObservedTraceLength` | 6.30 | recorded per anchor, histogram in the bank (3 ×76 … 21 ×3), used **only** by the bank builder's prefix rule | bank `stats.observed_trace_length_histogram`; spec §4 |
| `EpisodeLength` | 6.31 | **1** in every cell, by design. The bank records `episode_length: 0` at an anchor because an anchor is a state, not an episode | bank `sampling.episode_length`; spec §4 |
| `KernelStepCount` | 6.32 | `0` at derivation; recorded per accepted step at assay time, **never used as a horizon** | bank `sampling.kernel_step_count`; spec §2.11 |
| `DependencyDepth` | 6.33 | **`UNKNOWN`**, not proxied | bank `sampling.dependency_depth` |
| `MinimalProofLength` | 6.34 | **`UNKNOWN`** for every anchor | bank `sampling.minimal_proof_length` |

Four things make this a real compliance rather than a stated intention:

1. The bank carries its own `sampling_proxy_note` on **every anchor** and in its `stats` block:
   *"prefix_length and observed_trace_length are SAMPLING PROXIES, never reasoning difficulty…
   a shorter proof may always exist."* The disclaimer travels with the data, so a downstream reader
   who never opens this document still meets it.
2. `UNKNOWN` is stored as the string `UNKNOWN`, not as a null or a zero, so it cannot be silently
   arithmetic'd.
3. Spec §4 contains the paragraph that forecloses the substitution in advance: an anchor at prefix
   position 7 of a 12-tactic proof is *not* "step 7 of 12 in difficulty", and selecting deeper
   anchors *"makes it a different sample of `EpisodeLength = 1` states"*, not a longer horizon.
4. Preregistration §7.1 now forbids the specific subgroup analysis that would smuggle the
   substitution back in — `depth_class = INITIAL` (78) vs `MID_PROOF` (145), which is available in
   the bank and reads exactly like a depth interaction. It is reported descriptively and never
   entered into a Δ.

**One residual risk, named rather than dismissed.** `depth_class` exists as a field. Fields that
exist get analysed. The prohibition is a document, and documents are weaker than absence.

*Also under §12.1 (F7).* No `LanguageCandidate` record with §12.1's eighteen required outputs is
produced for any arm — no `genome`, `genome_hash`, `parent_ids`, `mutation_ids`, `creation_seed` or
`status`. HC-V0.6 runs no candidate lifecycle (§21), no archive and no generation, so §12.1's
artefact has no consumer here; but the consequence is that design brief §2's requirement that
`R_ABLATED` be labelled `P_CHANGE` *"from its genes"* is **not** what happens.
`derive_intervention_class` derives it from the renderer's **declared slot set** — `R_ABLATED`'s is
a strict subset of the baseline's — and `arena/trajectory/representation.py` states plainly that
the gene table cannot express goal visibility today (`GOAL_VISIBILITY_GENE`). Declaration-derivation
is the stronger check of the two, because it cannot be defeated by writing a different gene name;
it is nonetheless a different mechanism from the one specified, and V05-17's underlying defect
(`gene_changes` never checked against genomes) is bypassed rather than closed. Recorded in
preregistration B5.

### 3.2 §12.3 and §26.2 — does the `R_ONLY` claim actually hold for `R_A` vs `R_B`?

This is the load-bearing question of the whole experiment, and it has two halves.

#### (a) The parity half — **COMPLIES**

§12.3 requires an `R_ONLY` candidate to **prove** four things. §26.2 requires eleven quantities held
fixed. Both are met, and by mechanism rather than by declaration:

| requirement | mechanism |
|---|---|
| same truth state (§12.3, §26.2) | **by construction**: all arms step the *same live `state_id`* in the *same* session by branching. `research/phase10/branching/` measured it — 6/6 distinct children from one parent, parent text unchanged after all branches, branch-from-child 6/6, and the README records that an earlier probe proved nothing because 26 of 28 tactics were rejected. Not a hash comparison: one object |
| same visible semantic inventory (§12.3) | `DeclarationDerivedRenderer.render` is `present(declare_information(envelope))` and subclasses **cannot override `render`** (`__init_subclass__` raises); `present` never receives the envelope. A renderer physically cannot show what it did not declare. The V05-15 counterexample — declare less than you render — is unwriteable in the base class |
| nothing removed | `invert(R.render(s)) == R_A.render(s)` byte-for-byte at every state; failure is `DEAD_INFORMATION_PARITY` (§12.4) and *"No dead candidate receives Solver compute"*. **Measured over the realised bank** (`docs/HC_V0_6_REPRESENTATIONS.md`): `R_A_PRIME` 223/223, and `R_A` vs `R_A_PRIME` types as `R_ONLY` on all three of the declared-slot, declared-value and bijection checks |
| `R_A_PRIME` declares the *envelope's* text, not the perturbed text | so `R_A`/`R_A_PRIME` parity is exact rather than dependent on how `normalize_goal_text` happens to treat a trailing space. `arena/trajectory/representation.py` states this and warns that an identity computed from the *rendered* bytes would differ — a real trap, documented at the point where someone would fall into it |
| same action semantics / cardinality | one free-form Lean tactic string, same grammar sha256 `9b25cba2…`, same parser, same Lean, in every arm |
| tokenizer, Solver, controller, tools, training examples, evaluation tasks, verifier | identical by construction — §2.4–§2.9 of the spec, one digest, `verify_served()` recorded, no tools, no adaptation, same anchor in the same run |

Spec §3.2 also corrects a real error in the design brief's own contract: `invert ∘ render == R_A.render`
is a *left inverse*, which forbids removal but permits **addition**. The corrected contract adds a
structural condition — the layout function receives only the baseline rendering or only the
declaration — and that condition is the one the code actually implements. This is a case of the
specification catching its own brief.

#### (b) The tokenization half — **COMPLIES, and the reasoning must be argued, not asserted**

The challenge: `R_B` changes the byte layout, therefore changes what the fixed tokenizer segments,
therefore changes the token sequence. §26.6 says *"changing the tokenizer is `TAU_CHANGE` or
`JOINT`."* Is `R_B` a `TAU_CHANGE`?

**No.** Three steps:

1. **§6.13 defines `τ` as an object, not an output.** *"The tokenizer or low-level model encoder."*
   A tokenizer is a function: a vocabulary, a merge table, an encoding procedure. HC-V0.6 changes
   none of them. The same `τ` is applied to both arms.
2. **§26.2 requires the tokenizer held fixed; it does not require the token sequence held fixed** —
   and could not. Any change of bytes changes the sequence under any tokenizer. A reading of §26.2
   on which `τ(R_B(s)) ≠ τ(R_A(s))` disqualifies the comparison makes `R_ONLY` **empty**: no two
   distinct renderings could ever be compared, and §6.36's `RSTAR` — *"reserved for a
   representation-only `R_ONLY` search"* — would name an impossible object. A reading that empties a
   manual's own class is the wrong reading.
3. **§26.6's actual concern is a different one.** Read in full, it is about *frequency priors*:
   *"A fixed pretrained tokenizer gives different segmentation/frequency priors to English words and
   invented symbols."* Its remedy is not to forbid the comparison but to bound the claim —
   *"claims about intrinsic morphology require matched-adaptation and tokenization/frequency
   controls"* — and only then, separately, *"changing the tokenizer is `TAU_CHANGE` or `JOINT`."*
   Those are two sentences about two different acts.

**Verdict: `R_ONLY`. But the honest statement is stronger than "no confound", and it is a finding.**
The causal path runs `R → bytes → τ → tokens → π → tactic → Lean`, and **there is no path from `R`
to the outcome that avoids `τ`**. Segmentation is therefore a **mediator**, not a confounder: it
lies on the causal path and must not be adjusted away. What `Δ(R_A, R_B)` estimates is the *total*
effect of the rendering, tokenization consequences included. Two sentences are consequently
unavailable, in every outcome: *"the effect is due to structure, not tokenization"* (unidentifiable
here) and *"the effect is intrinsic to the representation"* (§26.6 requires matched adaptation,
which HC-V0.6 does not run). Both are in preregistration §8's universal prohibition list.

#### (c) The one §26.2 quantity that is **not** held fixed — F4

§26.2's list includes **"compute regime"**. HC-V0.6 matches the sampling half exactly (one call, no
retry, identical decode, identical caps: `num_ctx = 32768`, `num_predict = 128`, neither binding)
and does **not** match the token half: a re-layout changes prompt length, and prompt tokens are
**measured and reported per arm**, not equalised.

**Verdict: COMPLIES, as a recorded deviation.** The same argument as (b) applies — a reading on
which token count must be equal makes `R_ONLY` empty. But it is the single §26.2 quantity where
HC-V0.6 substitutes measurement for matching, and it is not cost-free:
`docs/HAMILTONIAN_CHESS_META_GOAL.md` §7a names *"a language that merely says less is not a better
language"* as a control the nearest prior work fails. Spec §8.3 makes per-arm token distributions
and `Δ` on tokens mandatory beside `Δ` on `p_accept`, and requires that a win at materially higher
token cost be reported as a different result from a win at parity. That is the most this design can
do; a token-matched design is a different experiment.

### 3.3 §27 — projection admissibility, P0–P3, for each of the four renderers

**Verdict: COMPLIES. Nothing reaches P3, and nothing reaches P2 or P1 either.**

Every slot every renderer exposes is read directly from the `BackendStateEnvelope` the live Lean
session produced. No slot is derived, summarised or computed; the derivation algorithm is field
access and the derivation budget is O(1).

| slot | class | `R_A` | `R_A_PRIME` | `R_B` | `R_ABLATED` |
|---|---|---|---|---|---|
| `GOAL_TEXT` | **P0** | ✓ verbatim | ✓ same characters under a different whitespace convention | ✓ same characters, re-laid-out | **withheld** |
| `GOAL_COUNT` | **P0** | ✓ | ✓ | ✓ | ✓ |
| `BACKEND_KIND` | **P0** | ✓ | ✓ | ✓ | ✓ |
| `BACKEND_STATE_ID` | **P0** | ✓ | ✓ | ✓ | ✓ |
| `PP_SCOPE` | **P0** | ✓ | ✓ | ✓ | ✓ |
| `STEP_INDEX` | **P0** | 0 | 0 | 0 | 0 |
| `ATTEMPTS_REMAINING` | **P0** | constant | constant | constant | constant |
| `TERMINAL_STATUS` | **P0** | `OPEN` | `OPEN` | `OPEN` | `OPEN` |

* **P1 — local deterministic structure: not used.** No binder/use links, no dependency edges, no
  typing relations, no precondition status.
* **P2 — bounded derived summaries: not used.** No summary of any kind is computed.
* **P3 — solution-dependent / future-dependent: NOT REACHED**, and the five §27 negatives are each
  answered false in spec §5: no answer label (`ReferenceProofExposureError`, `seal_reference_proof()`
  retains only counts and digests, `__slots__`), no future state (the suffix is never rendered; the
  prefix replay is `actor=REFERENCE` oracle-side work), no hidden solution, no minimum proof path
  (`MinimalProofLength` is `UNKNOWN` and nothing consults it), no candidate correctness (no arm
  learns any outcome, its own or another's).

The three `R_ONLY` renderers are **bijections of one another's output**, so their projection
identities are identical by construction — a bijection cannot change the projection class of a
slot. `R_ABLATED` *removes* `GOAL_TEXT`, which lowers the exposed information and is why it is
`P_CHANGE`; removal cannot introduce answer or future-state information, so §12.3's admissibility
audit for it is satisfied in the safe direction.

**Two honest qualifications, neither a P3 breach.** `PP_SCOPE` carries the theorem's namespace: P0,
because Lean itself rendered it, but under `LIKELY_PRETRAINING_EXPOSURE` a namespace is a recall
cue. It is identical in all four arms, so it threatens the *level* of `p_accept`, never the
*contrast*. And V05-14's 6-byte leakage-guard floor remains open (§3.5).

### 3.4 §28 — the verifier trust contract

**Verdict: COMPLIES.** All nine §28 fields are now declared in spec §7 as an explicit block:
`verifier_id`, version/domain, trust assumptions, accepted constructs, unsupported constructs,
timeout semantics, `UNKNOWN` semantics, error semantics, replay/rechecking method. (They were
substantively present before this revision but not written as the nine §28 fields; that is now
fixed.)

Three points carry the weight:

**The two adjudicators are kept apart, and the design brief blurs them.** Acceptance is decided by
Lean's **elaborator**; closure is decided by the **kernel** plus the axiom allow-list, in a
*separate re-elaboration* of the finished script. The brief calls the primary endpoint
"kernel-decided". It is not: an accepted-but-not-closing step is elaborator-decided, and no axiom
check exists to run on it because nothing has been proved. The defensible phrasing for `p_accept`
is *"accepted by the Lean elaborator"*. Spec §7.1 makes this correction explicitly.

**The allow-list is what closed RT-01, and its shape is right.**
`ALLOWED = { Classical.choice, Quot.sound, propext }`. RT-01 was the previous suite's CRITICAL:
`native_decide` produced `CLOSED_VERIFIED, reward 1.0, verified true`. The same attack now produces
`FAILED, reward 0.0, verified false, untrusted_axioms: ["Lean.ofReduceBool"]`. An allow-list fails
closed on the *next* exotic axiom; a deny-list would have to anticipate it. `rfl /-` — an
unterminated comment that comments out the `#print axioms` line — therefore also fails closed.

**§28's four inequalities are implemented as a disposition table, not as prose.** `UNKNOWN != FALSE`,
`TIMEOUT != FALSE`, `TOOL_ERROR != MATHEMATICAL_INVALID`, and neither success-on-crash nor
failure-on-infrastructure. Spec §7.3 assigns every observable outcome to numerator, denominator or
**VOID**, with three mandatory consequences: a VOID cell is re-run once and then drops the anchor's
pair **symmetrically across all arms**; VOID rates are reported per arm and arm-dependence is
**tested** (outcome O7); and **V05-13 is blocking** — today a dead model runtime is counted in
`parse_failures` and in neither `environment_errors`, which puts a transport failure straight into
the Solver's column and corrupts the denominator. Without that table, every timeout would silently
become a mathematical non-accept, which is a direct §28 violation. **The table exists; the code
behind it does not yet** (preregistration B2, B10).

### 3.5 §29 — which Goodhart channels this design opens and closes

**Verdict: COMPLIES on the channels it can close; CANNOT DETERMINE YET on two.**

§29 requires the assurance wording *"0 known critical exploits under attack_suite_version X"*, never
"shortcut-free". The standing value is `hc-v0.5-redteam-2026-09-08`: **25 confirmed defects, 0
CRITICAL, 7 HIGH**. A re-run against the HC-V0.6 bank is preregistration P13 and has not happened —
and the bank's own leakage pass is **not** a red-team suite.

| §29 attack class | HC-V0.6 |
|---|---|
| answer position, semantic ID leakage, label leakage | **closed** — there is no answer, no label and no ID in the input; the Solver sees an open goal state |
| lexical overlap, cross-split identifiers | **closed** — TRAIN only; the four sealed splits are recorded unread in the bank manifest |
| theorem/module identity | **closed as a leak, retained as a cluster** — `file_path` is the resampling unit; it is not in the prompt |
| **length / token patterns** | **OPENED — this is the treatment.** `R_B` changes prompt length. Mitigation: tokens measured per arm, `Δ` on tokens reported beside `Δ` on `p_accept` (§3.2c) |
| **field ordering** | **OPENED — this is also the treatment.** §29 lists field ordering as an *attack* class; HC-V0.6 manipulates it deliberately. The Refuter must therefore check something new: that `R_B`'s ordering does not correlate with the correct tactic across the bank. Nothing has checked this |
| binder renaming, alpha-equivalence, irrelevant reorderings | **closed by the bijection** — all three would break `invert(R.render(s)) == R_A.render(s)` |
| duplicated information | **closed by the bijection** — a duplicate is either invertible (and identical information) or not (and rejected) |
| malformed syntax, parser permissiveness | **closed** — strict single-JSON-object parse; parse failure is a mandatory per-arm secondary endpoint, not an absorbed error |
| **macro-cost hiding** | **OPENED by the endpoint's shape.** V05-09: `constructor <;> simp <;> omega` is allowed and costs `kernel_step_count = 1`. Mitigation: §13.1 macro accounting — tactic head and `kernel_step_count` recorded per accepted step — and `p_accept`, not `p_close`, is primary. If `TacticPolicy` stays `record_only`, `p_close` measures mathlib's automation more than the representation, and must be read that way |
| verifier crashes / timeouts | **closed** by the §7.3 VOID table, *conditional on V05-13 closing* |
| reward-shaping exploits | **closed** — no shaping. §14.5 and §22.1 are satisfied trivially: the endpoint is a binary elaborator verdict |
| retrieval / tool asymmetry | **closed** — no tools in any arm |
| **prompt injection** | **CANNOT DETERMINE YET.** A mathlib goal state is model-visible text drawn from a public corpus. Nothing has scanned the 223 rendered surfaces for text that reads as an instruction. Low prior, unchecked |
| **"the exact model-visible surface" rule** — F5 | **CANNOT DETERMINE YET.** §29: *"A shortcut detector making claims about model-visible cues MUST receive the exact model-visible surface, not a privileged canonical representation."* The bank's leakage pass ran on `solver_visible.goals_pp` — the Lean state. The model sees `template(R.render(state))`, four different surfaces. For the three bijective arms the *information* is provably identical, so the state-level scan is informative; but the literal requirement is about the surface, and the scan has not been run per arm on the rendered prompt |

**Two channels this design closes that are worth naming**, because they were open in HC-V0.5:
the retry channel (V05-07: a declared one-retry budget absorbed 6 live rejections when `skip` is
interleaved) is closed by `max_retries = 0`; and the position channel is converted from a confound
into noise by randomising arm order within each anchor from a recorded seed.

### 3.6 §30 — every statistical rule

| rule | verdict | evidence |
|---|---|---|
| **§30.1** retain task-level paired outcomes and theorem/problem-family identifiers | **COMPLIES** | one row per `(anchor, arm, replicate)`; every row carries `reelaboration_key`, `problem_id`, `theorem_full_name`, `file_path` |
| **§30.2** tiny samples are smoke only; scientific `n` justified by minimum practical effect, power/precision, dependence and multiplicity | **CANNOT DETERMINE YET — but now quantitatively** | three of the four inputs are computed (`docs/HC_V0_6_ANALYSIS_PLAN.md` §3.3): at α = 0.05, power 0.80, baseline ≈ 0.25, 223 anchors in 75 files, the **MDE is 12.2 / 14.7 / 17.8 points** at ICC 0 / 0.2 / 0.5. Detecting 10 points needs ≈ twice the bank; 5 points, ≈ eight times. `delta_min` remains open, and **if the defensible value is below ≈ 15 points the bank is inadequate as built** — which must be settled before freeze, not discovered after (§5.5) |
| **§30.3** nine required manifest fields | **CANNOT DETERMINE YET (F9)** | preregistration §0.1 tabulates all nine. **Four are complete** — primary endpoint, cluster unit, stopping rule, allowed outcomes. **Three are partial** — sample size (`n = 223`, `n_clusters = 75` filled; `k` and precision target open), paired method (estimator and bootstrap filled; collapsing rule open), multiplicity (policy filled; α values open). **Two are open** — `delta_min`/`δ_eq` and `evaluation_universe_hash`. Every one names its filler. **Legal while DRAFT; freezing with any open would violate §30.3** |
| **§30.4** winner's curse; scout evidence is developmental; confirmation must be fresh and must not guide selection | **COMPLIES** | TRAIN is not `ProjectHidden` (§6.28) and the spec says so in §2.1. Outcome O4 licenses `VALID_CANDIDATE` plus *one developmental reading*, never `FITNESS_CANDIDATE`. The sealed splits are untouched, so a future confirmation set still exists |
| **§30.5** discovery/evaluation separation | **COMPLIES** | there is no discovery step. One preregistered comparison, no candidate selection, no threshold tuned on this data. Preregistration §7.1 forecloses the post-hoc subgroup route |
| **§30.6** cluster dependence | **COMPLIES** | cluster = mathlib **file**, the coarser unit, subsuming theorem. 223 anchors → 78 theorems → **75 files**; 69 of 78 theorems contribute the maximum 3 anchors, so the design effect is large and real. The cluster bootstrap resamples *files with replacement carrying all their anchors and cells*; an anchor-naive interval may appear only as a labelled diagnostic |
| **§30.7** store raw outcomes, intervals and paired effects, not only means | **COMPLIES** | `CellOutcome` is the atom and `SCHEMA_VERSION` binds it; every reported number is a function of the cell table |

Two statistical decisions in the preregistration go **beyond** §30 and are recorded as deviations
from the design brief rather than from the manual:

1. **The Holm family is `{primary}` alone.** The brief specifies four members. Correcting C1 (noise
   floor), C1b (byte sensitivity) or C2 (sensitivity floor) makes each *harder* to trip — and each
   tripping is a **block** on a claim, not a claim. Multiplicity control exists to suppress false
   positives about the science; applying it to instrument-validity gates suppresses true negatives
   about the instrument. §29's fail-closed discipline and §43's *"MUST prefer explicit
   negative/blocked states over optimistic prose"* are what the deviation serves. **Owner sign-off
   required before freeze** (preregistration P16).
2. **C1b is analysed in two directions with two procedures**: a liberal, uncorrected significance
   test in its blocking direction, and a **TOST against `δ_eq`** in its licensing direction. Reading
   a non-significant C1b as "no byte sensitivity" is the absence-of-evidence error the equivalence
   region exists to prevent.

And one reporting rule that §30 does not require but the design brief does, now normative:
**§9.5's MDE rule** — *a null without a minimum detectable effect is not a result*, computed on the
**realised** clusters and cells, with C2 explicitly **not** serving as the MDE.

### 3.7 §25 — which gate HC-V0.6 actually sits at, and whether it is described honestly

**Verdict: COMPLIES — after this revision. Before it, the documents were silent on the ladder.**

§25's rungs are defined by **adaptation**, not by statistical care:

* **Gate 0** — *"No model calls. Schema, compile, truth fidelity, intervention declaration, required
  parity, action lowering, leakage/assurance."* HC-V0.6 has **done** this work: bijection checks,
  declaration-derived rendering, `derive_intervention_class`, the bank's leakage pass, action
  lowering into `session.step`.
* **Gate 1** — *"cheap scout. Catastrophic unreadability and gross failure detection. **MUST NOT
  crown a language.**"*
* **Gate 2** — *"short matched adaptation"*, which HC-V0.6 does not run (adaptation budget 0).

**HC-V0.6 sits at Gate 1.** It cannot be Gate 2 or above because §25's higher rungs require
adaptation, and HC-V0.6 is deliberately zero-shot — which also places it squarely and only in §24's
**Q-A regime**, where the manual itself warns *"Controlled English may dominate because of
pretraining familiarity."*

Being more disciplined than the rung demands does not promote the rung. HC-V0.6 has a preregistered
endpoint, cluster-aware intervals, four arms, a noise floor and a sensitivity floor — more than Gate
1 asks for, and none of it substitutes for the fresh project-hidden data, strong incumbent controls,
example-matched adaptation, selection-bias protection and independent rerun that Gate 5 requires and
that HC-V0.6 has none of. Spec §1.3 now states the placement and quotes the constraint; preregistration
§8 forbids presenting a Gate 1 number as though it settled which rendering is better.

---

## 4. Other requirements that bear on HC-V0.6

| § | requirement | verdict | evidence |
|---|---|---|---|
| **3.2 / 44.4** | after scientific exposure a manifest may be aborted but not edited | **COMPLIES** | preregistration §0 and §12 state it twice, name the exposure boundary (the first Solver call against the bank), and distinguish pre-freeze revision — which is what `v0.2-DRAFT` is — from post-exposure amendment, which is forbidden |
| **3.3** | evidence immutability; corrections are additive | **COMPLIES** | the bank records mismatches rather than filtering them (*"Mismatches are reported, never filtered out of the bank"*); there were none. The branching README preserves the earlier probe that proved nothing, and says why |
| **4.4** | mathematical truth is not a contestant | **COMPLIES** | renderers produce a `Mapping`; Lean adjudicates; the axiom allow-list bounds what "closed" can mean |
| **4.5** | evidence before claims | **COMPLIES** | maximum reachable tier is `VALID_CANDIDATE`; `RSTAR`/`LSTAR` forbidden in every outcome |
| **4.6** | human aesthetics are not fitness | **COMPLIES** | criterion is elaborator acceptance; see §48 item 13 for the honest note about candidate *generation* |
| **13.1** | macro accounting per episode | **COMPLIES** | `kernel_step_count`, tactic head, tokens, latency, wall-clock recorded. `model_action_count ≡ 1` and verifier calls ≡ 1 (2 when closure is checked) by design; both should appear as constants in the artefact rather than be inferred |
| **14.4** | `ENVIRONMENT_ERROR` SHALL NOT count as mathematical failure | **CANNOT DETERMINE YET** | the §7.3 table is correct; **V05-13 currently violates it in code** and is blocking (B2) |
| **14.6** | `INTERACTIVE_TASK` required for claims about alternative paths | **COMPLIES** | the Solver acts in a `VerifiedTask` and may take a non-recorded path; measured at HC-V0.5 — Lean accepted a non-reference tactic in 10 of 14 theorems, and in 2 an alternative closed a goal mathlib proves differently |
| **17.3** | a recorded trajectory is one path, not an oracle | **COMPLIES** | the reference proof is never used to score a proposal; only Lean scores |
| **17.5** | do not invent failed branches retrospectively | **COMPLIES** | every rejection is generated online with the verifier's verdict recorded |
| **18.2** | group by theorem/module/family, not random steps | **COMPLIES** | file-level clustering |
| **18** | `SourceAdmissionRecord` per admitted source | **VIOLATES (F1)** | §4.7 below |
| **18.4** | sample counts chosen after variance, cost, minimum effect and power are measured | **CANNOT DETERMINE YET** | cost is measured (417.34 s bank, 1.87 s/anchor); variance is provisional (§4.5); minimum effect and power are not computed |
| **16 / 16.1 / 16.9** | role separation; the Architect MUST NOT approve its own semantic gate | **CANNOT DETERMINE YET (F6)** | §4.4 below |
| **21** | candidate lifecycle | **NOT APPLICABLE** | no lifecycle is run; O1 names `VOID_INSTRUMENT` as the state a broken assay produces |
| **22 / 22.1** | fitness is a vector; shaped reward is not fitness | **NOT APPLICABLE** | no fitness record is produced for any arm, by design |
| **23** | test whether `Δ_L(20) > Δ_L(1)` | **NOT APPLICABLE, with a warning (F8)** | §4.6 below |
| **26.7** | prefer universal semantic action IDs for local input-representation assays | **COMPLIES with a recorded deviation** | a tactic string is not a universal action ID. `GOAL.md` §13 prefers `ACTION_03`-style responses for early causal tests. HC-V0.6 uses the action space Lean actually has, **identical in every arm**, so no output-protocol difference exists to contaminate the contrast; parse-failure rate is a mandatory per-arm secondary endpoint precisely so a layout that nudges output format cannot hide inside `p_accept` |
| **31** | measure whether language space is searchable | **NOT APPLICABLE** | undefined at one candidate; spec §1.2 forbids reporting searchability metrics and any "searchable landscape" claim |
| **35** | small next-action probes are diagnostic and SHALL NOT define the global language reward | **COMPLIES** | §48 item 6 |
| **40.6** | no `RSTAR`/`LSTAR` claim; one primary sentinel | **COMPLIES** | outcome O8 uses §40.6's blocked sentinels; every outcome forbids `RSTAR`/`LSTAR` |
| **43** | prefer explicit negative/blocked states over optimistic prose | **COMPLIES** | nine exhaustive outcomes, each with a sentinel; O8 forbids substituting a stub or a smaller bank to produce a number anyway |
| **47 Step 2** | freeze the manual as source | **COMPLIES** | `spec/SOURCE/…MANUAL_v0.2.md` unchanged; this audit modified nothing outside the three HC-V0.6 documents |
| **47 Step 10** | stop and hand off; report measured V0 costs, variance and blockers | **COMPLIES** | spec §10 lists the handoff, and three of its five items are already realised |
| **0.1 / 38.1** | anti-bureaucracy; specification work is timeboxed | **COMPLIES** | three documents, no new hierarchy, no atomisation of historical prose |

### 4.4 §16 — role separation (F6)

§16.1 says the Architect **MUST NOT** *"approve its own semantic gate"*, and §16.9 says roles other
than Architect / Solver / Refuter *"SHOULD be software or independent audit contexts."*

In practice, one agent context has proposed the candidate (`R_B`'s layout), built its phenotype
(`arena/trajectory/representation.py`), and written the manifest that will judge it
(`docs/HC_V0_6_PREREGISTRATION.md`). That is Architect, Builder and Experimentalist in one process.

**What mitigates it, honestly:**

* the semantic gate is **mechanical**, not approved: the bijection test is byte-for-byte over the
  whole bank, `DeclarationDerivedRenderer` forbids overriding `render`, and
  `derive_intervention_class` reads the declared slot set rather than a label anyone wrote;
* the thresholds are frozen **before** the data exists, which is what §16.1's prohibition on
  *"modify evaluation thresholds after results"* actually protects;
* this audit is a separate context, which is what §16.9's *"independent audit contexts"* asks for.

**What does not mitigate it:** the *choice* of `R_B` — which layout to try — is unreviewed, and a
designer who picks a variant they expect to win and then writes its test has a degree of freedom no
mechanical check removes. At one candidate with a two-sided test and no promotion, the exposure is
small. It would not stay small across a search.

### 4.5 Runtime determinism — PROVISIONAL, and what it changes

`research/phase10/noise/` measured, under the candidate frozen decoding
(`temperature=0.0, seed=20260908, top_k=20, top_p=0.95, num_ctx=32768, num_predict=128,
think=False`):

* **E1, back-to-back in one server process:** 40 calls at each of three prompt lengths
  (172 / 303 / 1072 chars) → **1 distinct response and 1 distinct tactic at every length**,
  modal rate 1.0. 120/120 byte-identical.
* **E2, interleaving:** a fixed prompt repeated 30 times with 17 other prompts interleaved →
  **1 distinct response**, modal rate 1.0, and `solo_modal_equals_interleaved_modal = True`.

**And HC-V0.5's finding (a) has been reproduced and localised.** Four repeat runs of one 6-episode
configuration (`artifacts/trajectory/noise_repro_{A,B,C,D}.json`) produced **four different
`result_hash` values** — exactly the HC-V0.5 observation. But all **13 proposed tactics were
identical across all four runs**, all four summaries were identical (5 accepted, 8 rejected, 1
solved, 1 environment error, 0 parse failures), and the only differing fields were `latency_ms`,
`wall_ms`, `wall_clock_s`, `generated_utc`, one `backend_error` string differing solely in a
temp-directory name, and `completion_tokens` on **1 of 13 calls** (16 in run A, 12 in B/C/D) for the
same parsed tactic.

So the three levels come apart: **`result_hash` is not reproducible; the response is reproducible on
12 of 13 calls; the tactic — and therefore the endpoint — was reproducible on 13 of 13.** HC-V0.5's
"the runtime is not reproducible" was correct and was measuring the hash, not the decision. For a
paired design whose outcome *is* the decision, that is the reassuring reading; it is not proof, and
the one divergent call shows the response layer is not strictly deterministic. Treat determinism as
**PROVISIONAL** until `docs/HC_V0_6_RUNTIME_NOISE.md` exists.

**Three of design brief §5's five questions remain unanswered**: whether the knobs matter
(`e3_knobs.py`, no output), whether divergence depends on position in the call history
(`e4_context_position.py`, no output), and — the one that actually sets `k` — the within-cell
**acceptance** variance (`e5_cell_variance.py`, no output). E1 and E2 measure *response identity* on
four prompts; a deterministic runtime implies zero acceptance variance, but only as far as that
coverage extends.

**If determinism holds**, the consequences are large and are preregistered rather than discovered:
`k = 1`; replicates add nothing; `Δ(R_A, R_A)` is **exactly zero by construction**, so C1 is
*reported as a construction with its licence* and never as "C1 passed"; outcome **O1 becomes
unreachable**; the replicate-collapsing question dissolves; and **the anchor sample becomes the sole
source of uncertainty**, which makes `n_clusters = 75` the only lever on precision and makes the
cluster bootstrap the whole of the interval rather than one component of it.

### 4.6 §23 — the central prediction, untested again (F8)

§23 is the manual's *"most distinctive high-level hypothesis"*: a useful language *"should preserve
or increase its advantage as reasoning dependency length and horizon increase"*, and the project
*"SHOULD explicitly test whether `Δ_L(20) > Δ_L(1)`"*.

HC-V0.6 supplies `Δ_L(1)` and **nothing else**, and says so: `EpisodeLength = 1` in every cell,
horizon claims forbidden in every outcome. The deviation is recorded with a reason —
`docs/HAMILTONIAN_CHESS_META_GOAL.md` §5.1 shows the absolute gap `p^H − q^H` is unimodal in `H`
under a *constant* per-step edge, so any horizon inference from a single-step number is arithmetic
dressed as a finding — and §1 makes `SHOULD` deviable with a recorded rationale. **Verdict: NOT
APPLICABLE to this milestone, no violation.**

The warning is about the programme, not the experiment. HC-V0.5 produced no horizon evidence;
HC-V0.6 by construction produces none; and the design deliberately makes the estimand
*harder* to extend, because an anchored one-action assay is not convertible into a horizon design
after the fact (spec §4). If a third milestone also defers §23, the project will have built
increasingly rigorous instrumentation for the one quantity its central hypothesis does not concern.
The honest next question after HC-V0.6 is *"what would `Δ_L(h)` cost?"*, and spec §10's handoff —
cost per cell, VOID rate, achieved clusters, the noise model — is exactly what answers it.

### 4.7 §18 — the missing `SourceAdmissionRecord` (F1)

**VERDICT: VIOLATES.**

§18, verbatim: *"Every admitted source SHALL have a `SourceAdmissionRecord` containing:"* — followed
by seventeen named fields including `source_id`, `license_or_access_status`, `version/commit`,
`hashes`, `extraction_method`, `verification_method`, `project_exposure_status`,
`model_exposure_status`, `supported_task_mode`, `observed_trace_distribution`,
`dependency_depth_distribution_if_available`, `domain_distribution`, `grouping_unit`, `admitted_for`
and `known_limitations`.

The LeanDojo `benchmark_4` `random/train.json` corpus **is** an admitted source: HC-V0.6 scanned
40,000 of its records and derived 223 anchors from 78 of its theorems. The requirement binds.

**What exists:** a schema at `spec/world/SOURCE_ADMISSION_SCHEMA.json`, correctly traced to §18,
§18.1, §18.2, §6.28, §6.29, §6.25, §6.30 and §6.33.

**What does not exist:** any instance of it. `spec/implementation/HC_V0_MANIFEST.yaml` records
`source_admission_record: UNKNOWN`, and a repository-wide search finds no record for this source or
any other.

**Why this is a real violation and not a paperwork complaint.** Most of the *content* is scattered
across the bank manifest and spec §2.1 — hashes, commit, extraction method, verification method
(223/223 re-derivation), trace-length distribution, `grouping_unit`, the contamination note, the
sealed-splits list. Two fields are **nowhere**:

* **`admitted_for: TRAIN | DEV | SCOUT | PROMOTION | OOD | FINAL`** — this is the field §30.4 turns
  on. The schema's own comment says a source `admitted_for` PROMOTION or FINAL *"MUST NOT guide
  mutation, candidate selection, thresholds, or surrogate training"*, and that violating it is
  `DEAD_LEAKAGE` (§12.4). HC-V0.6 says in prose that its evidence is developmental; it has never
  *declared* the admission class in the field that machinery reads.
* **`supported_task_mode`** — the HC-V0 manifest records `UNKNOWN`, yet HC-V0.6 depends entirely on
  the answer being `INTERACTIVE`, and HC-V0.5 measured that it is.

**What closes it.** One record instance for this source, populated from the bank manifest plus
`admitted_for: SCOUT` (or `DEV`) and `supported_task_mode: INTERACTIVE`, validated against the
existing schema, written before the preregistration is frozen. It is perhaps an hour of work, which
is why leaving it open is the wrong trade: the cost of the record is far below the cost of a
developmental result later being read as a promotion-grade one because nothing ever said which it
was.

---

## 5. The findings, argued

### 5.1 What this audit did **not** find

No design element permits a candidate to change mathematical truth conditions, to see a future proof
state, to be credited for a verifier failure, or to convert a diagnostic probe into a global reward.
The three prohibitions checked hardest — §48's *"let candidates access future proof states"*,
§48's *"build another micro-benchmark as the global objective"*, and §26.2's `R_ONLY` parity — all
COMPLY, and the first and third comply **by mechanism** (oracle segregation with a tripwire; a
bijection plus a base class that forbids overriding `render`) rather than by declaration. Given that
V05-15 proved a declaration is believed rather than checked, mechanism is the only kind of
compliance worth having here.

### 5.2 F2 — `R_A_PRIME` meant two different things

Design brief §9.4 introduces `R_A_PRIME` as *"an `R_ONLY`, bijective, semantically null perturbation
of the baseline bytes (whitespace only)"*, and §9.6 makes the definition authoritative:
*"`Arm.R_A_PRIME.renderer_id` is therefore `"R_A_PRIME"`, not `"R_A"`."*

`arena/experiments/hc_v0_6/schema.py` says the opposite: *"`R_A` and `R_A_PRIME` are two independent
draws through the **same** renderer"*, and `Arm.renderer_id` returns `"R_A"` for `R_A_PRIME`.
`arena/experiments/hc_v0_6/estimators.py` binds `Comparison.C1_IDENTITY` to `(R_A, R_A_PRIME)`.
`arena/trajectory/representation.py`'s `ARMS` registry has three entries and no whitespace renderer.

**Why this is the most dangerous finding in the audit: it fails silently and it fails in the
flattering direction.** A run against the current code produces four arms and three comparisons,
every number well-formed. The arm labelled `R_A_PRIME` would measure the runtime noise floor —
almost certainly ≈ 0, and *exactly* 0 if determinism holds. A result document written from design
brief §9.4 would then read that ≈ 0 as *"a null byte perturbation did not move the endpoint,
therefore `Δ(R_A, R_B)` is attributable to structure"* — the strongest sentence the experiment can
produce, licensed by a control that was never run.

**CLOSED 2026-09-08, during this audit.** `arena/trajectory/representation.py`'s `ARMS` now
registers `R_A_PRIME: WhitespacePerturbedNative()`; `Arm.renderer_id` returns `str(self.value)`, so
every arm has its own renderer; `Comparison` has four members including `C1B_WHITESPACE`; and
`docs/HC_V0_6_REPRESENTATIONS.md` reports the perturbation measured over the bank — 223/223
bijective, +5.6 % median length against `R_B`'s +37 %.

**Kept in the record because the failure mode recurs.** Nothing in the *output* of the old code
would have revealed the problem. Preregistration B11 therefore requires the check to be re-run at
freeze rather than assumed to stay closed: the general shape — *an arm whose name in the document
and whose behaviour in the code disagree* — is detectable only by reading both, and this design now
has four arms whose names differ by two characters.

### 5.3 F3 — the estimator Holm-corrects its own safety gates

`PREREGISTERED_FAMILY` in `arena/experiments/hc_v0_6/estimators.py` is
`(PRIMARY_RB_VS_RA, C1_IDENTITY, C2_ABLATION)`, and its comment cites design brief §6.

Under Holm, C1 needs a **smaller** p-value to be declared significant — that is, to trip the "the
assay is broken" verdict of spec §9.1. Multiplicity control suppresses false positives about the
science; applied to an instrument-validity check it suppresses **true negatives about the
instrument**. The threshold moves in the direction that protects the headline result from its own
noise floor.

**CLOSED 2026-09-08, and closed better than this audit proposed.** `arena/experiments/hc_v0_6/calibration.py`
now separates the two uses: the Holm family stays at the design brief's four members and governs
**effect claims**, while every **gate** reads the raw permutation p-value, with C1's α set above the
primary α on purpose. Its docstring names the disagreement and resolves it —
*"these gates read the raw permutation p-value… The two documents disagree on the size of the Holm
family; they do not disagree on this, and this is the part that decides whether a number is
published."*

Preregistration §5 has been rewritten to that two-layer form, so the manifest and the code now
agree, and the deviation from design brief §9.6 has disappeared rather than been argued: the brief's
family is adopted in full, and the manifest legislates only the gates, which the brief does not
cover. This is a better outcome than the audit's original position, which rejected the brief's
family outright and was stronger than the safety argument required. P16 remains an owner sign-off
on the two-layer reading, not on a conflict.

### 5.4 F5 — the surface the leakage scan actually saw

§29: *"A shortcut detector making claims about model-visible cues MUST receive the exact
model-visible surface, not a privileged canonical representation."*

The bank's anchor-level pass is genuinely good work — it applied `TACTIC_IN_STATE_BEFORE`,
`FULL_NAME_IN_STATE` and `LEAKS_PREFIX_TACTIC_IN_STATE` to *the live state a Solver would see*, plus
a conservative extra filter on already-played prefix tactics, and found **0 leaks in 223 anchors**.
That closes the larger half of V05-14, which was that `full_name` was never registered.

But it ran on `solver_visible.goals_pp`. The model sees `template(R.render(state))` — four surfaces,
one of which withholds the goal text and two of which re-lay it out. For the three bijective arms
the information is provably identical, so the scan is informative for them; the literal §29
requirement is nonetheless unmet until the scan runs on the rendered prompts per arm. Two smaller
holes also remain: V05-14's **6-byte guard floor**, and `pp_scope.current_namespace`, which is
deliberately exposed as P0 and therefore cannot be filtered without changing the projection — it is
identical across arms, so it threatens the level and not the contrast.

### 5.5 The bank may be too small for any `delta_min` worth defending

Not a manual violation — it is exactly the situation §30.2 exists to expose, and the design does
expose it — but it is the finding with the largest practical consequence, so it is stated plainly.

At the realised bank the study can detect **12–18 percentage points** of change in single-action
acceptance and nothing smaller (`docs/HC_V0_6_ANALYSIS_PLAN.md` §3.3). A representation effect that
large would be remarkable. The effects this programme is realistically hunting — a few points of
acceptance from a layout change — are **below the instrument's floor**.

That produces a specific trap, and naming it in advance is the whole point of a preregistration:

* set `delta_min ≈ 15 points` and the study is well-powered for an effect nobody expects, so an
  informative null (O3) is nearly guaranteed and nearly vacuous;
* set `delta_min ≈ 5 points` and the study is underpowered by construction, so the honest outcome
  is **O6 before the first Solver call**;
* set `delta_min` *at* whatever the MDE turns out to be and the gate is circular — the same failure
  preregistration §2 constraint 3 already forbids for C2.

The manual-compliant responses are to **widen the bank before freezing** (≈ 467 anchors in ≈ 158
files buys 10 points at ICC 0.2 — the existing builder cost 1.87 s per anchor, so this is minutes of
Lean time, not days), or to **declare O6 in advance** and report the design as a cost-and-variance
measurement for the next pilot, which is precisely what §47 Step 10 asks a V0 stage to hand off.
What is *not* available is running it, seeing a null, and describing it as evidence of no effect.

### 5.6 F4 and §48 #6 — the two places where compliance rests on a standing rule

Two findings are COMPLIES only because a document says so, and both deserve to be watched:

* **Prompt tokens are measured, not matched** (§3.2c). The mitigation is a reporting requirement.
  A result that shows `R_B` winning at materially higher token cost, reported without the token
  table, would be exactly the failure `docs/HAMILTONIAN_CHESS_META_GOAL.md` §7a names.
* **`p_accept` is a micro-probe** (§48 #6, §35). Nothing about the *measurement* prevents it from
  becoming a global objective; only the standing prohibition does. The moment someone iterates on
  renderers against `p_accept`, §48 is violated regardless of what this document says — and that
  iteration is the natural next thing to want after a positive Δ.

---

## 6. Preconditions this audit adds to the freeze gate

None of these is new science; each is a gap this audit found in the design as executed.

| id | precondition | finding |
|---|---|---|
| **A1** | a `SourceAdmissionRecord` instance exists for the LeanDojo TRAIN source, validated against `spec/world/SOURCE_ADMISSION_SCHEMA.json`, with `admitted_for` and `supported_task_mode` filled | F1 |
| **A2** | ~~`R_A_PRIME` exists as a whitespace-perturbed bijective renderer~~ — **DISCHARGED**; B11 nonetheless re-verifies it at freeze rather than trusting it to stay closed | F2 |
| **A3** | ~~the estimator's comparison family matches preregistration §5~~ — **DISCHARGED**; the gates read uncorrected p-values and the manifest adopts the brief's four-member family for effect claims | F3 |
| **A4** | the leakage scan is re-run on the **rendered prompt of each arm**, not only on the Lean state | F5 |
| **A5** | the §7.3 disposition table is implemented and V05-13 closed, so an `ENVIRONMENT_ERROR` cannot enter the Solver's denominator (= B2, B10) | §3.4, §14.4 |
| **A6** | `docs/HC_V0_6_RUNTIME_NOISE.md` answers all five of design brief §5's questions, including the within-cell acceptance variance, and `k` is frozen from it (= B1) | §4.5 |
| **A7** | the power analysis runs on 75 clusters and either justifies them for the chosen `delta_min` or declares O6 **before** the first Solver call. **Half discharged**: the MDE is computed (12–18 points); `delta_min` is not chosen | §3.6, §30.2 |
| **A8** | the `delta_min` / bank-size decision of §5.5 is made explicitly — widen the bank before freezing, or declare O6 in advance. Choosing `delta_min` to match the MDE is forbidden (preregistration §2, constraint 3) | F0, §5.5 |

A manifest frozen with A1–A8 open is a plan, not a preregistration.
