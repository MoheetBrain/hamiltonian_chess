# HC-V0.6 — local model inventory and baseline `R_A` preflight

**Status: MEASUREMENT.** Every number below was produced by a command recorded here. Nothing is
carried over from a previous document and nothing is estimated. Where a fact was not measured it
says **not measured**.

**Scope limit.** This is **model-eligibility calibration**. Exactly one arm (`R_A`) was played, so
this document contains no comparison between representations, and none can be derived from its
artefacts. No primary model is recommended here; the lead applies the frozen selection rule.

Raw JSON: `research/phase10/models/out/inventory.json`,
`research/phase10/models/out/smoke.json`, `research/phase10/models/out/preflight_summary.json`,
and one full manifest + cell table per model at
`artifacts/trajectory/hc_v0_6_preflight_<model>.json`.

Collectors: `research/phase10/models/inventory.py`, `research/phase10/models/smoke.py`,
`research/phase10/models/preflight.py`. All three read the repository's own modules; none of them
re-implements the runner, the solver or the endpoint.

---

## 1. The runtime

| field | value |
|---|---|
| runtime | ollama |
| runtime version | `0.33.2` (`/api/version`) |
| endpoint | `http://localhost:11434` |
| installed models | 5 |
| Lean toolchain | `Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)`, `leanprover/lean4:v4.10.0-rc1`, `check_toolchain().available == True` |
| mathlib checkout | `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4` |

There is exactly one model runtime in use by this repository (Ollama over HTTP). No second runtime
was found and none was installed.

---

## 2. Inventory

Facts from `/api/tags` and `/api/show`. **Nothing here is inferred from a tag name.**

| model | digest (12) | param size | parameter count | quant | family | architecture | ctx capability | on disk | runtime | lineage |
|---|---|---|---|---|---|---|---|---|---|---|
| `gemma3:4b` | `a2af6cc3eb7f` | 4.3B | 4,299,915,632 | Q4_K_M | `gemma3` | `gemma3` | 131,072 | 3,338,801,804 B (3.11 GiB) | ollama 0.33.2 | **UNKNOWN** |
| `gemma4:e4b` | `c6eb396dbd59` | 8.0B | 7,996,157,674 | Q4_K_M | `gemma4` | `gemma4` | 131,072 | 9,608,350,718 B (8.95 GiB) | ollama 0.33.2 | **UNKNOWN** |
| `gemma4:12b` | `4eb23ef187e2` | 11.9B | 11,907,350,576 | Q4_K_M | `gemma4` | `gemma4` | 262,144 | 7,556,508,396 B (7.04 GiB) | ollama 0.33.2 | **UNKNOWN** |
| `gemma4:31b` | `6316f0629137` | 31.3B | 31,273,089,132 | Q4_K_M | `gemma4` | `gemma4` | 262,144 | 19,868,981,791 B (18.5 GiB) | ollama 0.33.2 | **UNKNOWN** |
| `qwen3.6:27b-mlx` | `d49fd9e0da45` | 27.8B | 27,781,081,984 | nvfp4 | `qwen3_5` | `qwen3_5` | 262,144 | 18,785,066,095 B (17.5 GiB) | ollama 0.33.2 | **UNKNOWN** |

`ctx capability` is the model's own `<architecture>.context_length`. The assay does **not** use it:
`FROZEN_DECODING["num_ctx"] = 32768` is pinned identically for every model
(`ollama ps` confirmed `CONTEXT 32768` on the loaded models during the run).

`gemma4:12b` reports 7.04 GiB on disk against 11.9B parameters while `gemma4:e4b` reports 8.95 GiB
against 8.0B. That inversion is what the runtime reports; it was not investigated.

### 2b. Structure and framing (same source)

| model | format | blocks | d_model | heads (q/kv) | tokenizer `model`/`pre` | vocab size | RENDERER | PARSER | legacy `template` | capabilities |
|---|---|---|---|---|---|---|---|---|---|---|
| `gemma3:4b` | gguf | 34 | 2560 | 8 / 4 | `llama`/`default` | not reported | *(none)* | *(none)* | full Go chat template | completion, vision |
| `gemma4:e4b` | gguf | 42 | 2560 | 8 / 2 | `llama`/`gemma4` | not reported | `gemma4` | `gemma4` | `{{ .Prompt }}` | audio, completion, thinking, tools, vision |
| `gemma4:12b` | gguf | 48 | 3840 | 16 / *(null)* | `gemma4`/*(empty)* | not reported | `gemma4` | `gemma4` | `{{ .Prompt }}` | audio, completion, thinking, tools, vision |
| `gemma4:31b` | gguf | 60 | 5376 | 32 / *(null)* | `llama`/`gemma4` | not reported | `gemma4` | `gemma4` | `{{ .Prompt }}` | completion, thinking, tools, vision |
| `qwen3.6:27b-mlx` | safetensors | 64 | 5120 | not reported | not reported | not reported | `qwen3.5` | `qwen3.5` | `{{ .Prompt }}` | completion, thinking, tools, vision |

**Vocabulary size is not reported by this runtime for any installed model** —
`tokenizer.ggml.tokens` is null on all five — so it is recorded as not-reported rather than as 0,
and it is *not* used as classification evidence.

Two framing facts that matter for the preflight and are recorded rather than smoothed over:

* `gemma3:4b` is the only model with **no `RENDERER`/`PARSER` directive**. Its prompt is framed by
  Ollama's legacy Go chat template; the other four go through a native renderer. This is a real
  difference in how the identical prompt string reaches the weights.
* `gemma3:4b` is also the only model that does **not** declare the `thinking` capability, yet it
  accepted `think=False` without error (§4).

---

## 3. Pairwise family classification

Decided from `general.architecture`, `details.family`, `<arch>.context_length`, the tokenizer
metadata and the digest. **The tag name is not evidence and was not used.** Every relation is an
*architecture-family* statement; **training lineage is `UNKNOWN` for all ten pairs** because no
runtime field records training data, base checkpoint or fine-tuning history for both members of any
pair.

| A | B | relation | evidence |
|---|---|---|---|
| `gemma3:4b` | `gemma4:e4b` | **DISTINCT_MODEL_FAMILY** | architecture `gemma3` vs `gemma4`; family `gemma3` vs `gemma4` |
| `gemma3:4b` | `gemma4:12b` | **DISTINCT_MODEL_FAMILY** | architecture `gemma3` vs `gemma4`; family `gemma3` vs `gemma4` |
| `gemma3:4b` | `gemma4:31b` | **DISTINCT_MODEL_FAMILY** | architecture `gemma3` vs `gemma4`; family `gemma3` vs `gemma4` |
| `gemma3:4b` | `qwen3.6:27b-mlx` | **DISTINCT_MODEL_FAMILY** | architecture `gemma3` vs `qwen3_5`; family differs; format gguf vs safetensors |
| `gemma4:12b` | `gemma4:31b` | **SAME_FAMILY_VARIANT** | identical architecture `gemma4` and family `gemma4`; identical ctx 262,144; differ in parameter count (11.9B vs 31.3B) and in tokenizer metadata encoding |
| `gemma4:12b` | `gemma4:e4b` | **SAME_FAMILY_VARIANT** | identical architecture and family; differ in parameter count (11.9B vs 8.0B), ctx (262,144 vs 131,072) and tokenizer metadata encoding |
| `gemma4:31b` | `gemma4:e4b` | **SAME_FAMILY_VARIANT** | identical architecture, family and tokenizer metadata (`llama`/`gemma4`); differ in parameter count (31.3B vs 8.0B) and ctx (262,144 vs 131,072) |
| `gemma4:12b` | `qwen3.6:27b-mlx` | **DISTINCT_MODEL_FAMILY** | architecture `gemma4` vs `qwen3_5` |
| `gemma4:31b` | `qwen3.6:27b-mlx` | **DISTINCT_MODEL_FAMILY** | architecture `gemma4` vs `qwen3_5` |
| `gemma4:e4b` | `qwen3.6:27b-mlx` | **DISTINCT_MODEL_FAMILY** | architecture `gemma4` vs `qwen3_5` |

### What that means in plain terms

* **Three genuinely different architecture families are installed:** `gemma3`, `gemma4`, `qwen3_5`.
  The evidence is the architecture string and the `details.family` field reported by `/api/show`,
  not the tag.
* **`gemma4:e4b`, `gemma4:12b` and `gemma4:31b` are size variants of one architecture family.** All
  three report architecture `gemma4`, family `gemma4`, the same quantization `Q4_K_M`, the same
  attention geometry keys (`key_length` 512 / `key_length_swa` 256, `value_length` 512,
  `final_logit_softcapping` 30, `rope.freq_base` 1e6) and the same renderer/parser `gemma4`. They
  differ in size; `e4b` additionally differs in declared context length (131,072 vs 262,144) and in
  sliding window (512 vs 1024 on `12b`/`31b`).
* **`gemma3:4b` is not a size variant of the `gemma4` models.** Different architecture string,
  different context length, different attention geometry (`key_length` 256; `key_length_swa`,
  `final_logit_softcapping` and `rope.freq_base` all absent), different tokenizer `pre`
  (`default` vs `gemma4`), and no renderer/parser directive at all.
* **Quantization is not a distinguishing axis within `gemma4`:** all three are `Q4_K_M`. The only
  quantization difference in the whole inventory is `qwen3.6:27b-mlx` at `nvfp4`, which is
  confounded with its being a different architecture and a safetensors rather than gguf blob.
* **Only one model exposes any training-provenance field at all:** `gemma4:12b` declares
  `general.base_model.0 = "Gemma 4 12B" (Google, huggingface.co/google/gemma-4-12B)` and
  `general.license = apache-2.0`. That is a *distribution* claim in the blob's own metadata; it is
  recorded verbatim and is **not** treated as established training lineage, and no other model
  carries it. Lineage stays `UNKNOWN` everywhere.

---

## 4. Wiring check (before the preflight, not after)

HC-V0.5 found a silent failure: with `think` unset, the Solver's `response` came back empty and
every proposal became a `PARSE_FAILURE`, so the model looked incapable when it was misconfigured.
`WIRE_FLAGS` sets `think=False` for all models, but a model that rejects that flag, or whose chat
renderer differs, could fail the same way. So every model was smoked first, on the five hand-written
goals in `arena.trajectory.solver.SMOKE_GOALS` (not drawn from the bank).

Command: `.venv/bin/python research/phase10/models/smoke.py`

| model | OK | statuses | `thinking` chars | wall clock |
|---|---|---|---|---|
| `gemma3:4b` | 5/5 | all `OK` | 0 on every call | 2.5 s |
| `gemma4:12b` | 5/5 | all `OK` | 0 on every call | 3.5 s |
| `gemma4:31b` | 5/5 | all `OK` | 0 on every call | 9.0 s |
| `gemma4:e4b` | 5/5 | all `OK` | 0 on every call | 4.4 s |
| `qwen3.6:27b-mlx` | 5/5 | all `OK` | 0 on every call | 10.6 s |

**No model is mis-wired at the transport level.** Every model accepted `think=False`, `raw=False`,
`stream=False` and the JSON grammar, and returned a non-empty parseable `{"tactic": ...}`.
`gemma3:4b` accepted `think=False` even though it does not declare the `thinking` capability.

---

## 5. Baseline `R_A`-only preflight

Command: `.venv/bin/python research/phase10/models/preflight.py`

Held identical for every model, by construction rather than by intent — all of it comes from
`arena.trajectory.solver` module constants, none of it from the preflight script:

| knob | value |
|---|---|
| arm | `Arm.R_A` **only** |
| replicates | 1 |
| seed | 20260909 |
| `theorem_limit` / `theorem_sample_seed` | 15 / 20260909 |
| prompt template | `hc-v0.5-tactic-json-v1` |
| output grammar | `json-object-tactic-v1` |
| decoding | `temperature=0, seed=20260908, top_k=20, top_p=0.95, min_p=0, repeat_penalty=1.0, presence_penalty=0.0, num_predict=128, num_ctx=32768` |
| wire flags | `raw=False, think=False, stream=False` |
| evaluation universe | anchor bank `f13ffee5aae464d6f4717c4f85cd6ec1091eb19d9ca0ab5cd716094a9b583b40` — 1,127 anchors · 393 theorems · 330 files |
| realised sample | **45 anchors · 15 theorems · 15 clusters**, `anchor_universe_hash = bb0a862ca37cd25b…` |
| primary endpoint | `KERNEL_ACCEPTED_STATE_CHANGE` (`CellOutcome.accepted`) |

**Every model was played on the identical 45 anchors.** Verified, not assumed: all five cell tables
carry the same `anchor_universe_hash` and the same anchor-id set. 0 anchors were skipped and 0
theorem errors occurred, for every model. Served digests matched the inventory for all five, and
`build_manifest`'s own `verify_served()` returned `VERIFIED_AGAINST_LIVE_RUNTIME` in all five
manifests.

### 5a. Results

| model | digest | events / n | **p̂** | 95% Wilson CI | accepted no-op | rejected | parse-fail cells | env errors | median latency | mean latency | median prompt tok | median resp tok | wall clock |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gemma3:4b` | `a2af6cc3eb7f` | **0 / 45** | 0.000 | [0.000, 0.079] | 0 | 44 | 1 | 0 | 158 ms | 187.2 ms | 150 | 10 | 40.3 s |
| `gemma4:e4b` | `c6eb396dbd59` | **6 / 45** | 0.133 | [0.063, 0.262] | 0 | 39 | 0 | 0 | 225 ms | 326.5 ms | 148 | 12 | 46.0 s |
| `gemma4:12b` | `4eb23ef187e2` | **7 / 45** | 0.156 | [0.077, 0.288] | 0 | 37 | 1 | 0 | 355 ms | 493.1 ms | 152 | 8 | 54.4 s |
| `gemma4:31b` | `6316f0629137` | **16 / 45** | 0.356 | [0.232, 0.502] | 1 | 28 | 0 | 0 | 975 ms | 1112.9 ms | 152 | 11 | 84.1 s |
| `qwen3.6:27b-mlx` | `d49fd9e0da45` | **18 / 45** | 0.400 | [0.270, 0.545] | 0 | 27 | 0 | 0 | 773 ms | 908.7 ms | 161 | 13 | 75.6 s |

Total preflight wall clock for all five models, including model loads and every Lean session:
**5 min 01 s** (`time` on the whole run). Per-model `wall_clock_s` above is the `run_assay` call
only. `tool_timeouts` and `unsupported` were 0 for every model and are omitted from the table.

### 5b. Parse-status detail

`parse-fail cells` above counts cells that never reached Lean. The reason matters, so it is broken
out:

| model | `OK` | `TRUNCATED` | `PARSE_FAILURE` | `TRANSPORT_FAILURE` | parse-failure rate |
|---|---|---|---|---|---|
| `gemma3:4b` | 44 | 1 | 0 | 0 | 2.2 % |
| `gemma4:e4b` | 45 | 0 | 0 | 0 | 0.0 % |
| `gemma4:12b` | 44 | 1 | 0 | 0 | 2.2 % |
| `gemma4:31b` | 45 | 0 | 0 | 0 | 0.0 % |
| `qwen3.6:27b-mlx` | 45 | 0 | 0 | 0 | 0.0 % |

**No model produced a single `PARSE_FAILURE` or `TRANSPORT_FAILURE`.** The two non-`OK` cells are
`TRUNCATED` — the generation hit `num_predict=128` on one long anchor — which the schema keeps
separate from `PARSE_FAILURE` precisely so that "we cut it off" is not read as "it emitted garbage".

### 5c. Cost split

| model | solver seconds | Lean seconds | seconds / solver call |
|---|---|---|---|
| `gemma3:4b` | 8.5 | 0.0 | 0.188 |
| `gemma4:e4b` | 14.7 | 0.2 | 0.327 |
| `gemma4:12b` | 22.2 | 0.2 | 0.494 |
| `gemma4:31b` | 50.1 | 0.3 | 1.114 |
| `qwen3.6:27b-mlx` | 40.9 | 0.4 | 0.909 |

Lean's own `step` cost is sub-second in total for 45 steps, because every arm branches inside an
already-open session on a pre-built Mathlib. The wall-clock remainder (roughly 30 s per model) is
the 15 `open_anchor_session` startups, which are model-independent.

---

## 6. Eligibility

Criterion applied identically to all five: **a model is eligible unless it is at the floor, at the
ceiling, broken, or unsupported.** "Floor" is read off the 95 % Wilson interval at the realised
n = 45, not off a point estimate.

| model | verdict | reason |
|---|---|---|
| `gemma3:4b` | **INELIGIBLE — AT THE FLOOR** | 0 events in 45; CI [0.000, 0.079] excludes any rate above 8 %. Not broken and not mis-wired: 44/45 proposals reached the kernel and were rejected on the mathematics (see §7). |
| `gemma4:e4b` | **ELIGIBLE** | 6/45 = 0.133, CI excludes 0 and excludes 1; no parse failures, no environment errors. |
| `gemma4:12b` | **ELIGIBLE** | 7/45 = 0.156, CI excludes 0 and excludes 1; one truncation, no parse failures, no environment errors. |
| `gemma4:31b` | **ELIGIBLE** | 16/45 = 0.356, CI excludes 0 and excludes 1; clean run. |
| `qwen3.6:27b-mlx` | **ELIGIBLE** | 18/45 = 0.400, CI excludes 0 and excludes 1; clean run. Matches `RECORDED_SOLVER` on every served field. |

No model is at the ceiling: the highest p̂ is 0.400 with an upper bound of 0.545.
No model is broken: zero `ENVIRONMENT_ERROR`, zero `TOOL_TIMEOUT`, zero `TRANSPORT_FAILURE`, zero
skipped anchors, zero theorem errors, across all five.
No model is unsupported: all five accepted the frozen wire flags, the JSON grammar and
`num_ctx=32768`.

---

## 7. Is any model mis-wired rather than incapable?

**Conclusion: no. `gemma3:4b` is incapable at this task under these conditions, not misconfigured.**
The evidence, in the order it rules the alternative out:

1. **The HC-V0.5 failure mode is directly excluded by measurement.** That failure was an *empty*
   `response` with the whole budget spent on hidden reasoning. `gemma3:4b` returned a non-empty,
   grammar-valid `{"tactic": ...}` on 44 of 45 cells, and `thinking` was empty (0 characters) on
   every smoke call.
2. **Its parse-failure rate is 2.2 %, the same as `gemma4:12b`'s and lower than nothing.** The
   trigger condition for a misconfiguration investigation — a *high* parse-failure rate — is not
   met. The single non-`OK` cell is a `TRUNCATED`, not a `PARSE_FAILURE`.
3. **The prompt reached the weights intact.** Its median prompt token count is 150, inside the
   148–161 band of the other four models on the identical anchors; its range (84–693) tracks theirs
   (82–735). A model that was not being shown the goal would not scale its prompt with the goal.
4. **It produced 31 distinct, Lean-tactic-shaped strings**, and Lean evaluated every one of them.
   The failures are mathematical and syntactic, not structural: `rewrite h` (Lean 4 requires
   `rewrite [h]`), bare `rw` with no rule list, `rw [ncard_eq]}` with a stray brace, and invented
   lemma names such as `rewrite_insert` and `rewrite_product_eq_product`. It also proposed the
   genuinely well-formed `intro`, `simp` and `contradiction`, which the kernel rejected because they
   do not apply at those goals — which is only possible if the kernel really ran them.

**One caveat recorded rather than resolved.** `gemma3:4b` is the only model with no
`RENDERER`/`PARSER` directive, so its prompt is framed by Ollama's legacy Go chat template while the
other four use a native renderer. `solver_for` accepts this by design ("only the served weights,
tokenizer and chat renderer change, and those are exactly the thing under comparison"), and the
model demonstrably answered — but the floor verdict is a verdict *under this framing*, and a
different chat framing was **not measured**.

---

## 8. Information rate

```
information_rate = p_hat * (1 - p_hat) / median_call_seconds
```

| rank | model | p̂ | median call (s) | **information rate** |
|---|---|---|---|---|
| 1 | `gemma4:e4b` | 0.133 | 0.225 | **0.5136** |
| 2 | `gemma4:12b` | 0.156 | 0.355 | **0.3700** |
| 3 | `qwen3.6:27b-mlx` | 0.400 | 0.773 | **0.3105** |
| 4 | `gemma4:31b` | 0.356 | 0.975 | **0.2350** |
| 5 | `gemma3:4b` | 0.000 | 0.158 | **0.0000** |

**What it captures.** The Bernoulli variance a model generates per second of its own generation
time. A paired binary assay's precision at fixed compute scales with this, so it is a fair
first-order answer to "how much statistical signal does one second of this model buy".

**What it does not capture, and must not be read as.**

* **Not capability.** It is maximised at p̂ = 0.5, so a *better* model can rank lower. `gemma4:e4b`
  ranks first with the second-lowest event rate of the four eligible models.
* **Not the floor test.** `gemma3:4b` scores 0.0000 only because p̂ = 0; the rate is silent about
  whether a model is at the floor, which §6 decides separately.
* **Not the assay's power.** It ignores pairing, the mathlib-file clustering unit, between-anchor
  correlation, and the effect size under test — all of which the preregistered analysis uses.
* **Not total cost.** It excludes Lean's step cost, the 15 session startups, and model load/reload
  cost, which for a 27–31 B model is a real fraction of a short run.
* **Not stable at n = 45.** p̂ carries a wide interval (e.g. `gemma4:e4b`'s [0.063, 0.262] maps to a
  rate anywhere in roughly [0.26, 0.86]). The ranking of the middle three is inside its own noise.

**It is a heuristic, not a decision rule.** It is reported because it was asked for, and it is not
used here to select anything.

---

## 9. Honest limitations

* **n = 45 anchors, 15 clusters, k = 1.** Every p̂ carries a wide interval. Nothing here supports a
  fine-grained ranking of the three middle models.
* **Latency is confounded with run order and co-residency.** Models were run strictly sequentially
  (never concurrently), but Ollama's `keep_alive` left more than one model resident at times —
  `ollama ps` immediately after the run showed `qwen3.6:27b-mlx` (27 GB) and `gemma4:e4b` (9.7 GB)
  both loaded. Models later in the sequence therefore ran under more memory pressure than
  `gemma3:4b`, which ran first on an empty runtime. Medians absorb the one-off load call but not
  sustained pressure. **The magnitude of this effect was not measured.**
* **Another agent was running Lean concurrently** during this window. Lean's own contribution is
  sub-second per model here, so the effect on these numbers is small, but the ~30 s per model of
  session-startup wall clock is subject to that contention and was not isolated.
* **Latency is single-run.** No model was re-timed, so no within-model latency variance is reported.
* **`gemma3:4b`'s chat framing differs** from the other four (§7 caveat). Not measured under an
  alternative framing.
* **No lineage claim is made anywhere.** Five models, ten pairs, `UNKNOWN` training lineage on all
  ten.
* **`R_A` only.** No Δ between representations exists in any artefact this document points at.

---

## 10. Gates (actual output)

```
$ .venv/bin/python -m ruff check research/phase10/models/
All checks passed!

$ .venv/bin/python -m ruff format --check research/phase10/models/
3 files already formatted

$ .venv/bin/python -m ruff format --check .
383 files already formatted

$ .venv/bin/python -m ruff check .
F821 Undefined name `cells_path`
   --> arena/experiments/hc_v0_6_assay.py:457:27
Found 1 error.
```

The repo-wide `ruff check .` failure is **not** in a file added or edited here.
`arena/experiments/hc_v0_6_assay.py` is owned elsewhere and the undefined name is in its
`main()` CLI path, which this preflight never calls — it imports `run_assay` and `build_manifest`
directly. It is reported, not fixed.

`.venv/bin/python -m pytest` was **not run** as part of this work item.
