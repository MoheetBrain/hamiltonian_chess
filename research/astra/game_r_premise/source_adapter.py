"""Train-only LeanDojo bridge. Source text is retained, never claimed to be a Lean AST.

The existing production index and sampler are reused. This research adapter narrows
admission to explicit source theorem headers and checks every candidate's import and
declaration-order availability. No Lean kernel replay is performed.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from arena.environments import premise_selection as ps
from .schema import BackendText, Candidate, CanonicalPremiseSelectionState, order_candidates

ADAPTER_VERSION = "astra-leandojo-source-v1"
DEFAULT_SOURCE = Path("/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4")
LEVEL = ps.LEVELS_BY_NAME["L3_same_module_freq_matched"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def split_state(text: str) -> tuple[str, str]:
    """Lossless single-goal boundary only; no speculative binder parsing."""
    matches = list(re.finditer(r"(?m)^⊢", text))
    if len(matches) != 1 or text.count("⊢") != 1:
        raise ValueError("requires exactly one unambiguous goal delimiter")
    pos = matches[0].start()
    context, goal = text[:pos], text[pos:]
    if not goal[1:].strip():
        raise ValueError("empty goal")
    return context, goal


def source_signature(code: str) -> str:
    """Extract an exact explicit theorem header, rejecting unsupported lexical forms.

    This is deliberately not a Lean parser. Comments, strings, syntax quotation,
    nested assignments, inferred theorem types and equation-style declarations
    are excluded. Keeping the entire prefix avoids the production 400-char cap.
    Ambient section variables/notation are not recoverable from corpus.jsonl.
    """
    stack: list[str] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    top_colon = False
    def validate(header: str) -> str:
        if stack or not top_colon or not re.search(r"\b(?:theorem|lemma)\s", header):
            raise ValueError("requires balanced explicit theorem/lemma type")
        # `let x := ...` can occur outside bracket delimiters in a theorem type.  The
        # small scanner intentionally rejects it rather than returning a prefix that
        # ends before the theorem's real type.
        if re.search(r"\b(?:let|where|mutual|private|protected|by)\b", header):
            raise ValueError("unsupported declaration visibility/syntax")
        return header

    i = 0
    while i < len(code):
        char = code[i]
        if code.startswith(("--", "/-"), i) or char in {'"', '`', '«', '»'}:
            raise ValueError("unsupported comment/string/quoted identifier in header")
        if code.startswith(":=", i):
            if stack:
                raise ValueError("nested assignment in header")
            return validate(code[:i])
        if char in "([{":
            stack.append(char)
        elif char in ")]}":
            if not stack or stack.pop() != pairs[char]:
                raise ValueError("unbalanced header delimiters")
        elif char == ":" and not stack:
            top_colon = True
        i += 1
    # LeanDojo corpus already strips the proof body from most theorem entries.
    # A bodyless explicit theorem declaration is its complete recorded header.
    return validate(code)


def validate_source_pin(source: Path) -> dict[str, str]:
    """Verify the local dataset identity before any train/corpus read."""
    metadata = source / "metadata.json"
    try:
        record = json.loads(metadata.read_text(encoding="utf-8"))
        commit = record["from_repo"]["commit"]
        version = record["leandojo_version"]
        name = record["dataset_name"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid LeanDojo metadata: {metadata}") from error
    if commit != ps.DATASET_COMMIT or version != "2.0.0" or name != "LeanDojo Benchmark 4":
        raise ValueError(
            f"source pin mismatch: dataset={name!r} version={version!r} commit={commit!r}"
        )
    return {"dataset_name": name, "leandojo_version": version, "mathlib_commit": commit}


@dataclass(frozen=True)
class SourceDecl:
    name: str
    path: str
    signature: str
    source_start: tuple[int, int]
    source_end: tuple[int, int]
    order: int


def load_source_headers(corpus_path: Path) -> tuple[dict[str, SourceDecl], dict[str, int]]:
    """Read only the library corpus (no traced validation/test data)."""
    headers: dict[str, SourceDecl] = {}
    seen: set[str] = set()
    stats: Counter[str] = Counter()
    order = 0
    with ps.guard_source_path(corpus_path).open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            for premise in record.get("premises", []):
                name = premise.get("full_name")
                if not name or name in seen:
                    continue
                seen.add(name)
                current_order = order
                order += 1
                stats["declarations_seen"] += 1
                try:
                    signature = source_signature(premise.get("code", ""))
                    start, end = tuple(premise["start"]), tuple(premise["end"])
                    if len(start) != 2 or len(end) != 2:
                        raise ValueError("missing positions")
                except (ValueError, KeyError) as error:
                    stats[f"excluded:{error}"] += 1
                    continue
                headers[name] = SourceDecl(name, record["path"], signature, start, end, current_order)
                stats["explicit_source_headers"] += 1
    return headers, dict(stats)


def candidate_available(index: ps.PremiseIndex, transition: ps.Transition, name: str) -> bool:
    """Import-closure plus conservative same-file declaration-order check.

    Scope is source-level availability, not a claim of elaboration or applicability.
    The target theorem itself and every later declaration in its file are rejected.
    """
    declaration = index.decls.get(name)
    target = index.decls.get(transition.thm)
    if declaration is None or name == transition.thm:
        return False
    if not index.in_scope(transition.file_path, declaration.path):
        return False
    if declaration.path == transition.file_path:
        return target is not None and target.path == transition.file_path and declaration.order < target.order
    return True


class ScopeCheckedGenerator(ps.PremiseSelectionGenerator):
    """Production L3 sampler with symmetric signature and availability filters."""

    def __init__(self, index: ps.PremiseIndex, headers: dict[str, SourceDecl], seed: int):
        super().__init__(index, ps.GeneratorConfig(seed=seed))
        self.headers = headers

    def accepts(self, transition: ps.Transition, name: str) -> bool:
        return name in self.headers and candidate_available(self.index, transition, name)

    def _tier_candidates(self, tier, transition, gold, banned, goal_tokens, rng):
        return [name for name in super()._tier_candidates(tier, transition, gold, banned, goal_tokens, rng)
                if self.accepts(transition, name)]

    def generate(self, transition: ps.Transition, level: ps.Level = LEVEL):
        if level.explicit_positive:
            raise ValueError("L0 explicit-positive hints are forbidden in this bridge")
        if len(transition.premises) != 1 or not self.accepts(transition, transition.premises[0].full_name):
            return None
        return super().generate(transition, level)


def adapt_item(theorem: dict, step: ps.RawStep, generated: ps.PremiseItem,
               index: ps.PremiseIndex, headers: dict[str, SourceDecl], seed: int,
               proof_counts: Counter[str]) -> CanonicalPremiseSelectionState:
    context, goal = split_state(step.state_before)
    task_id = hashlib.sha256(f"{ADAPTER_VERSION}|{seed}|{step.proof_id}|{step.step_index}".encode()).hexdigest()[:24]
    candidates = []
    private_candidates = {}
    for option in generated.options:
        decl = headers[option.full_name]
        premise_id = "premise_" + hashlib.sha256(f"{ps.DATASET_COMMIT}|{decl.path}|{decl.name}".encode()).hexdigest()[:24]
        candidates.append(Candidate(
            premise_id=premise_id, name=decl.name,
            statement=BackendText(text=decl.signature, role="premise-signature", backend="lean4-source",
                                  assurance="source-header-not-elaborated"),
            provenance={"source_path": decl.path, "declaration_order": decl.order,
                        "source_start": list(decl.source_start), "source_end": list(decl.source_end),
                        "statement_sha256": hashlib.sha256(decl.signature.encode()).hexdigest()},
        ))
        private_candidates[premise_id] = {
            "citation_frequency": index.freq(decl.name), "same_proof_count": proof_counts[decl.name],
            "tier": option.tier,
        }
    target_name = step.premises[0].full_name
    target_id = next(candidate.premise_id for candidate in candidates if candidate.name == target_name)
    candidates = order_candidates(task_id, tuple(candidates), seed)
    return CanonicalPremiseSelectionState(
        task_id=task_id,
        provenance={"source_repo": "https://github.com/leanprover-community/mathlib4",
                    "source_version": "LeanDojo Benchmark 4 / leandojo 2.0.0",
                    "source_commit": ps.DATASET_COMMIT, "source_relpath": ps.PERMITTED_TRACE_RELPATH,
                    "theorem_id": step.proof_id, "proof_id": step.proof_id,
                    "theorem_name": theorem["full_name"], "file_path": theorem["file_path"],
                    "trace_step": step.step_index},
        formal_system="Lean4",
        context=BackendText(text=context, role="local-context"),
        goal=BackendText(text=goal, role="goal"),
        candidate_premises=tuple(candidates), target_choice_id=target_id,
        oracle_evidence={"kind": "dataset-recorded-single-premise-citation",
                         "cited_premise": target_name, "cited_definition_path": step.premises[0].def_path,
                         "tactic_sha256": hashlib.sha256(step.tactic.encode()).hexdigest(),
                         "annotation_sha256": hashlib.sha256(step.annotated_tactic.encode()).hexdigest(),
                         "state_after_sha256": hashlib.sha256(step.state_after.encode()).hexdigest(),
                         "kernel_replay": False,
                         "claim": "recorded next-step citation, not unique applicable/useful premise"},
        source_raw_state=step.state_before,
        audit_metadata={"candidate_metadata": private_candidates, "sampler_level": LEVEL.name,
                        "adapter_version": ADAPTER_VERSION, "seed": seed,
                        "scope_assurance": "import-closure-and-source-declaration-order; not elaborated",
                        "signature_assurance": "exact explicit source header; ambient section context unavailable"},
    )
