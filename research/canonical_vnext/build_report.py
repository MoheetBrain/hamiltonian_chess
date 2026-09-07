"""Assemble artifacts/reports/canonical_vnext_gap_verification.json from the pressure test.

Analysis only.  Reads research/canonical_vnext/pressure_test_raw.json (produced by
pressure_test.py) and merges it with the schema adjudication derived by reading
arena/canonical/**, arena/languages/_wire.py, arena/languages/phenotype.py and
arena/verifier/native.py.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "research/canonical_vnext/pressure_test_raw.json"
OUT = ROOT / "artifacts/reports/canonical_vnext_gap_verification.json"

raw = json.loads(RAW.read_text())
by_state = raw["loss_class_frequency_by_state"]
by_record = raw["loss_class_frequency_by_record"]
notes = raw["aggregate_notes"]


def freq(name: str) -> dict:
    return {
        "loss_class": name,
        "states": by_state.get(name, {}).get("states", 0),
        "pct_of_states": by_state.get(name, {}).get("pct_of_states", 0.0),
        "records": by_record.get(name, {}).get("records", 0),
        "pct_of_records": by_record.get(name, {}).get("pct_of_records", 0.0),
    }


schema_description = {
    "version_constant": {
        "value": "arena-canonical-v0.1.0",
        "site": "arena/canonical/schema.py:15",
        "note": "carried on CanonicalState.schema_version (schema.py:211) and therefore inside every mathematical_hash",
    },
    "types": {
        "CanonicalExpression": {
            "site": "arena/canonical/schema.py:42-75",
            "fields": {
                "op": "str - free-form operator name, no whitelist anywhere in arena/",
                "args": "tuple[CanonicalExpression, ...] - ordered children",
                "value": "str | int | float | bool | None - a single JSON scalar leaf",
                "sort": "str = 'Unknown' - a flat sort tag, no structure, no levels",
                "attributes": "tuple[tuple[str, str], ...] - string->string only (to_dict emits a dict)",
            },
            "invariants": [
                "to_dict omits empty args / None value / empty attributes (schema.py:52-60), so encoding is canonical-by-omission",
                "from_dict sorts attributes (schema.py:70), so attribute order is not identity-bearing",
                "content_hash = sha256 of canonical_json(to_dict()) (schema.py:73-75)",
            ],
        },
        "MathObject": {
            "site": "arena/canonical/schema.py:78-103",
            "fields": {
                "object_id": "str",
                "type_name": "str - flat string",
                "value": "CanonicalExpression | None",
                "shape": "tuple[int | str, ...]",
                "unit": "str | None",
            },
        },
        "Binding": {
            "site": "arena/canonical/schema.py:106-112",
            "fields": {
                "binder_id": "str",
                "variable": "str",
                "type_name": "str - FLAT STRING, cannot hold a term",
                "scope_id": "str - must appear in CanonicalState.local_scope",
                "binder_kind": "str = 'free' - free-form, but only the literal 'free' has semantics",
            },
            "invariants": [
                "no to_dict/from_dict: serialised with dataclasses.asdict via _dataclass_records (schema.py:192-193)",
                "CanonicalState.from_dict does Binding(**item) (schema.py:245): an unknown key is a TypeError",
                "native verifier collects free names only from bindings whose binder_kind == 'free' (arena/verifier/native.py:136)",
                "no value field: a let-bound (ldecl) local cannot carry its definition",
                "no attributes field: nothing can be smuggled onto a Binding at all",
            ],
        },
        "Obligation": {
            "site": "arena/canonical/schema.py:115-137",
            "fields": {
                "obligation_id": "str",
                "proposition": "CanonicalExpression",
                "status": "str = 'OPEN' - free-form; 'OPEN'/'DISCHARGED' have meaning in native.py:134",
                "source": "str = 'canonical' - free-form",
            },
            "invariants": [
                "no scope_id and no binding list: an obligation cannot be tied to a local context",
            ],
        },
        "EvidenceNode": {
            "site": "arena/canonical/schema.py:140-146",
            "fields": {
                "evidence_id": "str",
                "status": "str",
                "dependencies": "tuple[str, ...]",
                "authority": "str = 'native'",
                "certificate_hash": "str | None",
            },
            "invariants": [
                "dependencies must resolve inside the state and must be acyclic (native.py:93-114)",
            ],
        },
        "CanonicalAction": {
            "site": "arena/canonical/schema.py:149-189",
            "fields": {
                "action_id": "str",
                "operation": "str - UNCONSTRAINED; no operation whitelist exists in arena/",
                "target_ids": "tuple[str, ...] - must be a subset of object_ids | {'goal'} (native.py:231-241)",
                "arguments": "tuple[CanonicalExpression, ...] - POSITIONAL, not a name->term map",
                "warrant": "str",
                "preconditions": "tuple[CanonicalExpression, ...]",
                "generated_obligations": "tuple[Obligation, ...]",
                "expected_usefulness": "float",
            },
            "invariants": [
                "no premise-reference field: external library lemmas have no slot",
            ],
        },
        "CanonicalState": {
            "site": "arena/canonical/schema.py:196-290",
            "fields": [
                "state_id", "objects", "bindings", "assumptions", "established_facts",
                "propositions", "goal", "obligations", "evidence_dependencies", "local_scope",
                "legal_actions", "plausible_invalid_actions", "terminal_status",
                "schema_version", "execution_metadata",
            ],
            "invariants": [
                "goal is a SINGLE mandatory CanonicalExpression (schema.py:204); from_dict raises KeyError without it (schema.py:255) and the wire validator rejects the payload",
                "bindings/local_scope are state-global: there is no per-goal context",
                "ids must be unique per collection (native.py:66-80, _wire.py:219-230)",
                "every binding.scope_id must be present in local_scope (native.py:82-91)",
            ],
        },
        "VerificationRecord": {"site": "arena/canonical/schema.py:293-300"},
        "CanonicalTransition": {"site": "arena/canonical/schema.py:303-318"},
        "CanonicalTrajectory": {
            "site": "arena/canonical/schema.py:321-350",
            "fields": {"provenance": "tuple[tuple[str, str], ...] - free string map, untyped"},
        },
    },
    "hashing": {
        "canonical_json": "arena/canonical/schema.py:30-35 - sort_keys=True, separators=(',',':'), ensure_ascii=False",
        "stable_hash": "arena/canonical/schema.py:38-39 - sha256 over canonical_json",
        "CanonicalState.mathematical_hash": {
            "site": "arena/canonical/schema.py:281-283",
            "includes": [
                "schema_version", "objects", "bindings", "assumptions", "established_facts",
                "propositions", "goal", "obligations", "evidence_dependencies", "local_scope",
                "legal_actions", "plausible_invalid_actions", "terminal_status",
            ],
            "excludes": ["state_id", "execution_metadata"],
            "verified": "replacing schema_version alone changes mathematical_hash (executed probe E)",
        },
        "CanonicalState.artifact_hash": "arena/canonical/schema.py:285-287 - full to_dict including state_id and execution_metadata",
        "CanonicalTrajectory.content_hash": "arena/canonical/schema.py:346-350 - full dict minus trajectory_id",
    },
    "closed_wire_contract": {
        "site": "arena/languages/_wire.py:20-29, 147-216",
        "behaviour": "_dict() rejects BOTH missing and unknown keys at every level; _STATE_FIELDS is an exact set",
        "roundtrip": "payload_to_state re-serialises and demands byte equality with the input (_wire.py:233-241)",
        "verified": "adding a top-level 'goals' key is rejected as unknown (executed probe B)",
    },
    "blast_radius_of_any_field_addition": [
        "every CanonicalState.mathematical_hash changes if SCHEMA_VERSION changes (probe E)",
        "arena/languages/_wire.py:_STATE_FIELDS and STATE_FIELD_ORDER must change or every payload is rejected",
        "arena/languages/phenotype.py:_KNOWN_KEYS is INDEX-ADDRESSED (_role_map, phenotype.py:78-99 builds 'r{index:x}' / '@{index:x}' labels), so inserting a key renames the compressed and symbolic role labels of EVERY candidate language",
        "3 committed artifacts embed the literal 'arena-canonical-v0.1.0': artifacts/experiments/fitness_v3/frozen_manifest.json, artifacts/experiments/fitness_v2/probe_manifest.json, artifacts/worlds/arena-world-v0.jsonl",
        "hash-pinned tests: tests/canonical/test_schema.py, tests/languages/test_seed_roundtrip.py, tests/experiments/test_fitness_v3.py, tests/experiments/test_fitness_v4.py, tests/experiments/test_game_r_mutant_audit.py, tests/model_view/test_model_view.py, tests/compiler/test_facade.py",
    ],
    "escape_hatches_that_already_exist": [
        "CanonicalExpression.attributes accepts any string->string map, so arbitrary JSON can be smuggled losslessly as text (probe D: accepted by the wire validator, bytes recovered)",
        "CanonicalExpression.value accepts any JSON scalar; the production Lean transcriber already stores a universe level as canonical_json text (arena/environments/formal_structural.py:128-129)",
        "CanonicalAction.operation and Obligation.status/source are unconstrained strings",
        "Binding has NO escape hatch: no attributes, no value, and from_dict does Binding(**item)",
    ],
}

gaps = {
    "G1": {
        "claim": "Only ONE mandatory goal is supported; real proof states have multiple open goals.",
        "verdict": "CONFIRMED",
        "code_evidence": [
            "arena/canonical/schema.py:204 - goal: CanonicalExpression (single, no default, mandatory)",
            "arena/canonical/schema.py:255 - from_dict does raw['goal']; probe A raised KeyError",
            "arena/languages/_wire.py:147-163,205 - 'goal' is a required exact key; probe A2 rejected the payload",
            "arena/environments/formal_structural.py:291-293 - the EXISTING production Lean adapter discards every record whose goal list length != 1",
            "arena/canonical/schema.py:115-119 - Obligation has no scope_id, so goals 2..n moved into obligations lose their local context",
        ],
        "what_cannot_be_expressed": (
            "A closed proof state (0 goals) has nothing to put in the mandatory goal slot. "
            "A branching state (>1 goal) can put goals 2..n into obligations, but bindings and "
            "local_scope are state-global and Obligation carries no scope, so a state whose goals "
            "have different local contexts cannot be represented without inventing structure."
        ),
        "concrete_example": (
            "Lean `constructor` on `A / B` yields two goals sharing a context (representable, lossy); "
            "`induction n` yields a zero case with context {n:Nat} absent and a successor case with "
            "{n:Nat, ih:P n} present - two goals, two different contexts, one binding table."
        ),
        "measurements": [freq("ZERO_GOAL_MANDATORY_SLOT"), freq("MULTI_GOAL_SINGLE_SLOT"),
                         freq("PER_GOAL_LOCAL_CONTEXT_COLLISION"), freq("GOAL_IDENTITY_DROPPED")],
        "classification": "REQUIRED",
        "classification_justification": (
            "64/368 states (17.4%) have zero goals and are UNMAPPABLE outright; 42/368 (11.4%) have "
            "more than one. 66/184 records (35.9%) contain at least one UNMAPPABLE state. This is "
            "the only measured class that blocks import rather than degrading it."
        ),
    },
    "G2": {
        "claim": "No metavariable assignment map.",
        "verdict": "CONFIRMED",
        "code_evidence": [
            "arena/canonical/schema.py:196-212 - CanonicalState has no metavariable collection",
            "arena/canonical/schema.py:115-119 - Obligation is the nearest analogue and has no type, no kind, no assignment",
            "the source records carry state.metavariables[] with identity/kind/type/assigned/assignment and state_delta.metavariables_assigned[]",
        ],
        "what_cannot_be_expressed": (
            "The identity of the goal itself. In Lean a goal IS a metavariable; the corpus stores "
            "goal.identity = 'm0' and a matching metavariables entry with its type and kind "
            "(NATURAL / SYNTHETIC / SYNTHETIC_OPAQUE). None of identity, kind, type or assignment has a slot."
        ),
        "concrete_example": (
            "`refine f ?a ?b` creates two SYNTHETIC metavariables and assigns the parent goal to an "
            "application mentioning them. The canonical state can hold the new goals' propositions "
            "but not the fact that they are holes in one partially built term."
        ),
        "measurements": [freq("METAVARIABLE_CONTEXT_DROPPED"), freq("METAVARIABLE_ASSIGNMENT_DROPPED")],
        "extra_counts": {
            "metavariables_seen": notes["metavariables_total"],
            "of_which_assigned_with_a_term": notes["metavariables_assigned_total"],
        },
        "classification": "REQUIRED",
        "classification_justification": (
            "100% of records (184/184) carry a metavariable inventory and 62.0% carry at least one "
            "assigned metavariable with a term. Goal identity is metavariable identity, so G1 cannot "
            "be fixed correctly without this; the two are one structure."
        ),
    },
    "G3": {
        "claim": "Binding.type_name is a plain string, losing dependent-type structure.",
        "verdict": "CONFIRMED",
        "code_evidence": [
            "arena/canonical/schema.py:110 - type_name: str",
            "arena/canonical/schema.py:245 - Binding(**item); probe C shows an extra key is a TypeError",
            "arena/languages/_wire.py:89-92 - every Binding field must be a string, exactly five keys",
            "Binding has no attributes and no value field, so unlike CanonicalExpression it has NO string escape hatch for structure",
        ],
        "what_cannot_be_expressed": (
            "Any local hypothesis whose type is a term rather than a name. 4288 of 5071 local-context "
            "entries in the sample (84.6%) have a compound type tree. Under the current schema the "
            "only faithful move is to name the type by a content hash, which destroys every "
            "dependency between binders."
        ),
        "concrete_example": (
            "`h : SatisfiesM p (x >>= f)` becomes type_name='lean.type#<sha16>'. The fact that the "
            "type mentions the earlier binders x, f and p is gone, so no reader and no verifier can "
            "see the dependency the proof turns on."
        ),
        "measurements": [freq("DEPENDENT_TYPE_FLATTENED")],
        "extra_counts": {
            "local_context_entries": notes["local_context_entries"],
            "with_compound_type": notes["local_context_entries_with_compound_type"],
            "pct_compound": round(
                notes["local_context_entries_with_compound_type"] * 100
                / max(1, notes["local_context_entries"]), 1),
        },
        "classification": "REQUIRED",
        "classification_justification": (
            "100% of records (184/184) and 84.6% of individual local-context entries are affected, "
            "and Binding is the one record with no string escape hatch, so not even a lossless "
            "backend-native blob can rescue it without a schema change."
        ),
    },
    "G4": {
        "claim": "No universe levels.",
        "verdict": "CONFIRMED as a structural gap, REFUTED as a losslessness gap",
        "code_evidence": [
            "arena/canonical/schema.py:49 - sort: str = 'Unknown' is a flat tag with no level structure",
            "arena/environments/formal_structural.py:128-129 - the production transcriber already stores a level as canonical_json(...) TEXT in value",
            "arena/environments/formal_structural.py:118-124 - symbol nodes drop universe_arguments entirely today",
            "probe D - a JSON-encoded level in attributes passes the strict wire validator and round-trips byte-identically",
            "nothing in arena/ reads, compares or reasons about universe levels",
        ],
        "what_cannot_be_expressed": (
            "A universe level as structure that alpha_normalize, expressions_equivalent or the "
            "native verifier can see. As bytes it is expressible today."
        ),
        "concrete_example": (
            "`Sort (succ (param u_1))` and `Sort (succ (param u_2))` differ only in a level. As "
            "opaque strings they compare unequal, which is correct here but accidental: "
            "`max u v` vs `max v u` would also compare unequal though they denote the same level."
        ),
        "measurements": [freq("UNIVERSE_LEVEL_NONTRIVIAL"), freq("UNIVERSE_ARGUMENTS_ON_SYMBOL"),
                         freq("UNIVERSE_ASSIGNMENTS_DROPPED")],
        "extra_counts": {
            "sort_nodes_with_nontrivial_level": notes["sort_nodes_with_nontrivial_level"],
            "symbol_occurrences_carrying_universe_arguments": notes["symbols_with_universe_arguments"],
            "level_constructors_observed": ["zero", "succ", "param", "max", "imax", "mvar"],
        },
        "classification": "BACKEND_EXTENSION",
        "classification_justification": (
            "Universe data is ubiquitous (100% of records, 34781 symbol occurrences) but nothing in "
            "the Arena reasons about it, and CanonicalExpression.value/attributes already hold it "
            "losslessly as text. A typed level algebra in the universal core would buy nothing "
            "measurable today; a lossless lean-native field is enough. Revisit only if a task ever "
            "requires level equality, which no current fitness mechanism does."
        ),
    },
    "G5": {
        "claim": "No implicit / instance / strict-implicit argument kinds.",
        "verdict": "PARTIALLY CONFIRMED",
        "code_evidence": [
            "arena/canonical/schema.py:112 - binder_kind: str = 'free' EXISTS and is unconstrained, so the VALUE is expressible",
            "arena/verifier/native.py:136 - only binder_kind == 'free' declares a name; probe F shows binder_kind='implicit' or 'instance' makes the native verifier raise UNBOUND_VARIABLE on arena-native var terms",
            "arena/environments/formal_structural.py:130-132 - the production transcriber already stores binder_role as an expression attribute string",
            "expression-level binder nodes (lean.lambda / lean.dependent_function) have no binder_kind field of their own; only the string attributes map",
            "goal.local_instances (the instance cache) has no slot anywhere",
        ],
        "what_cannot_be_expressed": (
            "Nothing, at the byte level. What is broken is semantics: the one field that names a "
            "binder kind is overloaded to mean 'is this name declared?', so using it for Lean's four "
            "roles silently disables the verifier's scope checking."
        ),
        "concrete_example": (
            "`theorem foo {a : A} [inst : Monad m] (x : M a)` mixes IMPLICIT, INSTANCE_IMPLICIT and "
            "EXPLICIT. All four Lean roles occur in the sample "
            "(EXPLICIT, IMPLICIT, STRICT_IMPLICIT, INSTANCE_IMPLICIT). Recording them faithfully in "
            "binder_kind makes NativeVerifier reject the state."
        ),
        "measurements": [freq("NONEXPLICIT_BINDER_KIND"), freq("LOCAL_INSTANCES_DROPPED")],
        "extra_counts": {
            "binder_roles_observed": ["EXPLICIT", "IMPLICIT", "INSTANCE_IMPLICIT", "STRICT_IMPLICIT"],
            "distinct_binder_x_type_structures_observed": raw["novelty_binder_structures"]["total_distinct"],
        },
        "classification": "BACKEND_EXTENSION",
        "classification_justification": (
            "94.0% of records contain a non-EXPLICIT binder, but the field to hold the value already "
            "exists and the wire form already accepts it. The measured defect is in "
            "arena/verifier/native.py:136, not in the shape of Sigma, so this is a backend/verifier "
            "fix, not a universal-core field. A separate free/declared predicate would decouple it."
        ),
    },
    "G6": {
        "claim": "No substitution map.",
        "verdict": "CONFIRMED for metavariable assignment; UNTESTED for term-rewriting substitution",
        "code_evidence": [
            "arena/canonical/schema.py:154 - CanonicalAction.arguments is a POSITIONAL tuple, not a name->term map",
            "arena/canonical/schema.py:50 - attributes is string->string, so it cannot hold terms as structure",
            "no CanonicalState field holds a variable->term mapping",
        ],
        "what_cannot_be_expressed": (
            "Which metavariable was assigned which term by a step. The corpus records it twice "
            "(metavariables[].assignment and state_delta.metavariables_assigned); neither has a slot."
        ),
        "concrete_example": (
            "`exact ⟨x, hx⟩` assigns the goal metavariable to an anonymous constructor term. The "
            "canonical transition can show the goal disappearing but not the witness that closed it, "
            "which is exactly the evidence a Refuter needs to distinguish a real close from laundering."
        ),
        "measurements": [freq("MVAR_SUBSTITUTION_MAP_DROPPED")],
        "classification": "REQUIRED",
        "classification_justification": (
            "100% of records carry assignment data. It is however the SAME structure as G2: in Lean "
            "the substitution map is the metavariable assignment map, so G2 and G6 must be counted "
            "as one required addition, not two. The distinct term-rewriting reading of 'substitution "
            "map' has no evidence in this single-source sample."
        ),
    },
    "G7": {
        "claim": "No distinct-variable conditions (Metamath-style).",
        "verdict": "REFUTED on the available evidence / NOT APPLICABLE to this source",
        "code_evidence": [
            "0 of 368 sampled states contain any distinct-variable, disjoint-variable or dv payload",
            "Lean 4 has no distinct-variable conditions; it uses de Bruijn indices and free-variable identities, both of which the corpus records",
            "arena/canonical/equivalence.py:10-48 - alpha_normalize already gives depth-indexed bound identities, which is the mechanism DV conditions substitute for",
        ],
        "what_cannot_be_expressed": (
            "Nothing that this evidence base contains. The claim is neither confirmed nor refuted "
            "for a Metamath source, because no Metamath data was examined."
        ),
        "measurements": [freq("DISTINCT_VARIABLE_CONDITION")],
        "classification": "DEFER",
        "classification_justification": (
            "Zero occurrences in 368 real proof states. Adding a DV structure to the universal core "
            "on the strength of a hypothetical second backend would be cost with no measured benefit. "
            "Re-open only if a Metamath/set.mm import is actually planned; that import is the "
            "experiment that would settle it."
        ),
    },
    "G8": {
        "claim": "No definitional-equality step type.",
        "verdict": "REFUTED as a schema gap; the real gap is in the verifier, not in Sigma",
        "code_evidence": [
            "arena/canonical/schema.py:152 - CanonicalAction.operation is an unconstrained str; probe G constructed operation='defeq_unfold' and it serialised cleanly",
            "no operation whitelist exists anywhere in arena/ (grep found none)",
            "arena/canonical/schema.py:293-300 - VerificationRecord already carries verifier/authority/certificate_hash, which is where a kernel-checked defeq belongs",
            "arena/verifier/native.py has no defeq rule, and cannot have one: it is a structural checker with no reduction machinery",
            "the corpus cannot test this: action.kind is the constant LEAN_ELABORATED_TACTIC_OCCURRENCE and carries NO tactic name, so 0/184 records expose a defeq step to measure",
        ],
        "what_cannot_be_expressed": (
            "Nothing about the step type. What is missing is an authority able to certify that two "
            "canonical expressions are definitionally equal, and that is a verifier, not a field."
        ),
        "concrete_example": (
            "`show 2 + 2 = 4 from rfl` is representable today as "
            "CanonicalAction(operation='defeq', target_ids=('goal',)) with a VerificationRecord whose "
            "authority is the Lean kernel. Nothing in the schema blocks it."
        ),
        "measurements": [freq("DEFEQ_STEP_TYPE")],
        "classification": "NOT_CANONICAL",
        "classification_justification": (
            "The step type is already expressible; only its truth is not checkable natively. This "
            "belongs to the verification/authority layer (VerificationRecord + an external adapter), "
            "not to Sigma."
        ),
    },
}

new_gaps = {
    "N1_goal_identity_and_focus_order": {
        "verdict": "CONFIRMED (new)",
        "description": (
            "Goals have identities (metavariable ids) and states have a focus_order. Neither has a "
            "slot, so goal order and which goal is in focus cannot be recovered."
        ),
        "measurements": [freq("GOAL_IDENTITY_DROPPED"), freq("FOCUS_ORDER_DROPPED")],
        "classification": "REQUIRED",
        "classification_justification": "Subsumed by a correct G1+G2 fix; 100% / 18.5% of records respectively.",
    },
    "N2_let_bound_local_declarations": {
        "verdict": "CONFIRMED (new; not in G1-G8)",
        "description": (
            "Local declarations come in two roles: cdecl (a hypothesis) and ldecl (a let-binding "
            "with a definition). Binding has neither a value field nor an attributes map, so an "
            "ldecl's definition is unrecoverable and the cdecl/ldecl distinction itself is lost."
        ),
        "code_evidence": ["arena/canonical/schema.py:106-112", "arena/languages/_wire.py:89-92"],
        "measurements": [freq("LET_VALUE_DROPPED"), freq("DECLARATION_ROLE_DROPPED")],
        "classification": "REQUIRED",
        "classification_justification": (
            "9.2% of records. Low frequency, but the loss is silent and unrecoverable: a state with "
            "`x := 3` becomes a state with an opaque `x`, changing what is provable. Since Binding "
            "must be reopened for G3 anyway, the marginal cost is near zero."
        ),
    },
    "N3_external_premise_references": {
        "verdict": "CONFIRMED (new; the prior report mentions it only inside its 'tactic actions' item)",
        "description": (
            "CanonicalAction has no field for the library lemmas a step used. target_ids cannot be "
            "reused because arena/verifier/native.py:231-241 rejects any target not in "
            "object_ids | {'goal'}."
        ),
        "measurements": [freq("PREMISE_REFS_UNPLACEABLE")],
        "classification": "BACKEND_EXTENSION",
        "classification_justification": (
            "65.8% of records carry premise references, but they are properties of the step's "
            "provenance rather than of the mathematical state, and warrant (a free string) can hold "
            "them losslessly today. Promote to REQUIRED only if premise selection becomes a task."
        ),
    },
    "N4_obligations_have_no_scope": {
        "verdict": "CONFIRMED (new; the mechanism behind G1)",
        "description": (
            "Obligation(obligation_id, proposition, status, source) has no scope_id and no binding "
            "list, so the only available multi-goal workaround cannot attach a local context to the "
            "extra goals. Obligation.source is a free string and could smuggle a scope id, which is "
            "exactly the kind of untyped convention a vNext should replace."
        ),
        "code_evidence": ["arena/canonical/schema.py:115-137"],
        "classification": "REQUIRED",
        "classification_justification": "It is the reason G1 cannot be worked around; it is part of the same fix.",
    },
    "N5_native_verifier_is_blind_to_imports": {
        "verdict": "CONFIRMED (new; measurement artefact of high importance)",
        "description": (
            "All 304 constructed states passed the strict wire validator AND NativeVerifier with "
            "ZERO issue codes, because every operator was namespaced lean.* and none matches "
            "BINDER_OPERATORS, PARTIAL_OPERATORS or the arithmetic arity/sort rules in "
            "arena/verifier/native.py:12-13,147-230. 'The verifier accepts it' therefore carries no "
            "information about imported Lean states."
        ),
        "measured": {"constructed_states": 304, "native_issue_codes_raised": raw["native_verifier_issue_codes"]},
        "classification": "NOT_CANONICAL",
        "classification_justification": (
            "This is a verifier-coverage fact, not a Sigma shape. It matters because it means a "
            "vNext import cannot be validated by the native verifier and MUST be gated by an "
            "external authority (VerificationRecord) to be worth anything."
        ),
    },
}

report = {
    "report_id": "canonical-vnext-gap-verification",
    "generated_for": "arena-canonical-v0.1.0",
    "status": "ANALYSIS ONLY - no production schema, artifact, verifier or experiment was modified",
    "method": {
        "adjudication": "direct reading of arena/canonical/**, arena/languages/_wire.py, arena/languages/phenotype.py, arena/verifier/native.py, arena/environments/formal_structural.py, plus executed probes A-H",
        "pressure_test": "research/canonical_vnext/pressure_test.py, run against real Lean 4 proof states, importing the canonical schema read-only",
        "executed_probes": {
            "A": "CanonicalState.from_dict without goal -> KeyError('goal')",
            "A2": "wire validator without goal -> WireValidationError missing=['goal']",
            "B": "wire validator with an extra top-level 'goals' key -> WireValidationError unknown=['goals']",
            "C": "Binding(**{... 'universe': 'u'}) -> TypeError (no escape hatch on Binding)",
            "D": "JSON-encoded universe level in CanonicalExpression.attributes -> ACCEPTED, bytes recovered",
            "E": "changing schema_version alone changes mathematical_hash -> True",
            "F": "binder_kind 'free' accepted; 'implicit' and 'instance' -> UNBOUND_VARIABLE from NativeVerifier",
            "G": "CanonicalAction(operation='defeq_unfold') constructs and serialises cleanly",
            "H": "field inventories of Obligation / Binding / CanonicalState",
        },
    },
    "schema_description": schema_description,
    "sample_provenance": raw["provenance"],
    "pressure_test_results": {
        "states_analysed": raw["states_analysed"],
        "verdicts_by_state": raw["verdicts_by_state"],
        "verdicts_by_record": raw["verdicts_by_record"],
        "lossless_states": raw["verdicts_by_state"].get("LOSSLESS", 0),
        "goal_count_distribution": raw["goal_count_distribution"],
        "verdict_definitions": {
            "LOSSLESS": "every source information item has a first-class typed slot",
            "LOSSY_STRUCTURAL": "a state can be built and passes the wire validator and the native verifier, but some information survives only as an opaque string or is dropped",
            "UNMAPPABLE": "a hard cardinality or typing constraint is violated; no faithful state exists at any encoding",
        },
        "byte_lossless_note": (
            "Every LOSSY_STRUCTURAL state could be made byte-lossless today by JSON-encoding the "
            "missing data into CanonicalExpression.attributes (probe D). That is NOT true for "
            "Binding (probe C) nor for the UNMAPPABLE cardinality cases."
        ),
        "failure_class_frequency_by_state": by_state,
        "failure_class_frequency_by_record": by_record,
        "never_observed": raw["never_observed_loss_classes"],
        "native_verifier_issue_codes_raised": raw["native_verifier_issue_codes"],
        "aggregate_counts": notes,
    },
    "gap_adjudication": gaps,
    "new_gaps_discovered": new_gaps,
    "classification_table": {
        "REQUIRED": [
            "G1 multiple goals (with N1 goal identity/focus and N4 obligation scope)",
            "G2 metavariable context and assignment (same structure as G6)",
            "G3 binder types as terms",
            "G6 substitution map - counted as one addition with G2",
            "N2 let-bound local declarations",
        ],
        "DEFER": ["G7 distinct-variable conditions"],
        "BACKEND_EXTENSION": [
            "G4 universe levels",
            "G5 implicit/instance/strict-implicit binder kinds",
            "N3 external premise references",
        ],
        "NOT_CANONICAL": [
            "G8 definitional-equality step type",
            "N5 native verifier blindness to imported states",
        ],
    },
    "novelty_and_saturation": {
        "semantic_constructs": raw["novelty_semantic_constructs"],
        "binder_and_type_structures": raw["novelty_binder_structures"],
        "reading": (
            "Semantic-construct novelty saturates fast: 54 new constructs in records 1-50 "
            "(108 per 100), 1 in records 51-100 (2 per 100), 0 thereafter; 55 distinct in total. "
            "Binder x type structures are still climbing: 19, then 5, then 3, then 1 new "
            "(38.0 / 10.0 / 6.0 / 2.9 per 100 records), 28 distinct of a plausible ~64-cell product "
            "space (2 binder node kinds x 4 binder roles x ~8 binder-type node kinds)."
        ),
        "caveat": (
            "This is ONE source: the Lean 4.10.0-rc1 elaborator applied to mathlib4 and Batteries, "
            "through one extractor. Saturation of a node vocabulary fixed by Lean's own Expr type is "
            "close to tautological and says nothing about heterogeneous sources. A second source is "
            "needed before any saturation claim: specifically a backend whose primitives differ, "
            "e.g. a Metamath/set.mm export (the only thing that can test G7 at all), or the "
            "gold125 trajectory schema in hmlt-reasoning-corpus-lean-attestation/schemas/, or "
            "Arena's own symbolic/numeric domain states. Until then treat 55 as a lower bound on "
            "the universal construct count, not an estimate of it."
        ),
    },
    "explicitly_not_recommended": {
        "note": (
            "Typed E-Graph core, MMT/OMDoc, a Lean-native IR, a Metamath-native IR and universal "
            "micro-action decomposition are all treated as UNPROVEN HYPOTHESES and none is "
            "recommended here."
        ),
        "evidence_bearing_on_them": [
            {
                "hypothesis": "Typed E-Graph core",
                "evidence": "The only equality machinery measured is alpha_normalize (arena/canonical/equivalence.py). Nothing in the sample required congruence closure; the measured failures are cardinality and typing, not equality saturation.",
                "settling_experiment": "Import a corpus of defeq/rewrite steps with tactic names (this corpus has none) and measure how many transitions the native structural checker cannot decide but an e-graph could.",
            },
            {
                "hypothesis": "Lean-native or Metamath-native IR",
                "evidence": "Probe D shows a lossless backend-native STRING field already suffices for G4, G5 and N3. The three REQUIRED gaps (G1/G2/G6, G3, N2) are not backend-specific: multiple goals, typed contexts and let-bindings exist in Lean, Isabelle, Coq and HOL alike.",
                "settling_experiment": "Attempt the same mapping against a second, non-Lean backend and see whether its unmappable classes coincide with G1/G2/G3/N2 or diverge.",
            },
            {
                "hypothesis": "Universal micro-action decomposition",
                "evidence": "Untestable on this corpus: action.kind is the single constant LEAN_ELABORATED_TACTIC_OCCURRENCE with no tactic name, so 0/184 records expose an action vocabulary to decompose.",
                "settling_experiment": "Re-extract with tactic syntax captured, then measure whether a fixed micro-action set covers the observed tactic distribution.",
            },
            {
                "hypothesis": "MMT/OMDoc",
                "evidence": "No evidence gathered; out of scope of this measurement.",
                "settling_experiment": "None proposed.",
            },
        ],
        "losslessness_over_elegance": (
            "For G4, G5 and N3 a lossless backend-native field (or even the existing "
            "attributes/warrant strings) preserves every byte at zero blast radius. Only G1/G2/G6, "
            "G3 and N2 genuinely require the universal core to change, and G3/N2 do so only because "
            "Binding uniquely lacks any escape hatch."
        ),
    },
}

OUT.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
print("wrote", OUT, OUT.stat().st_size, "bytes")
