# TRAINING_LANGUAGE_V0 (TL0) — specification

`language_id: TL0` · `language_version: 0.1.0` ·
`evidence_level: TRAINING_LANGUAGE_V0_BASELINE`

**This release is packaging and interfaces.** It is not a Game-R result. Nothing in it may
be called R\*, and it makes no claim that any representation trains better than any other.
It was built independently of the tournament precisely so that whichever surface the
integrator selects can be plugged in at integration time (§8).

---

## 1. Design principles

1. **Small core, libraries for the rest.** Ten record kinds define how state, actions,
   bindings, types, scope, evidence, obligations and transitions are represented. Domains
   — algebra, number theory, analysis, probability, topology, combinatorics — are
   `Library` **values**: lists of type heads, operator symbols and operation names. Adding
   a domain adds no production, no bracket, no parser branch, no renderer branch. An
   over-built ontology would be a failure, not a bonus.
2. **The substrate is frozen; TL0 builds on it.** `arena-canonical-v0.1.0` is not
   modified and `schema_version` is never bumped — doing so re-hashes every state in the
   project (`docs/CANONICAL_VNEXT_PILOT.md` §2).
3. **Never drop silently.** Where TL0 exceeds what a consumer schema can express, the
   excess is carried explicitly and the carrying is *recorded* (§7). Where a consumer
   demands data the source lacks, the invention is recorded as `SYNTHESIZED`.
4. **Fail closed.** An invalid state cannot be constructed, rendered or parsed. `VERIFIED`
   cannot be spelled without a verification record (§4).
5. **Determinism is a checked property, not a promise.** See §6.
6. **The renderer is a function of a declared configuration.** `docs/ROUTE_B_PARITY_AUDIT.md`
   §1 found that five of the eight historical seed arms never read their own genome —
   changing a gene changed no byte. TL0's renderer takes `(state, RenderConfig)` and
   nothing else, and its wrapper surfaces derive every rendering decision from the wrapped
   language's declared genes.

---

## 2. Core objects

| Object | Carries | Notes |
|---|---|---|
| `Type` | `head`, `params: tuple[Type, ...]` | **structured**, not a flat string (gap G3) |
| `Term` | `op`, `sort: Type`, `value`, `args`, `attributes` | the one expression node: terms, propositions and identities are all Terms |
| `Scope` | `scope_id`, `parent_id` | a **forest**; this is what gives goals per-goal context |
| `Decl` | `decl_id`, `name`, `sort`, `scope_id`, `kind`, `value`, `attributes` | one record for objects, variables, binders, definitions, **let-values** (gap N2) and **metavariables** |
| `Claim` | `claim_id`, `role`, `scope_id`, `statement`, `status`, `evidence_id`, `depends_on` | assumptions, facts, propositions, definitions, identities |
| `Goal` | `goal_id`, `scope_id`, `statement`, `status`, `focused`, `evidence_id` | **zero, one or many** (gap G1) |
| `Obligation` | `obligation_id`, `scope_id`, `statement`, `status`, `source`, `evidence_id` | **scoped** (gap N4) |
| `Evidence` | `evidence_id`, `status`, `verifier`, `verifier_version`, `certificate_hash`, `details`, `depends_on` | the only thing that can license `VERIFIED` |
| `Action` | `action_id`, `operation`, `targets`, `arguments`, `warrant`, `preconditions`, `generated_obligations`, `status`, `evidence_id` | §5 |
| `Extension` | `owner_id`, `key`, `payload` | explicit lossless carrier, **visible in the rendered text** |

`State` holds those plus `libraries`, `substitution` (metavariable → term; gaps G2 ≡ G6 are
one structure, not two) and `terminal_status`.

`State.__post_init__` enforces: unique ids; every referenced scope, evidence and dependency
resolves; the scope forest is acyclic; every substituted name is a declared `METAVAR`; and
the `VERIFIED` rule of §4.

### The measured REQUIRED gaps

`docs/CANONICAL_VNEXT_PILOT.md` measured 368 real Lean states: **0 mapped losslessly, 20.7%
were unmappable**. Its REQUIRED set is handled here as follows.

| Gap | Handling in TL0 |
|---|---|
| G1 + N1 multi-goal, per-goal context | **native** — `State.goals` is a tuple; each `Goal` names a `Scope` in a forest |
| N4 obligation scope | **native** — `Obligation.scope_id` |
| G2 ≡ G6 metavariable / substitution | **native** — `DeclKind.METAVAR` + `State.substitution`, one structure |
| G3 structured types | **native** — `Type` is a tree |
| N2 let-bound values | **native** — `Decl.value` |
| G4 universe levels, G5 binder kinds, N3 external premise refs (`BACKEND_EXTENSION`) | `binder_kind` is native (`DeclKind`); universe levels and premise refs ride in `Term.attributes` or an `Extension` record, byte-lossless, exactly as the pilot classified them |
| G7 distinct-variable conditions | **deferred**, matching the pilot's `DEFER`: zero occurrences in the corpus, and a Metamath source would be needed to judge it. Representable today only as an `Extension`, and that limitation is recorded here rather than papered over |
| G8, N5 | not canonical-schema questions; they belong to the verification layer, which TL0 does not touch |

---

## 3. Model-facing syntax

```
document := "TL0" SP version SP state_id NL record*
record   := KEYWORD field* NL                    -- exactly one physical line
field    := ATOM | STRING | type | term | attrs
type     := "[" (ATOM|STRING) type* "]"
term     := "(" (ATOM|STRING) type value term* attrs? ")"
value    := "_" | "#i" INT | "#f" FLOAT | "#b" ("true"|"false") | "#s" STRING
attrs    := "{" ((ATOM|STRING) "=" STRING)* "}"
```

Records: `lib`, `scope`, `decl`, `claim`, `goal`, `oblig`, `evid`, `subst`, `dep`, `ext`,
`status`. `act` opens a block closed by `end`, with sub-records `target`, `arg`, `pre`,
`warrant`, `gen`.

`_` is a hole (absent id, absent value, absent term). Optional *strings* are always quoted,
so the literal `"_"` never collides with a hole. Bare atoms use
`A-Za-z0-9_.:-+*/<>?!~^$%@'`; anything else is quoted with `\\`, `\"`, `\n`, `\r`, `\t`
and `\uXXXX` escapes. No rendered token ever contains a raw newline, so a document can
always be split on newlines before tokenising.

Example:

```
TL0 0.1.0 state:demo
lib core 0.1.0
scope s0 _
scope s1 s0
decl d.n n [Nat] s0 forall _
decl d.k k [Nat] s1 let (add [Nat] _ (var [Nat] #s "n") (lit [Nat] #i 1))
claim c.1 assumption s0 ASSUMED _ (le [Prop] _ (lit [Nat] #i 0) (var [Nat] #s "n"))
goal g.1 s1 OPEN 1 _ (even [Prop] _ (var [Nat] #s "k"))
evid e.1 VERIFIED "arena.native" "0.1.0" "abc123" "kernel accepted"
status OPEN
```

The parser tolerates leading/trailing whitespace and blank lines, because it is pointed at
model output. It tolerates nothing else: missing *and* unknown fields both raise, mirroring
`arena/languages/_wire.py`.

---

## 4. Status and epistemics

`ASSUMED · PROPOSED · DERIVED · VERIFIED · REFUTED · OPEN`.

**`VERIFIED` is not representable without a named verifier and a verification record.**
Enforced in three places, each of which raises `StatusError`:

1. `Claim`, `Goal`, `Obligation`, `Action` construction — `status == VERIFIED` with no
   `evidence_id` raises.
2. `Evidence` construction — `status == VERIFIED` with no `verifier` or `verifier_version`
   raises.
3. `State` assembly — a `VERIFIED` annotation's `evidence_id` must resolve to an
   `Evidence` node that is itself `VERIFIED` and names a verifier and a version.

The parser inherits all three, because parsing constructs these objects. So does
`VerificationOutcome` in the training schema. `tests/releases/test_status.py` asserts each
attempt raises rather than asserting that it "should not" be done.

---

## 5. Action / reasoning protocol

An `Action` is `operation · targets · arguments · warrant · preconditions ·
generated_obligations · status · evidence_id`.

The **state delta is never stored inside the action**. A `Transition` is
`transition_id · state_before · action · state_after · verification`, and `Transition.delta()`
*computes* a `StateDelta` — goals added, removed and closed; obligations added and
discharged; claims, declarations, evidence and scopes added; generated obligations that
never landed; whether the terminal status moved. A stored delta could disagree with the
states it claims to relate; a computed one cannot.

One rule on `Transition` is fail-closed: **a transition whose verification says `VERIFIED`
must leave a matching verification record in `state_after`**, otherwise a trajectory could
assert a verification that no state can show — the §4 failure mode, one level up. A
transition also refuses an action that reuses the id of a different action `state_before`
offered; externally proposed actions with fresh ids are allowed.

TL0 does not decide whether a step is valid. A verifier does. `Action.status` is a
*proposal*, and `VERIFIED` on it obeys §4 like everything else.

---

## 6. Determinism

`render_state(state, config)` is a pure function of its two arguments.

* **No ambient input.** No module in the package imports `random`, `time`, `datetime`,
  `uuid`, `secrets` or `os.environ`. Asserted by a static scan over the package, the same
  method `docs/ROUTE_B_PARITY_AUDIT.md` used on `arena/languages`.
* **No dict-order dependence.** The only mappings TL0 holds are attribute tuples, sorted at
  construction by `normalise_attributes`. Every other collection is an ordered tuple, so
  emission order is data. A test permutes the insertion order of every attribute mapping in
  a state and asserts byte-identical output.
* **No hash-seed dependence.** A test renders the same state in two subprocesses under
  different `PYTHONHASHSEED` values and compares bytes.
* **Round-trip.** `parse_state(render_state(s)) == s` for every state, under the default
  lossless configuration. Non-default configurations are *views*; `RenderConfig.is_lossless`
  says so, and no round-trip is claimed for them.

---

## 7. Correspondence to the Arena canonical substrate

`canonical_adapter.to_canonical(state, policy, profile)` returns the canonical state **and**
a `LossReport`. Every mapping decision is one of:

* `ENCODED` — injective and reversible. Structured types become the flat canonical `sort`
  string using TL0's own type syntax (`[Fun [Nat] [Prop]]`). Bytes and tree both survive;
  the substrate reasons about it as an opaque string.
* `CARRIED` — verbatim, out of band, under a reserved `tl0.*` attribute. `attributes` is
  `string → string` and survives the strict wire validator byte-identically (the pilot's
  Probe D). TL0 forbids user attribute keys beginning `tl0.`, so a carrier can never be
  shadowed.
* `SYNTHESIZED` — required by the substrate but absent from the source. Above all the
  single mandatory `goal`: a zero-goal state emits a placeholder `tl0.absent_goal`.
* `DROPPED` — genuinely lost. Only reachable under `LossPolicy.DROP`.

`LossPolicy`: `NATIVE_ONLY` refuses anything beyond `ENCODED` — which for a realistic state
means it refuses, and that refusal is the honest statement of what the frozen substrate can
express. `CARRY` (default) attaches carriers. `DROP` emits a substrate-pure state and lists
the casualties.

`from_canonical` reverses `to_canonical` **exactly** when the carriers are present, and
otherwise imports a foreign canonical state best-effort with every invention recorded.

### Compatibility profiles

Two properties of the **frozen** verifier were read out of `arena/verifier/native.py`:

* `:82-84` — every binding's `scope_id` must appear in `local_scope`, else `UNKNOWN_SCOPE`.
* `:136` — only `binder_kind == "free"` counts as declared, so an honest `forall` /
  `implicit` / `instance` produces `UNBOUND_VARIABLE`.
* `:231-232` — `all_targets = set(object_ids) | {"goal"}`, so an action targeting a goal id
  produces `UNKNOWN_ACTION_TARGET`.

`CompatibilityProfile.ARENA_VERIFIER` (default) rewrites all three and carries the truth, so
the reverse mapping stays exact. `CompatibilityProfile.HONEST` does not. The conformance
suite runs the real `NativeVerifier` over both, so the difference is measured, not asserted.
**These are properties of the frozen verifier, not defects introduced here, and TL0 does not
fix them — fixing them would mean editing the frozen substrate.**

---

## 8. The selection seam

A `Surface` turns a TL0 state into model-facing text and back. Two ship:

* `NativeSurface` — TL0's own text. **The default**, on the narrow ground that it is the
  only surface that renders the whole core without routing through a schema that cannot
  express multi-goal, scope, substitution or let-values. That is an expressiveness
  argument, not a training claim.
* `CanonicalSurface(language)` — wraps *any* `arena.languages.base.CandidateLanguage`: the
  eight seed surfaces, a `GenomePhenotypeLanguage` built from an evolved genome, or
  whatever the tournament returns. `wrap_candidate` and `wrap_genome` are the entry points.

Selecting a winner is one call:

```python
registry = build_default_registry()
registry.register(wrap_candidate(winner))
registry.set_default(f"via:{winner.candidate_id}")
```

Nothing else in the package changes: the training schema, acquisition guide and hashes all
read the `SurfaceDescriptor`.

---

## 9. Training data schema

`tl0-training-record-v1`. One record is one decision.

```
schema_version · trajectory_id · problem_id · step_index
state_t · rendered_state_t
candidate_actions[] · rendered_candidate_actions[]
chosen_action · rendered_chosen_action · warrant
next_state · rendered_next_state
verification{verifier, verifier_version, status, accepted, certificate_hash, details}
outcome
provenance{source, source_id, generator, generator_version,
           sealed_splits_excluded, sealed_splits_manifest, licence, notes}
surface{surface_id, family, summary, lossless_round_trip, configuration, tl0_version}
content_hash
```

* **`state_t` is the lossless TL0 text**, and `rendered_state_t` is the surface's text.
  There is exactly one structural serialization and one hashing scheme
  (`arena.canonical.schema.stable_hash`), matching the discipline
  `arena/training/route_b_data.py` states for its own manifests.
* **Targets are rendered through the same surface as the inputs.** An action is wrapped in
  an `action_envelope` — the scope forest plus only the declarations, goals and evidence the
  action refers to — and pushed through the same `Surface`. Every arm therefore has
  input-grammar = output-grammar, which removes `ROUTE_B_PARITY_AUDIT` defect **D3** by
  construction rather than by preregistration.
* **`write_jsonl` refuses** any record whose provenance does not assert
  `sealed_splits_excluded`, and `read_jsonl` refuses any record whose `content_hash` does
  not match its content.

---

## 10. Acquisition guide

`acquisition_guide(surface)` = frozen `PREAMBLE` + generated syntax section + frozen
`CLOSING`. Its candidate-neutrality rests on four checked properties:

1. `PREAMBLE` and `CLOSING` are byte-identical for every surface.
2. The syntax section is generated by the surface from its own descriptor. There is no
   hand-written per-candidate prompt to tune — the exact failure mode
   `ROUTE_B_PARITY_AUDIT` §1 found in the historical arms.
3. No guide contains a candidate identifier, a surface identifier, or any comparative or
   evaluative term from `BANNED_TERMS`.
4. Every syntax section fits one shared character budget, so length cannot silently favour
   an arm.

**Limitation, stated plainly.** Identical text guarantees identical *content*, not identical
*helpfulness*. A grammar a base model saw more of in pretraining is easier to acquire from
the same words. No static property of this file can correct for that; only a matched
experiment can measure it, and this release has not run one.

---

## 11. Extension rules

* **A new domain is a `Library` value.** `Library.extend(...)` derives a wider one.
  Registering it changes what `check_vocabulary` reports and changes **no rendered byte** of
  an existing state. Pinned by `tests/releases/test_libraries.py`.
* **A new consumer-schema field is a carrier, not a grammar change.** Add a `tl0.*` key in
  `canonical_adapter` and a `LossItem` describing it.
* **Data the core does not model goes in an `Extension` record**, which is visible in the
  rendered text so a consumer sees that something was carried.
* **Changing any hashed file requires regenerating `HASHES.json`** (`python -m
  releases.TRAINING_LANGUAGE_V0.hashes`), or the suite fails.
* **A change to the record shape, the grammar or the carrier layout bumps its own version
  string** — `language_version`, `tl0-training-record-v1`, `tl0-canonical-carrier-v1` — and
  never `arena-canonical-v0.1.0`.

---

## 12. Known limitations

1. **G7 (distinct-variable conditions) is deferred**, matching the pilot's classification.
   It is representable only as an `Extension`, not natively.
2. **The `ARENA_VERIFIER` profile trades honesty for acceptance.** `binder_kind` is
   flattened to `free` and goal-targeting actions are retargeted to `"goal"`. The truth is
   carried and the reverse mapping is exact, but a canonical consumer reading the emitted
   state *without* the carriers sees a less specific state than TL0 held.
3. **`NativeVerifier` acceptance carries little information about imported data** — pilot
   finding N5: `lean.*` operations match none of its rules. TL0 does not change this and
   does not treat acceptance as evidence.
4. **Carriers perturb `mathematical_hash`.** `tl0.*` attributes are part of the goal
   expression, so a carried state and a `DROP`-policy state of the same mathematics have
   different canonical hashes. Use one policy consistently within an experiment.
5. **No claim about training.** No model was called and no matched experiment was run for
   this release.
