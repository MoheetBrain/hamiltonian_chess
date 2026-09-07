"""Throwaway pressure test: map real Lean 4 proof states into arena-canonical-v0.1.0.

ANALYSIS ONLY.  Nothing under ``arena/`` is modified; the canonical schema, the strict wire
validator and the native verifier are imported read-only and used exactly as production uses
them.  No model call is made.  No file outside this worktree is written.

Question asked
--------------
For each real proof state, can the CURRENT canonical schema hold it?  Three verdicts:

* ``LOSSLESS``            every information item in the source state has a first-class,
                          structurally typed slot in ``CanonicalState``.
* ``LOSSY_STRUCTURAL``    a state can be built and passes the wire validator + native
                          verifier, but some source information survives only as an opaque
                          string (``CanonicalExpression.value`` / ``attributes``) or is
                          dropped entirely.
* ``UNMAPPABLE``          a hard cardinality/typing constraint of the schema is violated, so
                          no faithful state exists at any encoding (e.g. zero goals against a
                          mandatory ``goal`` field, or two goals with colliding local
                          contexts against a single state-global binding table).

We deliberately do NOT change the schema to make anything pass.

Sample provenance
-----------------
Source   : HML_V3 ``data/corpus/lean_runtime_v2_full.canonical.part-{000..004}.jsonl.gz``
           (Lean 4.10.0-rc1 elaborator capture, ``canonical-math-transition-v2.0.0``),
           the same corpus ``arena/environments/formal_structural.py`` already consumes.
Universe : 1150 transition records across 5 parts.
Selection: deterministic stride.  Records are read in part order (000..004), records whose
           ``corpus_metadata.source_file`` belongs to the donor's read-once sealed shard are
           skipped (only sealed *file names* are read, never sealed states), and every
           ``STRIDE``-th surviving record is kept until ``TARGET_RECORDS`` are collected.
Unit     : one *proof state*.  Each record contributes ``state_before`` and ``state_after``.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from arena.canonical.schema import (
    SCHEMA_VERSION,
    Binding,
    CanonicalExpression,
    CanonicalState,
    MathObject,
    Obligation,
    canonical_json,
    stable_hash,
)
from arena.languages._wire import WireValidationError, state_to_payload
from arena.verifier.native import NativeVerifier

DONOR_ROOT = Path("/Users/moheet/Documents/ChatGPT/HML_V3")
CORPUS_GLOB = "data/corpus/lean_runtime_v2_full.canonical.part-*.jsonl.gz"
SEALED_GLOB = "data/corpus/sealed_final_v2.part-*.jsonl.gz"
STRIDE = 5
TARGET_RECORDS = 200

# ---------------------------------------------------------------------------------------
# loss classes -> claimed gap ids
# ---------------------------------------------------------------------------------------
LOSS_CLASS_GAP = {
    "MULTI_GOAL_SINGLE_SLOT": "G1",
    "ZERO_GOAL_MANDATORY_SLOT": "G1",
    "PER_GOAL_LOCAL_CONTEXT_COLLISION": "G1",
    "GOAL_IDENTITY_DROPPED": "G1",
    "FOCUS_ORDER_DROPPED": "N1",
    "METAVARIABLE_CONTEXT_DROPPED": "G2",
    "METAVARIABLE_ASSIGNMENT_DROPPED": "G2",
    "DEPENDENT_TYPE_FLATTENED": "G3",
    "LET_VALUE_DROPPED": "N2",
    "UNIVERSE_LEVEL_NONTRIVIAL": "G4",
    "UNIVERSE_ARGUMENTS_ON_SYMBOL": "G4",
    "UNIVERSE_ASSIGNMENTS_DROPPED": "G4",
    "NONEXPLICIT_BINDER_KIND": "G5",
    "LOCAL_INSTANCES_DROPPED": "G5",
    "MVAR_SUBSTITUTION_MAP_DROPPED": "G6",
    "DISTINCT_VARIABLE_CONDITION": "G7",
    "DEFEQ_STEP_TYPE": "G8",
    "PREMISE_REFS_UNPLACEABLE": "N3",
    "DECLARATION_ROLE_DROPPED": "N2",
}

# Lean AST node kinds and the ordered child keys carrying subexpressions.  Same table as
# arena/environments/formal_structural.py:61, extended with the keys that table omits so we
# can see everything the production transcriber silently drops.
CHILD_KEYS: dict[str, tuple[str, ...]] = {
    "application": ("function", "argument"),
    "lambda": ("binder_type", "body"),
    "dependent_function": ("binder_type", "body"),
    "let": ("type", "value", "body"),
    "annotated": ("expression",),
    "projection": ("structure",),
    "local_reference": (),
    "metavariable_reference": (),
    "bound_variable": (),
    "symbol": (),
    "literal": (),
    "sort": (),
}


# ---------------------------------------------------------------------------------------
# sampling
# ---------------------------------------------------------------------------------------
def sealed_source_files() -> frozenset[str]:
    names: set[str] = set()
    for path in sorted(DONOR_ROOT.glob(SEALED_GLOB)):
        with gzip.open(path, "rt") as handle:
            for line in handle:
                record = json.loads(line)
                names.add(str(record.get("corpus_metadata", {}).get("source_file", "")))
    return frozenset(names - {""})


def sample_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sealed = sealed_source_files()
    kept: list[dict[str, Any]] = []
    seen = 0
    eligible = 0
    skipped_sealed = 0
    parts = sorted(DONOR_ROOT.glob(CORPUS_GLOB))
    for path in parts:
        with gzip.open(path, "rt") as handle:
            for line in handle:
                record = json.loads(line)
                seen += 1
                source_file = str(record.get("corpus_metadata", {}).get("source_file", ""))
                if source_file in sealed:
                    skipped_sealed += 1
                    continue
                if eligible % STRIDE == 0 and len(kept) < TARGET_RECORDS:
                    record["__part"] = path.name
                    kept.append(record)
                eligible += 1
    provenance = {
        "donor_root": str(DONOR_ROOT),
        "corpus_glob": CORPUS_GLOB,
        "parts": [p.name for p in parts],
        "records_in_universe": seen,
        "records_skipped_sealed_source_file": skipped_sealed,
        "records_eligible": eligible,
        "selection_rule": f"every {STRIDE}th eligible record in part order, capped at {TARGET_RECORDS}",
        "records_sampled": len(kept),
        "sealed_shard_treatment": "only corpus_metadata.source_file read from sealed shard; no sealed state loaded",
        "unit_of_analysis": "one proof state (state_before and state_after per record)",
        "source_schema_version": kept[0].get("schema_version") if kept else None,
    }
    return kept, provenance


# ---------------------------------------------------------------------------------------
# transcription (faithful, extended beyond the production transcriber)
# ---------------------------------------------------------------------------------------
def is_trivial_level(level: Any) -> bool:
    return isinstance(level, dict) and level.get("constructor") == "zero" and len(level) == 1


def level_constructors(level: Any, out: set[str]) -> None:
    if isinstance(level, dict):
        if "constructor" in level:
            out.add(str(level["constructor"]))
        for value in level.values():
            level_constructors(value, out)
    elif isinstance(level, list):
        for item in level:
            level_constructors(item, out)


def transcribe(node: Any) -> CanonicalExpression:
    """Best-effort faithful transcription, string-encoding anything without a typed slot."""

    if not isinstance(node, dict):
        return CanonicalExpression("lean.opaque", sort="LeanTerm")
    kind = str(node.get("node", "unknown"))
    children = tuple(
        transcribe(node[key])
        for key in CHILD_KEYS.get(kind, ())
        if isinstance(node.get(key), dict)
    )
    value: str | int | None = None
    attributes: list[tuple[str, str]] = []
    if kind in {"local_reference", "metavariable_reference"}:
        value = str(node.get("identity", ""))
    elif kind == "symbol":
        value = str(node.get("name", node.get("identity", "")))
        if node.get("universe_arguments"):
            # no typed slot: survives only as an opaque JSON string
            attributes.append(("universe_arguments", canonical_json(node["universe_arguments"])))
    elif kind == "bound_variable":
        value = int(node.get("index", 0))
    elif kind == "literal":
        raw = node.get("value", node.get("literal"))
        value = str(raw) if raw is not None else None
    elif kind == "sort":
        # no typed slot for a universe level: flattened to a JSON string
        value = canonical_json(node.get("level", {}))
    if kind in {"lambda", "dependent_function", "let"}:
        attributes.append(("binder_role", str(node.get("binder_role", ""))))
        attributes.append(("binder_name", str(node.get("binder_name", ""))))
    return CanonicalExpression(
        f"lean.{kind}", children, value=value, sort="LeanTerm",
        attributes=tuple(sorted(attributes)),
    )


def walk_source(node: Any, visit) -> None:
    if isinstance(node, dict):
        visit(node)
        for value in node.values():
            walk_source(value, visit)
    elif isinstance(node, list):
        for item in node:
            walk_source(item, visit)


def type_expression(entry: dict[str, Any]) -> Any:
    """The type tree of a local-context entry (records nest it under `type`)."""

    raw = entry.get("type")
    if isinstance(raw, dict) and "expression" in raw and isinstance(raw["expression"], dict):
        return raw["expression"]
    return raw


def is_leaf_type(node: Any) -> bool:
    """True iff the type is a bare name that a plain `type_name: str` could hold."""

    if not isinstance(node, dict):
        return False
    kind = node.get("node")
    if kind == "symbol":
        return not node.get("universe_arguments")
    if kind in {"local_reference", "bound_variable", "literal"}:
        return True
    if kind == "sort":
        return is_trivial_level(node.get("level", {}))
    return False


# ---------------------------------------------------------------------------------------
# analysis of one proof state
# ---------------------------------------------------------------------------------------
def analyse_state(record: dict[str, Any], which: str) -> dict[str, Any]:
    state = record.get(which, {}) or {}
    goals = state.get("goals", []) or []
    mvars = state.get("metavariables", []) or []
    focus_order = state.get("focus_order", []) or []
    universe_assignments = state.get("universe_assignments", []) or []
    action = record.get("action", {}) or {}

    losses: set[str] = set()
    constructs: set[str] = set()
    binder_structures: set[str] = set()
    notes: dict[str, Any] = {}

    # -- goals ---------------------------------------------------------------------------
    if len(goals) == 0:
        losses.add("ZERO_GOAL_MANDATORY_SLOT")
    if len(goals) > 1:
        losses.add("MULTI_GOAL_SINGLE_SLOT")
        losses.add("FOCUS_ORDER_DROPPED")
        # do the goals' local contexts actually conflict under one state-global table?
        by_identity: dict[str, set[str]] = {}
        per_goal_ids: list[set[str]] = []
        for goal in goals:
            ids: set[str] = set()
            for entry in goal.get("local_context", []) or []:
                identity = str(entry.get("identity", ""))
                ids.add(identity)
                by_identity.setdefault(identity, set()).add(
                    stable_hash(type_expression(entry) or {})
                )
            per_goal_ids.append(ids)
        collision = any(len(v) > 1 for v in by_identity.values())
        disjoint = any(a != b for a in per_goal_ids for b in per_goal_ids)
        if collision or disjoint:
            losses.add("PER_GOAL_LOCAL_CONTEXT_COLLISION")
            notes["context_collision_same_id_diff_type"] = collision
            notes["context_sets_differ_between_goals"] = disjoint
    for goal in goals:
        if goal.get("identity"):
            losses.add("GOAL_IDENTITY_DROPPED")
        if goal.get("local_instances"):
            losses.add("LOCAL_INSTANCES_DROPPED")

    # -- local contexts ------------------------------------------------------------------
    context_entries = 0
    compound_types = 0
    for goal in goals:
        for entry in goal.get("local_context", []) or []:
            context_entries += 1
            role = str(entry.get("binder_role", ""))
            constructs.add(f"binder_role:{role}")
            if role and role != "EXPLICIT":
                losses.add("NONEXPLICIT_BINDER_KIND")
            declaration_role = str(entry.get("declaration_role", ""))
            constructs.add(f"declaration_role:{declaration_role}")
            if declaration_role and declaration_role != "cdecl":
                losses.add("DECLARATION_ROLE_DROPPED")
            if entry.get("value") is not None or declaration_role == "ldecl":
                losses.add("LET_VALUE_DROPPED")
            type_node = type_expression(entry)
            if not is_leaf_type(type_node):
                compound_types += 1
                losses.add("DEPENDENT_TYPE_FLATTENED")
    notes["local_context_entries"] = context_entries
    notes["local_context_entries_with_compound_type"] = compound_types

    # -- metavariables -------------------------------------------------------------------
    goal_ids = {str(g.get("identity", "")) for g in goals}
    assigned = 0
    non_goal_mvars = 0
    for mvar in mvars:
        constructs.add(f"mvar_kind:{mvar.get('kind')}")
        if str(mvar.get("identity", "")) not in goal_ids:
            non_goal_mvars += 1
        if mvar.get("assigned") or mvar.get("assignment") is not None:
            assigned += 1
    if mvars:
        losses.add("METAVARIABLE_CONTEXT_DROPPED")
    if assigned:
        losses.add("METAVARIABLE_ASSIGNMENT_DROPPED")
        losses.add("MVAR_SUBSTITUTION_MAP_DROPPED")
    notes["metavariables"] = len(mvars)
    notes["metavariables_assigned"] = assigned
    notes["metavariables_not_goals"] = non_goal_mvars

    # a substitution map also appears at the transition level
    if which == "state_before" and (record.get("state_delta", {}) or {}).get(
        "metavariables_assigned"
    ):
        losses.add("MVAR_SUBSTITUTION_MAP_DROPPED")

    if universe_assignments:
        losses.add("UNIVERSE_ASSIGNMENTS_DROPPED")

    # -- expression-level scan -----------------------------------------------------------
    nontrivial_levels = 0
    universe_arg_symbols = 0
    level_ctors: set[str] = set()

    def visit(node: dict[str, Any]) -> None:
        nonlocal nontrivial_levels, universe_arg_symbols
        kind = node.get("node")
        if kind is None:
            return
        constructs.add(f"node:{kind}")
        for key in node:
            constructs.add(f"field:{kind}.{key}")
        if kind in {"lambda", "dependent_function", "let"}:
            binder_type = node.get("binder_type") or node.get("type") or {}
            signature = (
                f"{kind}|{node.get('binder_role', '')}|"
                f"{binder_type.get('node') if isinstance(binder_type, dict) else 'none'}"
            )
            binder_structures.add(signature)
            role = str(node.get("binder_role", ""))
            if role and role != "EXPLICIT":
                losses.add("NONEXPLICIT_BINDER_KIND")
        if kind == "sort":
            level = node.get("level", {})
            level_constructors(level, level_ctors)
            if not is_trivial_level(level):
                nontrivial_levels += 1
                losses.add("UNIVERSE_LEVEL_NONTRIVIAL")
        if kind == "symbol" and node.get("universe_arguments"):
            universe_arg_symbols += 1
            level_constructors(node["universe_arguments"], level_ctors)
            losses.add("UNIVERSE_ARGUMENTS_ON_SYMBOL")

    walk_source(goals, visit)
    walk_source(mvars, visit)
    for ctor in level_ctors:
        constructs.add(f"level:{ctor}")
    notes["sort_nodes_with_nontrivial_level"] = nontrivial_levels
    notes["symbols_with_universe_arguments"] = universe_arg_symbols

    # -- distinct-variable conditions (G7) -----------------------------------------------
    blob = canonical_json(state)
    if "distinct_variable" in blob or "disjoint_variable" in blob or '"dv"' in blob:
        losses.add("DISTINCT_VARIABLE_CONDITION")

    # -- action premises (transition level, recorded once on state_before) ---------------
    if which == "state_before" and action.get("external_premise_refs"):
        losses.add("PREMISE_REFS_UNPLACEABLE")
        notes["external_premise_refs"] = len(action["external_premise_refs"])

    # -- attempt an actual CanonicalState -------------------------------------------------
    build: dict[str, Any] = {}
    verdict: str
    if len(goals) == 0:
        verdict = "UNMAPPABLE"
        build["reason"] = "CanonicalState.goal is mandatory; no expression exists to put there"
    else:
        try:
            canonical = build_state(goals, record, which)
            payload = state_to_payload(canonical)
            result = NativeVerifier().verify_state(canonical)
            build = {
                "wire_valid": True,
                "native_accepted": result.accepted,
                "native_issues": sorted({issue.code for issue in result.issues}),
                "mathematical_hash": canonical.mathematical_hash,
                "payload_bytes": len(canonical_json(payload)),
            }
            if not result.accepted:
                verdict = "UNMAPPABLE"
                build["reason"] = "native verifier rejects the faithful encoding"
            elif "PER_GOAL_LOCAL_CONTEXT_COLLISION" in losses:
                verdict = "UNMAPPABLE"
                build["reason"] = (
                    "goals carry different local contexts; one state-global binding table "
                    "cannot represent them without inventing scopes the source does not have"
                )
            elif losses:
                verdict = "LOSSY_STRUCTURAL"
            else:
                verdict = "LOSSLESS"
        except (WireValidationError, ValueError, TypeError) as error:
            verdict = "UNMAPPABLE"
            build = {"wire_valid": False, "reason": f"{type(error).__name__}: {error}"}

    return {
        "record_id": record.get("transition_id"),
        "part": record.get("__part"),
        "which": which,
        "source_file": record.get("corpus_metadata", {}).get("source_file"),
        "goal_count": len(goals),
        "verdict": verdict,
        "losses": sorted(losses),
        "constructs": sorted(constructs),
        "binder_structures": sorted(binder_structures),
        "notes": notes,
        "build": build,
        # byte-lossless smuggling: anything without a typed slot could still be stuffed into
        # attributes/value as a JSON string, EXCEPT hard cardinality violations.
        "byte_lossless_possible": verdict != "UNMAPPABLE",
    }


def build_state(goals: list[dict[str, Any]], record: dict[str, Any], which: str) -> CanonicalState:
    """Faithful best-effort encoding under the CURRENT schema.  No schema change."""

    first, rest = goals[0], goals[1:]
    bindings: list[Binding] = []
    scopes: list[str] = []
    objects: list[MathObject] = []
    seen_binders: set[str] = set()
    for index, goal in enumerate(goals):
        scope = f"scope:goal:{index}"
        scopes.append(scope)
        for entry in goal.get("local_context", []) or []:
            binder_id = f"binder:{index}:{entry.get('identity', '')}"
            if binder_id in seen_binders:
                continue
            seen_binders.add(binder_id)
            type_node = type_expression(entry)
            # `type_name` is a plain string: a compound dependent type can only be named,
            # so we name it by its content hash and lose the structure.
            if is_leaf_type(type_node):
                type_name = str(
                    type_node.get("name") or type_node.get("identity") or type_node.get("node")
                )
            else:
                type_name = f"lean.type#{stable_hash(type_node or {})[:16]}"
            bindings.append(
                Binding(
                    binder_id=binder_id,
                    variable=str(entry.get("identity", "")),
                    type_name=type_name,
                    scope_id=scope,
                    binder_kind="free",
                )
            )
    target_of = lambda goal: transcribe(  # noqa: E731
        (goal.get("target") or {}).get("expression", goal.get("target"))
    )
    obligations = tuple(
        Obligation(
            obligation_id=f"obligation:goal:{index + 1}",
            proposition=target_of(goal),
            status="OPEN",
            source="lean-import",
        )
        for index, goal in enumerate(rest)
    )
    return CanonicalState(
        state_id=f"state:pressure:{which}:{stable_hash(record.get('transition_id', ''))[:16]}",
        objects=tuple(objects),
        bindings=tuple(bindings),
        assumptions=(),
        established_facts=(),
        propositions=(),
        goal=target_of(first),
        obligations=obligations,
        evidence_dependencies=(),
        local_scope=tuple(scopes),
        legal_actions=(),
        plausible_invalid_actions=(),
        terminal_status="OPEN",
        schema_version=SCHEMA_VERSION,
        execution_metadata=(),
    )


# ---------------------------------------------------------------------------------------
def novelty_curve(rows: list[dict[str, Any]], key: str, block: int = 50) -> dict[str, Any]:
    seen: set[str] = set()
    blocks: list[dict[str, Any]] = []
    current_new = 0
    for index, row in enumerate(rows, start=1):
        for item in row[key]:
            if item not in seen:
                seen.add(item)
                current_new += 1
        if index % block == 0:
            blocks.append(
                {
                    "records": f"{index - block + 1}-{index}",
                    "new_in_block": current_new,
                    "per_100_records": round(current_new * 100 / block, 1),
                    "cumulative_distinct": len(seen),
                }
            )
            current_new = 0
    if current_new or len(rows) % block:
        blocks.append(
            {
                "records": f"{len(rows) - (len(rows) % block) + 1}-{len(rows)}",
                "new_in_block": current_new,
                "per_100_records": round(current_new * 100 / max(1, len(rows) % block), 1),
                "cumulative_distinct": len(seen),
            }
        )
    return {"blocks": blocks, "total_distinct": len(seen), "items": sorted(seen)}


def main() -> None:
    records, provenance = sample_records()
    per_record: list[dict[str, Any]] = []
    per_state: list[dict[str, Any]] = []
    for record in records:
        before = analyse_state(record, "state_before")
        after = analyse_state(record, "state_after")
        per_state.extend([before, after])
        per_record.append(
            {
                "record_id": record.get("transition_id"),
                "constructs": sorted(set(before["constructs"]) | set(after["constructs"])),
                "binder_structures": sorted(
                    set(before["binder_structures"]) | set(after["binder_structures"])
                ),
                "losses": sorted(set(before["losses"]) | set(after["losses"])),
                "verdicts": [before["verdict"], after["verdict"]],
            }
        )

    verdicts = Counter(row["verdict"] for row in per_state)
    loss_counts: Counter[str] = Counter()
    for row in per_state:
        loss_counts.update(row["losses"])
    record_loss_counts: Counter[str] = Counter()
    for row in per_record:
        record_loss_counts.update(row["losses"])

    out = {
        "provenance": provenance,
        "states_analysed": len(per_state),
        "verdicts_by_state": dict(verdicts),
        "verdicts_by_record": dict(
            Counter(
                "UNMAPPABLE"
                if "UNMAPPABLE" in row["verdicts"]
                else ("LOSSY_STRUCTURAL" if "LOSSY_STRUCTURAL" in row["verdicts"] else "LOSSLESS")
                for row in per_record
            )
        ),
        "loss_class_frequency_by_state": {
            name: {
                "gap": LOSS_CLASS_GAP.get(name, "?"),
                "states": count,
                "pct_of_states": round(count * 100 / len(per_state), 1),
            }
            for name, count in loss_counts.most_common()
        },
        "loss_class_frequency_by_record": {
            name: {
                "gap": LOSS_CLASS_GAP.get(name, "?"),
                "records": count,
                "pct_of_records": round(count * 100 / len(per_record), 1),
            }
            for name, count in record_loss_counts.most_common()
        },
        "never_observed_loss_classes": sorted(set(LOSS_CLASS_GAP) - set(loss_counts)),
        "goal_count_distribution": dict(
            sorted(Counter(row["goal_count"] for row in per_state).items())
        ),
        "novelty_semantic_constructs": novelty_curve(per_record, "constructs"),
        "novelty_binder_structures": novelty_curve(per_record, "binder_structures"),
        "native_verifier_issue_codes": dict(
            Counter(
                code for row in per_state for code in row.get("build", {}).get("native_issues", [])
            )
        ),
        "aggregate_notes": {
            "local_context_entries": sum(
                row["notes"].get("local_context_entries", 0) for row in per_state
            ),
            "local_context_entries_with_compound_type": sum(
                row["notes"].get("local_context_entries_with_compound_type", 0)
                for row in per_state
            ),
            "metavariables_total": sum(row["notes"].get("metavariables", 0) for row in per_state),
            "metavariables_assigned_total": sum(
                row["notes"].get("metavariables_assigned", 0) for row in per_state
            ),
            "sort_nodes_with_nontrivial_level": sum(
                row["notes"].get("sort_nodes_with_nontrivial_level", 0) for row in per_state
            ),
            "symbols_with_universe_arguments": sum(
                row["notes"].get("symbols_with_universe_arguments", 0) for row in per_state
            ),
        },
    }
    Path(sys.argv[1]).write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    manifest = [
        {
            "record_id": row["record_id"],
            "part": row["part"],
            "which": row["which"],
            "source_file": row["source_file"],
            "goal_count": row["goal_count"],
            "verdict": row["verdict"],
            "losses": row["losses"],
        }
        for row in per_state
    ]
    Path(sys.argv[2]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in (
        "states_analysed", "verdicts_by_state", "verdicts_by_record",
        "goal_count_distribution", "native_verifier_issue_codes",
        "never_observed_loss_classes", "aggregate_notes",
    )}, indent=2))
    print("LOSS CLASSES (by state):")
    for name, info in out["loss_class_frequency_by_state"].items():
        print(f"  {name:38s} {info['gap']:3s} {info['states']:5d}  {info['pct_of_states']:5.1f}%")
    print("NOVELTY constructs:", json.dumps(out["novelty_semantic_constructs"]["blocks"]))
    print("NOVELTY binders   :", json.dumps(out["novelty_binder_structures"]["blocks"]))
    print("provenance:", json.dumps(provenance))


if __name__ == "__main__":
    main()
