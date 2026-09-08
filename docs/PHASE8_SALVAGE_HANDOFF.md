# Phase 8 Salvage Handoff — diagnostic infrastructure, not a representation result

**Status: `PHASE8_DIAGNOSTIC_INFRASTRUCTURE`.**

**No founder tournament was run. No preregistration was frozen. No language was ranked. No
scientific result is claimed here, and none may be read out of this commit.**

Phase 8 was building the programme's first experiment to compare several representations of
identical mathematics against one Solver. Mid-build the project owner reset the mission: the
controlled representation experiment is now explicitly a *local fitness assay* inside a larger
open-ended language-discovery system (`docs/HAMILTONIAN_CHESS_META_GOAL.md`). This document
records exactly what Phase 8 built, what state each piece is in, what it measured at zero model
cost, and what it never got to do — so that nothing useful is lost and nothing unfinished is
mistaken for evidence.

---

## 1. Why Phase 8 stopped

Two independent reasons, both recorded rather than reconciled after the fact:

1. **The owner reset the mission** (the governing reason). Game R is demoted from mission to
   assay; the founder tournament is explicitly stood down.
2. **The frozen Solver ceased to exist mid-session.** Phase 8's preregistration named
   `qwen38-rvn:latest`, digest `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`
   — V7's Solver, chosen so the difficulty ladder could be read against V7's measured ceiling. At
   **11:43 on 2026-09-08** that model, together with `qwen38-huihui` and `qwen36-huihui`, was
   removed from the local Ollama and replaced by `qwen3.6:27b-mlx`
   (digest `d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`, family `qwen3_5`,
   27.8B, `nvfp4`, `safetensors`, template `{{ .Prompt }}`, context 262144, capabilities
   `completion, vision, tools, thinking`). The manifest is gone, so the old digest is
   unrecoverable, and the name is a local build that cannot be re-pulled from a registry.

Both facts were established **before** any founder call. The earlier engineering measurements in
this document that used the old Solver (token counts and latencies) were taken while it was still
served and are labelled as such.

**Consequence for anyone reading old numbers:** V7's ladder values (`precondition_conjunction`
≥ 0.958 at premises 2/3/5) were measured on a Solver that no longer exists on this machine. They
may not transfer to any replacement. Nothing in Phase 8 assumed otherwise, because Phase 8 never
ran a Solver against its own ladder.

---

## 2. Inventory — every Phase 8 file, classified

| Component | Path | LOC | Tests | State |
|---|---|---|---|---|
| Extended precondition ladder | `arena/environments/precondition_ladder.py` | 1,132 | 23 | **COMPLETE** |
| Rendered-prompt adversary | `arena/experiments/rendered_prompt_adversary.py` | 1,620 | 21 | **COMPLETE** |
| Power analysis | `arena/experiments/precondition_power.py` | 1,286 | 31 | **COMPLETE** |
| Live Ollama adapter | `arena/experiments/ollama_live.py` | 299 | 14 | **COMPLETE** (live path never exercised end to end — see §5) |
| Founder runner | `arena/experiments/game_r_precondition_founder_v1.py` | 1,686 | 37 | **COMPLETE**, dry-run green; live stages never run |
| Parity contract | `tests/experiments/test_precondition_parity.py` | — | 13 | **COMPLETE** |
| Shortcut audit script | `research/phase8/shortcut/rendered_shortcut_audit.py` | 179 | via module tests | **COMPLETE**, output committed |
| Parity/span audit script | `research/phase8/parity/span_audit.py` | 727 | via test file | **COMPLETE**, output committed |
| Transitive reanalysis | `research/phase8/transitive/*.py` | 1,879 | none | **PARTIAL** — scripts run, three JSON outputs exist, **no write-up, conclusions not integrated** |
| Preregistration | `docs/GAME_R_PRECONDITION_FOUNDER_V1_SPEC.md` | — | — | **SKELETON WITH `TBD`s — NEVER FROZEN, NOW SUSPENDED** |
| Shortcut audit write-up | `docs/PRECONDITION_RENDERED_SHORTCUT_AUDIT.md` | — | — | **COMPLETE** as a measurement; its §7 "preregistered gate" is a *proposal that was never enacted* |
| Power write-up | `docs/PRECONDITION_POWER_ANALYSIS.md` | — | — | **MISSING** — the module and its tests exist, the document was never written |

Test totals: **1,132 passed, 1 skipped** (base commit `2047fda`: 964 passed, 1 skipped), so Phase 8
added **168 tests**. `ruff check`, `ruff format --check` and `mypy arena` (135 files) are clean.

---

## 3. What Phase 8 actually measured — all at zero model cost

These are real measurements on committed artifacts. They are properties of *generators and
renderers*, not of any Solver, and they survive the mission reset intact.

### 3.1 The mechanism is clean on the rendered prompt

`artifacts/reports/precondition_rendered_shortcut_audit.json`, 45 cells (9 strata × 5 surfaces),
adversaries developed and frozen on one pool and evaluated on a disjoint fresh pool of 400 items.

- Best frozen adversary anywhere: **0.5625** (`P05`, Compact Symbolic). Chance is 0.500.
- Every candidate stratum at premises ≥ 7 sits at **≤ 0.54**.
- Every candidate-mention and option-text feature is **pinned at exactly 0.5 on 100% of twin
  pairs** — balance by construction, now confirmed on the bytes the Solver would actually see,
  not on the canonical JSON that V1–V7 audited by mistake.
- Only two of nineteen features can move across a twin at all (`gzip_delta`,
  `window_ngram_overlap`), and their excess over the label-permutation selection null is ≤ 0.04.

This closes forensic-audit defects C1 (the audit read a string the Solver never receives) and C3e
(a max-over-rules with the ancestor's Bonferroni + Clopper–Pearson correction deleted) —
**prospectively, in new code, without touching the frozen instruments.**

### 3.2 Representation parity holds — but two "different" surfaces are nearly the same string

`artifacts/reports/precondition_parity_audit.json`, 6 strata × 8 surfaces × 28 arm pairs.

- Harness parity passes everywhere: one envelope signature, one answer protocol, exact canonical
  recovery per arm, distinct rendered bytes, twin differences local to the assumptions block.
- **The finding worth carrying forward:** `L3_JSON_AST` and `L6_GRAPH_TRIPLES` share **98.6%** of
  their state bytes via ≥40-character spans at `P20`, and `L0_STRUCTURED_ENGLISH` vs
  `L3_JSON_AST` reaches a **0.82** sequence-similarity ratio. The eight seed "languages" are not
  eight independent points in design space; several are one serialisation behind different key
  names. This is exactly the failure the V7 audit's E1 test caught in the Astra bridge, appearing
  again inside the seed population itself.

**This is a meta-game finding, not a Phase-8 finding.** Any evolutionary search that treats the
eight seeds as a diverse founding population is starting from a narrower space than it thinks.

### 3.3 Difficulty ladder and cost, on the now-deleted Solver

Measured while `qwen38-rvn` was still served, via `num_predict=1` preflight (exact
`prompt_eval_count`, not a character heuristic):

| stratum | JSON AST tokens / s | Structured English | Compact Symbolic |
|---|---|---|---|
| P12 | 12,093 / 21.9 s | 9,805 / 16.6 s | 5,183 / 8.4 s |
| P16 | 15,162 / 28.2 s | 12,298 / 22.1 s | 6,508 / 11.0 s |
| P20 | 18,147 / 36.0 s | 14,707 / 29.3 s | 7,749 / 14.2 s |

All fit the 32,448-token budget. Characters per token: JSON-like 3.0, Structured English 3.4,
Compact 2.3. A rotated-option twin run immediately after its base costs ≈ 2 s because Ollama
serves the KV-cached prefix — which is what made a position audit affordable at all.

---

## 4. What is reusable in the meta-game, and why

| Piece | Meta-game role |
|---|---|
| **Rendered-prompt adversary** | A general anti-cheating tool. Any evolved language must be shown not to leak its answer through surface statistics; this family (64 rules + 2 shallow models, Holm/Clopper–Pearson, DEV/EVAL split, permutation null) applies to *any* renderer, not just the precondition mechanism. It only ever sees `(prompt, n_options)`, enforced by an AST import ban. |
| **Power analysis** | Sizes any matched parent-vs-child comparison. Exact McNemar power, clustered variants, equivalence tests, and a shortcut-gate operating characteristic. |
| **Founder runner** | The skeleton of a *matched evaluator*: parity enforcement, cache identity, budget, position audit by option rotation, artifact non-overwrite, cache-sentinel protection. Refactor its stage boundaries; keep its discipline. |
| **Live Ollama adapter** | Exact token counting on a runtime with no tokenize endpoint, via preflight with memoisation. Needed by any Solver-facing evaluation. |
| **Precondition ladder** | Demoted to a **diagnostic arena**: a deterministic, balanced-by-construction, difficulty-parameterised generator with a verified independent truth oracle. Useful as a cheap Level-1 instrument; not a long-horizon world. |

---

## 5. What Phase 8 never did — stated plainly

- **No model call was ever made through the founder runner.** The live stages (`--smoke`,
  `--calibrate`, `--tournament`) exist, are unit-tested against a stub, and were never executed
  against a real Solver. The one live attempt failed at the digest check because the Solver had
  been deleted; that is the full extent of the live exercise.
- **No stratum was selected.** The calibration band and target in the spec are `TBD`.
- **No Δ(R_A, R_B) was computed.** The programme's central quantity remains uncomputed, exactly
  as it was after V7.
- **The preregistration was never frozen** and is now suspended. Its §7 roster, §6 shortcut gate
  and §10 endpoints are a *design*, not a commitment, and no threshold in it has ever governed a
  result.
- **The transitive-dependency reanalysis is unfinished.** Scripts and three JSON outputs exist;
  no document, no verdict. Do not cite it.
- **`docs/PRECONDITION_POWER_ANALYSIS.md` was never written.** The numbers live only in the
  module and its tests.

---

## 6. Standing sentinels — unchanged by this commit

`RSTAR_NOT_IDENTIFIED` · `GAME_R_INSTRUMENT_NOT_QUALIFIED` (operational) ·
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` (scientific) · `TRAINING_LANGUAGE_V0_BASELINE`

Phase 8 created no sentinel and retired none. It produced infrastructure and two zero-model-cost
measurements, both of which are properties of generators and renderers.

---

## 7. If Phase 8 is ever resumed

It would need: a Solver decision recorded from scratch (the old one is gone); the calibration band
derived and frozen; the stratum selected on control-arm data only; the frozen adversary set
re-evaluated on the exact tournament pool; and the `TBD`s in the spec filled *before* the first
founder call. None of that is authorised now. The correct next step is the meta-game, not this
experiment.
