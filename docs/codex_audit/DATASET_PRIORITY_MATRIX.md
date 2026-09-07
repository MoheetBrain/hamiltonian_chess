# Dataset Priority Matrix

Metadata was checked against official repositories/cards on 2026-09-07. No bulk data was
downloaded. “Verifier” means an executable mathematical checker, not merely final-answer text.

## Priority by information gain per engineering hour

| Priority | Dataset | Official metadata | Arena role | What it contains | Verification / contamination | Local / effort / immediate EV |
|---:|---|---|---|---|---|---|
| 1 | LeanDojo Benchmark 4 | [LeanDojo](https://github.com/lean-dojo/LeanDojo), MIT tool; benchmark extracted from Mathlib | trajectory data, operation discovery, D, U links | theorem proof states, tactics, premises, splits | Lean-sourced traces; preserve theorem splits; common model-training contamination | **Local**, 259,580 derived steps; low effort; highest EV |
| 2 | Mathlib4 pinned | [Mathlib4](https://github.com/leanprover-community/mathlib4), Apache-2.0 | Σ, U, verifier, D | evolving Lean 4 library and tactics | Lean kernel; version sensitivity is absolute | **Local** at `29dcec0`, but build incomplete (38 olean); medium effort, very high EV |
| 3 | Lean runtime V2 (local derivative) | pinned Mathlib/LeanDojo provenance | Σ pressure test, formal states | 1,150 elaborated transitions; 461 eligible states | structural facts recomputed; not full tactic replay | **Local**; low effort; ideal bounded pilot |
| 4 | miniF2F v2 | [updated benchmark](https://github.com/facebookresearch/miniF2F), v2 frozen Oct 2022, 488 statements; per-system licences | OOD/evaluation, formal↔informal | Olympiad statements in Lean/Isabelle/Metamath plus informal text | proof assistant for completed proofs; globally saturated benchmark | **Local** Lean4 port, 500 declarations; low-medium ingestion; keep eval-only |
| 5 | ProofNet | [official repo](https://github.com/zhangir-azerbayev/ProofNet), 371 examples, MIT | formal/informal alignment, OOD eval | undergraduate NL statement/proof paired with Lean statement | original is Lean 3; statements do not supply proof trajectories | **Local** community Lean4 port; low-medium effort; evaluation first |
| 6 | OpenAI PRM800K / held-out 500 | [official repo](https://github.com/openai/prm800k), MIT repository | controller/search, dead-end and progress labels | 101,599 solutions, ~800k process labels; 500 held-out MATH problems | human process labels, not logical verification; MATH contamination high | **Local** official clone; low effort; high controller EV, low Σ EV |
| 7 | Nemotron-Math-Proofs-v1 | [official card](https://huggingface.co/datasets/nvidia/Nemotron-Math-Proofs-v1), Dec 2025, ~925k rows, CC-BY-SA-4.0 | eventual training, formal/NL alignment, proof generation | ~580k NL proof problems, ~550k Lean statements, ~900k generated trajectories | generated proofs compiler-checked where completed; source licences vary; heavy benchmark contamination | not local; high ingestion/replay effort; high later EV |
| 8 | NuminaMath-1.5 | [official card](https://huggingface.co/datasets/AI-MO/NuminaMath-1.5), 896,215 rows / 531 MB, Apache-2.0 | D, curriculum, eventual training | informal problems with CoT and rich source metadata | final-answer/curation, not proof truth; duplicates and benchmark mixture likely | partial/local derivative exists; medium audit effort; high D EV only |
| 9 | Goedel-Pset-v1 | [official card](https://huggingface.co/datasets/Goedel-LM/Goedel-Pset-v1), 1.73M parquet rows | formalization pool, D | NL problem paired with Lean statement | compilation with `sorry` plus model-based faithfulness/completeness; not proved statements; licence requires manual check | not local; high audit/replay effort; medium EV |
| 10 | DeepSeek-Prover-V2 / ProverBench | [official repo](https://github.com/deepseek-ai/DeepSeek-Prover-V2), 325 benchmark problems and released miniF2F solutions | D, evaluation, subgoal research | Lean4 formalizations and generated whole proofs | Lean-checkable; model-data licence does not automatically license upstream data | not local; medium effort; medium-high task-family EV |
| 11 | MATH / MATH-500 | [MATH repo](https://github.com/hendrycks/math), 7,500 train + 5,000 test, MIT repo; official PRM split supplies held-out 500 | D, OOD eval, informal reasoning | competition problems and worked solutions | answer checking only; ubiquitous contamination; redistribution/licence scope needs review | **Local** MATH + exact 500; low effort; keep 500 eval-only |
| 12 | NaturalProofs | [official repo](https://github.com/wellecks/naturalproofs), 2021 | retrieval, reasoning-operation discovery, NL proof generation | ProofWiki-derived theorems, proofs, definitions and reference tasks | natural-language, no executable proof checker; web-source contamination | not local; medium effort; medium discovery EV |
| 13 | Isabelle AFP | [official archive](https://isa-afp.org/), current statistics 1,025 entries / ~325,500 lemmas; BSD-style or LGPL | cross-system U, trajectories, OOD | Isabelle developments and proofs | mechanically checked, but new Isabelle adapter required | not local; high ingestion effort; high long-run, low immediate EV |
| 14 | Metamath `set.mm` | [official repo](https://github.com/metamath/set.mm), active database | cross-system Σ/U, microstep trajectories | compressed proof steps over ZFC | independently reverified by multiple verifiers; different foundation | not local; high adapter effort; medium long-run EV |
| 15 | AMPS | [official MATH repo](https://github.com/hendrycks/math) links AMPS; large synthetic pretraining corpus | eventual pretraining, D | Khan-style and Mathematica-generated problems | informal/synthetic; high duplication/template and licence risk | 103,059 Khan rows local; medium cleaning, low immediate causal EV |
| 16 | GSM8K | [official repo](https://github.com/openai/grade-school-math), 8.5k, MIT | development, arithmetic D | 2–8-step human-written arithmetic word problems | answer calculations, occasional known errors; saturated benchmark | **Local**, 8,792; low effort, low structural EV |
| 17 | Open textbooks | [Hefferon](https://hefferon.net/source.html), GFDL or CC-BY-SA-3.0; [Levin](https://math.oscarlevin.com/textbooks.html), CC-BY-SA-4.0 source | D, operation discovery, later formalization | proof-oriented linear algebra and discrete mathematics prose/exercises | no executable verifier until formalized; clean source attribution available | not registered as corpora; high segmentation/formalization effort; medium diversity EV |

## ProofNet-Verified caveat

No separate authoritative “ProofNet-Verified” release was located in the audited local registry
or official ProofNet repository. Treat that name as `REPORTED_NOT_REPRODUCED` until a precise
repository, commit, licence and verification procedure are supplied. Do not merge it with the
371-example original or the local community Lean4 port.

## Decision rules

- For the next instrument, prioritize *locally present executable state transitions*, not raw
  dataset size.
- Preserve miniF2F, ProofNet, MATH-500 and official LeanDojo test partitions as evaluation.
- Treat `by sorry` compilation as statement well-typedness, not theorem proof.
- Resolve per-row upstream licence fields before redistributing mixed corpora.
- Do not ingest AFP/set.mm merely to make vNext universal; add a backend only after a concrete
  task requires its semantics.
