# HC-V0 ACCEPTANCE TESTS

**Source:** manual §42 (acceptance test categories), §50 Phase E (required tests), §40.5 (success
criterion). Authority rank 3 (`spec/00_CONSTITUTION.md` C7). Restricted adjectives carry
`spec/01_GLOSSARY.md` Part B meanings.

**Scope reduction (§0.1, §42).** §42 says CI *SHOULD* contain tests in seven categories. This
document keeps only what HC-V0 must actually pass, and marks the rest `DEFERRED`. Adding a test
for a gate HC-V0 does not run would be the bureaucracy §0.1 forbids.

**Status vocabulary.** `PRESENT` — a test exists and is named below. `PARTIAL` — a related test
exists but does not assert the manual's requirement. `MISSING` — nothing asserts it.
Test files marked *(untracked)* were written concurrently by other agents and were uncommitted when
this document was written; their existence was verified by reading the worktree on 2026-09-08.

---

## 1. §50 Phase E — the eight required tests

These are named individually by §50 Phase E step 25 and are the gating set for HC-V0.

| # | §50 requirement | Status | Where |
|---|---|---|---|
| E1 | **truth cannot mutate** | **PRESENT** | `tests/evolution/test_loop.py::test_the_gate_kills_a_renderer_that_drops_an_assumption` and `::test_the_gate_accepts_every_honest_seed_surface` *(untracked)*; supported by `tests/model_view/test_model_view.py::test_tampered_projection_fails_independent_recomputation` and `::test_track_c_projection_is_recomputed_and_canonical_truth_is_recovered`; `tests/languages/test_seed_roundtrip.py::test_seed_languages_are_deterministic_and_lossless` |
| E2 | **intervention class is explicit** | **MISSING** | Nothing in the repository names an intervention class. See CONFORMANCE GAPS 1. Required assertions: every `LanguageCandidate` carries one of the eight §6.26 values; every fitness record carries the same value; a declared class that does not match the genome delta raises `DEAD_UNDECLARED_INTERVENTION` (§12.4); an `R_ONLY` comparison that fails the §26.2 fixed-variable list is refused. |
| E3 | **dead candidates cannot evaluate** | **PARTIAL** | `tests/evolution/test_loop.py::test_a_killed_candidate_is_never_scored` *(untracked)* asserts the behaviour for the semantic gate. **MISSING:** the same assertion over all thirteen §21 terminal states and all eight §12.4 compiler outcomes. |
| E4 | **lineage / provenance determinism** | **PRESENT** | `tests/evolution/test_loop.py::test_two_runs_are_identical_apart_from_timing`, `::test_pareto_rank_selection_is_deterministic` *(untracked)*; `tests/evolution/test_record.py::test_content_hash_is_stable_across_processes`, `::test_content_hash_ignores_only_the_wall_clock` *(untracked)*; `tests/genome/test_mutation_and_crossover.py::test_mutation_is_deterministic_and_records_parent_and_tests`, `::test_history_is_explicit_and_immutable` |
| E5 | **action macro kernel-cost accounting** | **MISSING** | §13.1 requires every episode to record `model_action_count`, `kernel_step_count`, tool calls, verifier calls, wall-clock and tokens/compute, so that bundling many kernel operations into one model action cannot create a fake efficiency win (§0 correction 7). No `kernel_step_count` field exists. `arena/trajectory/schema.py`'s `Horizon` carries `achieved / verified / reference / solver_actions / reference_actions` and no kernel-cost term. |
| E6 | **fitness-memory append-only semantics** | **PRESENT** | `tests/evolution/test_record.py::test_the_store_is_append_only`, `::test_an_identical_re_append_is_reuse_not_a_duplicate`, `::test_the_guard_raises_when_the_same_conditions_give_a_new_reading`, `::test_a_new_model_or_context_is_a_new_record_never_an_overwrite`, `::test_a_tampered_stored_hash_is_refused` *(untracked)* |
| E7 | **task vs trajectory distinction** | **PARTIAL** | `tests/trajectory/test_schema.py::test_horizon_counts_actions_not_reference_length` and `::test_verified_horizon_is_zero_unless_the_kernel_closed_it` *(untracked)* assert that a recorded reference length is not the model's horizon — the §17.6 half. **MISSING:** the §6.25/§17.1 half, because no `VerifiedTask` object exists. Required assertions: a `VerifiedTrajectory` collection cannot be presented as an interactive task; a Solver action differing from the recorded action is not scored wrong unless the verifier says so (§17.3); a replay-only source cannot license an autonomous long-horizon claim (§40.3). |
| E8 | **one complete outer generation** | **PRESENT** | `tests/evolution/test_loop.py::test_one_generation_runs_end_to_end_offline`, `::test_the_archive_receives_rows_and_ranking_returns_a_front`, `::test_the_fitness_vector_is_not_collapsed_to_a_scalar`, `::test_the_loop_makes_no_network_call` *(untracked)* |

**E2 and E5 are the two that block §40.5.** The success criterion names "truthful intervention
classification" explicitly, and §13.1's accounting is what stops an `A_CHANGE` comparison from being
won by hiding cost.

---

## 2. §42 categories — V0 subset

### 2.1 Specification / schemas (§42)

| Requirement | Status | Where |
|---|---|---|
| schema validation | **PRESENT** | `tests/genome/test_schema_and_registry.py::test_genome_parser_rejects_missing_unknown_and_invalid_gene_values`, `::test_all_fourteen_gene_families_are_machine_readable` |
| no duplicate IDs | **PRESENT** | `tests/genome/test_schema_and_registry.py::test_registry_rejects_duplicate_ids_and_gene_vectors`, `::test_seed_population_has_stable_unique_ids_and_hashes` |
| glossary uniqueness | **MISSING** | No test reads `spec/01_GLOSSARY.md`. A V0-adequate check is: every term defined once; every `spec/` use of a §1 restricted adjective cites a Part B entry or defines an inline operational meaning. |
| authority precedence | **MISSING** | No code path reads `spec/00_CONSTITUTION.md` C7. |
| unresolved ambiguity lint | **MISSING** | No test asserts that `spec/02_CLAIM_LEDGER.jsonl` parses, carries the §37 field set exactly, uses only §37 types, and has unique ids. **This is the cheapest missing test in the set and should be written first.** |

### 2.2 Language genome (§42)

| Requirement | Status | Where |
|---|---|---|
| deterministic serialization | **PRESENT** | `tests/genome/test_schema_and_registry.py::test_genome_roundtrip_preserves_hash` |
| hash stability | **PRESENT** | as above; `tests/evolution/test_record.py::test_content_hash_is_stable_across_processes` *(untracked)* |
| constraint rejection | **PARTIAL** | `tests/genome/test_mutation_and_crossover.py::test_mutation_rejects_invalid_resulting_combination` and `test_schema_and_registry.py::test_invalid_dependency_is_reported` reject invalid combinations of the current fourteen-gene genome. **MISSING:** rejection against the §11 constraint list — `INDEXED` binders without a deterministic index-assignment procedure, `GRAPH` topology without deterministic node identity, `COMPOSITIONAL_SYMBOLIC` morphology without a declared morpheme grammar, `ACTION_STATE_DELTA` without state-delta validation, explicit dependency projection without a derivation algorithm — each failing as `DEAD_GENOME_CONSTRAINT`. |
| mutation provenance | **PRESENT** | `tests/genome/test_mutation_and_crossover.py::test_mutation_is_deterministic_and_records_parent_and_tests`, `::test_proposal_cannot_understate_structural_impact` |
| lineage integrity | **PRESENT** | `tests/genome/test_mutation_and_crossover.py::test_history_is_explicit_and_immutable` |
| **a one-gene mutation changes the rendered bytes** | **PRESENT, and it fails for seven of eight seeds by design** | `tests/evolution/test_loop.py::test_an_inert_mutation_is_detected_and_recorded_as_inert` and `::test_live_and_inert_families_partition_the_genome` *(untracked)*. This test category is not in §42; it is required here because a mutation that changes 0 bytes makes the comparison vacuous (`CLM-FACT-GENOMEBLIND-011`). |

### 2.3 Compiler (§42)

| Requirement | Status | Where |
|---|---|---|
| deterministic rendering | **PRESENT** | `tests/languages/test_seed_roundtrip.py::test_seed_languages_are_deterministic_and_lossless` |
| binding / scope preservation | **PARTIAL** | `tests/languages/test_malformed.py::test_duplicate_semantic_ids_are_rejected`, `::test_structured_english_rejects_reordered_roles` |
| type preservation | **PARTIAL** | covered incidentally by round-trip; no dedicated assertion |
| semantic parity | **PRESENT** | `tests/experiments/test_precondition_parity.py` (13 tests); `tests/model_view/test_model_view.py::test_track_e_is_exactly_recoverable_surface_without_content_projection` |
| no answer leakage | **PRESENT** | `tests/assurance/test_side_channels.py::test_literal_target_leak_is_critical`, `::test_balanced_clean_records_have_no_literal_leak`; `tests/model_view/test_model_view.py::test_projection_never_reads_hidden_action_pools`; `tests/experiments/test_rendered_prompt_adversary.py` (21 tests) |
| action lowering | **MISSING** | No `lower_L(a_L) -> [a_K…]` interface exists, so `DEAD_ACTION_LOWERING` cannot be tested. The committed action space is "pick one of k" (`docs/HAMILTONIAN_CHESS_META_MDP.md` §1). |

### 2.4 Trajectory world (§42)

| Requirement | Status | Where |
|---|---|---|
| state / action / next-state linkage | **PRESENT** | `tests/trajectory/test_schema.py` asserts `len(states) == len(actions) + 1` and endpoint chaining, so unrelated one-step probes cannot be concatenated *(untracked)* |
| deterministic replay | **PRESENT** | `tests/trajectory/test_lean_backend.py::test_bank_selection_is_deterministic_given_a_seed`, `::test_replay_driver_produces_a_verified_trajectory_of_at_least_five_steps` *(untracked)* |
| verifier evidence | **PRESENT** | `tests/trajectory/test_lean_backend.py::test_verify_bank_catches_missing_step_evidence`, `::test_verify_bank_refuses_an_unfinished_episode`, `::test_string_equality_is_never_used_for_verification`, `::test_state_identity_used_by_the_arena_is_the_backend_id` *(untracked)* |
| horizon calculation | **PARTIAL** | `tests/trajectory/test_schema.py::test_horizon_counts_actions_not_reference_length`, `::test_verified_horizon_is_zero_unless_the_kernel_closed_it` *(untracked)*. **MISSING:** `KernelStepCount`, `DependencyDepth`, and `MinimalProofLength: VALUE \| UNKNOWN` (§6.32–§6.34, §17.6). |
| split isolation | **MISSING** | No test asserts that the sealed LeanDojo splits are unread, that splits are grouped by theorem/module rather than by step (§18.2), or that a `PROMOTION`/`FINAL` source did not guide search (§30.4). |
| provenance hashes | **PRESENT** | `tests/trajectory/test_schema.py::test_pp_hash_tampering_is_detected_on_load`, `::test_content_hash_tampering_is_detected_on_load`, `::test_derived_trajectory_id_is_a_function_of_the_content` *(untracked)* |

### 2.5 Evaluation (§42)

| Requirement | Status | Where |
|---|---|---|
| matched task identity | **PRESENT** | `tests/experiments/test_game_r_formal_v1.py` (cache identity, parity, budget) |
| cache key completeness | **PRESENT** | as above; `tests/evolution/test_record.py::test_the_identity_carries_exactly_the_eleven_declared_components`, `::test_a_missing_identity_component_is_a_refusal_not_a_blank_slot` *(untracked)* |
| prompt hash identity | **PRESENT** | `tests/experiments/test_game_r_formal_v1.py` |
| candidate / task pairing | **PRESENT** | as above |
| paired statistics | **PRESENT** | `tests/experiments/test_precondition_power.py` (31 tests) |
| no train / promotion overlap | **PARTIAL** | `tests/evolution/test_record.py::test_a_confirmatory_record_without_a_preregistration_is_malformed` *(untracked)* asserts the record-level guard; no test asserts pool disjointness itself |
| no hidden data exposure | **PRESENT** | `tests/trajectory/test_arena_v0.py::test_the_observation_never_contains_the_remaining_reference_proof`, `::test_observation_guard_refuses_to_show_a_remaining_reference_tactic`, `::test_leakage_filter_drops_the_two_measured_channels` *(untracked)* |

### 2.6 Evolution (§42)

Covered by E3, E4, E6, E8 above. §42's four items — lifecycle transition legality, population update
determinism, archive update, dead candidate cannot be evaluated, one full smoke generation — map
onto them. **Lifecycle transition legality is `MISSING`**: no enumerated §21 state machine with
code-enforced transitions exists (see CONFORMANCE GAPS 3).

### 2.7 Refuter (§42)

| Requirement | Status | Where |
|---|---|---|
| alpha-renaming | **PRESENT** | `tests/assurance/test_properties.py`, `tests/assurance/test_exhaustive.py` |
| answer-order controls | **PRESENT** | `tests/experiments/test_rendered_prompt_adversary.py`; the option-rotation position audit in `tests/experiments/test_game_r_precondition_founder_v1.py` (37 tests) |
| surface leakage tests | **PRESENT** | `tests/assurance/test_side_channels.py`, `tests/experiments/test_rendered_prompt_adversary.py` |
| verifier failure distinction | **PARTIAL** | `tests/assurance/test_exhaustive.py::test_native_verifier_survives_declared_semantic_attack_suite`. **MISSING:** an assertion that `UNKNOWN != FALSE`, `TIMEOUT != FALSE` and `TOOL_ERROR != MATHEMATICAL_INVALID` at the adapter boundary (§28). |
| parser permissiveness regression | **PRESENT** | `tests/languages/test_malformed.py` (5 tests), `tests/assurance/test_fuzz.py` |

---

## 3. DEFERRED test categories

`DEFERRED` (§37), because HC-V0 does not run the gate they would guard:

- matched-adaptation and learning-curve tests (Gate 2–3);
- confirmation, multiplicity and selection-adjustment tests over fresh project-hidden data (Gate 5);
- multi-Solver-family robustness tests (Gate 6);
- surrogate and Architect-learning eligibility tests (§34);
- searchability-metric tests (§31) — these become required for Pilot 1, not V0.

---

## 4. Baseline commands (§50 Phase E step 24)

```text
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy arena
```

**NOT RUN by the specification agent.** This agent wrote no code and executed no test suite; two
other agents were concurrently modifying `arena/trajectory/` and `arena/evolution/`, so any result
recorded here would describe a moving tree. Recording "not run" is required by the commit protocol
and by §43's preference for explicit states. The last recorded full-suite figure is
**1,132 passed, 1 skipped** with `ruff check`, `ruff format --check` and `mypy arena` reporting no findings, from
`docs/PHASE8_SALVAGE_HANDOFF.md` §2 — that figure predates every untracked change listed above and
**must not** be quoted as a current result.

---

## CONFORMANCE GAPS

1. **E2 has no implementation to test.** `InterventionClass` is absent from the repository
   (`CLM-GAP-INTERVENTION-040`). §50 Phase E names "intervention class is explicit" as a required
   test and §40.5 names truthful intervention classification as a success criterion. Type:
   `KNOWN_FACT`. **Blocking for HC-V0 completion.**
2. **E5 has no field to test.** No `kernel_step_count` exists anywhere; §13.1 requires it per
   episode and §0 correction 7 explains why. Type: `KNOWN_FACT`. **Blocking for any `A_CHANGE`
   comparison; non-blocking for an `R_ONLY` V0 run, which changes no action semantics — but the
   field must still be recorded, because §13.1 says "every episode".**
3. **The §21 lifecycle state machine is not enumerated in code**, so "candidate lifecycle transition
   legality" (§42) cannot be tested and E3 can only be asserted for the one gate that exists. Type:
   `KNOWN_FACT`.
4. **No test reads anything under `spec/`.** The five §42 specification-category checks are all
   `MISSING` or `PARTIAL`. The cheapest and highest-value one is a parser/lint over
   `spec/02_CLAIM_LEDGER.jsonl` asserting the §37 record shape, legal §37 types, and unique ids.
   Type: `KNOWN_FACT`.
5. **Test-file references above point partly at untracked files.** `tests/evolution/` and
   `tests/trajectory/` were uncommitted when this document was written. If either package changes
   shape before commit, the E1/E3/E4/E6/E7/E8 rows must be re-verified rather than trusted. Type:
   `KNOWN_FACT`.
