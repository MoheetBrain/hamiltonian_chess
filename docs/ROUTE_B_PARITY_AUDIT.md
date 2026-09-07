# Route B Parity Audit — measured defects in the matched-training path

**Method.** Static audit of the existing training path plus read-only rendering of the 676-world
through all eight language surfaces. **No model call, no GPU minute, no training run.** Rendering
is a pure function (verified: no `random`/`time`/`uuid`/`datetime`/`os.environ` anywhere in
`arena/languages`, `arena/model_view`, `arena/compiler`, `arena/canonical`, `arena/genome`).

**Why this document exists.** Route B claims to change *only* the representation `R`. That claim
is only as good as the machinery enforcing it. This audit enumerates every axis along which two
arms could differ, and marks each GUARANTEED (with the code that guarantees it) or MUST BUILD.
Six defects below would silently bias a Route B result, and **none of them is detectable from any
recorded artifact** — which is why they are written down before the experiment, not after.

---

## 1. The blocking finding: the five historical arms ignore the genome

`CandidateLanguage` (`arena/languages/base.py:18-61`) is a bidirectional codec. The eight seed
surfaces are **hand-written codecs that merely *attach* a genome as an attribute**:

| Arm | File | Bytes actually decided by |
|---|---|---|
| L0_STRUCTURED_ENGLISH | `structured_english/__init__.py:33-55` | literal `_HEADER` `:13`, `_LABELS` map `:14-30` |
| L1_CURRENT_HML | `hml/__init__.py:20-45` | literal `_HEADER` `:17`, `key := json;` lines `:26` |
| L2_SEXPR | `sexpr/__init__.py:15-31` | `_PREFIX` `:12` + `sexpr_encode` |
| L3_JSON_AST | `json_ast/__init__.py:13-33` | `canonical_json` envelope `:17-20` |
| L5_COMPACT_SYMBOLIC | `symbolic/__init__.py:24-41` | `ΣHC0\|` header `:13`, `_ALIASES` `:14-20` |

`StructuredEnglishLanguage._encode_payload` (`:37-40`) **never reads `self.genome`**. For these
five arms, changing a gene changes nothing.

The genome-driven surface is a **different class**: `GenomePhenotypeLanguage`
(`arena/languages/phenotype.py:272-329`, `format_id = "arena-genome-phenotype-v1"`). The 120
one-gene mutants render through it; the eight seed arms do not.

**Consequence.** Running Route B over the five hand-written seed arms measures *codec
implementations*, not genes. Running it over phenotype-rendered genomes measures genes. **Mixing
the two in one experiment confounds "representation" with "codec implementation."** Route B must
declare which of the two questions it is asking, and use one family throughout.

Related: **five of the fourteen gene families are inert** — `alphabet`, `composition`,
`obligations`, `evidence`, `error_locality` affect no rendered byte (absent from `phenotype.py`;
corroborated by `PHENOTYPE_GENES`, `arena/experiments/game_r_mutant_audit.py:187-197`). Nine
genes are active.

---

## 2. Six defects that would silently bias a Route B result

### D1 — Truncation is silent and side-inconsistent (highest risk)

- **Training** truncates **LEFT**: `ids = (prompt_ids + target_ids)[-args.max_len:]`
  (`gpu_matched_runner.py:165`) — drops the *start* of the prompt.
- **Evaluation** truncates **RIGHT** (tokenizer default; only `padding_side` is set at `:138`):
  `tokenizer(prompts, truncation=True, max_length=args.max_len)` (`:230-237`) — drops the *end*,
  including the generation prompt and `"NEXT ACTION (JSON):"`.

Two different mutilations of the same item, and **the amount lost is monotone in representation
length**. Nothing logs or counts a truncation event. A longer representation is therefore
penalised twice, invisibly.

**Required fix:** assert `max encoded length < max_len` per arm and abort otherwise; set
`truncation_side` explicitly; count and report every truncation event.

### D2 — The label mask makes supervision depend on representation length

`prompt_len = min(len(prompt_ids), max(0, len(ids) - 1))` (`:166`), used at
`labels[row, prompt_len:len(ids)]` (`:204`).

Under truncation the target actually begins at `max_len - len(target_ids)`, but `len(prompt_ids)`
is strictly larger. Fewer target tokens are supervised — collapsing to a *single* token once
`len(prompt_ids) ≥ max_len - 1`. **The number of supervised tokens is a function of
representation length.** This is a correctness bug, not a design choice.

### D3 — Input/output surface affinity favours one arm by construction

`target_text` is always canonical JSON (`render_dataset.py:54-55`), never rendered through the
arm's own surface. **`L3_JSON_AST` alone therefore has input-grammar = output-grammar.** It won
the historical sprint (dev exact 0.979 @224, 1.000 @576).

This is a live alternative explanation for the headline historical result. Route B must either
render targets in each arm's own surface, or preregister the confound explicitly and stop
treating JSON's win as evidence about representation.

### D4 — The control is chosen after seeing the scores

`analyse_sprint.py:63` selects `best_control` by *observed* score, then compares the candidate
against it. This inflates every reported delta. The control must be named in advance.

### D5 — The deadline guard silently produces unequal training

`gpu_matched_runner.py:192-194` truncates training mid-arm; `:287-290` skips arms entirely.
Historically **L1 and L2 never received Stage B**. A short arm must refuse to persist, or the
deadline must be removed.

### D6 — Held-out *verified* accuracy does not exist

`score_prediction` (`:71-82`) defines `verified` as the presence of three JSON keys — documented
in-band at `:77-78` as "NOT a claim that the action is optimal". It read **1.0000 for every arm at
every stage**. It is a degenerate endpoint.

`NativeVerifier` is instantiated in eight places across the codebase — **always on generated or
probe states, never on a model prediction.** Note its limits: it is structural/type-level
(duplicate ids, unbound variables, arity, sort mixing, matrix shape, illegal transition action,
goal/obligation laundering), **never mathematical truth**. Truth is checked only by the
differential layer (SymPy/Z3 plus a seeded 32-sample numeric falsifier that explicitly disclaims
proof, `arena/verifier/numeric.py:60-88`).

---

## 3. Parity checklist

GUARANTEED = enforced by the cited code today. MUST BUILD = not enforced.

| # | Axis | Status |
|---|---|---|
| 1 | Canonical content per item | GUARANTEED — `render_dataset.py:79-84`, `:117-122` |
| 2 | Observation projection / answer non-leakage | GUARANTEED — `render_dataset.py:50-52` + `compiler/projection.py:34-35`. But `assert_no_answer_leakage` (`projection.py:47-54`) **exists and is never called** — cheap to wire |
| 3 | Surface losslessness (each arm shows all the content) | **MUST BUILD** — `render_dataset.py` never re-parses a surface. Reuse `compiler/validator.py:20-40` and `game_r_mutant_audit.py:93-107` |
| 4 | Task selection / split | GUARANTEED — `prepare_matched_data.py:42-73`, disjointness asserted `:70-72` |
| 5 | Target action bytes | GUARANTEED — `render_dataset.py:54-55`, `:123-128` |
| 5b | Input/output surface affinity | **MUST DECIDE — see D3** |
| 6 | Prompt scaffolding / instruction text | GUARANTEED — single `SYSTEM` `:41-44`, single `build_prompt` `:47-52`. Do **not** import `acquisition_guide` (`phenotype.py:319-329`); it is genome-dependent by design |
| 7 | Tokenizer | GUARANTEED — one `AutoTokenizer` for all arms `:135-138` |
| 8 | Base checkpoint | GUARANTEED — snapshot `:144`, reloaded per arm `:172` |
| 9 | LoRA init | GUARANTEED — `torch.manual_seed` `:170` precedes `get_peft_model` `:181` |
| 10 | Optimiser state | GUARANTEED — fresh `AdamW` per arm `:183-185` |
| 11 | Seed | **PARTIAL** — no `torch.use_deterministic_algorithms`, no `CUBLAS_WORKSPACE_CONFIG`; only one seed was ever run |
| 12 | Example order | GUARANTEED — same index list per arm; sequential, no shuffle `:191` |
| 13 | Update count | **MUST BUILD — see D5** |
| 14 | Nominal sequence length | GUARANTEED — `max_len` 1536 for all arms `:94` |
| 15 | Truncation | **MUST BUILD — see D1** |
| 16 | Label-mask boundary | **BUG — see D2** |
| 17 | Padding | GUARANTEED (benign asymmetry) — train right-pads with `-100` `:198-204`; eval left-pads with a correct new-token slice `:244` |
| 18 | Evaluation slice | GUARANTEED — same dev/fresh indices for all arms |
| 19 | Decoding | GUARANTEED — `do_sample=False, max_new_tokens=192` `:239-241` |
| 20 | Primary endpoint (verified accuracy) | **MUST BUILD — see D6** |
| 21 | Dataset + config provenance | **MUST BUILD** — `write_jsonl`'s dataset hash (`render_dataset.py:131-137`) is never called; `matched_adaptation.py` is dead code with no production caller |
| 22 | Control selection | **MUST BUILD — see D4** |
| 23 | Paired statistics | AVAILABLE — `training/evaluation.py:18-46`, `evaluation/landscape.py:40-89` |
| 24 | Budget mode (example- vs token-matched) | DECLARED, UNENFORCED — `BudgetMode` unused; runner hardcodes the string `:265` |
| 25 | GPU / library provenance | GUARANTEED — `:114-128` |
| 26 | Codec family | **MUST DECIDE — see §1** |
| 27 | Ceiling / headroom | **FATAL if unfixed** — two arms reached `exact = 1.000` at 576 examples |

---

## 4. What `assert_matched_semantics` does and does not guarantee

`arena/training/render_dataset.py:87-128`. **Guarantees** (fail-closed, directly tested at
`tests/training/test_evaluation.py:62-67`): ≥ 2 arms; no empty arm; equal lengths; no two arms
share an `input_hash` sequence; identical `canonical_id` sequence; identical `target_hash`
sequence.

**Does not guarantee** anything about tokenisation, prompt scaffolding, context budget,
truncation, or **information content**. It never re-parses a rendered surface. *An arm that
silently dropped half the canonical state would pass every check*, because only *inequality* of
`input_hash` is tested.

The stronger control already exists elsewhere and should be reused for Route B:
`assert_information_parity` (`arena/experiments/fitness_v4.py:1165-1183`) compiles each genome,
recovers the `mathematical_hash`, builds the **full prompt**, and refuses byte-identical prompts.
The only check that reads *what is actually on the page* is `prompt_information_inventory`
(`arena/experiments/game_r_mutant_audit.py:93-107`), which decodes the rendered surface through
the **unbound base codec**, so a renderer cannot hide emitted content behind a filtering parser.

**Documentation drift to fix:** `prepare_matched_data.py:100-101` still claims the guard "is
vacuously true on an empty mapping". That hole was closed; the comment is stale.

---

## 5. Measured truncation headroom

676-world, `seed=0`, `input_text` characters after `NEXT_ACTION` projection:

| Arm | mean | p90 | p99 | max |
|---|---|---|---|---|
| L5_COMPACT_SYMBOLIC | 828 | 1024 | 1416 | 1416 |
| L0_STRUCTURED_ENGLISH | 1051 | 1247 | 1639 | 1639 |
| L3_JSON_AST | 1070 | 1266 | 1658 | 1658 |
| L1_CURRENT_HML | 1098 | 1294 | 1686 | 1686 |
| L4_TYPED_PREFIX | 1147 | 1385 | 1782 | 1782 |
| L7_HYBRID_ROLE_LABELLED | 1287 | 1549 | 1963 | 1963 |
| L2_SEXPR | 1297 | 1559 | 1973 | 1973 |
| **L6_GRAPH_TRIPLES** | **2822** | **3539** | **4125** | **4125** |

Target text: mean 368, max 709 characters. Recorded train tokens/example: L2 583, L5 420 (1.39×).

**Reading.** At `max_len` 1536 the five historical arms have headroom, so the historical sprint was
probably not truncated. But `L6_GRAPH_TRIPLES` is ≈ 3.4× `L5`, and Route B *requires* a harder,
non-saturating family — which moves every arm up. D1 and D2 together are the axis most likely to
silently invalidate Route B.

---

## 6. Candidate population — real counts

| Reported | Real | Evidence |
|---|---|---|
| 8 seeds | **8 — confirmed** | `artifacts/candidates/seeds.json` (`"count":8`) |
| 120 one-gene mutants | **120 — confirmed**, but stored in `artifacts/experiments/fitness_v1/candidate_population.json`, *not* `artifacts/candidates/` | ids `RF1-*`, all `mutation_distance == 1`, `population_hash 815efcc2…`; 15 children × 8 parents; genes: grammar/binders/types/state/actions/serialization/morphology 16 each, redundancy 8 |
| — | **⚠ 20 extra `M-*` directories** from an older wave, all parented on `L1_CURRENT_HML`, status `GENOME_VALIDATED_RENDERER_PENDING`, genome-only, no evaluation | On-disk `genome.json` count is **28, not 128** — do not count directories |
| FITNESS / LEARNABILITY / ROBUST / RSTAR: none | **Confirmed none** | These tokens appear **nowhere in `arena/`** — they exist only in prose. Nothing computes these tiers |

**Promotion gates: 2 of 5 tiers are machine-checked.** Gate 0 / coverage
(`arena/fitness/gates.py:63-143`) and Game-R admissibility (`assert_game_r_genome`,
`fitness_v4.py:1136-1140`, plus the 5-check audit `game_r_mutant_audit.py:171-186`) are code.
RSTAR is code (`arena/release.py:57-146`). **FITNESS_CANDIDATE, LEARNABILITY_CANDIDATE and
ROBUST_CANDIDATE are prose only** — a real gap if any future session assumes a gate exists.
