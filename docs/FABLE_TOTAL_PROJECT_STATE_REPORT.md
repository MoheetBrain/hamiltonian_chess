# Fable total project-state report

Recorded 2026-09-08. This report separates committed evidence from Claude's current uncommitted Phase-8 work. Evidence tags are `[CODE]`, `[ARTIFACT]`, `[PREREG]`, `[TEST]`, `[AUDIT]`, `[INFERENCE]`, and `[UNKNOWN]`.

## 1. Executive summary

Hamiltonian Arena is an experiment about whether changing the external organization of identical mathematical information changes a matched AI solver's verified mathematical capability. Its constitution freezes the mathematical state, visible projection, tokenizer, solver, controller, tasks, tools, verifier and budget while Game R varies only representation `R`.[CODE: `GOAL.md` §§3–7]

The project has a substantial canonical toy world, eight seed codecs, assurance tests, 120 one-gene mutants, real-formal capability families, a reusable tournament harness, and a released baseline training language.[CODE][ARTIFACT] It has not yet produced a valid representation comparison. V1 and V2 scored multiple candidate IDs, and V3 scored 12 founder IDs, but those instruments were invalid or unqualified; V4–V7 used one control representation only.[ARTIFACT][AUDIT] Therefore there is no defensible `Δ = Acc(R_A) − Acc(R_B)`, no FITNESS_CANDIDATE, and no `RSTAR_0_1`.[INFERENCE]

V7 is best described as `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`, not as a clean representation result. Its arithmetic, cache accounting and response validity largely hold, but its shortcut gate was evaluated on canonical probe features while the model saw rendered prompts, its selected cells have only 24 positive examples, its position gate is at chance, and later audits found population-scale and rendered-surface issues.[AUDIT: `docs/V7_TOTAL_FORENSIC_AUDIT.md`]

Claude's newest Phase-8 work is local and uncommitted. The worktree is based at committed `2047fda`, but the precondition ladder, founder runner, rendered-prompt adversary audit, parity audit, tests and reports are all untracked.[CODE][GIT] The 45-cell rendered shortcut run completed, but its preregistration is still explicitly a draft skeleton with key thresholds and sample-size decisions marked `TBD`.[ARTIFACT][PREREG] It cannot authorise a founder tournament.

## 2. Current system

The canonical world is `arena-canonical-v0.1.0`. `CanonicalState` stores typed objects, bindings, assumptions, facts, propositions, a goal, obligations, evidence dependencies, scope, legal actions and plausible invalid actions; `CanonicalAction` stores operation, targets, arguments, warrant, preconditions and generated obligations.[CODE: `arena/canonical/schema.py`] The frozen world has 676 one-transition tasks across 13 domains: 520 Gold, 104 Silver and 52 Reject, with world hash `ac16014cd20fbed2dabacd75bff3fd19723e3e96048f82a1ee1a574f59daf256`.[ARTIFACT: `docs/CLAUDE_FINAL_HANDOFF.md:60-66`]

The constitutional variables are: `Σ` canonical semantics/truth; `P` visible-information projection; `R` model-facing organization; `τ` tokenizer; `π` solver; `C` search/controller; `D` task distribution; `U` libraries/tools; `V` verifier; `B` resource budget.[CODE: `GOAL.md:76-100`] Game R freezes every variable except `R`; Game P varies which true relations are exposed; Game C varies search/controller; Game T varies verified curriculum; Game J studies later interactions.[CODE: `GOAL.md:132-286]

The verifier checks canonical/native mathematical constraints, exact arithmetic and bounded structured states where the corresponding adapter supports them. It does not turn a surface string into a Lean kernel proof, establish that a recorded premise citation is the only valid premise, or prove that a synthetic task generalises to real mathematics.[CODE][AUDIT]

The eight seed representations are Structured English, compatibility HML, S-expressions, JSON AST, Typed Prefix, Compact Symbolic, Graph Triples and Hybrid Role-Labelled.[CODE: `arena/genome/seeds.py:31-183`] They are codecs over the canonical wire record. The 14-gene genome controls actions, alphabet, binders, composition, error locality, evidence, grammar, morphology, obligations, redundancy, serialization, state, token policy and types.[CODE: `arena/genome/schema.py`] A committed V1 artifact contains 120 one-gene mutants plus eight seeds; all 120 passed Gate 0 and a later audit found 120/120 Game-R-compatible.[ARTIFACT: `docs/EXPERIMENT_LOG.md:40-42`; `docs/CLAUDE_FINAL_HANDOFF.md:168-169`]

The training-language release is a baseline canonical record language, not a discovered winner. Its raw package hash is `443c8f7950147b826797e409ed36ffbed1bf1d08482365f6db57349fca161135`; `docs/TRAINING_LANGUAGE_V0.md` contains a stale different package hash, so the release note must not be treated as the authoritative hash.[ARTIFACT][AUDIT]

## 3. Scientific history

| Phase | Evidence and scale | Result | What it supports |
|---|---|---|---|
| V1 | Gemma 3 4B calibration; four candidate IDs; 64 rows; 120 Gate-0 survivors | invalid: option-position/constant answering | position controls are mandatory; no `R` claim |
| V2 | Gemma 4 12B; four controls; 192 calibration probes; JSON A/B | instrument valid, but 0.125 headroom below frozen 0.15; stopped before matched run | solver/protocol calibration only |
| Matched A100 sprint | Qwen2.5-7B LoRA, five arms, stages A/B/C; historical 480 evaluations per stage family | early JSON > Structured English > HML > S-expression, then saturation; `WEAK_CONTINUE` | historical training observation; later audits invalidate causal ranking |
| V3 | six synthetic mechanisms; 12 founders; 432 rows, 66 cache hits | invalid: prompt truncation, malformed outputs, confounded mechanism families | representation result void |
| V4 | five mechanism ladders; 356 calls; grammar repair not yet complete | `FITNESS_V4_NOT_QUALIFIED`; 0/3 | instrument and solver failure diagnosis |
| V5 | Gemma 4 12B, 864-probe development bank; grammar-constrained | 0/3 qualified; malformed-output problem fixed; constant-answer/ceiling and selector defects exposed | capability instrument negative; no `R` claim |
| Phase 6 | Qwen route and cache dispute | later audit finds cache-hit field was not recorded by the pipeline; solver finding survives, qualification claim is disputed | Qwen can read the task interface; no representation result |
| V7 | Qwen38-RVN bare; 864 main fresh rows + 8 fresh Q0; one control ID | `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`; 0/3 | arithmetic/cache/response portions stand; mechanism verdicts require qualification |

The historical multi-arm count matters: V1=4 candidate IDs, V2=4, the A100 sprint=5 arms, V3=12 founders; V4, V5, Phase 6 and V7 each used one control ID.[ARTIFACT][AUDIT] The accurate conclusion is “no valid representation winner,” not “no multi-representation scoring ever occurred.”

## 4. V7 and mechanism status

V7 recorded 864 fresh main calls, eight fresh Q0 calls, zero cache reuse and zero cross-condition rows; Q0 was 1.000 and all main rows had valid six-token constrained completions.[ARTIFACT: `artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json`] Its model digest was `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`, runtime configuration hash `fbf95fc39cc59be68387ee511a5296c30f43cda80b5e49b97a90287c265734db`, and primary budget 900 calls.[ARTIFACT]

`formal_expression_depth` selected level 2: positive accuracy 0.7917, best canonical shortcut `first_mentioned_in_state` 0.8333, answer entropy 0.995 bits, largest answer share 0.5417, position invariance 0.5833; verdict `VOID_SHORTCUT`.[ARTIFACT] `transitive_dependency` selected level 3: positive accuracy 0.7500, best shortcut 0.6667, margin 0.0833 below the declared 0.10, position invariance 0.8333; verdict `VOID_SHORTCUT`.[ARTIFACT] `precondition_conjunction` never entered the qualifying accuracy band: positive scores were 1.0000, 0.9583, 1.0000 and 1.0000 across its four levels; verdict `VOID_CEILING`.[ARTIFACT]

The later population audit refutes the strong form of V7's transitive `VOID_SHORTCUT`: its finite `n=24` shortcut score was not population-scale evidence. It also finds formal-expression's first-mentioned/depth relationship is a real structural property of the generated Lean terms, while precondition's chance shortcut scores are pinned by its construction.[AUDIT: committed `06ab9fc`; `docs/V7_TOTAL_FORENSIC_AUDIT.md`]

The three current real-formal families are premise selection, rewrite direction and legal transformation. Premise selection has 63,831 production items in the historical full measurement but the existing items carry pre-rendered Lean strings, not a shared canonical object. Rewrite direction has 3,466 within-lemma balanced items in its controlled pool. Legal transformation has 24,000 Tier-B constructed pairs and no Lean-verified Tier-A result. All three are capability-only until a canonical adapter exists.[PREREG: `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md`]

## 5. Representation-search status

Game R has never completed a valid live tournament. The 120-mutant artifact is semantic assurance and compatibility screening, not fitness. No parent-child fitness correlation, mutation benefit rate, local smoothness, ruggedness, Hall-of-Fame selection pressure or evolutionary trajectory has been measured.[ARTIFACT][UNKNOWN]

The current tournament harness is substantial: cache identities include experiment, model, runtime, genome, probe and prompt hashes; cache scopes distinguish fresh, same-condition reuse and cross-condition; parity rejects changed content and byte-identical arms; token budgets fail closed; resumption preserves completed rows.[CODE: `arena/experiments/game_r_formal_v1.py`; TEST: `tests/experiments/test_game_r_formal_v1.py`] Its live Ollama path is implemented and tested through injected transports, but no valid founder tournament has exercised it.[TEST][ARTIFACT]

Astra's committed research bridge is useful as a deterministic source-envelope and parity prototype: branch `astra/canonical-game-r-bridge`, commit `5811161684d962195276cb9459720750b0e970cd`, 300 source items, five codecs, 1,500 renderings and 1,800 option permutations.[ARTIFACT: `research/astra/`] Its codecs preserve the same raw Lean source strings while changing framing; they do not recover elaborated Lean semantics. It is not evidence that Game R has run.

## 6. Claude's current uncommitted Phase-8 state

The Phase-8 worktree `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/hamiltonian-phase-8-experiment-691d22` is on committed `2047fda` but has untracked Phase-8 code, tests, frozen-adversary manifests and reports. The five implementation modules include a precondition ladder, founder runner, live Ollama adapter, power utility and rendered-prompt adversary audit.[GIT][CODE]

The rendered shortcut audit completed 45 cells: nine strata, five surfaces/arms, 100 ADV_DEV families and 200 SHORTCUT_EVAL families per cell, 300 bootstrap draws and 1,000 permutations. The audit is exploratory because `docs/GAME_R_PRECONDITION_FOUNDER_V1_SPEC.md` calls itself a draft skeleton and leaves gate thresholds, sample size, stratum and freezing SHA as `TBD`.[ARTIFACT][PREREG] Non-significance in most cells is not a qualification pass.

The summary “clean on P09–P20” is too strong. The full within-twin permutation artifact reports 13/45 cells with `p < .05`, including P12/L0 and P16/L0; the frozen best-Holm summary has three significant cells: P05/L5 `p=.03546`, P05_M2_D2/L2 `p=.01587906`, and P05_M2_D2/L5 `p=.04665`.[ARTIFACT][AUDIT] The exact family-level dependence and the distinction between decided-item confidence bounds and headline accuracy must be retained. A direct live founder tournament, calibration or clean preregistration freeze was not demonstrated; existing smoke/calibration outputs use stubs.[CODE][ARTIFACT][UNKNOWN]

The targeted Phase-8 test set passed 168 tests; Ruff and mypy passed on the committed source. This validates software paths, not the scientific gate.[TEST]

## 7. Data, compute and engineering readiness

LeanDojo Benchmark 4 is locally present at `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4`; the committed corpus strategy records 259,580 transitions and the train/val/test metadata. The project’s own audit shows `novel_premises` val/test were parsed before the seal was declared, and `steps.jsonl` exposes split metadata; the `PROMOTION_OOD` label is therefore not trustworthy.[AUDIT: `docs/V7_TOTAL_FORENSIC_AUDIT.md`; `docs/CORPUS_STRATEGY.md`]

Two Lean runtime trees must not be conflated: an unbuilt sibling reports 38 `.olean` files, while the built runtime tree contains 5,680 `.olean` files across 4,447 Mathlib modules plus packages.[AUDIT] The historical Tier-A replay yield was 32/100, so a 199,000-attempt scale-up would be needed to obtain roughly 63,831 usable single-premise/single-goal rows at that yield.[AUDIT]

The machine is an Apple M5 Max with 51,539,607,552 bytes of RAM and 18 logical CPUs. Ollama 0.33.2 is installed with Gemma 4 12B/31B, Qwen38-RVN, Qwen36-Huihui and Qwen38-Huihui manifests. Cloud instances `a100-40`, `a100` and `h3` are all `TERMINATED`; no cloud GPU is running.[CODE][COMPUTE]

The committed repository’s targeted Phase-8 tests passed 168/168, Ruff passed, and mypy passed on 135 files. The full repository test collection has 1,170 tests including Astra tests; these are engineering checks, not evidence of a representation effect.[TEST]

## 8. Proven, refuted and never tested

Proven: the canonical v0 world and its hashes; seed codec roundtrips and assurance; V1 position collapse; V3/V4/V5/V7 protocol defects recorded above; V7’s exact fresh-row and cache accounting; Qwen/Gemma can produce valid constrained decisions on the synthetic interface; the current real-formal families are raw-string capability environments; and the Phase-8 code is locally testable.[ARTIFACT][TEST][AUDIT]

Refuted or withdrawn: HML is superior; JSON is best; Compact Symbolic is best; any language has beaten another in a valid Game-R comparison; the historical A100 ranking is a causal sample-efficiency result; V7’s strong `transitive_dependency` shortcut verdict; clean hidden status for LeanDojo promotion pools; and the claim that no experiment ever scored multiple representation IDs.[AUDIT]

Never tested: a valid matched live Game-R tournament; a valid representation delta; a fine-tuning comparison using clean held-out data; evolutionary generations; robust cross-solver representation effects; a clean real-Lean canonical tournament; and any claim that TRAINING_LANGUAGE_V0 is optimal.[UNKNOWN]

## 9. Highest-value next experiment and decisions

The highest expected-value immediate experiment is a preregistered, independent precondition founder pilot only after Phase-8 artifacts are frozen: extend the precondition ladder until a control cell has headroom, audit every rendered arm with a train/evaluation adversary split, enforce a shared semantic state and option permutation protocol, use independent selection and qualification pools, and size the experiment for the declared practical effect. This would be the first chance to compute a valid `Δ`, but it remains synthetic and cannot establish transfer to real Lean.[INFERENCE]

Decision 1: either freeze and pass the complete Phase-8 preregistration, or stop it. A draft with `TBD` thresholds cannot authorise calls.

Decision 2: if the synthetic pilot survives rendered adversary, permutation and power gates, run the first two-arm founder comparison and report the full learning/accuracy vector. If it fails, do not create another ladder.

Decision 3: build a genuinely elaborated Lean premise-selection adapter from the built runtime, with fresh never-inspected promotion data. Astra’s source-envelope bridge is a useful scaffold, but the raw pretty-string projection is insufficient for a strong real-mathematics Game-R claim.

Evolution is not ready: no fitness landscape, selection pressure or parent-child signal exists. Fine-tuning is not ready for a causal representation claim: no clean promotion split, matched data protocol or valid Game-R result exists. Adding another Solver is lower value than repairing the instrument and sealing the data.[INFERENCE]

Top risks are: dirty-only scientific work being mistaken for a frozen result; draft thresholds; shortcut gates computed on a different object from the Solver input; position anchoring; tiny and dependent `n=24` cells; contaminated promotion pools; synthetic-task generalisation; shared-text source codecs misread as semantic representations; stale package hashes; and unrecorded cache/selection quantities.[AUDIT]

## 10. Git state

This report is on forensic branch `codex/fable-total-state-20260908`, based on Claude’s committed `2047fda`. Astra remains independently pushed at `origin/astra/canonical-game-r-bridge` commit `5811161`. Claude’s Phase-8 additions are intentionally not merged or committed by this audit.

If I had to explain the state to Demis Hassabis in 60 seconds: Hamiltonian Arena has built serious infrastructure for testing whether mathematical notation changes AI reasoning, and it has learned a lot about benchmark failure, shortcut leakage, position bias, cache discipline and solver ceilings. It has not yet measured the causal representation effect it was created to measure. The latest Claude work is a promising but unfinished synthetic precondition pilot, while the real-Lean route still lacks an elaborated canonical adapter and clean promotion data. The scientifically honest next move is to freeze and audit one small instrument completely, run the first valid two-arm comparison only if it survives those gates, and treat every current language ranking as unproven.
