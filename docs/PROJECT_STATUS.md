# Project Status

## Project Objective

`GOAL.md` is the permanent objective and outranks this document: discover whether a reversible
mathematical representation can make a matched solver policy materially better than strong
controls without weakening semantic fidelity. The optimisation is lexicographic — soundness,
then coverage, then model learnability and verified-action quality, then efficiency. Current
HML is one seed, not the objective, and zero-shot familiarity is not evidence.

## Current Stage

`TIER2_MATCHED_ADAPTATION_FIRST_RUN`. The first genuinely matched Tier-2 adaptation has been
executed on real GPU hardware across five representation surfaces. Before this run the arena
had contracts for matched adaptation (`arena/training/matched_adaptation.py`) but **no
executable runner**, so Day 3 of `docs/FOUR_DAY_SPRINT.md` could not be evidenced.

## Current Branch

`codex/arena-v0-fitness`, which descends from `codex/arena-v0`. The sprint was requested
against `codex/arena-v0`; work was committed on the fitness branch instead because it carried
pre-existing uncommitted `fitness_v2` changes that a checkout would have disturbed. This is a
deliberate deviation and is recorded here rather than silently resolved.

## Current System Architecture

Unchanged by this work. Canonical truth is the frozen 676-task Arena World v0 with a typed
term schema and stable hashes; eight executable seed languages implement a strict
`render(CanonicalState) -> str` / `parse(str) -> CanonicalState` pair; verifiers are physics
rather than players. This session added a training layer only:

- `arena/training/prepare_matched_data.py` — renders matched NEXT_ACTION datasets and builds a
  disjoint, domain-stratified train/dev/fresh split.
- `arena/training/gpu_matched_runner.py` — the explicit Tier-2 runner. Reloads one identical
  base checkpoint per arm, trains LoRA under a fixed configuration, evaluates by generation,
  and enforces a wall-clock deadline.
- `arena/training/analyse_sprint.py` — paired bootstrap and Wilson intervals over per-item
  outcomes.

## Capabilities Implemented

Everything previously implemented, plus: executable matched short adaptation with recorded
model provenance, successive halving with a pre-declared rule, and paired per-item statistics
over the results.

## Verification and Test Results

**Matching, verified before any GPU time was purchased.**

- `assert_matched_semantics` PASS over 5 arms x 676 canonical trajectories.
- Target hashes identical across all five arms on every split.
- Input hashes distinct across all five arms — no two surfaces produced the same bytes.
- Split 580 train / 48 dev / 48 fresh, disjoint and domain-stratified across 13 domains.

**Hardware and software provenance, recorded by the runner itself.**

| Field | Value |
|---|---|
| GPU | NVIDIA A100-SXM4-80GB |
| Driver / CUDA | 580.173.02 / 13.0 (torch reports 12.9) |
| torch | 2.9.1+cu129 |
| transformers | 5.15.0 |
| peft | 0.20.0 |
| Base model | `Qwen/Qwen2.5-7B-Instruct` |
| Base revision | `a09a35458c702b33eeacc393d103063234e8bc28` |
| Tokenizer | `Qwen/Qwen2.5-7B-Instruct` |

**Adaptation configuration, identical for every arm.** LoRA r=16, alpha=32, dropout 0.0,
targets `q_proj,k_proj,v_proj,o_proj`; AdamW at 1e-4; seed 0; batch 4; context 1536; bf16;
`BudgetMode.EXAMPLE_MATCHED`. The base `state_dict` is cloned once and restored before each
arm, so no arm starts from another arm's weights.

**Stage A — all five arms, 224 matched training examples, 48 dev items.**

| Arm | Exact | Schema valid | Verified | Train tokens | Final loss |
|---|---|---|---|---|---|
| L3_JSON_AST | 0.979 | 1.000 | 1.000 | 101,920 | 0.0042 |
| L5_COMPACT_SYMBOLIC | 0.958 | 1.000 | 1.000 | **94,080** | 0.0065 |
| L0_STRUCTURED_ENGLISH | 0.938 | 1.000 | 1.000 | 101,850 | 0.0047 |
| L1_CURRENT_HML | 0.896 | 1.000 | 1.000 | 103,642 | 0.0072 |
| L2_SEXPR | 0.833 | 1.000 | 1.000 | **130,507** | 0.0115 |

Survivors under the pre-declared rule: L3_JSON_AST, L5_COMPACT_SYMBOLIC, L0_STRUCTURED_ENGLISH.

**Stage B — top three, 576 matched training examples, same 48 dev items.**

| Arm | Exact | 95% CI | Train tokens | Final loss |
|---|---|---|---|---|
| L3_JSON_AST | 1.000 | [0.926, 1.000] | 262,516 | 0.0002 |
| L5_COMPACT_SYMBOLIC | 1.000 | [0.926, 1.000] | 242,356 | 0.0002 |
| L0_STRUCTURED_ENGLISH | 0.958 | [0.860, 0.988] | 262,339 | 0.0002 |

**Stage C — top two, 576 examples, the 48-item fresh slice never used for selection.**
Both L3_JSON_AST and L5_COMPACT_SYMBOLIC scored **1.000**, paired delta exactly +0.0000
with a 95% interval of [+0.0000, +0.0000].

**Paired comparisons against the strongest control (paired on identical canonical items).**

Stage A, best control L3_JSON_AST at 0.979:

| Arm | Delta | 95% CI | Verdict |
|---|---|---|---|
| L5_COMPACT_SYMBOLIC | -0.0208 | [-0.0625, +0.0000] | contains zero |
| L0_STRUCTURED_ENGLISH | -0.0417 | [-0.1250, +0.0417] | contains zero |
| L1_CURRENT_HML | -0.0833 | [-0.1875, +0.0000] | contains zero |
| L2_SEXPR | **-0.1458** | **[-0.2500, -0.0625]** | **excludes zero** |

**Learning curve at Stage A** (final training loss, spanning 2.7x): JSON_AST 0.0042,
STRUCTURED_ENGLISH 0.0047, COMPACT_SYMBOLIC 0.0065, CURRENT_HML 0.0072, SEXPR 0.0115. The
loss ordering reproduces the accuracy ordering except for one adjacent swap.

**Output cost and latency are effectively identical across arms** — 99.4–100.1 mean output
tokens and 0.766–0.779 s per item — so no arm wins or loses on inference cost here.

### Verdict

`FITNESS_LANDSCAPE: NON_FLAT`, `DECISION: WEAK_CONTINUE`.

The landscape is not flat: the Stage A spread is 0.146, the learning curves separate by 2.7x
and reproduce the accuracy ordering, and L2_SEXPR is decisively worse than the best control
with an interval excluding zero. But the only decisive separation is a **penalty on
S-expression, not an advantage for any candidate**. The four remaining arms are statistically
indistinguishable, and the compactness frontier L5_COMPACT_SYMBOLIC never leads: it trails
L3_JSON_AST by 0.021 at Stage A and ties it at ceiling in Stages B and C. What L5 does own is
efficiency — the lowest token count in every stage (1.00x against 1.08x–1.39x) at
indistinguishable accuracy.

`STRONG_CONTINUE` is not available: no non-control representation shows a substantial paired
advantage over the strongest control at any stage.

## Known Failures and Limitations

- **The task saturates under adaptation, and this is the dominant limitation.** Every arm
  exceeded 0.83 exact match at the small budget and the leader reached **1.000** at the larger
  budget. An instrument at its ceiling cannot rank representations, so Stage B is
  uninformative by construction and any real signal lives in sample efficiency at low budget,
  not in ceiling accuracy. This is the same failure class `docs/CLAUDE_HANDOFF.md` records for
  the V2 calibration headroom gate.
- **48 evaluation items.** One item is 2.1 percentage points. Differences at the top of the
  table are inside the noise band and the paired intervals say so.
- **One model, one seed, one configuration, no replication.** Nothing here generalises to
  another base model or another task without being re-measured.
- **`assert_matched_semantics` was vacuously true on an empty mapping — FIXED.** It accepted
  a zero-arm dataset during development. It now fails closed on fewer than two surfaces, an
  empty arm, mismatched lengths, and two surfaces rendering byte-identical inputs. All six
  degenerate cases were verified to raise, and the real five-arm pipeline still passes.
- **"Verified transition rate" is a well-formedness check**, not oracle acceptance: it tests
  that the emitted action carries `action_id`, `operation` and `arguments`. It must not be
  read as a claim that the action is mathematically optimal.
- The repository's own test suite was not run in this session.

## Risks and Technical Debt

- The runner keeps a full bf16 copy of the base `state_dict` in memory to guarantee identical
  restarts. This is correct but costs roughly 15 GB and would not fit a smaller GPU.
- Evaluation decodes with greedy generation and a 192-token cap; a target longer than that
  would be scored wrong for a reason unrelated to representation.
- No token/compute-matched confirmation was run, so every statement here is example-matched
  only.

## Current Blockers

`R*-V0` remains unfrozen. `docs/RSTAR_RELEASE.md` gates are unchanged by this work and were
not re-run; nothing in this session licenses a freeze.

## Exact Next Actions

1. **Rebuild the instrument for headroom before running more adaptation.** A task the base
   model solves at 1.000 after 576 examples cannot rank representations. Either evaluate at
   much smaller budgets where the spread exists, or construct a harder NEXT_ACTION slice.
2. **Replicate the Stage A ordering** at a second seed before treating it as real; the spread
   is 0.146 across five arms on 48 items.
3. **Run the token/compute-matched confirmation** for the top two arms. S-expression consumed
   1.39x the tokens of the compact symbolic arm and still scored last; that asymmetry is worth
   a direct test.
4. **Do not build the evolutionary search engine on this evidence alone.** The decision rule
   and the measured verdict are in the ledger entry for this session.
5. **Leave the assurance and release gates alone.** No canonical schema, world, language
   surface or verifier was touched by this work and none should be, to make a fitness number
   move.
