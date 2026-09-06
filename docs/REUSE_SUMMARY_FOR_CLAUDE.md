# Cross-Repository Reuse Summary for Claude

This is the human-readable companion to `artifacts/reuse/cross_repo_assets.json`,
`conflicts.json`, and `provenance.jsonl`. Historical repositories supplied experiment design,
tests, terminology, and failure memory. They did not replace Arena truth, and none of their old
model scores count as Arena observations.

## Authority boundary

| Source | Authority in this project |
|---|---|
| Arena World v0 | Frozen mathematical truth and task oracle for this experiment |
| `hamiltonian-lang` | Historical executable HML behavior only |
| `hml-standard` | HML terminology/conformance reference, not executable truth |
| `hml-reasoning-corpus` | Empirical method and corpus-design evidence |
| `HML_V3` | Later experimental search/calibration designs and failure memory |

## MoheetBrain/HML_V3

### `codex/open-ended-search-v2` at `4395a8c717a334be58b29d53b43c0c842d0e03ac`

What was there:

- `research/representation_search/HML_FAILURE_MEMORY.md`: accumulated failures and anti-Goodhart
  constraints.
- `src/hml_v3/representation_search/mutations.py`: one-axis mutation proposals tied to causal
  hypotheses.
- `src/hml_v3/representation_search/compiler.py`: genome-driven renderer compilation.
- `src/hml_v3/micromath/calibration.py`, `calibration_v2.py`, and `instruments_v2.py`: positive,
  relation-destroyed, parity, uncertainty, and ladder calibration ideas.
- `src/hml_v3/micromath/counterfactuals.py`: minimal pairs produced by transposing semantic
  roles while holding token multisets close.
- `reports/micromath_lab_v2/FINAL_REPORT_V2.md` and `KNOWN_BAD_V2.json`: a valid negative result
  and the warning that six of eight intended known-bads did not actually hide their target.

What Arena took:

- The one-edit neighborhood principle became the 120 controlled children in
  `arena/experiments/fitness_v1.py`.
- Explicit positive-versus-relation-destroyed calibration, paired counterfactual inversion,
  exact parity, and fail-closed validation became `arena/experiments/fitness_v2.py`.
- The instruction to validate the model-visible view itself—not merely source roundtrip—became
  neutral display IDs, empty oracle action pools, byte-identical destroyed twins, and tests in
  `tests/experiments/test_fitness_v2.py`.
- Failure memory informs `docs/MODEL_FITNESS_EXPERIMENT_V2.md` and the known-failure section of
  `docs/CLAUDE_HANDOFF.md`.

What Arena did not take and why:

- The 42-axis V3 genome/compiler was not copied because it is coupled to a different canonical
  projection and would silently change the frozen Arena search space.
- Old MicroMath scores were not pooled because model, task, prompt, and oracle differ.
- Counterfactual code was not copied. Arena reimplemented bounded domain oracles against its own
  canonical records because V3 explicitly warned that some generated siblings were canonical
  but not independently theorem-proved.

Classification: adapted experimental rules and historical warnings; no direct score/data import.

### Other inspected HML_V3 states

`codex/lean-runtime-semantic-capture-v2` at
`99475f4f64b1c47c91b588e8a5b08fed70ca117b` and `codex/evidence-first-foundation` at
`5d4d7a683cfb081733cc39baa53cfc3baad29d3d` contained richer Lean/runtime capture and earlier
evidence-first architecture. They were references only. Importing them would alter Arena World
v0 rather than repair the V2 measurement bottleneck. No Arena component consumes their data.

## MoheetBrain/hml-reasoning-corpus

### `claude/max-ev-representation-experiment-v1` at
`bf2cd75a0676afdb73ab15fe5963cb6138e27060`

What was there:

- `experiments/max_ev_representation_v1/arms/common.py`: a common model-facing IR and matched
  renderings.
- `dataset/v1/MANIFEST.json`: 5,619 rows with theorem grouping and structural OOD splits.
- `dataset/build.py` and `audit/counterfactual_splits.py`: group-aware split and leakage audits.
- `mutate/mutations.py`: 16 hard-negative mutation families.
- `harness/metrics.py`: task-paired comparisons, grouped bootstrap, exact discordances, and
  missingness discipline.
- `reports/PREREGISTERED_ANALYSES.md`: predeclared comparisons and falsifiers.
- `reports/INVALIDATED_INSTRUMENTATION_RUN.md`: a 50K run invalidated because literal Unicode
  escapes affected only one representation.
- `reports/STAGE1_RESULT.md`: HML placed third; the best-control difference was unresolved.

What Arena took:

- Domain/operation-grouped DEV, SCOUT, PROMOTION, and structural OOD splitting in
  `arena/experiments/fitness_v1.py`.
- Reimplemented paired bootstrap, `n10`/`n01`, and exact McNemar calculations in
  `arena/evaluation/landscape.py`, tested by `tests/evaluation/test_landscape.py`.
- Common-envelope, information-equality, explicit missing/malformed rows, and decoded Unicode
  audit principles in the fitness tests and documentation.
- The 15-point developmental margin/headroom convention informed the preregistered V2 gates;
  it was committed before candidate comparisons.

What Arena did not take and why:

- The 5,619 rows remain `ADAPT`/`IMPORT_AS_TEST`, not `REUSE_DIRECTLY`. Their three-class
  validity oracle and semantic-state schema are not Arena's next-action oracle/schema.
- No prior score or trained model was imported. Historical exposure also makes those rows
  unsuitable for hidden PROMOTION/OOD.
- Hard-negative source records were not admitted as Gold because no full schema-and-oracle
  adapter was needed for this V2 bottleneck.

Classification: method/code ideas were independently reimplemented; dataset deferred; old
results are historical warnings only.

### `codex/reasoning-layer-discovery` at
`8d7cc1d99dc6748fd4d6dac174d251671d403678`

This state separated representation-neutral reasoning records from surface syntax. Arena took
the conceptual separation among canonical truth, representation, solver, and verifier. That
separation exists throughout `arena/canonical`, `arena/languages`, `arena/players/solver.py`, and
`arena/verifier`. No source data or scores were imported.

### `codex/synthetic-math-hml` at `91fdda35851caa0445c1becdb1d7a756d5bcee3d`

This older synthetic corpus was inspected as provenance. It was not used because newer max-EV
records have stronger audit structure and neither schema is directly compatible with Arena.

## MoheetBrain/hml-standard

### `main` at `e879f5f5fe55ad2dc4ab15eb1c10a15de91aa59c`

What was there:

- `standard/rules.json`: HML 1.0 normative rules.
- `MODEL_REFERENCE.md`: model-facing syntax/conformance reference.
- `spec/27_versioning.md`: semantic-unfreeze/versioning governance.
- The README's explicit distinction between documentation authority and executable authority.

What Arena took:

- Terminology for the current-HML control and the governance rule that semantic changes require
  a new experiment version.
- The requirement that acquisition guidance be mechanically tied to the actual renderer, used
  by `GenomePhenotypeLanguage.acquisition_guide()`.

What Arena did not take and why:

- HML Standard is not Arena's mathematical oracle. Its rules neither certify Arena Gold nor
  privilege HML in candidate ranking.
- No conformance claim is made for the compatibility-only Arena HML seed.

Classification: terminology/conformance reference and governance rule only.

## MoheetBrain/hamiltonian-lang

### `codex/final-hml-signal` at `273a5145fb4128daf37493de396126aa8cc84d97`

What was there:

- `evaluation/syntax_gate/partition.py`: explicit gate-only and hidden track separation.
- `evaluation/syntax_gate/prompts.py`: matched prompt construction.
- `evaluation/syntax_gate/stats.py`: paired-only statistics retaining failed rows.
- `evaluation/acq0/protocols/calibration.py` and `prompts/sensitivity.py`: calibration and prompt
  sensitivity checks.
- `evaluation/results/acq0/v2_tranche_a/INVALID_INSTRUMENT.md`: a model-visible projection that
  omitted the decisive relation despite passing source-renderer roundtrip.
- `evaluation/arena/results/ACQUISITION_INSTRUMENT_FINAL.json`: six mechanically scored reading
  kinds and recorded prompt repairs.
- `experiments/common_envelope_10k/common_envelope.py` and
  `COMMON_ENVELOPE_REPORT.md`: neutral JSON beat HML by 2.77 points after equalizing non-state
  prompt bytes, reversing an earlier unequal-envelope claim.
- `tests/syntax_gate/test_information_equality.py` and historical tests: information parity and
  binder/scope/evidence/partiality exploit memory.

What Arena took:

- Split firewalls, common envelope, prompt equality, lossless parsing, and raw-completion audit.
- The rule that candidate guides are generated from candidate genomes rather than hand-tuned.
- Information-equality checks in `tests/experiments/test_fitness_v1.py` and answer-leakage checks
  in `tests/experiments/test_fitness_v2.py`.
- Historical position-bias and projection failures directly motivated semantic flip consistency,
  destroyed twins, and swapped-order diagnostics.

What Arena did not take and why:

- The historical +35.55-point HML claim is rejected as a prompt-envelope confound.
- The common-envelope -2.77-point result is credible in its own experiment but remains prior
  evidence only; it is not pooled with Arena.
- Old scorer outputs and raw model completions do not enter V2 cache or metrics.

Classification: adapted tests and experimental rules; historical warnings/results only.

### `feature/hml-reasoning-kernel-v2` at
`3b7fe893609c2ce39c8088c1cb0c3fe2e45d6af4`

What was there: `src/hamiltonian_lang/semantic_state` provided executable claims, goals, actions,
evidence, obligations, and transition verification.

What Arena took: architecture lessons for explicit obligations/evidence and verifier boundaries,
already represented in `arena/canonical/schema.py` and `arena/verifier/native.py`.

What Arena did not take: the richer semantic-state classes themselves. A direct import would
change frozen Arena truth and require a separately versioned, proved adapter.

Classification: executable semantic reference, not Arena code or data.

## Exhaustive asset traceability table

This table normalizes every asset in `cross_repo_assets.json`. "Inspected" means read during
the audit; "adapted" means the principle was reimplemented and reverified in Arena. It also
resolves the HML Standard provenance question: `README.md` supplied the authority distinction,
while the three paths below were separately inspected for rules, model guidance, and versioning.

| Repository / branch / full SHA | Source path | Arena destination | Classification | Verification/use |
|---|---|---|---|---|
| HML_V3 / `codex/open-ended-search-v2` / `4395a8c717a334be58b29d53b43c0c842d0e03ac` | `research/representation_search/HML_FAILURE_MEMORY.md` | `docs/CROSS_REPO_ASSET_AUDIT.md`; handoff failure table | ADAPT / historical warning | Compared with Arena guards; no scores copied |
| same | `src/hml_v3/representation_search/mutations.py` | `arena/experiments/fitness_v1.py` | ADAPT / experimental rule | 120 one-gene identities and Gate 0 tests |
| same | `src/hml_v3/representation_search/compiler.py` | none; deferred reference | REFERENCE_ONLY / code | Coupling reviewed; no import |
| same | `src/hml_v3/micromath/calibration.py` | `arena/experiments/fitness_v2.py` | ADAPT / experimental rule | Q1/Q2 tests and raw audits |
| same | `reports/micromath_lab_v2/FINAL_REPORT_V2.md` | audit and handoff failure memory | REFERENCE_ONLY / historical result | Used only as negative prior |
| hml-reasoning-corpus / `claude/max-ev-representation-experiment-v1` / `bf2cd75a0676afdb73ab15fe5963cb6138e27060` | `experiments/max_ev_representation_v1/arms/common.py` | `arena/languages/phenotype.py`; projection/tests | ADAPT / code pattern | Arena roundtrip/information tests |
| same | `experiments/max_ev_representation_v1/dataset/v1/MANIFEST.json` | none; future DEV adapter only | ADAPT-DEFERRED / data | 5,619 rows inspected; zero imported |
| same | `experiments/max_ev_representation_v1/mutate/mutations.py` | none yet; candidate Refuter expansion | IMPORT_AS_TEST-DEFERRED / test data | Requires case-by-case oracle adapter |
| same | `experiments/max_ev_representation_v1/dataset/build.py` | `arena/experiments/fitness_v1.py`; `fitness_v2.py` | ADAPT / experimental rule | Disjoint group/slice tests |
| same | `experiments/max_ev_representation_v1/harness/metrics.py` | `arena/evaluation/landscape.py` | ADAPT / code pattern | Exact McNemar/bootstrap unit tests |
| same | `experiments/max_ev_representation_v1/reports/PREREGISTERED_ANALYSES.md` | V1/V2 experiment docs and freeze rules | ADAPT / terminology/rule | Pre-candidate commit audit |
| same | `experiments/max_ev_representation_v1/reports/STAGE1_RESULT.md` | cross-repo audit and handoff | REFERENCE_ONLY / historical result | Never pooled with Arena |
| same | `experiments/max_ev_representation_v1/reports/INVALIDATED_INSTRUMENTATION_RUN.md` | `tests/assurance/test_side_channels.py`; handoff | IMPORT_AS_TEST / warning | Decoded-prompt asymmetry regressions |
| hml-standard / `main` / `e879f5f5fe55ad2dc4ab15eb1c10a15de91aa59c` | `standard/rules.json` | terminology/conformance reference only | REFERENCE_ONLY / specification | Inspected; Arena truth unchanged |
| same | `MODEL_REFERENCE.md` | `GenomePhenotypeLanguage.acquisition_guide()` design | ADAPT / terminology | Guide mechanically bound to genome |
| same | `spec/27_versioning.md` | V1/V2 version/freeze governance | ADAPT / experimental rule | New V2 namespace; V1 untouched |
| hamiltonian-lang / `feature/hml-reasoning-kernel-v2` / `3b7fe893609c2ce39c8088c1cb0c3fe2e45d6af4` | `src/hamiltonian_lang/semantic_state` | `arena/canonical`; `arena/verifier` architecture reference | REFERENCE_ONLY / code | Schema mismatch documented; no import |
| hamiltonian-lang / `codex/final-hml-signal` / `273a5145fb4128daf37493de396126aa8cc84d97` | `evaluation/syntax_gate/partition.py` | V1/V2 split manifests | ADAPT / code pattern | Source/slice disjointness tests |
| same | `evaluation/syntax_gate/prompts.py` | V1/V2 prompt builders | ADAPT / code pattern | Common-envelope and leak tests |
| same | `evaluation/syntax_gate/stats.py` | `arena/evaluation/landscape.py` | ADAPT / code pattern | Malformed rows retained; paired tests |
| same | `experiments/common_envelope_10k/common_envelope.py` | V1/V2 common-envelope rule | ADAPT / experimental rule | Candidate-neutral prompt construction |
| same | `experiments/common_envelope_10k/COMMON_ENVELOPE_REPORT.md` | audit/handoff | REFERENCE_ONLY / historical result | Unequal-envelope claim rejected; no pooling |
| same | `tests/syntax_gate/test_information_equality.py` | `tests/experiments/test_fitness_v1.py`; `test_fitness_v2.py` | IMPORT_AS_TEST / test pattern | Canonical identity/action leak regressions |
| same | `tests` | `tests/assurance`; `arena/players/refuter.py` | IMPORT_AS_TEST / historical exploit class | Independently reproduced applicable cases only |

Additional inspected repository states without catalogued imports were HML_V3
`codex/lean-runtime-semantic-capture-v2` at
`99475f4f64b1c47c91b588e8a5b08fed70ca117b`, HML_V3 `codex/evidence-first-foundation` at
`5d4d7a683cfb081733cc39baa53cfc3baad29d3d`, hml-reasoning-corpus
`codex/reasoning-layer-discovery` at
`8d7cc1d99dc6748fd4d6dac174d251671d403678`, and `codex/synthetic-math-hml` at
`91fdda35851caa0445c1becdb1d7a756d5bcee3d`. All are REFERENCE_ONLY; their destination is this
summary/architecture rationale, and their verification was read-only history inspection.

## V2-specific reuse outcome

The targeted V2 pass saved design time but did not bypass verification. The most valuable reused
ideas were semantic transposition, information-destroyed controls, model-visible-view hashing,
exact position parity, and uncertainty-aware staged gates. Arena's implementation and all 48
pair truths were freshly generated and reverified. The relevant Arena destinations are:

- `arena/experiments/fitness_v2.py`
- `tests/experiments/test_fitness_v2.py`
- `docs/MODEL_FITNESS_EXPERIMENT_V2.md`
- `artifacts/experiments/fitness_v2/probe_manifest.json`
- `artifacts/experiments/fitness_v2/model_qualification.json`
- `artifacts/experiments/fitness_v2/protocol_selection.json`

Nothing from a historical repository is hidden evaluation material. Any future dataset import
must add a versioned adapter, record provenance, prove oracle equivalence, and remain DEV until
fresh status is justified.
