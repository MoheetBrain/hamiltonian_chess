# Language Meta-Genome V0 — specification

**Status: `DESIGN_SPECIFICATION_NOT_IMPLEMENTED`.**

This document specifies the successor to the fourteen-gene `LanguageGenome`. It is a design, not
an implementation. **No code in `arena/genome/`, `arena/languages/` or `arena/model_view/` was
changed to produce it**, and the current genome and its eight seeds are not deleted, edited or
deprecated by this document. Nothing here is a scientific result; it makes no claim that any
language reasons better than any other.

It answers item 2 of `docs/HAMILTONIAN_CHESS_META_GOAL.md` §6: *"a language meta-genome wide
enough that a mutation can change the ontology, the state topology, the lexicon and the action
granularity — not only the skin."*

Everything in §1 is a measurement, reproduced against the code in this worktree. Everything from
§3 onward is design and is labelled as such.

---

## 1. Diagnosis — why eight seeds are not eight design points

### 1.1 The finding being explained

`docs/PHASE8_SALVAGE_HANDOFF.md` §3.2, from `artifacts/reports/precondition_parity_audit.json`:

- `L3_JSON_AST` vs `L6_GRAPH_TRIPLES`: **e1_coverage = 0.9860** at stratum `P20`
  (`overall_worst_pairs_all_eight.e1_coverage_max_direction`). The audit defines e1_coverage as
  *"fraction of arm X's state characters inside a 40-char window that occurs verbatim in arm Y"*.
- `L0_STRUCTURED_ENGLISH` vs `L3_JSON_AST`: **seqmatch_ratio = 0.8227** at `P09`.

### 1.2 The mechanism, read out of the code

The hypothesis in the brief is correct, and the code is more specific than the hypothesis.

**(a) There is exactly one payload tree, and every phenotype must return it byte-for-byte.**

`GenomePhenotypeLanguage._encode_payload` (`arena/languages/phenotype.py:292-296`) begins from
`payload`, which is `state_to_payload(state)` — the canonical dict produced by
`CanonicalState.to_dict()` and validated by `arena/languages/_wire.py:validate_state_payload`.
The reverse path is locked by `_wire.py:payload_to_state`:

```python
normalized = json.loads(json.dumps(state.to_dict(), ...))
if normalized != validated:
    _fail("$", "payload is not in canonical wire form")
```

and by `_wire.py:_dict`, which rejects a payload with **missing or extra** fields
(`f"field mismatch; missing={...}, unknown={...}"`). So a phenotype is constrained to be a
*bijection back to one fixed dict with one fixed key set*. It is architecturally incapable of
omitting a concept, adding a concept, or changing what is in the tree. The module docstring says
so plainly: *"Its transformations are presentation changes only."* That is not a bug — it is the
safety property that makes the semantic gate work. It is also the reason the genome can only
change the skin.

**(b) The genes are five presentation dials over that fixed tree.** All of `phenotype.py`'s
gene-dependent behaviour is:

| Dial | Code | What it can do |
|---|---|---|
| key renaming | `_role_map` `:74-105` | rewrite the 46 known key names |
| type marker | `_type_encode` `:113-129` | wrap `{op,sort,…}` and write one of four **string literals**: `"typed"`, `"declared"`, `"hint"`, `"refinement"` |
| binder shuffle | `_binding_encode` `:132-151` | keep the 5-field record, or emit its 5 fields in one of three orders |
| top-level order | `_ordered_payload` `:185-196` | one of four **permutations** of `STATE_FIELD_ORDER` (identity / sorted / priority / reversed) |
| encoder + envelope | `_grammar_encode` `:199-224`, `_wrap` `:238-246` | three encoders, four envelope strings |

Note what `_ordered_payload` is: `{key: payload[key] for key in order}`. Same keys, same values,
same subtrees — a permutation. And `_type_encode`'s four policies differ **only in the value of
`form`**; every other byte is identical.

**(c) `_grammar_encode` has three branches, not eight.** `S_EXPRESSION` → `sexpr_encode`;
`PREFIX`/`HYBRID` → `typed_prefix_encode`; **everything else** → `json.dumps`. So
`labelled-linear`, `json-ast`, `postfix`, `graph-triple` and `symbolic` — five of the eight
`GrammarFamily` values, and four of the eight seeds — are the *same JSON encoder*. The parity
audit's own `surface_classes` block records this independently: `encoder_class` is `"json"` for
L0, L3, L5 and L6; `"typed_prefix"` for L1, L4 and L7; `"sexpr"` for L2 alone.

**(d) L3 and L6 additionally share their role map.** `_role_map` branches on
`redundancy == COMPRESSED`, `token_policy ∈ {SYMBOLIC, COMPACT}`, and `morphology`. L3 and L6 are
both `HIGH_EXPLICIT` + `ROLE_LABELLED` + `STRUCTURAL_ROLE`, so they produce a **byte-identical
key table**. Measured across the seeds:

```
identical role map: ['L0_STRUCTURED_ENGLISH', 'L4_TYPED_PREFIX']
identical role map: ['L3_JSON_AST', 'L6_GRAPH_TRIPLES']
```

Eight genomes → six distinct role maps → three encoder classes.

**Therefore L3 and L6 differ in exactly four things:** the envelope string (`ARENA_TREE[` vs
`STATE ROOT ->`), the `GRAMMAR=` declaration line, the literal `"typed"` vs `"declared"` at each
typed node, and a **reversal of the top-level key order**. Every subtree — every assumption, every
object, every action — is byte-identical. Because pretty-printed JSON keeps each subtree
contiguous, a top-level reordering leaves long verbatim spans intact, which is precisely what a
≥40-character-window statistic measures. 0.986 is not an accident; it is the arithmetic
consequence of "same encoder, same key table, permuted order".

### 1.3 Independent reproduction

Reproduced in this worktree with `.venv/bin/python`, rendering a synthetic 20-premise state
(20 assumptions / 20 objects / 20 bindings / 4 obligations / 4 evidence nodes / 4 actions,
43,335 characters through L3) through `GenomePhenotypeLanguage` for all eight seeds, and
recomputing the audit's e1_coverage statistic (40-character windows, max direction):

| pair | e1_coverage |
|---|---|
| `L3_JSON_AST` \| `L6_GRAPH_TRIPLES` | **0.988** |
| `L0_STRUCTURED_ENGLISH` \| `L6_GRAPH_TRIPLES` | 0.183 |
| `L0_STRUCTURED_ENGLISH` \| `L3_JSON_AST` | 0.179 |
| `L1_CURRENT_HML` \| `L7_HYBRID_ROLE_LABELLED` | 0.049 |

0.988 against the committed audit's 0.986 on its own generator: the mechanism reproduces.

### 1.4 The sharper, previously quantified-only-in-prose result: most mutations are no-ops

`docs/ROUTE_B_PARITY_AUDIT.md` §1 already records that **five of the fourteen gene families are
inert** (`alphabet`, `composition`, `obligations`, `evidence`, `error_locality`), corroborated by
`arena/experiments/game_r_mutant_audit.py:189-199`'s `PHENOTYPE_GENES` tuple, which lists exactly
nine. That is prior art and this document does not claim it. Confirmed here by grep: those five
enums are imported nowhere outside `arena/genome/{genes,seeds,schema,__init__}.py`.

What has not previously been quantified is the effect on the **mutation neighbourhood**, which is
what the outer loop actually spends its budget on. Enumerating every single-gene child of
`L3_JSON_AST` that passes `validate_genome`, and rendering both the state and an action option:

| gene | legal single-gene alternatives | changes state bytes | changes option bytes |
|---|---|---|---|
| alphabet | 2 | 0 | 0 |
| token_policy | 0 | — | — |
| morphology | 4 | 4 | 4 |
| grammar | 6 | 6 | 6 |
| composition | 3 | 0 | 0 |
| types | 3 | 3 | 3 |
| binders | 3 | 3 | 0 |
| state | 1 | 1 | 0 |
| actions | 3 | 0 | 3 |
| obligations | 3 | 0 | 0 |
| evidence | 2 | 0 | 0 |
| serialization | 0 | — | — |
| redundancy | 2 | 2 | 2 |
| error_locality | 3 | 0 | 0 |
| **total** | **35** | | |

**Thirteen of the thirty-five legal single-gene children of `L3_JSON_AST` are byte-identical
clones of their parent** — same state bytes, same option bytes. Two further families
(`token_policy`, `serialization`) have *zero* legal alternatives from L3, pinned by
`DEPENDENCY_CONSTRAINTS`. So 37% of L3's mutation neighbourhood is a no-op, and an outer loop
sampling uniformly over gene families would spend roughly a third of its Solver budget running a
paired causal assay between a genome and its own byte-for-byte twin.

Also visible in the table: `binders` and `state` change the state render but not the option
render, and `actions` does the reverse. `render_action_choice` (`phenotype.py:307-318`) emits only
`action.arguments` — it discards `operation`, `target_ids`, `warrant`, `preconditions` and
`generated_obligations`. The Solver's action is "pick one of k candidate results". This
corroborates `docs/HAMILTONIAN_CHESS_META_MDP.md` §7 question 3: **the action-granularity gene is
inert because the action space is inert.**

### 1.5 The diagnosis in one sentence

The genome is a *codec* genome over a *fixed ontology*: `CanonicalState` hard-codes which concepts
exist, `_wire.py` hard-codes that all of them must be present and none may be added, and the
fourteen genes select among a handful of key-naming, ordering, bracketing and wrapping choices
over that immovable payload. The eight seeds collapse because there was never more than a
low-dimensional skin to vary — and the two seeds that collapse hardest are the two whose skin
choices happen to coincide.

---

## 2. What the current fourteen-gene genome gets right

It is not worthless. Five things in it are load-bearing and the meta-genome must inherit, not
replace, them.

1. **Content-addressable identity with ancestry.** `LanguageGenome.genome_hash` (the gene vector)
   and `candidate_hash` (gene vector + ancestry + display name) are separated deliberately
   (`arena/genome/schema.py:137-151`), and `derive_candidate_id` makes a child's ID a deterministic
   function of `(parent_ids, genes)`. Reproducibility is structural, not conventional.
2. **Mutation with provenance, already built and already strict.** `MutationProposal` carries
   parent, operator, `GeneChange(gene, from_value, to_value)`, hypothesis, expected benefit,
   soundness risk, evaluation tier, impact class and scope; `proposal_id` commits to all of it;
   `apply_mutation` refuses a *stale* proposal (`f"stale proposal for {gene}: expected …, found …"`).
   `MutationHistory` is append-only and refuses duplicate results. **The causal-assay requirement
   for single-gene deltas is already satisfied at the bookkeeping layer.** The meta-genome needs a
   wider gene space, not a new provenance system.
3. **Declared, machine-readable gene dependencies.** `DEPENDENCY_CONSTRAINTS` encodes eight
   real constraints with rationales and rejects illegal genomes *before* evaluation. This is the
   right shape for a much larger space.
4. **Targeted evaluation planning.** `GENE_AFFECTED_TESTS` maps each gene to the test slices it
   can break, and `required_impact_class` escalates the evaluation tier automatically. A wide
   meta-genome needs this more, not less.
5. **A hard, fail-closed truth boundary that demonstrably works.** `ModelViewCompiler.validate`
   refuses a render that does not recover `mathematical_hash`; `arena/verifier/**` and
   `arena/canonical/**` import nothing from `arena/genome`, `arena/languages` or
   `arena/model_view` (verified by grep in this worktree). The layer A/B boundary of the meta-goal
   is real code today.

And one thing the *project* got right that the genome did not: `ContentGenome` /
`derive_truth_view` (`arena/model_view/`) is a working escape hatch from the fixed-payload trap.
It emits `DerivedRelation`s with `witness_hashes` and a `derivation_rule`, plus an explicit
`omissions` list, into a channel that is **not** subject to the wire validator. §5 and §7 build on
it.

---

## 3. `LanguageMetaGenomeV0` — the specification

### 3.0 Shape and invariants of the container

```
LanguageMetaGenomeV0
  candidate_id            str, content-addressed as today
  parent_ids              tuple[str, ...]
  track                   SearchTrack               (reused unchanged)
  O: OntologyGenes        per-concept explicitness
  S: TopologyGenes        relational layout
  G: GrammarGenes         syntax and binding
  M: LexiconGenes         morphology and word-formation
  I: InterfaceGenes       serialization  (≈ today's genome)
  A: ActionGenes          reasoning action protocol
  W: WorkspaceGenes       Solver-writable scratch region   (DEFERRED in V0)
  tau: TokenizerGenes     DEFERRED / frozen in V0
  schema_version          "arena-language-meta-genome-v0.1.0"
```

`W` is included because `docs/HAMILTONIAN_CHESS_META_GOAL.md` §7a names *workspace* as one of the
seven axes of the surviving contribution. It was absent from the brief's family list and from the
first draft of this document; adding it is a correction, not a flourish. Its genes are specified
in §3.6a and every one of them is `SUBSTRATE_BLOCKED` in V0.

Rules that apply to every family:

- **Every gene is a small, named, ordinal-or-nominal enum.** No free-form strings, no numeric
  ranges. This is what makes a single-gene delta legible to the causal assay and hashable.
- **Every gene declares an `ACTIVE` / `DEFERRED` status in V0.** A `DEFERRED` gene is present in
  the schema, serialized, hashed and provenance-tracked, but is pinned to its default and the
  Architect may not propose a change to it. This keeps the data schema stable so that a fitness
  memory recorded in V0 is still readable when a family is activated.
- **Every gene declares an `ImpactClass`** in the existing vocabulary (`SURFACE_ONLY`,
  `STRUCTURAL_SEMANTIC`, `CANONICAL_SEMANTIC_EXTENSION`) and a **`RenderabilityStatus`**
  (new): `RENDERABLE` (a codec path exists), `RENDERER_PENDING` (legal genome, no codec — the
  existing `GENOME_VALIDATED_RENDERER_PENDING` state from `docs/LANGUAGE_GENOME.md`), or
  `SUBSTRATE_BLOCKED` (no codec is possible on the current substrate; needs the trajectory world
  or the TL0 route).
- **Provenance is unchanged**: `MutationProposal`/`GeneChange`/`MutationRecord` extend to
  `(family, gene, from, to)` and nothing else changes.

### 3.1 O — reasoning ontology

**The design requirement the brief is emphatic about: a language must be able to OMIT a concept,
not merely to include it in a different shape.** O is therefore *not* a set of feature flags and
*not* a list of mandatory primitives. It is one gene per candidate concept, over a four-valued
ordinal domain that includes absence:

| Value | Meaning | Legality |
|---|---|---|
| `ABSENT` | the concept does not appear in the observation at all | legal **only** if the concept is deterministically derivable from what remains, by a declared rule (§5) |
| `IMPLICIT` | the information is present but carries no distinguishing marker; the reader must infer the role | always legal |
| `EXPLICIT_TAGGED` | given a distinguished label/role inside a shared container | always legal |
| `EXPLICIT_CONTAINER` | given its own addressable section, with its own identifiers | legal if `G.identifiers` can address it |

Default for every O gene: `EXPLICIT_TAGGED` (this is what the canonical schema does today, and
starting at the incumbent is deliberate — see the meta-goal's "English is the incumbent organism").

**Candidate concepts.** These are *candidate gene values, not mandatory primitives*. The system's
job is to discover, per concept, whether explicitness helps.

| Gene | Concept | V0 status | Notes |
|---|---|---|---|
| `O.fact` | established fact | **ACTIVE** | `CanonicalState.established_facts` |
| `O.assumption` | assumption / premise | **ACTIVE** | `assumptions`; today's `premise_projection` |
| `O.obligation` | open obligation | **ACTIVE** | `obligations`; today's `obligation_projection` |
| `O.dependency` | dependency edge | **ACTIVE** | today's `dependency_projection` |
| `O.evidence` | evidence node | **ACTIVE** | today's `evidence_projection` |
| `O.goal` | goal | **ACTIVE** | today's `action_goal_projection` |
| `O.provenance` | who/what licensed a step | DEFERRED | exists as `EvidenceNode.authority`; only `LOCAL_PROVENANCE` today |
| `O.warrant` | the rule invoked | DEFERRED | exists as a bare `CanonicalAction.warrant: str`, never rendered as an option field |
| `O.definition` | definition vs. fact | DEFERRED | **not in `CanonicalState`**; exists as `TL0 ClaimRole.DEFINITION` |
| `O.subgoal` | decomposed goal | DEFERRED | **not in `CanonicalState`** (one `goal: CanonicalExpression`); exists as TL0's `Goal` tuple + scope forest |
| `O.branch` | open alternative | DEFERRED | not represented anywhere; needs horizon > 1 |
| `O.failure` | abandoned path | DEFERRED | not represented anywhere; needs horizon > 1 |
| `O.counterexample` | refuting witness | DEFERRED | `VerificationStatus.REFUTED` exists; no witness object |
| `O.conjecture` | unproved proposal | DEFERRED | ≈ `TL0 Status.PROPOSED` |
| `O.epistemic_state` | per-item certainty | DEFERRED | bare `status: str` today; `TL0 Status` is a real six-valued enum |

The DEFERRED rows are not decoration: each names the concrete artifact that would have to carry
the concept. **Six of the nine deferred concepts already exist in
`releases/TRAINING_LANGUAGE_V0/core.py`** (`Status`, `DeclKind`, `ClaimRole`, multi-`Goal`, scope
forest, `Obligation.scope_id`). That is the migration route (§6), and it is why the answer to
"how do we make subgoals first-class" is *not* "bump `arena-canonical-v0.1.0`", which
`docs/CANONICAL_VNEXT_PILOT.md` §2 forbids because it re-hashes every state in the project.

### 3.2 S — state / relational topology

Where O says *whether* a concept is shown, S says *where it is shown relative to everything else*.
This is the family that directly attacks the collapse finding, because e1_coverage is an
adjacency statistic.

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `S.topology` | `SEQUENCE`, `TREE_MIRROR`, `DAG`, `HYPERGRAPH` | `TREE_MIRROR` | **ACTIVE** (`SEQUENCE`, `TREE_MIRROR`, `DAG` renderable; `HYPERGRAPH` `RENDERER_PENDING`) |
| `S.organising_centre` | `SCHEMA_ORDER`, `GOAL_CENTRED`, `DEPENDENCY_CENTRED`, `BRANCH_LOCAL`, `RECENCY` | `SCHEMA_ORDER` | **ACTIVE** except `BRANCH_LOCAL` (`SUBSTRATE_BLOCKED`, needs branches) |
| `S.locality` | `GLOBAL`, `WINDOWED_K`, `OWNER_LOCAL`, `ACTION_LOCAL` | `GLOBAL` | **ACTIVE** — generalises today's `*_projection` locality values |
| `S.temporal` | `FULL_STATE`, `DELTA_PLUS_CONTEXT`, `CHANGED_RELATIONS_ONLY` | `FULL_STATE` | **ACTIVE** — this *is* today's `state_delta_projection` |
| `S.repetition` | `REPEAT_VERBATIM`, `REFERENCE_BY_ID`, `HASH_ELIDED` | `REPEAT_VERBATIM` | **ACTIVE** |

`S.organising_centre` is the single most important new gene in V0 and §4 works it through.

### 3.3 G — grammar and binding

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `G.family` | `LABELLED_LINEAR`, `PREFIX`, `INFIX`, `POSTFIX`, `S_EXPRESSION`, `TYPED_BLOCK`, `GRAPH_SERIAL`, `HYBRID` | `LABELLED_LINEAR` | **ACTIVE** for the three that have encoders (`json`, `sexpr`, `typed_prefix`); `INFIX`, `POSTFIX`, `TYPED_BLOCK`, `GRAPH_SERIAL` are `RENDERER_PENDING` — **today they silently alias JSON and that is the defect §1.2(c) names** |
| `G.identifiers` | `NAMED`, `INDEXED`, `LOCAL_ONLY`, `CONTENT_ADDRESSED` | `NAMED` | **ACTIVE** |
| `G.binders` | `NAMED_LEXICAL`, `STRUCTURAL_ID`, `LOCALLY_NAMELESS`, `EXPLICIT_BINDER_FORM` | `STRUCTURAL_ID` | **ACTIVE** (first three inherited from `BinderPolicy`) |
| `G.scope_marking` | `NONE`, `IMPLICIT_NESTING`, `EXPLICIT_DELIMITER`, `EXPLICIT_SCOPE_ID` | `IMPLICIT_NESTING` | **ACTIVE** |
| `G.types` | `EXPLICIT_EVERY_USE`, `DECLARATION_ONLY`, `INFERRED`, `REFINEMENT` | `EXPLICIT_EVERY_USE` | **ACTIVE**, inherited — but see §8: today these four differ by one string literal |

**A hard rule for G, forced by §1.2(c):** a `G.family` value may only be `ACTIVE` if it has its
own encoder. Aliasing an unimplemented grammar onto JSON is what manufactured the L3/L6 collapse,
and the meta-genome must make that a validation error rather than a silent fallthrough.

### 3.4 M — morphology and lexicon

A first-class research axis, and the one where the owner's instruction is explicit in **both**
directions: do not assume `APPLY`/`CREATE`/`TRANSFORM`/`INTRODUCE` are good primitives, and do not
assume invented symbols are better. The design must let evaluation decide, which means M's values
must be *symmetrically* available and none of them privileged by the schema.

The implementation device: today's `_role_map` is already a lexicon table computed from three
genes. Generalise it into a **declared, versioned `Lexicon` value** — the same trick TL0 uses for
domain vocabulary (`releases/TRAINING_LANGUAGE_V0/libraries.py`, where a `Library` is a *value*
that adds no production and no code path). A lexicon swap then costs zero codec work.

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `M.register` | `NATURAL_ENGLISH`, `CONTROLLED_ENGLISH`, `FORMAL_ENGLISH`, `CONVENTIONAL_MATH_SYMBOLS`, `ARBITRARY_ATOMS`, `COMPACT_ABBREVIATION`, `INVENTED_MORPHEMES`, `HYBRID` | `CONTROLLED_ENGLISH` | **ACTIVE** |
| `M.composition` | `ATOMIC`, `PREFIX_ROLE`, `SUFFIX_ROLE`, `CIRCUMFIX`, `AGGLUTINATIVE` | `PREFIX_ROLE` | **ACTIVE** (first three inherited from `Morphology`) |
| `M.role_marking` | `NONE`, `POSITIONAL`, `AFFIX`, `SEPARATE_TAG` | `AFFIX` | **ACTIVE** |
| `M.lexicon_id` | a registered `Lexicon` value id + version | `arena-lexicon-en-v0` | **ACTIVE** |
| `M.length_class` | `LONG`, `MEDIUM`, `SHORT`, `MINIMAL` | `MEDIUM` | **ACTIVE**, and **mandatory as a covariate** (§8) |

`M.length_class` is not a research axis; it is a control. Register and length are physically
entangled (invented morphemes fragment into more tokens than English words), and without an
explicit length gene an M result is uninterpretable. §8 states plainly that V0 still cannot fully
separate them.

### 3.5 I — serialization / interface

**This family is the current fourteen-gene genome, and it is retained essentially unchanged.**
Saying so is the honest accounting: the existing genome is a good *I* genome and a bad *everything
else* genome.

| Gene | Inherited from | Default | V0 status |
|---|---|---|---|
| `I.alphabet` | `Alphabet` | `ASCII` | **ACTIVE** — but currently inert; activating it means writing the codec branch that does not exist |
| `I.envelope` | `SerializationPolicy` | `TREE` | **ACTIVE** |
| `I.redundancy` | `RedundancyPolicy` | `MEDIUM` | **ACTIVE** |
| `I.error_locality` | `ErrorLocalityPolicy` | `EXPLICIT_DELIMITERS` | **ACTIVE** — currently inert |
| `I.token_shape` | `TokenPolicy` | `ROLE_LABELLED` | **ACTIVE** — overlaps `M`; see §8 |

I covers: character repertoire, envelope/wrapping, whitespace and key compression, delimiter and
checksum conventions, and token spelling. It does **not** cover — and never covered — which
concepts exist, where they sit relative to each other, what the lexicon means, or what an action
is. Those are O, S, M and A.

### 3.6 A — reasoning action protocol

**Action granularity is a gene.** The design must not declare the finest decomposition "more
mathematical"; a coarse action may well be better for a pretrained Solver, and that is an
empirical question.

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `A.granularity` | `MONOLITHIC` (`APPLY_THEOREM`), `PAIRED` (select → commit), `DECOMPOSED_5` (`SELECT_THEOREM → MATCH_PREMISE → INSTANTIATE_BINDERS → GENERATE_OBLIGATIONS → COMMIT_TRANSITION`), `SOLVER_CHOSEN` (the Solver picks its own grain per step) | `MONOLITHIC` | **DEFERRED — `SUBSTRATE_BLOCKED`** |
| `A.form` | `FREE_TEXT`, `TYPED_ACTION`, `VERB_TARGET_ARGS`, `RULE_PREMISE_CONCLUSION` | `TYPED_ACTION` | **ACTIVE** (inherited `ActionPolicy`; affects option bytes only) |
| `A.target_binding` | `IMPLICIT`, `TARGET_ID`, `TARGET_BLOCK` | `TARGET_ID` | **ACTIVE** — this is today's `action_goal_projection` |
| `A.precondition_display` | `HIDDEN`, `LISTED`, `CHECKED_OFF` | `LISTED` | **ACTIVE** |
| `A.obligation_emission` | `SILENT`, `LISTED_AFTER`, `LISTED_INLINE` | `LISTED_AFTER` | **ACTIVE** |
| `A.failure_protocol` | `NONE`, `REPORT_STUCK`, `REPORT_STUCK_WITH_REASON`, `BACKTRACK` | `NONE` | **DEFERRED — `SUBSTRATE_BLOCKED`** |

`A.granularity` and `A.failure_protocol` are the two genes with the highest hypothesised
long-horizon value and **zero measurable effect on the current substrate**, because the action
space is "pick one of k options" and `render_action_choice` emits only `arguments`. They are
specified now — so that the fitness-memory schema is stable — and pinned until the verified
trajectory world of `docs/HAMILTONIAN_CHESS_META_MDP.md` §1 exists. Activating them earlier would
generate provenance for a variable that cannot move.

### 3.6a W — workspace

Everything above concerns how the *state* is presented to the Solver. `W` concerns whether the
language gives the Solver a region it may **write into** — a scratchpad, a goal stack, a notes
block that persists across steps — and what the language obliges it to record there.

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `W.presence` | `NONE`, `EPHEMERAL_SCRATCH`, `PERSISTENT_NOTES`, `STRUCTURED_WORKSPACE` | `NONE` | **DEFERRED — `SUBSTRATE_BLOCKED`** |
| `W.schema` | `FREE_TEXT`, `TYPED_SLOTS`, `SAME_AS_STATE` | `FREE_TEXT` | **DEFERRED — `SUBSTRATE_BLOCKED`** |
| `W.obligation` | `OPTIONAL`, `REQUIRED_PER_STEP`, `REQUIRED_ON_BRANCH` | `OPTIONAL` | **DEFERRED — `SUBSTRATE_BLOCKED`** |
| `W.persistence` | `STEP`, `TRAJECTORY`, `PROBLEM` | `STEP` | **DEFERRED — `SUBSTRATE_BLOCKED`** |
| `W.verification` | `UNVERIFIED_ANNOTATION`, `CHECKED_AGAINST_KERNEL` | `UNVERIFIED_ANNOTATION` | **DEFERRED — `SUBSTRATE_BLOCKED`** |

Blocked for the same reason as `A.granularity`: with a maximum horizon of 1 there is nothing for a
workspace to persist across, and with an action space of "pick one of k" there is nothing to write.

`W.verification` carries a truth hazard the other families do not, and it must be recorded now
even though the gene is pinned: **anything the Solver writes into a workspace is unverified by
construction.** If a later state renders that text back to the Solver as though it were established,
the language has manufactured a fact. Under §5, workspace content therefore lives strictly in the
projection channel, never in the core, is tagged with an epistemic status the kernel did not grant,
and never participates in `id_K`. `CHECKED_AGAINST_KERNEL` is the only value that may promote
workspace content, and only via a real verifier call.

### 3.7 τ — tokenizer

| Gene | Domain | Default | V0 status |
|---|---|---|---|
| `tau.scheme` | `SOLVER_NATIVE`, `BPE_RETRAINED`, `UNIGRAM`, `BYTE_LEVEL`, `DOMAIN_AUGMENTED` | `SOLVER_NATIVE` | **DEFERRED — FROZEN** |
| `tau.reserved_atoms` | `NONE`, `ROLE_LABELS`, `OPERATORS`, `BOTH` | `NONE` | **DEFERRED — FROZEN** |
| `tau.vocab_delta_budget` | `0`, `64`, `256`, `1024` new atoms | `0` | **DEFERRED — FROZEN** |

**Why τ must stay frozen in V0 — four reasons, in order of force.**

1. **It breaks the matched comparison, which is the whole method.**
   `docs/HAMILTONIAN_CHESS_META_MDP.md` §1 defines the comparison as *two observation functions
   over one identical process*, with `T_K` and `r` independent of `L`. Changing the tokenizer
   changes the Solver's input embedding map for **every** candidate, parent and child alike. The
   paired McNemar design in `game_r_formal_v1.compare_arms` assumes only `Ω_L` differs; a τ
   mutation violates that assumption at the level of the model, not the language.
2. **A τ change is a model change, not a language change.** A pretrained Solver's embedding table
   is fixed. `BPE_RETRAINED` or `DOMAIN_AUGMENTED` requires new embedding rows and adaptation,
   which turns "is this language better?" into "is this fine-tune better?" — the exact confound
   `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` exists to warn about.
3. **τ confounds M irrecoverably.** Morphology and tokenization are the same phenomenon observed
   at two granularities. Varying both at once makes every M result uninterpretable, and M is the
   family the owner explicitly wants a clean answer on.
4. **It is not even observable at the required fidelity.** `arena/experiments/ollama_live.py`
   measures prompt tokens by a `num_predict=1` preflight because the runtime has no tokenize
   endpoint; the parity audit's token figures are labelled *"ESTIMATES only: chars / assumed
   chars-per-token"*. And the frozen Solver was deleted mid-experiment once already
   (`PHASE8_SALVAGE_HANDOFF` §1). Token-level identity is the least stable quantity in the stack.

**Recommendation:** keep τ in the schema, hashed and recorded in provenance so that every fitness
reading is labelled with the tokenizer it was taken under; do not activate it until an M result
exists to interpret it against.

---

## 4. Worked example — `L3_JSON_AST` in the meta-genome, and one real mutation

### 4.1 The seed, re-expressed

`L3_JSON_AST` (`arena/genome/seeds.py:80-96`) maps as:

```
O.fact=EXPLICIT_TAGGED   O.assumption=EXPLICIT_TAGGED   O.obligation=EXPLICIT_TAGGED
O.dependency=EXPLICIT_TAGGED  O.evidence=EXPLICIT_TAGGED  O.goal=EXPLICIT_TAGGED
   (all six pinned by CanonicalState + _wire.py; no seed can differ)

S.topology=TREE_MIRROR   S.organising_centre=SCHEMA_ORDER   S.locality=GLOBAL
S.temporal=FULL_STATE    S.repetition=REPEAT_VERBATIM
   (S.topology=TREE_MIRROR from state=dag, which in phenotype.py is the "priority" permutation)

G.family=LABELLED_LINEAR (json encoder)   G.identifiers=NAMED   G.binders=STRUCTURAL_ID
G.scope_marking=IMPLICIT_NESTING          G.types=EXPLICIT_EVERY_USE

M.register=CONTROLLED_ENGLISH   M.composition=ATOMIC   M.role_marking=SEPARATE_TAG
M.lexicon_id=arena-lexicon-en-v0  M.length_class=LONG
   (morphology=structural-role renders keys as "field/{index}/{name}")

I.alphabet=UNICODE  I.envelope=TREE  I.redundancy=HIGH_EXPLICIT
I.error_locality=STRUCTURAL_MARKERS  I.token_shape=ROLE_LABELLED

A.form=TYPED_ACTION  A.target_binding=TARGET_ID  A.precondition_display=LISTED
A.granularity=MONOLITHIC (pinned)  A.failure_protocol=NONE (pinned)

tau.* = defaults (frozen)
```

Note the first block: **the six ACTIVE O genes are all pinned to the same value for all eight
seeds.** That is the collapse, restated in the new vocabulary. The seed population varies nothing
in O, nothing in S except a key permutation, and nothing in M except a key-name affix.

### 4.2 The mutation

```
S.organising_centre : SCHEMA_ORDER → GOAL_CENTRED
```

Everything else held. Under `SCHEMA_ORDER` the observation is: schema fields, in a fixed order,
each holding an unordered heap. Under `GOAL_CENTRED` it is: the goal first; then the transitive
closure of the state that the goal's free variables actually reach — the bindings that bind them,
the objects they name, the assumptions and facts that mention them, the obligations over them and
the evidence licensing those — as a contiguous block; then everything else under a `remainder`
heading.

**Why this is not a re-skin.** The partition is computed from the *mathematics* (free-variable
reachability over the canonical expression graph), not from key names. Two states with identical
schema-order renders produce different goal-centred renders whenever their dependency structure
differs. Adjacency — which is what a ≥40-character-window statistic measures — therefore changes as
a function of the problem. A permutation of `STATE_FIELD_ORDER` cannot do that; it is the same
permutation for every state.

**And it is the right shape for the only horizon claims that survive prior art.**
`HAMILTONIAN_CHESS_META_GOAL` §5.1 (added 2026-09-08) rules out the naive slogan: a per-step edge
compounding over a horizon is arithmetic, and the absolute gap `p^n − q^n` is *unimodal* in `n`, so
"the gap widens" is metric-dependent and must be preregistered. The two claims worth winning are a
**rank reversal across horizon** and **super-compounding** (the per-step gap itself widening with
depth). `S.organising_centre` is a plausible generator of both, and this is why it is a
*mechanism* and not merely a permutation: under `SCHEMA_ORDER` the distance between an obligation
and the fact discharging it grows with state size, so the per-step retrieval burden grows with
depth; under `GOAL_CENTRED` it does not. That is a super-compounding *hypothesis* with a stated
mechanism — not evidence, and not a prediction this document is entitled to make. It is recorded
here so that whoever preregisters the comparison knows which of the two targets this gene aims at
and which metric that requires.

**Why it is truth-preserving.** It is a partition-and-reorder. The recovery function re-merges the
partitions and restores canonical list order (see the index caveat below). `mathematical_hash` is
unchanged; nothing is added, nothing is dropped. It sits in Track E, not Track C.

### 4.3 What would have to change in `arena/languages/` — concrete cost

| # | Change | Where | Est. |
|---|---|---|---|
| 1 | New module `_topology.py`: free variables of a `CanonicalExpression`; transitive reachability over `bindings`/`objects`/`assumptions`/`established_facts`/`obligations`/`evidence_dependencies`; a pure `partition(payload) -> (reached, remainder)` | new file in `arena/languages/` | ~180 LOC |
| 2 | Replace `_ordered_payload` (`phenotype.py:185-196`) with an `S`-dispatching **layout** function returning a *nested* payload, not a permutation of one flat dict | `phenotype.py` | ~60 LOC |
| 3 | Write the inverse in `_decode_payload`: re-merge partitions, restore canonical list order | `phenotype.py:298-303` | ~60 LOC |
| 4 | **The index caveat.** `CanonicalState.to_dict()` preserves tuple order, and `stable_hash` sorts dict keys but *not* list elements — so reordering `assumptions` changes `mathematical_hash`. The partitioner must therefore emit each moved item with its canonical index, and the decoder must sort by it. Without this, stage 2 of the gate fails and the mutation is (correctly) rejected. | `_topology.py` + decoder | ~40 LOC |
| 5 | New `DependencyConstraint`: `S.organising_centre ∈ {GOAL_CENTRED, DEPENDENCY_CENTRED}` requires `G.identifiers ≠ LOCAL_ONLY`, since `remainder` must be able to reference partitioned items | `validation.py`-equivalent in the new package | ~10 LOC |
| 6 | Property tests: round-trip over the `arena/assurance/` fuzz corpus; a *behavioural novelty* test asserting the goal-centred render differs from the schema-order render on an adversarial fixture while both recover one `mathematical_hash` (the pattern `docs/CONTENT_GENOME_V1.md` already mandates for content genes) | `tests/` | ~200 LOC |

**Not required:** no change to `arena/languages/_wire.py`, no change to `arena/canonical/schema.py`,
no `schema_version` bump, no change to `arena/verifier/**`, no change to
`ModelViewCompiler.validate`. The decoder restores the exact canonical wire form, so the frozen
validator never sees the topology at all.

**Total ≈ 550 LOC including tests, no truth-kernel contact.** This is the cheapest mutation in the
meta-genome that produces a genuinely different language, which is why §7 ranks S first.

**For contrast — the cost of an O mutation that adds a concept.** `O.subgoal: ABSENT →
EXPLICIT_CONTAINER` cannot be done this way at all: `CanonicalState.goal` is a single
`CanonicalExpression`, and `_wire.py:_STATE_FIELDS` rejects any payload with an extra field.
The two routes are (a) bump `arena-canonical-v0.1.0` — forbidden, it re-hashes every state
(`CANONICAL_VNEXT_PILOT` §2); or (b) route the observation through
`releases/TRAINING_LANGUAGE_V0/`, whose `State` already carries a tuple of `Goal`s over a scope
forest and whose `to_canonical` emits a `LossReport`. Route (b) is real but it is a
multi-week integration, not a mutation. That asymmetry is the single most important fact for
planning: **S and M mutations cost hundreds of lines; O expansions cost an integration.**

---

## 5. Truth preservation — the invariant and the gate

### 5.1 Where the line is

The truth kernel and the verifier are **outside the genome**. Formally, with `S` a backend state,
`a` an action, `T_K` the transition, `r` the reward, `id_K` the backend's own state identity, and
`Ω_L` the observation function of language `L`:

> **T1 — kernel independence.** `T_K` and `r` are functions of `(S, a)` alone. No gene appears in
> their signature, directly or transitively.

Mechanically checkable, and **it holds today**: `arena/verifier/**` and `arena/canonical/**`
import nothing from `arena/genome`, `arena/languages` or `arena/model_view` (grep-verified in this
worktree). The check should be promoted to a CI-enforced AST import ban, in the same style as the
adversary's existing import ban.

> **T2 — recoverable core.** `Ω_L` is split into a **core channel** and a **projection channel**.
> For every `S` in the declared state class:
> `id_K( Ω_L⁻¹( core(Ω_L(S)) ) ) == id_K(S)`.

This is the existing gate, and it is why the existing genome cannot omit anything. The meta-genome
does not weaken it; it *names the channel it applies to*, so that O can omit **outside** the core:

> **T3 — omission is legal iff it is recomputable.** For every concept whose O gene is `ABSENT`,
> the genome must name a pure, versioned derivation rule `ρ` such that
> `derive_ρ(recovered_core) == omitted_content`, bit for bit. Symmetrically, for every relation the
> language makes explicit that is not literally in the core, `derive_ρ(recovered_core)` must
> reproduce it and its `witness_hashes` must resolve into `S`.

One equality, checked in both directions. This is exactly the contract `DerivedRelation`
(`relation`, `payload`, `witness_hashes`, `derivation_rule`) and `TruthDerivedView.omissions`
already encode in `arena/model_view/projection.py`; the meta-genome generalises it rather than
inventing it.

> **T4 — no oracle.** `Ω_L` is a pure function of `(S_t, options, S_{t-1})`. Option correctness
> labels, future proof steps, oracle values and unverified inferences are never inputs.

Partly enforced today (`derive_truth_view` takes exactly those three arguments and
`_action_payload` pops `expected_usefulness`), and attacked empirically by
`arena/experiments/rendered_prompt_adversary.py`, which sees only `(prompt, n_options)` under an
AST import ban.

> **T5 — mathematical identity under mutation.** For a parent/child pair differing in one gene,
> both render the *same* canonical object, and both recover to the same `id_K`.

Already implemented by `ModelViewCompiler.validate`.

> **T6 — enforced information parity.** Within a track, a candidate may not win by showing less.
> Two candidates compared in `TRACK_E_EQUAL_INFORMATION` must have identical
> `derived_relation_hashes` and identical `omitted_relations`; two candidates compared in
> `TRACK_C_CONTENT_PROJECTION` must have their omission sets **declared and compared**, and a
> difference in outcome that coincides with a difference in omission set is reported as
> confounded, not as a language effect.

T6 is not inherited from the existing code — it is imposed by
`docs/HAMILTONIAN_CHESS_META_GOAL.md` §7a, which states that the nearest prior work is vulnerable
precisely because it "deliberately breaks parity by optimising for token reduction — a language
that merely says less is not a better language". This is binding on the meta-genome in a way it was
not binding on the old one, because the old genome *could not* say less; O can. T6 is the price of
giving O the power to omit.

The instrumentation already exists: `InformationAccounting` records `derived_relation_hashes`,
`omitted_relations`, `repeated_witness_count`, `surface_utf8_bytes` and `projection_utf8_bytes` per
compiled view. T6 is a comparison rule over those fields, not new machinery. §7a's companion
requirement — a **compute- and sampling-matched control**, since published gains in this area have
been attributed to extra sampling rather than to the artifact — is an evaluator obligation, not a
genome one, but it must be satisfied before any fitness reading from this genome is reported.

**The one-sentence line:** *a gene may change what is shown, where it is shown, and what it is
called; it may never change what is true, and it may only omit what can be put back.*

### 5.2 The semantic gate — render → parse → recover → compare

Fail-closed, non-compensatory, ordered cheapest-first, run before any Solver call is spent.

| Stage | Check | Failure mode caught | Exists today? |
|---|---|---|---|
| 0 | genome validity against declared gene dependencies | illegal combination | **yes** — `require_valid_genome` |
| 1 | determinism: render twice, and in a fresh process, byte-identical | hidden nondeterminism | **yes** — the purity audit in `ROUTE_B_PARITY_AUDIT` header |
| 2 | **core recovery**: `parse(core(text)).mathematical_hash == state.mathematical_hash` | a gene changed the mathematics | **yes** — `ModelViewCompiler.validate`, measured to refuse a renderer that drops one `holds(...)` assumption |
| 3 | **derivation replay**: every `ABSENT` concept is reproduced from the core by its declared `ρ`; every explicit derived relation recomputes to its `relation_hash` and its witnesses resolve into `S` | silent information loss; fabricated relations | **partly** — `validate` re-derives the projection and compares hashes; the `ABSENT` direction is new |
| 4 | **non-injection**: the set of canonical expression/object hashes appearing anywhere in the render ⊆ (`S` ∪ derived closure) | a language invents mathematics | new, cheap |
| 5 | **adversary**: rendered-prompt adversary on the exact bytes, non-compensatory | the render leaks the answer | **yes** — `rendered_prompt_adversary.py` |
| 6 | **phenotypic distinctness**: `e1_coverage(parent, child)` below a declared threshold, or a declared structural statistic differs | **the no-op mutation** | **new, and the direct answer to §1.4** |

Stages 0–6 are **per-candidate** and run before evaluation. **T6 (information parity) is not a
per-candidate gate** — it is a rule on the *comparison*, checked when a parent and child are paired,
using the `InformationAccounting` fields both already carry. It belongs to the evaluator, not the
compiler, and it must be enforced there or the O family's power to omit becomes a way to win by
saying less.

Stage 6 is not a truth check; it is a budget check, and it is the stage this document exists to
add. Thirteen of thirty-five single-gene children of `L3_JSON_AST` are byte-identical to their
parent. Every one of those, under the current design, would be handed to a paired Solver
comparison that cannot possibly find a difference. Stage 6 rejects them for free and records the
rejection — which also gives the outer loop an honest map of which genes are currently inert.

### 5.3 How O and S interact with `ContentGenome` and `SearchTrack`

The existing machinery is not superseded. It is a **hand-picked six-cell slice of O × S**, and the
mapping is exact:

| `ContentGenome` gene | Meta-genome equivalent |
|---|---|
| `dependency_projection` (`IMPLICIT` / `EXPLICIT_EDGE` / `EXPLICIT_LOCAL_EDGE`) | `O.dependency` × `S.locality` |
| `premise_projection` (`GLOBAL_LIST` / `ACTION_LOCAL` / `EXPLICIT_EDGE`) | `O.assumption` × `S.locality` |
| `obligation_projection` (`GLOBAL` / `OWNER_LOCAL` / `ACTION_LOCAL`) | `O.obligation` × `S.locality` |
| `evidence_projection` (`STATUS_ONLY` / `PROOF_EDGE` / `LOCAL_PROVENANCE`) | `O.evidence` + `O.provenance` |
| `action_goal_projection` (`IMPLICIT` / `TARGET_ID` / `TARGET_BLOCK`) | `O.goal` × `A.target_binding` |
| `state_delta_projection` (`FULL_BEFORE_AFTER` / `DELTA_PLUS_CONTEXT` / `EXPLICIT_CHANGED_RELATIONS`) | `S.temporal` |

Note the shape: every one of the six is an (explicitness × locality) pair. That is exactly O × S,
discovered piecemeal. The meta-genome's contribution is to *name the two axes* so that new cells
can be reached by mutation instead of by hand.

And `SearchTrack` becomes the **legality régime over O**, not a separate concept:

- `TRACK_E_EQUAL_INFORMATION` — no O gene may be `ABSENT`; the core channel is the whole state;
  gate stages 3 and 4 are trivially satisfied. This is the régime for measuring S, G, M and I,
  where information content must be held constant.
- `TRACK_C_CONTENT_PROJECTION` — O genes may be `ABSENT` (subject to T3) and may promote derivable
  relations to explicit. This is Game P's territory, and it is where O is actually varied.

A cross-track comparison is **not** a language comparison and must never be reported as one — the
existing `InformationAccounting` (`omitted_relations`, `derived_relation_hashes`,
`repeated_witness_count`, byte counts) is what makes the difference auditable.

---

## 6. Migration — how the current genome and the eight seeds map in

**Nothing is deleted.** `LanguageGenome`, `SEED_GENOMES` and `GenomePhenotypeLanguage` remain
valid and continue to render. The meta-genome is a **new package that wraps them**, in the same
relationship `ModelViewGenome` already has to `LanguageGenome`.

### 6.1 Gene-level mapping

| Current gene | Meta-genome home | Note |
|---|---|---|
| `alphabet` | `I.alphabet` | inert today; activating it means writing a codec branch |
| `token_policy` | `I.token_shape` | overlaps `M.register`; §8 |
| `morphology` | `M.composition` + `M.role_marking` | splits in two |
| `grammar` | `G.family` | **five of its eight values currently alias one JSON encoder** |
| `composition` | `G.family` (typed-tree values) | inert today |
| `types` | `G.types` | active, but a one-literal difference |
| `binders` | `G.binders` | active |
| `state` | `S.topology` + `S.organising_centre` | **splits in two; this is the main widening** |
| `actions` | `A.form` | active on option bytes only |
| `obligations` | `O.obligation` × `S.locality` | inert in the codec; **live in `ContentGenome.obligation_projection`** |
| `evidence` | `O.evidence` × `S.locality` | inert in the codec; live in `evidence_projection` |
| `serialization` | `I.envelope` | active |
| `redundancy` | `I.redundancy` + `M.length_class` | splits in two |
| `error_locality` | `I.error_locality` | inert today |

The four inert-in-the-codec genes (`obligations`, `evidence`, `composition`, `error_locality`)
are *not* deleted — three of them turn out to have live homes in the model-view layer, which is
further evidence that the projection channel, not the wire channel, is where semantics lives.

### 6.2 Seed mapping

All eight seeds lift by the table above. The result is worth stating baldly, because it is the
finding restated: **under the meta-genome, all eight seeds share identical O genes, identical
`S.organising_centre`, identical `S.locality` and identical `S.temporal`.** They differ only in
G, M and I. The founding population spans three of eight families.

The remedy is not to discard the seeds — they are legitimate points and L2/L5 are genuinely
distinct — but to **add founders that differ in S and M**, generated by the mutations of §4 and
§7, before any generation is run.

### 6.3 Code that would have to change (named)

| File / function | Change |
|---|---|
| new `arena/meta_genome/schema.py` | `LanguageMetaGenomeV0`, content-addressed exactly like `LanguageGenome` (`genome_hash` / `candidate_hash` / `derive_candidate_id`) |
| new `arena/meta_genome/families.py` | the eight family enums; a `GENE_STATUS` table carrying `ImpactClass` + `RenderabilityStatus` for every gene |
| new `arena/meta_genome/lift.py` | `lift(LanguageGenome) -> LanguageMetaGenomeV0` and `project(meta) -> LanguageGenome` for the I/G subset, so old candidates and old fitness records stay readable |
| `arena/genome/mutation.py` | `GeneChange` gains a `family` field; `OPERATOR_GENE_SCOPE` extends to the new families; `apply_mutation` is otherwise unchanged — **its stale-proposal check and history semantics are exactly what a wide space needs** |
| `arena/genome/validation.py` | `DependencyConstraint` generalised to `(family, gene)` pairs; `GENE_AFFECTED_TESTS` extended; a **new rule that a `G.family` value without its own encoder is invalid rather than silently JSON** |
| `arena/languages/phenotype.py` | `_ordered_payload` → an `S`-dispatching layout function with a real inverse; `_role_map` → a lookup into a declared `Lexicon` value |
| new `arena/languages/_topology.py` | reachability and partitioning (§4.3) |
| new `arena/languages/_lexicon.py` | `Lexicon` as a registered, versioned *value*, modelled on `releases/TRAINING_LANGUAGE_V0/libraries.py` |
| `arena/model_view/genome.py` | `ModelViewGenome.surface: LanguageGenome` → `LanguageMetaGenomeV0`; `ContentGenome` retained and **re-expressed as a derived view of O × S** so existing records keep parsing |
| `arena/model_view/projection.py` | `derive_truth_view` generalised from six hard-coded axes to a dispatch over O × S; `omissions` gains the `ABSENT`-with-`ρ` case |
| `arena/model_view/compiler.py` | `ModelViewCompiler.validate` gains gate stages 3 (the `ABSENT` direction), 4 and 6 |
| `arena/experiments/game_r_mutant_audit.py` | `PHENOTYPE_GENES` (currently a 9-tuple) recomputed from `GENE_STATUS` rather than hand-maintained |
| **unchanged** | `arena/canonical/**`, `arena/verifier/**`, `arena/languages/_wire.py`, `releases/TRAINING_LANGUAGE_V0/**` |

---

## 7. Smallest viable V0 — ranked, and ruthless

The owner wants an executable loop within days, not a complete ontology. Ranked by
(design-space gain) ÷ (engineering cost), gated by *can the current substrate show a difference at
all*.

### ACTIVATE FIRST

**1. `S.organising_centre` — activate alone, this week.**
One gene, four legal values, ~550 LOC including tests (§4.3), no truth-kernel contact, no schema
bump. It is the only gene that changes *adjacency as a function of the mathematics*, which is both
the thing the collapse finding says is missing and the thing the long-horizon hypothesis is about.
A four-value gene over the existing eight seeds is already a 32-candidate population that is not a
re-skin.

**2. `M.lexicon_id` + `M.register` — activate second.**
Once `_role_map` is a lookup into a registered `Lexicon` *value*, a lexicon swap costs zero codec
work — TL0 already proves the pattern (`tests/releases/test_libraries.py` pins that registering a
library changes no rendered byte of an existing state). This is the axis the owner flagged as
first-class, and it is nearly free. Run it with τ frozen and `M.length_class` recorded as a
covariate.

**3. The six existing `ContentGenome` axes, re-labelled as O × S.**
**Zero new engineering** — `derive_truth_view` already implements all eighteen values, with
witnesses, derivation rules and an omissions ledger. Re-expressing them costs a mapping table and
buys the O family a working implementation on day one. Caveat, recorded honestly:
`docs/REPRESENTATION_LANDSCAPE.md` reports the content mini-family produced *negative* engineering
evidence on a single-step probe (explicit dependency edges lost both obligation-owner positives;
target blocks had only 50% valid responses). Expect these to look bad until the horizon is > 1;
that is a reason to keep them cheap, not a reason to omit them.

**4. Gate stage 6 (phenotypic distinctness) — activate with the loop itself.**
Not a language feature; a budget feature. Recovers ~37% of the mutation budget on L3-like parents
(§1.4) and produces, for free, an empirical map of which genes are currently inert. Should be built
before generation 1, not after.

### KEEP BUT DEPRIORITIZE

**5. `I.*` and `G.*` — retained, sampled at low rate.**
They work, they are the current genome, and they are the least likely to matter. Two specific
repairs are worth doing because they are *correctness* fixes, not features: make an unimplemented
`G.family` an invalid genome instead of a silent JSON alias (§1.2c), and either implement or
formally mark-inert `I.alphabet` and `I.error_locality`.

### DEFER — and say why

**6. O beyond the six existing axes — DEFERRED to the TL0 route.**
`O.definition`, `O.subgoal`, `O.conjecture`, `O.epistemic_state` etc. cannot be rendered without
either a forbidden canonical schema bump or a TL0 integration (§4.3). Six of them already exist in
`releases/TRAINING_LANGUAGE_V0/core.py`. This is a multi-week integration and it should be
scheduled *after* the loop runs, not before.

**7. `A.granularity`, `A.failure_protocol` — DEFERRED, `SUBSTRATE_BLOCKED`.**
The highest-value family in the whole design and it is worth **zero** today: maximum horizon
anywhere in the repository is 1 (`HAMILTONIAN_CHESS_META_MDP` §1), and the Solver's action is
"pick one of k". Specify now, pin now, activate the day the verified trajectory world exists.

**8. `W.*` — DEFERRED, `SUBSTRATE_BLOCKED`, and the most hazardous family.**
Nothing to persist at horizon 1, nothing to write with a one-of-k action space, and a truth hazard
(§3.6a) that needs the projection-channel discipline of §5 to be working before it is switched on.

**9. `S.topology=HYPERGRAPH`, `S.organising_centre=BRANCH_LOCAL` — DEFERRED.**
No encoder; no branches.

**10. τ — FROZEN.** §3.7.

### The V0 loop this implies

Population = 8 seeds × 4 values of `S.organising_centre` (32), filtered by gate stages 0–6, one
mutation operator (`change-organising-centre`), one cheap evaluation tier, one archive update,
one generation. That is `HAMILTONIAN_CHESS_V0` from `HAMILTONIAN_CHESS_META_MDP` §6, with a gene
that can actually move.

Two obligations attach to it before any number leaves the loop, both from
`HAMILTONIAN_CHESS_META_GOAL` §5.1 and §7a: the comparison metric must be **preregistered** (the
absolute-accuracy gap is unimodal in horizon, so an undeclared metric choice can manufacture or
destroy the effect), and the arms must be **compute- and sampling-matched** as well as
information-matched (T6). Neither is a genome feature; both invalidate the reading if missing.

**The V0 winner is not a scientific result and must not be described as one.**

---

## 8. WHAT THIS DESIGN COULD GET WRONG

Stated as failure modes, not caveats. Each is a way this document could be wrong, not a way it
could be improved.

1. **The collapse could recur one level up.** A wide *genotype* whose *phenotype* is still narrow
   is exactly the failure just diagnosed, and adding families does not by itself prevent it. If
   `S.organising_centre` turns out to be four permutations of a mostly-unreachable graph, V0 has
   reproduced the L3/L6 problem with more paperwork. Stage 6 is the mitigation and it is only a
   byte statistic.
2. **Stage 6 could select for superficial novelty.** `e1_coverage` cannot distinguish "goal-centred
   reordering computed from the mathematics" from "random key shuffling". A gene that scrambles
   bytes passes the distinctness gate while changing nothing structural — the exact inverse of the
   current failure, and equally useless. The design says "pair it with a structural statistic"
   without specifying one; that is a genuine hole.
3. **O may be untestable at V0 scale and get falsely written off.** On a single-step, two-option
   probe most O values are behaviourally identical, and `REPRESENTATION_LANDSCAPE` already records
   the content family looking *worse* than baseline. Running O before the horizon exists risks
   producing "ontology doesn't matter" from an instrument that cannot see ontology. §7 defers it
   for this reason, but the temptation to run it early will be strong because the code exists.
4. **M cannot be cleanly separated from length, even with τ frozen.** Invented morphemes fragment
   into more tokens than English words; a shorter render leaves more effective attention budget
   (`REPRESENTATION_LANDSCAPE` hypothesises exactly this for compact symbolic). `M.length_class` is
   a covariate, not a control. **V0 has no length-matched design, so an M result in V0 is
   confounded with prompt length and must be reported as such.**
5. **The derivation-replay stage may degenerate.** T3 makes omission legal iff recomputable. If
   `ρ` is expensive, partial, or awkward to write, the path of least resistance is to declare
   nothing derivable and omit nothing — which silently collapses Track C into Track E while the
   schema still says two tracks exist.
6. **The identity the whole gate rests on is known to be inadequate for the target world.**
   Every stage compares `CanonicalState.mathematical_hash`. `CANONICAL_VNEXT_PILOT` reports that
   the canonical schema maps **0 of 368 real Lean states losslessly, 20.7% unmappable**. If the
   substrate moves to a backend-native envelope — which `HAMILTONIAN_CHESS_META_GOAL` §6.1
   explicitly permits — `id_K` changes and every gate stage must be re-derived against it. This
   design is specified against an identity that is already known not to reach the target world.
   **This is the largest risk in the document.**
7. **"Single-gene delta" may be unachievable in the interesting region.** `DEPENDENCY_CONSTRAINTS`
   already pins two families to zero legal alternatives from `L3_JSON_AST`. A wider space means
   more constraints, and O × S × G interact strongly (a `GOAL_CENTRED` layout constrains
   `G.identifiers`; an `ABSENT` O gene constrains `S.locality`). If the interesting mutations are
   all necessarily multi-gene, the causal assay loses identifiability and the outer loop's central
   claim — "μ caused it" — becomes unavailable exactly where it matters.
8. **The premise that seed diversity is desirable may be wrong.** This design assumes the eight
   seeds *should* have been eight design points. It is possible that surface diversity is
   genuinely unimportant and the only axis that matters is content — in which case the correct
   response to the collapse finding was to invest everything in O and the trajectory world, and
   activating S and M first (as §7 recommends) is a well-engineered detour.
9. **Deferring τ may defer the actual effect.** If machine-facing advantage lives mostly in
   tokenization — plausible, since that is where a pretrained model's priors are hardest — then
   freezing τ freezes the independent variable. The four reasons in §3.7 are methodological, not
   evidential; none of them is a measurement showing τ does not matter.
10. **Seven families with per-concept O genes is a large space and the budget is small.** At
    measured rates (15–36 s per call at 12–18k prompt tokens, `PHASE8_SALVAGE_HANDOFF` §3.3) a
    generation is compute-bound. A space this wide, searched with single-gene deltas under
    successive halving, may simply random-walk. The ruthless V0 in §7 is a response to this, but
    "activate one gene" is not obviously an evolutionary search at all.
11. **Naming a family does not make it evolvable.** This document specifies O, A, W and τ in full
    and then pins most of them. If the trajectory world slips, the meta-genome is — in practice —
    an S+M+G+I genome with a large aspirational appendix, and should be described that way rather
    than as an eight-family design.
12. **The design omitted a family the project had already named.** `W` (workspace) is listed in
    `HAMILTONIAN_CHESS_META_GOAL` §7a as one of the seven axes of the surviving contribution, and
    it was absent from the brief's family list and from this document's first draft; it was added
    only after the meta-goal changed on disk mid-task. If one named family could be missed, the
    family list is not demonstrably closed, and "eight families" should be read as "eight so far".
13. **T6 may be unsatisfiable exactly where O is interesting.** Information parity forbids winning
    by saying less — but an `ABSENT` O gene is *definitionally* saying less, even when what is
    omitted is recomputable. The distinction the design leans on ("recomputable omission is not
    information loss") is a claim about an idealised reader, not about a Solver with finite
    attention. If a Solver cannot in practice recompute what `ρ` can, then Track C's whole premise
    is wrong and T6 will either block every interesting O mutation or be quietly weakened. Which of
    those happens is not decided by this document.
14. **The prior-art boundary may already have consumed the contribution.**
    `HAMILTONIAN_CHESS_META_GOAL` §7a returns `NOVEL_ONLY_IN_COMBINATION` and records that
    automated search over how state is rendered to an LLM agent, scored by downstream task success,
    **is already published**. That is a description of the outer loop this genome feeds. What
    survives is the *combination* — enforced parity, constant primitive set, verified long-horizon
    scoring — none of which is a property of the meta-genome itself. A wider genome does not widen
    the contribution; only the controls do. This document could be entirely correct and still not
    move the project's novelty position at all.

---

## 9. Provenance of this document

Every measurement in §1 was taken in this worktree against the code as committed at
`c1dd586`, using `.venv/bin/python`, with no network access, no model call and no file
modification outside this document. The e1_coverage reproduction (§1.3) and the mutation-
neighbourhood enumeration (§1.4) were computed inline and not persisted; both are reproducible
from `arena.genome.seeds`, `arena.genome.validation.validate_genome` and
`arena.languages.phenotype.GenomePhenotypeLanguage` on any synthetic `CanonicalState`. The
committed measurements they corroborate are in
`artifacts/reports/precondition_parity_audit.json`. §§3–8 are design and have not been
implemented, executed or evaluated.

`docs/HAMILTONIAN_CHESS_META_GOAL.md` was edited on disk while this document was being written.
The additions — §5.1 (the horizon claim is partly tautological and metric-dependent; the two
targets are rank reversal and super-compounding) and §7a (`NOVEL_ONLY_IN_COMBINATION`; enforced
information parity and a compute/sampling-matched control are mandatory; *workspace* is one of the
named axes) — were read after the first draft and are incorporated in §3.0, §3.6a, §4.2, §5.1 (T6),
§7 and §8 items 12–14. Sections written before that edit and not listed here were not revised
against it.
