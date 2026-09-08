# Lean backend state identity — V0

**Status: mechanism shipped, no scientific claim attached.** Implemented in
`arena/trajectory/state_identity.py`, tested in `tests/trajectory/test_state_identity.py`
(22 tests) and exercised on live Lean by `tests/trajectory/test_task.py`.

This document says what the two identities are, what each one guarantees, what neither
guarantees, and why the Arena canonical schema is not used for any of it.

---

## 1. Why there is no canonical state here

`docs/CANONICAL_VNEXT_PILOT.md` measured **0 of 368** real Lean tactic states mapping losslessly
into `arena-canonical-v0.1.0` (20.7% outright unmappable). Manual §17.4 permits backend-native
truth precisely so this case does not have to be forced. It is not forced:
`BackendStateEnvelope.derived.canonical_state` is typed `None` — not `dict | None` — so a
non-null value is a type error rather than an optimistic claim, and
`VerifiedTask.descriptor()["state_identity_scheme"]["canonical_projection"]` reads
`NOT_ATTEMPTED (0/368 lossless)`.

**Consequence:** state identity in this world is the *backend's*, not the Arena's.

## 2. Why the rendered text is not the identity either

Measured on the same corpus: raw pretty-printed state equality scored **40.6%** where real
semantic agreement was **98.1%**. The cause is scope-dependent rendering — the same goal prints
as `univ` under `open Finset` and `Finset.univ` without it. A verifier that compared state
strings would have rejected **59.4% of mathematically correct steps**.

So the pretty-printed goal is not an identity on its own. It becomes usable only when bound to
the scope it was rendered under, and even then it is a *sufficient* condition for sameness, never
a necessary one.

## 3. `KernelStateIdentity` — which actual backend state is this?

```
KernelStateIdentity(backend_kind, session_id, state_id, goal_digest, scope_digest, normalization)
```

Two derived keys, deliberately separate:

| Key | Composition | Scope-dependent? | Session-dependent? |
|---|---|---|---|
| `kernel_key` | `backend_kind \| session_id \| state_id` | **no** | yes |
| `reelaboration_key` | `backend_kind \| scope_digest[:16] \| goal_digest` | yes | **no** |

### It guarantees

* **`kernel_key` equality ⟺ the same saved backend state.** The backend says so; the state can be
  re-entered with `LeanTrajectoryArena.branch()`. This holds **whatever the goal was rendered
  as** — re-render the same state under a different scope, different `pp` options, or a different
  `Ω_L`, and `same_kernel_state_as` is still true. That is the "independent of pretty-print
  changes that do not change the state" property, and
  `test_kernel_key_is_independent_of_how_the_state_was_printed` asserts it.
* **`reelaboration_key` is stable across re-elaboration.** A fresh session that re-elaborates the
  same declaration reaches the same key even though the session id and the `sid` are new. This is
  the key a determinism check, a bank or a cache uses; `test_reset_is_deterministic_against_live_lean`
  asserts it on live Lean.
* **It is not raw string comparison.** The digest is taken over normalised text — Unicode NFC,
  `\r\n`→`\n`, line-wise right-strip, leading/trailing blank-line trim — bound to a canonical,
  order-insensitive form of the scope. Presentational noise that byte equality rejects does not
  move the identity (`test_reelaboration_key_survives_presentational_noise_that_byte_equality_rejects`).
  The normalisation is *named in the identity itself* (`goal-text-nfc-linewise-rstrip-v0`) so a
  future change of normalisation appears as a different identity rather than a silent drift.

### It does not guarantee

* **It is not a semantic equality decision procedure.** `univ` under `open Finset` and
  `Finset.univ` without it are the same mathematics and have *different* re-elaboration keys.
  `same_after_reelaboration_as(...) == False` means **UNKNOWN**, never "different mathematics".
  Only Lean decides that, and this module never asks it to.
* **The converse also fails:** identical `pp` under two different scopes need not be the same
  state, which is why the scope digest is inside the key rather than beside it.
* **A `state_id` is meaningless across sessions.** `sid=3` in two sessions names two different
  live handles that cannot be branched between, so `same_kernel_state_as` is `False` across
  sessions by construction. That is correct, not a limitation to be optimised away.
* **The normalisation is shallow on purpose.** It does not reorder hypotheses, alpha-rename
  binders, unfold notation or resolve namespaces. Anything deeper would be a semantic claim this
  project cannot support. LOSSLESS_FIRST, ABSTRACT_LATER.

## 4. `WorkspaceProjectionIdentity` — which declared information reached the language?

```
WorkspaceProjectionIdentity(workspace_kind, exposed_slots, information_digest,
                            intervention_class, renderer_id, rendered_bytes_digest,
                            slots_were_declared)
```

`projection_hash` is a function of `workspace_kind`, `exposed_slots` and `information_digest`
**and of nothing else**. `renderer_id` and `rendered_bytes_digest` are recorded for provenance
and *excluded* from it. That exclusion is the whole mechanism: two renderings of the same
declared information hash equally however different their bytes.

A **slot** is a semantic position, not a key name (`GOAL_TEXT`, `GOAL_COUNT`, `BACKEND_KIND`,
`BACKEND_STATE_ID`, `PP_SCOPE`, `STEP_INDEX`, `ATTEMPTS_REMAINING`, `TERMINAL_STATUS`,
`LAST_DIAGNOSTIC`). A renderer that implements `InformationDeclaringRenderer` declares
`slot -> value`; one that does not gets a conservative identity derived from its output keys, in
which every unrecognised key becomes its own `UNDECLARED:<key>` slot. Nothing is dropped
silently, so a renderer cannot smuggle extra information past the identity by inventing a key.

### It guarantees

* Two `R_ONLY` renderers that declare the same slots with the same canonical values produce the
  **same** `projection_hash` while their `rendered_bytes_digest` differ
  (`test_two_r_only_renderers_agree_on_identity_and_disagree_on_bytes`).
* Slot order in the declaration is irrelevant; values are canonicalised (text through the same
  normalisation as §3, scopes through the same order-insensitive form).
* Renaming the renderer or changing the bytes cannot change the identity
  (`test_renderer_id_and_rendered_bytes_are_excluded_from_the_projection_hash`).

### It does not guarantee

* It is **not** evidence that two languages are equally *usable*. It establishes manual §12.3's
  parity precondition — the same declared information was available — and nothing more.
* It is only as good as the declaration. A renderer that mislabels a slot produces a false
  parity. The declaration is a **claim by the candidate language**, checkable against the rendered
  bytes by a reader, not proved here.
* An undeclared renderer gets no parity at all, by design: without a declaration there is no
  evidence that a renamed key carries the same information.

## 5. How `R_ONLY` parity will be checked

`check_projection_parity(left, right, intervention_class)` returns a
`ProjectionParityResult(parity_required, parity_holds, bytes_differ, admissible, explanation)`.

* `R_ONLY` — `parity_required=True`. Parity **must** hold; the expected shape is
  `parity_holds and bytes_differ`. `InterventionClass.requires_visible_information_parity`
  (manual §12.3, §26.2) is the authority, and it is read from
  `arena/evolution/record.py` rather than re-declared here.
* `P_CHANGE` / `O_CHANGE` / `A_CHANGE` / `T_CHANGE` / `TAU_CHANGE` / `C_CHANGE` / `JOINT` —
  `parity_required=False`. A difference in the projection identity **is the intervention**, not a
  fault, and the result says so in words. Reporting it as a violation is how an ontology change
  gets mislabelled a representation change (manual §26.3).

The intended protocol for a future comparison: run one `VerifiedTask` (whose `task_id` deliberately
**excludes** the renderer, so two languages provably play the same task) under two `Ω_L`s, collect
the per-step `WorkspaceProjectionIdentity`, and require `check_projection_parity(...).admissible`
at **every** step before any `Δ(R_A, R_B)` is reported. Nothing here computes `Δ(R_A, R_B)`, and
no `RSTAR`/`LSTAR` claim is made or licensed by this document.

## 6. Where this is used

* `VerifiedTask.observe()` returns a `WorkspaceProjection` = exact rendered bytes + the identity
  of the information in them.
* `VerifiedTask.state_identity()` and every `TaskStepResult.state_identity` carry a
  `KernelStateIdentity`.
* `TaskEpisodeReport` records the start and final kernel identities, so an episode's endpoints
  are addressable without re-running it.

## 7. What is deliberately absent

* No canonical projection, no `mathematical_hash`, no cross-backend state equality.
* No semantic normal form, no definitional-equality check, no `whnf`.
* No claim that the two identities together decide state equality. They decide **addressability**
  (kernel) and **information parity** (projection). Mathematics stays with Lean.
