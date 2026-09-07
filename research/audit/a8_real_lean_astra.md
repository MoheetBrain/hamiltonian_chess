# A8 — The real-Lean route and the Astra bridge

**Auditor 8 of 9 · V7 total forensic audit · Parts L and M · 2026-09-07**

**Mandate: falsify the proposed route.** The proposal under test is
*real Lean premise selection → semantic extraction → representation-neutral canonical state →
counterfactual shortcut balancing → the same state rendered through several representations →
paired representation comparison.*

**Compliance.** Read-only. No model/LLM call, no GPU, no network, no download. Lean/lake were
**not** built or run — only inspected on disk. The four files in
`artifacts/manifests/SEALED_SPLITS.json` were **never opened by this audit**; every read of the
LeanDojo benchmark went through
`arena.environments.premise_selection.require_permitted_train`/`guard_source_path`
(`arena/environments/premise_selection.py:68`, `:992`), which raise `SealedSplitError` on all
four. No existing file was modified. New files are confined to `research/audit/a8_lean/` and this
document.

**Scripts** (all re-runnable, all CPU-only, all deterministic):

| Script | Output |
|---|---|
| `research/audit/a8_lean/n60_power.py` | `out/n60_power.json` |
| `research/audit/a8_lean/lean_runtime_inventory.py` | `out/lean_runtime_inventory.json` |
| `research/audit/a8_lean/leandojo_string_census.py` | `out/leandojo_string_census.json` |
| `research/audit/a8_lean/astra_projection_probe.py` | `out/astra_projection_probe.json` |
| `research/audit/a8_lean/astra_invariance_cause.py` | `out/astra_invariance_cause.json` |
| `research/audit/a8_lean/statement_completeness.py` | `out/statement_completeness.json` |
| `research/audit/a8_lean/production_vs_astra.py` | `out/production_vs_astra.json` |

Astra's own audits were re-run to replay its claims:

```
PYTHONPATH=. .venv/bin/python -m research.astra.game_r_premise.shortcut_audit \
    --bank research/astra/artifacts/dev_bank.jsonl --out research/audit/a8_lean/out/replay_shortcut_results.json
PYTHONPATH=. .venv/bin/python -m research.astra.game_r_premise.audit \
    --bank research/astra/artifacts/dev_bank.jsonl --out research/audit/a8_lean/out
```

Both reproduce the committed artifacts **byte-identically** (`shortcut_results.json` compared
field-by-field: `n_diff = 0`; `parity_report.json` including all 300 `rows`: exact equality).

---

# PART L — the real-Lean route

## L1. Why premise selection is not already the better experimental substrate

It *is* the better **capability** substrate, and the spec says so
(`docs/GAME_R_FORMAL_ARENA_V1_SPEC.md:38-40`). It is not a Game-R substrate, and it is not a
promotable one. Five real blockers, in order of severity:

| # | Blocker | Class | Evidence |
|---|---|---|---|
| B1 | Items are pre-rendered strings; R is already fixed at "Lean's pretty-printer" | **CONFIRMED**, blocking for Game R | §L2 |
| B2 | The four evaluation pools were already fully read, and the shipped distractor design was chosen *after* measuring them | **CONFIRMED**, blocking for promotion | §L2c, §M16 |
| B3 | The source strings are provably lossy: 83.1 % carry inaccessible `✝` names, 7.9 % carry elided `⋯` subterms | **CONFIRMED**, blocking for semantic parity | §L4 |
| B4 | The elaborated substrate that would fix B1/B3 exists but holds only **1,150** transitions (190 single-premise / single-goal) | **CONFIRMED**, scale-limiting | §L5 |
| B5 | Upgrading a string bank to a semantic bank needs Lean replay at a measured **32/100** yield | **CONFIRMED**, cost | §L6 |

Nothing here is a criticism of the family as a capability instrument. 63,831 items, chance
0.167, ceiling 0.45, best shortcut 0.327 (`artifacts/manifests/premise_selection_manifest.json`
→ `shortcut_gate`) is a genuinely well-built instrument, and its rejection record
(`L1_cross_module` killed at 0.866 → 0.644 rather than tuned) is exemplary. The problem is that
it answers a different question from the one the proposal wants answered.

## L2. Exactly what prevents it from Game R — verified in the code

`GOAL.md:187-221` (§5) requires freezing Σ, P, τ, π, C, D, U, V, B and varying only R, where R
may alter *"grammar · syntax · tree/DAG/linear organization · field structure · binder
representation · scope representation · identifier system · dependency locality · type placement ·
role labels · redundancy · canonical ordering · surface morphology · compression · serialization"*.
`GOAL.md:597-605` (§13) additionally requires **semantic parity**: the arms must
*"represent the same underlying mathematical state"*.

**(a) The record carries strings, not semantic objects.** `arena/environments/premise_selection.py`:

* `:107` `RawStep.state_before: str`
* `:120` `Transition.state_before: str` — the sanitised object the generator sees
* `:138-143` `PremiseOption` = `(full_name: str, def_path: str, tier: str)`
* `:147-160` `PremiseItem.prompt: str`, `options: tuple[PremiseOption, ...]`
* `:907-936` `render_prompt()` emits a fixed Markdown skeleton with the raw
  `transition.state_before` interpolated verbatim

There is no type, no expression tree, no binder identity, no metavariable — only the
pretty-printer's output. Verified by grep, reproducing the spec's own claim:

```
$ grep -c 'CanonicalState\|CanonicalAction\|CanonicalExpression' arena/environments/*.py
premise_selection.py: 0     rewrite_direction.py: 0     legal_transform.py: 1     formal_structural.py: 21
```

Eight representation arms handed `PremiseItem.prompt` receive byte-identical bytes. No
representation effect is *expressible*, let alone measurable. **CONFIRMED. Severity: blocking.**

**(b) The upgrade path is lossy.** `docs/CANONICAL_VNEXT_PILOT.md:19-21` — **0 of 368** real Lean
states map losslessly into `arena-canonical-v0.1.0`; 20.7 % are hard-unmappable. Specifically for
this family, pilot gap **N3** (`:80`, and its `BACKEND_EXTENSION` classification at `:97`) says `action.external_premise_refs` has no slot and
`target_ids` is restricted to `object_ids ∪ {"goal"}` by `arena/verifier/native.py:231-241` —
"**Blocks premise-selection task families**", at 65.8 % of records. So the obvious route (parse the
pretty string into `CanonicalState`) is blocked at both ends: the parse is lossy and the target
schema cannot hold the answer space.

**(c) A third blocker the spec does not mention.** `research/environments/measurements/premise_selection_shortcuts.json`
names its own source as
`.../leandojo_benchmark_4/{random,novel_premises}/{val,test}.json` — **all four sealed pools** —
and records a complete per-policy premise-selection shortcut measurement fitted on them
(2,487 `random` and 3,586 `novel_premises` single-premise items, k=4, best shortcut up to
**0.8635**). File mtime `2026-09-07 06:42:28`.
`research/environments/measurements/census_leandojo_heldout.json` (mtime `06:38:34`) parsed all
four and recorded per-split step counts, distinct-premise counts and tactic-head histograms
(21,632 steps in total). `artifacts/manifests/SEALED_SPLITS.json` was written at
`sealed_utc 2026-09-07T11:09:59Z` (mtime `12:22:22`), and
`arena/environments/premise_selection.py` was committed at `cf1b07f`,
`2026-09-07 12:44:44 +0100`. **The seal post-dates the reads by five to six hours, and the shipped
distractor tier design post-dates them by six hours.** The measured policies — `same_proof`
(best shortcut 0.3646), `same_file_freq_matched` (0.489), `overlap_and_freq_matched` (0.4489),
`uniform_corpus` (0.8385) — are precisely the shipped/rejected tiers (a)–(d). The design was
*selected on the evaluation pools*. **CONFIRMED. Severity: critical for any promotion claim.**

## L3. Can a representation-neutral object be recovered from what LeanDojo actually gives?

**From LeanDojo alone: no.** Measured field inventory (`out/leandojo_string_census.json`, and a
direct dump of the first record):

* theorem object: `url · commit · file_path · full_name · start · end · traced_tactics`
* `traced_tactics[i]`: **exactly four keys** — `tactic`, `annotated_tactic`, `state_before`,
  `state_after`. All strings; `annotated_tactic` is `[str, [{full_name, def_path}, …]]`.
* `corpus.jsonl` record: `path · imports · premises[{full_name, code, start, end, kind}]`.
  `code` is raw source text; there is no type, no elaborated statement, no section context.

Everything downstream is string surgery over those. `state_before` is *delaborated* output:
implicit arguments, instance arguments, coercion functions, universe levels and FVar identities
are all absent by construction of Lean's pretty-printer.

**From a Lean runtime capture: yes — and it has already been done.** The corpus
`HML_V3/data/corpus/lean_runtime_v2_full.canonical.part-{000..004}.jsonl.gz`
(schema `canonical-math-transition-v2.0.0`, spec
`HML_V3/research/canonical_ir/LEAN_RUNTIME_STATE_SPEC.md`) contains exactly the
representation-neutral object the proposal describes. Measured by
`research/audit/a8_lean/lean_runtime_inventory.py`:

* **1,150 transitions**, 1,085 distinct theorems, 738 source files, 27 mathlib domains.
* Goal targets are **elaborated expression trees**, node vocabulary measured over the whole
  corpus: `application 59,816 · symbol 31,727 · local_reference 25,093 · bound_variable 3,388 ·
  metavariable_reference 3,061 · lambda 2,229 · literal 1,114 · dependent_function 1,008 ·
  sort 248 · annotated 189 · let 2`. Mean tree depth 10.5, max 59.
* Local declarations carry **stable identity separate from spelling**: 21,620 declarations, each
  with both `identity` (`f0`, `f1`, …) and `user_name_diagnostic`. Binder roles:
  `EXPLICIT 9,151 · IMPLICIT 8,772 · INSTANCE_IMPLICIT 3,648 · STRICT_IMPLICIT 49`.
  Declaration roles `cdecl 21,443 · ldecl 177` (let-values present).
* Metavariables: `NATURAL 3,526 · SYNTHETIC_OPAQUE 1,367 · SYNTHETIC 1,072`, with types and
  assignments; 4,380 assigned. Goal identity is the real `MVarId`; focus order explicit.
* Universes are `Level` trees (`succ`/`param`/…), attached to `symbol` nodes as
  `universe_arguments`.
* Premise identity is first class: `action.external_premise_refs` (elaborated `Expr.const`
  traversal) and `state_delta.external_premises_used`; 749/1,150 transitions carry them.
* Dependency edges: `provenance.lean_runtime_snapshot.transitive_import_modules` on 1,150/1,150.
* Every state carries an explicit `information_accounting` block:
  `expression_structure = PRESERVED`, `binder_and_local_identity =
  PRESERVED_WITH_CROSS_RUN_NORMALIZATION`, `standalone_constraint_table = UNEXPOSED_BY_LEAN_4_10`.

**Verdict: the semantic-extraction step of the proposal is not research — it is already built.
What is missing is scale, not method.** **CONFIRMED.**

## L4. Truth-relevant information absent from the current strings

Measured over the first 5,000 theorems / 10,720 traced steps of `random/train.json`
(`out/leandojo_string_census.json`), and over Astra's 300-item bank
(`out/astra_projection_probe.json`):

| Missing / corrupted | Rate in train steps | Rate in Astra's 300 | Why it is truth-relevant |
|---|---|---|---|
| **Elided subterms `⋯` / `…`** | 843/10,720 = **7.86 %** (201/2,629 = 7.6 % of *usable* steps) | **19/300 = 6.33 %** state, 7/60 = 11.7 % of holdout; **1/300 candidate statements** | The pretty-printer deleted mathematics. No decoder can recover it. |
| **Inaccessible `✝` names** | 8,906/10,720 = **83.08 %** | **247/300 = 82.3 %** | `inst✝³⁰` is not a legal identifier and is not an FVarId; hypothesis identity is destroyed |
| **Coercion arrows `↑`** | — | **84/300 = 28 %** state, 25/300 statements | the coercion *function* is elided; two different coercions print the same |
| **Universe metavariables `?u.NNNN`** | 188/10,720 = 1.75 % | 3/300 = 1 % | universe unification is unresolved in the print |
| Implicit / instance arguments | 100 % (structural) | 100 % | `pp.explicit` is off; applicability of a premise is decided by exactly these |
| Binder kinds, FVar/MVar identity, elaborated types, `Level` trees, `ldecl` values, defeq/reducibility, ambient section context, `Syntax`/`mdata` | 100 % absent | 100 % absent | see §L5 |
| Short-name ambiguity | 571 of 7,023 short names (**8.1 %**) are owned by ≥2 full names | — | the leak filter and the distractor sampler both key on short names |

Two are decisive on their own. **`⋯` proves the projection is non-injective**: distinct proof
states print identically. **`✝` proves binder identity is unreconstructible**: Lean's own
disambiguating superscripts are display artefacts, not identities.

## L5. Field-by-field availability

| Field | LeanDojo (`random/train.json` + `corpus.jsonl`) | Already captured in `lean_runtime_v2_full` | Needs a fresh Lean run |
|---|---|---|---|
| Elaborated expression trees | **unavailable** | **available** (11 node kinds, 1,574 goal targets measured) | only for new states |
| Resolved constants (+ universe args) | **unavailable**; only the *cited* name string | **available** (`symbol.identity` + `universe_arguments`; `elaborated_external_constant_refs`) | only for new states |
| Local declaration identities | **unavailable** (`✝` names, 83 %) | **available** (21,620 decls with `identity` ⟂ `user_name_diagnostic`) | only for new states |
| Binder identities / kinds | **unavailable** | **available** (4 `BinderInfo` values, `cdecl`/`ldecl`) | only for new states |
| Types | **unavailable** (`corpus.code` is source text, cut at `:=`) | **available** (structured `Type` trees, incl. dependent function types) | only for new states |
| Dependency edges | **partial** — `corpus.imports` file-level only; `build_import_closure` (`premise_selection.py:484`) computes a transitive file bitset | **available** at module level (`transitive_import_modules`, 169 modules on record 0) + `local_context_refs` | term-level premise→subterm edges need elaboration |
| Premise identities | **partial** — syntactic citation only (`annotated_tactic[1]`) | **available** — `external_premise_refs` (elaborated), with `reference_completeness = PARTIAL_TACTICS_WITHOUT_TERMINFO_MAY_HIDE_INTERNAL_USE` | full completeness needs a kernel-level tactic instrumentation Lean 4.10 does not expose |

One caveat that matters for the experiment's oracle: LeanDojo's gold is the **syntactically cited**
premise; the runtime corpus's `external_premises_used` is the **elaborated** premise set. They are
not the same object, and switching substrates silently changes the truth function.

## L6. What a Lean REPL could add, and at what cost

**Availability (inspected, not run).** `/Users/…/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec07…/mathlib4`
is 18 GB with **5,680 `.olean`** files; `Lean4Repl.olean` is **built**;
`lean-toolchain = leanprover/lean4:v4.10.0-rc1`; `elan`, `lake`, `lean` are on `PATH`. Offline
replay is genuinely possible. (`docs/CANONICAL_VNEXT_PILOT.md:148-156` records that a different
audit read the *source-only* checkout with 38 oleans and wrongly concluded otherwise — name the
`runtime_work` path explicitly.)

**What it adds:** everything in the "needs a fresh Lean run" column above, plus a real kernel
oracle for the `legal_transform` family (today **100 % `TIER_B_CONSTRUCTED`, zero Lean-verified**,
`docs/GAME_R_FORMAL_ARENA_V1_SPEC.md:110-113`).

**Cost, at the historical yield.** `docs/CORPUS_STRATEGY.md:173-176` disambiguates the number:
44/100 attempts were *supported* (32 PASS + 11 STATE_MISMATCH + 1 TACTIC_FAIL); the pass rate is
**32/100**. Budget accordingly:

| Target bank | Attempted replays at 32 % | Note |
|---|---|---|
| 190 items (the existing single-premise/single-goal set) | ~594 | no new capture needed at all |
| 1,000 items | ~3,125 | matches the spec's own estimate (`:113`) |
| 5,000 items | ~15,625 | the only recorded timing figure anywhere is ≈130 worker-hours for 100k verified items (`docs/PROJECT_LEDGER.md:1134`), and it is an estimate, not a measurement |
| 63,831 items (parity with today's string family) | **~199,472** | not laptop-feasible |

`docs/CORPUS_STRATEGY.md:513` also records that per-job timing is **NOT FOUND** in the retained
logs, so any replay budget must be *measured on a fresh n ≥ 100 sample before it is committed to*.
That measurement is itself the cheapest possible first experiment (§L7, §Falsification).

## L7. The minimum canonical schema for a real premise-selection Game-R experiment

Game R needs R to be able to vary binder representation, scope representation, identifier system,
dependency locality, type placement and role labels (`GOAL.md:206-215`). Every one of those is a
*structure* that must exist in the state object before a representation can reorganise it. That
fixes the minimum schema. It is not a wish-list: every field below is measured present in
`lean_runtime_v2_full`.

**MINIMUM SCHEMA — `premise-selection-game-r-v1`**

1. **Expression** — recursive node union with at minimum
   `application · lambda · dependent_function · bound_variable(de Bruijn) · local_reference(id) ·
   metavariable_reference(id) · symbol(global id, universe args) · sort(Level) · literal ·
   let · annotated`. *(Enables: tree/DAG/linear reorganisation, compression, canonical ordering.)*
2. **Level** — `zero · succ · max · imax · param · mvar`. *(Enables: type placement,
   redundancy control.)*
3. **Type** — a tree, not a flat string. 84.6 % of real context entries carry compound types
   (`docs/CANONICAL_VNEXT_PILOT.md` G3).
4. **Declaration** — `identity` (stable, opaque) ⟂ `display_name` (mutable), `binder_role`
   ∈ {EXPLICIT, IMPLICIT, STRICT_IMPLICIT, INSTANCE_IMPLICIT}, `declaration_role` ∈ {cdecl, ldecl},
   `type`, optional `value`, `scope_id`. *(Enables: identifier system and binder representation to
   vary — and makes α-renaming a **certified** metamorphic test rather than a regex gamble.)*
5. **Scope forest + goal list** — ordered goals, each naming a scope; explicit focus. Zero, one or
   many goals (17.4 % of real states have zero goals; 11.4 % have more than one).
6. **Metavariable context** — `identity · kind · type · assignment` as one structure (pilot
   G2 ≡ G6).
7. **Premise reference — first class, and this is the load-bearing addition.** Each candidate is
   `{premise_id, resolved global constant identity, universe arguments, its *elaborated* statement
   as a Type/Expression tree, provenance}`. The chosen premise is an action argument of that type.
8. **Dependency edges** — module-level import closure **and** the term-level edges
   `premise_subterm ↔ goal_subterm` that make "dependency locality" (a named R axis) variable.
9. **Provenance / assurance** — source pin, capture mechanism, and an explicit
   `information_accounting` block naming what is PRESERVED / DELEGATED / UNEXPOSED. Without it the
   schema will be misread as complete, which is pilot finding **N5** ("the verifier accepts it"
   carries no information).
10. **Oracle record** — which premise, *by which definition* (syntactic citation vs elaborated
    use), with a kernel-replay flag. Astra's `oracle_evidence.kernel_replay: false` is the right
    shape; the flag must be honest and must be reported with every result.

**Which target?**

| Target | Verdict |
|---|---|
| `arena-canonical-v0.1.0` | **Wrong target. Do not use.** 0/368 lossless; 20.7 % unmappable; one mandatory goal (G1); flat `Binding.type_name` (G3); no `Binding.value` and *no escape hatch* (N2); **no slot for premise refs and `target_ids` restricted to `object_ids ∪ {"goal"}` (N3) — this alone blocks the family**; and `mathematical_hash` covers `schema_version`, so any fix re-hashes the entire project (`CANONICAL_VNEXT_PILOT.md` §2). |
| `releases/TRAINING_LANGUAGE_V0/` (TL0 0.1.0) | **Right target, with one required promotion.** Native for every REQUIRED gap: multi-goal over a scope *forest* (G1+N1), `Obligation.scope_id` (N4), `DeclKind.METAVAR` + `State.substitution` as one structure (G2≡G6), `Type` as a tree (G3), `Decl.value` (N2). `Action` carries `arguments: tuple[Term, ...]`, and `Claim` carries a structured `statement: Term` — so candidate premises *can* be typed objects. **But `SPEC.md` §2 classifies N3 (external premise refs) as `BACKEND_EXTENSION`: premise refs "ride in `Term.attributes` or an `Extension` record".** For this family the premise *is the answer space*; if it is an opaque payload string then R is fixed over exactly the part of the state under test, and Astra's failure mode reappears one level up. **N3 must be promoted from BACKEND_EXTENSION to native for `premise-selection-game-r-v1`.** That is a small, local spec edit — TL0 does not bump `arena-canonical` and does not re-hash the project (`docs/TRAINING_LANGUAGE_V0.md`, "The canonical seam"). |

Two TL0 limitations must be carried into any preregistration:
`SPEC.md` §12(2) — the default `ARENA_VERIFIER` profile flattens `binder_kind` to `free` and
retargets goal actions, so *the honest state and the accepted state differ*; and §12(4) — `tl0.*`
carriers perturb `mathematical_hash`, so one `LossPolicy` must be fixed for the whole experiment.

---

# PART M — the Astra bridge

## M8. What Astra has actually proven (verified by re-running its audits)

Both audits reproduce **byte-identically** (see header). Astra's claims, adjudicated:

| Claim | Verdict | What it actually establishes |
|---|---|---|
| 300 items, one per theorem group, 240/60 split | **TRUE** | `coverage_report.json`: 300 admitted, 300 unique theorem groups, 240/60 |
| 1,500 renderings, 5 codecs | **TRUE** | `parity_report.json`: `original_renderings_checked: 1500` |
| 1,800 permutations | **TRUE** | every cyclic shift of 6 candidates × 300 items; answer follows semantic identity |
| 300/300 private-field noninterference | **TRUE** | poisoning `target_choice_id`, `oracle_evidence`, `provenance`, `audit_metadata` changes no rendered byte |
| `GAME_R_SOURCE_PROJECTION_PARITY_PASS` | **TRUE as stated, and correctly named** | all five codecs decode to a byte-identical ordered inventory of the *visible projection* |
| best visible heuristic 0.4167 | **TRUE**, replayed exactly (25/60) | see §M13 |
| no kernel replays, no elaborated types | **TRUE** | `coverage_report.json`: `kernel_replays: 0`, `elaborated_kernel_types: 0` |

**What Astra proved:** that five serialisation *envelopes* over one frozen, allowlisted, immutable
projection are lossless, deterministic, mutually decodable, private-data-tight and
permutation-robust. That is a real and non-trivial engineering result. Astra says so itself
(`docs/astra/ASTRA_GAME_R_BRIDGE_HANDOFF.md`, final paragraph: *"the bridge is therefore
representation-neutral at the source-projection layer and does not yet support claims about
representation effects on mathematical semantics"*). **This audit confirms Astra's own
self-assessment and finds it, if anything, understated.**

**What Astra did not prove — and the measurement that shows it.** `astra_projection_probe.py`
renders item 0 through all five codecs and measures how much of each rendering is the *same*
`canonical_json` payload:

| codec | rendered bytes | fields carried byte-verbatim | fraction of bytes that are the identical JSON payload |
|---|---|---|---|
| `compact_symbolic` | 1,539 | 6/6 | **97.6 %** |
| `json_ast` | 1,587 | 6/6 | **94.6 %** |
| `structured_english` | 1,628 | 6/6 | **92.3 %** |
| `hml` | 1,654 | 6/6 | **90.8 %** |
| `sexpr` | 1,808 | 3/6 | 6.9 % |

and `astra_invariance_cause.py` extends the check to the whole bank: for **300/300 items × 5/5
codecs**, the Lean context text, the goal text, all six candidate names and all six candidate
statements appear **byte-verbatim** in the rendered output. `renderer_bridge.py:55-71` is the
reason: four of the five codecs are literally `canonical_json(p[key])` wrapped in a different
line prefix (`"Local context: "` vs `"  context := "` vs `"c":`); `sexpr` restructures the outer
record but still embeds the Lean strings verbatim.

**So the five "representations" vary the envelope and never the mathematics.** Of the fifteen R
axes named in `GOAL.md:206-215`, Astra's codecs vary *serialization*, *surface morphology* and a
little *field structure*. They vary **none** of: binder representation, scope representation,
identifier system, dependency locality, type placement, role labels, tree/DAG/linear organisation,
canonical ordering, redundancy, compression. Those are exactly the axes a representation
hypothesis is about. **CONFIRMED. Severity: this is the central limitation of the bridge.**

## M9. Does source-projection parity equal semantic parity? No. The gap, formally.

Let σ ∈ Σ be the Lean proof state and let π_src : Σ → S be Astra's source projection (Lean's
delaborator applied to the goal, plus a lexical source-header extractor,
`source_adapter.py:44-84`). Let {ρ_r}_{r∈R} be the five codecs and δ_r their decoders.

Astra proves, for all σ in the bank and all r, r′ ∈ R:

> **(P1)** δ_r(ρ_r(π_src(σ))) = δ_{r′}(ρ_{r′}(π_src(σ))) = π_src(σ)

i.e. every ρ_r **factors through π_src** and is injective on its image. `information_inventory.py`
implements exactly that: it walks `visible_projection(state)` and compares ordered
(path, type, value) triples.

Semantic parity in `GOAL.md:597-605` requires something strictly stronger:

> **(P2)** for all σ, σ′ ∈ Σ: if π_src(σ) = π_src(σ′) then σ ≡_math σ′ — π_src must be injective
> modulo mathematical equivalence; equivalently, π_src must be a **sufficient statistic** for the
> truth function T(σ) = "which premise does the valid next step cite".

**(P1) ⇏ (P2).** (P1) is a statement about the codecs; (P2) is a statement about the projection.
Five bit-exact re-encodings of a lossy quotient are five bit-exact re-encodings of a lossy
quotient. Formally, Astra establishes parity *on the quotient Σ/ker(π_src)* and says nothing about
whether that kernel is trivial with respect to ≡_math.

**And π_src is measurably non-injective.** `⋯` erases subterms; `✝` erases hypothesis identity;
implicit and instance arguments are never printed; coercion functions are collapsed to `↑`. Two
mathematically distinct σ can therefore print identically. **(P2) is refuted, not merely
unproven.** See §M10.

The correct label for what Astra has is: **R-invariance of a fixed lossy projection.** Astra's own
name for it, `GAME_R_SOURCE_PROJECTION_PARITY_PASS`, is exact.

## M10. **Could all five codecs faithfully reproduce the same INCOMPLETE projection while all omitting important mathematical information?**

**Yes. This is not a hypothetical — it is what the committed artifact does.**
`out/astra_projection_probe.json` and `out/statement_completeness.json`, over the 300-item bank:

| Omission, present in the projection all five codecs reproduce | Count / 300 items | Holdout / 60 |
|---|---|---|
| State contains an **elided subterm `⋯`** — the pretty-printer deleted mathematics | **19 (6.33 %)** | **7 (11.7 %)** |
| State contains **inaccessible `✝` hypothesis names** | **247 (82.3 %)** | 49 (81.7 %) |
| State contains a **coercion arrow `↑`** with the coercion function elided | 84 (28.0 %) | 22 (36.7 %) |
| State contains an **unassigned universe metavariable `?u.N`** | 3 (1.0 %) | — |
| A **candidate statement** itself contains `⋯` | 1 | — |
| A **candidate statement** contains a coercion arrow | 25 | — |
| **Candidate statements that are not closed propositions** — they reference identifiers bound by an ambient `variable`/`section` command that `corpus.jsonl` does not record | **341 / 1,800 statements (18.9 %)**, affecting **178 / 300 items (59.3 %)** | — |

The last row is the most damaging and is a *lower bound* (the measurement counts any identifier
that coincides with any mathlib name component as resolved). Concrete instances taken from the
bank:

* `Int.cast_le` renders as `lemma cast_le : (m : R) ≤ n ↔ m ≤ n` — `m`, `n`, `R` are ambient.
  This is not a proposition; it is a fragment.
* `Polynomial.expand_mul` renders as
  `theorem expand_mul (f : R[X]) : expand R (p * q) f = expand R p (expand R q f)` — `R`, `p`, `q`
  are ambient section variables. `source_signature()` (`source_adapter.py:44`) is explicit about
  this: *"Ambient section variables/notation are not recoverable from corpus.jsonl."*
* `Polynomial.coeff_eq_zero_of_degree_lt : (h : degree p < n) : coeff p n = 0` — `p`, `n` ambient.

Every one of those fragments is rendered byte-identically by all five codecs, and every codec
passes parity. **A parity pass over an incomplete projection is exactly as strong as the
projection. CONFIRMED. Severity: this is the falsification the question asked for.**

## M11. Why α-renaming and independent-context permutation are unsupported on all 300 rows

Not a policy choice and not conservatism about Lean — a **fragment gate that real mathlib cannot
enter**. `research/astra/game_r_premise/invariance.py:31`:

```python
_LOCAL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z_][A-Za-z0-9_]*)*) : (Nat|Int)\n")
```

applied with `re.fullmatch` to **every** context line (`:45`), and `:52-58` additionally requires
the goal to be `⊢ `-prefixed, to contain only `[A-Za-z0-9_⊢\s()+*=<>≤≥≠-]`, to have no
unresolved identifiers, and to contain **no application at all** (`:57`, "even `f x` would need
type/scope resolution").

Measured (`out/astra_invariance_cause.json`), over the 3,800 context lines of the bank:

* **1 of 3,800 context lines** matches the gate.
* Outcome over 300 items: 298 raise *"requires only independent Nat/Int variable declarations"*,
  2 raise *"no supported local declarations"* (empty context). **0 supported.**
* Non-conformance causes: 2,484 lines are typed locals whose type is not `Nat`/`Int`
  (`R : Type u`, `f : R[X]`, …); **1,191 lines carry an inaccessible `✝` name**, which is not a
  legal identifier and therefore can never be renamed by substitution; 109 are `case` labels;
  15 are wrapped continuations.

**Root cause, stated plainly:** the transformation is defined on a binder-free `Nat`/`Int`
arithmetic fragment, and the substrate is type-universe/typeclass-instance mathlib. The two do not
intersect. And the deeper reason the gate had to be that narrow is §L4: in pretty-printed text
**identity *is* spelling**, so any renaming is a guess. In the elaborated corpus (§L3) identity and
spelling are separate fields on 21,620 declarations, and α-renaming becomes a one-line, provably
sound operation. **CONFIRMED.**

## M12. Does failing closed protect correctness while preventing the tests that matter?

**Both, and the trade is currently all cost.** Failing closed is unambiguously correct: a regex
α-renamer over Lean text would capture bound names and silently corrupt dependent types
(`docs/astra/SOURCE_GROUNDED_BRIDGE_AUDIT.md` §3 argues this correctly), and a false
"α-invariance PASS" is worse than no test.

But count what survives. Of the metamorphic battery, only two families execute:

* **option permutation** (1,800 checks) — tests that the *harness* keys the answer to candidate
  identity rather than position. A property of `verify_response`, not of a representation.
* **private-field noninterference** (300) — tests the firewall. Again the harness.

The two tests that would actually probe representation invariance — α-renaming (identifier system)
and independent-context permutation (scope representation, canonical ordering) — are **0/300**.
Those are two of the fifteen R axes in `GOAL.md:206-215`, and they are the two Astra chose to try.
So the bridge currently has **no executed test of any representation invariance of the
mathematics**, only of the plumbing.

Failing closed is therefore protecting a correctness property while the instrument silently
reports a full green board. `parity_report.json` emits `alpha_rename_unsupported: 300` — visible,
to Astra's credit — but the top-level `status` is still
`GAME_R_SOURCE_PROJECTION_PARITY_PASS`. **A reader who sees only the status learns the opposite of
the truth.** Recommendation: any future run must promote the unsupported counts into the status
string (e.g. `PARITY_PASS_METAMORPHIC_COVERAGE_0_OF_2`). **CONFIRMED. Severity: medium-high
(reporting), low (correctness).**

## M13. Is 300 enough for development? Is 60 enough for shortcut estimation? The interval.

**The interval on 0.4167 at n = 60** (`out/n60_power.json`; 25/60 correct, chance 1/6, k=6):

| Interval | 95 % bounds | width |
|---|---|---|
| **Wilson** | **[0.3006, 0.5427]** | **0.242** |
| Clopper–Pearson (exact) | [0.2907, 0.5512] | 0.260 |
| Wilson, Bonferroni over the 25 rules the maximum was taken over (α = 0.002, z = 3.090) | **[0.2451, 0.6111]** | 0.366 |
| Clopper–Pearson, Bonferroni | [0.2301, 0.6219] | 0.392 |

The point estimate is **not** a noise artifact: one-sided binomial p vs chance = 4.2 × 10⁻⁶, and a
Monte-Carlo reference (20,000 draws) for the maximum of 25 independent chance-level rules on n = 60
gives mean 0.266 and **p95 = 0.317**, below 0.4167. The rule is real. But its *value* is known only
to ±0.12 (±0.18 after multiplicity), which is useless as a floor: any ceiling set from it would be
somewhere between 0.30 and 0.62.

Three further reasons 60 is not enough:

1. **The rule ties on 22/60 items (36.7 %)** and is informative on only 43/60. The published
   0.4167 uses "first candidate in the frozen order" tie-breaking. Under random tie-breaking
   (20,000 draws) the same rule scores **mean 0.436, 90 % interval [0.383, 0.483]** — *higher*
   than published. So the reported number is if anything conservative, but it is a number produced
   by a coin-flip on a third of the items.
2. **It is statistically inconsistent with the production measurement of the same rule on the same
   sampler.** Astra uses `LEVELS_BY_NAME["L3_same_module_freq_matched"]`
   (`source_adapter.py:21`). The production gate measures
   `lexical_overlap_name_vs_goal = 0.2420` on **17,513** grouped-holdout L3 items
   (`premise_selection_manifest.json`). Two-proportion test:
   **z = 3.151, two-sided p = 0.0016** (`out/production_vs_astra.json`). 0.2420 lies *below*
   Astra's Wilson lower bound of 0.3006. Either the 60-item estimate is off, or — more likely —
   Astra's extra admission filter changed the population: `source_signature()` admits only
   declarations with an explicit `theorem`/`lemma` header (114,065 of 180,907 declarations;
   49,014 rejected for "requires balanced explicit theorem/lemma type"), and mathlib's naming
   convention makes theorem names *describe their statements*, so filtering to theorem-shaped
   premises selects for exactly the items where lexical name↔goal matching works. **LIKELY, and
   testable cheaply** by re-running the production L3 gate restricted to theorem/lemma golds.
3. **Power.** At n = 60, a paired-free comparison of a Solver against the 0.4167 floor has
   power 0.10 to detect 0.45, 0.23 to detect 0.50, **0.43 to detect 0.55**, 0.64 to detect 0.60.
   To pin the floor to ±0.05 needs **n ≈ 374**; to ±0.02, **n ≈ 2,335**.

**Verdict.** 300 rows are adequate for *plumbing* development — determinism, parity, firewall,
permutation — which is what they were used for and what Astra claims. They are **not** adequate to
establish a shortcut floor, and Astra explicitly declines to claim otherwise
(`shortcut_results.json`: `"qualification_gate_applied": false`, `"numeric_ceiling": null`,
`status: DEVELOPMENT_DIAGNOSTIC_ONLY`). **The artifact's self-labelling is correct; the risk is
that downstream documents will quote 0.4167 as a floor.** It is already quoted without its
interval in `docs/astra/ASTRA_GAME_R_BRIDGE_HANDOFF.md` and `docs/astra/PREMISE_SHORTCUT_AUDIT.md`.

## M14. Were the 60 items selected before the shortcut results were seen?

**Mechanically: the selection cannot depend on the labels. Procedurally: it is not
pre-registered, and cannot be certified from the repository.** Evidence:

* **In favour.** `build_dev_bank.py:118` assigns the partition by
  `stable_rank(seed, "dev-partition", item.provenance["theorem_id"])`, i.e.
  `sha256(seed|"dev-partition"|theorem_id)` — a function of the theorem identity and the seed only.
  Nothing outcome-derived enters it. The comment at `:117` says "Split ranking independent of
  labels", and that is true as written. The split is written into `dev_bank.jsonl` and into
  `development_manifest.json` (240/60), and `shortcut_audit.py:41-53` *honours the declared
  partition* rather than re-deriving one, refusing if a theorem group crosses partitions (`:51`).
  The seed `20260907` is the same value as the production
  `GeneratorConfig.seed` (`premise_selection.py:678`), so it is not a tuned parameter.
  The audit itself fits every counter, lookup table and the MDL rule on the 240 only
  (`shortcut_audit.py:130-155`, `fit_policy` field).
* **Against.** All 25 files — the split code, the bank, the manifest, the shortcut results and the
  docs quoting 0.4167 — arrive in a **single commit**, `5811161 "research: add canonical premise
  Game-R bridge"`, `2026-09-07 14:37:36 +0100`, 11,199 insertions. There is no antecedent artifact,
  no preregistration document, and no mention of Astra in
  `docs/FITNESS_V7_PREREGISTRATION.md`, `docs/PHASE6_PREREGISTRATION.md`, or anywhere in
  `docs/PROJECT_LEDGER.md` before line 1159 (which records the *merge*, after the fact). The
  choices `count=300`, `limit_theorems=5000` and the L3 level are defaults in
  `build_dev_bank.py:52` and `source_adapter.py:21` with no recorded rationale.
* **A material confound that no seed can fix.** `shortcut_audit.py:272` records it honestly:
  *"Source-pool frequencies/same-proof membership may have been used by the upstream distractor
  sampler before development partitioning."* The distractors for the 60 held-out items were sampled
  using frequency and same-proof statistics computed over the whole 5,000-theorem pool — including
  the 60. That is a real, acknowledged information flow from holdout into item construction.

**Classification: LIKELY pre-specified by construction, NOT pre-registered as a procedure, and
partially confounded by pool-level sampling statistics.** For a development diagnostic that is
acceptable. For anything promotable it is not, and Astra's own recommendation
(`shortcut_results.json` → `future_preregistration_recommendation`) says exactly that.

## M15. Are same-proof and same-module distractors hard enough? Can names still dominate?

**They help a great deal and they are not sufficient. Lexical name signal survives every shipped
control.** Production numbers (`research/environments/measurements/premise_selection_shortcuts.json`,
k = 4, chance 0.25), which are the *reason* the tiers were designed as they were:

| distractor policy | best shortcut | mean name-token overlap with state, gold vs distractor |
|---|---|---|
| `uniform_corpus` | 0.8385 | 1.787 vs **0.248** |
| `freq_matched` | 0.7391 | 1.824 vs 0.204 |
| `same_file` | 0.6544 | 1.787 vs 1.254 |
| `same_file_freq_matched` | 0.4890 | 2.005 vs 1.347 |
| `overlap_and_freq_matched` | 0.4489 | 1.269 vs **1.269** |
| `same_proof` | **0.3646** | 1.726 vs 1.361 |

and the shipped ladder (`premise_selection_manifest.json`, k = 6, chance 0.167, n ≈ 17–19 k
grouped holdout):

| level | lexical name↔goal alone | best combined |
|---|---|---|
| L2_standard | 0.2217 | 0.3269 |
| L3_same_module_freq_matched | 0.2420 | 0.3283 |
| L4_high_similarity (k=8, goal-only context) | 0.1877 | 0.2622 |
| ~~L1_cross_module~~ | 0.4446 | **0.6444 — REJECTED** |

Read as a whole, within the same k=4 measurement: moving from uniform-corpus to same-proof
distractors cuts the best shortcut from 0.8385 to 0.3646 — from 3.35× chance to 1.46×. On the
shipped k=6 ladder the lexical rule alone still sits at 1.33–1.45× chance and the *combined*
shallow model at 1.96×. **Lexical name matching does not dominate, but it is never eliminated, and it is the
single largest visible contributor at every rung.** Only `overlap_and_freq_matched` drives the
gold/distractor overlap gap to exactly zero (1.269 vs 1.269) — and that policy is **not** one of
the four shipped tiers. It should be.

The mechanism is structural: mathlib's naming convention deliberately encodes the statement in the
name (`coeff_eq_zero_of_degree_lt`, `pow_dvd_pow_iff`, `expand_mul`). Any premise-selection task
built over mathlib names inherits a real, non-removable lexical channel; the only complete defence
is to stop showing names, or to match overlap exactly. **CONFIRMED.**

## M16. Are the historically exposed LeanDojo evaluation pools usable for final promotion?

**No. Definitively, and more strongly than the manifest admits.**

1. **All four pools were parsed and summarised.** `census_leandojo_heldout.json` (mtime
   `2026-09-07 06:38:34`) contains, for each of `random/{val,test}` and
   `novel_premises/{val,test}`: step counts (4,260 / 4,506 / 6,240 / 6,626 = **21,632 steps**),
   theorem counts, `with_premise_eq1`, `distinct_premises`, `rw_reverse`, multi-goal counts, and a
   top-30 tactic-head histogram.
2. **The exact task was already measured on them.** `premise_selection_shortcuts.json` (mtime
   `06:42:28`) declares its source as `{random,novel_premises}/{val,test}.json` and reports
   six distractor policies × eight heuristics on 2,487 `random` and 3,586 `novel_premises`
   single-premise items — including `novel_premises` `uniform_corpus` at **0.8635**.
3. **The shipped design was chosen afterwards.** Seal at `11:09:59Z`; environment committed at
   `12:44:44`. The four shipped tiers are the measured policies.
4. **`SEALED_SPLITS.json` under-reports this.** Its per-file `reason` for `random/{val,test}` says
   *"a prior audit reports random/val+test were already read (8,766 transitions)"* — but it labels
   `novel_premises/{val,test}` `PROMOTION_OOD` with the reason *"The only defence against solving
   premise selection by recall"*, with **no exposure note**, even though this repository contains
   a shortcut measurement fitted on 3,586 of their items. **CONFIRMED. Severity: high —
   documentation asserts a cleanliness that its own artifacts refute.**
5. **Even a clean pool would not be clean.** The manifest's own `contamination_note` is right:
   mathlib4 is HISTORICALLY_EXPOSED and exposure is transitive through Solver pretraining, and the
   Solvers' training cutoffs are UNRECORDED.

The `novel_premises` splits retain *one* narrow use they can still legitimately serve: a control
for **within-experiment premise recall** (do the gold premises appear in the training pool at
all). They cannot serve as OOD, and no promotion claim may rest on them.

## M17. A fresh split that could be constructed instead — concrete, and costed

Three tiers, cheapest first. All laptop-feasible except where noted.

**Tier 0 — repository-disjoint theorem split within mathlib (free, today).**
Partition mathlib4 by *top-level directory* (`Mathlib/Analysis`, `Mathlib/NumberTheory`, …) using
the domain field already measured in `out/lean_runtime_inventory.json` (27 domains, largest
`Data` = 162 transitions). Hold out whole domains, not theorems, so no premise, module, import
neighbourhood or naming family crosses the boundary — this defeats the same-module and
declaration-order channels *by construction*, unlike a theorem-level split.
Cost: **0 GPU, ~1 CPU-hour** to regenerate items. Honest label: `DEVELOPMENT_STRUCTURAL_OOD` —
still contaminated with respect to Solver pretraining, so it measures *generalisation across
mathematical area*, not novelty.

**Tier 1 — a non-mathlib Lean 4 repository never traced here (the real answer, ~1–2 days).**
`docs/CORPUS_STRATEGY.md` already nominates the candidates and marks them
`RESERVED_EVAL / never-train`: **miniCTX-v2 (non-mathlib)** — explicitly flagged as the OOD
hypothesis — and **PutnamBench (`lean4/`)**. Neither has been traced by this project.
Procedure: trace with the *already built* toolchain
(`external/runtime_work/…/mathlib4`, 5,680 oleans, `Lean4Repl.olean` present,
`leanprover/lean4:v4.10.0-rc1`, `elan`/`lake` on PATH — inspected, not run), capture
`LeanRuntimeState` v2 rather than pretty text, seal by *repository*, and hash before parsing.
Cost: dominated by elaboration, not by the model; budget the **32/100** yield —
≈3,125 attempted replays per 1,000 promoted items, plus the *unmeasured* per-job time that
`CORPUS_STRATEGY.md:513` says must be measured, not guessed.
This is the only tier that yields a defensible `PROMOTION` pool.

**Tier 2 — a second formal system (weeks; only if the representation result survives Tier 1).**
Metamath `set.mm`, already registered as `DEVELOPMENT` and the *only* source that can test pilot
gap G7 (0/368 occurrences in Lean). A representation effect that reproduces across Lean and
Metamath is a claim about mathematics; one that does not is a claim about Lean's delaborator.

**Sealing protocol for whichever tier is used** — derived from what went wrong here:
hash before any parse; record the seal *commit*, not just a timestamp; forbid **design**
decisions informed by the pool, not merely item construction (this is the failure in §M16); and
require the seal manifest to name every artifact that has ever read the file.

---

# The strongest case against the proposed route

Taking the falsification duty seriously, here is the case I would make if I wanted the route
abandoned. I believe items 1–4 are strong and items 5–6 are decisive as stated.

**1. The route's own premise is refuted by its own pilot: there is no lossless path from LeanDojo
to a canonical state.** The proposal reads "real Lean premise selection → semantic extraction".
The extraction cannot happen. LeanDojo gives four string fields per step; `corpus.jsonl` gives raw
source text. 0 of 368 real Lean states map losslessly into the canonical schema, 20.7 % do not map
at all, and pilot gap N3 says the schema has no slot for premise references at all. Any "semantic
extraction" from these files is *reconstruction by parsing pretty-printed output* — the one thing
`HML_V3/research/canonical_ir/LEAN_RUNTIME_STATE_SPEC.md` explicitly forbids
(*"Python never recovers an identity or expression tree from pretty text"*). A parser that
succeeds anyway is a parser that has guessed.

**2. The information the route needs is not merely missing — it is destroyed, at measured rates.**
83.1 % of states carry `✝` names that are not identifiers; 7.9 % carry `⋯` where the printer
deleted a subterm; every state hides implicit and instance arguments, which are exactly what
decides whether a premise applies. 18.9 % of Astra's candidate statements are not closed
propositions. The route proposes to build a *representation-neutral* object on a substrate whose
neutrality was already broken by the delaborator before anyone touched it.

**3. The one working demonstration of the route shows the failure mode in miniature.** Astra
executed the pipeline end to end on 300 real items and got a green board. Yet 300/300 items × 5/5
codecs carry the mathematical content byte-verbatim; both metamorphic tests are 0/300; the answer
space is a name string; and the parity theorem holds over a projection with measured holes. If the
route's output on 300 careful items is "five envelopes around the same string", the route as
specified does not produce a representation experiment.

**4. Even as a capability benchmark it may be measuring mathlib's naming convention.** Lexical
name↔goal overlap alone scores 1.3–1.5× chance at every shipped rung, and 2.5× chance in Astra's
bank. mathlib names *are* statements (`coeff_eq_zero_of_degree_lt`). A Solver that has read mathlib
— and every candidate Solver has — can score well by name recall. Astra's bank is worse than the
production family on this axis, and plausibly *because* its theorem/lemma-header filter selects for
descriptively-named premises (z = 3.15, p = 0.0016 against production L3). The route could easily
produce a benchmark on which the ranking of representations is the ranking of how legible the
premise names are in each.

**5. The route has no clean pool to promote into, and the contamination is design-level, not just
item-level.** All four evaluation pools were parsed; the exact task was measured on them; the
shipped distractor tiers were chosen from those measurements six hours before the seal. This
cannot be undone by not reading the files again. Any result promoted on `novel_premises` is a
result on a pool that shaped the instrument.

**6. The cost curve is wrong.** To reach semantic parity you need elaborated states. Those exist
for **1,150** transitions — **190** with one premise and one goal. Reaching the 63,831 items the
string family already has costs ~199,000 attempted replays at the measured 32/100, on a laptop,
with per-job timing recorded nowhere. So the route's realistic operating point is *hundreds* of
items — which is where §M13 shows the confidence interval is ±0.12 and the power to detect a
10-point effect is 0.43.

**What would make it "merely another capability benchmark."** If R is instantiated as
serialisation envelopes (Astra's five codecs, or JSON vs S-expression vs prose), then Σ, P and the
answer space are all held at "Lean pretty text" and the experiment measures format-parsing
robustness. That is a real property, but it is not the representation hypothesis, and a null result
would license no conclusion about representation. The tell is mechanical and cheap to check: **if
the Lean goal text appears byte-verbatim in every arm, R has not varied.** It does, in 300/300 ×
5/5 of Astra's renderings.

**What would make it fail outright.** (a) The elaborated corpus turns out not to intersect the
premise-citation task at usable volume — already close: 190 items. (b) Replay yield on a fresh
sample comes in below ~20 %, making any semantic bank uneconomic. (c) Alpha-renaming and context
permutation, once *actually* runnable on elaborated states, move Solver accuracy — which would mean
the Solver is reading names, not mathematics, and the whole family is a recall probe. (d) The
representation effect, if any, fails to reproduce across mathematical domains, which a
domain-disjoint split would expose immediately.

**The cheapest experiment that would reveal the failure early.** Three, in order, all CPU-only and
all completable in under a day:

* **E1 — the verbatim test (minutes, already written).** For any proposed arm set, assert that no
  contiguous ≥ 40-character span of the underlying Lean pretty text appears in more than one arm.
  Astra's five codecs fail this 300/300 × 5/5
  (`research/audit/a8_lean/astra_invariance_cause.py`). **Any arm set that fails E1 is not a Game-R
  arm set, and no tournament should be run on it.** This single check would have prevented the
  bridge from being described as a Game-R bridge in the first place.
* **E2 — the elaborated α-renaming probe (hours, no model).** Take the 190 single-premise /
  single-goal elaborated transitions, α-rename every local via `identity` ⟂ `user_name_diagnostic`
  (sound by construction, unlike the regex), and re-run the shortcut suite. If the lexical rules
  survive renaming, they are reading *global premise names*, and the family needs
  `overlap_and_freq_matched` distractors (the only policy that zeroes the overlap gap) before any
  Solver call. If they collapse, the family is healthier than the string version and the route is
  worth funding.
* **E3 — the replay-yield measurement (a few hours of CPU, no model).** Attempt fresh replay of
  n = 100 new transitions against the built `runtime_work` checkout and *measure* both pass rate and
  wall time. Every cost estimate in this programme currently rests on a single historical 32/100
  with no recorded timing. If the yield is materially below 32 % or the per-job time is large, the
  semantic route is dead on a laptop and the honest move is to run a *domain-disjoint capability*
  experiment on the string family and stop calling it Game R.

E1 costs minutes and is dispositive about whether the route is a representation experiment at all.
It should run before anything else.

---

# Classified flaw list

| ID | Finding | Class | Severity | Effect |
|---|---|---|---|---|
| **L-1** | Premise-selection records are strings (`state_before: str`, `PremiseOption(str, str, str)`); 0 canonical references | CONFIRMED | Blocking (Game R only) | R is fixed at Lean's pretty-printer; no representation effect is expressible |
| **L-2** | LeanDojo supplies four string fields per step and raw source per declaration; no elaborated semantics anywhere | CONFIRMED | High | "semantic extraction" from these files is parsing, i.e. guessing |
| **L-3** | Pretty-printed states are provably lossy: 83.1 % `✝`, 7.9 % `⋯`, 1.75 % `?u.`, implicits/instances never printed | CONFIRMED | High | semantic parity (`GOAL.md` §13) is refuted, not merely unproven |
| **L-4** | `corpus.jsonl` headers are not closed propositions: 18.9 % of candidate statements carry ambient free identifiers (59.3 % of items) | CONFIRMED | High | the "complete admitted source header" assurance is weaker than it reads |
| **L-5** | All four sealed pools were parsed and the premise-selection task measured on them; the shipped distractor design followed 6 h later | CONFIRMED | **Critical** | no promotion claim can rest on these pools; contamination is design-level |
| **L-6** | `SEALED_SPLITS.json` records no exposure for `novel_premises/{val,test}` although this repo contains a shortcut fit on 3,586 of their items | CONFIRMED | High | a document asserts cleanliness its own artifacts refute |
| **L-7** | The elaborated substrate exists but holds 1,150 transitions / **190** single-premise single-goal | CONFIRMED | High | realistic semantic banks are hundreds, not tens of thousands, of items |
| **L-8** | `arena-canonical-v0.1.0` cannot hold this family (N3: no premise-ref slot, `target_ids` restricted); 0/368 lossless | CONFIRMED | Blocking | rules the frozen schema out as the target |
| **L-9** | TL0 classifies premise refs as `BACKEND_EXTENSION`, i.e. an opaque carrier | CONFIRMED | Medium | must be promoted to native, else R is fixed over the answer space |
| **L-10** | Replay yield 32/100 (44 = 32 PASS + 11 STATE_MISMATCH + 1 TACTIC_FAIL); per-job timing NOT FOUND | CONFIRMED | Medium | ~199 k attempted replays to match the string family's scale |
| **M-1** | Astra proves R-invariance of a fixed lossy projection, not semantic parity | CONFIRMED | **Critical** | (P1) ⇏ (P2); parity on a quotient is parity on a quotient |
| **M-2** | 300/300 items × 5/5 codecs carry context, goal, names and statements **byte-verbatim**; 4 of 5 codecs are ≥ 90 % identical JSON | CONFIRMED | **Critical** | the codecs vary the envelope, never the mathematics; 0 of the 15 R axes that matter |
| **M-3** | The parity-passing projection provably omits mathematics: 19/300 `⋯`, 247/300 `✝`, 84/300 `↑`, 341/1800 open statements | CONFIRMED | **Critical** | direct answer to the key falsification question: **yes** |
| **M-4** | Both metamorphic tests are 0/300; the gate admits binder-free `Nat`/`Int` only; **1 of 3,800** context lines matches | CONFIRMED | High | no executed test of any representation invariance of the mathematics |
| **M-5** | 0.4167 at n = 60: Wilson [0.301, 0.543]; Bonferroni-25 [0.245, 0.611]; ties on 22/60 | CONFIRMED | High | unusable as a floor; must never be quoted without its interval |
| **M-6** | 0.4167 is inconsistent with production L3's 0.2420 on 17,513 items (z = 3.15, p = 0.0016) | CONFIRMED (discrepancy) / LIKELY (mechanism: theorem-header filter selects descriptive names) | High | Astra's bank is probably *easier* for lexical rules than the family it samples from |
| **M-7** | The 60-row holdout is label-independent by construction but not pre-registered; split, results and docs land in one commit; distractors were sampled using pool-level statistics that include the holdout | LIKELY / acknowledged confound | Medium | acceptable for a development diagnostic, not for promotion |
| **M-8** | Same-proof / same-module distractors cut lexical shortcut ~0.84 → ~0.24 but never remove it; only the unshipped `overlap_and_freq_matched` zeroes the gap | CONFIRMED | Medium | mathlib naming is a permanent channel; consider adding that tier |
| **M-9** | `status: GAME_R_SOURCE_PROJECTION_PARITY_PASS` is emitted alongside `alpha_rename_unsupported: 300` | CONFIRMED | Medium | a reader of the status alone learns the opposite of the truth |
| **M-10** | 300 items drawn from the first 5,000 theorems of one file; 300 of 2,146 attempted theorems (14.0 %); no representativeness claim | CONFIRMED (self-declared) | Low-Medium | fine for plumbing, not a population sample |

**Nothing in this audit refutes a claim Astra actually makes.** Every Astra number replayed
exactly, and its handoff already states the semantic gap in its own words. The exposure is that
its correct, carefully-scoped label — *source-projection* parity — is one adjective away from
being read as the thing the programme needs, and that adjective is doing all of the work.
