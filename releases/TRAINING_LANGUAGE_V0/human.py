"""Optional human-facing rendering, for debugging only.

Nothing in the training path calls this.  The model-facing form does not have to be
pretty, and making it pretty at the cost of round-tripping would be a bad trade; this is a
separate, deliberately one-way view.
"""

from __future__ import annotations

from .core import State, Term, Type
from .libraries import Library, check_vocabulary

_INDENT = "  "


def show_type(sort: Type) -> str:
    if not sort.params:
        return sort.head
    return f"{sort.head}<{', '.join(show_type(item) for item in sort.params)}>"


def show_term(term: Term) -> str:
    body = term.op
    if term.value is not None:
        body = f"{body}={term.value!r}" if term.op != "lit" else repr(term.value)
    if term.args:
        body = f"{body}({', '.join(show_term(item) for item in term.args)})"
    return f"{body} : {show_type(term.sort)}"


def show_state(state: State, *, libraries: tuple[Library, ...] = ()) -> str:
    """A grouped, indented view: each goal beside the context it actually holds."""

    lines: list[str] = [f"state {state.state_id}  [{state.terminal_status}]"]
    if state.libraries:
        joined = ", ".join(f"{item.library_id}@{item.version}" for item in state.libraries)
        lines.append(f"libraries: {joined}")
    for goal in state.goals:
        marker = "*" if goal.focused else "-"
        chain = " > ".join(state.scope_chain(goal.scope_id))
        lines.append(f"{marker} goal {goal.goal_id} [{goal.status.value}] in {chain}")
        for declaration in state.declarations_in_scope(goal.scope_id):
            suffix = f" := {show_term(declaration.value)}" if declaration.value is not None else ""
            lines.append(
                f"{_INDENT}{declaration.kind.value} {declaration.name} : "
                f"{show_type(declaration.sort)}{suffix}"
            )
        lines.append(f"{_INDENT}|- {show_term(goal.statement)}")
    if not state.goals:
        lines.append("- no goals")
    for claim in state.claims:
        link = f" <- {claim.evidence_id}" if claim.evidence_id else ""
        lines.append(
            f"{claim.role.value} {claim.claim_id} [{claim.status.value}]{link} "
            f"in {claim.scope_id}: {show_term(claim.statement)}"
        )
    for obligation in state.obligations:
        lines.append(
            f"obligation {obligation.obligation_id} [{obligation.status.value}] "
            f"in {obligation.scope_id} from {obligation.source}: "
            f"{show_term(obligation.statement)}"
        )
    for record in state.evidence:
        lines.append(
            f"evidence {record.evidence_id} [{record.status.value}] by "
            f"{record.verifier or '<none>'} {record.verifier_version or ''}".rstrip()
        )
    for name, term in state.substitution:
        lines.append(f"substitute {name} := {show_term(term)}")
    for action in state.actions:
        targets = ", ".join(action.targets) or "<none>"
        lines.append(
            f"action {action.action_id} [{action.status.value}] {action.operation} -> {targets}"
        )
        if action.warrant:
            lines.append(f"{_INDENT}warrant: {action.warrant}")
        for obligation in action.generated_obligations:
            lines.append(f"{_INDENT}generates {obligation.obligation_id}")
    for extension in state.extensions:
        lines.append(f"extension {extension.owner_id}.{extension.key}: {extension.payload}")
    if libraries:
        report = check_vocabulary(state, libraries)
        if not report.is_complete:
            lines.append(f"undeclared vocabulary: {report.to_dict()}")
    return "\n".join(lines) + "\n"


__all__ = ["show_state", "show_term", "show_type"]
