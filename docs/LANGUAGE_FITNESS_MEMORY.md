# Language Fitness Memory — record schema V0

**Status: `DESIGN_ONLY`. No store is created, no record is written, no surrogate is trained.**

This specifies the durable record that the outer loop writes once per evaluated
`(parent, mutation, environment)` triple. It is the dataset a surrogate
`predicted ΔJ(parent, mutation, environment)` is eventually fitted on
(`docs/HAMILTONIAN_CHESS_META_GOAL.md` §6.5). Fitting is explicitly out of scope; the schema exists
so that fitting becomes possible without a retrospective reconstruction from logs.

Companion document: `docs/LONG_HORIZON_FITNESS_V0.md` defines the fitness vector these records
carry.

---

## 1. Is there an existing store to reuse?

**Yes, partly. Reuse `arena/storage/db.py`; extend it; do not replace it. Reuse
`arena/storage/artifacts.py` unchanged for payloads.**

### `arena/storage/db.py` (388 LOC, tested in `tests/storage/test_db.py`)

A small SQLite control plane with `PRAGMA foreign_keys = ON` and 14 tables. What it already gives:

| Existing table | Fitness-memory role | Verdict |
|---|---|---|
| `languages(language_id, genome_hash, genome_json, family, status)` | parent and child genomes | **reuse directly** — `register_language` returns `stable_hash(genome)` |
| `language_parents(language_id, parent_id)` | lineage edges | **reuse directly** |
| `mutations(mutation_id, parent_id, child_id, proposal_json, decision)` | the mutation | **reuse the identity, extend the payload** — see §3.3 |
| `evaluations(evaluation_id, language_id, task_set_hash, tier, config_hash, status, result_hash, result_json)` | one evaluation at one ladder level | **the right shape, wrong key** — see §4 |
| `metrics(evaluation_id, metric, value, lower_bound, upper_bound)` | the fitness vector with CIs | **reuse** — the CI columns already exist and are unused |
| `failures(failure_id, language_id, class, severity, payload_json, regression_status)` | failure modes | **reuse**; the class vocabulary comes from `arena/training/verified_eval.FailureClass` and `arena/experiments/game_r_formal_v1.RowStatus` |
| `models(model_id, digest, tokenizer, metadata_json)` | model identity | **reuse; make it mandatory** — currently nothing writes it |
| `artifacts(artifact_id, kind, path, sha256, metadata_json)` | content-addressed payload pointers | **reuse** |
| `matches`, `hall_of_fame`, `training_runs`, `worlds`, `tasks`, `metadata` | league / world / training bookkeeping | reuse as-is |

### `arena/storage/artifacts.py` (37 LOC)

`ArtifactStore.write_json` writes `canonical_json(value) + "\n"` and returns
`StoredArtifact(artifact_id="artifact:<sha256[:20]>", path, sha256)`. Deterministic and
content-addressed. **Reuse unchanged** for every large payload (raw transcripts, survival curves,
adversary reports). The database stores the digest and the path; it does not store the blob.

### What is missing, precisely

Five gaps, and they are the entire reason this document exists:

1. **`record_evaluation` uses `INSERT … ON CONFLICT DO UPDATE`.** It silently overwrites a prior
   result at the same key. That is the opposite of append-only.
2. **The evaluation key omits the model.** `evaluation_id = "eval:" + stable_hash({language_id,
   task_set_hash, tier, config})`. Two runs of the same language on the same tasks under **two
   different Solvers** collide into one row and the second overwrites the first. This is the
   `CROSS_CONDITION` failure, at the database layer, with no refusal.
3. **`metrics` has no `n`, no cluster count, no estimator name.** A value with an interval but no
   sample size cannot be pooled, re-tested, or checked for granularity substitution.
4. **Nothing links an evaluation to a *mutation*.** `evaluations.language_id` is the child; the
   parent-vs-child comparison — which is the surrogate's actual label — has nowhere to live.
5. **`arena/surrogate/features.extract_features` flattens a genome and nothing else.** It has no
   slot for operator, environment, model, horizon bucket, or budget. The surrogate as written
   predicts hard-gate survival from genome shape; the surrogate the mission needs predicts ΔJ from
   `(parent, mutation, context)`.

---

## 2. The three discipline rules

### 2.1 Append-only

Records are **immutable once written**. There is no UPDATE path and no DELETE path.

- Every table in §3 is written with `INSERT` only. `INSERT OR REPLACE` and
  `ON CONFLICT DO UPDATE` are prohibited in the fitness-memory tables; a duplicate primary key is an
  **error**, surfaced, not absorbed.
- A superseded record is **superseded, not edited**: write a new record with a new
  `record_id`, and set `supersedes = <old record_id>` plus `supersede_reason`. Both rows survive.
  A reader that wants "current" filters on `record_id NOT IN (SELECT supersedes FROM …)`.
- Corrections follow the same rule. `docs/PROJECT_LEDGER.md`'s append-only discipline is the model.
- **A failed or refused evaluation is a record.** `HAMILTONIAN_CHESS_META_GOAL.md` §7: *"Failure is
  recorded, never quietly regenerated."* `status ∈ {COMPLETE, REFUSED, ABORTED, VOID}` with a
  `void_code`; a refusal carries the exception class from `game_r_formal_v1.HarnessRefusal`'s
  hierarchy (`ParityViolation`, `CacheIdentityViolation`, `BudgetExceeded`,
  `TokenAccountingRefusal`). A REFUSED record is training data: it tells the surrogate that this
  region of mutation space produces unevaluable candidates.

### 2.2 Keying — cross-condition reuse must be impossible by construction

This is the lesson of `game_r_formal_v1.cache_identity`, lifted from the call cache to the record
store. That function takes **eight** components —

```
experiment_version · model_digest · model_revision · runtime_condition ·
decoding_hash · task_id · candidate_id · prompt_hash
```

— refuses to build an identity with any component missing or empty, and `ResponseCache.load` raises
`CacheIdentityViolation` when a stored record's identity differs from the requested one
(`classify_cache_scope` → `CacheScope.CROSS_CONDITION`). Reuse under an *identical* identity is
`SAME_CONDITION_REUSE` and is legitimate; that distinction exists because Phase 6's rule ("cache
hits > 0") fired on 61 rows that were the same solver resuming its own work.

**The fitness-memory analogue.** A record's primary key is

```
record_id = "lfm:" + stable_hash(evaluation_identity)
```

where `evaluation_identity` is a mapping with **exactly** these eleven components, all required and
all non-empty:

| Component | Source |
|---|---|
| `schema_version` | this document's version constant |
| `harness_version` | `game_r_formal_v1.HARNESS_VERSION` |
| `parent_genome_hash` | `LanguageGenome.candidate_hash` |
| `child_genome_hash` | ditto |
| `mutation_hash` | `MutationProposal`'s stable hash |
| `environment_version` | e.g. `arena-precondition-ladder-v2.0.0` |
| `task_set_hash` | `stable_hash(sorted(qualified_task_ids))` |
| `model_digest` | the Ollama/backend digest |
| `model_revision` | `f"{solver.revision}|{counter.tokenizer_id}"` — the form `run_item` already builds |
| `decoding_hash` | `game_r_formal_v1.decoding_hash(decoding, response_schema)` |
| `ladder_level` | `L0`…`L6` |

Three consequences, all intentional:

1. **The same `(parent, mutation, environment)` re-scored under a different model, decoding,
   tokenizer, task set, harness version or ladder level produces a different `record_id`.** It is a
   *new record*, never an overwrite. The failure mode "silently re-scored under different
   conditions" is structurally impossible rather than forbidden by convention.
2. **A duplicate `record_id` with a different `result_hash` is a hard error** —
   `FitnessMemoryIdentityViolation`, mirroring `CacheIdentityViolation`. It means the pipeline is
   non-deterministic under a fully-specified identity, which is a bug worth stopping for.
3. **A missing component is a refusal to write**, exactly as `cache_identity` refuses to build an
   identity with a missing component. There is no default model digest, no default decoding.

**Grouping key for the surrogate.** Separately from `record_id`, every record carries

```
condition_id = stable_hash({model_digest, model_revision, decoding_hash,
                            environment_version, task_set_hash, ladder_level})
```

This is the key the surrogate groups by. Two records may only be compared, differenced, or pooled
when their `condition_id` matches. **Every query in §5 filters on `condition_id` first.** That is
the granularity-substitution guard: a ΔJ computed across two conditions is not a ΔJ.

### 2.3 Content hashes everywhere

Every payload larger than a scalar is stored as an artifact and referenced by
`(artifact_id, sha256, path)` from `ArtifactStore`. The record stores `result_hash =
stable_hash(result_json)` so a reader can verify the record was not edited in place. `canonical_json`
(sorted keys, fixed separators) is the only serialiser, so hashes are stable across processes.

---

## 3. The record

One logical record per `(parent, mutation, environment, condition, level)`. Physically, four new
tables plus reuse of the existing ones.

### 3.1 `fitness_records` — the spine

| Field | Type | Notes |
|---|---|---|
| `record_id` | TEXT PK | `"lfm:" + stable_hash(evaluation_identity)` (§2.2) |
| `schema_version` | TEXT | `arena-language-fitness-memory-v0.1.0` |
| `created_at` | TEXT | UTC ISO-8601; informational only, never part of identity |
| `identity_json` | TEXT | the full eleven-component `evaluation_identity`, canonical JSON |
| `condition_id` | TEXT | §2.2 grouping key, indexed |
| `generation` | INTEGER | outer-loop generation index |
| `parent_genome_id` | TEXT → `languages` | |
| `parent_genome_hash` | TEXT | |
| `child_genome_id` | TEXT → `languages` | |
| `child_genome_hash` | TEXT | |
| `mutation_id` | TEXT → `mutations` | |
| `ladder_level` | TEXT | `L0`…`L6` |
| `status` | TEXT | `COMPLETE` / `REFUSED` / `ABORTED` / `VOID` |
| `void_code` | TEXT NULL | e.g. `VOID_CEILING`, `VOID_SAMPLE_SIZE`, `ParityViolation` |
| `promoted` | INTEGER | did this record's candidate advance a level |
| `result_hash` | TEXT | `stable_hash` of the full result payload |
| `result_artifact_id` | TEXT → `artifacts` | pointer to the full JSON |
| `supersedes` | TEXT NULL | prior `record_id` this corrects |
| `supersede_reason` | TEXT NULL | required when `supersedes` is non-null |

### 3.2 Genomes — `parent_genome` / `child_genome`

Stored once each in the existing `languages` table via `register_language(language_id, family,
genome)`, which already returns `stable_hash(genome)`; lineage in `language_parents`. The record
references them by id **and** by hash, so a later genome-id reuse cannot silently repoint an old
record.

Also stored per genome, in a `genome_descriptors` table, because §3.3 of the fitness spec needs them
and because the seed population is already known to be far less diverse than its gene values imply
(`e1_coverage_max_direction = 0.9860` between `L3_JSON_AST` and `L6_GRAPH_TRIPLES`,
`artifacts/reports/precondition_parity_audit.json`):

`gene_values_json` · `phenotype_hash` · `e1_coverage_vs_incumbent` ·
`seqmatch_ratio_vs_incumbent` · `mean_prompt_tokens_by_stratum_json`.

### 3.3 `mutation` — operator, parameters, and which gene

The existing `mutations.proposal_json` already carries a serialised `MutationProposal`, which
already carries typed `GeneChange(gene, from_value, to_value)` tuples and validates them against
`parse_gene_value`. **Promote the parts the surrogate needs into columns** so they are queryable
without JSON extraction:

| Field | Source |
|---|---|
| `mutation_id` | existing PK |
| `mutation_hash` | `stable_hash(proposal.to_dict())` |
| `operator` | `MutationOperator` — one of the 24 in `arena/genome/mutation.py` |
| `changed_genes` | JSON array of `GeneFamily` values; `OPERATOR_GENE_SCOPE` constrains which are legal per operator |
| `gene_changes` | JSON array of `{gene, from_value, to_value}` |
| `n_genes_changed` | INTEGER — the mutation's radius |
| `evaluation_tier` | `EvaluationTier` (`surface` / `structural` / `canonical-governance`) |
| `soundness_risk` | `SoundnessRisk` (`low` / `medium` / `high`) |
| `layer` | **new**: `A` / `B` / `C` / `D` per `HAMILTONIAN_CHESS_META_GOAL.md` §4. Layer A is never legal. This column does not exist today because the current genome has **0 CONTENT_BEARING and 0 REASONING_PROTOCOL genes** (`artifacts/reports/genome-content-audit.json`) — every existing mutation is Layer D or C-surface. It must exist before the meta-genome widens, or the widening will be unqueryable. |
| `parameters_json` | operator-specific arguments |
| `decision` | `MutationDecision` (`pending` / `promoted` / `rejected`) |

### 3.4 `evaluation_context`

`arena` (environment module + version) · `mechanism` · `task_set_hash` ·
`task_ids_artifact_id` (the full sorted id list, content-addressed — not inlined) ·
`horizon_bucket` (`H1`/`H5`/`H10`/`H20`/`H50`/`FULL`, or `NA`) ·
`n_problems` · `n_trajectories` · `n_clusters` ·
`pool_role` (`DEV` / `SELECTION` / `QUALIFICATION` / `PROMOTION` / `OOD`) ·
`pool_disjoint_from` (JSON array of task-set hashes this pool is asserted disjoint from) ·
`horizon_length_confounded` (BOOLEAN, from ρ(H, prompt tokens) > 0.9) ·
`dependency_density_json` (T1 / T2 / T3 from the fake-horizon detector).

`pool_role` and `pool_disjoint_from` are what make "selection and evaluation are separate"
(`HAMILTONIAN_CHESS_META_GOAL.md` §7) *checkable after the fact* rather than merely asserted at the
time. V7's L1 defect — selection and qualification sharing the same 24 rows — would have been a
one-line query against these two fields.

### 3.5 `model`

`model_id` · `model_name` · `model_digest` · `model_revision` · `tokenizer_id` ·
`tokenizer_exact` (BOOLEAN) · `template_hash` · `context_length` · `capabilities` ·
`decoding_json` · `decoding_hash` · `response_schema_hash` · `runtime_condition` ·
`available` (BOOLEAN) · `last_seen_at`.

**`available` and `last_seen_at` are not bureaucracy.** On 2026-09-08 the Solver named in a live
preregistration (`qwen38-rvn`, digest `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`)
was deleted from the local Ollama along with its manifest; the digest is unrecoverable and the name
is a local build that cannot be re-pulled (`docs/PHASE8_SALVAGE_HANDOFF.md` §1). Every measurement
taken against it is now permanently unreproducible. The store must be able to answer *"which of my
records were taken on a model that no longer exists"* — and to answer it without pretending those
records are comparable to new ones.

`tokenizer_exact` is mandatory and must be true: `run_item` refuses to send a prompt when the
counter is not exact (`TokenAccountingRefusal`), and a record whose token counts came from a
character heuristic is not a measurement.

### 3.6 `dataset`

`dataset_version` · `generator_version` · `split` (`train`/`dev`/`val`/`test`/`promotion`) ·
`seal_state` (`UNSEALED` / `SEALED` / `SEAL_BROKEN`) · `seal_hash` · `sealed_at` ·
`declared_exposure_steps` · `measured_exposure_steps` · `contamination_report_artifact_id`.

**Both exposure fields are required.** V7's C10: the seal declared 8,766 exposed steps; the real
figure was **21,632**, a 60% under-declaration, and the contamination was design-level (the shipped
distractor tiers were the measured policies). A single `sealed: true` boolean is exactly the field
that hid it. Two fields that must be reconciled cannot.

### 3.7 `budget`

`model_calls` · `cached_calls` · `fresh_calls` · `cache_scopes_json`
(counts by `CacheScope`: `FRESH` / `SAME_CONDITION_REUSE` / `CROSS_CONDITION` — the last must always
be 0, since a non-zero value means the harness raised) ·
`prompt_tokens_total` · `completion_tokens_total` · `prompt_tokens_mean` · `prompt_tokens_p90` ·
`wall_clock_seconds` · `verifier_calls` · `verifier_cpu_seconds` ·
`gpu_seconds` (NULL outside L3/L5) · `budget_authorised` · `budget_exceeded` (BOOLEAN).

Budget parity across arms is asserted here and checked, not assumed — the failure mode "one arm got
more effective compute under an equal nominal budget" is §7.2 of the fitness spec.

### 3.8 `fitness_vector` — with intervals, in the existing `metrics` table, extended

One row per `(record_id, dimension)`. The existing `metrics` table already has `lower_bound` and
`upper_bound`; add the four columns that make a value interpretable:

| Field | Notes |
|---|---|
| `dimension` | `J_solve` / `J_horizon` / `J_learn` / `J_ood` / `J_search` / `J_repair` / `J_cost` |
| `value` | point estimate |
| `lower_bound`, `upper_bound` | existing columns |
| `confidence` | e.g. 0.95 |
| `estimator` | **new** — `wilson` / `clustered_bootstrap` / `mcnemar_exact` / `kaplan_meier` / `paired_z_did` / `median_iqr` |
| `n` | **new** — sample count at the estimator's own unit |
| `n_clusters` | **new** — number of clusters (problems / trajectories); `NULL` means unclustered and is a red flag on any trajectory-derived dimension |
| `unit_of_analysis` | **new** — `problem` / `trajectory` / `step` / `arm`. A `step` here on a comparative dimension is granularity substitution and should fail review. |
| `direction` | `maximize` / `minimize`, from `fitness.metrics.Direction` |
| `reportable` | BOOLEAN — false for a bucket that failed the §4.1 reportability rule |
| `unreportable_reason` | `INSUFFICIENT_N` / `VOID_FLOOR` / `VOID_CEILING` / `THRESHOLD_UNREPRESENTABLE` / `INSUFFICIENT_FAILURES` |

**`n_clusters` and `unit_of_analysis` are the two columns that make the programme's recurring failure
mode queryable.** A dimension whose `unit_of_analysis` is coarser than the claim drawn from it can
be found with one `SELECT`.

### 3.9 `uncertainty` (per record, comparative)

`comparison_json`, holding the full output of `game_r_formal_v1.compare_arms` — which is
`landscape.PairedComparison.to_dict()` plus recomputation and both Wilson intervals:

`n` · `accuracy_a` · `accuracy_b` · `delta` · `ci95` · `n10` · `n01` · `mcnemar_exact_p` ·
`clusters` · `wilson_a` · `wilson_b`

plus, added here: `holm_adjusted_p` · `holm_family_size` (the k the correction used) ·
`equivalence_json` (`precondition_power.equivalence_test` output, including its
`region_conditionally_unattainable` flag) · `power_at_declared_effect` ·
`declared_effect` · `representability_json` (`precondition_power.representability(n)`) ·
`confirmatory` (BOOLEAN — false at L0–L4, true only at L5/L6) ·
`preregistration_id` (NULL unless `confirmatory`).

**`confirmatory` plus `preregistration_id` is the mechanism that stops an exploratory number being
quoted as a result.** A record with `confirmatory = 1` and `preregistration_id IS NULL` is malformed
and should fail a store-level check.

### 3.10 `failure_modes`

Written to the existing `failures` table, one row per distinct class observed, with counts:

`failure_class` (`verified_eval.FailureClass` ∪ `game_r_formal_v1.RowStatus`) · `count` ·
`fraction_of_scored` · `severity` · `first_error_depth_median` (NULL outside trajectory levels) ·
`exemplar_artifact_id` · `regression_status`.

The vocabulary is already defined and load-bearing:
`UNPARSEABLE`, `MISSING_KEYS`, `UNDECODABLE`, `UNADJUDICATED`, `UNKNOWN_OPERATION`,
`BAD_ARGUMENTS`, `VERIFIER_REJECTED`, **`CONTENT_MISMATCH`** (*"where the hollow-action attack
lands"*), `VERIFIER_ERROR`, `VERIFIED_NOT_EXACT`, `EXACT`; and
`MODEL_SEMANTIC_ERROR`, `RESPONSE_SCHEMA_ERROR`, `OUTPUT_TRUNCATION`, `PROMPT_OVER_BUDGET`,
`SOLVER_ERROR`. Note that `SCORED_STATUSES` counts every solver-caused failure as *incorrect* rather
than dropping it — the record must preserve that distinction, because a language that fails by
producing unparseable output and one that fails by reasoning wrongly are different organisms.

Add two trajectory-specific classes: `NO_PROGRESS` (the trajectory looped without a verified step)
and `ABANDONED_UNDER_BUDGET` (the Solver stopped while budget remained).

### 3.11 `semantic_gate_results`

**Gate S** — the full `GateZeroEvidence` field set, not a boolean:
`critical_false_accepts` · `canonical_collisions` · `unresolved_scope_corruptions` ·
`proof_cycles` · `untracked_definedness_escapes` · `silent_semantic_losses` ·
`required_roundtrip_successes` · `required_roundtrip_total` · `gate_status`
(`PASS`/`NICHE`/`ELIMINATED`) · `reasons_json`.
Plus the coverage gate: the seven `CoverageMetrics` fields and its `GateResult`.

**Gate A** — the frozen adversary evaluation:
`adversary_family_version` (`arena-rendered-prompt-adversary-v1.0.0`) ·
`frozen_hash` (`FrozenAdversaries.content_hash`) ·
`dev_family_ids_hash` · `eval_family_ids_hash` · `dev_eval_disjoint` (BOOLEAN — `evaluate_frozen`
raises if not) · `n_adversaries` (5: `top_k=3` rules + 2 shallow models) · `n_eval` ·
`best_adversary` · `best_accuracy` · `best_holm_p` ·
`best_bonferroni_lower` / `best_bonferroni_upper` · `threshold` · `gate_verdict` ·
`false_void_probability_at_design` (from
`precondition_power.shortcut_gate_operating_characteristic`) ·
`twin_invariance_artifact_id`.

Recording `false_void_probability_at_design` alongside the verdict is what prevents the V7 C3e
repeat in either direction. At the V0 operating point (n_EVAL 800, threshold 0.60, 5 adversaries)
it is **0.0019**; at n_EVAL 400 with threshold 0.55 it would be **0.9937**, i.e. a gate that voids a
clean language almost every time. A verdict without that number is uninterpretable.

**Parity** — `game_r_formal_v1.ParityReport`: `envelope_signature` · `answer_protocol_hash` ·
`canonical_recovery_exact` · `distinct_rendered_bytes` · `e1_max_span_coverage` ·
`seqmatch_ratio` · `parity_verdict`.

### 3.12 `provenance`

`git_commit` · `git_branch` · `worktree_dirty` (BOOLEAN) · `harness_version` ·
`generator_version` · `environment_version` · `experiment_version` · `python_version` ·
`numpy_version` · `seeds_json` (every seed used: bootstrap, permutation, sampler) ·
`operator` (human or agent id) · `command_line` · `preregistration_artifact_id` ·
`input_artifact_hashes_json` · `code_file_hashes_json` (sha256 of every `arena/` module that
participated, from `arena/storage/hashes.file_sha256`, which already exists).

---

## 4. Where the records live

```
artifacts/
  arena.db                        # existing ArenaDatabase; new tables added by SCHEMA
  fitness_memory/
    <condition_id>/
      <record_id>.json            # full record, canonical JSON, ArtifactStore-written
      <record_id>.rows.jsonl      # per-trajectory rows (the paired outcome data)
      <record_id>.curves.json     # survival curves, first-error-depth histograms
      <record_id>.adversary.json  # FrozenEvaluation
```

- **The database is the index; the artifact store is the payload.** SQLite holds the identity, the
  metric scalars with intervals, and the pointers. Everything large is content-addressed on disk.
  This is already the split `arena/pipeline.py` uses.
- **Sharding by `condition_id`** means "all records comparable to this one" is a directory listing,
  and it makes an accidental cross-condition read visible in a path.
- **`<record_id>.rows.jsonl` is the important file.** It holds one row per trajectory with
  `(task_id, family_id, problem_id, arm, correct, first_error_depth, steps_verified, branches,
  repairs, tokens, seconds)`. Every statistic in `docs/LONG_HORIZON_FITNESS_V0.md` is recomputable
  from it. **A record whose rows file is absent is not a fitness record** — it is a summary, and a
  summary cannot be re-analysed at a different granularity, which is the precondition for catching
  granularity substitution at all.
- Retention: permanent. These files are small relative to what already exists in the repo
  (`steps.jsonl` is 271 MB).

### The one change required to `arena/storage/db.py`

`record_evaluation` currently keys on `{language_id, task_set_hash, tier, config}` and upserts.
The fitness-memory tables must instead:

1. key on the eleven-component identity of §2.2 (which includes the model and the mutation);
2. `INSERT` only, raising on a duplicate `record_id` whose `result_hash` differs;
3. return the existing row unchanged on a duplicate `record_id` whose `result_hash` matches
   (idempotent re-write, the `SAME_CONDITION_REUSE` analogue).

`record_evaluation` itself is left alone; the new tables are additive so nothing that currently
passes stops passing.

---

## 5. The queries the surrogate will need

The surrogate's label is **ΔJ_d(parent, mutation, condition)** for each dimension `d`. Every query
filters on `condition_id` first.

**Q1 — training rows.** All `COMPLETE` records at a given `ladder_level`, joined to
`fitness_vector` for one `dimension`, with `n_clusters IS NOT NULL` and `reportable = 1`, grouped by
`condition_id`. → `(features, ΔJ, weight = 1/variance, group = condition_id)`.

**Q2 — the same mutation across conditions.** All records sharing `mutation_hash` but differing in
`condition_id`. This is how the surrogate learns *transferability* — whether an operator's effect is
model-specific (`GOAL.md` §20's "representation advantage is strongly model-specific" outcome). It is
also the query that must **never** be used to pool a ΔJ.

**Q3 — operator effect and its consistency.** Group by `(operator, changed_genes)` within a
condition; return mean ΔJ, directional consistency, and n. This is exactly
`landscape.landscape_summary`'s `gene_effect_consistency`, promoted from a one-off report to a
standing query.

**Q4 — lineage.** Walk `language_parents` to reconstruct a candidate's full mutation path and the
ΔJ at each edge. Needed for epistasis: does operator μ₂ help only after μ₁.

**Q5 — screen validity.** For candidates with records at both L2 and L4 in the same generation,
Spearman ρ between the L2 ranking and the L4 ranking (`landscape.spearman`). This is the
three-generation retirement rule for the L2 screen, and it needs no new machinery.

**Q6 — horizon profile.** For one `(child_genome_hash, condition_id)`, all
`dimension = 'J_solve'` rows grouped by `horizon_bucket` with their intervals and `reportable`
flags. This *is* `J_horizon`; the schema stores the per-bucket rows and derives γ, rather than
storing a γ whose provenance cannot be re-checked.

**Q7 — the honesty queries.** Records where `pool_role = 'SELECTION'` and `pool_role =
'QUALIFICATION'` share a `task_set_hash` (V7 L1); records where `declared_exposure_steps <
measured_exposure_steps` (V7 C10); records where `unit_of_analysis = 'step'` on a comparative
dimension (granularity substitution); records where `confirmatory = 1` and `preregistration_id IS
NULL`; records where `cache_scopes_json` shows any `CROSS_CONDITION`. **Each of these returning a
non-empty result is a bug in the loop, not a finding about a language.** They should run as a
standing check after every generation.

---

## 6. Surrogate feature vector — what `extract_features` must grow into

Not built. Named so the schema above is sufficient for it.

`arena/surrogate/features.extract_features` flattens a genome-like mapping into
`{path: float}`, hashing categorical values with SHA-256 (never Python's randomised `hash`) — that
part is sound and reusable. What it lacks is everything outside the genome. The ΔJ surrogate needs
four blocks:

1. **Parent genome** — the existing flattening, plus the behavioural descriptors D1–D4 of the parent
   from `genome_descriptors`. The 98.6%-overlap measurement says gene values alone are a poor
   coordinate system.
2. **Mutation** — one-hot `operator` (24 values), one-hot `changed_genes`, `n_genes_changed`,
   `evaluation_tier`, `soundness_risk`, `layer`.
3. **Environment/context** — `environment_version`, `horizon_bucket`, `n_problems`, `pool_role`,
   `dependency_density` (T1/T2/T3), `horizon_length_confounded`.
4. **Condition** — `model_digest` (as a learned embedding or a categorical), `decoding_hash`,
   `context_length`, `tokenizer_id`.

**The target is ΔJ_d with its uncertainty, so training must be variance-weighted** — a ΔJ from n=40
and one from n=470 are not equal evidence. `SurrogateExample` already carries a `weight` and a
`group`; the weight becomes `1/Var(ΔJ)` from `fitness_vector`, and the group becomes `condition_id`
so cross-validation folds never straddle conditions.

**One thing this schema cannot fix.** The surrogate will be trained on records produced by the
search that the surrogate then steers. That is a closed loop, and it will be biased toward the
region the search has already explored. The mitigation is to record **every** evaluated mutation
including rejected and refused ones (§2.1), so the training set is not conditioned on success — but
it is a mitigation, not a solution, and the first surrogate's honest use is ranking within a
generation, never gating a candidate out of the ladder.

---

## 7. Explicitly out of scope for V0

- Any code. No table is created, no record is written.
- Training or calibrating a surrogate.
- Migrating the ~20 existing `artifacts/candidates/M-*` evaluations into this schema. They lack a
  model digest, a mutation link, and a cluster count; they are `GENOME_VALIDATED_RENDERER_PENDING`
  (`artifacts/reports/mutations-L1_CURRENT_HML.json`) and were never scored against a Solver.
  **Retrofitting them would fabricate identity components that were never recorded**, which is the
  exact failure this schema exists to prevent. They stay where they are.
- A distributed or multi-writer store. SQLite plus a content-addressed directory is sufficient for a
  single-machine loop and is what already exists.
