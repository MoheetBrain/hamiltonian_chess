# Reasoning-Operation Audit

## Scope and method

No language model labelled operations. The inventory uses existing Gold operation IDs and
layer annotations, LeanDojo tactic heads/effects/premises, and a recorded deterministic
codebook. Machine output: `research/codex_audit/operation_inventory.json`.

The crucial separation is:

- **canonical/mathematical**: a semantic state change such as introduce, rewrite, instantiate,
  construct, case split, derive, evaluate or discharge;
- **controller/search**: tactic selection, automation, retrieval, branching or backtracking;
- **presentational**: restatement/explanation with no mathematical state change.

A Lean tactic head is an interface command, not automatically an atomic mathematical operation.

## Source coverage

| Source | Problems / transitions | Verification scope | Ambiguity |
|---|---:|---|---:|
| Gold-10 | 10 / 23 | 21 `verified`, 2 `verified_as_undetermined`; hand-authored | 0 after retaining explicit semantic labels |
| Gold-25 | 25 / 118 | manual semantic checks | 0; labels are curated but ontology-specific |
| New Gold-125 rows | 100 / 651 | exact source-span/state audit, not formal replay | 125/651 = 19.20% `UNRESOLVED` |
| LeanDojo | 259,580 tactic transitions | formal trace source, not fresh replay per row | 54,826/259,580 = 21.12% under conservative head codebook |

Gold chains cover Hendrycks MATH subjects; LeanDojo covers 3,606 Mathlib source files.
`[VERIFIED_BY_SOURCE_DATA]`

## Empirical recurrence

The strongest recurring units across sources are:

1. introduce/localize assumptions and variables;
2. rewrite/substitute/normalize;
3. apply a definition, theorem or domain rule;
4. case analysis and induction;
5. construct a witness/intermediate result;
6. evaluate or bound;
7. discharge/close a goal;
8. controller automation and tactic selection.

LeanDojo's most frequent raw heads are `rw` 48,991, `simp` 33,298, `exact` 30,785,
`have` 16,876, `refine` 14,293, `apply` 10,032, `intro` 8,321, `simpa` 7,321,
`obtain` 6,526, `rcases` 5,175 and `ext` 5,159. These counts show recurring interfaces, not
an endorsed universal ontology.

Gold-125 declared layers are 391 core proof operations, 98 domain-library, 19 numeric backend,
9 core-state, 7 search-meta, 2 theorem-library, and 125 unresolved. All 651 are only
`SOURCE_GROUNDED`. `[VERIFIED_BY_SOURCE_DATA]`

## Where categories fail

- `simp`, `aesop`, `linarith`, `ring` and `omega` compress variable amounts of search and many
  kernel steps; they belong in controller/backend metadata unless expanded by an executable
  trace.
- `exact`, `apply` and `refine` combine controller choice with semantic theorem application.
  The argument/premise, not the head alone, identifies the mathematical operation.
- A source sentence can contain several algebraic transformations. Gold-125 explicitly records
  atomicity uncertainty; it should not be forced into one primitive.
- Presentation-only sentences are common in natural solutions but absent from Lean state
  transitions. They must not become canonical mutations merely because they occur in prose.
- `OTHER/UNRESOLVED` is evidence about ontology coverage, not noise to relabel automatically.

## Verification rates

“Formal trace source” means the recorded tactic came from a successful proof trace. It does not
mean this audit replayed all 259,580 steps. The available Stage100 attestation independently
replayed 32 exact transitions and had 68 nonpass cases due to reconstruction/environment limits.
Gold verification statuses are source/curation evidence and cannot be aggregated with Lean
kernel acceptance as one rate.

## Recommended codebook structure

Store two linked fields rather than one universal operation:

- `semantic_effect`: relation added/removed, goal transformed, witness introduced, branch
  created, obligation discharged;
- `controller_action`: raw tactic, premises selected, search budget, branch order, result.

Keep source-specific raw operations losslessly. Promote a cross-source canonical operation only
after deterministic adapters agree on before/after semantics and a verifier can check the
transition.
