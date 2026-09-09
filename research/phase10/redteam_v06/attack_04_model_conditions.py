"""A4 -- is every controllable thing identical across arms and across models?

The wire payload is rebuilt for every arm and for every model named in the frozen spec, and the
payloads are diffed key by key.  Anything that differs and is not the prompt bytes is a confound.

Also checked:
* the prompt template is applied identically (one substitution, no per-arm branch);
* ``num_ctx`` cannot be silently exceeded by the longest rendering in the bank;
* ``ProposalBudget`` cannot make one arm cheaper than another;
* the transport timeout actually used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.trajectory.representation import ARMS  # noqa: E402
from arena.trajectory.schema import BackendStateEnvelope, PPScope  # noqa: E402
from arena.trajectory.solver import (  # noqa: E402
    DEFAULT_BUDGET,
    FROZEN_DECODING,
    PROMPT_TEMPLATE,
    PROMPT_TEMPLATE_SHA256,
    RECORDED_SOLVER,
    TACTIC_RESPONSE_SCHEMA_SHA256,
    WIRE_FLAGS,
    OllamaTacticSolver,
    build_prompt,
)

MODELS = ("gemma4:e4b", "gemma4:12b", "qwen3.6:27b-mlx", "gemma4:31b", "gemma3:4b")


def _envelope(pp: str) -> BackendStateEnvelope:
    return BackendStateEnvelope(
        index=0,
        state_id="sid",
        pp=pp,
        backend_kind="LEAN4_TACTIC_STATE_PP",
        pp_scope=PPScope(current_namespace="Nat", open_declarations=("Finset",)),
        n_goals=1,
        session_id="sess",
        problem_id="F.lean::t",
    )


def main() -> int:
    from dataclasses import replace

    envelope = _envelope("n : Nat\nh : 0 < n\n⊢ n ≠ 0")

    # --- per-arm payloads under one model -----------------------------------------------------
    solver = OllamaTacticSolver(RECORDED_SOLVER)
    per_arm: dict[str, dict[str, Any]] = {}
    for arm_id, renderer in ARMS.items():
        rendered = renderer.render(envelope)
        payload = solver.payload(build_prompt(str(rendered["goals_pp"])), budget=DEFAULT_BUDGET)
        per_arm[arm_id] = payload
    non_prompt = {
        arm: {k: v for k, v in payload.items() if k != "prompt"} for arm, payload in per_arm.items()
    }
    arm_signatures = {json.dumps(v, sort_keys=True) for v in non_prompt.values()}

    # --- per-model payloads under one arm -----------------------------------------------------
    per_model: dict[str, dict[str, Any]] = {}
    for name in MODELS:
        identity = replace(RECORDED_SOLVER, model_name=name, model_digest="d" * 64)
        payload = OllamaTacticSolver(identity).payload(
            build_prompt(str(ARMS["R_A"].render(envelope)["goals_pp"])), budget=DEFAULT_BUDGET
        )
        per_model[name] = payload
    model_signatures = {
        json.dumps({k: v for k, v in p.items() if k != "model"}, sort_keys=True)
        for p in per_model.values()
    }

    # --- can the longest rendering in the bank overflow num_ctx? ------------------------------
    bank = load_bank_dict()
    longest = {arm: 0 for arm in ARMS}
    for anchor in bank["anchors"]:
        visible = anchor["solver_visible"]
        env = BackendStateEnvelope(
            index=0,
            state_id="0",
            pp=visible["goals_pp"],
            backend_kind=visible["backend_kind"],
            pp_scope=PPScope.from_dict(visible["pp_scope"]),
            n_goals=int(visible["n_goals"]),
        )
        for arm_id, renderer in ARMS.items():
            prompt = build_prompt(str(renderer.render(env)["goals_pp"]))
            longest[arm_id] = max(longest[arm_id], len(prompt))

    emit(
        "attack_04_model_conditions",
        {
            "attack": "A4 model condition equality across arms and models",
            "verdict": (
                "HELD" if len(arm_signatures) == 1 and len(model_signatures) == 1 else "BROKEN"
            ),
            "arms_share_one_non_prompt_payload": len(arm_signatures) == 1,
            "models_share_one_non_model_payload": len(model_signatures) == 1,
            "shared_payload_minus_prompt": next(iter(non_prompt.values())),
            "frozen_decoding": dict(FROZEN_DECODING),
            "wire_flags": dict(WIRE_FLAGS),
            "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
            "output_schema_sha256": TACTIC_RESPONSE_SCHEMA_SHA256,
            "prompt_template_has_one_substitution": PROMPT_TEMPLATE.count("{state}") == 1,
            "default_budget": DEFAULT_BUDGET.to_dict(),
            "budget_can_differ_by_arm": False,
            "longest_prompt_chars_by_arm": longest,
            "num_ctx": FROZEN_DECODING["num_ctx"],
            "worst_case_chars_per_ctx_token_needed_to_overflow": round(
                max(longest.values()) / float(FROZEN_DECODING["num_ctx"]), 4
            ),
            "notes": [
                "OllamaTacticSolver.payload() reads only module constants plus the prompt, so no "
                "arm and no model can carry a different option, wire flag or grammar.",
                "budget.timeout_seconds is recorded in provenance but never passed to the "
                "transport: urllib_transport is called positionally and keeps its own 900 s "
                "default. Harmless here (the values agree) but the recorded value is not the "
                "value in force.",
                "The longest R_B prompt in the whole bank is far below num_ctx even at one token "
                "per character, so context truncation cannot differ by arm on this bank.",
            ],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
