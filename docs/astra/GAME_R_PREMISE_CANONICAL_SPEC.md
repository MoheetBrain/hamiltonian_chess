# Scoped Game-R premise-selection state

Status: research-only prototype, generated on 2026-09-07 from Astra branch base `9f28c0c1b673804648052a54a65cf32eee875b05`.

This envelope makes one recorded LeanDojo premise-citation item available to multiple renderers. It is intentionally scoped. It does not replace `arena-canonical-v0.1.0`, modify the Gold world, or claim to be a lossless elaborated Lean AST.

## Frozen experiment object

`CanonicalPremiseSelectionState` contains:

| Field | Meaning | Assurance |
|---|---|---|
| `task_id` | stable item identity derived from source trace identity and seed | deterministic adapter ID |
| `provenance` | repository, LeanDojo version, mathlib commit, theorem, file and trace step | source record metadata |
| `formal_system` | `Lean4` | dataset declaration |
| `context` | exact prefix before the one unambiguous `⊢` delimiter | Lean pretty-printed source text |
| `goal` | exact `⊢ ...` suffix | Lean pretty-printed source text |
| `candidate_premises` | exactly six consistently ordered candidates, each with a neutral ID, visible name, complete admitted source header and provenance | source-header extraction; no kernel elaboration |
| `target_choice_id` | the one premise name marked by the recorded LeanDojo citation | private oracle; never rendered |
| `oracle_evidence` | hashes of tactic, annotation and successor plus citation definition path | private audit evidence; never rendered |
| `source_raw_state` | exact original state, checked equal to `context + goal` | private provenance/debugging |
| `audit_metadata` | sampler tier, frequencies, source order and partition | private audit only |

The task is attribution of the recorded next-step citation. It is not a claim that the cited premise was the only applicable premise, sufficient for proof, or mathematically optimal. The adapter uses the real training trace and corpus, with no model call and no Lean replay.

## Admission and ordering

Only `random/train.json` and `corpus.jsonl` are read. The source pin is checked against LeanDojo Benchmark 4, version 2.0.0 and mathlib commit `29dcec074de168ac2bf835a77ef68bbe069194c5`. Held-out files are byte-hashed only. The repository audit records all four historical evaluation files as exposed; they are not a clean promotion set.

Admitted rows have one cited premise, one goal delimiter, a complete explicit theorem/lemma source header for every candidate, import-closure availability, and a conservative same-file declaration-order check. The first 5,000 training theorems are a bounded development pool. One row per theorem group is admitted, then a deterministic 80/20 theorem-group split produces 240 development-training and 60 development-held-out items.

Candidates use the L3 same-module, frequency-matched sampler: 750 same-proof and 750 same-module distractor placements in the bank. A candidate order is generated once by `sha256(seed | task_id | premise_id)` and reused by every renderer. The answer follows the candidate semantic ID after permutation.

## Renderer contract

`visible_projection(state)` is the only renderer input. It contains the formal system, context, goal, question, candidate names/statements and neutral option labels. It contains no target ID, tactic, successor, split label, private metadata or answer-specific relation. Five deterministic research codecs are supported: structured English, JSON AST, S-expression, HML-compatible assignment lines and compact symbolic aliases. Their bytes differ; their decoded allowlisted inventory is identical.

The production founder languages are not silently claimed to support this object. Their existing wire schemas require `CanonicalState` expressions/actions and have no honest carrier for source-native Lean context, dependent binder information, premise citation choices or source-header assurance. The coverage report records this as `REPRESENTATION_COVERAGE_FAILURE`; this bridge remains an adapter experiment until a future canonical version admits these fields.

## Relation to Arena variables

`Σ` is the underlying formal proof-state/citation record. `P` is the allowlisted context, goal, candidate names and candidate statements. `R` is only the organization and serialization of that fixed projection. `τ`, `π`, `C`, `D`, `U`, `V` and `B` are not run by Astra and must be frozen by a future experiment. The recorded citation is a verifier-backed dataset annotation, not an independently replayed kernel oracle.
