# HC-V0.5 red team — the interactive path

**`attack_suite_version = hc-v0.5-redteam-2026-09-08`**

**Verdict.** The mathematics is sound; the *attribution* is not. Nothing I could build makes Lean
say yes to a false thing, makes a harness fault pay reward, or gets a reference tactic into the
Solver's prompt in the shipped configuration. What I could build, repeatedly and cheaply, is an
artefact that **claims a Solver did something a Solver did not do** — and a verification path that
cannot tell the difference. The single sharpest result: an episode whose every action was read
straight out of the LeanDojo record is emitted as `actor=SOLVER`,
`trust_tier=A_NATIVE_VERIFIED`, `kernel_verified=true`, `solver_actions == achieved`, and passes
`verify_bank(relive=True)` — the repository's strongest check — with **zero failures**.

Adapting manual §29's wording and refusing the word *unexploitable*:
**25 confirmed defects, 0 of them CRITICAL, under `attack_suite_version hc-v0.5-redteam-2026-09-08`.**
Seven are HIGH. **No CRITICAL exploit was found, so the milestone is not blocked on soundness** —
but no *autonomy* or *long-horizon capability* claim should be made from
`artifacts/trajectory/hc_v0_5_smoke.json` until V05-01, V05-02, V05-03 and V05-24 are closed,
because that artefact contains no evidence that would survive an audit.

The previous suite's four headline exploits were all re-run. **RT-01 (`native_decide`), RT-02 (the
published splice), RT-03 (relive replaying the source) and RT-13 (`mutation_hash` re-roll) are
genuinely closed** — before/after output in [Regression](#regression-against-hc-v0-redteam-2026-09-08).
**RT-04 (actor relabel) is not**, and RT-02/RT-03 are closed only against the *particular*
forgeries the previous suite wrote: one extra line each defeats the cheap checks that replaced them.

64 checks were executed; 37 recorded a defect and 27 recorded a defence holding. The defences are
in [Defences that held](#defences-that-held) and matter as much as the findings.

Everything is reproducible from `research/phase9/redteam_v05/`; raw JSON in
`research/phase9/redteam_v05/out/`.

---

## Findings

*Exploitable-by-search* asks §29's question: would an **automated evolutionary search** find this
by optimising the reward, as opposed to an **author or integrator** with write access?

| id | target | sev | status | one line | reproduction |
|---|---|---|---|---|---|
| V05-01 | 1 source-proof substitution | **HIGH** | CONFIRMED | an oracle-fed episode emits `actor=SOLVER`, `A_NATIVE_VERIFIED`, and passes `verify_bank(relive=True)`; nothing records where the tactic came from | `attack_emit_trajectory.py`, `attack_oracle_episode.py` |
| V05-02 | 7 model digest | **HIGH** | CONFIRMED | `verify_served()` exists and is never called; the manifest's solver digest is a module constant | `attack_episode_runner.py` → `E4` |
| V05-03 | 3 actor spoofing | **HIGH** | CONFIRMED | `build_trajectory` still rewrites every action's actor; a relabelled mathlib replay passes relive claiming `solver_actions=5`; the artefact's `"actor": "SOLVER"` is a string literal | `attack_forgery_v05.py` → `G3`; `attack_record_draws.py` → `R7`; `attack_episode_runner.py` → `E8` |
| V05-04 | 4 stale state identity | **HIGH** | CONFIRMED | two concurrent live Lean sessions of one task carry the *same* `kernel_key` **and** `record_key` — one still `OPEN` on a 127-byte goal, one `CLOSED_VERIFIED` on `no goals` | `attack_session_collision.py` |
| V05-05 | 5 action forgery | **HIGH** | CONFIRMED | every tactic replaced by `aesop` **and** the matching `verifier_evidence` rewritten (it is outside `content_hash`) passes `verify_bank(relive=False)` — the default — with zero failures | `attack_forgery_v05.py` → `G2` |
| V05-06 | 5 theorem splicing | **HIGH** | CONFIRMED | dropping the *optional* `session_id`/`problem_id` and splicing two theorems from one mathlib file yields `{achieved: 4, verified: 4}` from 3+1 that loads clean and passes the default check | `attack_legacy_splice.py` |
| V05-24 | 11 verifiability | **HIGH** | CONFIRMED | `run_episode` closes the task, so `emit_trajectory()` always raises: the HC-V0.5 runner emits **no** `VerifiedTrajectory`, and the committed artefact has no states, no `pp_sha256` and no kernel receipt | `attack_emit_trajectory.py` → `runner_can_emit_a_trajectory` |
| V05-07 | 6 retry exploitation | MEDIUM | CONFIRMED | the declared `ONE_DIAGNOSTIC_RETRY / max_retries=1` absorbed **6 rejections live** (40 scripted) when `skip` is interleaved; `skip` is accepted, is a no-op, and resets the counter | `attack_live_lean.py` → `L2`,`L2b`; `attack_policy_and_budget.py` → `P1` |
| V05-08 | 6 budget | MEDIUM | CONFIRMED | the model-action budget is not enforced by the task (4 permitted, 8 charged); 3 of the 5 declared caps are read nowhere in `task.py` | `attack_policy_and_budget.py` → `P2`,`P3` |
| V05-09 | §29 macro-cost hiding | MEDIUM | CONFIRMED | `constructor <;> simp <;> omega` is ALLOWED and costs `kernel_step_count=1`; the one live solve in this suite was a single `induction … <;> simp_all[flip]` | `attack_policy_and_budget.py` → `P6` |
| V05-10 | provenance | MEDIUM | CONFIRMED | `"selection": {}` in the committed artefact: `getattr(selection, "to_dict", lambda: {})()` and `TaskSelection` has only `manifest()` | `attack_episode_runner.py` → `E1` |
| V05-11 | provenance | MEDIUM | CONFIRMED | every step's `state_id` is `"?"` (the runner reads `backend_state_id`, the renderer emits `state_id`); `task_id` in the artefact is the `problem_id`, and the `vtask-` identity appears nowhere | `attack_episode_runner.py` → `E2`,`E3` |
| V05-12 | 6 failure policy | MEDIUM | CONFIRMED | a solver-side `PARSE_FAILURE`/`TRANSPORT_FAILURE` breaks the loop without stepping the task, so the declared policy never applies and the episode is filed `OPEN` | `attack_episode_runner.py` → `E7` |
| V05-13 | 9 attribution | MEDIUM | CONFIRMED | a dead model runtime is counted in `parse_failures` (the Solver's) and in **neither** `environment_errors` | `attack_episode_runner.py` → `E5` |
| V05-14 | 2 leakage | MEDIUM | CONFIRMED | `HashedLeakageGuard` has a 6-byte floor and never registers `full_name`, `file_path` or `pp_scope`; all four reach `goals_pp` and therefore the prompt | `attack_seal_and_leakage.py` → `S6`,`S7` |
| V05-15 | 2 leakage / parity | MEDIUM | CONFIRMED | a renderer implementing `declare_information` is believed: it can render an extra key and still pass `check_projection_parity` as `R_ONLY` | `attack_seal_and_leakage.py` → `S12` |
| V05-16 | 6 duplicate draws | MEDIUM | CONFIRMED | `harness_version` is an identity component and **not** a condition component: bumping it gives a second `FRESH` draw of the same edge in the same shard with `replicate:0000` | `attack_record_draws.py` → `R2b`,`R5` |
| V05-23 | 7 condition collision | MEDIUM | CONFIRMED | the HC-V0.5 manifest carries no `condition_id`, no `EvidenceActor` and no `ReplicateAuthorisation`, so `record.py`'s duplicate-draw machinery cannot see it at all | `attack_episode_runner.py` → `E10` |
| V05-17 | 6 duplicate draws | LOW-MED | CONFIRMED | `gene_changes` is never checked against the parent/child genomes; `intervention_class` is derived from a declaration | `attack_record_draws.py` → `R3` |
| V05-18 | reporting | LOW-MED | CONFIRMED | a crashed episode is filed `terminal_status: "OPEN"` — the `or "ENVIRONMENT_ERROR"` fallback can never fire | `attack_episode_runner.py` → `E6` |
| V05-19 | 4/10 stale state | LOW | CONFIRMED | a failed `reset()` leaves the *previous* episode's state attributed to the *new* session; `observe()` after `close()` returns a projection of a dead session reporting `TERMINAL_STATUS=OPEN` | `attack_state_identity.py` → `I2`,`I3` |
| V05-20 | 1 seal | LOW | CONFIRMED | `__slots__` blocks a new attribute name only: `task._probe` is reassignable, and an injected `arena_factory` closure is a retention channel the module's own scan claim does not cover | `attack_seal_and_leakage.py` → `S2b`,`S3` |
| V05-21 | 2 leakage | LOW | CONFIRMED | `TaskStepResult.info` (including the kernel receipt) is returned unchecked; the guard covers only `projection.rendered` and the diagnostic | `attack_seal_and_leakage.py` → `S10` |
| V05-22 | 2 leakage | LOW | CONFIRMED | `from_leandojo_record` runs the static leak filter and **records** the verdict rather than dropping; only `select_candidates` drops | `attack_seal_and_leakage.py` → `S11` |
| V05-25 | 4 identity | LOW | CONFIRMED | `KernelStateIdentity.rendered_under()` / `.from_dict()` mint an identity for any goal text with the kernel key intact | `attack_state_identity.py` → `I4` |

---

## V05-01 — an oracle-fed episode is indistinguishable from an autonomous one (HIGH)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam_v05/attack_emit_trajectory.py
.venv/bin/python research/phase9/redteam_v05/attack_oracle_episode.py
```

**Observed.** A real `VerifiedTask` on
`Mathlib/Data/Vector/MapLemmas.lean::Vector.map₂_flip`, driven by an `OllamaTacticSolver` whose
*transport* returns the record's own tactic:

```json
{"tactics_played":   ["induction xs, ys using Vector.inductionOn₂ <;> simp_all[flip]"],
 "tactics_recorded_in_the_source":
                     ["induction xs, ys using Vector.inductionOn₂ <;> simp_all[flip]"],
 "identical": true, "task_terminal": "CLOSED_VERIFIED", "reward": 1.0}
```

emitted and verified:

```json
{"actors": ["SOLVER"], "terminal_status": "CLOSED_VERIFIED", "kernel_verified": true,
 "trust_tier": "A_NATIVE_VERIFIED",
 "horizon": {"achieved": 1, "verified": 1, "solver_actions": 1, "reference_actions": 0},
 "verify": {"structural_passed": true, "relive_passed": true, "relive_matches": 1,
            "relive_failures": []}}
```

and, through the runner's own artefact shape, `"actor": "SOLVER"`, `"solved": true`, a genuine
64-hex `prompt_sha256`, and a manifest stamping the real
`d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`.

**Expected.** `episode.py`'s docstring: *"it never reads the reference proof.
`VerifiedTask` seals it and raises if it is present, so the runner **cannot** fall back to the
recorded tactic when the Solver fails."* That is true of the **task** and I could not break it
(see [Defences that held](#defences-that-held) 1–3). It is not true of the **runner**: the Solver
is a caller-supplied object satisfying a structural protocol, and `episode.main()` is the same
process that just read the LeanDojo record. The seal protects the environment from the answer; it
does not protect the record from the caller.

**Why it matters.** This is the whole HC-V0.5 claim. `TRAJECTORY_REPLAY` and `INTERACTIVE_TASK`
are separated by `arena/trajectory/task.py`'s module docstring as *the* distinction the file exists
to make real — and in the emitted evidence they are separated by a keyword argument and a string
literal. No reader of `hc_v0_5_smoke.json`, and no run of `verify_bank --relive`, can tell them
apart.

**Exploitable by an evolutionary search: no** (author/integrator only). It will not emerge from
optimisation; it will emerge from a hurried integration, and it is precisely the mistake a Phase-9
harness that already holds the records is most likely to make.

**Minimal fix recommended (not applied).**
1. Give `TacticProposal` a **provenance obligation** the task can check: `VerifiedTask.step`
   should take `(action, evidence)` where evidence carries the solver digest and the
   `prompt_sha256` the action was produced from, and refuse an action whose prompt hash is not
   the hash of the projection it just returned. That makes "this action was produced by a policy
   looking at this state" checkable rather than asserted.
2. Record that binding in `TrajectoryAction` (a `provenance_digest` field inside
   `semantic_core()`), so `verify_bank` can re-derive it.
3. Until (1) lands, stamp `solver.digest`, `solver.runtime` and the per-action `prompt_sha256`
   into the emitted trajectory's provenance notes, and have `_structural_problems` refuse a
   `SOLVER` trajectory that carries none.

---

## V05-02 — the solver digest is asserted, never verified (HIGH)

**Reproduction:** `attack_episode_runner.py` → `E4`.

**Observed.** `episode.py` contains no reference to `verify_served`. With a transport whose
`/api/tags` reports digest `deadbeef…`, `run_episode` completes and
`build_manifest` stamps `"model_digest": "d49fd9e0da45e486918c8731…"` — the module constant
`RECORDED_SOLVER.model_digest`. A live probe of the running Ollama confirms the constant is
*correct today* (`identity_from_live()` matches on every served field, `assert_matches` passes),
which is exactly why nobody notices that it is never checked.

**Expected.** `OllamaTacticSolver.verify_served`'s docstring: *"Refuse to run unless the live
runtime serves exactly the recorded model."* `SolverIdentityMismatch`'s docstring: *"Never
downgraded to a warning."* Neither is reachable from `episode.main()`.

**Why it matters.** `OLLAMA_HOST` is environmental, a tag can be re-pulled, and the digest is the
identity of the policy under measurement — the thing every fitness number is about. This is §29's
model-digest spoofing class, present by omission rather than by attack.

**Minimal fix.** Call `solver.verify_served()` once in `episode.main()` before the first episode,
store the *served* identity (not `RECORDED_SOLVER`) in the manifest, and record the comparison.

---

## V05-03 — the actor is still a caller assertion (HIGH, carry-over of RT-04)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam_v05/attack_forgery_v05.py       # G3
.venv/bin/python research/phase9/redteam_v05/attack_record_draws.py      # R7
.venv/bin/python research/phase9/redteam/attack_relive.py                # forged_solver_actor
```

**Observed.** `LeanTrajectoryArena.build_trajectory` still contains
`actions = tuple(replace(action, actor=actor) for action in self._actions)`, and
`require_single_actor` is called nowhere on that path. Relabelling a committed 5-action REFERENCE
replay to `SOLVER` and resealing gives
`{"achieved": 5, "verified": 5, "solver_actions": 5, "reference_actions": 0}` which passes both
`verify_bank(relive=False)` **and** `verify_bank(relive=True)`:

```json
"v05_forged_solver_actor": {"structural_passed": true, "relive_passed": true,
                            "relive_matches": 1, "relive_failures": []}
```

**Expected.** RT-04's recommended fix was *"make `build_trajectory(actor=…)` an assertion —
`require_single_actor(actor)` before emitting — rather than a rewrite."* The **ledger** half of
that fix landed and is strong (`EvidenceActor` in the identity and the condition,
`ActorPoolingViolation`, `ReferenceFitnessNotRepresentable` — all verified holding, below). The
**trajectory** half did not.

**Minimal fix.** Two lines: stamp the actor at the moment of choice (`ReplayDriver` → REFERENCE,
public `step()` → SOLVER, which `arena_v0.step` already does) and change `build_trajectory` to
`draft.require_single_actor(actor)` instead of `replace(...)`.

---

## V05-04 — two concurrent live sessions of one task are the same state (HIGH)

**Reproduction:** `.venv/bin/python research/phase9/redteam_v05/attack_session_collision.py`

**Observed**, on two real Lean REPL processes:

```json
{"problem": "Mathlib/Data/Vector/MapLemmas.lean::Vector.map₂_flip",
 "A_tactic": "skip",  "A_terminal": "OPEN",             "A_goal_bytes": 127,
 "B_tactic": "induction xs, ys using Vector.inductionOn₂ <;> simp_all[flip]",
 "B_terminal": "CLOSED_VERIFIED", "B_goal_bytes": 8,
 "kernel_key_A": "LEAN4_TACTIC_STATE_PP|vtask-c6da58b670145797c39d5b4d#ep0001|1",
 "kernel_key_B": "LEAN4_TACTIC_STATE_PP|vtask-c6da58b670145797c39d5b4d#ep0001|1",
 "same_kernel_state_as": true, "record_keys_equal": true, "goal_digests_equal": false}
```

**Expected.** `KernelStateIdentity.kernel_key`'s docstring: *"Two identities with equal kernel keys
name the **same saved backend state**: the backend itself says so, the state can be re-entered
with `branch()`."* The backend says no such thing. `session_id` is the label
`f"{task_id}#ep{episode_index:04d}"` minted by `VerifiedTask.reset`, and `task_id` is a pure
function of the task's semantic core — so two `VerifiedTask` objects built from one probe are one
`task_id`, and their first episodes are both `#ep0001`. `record_session_id` is
`derive_session_id(probe, policy, seed)`, content-addressed from the *opening conditions*, so it
collides too. **No field in `KernelStateIdentity` distinguishes two concurrent live sessions of
one task**, and the module's own text names the live/record distinction as the reason both are
carried side by side.

**Why it matters.** This is not an attack so much as ordinary use: two workers evaluating the same
task, a retry after a crash, or an A/B of two renderers on one task all produce it. Any cache,
bank or branch operation keyed on `kernel_key` will silently mix them.

**Minimal fix.** Mint the live session id from something the process actually owns — a UUID4 or
the backend subprocess's pid+start time — and keep the current label as a separate
`episode_label` field. The `reelaboration_key` guarantee (verified holding, below) is unaffected.

---

## V05-05 / V05-06 — the default bank check is defeated by editing what `content_hash` does not cover (HIGH)

**Reproduction**

```bash
.venv/bin/python research/phase9/redteam_v05/attack_forgery_v05.py     # G2
.venv/bin/python research/phase9/redteam_v05/attack_legacy_splice.py
```

**V05-05, observed.** The previous suite's action swap is now caught *before Lean runs*, by the
new evidence↔action cross-check in `_structural_problems`. That check compares `actions` with
`verifier_evidence`, and **`verifier_evidence` is still outside `semantic_core()`** (RT-05, never
fixed). Rewriting both in step and resealing:

```json
"v05_forged_action_and_evidence": {
  "structural_passed": true, "structural_failures": [],
  "relive_passed": false,
  "relive_failures": ["vt-a1f7cada31c265aaf6ed7d2f: relive mismatch: stored action 0 ('aesop')
                       produced a state the artefact does not record"]}
```

Original tactics: `["ext1 x", "push_cast", "simp_rw [...]", "push_cast", "rw [...]"]`, all replaced
by `aesop`. The forgery passes the **default** verification and is caught **only** by `--relive`.

**V05-06, observed.** `BackendStateEnvelope.session_id`/`problem_id` are optional and
`semantic_core()` includes them *only when non-empty*, documented as *"an absent field is an absent
claim"*. Deleting them turns a modern record into a legacy-shaped one that reseals cleanly, and
`_assert_one_episode` then falls back to the scope invariant — which two theorems declared in one
mathlib file satisfy byte for byte:

```json
{"file_path": "Mathlib/Analysis/Normed/Group/AddTorsor.lean",
 "theorem_a": "…::edist_vsub_vsub_le", "horizon_a": 3,
 "theorem_b": "…::dist_vsub_cancel_left", "horizon_b": 1,
 "scopes_identical": true,
 "splice": {"loads_without_error": true,
            "claimed_horizon": {"achieved": 4, "verified": 4, "kernel_step_count": 4}},
 "verify": {"structural_passed": true, "structural_failures": [],
            "relive_passed": false}}
```

A 3-step and a 1-step proof become a "4-step verified trajectory" that loads clean and passes the
default check.

**Expected.** `VerifiedTrajectory`'s docstring says the episode invariants *"refuse it now, and
they refuse it **without** Lean."* They refuse the published forgery. They do not refuse a forger
who reads the docstring, which names the residue itself: *"two theorems that happen to be declared
in byte-identical scopes are indistinguishable to a record that carries no binding at all"* — and
whether a record carries a binding is the forger's choice.

**Why it matters together.** `--relive` is a flag, not the default (`build_parser`), it needs the
Lean toolchain plus a streaming pass over the 373 MB split, and it is the only layer that catches
either forgery. Any statement of the form "the bank verifies" that does not say `--relive` is
worth very little.

**Minimal fix.** (a) put a `verifier_evidence` digest inside `semantic_core()` — RT-05's original
recommendation, now load-bearing for two checks instead of none; (b) make the session binding
**required** for records at the current `schema_version` and keep the optional path only for
records declaring the older schema; (c) make `--relive` the default and add `--no-relive` for the
cheap path, so the affordable check is the one you have to ask for.

---

## V05-24 — the interactive runner emits nothing that can be re-verified (HIGH)

**Reproduction:** `attack_emit_trajectory.py` → `runner_can_emit_a_trajectory`.

**Observed.**

```json
{"emitted": false, "episode_solved": true,
 "error": "TaskStateError: reset() must be called before the task can be driven",
 "why": "run_episode uses `with task as active:` and __exit__ calls close()"}
```

`run_episode` wraps the task in `with task as active:`; `VerifiedTask.__exit__` calls `close()`,
which sets `_arena = None`; `emit_trajectory()` starts with `self._require_arena()`. So the
emission path is unreachable from the shipped runner, and `episode.main()` never calls it anyway.

The committed `artifacts/trajectory/hc_v0_5_smoke.json` therefore contains, for its 4
`CLOSED_VERIFIED` episodes: the tactic strings, a terminal status, a prompt hash, token counts —
and **no states, no `pp_sha256`, no `verifier_evidence`, no `#print axioms` output, and
`state_id: "?"` on every step** (V05-11). There is no artefact a re-verification could consume.

**Expected.** `VerifiedTask.emit_trajectory`'s docstring describes exactly this bridge, and
`verify_bank(relive=True)` exists to re-execute it. When driven by hand the bridge works and the
result verifies (that is V05-01's output). The runner simply does not use it.

**Minimal fix.** Call `emit_trajectory()` inside the `with` block, before `__exit__`, and write the
trajectories alongside the summary as a bank; then `hc_v0_5_smoke` becomes re-verifiable by the
machinery that already exists.

---

## V05-07 — `max_retries=1` bounds a run of failures, not an episode (MEDIUM)

**Reproduction:** `attack_live_lean.py` → `L2`,`L2b`; `attack_policy_and_budget.py` → `P1`.

**Observed, in real Lean.** `skip` is `ACCEPTED_TRANSITION`, leaves `goal_digest` unchanged, costs
`kernel_step_count=1`, and restores `retries_remaining` to 1. Alternating a bogus tactic with
`skip` on `Vector.map₂_flip`:

```json
{"rejections_absorbed": 6, "declared_max_retries": 1, "terminal": "OPEN",
 "model_actions": 15}
```

Scripted, with a larger budget: **40 rejections absorbed**, episode still `OPEN`. The consecutive
baseline is 2 rejections → `FAILED`, as declared.

**Expected.** `FailurePolicySpec` is declared *"before any Solver performance was observed"* and
`ONE_DIAGNOSTIC_RETRY / max_retries=1` is written into every episode's provenance. `RetryScope.
PER_CONSECUTIVE_RUN` is documented (*"an accepted transition resets it"*) — so this is a disclosed
*design*, but its consequence is not: the number of invalid actions an episode absorbs is
unbounded by the failure policy and is set instead by the arena's `attempt_budget`. The advisory
`no_op_suspected` flag is computed on exactly this case and, by design, gates nothing.

**Exploitable by an evolutionary search: yes — first on the list.** A policy that emits `skip`
when unsure survives strictly longer at zero cost, and "actions accepted" and "horizon" both rise.

**Minimal fix.** Either count a no-op (`pp_sha256` unchanged) as not resetting the run, or add a
`PER_EPISODE` cap alongside the consecutive one and report both. `RetryScope.PER_EPISODE` already
exists and `_episode_retries_used` is already maintained — it is simply not consulted under the
default scope.

---

## V05-08 — three of the five declared budget caps are read nowhere (MEDIUM)

**Reproduction:** `attack_policy_and_budget.py` → `P2`,`P3`.

Source references in `arena/trajectory/task.py`: `budget.model_actions` ×3, `budget.wall_clock_s`
×3, `budget.kernel_steps` ×0, `budget.verifier_calls` ×0, `budget.tool_calls` ×0. A task capped at
`kernel_steps=1` spends 5. And the model-action cap is not enforced by the task at all — only the
*arena's* `attempt_budget` can end an episode, and an action that never reached the backend does
not consume one:

```json
{"budget_model_actions": 4, "model_actions_charged": 8, "arena_attempts": 4,
 "attempts_remaining_reported": 0, "terminal": "BUDGET_EXHAUSTED"}
```

`attempts_remaining` clamps at 0 and is shown to the Solver in the observation while the episode
continues — a false declaration in `Ω_L`'s output.

**Expected.** `_lean_arena_factory`'s docstring: *"the arena's `attempt_budget` is set to the
task's model-action budget so the two agree on `BUDGET_EXHAUSTED`"*, and `task.py`'s module
docstring: *"The model-action budget does **not** diverge."* Both hold only while every attempt
reaches the backend.

**Minimal fix.** Terminate on `attempts_remaining == 0` in `_finish_attempt`, and either enforce
the three count caps or type them `int | None` with `None` meaning NOT_CAPPED — the discipline
`minimal_proof_length` already applies.

---

## V05-09 — macro-cost hiding is back in the action cost (MEDIUM)

`ActionCost.kernel_step_count` is `1 if accepted else 0`. Under the default `record_only` policy
these are all ALLOWED and all cost 1: `constructor <;> simp <;> omega`,
`intro h; exact h.symm; rfl`, `repeat (first | rfl | simp | ring | omega | aesop)`,
`all_goals (simp; ring)`, `decide`, `native_decide`.

**Expected.** `ActionCost`'s docstring: *"`kernel_step_count` is the post-lowering cost that a
future action macro must not be able to hide. At V0's granularity one accepted tactic is one
lowered action and one kernel step."* `docs/HC_V0_5_INTERACTIVE_TASK_SPEC.md` §5 says the six
counters are *"what stops an action macro bundling many kernel operations into one model-facing
move and appearing cheap."* A `<;>` combinator **is** an action macro and it is legal under the
default policy today, so the premise of both sentences is already false. All four solves in the
committed smoke run are one-to-four `simp [...]` calls, and the recorded mathlib proof of the one
goal this suite closed live is a single `induction xs, ys using Vector.inductionOn₂ <;>
simp_all[flip]` — one model action, one "kernel step", an induction and a simp set.

**Fix:** as RT-14 recommended — populate it from something Lean can report (heartbeats consumed
per declaration), or type it `int | None` with `None` = NOT_MEASURED.

---

## V05-10 / V05-11 — the artefact binds nothing (MEDIUM)

`build_manifest` does `getattr(selection, "to_dict", lambda: {})()`. `TaskSelection` exposes
`manifest()` and no `to_dict`, so the default fires and the committed artefact contains
`"selection": {}` — losing the seed, `scan_limit`, `train_json`, the discard ledger, the leakage
ledger, `sealed_splits_not_read`, the contamination note and every task's `task_id` and
`source_hash`.

`run_episode` reads `projection.rendered.get("backend_state_id", "?")`; `BackendNativeRenderer`
emits `state_id`. Every step in the committed artefact has `state_id: "?"`. And
`EpisodeResult(task_id=task.problem_id, …)` — the `vtask-…` identity that covers the budget, the
failure policy, the seal and the source hash is in no artefact anywhere.

**Fix:** one character in the key name, `selection.manifest()`, and `task_id=task.task_id`.

---

## V05-12 / V05-13 — a harness fault is charged to the Solver (MEDIUM)

A `TRANSPORT_FAILURE` (dead Ollama) is counted by `EpisodeResult.parse_failures`
(`proposal_status != OK`) and by *neither* of `summarise`'s `environment_errors` conditions:

```json
{"step_proposal_status": ["TRANSPORT_FAILURE"],
 "summary": {"parse_failures": 1, "environment_errors": 0}, "episode_terminal": "OPEN"}
```

And a malformed proposal never reaches `task.step()`, so `ONE_DIAGNOSTIC_RETRY` — the policy whose
entire purpose is *"an environment that terminates on the first parse slip measures formatting,
not mathematics"* — never applies to the one failure it was written for; the episode is filed
`OPEN` with `retries_remaining` untouched.

This is the mirror image of §28's rule. The rule "an environment error is never a mathematical
failure" is enforced correctly **inside** `VerifiedTask` (verified holding, below) and inverted in
the runner's summary.

**Fix:** split `EpisodeResult.parse_failures` into `solver_parse_failures` (PARSE_FAILURE,
TRUNCATED) and `harness_failures` (TRANSPORT_FAILURE, PROMPT_OVER_BUDGET); count the latter in
`environment_errors`; and route a solver parse failure through `task.step()` (or an explicit
`task.charge_failure()`) so the declared policy governs it.

---

## V05-14 / V05-15 — what the leakage guard does not register (MEDIUM)

`HashedLeakageGuard` caught a 44-byte reference tactic injected into `goals_pp` and into the
diagnostic (both defences, below). It does not catch:

* a reference tactic shorter than `min_secret_len = 6` bytes — `ring`, `simp`, `rfl`, `ext`,
  `omega` — which is not settable through `VerifiedTask.from_probe`;
* `probe.full_name`, `probe.file_path` or `pp_scope.current_namespace`, none of which is ever
  registered as a secret. All three reached the prompt in the test.

Measured on the live path this did **not** fire: 5 real tasks, 14 reference tactics, 3 of them
under the floor (`ext y`, `ext`, `rfl`), **0 verbatim leaks at any length** in the live initial
observation, and `full_name`/`file_path` absent from all 5. The hole is real; the shipped
configuration does not walk into it.

`WorkspaceProjectionIdentity.from_information` believes `declare_information`: a renderer that
renders `coach_note` and declares only `{GOAL_TEXT, GOAL_COUNT}` gets a `projection_hash` equal to
an honest renderer's, and `check_projection_parity(..., R_ONLY)` returns
`parity_holds=true, admissible=true`. The conservative `from_rendered` fallback does fold the
extra key in — so the *undeclared* path is safe and the *declared* path is not, which is the
opposite of the incentive you want. The class docstring discloses this (*"only as good as the
renderer's declaration"*); it is not enforced anywhere.

**Fix:** drop the length floor for the runtime guard and match on whole tokens instead; register
`full_name` and `file_path` as secrets; and have `project_workspace` cross-check that every
rendered key is accounted for by a declared slot, folding the remainder in as
`UNDECLARED:` exactly as the fallback does.

---

## V05-16 / V05-17 / V05-23 — duplicate draws after the RT-13 fix (MEDIUM)

RT-13's own channel is closed: re-rolling `proposal_id` and `mutation_hash` now returns
`SAME_CONDITION_REUSE` and writes nothing. Six identity components sit outside
`CONDITION_COMPONENTS`: `schema_version`, `harness_version`, `parent_genome_hash`,
`child_genome_hash`, `intervention_class`, `replicate_id`. Of these, `parent`/`child` are the
experiment, `replicate_id` is authorised, `schema_version` is validated against a known set — and
**`harness_version` is a free string**:

```json
{"harness_version": {"scope": "FRESH", "same_condition_id": true,
                     "record_ids_differ": true, "replicate_id": "replicate:0000"}}
```

A harness that bumps its own version between generations — entirely normal — silently re-draws
every edge it re-evaluates, in the same condition shard, reported as a primary draw.

`intervention_class` is the same shape and cannot be varied *today* only because all fourteen
declared genes are `R_ONLY` and an undeclared gene fails closed. That is restriction of the gene
table, not a check: `gene_changes` is a declaration and `MutationDescriptor.__post_init__` only
requires it to be non-empty; no parent/child genome diff is ever consulted (V05-17). The moment a
non-`R_ONLY` family lands, one edge can be drawn twice by relabelling.

Separately (V05-23), the HC-V0.5 manifest carries no `condition_id`, no `EvidenceActor` and no
`ReplicateAuthorisation` at all, so none of this machinery can see interactive results.

**Fix:** move `harness_version` into `CONDITION_COMPONENTS` (a different harness *is* a different
condition) or out of the identity; verify `gene_changes` against the two genomes at construction;
and give the episode manifest a `condition_id`/`actor`/`replicate_id` block.

---

## V05-18 … V05-25 — the low cluster (LOW to LOW-MEDIUM)

Each is a one-line reproduction; each fix is one to three lines.

**V05-18 — a crashed episode is filed `OPEN`.** `attack_episode_runner.py` → `E6`. `EpisodeResult`
is constructed with `terminal_status="OPEN"`, and the exception handler does
`result.terminal_status = result.terminal_status or "ENVIRONMENT_ERROR"` — `"OPEN"` is truthy, so
the fallback is dead code. An arena that dies mid-episode yields
`{"terminal_status": "OPEN", "error": "RuntimeError: …"}`. *Fix:* set it unconditionally.

**V05-19 — state carried across a failed `reset()`, and `observe()` after `close()`.**
`attack_state_identity.py` → `I2`, `I3`. `reset()` advances `_episode_index` and `_session`
**before** the arena is opened, so if the arena raises, `_current` still holds the previous
episode's state and `state_identity()` attributes it to `#ep0002`
(`goal_digest_unchanged: true, session_before: …#ep0001, session_after: …#ep0002`). Separately,
`observe()` and `state_identity()` have no arena precondition — only `step()` does — so after
`close()` they return a projection of a dead session reporting `TERMINAL_STATUS=OPEN`.
*Fix:* clear `_current`/`_start_identity` at the top of `reset()`, and give `observe()` the same
`_require_arena()` precondition `step()` has.

**V05-20 — what `__slots__` actually buys.** `attack_seal_and_leakage.py` → `S2b`, `S3`.
`task.smuggled_reference = …` is refused, as the module docstring says. But every *declared* slot
stays writable, so `task._probe = <probe with reference_tactics>` is accepted and the constructor's
check is not re-applied. And the module's claim — *"a test can walk every object reachable from a
task and assert that no reference tactic string is present"* — is true of the shipped construction
(verified: zero hits over slots, `__dict__` and closure cells to depth 7) but not of the public
`arena_factory` seam, whose closure cells the same walk finds carrying the reference proof when a
caller closes over the probe. *Fix:* make `_probe` a read-only property over a private
`__slots__` entry set once, and re-assert `not probe.reference_tactics` in `reset()`.

**V05-21 — `TaskStepResult.info` is not leak-checked.** `attack_seal_and_leakage.py` → `S10`.
The guard covers `projection.rendered` and the diagnostic. `info` — which carries the kernel
receipt under `"kernel"` — is forwarded to the caller unchecked. Nothing in the shipped path puts
reference text there, but the guard's coverage is narrower than its docstring implies.
*Fix:* run `leakage_guard.assert_clean(canonical_json(dict(info)), where="the step info")`.

**V05-22 — the static filter in `from_leandojo_record` annotates rather than drops.**
`attack_seal_and_leakage.py` → `S11`. A record whose `state_before` contains its own gold tactic
builds a task; `provenance.static_leakage_filters` records `["TACTIC_IN_STATE_BEFORE"]` and the
task plays. The shipped path is safe because `select_candidates` drops such records before
`from_leandojo_record` sees them, and the docstring says the verdict *"is recorded in provenance"*.
The hazard is a future caller that builds tasks directly. *Fix:* add
`refuse_on_leak: bool = True`.

**V05-25 — unchecked identity constructors.** `attack_state_identity.py` → `I4`.
`KernelStateIdentity.rendered_under(text, scope)` mints an identity for arbitrary goal text with
the kernel key unchanged, and `from_dict` accepts any `goal_digest`/`state_id`. Both are
documented provenance carriers rather than verifiers, and neither consults a backend; noted for
completeness because `identity_hash` is offered as *"a provenance stamp"*.

---

## Regression against `hc-v0-redteam-2026-09-08`

Every previous exploit was re-run against the current tree. Pre-run copies of the previous suite's
JSON are preserved in `research/phase9/redteam_v05/out/prior/`.

| previous finding | before | after | verdict |
|---|---|---|---|
| **RT-01** `native_decide` | `terminal_status: CLOSED_VERIFIED`, `reward: 1.0`, `verified: true` | `terminal_status: FAILED`, `reward: 0.0`, `verified: false`, `untrusted_axioms: ["Lean.ofReduceBool"]`, allow-list `[Classical.choice, Quot.sound, propext]` | **CLOSED** |
| **RT-02** theorem splice | the published splice loaded clean, `{achieved: 10, verified: 10}` | `attack_trajectory_integrity.py` now **dies at line 129**: `TrajectoryIntegrityError: state 6 was rendered under a different elaboration scope than state 0` — the forgery cannot even be constructed | **CLOSED for that forgery**; see V05-06 for the variant that still works |
| **RT-03** relive replays the source | `forged_action_swap: {"passed": true, "relived": 1, "relive_matches": 1}` | `forged_action_swap: {"passed": false, "relived": 0, …}` — caught by the new evidence↔action check; and the *stronger* coordinated forgery is caught by relive itself | **CLOSED**; see V05-05 for the residue in the default mode |
| **RT-04** actor relabel | one episode → a REFERENCE and a SOLVER record, both self-consistent | `forged_solver_actor: {"passed": true, "relived": 1, "relive_matches": 1}` — **unchanged at the trajectory layer**; closed at the ledger layer | **OPEN** (V05-03) |
| **RT-13** `mutation_hash` re-roll | two `FRESH` records for one edge | `SAME_CONDITION_REUSE`, nothing written; `proposal_id`/`mutation_hash` are in `PROPOSAL_BOOKKEEPING_FIELDS` and in no hash | **CLOSED**; new channel at V05-16 |
| **stub fitness** | stub numbers reportable | `StubFitnessNotRepresentable` / `ReferenceFitnessNotRepresentable` raise at construction; `replace(reference_record, actor=SOLVER)` → `FitnessRepresentationError` | **CLOSED (type level)** |
| **RT-14** `KernelStepCount` always 0 | `kernel_step_count: 0` everywhere | `Horizon.kernel_step_count` now sums `action.kernel_steps` and reports 5 on a 5-action trajectory | **CLOSED for counting**; the macro question is V05-09 |

---

## Defences that held

Each was attacked with a script that would have recorded a defect had it worked.

1. **The seal is real.** `VerifiedTask.__init__` refuses a probe carrying `reference_tactics`.
   A deep object-graph walk of a task built through the **shipped** path — every slot, every
   `__dict__`, every function closure cell, depth 7 — finds **no reference-proof string**
   (`S2`). The same walk over a `TaskSelection` finds none (`S2c`). With every action rejected,
   a full scripted episode plays only the "solver's" tactics and ends `FAILED` (`S4`).
2. **The prompt allow-list works.** An observation carrying `reference_proof`,
   `remaining_tactics`, `full_name` and `pp_scope` yields a prompt containing only the goal
   (`S8`). `observed_state_text` reads one key and there is no fallback.
3. **The hashed guard catches what it registers.** A 44-byte sealed tactic appended to `goals_pp`
   → `AnswerLeakageError` naming only a digest prefix (`S5`); the same tactic in the backend
   diagnostic → refused (`S9b`); past the 400-char cap it is truncated away rather than shown
   (`S9`).
4. **`sorry` is refused at three independent layers, live.** `sorry`, `«sorry»` and
   `exact @sorryAx _ _ true` → `SORRY_REFUSED`/`UNSUPPORTED` with the reason
   *"tactic mentions unconditionally refused token(s)"*; `so​rry` (zero-width space) slips
   the Python policy and Lean answers `<stdin>:1:1: unknown tactic`; `rfl /-` →
   `unterminated comment`, and because the `#print axioms` line would be commented out the
   kernel check fails **closed**. Reward 0 in every case.
5. **RT-01 stays closed end to end.** See the regression table.
6. **The grammar and parser are strict.** Of 36 hostile wire payloads, 14 die at parse: fenced
   JSON, a preamble, two concatenated objects, an extra key, a Cyrillic-`с` `taсtic` key, a
   fullwidth `ｔactic` key, an empty or whitespace tactic, `null`/list/dict values, an array root,
   a bare string, a UTF-8 BOM. `decode_action` refuses a NUL byte.
7. **A harness fault is never a mathematical failure — inside the task.** `TIMEOUT` →
   `TOOL_TIMEOUT`/`ERROR_BACKEND`, `BACKEND_DEAD` → `ENVIRONMENT_ERROR`, `SESSION_EXPIRED` →
   `EPISODE_ABANDONED`; all with `reward 0.0`, `is_mathematical_failure=false`,
   `attributable_to_solver=false` and `retries_remaining` untouched (`P4`).
8. **Terminals are absorbing.** A timed-out episode cannot be relabelled: `task.step()` after a
   terminal raises `TaskStateError`, and `_absorb`/`_set_terminal` refuse a downgrade (`P5`).
   `abandon()` is never filed as a failure or a solve (`P8`). The wall-clock cap fires (`P7`).
9. **No stale projection on the rejection path.** A rejected action returns the *unchanged*
   current state; the observed sequence matched the expected one exactly (`I5`).
10. **`reelaboration_key` does what it claims.** Two independent live Lean sessions on one task
    reached initial states with **equal** re-elaboration keys — the documented, session-independent
    guarantee — while their kernel keys were meaningless (that is V05-04).
11. **Live leakage is zero.** 5 real tasks, 14 reference tactics, an independent recount with **no
    length floor** over the live initial observation: 0 verbatim leaks, `full_name` and
    `file_path` absent from all 5. `select_candidates` does drop leaking records
    (`LEAKAGE_FILTER`).
12. **The ledger half of RT-04 is strong.** `actor` is in both the identity and the condition, so
    one episode under two actors is two records in two shards; `records()` and `summary()` raise
    `ActorPoolingViolation` across actors; `replace(reference_record, actor=SOLVER)` raises
    `FitnessRepresentationError` because the vector it carries was licensed for REFERENCE.
13. **`ReplicateAuthorisation` refuses every unauthorised second draw tried**: a bare
    `replicate:0002`, a nonce id `draw-zzzzzzzz`, one stealing the reserved `PRIMARY_DRAW`
    authoriser, and a primary carrying a reason. An authorised replicate is accepted, as intended.
14. **`classify_intervention` fails closed** on an undeclared gene rather than assuming `R_ONLY`.
15. **`schema_version` is validated** against a known set, so it cannot be used as a draw nonce.
16. **The undeclared-renderer path is conservative**: `from_rendered` folds an unknown key into
    `UNDECLARED:` and the parity check correctly reports a difference (`S12b`).
17. **`result_hash` is deterministic** and separates runs that differ mathematically: two
    identical scripted runs hash identically; changing one tactic changes the hash (`E9`).
18. **`relive` genuinely re-executes the stored actions.** The honest control passes
    (`relive_matches: 1`); the coordinated forgery, the legacy splice and the promoted
    `CLOSED_VERIFIED` all fail there and only there.
19. **The sealed splits were never opened.**
20. **The repository's own suite is green.** `.venv/bin/python -m pytest -p no:cacheprovider`
    → **`1483 passed, 1 skipped in 180.41s`**, exit code 0. Corroborated independently by a
    JUnit run (`--junitxml`): `tests=1484, failures=0, errors=0, skipped=1`. Run before and
    after this suite with the same result.

---

## Are the disclosed limitations enforced, or only written down?

The directive lists four limitations as disclosed and therefore not findings. What is testable is
whether each is **structural** (a reader cannot be misled) or **conventional** (a reader can be).
`attack_disclosures.py`.

| disclosure | status | evidence |
|---|---|---|
| the model is weak on hard mathlib goals | **not tested** | no generation call was made |
| the retry re-proposes the identical tactic, because the diagnostic never reaches the Solver and decoding is deterministic | **ENFORCED, structurally** | `build_prompt`/`observed_state_text` read `goals_pp` and nothing else (`S8` proves the allow-list holds against a hostile observation); `FROZEN_DECODING` is `temperature=0.0, seed=20260908`. The disclosure is a consequence of two frozen objects, not a convention that could drift |
| contamination is unresolved | **STAMPED, not enforceable** | `TaskProvenance.contamination` defaults to `CONTAMINATION_NOTE`; the committed manifest carries `contamination` and `scientific_status: ENGINEERING_SMOKE_NOT_A_RESULT`. Nothing refuses a `HISTORICALLY_EXPOSED` problem — nothing can. The stamp is the honest response |
| `VerifiedTask`'s terminal can diverge from the emitted trajectory's (`ABANDONED`) | **ENFORCED** | a live task driven to `FAILED` emits `terminal_status: ABANDONED`, and the provenance notes carry `task_terminal_status=FAILED`, `task_terminal_outcome=UNRECOVERABLE_INVALID_ACTION`, `failure_policy=ONE_DIAGNOSTIC_RETRY`. The divergence is recoverable from the emitted record alone |

**V05-07 is not the disclosed retry defect.** The disclosure is that the retry is *useless* (the
Solver re-emits the same tactic). V05-07 is that the retry *allowance* is unbounded: with any
accepted no-op interleaved, `max_retries=1` absorbed 6 rejections live and 40 scripted. The first
makes the policy do nothing; the second makes it say something false.

---

## What I could not test, and why

* **Whether the live model exploits any of this.** No generation call was made; the budget was
  spent on Lean instead. Three read-only Ollama endpoints were queried to compare digests. So:
  whether a real policy discovers the `skip` retry-reset (V05-07) or the `<;>` macro (V05-09) is
  untested — I established only that both are legal, cheap and rewarding.
* **The four sealed splits.** Only the guard that refuses them.
* **Concurrency at scale.** V05-04 is demonstrated with two sessions in one process. Two
  *processes* sharing an `EvolutionRecordStore` or a Lean workdir is untested.
* **The mathlib build.** 18 GB of `.olean` taken as given; `Lean4Repl.olean` not checked against
  its source.
* **Exhaustive Lean unsoundness.** I attacked `sorry`/`sorryAx`/`admit`/`stop` in seven spellings,
  `decide`/`native_decide`, a zero-width-space identifier, an unterminated block comment, a line
  comment, a 2 500-character tactic, embedded newlines and a NUL byte. I did **not** attempt
  `implemented_by`/`extern` shims, `unsafe` definitions reachable from a tactic, `Lean.Meta`
  reflection, or an attack on the `lean_dojo_repl` elaborator itself.
* **Whether `--relive` is affordable as a default.** It costs ≈ 2–5 s per trajectory plus one
  streaming pass over the 373 MB split. I recommend making it the default (V05-05/06) without
  having measured that at bank scale.
* **Scale and drift.** 5 live tasks, 1 live solve, 1 emitted trajectory. Nothing here speaks to
  selection dynamics or to the 30-episode smoke's statistics.
* **Contamination.** Unchanged and unresolved; `Vector.map₂_flip` closing in one recorded tactic
  is exactly the case the `HISTORICALLY_EXPOSED` note is about.

---

## What an automated search would find on its own — ranked

1. **V05-07, `skip` as a retry reset — immediately.** One always-accepted no-op token converts a
   `max_retries=1` episode into an unbounded one and raises both "accepted transitions" and
   "episode length". Pure reward, no penalty, and `no_op_suspected` gates nothing by design.
2. **V05-09, combinator macros — immediately, as a free rider on (1).** `<;>`, `;`, `repeat` and
   `all_goals` are ALLOWED, close more goals per action, and cost `kernel_step_count = 1`. The
   reward pays for closure and charges nothing for horizon, so search pressure runs directly
   against the quantity being measured. All four solves in the committed smoke run are of this
   shape, and so is the recorded mathlib proof of the one goal this suite closed live — which was
   oracle-fed, not searched.
3. **V05-16, `harness_version` — the first time the harness version changes mid-search.** No
   intent required: every re-evaluated edge gets a second primary draw in the same condition.
   This is §30.4's winner's curse channel, reopened one field over from where RT-13 closed it.
4. **V05-08, budget overrun — only with a solver that emits an undecodable action** (a NUL byte
   is reachable through the JSON grammar); low probability from a well-behaved decoder.
5. **V05-14/15, renderer leakage and false `R_ONLY` parity — not under the current genome,
   immediately under the next.** All fourteen gene families are surface-only today and cannot
   express a declaring renderer. The moment a genome supplies its own `StateRenderer` — the seam
   `arena_v0` advertises — a renderer that shows more than it declares passes the parity check and
   the guard's 6-byte floor.

**Author or integrator only, not reachable by search:** V05-01, V05-02, V05-03, V05-04, V05-05,
V05-06, V05-10, V05-11, V05-12, V05-13, V05-17, V05-18, V05-19, V05-20, V05-21, V05-22, V05-23,
V05-24, V05-25. They are not less dangerous for that. V05-01 and V05-24 are the two a Phase-9
integration is most likely to produce in good faith, and V05-05/V05-06 remove the net that would
catch them.

---

## Recommended order of fixes (recommended, not applied)

1. **V05-24** — call `emit_trajectory()` inside the `with` block and write a bank. One line, and
   it makes every later fix checkable.
2. **V05-01 + V05-03** — bind the action to the policy that produced it (prompt hash + solver
   digest inside `semantic_core`), and make `build_trajectory(actor=…)` an assertion. Together
   these are what separates `INTERACTIVE_TASK` from `TRAJECTORY_REPLAY` in evidence rather than in
   prose.
3. **V05-02** — call `verify_served()` and record the served identity.
4. **V05-05 + V05-06** — put `verifier_evidence` inside `content_hash`; require the session
   binding at the current schema version; make `--relive` the default.
5. **V05-04** — mint the live session id from the process, not from the task id.
6. **V05-07 + V05-09** — do not reset the retry run on a no-op; measure or `None` the kernel step
   count before a macro-shaped action space lands.
7. **V05-10 + V05-11** — `selection.manifest()`, `task.task_id`, `state_id`.
8. **V05-16** — move `harness_version` into the condition.

---

*Suite, scripts and raw JSON: `research/phase9/redteam_v05/` (its `README.md` lists every command
and the exact environment). Nothing under `arena/`, `tests/`, `spec/` or `artifacts/` was modified.
Re-running the previous suite, as the directive requires, rewrote
`research/phase9/redteam/out/{relive,native_decide}.json` and its forged banks; the pre-run copies
are in `research/phase9/redteam_v05/out/prior/`.*
