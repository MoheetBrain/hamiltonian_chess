# A6 — Leakage, Contamination and Experiment Hygiene

**Auditor 6 of 9 · Hamiltonian Arena V7 Total Forensic Audit · Parts I and J**
Worktree `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/phase-6-parallel-setup-9c6068`,
branch `claude/phase-6-parallel-setup-9c6068`, HEAD `55229dc`. Read-only. No model call, no
network, no GPU. The four sealed LeanDojo splits were never opened — only `ls`, `stat`, `shasum`.

Scripts: `research/audit/a6_hygiene/{recompute_v7_verdict,verify_cache_vs_artifact,reproduce_dev_pool}.py`.

---

## 0. Headline

The V7 **arithmetic is beyond dispute**. Three independent reconstructions all close exactly:

| check | result |
|---|---|
| Verdict recomputed from the 864 stored rows (252 assertions) | **0 mismatches** |
| DEV probe bank rebuilt from source; `dev_pool_hash` | **bit-exact match** |
| 804 surviving cache entries vs artifact rows (identity + byte-identical output) | **804/804, 0 orphans** |

The defects found are **not** in the arithmetic. They are in (a) a materially **under-declared
sealed-split exposure**, (b) a **negative-control arm that is an arithmetic identity** consuming
one third of the call budget, (c) **shared state material** between two ladder levels, and
(d) a **live, unguarded read path** to the sealed splits in `research/`.

**A correction to this audit's own brief.** The brief states V7's probes come from
`DONOR_ROOT` / "the 1,150 Lean transitions" via LeanDojo, and asks whether the LeanDojo seal
protects them. That premise is wrong and the error matters: **V7 has no relationship to LeanDojo
whatsoever.** V7's probes come from a different donor corpus (`MoheetBrain/HML_V3`). The LeanDojo
sealed splits govern three *other* task families that V7 never ran. Everything below distinguishes
the two.

---

## Part I — Leakage and contamination

### I.1 — Provenance of every V7 task · `CONFIRMED`

**Evidence.** `arena/environments/formal_structural.py:46-52`:

```
DONOR_REPO  = "MoheetBrain/HML_V3"
DONOR_REF   = "codex/open-ended-search-v2"
DONOR_SHA   = "95e8a26f6519f226a149f4d7507d47f90bea9932"
DONOR_ROOT  = Path("/Users/moheet/Documents/ChatGPT/HML_V3")
CORPUS_GLOB = "data/corpus/lean_runtime_v2_full.canonical.part-*.jsonl.gz"
SEALED_GLOB = "data/corpus/sealed_final_v2.part-*.jsonl.gz"
```

`formal_structural.py` contains **no reference to LeanDojo, `random/train.json`, `corpus.jsonl`
or any LeanDojo path**, and its mtime is `2026-09-07 06:10:56` — worktree-creation time,
untouched by the entire sprint.

The funnel, measured by executing the committed construction offline
(`reproduce_dev_pool.py`), and cross-checked against `docs/FITNESS_V5_SPEC.md:72`,
`docs/TRAINING_DATA_FACTORY.md:49`, `docs/PROJECT_LEDGER.md:276`:

| stage | count | source |
|---|---|---|
| Real elaborated Lean 4 transitions in the donor corpus | **1,150** | `docs/FITNESS_V5_SPEC.md:72` |
| HML_V3 sealed-holdout source files excluded **by name only** | **126** files / 232 transitions | `formal_structural.py:245-259`, measured |
| Formal states loaded (`load_formal_states()`) | **461** | measured |
| Length-fair after 30,000-char budget over 8 founder surfaces | **104** | measured, `fitness_v5.py:867-890` |
| Stratified | shallow 34 · medium 34 · deep 36 | measured |
| **Actually used** (12 per level, `bucket[:12]`) | **36 distinct states** | `fitness_v5.py:901-908` |

**The selector** is `arena/experiments/fitness_v5.py:893-912` `build_dev_pool`, reached from
`fitness_v7.py:947`. It is **not** a sampler: it takes `bucket[index]` for `index in range(12)` —
the first twelve states of each stratum in `stratify` order, with no randomisation.

**The single most important structural fact, and it is not stated anywhere in the artifact:**

```python
# fitness_v5.py:903-908
formal = None
if mechanism == "formal_expression_depth":
    bucket = pool.get(str(params["stratum"]), [])
    formal = bucket[index]
```

Only **`formal_expression_depth`** is backed by real Lean states. **`transitive_dependency` and
`precondition_conjunction` pass `formal=None` and are entirely synthesised** from
`EXPERIMENT_SEED = 20260907`. So **576 of the 864 probes (67%) contain no real mathematics at
all**, and the environment-version string `arena-formal-structural-v1.0.0` stamped on all 864
rows overstates the grounding of two thirds of them.

This is directly visible in the answer vocabulary (measured):

| mechanism | distinct expected answers per 24 positives | most-reused answer |
|---|---|---|
| `formal_expression_depth` | 9–11 | used 7–8× |
| `transitive_dependency` | 24 / 24 | 1× |
| `precondition_conjunction` | 24 / 24 | 1× |

### I.2 — Were V7 templates/instances/structures seen in earlier work? · `CONFIRMED (yes, by design)`

`MECHANISMS`, `LADDERS`, `DEV_FAMILIES = 12`, `EXPERIMENT_SEED = 20260907`, `build_dev_pool`,
`_formal_pool`, `summarize`, `shortcut_audit` and `select_frontier_level` are **all imported from
`fitness_v5`** (`fitness_v7.py:115-140`). V7 is V5's instrument with a derived frontier target and
a per-level shortcut audit. `inherits_from` in the artifact declares 12 unchanged / 4 changed
components, so this is disclosed, not hidden.

The consequence is nonetheless real: **the V7 probe bank is not new**. The same 36 real states,
the same 12 families per cell and the same seed were used to develop and calibrate V5, whose
`QUALIFICATION_RULE` thresholds V7 inherits. `dev_pool_hash` is a property of code + corpus, both
of which predate the preregistration.

**The same 864 probe instances were run three times.** The identical hash
`f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b` is recorded in
`docs/FITNESS_V5_RESULT.md:7`, `docs/PHASE6_PREREGISTRATION.md:88` **and**
`docs/FITNESS_V7_PREREGISTRATION.md:81` — V5, Phase 6 ("V6") and V7 all scored **byte-identical
probes** against the same Solver family. `docs/FITNESS_V7_PREREGISTRATION.md:4` states it outright:
*"Probe bank unchanged"*. V7 changes gates and scoring, not instances.

**Two of the three mechanisms are older still.** `transitive_dependency` and
`precondition_conjunction` were introduced in **V4** (`fitness_v4.py:92,94,881,883`, added
2026-09-06 in `88bacc8`), and V5/V7 import V4's generators verbatim
(`fitness_v5.py:399-403`). Only `formal_expression_depth` and `formal_structural.py` are V5-era
(`2c61fdb`).

**Shortcut exposure was known before V7 ran.** `fitness_v7.py:41-46` records, ahead of any V7 call,
that `first_mentioned_in_state` scores 1.000 at `formal_expression_depth` L1, 0.8333 at L2 and
0.9167 at L3 — "because the audit is a property of the probe bank". V7's headline finding was
therefore predictable from the probe bank alone, with zero model calls. That is to V7's credit as
preregistration, but it means the 864 live calls confirmed a known property rather than
discovering one.

**No evidence of gradient training** on these probes: `docs/CURRENT_STATE.md:49` and
`docs/72_HOUR_SPRINT_HANDOFF.md:104-105` record no `torch` installed locally and all GPU
instances TERMINATED. `NO EVIDENCE FOUND` of fine-tuning.

**No V7 probe is unseen with respect to instrument development.** Severity: **medium** — it bounds
what a negative result can mean (it cannot be read as evidence about unseen material), but it does
not corrupt the recorded numbers.

### I.3 — Were the LeanDojo val/test pools read before sealing? · `CONFIRMED — and more than declared`

`artifacts/manifests/SEALED_SPLITS.json` concedes that **`random/val` + `random/test`** were read
("a prior audit reports random/val+test were already read (8,766 transitions)"), and labels
`novel_premises/{val,test}` as clean `PROMOTION_OOD` — "The only defence against solving premise
selection by recall."

**That claim is false, and the repository's own committed artifacts disprove it.**

`research/environments/common.py:55-58` — no seal guard of any kind:

```python
def load_theorems(split: str, part: str) -> list[dict[str, Any]]:
    """Load a small LeanDojo split file (val/test) fully into memory."""
    with open(leandojo_split_path(split, part), encoding="utf-8") as handle:
        return json.load(handle)
```

Four committed scripts loop over **both** splits × **both** parts:

- `research/environments/measure_census.py:95-97`
- `research/environments/measure_premise_selection.py:219`
- `research/environments/measure_representation_surface.py:26-28`
- `research/environments/measure_same_proof_deep.py:77-78`

Their **outputs are committed**. `research/environments/measurements/census_leandojo_heldout.json`:

| split | steps | with_premise ≥ 1 |
|---|---|---|
| `random/val` | 4,260 | 2,681 |
| `random/test` | 4,506 | 2,836 |
| **`novel_premises/val`** | **6,240** | **4,165** |
| **`novel_premises/test`** | **6,626** | **4,380** |
| `random/val+test` | 8,766 | 5,517 |

Those counts cannot exist without opening and parsing all four files.
`research/environments/measurements/premise_selection_shortcuts.json:4` names its steps source as
`.../{random,novel_premises}/{val,test}.json` and reports **3,586 novel_premises single-premise
items** with eight per-heuristic shortcut accuracies (best: `overlap_then_frequency` 0.8635) — i.e.
the premise-selection shortcut structure of the split that is supposed to be the defence against
premise-selection recall **has already been measured and published in-repo**.

**Timeline** (`git log --diff-filter=A`): the measurement scripts and artifacts were committed
`2026-09-07 11:38:57 +0100` in `a6e8ddf`; `SEALED_SPLITS.json` was committed `12:23:08 +0100` in
`e66bab1` and declares `sealed_utc: 2026-09-07T11:09:59Z`. The reads therefore predate the seal —
but the seal was authored **after** those artifacts were already in the repository and still
declared `novel_premises` clean.

**Exposure actually incurred: 21,632 steps (8,766 `random` + 12,866 `novel_premises`) across all
four sealed files. Declared: 8,766 — 40.5%.**

**Cause.** `research/environments/README.md:1-8`, committed in the same commit, states the scripts
and outputs "come from a subagent that was **terminated part-way through** by a session rate
limit", marks them UNVALIDATED, and says "Do **not** quote a figure from `measurements/`". The
exposure is nonetheless irreversible — and 8,766-derived statistics are quoted anyway, in
`docs/REASONING_OPERATION_DISCOVERY.md:12,385` and `artifacts/corpus/operation_inventory.json:32`.

**A repository claim that this refutes.** `docs/PROJECT_LEDGER.md:746-747` asserts the four splits
were "sealed by sha256 … **before any agent was spawned**". `REFUTED`: the reading agent had
already run at 05:38–05:53Z, and the seal is 11:09:59Z — 5 h 16 min later.

**A later audit already reached the correct position.**
`research/astra/game_r_premise/build_dev_bank.py:38-48` (commit `5811161`) marks **all four**
splits `HISTORICALLY_EXPOSED`, cites `census_leandojo_heldout.json` and
`premise_selection_shortcuts.json` as the evidence, and concludes a "fresh externally controlled,
never-inspected source partition [is] required; current partitions are not certified hidden."
**`SEALED_SPLITS.json` has never been amended** — `git log` shows one commit only (`e66bab1`). The
manifest is stale and contradicted in-repo.

Severity: **HIGH**. Effect: no LeanDojo split is clean OOD; the planned promotion gate has no
uncontaminated pool left.

### I.4 — Does hashing an already-exposed file make it hidden again? · **NO** · `REFUTED`

**Stated explicitly, as the audit requires: no. Hashing is not hiding, and sealing is not
un-reading.**

A sha256 is a *tamper-evidence* control. It proves a file's bytes have not changed since the hash
was taken — and the seal is intact: all four sealed files hash exactly to their recorded digests,
byte counts match, mtimes remain `2024-07-02` (verified this session). What a hash cannot do is
reach backwards and un-inform every artifact, threshold, script and design decision that was
derived from the file's contents while it was open. Information already extracted stays extracted;
it is now embedded in `census_leandojo_heldout.json`, `premise_selection_shortcuts.json`,
`representation_surface.json`, in the task-family designs those measurements shaped, and in the
judgement of whoever read them.

A seal applied after exposure converts a *clean holdout* into a *frozen contaminated holdout*. It
is worth having — it stops further leakage and makes future reads detectable — but it confers no
OOD status. `SEALED_SPLITS.json`'s own `contamination_note` gets this right for mathlib
("exposure is transitive, so no LeanDojo split can serve as clean OOD"); the `sealed[]` entries
then contradict it by assigning `novel_premises` the role `PROMOTION_OOD`.

**A methodological warning for later auditors.** `atime` on the donor volume is **not** a read
record. All eight LeanDojo files carry `atime = 2026-08-11 14:36:5x`, which looks like a
smoking gun. It is not: a same-volume control (reading the unsealed `metadata.json`, 244 bytes)
left its `atime` **unchanged**, while a control file elsewhere updated normally. The uniform
`2026-08-11` stamp is a bulk copy artefact. **Do not cite atime as evidence in either
direction.** I formed this hypothesis and refuted it against my own interest.

### I.5 — Which current sets are genuinely unseen? · The honest list

**With respect to V7's own inputs (HML_V3):**

| set | status |
|---|---|
| HML_V3 `sealed_final_v2` (126 source files / 232 transitions) | **GENUINELY UNSEEN.** Only `corpus_metadata.source_file` names are read, to exclude them (`formal_structural.py:245-259`). Verified: 126 names read, no state, target, option or answer. This is the **one** clean holdout in the project. |
| The 68 length-fair states not in `bucket[:12]` (104 − 36) | Loaded into memory and length-filtered, but never rendered into a probe or shown to a model. **Weakly unseen** — machine-touched, not agent-read. |
| The other 689 of 1,150 transitions (1,150 − 461) | Parsed and rejected by eligibility. **Weakly unseen.** |
| The 36 states actually used | **SEEN** — they are the V7 probes, and were V5's. |

**With respect to LeanDojo:** the honest list is **empty** — and worse than empty, because even
without opening a sealed file the val/test identities, file paths, line spans and premise names
are readable from the unsealed `steps.jsonl` (§I.6).
`random/{val,test}` — read (8,766 steps, declared). `novel_premises/{val,test}` — read (12,866
steps, **undeclared**). `random/train.json`, `corpus.jsonl` — the declared development source.
`novel_premises/train.json` — not referenced by any code path found, but it is a training split
and shares theorems with the rest.

**With respect to the Solver's pretraining:** nothing is unseen and nothing can be shown to be.
`SEALED_SPLITS.json` states it plainly: `qwen38-rvn`'s and `gemma4:12b`'s training cutoffs are
`UNRECORDED`, and mathlib4 is public. This bounds every claim in the project and is correctly
disclosed.

### I.6 — Does `steps.jsonl` leak the sealed splits? · `CONFIRMED — SEVERE`

**It exists, and it is the single largest unmitigated leakage surface in the estate.** It is not
in the donor root (`leandojo_raw/leandojo_benchmark_4/`) but one directory across, at
`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl` —
271,038,884 bytes, mtime 2026-08-10 16:43. Declared at `research/env_rewrite/stream.py:25` and
pinned by sha256 in `artifacts/manifests/rewrite_direction_manifest.json` as
`sources.metadata_index`.

**Split counts, verified by streaming and counting the `split` field only:**

```
TOTAL ROWS: 259580     SPLIT COUNTS: {'train': 250814, 'val': 4260, 'test': 4506}
```

Exactly the figures in the brief, and `val = 4,260` / `test = 4,506` are **byte-identical** to the
`random/val` and `random/test` step counts in `census_leandojo_heldout.json` — so `steps.jsonl`'s
val/test rows *are* the sealed `random` split.

**What a consumer can obtain for every sealed val/test step, without opening any sealed file.**
The 34 top-level keys include (listed from a TRAIN row only):

- **Full theorem identity** — `thm`, `prov.full_name`
- **Exact Lean source path** — `file_path`, plus **line/column spans** `prov.start` / `prov.end`
- **Composite key** — `proof_id`
- **Per-step premise names** — `premises`, `n_premises_used`, `added_names`
- **Tactic head and effect signature** — `head`, `eff`
- **Full proof shape** — `step_index`, `last_step`, `closed`, `noop`, `delta_goals`,
  `n_before`/`n_after`, hypothesis deltas, metavariable flags, `target_changed`, `raw_len`
- **Split membership**

Everything except the pretty-printed state text. **The pinned mathlib4 commit
`29dcec074de168ac2bf835a77ef68bbe069194c5` is present on this machine**
(`legal_transform_manifest.json.lean_tier_a_replay.mathlib_root`), so the line spans make the
sealed val/test theorem statements and proofs **fully recoverable** from a file that is not sealed.

**Status — all three negative:** absent from `SEALED_SPLITS.json` (verified: 0 matches); absent
from `.gitignore`; untracked (`git ls-files | grep steps.jsonl` → empty), and it lives outside the
repository in a directory under **no version control at all**. It is explicitly listed as a
*permitted* source in two manifests.

The project knows. `docs/72_HOUR_SPRINT_HANDOFF.md:91-93`:

> "`steps.jsonl` filtered to `split == "train"` — that file covers all splits (250,814 / 4,260 /
> 4,506), so an unfiltered consumer leaks the promotion pool."

and `tests/environments/test_rewrite_direction.py:379-382` states that val/test identities "can be
read from it and used as an exclusion list without touching a sealed pool" — that test
(`:386-398`) does read non-train `proof_id`s, a legitimate exclusion use which nonetheless
demonstrates how trivially available the identities are.

**Severity: HIGH.** Mitigation rests entirely on every future consumer remembering to filter
`split == "train"`. Effect on V7: **none** — V7 never touches LeanDojo.

### I.7 — Could theorem/module identities leak target labels? · `CONFIRMED (channel exists) / POSSIBLE (exploitable)`

**Names and paths do NOT reach the model.** Measured over all 288 `formal_expression_depth`
prompts (`module_identity_leak.py`):

```
theorem_id appears in prompt : 0
'.lean'    appears in prompt : 0
'Mathlib'  appears in prompt : 0
```

The identifying fields — `theorem_id`, `source_file`, `SourceProvenance.source_item_id` (e.g.
`Mathlib/Algebra/BigOperators/Group/Finset.lean::Finset.prod_of_injOn::0`) — are carried on the
probe's **oracle side only** (`fitness_v5.py:436-440`) and never rendered. They reach the artifact
only inside `dev_pool_hash`. Artifact rows carry no theorem name or path; `family_id` embeds a
truncated `stable_hash`, and answers are compared by `content_hash`. Local hypotheses are already
pseudonymised by the donor (30 distinct names, `f0`–`f29`).

**But module-identifying content does reach the prompt.** `transcribe`
(`formal_structural.py:117`) maps `kind == "symbol"` to the node's `name`, and those are **global
mathlib declaration names**, which survive into the rendered state. Measured over the 104
length-fair states:

```
distinct global mathlib symbols across the bank : 327
mean distinct symbols per state                 : 5.22
top: Eq(37) Membership.mem(16) Nat(16) Set(14) Iff(13) Set.instMembership(7) LE.le(7) Real(7)
distinct symbol-sets: 100; mapping to exactly ONE source file: 98 (98.0%)
states whose target carries NO global symbol: 0
```

**98 of 100 distinct symbol-sets uniquely determine the originating mathlib source file** within
this bank, and the pinned mathlib4 commit is present locally — so a symbol-set → module → theorem
lookup is feasible in principle.

**Honest limits on this finding.** The uniqueness is substantially an artefact of n = 104; in a
larger bank these common symbols would not discriminate. More decisively, **module identity cannot
answer the question asked**: the answer is which of two `f<N>` *local* identifiers sits deeper in
the goal tree, and that is not determined by which mathlib file the goal came from. So the channel
is real and confirmed, but its exploitability as a target label is `POSSIBLE`, **not
demonstrated** — and it is not the leak that voided V7. The measured leak is positional
(`first_mentioned_in_state`).

For the three unrun LeanDojo families the equivalent risk is materially higher — premise names
*are* the labels there, and `research/environments/measurements/sample_items.jsonl` shows options
carrying `full_name` **and `def_path`** (e.g. `Mathlib/Data/ZMod/Defs.lean`) inside rendered
options. Those families produced no result, so this is a forward-looking risk only.

### I.8 — Near-duplicate structures split across partitions? · `CONFIRMED`

Measured on the 864 rows and the rebuilt pool:

- 144 distinct `family_id` (12 per cell × 12 cells); 864 distinct `probe_hash`; **no `family_id`
  appears in more than one cell** — cells are disjoint at family level.
- **But `formal_expression_depth` L0 and L2 are built from an identical set of 12 real Lean
  states.** `LADDERS` gives L0 `{explicit: True, stratum: "medium"}` and L2
  `{explicit: False, stratum: "medium"}`, and both take `bucket[:12]` of the same 34-state medium
  bucket. Verified by set comparison: `L0 vs L2: identical state set = True`; all other pairs
  `False`.

**Effect.** For the mechanism the selector actually chose, the L0 "explicit positive ≥ 0.90"
instrument-limit gate (observed 1.000) and the L2 frontier measurement (observed 0.7917) are
computed **on the same twelve states**. L0 is therefore not an independent check that the
instrument works — it is the same material with the answer written in. The four-level ladder is
three distinct state samples, not four. Severity: **medium** (construct validity, not arithmetic).

- Only 210 distinct `expected_hash` across 864 rows; within `formal_expression_depth` cells,
  4–6 answers are shared by more than one family per cell, and one answer recurs 23×
  across the family. This concentration is a plausible contributor to that family's high
  `first_mentioned_in_state` / `more_frequent_in_state` shortcut scores.

---

## Part J — Implementation and experiment hygiene

### J.9 — The cache-deletion incident, reconstructed · `CONFIRMED`

**The record.** `docs/PROJECT_LEDGER.md:1070-1079` (entry heading line 1045), repeated at
`docs/PROJECT_STATUS.md:328-331` and `docs/72_HOUR_SPRINT_HANDOFF.md:117-121`, and in the body of
commit `9f28c0c`: while investigating unexpected files under `artifacts/cache/`, **the implementing
subagent deleted that directory three times**, destroying "approximately 55" cache entries of the
running V7 experiment (PID 3932, started 12:38), plus an 872-entry dry-run cache and a dry-run
artifact. No document names a specific agent, command or clock time; **no evidence found** for a
more precise attribution than "the implementing subagent".

**Reconstruction from the filesystem** (git holds nothing — `git ls-files artifacts/cache` is
empty and `.gitignore:14` is `artifacts/cache/`):

- `artifacts/cache/fitness_v7` **birth = 12:48:19**, identical to the first surviving cache file.
  The directory did not exist an instant earlier; the run's next write recreated it. That is the
  **last** deletion.
- `artifacts/cache` (parent) **birth = 12:38:18**, 38 s *before* the run began (12:38:56), and
  unchanged since — so the final deletion removed only the `fitness_v7` child.
- Surviving mtimes span 12:48:19 → 14:21:12 with **all 94 minutes populated** and a maximum
  inter-file gap of 22 s. **There is exactly one gap and it is at the head of the run:
  12:38:56 → 12:48:19 (9 m 23 s).** Nothing was destroyed after 12:48:19.
- The middle deletion left no recoverable trace (APFS keeps only the latest birth time):
  `POSSIBLE`, not established.

**What was lost — and the record understates it.** Joining cache identities to artifact rows
(`verify_cache_vs_artifact.py`):

```
ROWS WITH NO SURVIVING CACHE ENTRY : 60
      formal_expression_depth L0: 60 of 72 lost
      variants: ORIGINAL 10, COUNTERFACTUAL 10, DESTROYED_ORIGINAL 10,
                DESTROYED_COUNTERFACTUAL 10, SWAPPED_ORIGINAL 10, SWAPPED_COUNTERFACTUAL 10
surviving Q0 cache entries : 0  (artifact records 8)
```

**The true loss is 60 rows plus all 8 Q0 entries = 68 cache files, not "~55".** All of it falls in
the single block `formal_expression_depth` L0, which the log shows completing at 12:49:32 — the
only block spanning the deletion window. Eleven of twelve blocks are intact at 72/72.
Arithmetic closes exactly: `804 surviving + 60 lost = 864 rows`; `864 + 8 Q0 = 872 = planned`.

### J.10 — Could any V7 result have been lost, regenerated, reordered or changed? · `REFUTED`

**No. Three independent grounds.**

1. **By design.** `evaluate` (`fitness_v7.py:773-838`) iterates each probe once, over disjoint
   (mechanism, level) cells; each cache identity is therefore visited exactly once per run.
   `cached_call` (`fitness_v7.py:403-443`) writes the file *after* the call and returns the row
   from the in-memory response. A file deleted after that point cannot be re-read, cannot trigger
   a second call, and cannot alter a row already appended. The one code path that revisits
   identities — the `arms == "positives"` re-evaluation at `fitness_v7.py:1071-1090` — was **not
   taken**: `arm_schedule = "full"`.
2. **By the artifact.** All 864 rows carry `cache_scope = "FRESH"` and `cache_hit = false`;
   `fresh_calls_made == 864 == len(rows)`. **Not one row was served from cache**, so no cache
   entry — destroyed or surviving — could have influenced any measurement.
3. **By cross-check.** Zero orphan cache entries: every one of the 804 survivors maps to a
   committed row. No dry-run stub entry leaked into the live namespace — which independently
   corroborates the ledger's claim that the dry-run cache was destroyed, and rules out the worst
   failure mode (a live row silently served from a stub).

The ledger's assessment — **"no scientific corruption; resume capability only"** — is
**CONFIRMED by independent measurement**. Its only error is the magnitude (~55 stated vs 60 real).

### J.11 — Cryptographic verification of the 864 FRESH rows · `CONFIRMED`

`verify_cache_vs_artifact.py`, for all 804 surviving entries:

| check | result |
|---|---|
| filename == `stable_hash(identity)` (the path **is** the identity) | **804 / 804** |
| cached `result.response` **byte-identical** to row `raw_output` | **804 / 804** |
| all 14 identity fields equal the row's fields | **804 / 804** |
| orphan entries | **0** |

Against `artifacts/tmp/v7_run.log`: the trailing JSON line reads
`{"cache_scope_totals":{"FRESH":864},"instrument_qualified":false,"mode":"LIVE",`
`"qualified_mechanisms":[],"selected_levels":{}}` — identical to the artifact. All twelve
per-level log lines match the recomputed ladder values (§J.18). The log's line 2 records
`planned model calls (cold cache): 872 / budget 900; arms=full`.

Row identity is single-valued across all 864 rows for `experiment_version`, `instrument_version`,
`model_digest`, `model_template_hash`, `runtime_hash`, `decoding_hash`, `runtime_condition`,
`solver_kind`, `genome_hash` and `candidate_id` — one condition, one candidate, no mixing. Zero
rows carry an `error`.

### J.12 — Was any result file modified after preregistration? · `REFUTED (no)`

- Preregistration `e66bab1`, author = commit date **2026-09-07 12:23:08 +0100**, prereg-only
  (`SEALED_SPLITS.json`, `docs/FITNESS_V7_PREREGISTRATION.md` +189, three status/ledger files);
  **no code**. `docs/FITNESS_V7_PREREGISTRATION.md` has exactly one commit and zero diff to HEAD —
  **never edited**.
- Result artifact: **birth = ctime = mtime = 14:21:12**, links=1 — created once at the instant the
  run ended, never rewritten. Its sha256
  `ecdefc4f8399f82160e577050312781c2899d1f48e9a157a157c661b67fc13db` is identical in the working
  tree, in `f7b1b40`, and at HEAD. Nothing under `artifacts/` is newer than 14:21:12.
- `arena/experiments/fitness_v7.py`: birth = ctime = mtime **12:36:26**, 2 m 30 s before the run
  started, never rewritten; sha256 byte-identical to the blob in `cf1b07f`.
- `arena/environments/formal_structural.py` — the environment V7 actually scores — mtime
  **06:10:56**, untouched by the whole sprint.

### J.13 — Hash inventory

| item | value |
|---|---|
| Code — `arena/experiments/fitness_v7.py` sha256 | `83a2679646a16eab2e5d17bca930e6eaacafd64f01b5a88f5a2356ff76cedfe1` |
| Code — `arena/environments/formal_structural.py` sha256 | `b15f2431274c67dd3e5f35e208b8469ea0bd501ab9e8ce701ec80f73eb68f218` |
| Result artifact sha256 | `ecdefc4f8399f82160e577050312781c2899d1f48e9a157a157c661b67fc13db` |
| **DEV pool hash** (task/probe hash) | `f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b` — **reproduced bit-exactly** |
| Genome / candidate | `a81adb9692f6da2eeb6db74447ea28534923371dd06e575fc4b6e680383fa697` · `V5E_L3_JSON_AST` |
| Model digest | `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae` (`qwen38-rvn:latest`, 27.3B, Q4_K_M, family `qwen35`) |
| Model template hash | `39302355407942b6b0b50e1a78741740fc8a31926a4febea429526497e0e6008` (`template_is_passthrough = true`) |
| Runtime config hash | `fbf95fc39cc59be68387ee511a5296c30f43cda80b5e49b97a90287c265734db` |
| Decoding hash | `ed0c3deca8217f8e9f27db1f9512a472cbf1823d2c7a7f4108d3391df014697e` |
| Prompt hashes | **717 distinct over 864 rows** — see J.15 note; 2 distinct over the 8 Q0 rows |
| Sampling / decoding | `temperature 0.0`, `seed 20260905`, `top_k 64`, `top_p 0.95`, `num_ctx 32768`, `num_predict 64`, `raw true`, `think null`, engine `ollama`, format `json_schema:choice_ab` (enum A/B) |
| Instrument / experiment / environment / schema | `arena-game-r-derived-frontier-instrument-v7.0.0` · `arena-representation-fitness-v7` · `arena-formal-structural-v1.0.0` · `arena-fitness-v7-development-v1` |
| Sealed LeanDojo splits | all four sha256 **match the manifest exactly**; seal intact |

### J.14 — 872 planned vs 864 FRESH · `CONFIRMED — derived, not speculated`

From the code's own call schedule, `fitness_v7.py:918-926`:

```python
def planned_call_count(probes, arms):
    if arms == "full":
        return len(probes) + 8
```

`len(probes) = 864` (`dev_pool_probes`, reproduced bit-exactly) and `arms = "full"`, so
**planned = 864 + 8 = 872**. The `+ 8` is the Q0 format check: `q0_check` loops
`for index in range(8)` (`fitness_v7.py:844-882`).

`fresh_calls_made = 864` is `evaluate`'s `calls` counter, which sums FRESH **over probe rows
only** (`fitness_v7.py:833`); `cache_scope_totals` is likewise built from `all_rows`, which never
contains Q0. **The 8-call difference is exactly the Q0 arm, which is executed and reported in a
separate structure and deliberately excluded from the probe-row totals.** Verified:
`len(rows) + len(q0.rows) = 864 + 8 = 872 = planned_model_calls`. Nothing is missing, and the
budget was 900.

### J.15 — Are eight Q0/control calls excluded? · `CONFIRMED — proved from the artifact`

`d["q0"]["rows"]` has **length 8**; every one carries `cache_scope = "FRESH"`
(`{'FRESH': 8}`), `kind = "Q0"`, `case` 0–7, and `correct = true` → `d["q0"]["rate"] = 1.0`,
matching `v7_run.log:3` (`Q0 valid rate 1.000`, 12:39:02). They share the model digest, template
hash, runtime hash and decoding hash with the 864 probe rows, so they were the same condition —
but their identity uses `q0_cache_identity` (`fitness_v7.py:341-362`), which carries `kind`/`case`
instead of `task_id`/`probe_hash`, keeping them in a disjoint cache namespace. They are excluded
from `rows`, from `cache_scope_totals` and from `fresh_calls_made`, and included in
`planned_model_calls`. All 8 Q0 cache files were destroyed in the incident (§J.9); the 8 rows
survive in the artifact.

Only 2 distinct Q0 prompt hashes across 8 rows — the prompt alternates A/B by parity
(`expected = "A" if index % 2 == 0 else "B"`), so the format check is 4 repetitions of 2 prompts,
not 8 independent probes.

### J.16 — Concurrent writes into experiment directories during the run · `CONFIRMED (present, but harmless)`

51 non-cache files were written inside 12:38:56–14:21:12. Every one belongs either to the three
**new, unrun** LeanDojo task families (`premise_selection.py` 12:39:35, `legal_transform.py`
12:41:05 and their manifests/tests) or to the `TRAINING_LANGUAGE_V0` release
(12:42:46–12:48:45), plus docs, `.gitignore` and `.ruff_cache`. **Neither `fitness_v7.py` nor
`formal_structural.py` appears** — both predate the run. The two mid-run `artifacts/` writes are
manifests for families V7 never used.

Five git worktrees and five branches were live (`git worktree list`), and
`docs/SPRINT_COMPUTE_LEDGER.md:42` records six concurrent agents. Cache namespaces are partitioned
across worktrees (`fitness_v1/2/3` in the main repo, `v4/v5` in the takeover worktree, only
`fitness_v7` here), so the incident was confined to this worktree's V7 namespace.

Two timing coincidences, both `POSSIBLE` and neither established: peak foreign write activity
(12:39:05–12:48:45) overlaps the destruction window almost exactly; and `.gitignore` was edited at
12:45:07 — its line 14 is `artifacts/cache/` — carried by `ed30a75` ("untrack a regenerable 2.4 MB
derived dump"), which is a plausible reason the cache came under scrutiny.

### J.17 — Can tests modify cached experiment state? · `REFUTED — with one caveat`

**No test can touch a live cache.** Every V7 cache and artifact path in the suite is rooted at
pytest's `tmp_path` fixture — `tests/experiments/test_fitness_v7.py:359, 406-407, 418, 423, 552`
all pass `tmp_path`. `cache_root`/`cache_path`/`development_artifact_path`
(`fitness_v7.py:381-390, 908-915`) take `root` as a parameter and are never called with the repo
root in tests. `assert_v7_namespace` (`fitness_v7.py:290-309`) additionally refuses any path
belonging to a frozen instrument, and `tests/experiments/test_fitness_v7.py:442-460` asserts that
guard. No test writes into the repository's `artifacts/`.

The suite is in fact **actively defensive**: `tests/environments/test_rewrite_direction.py:250-265`
contains `test_sealed_splits_are_refused` and `test_load_signatures_refuses_a_sealed_path`, which
assert that `SealedSplitError` is raised for every sealed path — they reference `random/val.json`
but never open it.

**The caveat, and it is the live risk.** That guard exists **only in `arena/`**
(`premise_selection.py:42-50`, `rewrite_direction.py:68-71`, `legal_transform.py:29`).
`research/environments/common.py` has **no guard at all** — `load_theorems("novel_premises", "val")`
still opens the sealed file today, and four committed scripts call it in a loop (§I.3). **Running
`research/environments/measure_*.py` re-reads all four sealed splits.** Severity: **HIGH**;
this is an un-remediated contamination vector, not a historical one.

### J.18 — Does the verdict recompute exactly from stored rows? · **YES** · `CONFIRMED`

`recompute_v7_verdict.py` reimplements `summarize`, `answer_entropy_bits`,
`select_frontier_level` and `qualify_mechanism` independently (importing **no** arena module) and
re-derives every recorded quantity from the 864 rows plus the recorded `qualification_rule`.

```
CHECKS RUN: 252    MISMATCHES: 0
VERDICT RECOMPUTES EXACTLY FROM STORED ROWS: YES
```

Reproduced exactly: all 12 cells' `positive_accuracy`, `largest_answer_share`,
`answer_entropy_bits`, `valid_response_rate`, `destroyed_accuracy`, `positive_negative_gap`,
`position_invariance`, `positive_examples`, `shortcut_margin_at_this_level`,
`inside_qualifying_window`, `cache_scopes`; every `full_family_summary` field; all three
`selection` blocks; all three `qualification` blocks including the nine named `checks` and
`all_failures`; `qualified_mechanisms = []`; `selected_levels = {}`;
`instrument_qualified = false`; and the derived `frontier_target = ((0.5 + 0.2) + 0.85)/2 =
0.7749999999999999`. Per-level `best_shortcut_accuracy` and `status` also reproduce from the
stored `scores` via `max(s, 1−s)` (three ties on the *name* of the worst rule in
`precondition_conjunction`, all at score 0.5 — cosmetic, no effect).

The recomputed verdict:

| mechanism | selected | accuracy | best shortcut | margin | verdict |
|---|---|---|---|---|---|
| `formal_expression_depth` | L2 | 0.7917 | 0.8333 (`first_mentioned_in_state`) | −0.0417 | **VOID_SHORTCUT** |
| `transitive_dependency` | L3 | 0.7500 | 0.6667 (`first_mentioned_in_state`) | +0.0833 | **VOID_SHORTCUT** |
| `precondition_conjunction` | — | 0.9583 @L1 > 0.85 | — | — | **VOID_CEILING** |

→ 0 of 3 qualified, minimum 2 required → `instrument_qualified = false`. **This is exactly the
recorded V7 verdict.** The arithmetic is not in question; the audit can focus entirely on
construct validity.

### J.18b — A defect surfaced by the recomputation: the negative-control arm is an identity

Measured (`recompute_v7_verdict.py` §6):

```
destroyed rows                          = 288 / 864 (33.3% of the call budget)
identical-prompt groups                 = 141 covering 288/288 rows
every group opposite label              = True
every group byte-identical output       = True
every group scores exactly half correct = True
destroyed_accuracy overall              = 0.5
gap == accuracy - 0.5 in all 12 cells   = True
```

**Every one of the 288 destroyed rows shares its prompt with another destroyed row carrying the
opposite `expected_index`.** The Solver is deterministic (`temperature 0.0`, fixed seed), so it
returns byte-identical output within each pair; exactly one of the two is scored correct. The
"measured" negative control is therefore **forced to 0.5000 by construction** — it is arithmetic,
not evidence — and `positive_negative_gap ≡ positive_accuracy − 0.5`, making the
`negative_collapse` gate a restatement of `positive_accuracy ≥ 0.70` (= `window_low`).

V7 half-acknowledges this: `qualification_rule.dropped_gate` removes the destroyed *ceiling* gate
as "unreachable … carries no information", and the code comment at `fitness_v7.py:1128-1130`
concedes the gap gate "is exactly `positive >= window_low`". But V7 still **spends 288 live model
calls — one third of an 872-call budget — measuring a constant**, and still presents nine
independent-looking gates when one is redundant. This also explains the 717-vs-864 distinct prompt
hashes noted in J.13: 141 collisions, all of them destroyed pairs, none affecting cache identity
(which keys on `task_id` + `probe_hash`, not the prompt).

Severity: **medium** — efficiency and overstated gate independence, honestly disclosed in part,
with no effect on the recorded numbers.

---

## Classified flaw list

| # | Finding | Class | Severity | Effect on the V7 verdict |
|---|---|---|---|---|
| 1 | `SEALED_SPLITS.json` declares `novel_premises/{val,test}` clean `PROMOTION_OOD`; both were read and their statistics committed (12,866 steps; 21,632 total vs 8,766 declared) | `CONFIRMED` | **HIGH** | None on V7 (disjoint corpus). Destroys the planned LeanDojo promotion gate. |
| 2 | `research/environments/common.py:55-58` has no seal guard; four committed scripts still re-read all four sealed splits on execution | `CONFIRMED` | **HIGH** | None on V7. Live, un-remediated leakage path. |
| 3 | 2 of 3 mechanisms (576/864 probes) are **synthesised**, not real Lean, yet all 864 rows are stamped `arena-formal-structural-v1.0.0` | `CONFIRMED` | **HIGH** | None on arithmetic; materially weakens "real mathematics" framing of the negative result. |
| 3b | **`steps.jsonl` (271 MB, unsealed, untracked, no VCS) is a complete identity index for the sealed val/test pools** — theorem names, Lean paths, line spans, premise names, split labels; with the pinned mathlib4 commit local, the sealed proofs are recoverable without opening a sealed file | `CONFIRMED` | **HIGH** | None on V7. Largest unmitigated leakage surface in the estate. |
| 3c | Same 864 probe instances (`f804e0d9…`) scored by V5, Phase 6 and V7; 2 of 3 mechanisms date to V4; V7's shortcut finding was derivable from the probe bank with zero model calls (`fitness_v7.py:41-46`) | `CONFIRMED` | MEDIUM | None on arithmetic; V7 is a re-scoring, not an independent measurement. |
| 3d | `docs/PROJECT_LEDGER.md:746-747` claims the splits were sealed "before any agent was spawned"; the reads predate the seal by 5 h 16 min | `REFUTED` | MEDIUM | Record inaccuracy. |
| 3e | Exposure caused by a rate-limit-terminated subagent whose own README marks the outputs UNVALIDATED and says "do not quote"; 8,766-derived figures are quoted anyway in `docs/REASONING_OPERATION_DISCOVERY.md` and `artifacts/corpus/operation_inventory.json` | `CONFIRMED` | MEDIUM | None on V7; unvalidated numbers are load-bearing elsewhere. |
| 3f | Global mathlib symbol-sets reach the prompt and identify the source module for 98/100 states (exploitability not demonstrated; cannot determine the answer) | `CONFIRMED` / `POSSIBLE` | LOW | Not the leak that voided V7. |
| 4 | Negative-control arm is an arithmetic identity: 288 calls (33% of budget) forced to 0.5000; `negative_collapse` gate is redundant | `CONFIRMED` | MEDIUM | None. Budget waste; overstated gate independence. |
| 5 | `formal_expression_depth` L0 and L2 use an **identical** 12-state set, so the explicit-positive gate is not independent of the frontier measurement | `CONFIRMED` | MEDIUM | None on arithmetic; ladder is 3 samples, not 4. |
| 6 | Probe bank inherited wholesale from V5 (same seed, states, families); no V7 probe is unseen w.r.t. instrument development | `CONFIRMED` | MEDIUM | Bounds interpretation; disclosed via `inherits_from`. |
| 7 | Cache-deletion loss documented as "~55 rows"; true figure **60 rows + 8 Q0 = 68 entries** | `CONFIRMED` | LOW | None — no row was affected. Record inaccuracy. |
| 8 | Answer vocabulary concentrated in `formal_expression_depth` (9–11 distinct per 24; one answer 23×) | `CONFIRMED` | LOW | Plausible contributor to the shortcut that voided it. |
| 9 | Q0 is 4 repetitions of 2 prompts, not 8 independent format probes | `CONFIRMED` | LOW | None; rate 1.000 either way. |
| 10 | `docs/SPRINT_COMPUTE_LEDGER.md:41,45` still says V7 `running`, "≈4.8 h", "392 calls" — contradicts 864 calls / 1 h 42 m | `CONFIRMED` | LOW | None; stale compute record. |
| 11 | Any V7 result lost, regenerated, reordered or changed by the cache incident | **`REFUTED`** | — | All 864 rows FRESH, `cache_hit=false`, 804/804 corroborated, 0 orphans. |
| 12 | Result or instrument modified after preregistration | **`REFUTED`** | — | Artifact birth=mtime=14:21:12, sha256 identical to HEAD; prereg never edited. |
| 13 | Tests able to modify live cached experiment state | **`REFUTED`** | — | All test paths under `tmp_path`; namespace guard asserted. |
| 14 | Sealed splits tampered with, or read during the run | **`REFUTED`** | — | All four sha256 match exactly. (`atime` is not evidence — see I.4.) |
| 15 | V7 verdict arithmetic wrong or irreproducible | **`REFUTED`** | — | 252/252 checks; `dev_pool_hash` bit-exact. |
| 16 | Identity of the deleting agent, exact command, time of the middle deletion | `NO EVIDENCE FOUND` | — | Unrecoverable; APFS keeps only the latest birth time. |

## Bottom line

**The V7 run is clean where it counts and the negative result is strengthened, not weakened, by
this audit.** The verdict recomputes exactly from stored rows; the probe bank reproduces
bit-exactly from source; the surviving cache corroborates every row byte-for-byte; nothing was
modified after preregistration; and the cache incident — real, and worse than recorded — provably
could not have changed a single measurement, because not one row was ever served from cache.

The serious findings are elsewhere, and they concern **what happens next**, not what already
happened. The LeanDojo seal under-declares its own contamination by 60%, is contradicted by a
later in-repo audit that was never folded back into the manifest, remains readable by committed
scripts, and is in any case bypassed entirely by an unsealed, untracked 271 MB index that carries
the sealed pools' theorem names, file paths and line spans. **The project's planned promotion pool
is already spent.** None of this touches V7 — but all of it blocks the step after it.

Within V7 itself, two thirds of the probes are synthetic, one third of the call budget measured a
constant, two ladder levels share their state material, and the same 864 instances had already
been scored twice before. The verdict `V7_SHORTCUT_DOMINATED` — 0 of 3 mechanisms qualified — is
arithmetically impeccable. It is a statement about a **narrower, more artificial and less novel
instrument than its version strings imply**, and it confirmed a shortcut that the probe bank
already revealed with zero model calls.
