"""Item F: the renderer is a pure deterministic function of (state, configuration).

Three independent checks, none of which relies on reading the source and believing it.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Claim,
    ClaimRole,
    Decl,
    DeclKind,
    Scope,
    State,
    Term,
    Type,
    render_state,
)
from releases.TRAINING_LANGUAGE_V0.hashes import PACKAGE_ROOT

from .conftest import PROP, build_rich_state

FORBIDDEN_MODULES = {"random", "time", "datetime", "uuid", "secrets", "os"}
REPO_ROOT = Path(__file__).resolve().parents[2]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", sorted(PACKAGE_ROOT.glob("*.py")), ids=lambda item: item.name)
def test_no_module_imports_a_source_of_nondeterminism(path: Path) -> None:
    offenders = _imported_modules(path) & FORBIDDEN_MODULES
    assert not offenders, f"{path.name} imports {sorted(offenders)}"


def test_attribute_insertion_order_does_not_change_a_single_byte() -> None:
    pairs = [("z", "1"), ("a", "2"), ("m", "3"), ("b", "4")]
    renderings = set()
    for rotation in range(len(pairs)):
        ordered = dict(pairs[rotation:] + pairs[:rotation])
        state = State(
            state_id="s",
            scopes=(Scope("r"),),
            declarations=(Decl("d", "x", Type("Nat"), "r", DeclKind.FREE, attributes=ordered),),
            claims=(
                Claim(
                    "c",
                    ClaimRole.FACT,
                    "r",
                    Term("p", PROP, attributes=ordered),
                    attributes=ordered,
                ),
            ),
        )
        renderings.add(render_state(state))
    assert len(renderings) == 1


def test_rendering_is_stable_across_repeated_calls(rich_state: State) -> None:
    assert len({render_state(rich_state) for _ in range(20)}) == 1


def test_rendering_is_stable_across_python_hash_seeds() -> None:
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from tests.releases.conftest import build_rich_state;"
        "from releases.TRAINING_LANGUAGE_V0 import render_state;"
        "print(render_state(build_rich_state()), end='')"
    )
    outputs = set()
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", script, str(REPO_ROOT)],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        outputs.add(result.stdout)
    assert len(outputs) == 1
    assert next(iter(outputs)) == render_state(build_rich_state())


def test_render_config_is_the_only_other_input(rich_state: State) -> None:
    from releases.TRAINING_LANGUAGE_V0 import LOSSLESS, PROMPT_VIEW, RenderConfig

    assert render_state(rich_state, RenderConfig()) == render_state(rich_state, LOSSLESS)
    assert render_state(rich_state, PROMPT_VIEW) != render_state(rich_state, LOSSLESS)
    assert LOSSLESS.describe() == RenderConfig().describe()


def test_a_state_with_no_declared_order_still_has_one(minimal_state: State) -> None:
    assert render_state(minimal_state).splitlines() == [
        "TL0 0.1.0 state:min",
        "scope root _",
        "status OPEN",
    ]
