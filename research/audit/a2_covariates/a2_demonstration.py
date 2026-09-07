"""A2: concrete demonstrations that the label is obtainable without the intended operation.

Prints, for ONE real probe per mechanism at the level V7 selected, the exact
character-level computation a non-reasoning reader performs and the answer it yields.
NO model call.
"""

from __future__ import annotations

import json
from pathlib import Path

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    build_dev_pool,
    build_prompt,
    equal_information_genome,
)

OUT = Path(__file__).resolve().parent


def balance(text: str) -> list[int]:
    out = [0] * (len(text) + 1)
    d = 0
    for i, ch in enumerate(text):
        d += 1 if ch in "{[" else (-1 if ch in "}]" else 0)
        out[i + 1] = d
    return out


def occ(text: str, needle: str) -> list[int]:
    found, i = [], text.find(needle)
    while i >= 0:
        found.append(i)
        i = text.find(needle, i + 1)
    return found


def view(prompt: str) -> str:
    a = prompt.find("CURRENT STATE:\n")
    b = prompt.rfind("\nOPTIONS:\n")
    return prompt[a + len("CURRENT STATE:\n") : b]


def main() -> int:
    probes = build_dev_pool(Path.cwd())
    genome = equal_information_genome()
    picks = {
        ("formal_expression_depth", 2): None,
        ("transitive_dependency", 3): None,
        ("precondition_conjunction", 2): None,
    }
    out: dict[str, object] = {}
    for probe in probes:
        key = (probe.mechanism, probe.level)
        if key in picks and picks[key] is None and probe.variant.value == "ORIGINAL":
            picks[key] = probe
    for (mech, level), probe in picks.items():
        assert probe is not None
        prompt = build_prompt(genome, probe)
        v = view(prompt)
        bal = balance(v)
        stext = canonical_json(probe.state.to_dict(include_display_identity=False))
        names = [str(o.arguments[0].value) for o in probe.options]
        # the sibling COUNTERFACTUAL of the same family, for the flip check
        sibling = next(
            p
            for p in probes
            if p.family_id == probe.family_id and p.variant.value == "COUNTERFACTUAL"
        )
        sprompt = build_prompt(genome, sibling)
        sv = view(sprompt)
        sbal = balance(sv)
        rec = {
            "probe_id": probe.probe_id,
            "family_id": probe.family_id,
            "question": probe.question,
            "options": {"A": names[0], "B": names[1]},
            "preregistered_answer": "AB"[probe.expected_index],
            "ORIGINAL": {},
            "COUNTERFACTUAL_sibling": {
                "probe_id": sibling.probe_id,
                "preregistered_answer": "AB"[sibling.expected_index],
            },
        }
        for label, name in zip("AB", names, strict=True):
            q = f'"{name}"'
            hits, shits = occ(v, q), occ(sv, q)
            rec["ORIGINAL"][label] = {
                "identifier": name,
                "first_char_index_in_state_json": stext.find(q),
                "first_char_index_in_visible_state": v.find(q),
                "last_char_index_in_visible_state": v.rfind(q),
                "occurrences_in_visible_state": len(hits),
                "max_bracket_nesting_at_an_occurrence": max((bal[i] for i in hits), default=None),
            }
            rec["COUNTERFACTUAL_sibling"][label] = {
                "first_char_index_in_state_json": canonical_json(
                    sibling.state.to_dict(include_display_identity=False)
                ).find(q),
                "max_bracket_nesting_at_an_occurrence": max((sbal[i] for i in shits), default=None),
            }
        out[f"{mech}|L{level}"] = rec
    (OUT / "worked_examples.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
