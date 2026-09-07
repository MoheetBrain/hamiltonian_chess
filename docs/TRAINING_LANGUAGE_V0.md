# TRAINING_LANGUAGE_V0 — release note

**Package:** `releases/TRAINING_LANGUAGE_V0/` · **Spec:** `releases/TRAINING_LANGUAGE_V0/SPEC.md`
**Language:** `TL0 0.1.0` · **Evidence level:** `TRAINING_LANGUAGE_V0_BASELINE`
**Package hash:** `0d57e0a7bb4c149279fdf4cc9685679b8d8426c40b8e82f624612741fed4bf69`

## What this is, and what it is not

TL0 is the *language and packaging* layer for post-tournament training: a small extensible
core for machine-facing mathematical state, a deterministic renderer and parser, a canonical
adapter, a fine-tuning record schema, a candidate-neutral acquisition guide, and a plug
point where the selected representation goes.

**It is not a Game-R result.** It was built independently of the tournament, so that
whichever surface the integrator selects can be wrapped at integration time. Nothing in it
may be called R\*. No model was called, no GPU used, no network touched, no Lean built, and
no file listed in `artifacts/manifests/SEALED_SPLITS.json` read.

## The core, and why it is small

Ten record kinds — `scope`, `decl`, `claim`, `goal`, `oblig`, `evid`, `subst`, `dep`,
`ext`, `lib`, plus the `act` block — cover terms, types, propositions, definitions,
assumptions, facts, goals, variables, identities, binders, scope, dependencies, obligations,
evidence and state. One `Decl` record covers objects, variables, binders, definitions,
let-values and metavariables; one `Term` node covers terms, propositions and identities.

Domain vocabulary (algebra, number theory, analysis, probability, topology, combinatorics)
is a `Library` **value**: type heads, operator symbols and operation names with one-line
summaries. Adding a domain adds no production, no bracket and no code path.
`tests/releases/test_libraries.py` pins that registering a new library changes what
`check_vocabulary` reports and changes **no rendered byte** of an existing state.

## The measured gaps

Against the REQUIRED set in `docs/CANONICAL_VNEXT_PILOT.md` (0 of 368 real Lean states
mapped losslessly; 20.7% unmappable):

| Gap | TL0 |
|---|---|
| G1 + N1 multi-goal with per-goal context | **native** — a tuple of goals over a scope *forest* |
| N4 obligation scope | **native** — `Obligation.scope_id` |
| G2 ≡ G6 metavariable / substitution | **native**, as one structure |
| G3 structured types | **native** — `Type` is a tree, not a flat string |
| N2 let-bound values | **native** — `Decl.value` |
| G4 / G5 / N3 (BACKEND_EXTENSION) | attributes and `Extension` records, byte-lossless |
| G7 distinct-variable conditions | **deferred**, matching the pilot; representable only as an `Extension`, and that limitation is recorded rather than hidden |

## The canonical seam

`to_canonical` returns the canonical state **and** a `LossReport`. Every decision is
`ENCODED` (injective and reversible), `CARRIED` (verbatim under a reserved `tl0.*`
attribute), `SYNTHESIZED` (required by the substrate, absent from the source) or `DROPPED`
(only under `LossPolicy.DROP`). `from_canonical` reverses it exactly when the carriers are
present, and imports a foreign canonical state best-effort otherwise, recording every
invention.

`arena-canonical-v0.1.0` is **not modified**. `schema_version` is not bumped — that would
re-hash every state in the project.

### Two measured properties of the frozen verifier

Read out of `arena/verifier/native.py`, not assumed, and reproduced by the test suite:

* `:82-84` — every binding scope must appear in `local_scope`, else `UNKNOWN_SCOPE`.
* `:136` — only `binder_kind == "free"` counts as declared, so honest binder kinds produce
  `UNBOUND_VARIABLE`.
* `:231-232` — action targets are restricted to `object_ids ∪ {"goal"}`.

`CompatibilityProfile.ARENA_VERIFIER` (default) rewrites all three and carries the truth;
`HONEST` does not. The suite runs the real `NativeVerifier` over both: the first is
accepted, the second reports exactly those three codes. **TL0 does not fix them — that
would mean editing the frozen substrate.**

## Two audit defects removed by construction

* **ROUTE_B_PARITY_AUDIT §1** — the five historical arms never read their own genome. TL0's
  renderer is a function of `(state, RenderConfig)`; its wrapper surfaces derive every
  decision from the wrapped language's declared genes.
* **ROUTE_B_PARITY_AUDIT D3** — targets were always canonical JSON, giving `L3_JSON_AST`
  alone input-grammar = output-grammar. TL0 renders an action by wrapping it in an
  `action_envelope` and pushing it through the *same* surface, so every arm is
  self-consistent.

## Selection seam

```python
registry = build_default_registry()
registry.register(wrap_candidate(winner))  # or wrap_genome(evolved_genome)
registry.set_default(f"via:{winner.candidate_id}")
```

The shipped default is the native TL0 surface, on the narrow ground that it is the only one
that renders the whole core without routing through a schema that cannot express multi-goal,
scope, substitution or let-values. That is an expressiveness argument, not a training claim.

## Verification

`python -m pytest tests/releases -q` — see `releases/TRAINING_LANGUAGE_V0/VERSION` for the
recorded results and `SPEC.md` §12 for the known limitations.
