"""Formal structural probe bank v1: Game-R probes built from real Lean 4 proof states.

Motivation.  Fitness V3 and V4 measured synthetic states produced by Arena's own generators.
That invites a fair objection: an artificial generator may create structure no real
mathematics contains, so a representation effect measured on it need not transfer.  This
module replaces the generator with *real elaborated Lean 4 goal states* captured from
mathlib and Batteries, and asks a structural reading question whose answer this module
recomputes independently by walking the transcribed tree.

What is and is not claimed.

* The **states** are Tier A: they were produced by Lean's own elaborator, not by a model and
  not by a template.
* The **structural answer** is Tier B: Arena recomputes it from the transcribed record.
* Nothing here claims the underlying tactic step was replayed or that the theorem is true.
  The source corpus records elaboration-time capture, not re-execution, and its own
  attestation gate did not pass.  A depth question does not need that guarantee.

Sealed-holdout discipline.  The donor corpus reserves 126 mathlib source files (232
transitions) as a read-once holdout.  This module reads only the *source file names* of that
shard in order to exclude them, and never their states or answers.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arena.canonical.schema import (
    CanonicalExpression,
    CanonicalState,
    MathObject,
    canonical_json,
    stable_hash,
)
from arena.provenance import SourceProvenance, TrustTier

ENVIRONMENT_VERSION = "arena-formal-structural-v1.0.0"
ADAPTER_VERSION = "arena-lean-transcriber-v1.0.0"

DONOR_REPO = "MoheetBrain/HML_V3"
DONOR_REF = "codex/open-ended-search-v2"
DONOR_SHA = "95e8a26f6519f226a149f4d7507d47f90bea9932"
DONOR_ROOT = Path("/Users/moheet/Documents/ChatGPT/HML_V3")
CORPUS_GLOB = "data/corpus/lean_runtime_v2_full.canonical.part-*.jsonl.gz"
SEALED_GLOB = "data/corpus/sealed_final_v2.part-*.jsonl.gz"
DONOR_LICENSE = "private research repository; internal reuse only, not redistributed"
EXTRACTION_PATH = "Lean 4 v4.10.0-rc1 elaborator via HML_V3 LeanRuntimeExtractV2"
DONOR_CAVEATS = (
    "elaboration-time capture, not tactic replay; the donor attestation gate reports passed=false",
    "reference_completeness is PARTIAL_TACTICS_WITHOUT_TERMINFO_MAY_HIDE_INTERNAL_USE, so premise counts are lower bounds",
    "sealed_final_v2 source files are excluded by name and never read",
)

#: Lean AST node kinds and the ordered child keys that carry their subexpressions.
_CHILD_KEYS: dict[str, tuple[str, ...]] = {
    "application": ("function", "argument"),
    "lambda": ("binder_type", "body"),
    "dependent_function": ("binder_type", "body"),
    "annotated": ("expression",),
    "local_reference": (),
    "metavariable_reference": (),
    "bound_variable": (),
    "symbol": (),
    "literal": (),
    "sort": (),
}


@dataclass(frozen=True, slots=True)
class StructuralFeatures:
    """Structural facts recomputed from the transcribed tree, never copied from the source."""

    max_depth: int
    node_count: int
    distinct_identifiers: int
    max_recurrence: int
    deepest_identifier: str | None
    runner_up_identifier: str | None
    depth_lead: int
    local_context_entries: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_depth": self.max_depth,
            "node_count": self.node_count,
            "distinct_identifiers": self.distinct_identifiers,
            "max_recurrence": self.max_recurrence,
            "deepest_identifier": self.deepest_identifier,
            "runner_up_identifier": self.runner_up_identifier,
            "depth_lead": self.depth_lead,
            "local_context_entries": self.local_context_entries,
        }


def transcribe(node: Any) -> CanonicalExpression:
    """Faithfully transcribe one Lean AST node into a canonical expression.

    The transcription is structural, not semantic: node kinds become ``op`` names prefixed
    with ``lean.`` so they cannot collide with Arena's own operator vocabulary, and no
    Arena verifier rule is triggered by them.  Ordering of children is preserved exactly,
    because every structural question asked here depends on it.
    """

    if not isinstance(node, dict):
        return CanonicalExpression("lean.opaque", sort="LeanTerm")
    kind = str(node.get("node", "unknown"))
    children = tuple(
        transcribe(node[key])
        for key in _CHILD_KEYS.get(kind, ())
        if isinstance(node.get(key), dict)
    )
    value: str | int | None = None
    if kind == "local_reference" or kind == "metavariable_reference":
        value = str(node.get("identity", ""))
    elif kind == "symbol":
        value = str(node.get("name", node.get("identity", "")))
    elif kind == "bound_variable":
        value = int(node.get("index", 0))
    elif kind == "literal":
        raw = node.get("value", node.get("literal"))
        value = str(raw) if raw is not None else None
    elif kind == "sort":
        value = canonical_json(node.get("level", {}))
    attributes: tuple[tuple[str, str], ...] = ()
    if kind in {"lambda", "dependent_function"}:
        attributes = (("binder_role", str(node.get("binder_role", ""))),)
    return CanonicalExpression(
        f"lean.{kind}", children, value=value, sort="LeanTerm", attributes=attributes
    )


def identifier_depths(expression: CanonicalExpression, depth: int = 0) -> dict[str, list[int]]:
    """Every occurrence depth of every local reference, by walking the transcribed tree."""

    found: dict[str, list[int]] = {}
    if expression.op == "lean.local_reference" and isinstance(expression.value, str):
        found.setdefault(expression.value, []).append(depth)
    for child in expression.args:
        for name, depths in identifier_depths(child, depth + 1).items():
            found.setdefault(name, []).extend(depths)
    return found


def _node_count(expression: CanonicalExpression) -> int:
    return 1 + sum(_node_count(child) for child in expression.args)


def _max_depth(expression: CanonicalExpression, depth: int = 0) -> int:
    if not expression.args:
        return depth
    return max(_max_depth(child, depth + 1) for child in expression.args)


def structural_features(
    expression: CanonicalExpression, local_context_entries: int
) -> StructuralFeatures:
    occurrences = identifier_depths(expression)
    maxima = {name: max(values) for name, values in occurrences.items()}
    ranked = sorted(maxima.items(), key=lambda item: (-item[1], item[0]))
    deepest = ranked[0][0] if ranked else None
    runner_up = ranked[1][0] if len(ranked) > 1 else None
    lead = (ranked[0][1] - ranked[1][1]) if len(ranked) > 1 else 0
    return StructuralFeatures(
        max_depth=_max_depth(expression),
        node_count=_node_count(expression),
        distinct_identifiers=len(occurrences),
        max_recurrence=max((len(values) for values in occurrences.values()), default=0),
        deepest_identifier=deepest,
        runner_up_identifier=runner_up,
        depth_lead=lead,
        local_context_entries=local_context_entries,
    )


def relabel(expression: CanonicalExpression, left: str, right: str) -> CanonicalExpression:
    """Swap two local-reference identities everywhere.

    This is the counterfactual operator.  It preserves the tree shape and the token
    multiset exactly and inverts the answer, so a model that reads structure must flip its
    choice while a model that reads surface statistics cannot.
    """

    value = expression.value
    if expression.op == "lean.local_reference" and isinstance(value, str):
        if value == left:
            value = right
        elif value == right:
            value = left
    return CanonicalExpression(
        expression.op,
        tuple(relabel(child, left, right) for child in expression.args),
        value=value,
        sort=expression.sort,
        attributes=expression.attributes,
    )


def destroy_depth_relation(left: str, right: str) -> CanonicalExpression:
    """Relation-destroyed control: both identifiers present, at identical depth.

    Content is preserved (both identities still occur) but the differential-depth relation
    the question asks about is gone, so the question has no structural answer and a reader
    that was genuinely reading depth must fall to chance.
    """

    return CanonicalExpression(
        "lean.application",
        (
            CanonicalExpression("lean.local_reference", value=left, sort="LeanTerm"),
            CanonicalExpression("lean.local_reference", value=right, sort="LeanTerm"),
        ),
        sort="LeanTerm",
    )


@dataclass(frozen=True, slots=True)
class FormalState:
    """One transcribed Lean goal state with its recomputed structural facts."""

    item_id: str
    source_file: str
    theorem_id: str
    target: CanonicalExpression
    context_identities: tuple[str, ...]
    features: StructuralFeatures
    provenance: SourceProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "source_file": self.source_file,
            "theorem_id": self.theorem_id,
            "features": self.features.to_dict(),
            "context_identities": list(self.context_identities),
            "provenance": self.provenance.to_dict(),
        }


def sealed_source_files(root: Path = DONOR_ROOT) -> frozenset[str]:
    """Source-file names of the donor's read-once holdout, so they can be excluded.

    Only ``corpus_metadata.source_file`` is read.  No state, target, option or answer from
    the sealed shard is ever loaded.
    """

    names: set[str] = set()
    for path in sorted(root.glob(SEALED_GLOB)):
        with gzip.open(path, "rt") as handle:
            for line in handle:
                record = json.loads(line)
                names.add(str(record.get("corpus_metadata", {}).get("source_file", "")))
    return frozenset(names - {""})


def iter_corpus(root: Path = DONOR_ROOT) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in sorted(root.glob(CORPUS_GLOB)):
        with gzip.open(path, "rt") as handle:
            for line in handle:
                yield path, json.loads(line)


def load_formal_states(
    *,
    root: Path = DONOR_ROOT,
    min_lead: int = 1,
    min_depth: int = 4,
    min_recurrence: int = 2,
    limit: int | None = None,
) -> tuple[FormalState, ...]:
    """Transcribe eligible states and recompute their structure independently.

    Eligibility is purely structural and is applied before any model sees anything:
    the goal target must have a *unique* deepest local reference leading the runner-up by
    ``min_lead`` (the V1 lesson `FM-047`: a tie makes the question ill-posed), and must be
    deep and repetitive enough to be a real structural reading task.
    """

    excluded = sealed_source_files(root)
    states: list[FormalState] = []
    for path, record in iter_corpus(root):
        metadata = record.get("corpus_metadata", {})
        source_file = str(metadata.get("source_file", ""))
        if source_file in excluded:
            continue
        goals = record.get("state_before", {}).get("goals", [])
        if len(goals) != 1:
            continue
        goal = goals[0]
        target = transcribe(goal.get("target"))
        context = tuple(
            str(entry.get("identity", "")) for entry in goal.get("local_context", []) if entry
        )
        features = structural_features(target, len(context))
        if features.deepest_identifier is None or features.runner_up_identifier is None:
            continue
        if features.depth_lead < min_lead:
            continue
        if features.max_depth < min_depth or features.max_recurrence < min_recurrence:
            continue
        record_sha = hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()
        item_id = f"fs:{stable_hash({'t': record['transition_id']})[:16]}"
        provenance = SourceProvenance(
            source_repo=DONOR_REPO,
            source_ref=DONOR_REF,
            source_sha=DONOR_SHA,
            source_path=str(path.relative_to(root)),
            source_item_id=str(record["transition_id"]),
            source_record_sha256=record_sha,
            license=DONOR_LICENSE,
            trust_tier=TrustTier.A_NATIVE_VERIFIED,
            extraction_path=EXTRACTION_PATH,
            verifier="arena structural re-derivation (identifier_depths)",
            adapter_version=ADAPTER_VERSION,
            canonicalization_sha256=stable_hash(target.to_dict()),
            caveats=DONOR_CAVEATS,
        )
        states.append(
            FormalState(
                item_id=item_id,
                source_file=source_file,
                theorem_id=str(record.get("source_specific_reference", {}).get("theorem_id", "")),
                target=target,
                context_identities=context,
                features=features,
                provenance=provenance,
            )
        )
        if limit is not None and len(states) >= limit:
            break
    return tuple(states)


def build_state(
    target: CanonicalExpression, identifiers: Sequence[str], goal_op: str
) -> CanonicalState:
    """Wrap a transcribed target in a minimal, verifier-clean canonical state."""

    objects = tuple(
        MathObject(
            f"object:id:{name}",
            "LeanLocal",
            CanonicalExpression("symbol", value=name, sort="Identifier"),
        )
        for name in sorted(set(identifiers))
    )
    return CanonicalState(
        state_id="state:formal-structural:neutral",
        objects=objects,
        bindings=(),
        assumptions=(),
        established_facts=(),
        propositions=(),
        goal=CanonicalExpression(goal_op, (target,), sort="Proposition"),
        obligations=(),
        evidence_dependencies=(),
        local_scope=("scope:root",),
        legal_actions=(),
        plausible_invalid_actions=(),
        terminal_status="OPEN",
        execution_metadata=(),
    )


def stratify(states: Sequence[FormalState], buckets: int = 3) -> dict[str, list[FormalState]]:
    """Split by target depth into difficulty strata, using empirical quantiles."""

    ordered = sorted(states, key=lambda item: (item.features.max_depth, item.item_id))
    if not ordered:
        return {}
    size = max(1, len(ordered) // buckets)
    names = ["shallow", "medium", "deep"][:buckets]
    out: dict[str, list[FormalState]] = {name: [] for name in names}
    for index, state in enumerate(ordered):
        out[names[min(index // size, buckets - 1)]].append(state)
    return out


__all__ = [
    "ADAPTER_VERSION",
    "ENVIRONMENT_VERSION",
    "FormalState",
    "StructuralFeatures",
    "build_state",
    "destroy_depth_relation",
    "identifier_depths",
    "load_formal_states",
    "relabel",
    "sealed_source_files",
    "stratify",
    "structural_features",
    "transcribe",
]
