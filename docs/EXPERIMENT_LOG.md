# Experiment Log

## Reconstruction

- Confirmed the target repository had no commits or advertised remote refs.
- Recorded source-repository SHAs, corpus counts, hardware, local models, Lean, and tool state in
  `CURRENT_STATE.md`.
- Observed one HML V3 test failure and one final-signal collection failure; neither was changed.

## Build verification

- Installed the isolated environment with `uv sync --all-extras`.
- Verified all eight candidate surfaces on shared canonical states.
- Verified the 676-task generator balance and quality policy.
- Ran Ruff, mypy, and the 103-test repository suite after integration.
- Built the final world with seed 0 and hash
  `ac16014cd20fbed2dabacd75bff3fd19723e3e96048f82a1ee1a574f59daf256`.
- Ran static match `match:78f6093ba41426a45b4c` over all eight seed languages.

## Assurance smoke

- Semantic properties: 16/16 passed on the frozen base state.
- Canonical expression universe: 2,703/2,703 passed.
- Evidence graph universe: 64/64 passed.
- Differential claims: zero unresolved disagreements across nine supported checker verdicts.
- Required-world roundtrip: 1,352/1,352 states for every seed candidate.

## Interpretation

These are infrastructure and bounded soundness results. No matched model adaptation has run,
so no candidate has earned the R* name. The exact generated tournament values live under
`artifacts/reports/` and in `artifacts/arena.db`.

## Representation fitness v1 continuation

- Created `codex/arena-v0-fitness` from `c1dd586` and pre-registered the scientific objects in
  commit `f17bb0f73ac942d43b614704e54c019a64284368` before any model inference.
- Audited all branches, tags, and history of HML_V3, hml-reasoning-corpus, hml-standard, and
  hamiltonian-lang. Historical scores were retained only as priors/failure memory.
- Materialized 120 deterministic one-gene executable phenotypes across all eight parents.
  All 120 passed 124,800 Gold state/phenotype checks with zero critical failures or collisions.
- Froze a group-aware 520-Gold split: 160 DEV, 120 SCOUT, 160 PROMOTION, 80 structural OOD.
- Ran 64 cached calibration cells with local `gemma3:4b` at the frozen Q4_K_M blob digest.
  The nominal strongest-control accuracy was 7/16, but both leading controls chose A on every
  task and no control beat the 9/16 always-B baseline.
- Marked the instrument `INSTRUMENT_INVALID_POSITION_ONLY` and stopped before Tier 2A. No
  candidate model ranking, landscape model claim, matched adaptation, or R* decision was made.
