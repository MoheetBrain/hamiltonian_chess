# HC-V0 red team — manual §47 Step 9

**`attack_suite_version = hc-v0-redteam-2026-09-08`**

**Verdict.** The loop is *not* trustworthy as a source of verified-trajectory claims today. One
defect reaches the kernel verdict itself: `native_decide` produces
`TerminalStatus.CLOSED_VERIFIED`, reward `1.0` and `trust_tier="A_NATIVE_VERIFIED"` on a
declaration whose `#print axioms` reports `Lean.ofReduceBool` — an axiom the Lean kernel never
checks — because `verify_closed_script` computes `contains_of_reduce_bool` and then does not use
it. (Precisely: this admits an *unchecked* theorem, not a *false* one; the trust base silently
shifts from the Lean kernel to the Lean compiler and the machine's C toolchain, which is exactly
what `CLOSED_VERIFIED` is supposed to exclude.) Every other confirmed finding is a claim a record
can make that no code checks: who chose an action, which parent it came from, how long the
reference proof was, whether the stored actions are the ones that ran.

Adapting the manual's §29 default wording, and refusing the word "unexploitable":
**21 confirmed exploits, 1 of them CRITICAL, under `attack_suite_version hc-v0-redteam-2026-09-08`.**

The `sorry` defence, the absence of any state-vs-state string comparison, determinism, the
re-scoring guard, dead-candidate enforcement and the sealed-split guard all **held under attack**,
and the builder's headline leakage numbers **replicated exactly**. Those are in
[Defences that held](#defences-that-held), which matters as much as the findings.

Everything below is reproducible from `research/phase9/redteam/`; raw JSON is in
`research/phase9/redteam/out/`.

---

## Findings

Legend — **CONFIRMED**: the attack succeeded. **PARTIAL**: it succeeded against the default check
and was caught only by an optional or expensive one. **REFUTED**: the defence held (listed
separately).

*Exploitable-by-search* asks the §29 question: would an **automated evolutionary search** find this
by optimising, as opposed to a malicious or careless **author** with write access?

| id | target | sev | status | one line | reproduction |
|---|---|---|---|---|---|
| RT-01 | Lean kernel | **CRITICAL** | CONFIRMED | `native_decide` → `CLOSED_VERIFIED` on `Lean.ofReduceBool`; `verified` ignores `contains_of_reduce_bool`, and so does `_structural_problems` | `attack_native_decide_end_to_end.py` |
| RT-02 | truth mutation / horizon | HIGH | PARTIAL | two unrelated theorems spliced into one "10-step trajectory"; loads clean, passes `verify_bank` | `attack_trajectory_integrity.py` → `T1` |
| RT-03 | verification | HIGH | CONFIRMED | `_relive` replays the **source record's** tactics, never the stored actions; all 5 actions replaced by `aesop` and relive still passes | `attack_relive.py` → `forged_action_swap` |
| RT-04 | lineage / reporting | HIGH | CONFIRMED | `build_trajectory(actor=…)` overwrites who chose every action; one episode → a REFERENCE and a SOLVER record, both self-consistent | `attack_followups.py` → `F5` |
| RT-05 | provenance | MED-HIGH | CONFIRMED | `verifier_evidence` is outside `content_hash`: the kernel receipt can be rewritten with the hash unchanged | `attack_trajectory_integrity.py` → `T4` |
| RT-06 | horizon | MEDIUM | CONFIRMED | `reference_horizon` is a caller-supplied int, never checked against the probe; `999` accepted, `observed_trace_length` follows | `attack_trajectory_integrity.py` → `T6`, `attack_followups.py` → `F5` |
| RT-07 | semantic gate | MEDIUM | CONFIRMED | the round-trip is self-inverse: dropping **any** payload key (incl. `goal`) still recovers the identical `mathematical_hash`; a renderer that appends the answer passes all three gate checks | `attack_gate_and_reporting.py` → `G1`, `G2` |
| RT-08 | semantic gate | MEDIUM | CONFIRMED | the `child_language` the gate validates is byte-different from the codec that builds the prompt, for all 8 seeds | `attack_followups.py` → `F1` |
| RT-09 | inner MDP | MEDIUM | CONFIRMED | `arena.branch()` is cosmetic: it returns the branched-to observation but the next `step()` applies to `states[-1]` | `attack_lean_kernel.py` → `K7` |
| RT-10 | fitness memory | MEDIUM | CONFIRMED | delete the record file → re-append a different result as `FRESH`; re-seal an edited record → accepted. No chain, no manifest attestation, no signature | `attack_evolution_record.py` → `L5`, `L6` |
| RT-11 | fitness memory | MEDIUM | CONFIRMED | `rows.jsonl` can be detached and the record still reads clean — the store's own docstring says that must not be possible | `attack_evolution_record.py` → `L7` |
| RT-12 | lineage | MEDIUM | CONFIRMED | `parent_genome_id` is not in the eleven-component identity; a record can name a parent that never existed with every hash intact | `attack_evolution_record.py` → `L1`, `L1b` |
| RT-13 | cache identity | MEDIUM | CONFIRMED | `mutation_hash` is caller-supplied, never derived from `gene_changes`: re-rolling it gives the same (parent, child, condition) a second `FRESH` record | `attack_evolution_record.py` → `L2` |
| RT-14 | macro-cost hiding (§29) | MEDIUM | CONFIRMED | `KernelStepCount` is `0` everywhere and is never assigned anywhere in the package | `attack_contract_classes.py` → `C3` |
| RT-15 | reporting | MEDIUM | CONFIRMED | the committed bank's stored `horizon` block predates the §6.30–6.34 retrofit: `minimal_proof_length`, `dependency_depth`, `episode_length`, `observed_trace_length`, `kernel_step_count` are absent from both bank files | `attack_contract_classes.py` → `C3`; one-liner below |
| RT-16 | reporting / statistics | MEDIUM | CONFIRMED | `league-registry.json` — the durable archive — has no scientific-status stamp, no model identity, no condition id, and marks all 256 stub rows `verified: true` | `attack_gate_and_reporting.py` → `G6` |
| RT-17 | Lean kernel | LOW-MED | CONFIRMED | `verify_closed_script` cannot verify an **axiom-free** proof: `1 = 1 := by rfl` → `verified=false` | `attack_followups.py` → `F3` |
| RT-18 | provenance | LOW | CONFIRMED | `states_hash` / `actions_hash` are written but never validated on load | `attack_trajectory_integrity.py` → `T5` |
| RT-19 | oracle leakage | LOW | CONFIRMED | the runtime tripwire is a no-op for 7.69 % of reference tactics (< 6 chars) and never checks `full_name`, file path, premise names, `pp_scope`, or any non-verbatim variant | `attack_leakage.py` → `R4`; `attack_followups.py` → `F4` |
| RT-20 | cache identity | LOW | CONFIRMED | `records()` globs every condition shard and `summary()` folds them into one `manifest_hash`; `RecordScope.CROSS_CONDITION` is unreachable by construction | `attack_evolution_record.py` → `L8` |
| RT-21 | tactic policy | LOW | CONFIRMED | `classify` over-blocks: any tactic containing the whole-word token `stop` or `admit` is refused (e.g. `exact stop` on a hypothesis named `stop`). Fails safe | `attack_lean_kernel.py` → `K1` |

---

## RT-01 — `native_decide` closes a goal on an axiom the kernel never checks (CRITICAL)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam/attack_native_decide_end_to_end.py
```

**Observed**

```json
{"tactic": "native_decide",
 "terminal_status": "CLOSED_VERIFIED", "reward": 1.0,
 "kernel_evidence": {"verified": true,
   "print_axioms": "'probe_redteam_of_reduce_bool' depends on axioms: [propext, Lean.ofReduceBool]",
   "contains_sorry_ax": false, "contains_of_reduce_bool": true, "exit_code": 0, "errors": ""},
 "trust_tier_claimed": "A_NATIVE_VERIFIED",
 "bank_verify_passed": true, "bank_verify_failures": []}
```

**Expected.** `lean_backend.verify_closed_script`'s own docstring says: *"A proof closed by
`decide`/`native_decide` shows `Lean.ofReduceBool` and is flagged rather than silently accepted."*
It is flagged in the evidence record and then accepted anyway:

```python
verified = completed.returncode == 0 and not has_sorry and not errors
```

`contains_of_reduce_bool` appears nowhere in that expression, and `_structural_problems` in
`arena/trajectory/arena_v0.py` tests `evidence.contains_sorry_ax` but not
`evidence.contains_of_reduce_bool` (verified by `inspect.getsource` in the script).

**Why it matters.** `Lean.ofReduceBool` is not a kernel-checked reduction: it asserts that the Lean
compiler's native evaluation of a `Bool` agrees with its definitional value. Its trust base is the
Lean compiler, the C toolchain and the machine — not the kernel. `native_decide` is **allowed by
the default `record_only` policy**, which is the policy both committed banks were built under
(`artifacts/trajectory_bank_v0/*/manifest.json` → `"policy_name": "record_only"`).

**Exploitable by an evolutionary search: yes, fastest of all findings.** It is a single 13-character
allowed token that closes any decidable goal in one step for reward `1.0`. Any reward-maximising
solver finds it in minutes. Its side-effect — collapsing the horizon to 1 — is invisible to `r`,
which is `+1` for `CLOSED_VERIFIED` and `0` otherwise.

**Minimal fix recommended (not applied).** Two lines:

1. in `verify_closed_script`, `verified=(returncode == 0 and not has_sorry and not
   has_reduce_bool and not errors)` — or, if `ofReduceBool` is to remain admissible, make it an
   explicit named parameter `allow_native_reduction: bool = False` so the choice is recorded, not
   defaulted;
2. in `_structural_problems`, add the `contains_of_reduce_bool` twin of the existing `sorryAx`
   check so an already-written bank is caught on re-verification.

A third, cheaper mitigation: move `native_decide` from `HEAVY_AUTOMATION` (a *policy* list that the
default does not apply) into `ALWAYS_REFUSED` (which the default does apply).

**Note for the record:** the committed bank is *clean* of this. Zero of its 26 trajectories carry
`contains_of_reduce_bool` or `contains_sorry_ax`; 4.9 % of its 81 verified actions have a
`HEAVY_AUTOMATION` head (`push_cast` ×2, `linarith` ×2), and the max-14 trajectory has none.

---

## RT-02 — two unrelated theorems concatenate into one trajectory (HIGH, PARTIAL)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam/attack_trajectory_integrity.py   # T1
.venv/bin/python research/phase9/redteam/attack_relive.py                 # forged_concat
```

**Observed.** Splicing the 5 states/actions of
`Mathlib/RingTheory/MvPolynomial/Homogeneous.lean::MvPolynomial.IsHomogeneous.rename_isHomogeneous_iff`
onto `Mathlib/MeasureTheory/Integral/Bochner.lean::MeasureTheory.weightedSMul_add_measure`,
renumbering only `index` and `state_id`, yields a record reporting
`{"achieved": 10, "verified": 10}` under the first theorem's `problem_id`. It loads through
`VerifiedTrajectory.from_dict` with hashes verified and passes `verify_bank(relive=False)` with
zero failures.

**Expected.** `VerifiedTrajectory`'s docstring: *"every action's endpoints name the adjacent
envelopes' backend state ids (so ten unrelated one-step probes cannot be concatenated into a
'ten-step trajectory')."* The check is `action.from_state_id == states[i].state_id`. State ids are
the REPL's per-session small integers (`"0"`, `"1"`, …, observed across the whole committed bank),
and nothing binds a state id to its `pp` bytes, to a session, or to a problem. Renumbering is free.

**Caught by.** `verify_bank(relive=True)` — `relive mismatch: horizon 5 != stored 10`. That check
needs the Lean toolchain plus a scan of the 373 MB split and is **not** the default.

**Exploitable by an evolutionary search: no.** This needs write access to the bank file. It is an
author/operator exploit, and a strong argument for treating `--relive` as mandatory before any
bank is cited.

**Minimal fix recommended.** Bind state identity to content and to the episode: make
`envelope_id` (already `backend_kind:state_id:pp_sha256[:32]`) the thing the chain check compares,
and add a per-episode salt (e.g. the session's probe hash) to the state id so ids from two
sessions cannot be renumbered into one chain. Additionally have `__post_init__` require that every
state's `pp_scope` is identical, which the splice above violates but nothing tests.

---

## RT-03 — `relive` never re-executes the stored actions (HIGH)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam/attack_trajectory_integrity.py   # T7 writes the bank
.venv/bin/python research/phase9/redteam/attack_relive.py                 # forged_action_swap
```

**Observed.** Every tactic of a `CLOSED_VERIFIED` 5-step trajectory replaced with the string
`aesop` (state chain, action count and evidence untouched), then:

```json
"forged_action_swap": {"passed": true, "relived": 1, "relive_matches": 1, "failures": []}
```

**Expected.** `verify_bank`'s docstring: *"`relive=True` additionally re-executes every
trajectory's action sequence against a fresh Lean session and requires the same terminal status —
the only check that can catch a bank whose evidence was fabricated wholesale."* The implementation
of `_relive` calls `driver.run(record, built.probe)`, and `ReplayDriver.run` plays
`probe.reference_tactics`, which come from the **LeanDojo source record**. `trajectory.actions` is
never read. So `relive` re-verifies the source, not the artefact, and agreement is only on terminal
status and action *count*.

**Exploitable by an evolutionary search: no** (author-only), but it removes the safety net that
RT-02, RT-04 and RT-05 rely on being there.

**Minimal fix recommended.** In `_relive`, replay `tuple(a.tactic for a in trajectory.actions)`
through a fresh `LeanTrajectoryArena`, and additionally require the re-run's per-step
`pp_sha256` sequence to equal the stored one. Keep the reference replay as a separate,
differently-named check (it answers a different question: "is the source still reproducible?").

---

## RT-04 — the actor label is a caller assertion, not a fact (HIGH)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam/attack_followups.py              # F5
.venv/bin/python research/phase9/redteam/attack_trajectory_integrity.py   # T2
.venv/bin/python research/phase9/redteam/attack_relive.py                 # forged_solver_actor
```

**Observed.** One live episode, `build_trajectory` called three times:

| call | `solver_actions` | `reference_actions` | `observed_trace_length` |
|---|---|---|---|
| `actor=REFERENCE, reference_horizon=1` | 0 | 1 | 1 |
| `actor=SOLVER, reference_horizon=1` | 1 | 0 | 1 |
| `actor=SOLVER, reference_horizon=999` | 1 | 0 | **999** |

Three distinct `trajectory_id`s, three valid `content_hash`es, one episode. Relabelling the
committed bank's REFERENCE actions to SOLVER and re-sealing passes `verify_bank(relive=True)`.

**Expected.** `LeanTrajectoryArena.step` stamps `Actor.SOLVER` on the action it just executed;
`build_trajectory` then does `replace(action, actor=actor)` for **every** action with whatever the
caller passes. The team's disclosure — *"ALL 120 bank actions are actor=REFERENCE. ZERO solver
actions"* — is true of the committed artefact (verified: `{'REFERENCE'}` across all 120) but is
**enforced by nothing**. The distinction that separates "the environment works" from "a policy
solved it" is a keyword argument.

**Exploitable by an evolutionary search: no**, but this is the single field a future integrator is
most likely to set wrongly, and no test would catch it.

**Minimal fix recommended.** Carry the actor on the action at the moment of choice (the arena
already knows: an action played by `ReplayDriver` is REFERENCE, one played through the public
`step()` by a solver is SOLVER) and make `build_trajectory(actor=…)` an **assertion** —
`require_single_actor(actor)` before emitting — rather than a rewrite. `require_single_actor`
already exists and is never called on this path.

---

## RT-05 — the kernel receipt is outside `content_hash` (MEDIUM-HIGH)

**Reproduction:** `attack_trajectory_integrity.py` → `T4`.

**Observed.** Rewriting `print_axioms` to `'probe_ANYTHING_AT_ALL' depends on axioms:
[SomeMadeUpAxiom]` leaves `content_hash` at `df6444c0…` — bit-identical — and the record loads
without complaint.

**Expected.** `VerifiedTrajectory.semantic_core()` — the pre-image of `content_hash` and hence of
`trajectory_id` — lists `states`, `actions`, `terminal_status`, `reference_horizon`, `provenance`
and omits `verifier_evidence` entirely. Yet `kernel_verified` (and therefore the `CLOSED_VERIFIED`
invariant in `__post_init__`) is computed **only** from `verifier_evidence`. The one field the
integrity check depends on is the one field the integrity check does not cover.

**Minimal fix recommended.** Add a `verifier_evidence` digest to `semantic_core()` (the evidence
dicts minus `wall_ms`-style noise), and check `states_hash` / `actions_hash` on load (RT-18) so
all three stored hashes mean something.

---

## RT-06 — `reference_horizon` is unbound (MEDIUM)

`build_trajectory(reference_horizon=999)` on a 1-action episode is accepted and
`Horizon.observed_trace_length` — the manual §6.30 quantity — reports `999`. Nothing compares it
to `len(probe.reference_tactics)`. Reproduction: `attack_followups.py` → `F5`,
`attack_trajectory_integrity.py` → `T6`. **Fix:** derive it in `build_trajectory` from
`self._probe.reference_tactics` and make the parameter an optional cross-check, not the source.

---

## RT-07 — the semantic gate's round-trip is self-inverse (MEDIUM)

**Reproduction:** `attack_gate_and_reporting.py` → `G1`, `G2`.

**Observed.** Two hostile `CandidateLanguage` subclasses, defined inside the attack script:

* `LeakyRenderer` appends `"ANSWER: the correct option is index 0"` after a marker and strips it in
  `_decode_payload`. Full gate verdict: `semantic_roundtrip PASS`, `mutation_effective PASS`,
  `arena_parity PASS`, `failure_modes []`.
* `AmnesiacRenderer` drops one payload key at render time and restores it at parse time. **All 15
  keys round-trip to the identical `mathematical_hash` while dropped** — including `goal`
  (132 bytes), `assumptions` (1 761), `objects` (1 406) and `propositions` (1 788).

**Expected.** `semantic_gate`'s docstring says check 1 *"is what kills a renderer that drops a
`holds(...)` assumption."* It cannot, because `ModelViewCompiler.validate` recovers the state with
**the same codec that rendered it**: `recovered = self.surface.parse(compiled.text…)`. Any
information the parser can re-synthesise is invisible to the test. The second half of `validate`,
`compiled != expected` where `expected = self.compile(...)`, is a comparison of `f(x)` with `f(x)`
and is vacuous as the gate calls it.

**Exploitable by an evolutionary search: not today, and this is the important qualifier.** The
renderer the loop actually evaluates is `GenomePhenotypeLanguage(model_view(genome).surface)`,
driven by a 14-family enum genome that cannot express a compensating parser. The protection is
**restriction of the mutation space, not the gate**. The moment the meta-genome's Layer B/C genes
land (`docs/LANGUAGE_META_GENOME_V0.md`) — or the moment a genome supplies its own
`StateRenderer` through the seam `arena_v0` explicitly advertises — the gate stops covering the
thing it is named for.

**Minimal fix recommended.** Round-trip through an **independent** decoder, not the arm's own:
`assert_arena_parity` already has `prompt_information_inventory(language, state)` for exactly this
purpose — extend check 1 to compare the surface's information inventory decoded by the *unbound
base codec* against the canonical state, so content the arm's parser reinvents is not credited.

---

## RT-08 — the gate validates a renderer that is not on the evaluation path (MEDIUM)

For all eight seeds, `language_for_genome(g).render(state)` and
`GenomePhenotypeLanguage(model_view(g).surface).render(state)` produce **different bytes**
(`attack_followups.py` → `F1`; e.g. `StructuredEnglishLanguage` vs `GenomePhenotypeLanguage`). The
gate's first check and its `child_language` injection point — documented as *"so a hostile or
hand-written renderer can be put through check 1"* — operate on the first object; the prompt the
evaluator scores comes from the second. The `Evaluator` protocol is nevertheless handed
`language=language_for_genome(child)`, and `StubLadderEvaluator` discards it (`del language`). A
real evaluator that used it would be scoring an object the parity check never saw.

**Fix:** make the object explicit — build the surface once, pass the same instance to the gate, to
`build_prompt` and to the evaluator, and assert identity rather than reconstructing it three times.

---

## RT-09 — `arena.branch()` does not rewind where the next action lands (MEDIUM)

**Reproduction:** `attack_lean_kernel.py` → `K7`.

```json
{"root_state_id": "0", "after_step1_state_id": "1", "branch_returned_state_id": "0",
 "next_step_applied_from": "1", "expected_if_branch_rewound": "0", "branch_is_cosmetic": true}
```

`LeanTrajectoryArena.branch` calls `session.branch(state_id)`, logs it, and returns the
observation of the old state — but never mutates `self._states`, and `step()` reads
`current = self._states[-1]`. So after a branch the Solver is shown state `0` and its next action
is applied to state `1`. The session layer supports genuine re-entry correctly (`K6`); the arena
layer does not use it. Any `(o_t, a_t)` pair collected across a branch is mislabelled — in the
component whose entire purpose is to produce trustworthy trajectory data.

**Fix:** either make `branch` truncate/fork `self._states` and `self._actions` into a new segment,
or remove the method and expose branching only at the session layer until the trajectory schema can
represent a tree.

---

## RT-10, RT-11, RT-12, RT-13, RT-20 — the fitness-memory layer (MEDIUM / LOW)

**Reproduction:** `attack_evolution_record.py` (`L1`, `L1b`, `L2`, `L5`, `L6`, `L7`, `L8`).

| attack | result |
|---|---|
| claim `parent_genome_id="a-parent-that-never-existed"` | `FRESH`, `record_id` **unchanged** — `parent_genome_id` is not one of the eleven identity components |
| swap `parent_genome_hash` to another seed's hash, keep the id | `FRESH`, accepted; no cross-check exists |
| re-roll `mutation_hash` on an otherwise identical record | two `FRESH` records, same parent, same child, same `condition_id` |
| declare `gene_changes=[alphabet]` when `token_policy` changed | accepted; `intervention_class` derives from the declaration |
| edit `promoted` in the stored JSON | **BLOCKED** — `does not reproduce its stored content_hash` |
| edit `promoted` and recompute all three hashes | **ACCEPTED**, `promoted=True`, `supersedes=None` |
| `unlink()` the record file, re-append a different result | `FRESH` |
| `unlink()` the `.rows.jsonl` | record still reads clean, no complaint |
| two records under different `condition_id`s | `records()` returns both; `summary()` folds both into one `manifest_hash` |

The append-only guarantee is an in-memory index rebuilt from `self.path.glob("*/lfm-*.json")`.
There is no hash chain, no `prev_hash`, no signed manifest and no append log, so "append-only"
means "append-only for a caller that only uses this class". The `ArtifactStore.write_json` under
it is an unconditional `path.write_text`.

`RT-13` is the one of these an **evolutionary search would exploit on its own**: `mutation_hash`
is `proposal.proposal_hash`, never derived from `gene_changes`, so a proposer that re-emits the
same parent→child edge under a new proposal id gets a second independent draw under any stochastic
evaluator, with no multiplicity accounting anywhere. `EvolutionLoop.run_generation` dedupes by
`candidate_id` within one generation (`used`), but not across generations and not across runs.

**Minimal fixes recommended.** (a) add `parent_genome_id` to the identity, or drop it and resolve
lineage only by hash; (b) derive `mutation_hash` from `(parent_genome_hash, child_genome_hash,
sorted(gene_changes))` so it cannot be re-rolled; (c) verify `gene_changes` against the actual
parent/child genome diff at construction; (d) write a per-run append log whose each line carries
`prev_content_hash`, and store the run's `manifest_hash` in a file the store refuses to overwrite;
(e) on read, require the `.rows.jsonl` sibling to exist and its line count to equal
`fitness_vector["J_solve"].n`, per the store's own docstring.

---

## RT-14 — macro-cost hiding: `KernelStepCount` is always zero (MEDIUM)

`Horizon.kernel_step_count` is documented as *"the post-lowering cost (§6.32, 13.1) so a macro that
bundles many kernel operations cannot look cheap."* It defaults to `0` and **nothing in
`arena/trajectory/` ever assigns it** (checked by source scan in `attack_contract_classes.py` →
`C3`). A one-tactic `linarith` and a fourteen-tactic hand proof therefore report the same
post-lowering cost: zero. This is the §29 attack class *macro-cost hiding*, present by omission.
Combined with RT-01 it is the mechanism by which `native_decide` looks free.

**Fix:** either populate it (Lean can report `maxHeartbeats` consumption per declaration) or change
the type to `int | None` with `None` meaning NOT_MEASURED, so a reader cannot mistake "not counted"
for "cost zero" — the same discipline `minimal_proof_length` already applies by returning the
literal string `UNKNOWN`.

---

## RT-15 — the committed bank predates the horizon-vocabulary retrofit (MEDIUM)

```bash
.venv/bin/python -c "import json;r=[json.loads(l) for l in open('artifacts/trajectory_bank_v0/h5/bank.jsonl') if l.strip()];print(sorted(r[0]['horizon']))"
# ['achieved', 'reference', 'reference_actions', 'solver_actions', 'verified']
grep -c minimal_proof_length artifacts/trajectory_bank_v0/*/bank.jsonl    # 0 and 0
```

`Horizon.to_dict()` now emits ten keys; the stored artefact has five. Absent from both bank files:
`episode_length`, `observed_trace_length`, `kernel_step_count`, `dependency_depth`,
`minimal_proof_length`. The last two are the fields whose *stated purpose* is to stop a reader
mistaking a 14-tactic replay for a "14-step required reasoning task" (§17.6) — and they are not in
the only durable artefact. It loads clean because `horizon` is derived on read and is not covered
by `content_hash`, so the stored block is decorative and silently ignored.

**Fix:** regenerate the banks (they cost 51 s and 24 s respectively per their own manifests), or
have `load_bank` refuse a `horizon` block that disagrees with the recomputed one instead of
ignoring it.

---

## RT-16 — the durable archive carries no disclaimer (MEDIUM)

**Reproduction:** `attack_gate_and_reporting.py` → `G6` (2 generations, 12 candidates).

| file | carries `EXECUTABILITY_ONLY_NOT_A_RESULT`? | carries the prose status? |
|---|---|---|
| `summary.json` | **yes** | yes |
| `lfm-*.json` (per record) | no | **yes** (`provenance.scientific_status`) |
| `league-registry.json` | **no** | **no** |

`league-registry.json` is the file that holds cross-candidate rankings, Pareto state and
`objective_metrics` (`{"J_solve": 0.5625, "J_cost": 18755.0}`). It contains **256 observations, all
marked `verified: true`**, produced by `sha256(prompt) mod n_options`; `LeagueRegistry` filters on
exactly that flag when computing ratings (`registry.py:175`). It mentions neither "stub" nor
"model", carries no `condition_id`, and its `domain_ratings` intervals use `"method": "normal"` on
16 binary observations drawn from 8 twin families — the anti-conservative, unclustered interval
that the `FitnessRecord` correctly flags (`"clustered": false`, `"cluster_unit_available":
"family_id"`) and the archive does not. This is granularity substitution in the one artefact a
reader is most likely to open, and it is the recurring named failure in
`docs/V7_TOTAL_FORENSIC_AUDIT.md`.

To answer the brief's specific question: **yes, `J_solve = 0.75` is reachable by a reader who never
sees the stamp** — it is in `league-registry.json` and in every `lfm-*.json`'s
`fitness_vector`, and the machine-readable stamp is only in `summary.json`.

**Fix:** put `scientific_status`, `model.digest`/`is_stub` and `condition_id` into
`LeagueRegistry.save()`'s payload; refuse `verified=True` on an observation whose `ModelIdentity`
has `is_stub=True`; and either cluster the league intervals by `family_id` or label their method
`normal_unclustered_diagnostic`.

---

## RT-17 — an axiom-free proof cannot be verified (LOW-MEDIUM, fails safe)

```bash
.venv/bin/python research/phase9/redteam/attack_followups.py   # F3
# theorem probe_redteam_axiom_free : 1 = 1 := by rfl
# -> verified=false, exit_code=0, print_axioms="",
#    errors="'probe_redteam_axiom_free' does not depend on any axioms"
```

`_AXIOMS_RE = ^'(?P<name>[^']+)' depends on axioms: \[(?P<axioms>[^\]]*)\]` matches only the
"depends on axioms: [...]" spelling. Lean prints `'X' does not depend on any axioms` when there are
none, `match is None` follows, and the `errors or output[-4000:]` fallback files Lean's success
message as an error. The direction is safe (a correct proof is rejected, never the reverse), but it
biases the instrument: the cleanest proofs are the ones discarded, the reported flat-replay success
rate is an underestimate, and a solver that finds an axiom-free proof is scored `FAILED`. Under
selection that is a mild pressure **away** from the best behaviour.

**Fix:** add the alternative branch to the regex and treat "does not depend on any axioms" as the
empty axiom list.

---

## RT-19 — leakage channels the filter does not inspect (LOW)

The record-level `LeakageFilter` has exactly two criteria and both are applied to LeanDojo's
**recorded** `state_before`. The observation a Solver receives is the **live REPL** pretty-print,
which this project's own audit measured as differing from the recorded text 40.6 % of the time. The
runtime tripwire `assert_observation_clean` closes only part of that gap:

* it checks **only** not-yet-played reference tactics, verbatim, of length ≥ 6. Measured on the
  first 6 000 records of the development split: **1 000 of 13 003 tactics (7.69 %) are shorter than
  6 characters** — `simp` ×280, `rfl` ×200, `ext` ×86, `ring` ×49, `omega` ×34 … For those steps
  the tripwire is a no-op by construction (`attack_leakage.py` → `R4/C1`);
* it never checks `full_name`, the file path, premise names, `pp_scope.current_namespace` /
  `open_declarations` (both of which `BackendNativeRenderer` puts in the observation), any recorded
  `state_after`, or any non-verbatim variant — a single extra space defeats the substring test
  (`C4`).

**Measured on the committed bank the exposure is zero.** Scanning all 120 non-terminal states of
both banks for any remaining reference tactic of any length: **0 leaks in 77 + 43 states**. The
hole is real; it did not fire here.

**Fix:** run the tripwire against the live state with no length floor but with a whole-token match
(so `rfl` in `⊢ rfl = rfl` is not a false positive), and add `full_name` and `file_path` to the
runtime criteria, not only the record-level ones.

---

## Defences that held

Every one of these was attacked with a script that would have recorded a defect if it had worked.

**1. `sorry` is refused at three independent layers.** (`attack_lean_kernel.py` → `K1`, `K2`, `K3`)
`TacticPolicy.classify` tokenises the tactic and intersects with `ALWAYS_REFUSED`, catching all ten
spellings tried, including `«sorry»`, `exact (by sorry : True)`, `first | rfl | sorry`,
`all_goals sorry`, `exact @sorryAx _ _ true` and `have h : True := by sorry`. With the Python guard
**removed entirely** (a `NullPolicy` subclass that classifies everything ALLOWED), the
`lean_dojo_repl` backend itself answers `{"error": "proof contains \`sorry\`"}` for both `sorry` and
`admit`, and `stop` is a parse error. Handed straight to the kernel authority with no policy in the
path, `verify_closed_script(probe, ["sorry"])` returns
`'probe_redteam_triv' depends on axioms: [sorryAx]`, `verified=false`. Three layers, independently
sufficient. This is the strongest thing in the codebase.

**2. No verdict anywhere is computed by comparing two states.** (`attack_contract_classes.py` →
`C4`; `tests/trajectory/test_arena_v0.py`) The only state-text comparison in `arena/trajectory/` is
`is_no_goals(s) == "no goals"`, a fixed backend literal, and it is a necessary-not-sufficient
condition with closure decided by the kernel. Consequently the §29 classes *binder renaming*,
*alpha-equivalence* and *irrelevant reorderings* have **no verification surface to attack** — I
could not construct an attack because there is nothing to attack. The repository enforces this with
an AST scan that has a negative control (a synthetic string-matching verifier is flagged).
*Caveat:* the scan globs `arena/trajectory/*.py` only, and its `STATE_TEXT_NAMES` heuristic does not
flag `assert_observation_clean`'s `candidate in payload` containment test.

**3. Determinism is real, and the re-scoring guard works.** (`attack_evolution_record.py` → `E0`,
`L4`; `attack_gate_and_reporting.py` → `G7`) Two independent runs produced identical `run_id`,
`record_ids`, `content_hashes`, `manifest_hash` (`97b0016e…`) and `final_front`. Re-running under
`PYTHONHASHSEED` 0, 1 and 12345 in separate processes gave byte-identical results, so determinism
does not rest on dict or set iteration order. An identical re-append returns
`SAME_CONDITION_REUSE` and writes nothing; the same identity with a different `result_hash` raises
`FitnessMemoryIdentityViolation`; a naive in-place JSON edit is caught by `content_hash` on read.

**4. Dead-candidate enforcement is complete.** (`attack_followups.py` → `F2`) A candidate killed by
the semantic gate: `outcome=KILLED_BY_SEMANTIC_GATE`, `status=REFUSED`, `void_code=MUTATION_INERT`,
`evaluation_ran=false`, `budget.calls=0`, `fitness_vector.measured()={}`, `rows` file **0 bytes**,
and it never enters the league registry. An inert (byte-identical) mutation is killed with
evidence: `"0/16 rendered prompts differ from the parent across 8 families"`. A renderer that raises
kills the candidate as `TRUTH_ALTERED` rather than passing.

**5. The sealed-split guard held against every evasion tried.** (`attack_contract_classes.py` →
`C1`) All four sealed paths refused; `random/./val.json`, `random/../random/val.json`, the resolved
absolute path and a `//`-aliased path were all refused too; `random/train.json` allowed. The sealed
splits were never opened by this red team.

**6. The §28 trust contract holds where I could test it.** (`C2`, `C2b`) A kernel re-elaboration
starved to a 1 s timeout returns `verified=false`, `contains_sorry_ax=false` and the explicit
message `kernel re-elaboration exceeded 1.0s` — a timeout is not recorded as a falsehood. A probe
that cannot elaborate ends the episode `ERROR_BACKEND`, **not** `FAILED` — infrastructure failure is
not candidate failure. A forged session state id returns the typed `UNKNOWN_STATE_ID` and is logged
(`K6`).

**7. The builder's leakage numbers replicate exactly.** (`attack_leakage.py` → `R1`, `R2`) Counted
with an implementation written independently of `LeakageFilter`: h5 (scan 6 000, min_horizon 5) →
**7 leaking steps, 6 problems dropped**; h12 (scan 12 000, min_horizon 12) → **9 leaking steps, 8
problems dropped**. Both match the manifests to the unit. Two facts worth adding: every drop was
`TACTIC_IN_STATE_BEFORE` — the `FULL_NAME_IN_STATE` criterion has **never fired** in either scan —
and scanning the committed bank's own live states for any remaining reference tactic of any length
finds **zero leaks**.

**8. `relive` catches the two forgeries it is shaped for.** (`attack_relive.py`) Concatenation →
`horizon 5 != stored 10`; `FAILED` promoted to `CLOSED_VERIFIED` → `terminal FAILED != stored
CLOSED_VERIFIED`. It is a real check with a real cost (3.4 s per trajectory) — it simply does not
cover the actions (RT-03).

**9. `classify_intervention` fails closed.** An undeclared gene raises `UnclassifiedGeneError`
rather than defaulting to `R_ONLY`, exactly as its comment promises.

**10. The committed artefacts are clean.** 26 trajectories, 120 actions, all `REFERENCE`; zero
`sorryAx`, zero `ofReduceBool`; 4.9 % of verified actions have a `HEAVY_AUTOMATION` head and the
max-horizon-14 trajectory has none. `.venv/bin/python -m pytest` → **1275 passed, 1 skipped**,
matching the commit message.

---

## What I could not test, and why

* **Anything requiring a model call.** The brief forbids them. So: whether a real solver exploits
  the leakage channels of RT-19; whether the 64-rule rendered-prompt adversary is an adequate
  family (that is a scientific question, not an engineering one); whether contamination is
  realised; and whether an `Evaluator` that actually uses its `language=` argument would surface
  RT-08 as a live hole. The V0 evaluator is a hash function, so every fitness number I saw is
  noise by construction and I attacked the *plumbing*, not the measurement.
* **The four sealed splits.** Only the guard was tested; the files stay sealed.
* **Exhaustive Lean unsoundness search.** I attacked `sorry`/`admit`/`stop`/`sorryAx`,
  `native_decide`/`decide`, out-of-scope self-reference, forged and replayed `sid`s, and the
  `#print axioms` identity match. I did **not** attempt: an attack on the `lean_dojo_repl` elab
  itself, `Lean.Meta`/reflection tricks, `implemented_by`/`extern` shims, `unsafe` definitions
  reachable from a tactic, or a tactic that escapes the two-space-indented tactic block into a
  top-level command (I tried and could not — `_indent_tactic` prefixes every line — but I cannot
  prove no escape exists). "0 known critical exploits" is not "unexploitable".
* **`VerifiedTask`.** It does not exist in code, as the team discloses, so the interactive
  long-horizon path could not be attacked at all.
* **Scale and drift.** Two generations, 12 candidates, one population of 4. Nothing here says
  anything about selection dynamics, winner's curse (§30.4) or landscape ruggedness at pilot scale.
* **Concurrency.** No test of two processes appending to one record store, or two arenas sharing a
  workdir.
* **The mathlib checkout itself.** 18 GB of `.olean` taken as given; I did not verify the build's
  integrity or that `Lean4Repl.olean` matches its source.

---

## Which findings an evolutionary search would find on its own — ranked

A search optimises the reward it is given. In HC-V0 that reward is `+1` for `CLOSED_VERIFIED` and
`0` otherwise (trajectory arena), or `J_solve` (outer loop). Ranked by how quickly a search would
stumble into each, and how much it would pay off:

1. **RT-01 `native_decide` — minutes.** One allowed 13-character token; closes any decidable goal;
   full reward; no penalty. A search does not need to "understand" the exploit — it needs to sample
   the token once and observe reward 1.0. This is the finding that will actually bite. Its
   siblings `decide`, `omega`, `aesop`, `exact?`, `apply?` are also allowed by default and collapse
   the horizon to 1 while paying full reward: **the reward function pays for closure and charges
   nothing for horizon**, so search pressure runs directly against the thing being measured. That
   is a design point, not a bug, but it is the point at which the instrument stops measuring
   horizon.
2. **RT-14 macro-cost hiding — immediately, as a free rider on (1).** `KernelStepCount` is zero for
   every action and `J_cost` is prompt bytes, so nothing in the objective notices that one macro
   tactic did the work of fourteen. There is no signal to discourage (1).
3. **RT-13 `mutation_hash` re-roll — first multi-generation run with a stochastic evaluator.** No
   intent required: any proposer that re-emits an edge under a new proposal id gets a second
   independent draw, and the best-of-N is what the archive keeps. This is the classic winner's
   curse channel (§30.4) and it is open because `mutation_hash` is asserted rather than derived.
4. **RT-17 axiom-free false negative — slowly, as an anti-signal.** Selection would learn to avoid
   the cleanest proofs because they score `FAILED`. Mild, but it is selection pressure pointing the
   wrong way.
5. **RT-07 / RT-08 renderer blind spots — not under the current genome; immediately under the
   next.** The 14-family enum cannot express a lossy renderer with a compensating parser. The
   moment Layer B/C genes land or a genome supplies its own `StateRenderer` through the seam
   `arena_v0` advertises, the gate that is supposed to stop truth mutation stops covering it, and a
   search that can vary the renderer will find the appended-answer channel fast — it pays
   immediately and passes every gate.
6. **RT-19 leakage below the tripwire — only with a renderer under search control**, same
   condition as (5).

**Not reachable by search at all — author or operator only:** RT-02, RT-03, RT-04, RT-05, RT-06,
RT-10, RT-11, RT-12, RT-15, RT-16, RT-18, RT-20. These need write access to the artefacts or to the
call site. They are not less dangerous for that — RT-04 in particular is the field most likely to
be set wrongly in good faith, and RT-03 removes the net that would catch it — but they will not
emerge from optimisation. They will emerge from a hurried integration.

---

## Recommended order of fixes (recommended, not applied)

1. RT-01 — two lines, closes the only live soundness gap.
2. RT-03 + RT-04 — make `relive` replay the stored actions and make the actor an assertion; these
   two together restore the ability to catch RT-02, RT-05 and RT-06.
3. RT-05 + RT-18 — put `verifier_evidence` inside `content_hash` and check the two unused hashes.
4. RT-16 — stamp the league registry; refuse `verified=true` on stub observations.
5. RT-13 + RT-12 — derive `mutation_hash`; bind `parent_genome_id` to its hash.
6. RT-07 — decode the surface with the unbound base codec, before the genome grows a renderer gene.

---

*Suite, scripts and raw JSON: `research/phase9/redteam/` (`README.md` there lists every command and
the exact environment). Nothing under `arena/`, `tests/`, `spec/` or `artifacts/` was modified; the
only change to the working tree is the untracked `research/phase9/redteam/` directory and this
document.*
