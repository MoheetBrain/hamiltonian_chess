"""Shared machinery for the HC-V0.6 runtime-noise measurement.

Every experiment in this package drives the **production** Solver adapter
(:class:`arena.trajectory.solver.OllamaTacticSolver`) rather than a hand-rolled HTTP client, so
what is measured is the configuration the assay will actually use: the same frozen prompt
template, the same ``format`` grammar, the same ``WIRE_FLAGS`` (``think=False`` is load-bearing --
with thinking on the answer is diverted and ``response`` comes back empty).

Only one thing is ever varied: ``SolverIdentity.decoding``, i.e. the ``options`` dict on the wire.
:func:`variant_identity` produces that variation with :func:`dataclasses.replace`, which leaves
every served field untouched, so :meth:`OllamaTacticSolver.verify_served` still refuses a
substituted model.

Every script writes **one JSON object per call** to a ``.jsonl`` file under ``out/``.  Summaries
are derived from those rows and never replace them.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import subprocess
import time
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from arena.trajectory.solver import (
    FROZEN_DECODING,
    RECORDED_SOLVER,
    WIRE_FLAGS,
    OllamaTacticSolver,
    ProposalBudget,
    SolverIdentity,
    build_prompt,
    identity_from_live,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent / "out"
SMOKE_ARTIFACT = REPO_ROOT / "artifacts" / "trajectory" / "hc_v0_5_smoke.json"

#: The digest the whole milestone is bound to.  A mismatch stops the run; nothing is substituted.
REQUIRED_DIGEST_PREFIX = "d49fd9e0da45"


class ModelUnavailable(RuntimeError):
    """The runtime does not serve the model this measurement is about."""


# ---------------------------------------------------------------------------------------------
# Environment capture
# ---------------------------------------------------------------------------------------------


def _sh(command: Sequence[str]) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip()


def environment_record(served: SolverIdentity) -> dict[str, Any]:
    """Everything needed to say which machine and which runtime produced these numbers."""

    return {
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_model": _sh(["sysctl", "-n", "hw.model"]),
        "host_cpu": _sh(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "host_memory_bytes": _sh(["sysctl", "-n", "hw.memsize"]),
        "macos": _sh(["sw_vers", "-productVersion"]),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "ollama_version": served.runtime_version,
        "model_name": served.model_name,
        "model_digest": served.model_digest,
        "quantization": served.quantization,
        "parameter_size": served.parameter_size,
        "architecture": served.architecture,
        "renderer": served.renderer,
        "parser": served.parser,
        "context_limit": served.context_limit,
        "wire_flags": dict(WIRE_FLAGS),
        "frozen_decoding": dict(FROZEN_DECODING),
        "prompt_template_sha256": served.prompt_template_sha256,
        "output_schema_sha256": served.output_schema_sha256,
    }


def verified_solver(endpoint: str) -> tuple[OllamaTacticSolver, SolverIdentity]:
    """Refuse to run unless the served model is exactly the recorded one."""

    solver = OllamaTacticSolver(endpoint=endpoint)
    served = identity_from_live(RECORDED_SOLVER.model_name, endpoint=endpoint)
    if not served.model_digest.startswith(REQUIRED_DIGEST_PREFIX):
        raise ModelUnavailable(
            f"served digest {served.model_digest!r} does not start with "
            f"{REQUIRED_DIGEST_PREFIX!r}; refusing to substitute another model"
        )
    RECORDED_SOLVER.assert_matches(served)
    return solver, served


# ---------------------------------------------------------------------------------------------
# Option variants
# ---------------------------------------------------------------------------------------------


def variant_identity(
    overrides: Mapping[str, Any] | None = None,
    *,
    drop: Iterable[str] = (),
    base: SolverIdentity = RECORDED_SOLVER,
) -> SolverIdentity:
    """A copy of ``base`` whose ``options`` dict is ``base``'s with ``overrides`` / ``drop``.

    Served fields are untouched, so identity verification still applies.
    """

    options = base.decoding_options()
    for key in drop:
        options.pop(key, None)
    options.update(dict(overrides or {}))
    pairs = tuple(sorted((str(key), value) for key, value in options.items()))
    return dataclasses.replace(base, decoding=pairs)


def solver_with(
    identity: SolverIdentity, *, endpoint: str, transport: Any = None
) -> OllamaTacticSolver:
    return OllamaTacticSolver(identity, endpoint=endpoint, transport=transport)


# ---------------------------------------------------------------------------------------------
# The prompt corpus
# ---------------------------------------------------------------------------------------------


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class Goal:
    """A real Lean goal state, presented to the Solver exactly as the arena presents one."""

    state_id: str
    goals_pp: str
    n_goals: int = 1
    problem_id: str = ""
    source: str = ""

    @property
    def step_index(self) -> int:
        return 0

    @property
    def rendered(self) -> Mapping[str, Any]:
        return {"renderer_id": "backend-native-v0", "goals_pp": self.goals_pp}

    @property
    def prompt(self) -> str:
        return build_prompt(self.goals_pp)

    @property
    def prompt_sha256(self) -> str:
        return sha256(self.prompt)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "problem_id": self.problem_id,
            "source": self.source,
            "n_goals": self.n_goals,
            "prompt_chars": len(self.prompt),
            "prompt_sha256": self.prompt_sha256,
        }


def _fresh_goals(path: Path) -> list[Goal]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    goals: list[Goal] = []
    for row in payload["goals"]:
        goals.append(
            Goal(
                state_id=str(row["state_id"]),
                goals_pp=str(row["goals_pp"]),
                n_goals=int(row.get("n_goals", 1)),
                problem_id=str(row.get("problem_id", "")),
                source="fresh-lean-repl",
            )
        )
    return goals


def _recorded_goals(path: Path) -> list[Goal]:
    """Real Lean states recovered from the HC-V0.5 smoke artefact.

    Recovery is **verified**, not assumed: a state is kept only when
    ``sha256(build_prompt(state.backend_native.pp))`` equals a ``prompt_sha256`` the recorded run
    actually sent.  That makes each prompt byte-identical to one the runtime has already seen.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    wanted: dict[str, dict[str, Any]] = {}
    for episode in payload["episodes"]:
        for step in episode["steps"]:
            wanted[str(step["prompt_sha256"])] = {
                "state_id": str(step.get("state_id", "")),
                "problem_id": str(episode.get("problem_id", "")),
            }
    goals: dict[str, Goal] = {}
    for episode in payload["episodes"]:
        for state in episode["trajectory"]["states"]:
            native = state.get("backend_native") or {}
            pp = str(native.get("pp", ""))
            if not pp.strip():
                continue
            digest = sha256(build_prompt(pp))
            if digest not in wanted or digest in goals:
                continue
            goals[digest] = Goal(
                state_id=str(state.get("state_id", "")) or wanted[digest]["state_id"],
                goals_pp=pp,
                n_goals=int(native.get("n_goals", 1) or 1),
                problem_id=str(state.get("problem_id", "")),
                source="hc_v0_5_smoke.json:verified-prompt-sha256",
            )
    ordered = sorted(goals.items(), key=lambda item: item[0])
    return [goal for _, goal in ordered]


def load_corpus(*, fresh: Path | None = None) -> list[Goal]:
    """The prompt corpus: fresh Lean states when available, else verified recorded ones."""

    if fresh is not None and fresh.exists():
        goals = _fresh_goals(fresh)
        if goals:
            return goals
    return _recorded_goals(SMOKE_ARTIFACT)


def by_length(goals: Sequence[Goal]) -> list[Goal]:
    return sorted(goals, key=lambda goal: (len(goal.prompt), goal.prompt_sha256))


# ---------------------------------------------------------------------------------------------
# Calling and recording
# ---------------------------------------------------------------------------------------------


def call(
    solver: OllamaTacticSolver,
    goal: Goal,
    *,
    budget: ProposalBudget,
    tags: Mapping[str, Any],
) -> dict[str, Any]:
    """One real generation, recorded whole.

    ``response_sha256`` is over the **raw response bytes**; ``tactic`` is the parsed action.  Both
    are reported, because "the bytes differ" and "the action differs" are different findings.
    """

    started = time.time()
    proposal = solver.propose(goal, budget=budget)
    row: dict[str, Any] = dict(proposal.to_dict())
    row.pop("provenance", None)
    row["response_sha256"] = sha256(proposal.raw_output)
    row["goal_state_id"] = goal.state_id
    row["goal_problem_id"] = goal.problem_id
    row["goal_source"] = goal.source
    row["prompt_chars"] = len(goal.prompt)
    row["options"] = solver.identity.decoding_options()
    row["wall_started_epoch"] = round(started, 6)
    row["wall_seconds"] = round(time.time() - started, 6)
    row.update(dict(tags))
    return row


class JsonlWriter:
    """Append-only per-call log.  Flushed after every row so a killed run keeps its data."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._handle = path.open("w", encoding="utf-8")
        self.rows = 0

    def write(self, row: Mapping[str, Any]) -> None:
        self._handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        self._handle.flush()
        self.rows += 1

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_meta(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), "utf-8")


# ---------------------------------------------------------------------------------------------
# Small statistics, stated rather than imported
# ---------------------------------------------------------------------------------------------


def modal_fraction(values: Sequence[str]) -> tuple[str, float]:
    """The most common value and the fraction of calls that produced it."""

    if not values:
        return "", 0.0
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    best = max(counts.items(), key=lambda item: (item[1], item[0]))
    return best[0], best[1] / len(values)


def bernoulli_variance(values: Sequence[str]) -> float:
    """``p(1-p)`` where ``p`` is the modal-agreement rate: the within-cell noise of "same answer"."""

    _, p = modal_fraction(values)
    return p * (1.0 - p)


def base_parser(description: str, default_out: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--out", type=Path, default=OUT_DIR / default_out)
    parser.add_argument(
        "--fresh-goals",
        type=Path,
        default=OUT_DIR / "fresh_goals.json",
        help="JSON of Lean-derived goals; falls back to the verified recorded corpus",
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    return parser
