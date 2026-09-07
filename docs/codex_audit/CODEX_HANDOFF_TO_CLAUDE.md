# Codex Handoff to Claude

## Git identity

- Branch: `codex/forensic-audit-20260907`
- Base SHA: `b150ce1c0c758f773ca5e575a3db82928dcb3737`
- Final SHA: resolve immutable branch head with
  `git rev-parse codex/forensic-audit-20260907` (a commit cannot contain its own SHA without
  changing that SHA).
- Remote SHA: after push, verify with
  `git ls-remote origin refs/heads/codex/forensic-audit-20260907`.
- Writes are confined to `docs/codex_audit/` and `research/codex_audit/`.

## Read this first

Phase 6 must be classified `PHASE6_INVALID` under its literal preregistered rule: the Qwen
artifact contains cache hits. The numerical result is still useful descriptively because every
row identity binds the Qwen digest and bare runtime. Qwen escapes Gemma's fixed-cell degeneracy
and qualifies one mechanism, but the frozen Game-R gate requires at least two. Do not launch
founders and do not lower the threshold.

## Confirmed defects

1. Old model name/cache digest decoupling could replay another model's cache — fixed.
2. Gemma and Qwen renderer paths were asymmetric — contained by bare/bare.
3. Gemma-bare temporarily overwrote frozen Phase-5 `result.json` — restored/fixed.
4. Qwen artifact has 13 ladder resume hits plus 48 within-run full-family reuse hits — literal
   Phase-6 invalidation rule fired.
5. Destroyed twins force negative accuracy .500; gap gate requires positive ≥.70 while the
   frontier selector targets .625.
6. Formal-depth target preorder/first-mentioned shortcut is 1.000 shallow and .9167 deep.
7. Route-B split seed is unused.
8. Route-B Stage B mixes 424 GOLD, 104 SILVER, 48 REJECT.
9. Route-B at budget 224 has 21/48 answer-or-problem recurrence, including 5 exact problems.
10. Route-B “verified” checks only JSON key presence.
11. Route-B compares five hard-coded codecs, not causal genome-gene changes.
12. Route-B tail-truncates to 1,536 tokens and compares representation-dependent token losses.
13. World-v0 state→action ID and domain→operation policies solve 676/676.
14. World-v0 contains one legal action in 676/676; correct NEXT_ACTION projection removes it,
    making this a projection-bypass risk.
15. The canonical-vNext report's 5,680-olean/full-build claim does not match the audited pinned
    checkout, which has 38 olean and a 32/100 replay-pass sample.
16. The shared virtualenv can import another checkout without explicit `PYTHONPATH`.
17. Qwen Phase-6 result is untracked in your worktree and must be frozen without rerun.

Full consequences and owners: `MASTER_RISK_REGISTER.md`.

## Hypotheses falsified or corrected

- “~300,000 granular reasoning steps” is false: 792 steps across 135 problems. The ~260k
  quantity is LeanDojo tactic transitions.
- “first-mentioned ≈.913 on all length-fair states” is imprecise: deep L3 is 22/24=.9167;
  pooled four-level bank is 78/96=.8125; shallow is 24/24=1.0.
- ID-disjoint Route-B splits are not content-clean: 5 exact problems recur at Stage A, with
  broader answer/action recurrence.
- Route-B `verified=1.0` is not verifier acceptance.
- Different codec bytes do not establish a specific genome gene effect.
- World-v0 next-action success cannot rule out metadata learning.
- `result-qwen38-rvn_latest-bare.json` cannot be called a valid confirmatory Phase-6 result
  under the frozen cache rule.

## Datasets discovered and verified

- LeanDojo `steps.jsonl`: 259,580 rows, 271,038,884 bytes, SHA `ddd90685…`, 418,704 premise
  refs, Mathlib `29dcec0`.
- Lean runtime V2: 1,150 rows in five gzip parts, 461 structurally eligible, 104 length-fair.
- Granular Gold chains: 10+25+100 problems, 23+118+651 = 792 steps.
- PRM800K official clone: 101,599 records; exact held-out 500 SHA `35dc4108…`.
- HML_V3 registry: 27 local entries including Lean-Domino 241,265, STP 3,262,558,
  NuminaMath-Lean 104,155, Herald 44,553, state-tactic 56,407, MATH 12,500, AMPS 103,059,
  Pythagoras 126,113 and GSM8K 8,792.
- Pinned Mathlib: `29dcec0`, Lean 4.10.0-rc1, 38 olean, 352,733,938 bytes.

Exact paths and trust boundaries: `LOCAL_MATH_DATA_ATLAS.md` and
`research/codex_audit/local_data_registry.json`.

## Results reproduced

- Phase-5 frozen SHA `0c5b3271…`; Gemma-bare SHA `6deead58…`; Qwen uncommitted SHA
  `e753de98…`.
- Qwen ladders: formal `.1/.833/.792/.625`, transitive `.958/1/.958/.750`, precondition
  `1/.958/1/1`; only transitive qualifies.
- Fixed collapsed cells: Gemma framed 72/72 modal, Gemma bare 67/72, Qwen bare 36/72;
  Qwen exact McNemar p=`2.91e-11`.
- Route-B seed/quality/overlap/metric/codec/token findings.
- All 676 World-v0 baseline findings.
- Local corpus row counts, hashes, repository pins and operation frequencies.

## Unresolved discrepancies

- Exact provenance of the 13 Qwen ladder cache rows is inferred from the documented restart and
  matching identities; no append-only per-call ledger was available.
- Source of the claimed 5,680 `.olean` count is unknown.
- “ProofNet-Verified” was not found as a distinct official/local release.
- Licences for some mixed/generated datasets (especially Goedel source rows) require legal
  review beyond repository-level metadata.
- Whether clean rewrite/premise tasks can balance every deterministic shortcut is untested.

## Files created

### Reports

- `docs/codex_audit/EXPERIMENT_EVIDENCE_LEDGER.md`
- `docs/codex_audit/PHASE6_FORENSIC_REVIEW.md`
- `docs/codex_audit/ROUTE_B_CAUSAL_AUDIT.md`
- `docs/codex_audit/WORLD_V0_LEAKAGE_AUDIT.md`
- `docs/codex_audit/LOCAL_MATH_DATA_ATLAS.md`
- `docs/codex_audit/DATASET_PRIORITY_MATRIX.md`
- `docs/codex_audit/REASONING_OPERATION_AUDIT.md`
- `docs/codex_audit/FUTURE_ENVIRONMENT_RANKING.md`
- `docs/codex_audit/FORMAL_DEPTH_SHORTCUT_AUDIT.md`
- `docs/codex_audit/CANONICAL_VNEXT_RED_TEAM.md`
- `docs/codex_audit/GAME_THEORY_IMPLEMENTATION_GAPS.md`
- `docs/codex_audit/MASTER_RISK_REGISTER.md`
- `docs/codex_audit/MASTER_SCIENTIFIC_REVIEW.md`
- `docs/codex_audit/CODEX_HANDOFF_TO_CLAUDE.md`

### Machine outputs

- `research/codex_audit/experiment_evidence.json`
- `research/codex_audit/route_b_audit.json`
- `research/codex_audit/world_v0_baselines.json`
- `research/codex_audit/local_data_registry.json`
- `research/codex_audit/operation_inventory.json`
- `research/codex_audit/risk_register.json`
- `research/codex_audit/formal_depth_shortcuts.json` (additional direct reproduction)

### Reproduction scripts

- `research/codex_audit/scripts/experiment_evidence.py`
- `research/codex_audit/scripts/route_b_audit.py`
- `research/codex_audit/scripts/world_v0_baselines.py`
- `research/codex_audit/scripts/local_data_inventory.py`
- `research/codex_audit/scripts/operation_inventory.py`
- `research/codex_audit/scripts/formal_depth_shortcuts.py`
- `research/codex_audit/scripts/risk_register.py`

### Audit tests

- `research/codex_audit/tests/test_audit_outputs.py`

## Reproduce

From the audit worktree, with the shared Python executable but forced local import:

```bash
export PYTHONPATH="$PWD"
PY=/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.venv/bin/python
$PY -c 'import arena, pathlib; print(pathlib.Path(arena.__file__).resolve())'
$PY research/codex_audit/scripts/experiment_evidence.py --root "$PWD" \
  --qwen-phase6 /absolute/path/to/result-qwen38-rvn_latest-bare.json \
  --out research/codex_audit/experiment_evidence.json
$PY research/codex_audit/scripts/route_b_audit.py --root "$PWD" \
  --out research/codex_audit/route_b_audit.json
$PY research/codex_audit/scripts/world_v0_baselines.py --root "$PWD" \
  --out research/codex_audit/world_v0_baselines.json
$PY research/codex_audit/scripts/local_data_inventory.py \
  --out research/codex_audit/local_data_registry.json
$PY research/codex_audit/scripts/operation_inventory.py \
  --leandojo /Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl \
  --reasoning-root /Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus \
  --out research/codex_audit/operation_inventory.json
$PY research/codex_audit/scripts/formal_depth_shortcuts.py --root "$PWD" \
  --out research/codex_audit/formal_depth_shortcuts.json
$PY research/codex_audit/scripts/risk_register.py \
  --out research/codex_audit/risk_register.json
```

Do not run those commands without first verifying the printed import path is this worktree. None
calls Ollama or a model.

## Integration labels

### SAFE_TO_CHERRY_PICK

The entire `docs/codex_audit/` and `research/codex_audit/` namespaces. They are additive and do
not modify frozen experiments, caches, artifacts or shared status files.

### REPORT_ONLY

All findings about Phase 6, Route B, World-v0, formal depth and vNext. Decide which shared status
documents to update in your own branch. The external absolute paths in machine JSON are an audit
snapshot, not portable runtime configuration.

### DO_NOT_MERGE

No production patch is included. Do not copy or modify the external Qwen artifact through this
branch. Do not merge any threshold change, founder launch or retroactive reinterpretation; none
is authorized here.

## First action on return

Freeze the Qwen artifact at its audited SHA and publish `PHASE6_INVALID` plus the narrower
descriptive solver-effect observation. Then stop: no founder or model run. Read
`MASTER_SCIENTIFIC_REVIEW.md` and decide between the bounded two-family Lean pilot and a fully
repaired Route-B design.
