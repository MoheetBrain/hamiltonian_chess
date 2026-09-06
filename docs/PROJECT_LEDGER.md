# Project Ledger

Append-only. One chronological entry per commit. Never rewrite or delete an entry except to
correct a demonstrable factual error, and record that correction inside the entry itself.

---

## 2026-09-05 — First Tier-2 matched adaptation: the arena gets a real training runner

**Date and time.** 2026-09-05, 21:00–22:00 UTC. **Branch.** `codex/arena-v0-fitness`.
**Project stage.** `TIER2_MATCHED_ADAPTATION_FIRST_RUN`.

**Objective of the change.** Decide, before investing in open-ended language evolution,
whether matched adaptation produces a representation-dependent machine-fitness signal, or
whether the fitness landscape is flat. `docs/FOUR_DAY_SPRINT.md` Day 3 named this as the
highest-information next action and it was the one unchecked box blocking `R*-V0`.

**Files and systems changed.** New: `arena/training/prepare_matched_data.py` (matched dataset
construction and split), `arena/training/gpu_matched_runner.py` (the explicit Tier-2 runner
that `matched_adaptation.py` delegates to), `arena/training/analyse_sprint.py` (paired
statistics), `docs/PROJECT_STATUS.md`, `docs/PROJECT_LEDGER.md`. No canonical schema, world
generator, language surface or assurance component was touched; Arena truth is unchanged.

**What was completed.** A full five-arm matched NEXT_ACTION adaptation on one A100 80GB under
a hard 55-minute budget, with successive halving across three stages. Results are recorded in
`docs/PROJECT_STATUS.md` and in the run artefacts.

**Decisions made and why.**

- **A runner was written rather than the CLI extended.** `docs/ARENA_PROTOCOL.md` Tier 2 says
  the generic CLI must refuse to imply a Tier-2 run occurred and that a concrete runner must
  supply model and training evidence. The runner records torch/transformers/peft versions,
  CUDA, GPU name, base model revision digest and tokenizer into its own output.
- **Every arm reloads the same base checkpoint.** The base `state_dict` is cloned once and
  restored before each arm, so no arm inherits another's weights. This is the single most
  likely silent invalidator of a multi-arm adaptation and it is enforced in code.
- **EXAMPLE_MATCHED was the primary regime and token counts are reported separately.** The
  arms differ in tokens by construction (S-expression costs 1.39x the compact symbolic arm).
  Equalising them would be a different experiment; conflating the two would be the whole
  result. The protocol's warning against pretending the regimes are equivalent is honoured by
  reporting the token ratios beside every accuracy.
- **The halving rule was fixed before any score was read**, in `HALVING_RULE`, with a 0.06
  minimum margin so an arm is never eliminated on a 1–2 item difference.
- **The split is disjoint and domain-stratified**, so no canonical world is both trained on
  and evaluated on, for any arm.

**Tests and verification actually executed.**

- `python -m arena.training.prepare_matched_data` — 5 arms x 676 worlds, split 580/48/48;
  `assert_matched_semantics` PASS; identical target hashes across arms confirmed; distinct
  input hashes across arms confirmed.
- `nvidia-smi` on the instance — NVIDIA A100-SXM4-80GB, driver 580.173.02, CUDA 13.0.
- `torch.cuda.is_available()` — True, torch 2.9.1+cu129, transformers 5.15.0, peft 0.20.0.
- `gpu_matched_runner.py` — executed; per-stage results in `gpu_sprint_results.json`.
- `analyse_sprint.py` — executed on the results; paired bootstrap and Wilson intervals.
- The repository's own test suite was **not** run in this session.

**Results and failures.** See `docs/PROJECT_STATUS.md` for the table and the verdict. The
dominant limitation is that the adapted task saturates: every arm exceeds 0.83 exact match
after Stage A, so the instrument has little headroom and differences at the top compress into
the noise band of a 48-item slice. This is the same class of problem `docs/CLAUDE_HANDOFF.md`
records for the V2 calibration headroom gate, and it is reported rather than worked around.

**Unresolved uncertainty.**

- One base model, one seed, one adaptation configuration. No replication.
- 48 evaluation items per stage: one item is 2.1 percentage points.
- `assert_matched_semantics` is vacuously true on an empty mapping; the arm count is asserted
  separately in `prepare_matched_data.py`. The guard itself should be strengthened.
- The verified-transition rate here checks that the emitted action is well-formed for the
  oracle (required keys, right shapes). It is **not** a claim that the action is optimal or
  that a domain oracle accepted it.

**Effect on the overall project.** The Day 3 box "execute matched short adaptation against
four strong controls" is now evidenced rather than aspirational, and the decision on whether
to build the evolutionary search engine rests on measured paired comparisons instead of
static compactness. `R*-V0` remains unfrozen.

**Next intended step.** Recorded in `docs/PROJECT_STATUS.md` under Exact Next Actions.

---

## 2026-09-06 — Harden assert_matched_semantics so empty candidate sets fail closed

**Date and time.** 2026-09-06. **Branch.** `codex/arena-v0-fitness`.
**Project stage.** `TIER2_MATCHED_ADAPTATION_FIRST_RUN`.

**Objective of the change.** Close the guard defect recorded in the previous entry before it
can invalidate another matched run.

**Files and systems changed.** `arena/training/render_dataset.py`, `docs/PROJECT_STATUS.md`,
`docs/PROJECT_LEDGER.md`. No canonical schema, world, language surface or verifier touched.

**What was completed.** `assert_matched_semantics` now rejects: fewer than two candidate
surfaces, any empty arm, arms of differing length, and two arms whose rendered inputs are
byte-identical. The original checks on identical canonical trajectories and identical target
hashes are unchanged.

**Decisions made and why.** The byte-identical-inputs check was added beyond the reported
defect because two surfaces that render the same bytes are the same experiment run twice, and
a difference between them could only be noise — the same class of error as the
`DEPTH_ADAPTIVE`/`DUAL_VIEW` duplicate found in the HML hard-regime comparison.

**Tests and verification actually executed.**
- Six degenerate cases (empty mapping, one arm, empty arm, identical inputs, length mismatch,
  target mismatch) — **all six raise**; a valid matched pair is still accepted.
- `python -m arena.training.prepare_matched_data` — the real five-arm pipeline still passes.
- `.venv/bin/python -m pytest` — **122 passed**.

**Failures and unresolved uncertainty.** None introduced. The saturation limitation on the
NEXT_ACTION task is unchanged and remains the blocking issue for ranking representations.

**Effect on the overall project.** A matched-adaptation run can no longer report PASS over
nothing. This does not change any measured result.

**Next intended step.** Governed by the HML kill gate: the arena headroom rebuild proceeds
only if `PATH_TO_ROOT` replicates across two readers.
