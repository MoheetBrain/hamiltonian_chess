"""Read-only paths for the reasoning-operation discovery study.

Every path below is OUTSIDE this worktree and is opened READ-ONLY.
No path here is written to. No model, network, or Lean call is made by any
script in research/operations/.
"""

from __future__ import annotations

from pathlib import Path

CORPUS = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus")
ATTEST = Path("/Users/moheet/Documents/ChatGPT/hmlt-reasoning-corpus-lean-attestation")
HMLV3 = Path("/Users/moheet/Documents/ChatGPT/HML_V3")
RESEARCH_ART = Path("/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts")
PRM800K = Path("/Users/moheet/Documents/ChatGPT/prm800k/prm800k")

# --- taxonomies -------------------------------------------------------------
SCHEMAS = CORPUS / "schemas"
ONTOLOGY_V1 = SCHEMAS / "reasoning_ontology_v1.yaml"
REG_G125 = SCHEMAS / "reasoning_operation_registry_gold125_v1.json"
REG_G25 = SCHEMAS / "reasoning_operation_registry_gold25_v0.json"
STAGES = SCHEMAS / "reasoning_stages.json"
GAPS = SCHEMAS / "gold125_gap_registry_v1.json"

# --- human-annotated informal (MATH) ---------------------------------------
GOLD125_ONTOLOGY = CORPUS / "data" / "derived" / "gold125_ontology_v1"
GOLD10 = CORPUS / "data" / "gold_10"

# --- synthetic informal -----------------------------------------------------
SYNTH_TRANSITIONS = RESEARCH_ART / "synthetic_math" / "transitions.jsonl"

# --- formal -----------------------------------------------------------------
LEANDOJO = RESEARCH_ART / "leandojo_raw" / "leandojo_benchmark_4"
LEAN_241K = RESEARCH_ART / "lean_domino_v2" / "lean_canonical_records.jsonl"
HMLV3_CORPUS = HMLV3 / "data" / "corpus"
MICROMATH = HMLV3 / "data" / "micromath_lab_v2"

# --- informal model-generated ----------------------------------------------
PRM_DEEP_SAMPLE = (
    ATTEST / "experiments" / "prm800k_audit" / "samples" / "deep_sample.jsonl"
)
PRM_PHASE1_TRAIN = PRM800K / "data" / "phase1_train.jsonl"
PRM_PHASE2_TEST = PRM800K / "data" / "phase2_test.jsonl"

# --- output -----------------------------------------------------------------
WORKTREE = Path(
    "/Users/moheet/Documents/ChatGPT/hamiltonian_chess/"
    ".claude/worktrees/phase-6-parallel-setup-9c6068"
)
OUT_JSON = WORKTREE / "artifacts" / "corpus" / "operation_inventory.json"
DOC_MD = WORKTREE / "docs" / "REASONING_OPERATION_DISCOVERY.md"

# intermediate measurement dumps live in the session scratchpad, never in the repo
SCRATCH = Path(
    "/private/tmp/claude-501/-Users-moheet-Documents-ChatGPT-hamiltonian-chess-"
    "-claude-worktrees-phase-6-parallel-setup-9c6068/"
    "c625765c-0962-49c6-b99b-560f570581b8/scratchpad"
)
