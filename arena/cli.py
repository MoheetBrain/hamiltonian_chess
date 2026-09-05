"""Hamiltonian Arena command-line control plane."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.languages.registry import get_language, seed_languages
from arena.pipeline import ArenaRuntime
from arena.players.solver import SolverRequest
from arena.storage.artifacts import ArtifactStore
from arena.tasks.generators.world_v0 import DEFAULT_WORLD_SIZE, build_world_v0
from arena.training.scout import ScoutConfig, run_scout

app = typer.Typer(no_args_is_help=True, help="Evidence-first mathematical-language Arena.")
worlds_app = typer.Typer(no_args_is_help=True, help="Build and validate canonical worlds.")
languages_app = typer.Typer(no_args_is_help=True, help="Manage executable seed languages.")
candidate_app = typer.Typer(no_args_is_help=True, help="Create and inspect candidates.")
league_app = typer.Typer(no_args_is_help=True, help="Run the multi-objective candidate league.")
curriculum_app = typer.Typer(no_args_is_help=True, help="Control information acquisition.")
training_app = typer.Typer(no_args_is_help=True, help="Run explicit model experiments.")
rstar_app = typer.Typer(no_args_is_help=True, help="Apply the fail-closed R*-V0 gate.")

app.add_typer(worlds_app, name="worlds")
app.add_typer(languages_app, name="languages")
app.add_typer(candidate_app, name="candidate")
app.add_typer(league_app, name="league")
app.add_typer(curriculum_app, name="curriculum")
app.add_typer(training_app, name="training")
app.add_typer(rstar_app, name="rstar")

console = Console()


def _runtime() -> ArenaRuntime:
    return ArenaRuntime(Path.cwd())


def _json(value: object) -> None:
    console.print_json(json.dumps(value, ensure_ascii=False, default=str))


@app.command("init")
def initialize() -> None:
    """Initialize the SQLite control plane and artifact directories."""

    _json(_runtime().initialize())


@worlds_app.command("build")
def worlds_build(
    count: int = typer.Option(DEFAULT_WORLD_SIZE, min=1, help="Exact number of tasks."),
    seed: int = typer.Option(0, help="Deterministic generator seed."),
) -> None:
    _json(_runtime().build_worlds(total=count, seed=seed))


@worlds_app.command("validate")
def worlds_validate() -> None:
    result = _runtime().validate_worlds()
    _json(result)
    if not result["valid"]:
        raise typer.Exit(1)


@languages_app.command("seed")
def languages_seed() -> None:
    _json(_runtime().seed_candidate_languages())


@languages_app.command("list")
def languages_list() -> None:
    rows = [
        {
            "candidate_id": language.candidate_id,
            "format_id": language.format_id,
            "genome_hash": language.genome.genome_hash,
        }
        for language in seed_languages()
    ]
    _json(rows)


@candidate_app.command("create")
def candidate_create(
    parent: str = typer.Option(..., "--parent", help="Parent candidate ID."),
    seed: int = typer.Option(0, help="Deterministic proposal seed."),
) -> None:
    _json(_runtime().mutate(parent, count=1, seed=seed))


@app.command("mutate")
def mutate(
    parent: str = typer.Option(..., "--parent", help="Parent candidate ID."),
    count: int = typer.Option(20, "--n", min=1, help="Number of valid proposals."),
    seed: int = typer.Option(0, help="Deterministic proposal seed."),
) -> None:
    _json(_runtime().mutate(parent, count=count, seed=seed))


@app.command("evaluate")
def evaluate(
    candidate_id: str = typer.Argument(..., help="Executable candidate ID."),
    tier: int = typer.Option(1, min=0, max=2),
) -> None:
    try:
        result = _runtime().evaluate(candidate_id, tier=tier)
    except (KeyError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    _json(result.to_dict())


@league_app.command("run")
def league_run(tier: int = typer.Option(1, min=0, max=1)) -> None:
    _json(_runtime().run_league(tier=tier))


@app.command("assure")
def assure(candidate_id: str = typer.Argument(...)) -> None:
    try:
        result = _runtime().assure(candidate_id)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from error
    _json(result)
    if int(result["critical_failures"]) > 0:
        raise typer.Exit(1)


@app.command("refute")
def refute(candidate_id: str = typer.Argument(...)) -> None:
    """Run the frozen semantic Refuter and minimized-failure store."""

    result = _runtime().assure(candidate_id)
    _json(result["refuter"])
    if int(result["refuter"]["false_accepts"]) > 0:
        raise typer.Exit(1)


@curriculum_app.command("evolve")
def curriculum_evolve() -> None:
    """Report the current acquisition state without inventing observations."""

    _json(
        {
            "status": "WAITING_FOR_SOLVER_OBSERVATIONS",
            "policy": "disagreement + expected ranking information + frontier uncertainty",
            "next_action": "run `arena training scout` or a matched Tier-2 experiment",
        }
    )


@training_app.command("scout")
def training_scout(
    model: str = typer.Option(..., help="Exact local Ollama model name."),
    candidate_id: str = typer.Option("L5_COMPACT_SYMBOLIC", "--candidate"),
    count: int = typer.Option(4, min=1, max=64),
    seed: int = typer.Option(0),
) -> None:
    """Run an explicitly labelled frozen-model acquisition scout."""

    language = get_language(candidate_id)
    world = build_world_v0(total=max(13, count), seed=seed)
    requests = tuple(
        SolverRequest(
            task.task_id,
            "NEXT_ACTION_FREE_GENERATION",
            candidate_id,
            language.render(
                project_state_for_observation(
                    task.trajectory.initial_state, ObservationKind.NEXT_ACTION
                )
            ),
            "canonical CanonicalAction JSON object",
        )
        for task in world.tasks[:count]
    )
    responses = run_scout(requests, ScoutConfig(model=model, seed=seed))
    result = {
        "scope": "FROZEN_MODEL_SCOUT_NOT_MATCHED_LEARNING",
        "model": model,
        "candidate_id": candidate_id,
        "seed": seed,
        "responses": [asdict(response) for response in responses],
    }
    artifact = ArtifactStore(Path.cwd() / "artifacts").write_json(
        f"reports/scout-{candidate_id}-{seed}.json", result
    )
    _json({**result, "artifact": str(artifact.path)})


@app.command("finalists")
def finalists() -> None:
    status = _runtime().status()
    scoreboard = status["scoreboard"]
    rows = [] if scoreboard is None else scoreboard["rows"]
    _json(
        {
            "static_frontier": [
                row["candidate_id"] for row in rows if row["pareto_status"] == "FRONTIER"
            ],
            "release_winner": None,
            "reason": "matched model fitness is unmeasured",
        }
    )


@rstar_app.command("freeze")
def rstar_freeze(candidate_id: str = typer.Argument(...)) -> None:
    try:
        decision = _runtime().release_decision(candidate_id)
    except KeyError as error:
        raise typer.BadParameter(str(error)) from error
    _json(decision.to_dict())
    if not decision.released:
        raise typer.Exit(2)


@app.command("report")
def report() -> None:
    runtime = _runtime()
    text = runtime.report()
    runtime.store.write_text("reports/status.md", text)
    console.print(text)


@app.command("status")
def status() -> None:
    """Show the complete current dashboard."""

    current = _runtime().status()
    console.print(_runtime().report())
    scoreboard = current["scoreboard"]
    if scoreboard is None:
        console.print("No scoreboard yet. Run: arena league run")
        return
    table = Table(title="Static Arena Scoreboard")
    for column in ("Candidate", "Gate 0", "Coverage", "Roundtrip", "Tokens*", "Pareto"):
        table.add_column(column)
    for row in scoreboard["rows"]:
        table.add_row(
            str(row["candidate_id"]),
            str(row["soundness_gate"]),
            f"{float(row['coverage']):.3f}",
            f"{float(row['roundtrip']):.3f}",
            f"{float(row['tokens_proxy']):.1f}",
            str(row["pareto_status"]),
        )
    console.print(table)
    console.print("* ceil(UTF-8 bytes / 4), not a model tokenizer")


if __name__ == "__main__":
    app()
