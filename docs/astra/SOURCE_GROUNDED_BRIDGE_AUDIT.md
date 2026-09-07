# Source-grounded bridge architecture audit

Recorded 2026-09-07. Bounded audit of project source syntheses and implementation. This document does not independently verify the literature those syntheses cite, propose a universal ontology, or claim a representation effect.

## Sources actually consulted

| Source | Relevant finding applied here |
|---|---|
| `GOAL.md`, completely read, especially §§3–6, 13, 17, 20 | Freeze semantics, visibility, tasks and verifier separately from representation; preserve the possibility of a negative result |
| [HML Semantic Constitution v1](/Users/moheet/Documents/ChatGPT/hamiltonian-lang-final-signal/docs/semantics/HML_SEMANTIC_CONSTITUTION_V1.md:11), §§1–4 | PARSES, TYPECHECKS, denotation, entailment, execution and proof are distinct judgments; binder order affects meaning; unresolved scope/obligations cannot be silently accepted |
| [Local prior-art synthesis](/Users/moheet/Documents/ChatGPT/hamiltonian-lang-final-signal/docs/research/PRIOR_ART.md:626), §5.1 and lines 850–878 | Representation/inference interaction is an empirical question; novelty of notation does not establish capability; pretraining familiarity is a live alternative explanation. These are claims of the local synthesis, not freshly verified external facts |
| [Lean runtime state specification](/Users/moheet/Documents/ChatGPT/HML_V3/research/canonical_ir/LEAN_RUNTIME_STATE_SPEC.md:6), boundary, expression and binder sections | Runtime identities and expression constructors come from Lean capture; Python must not infer FVar/MVar identity from pretty text |
| [Canonical Math State V2](/Users/moheet/Documents/ChatGPT/HML_V3/research/canonical_ir/CANONICAL_MATH_STATE_V2.md:9), additions and equivalence sections | Preserve meaningful focus/context order; distinguish preserved, delegated, backend-specific, lost and unknown; structural equivalence does not claim definitional equality |
| `docs/REASONING_OPERATION_DISCOVERY.md:249`, `docs/CORPUS_STRATEGY.md:381` | Matching operation names can manufacture equivalence; store raw evidence and provenance before abstracting |
| `docs/SOUNDNESS.md:3`, `docs/ARENA_PROTOCOL.md:7`, requested Codex audits | Finite assurance is not universal soundness; refutation, negative controls and permanent failure memory constrain claims |

These sources are precedent and evidence only. The legacy repository's instructions to change its GOAL or run an experiment do not apply to this task. Arena GOAL.md remains untouched and authoritative.

## 1. Does the scoped bridge preserve semantics/representation separation?

**Yes for a declared trace-citation experiment, conditional on enforced projection and decoder parity; no claim of a universal semantic import.** The mathematical backend remains pinned Lean/Mathlib and the recorded citation is external oracle evidence. The source envelope retains formal-system identity, raw proof-state evidence and declaration provenance. A separate immutable visible object defines P. Each renderer must receive only that object and decode to the same inventory; target, tactic, successor and private identity maps remain outside it.

The decisive boundary is not “JSON versus text.” It is whether representation changes can alter the target, candidates, visible facts or verification meaning. A typed native text field can preserve the *available evidence* without pretending to recover information that LeanDojo never supplied. Its hash proves stable bytes, not completeness of Lean semantics.

The bridge therefore supports a narrow causal question: does organizing the same local-context/goal/candidate-statement evidence differently affect recorded-premise attribution? It does not yet support structural Lean-term/binder representation search. A later elaborated adapter needs a separate version, hashes, coverage and assurance before it expands that claim.

## 2. Is the renderer mistaken for mathematical meaning anywhere?

Two existing traps require explicit avoidance:

- `CanonicalExpression` is documented as structural, never source syntax (`arena/canonical/schema.py:43`). Encoding arbitrary Lean as `op="lean"` with a string value bypasses the intention and gives a false impression of semantic AST coverage.
- Public candidate parsing checks v0 wire shape (`arena/languages/base.py:40`), while native verification is structural and bounded (`docs/SOUNDNESS.md:34`). Neither establishes Lean elaboration, type correctness, equivalence or proof. TL0 carriers are reversible storage with explicit losses, not a replacement kernel (`releases/TRAINING_LANGUAGE_V0/canonical_adapter.py:6`).

The proposed native-field envelope avoids these traps only if its reports call fields `backend-native`/`textual` rather than elaborated ASTs. Five successful codec roundtrips establish transport parity; they do not imply five full mathematical languages can express the source's internal structure.

## 3. Are binder, scope or type distinctions lost?

**The source already omits elaborated distinctions.** Pretty-printed text does not expose complete FVar/MVar identities, universe assignments, instance resolution, coercions or reducibility. Byte preservation cannot restore those. The bridge should say “lossless relative to admitted source evidence,” not “lossless Lean state.”

Current v0 has one mandatory goal (`schema.py:204`), flat binding types and no binding value (`:107`), no explicit per-goal metavariable context or substitution map. These are exact coverage failures, consistent with `docs/CANONICAL_VNEXT_PILOT.md:57` and `:79`. Native ordered context and goal blocks can be retained as textual records; backend formal distinctions remain **BACKEND_SPECIFIC** or **CANONICAL_VNEXT_CANDIDATE**, not fabricated structure.

Alpha-renaming is the most delicate metamorphic test. Plain token substitution can capture bound names or change references in dependent types. Arbitrary Lean alpha-equivalence cannot be certified by a regex. Admit only a conservatively justified subset, preserve exact native text elsewhere, and report skipped cases. Context permutation is safe only when dependencies and scope justify it; it is not an unconditional property of a list. Reordering a Lean goal list may change focus and hence action meaning, so preserve it.

## 4. Does P contain information belonging to Game P?

Candidate statements, context, goal text and neutral option identity may form one newly frozen P. Adding statements to the historical names-only task changes P, but varying codecs after that freeze is legitimate Game R. Derived relations such as binder-use edges, premise-to-goal matching, inferred substitutions, proof dependencies, “useful” scores or selected-type compatibility cannot appear in one arm only.

`ModelViewCompiler` explicitly adds truth-derived relations only under `CONTENT_PROJECTION` (`arena/model_view/compiler.py:78`). Do not invoke this route selectively for an Astra renderer. Even true relations change visible information unless included equally in the experiment's frozen P. Existing L0 gold-signature hints and L4 context elision (`arena/environments/premise_selection.py:601`, `:616`, `:922`) are separate control/projection conditions, not representation variants.

Metadata needs the same discipline: theorem names, source module/order, proof position, tier, citation frequency and record hashes can become answer-correlated clues. Private provenance must remain auditable, but render only the explicitly admitted metadata. Neutral IDs must not encode the target or drive representation-specific sorting.

## 5. Can candidate languages be compared causally?

**The bridge can make a comparison executable; it cannot qualify the measurement by itself.** Required evidence is:

1. One task bank with pinned source hashes, immutable target identity and candidate ordering seeded from task identity, independent of representation.
2. A strict projector; all renderers decode to precisely the same ordered visible inventory, including multiplicity, native text, option identity and types. Negative tests must delete/change/add fields and make parity fail.
3. Determinism, safe-subset metamorphisms and explicit unsupported cases; option permutation moves the answer by candidate identity rather than by position.
4. A development-only shortcut report. Balanced option positions do not defeat first-mention, name-frequency or source-locality rules, as the existing World-v0/depth audits already show. If a new strongest shortcut is high, report it and redesign/preregister later rather than raising a ceiling after measurement.
5. Later preregistration matching Solver, tokenizer, controller, tools, training budget, response interface and hidden evaluation. All candidate prompts must fit; truncation is information loss. Zero-shot familiarity remains distinct from matched learnability.

These steps implement the operational/denotational/axiomatic separation: citation recovery is an executable labeling rule; native formulas denote mathematics under their backend; checked proofs require backend evidence. The experiment must not collapse these into one `VERIFIED` field.

## Bounded verdict

The scoped envelope is the right near-term boundary. It preserves available evidence without editing frozen Σ and permits controlled serialization comparisons. The remaining limits are material: recorded attribution rather than unique mathematical necessity; native text rather than elaborated semantics; restricted alpha/context transformations; and a new candidate-statement P that requires its own shortcut and measurement qualification. No model capability, RSTAR status or universal soundness follows from this audit.
