# Hamiltonian Chess — Repository Remap

**Status: AUDIT ONLY.** No source file, artifact, hash, sentinel or test was modified to produce
this document. Every number below was either read out of the source at a cited line, read out of a
committed artifact, or *measured* by running the repository's own code in this worktree
(`.venv/bin/python`). Measurements made for this audit are labelled **[measured here]** and the
probe is described inline so it can be re-run.

Audit date 2026-09-08. Branch `claude/hamiltonian-phase-8-experiment-691d22`, base `c1dd586`.
`.venv/bin/python -m pytest` at audit time: **1,132 passed, 1 skipped, 0 failed**.

**Worktree note.** At audit time this worktree also contained untracked files written by concurrent
sessions — `docs/HAMILTONIAN_CHESS_META_GOAL.md`, `docs/HAMILTONIAN_CHESS_META_MDP.md`,
`docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md`, `research/phase9/`. This audit created exactly one file
(this one) and read those others only where cited, with attribution. Nothing from them is treated
as this document's own evidence.

---

## 0. The remap criterion

The project's top-level mission is no longer "find the best representation for a 2-option
micro-probe". It is an **open-ended meta-game**: an INNER mathematical-reasoning MDP over
*verified multi-step trajectories*, in which a Solver observes state only through a language `L`
and the verifier owns truth, nested inside an OUTER evolutionary search over a *population of
languages* (choose parent → mutate → semantic gate → matched evaluation → fitness vector → archive
→ next generation). A component is therefore classed by asking one question and one question only:
**what does it do when the horizon is >1 step and the population is >1 generation?** A component is
**KEEP** if it already runs unchanged under those two conditions; **REFACTOR** if the concept
survives but the interface is pinned to horizon-1 or generation-1 (or to a hand-written surface
registry); **DEMOTE_TO_DIAGNOSTIC** if it remains a correct and useful *instrument* but measures
the local fitness assay rather than the mission; **ARCHIVE** if it is a historically important
result that is superseded, refuted or structurally unusable and must not be built on; **MISSING**
if the meta-game requires it and no code implements it. Nothing is classed on aesthetics, LOC, or
age — only on measured behaviour under the two conditions.

**The single most consequential measured fact in this document:** the repository's true maximum
horizon is **1**, in every environment, every experiment, every trajectory, and in the harness's
own `TaskItem` type. `CanonicalTrajectory` exists but has never been populated with more than one
transition — 676 of 676 world-v0 trajectories carry exactly one **[measured here]**.

---

## 1. Master table

LOC = `wc -l`. "Tested by" lists the test files that import the component. "Dependents" lists
non-test importers. Classes: **K**=KEEP, **RF**=REFACTOR, **DD**=DEMOTE_TO_DIAGNOSTIC,
**AR**=ARCHIVE.

| # | Component | Paths | LOC | Tested by | Dependents (non-test) | Class | Evidence |
|---|---|---|---:|---|---|---|---|
| 1 | Canonical schema (Σ) | `arena/canonical/schema.py`, `equivalence.py`, `__init__.py` | 435 | `tests/canonical/test_schema.py` (70) | everything | **RF** | 8 frozen dataclasses incl. `CanonicalTransition` (`schema.py:304`) and `CanonicalTrajectory` (`:322`) which **exist but are never populated with >1 transition**; 0/368 real Lean states map losslessly (§3.1) |
| 2 | World generator (Gold v0) | `arena/tasks/generators/world_v0.py` | 613 | `tests/tasks/test_world_v0.py` (67) | `pipeline.py`, `route_b_data.py`, `hall_of_fame.py` | **DD** | 676 tasks, **every one** `len(transitions)==1`, `legal_actions==1`, `plausible_invalid_actions==1` **[measured here]**; `proof_length=1` hardcoded `world_v0.py:540` |
| 3 | Task schema | `arena/tasks/schema.py`, `curriculum.py`, `quality.py` | 1077 (pkg) | `tests/tasks/test_curriculum.py` | `world_v0`, `pipeline` | **RF** | `ArenaTask` wraps a `CanonicalTrajectory` (`schema.py:93`) — the right shape, wrong content |
| 4 | Verifier | `arena/verifier/` (base, native, differential, numeric, sympy, z3, lean_adapter, external) | 741 | `tests/verifier/test_native.py` (44), `test_external.py` (25) | `assurance`, `world_v0`, `pipeline`, `players/refuter` | **K** | `Verifier` protocol already has `verify_transition` (`base.py:44`); representation-independent by construction |
| 5 | Semantic assurance | `arena/assurance/` (mutations 656, reducers 241, suite 159, failures 155, exhaustive 89, properties 85, fuzz 82, side_channels 87) | 1574 | 5 files in `tests/assurance/` (88 total) | `players/refuter`, `pipeline` | **K** | Bounded, denominator-explicit, verifier-backed; `roundtrip_property` (`properties.py:66`) is exactly the meta-game's losslessness check |
| 6 | Refuter | `arena/players/refuter.py` | 143 | `tests/players/test_refuter.py` (28) | `arena/pipeline.py:304` | **K** (wiring RF) | Semantic + grammar attack with counterexample minimisation; **but the production call site passes `parser=None`, so the grammar half never runs** (`pipeline.py:308-309`) and it attacks exactly one state (`pipeline.py:303,307`) |
| 7 | Model-view compiler | `arena/model_view/compiler.py` (136), `genome.py` (215), `projection.py` (308) | 671 | `tests/model_view/test_model_view.py` (99) | `game_r_formal_v1`, `fitness_v3/4/5/7` | **K** | `validate()` (`compiler.py:117`) enforces mathematical-hash recovery **and** independent reproducibility — the meta-game's semantic gate primitive |
| 8 | Genome phenotype codec | `arena/languages/phenotype.py` | 332 | `tests/languages/test_seed_roundtrip.py`, `test_malformed.py` | `model_view/compiler.py:10`, `game_r_formal_v1` | **K** | The **only** genome-driven codec: 22–24 of 44 one-gene variants change rendered bytes, 0/44 lose round-trip **[measured here]** (§3.2) |
| 9 | 8 seed surface codecs | `arena/languages/{structured_english,hml,sexpr,json_ast,prefix,symbolic,graph,hybrid}/__init__.py` | 449 | `tests/languages/*` (168) | `registry.py`, `pipeline.py`, `route_b_data.py` | **AR** | **0 of 44 one-gene mutations change one byte, for all 8 codecs** **[measured here]**. `_encode_payload` never reads `self.genome` — grep returns nothing (§3.2) |
| 10 | Wire validator / notation | `arena/languages/_wire.py` (250), `_notation.py` (231), `_json_tools.py` (36), `base.py` (61), `registry.py` (70) | 648 | `tests/languages/conftest.py` etc. | all codecs | **K** (`_wire`, `_notation`) / **RF** (`registry`) | `_wire` is a closed contract rejecting missing *and* unknown keys (`_wire.py:20-29`); `registry.py:52-62` hard-codes exactly 8 surfaces — no mutant can be registered |
| 11 | Language genome (R) | `arena/genome/` (mutation 439, validation 198, schema 199, seeds 186, genes 176, crossover 130, registry 53) | 1499 | `tests/genome/*` (210) | `players/architect`, `model_view/genome`, `phenotype`, `languages/*` | **RF** | 14 gene families, but **5 are byte-inert on state rendering** (`alphabet`, `composition`, `obligations`, `evidence`, `error_locality`) **[measured here]**; the repo's own audit artifact records `phenotype_genes` = 9 (`artifacts/reports/game-r-mutant-audit.json`) |
| 12 | Architect (mutation proposer) | `arena/players/architect.py` | 98 | `tests/players/test_architect.py` (14) | `arena/pipeline.py:168` | **RF** | Deterministic one-gene neighbour enumerator (`architect.py:50-95`); `name = "deterministic-neighbour-architect-v0"` — **not learned**, receives no fitness feedback |
| 13 | League registry / archive | `arena/league/registry.py` (262), `selection.py` (61), `hall_of_fame.py` (63), `matches.py` (38), `__init__.py` (15) | 439 | `tests/league/test_registry.py` (54) | `pipeline.py:16-18` | **RF** | Multi-axis, no scalar Elo, Pareto status persisted. But `artifacts/matches/league-registry.json` holds **8 candidates, 0 observations, 0 matches**; `matches.py` has no runtime producer; `players/league_manager.py` (21 LOC) has **zero importers repo-wide** |
| 14 | Fitness metrics / gates / Pareto | `arena/fitness/metrics.py` (260), `gates.py` (146), `pareto.py` (133), `__init__.py` (27), `search_metrics.py` (30), `entropy.py` (5) | 601 | `tests/fitness/test_fitness.py` (51) | `pipeline`, `reporting`, `league`, `evaluation/static` | **RF** (metrics/gates/pareto) / **AR** (`search_metrics`, `entropy`, `__init__`) | `pareto.py` is live via `pipeline.py:13`→`selection.py:37`; `search_metrics.py` and `entropy.py` have **zero importers and zero tests** |
| 15 | Surrogate | `arena/surrogate/` (model 202, dataset 83, features 82, `__init__` 15) | 382 | `tests/surrogate/test_surrogate.py` (43) | **none** | **AR** | Only importer is its own test, whose data is 6 hand-written literals (`test_surrogate.py:8-9`). Never trained on a genome or an evaluation result |
| 16 | Evaluation (static + landscape) | `arena/evaluation/static.py` (273), `landscape.py` (202) | 480 | `tests/evaluation/*` (80) | `pipeline`, `release`, `reporting`; `landscape` → `game_r_formal_v1:70`, `fitness_v2:32`, `precondition_power:66` | **DD** (`static`) / **K** (`landscape`) | `static.py` scores *bytes*, not a Solver (that is the whole `L5_COMPACT_SYMBOLIC` "win"); `landscape.py` supplies McNemar + clustered bootstrap, which the meta-game needs unchanged |
| 17 | Pipeline / CLI control plane | `arena/pipeline.py` (388), `cli.py` (385), `release.py` (152), `reporting.py` (124) | 1049 | `tests/integration/test_runtime.py` (27), `tests/test_release.py` (8) | console script `arena` | **RF** | **The outer loop is severed here**: `mutate()` writes genomes with status `GENOME_VALIDATED_RENDERER_PENDING` (`pipeline.py:180`) and `evaluate()` refuses any candidate without a registered renderer (`pipeline.py:210-214`); `run_league()` iterates `seed_languages()` only (`pipeline.py:238`) |
| 18 | Compiler facade | `arena/compiler/projection.py` (54), `validator.py` (40), + parser/renderer/canonicalizer/diagnostics (68) | 183 | `tests/compiler/*` (46) | `projection.py` has 8 importers | **K** (`projection`, `validator`) / **AR** (facade four) | `projection.py` (leak-scrubbing observation projection) is the most-reused file in the package; the 4 facade files are imported only by `__init__.py` and one test |
| 19 | Provenance / storage / cache | `arena/provenance.py` (132), `arena/storage/` (db 388, artifacts 37, hashes 19) | 576 | `tests/storage/test_db.py` (56), `tests/corpus/*` | `artifacts.py` used by **12 experiment files**; `db.py` by `pipeline` only | **K** (`provenance`, `artifacts`, `hashes`) / **RF** (`db`) | `ArtifactStore` is the single most-used module across experiments; `db.py` is confined to the CLI island |
| 20 | Corpus strategy | `arena/corpus/trace.py` (430), `contamination.py` (396), `provenance.py` (332), `__init__.py` (63) | 1221 | `tests/corpus/*` — 3 files, 744 LOC, 71 test functions | **none anywhere** | **K** (concept) / **RF** (unwired) | `grep -rn "arena.corpus"` hits only `tests/corpus/`. Exposure is transitive through derivation (`contamination.py`), `may_train` returns False for unregistered sources; registry `artifacts/corpus/source_registry.json` has 27 sources, 12 never-train, 6 licence-blocked, 25 unverified |
| 21 | Formal donor adapter | `arena/environments/formal_structural.py` | 398 | **no dedicated test file** | `fitness_v5:48`, `fitness_v7:114`, `game_r_formal_v1:69` | **K** | The only Lean→canonical bridge that produces `CanonicalState`; `DONOR_ROOT` at `:49` is the sole hardcoded absolute path in `arena/` that is opened. **It survives §3.1 only by discarding data: `:291-293` `if len(goals) != 1: continue`** |
| 22 | Precondition ladder (V2) | `arena/environments/precondition_ladder.py` | 1132 | `tests/environments/test_precondition_ladder.py` (543) + 3 more | `game_r_precondition_founder_v1` (dynamic import `:444`) | **DD** | Horizon 1; `options: tuple[CanonicalAction, CanonicalAction]` (`:479`) — binarity is enforced by the type. Balanced by construction; the cleanest instrument in the repo |
| 23 | Three real formal families | `arena/environments/{premise_selection,rewrite_direction,legal_transform}.py` | 3367 | `tests/environments/*` (1292) | **no experiment imports them** | **AR** (as Game-R arms) / **DD** (as solver-capability probes) | 63,831 + 3,466 + 24,000 items from 250,814 LeanDojo train steps. They emit **raw Lean pretty-printed strings**, zero `CanonicalState` — a pre-rendered string fixes R, so all 8 arms would receive byte-identical input. The spec itself leads with this (`GAME_R_FORMAL_ARENA_V1_SPEC.md:4-8`) |
| 24 | V1–V7 fitness experiments | `arena/experiments/fitness_v{1,2,3,4,5,7}.py` (+forensics, preflight) | 8328 | `tests/experiments/test_fitness_v{1,2,3,4,7}.py` (1489) — **no `test_fitness_v5.py` exists** | v7←v5←v4 chain | **DD** (v4/v5/v7 machinery) / **AR** (v1/v2/v3 verdicts) | All horizon 1, all 2-option; V3 ruled invalid; V7 `V7_SHORTCUT_DOMINATED`, 0/3 qualified; V1's `materialize_population()` (`fitness_v1.py:115`) is generation 1, frozen |
| 25 | Tournament harness | `arena/experiments/game_r_formal_v1.py` | 1773 | `tests/experiments/test_game_r_formal_v1.py` (870) | `game_r_precondition_founder_v1` | **RF** | `assert_arena_parity` (`:625`) is a real semantic gate incl. "byte-identical arms are a refusal" (`:696-701`). But `TaskItem` (`:319`) is single-step by type and `Solver` (`:948`) is stateless by type. **It has never made a model call.** |
| 26 | Mutant audit | `arena/experiments/game_r_mutant_audit.py` | 349 | `tests/experiments/test_game_r_mutant_audit.py` (104) | — | **K** | 5-check Game-R compatibility gate; artifact records **120/120 `GAME_R_COMPATIBLE`**, 128 rows (8 founders + 120 mutants), 0 structural near-duplicates |
| 27 | Phase-8 adversary | `arena/experiments/rendered_prompt_adversary.py` | 1620 | `tests/experiments/test_rendered_prompt_adversary.py` (657) | — | **K** | Scores on the **rendered prompt** only, with Bonferroni + Clopper–Pearson + permutation null — it repairs the C1/C3d/C3e defects that voided V7 |
| 28 | Phase-8 power analysis | `arena/experiments/precondition_power.py` | 1573 | `tests/experiments/test_precondition_power.py` (394) | — | **K** | Exact clustered McNemar power by FFT; no model call. Directly reusable as the meta-game's sample-size calculator |
| 29 | Phase-8 founder experiment | `arena/experiments/game_r_precondition_founder_v1.py` | 1762 | `tests/experiments/test_game_r_precondition_founder_v1.py` (1147) | — | **RF** | 3 stages (smoke/calibration/tournament) with cache sentinels and Holm — the closest thing to a generation, but it evaluates **one fixed roster**, never a population |
| 30 | Solver adapter | `arena/experiments/ollama_live.py` (310); `OllamaSolver` in `game_r_formal_v1.py:1017` | 310 | `tests/experiments/test_ollama_live.py` (356) | `game_r_precondition_founder_v1:89` | **K** | Digest-frozen solver (`FROZEN_SOLVER`), injectable transport, exact `prompt_eval_count` token accounting |
| 31 | Matched training | `arena/training/` (route_b_data 627, verified_eval 561, gpu_matched_runner 360, prepare_matched_data 353, gpu_authorisation 207, render_dataset 137, analyse_sprint 106, matched_adaptation 67, evaluation 46, scout 30) | 2495 | `tests/training/*` (1391) | `route_b_data`→`languages/registry` | **K** (`gpu_authorisation`, `verified_eval`, `route_b_data` nesting logic) / **AR** (Route B historical results) | `gpu_matched_runner.py:33` `HALVING_RULE` is a **real successive-halving rule** — and is imported by nothing but two helper functions in a test |
| 32 | TRAINING_LANGUAGE_V0 | `releases/TRAINING_LANGUAGE_V0/` (12 modules) | 4008 | `tests/releases/*` — 13 files, 1,713 LOC, **129 test functions** | **nothing in `arena/` imports it**; it imports `arena.canonical`, `arena.genome`, `arena.languages` (one-way) | **K** (as the vNext Σ candidate) | Handles every REQUIRED canonical-vNext gap natively; `package_hash 443c8f79…`; self-labelled `evidence_level: TRAINING_LANGUAGE_V0_BASELINE`, "NOT a Game-R result". Its `HONEST` profile is *rejected* by the frozen `NativeVerifier` |
| 33 | Astra bridge | `research/astra/` (8 modules, 1223), `docs/astra/` | 1223 | `research/astra/tests/*` (3 files, 258 LOC) — **not under `tests/`** | research-only; imports `arena.languages._json_tools`/`_notation` | **AR** (as a Game-R arm set) / **DD** (as a source-projection parity study) | 300 dev items, 5 representations, 1,500 renderings, 300/300 private-field noninterference. But it fails the ≥40-char cross-arm span falsifier at **300/300 × 5/5**; 4 of 5 codecs are 91–98% identical JSON behind a different line prefix. Status `CANONICAL_GAME_R_BRIDGE_PARTIAL`; 2 commits, frozen |
| 34 | Research / audit corpus | `research/` (41 dirs) | 24960 | `research/codex_audit/tests/` (79), `research/astra/tests/` (258) | excluded from lint (`pyproject.toml:37`) | **DD** | One-off analysis scripts kept for reproducibility; never imported by `arena/` |

### 1a. Class tally

The 34 rows above group files; several rows carry a split class. The definitive per-component
tally is below — **57 classified units**.

**KEEP — 18.** `arena/verifier/` · `arena/assurance/` · `arena/players/refuter.py` (the class) ·
`arena/model_view/` · `arena/languages/phenotype.py` · `arena/languages/{_wire,_notation,_json_tools,base}.py` ·
`arena/genome/{mutation,crossover,validation}.py` · `arena/environments/formal_structural.py` ·
`arena/experiments/game_r_mutant_audit.py` · `arena/experiments/rendered_prompt_adversary.py` ·
`arena/experiments/precondition_power.py` · `arena/experiments/ollama_live.py` +
`game_r_formal_v1.OllamaSolver` · `arena/training/{gpu_authorisation,verified_eval}.py` +
`route_b_data` nesting/quality discipline · `releases/TRAINING_LANGUAGE_V0/` ·
`arena/provenance.py` + `arena/storage/{artifacts,hashes}.py` · `arena/evaluation/landscape.py` ·
`arena/compiler/{projection,validator}.py` · `arena/corpus/` (as a concept).

**REFACTOR — 13.** `arena/canonical/schema.py` · `arena/tasks/schema.py` + `curriculum.py` ·
`arena/languages/registry.py` · `arena/genome/{genes,seeds,schema}.py` (the gene vector) ·
`arena/players/architect.py` · `arena/league/{registry,selection,hall_of_fame}.py` ·
`arena/fitness/{metrics,gates,pareto}.py` · `arena/pipeline.py` + `cli.py` + `release.py` +
`reporting.py` · `arena/experiments/game_r_formal_v1.py` ·
`arena/experiments/game_r_precondition_founder_v1.py` · `arena/corpus/` wiring ·
`arena/storage/db.py` · the Refuter's production call site (`pipeline.py:304-310`).

**DEMOTE_TO_DIAGNOSTIC — 7.** `arena/tasks/generators/world_v0.py` ·
`arena/environments/precondition_ladder.py` · the V4/V5/V7 instrument machinery ·
`arena/evaluation/static.py` · the three real formal families *as solver-capability probes* ·
`research/` (41 dirs, 24,960 LOC) · the Astra bridge *as a source-projection parity study*.

**ARCHIVE — 12.** The 8 hand-written seed codecs (`arena/languages/*/__init__.py`) · Route B's
historical evidence · the V1/V2/V3 fitness verdicts · Phase-6 §11's selector claim ·
`formal_expression_depth` as a Game-R mechanism · the three real formal families *as Game-R arms* ·
the Astra bridge *as an arm set* · `arena/surrogate/` · `arena/fitness/{search_metrics,entropy,__init__}.py` ·
`arena/players/{curriculum,league_manager}.py` (as implementations) · the four
`arena/compiler/` facade files · the World-v0 `NEXT_ACTION` causal claims.

**MISSING — 7.** Inner trajectory arena · generation loop · language fitness record/history ·
multi-fidelity evaluator · language meta-genome · learned Architect · trained surrogate. (§5.)

**Repository totals:** `arena/` 36,398 LOC · `tests/` 12,562 · `research/` 24,960 · `releases/`
4,008. `.venv/bin/python -m pytest` → **1,132 passed, 1 skipped, 0 failed** **[measured here]**.
154 files under `artifacts/`, 143 of them JSON.

---

## 2. Reasoning by class

### 2.1 KEEP — runs unchanged in the meta-game

**The verifier (`arena/verifier/`, 741 LOC).** The `Verifier` protocol already declares
`verify_transition(transition) -> VerificationResult` (`base.py:44`), so the truth authority is
*already* transition-shaped even though nothing feeds it a chain. `NativeVerifier` is
representation-independent by construction: it reads `CanonicalState` fields, never bytes. Two
caveats that are bugs, not design faults, and are cheap to fix: `native.py:136` treats
`binder_kind == "free"` as "declared", so honestly setting `implicit`/`instance` triggers
`UNBOUND_VARIABLE`; and `native.py:231` restricts `action.target_ids` to `object_ids ∪ {"goal"}`,
which blocks external premise references (32.9% of real Lean states, §3.1).

**Semantic assurance (`arena/assurance/`, 1,574 LOC).** `semantic_mutations` produces
witness-backed mutants with an *expected* verdict, and `run_assurance_suite` reports explicit
denominators including `UNSUPPORTED`. This is the honest core of the semantic gate. `roundtrip_
property` (`properties.py:66`) is literally the meta-game's "a language may not change what a state
means" check.

**The Refuter (`arena/players/refuter.py`, 143 LOC).** Keep the class; the *wiring* is REFACTOR.
It minimises counterexamples (`minimize_subject`, `minimize_text`) and separates false-accept
(CRITICAL) from false-reject (ERROR). Its production call site is crippled: `pipeline.py:308-309`
passes `rendered_source=None, parser=None`, so `attack_parser` never runs, and it is invoked on
`world.tasks[0].trajectory.initial_state` — a single state. Also note `RefuterReport.false_accepts`
is partitioned by `severity == "CRITICAL"` (`refuter.py:140`) rather than by the `false_accept`
boolean computed at `:59`; this is currently harmless only because the grammar path is dead, and
`release.py` consumes `assurance.false_accepts` for the release gate.

**Model-view compiler (`arena/model_view/`, 671 LOC).** `ModelViewCompiler.validate`
(`compiler.py:117-136`) does three things the meta-game needs verbatim: recovers the canonical
mathematical hash from the rendered surface, re-derives the compiled view independently and
compares (so accounting cannot be fabricated), and checks the serialized projection against the
compiled record. `InformationAccounting` already records surface bytes, projection bytes, omitted
relations and repeated witnesses — a fitness vector's raw material.

**The genome phenotype (`arena/languages/phenotype.py`, 332 LOC).** This is the only executable
language in the repository whose emitted bytes are a function of its genes (§3.2). Everything in
the meta-game's language layer should be built on this class and nothing else.

**Phase-8 additions (`rendered_prompt_adversary.py` 1,620; `precondition_power.py` 1,573;
`ollama_live.py` 310).** These three are the highest-quality new code in the repo and are directly
meta-game reusable. The adversary scores on `(prompt, n_options)` and nothing else — it is the
shortcut gate the outer loop must run before believing any fitness. The power module computes exact
clustered McNemar power by FFT convolution and never calls a model — it is the sample-size
calculator for a generation's budget. `ollama_live` is a digest-frozen, injectable-transport Solver
adapter with exact token accounting.

**The formal donor adapter (`arena/environments/formal_structural.py`, 398 LOC).** It is the only
code path that turns real Lean into `CanonicalState`. It has **no dedicated test file** — the sole
test contact is `tests/environments/test_legal_transform.py:14` importing `relabel` — which is a
real gap given that V5 and V7 scored on its output.

**`TRAINING_LANGUAGE_V0` (4,008 LOC).** Keep, but understand what it is: a *self-contained release
package* that nothing in `arena/` imports. Its importers are exclusively `tests/releases/*`. It
is the only artefact in the repo that natively carries the five REQUIRED canonical-vNext gaps, so
it is the leading candidate for the meta-game's Σ — not a language arm.

**Provenance, cache and artifact store.** `ArtifactStore` (`arena/storage/artifacts.py`, 37 LOC) is
used by twelve experiment files and is the cheapest thing in the repo per unit of value.
`arena/provenance.py` is used outside the CLI island (by `formal_structural`, `legal_transform`,
`corpus/*`).

**`arena/evaluation/landscape.py` and `arena/compiler/projection.py`.** Paired statistics and
leak-scrubbing observation projection respectively; both are imported directly by path across the
experiment world.

### 2.2 REFACTOR — right concept, wrong interface

**The canonical layer (row 1).** `CanonicalTransition` and `CanonicalTrajectory` are declared but
degenerate: they are constructed at exactly one site (`world_v0.py:507`) with a 1-tuple literal
(`:511`), and `research/codex_audit/scripts/world_v0_baselines.py:70` *asserts* `len(transitions)
== 1` as an invariant. The type is right; nothing has ever exercised it. Separately, the schema
cannot carry real Lean (§3.1). The refactor is two-part: (a) populate trajectories, (b) add a
backend-native envelope rather than force real Lean through `arena-canonical-v0.1.0`.

**The language genome (row 11).** Fourteen declared families, nine that reach the bytes, five that
are decorative. `alphabet` (0/2 variants change a byte), `composition` (0/3), `obligations` (0/3),
`evidence` (0/2), `error_locality` (0/3) **[measured here]**. `binders` is live (3/3) *only* on
states that actually have bindings — 156 of 676 world-v0 tasks. `actions` never touches
`render(state)` but produces 4 distinct outputs from `render_action_choice` **[measured here]**.
A meta-genome must either delete the inert families or give them phenotype effect; carrying
inert genes inflates the search space by 13 of 44 single-gene moves with zero information.

**The language registry (`arena/languages/registry.py:52-62`).** `SEED_LANGUAGES` is a hard-coded
8-tuple of hand-written instances. This is *the* mechanical reason the outer loop cannot close:
`pipeline.evaluate()` calls `get_language(candidate_id)` (`pipeline.py:210`) and raises "candidate
has no executable renderer/parser; it cannot enter evaluation" for anything not in that tuple. A
genome-addressed registry that instantiates `GenomePhenotypeLanguage(genome)` on demand removes the
blockage in a few lines.

**League / archive (row 13).** The data model is better than the mission needs (multi-axis, no
scalar Elo, Pareto status, Hall-of-Fame suite hashing). What is missing is *any producer*:
`artifacts/matches/league-registry.json` has 8 candidates, 0 observations, 0 matches;
`record_observation`/`record_match`/`_recompute` (`registry.py:152-188`) have never fired in a real
run; `LeagueMatch` has no runtime constructor; and `arena/players/league_manager.py` — the façade
`GOAL.md` §10 names as owning "population / archive / lineage / Hall of Fame / successive halving /
promotion / retirement / resource allocation" — is a 21-line stub with **zero importers repo-wide**.

**The tournament harness (row 25).** `assert_arena_parity` is the best code in the repository for
the meta-game's purposes and should be lifted almost verbatim. But `TaskItem` (`:319`) declares
`canonical_state`, `options`, `correct_index` and nothing else — no successor state, no reward, no
termination. `Solver` (`:948`) is `generate(prompt) -> SolverResponse`: stateless by type.
`run_mechanism` (`:1265-1298`) is a flat double comprehension over `(item, genome)`. Extending this
to a trajectory means a new `TrajectoryItem`/`TrajectorySolver` pair, not an edit.

**Pipeline / CLI (row 17), fitness metrics/gates/pareto (row 14), corpus (row 20),
`storage/db.py`.** All correct in isolation, all wired to the wrong loop or to no loop.

### 2.3 DEMOTE_TO_DIAGNOSTIC — useful instrument, not the mission

The V1–V7 micro-probe stack and its environments. Concretely: `world_v0` (2), the precondition
ladder (22), the V4/V5/V7 instruments (24), `evaluation/static.py` (16), the three real formal
families *as solver-capability probes* (23), and the whole of `research/` (34).

The justification is uniform and measured: **maximum horizon 1, and 2 options enforced by the type
system.** Six independent modules declare a fixed 2-tuple:
`precondition_ladder.py:479`, `fitness_v3.py:103`, `fitness_v4.py:221`, `fitness_v5.py:297`
(`tuple[CanonicalAction, CanonicalAction]`), `fitness_v2.py:148`
(`tuple[CanonicalExpression, CanonicalExpression]`), `rewrite_direction.py:581`
(`tuple[str, str]`). A third option is not representable without a type change. The one
generic declaration is the harness's own `MaterialisedItem.options: tuple[CanonicalAction, ...]`
(`game_r_formal_v1.py:382`), which supports 2–26 — and every wired environment supplies 2. The parsers hard-enforce it (`fitness_v1.py:363-370`,
`fitness_v3.py:559-567`, `fitness_v4.py:1185-1193` accept only `A`/`B`). The only exception is
`premise_selection.py:601-616`, which is genuinely 6- and 8-way — and still horizon 1.

These remain valuable. `precondition_conjunction` is the one mechanism that is balanced *by
construction* rather than by audit, and `rendered_prompt_adversary` + `precondition_power` make it
the only defensible local assay in the repo. Demotion means: keep running it as a fast, cheap
sanity instrument on a candidate language; never mistake its number for the mission's fitness.

`evaluation/static.py` deserves a specific note: it scores **bytes**, not a Solver. The README's
`L5_COMPACT_SYMBOLIC` frontier is a *byte-cost* frontier and the README already says so. Under the
meta-game this is a cheap fidelity-0 pre-filter, nothing more.

### 2.4 ARCHIVE — preserve, do not build on

1. **The 8 hand-written seed codecs** (`arena/languages/*/__init__.py`, 449 LOC). Measured: 0 of 44
   one-gene mutations change one byte, for every one of the 8. They are *labelled* with a genome
   (`from arena.genome.seeds import L1_CURRENT_HML`, then `genome = L1_CURRENT_HML`) but no
   `_encode_payload` or `_decode_payload` in any of the 8 reads `self.genome`. They round-trip
   losslessly and are historically the "8 founders", but as *evolvable* languages they are inert.
2. **Route B's historical evidence.** `docs/PROJECT_STATUS.md` records it as VOID: `verified` was a
   three-key presence check reading 1.000 everywhere; `stratified_split`'s seed is inert; World-v0
   `NEXT_ACTION` is model-free solvable **676/676** (`artifacts/reports/next_action_leakage.json`).
3. **The V3 fitness verdict** (input truncation) and **the V4 verdict** (64-token cap + a
   representation-specific character guard, 89 malformed rows in 348). Both are recorded as
   instrument failures.
4. **Phase-6 §11's claim** that a selector fix alone would have qualified `formal_expression_depth`
   — refuted by V7 measuring 0.8333 at L2 against V5's own frozen `shortcut_rule_max = 0.75`.
5. **`formal_expression_depth` as a Game-R mechanism.** Solvable at **1.000** by bracket-depth
   counting on the rendered prompt on all eight surfaces; under any bracketed serialisation the
   optimal strategy is representation-*invariant*. Unrescuable.
6. **The three real formal families as Game-R arms.** They emit pre-rendered Lean strings and
   contain zero `CanonicalState`; eight arms would receive byte-identical input.
7. **The Astra bridge as an arm set.** Fails the ≥40-char cross-arm span falsifier 300/300 × 5/5.
8. **`arena/surrogate/`** (382 LOC), **`arena/fitness/search_metrics.py`** (30) and
   **`entropy.py`** (5), **`arena/players/curriculum.py`** (26) and **`league_manager.py`** (21),
   and the four `arena/compiler/` facade files (68). Zero non-test importers between them.

The **World-v0 causal claim** deserves separate emphasis. It is not merely superseded; it is
*measured to be model-free solvable at 676/676 whole-target exact*, held-out 96/96, with 7 of 8
target fields fully mechanical, unrepaired by identifier obfuscation. Any historical fitness number
derived from `WORLD_V0_NEXT_ACTION` is uninformative about mathematical learning.

---

## 3. The five questions, answered with evidence

### 3.1 Can the canonical schema carry real Lean states? **No. Verified and quantified.**

`artifacts/reports/canonical_vnext_gap_verification.json`, read directly:

| Quantity | Value |
|---|---:|
| States analysed | **368** (184 records × state_before/state_after) |
| **Lossless** | **0** |
| `LOSSY_STRUCTURAL` | 292 (79.3%) |
| `UNMAPPABLE` | 76 (20.7%) |
| Records with ≥1 unmappable state | 66 / 184 (35.9%) |
| `native_verifier_issue_codes_raised` | **`{}` — empty** |

Sample provenance: `/Users/moheet/Documents/ChatGPT/HML_V3`,
`data/corpus/lean_runtime_v2_full.canonical.part-*.jsonl.gz`, 1,150 records in universe, 918
eligible, 232 skipped as sealed, every 5th eligible record → 184 sampled.

Per-state failure classes (top): `DEPENDENT_TYPE_FLATTENED` 304 (82.6%), `GOAL_IDENTITY_DROPPED`
304 (82.6%), `METAVARIABLE_CONTEXT_DROPPED` 304 (82.6%), `UNIVERSE_ARGUMENTS_ON_SYMBOL` 304
(82.6%), `NONEXPLICIT_BINDER_KIND` 286 (77.7%), `UNIVERSE_LEVEL_NONTRIVIAL` 273 (74.2%),
`MVAR_SUBSTITUTION_MAP_DROPPED` 252 (68.5%), `LOCAL_INSTANCES_DROPPED` 210 (57.1%),
`METAVARIABLE_ASSIGNMENT_DROPPED` 164 (44.6%), `PREMISE_REFS_UNPLACEABLE` 121 (32.9%),
`ZERO_GOAL_MANDATORY_SLOT` 64 (17.4%), `MULTI_GOAL_SINGLE_SLOT` 42 (11.4%).

Goal-count distribution over the 368 states: **0 goals in 64**, 1 in 262, 2 in 18, 3 in 15, 4 in 5,
5 in 2, 6 in 1, 7 in 1. `CanonicalState.goal` is a single mandatory field (`schema.py:196-212`), so
17.4% of real states are hard-unmappable on that ground alone.

Aggregate structural counts: 5,071 local-context entries of which **4,288 (84.6%) have compound
types**; 1,375 metavariables (992 assigned); 34,781 symbol occurrences carrying universe arguments.

Two facts decide the architecture:

- **A version bump re-hashes the project.** `mathematical_hash` (`schema.py:281-283`) covers
  everything except `state_id` and `execution_metadata` — *including* `schema_version`. Every
  stored state hash in every artifact changes on any `SCHEMA_VERSION` edit.
- **`phenotype.py:78-99` builds compressed/symbolic role labels by index into `_KNOWN_KEYS`.**
  Inserting one field renames every candidate language's serialization.

**Decision this supports:** the trajectory arena must NOT reuse `arena-canonical-v0.1.0` as its
import format for real backends. It needs a **backend-native envelope** — either
`releases/TRAINING_LANGUAGE_V0` (which already carries all five REQUIRED gaps natively) or a
backend-tagged wrapper — with the canonical layer retained for the Arena's own generated worlds,
where it is lossless by construction.

**The most dangerous finding, restated:** all 304 constructed states passed the wire validator
*and* `NativeVerifier` with **zero issue codes**, because `lean.*` operations match none of its
rules. A future session importing formal data and seeing a clean verifier result would be
concluding nothing at all.

### 3.2 Is the language layer genome-driven end to end? **Only for one class. The Route-B defect is NOT confined to `route_b_data.py`.**

Probe: for each language, hold `candidate_id` and `parent_ids` **fixed**, mutate each of the 14
gene families to every other legal value (44 single-gene variants per genome), re-render the same
`CanonicalState` from world-v0, and compare bytes and round-trip. **[measured here]**

| Language class | Variants | Bytes changed | Round-trip failures |
|---|---:|---:|---:|
| `L0_STRUCTURED_ENGLISH` … `L7_HYBRID_ROLE_LABELLED` (all 8 hand-written codecs) | 44 each | **0 each** | 0 |
| `GenomePhenotypeLanguage(L0..L7)` | 44 each | **22–24 each** | **0 each** |

Per-gene byte effect for `GenomePhenotypeLanguage` (identical across all 8 seeds except
`token_policy` for L5, and `redundancy`):

`grammar` 7/7 · `morphology` 4/4 · `types` 3/3 · `state` 3/3 · `serialization` 3/3 ·
`token_policy` 2/3 (0/3 for L5) · `redundancy` 1–2/2 · `binders` 0/3 **on a state with no
bindings, 3/3 on a state with bindings** · `alphabet` 0/2 · `composition` 0/3 · `actions` 0/3 on
`render(state)` but **4 distinct outputs from `render_action_choice`** · `obligations` 0/3 ·
`evidence` 0/2 · `error_locality` 0/3.

So: **9 of 14 gene families reach the bytes; 5 are inert** (`alphabet`, `composition`,
`obligations`, `evidence`, `error_locality`). This exactly matches the repository's own
`artifacts/reports/game-r-mutant-audit.json`, whose `phenotype_genes` field lists 9 families, and
`docs/PROJECT_STATUS.md`, which records "Five of fourteen gene families are inert."

The mechanism of the seed-codec defect, in source: every one of the 8 packages does
`from arena.genome.seeds import L<N>_...` and then `genome = L<N>_...` as a **class attribute**,
and no `_encode_payload`/`_decode_payload` in any of them references `self.genome`. Examples:
`arena/languages/hml/__init__.py:25-27` uses only `STATE_FIELD_ORDER` + `canonical_json`;
`arena/languages/symbolic/__init__.py:28-30` uses a frozen 15-letter alias table declared at
`:14-20`; `arena/languages/graph/__init__.py:35-63` is a fixed node/edge walk.
`grep -rn "self\.genome" arena/languages/*/__init__.py` returns **nothing**.

A methodological warning for anyone re-running this: `arena/languages/json_ast/__init__.py:19`
embeds `self.candidate_id` in its envelope. A naïve sweep that renames the candidate while mutating
a gene reports 44/44 "changed" for JSON-AST — a **false positive** caused by the *name*, not the
gene. Holding `candidate_id` fixed gives 0/44, as for the other seven.

**Conclusion:** the owner's hypothesis under-states the problem. `arena/training/route_b_data.py`
does not define a codec at all — it imports `LANGUAGE_REGISTRY` (`route_b_data.py:44`, used at `:374`, `:389`). The defect
lives in `arena/languages/*/__init__.py`, i.e. in the **eight seed representations themselves**,
and is inherited by every consumer of `LANGUAGE_REGISTRY`: `pipeline.py`, `cli.py`,
`fitness_v1.py`, `route_b_data.py`, `render_dataset.py`.

The repair already exists and is already enforced in the newest code:
`game_r_formal_v1.founder_genome` (`:535-545`) builds a `ModelViewGenome` around
`SEED_GENOME_BY_ID[surface_id]` and renders through `GenomePhenotypeLanguage`; and
`assert_arena_parity` (`:625`) **refuses byte-identical arms** (`:696-701`) — a guarantee written,
per its own docstring, precisely because of the Route-B defect.

### 3.3 Does anything model a MULTI-STEP trajectory? **No. Maximum horizon is 1, everywhere.**

`CanonicalTrajectory` is constructed at exactly **one** site in the repository:
`arena/tasks/generators/world_v0.py:507`, and the `transitions` argument is the 1-tuple literal
`(transition,)` at `:511`. `proof_length=1` is hardcoded at `:540`.

**[measured here]** `generate_tasks(total=676, seed=0)` over the full Gold world:

| Quantity | Distribution |
|---|---|
| transitions per trajectory | **{1: 676}** |
| `legal_actions` | {1: 676} |
| `plausible_invalid_actions` | {1: 676} |
| bindings in `initial_state` | {0: 520, 1: 156} |
| obligations | {0: 624, 1: 52} |
| evidence_dependencies | {0: 624, 2: 52} |
| quality | GOLD 520 · SILVER 104 · REJECT 52 |
| domains | 13 domains × 52 each |

Every other `CanonicalTransition` construction is a standalone single-transition probe, never
chained: `world_v0.py:495` (`transition_stub` → `verify_transition`),
`arena/training/verified_eval.py:392` (`state_before=item.state, state_after=item.state`, a
self-loop legality probe), `arena/assurance/mutations.py:410` and `:435` (two refuter cases).
Every consumer indexes position 0 only (`pipeline.py:103,112`; `research/leakage/measure.py:36`;
`research/codex_audit/scripts/route_b_audit.py:60,63,69,115`; `world_v0_baselines.py:32,37,44`).
`research/codex_audit/scripts/world_v0_baselines.py:70` **asserts** it:
`checks["one_transition"].append(len(task.trajectory.transitions) == 1)`.

Horizon by environment (all confirmed single-step):

| Environment | LOC | Max horizon | #options | Persistent state ≥2 decisions |
|---|---:|---:|---|---|
| `formal_structural.py` | 398 | 1 | emits states only | No |
| `legal_transform.py` | 1315 | 1 | binary VALID/INVALID *label* | No |
| `precondition_ladder.py` | 1132 | 1 | 2 (typed tuple, `:479`) | No |
| `premise_selection.py` | 1032 | 1 | **6 or 8** (`:601-616`) | No |
| `rewrite_direction.py` | 1020 | 1 | 2 (`:581`) | No |
| `world_v0.py` | 613 | 1 | 2 (`:536-537`) | No |
| `fitness_v1…v7` | 8328 | 1 | 2 | No |
| `game_r_formal_v1.py` | 1773 | 1 | 2–26 supported, 2 wired | No |
| `game_r_precondition_founder_v1.py` | 1762 | 1 | 2 | No |

Mechanism-level proof, not inference:

- `game_r_formal_v1.py:948-961` — the `Solver` Protocol's only method is
  `generate(prompt: str, *, schema, decoding) -> SolverResponse`. A bare string in, one answer out.
- `game_r_formal_v1.py:1265-1298` — `run_mechanism` is a flat comprehension
  `for item in items for genome in genomes`; one prompt, one `generate`, one scored row.
- `game_r_formal_v1.py:1031-1040` — `OllamaSolver.generate` posts `{"model", "prompt", "stream": False, "format", "options"}`
  and never sends Ollama's `context` array or a `messages` list, so even the KV cache carries no
  logical state.
- `fitness_v7.py:211` — `SolverCall = Callable[[V5Probe, str], dict]`: stateless by type.
- No `def step(...)` gym-style method exists anywhere in the repo. `horizon` appears once,
  inside the word "horizontal" in a corpus excerpt. `multi_step` appears twice, both in a data
  artifact recording that the corpus is **not** linked into multi-step chains
  (`artifacts/corpus/user_reasoning_chain_inventory.json:636,638`).

The only objects that survive between rows are a call counter (`CallBudget`,
`game_r_formal_v1.py:1068`), a response memo (`ResponseCache`, `:820`) and `StubSolver.calls`. None
feeds back into any decision.

### 3.4 State of `arena/league/`, `arena/fitness/`, `arena/surrogate/`

There are two disjoint worlds in this package. `arena/experiments/` (17 files, 16,194 LOC, where
all the real measurement lives) imports **zero** of `arena.league`, `arena.fitness`,
`arena.surrogate`, `arena.players`, `arena.pipeline`, `arena.cli`, `arena.reporting`,
`arena.release`. The experiment world talks only to `canonical.schema`, `storage.artifacts`,
`model_view.*`, `languages.phenotype`, `genome.seeds`, `evaluation.landscape`,
`compiler.projection`. Everything else is a **pipeline island** reachable only through the `arena`
console script and one 27-line integration test.

| Module | LOC | Non-test importers | Tests | Verdict |
|---|---:|---|---|---|
| `league/registry.py` | 262 | `pipeline.py:17`, `league_manager.py:9`, `hall_of_fame.py:10`, `selection.py:8` | `tests/league/test_registry.py` | Live in the island; **rating machinery never fired**: `artifacts/matches/league-registry.json` = 8 candidates, 0 observations, 0 matches |
| `league/selection.py` | 61 | `pipeline.py:18`, `league_manager.py:10` | yes | LIVE (`pipeline.py:266`) |
| `league/hall_of_fame.py` | 63 | `pipeline.py:16` | yes | `HallOfFameSuite` LIVE (`pipeline.py:274`); the `HallOfFame` class is dead |
| `league/matches.py` | 38 | `registry.py:20`, `league_manager.py:8` | yes | **No runtime producer** — no `LeagueMatch` is ever constructed outside tests |
| `league/__init__.py` | 15 | none | — | Dead façade |
| `players/league_manager.py` | 21 | **zero repo-wide** | none | **DEAD** — and it is the component `GOAL.md` §10 names as owning the outer loop |
| `fitness/metrics.py` | 260 | `pipeline:12`, `reporting:11`, `registry:19`, `static:22`, `gates:8`, `pareto:9` | yes | LIVE, partially (`MachineMetrics`, `machine_metrics_from_trials`, `MetricBundle` have zero callers) |
| `fitness/gates.py` | 146 | `evaluation/static.py:17` only | yes | LIVE via `evaluate_lexicographic`; `evaluate_gate_zero`/`evaluate_coverage_gate` test-only |
| `fitness/pareto.py` | 133 | `pipeline:13`, `reporting:12`, `selection:7`, `league_manager:7` | yes | **LIVE outside tests** — `pipeline.py:261-266` → `rank_registry` → `pareto_fronts` (`selection.py:37`); `"pareto_status": "PARETO_RANK_1"` is on disk. `pareto_front` (singular) has no caller |
| `fitness/entropy.py` | 5 | none | none | DEAD re-export shim |
| `fitness/search_metrics.py` | 30 | **none** | **none** | DEAD |
| `surrogate/*` | 382 | **none** | `tests/surrogate/test_surrogate.py` (43) | **DEAD.** Its only data is 6 hand-written literals (`test_surrogate.py:8-9`); the sklearn path is never reached (tests pass `prefer_sklearn=False` and assert the sklearn path is declined) |

Answering the sub-question directly: **`arena/fitness/pareto.py` IS used outside tests** (four
importers, output on disk) — this contradicts the implicit framing that the fitness package is
dead. **`arena/surrogate/` is never trained on real data and is called by nothing.**

### 3.5 What already implements parts of the OUTER loop?

| Outer-loop stage | Exists? | Where | Gap |
|---|---|---|---|
| Population | **Partial** | `fitness_v1.py:115` `materialize_population()` — "120 deterministic one-gene children", round-robin across 8 parents × gene families | Generation **1 only**, frozen; `TARGET_POPULATION` is a constant |
| Mutation operator | **Yes** | `genome/mutation.py` (439 LOC): `MutationOperator` (14 kinds), `MutationProposal.build`, `apply_mutation` (`:407`), `MutationRecord`, `MutationHistory`; `players/architect.py:50-95` enumerates every legal one-gene neighbour under a sha256-seeded shuffle | Pure single-genome transform; no loop, no fitness feedback |
| Crossover | **Yes** | `genome/crossover.py` (130 LOC) | Not called by any loop |
| Semantic gate | **Yes, and good** | `game_r_formal_v1.assert_arena_parity` (`:625`); `game_r_mutant_audit.py` 5-check gate; `model_view/compiler.py:validate`; `assurance/properties.roundtrip_property` | Single-state; not applied to a generation |
| Archive | **Partial** | `league/registry.py` (multi-axis ratings, Pareto status, persistence), `hall_of_fame.py` (frozen suite hashing) | 0 observations ever recorded; no lineage query; `parent_ids` (`registry.py:63`) is stored and never read for selection |
| Selection | **Yes** | `league/selection.py:rank_registry` (`:11`) and `select_frontier_diverse` (`:46`, crowding distance) | Ranks a registry that has no data |
| Successive halving | **Yes — once** | `arena/training/gpu_matched_runner.py:33` `HALVING_RULE` with `minimum_margin: 0.06`, stage A (all 5 arms, eliminate if trailing leader by >0.06) → stage B (top 3) → stage C (top 2 on a fresh slice never used for selection) | Standalone `main()`, requires CUDA, imported by nothing but two helper functions in `tests/training/test_verified_eval.py:23-24` |
| Multi-fidelity budget | **No** | `pipeline.evaluate(tier)` accepts 0 or 1 and runs the **identical** `evaluate_static` for both (`pipeline.py:205-206,222,228`); `tier` is a filename label | `arena/fitness/gates.py:14 ELIMINATED` is a per-candidate pass/fail, not a competitive cull |
| Generation loop | **No** | grep for `for generation`/`generation_index`/`num_generations` across `arena/` → **zero hits** | — |
| Fitness history | **No** | `MutationHistory` records *proposals*, not scores | — |
| Learned Architect | **No** | `architect.py:48` `name = "deterministic-neighbour-architect-v0"`; `_OPERATOR_BY_GENE` is a hardcoded 14-entry dict; hypotheses are f-string templates (`:80-81`) | Never receives an evaluation result |

**The loop is severed at exactly one edge, and it is a two-line edge.** `pipeline.mutate()` writes
mutant genomes with status `"GENOME_VALIDATED_RENDERER_PENDING"` (`pipeline.py:180`);
`pipeline.evaluate()` does `get_language(candidate_id)` and raises *"candidate has no executable
renderer/parser; it cannot enter evaluation"* (`pipeline.py:210-214`); `run_league()` iterates
`seed_languages()` only (`pipeline.py:238`). Confirmed on disk: `artifacts/candidates/M-*/`
contains `genome.json` **only** (20 such directories), while `artifacts/candidates/L1_CURRENT_HML/`
has both `genome.json` and `evaluation-tier-1.json`. **20+ mutants, zero evaluations.**

Since `GenomePhenotypeLanguage(genome)` will render any valid genome, the renderer that
`get_language` cannot find already exists. The blockage is the hard-coded registry, not the codec.

---

### 3.6 External data and donor corpora — all present, and larger than the code

Every external path referenced anywhere in `arena/`, `research/`, `releases/` or `docs/` was tested
with `du -sh` / `find -type f | wc -l`. **30 of 30 exist. Zero missing.**

| Asset | Referenced from | Size / count |
|---|---|---|
| `HML_V3` donor root | `formal_structural.py:49` (the only opened absolute path in `arena/`) | **124 GB**, 71,694 files |
| `lean_runtime_v2_full.canonical.part-{000..004}.jsonl.gz` | `formal_structural.py:50` | 5 shards, 20.5 MB gz, **1,150 records** |
| `sealed_final_v2.part-000.jsonl.gz` | `formal_structural.py:51` | 1 shard, 3.75 MB gz, **232 records / 126 source files** — read for *source-file names only* |
| Built mathlib4 @ `29dcec07…` | `legal_transform.py:225-226` (a replay-recipe string literal, not an opened path) | **18 GB**, 58,867 files |
| Source-only mathlib4 checkout @ same commit | docs | 349 MB, 6,046 files |
| LeanDojo Benchmark 4 root | `research/environments/common.py:17-20`, `env_premise`, `astra/source_adapter.py:20` | **795 MB**, 17 files |
| `leandojo/steps.jsonl` | `GAME_R_FORMAL_ARENA_V1_SPEC.md §3` | 258 MB — 259,580 rows (train 250,814 / val 4,260 / test 4,506) |
| `random/{val,test}.json`, `novel_premises/{val,test}.json` | `research/astra/artifacts/source_seal.json` | sealed by hash — **but all four recorded `HISTORICALLY_EXPOSED`; none is certified hidden** |

Two consequences for the meta-game.

**(a) The mathlib ambiguity is resolved and matters.** Two checkouts of the same commit exist: the
`runtime_work` one is built (18 GB, 58,867 files), the `checkouts` one is source-only (349 MB) —
sizes measured here; the `.olean` counts (5,680 vs 38) and the **32/100 replay yield** are quoted
from `docs/CANONICAL_VNEXT_PILOT.md` §7b and were not re-derived by this audit. Any design that
needs kernel adjudication must name `runtime_work` explicitly and budget that yield.

**(b) The single-goal filter is how the canonical layer survives real Lean at all.**
`formal_structural.py:291-293` is:

```python
goals = record.get("state_before", {}).get("goals", [])
if len(goals) != 1:
    continue
```

**[measured here]** — streaming all five donor shards (the sealed shard was never opened) and
counting `state_before` goals over all 1,150 records:

| `len(state_before.goals)` | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| records | **892** | 157 | 65 | 22 | 8 | 3 | 1 | 1 | 1 |

The filter therefore keeps **892 of 1,150 records (77.6%) and discards 258 (22.4%)** before anything
reaches `CanonicalState`. That is not a bug; it is the price the current Σ charges. But it means the
"Lean-derived probe bank" V5 and V7 scored on is a *filtered* population selected for compatibility
with a schema limitation, and no measurement on it generalises to the discarded 22.4%.

**(b2) The donor corpus cannot be chained at all — this is the decisive fact for M1.**
**[measured here]**, over the same 1,150 records:

| Quantity | Value |
|---|---:|
| Records | 1,150 |
| Distinct theorems | 738 |
| Steps per theorem | 1:515 · 2:134 · 3:47 · 4:24 · 5:4 · 6:7 · 7:1 · 8:2 · 9:1 · 10:2 · 16:1 |
| Theorems with ≥2 steps | 223 |
| Max steps for one theorem | 16 |
| **`state_after` ids that appear as some `state_before` id** | **0 of 1,150** |

Zero joins. The donor is an *elaboration-time capture*, exactly as
`formal_structural.py:54-58 DONOR_CAVEATS` says ("elaboration-time capture, not tactic replay; the
donor attestation gate reports passed=false"). Multiple steps of one theorem exist as independent
records, but no record's post-state is any record's pre-state, so the corpus **cannot be assembled
into a trajectory by state identity**. Any trajectory arena built on `formal_structural`'s donor
would have to re-derive chaining from source positions, or replay in Lean.

**(c) `research/operations/paths.py:47-52` writes into a stale sibling worktree**
(`phase-6-parallel-setup-9c6068`) and `:55-59` points at a dead scratchpad UUID. Any re-run of
`research/operations/` from this worktree would fail or write into the wrong tree.

---

## 4. WHERE THE OWNER'S HYPOTHESIS IS WRONG

The hypothesis is mostly correct. These are the places the evidence contradicts or materially
sharpens it.

**W1 — "KEEP seed languages" is wrong; they are ARCHIVE.** The hypothesis lists *seed languages*
under KEEP. Measured: all 8 hand-written codecs change **0 of 44** bytes under one-gene mutation.
What deserves KEEP is the *seed genome vector* (`arena/genome/seeds.py`, 186 LOC, 8 × 14 gene
values) plus `GenomePhenotypeLanguage`. The eight `arena/languages/*/__init__.py` packages should
be archived as historical surfaces, not carried into the meta-game as arms.

**W2 — the Route-B codec defect is NOT confined to `route_b_data.py`.** The hypothesis asks whether
it is. It is not: `route_b_data.py` defines no codec (it imports `LANGUAGE_REGISTRY` at `:44`). The
defect is in the seed language layer and propagates to `pipeline.py`, `cli.py`, `fitness_v1.py`,
`render_dataset.py` and `route_b_data.py` alike.

**W3 — "KEEP language compiler concepts" understates it: the compiler and the parity gate are the
strongest assets in the repository.** `ModelViewCompiler.validate` plus `assert_arena_parity`
already implement the meta-game's semantic gate, including the byte-identical-arm refusal. These
should be promoted to first-class infrastructure, not merely kept.

**W4 — "REFACTOR league" overstates what is there.** The league is not an under-powered archive; it
is an archive with **zero recorded observations** and no producer. `LeagueMatch` is never
constructed at runtime; `league_manager.py` has zero importers. Treating it as REFACTOR is right
only if "refactor" is understood to include "write the producer that has never existed".

**W5 — "REFACTOR fitness" is half right; part of `arena/fitness/` is ARCHIVE.**
`fitness/pareto.py`, `metrics.py` and `gates.py` are live and refactorable. `fitness/entropy.py`
(5 LOC), `fitness/search_metrics.py` (30 LOC) and `fitness/__init__.py` (27 LOC) have zero
importers and, for `search_metrics.py`, zero tests.

**W6 — "MISSING: multi-fidelity evaluator" is not fully missing.** A real, preregistered successive-
halving rule exists at `arena/training/gpu_matched_runner.py:33` with three stages, an explicit
`minimum_margin: 0.06`, tie-carrying, and a stage-C slice never used for selection. It is unwired
and CUDA-gated, but the *design* does not need inventing. Similarly, `precondition_power.py`
(1,573 LOC) already computes the exact clustered power that a multi-fidelity budget allocator
needs.

**W7 — "MISSING: mutation operator" is wrong.** `arena/genome/mutation.py` (439 LOC),
`crossover.py` (130 LOC) and `players/architect.py` (98 LOC) implement proposal, validation,
application, hashing and history. What is missing is the *loop that calls them twice*.

**W8 — "DEMOTE precondition_conjunction" needs a caveat.** It is the only mechanism in the repo
that is **balanced by construction and verified in source** — `_premise_family` builds `objects`
and `propositions` once and passes them unchanged to all three arms. Demote it as a *mission
target*, but it should remain the meta-game's standard fast fidelity-0 assay, because nothing else
in the repo has that property.

**W9 — "ARCHIVE World-v0 causal claims" is right but too weak.** It is not that the claims are
superseded; `WORLD_V0_NEXT_ACTION` is **model-free solvable at 676/676 whole-target exact**
(`artifacts/reports/next_action_leakage.json`), 96/96 held out, 0.8195 with zero arithmetic, 7 of 8
target fields fully mechanical, unrepaired by identifier obfuscation. The task is not a hard task
that was measured badly; it is not a task.

**W10 — the canonical layer needs more than a REFACTOR label.** The hypothesis puts "canonical
trajectory layer" under REFACTOR. That is right for the *trajectory* types, but the *state* type
carries a second, separable problem: 0/368 real Lean states map losslessly, and any fix re-hashes
every artifact in the project because `schema_version` is inside `mathematical_hash`
(`schema.py:281-283`). These are two decisions, not one.

**W11 — "KEEP source corpora" needs a boundary.** The donor corpus and LeanDojo trace are real and
local. But the three environments built from them (`premise_selection`, `rewrite_direction`,
`legal_transform`, 3,367 LOC, 1,292 LOC of tests) emit pre-rendered Lean strings and therefore
**cannot be language arms at all**. Keep the corpora; archive those three as Game-R substrates.

**W12 — a gap the hypothesis does not mention: test coverage is not where the risk is.**
`arena/environments/formal_structural.py` (398 LOC) — the probe bank V5 and V7 actually scored —
has **no dedicated test file**. `arena/experiments/fitness_v5.py` (1,206 LOC) has **no test file**
(`tests/experiments/test_fitness_v5.py` does not exist), while V7, which imports 15+ symbols from
it, has 788 lines of tests.

**W13 — "KEEP source corpora" is right, but the probe bank they feed is a filtered population.**
`formal_structural.py:291-293` discards every record whose `state_before` goal list length is not
exactly 1 — **258 of 1,150 donor records (22.4%)** **[measured here]**. Every V5/V7 number is
conditioned on that filter, and the hypothesis does not account for it.

**W14 — "MISSING: language fitness history" is right, but the schema for it already exists and is
empty, which is a different problem from absent.** `MatchObservation` (`league/matches.py:10`),
`AxisRating` and `objective_metrics` (`league/registry.py:33,63`) are a complete, tested data model
with **zero recorded observations**. The missing piece is a 30-line adapter from a scored row set to
`record_match`, not a new subsystem.

**W15 — sealed splits are not sealed in the sense the word implies.**
`research/astra/artifacts/source_seal.json` byte-hashes the four LeanDojo val/test files, but
records all four as `HISTORICALLY_EXPOSED` — "none is certified hidden". Combined with
`docs/PROJECT_STATUS.md`'s record that `novel_premises/{val,test}` were parsed 5h16m *before* the
seal and that the shipped distractor tiers are the measured policies, the premise-selection
promotion pool is spent. Any OOD claim from these splits is unavailable, and the hypothesis's KEEP
of "source corpora" should carry that boundary explicitly.

---

## 5. MISSING — ranked by blocking-ness

### M1. The inner trajectory arena (horizon > 1) — **absolute blocker**

Nothing in the repository takes more than one decision. There is no `step`, no `reset`, no
successor state, no episode return, no termination predicate, and the harness's `TaskItem`
(`game_r_formal_v1.py:319`) and `Solver` (`:948`) are single-step *by type*. Until this exists,
"long-horizon mathematical reasoning" cannot be measured at all, and every fitness number is a
statement about one lookup.

*Closest existing thing:* `CanonicalTrajectory` (`schema.py:322`) — the right type, populated once,
with one transition; and `game_r_formal_v1.TaskEnvironment` (`:360`) — the right protocol shape
(`items(*, families, levels)`) but returning independent items.

*Cheapest credible path:* add a `TrajectoryItem` protocol alongside `TaskItem` carrying
`initial_state`, a `legal_actions(state)` callable, and a verifier-owned `step(state, action) ->
(state', VerificationResult, terminal)`; and a `TrajectorySolver` protocol whose `act(view,
history)` returns one action. Then implement **one** environment against it.

**The corpus choice is already decided by measurement, and it is not the one it looks like.**
`formal_structural`'s HML_V3 donor **cannot be chained**: 0 of 1,150 `state_after` ids appear as any
`state_before` id **[measured here]**, because it is an elaboration-time capture, not tactic replay
(`formal_structural.py:54-58`). The chainable source is the LeanDojo Benchmark 4 trace, where
`state_after` and `state_before` are recorded per traced tactic. A concurrent Phase-9 data audit in
this worktree (`research/phase9/data_audit/{steps_horizons,leandojo_chained}.json`, produced by
another session and **not re-derived by this audit**) records, over 250,814 train steps in 59,557
proofs: mean horizon 4.21, median 2, max 128; **38,755 proofs of length ≥2, 25,911 ≥3, 15,275 ≥5,
5,892 ≥10**; and, restricting to proofs whose adjacent `state_after`/`state_before` pairs match
exactly (67.3% of 191,257 adjacent pairs), **19,881 fully chained proofs of length ≥2, 8,150 ≥3,
1,983 ≥5, 132 ≥10, max 35**. Those figures should be independently re-derived before they are
relied on, but they identify the right file.

So: build the trajectory arena on LeanDojo `random/train.json` / `steps.jsonl`, use a 3–10 step
tactic-selection episode, and keep `formal_structural` for what it is good at — single-state
canonical transcription. Do **not** build this on `world_v0`, whose successor state is model-free
derivable 676/676.

### M2. A closed generation loop — **blocker, but nearly free**

There is no `for generation` anywhere in `arena/`. The loop is severed at one edge:
`pipeline.evaluate()` refuses any candidate without a hand-registered renderer
(`pipeline.py:210-214`), and only the 8 seeds are registered (`registry.py:52-62`).

*Closest existing thing:* every stage already exists separately — `Architect.propose`
(mutation), `assert_arena_parity` (gate), `run_mechanism` (evaluation), `rank_registry` +
`select_frontier_diverse` (selection), `LeagueRegistry` (archive).

*Cheapest credible path:* (a) make `get_language` fall back to
`GenomePhenotypeLanguage(genome)` for any genome on disk — this alone lets the 120 existing mutants
enter evaluation for the first time; (b) write `LeagueManager.run_generation(parents, budget)` in
`arena/players/league_manager.py`, which today is a 21-line stub with zero importers, wiring the
five existing stages in order. This is plumbing, not research.

### M3. A language fitness record and history — **blocker for any selection pressure**

`MutationHistory` (`mutation.py:376`) records *proposals*; nothing records a *score* against a
genome. `LeagueRegistry` has the schema for it (`AxisRating`, `objective_metrics`) and **zero
observations**.

*Closest existing thing:* `LeagueRegistry.record_observation`/`record_match` (`registry.py:152-188`)
and `MatchObservation` (`matches.py:10`) — a complete, tested, unused data model.

*Cheapest credible path:* write the one adapter that converts a `run_mechanism` row set into
`MatchObservation`s and calls `record_match`. The archive then populates itself and
`rank_registry` starts returning real fronts.

### M4. A multi-fidelity evaluator with early elimination — **high**

*Closest existing thing:* `gpu_matched_runner.py:33` `HALVING_RULE` (a real 3-stage rule with
`minimum_margin: 0.06` and a selection-free stage-C slice) and `precondition_power.py`'s exact
clustered McNemar power.

*Cheapest credible path:* lift `HALVING_RULE` out of the CUDA-gated script into a small
`arena/evaluation/halving.py`, parameterise the stage budgets from
`precondition_power.required_families(...)`, and drive it from the generation loop (M2). Note
`pipeline.evaluate`'s `tier` argument is currently a filename label with identical computation for
0 and 1 — it is a name to reuse, not a mechanism.

### M5. A language meta-genome — **high**

The current 14-gene vector describes a *serialization*, not a language: 5 families are byte-inert
**[measured here]**, and there is no gene for anything the inner MDP would actually vary — what is
in scope, what is elided, how history is summarised, what the action grammar is, how much of the
proof state is shown per step.

*Closest existing thing:* `ContentGenome` (`model_view/genome.py:75`) — 6 content genes over
truth-derived projections (dependency, action-goal, premise, obligation, state-delta, evidence),
with declared invariants, cost tiers and instrumentation in `CONTENT_GENE_METADATA` (`:166-209`).
This is the correct *shape* for a meta-genome and is already wired through `ModelViewCompiler`
under `SearchTrack.CONTENT_PROJECTION`. Game R pins it at the Track-E default and never varies it.

*Cheapest credible path:* keep `LanguageGenome` as the surface half, drop or repair the 5 inert
families, and promote `ContentGenome` to the second half — then extend it with horizon-specific
genes (history window, subgoal exposure, action-grammar arity). `ModelViewGenome` already composes
the two (`model_view/genome.py:111-163`).

### M6. A learned Architect — **medium (research), low (blocking)**

*Closest existing thing:* `players/architect.py` — deterministic neighbour enumeration; and
`arena/surrogate/` (382 LOC), which was written to predict fitness from genome features
(`features.py:17` flattens "a genome-like record") and has never seen one.

*Cheapest credible path:* do **not** start here. Once M3 populates a fitness history, feed it to
the existing surrogate (`surrogate/dataset.py` + `model.py`) as a proposal *re-ranker* over
`Architect.propose`'s output. That is a 50-line change that turns dead code into a weak learned
prior. A generative Architect is premature until a fitness signal exists at all.

### M7. A surrogate trained on real data — **low**

Subsumed by M6. Recorded separately only because the hypothesis lists it.

---

## 6. REUSE MAP FOR THE META-GAME

| Meta-game component | Build on | Verdict |
|---|---|---|
| **Inner trajectory arena** | `arena/canonical/schema.py:304,322` (`CanonicalTransition`/`CanonicalTrajectory` types), `arena/verifier/base.py:44` (`verify_transition`), `arena/environments/formal_structural.py` (real Lean transitions), `arena/experiments/game_r_formal_v1.py:319,360` (protocol shape to extend) | **NEW module**, reusing those four. No existing environment can be adapted: all are horizon-1 by type |
| **Language meta-genome** | `arena/model_view/genome.py:75-209` (`ContentGenome` + `CONTENT_GENE_METADATA`) as the content half; `arena/genome/schema.py:44` (`LanguageGenome`) as the surface half, minus the 5 inert families; `arena/model_view/genome.py:111` (`ModelViewGenome`) composes them | **REFACTOR existing** |
| **Semantic gate** | `arena/experiments/game_r_formal_v1.py:625` (`assert_arena_parity`), `arena/model_view/compiler.py:117` (`validate`), `arena/experiments/game_r_mutant_audit.py` (5-check compatibility), `arena/assurance/properties.py:66` (`roundtrip_property`), `arena/players/refuter.py` | **KEEP, lift verbatim**, then extend from state to trajectory |
| **Matched evaluator** | `arena/experiments/game_r_formal_v1.py` (prompt envelope, cache identity, budget, `RowStatus`), `arena/experiments/ollama_live.py` (digest-frozen solver + exact token counting), `arena/training/prepare_matched_data.py` + `route_b_data.py` (nesting/quality-filter discipline), `arena/experiments/rendered_prompt_adversary.py` (shortcut gate on the rendered prompt) | **REFACTOR existing** (stateless `Solver` protocol must become episodic) |
| **Fitness record** | `arena/league/matches.py:10` (`MatchObservation`), `arena/league/registry.py:33` (`AxisRating`), `arena/fitness/metrics.py`, `arena/evaluation/landscape.py` (McNemar + clustered bootstrap), `arena/experiments/precondition_power.py` (power/sample size) | **REFACTOR existing** — the schema is complete and has never received a single observation |
| **Archive** | `arena/league/registry.py` (multi-axis, Pareto status, persistence), `arena/league/hall_of_fame.py:15` (`HallOfFameSuite` content hashing), `arena/league/selection.py:46` (`select_frontier_diverse`, crowding distance), `arena/fitness/pareto.py` | **REFACTOR existing** — needs a producer and lineage queries; `parent_ids` is stored (`registry.py:63`) and never read |
| **Mutation operator** | `arena/genome/mutation.py` (operators, proposal, `apply_mutation`, `MutationRecord`, `MutationHistory`), `arena/genome/crossover.py`, `arena/genome/validation.py`, `arena/players/architect.py` | **KEEP** — complete and tested; needs only to be called in a loop and extended to the content half of the genome |
| **Outer loop** | `arena/players/league_manager.py` (21-LOC stub, zero importers — the intended home), `arena/pipeline.py:165-238` (the severed `mutate`→`evaluate`→`run_league` path), `arena/training/gpu_matched_runner.py:33` (`HALVING_RULE`) | **NEW**, assembled from existing parts. The one hard blocker to remove first is the hard-coded `SEED_LANGUAGES` registry (`arena/languages/registry.py:52-62`) that `pipeline.py:210` depends on |

---

## 7. What could not be determined

- **Whether any REQUIRED canonical-vNext change is safe to make.** The blast radius (project-wide
  re-hash + `_KNOWN_KEYS` index shift) is measured; the cost of executing it is not.
- **The LeanDojo chained-horizon figures quoted in M1 were not produced by this audit.** They come
  from `research/phase9/data_audit/` — untracked files written by a concurrent session in this
  worktree. I verified the *HML_V3* chainability result independently (0 of 1,150 joins) but did not
  re-derive the LeanDojo numbers, which would require streaming a 373 MB JSON. Treat them as a
  pointer to the right file, not as this document's evidence.
- **Whether `qwen38-rvn` or any local Solver can act coherently over a horizon > 1.** Every solver
  measurement in the repo is single-turn; there is no evidence either way.
- **The true cost of a generation.** `precondition_power.py` can compute the sample size, but no
  wall-clock or token cost per trajectory episode has ever been measured, because no episode has
  ever been run.
