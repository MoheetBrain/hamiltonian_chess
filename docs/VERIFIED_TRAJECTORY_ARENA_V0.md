# Verified Trajectory Arena V0 — what exists locally, and the smallest real thing we can build

**Status: audit complete, nothing built.** Every number below was measured on this machine during
this audit; scripts and raw JSON are in `research/phase9/data_audit/`. No model was called and
nothing was downloaded. The four sealed LeanDojo splits were never opened (see that directory's
`README.md` for the exact discipline observed).

**The one-line answer.** A complete, built mathlib4 and a working Lean 4.10.0-rc1 toolchain are
already on this machine, and LeanDojo's `lean_dojo_repl` tactic is *already compiled into it*. A
live, stateful, branchable, kernel-verified Lean proof environment starts in **3.2 seconds** and
runs tactics at **193 steps/second**. That is the V0 arena. It is days of glue, not weeks of
infrastructure, and it is the only local option that yields genuine ≥5-step verified trajectories
in which the model's own choices determine the state sequence.

---

## 0. What the mission needs, and the trap

The target object is a `VerifiedTrajectory`: persistent evolving state, deterministic
verification, no answer leakage, unambiguous termination. The failure mode to avoid is a
*measurement* of long-horizon reasoning that is actually a measurement of something else. Three
specific illusions are live here, and §7 lists them in full:

1. concatenating unrelated single-step probes and calling the concatenation a trajectory
   (explicitly forbidden by the owner);
2. replaying a recorded trajectory the model never influenced;
3. "verification" that is a string comparison against a recorded transcript.

Illusion 3 is not hypothetical. **§4.3 measures it: 40.6% of replayed successor states differ
textually from the recorded ones even when Lean accepts the tactic and the mathematics is
identical.** A string-matching verifier would have scored 59.4% of *correct* steps as wrong.

### 0.1 The current Arena, measured

The premise that motivated this audit is broadly right but worth stating precisely.

| environment | options | items | horizon |
|---|---|---|---|
| `premise_selection` | **K = 6** (K = 8 at L4) | 56,847–63,831 | **1** |
| `rewrite_direction` | K = 2 (FORWARD/REVERSE) | 3,466 controlled | **1** |
| `legal_transform` | K = 2 (VALID/INVALID) | 24,000 / 12,000 pairs, **100% `TIER_B_CONSTRUCTED`, zero Lean-verified** | **1** |
| `precondition_ladder` | K = 2 | — | **1** |
| `formal_structural` | structural depth question | 1,150 transitions | **1** |
| `artifacts/worlds/arena-world-v0.jsonl` | — | 676 tasks | **1 transition in 676 of 676** |

So: not all of them are two-option (premise selection is 6- or 8-way), but **every one of them has
horizon exactly 1**. `arena/canonical/schema.py:322` already defines a `CanonicalTrajectory` with a
`transitions` tuple; it has never been instantiated with more than one element. The container for
long-horizon work exists and is empty.

---

## 1. Inventory of every local candidate

Sizes are exact bytes. "Trajectories" counts *problems with a step sequence*, not items.

### 1.1 Sources with genuine machine-readable intermediate STATES

| # | Path | Bytes | Format | Trajectories | ≥2 | ≥5 | ≥10 | ≥20 | max |
|---|---|---|---|---|---|---|---|---|---|
| **L1** | `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json` | 373,077,058 | one-line JSON array | 118,517 records; **59,557 with tactics**; 250,814 steps | 38,755 | **15,275** | **5,892** | **1,605** | **128** |
| L1-chain | *same file, restricted to linearly chained proofs* | — | — | **40,683** | 19,881 | **1,983** | **132** | **6** | **35** |
| L1-prefix | *same file, maximal chained prefix of every proof* | — | — | 59,557 | 29,891 | 4,783 | 616 | 31 | 35 |
| L2 | `.../leandojo_benchmark_4/novel_premises/train.json` | 364,899,019 | JSON array | 118,517 rec / 246,714 steps | 38,336 | 15,012 | 5,786 | 1,557 | 128 |
| L3 | `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/lean_domino_v2/lean_canonical_records.jsonl` | 755,808,347 | jsonl, **pre-parsed states** | 241,265 rows → 61,544 groups (all splits) | 39,914 | 14,280 | 5,233 | 1,372 | 125 |
| L4 | `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl` | 271,038,884 | jsonl, **features only, no state text** | train 250,814 rows / 59,557 proofs (val 4,260, test 4,506 unread) | 38,755 | 15,275 | 5,892 | 1,605 | 128 |
| L5 | `/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus/lean_runtime_v2_full.canonical.part-00{0..4}.jsonl.gz` | 17,042,127 | 5× gz jsonl, **richest state schema on disk** | 1,150 transitions / **1,085 theorems** | **48** | **2** | **0** | **0** | **8** |
| L5b | `…/lean_runtime_v2.canonical.part-*` | 8,681,357 | gz jsonl | 608 / 608 | 0 | 0 | 0 | 0 | **1** |
| L5c | `…/search_pool_v2.part-*` | 13,290,755 | gz jsonl | 918 / 872 | 32 | 1 | 0 | 0 | 8 |
| L5d | `…/targeted_v2.canonical.part-*` | 8,364,404 | gz jsonl | 542 / 497 | 32 | 2 | 0 | 0 | 8 |
| L6 | `/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus/data/hml_50k_final/canonical/records.jsonl.gz` | 62,097,745 | gz jsonl | 56,000 rows → 16,950 | 8,722 | 3,261 | 1,176 | 282 | 86 |
| L7 | `…/hmlt-reasoning-corpus/data/gold125/trajectories/*.json` (100 files) | 7,712,718 | JSON per problem | 100 | 98 | 63 | 17 | 3 | 23 |
| L8 | `…/gold25/` (25) + `…/gold_10/` (10) | 664,294 + 75,664 | JSON per problem | 35 | 35 | 12 | 0 | 0 | 8 |
| **G** | **built mathlib4 + Lean 4.10.0-rc1 + `lean_dojo_repl`** (§2) | 18 GB | live proof assistant | **generative — bounded only by compute** | — | — | — | — | **unbounded** |

### 1.2 Sources with step *depth* but no machine-readable state

| # | Path | Bytes | Steps field | ≥2 | ≥5 | ≥10 | ≥20 | Verdict |
|---|---|---|---|---|---|---|---|---|
| P1 | `…/hml_research_artifacts/prm800k_raw/prm800k/data/phase2_train.jsonl` | 456,135,365 | `question.pre_generated_steps` (list of strings) | 97,778 | 96,082 | 67,326 | **14,961** | deepest local corpus; informal prose; **`ground_truth_solution` sits in the same object as `problem`**; on both `never_train_list` and `licence_blocked` |
| P1b | same file | — | `label.steps` (rated, incl. rejected branches) | 90,727 | 61,846 | 24,436 | 3,035 | same objections |
| P2 | `/Users/moheet/Documents/ChatGPT/prm800k/prm800k/data/phase2_train.jsonl` | 456,135,365 | byte-identical duplicate of P1 | — | — | — | — | duplicate |
| P3 | `…/hf_sources/Pythagoras_SFT/pythagoras_sft_partial_dataset.json` | 996,190,986 | `Reasoning Chain` (**one prose string**) | — | — | — | — | no states; **`Formal Statement` embeds the answer and ends `:= by sorry`** |
| P4 | `…/hf_sources/NuminaMath-LEAN/data/train-00000-of-00001.parquet` | 78,426,425 | `formal_proof` (**one string**) | — | — | — | — | 31,634/104,155 have a proof; `answer` is a sibling of `problem` |
| P5 | `…/hf_sources/Herald_proofs/…parquet` | 57,908,255 | `formal_proof` (string) | — | — | — | — | `informal_proof` leaks next to `informal_theorem` |
| P6 | `…/hf_sources/STP_Lean_0320/…parquet` ×10 | ~1.6 GB | `target` (string) | — | — | — | — | 3,262,558 rows, **no state field at all** |

### 1.3 Not trajectories

Hendrycks MATH (12,500 rows, `problem/level/type/solution`); AMPS-Khan (103,059 rows, `hints/solutions`
concatenated with no delimiter); GSM8K (7,473/1,319); `state_tactic_pairs` (56,407 rows, `tactic`+`input`,
**no after-state**, and a measured 75.5% lemma-name leak — worse than `docs/CORPUS_STRATEGY.md`'s "~35%");
ProofNet Lean-4 port (371 statements, bodies are `sorry`); miniF2F (Lean source only);
`corpus.jsonl` (60,420,959 B; 5,674 files, 180,973 declarations — the premise/import graph, not trajectories).

**Absent from this machine** (paths swept to depth 10 across `/Users/moheet`): Metamath / `set.mm`,
TPTP, SMT-LIB `*.smt2`, Coq / CoqGym, HolStep, Isabelle AFP traces, PutnamBench, miniCTX,
OpenWebMath, NaturalProofs, full NuminaMath, full AMPS. **Lean-Workbook is present but is two
git-LFS pointer stubs** (132 B and 133 B) — the only LFS stubs found anywhere; the payload is not
on disk. `~/.cache/huggingface` holds no mathematical datasets.

### 1.4 Horizon histograms

**LeanDojo `random/train.json`, all recorded tactics per theorem** (the pool a *live* arena can draw on):

```
steps:  1     2     3     4    5    6    7    8    9   10   11   12   13   14   15
       20802 12844 6576  4060 2992 2183 1677 1364 1167 856  694  587  454  397  346
steps: 16    17    18    19   20   21   22   23   24   25   26   27   28   29   30
       304   239   219   191  164  147  126  111   85   95   75   54   59   61   55
       … 31–40: 51 36 44 30 30 24 19 28 22 12 …  ≥50: 159   ≥100: 15   max: 128
```

**Same file, restricted to proofs whose recorded list is a genuine linear chain**
(`state_after[i] == state_before[i+1]` for every i) — the pool a *recorded-replay* arena can draw on:

```
steps:  1     2     3    4    5   6   7   8   9  10  11  12  13  14  15 …
       20802 11731 4282 1885 887 491 230 137 106 49  24  22   7   7   6 …
       ≥5: 1983   ≥10: 132   ≥20: 6   max: 35
```

**HML_V3 `lean_runtime_v2_full`** (1,150 transitions, the corpus `formal_structural` reads):

```
steps:  1    2   3  4  5  6  7  8
       1037  40  4  2  1  0  0  1      ≥5: 2   ≥10: 0   max: 8   mean 1.06
```

---

## 2. Does a usable Lean binary and a built mathlib genuinely exist? Yes. Naming the path.

Two prior audits reached opposite conclusions because **both checkouts exist and only one is built.**

| path | size | `.olean` | built? |
|---|---|---|---|
| `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4` | **18 GB** | **5,680** | **YES — complete** |
| `/Users/moheet/Documents/ChatGPT/HML_V3/external/checkouts/mathlib4-29dcec0` | 349 MB | 38 | no — source only |

The build is **complete, not partial**: `Mathlib.lean` has **4,447** `import` lines and
`.lake/build/lib/Mathlib/` contains **exactly 4,447** `.olean` files. The remaining 1,233 are
dependencies (`lean4` 918, `batteries` 158, `aesop` 106, `proofwidgets` 33, `Qq` 12, `importGraph` 2,
`Cli` 1) plus `Mathlib.olean`, `Lean4Repl.olean` and `lakefile.olean`.
`lean-toolchain` = `leanprover/lean4:v4.10.0-rc1`. Toolchains installed under `~/.elan/toolchains`:
`v4.10.0-rc1`, `v4.32.2`, `v4.33.0`, `v4.33.1`.

### 2.1 Trivial elaboration — command and real output

```
$ env -C $MB /Users/moheet/.elan/bin/lean --version
Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)

$ cat research/phase9/data_audit/lean_probe_trivial.lean
import Mathlib.Tactic.NormNum
example : (2 : Nat) + 2 = 4 := by norm_num
theorem probe_add_comm (a b : Nat) : a + b = b + a := by
  induction a with
  | zero => simp
  | succ n ih => omega
#eval "LEAN_PROBE_OK"

$ time env -C $MB /Users/moheet/.elan/bin/lake env /Users/moheet/.elan/bin/lean \
      $PWD/research/phase9/data_audit/lean_probe_trivial.lean
…/lean_probe_trivial.lean:6:11: warning: unused variable `ih`
note: this linter can be disabled with `set_option linter.unusedVariables false`
"LEAN_PROBE_OK"
env -C … 0.46s user 0.46s system 35% cpu 2.575 total
EXIT=0
```

`lake env` only sets `LEAN_PATH`. **Nothing was written into the mathlib checkout.**

### 2.2 The buried asset: `lean_dojo_repl` is already compiled

`Lean4Repl.lean` sits at the root of the built checkout and `.lake/build/lib/Lean4Repl.olean`
exists. It defines `elab "lean_dojo_repl" : tactic` and `elab "#lean_dojo_repl" : command`, a
JSON line protocol `{"sid": <state id>, "cmd": "<tactic>"} → {"sid", "tacticState", "error"}`.
The Python `lean_dojo` package is **not** installed and is **not needed** — the protocol is 30
lines of `subprocess`.

Measured live session (`drive_repl.py`, real output, theorem `RelSeries.smash_castAdd`):

```
[  4.6s] REPL ready. initial sid=0
INITIAL STATE:  … ⊢ (p.smash q connect).toFun (Fin.castAdd q.length i).castSucc = p.toFun i.castSucc
[  4.6s] step 0 `unfold smash`      -> sid=1
[  4.6s] step 1 `dsimp`             -> sid=2  ⊢ (if H : ↑i < p.length then … ) = p.toFun i.castSucc
[  4.6s] step 2 `rw [dif_pos i.2]`  -> sid=3  ⊢ p.toFun ⟨↑i, ⋯⟩ = p.toFun i.castSucc
[  4.6s] step 3 `rfl`               -> sid=4  no goals
[  4.6s] BRANCH from sid=1 with a bogus tactic -> ERROR: type mismatch
                                                   Nat.zero has type ℕ : Type but is expected …
total wall 4.6s
```

Four properties this establishes, none of which any recorded corpus can provide:

* **State is persistent and addressable.** `sid` names a saved tactic state; the arena can revisit
  `sid=1` after reaching `sid=4`. Search, backtracking and counterfactual branches are free.
* **Wrong actions are rejected with a real reason** — the type error above is Lean's, not a lookup.
* **Termination is unambiguous**: `tacticState == "no goals"`.
* **`sorry` is refused by the REPL itself**: sending `{"sid":0,"cmd":"sorry"}` returns
  `{"error": "proof contains `sorry`"}`. The obvious cheat is closed at the backend.

### 2.3 Cost, measured

`repl_throughput.py`, 6 episodes across 6 different mathlib files:

| quantity | measured |
|---|---|
| REPL startup (import + elaborate the file prefix) | min **2.57 s**, mean **3.24 s**, max **4.44 s** |
| tactic steps once warm | **17 steps in 0.088 s → 193 steps/s** |
| whole-trajectory batch re-elaboration (`run_replay_probes.sh`, 30 probes) | mean **3.3 s**, max 12.3 s; **29/30 elaborated with zero errors** |

Startup dominates and is per-episode, not per-step. A 20-step episode costs ~3.3 s of Lean, of
which the tactics are ~0.1 s. On one machine that is roughly **1,000 episodes/hour single-threaded**,
and the work is embarrassingly parallel.

---

## 3. The four options, compared

### (a) Live Lean replay through a real Lean binary — **RECOMMENDED**

*What "verified" means:* the Lean 4 elaborator accepted the model's tactic in the current
metavariable context, and the terminal declaration type-checks with `#print axioms` reporting no
`sorryAx`. This is kernel-backed. Verified with the real thing:

```
$ cat research/phase9/data_audit/axioms_probe.lean
import Mathlib.Tactic
theorem good_one (a b : Nat) : a + b = b + a := by omega
theorem cheated  (a b : Nat) : a * b = b * a := by sorry
#print axioms good_one
#print axioms cheated

$ env -C $MB … lake env lean …/axioms_probe.lean
…:4:8: warning: declaration uses 'sorry'
'good_one' depends on axioms: [propext, Quot.sound]
'cheated' depends on axioms: [sorryAx]
EXIT=0
```

*What could be faked:* almost nothing at the step level. The residual risks are (i) a tactic that
closes the goal by naming the theorem itself or a downstream corollary — controlled by truncating
the file prefix *before* the declaration, which this audit already does and verified works;
(ii) `native_decide` / `decide` brute force — detectable in `#print axioms` output
(`Lean.ofReduceBool`) and cheaply bannable by tactic allow-list; (iii) `exact?`/`apply?`/`aesop`
outsourcing the search to mathlib's own automation — a real scientific confound, controlled by an
explicit tactic budget and by reporting per-tactic-family results.

*Engineering cost:* **days.** The pieces that already exist: built mathlib, working toolchain, a
compiled REPL, a 373 MB problem bank with per-theorem file/position, and a probe builder in this
audit that constructs a valid REPL file from a `(file_path, start, end, full_name)` tuple with
**29/30 success**. What has to be written: a `subprocess` REPL client (~50 lines, written and
working — `drive_repl.py`), an episode driver, a problem sampler, and a result schema.

*Honest scientific limitation:* mathlib4 is `HISTORICALLY_EXPOSED` per
`artifacts/manifests/SEALED_SPLITS.json`, and the exposure is transitive. **No LeanDojo split can
serve as pretraining-clean OOD.** A model may have memorised the proof. This measures long-horizon
*execution under verification*, not long-horizon *discovery*, unless paired with the sealed
`novel_premises` split at promotion time or with problems whose statements post-date the model.

### (b) Recorded transitions read as a trajectory, no replay

*What "verified" means:* the recorded next state matched the tactic — i.e. **nothing was verified
during the episode**; the trajectory is a transcript of what mathlib's authors did.

*What could be faked:* everything that matters. The model never influences the state, so no
credit assignment across steps is possible; the "verifier" is a comparison against a recording.

*Engineering cost:* ~1 day.

*Why it loses, quantitatively:* the recorded lists are **traversals of a proof tree, not chains**.
Measured on `random/train.json`: of 191,257 adjacent pairs, only **128,644 (67.3%)** satisfy
`state_after[i] == state_before[i+1]`, and only **19,881 of 38,755** multi-step proofs (51.3%) chain
all the way through. The usable linear pool collapses to **1,983 proofs with ≥5 steps, 132 with ≥10,
and 6 with ≥20** (§1.4). *Six.* A ≥20-step claim built on six proofs is not a measurement.

*And the verifier itself is unsound as string equality* — see §4.3.

### (c) Non-Lean, deterministically checkable symbolic rewriting (SymPy / Z3)

The repository already has `arena/verifier/sympy_adapter.py` (SymPy 1.14.0) and
`arena/verifier/z3_adapter.py` (z3 installed), both translating `CanonicalExpression`.
*(Note: `arena/verifier/native.py` is the structural/semantic survival checker over
`CanonicalState`; it is not the SymPy/Z3 wrapper — those are the two adapter modules.)*

*What "verified" means:* each rewrite preserves semantic equality (SymPy `simplify(a-b)==0`, or
Z3 `unsat` on the negation). Solve ≫ verify holds, and it is deterministic and model-free.

*What could be faked:* the *problems*. A generator we write produces trajectories whose difficulty
we chose; long horizons are trivially manufactured by chaining more rewrites, and a 20-step chain
of `x+0 → x` is 20 steps of nothing. There is no external standard of mathematical interest.
This is the same objection that made V3/V4's synthetic states unpersuasive, at greater length.

*Engineering cost:* days for a generator, but weeks to earn any credibility that the horizon is real.

*Honest limitation:* it measures execution of a rewrite system we designed. Worth building later as
a **control arm** — a non-Lean environment with the same horizon profile, to test whether a
long-horizon result transfers off the Lean backend. Not the V0.

### (d) Informal step corpora (PRM800K)

The deepest trajectories on the machine by a wide margin — **67,326 problems with ≥10 steps,
14,961 with ≥20**. But there is no state, only prose; verification would require a model judge,
which the mission forbids; `ground_truth_solution` and `ground_truth_answer` sit in the same object
as `problem`; and it is on both the `never_train_list` and the `licence_blocked` list in
`artifacts/corpus/source_registry.json`. **Excluded.**

### (e) HML_V3 `lean_runtime_v2_full` — the V7 audit's claim, checked

`docs/V7_TOTAL_FORENSIC_AUDIT.md` §14 is **factually correct and it does not mean what a trajectory
arena needs.** Verified by `audit_hml_v3_corpus.py`:

| V7 claim | measured |
|---|---|
| 1,150 transitions | **1,150** ✅ |
| identity ⟂ display_name (canonical fvar/mvar id maps) | present on every record ✅ |
| four binder roles, Level trees, structured goals | goals carry `identity`, `local_context`, `local_instances`, `target` ✅ |
| `external_premise_refs` | present; **749/1,150 non-empty** ✅ |
| transitive imports on 1,150/1,150 | **1,150/1,150** ✅ |
| only 190 single-premise/single-goal | **190** ✅ |

And the number that decides it: those 1,150 transitions cover **1,085 distinct theorems**. Mean
horizon **1.06**. Only 48 theorems reach 2 steps, 2 reach 5, none reach 10, max 8. **Zero of 65
adjacent pairs chain by `state_id`.** Two further facts kill replay outright: the `action` object
has **no tactic name** (its keys are `external_premise_refs, kind, local_context_refs,
reference_completeness, reference_mechanism, source_location`), and every record is stamped
`PARTIAL_TACTICS_WITHOUT_TERMINFO_MAY_HIDE_INTERNAL_USE`.

**This corpus is the best per-transition semantic record on the machine and is useless as a
trajectory source.** Richness is not horizon.

---

## 4. Recommendation

> ### Build V0 on option (a): live Lean 4.10.0-rc1 + the built mathlib4 at
> ### `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4`,
> ### driven through the already-compiled `lean_dojo_repl`, with problems sampled from
> ### `random/train.json` (LeanDojo Benchmark 4, CC BY 2.0, mathlib4 `29dcec07…`).

### 4.1 Why it beats the alternatives

* It is the **only** option where the model's own action determines the next state. (b) is a
  recording; (c) and (d) do not verify.
* It is the only option whose verifier is **kernel-backed and already anti-cheat**: `sorry` is
  refused by the REPL, and `#print axioms` catches a `sorryAx`-tainted terminal.
* Its ≥20-step pool is **1,605 theorems**, versus **6** for recorded linear replay — a 268×
  difference that comes entirely from the branching structure being *real state* in a live
  environment and *broken chain* in a transcript.
* The infrastructure cost is already paid: 18 GB build, compiled REPL, 3.24 s startup, 193 steps/s.
* Provenance and licence are clean: LeanDojo Benchmark 4 is **CC BY 2.0** with a nine-component
  `licenses/` directory; mathlib4 is Apache 2.0; the commit is pinned in the data itself.

### 4.2 What it CANNOT support — state this in every result

1. **It cannot establish pretraining-cleanliness.** mathlib4 is `HISTORICALLY_EXPOSED` and exposure
   is transitive. A ≥10-step success may be recall of a memorised proof. The only local controls
   are the sealed `novel_premises/{val,test}.json` (promotion only, single use) and reporting
   results split by theorem popularity/recency. **Do not claim "long-horizon reasoning"; claim
   "long-horizon execution under kernel verification".**
2. **It cannot run Game R.** `docs/CANONICAL_VNEXT_PILOT.md` measured **0 of 368** real Lean states
   mapping losslessly into `arena-canonical-v0.1.0` (20.7% unmappable). The observation is a Lean
   pretty-printed string, which **fixes R** at "Lean's pretty-printer". Eight representation arms
   would receive byte-identical input. V0 is a *capability* instrument, not a representation one.
3. **It cannot cheaply avoid mathlib's own automation.** `simp`, `aesop`, `omega`, `decide`,
   `exact?` can collapse a 10-step proof to 1. Without a tactic budget and an allow-list, "horizon"
   measures the model's willingness to type `aesop`.
4. **It cannot produce a stable pretty-printed state as ground truth.** See §4.3.
5. **It cannot be reproduced off this machine without the 18 GB build.** V0 is machine-pinned.

### 4.3 The measurement that dictates the schema: pretty-printed states are not stable

30 recorded trajectories were rebuilt as Lean files (file prefix + statement + recorded tactics,
each followed by `trace_state`) and elaborated. **29/30 elaborated with zero errors.** Comparing
Lean's own `trace_state` output against LeanDojo's recorded successor state, over 106 comparable
states:

| comparison | matches | fraction |
|---|---|---|
| byte-identical after whitespace normalisation | 43 | **0.406** |
| identical after stripping namespace qualifiers (`Finset.univ` ≡ `univ`) | 104 | **0.981** |
| genuinely different mathematics | **2** | 0.019 |

The corpus is a faithful transcript — **98.1%** — but the *rendering* is scope-dependent: the same
goal prints as `univ` under `open Finset` and `Finset.univ` without it. **A verifier that compares
state strings would reject 59.4% of mathematically correct steps.** Truth must stay with the
backend, exactly as the mission directs. The Arena canonical schema must not be asked to be the
authority on Lean state — see §5.2.

### 4.4 A secondary finding that raises the ceiling

Tree-shaped proofs — those the recorded chain cannot represent — were fed to the live REPL as a
**flat** tactic script. **5 of 6 closed to `no goals`** (11, 5, 13, 14 and 10 steps; the failure was
`introN failed, insufficient number of binders`). Lean's goal stack absorbs most of the structuring
that breaks the recorded chain. So option (a) can draw on a substantial part of the *full* 250,814
transitions, not merely the 40,683 linear ones — though the 5/6 rate is from a sample of six and
must be re-measured at scale before being relied on.

---

## 5. `VerifiedTrajectory` — schema grounded in the real fields

Every key below either exists in the source data or is produced by the Lean REPL. Field origins
are named.

```jsonc
{
  "schema": "arena-verified-trajectory-v0",
  "trajectory_id": "…",
  "problem_id": "Mathlib/Order/RelSeries.lean::RelSeries.smash_castAdd",
        // = LeanDojo file_path + "::" + full_name  (both real keys of random/train.json)

  "formal_backend": {
    "system": "lean4",
    "toolchain": "leanprover/lean4:v4.10.0-rc1",          // from lean-toolchain
    "lean_version_string": "Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)",
    "mathlib_commit": "29dcec074de168ac2bf835a77ef68bbe069194c5",  // = train.json `commit`
    "mathlib_build_root": "/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4",
    "repl": "Lean4Repl.lean :: lean_dojo_repl",
    "olean_count": 5680
  },

  "source_version": {
    "dataset": "LeanDojo Benchmark 4", "leandojo_version": "2.0.0",   // metadata.json
    "split": "train",                                                  // property of the FILE
    "creation_time": "2024-07-02 13:14:48.804567",
    "license": "CC BY 2.0",
    "file_path": "Mathlib/Order/RelSeries.lean",   // train.json key
    "full_name": "RelSeries.smash_castAdd",        // train.json key
    "start": [514, 1], "end": [518, 26]            // train.json keys
  },

  // ---- STATES: backend-native envelope. The Lean text is the AUTHORITY. ----
  "states": [
    {
      "index": 0,
      "state_id": "0",                        // REPL `sid` — persistent, addressable, branchable
      "backend_native": {
        "kind": "LEAN4_TACTIC_STATE_PP",
        "pp": "α : Type u_1\n…\n⊢ (p.smash q connect).toFun … = p.toFun i.castSucc",
        "pp_scope": {                         // WHY the pp is not canonical — see §4.3
          "open_declarations": [], "current_namespace": "RelSeries",
          "options": []                       // key names taken from HML_V3 provenance.lean_runtime_snapshot
        },
        "pp_sha256": "…",
        "n_goals": 1                          // = lean_domino_v2 state_before.n_goals
      },
      "derived": {                            // ADVISORY ONLY. Never the verification authority.
        "hypotheses": [{"name": "p", "type": "RelSeries r"}],   // lean_domino_v2 state_before.hypotheses
        "target": "…",                                          // lean_domino_v2 state_before.target
        "canonical_state": null,              // arena-canonical-v0.1.0 projection, or null.
        "canonical_projection_status": "UNMAPPABLE"
        // CANONICAL_VNEXT_PILOT measured 0/368 lossless. `null` is the expected value.
      }
    }
  ],

  "actions": [
    {
      "index": 0,
      "from_state_id": "0", "to_state_id": "1",
      "actor": "solver",                       // "solver" | "reference" — NEVER mix in one trajectory
      "tactic": "unfold smash",                // train.json traced_tactics[i].tactic
      "annotated_tactic": ["unfold smash", []],// train.json traced_tactics[i].annotated_tactic
      "premises_used": [],                     // steps.jsonl `premises` / HML_V3 external_premise_refs
      "effect_signature": "INTRODUCE_AND_TRANSFORM|dg0|T1|A1|R0|B0",  // lean_domino_v2 observed_action
      "wall_ms": 6
    }
  ],

  "verifier_evidence": [
    {
      "step": 0, "verifier": "lean4-repl", "verdict": "ACCEPTED",
      "backend_response": {"sid": 1, "tacticState": "…", "error": null},
      "rejected_reason": null
    },
    {
      "step": "TERMINAL", "verifier": "lean4-kernel",
      "print_axioms": "'probe_RelSeries_smash_castAdd' depends on axioms: [propext, Quot.sound]",
      "contains_sorryAx": false, "contains_ofReduceBool": false
    }
  ],

  "terminal_status": "CLOSED_NO_GOALS",
     // CLOSED_NO_GOALS | OPEN_BUDGET_EXHAUSTED | REJECTED_TACTIC_LIMIT
     // | ERROR_BACKEND | ABORTED_SORRY_ATTEMPT
  "horizon": 4,                     // = len(actions); reference length also recorded for difficulty
  "reference_horizon": 4,           // = len(train.json traced_tactics) — NOT the model's horizon

  "provenance": {
    "trust_tier": "VERIFIED_FORMAL",
    "generated_utc": "…", "generator": "arena/environments/lean_trajectory.py@…",
    "seed": 0,
    "sealed_splits_not_read": ["novel_premises/val.json","novel_premises/test.json",
                               "random/val.json","random/test.json"],
    "contamination": "mathlib4 HISTORICALLY_EXPOSED; transitive; not pretraining-clean OOD",
    "tactic_allow_list_version": "…", "tactic_budget": 40
  }
}
```

### 5.1 Why the backend-native envelope, concretely

`docs/CANONICAL_VNEXT_PILOT.md` measured **0 of 368** real Lean states mapping losslessly into
`arena-canonical-v0.1.0`, 20.7% unmappable. This audit adds the second reason: §4.3 shows the
pretty-printed form is itself **scope-dependent**, so it is not a canonical form either. Hence:

* `backend_native.pp` + `pp_scope` + `pp_sha256` is what the model sees and what gets hashed.
* `derived.canonical_state` is `null` by default and is **never** consulted by any verifier.
* Equality between states is decided by the **backend `sid`**, never by comparing strings.

### 5.2 What this schema deliberately refuses

It does not claim a `CanonicalState` for a Lean goal. It does not treat the recorded tactic as the
only correct action. It does not let `derived` fields carry verification weight.

---

## 6. Determinism, leakage and termination controls

**Determinism.** Pin `mathlib_commit`, `toolchain`, `maxHeartbeats` and `maxRecDepth` in the
manifest; record `lean --version` verbatim per run. Ban wall-clock-sensitive tactics. Record the
`pp_sha256` of every state so a re-run is bit-comparable. Fresh REPL process per episode (no
cross-episode environment state). Recorded startup variance was 2.57–4.44 s, all deterministic in
output.

**Leakage — the four channels, each with a control and a measured baseline.**

| channel | control | measured |
|---|---|---|
| the theorem proves itself (`exact <full_name>`) | truncate the file prefix **before** the declaration; rename to `probe_<name>` | verified working: 29/30 probes elaborated with the theorem out of scope |
| the answer printed in the observation | the observation is the goal state; the tactic is the label | only **92 of 250,814** steps have the gold tactic text verbatim in `state_before` (0.037%); only **2 of 59,557** proofs have their own `full_name` in a `state_before` — drop both |
| downstream corollaries in scope | truncation handles same-file; cross-file needs an import-closure check against `corpus.jsonl` (`path`, `imports`, `premises[].full_name`) | not yet measured — **open work** |
| automation shortcut | tactic allow-list + budget; reject `sorry` (REPL already does), flag `native_decide`/`decide` via `#print axioms` `ofReduceBool` | `sorry` refusal verified live |

**Termination.** `tacticState == "no goals"` is unambiguous and was the terminal state in
**40,594 of 40,683** fully-chained recorded proofs (99.8%). Harden it with the kernel check:
the declaration must elaborate and `#print axioms` must not report `sorryAx`. Every other outcome is
an explicit non-terminal status; there is no "probably done".

---

## 7. WHAT WOULD MAKE THIS FAKE

Read this section before believing any number the V0 arena produces.

1. **Concatenating unrelated micro-probes.** Ten `premise_selection` items in a row is not a
   10-step trajectory; it is ten 1-step trajectories with a shared prompt. *Explicitly forbidden by
   the owner.* Detection: if state *k+1* is computable without state *k*, the horizon is 1.
   The schema encodes this — `to_state_id` must equal the next `from_state_id`, and the backend
   `sid` must have been produced by the previous action.

2. **Replaying a recording the model never influenced.** If the environment supplies the tactic
   list, the model is a transcription task. `actions[].actor` exists to make this visible; a
   trajectory mixing `"reference"` and `"solver"` actions must never be reported as a solver result.

3. **Verification that is a string match.** §4.3 measures this: string equality of pretty-printed
   states scores **40.6%** where the real agreement is **98.1%**. A string-matching verifier is both
   unsound (scope-equivalent renderings differ) and gameable (produce the recorded text). Only the
   backend `sid` transition and `#print axioms` count.

4. **Horizon inflated by automation.** `simp_all`, `aesop`, `omega`, `decide`, `exact?` can close a
   10-step goal in one move — or, worse, a model can pad with no-ops. `steps.jsonl` already records
   a `noop` flag; measure and report the no-op rate, and require that each step change the goal.

5. **Horizon inflated by the tree/chain confusion.** The 250,814 figure is a traversal of proof
   *trees*; only **67.3%** of adjacent pairs chain. Quoting "5,892 proofs with ≥10 steps" as a
   *recorded chain* pool would be false — the true recorded-chain figure is **132**. Always say
   which pool a number comes from.

6. **Memorisation reported as reasoning.** mathlib4 is `HISTORICALLY_EXPOSED`, transitively. A
   model that has seen `RelSeries.smash_castAdd` is not reasoning for 4 steps; it is recalling.
   Nothing in this arena distinguishes the two. This is the single biggest threat to the result
   and it is **not solved** by anything in this document.

7. **Selection effects from the probe builder.** This audit's own builder discarded multi-line
   tactics and non-`theorem` declarations to get clean probes. If the arena inherits those filters
   it will sample easy, short, syntactically tidy proofs and report their horizon as typical.
   Log every discard reason and its count, as the existing environment manifests already do.

8. **`sid` reuse hiding a failure.** The REPL keeps every saved state. A driver that silently
   retries from an earlier `sid` after a rejected tactic turns a failed episode into a successful
   one. Every attempt, including rejected ones, belongs in `verifier_evidence`.

---

## 8. The cheapest path to ≥20-step trajectories

**There is one, and it is option (a) unmodified.** The pool is already there:

| pool | ≥20 steps | ≥30 | ≥50 | ≥100 |
|---|---|---|---|---|
| recorded linear chains (option b) | **6** | 1 | 0 | 0 |
| theorems whose reference proof needs that many tactics (option a) | **1,605** | 628 | 159 | 15 |

A 20-step episode costs ~3.3 s of Lean (3.2 s startup + ~0.1 s of tactics), so the entire 1,605-theorem
≥20-step bank is roughly **90 minutes of single-core compute**, or minutes in parallel. **No new data
is needed and nothing has to be downloaded.**

Ranked, cheapest first:

1. **Sample from the 1,605 `≥20 reference tactic` theorems in `random/train.json`.** Zero new data,
   zero new infrastructure. Caveat: reference length is a proxy for required depth, not a guarantee —
   a model may close a 20-tactic proof in 3 with `aesop`. Mitigate with the tactic allow-list, and
   report the *achieved* horizon, never the reference one.
2. **Raise the horizon by restricting the tactic vocabulary.** Banning `simp`/`aesop`/`omega`/`decide`
   forces elementary steps and lengthens genuine proofs. Free, but changes the task's meaning — state it.
3. **Chain within a file by dependency, not by concatenation.** Prove lemma A, then prove theorem B
   whose proof *uses* A, in one REPL session. `corpus.jsonl` gives the premise graph
   (`path`, `imports`, `premises[].full_name`) and 180,973 declarations across 5,674 files. Horizon
   becomes the sum of the sub-proofs and state genuinely persists across them. Days of work, and this
   is the honest way to reach 50+ — **but note the trap in §7.1**: it is only a real trajectory
   because B's proof *consumes* A. If B does not use A, this is exactly the forbidden concatenation.
4. **What will NOT work:** every recorded corpus. HML_V3 maxes at 8 (and does not chain at all);
   `gold125` maxes at 23 with 3 problems; recorded linear replay maxes at 35 with six proofs ≥20.
   PRM800K has 14,961 problems with ≥20 steps and no verifiable state, no licence and no state at all.

---

## 9. Exact next actions

1. Write `arena/environments/lean_trajectory.py`: REPL client (the working one is
   `research/phase9/data_audit/drive_repl.py`), episode driver, `VerifiedTrajectory` emitter.
2. Freeze `artifacts/manifests/lean_trajectory_manifest.json` — tactic allow-list, budget,
   `maxHeartbeats`, sampler seed, discard reasons — **before** any solver call, per the standing rule.
3. Measure at scale what §4.4 measured on six: the REPL success rate on tree-shaped proofs, and the
   probe-builder yield across the whole 59,557-proof bank. The 29/30 and 5/6 rates are small samples.
4. Close the unmeasured leakage channel: cross-file corollary scope, using `corpus.jsonl`.
5. Only then run a solver, and report the achieved horizon distribution alongside every §7 control.
