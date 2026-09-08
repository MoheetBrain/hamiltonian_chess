# SOURCE LEDGER

**Authority:** subordinate to `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`
(the *manual*). Written under manual §36.3 and §49. Every normative statement elsewhere in `spec/`
traces to a manual section number; this file traces the manual's own **source classes** (§49) to
the documents and artifacts in this repository that instantiate them.

Epistemic type of this document as a whole: `KNOWN_FACT` (§37) — it records paths and hashes that
were read on 2026-09-08, not judgements about them.

---

## 1. Frozen sources and their hashes

| Role | Path | sha256 | Status |
|---|---|---|---|
| Governing specification manual (§47 Step 2) | `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` | `f3c04e691d4cda2622b3440eec60d2d8f0c7dd24d09238656bdfa5e35a1768cf` | **Stored unchanged.** 2,829 lines. Not edited, not reformatted, not exploded (§47 Step 2, §0.1). |
| Prior permanent objective | `GOAL.md` | `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b` | **Preserved unmodified.** |

### 1.1 The standing of `GOAL.md` (§3.1, §3.3)

`GOAL.md` is **not retracted, not edited, and not superseded retroactively** (§3.3: evidence and
prior contracts are immutable; corrections are additive).

- **For mission purposes** `GOAL.md` is now subordinate. `docs/HAMILTONIAN_CHESS_META_GOAL.md`
  states this explicitly ("This document sits ABOVE `GOAL.md`"), and the manual's §4 constitution
  plus §3.1 precedence order place the accepted constitution above historical documents.
- **For local Game-R assays `GOAL.md` still governs.** Every discipline it mandates — paired
  parent-vs-child comparison, frozen semantics inside an assay, one Solver held fixed, held-fixed
  visible information, deterministic verification, shortcut attacks, provenance, cache discipline,
  preregistration — remains binding wherever an assay is run. This is the demotion described in
  `docs/HAMILTONIAN_CHESS_META_GOAL.md` §3 and is consistent with manual §35 ("DEMOTE TO
  DIAGNOSTIC") and §4 (Game R is a controlled assay inside Arena, not the meta-game).
- `GOAL.md` §16's evidence ladder is the ancestor of manual Appendix D. Where the two differ, the
  manual governs prospectively (§3.1).

---

## 2. §49 source-class trace table

Each row: the manual's declared source class, the repository artifacts that instantiate it, and
what specification content in `spec/` depends on it.

| §49 source class | Instantiating artifacts in this repository | Consumed by |
|---|---|---|
| `OWNER_DIRECTIVE` | `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`; `GOAL.md`; `docs/HAMILTONIAN_CHESS_META_GOAL.md` (records the 2026-09-08 owner mission reset and the demotion of Game R); `docs/PHASE5_SCHEDULED_DIRECTIVE.md` | `spec/00_CONSTITUTION.md`, `spec/meta_game/HC_V0_OUTER_LOOP.md` |
| `CURRENT_ARENA_GOAL` | `GOAL.md`; `docs/ARENA_PROTOCOL.md`; `docs/ARENA_MASTER_ARCHITECTURE.md`; `docs/ARCHITECTURE.md`; `docs/CURRENT_STATE.md`; `docs/PROJECT_STATUS.md` | `spec/00_CONSTITUTION.md`, `spec/evaluation/HC_V0_EVALUATOR_CONTRACT.md` |
| `HML_LEGACY_GOAL` | `docs/REUSE_SUMMARY_FOR_CLAUDE.md`; `docs/CROSS_REPO_ASSET_AUDIT.md`; `artifacts/reuse/provenance.jsonl`; `artifacts/reuse/cross_repo_assets.json` | `spec/01_GLOSSARY.md` (§5.1 HML is an ancestor, not the answer) |
| `HML_LEGACY_ARCHITECTURE` | `releases/TRAINING_LANGUAGE_V0/` (`SPEC.md`, `core.py`, `syntax.py`, `libraries.py`, `HASHES.json`); `docs/TRAINING_LANGUAGE_V0.md`; `docs/LANGUAGE_GENOME.md`; `arena/canonical/` | `spec/language/language_genome_v0.schema.json` |
| `SEMANTICS_SOURCE_SYNTHESIS` | `docs/SOUNDNESS.md`; `docs/MATHEMATICAL_WORLD.md`; `docs/ARCHITECTURE.md`; `docs/CONTENT_GENOME_V1.md` | `spec/world/VERIFIED_TASK_TRAJECTORY_CONTRACT.md` (§7 three-layer firewall, §8 PL constitution) |
| `EXPERIMENTAL_RESULT` | `docs/EXPERIMENT_LOG.md`; `docs/FITNESS_V5_RESULT.md`; `docs/FITNESS_V7_RESULT.md`; `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md`; `docs/CANONICAL_VNEXT_PILOT.md`; `docs/VERIFIED_TRAJECTORY_ARENA_V0.md`; `artifacts/reports/*.json`; `research/*/` raw JSON | `spec/02_CLAIM_LEDGER.jsonl` (every `KNOWN_FACT` row) |
| `FORENSIC_AUDIT` | `docs/V7_TOTAL_FORENSIC_AUDIT.md`; `research/audit/a1…a9*.md`; `docs/ROUTE_B_HISTORICAL_AUDIT.md`; `docs/ROUTE_B_PARITY_AUDIT.md`; `docs/PRECONDITION_RENDERED_SHORTCUT_AUDIT.md`; `docs/GENOME_CONTENT_AUDIT.md`; `docs/CANONICAL_VNEXT_GAP_REPORT.md` | `spec/02_CLAIM_LEDGER.jsonl` sentinels; `spec/evaluation/HC_V0_EVALUATOR_CONTRACT.md` |
| `PRIOR_ART_AUDIT` | `docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md` (verdict `NOVEL_ONLY_IN_COMBINATION`) | `spec/00_CONSTITUTION.md` §5 reference; `spec/02_CLAIM_LEDGER.jsonl` `CLM-PRIORART-001` |
| `SPECIFICATION_RESEARCH` | the manual itself; `docs/HAMILTONIAN_CHESS_META_MDP.md`; `docs/HAMILTONIAN_CHESS_REPO_REMAP.md`; `docs/LANGUAGE_META_GENOME_V0.md`; `docs/LONG_HORIZON_FITNESS_V0.md`; `docs/LANGUAGE_FITNESS_MEMORY.md`; `docs/PHASE8_SALVAGE_HANDOFF.md` | every file in `spec/` |
| `ENGINEERING_ADR` | `docs/DECISIONS.md` (historical decision log); `spec/ADR/` — **empty at time of writing**, and that is correct under §0.1: no ADR is required until a `SHOULD` is deviated from | `spec/implementation/HC_V0_MANIFEST.yaml` |

---

## 3. What is deliberately absent

Under §0.1 and §36.1 ("Only files required to remove a current blocker need to exist"):

- `spec/ADR/` is an empty directory. An ADR is written when a manual `SHOULD` is deviated from
  (§1), not in advance.
- `spec/language/LANGUAGE_META_GENOME_V0.md` (named in §36.1's tree) is **not** duplicated here.
  `docs/LANGUAGE_META_GENOME_V0.md` already exists, is committed, and is the repository's
  gene-family narrative. Creating a second prose copy would be the bureaucracy §0.1 forbids.
  `spec/language/language_genome_v0.schema.json` carries the machine-checkable part and records
  the divergences from the manual in its `$comment`.
- The historical `docs/` corpus is **not** atomized. §50 Phase B step 8: "Create a CURRENT claim
  ledger; do not atomize every historical sentence."

---

## 4. CONFORMANCE GAPS

Recorded here rather than papered over, per the task's standing instruction and §43 ("prefer
explicit negative/blocked states over optimistic prose").

1. **`spec/ADR/` is empty while `docs/DECISIONS.md` holds ADR-shaped content.** The manual's §3.1
   precedence names "accepted ADR / decision record" as authority rank 4. `docs/DECISIONS.md`
   entries dated 2026-09-05 predate the manual and were not written in the §39 packet form. They
   are treated as `HML_LEGACY_ARCHITECTURE` / `ENGINEERING_ADR` evidence, **not** as accepted ADRs
   under the current constitution. Type: `KNOWN_FACT`.
2. **Two documents named in §36.1 already exist outside `spec/`.**
   `docs/LANGUAGE_META_GENOME_V0.md` and `docs/LANGUAGE_FITNESS_MEMORY.md` are at `docs/`, not
   `spec/language/` and `spec/meta_game/`. They were not moved: the task forbids editing `docs/`,
   and §0.1 forbids duplicating them. The `spec/` files cite them by path. Type:
   `ENGINEERING_DECISION`.
3. **`docs/LANGUAGE_FITNESS_MEMORY.md` diverges from manual §33 in field names and coverage.**
   Enumerated in the `$comment` of `spec/meta_game/LANGUAGE_FITNESS_MEMORY_SCHEMA.json`. The manual
   wins (§3.1).
