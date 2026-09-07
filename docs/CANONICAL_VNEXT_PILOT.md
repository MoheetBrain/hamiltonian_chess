# Canonical vNext — Measured Pilot

**Status: EVIDENCE ONLY. No production schema change was made, proposed for adoption, or
implemented.** `arena-canonical-v0.1.0` is untouched; the Gold set, the verifier, the language
surfaces and every Game-R hash are unchanged. Scripts and raw output are under
`research/canonical_vnext/`; machine-readable results in
`artifacts/reports/canonical_vnext_gap_verification.json`.

**Method.** 184 records / 368 real Lean 4 proof states, stride-5 sample from
`HML_V3/data/corpus/lean_runtime_v2_full.canonical.part-{000..004}.jsonl.gz` (1,150 records;
the 232 sealed-shard records were excluded by source-file name). Each state was mapped into the
**current** canonical schema, imported read-only, and every failure recorded by class. **The
schema was never modified to make a record pass.** No model call, no Lean execution.

---

## 1. Headline

**0 of 368 states mapped losslessly.** 292 (79.3%) mapped with loss; **76 (20.7%) could not be
mapped at all**; 66 of 184 records (35.9%) contain at least one unmappable state.

That is a statement about *importing real formal mathematics*, not about the Arena's own
generated world, which the schema handles by construction.

---

## 2. What the schema actually is

`arena-canonical-v0.1.0` (`arena/canonical/schema.py:15`) is eight frozen dataclasses.
`CanonicalExpression` is `op / args / value / sort / attributes`, where `sort` is a **flat string**
and `attributes` is `string → string`. `CanonicalState` (`:196-212`) has 15 fields including
**one mandatory `goal`**, with *state-global* `bindings` and `local_scope`.

Three properties dominate every migration question:

1. **`mathematical_hash` (`:281-283`) covers everything except `state_id` and
   `execution_metadata` — including `schema_version`.** Bumping the version therefore changes
   every state hash in the project.
2. **The wire form is closed.** `_wire.py:20-29` rejects both missing *and unknown* keys, and
   `payload_to_state` demands a byte-identical round-trip.
3. **`phenotype.py:78-99` builds compressed/symbolic role labels by *index* into `_KNOWN_KEYS`.**
   Inserting a single field renames every candidate language's serialization.

Any future schema change is therefore a project-wide re-hashing event, not a local edit. This is
the single most important engineering fact in this report.

---

## 3. Adjudication of the claimed gaps

Claims G1–G8 came from `docs/CANONICAL_VNEXT_GAP_REPORT.md`. Each was tested, not assumed.

| Gap | Verdict | Measured frequency |
|---|---|---|
| **G1** only one mandatory goal | **CONFIRMED** | **0 goals** in 64 states (17.4%) → hard unmappable; **>1 goal** in 42 (11.4%); goals with *differing contexts* in 12 (28.6% of multi-goal) |
| **G2** no metavariable assignment map | **CONFIRMED** | 100% of records; 1,375 metavariables, 992 assigned |
| **G3** `Binding.type_name` is a flat string | **CONFIRMED** | 100% of records; **4,288 / 5,071 context entries (84.6%) have compound types** |
| **G4** no universe levels | **CONFIRMED structurally, REFUTED for losslessness** | 100% of records; 34,781 symbol occurrences carry universe arguments — but already stored losslessly as text by the production transcriber (`formal_structural.py:128-129`) |
| **G5** no implicit/instance argument kinds | **PARTIALLY CONFIRMED** | 94% of records; all four Lean roles present — but **`binder_kind` already exists** |
| **G6** no substitution map | **CONFIRMED, and identical to G2** | 100% — G2 and G6 are one structure, not two |
| **G7** no distinct-variable conditions | **REFUTED / NOT APPLICABLE** | **0 of 368 states** |
| **G8** no definitional-equality step type | **REFUTED as a schema gap** | 0 measurable. `CanonicalAction.operation` has **no whitelist anywhere** and accepts `"defeq_unfold"`. What is missing is a *verifier* for defeq, which belongs on `VerificationRecord` |

**Two refutations worth stating plainly.** G7 has zero occurrences in real Lean data — it is a
Metamath-shaped requirement and cannot be judged from this corpus at all. G8 is not a schema gap;
the report that raised it mistook an unconstrained field for a missing one.

**G5's real defect is elsewhere and is a live bug:** `arena/verifier/native.py:136` treats
`binder_kind == "free"` as "this name is declared", so setting it honestly to `implicit` or
`instance` makes the verifier emit `UNBOUND_VARIABLE`. The field exists; the verifier punishes
using it.

---

## 4. New gaps discovered (not in G1–G8)

| ID | Gap | Frequency | Why it matters |
|---|---|---|---|
| **N2** | Let-bound locals (`ldecl`) carry a **definition**; `Binding` has no `value` field — and, uniquely, **no escape hatch**: `Binding(**item)` rejects extra keys | 9.2% of records | The only gap with nowhere to put the data |
| **N3** | `action.external_premise_refs` has no slot; `target_ids` is restricted to `object_ids ∪ {"goal"}` by `native.py:231-241` | 65.8% of records | Blocks premise-selection task families |
| **N4** | `Obligation` has no `scope_id` | — | This is *why* the multi-goal workaround fails; N4 and G1 are one problem |
| **N5** | All 304 constructed states passed the wire validator **and `NativeVerifier` with zero issue codes** — because `lean.*` operations match none of its rules | 100% | **"The verifier accepts it" carries no information about imported data.** A silent-acceptance failure mode |

**N5 is the most dangerous finding in this report.** A future session importing formal data and
seeing a clean verifier result would reasonably conclude the import was sound. It would be
concluding nothing at all.

---

## 5. Classification

Driven by measured frequency, not intuition.

| Class | Gaps | Rationale |
|---|---|---|
| **REQUIRED** | G1 (+N1 goal identity/focus, +N4 obligation scope); G2/G6 **as one structure**; G3; N2 | The only classes that block import or lose data irrecoverably |
| **BACKEND_EXTENSION** | G4, G5, N3 | Ubiquitous, but already byte-lossless in `attributes` / `binder_kind` / warrant fields, and **nothing in the Arena reasons about them**. A lossless backend-native field suffices |
| **DEFER** | G7 | Zero evidence in this corpus |
| **NOT_CANONICAL** | G8, N5 | Verification layer, not Σ |

Probe D confirmed that arbitrary JSON survives `attributes` byte-identically, which is what makes
the BACKEND_EXTENSION route viable rather than merely convenient.

---

## 6. Saturation

- **Semantic constructs:** 54 new in records 1–50 (108 per 100), 1 in 51–100 (2 per 100),
  **0 thereafter**. 55 distinct in total — **saturated**.
- **Binder × type structures:** 19, 5, 3, 1 new (38.0 / 10.0 / 6.0 / 2.9 per 100) — **still
  climbing**; 28 of a plausible ~64-cell space.

**The caveat is larger than the result.** This is **one source** (Lean 4.10 elaborator over
mathlib4/Batteries, one extractor). Saturation of a vocabulary that is fixed by Lean's own `Expr`
type is close to tautological. **No saturation claim across heterogeneous sources is supported by
this pilot**, and none is made. Treat 55 as a lower bound.

A second source is required before the saturation criterion in `docs/CORPUS_STRATEGY.md` can be
evaluated at all. The specific candidates: a **Metamath / set.mm** export (the only thing that can
test G7), the gold125 trajectory schema in `hmlt-reasoning-corpus-lean-attestation/schemas/`, or
the Arena's own symbolic-domain states.

---

## 7. Architectures explicitly NOT adopted

Treated as **unproven hypotheses**, with the experiment that would settle each recorded in the
JSON: Typed E-Graph core · MMT/OMDoc · Lean-native IR · Metamath-native IR · universal micro-action
decomposition.

Note that **this corpus cannot test micro-action decomposition at all**: `action.kind` is the
single constant `LEAN_ELABORATED_TACTIC_OCCURRENCE` with no tactic name recorded. Anyone proposing
a universal micro-action ontology on the strength of this corpus would be proposing it on no
evidence.

**Losslessness > elegance.** The measured result points at a small number of REQUIRED structural
changes plus backend-native fields for the rest — not at a new architecture.

---

## 7b. Correction — which mathlib checkout is built

An independent audit reported that the pinned checkout holds only **38 `.olean`** files and
concluded the "fully built mathlib" claim was unsupported. Both readings are correct; they are
**different checkouts of the same commit** `29dcec07…`, and the ambiguity is worth recording
because two careful audits reached opposite conclusions from it:

| Path | Built? | Size | `.olean` |
|---|---|---|---|
| `HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec07…/mathlib4` | **yes** | 18 GB | **5,680** |
| `HML_V3/external/checkouts/mathlib4-29dcec0` | no (source only) | 349 MB | 38 |

Offline replay capability therefore **stands**, but only from the `runtime_work` path. Any design
that needs kernel adjudication must name that path explicitly, and must still budget the measured
**32/100** replay yield.

## 8. What a future session should do, in order

1. **Do not bump `schema_version` casually.** It re-hashes the project (§2). Batch every REQUIRED
   change into one version, and plan the re-hash.
2. **Fix `native.py:136` first** — it is a small, self-contained bug that currently punishes honest
   `binder_kind` values (G5).
3. **Add verifier coverage for imported operations before importing at scale**, or record
   explicitly that acceptance means nothing for `lean.*` operations (N5).
4. **Run the second-source pressure test** (Metamath) before making any saturation claim.
5. Only then consider the REQUIRED structural set: multi-goal with per-goal context and obligation
   scope (G1+N1+N4), the metavariable/substitution structure (G2≡G6), structured types (G3), and
   let-values (N2).
