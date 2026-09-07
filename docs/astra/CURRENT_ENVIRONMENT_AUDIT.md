# Current real-environment and language boundary audit

Recorded 2026-09-07. This is a read-only source audit, not a new model result. References below are repository-relative `path:line` coordinates, stable at Astra's base `9f28c0c1b673804648052a54a65cf32eee875b05`. Claude's newer committed documentation was inspected separately at `d026379c08e7da66e374fe01e55c82e4ae9f0d6c` in `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/phase-6-parallel-setup-9c6068`.

## Finding

The three environments are **CAPABILITY_ONLY**, with some useful typed task records. None supplies a canonical visible premise object to an Arena candidate language. The working hypothesis is confirmed by code, but “raw string fixes R” needs a qualification: a frozen native string can be embedded in multiple record serializations; that tests the organization of those records, not alternative representations of the internal Lean expression structure.

Claude already documented this gap in `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md:25` at d026379. Its proposed v0 mapping is acknowledged as lossy. Astra's scoped native-field envelope follows the user's LOSSLESS_FIRST directive instead. No existing premise bridge was found by searching `arena/`, `research/` (excluding new Astra work), and `releases/` for premise/canonical/bridge implementations.

## Environment comparison

| Property | Premise selection | Rewrite direction | Legal transformation |
|---|---|---|---|
| Classification | **CAPABILITY_ONLY** | **CAPABILITY_ONLY** | **CAPABILITY_ONLY**, constructed-label limitations |
| `CanonicalState` use | None; `Transition.state_before: str`, `PremiseItem.prompt: str` (`arena/environments/premise_selection.py:113`, `:147`) | None; `RewriteDirectionItem.state: str` (`arena/environments/rewrite_direction.py:568`) | None; only canonical `stable_hash` imported (`arena/environments/legal_transform.py:44`); states are strings (`:458`) |
| `CanonicalAction` use | None; `PremiseOption(full_name, def_path, tier)` (`premise_selection.py:138`) | None; forward/reverse strings and answer index (`rewrite_direction.py:581`) | None; `action: str` (`legal_transform.py:466`) |
| Native Lean strings | Whole before-state; candidate names, optional control hint | Before-state, parsed signature and textual sides; target location | Before-state, proposed tactic, proposed successor |
| Source provenance | LeanDojo 2.0.0 / Mathlib `29dcec07…`; proof/file/theorem/step/train/commit/generator/seed (`premise_selection.py:855`) | Same source and commit (`rewrite_direction.py:54`); item provenance (`:588`, `:797`) | Typed `SourceProvenance`, record hash, adapter version, source item and caveats (`legal_transform.py:1053`) |
| Target oracle | Single syntactically annotated citation in recorded next tactic (`premise_selection.py:231`, `:298`, `:824`) | Direction of first bracket element of recorded tactic (`rewrite_direction.py:232`, `:851`) | Recorded positive plus chosen corruption; `valid` is assigned (`legal_transform.py:1087`) |
| Verifier strength | Citation extraction, index and leak checks; no per-item Lean replay or proof of unique usefulness | Direction is syntactic trace evidence; equation parsing explicitly heuristic, not elaboration (`rewrite_direction.py:38`) | **All generated items Tier B**, no Lean execution (`legal_transform.py:15`, `:1102`); documented residual equivalence risks (`:162`) |
| Alternatives | K = 6, or 8 at L4; same-proof/module/import/lexical tiers; deterministic shuffle (`premise_selection.py:601`, `:793`, `:820`) | Two directions, common seeded permutation | Binary VALID/INVALID on paired triples; no alternative `CanonicalAction` bank |
| Actual renderer | `render_prompt`, fixed prose + raw state + names (`premise_selection.py:907`) | `RewriteDirectionItem.render`, fixed prose + strings (`rewrite_direction.py:595`) | `ITEM_TEMPLATE` plus string formatting (`legal_transform.py:488`) |
| Existing visible P | Normal arm: state + candidate names. L0 adds gold-specific redacted signature; L4 deletes context (`premise_selection.py:616`, `:894`, `:922`) | State + lemma identity/type/sides + target + both direction definitions; successor hidden; L0 gives deciding fact (`rewrite_direction.py:595`, `:632`) | Before/action/after; hides label, tier, corruption axis, provenance (`legal_transform.py:491`) |

The “correct premise” means **recorded citation**, not “only mathematically valid premise,” “all dependencies,” “sufficient premise,” or “best next action.” LeanDojo annotation does not record every simplifier/typeclass/unfolding dependency (`legal_transform.py:59`). Likewise recorded rewrite direction is not a proof that the other direction could never work. Legal transformation's textual type difference is not Lean definitional inequality (`legal_transform.py:176`). These distinctions constrain the eventual scientific claim.

## What Claude already supplied

- Deterministic train-only loaders, premise provenance, candidate sampling, fixed renderers, grouped development shortcut tooling and three task-family manifests.
- A frozen V7 instrument (`docs/FITNESS_V7_PREREGISTRATION.md`), independent from these real families. No V7 execution or result interpretation is part of this audit.
- `TRAINING_LANGUAGE_V0`: structured types, goal/scoped context records, lets and substitution (`releases/TRAINING_LANGUAGE_V0/core.py:9`), carriers and loss reports for the v0 boundary (`canonical_adapter.py:6`), and a training-record factory. This is useful infrastructure; the newer `docs/TRAINING_DATA_FACTORY.md:82` still calls for an environment adapter as its next step.
- The TL0 compatibility profile deliberately rewrites binder kinds/targets for the frozen native verifier and carries originals (`canonical_adapter.py:23`). Reversible storage does not make the v0 native verifier a Lean checker.

## Exact representation coverage failures

All public founder `render/parse` contracts require `CanonicalState` and strict v0 wire validation (`arena/languages/base.py:33`, `arena/languages/_wire.py:20`). A private generic codec accepting a dict does **not** establish public founder support for arbitrary Lean mathematics.

| Component | Exact missing construct / failure | Safe reusable part |
|---|---|---|
| Structured English | Fixed `STATE_FIELD_ORDER` and labels; no premise-envelope `context`, `candidate_premises`, backend type text or native goal groups (`arena/languages/structured_english/__init__.py:15`) | Existing JSON atom serialization / labelled-record convention |
| HML compatibility | Fixed v0 state fields; no native Lean binding/scope/type semantics (`arena/languages/hml/__init__.py:24`) | Compatibility record/assignment convention, expressly no imported HML semantics |
| Compact Symbolic | Fixed 15-field alias map; no envelope fields (`arena/languages/symbolic/__init__.py:15`) | Explicit reversible aliases and JSON value codec |
| JSON AST | Private payload codec handles dictionaries; public parser still invokes v0 validation (`arena/languages/json_ast/__init__.py:18`, `base.py:40`) | Strict JSON codec; describe resulting artifact as a premise-envelope JSON encoding, not a Lean AST |
| S-expression | Private codec handles dictionaries; public state parser still enforces v0 (`arena/languages/sexpr/__init__.py:22`, `base.py:40`) | Existing `sexpr_encode/sexpr_decode` |
| `GenomePhenotypeLanguage` | `_binding_encode` requires v0 five-field bindings; `_ordered_payload` assumes v0 roles; it does not derive de Bruijn identity from Lean (`arena/languages/phenotype.py:155`, `:292`) | Generic grammar/value encoding can be reused only with declared adapter coverage |
| `ModelViewCompiler` | Takes v0 states/actions; `derive_truth_view` consumes v0 facts, preconditions, obligations and evidence, not Lean trace records (`arena/model_view/compiler.py:68`, `projection.py:91`) | Pattern of independent reconstruction and accounting, not its v0 truth assumptions |

Each public-founder gap is **REPRESENTATION_COVERAGE_FAILURE** until an explicit envelope adapter exists and its decoder recovers the same P. Surface adapters are distinct artifacts from the established founders. No raw Lean term should be manufactured as a v0 `CanonicalExpression` merely because `op` and `value` accept strings.

## Data and projection traps

1. **Truncated signature is not a lossless source.** Existing `_signature` takes bytes-as-Python-characters before the first `:=`, normalizes whitespace and cuts to 400 characters (`premise_selection.py:447`). A let inside a declaration type can precede its body separator. Use full source evidence and a conservative statement extractor that fails closed.
2. **Train flavour matters.** `random/train` and `novel_premises/train` are different partition policies. An adapter developed using random/train cannot inherit novel-premises novelty guarantees by relabelling its manifest.
3. **Historical exposure is real.** `docs/CORPUS_STRATEGY.md:166` and `:255` explicitly report prior semantic analysis of random val/test. Existing “four sealed, never opened” prose at d026379 is therefore too broad. Astra must retain historical exposure, including known derived census artifacts, and treat merely hashing a split as exclusion, not proof of never-exposed status. This audit did not open held-out semantic files.
4. **Do not serialize whole task records.** `PremiseItem.to_json()` contains target indices, gold tier and answer-correlated features (`premise_selection.py:163`, `:866`). `ModelViewCompiler.compile` renders the state it receives; it is not by itself a task-specific oracle firewall (`compiler.py:75`).
5. **Statements change the experiment relative to baseline.** Supplying all candidate statements is a new frozen P. It can be fair across Astra representations, but cannot be compared against the existing names-only baseline as an R-only intervention.

## Read coverage and scope

Read GOAL.md completely; inspected CURRENT_STATE, CLAUDE_FINAL_HANDOFF, PARALLEL_NEXT_STAGE_HANDOFF, PHASE6_INTEGRATION_MAP, FUTURE_ENVIRONMENT_FAMILIES, CORPUS_STRATEGY, and the requested MASTER_SCIENTIFIC_REVIEW, WORLD_V0_LEAKAGE_AUDIT, FORMAL_DEPTH_SHORTCUT_AUDIT, GAME_THEORY_IMPLEMENTATION_GAPS and CANONICAL_VNEXT_RED_TEAM. These are historical evidence, not permission to override newer code or the permanent objective. Newer d026379 Formal Arena/Training Factory specs were read completely. Production, release, V7, cache and frozen result files were not edited.
