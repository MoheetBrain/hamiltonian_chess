"""A3 -- what can the 6-character floor in ``assert_prompt_is_oracle_free`` actually let through?

The runtime tripwire is::

    if len(needle) >= 6 and needle in payload: raise

so every recorded tactic whose stripped length is < 6 is *never checked*.  This attack quantifies
the exposure on the frozen bank rather than arguing about it:

1. how many reference-tactic occurrences fall below the floor, and which strings they are;
2. of those, how many actually appear **verbatim in the rendered payload of some arm** -- i.e.
   how many would be a real leak that the floor lets past;
3. the same scan run with the floor REMOVED (length >= 1), for every arm, so the true
   leak count of the frozen design is measured and not assumed;
4. whether R_B's own markup vocabulary can manufacture a match.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.trajectory.representation import ARMS, UnrenderableStateError  # noqa: E402
from arena.trajectory.schema import BackendStateEnvelope, PPScope  # noqa: E402

FLOOR = 6


def main() -> int:
    bank = load_bank_dict()
    anchors = bank["anchors"]

    below: Counter[str] = Counter()
    total_occurrences = 0
    for anchor in anchors:
        for tactic in anchor["oracle"]["reference_tactics"]:
            needle = tactic.strip()
            total_occurrences += 1
            if len(needle) < FLOOR:
                below[needle] += 1

    # --- render every anchor under every arm and scan with NO floor ---------------------------
    leaks: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    model_visible: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    refusals: Counter[str] = Counter()
    rendered_chars: dict[str, list[int]] = {arm: [] for arm in ARMS}
    for anchor in anchors:
        visible = anchor["solver_visible"]
        envelope = BackendStateEnvelope(
            index=0,
            state_id=anchor["derivation_state_id"],
            pp=visible["goals_pp"],
            backend_kind=visible["backend_kind"],
            pp_scope=PPScope.from_dict(visible["pp_scope"]),
            n_goals=int(visible["n_goals"]),
            session_id="audit",
            problem_id=anchor["oracle"]["problem_id"],
        )
        tactics = [t.strip() for t in anchor["oracle"]["reference_tactics"] if t.strip()]
        for arm_id, renderer in ARMS.items():
            try:
                rendered = renderer.render(envelope)
            except UnrenderableStateError as error:
                refusals[f"{arm_id}:{error.args[0] if error.args else 'REFUSED'}"] += 1
                continue
            payload = json.dumps(dict(rendered), ensure_ascii=False)
            shown = str(rendered.get("goals_pp", ""))
            rendered_chars[arm_id].append(len(shown))
            for needle in tactics:
                if needle in payload:
                    leaks[arm_id].append(
                        {
                            "anchor_id": anchor["anchor_id"],
                            "tactic": needle,
                            "len": len(needle),
                            "caught_by_floor": len(needle) >= FLOOR,
                            "in_model_visible_goals_pp": needle in shown,
                        }
                    )
                if needle in shown:
                    model_visible[arm_id].append(
                        {
                            "anchor_id": anchor["anchor_id"],
                            "tactic": needle,
                            "len": len(needle),
                            "caught_by_floor": len(needle) >= FLOOR,
                        }
                    )

    # --- can R_B's markup manufacture a match? -----------------------------------------------
    markup = ["[GOAL 1 OF 1]", "[HYPOTHESES 0]", "[TARGET]", "[CASE] ", "(1) "]
    markup_collisions = sorted({t for t in below if any(t in m for m in markup)})

    below_floor_leaks = {
        arm: [entry for entry in found if not entry["caught_by_floor"]]
        for arm, found in leaks.items()
    }
    any_leak = any(model_visible[arm] for arm in model_visible)
    emit(
        "attack_03_leakage",
        {
            "attack": "A3 no reference leakage: what does the 6-character floor let through?",
            "verdict": "BROKEN" if any_leak else "HELD",
            "anchors_scanned": len(anchors),
            "reference_tactic_occurrences": total_occurrences,
            "occurrences_below_the_floor": sum(below.values()),
            "distinct_strings_below_the_floor": dict(below.most_common()),
            "verbatim_matches_in_rendered_payload_by_arm": {
                arm: len(found) for arm, found in leaks.items()
            },
            "verbatim_matches_that_the_floor_would_NOT_catch": {
                arm: len(found) for arm, found in below_floor_leaks.items()
            },
            "verbatim_matches_in_MODEL_VISIBLE_goals_pp_by_arm": {
                arm: len(found) for arm, found in model_visible.items()
            },
            "model_visible_examples": {
                arm: found[:5] for arm, found in model_visible.items() if found
            },
            "payload_only_examples": {arm: found[:3] for arm, found in leaks.items() if found},
            "renderer_refusals": dict(refusals),
            "max_rendered_goals_pp_chars_by_arm": {
                arm: (max(values) if values else 0) for arm, values in rendered_chars.items()
            },
            "markup_strings_colliding_with_a_sub_floor_tactic": markup_collisions,
            "note": (
                "A verbatim match is the only thing either tripwire can detect. The floor is a "
                "false-positive guard, and this measures what it costs: every sub-floor tactic "
                "string, and whether any of them actually reaches a rendered payload."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
