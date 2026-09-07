"""Metamorphic operations with explicit support boundaries, never guessed Lean scope."""
from __future__ import annotations

import re
from dataclasses import replace

from .schema import CanonicalPremiseSelectionState


class UnsupportedTransformation(ValueError):
    pass


def permute_options(state: CanonicalPremiseSelectionState, permutation: tuple[int, ...]) -> CanonicalPremiseSelectionState:
    if sorted(permutation) != list(range(len(state.candidate_premises))):
        raise ValueError("not a candidate permutation")
    return replace(state, candidate_premises=tuple(state.candidate_premises[i] for i in permutation))


def obfuscate_option_identities(state: CanonicalPremiseSelectionState) -> CanonicalPremiseSelectionState:
    """Rename only experimental semantic IDs; Lean constant names are untouched.

    Obfuscating Lean identifiers generally needs elaborator identities. Inventing a token
    substitution would silently conflate locals, global constants and shadowed binders.
    """
    mapping = {c.premise_id: f"neutral_semantic_{i:02d}" for i, c in enumerate(state.candidate_premises)}
    return replace(state, candidate_premises=tuple(replace(c, premise_id=mapping[c.premise_id]) for c in state.candidate_premises), target_choice_id=mapping[state.target_choice_id])


_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LOCAL = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z_][A-Za-z0-9_]*)*) : (Nat|Int)\n")


def _flat_arithmetic_locals(state: CanonicalPremiseSelectionState) -> tuple[str, ...]:
    """Very small certified lexical fragment: independent Nat/Int locals, arithmetic goal.

    No application, binders, constants, coercions, dots, comments, strings, notation
    declarations or local definitions admitted. This checks a source fragment, not Lean.
    """
    lines = state.context.text.splitlines(keepends=True)
    if not lines:
        raise UnsupportedTransformation("no supported local declarations")
    names = []
    for line in lines:
        match = _LOCAL.fullmatch(line)
        if match is None:
            raise UnsupportedTransformation("requires only independent Nat/Int variable declarations")
        names.extend(match[1].split())
    if len(names) != len(set(names)) or set(names) & {"Nat", "Int"}:
        raise UnsupportedTransformation("shadowed or reserved local identifiers")
    goal = state.goal.text
    if not goal.startswith("⊢ ") or re.search(r"[^A-Za-z0-9_⊢\s()+*=<>≤≥≠-]", goal):
        raise UnsupportedTransformation("goal outside flat arithmetic fragment")
    if not set(_IDENT.findall(goal)) <= set(names):
        raise UnsupportedTransformation("goal has unresolved identifiers")
    # Reject adjacent atom application: even f x would need type/scope resolution.
    if re.search(r"[A-Za-z0-9_]\s+[A-Za-z0-9_]", goal[2:]):
        raise UnsupportedTransformation("application is outside supported fragment")
    return tuple(names)


def alpha_rename_locals(state: CanonicalPremiseSelectionState) -> CanonicalPremiseSelectionState:
    names = _flat_arithmetic_locals(state)
    mapping = {name: f"local_{i:03d}" for i, name in enumerate(names)}
    # Simultaneous substitution is capture-free in the restricted binder-free goal.
    transform = lambda text: _IDENT.sub(lambda m: mapping.get(m[0], m[0]), text)
    context = replace(state.context, text=transform(state.context.text))
    goal = replace(state.goal, text=transform(state.goal.text))
    return replace(state, context=context, goal=goal, source_raw_state=context.text + goal.text)


def permute_independent_context(state: CanonicalPremiseSelectionState) -> CanonicalPremiseSelectionState:
    _flat_arithmetic_locals(state)
    context = replace(state.context, text="".join(reversed(state.context.text.splitlines(keepends=True))))
    return replace(state, context=context, source_raw_state=context.text + state.goal.text)
