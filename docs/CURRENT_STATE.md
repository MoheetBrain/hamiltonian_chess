# Current State Reconstruction

Recorded: 2026-09-05 (Europe/London)

## Arena repository

- Path: `/Users/moheet/Documents/ChatGPT/hamiltonian_chess`
- Branch at reconstruction: unborn `main`; implementation branch: `codex/arena-v0`
- Start SHA: `0000000000000000000000000000000000000000` (empty repository)
- Remote: `https://github.com/MoheetBrain/hamiltonian_chess.git`
- Remote state at reconstruction: no advertised refs (empty)
- Isolation: dedicated repository; no HML or corpus worktree is modified

## Read-only source repositories

| Source | Path | Branch | SHA | State | Reuse decision |
|---|---|---|---|---|---|
| HML V3 experiments | `/Users/moheet/Documents/ChatGPT/HML_V3` | `codex/open-ended-search-v2` | `4395a8c717a334be58b29d53b43c0c842d0e03ac` | dirty | evidence only; no blind copy |
| Hamiltonian Lang final-signal | `/Users/moheet/Documents/ChatGPT/hamiltonian-lang-final-signal` | `claude/model-language-representation-freeze` | `b011511e72572608eb7836d3b8a1a6bb794c890d` | clean | optional semantic reference only |
| Reasoning corpus | `/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus` | `claude/max-ev-representation-experiment-v1` | `bf2cd75a0676afdb73ab15fe5963cb6138e27060` | clean | provenance-preserving adapter candidate |
| PRM800K | `/Users/moheet/Documents/ChatGPT/prm800k` | `main` | `7ecc794703b2877f63226f2477a49b34f9b25163` | clean | Silver/raw source only |

The HML V3 branch already contains canonical records, renderer candidates, genome search,
failure memory, Pareto gates, and neural probes. Its canonical records explicitly warn that
pretty-printed Lean expressions are source-specific rather than a universal AST. Arena v0
therefore uses a new typed term schema and imports nothing until an adapter proves semantic
accounting.

## Existing corpus and experiments

- `hmlt-reasoning-corpus/data/vnext_10k`: 10,000 source records with 8,132 train, 952 dev,
  and 916 test records; four rendered views (`AST`, `HML_LINEAR`, `HML_TREE`,
  `STRUCTURED_NEUTRAL`); approximately 37 MB.
- `hmlt-reasoning-corpus/data/gold_10`: 10 frozen Gold examples, approximately 92 KB.
- `hmlt-reasoning-corpus/data/hml_structural_final`: audited structural artifacts,
  approximately 108 KB.
- HML V3 reports show prior representation-search and losslessness experiments. Those results
  are priors, not Arena scores, because the canonical schema and test protocol differ.

## Legacy test state (observed, not repaired here)

- HML V3 local environment: 231 tests and 338 subtests passed before
  `FailureMemoryTests.test_every_lesson_declares_its_evidence_status` failed because `FM-053`
  carries `REASONING_ERROR` where the test permits only measured/asserted evidence statuses.
- Hamiltonian Lang final-signal local environment: collection stopped in
  `tests/arena/test_b2_audit.py`; `evaluation.arena.endpoints.common` is absent.

Neither legacy suite is green, so neither repository is a trusted dependency.

## Hardware and local models

- Apple MacBook Pro `Mac17,6`, Apple M5 Max
- CPU: 18 cores (6 Super, 12 Performance)
- GPU: integrated 40-core Apple GPU, Metal 4
- Unified memory: 48 GB
- macOS 26.6.2, arm64
- Ollama installed at `/opt/homebrew/bin/ollama`
- Installed Ollama models at reconstruction:
  `qwen36-huihui:latest` (29 GB), `qwen38-huihui:latest` (24 GB),
  `qwen38-rvn:latest` (16 GB), `gemma4:e4b` (9.6 GB), `gemma3:4b` (3.3 GB),
  `gemma4:12b` (7.6 GB), and `gemma4:31b` (19 GB).

Model names are local labels, not scientific identities. Any result must also record the
Ollama digest, tokenizer identity when available, prompt hash, generation settings, and seed.

## Verifiers and Python tooling

- Python 3.14.7 and `uv` are installed.
- Lean 4.33.1 (`819816b2e0a3bf405af45ae5c7af2491d8f5bee6`) and Lake 5.0.0 are installed.
- SQLite is provided by macOS.
- SymPy, Z3, pytest, Hypothesis, NumPy, scikit-learn, and PyTorch were not importable from the
  global Python at reconstruction. Arena declares isolated `uv` dependencies for SymPy, Z3,
  pytest, Hypothesis, and scikit-learn; model training remains an optional external adapter.
- No NVIDIA/CUDA device is present. Local matched training must use an Apple-compatible model
  stack or an explicitly recorded remote runner; Ollama inference alone is not matched
  adaptation.

## Scientific consequence

The local machine is adequate for deterministic canonical generation, thousands of static
candidates, fuzzing, SymPy/Z3 differential checks, small Ollama scouts, and a lightweight
surrogate. It cannot by itself establish cross-model representation-level superiority or run
a credible 1M-trajectory training programme. Arena must be allowed to finish with no R*.
