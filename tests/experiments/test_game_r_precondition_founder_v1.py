"""Tests for the Phase-8 founder-on-precondition-ladder experiment module.

Offline, CPU-only, no model call: the only solvers are :class:`StubSolver` and thin wrappers
around it.  Every path written goes under ``tmp_path``; the real ``artifacts/`` tree is never
touched.  Where a test needs items it uses the harness stub environment (fast) or the real
ladder's ``SMOKE`` pool with one or two families.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from arena.environments import precondition_ladder as pl
from arena.experiments import fitness_v5, game_r_formal_v1, ollama_live
from arena.experiments import game_r_precondition_founder_v1 as exp
from arena.experiments.game_r_formal_v1 import (
    HARNESS_VERSION,
    BudgetExceeded,
    CallBudget,
    HarnessRefusal,
    ItemVariant,
    SolverResponse,
    StubSolver,
    StubSolverPolicy,
    StubTokenCounter,
    SyntaxGuidePolicy,
    build_prompt,
    decoding_hash,
    founder_genome,
    prompt_bytes_hash,
    qualified_task_id,
    response_schema,
    rotate_options,
)
from arena.experiments.ollama_live import frozen_decoding
from arena.storage.artifacts import ArtifactStore

TRIO: tuple[str, ...] = ("L3_JSON_AST", "L1_CURRENT_HML", "L5_COMPACT_SYMBOLIC")
MODULE_SOURCE = Path(exp.__file__).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a test attempted a network call")

    monkeypatch.setattr(ollama_live, "urlopen", refuse)
    monkeypatch.setattr(fitness_v5, "urlopen", refuse)
    monkeypatch.setattr(game_r_formal_v1, "urlopen", refuse)


# ------------------------------------------------------------------------------- helpers


def _stub(families: int = 3, strata: Sequence[str] = ("S1",)) -> tuple[exp.TaskBatch, ...]:
    return exp.stub_batches(tuple(strata), families=families)


def _solver() -> StubSolver:
    return StubSolver(policy=StubSolverPolicy.DETERMINISTIC_MIX, n_options=2)


def _files(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def _control() -> tuple[Any, ...]:
    return exp.founder_roster((exp.BASELINE_SURFACE,))


def _row(
    task: str,
    pairing: str,
    variant: str,
    *,
    answer: str | None,
    content: str | None,
    status: str = "CORRECT",
    valid: bool | None = None,
) -> dict[str, Any]:
    return {
        "mechanism": "m",
        "environment_version": "env",
        "task_id": task,
        "pairing_key": pairing,
        "family_id": task.split("#")[0],
        "level": 1,
        "variant": variant,
        "candidate_id": "GRF_X",
        "prompt_hash": "p" * 64,
        "cache_key": "k" * 64,
        "prompt_tokens_counted": 10,
        "prompt_token_limit": 32448,
        "n_options": 2,
        "correct_index": 0,
        "cache_hit": False,
        "cache_scope": "FRESH",
        "status": status,
        "selected_index": None if answer is None else 0,
        "selected_answer_id": answer,
        "selected_content_hash": content,
        "correct": status == "CORRECT",
        "valid": (answer is not None) if valid is None else valid,
        "prompt_tokens_reported": 10,
        "token_count_mismatch": False,
        "raw_output": "",
    }


class _SentinelKiller:
    """A Solver hook: delegates to the stub and deletes ``path`` on its ``at``-th call."""

    def __init__(self, inner: StubSolver, path: Path, at: int, *, rmtree: bool = False) -> None:
        self.inner = inner
        self.path = path
        self.at = at
        self.rmtree = rmtree
        self.calls = 0

    @property
    def name(self) -> str:
        return self.inner.name

    @property
    def digest(self) -> str:
        return self.inner.digest

    @property
    def revision(self) -> str:
        return self.inner.revision

    def generate(
        self, prompt: str, *, schema: Mapping[str, Any], decoding: Mapping[str, Any]
    ) -> SolverResponse:
        self.calls += 1
        if self.calls == self.at:
            if self.rmtree:
                shutil.rmtree(self.path)
            else:
                self.path.unlink()
        return self.inner.generate(prompt, schema=schema, decoding=decoding)


def _strip(value: Any) -> Any:
    volatile = {"timing", "latency_seconds", "paths", "artifact", "started_at", "elapsed_seconds"}
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in volatile}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


# ---------------------------------------------------------------------------- namespaces


def test_frozen_namespace_set_is_exactly_the_earlier_instruments() -> None:
    assert set(exp.FROZEN_NAMESPACES) == {
        "fitness_v1",
        "fitness_v2",
        "fitness_v3",
        "fitness_v4",
        "fitness_v5",
        "fitness_v6",
        "fitness_v7",
        "model_fitness",
        "game_r_formal_v1_dry_run",
    }


@pytest.mark.parametrize("namespace", exp.FROZEN_NAMESPACES)
def test_frozen_namespaces_are_refused_wherever_they_appear(namespace: str) -> None:
    for path in (
        f"artifacts/cache/{namespace}/abc.json",
        f"experiments/{namespace}/development/result.json",
        Path("/anywhere") / namespace / "y.json",
    ):
        with pytest.raises(exp.FrozenNamespaceRefusal, match="frozen-instrument path"):
            exp.assert_phase8_namespace(path)
        with pytest.raises(ValueError):  # the V7 contract: a ValueError, never a warning
            exp.refuse_frozen_paths("artifacts/ok.json", path)


def test_own_namespaces_pass_and_are_phase8_only() -> None:
    assert set(exp.NAMESPACES) == {"smoke", "dryrun", "calibration", "tournament"}
    for name in exp.NAMESPACES:
        cache = exp.CACHE_NAMESPACES[name]
        artifact = exp.ARTIFACT_NAMESPACES[name]
        assert cache == f"artifacts/cache/game_r_precondition_founder_v1/{name}"
        assert artifact == f"experiments/game_r_precondition_founder_v1/{name}"
        assert exp.assert_phase8_namespace(cache) == cache
        assert exp.refuse_frozen_paths(cache, artifact) == (cache, artifact)
    assert exp.SMOKE_CACHE_SUFFIX == "artifacts/cache/game_r_precondition_founder_v1/smoke"


def test_stage_paths_refuse_a_frozen_root(tmp_path: Path) -> None:
    stage = exp.Stage(exp.StageKind.SMOKE, tmp_path / "fitness_v5")
    with pytest.raises(exp.FrozenNamespaceRefusal):
        _ = stage.cache_root
    with pytest.raises(exp.FrozenNamespaceRefusal):
        exp.run_arms(
            stage,
            _stub(1)[0],
            _control(),
            solver=_solver(),
            counter=StubTokenCounter(),
            budget=CallBudget(10),
            label="x",
        )
    assert not (tmp_path / "fitness_v5").exists()


@pytest.mark.parametrize("kind", ["smoke", "calibration", "tournament"])
def test_each_stage_writes_only_under_its_own_namespace(tmp_path: Path, kind: str) -> None:
    batches = _stub(2, ("S1", "S2"))
    before = _files(tmp_path)
    common: dict[str, Any] = {
        "solver": _solver(),
        "counter": StubTokenCounter(),
        "budget": CallBudget(1000),
    }
    if kind == "smoke":
        payload = exp.run_smoke(tmp_path, batch=batches[0], **common)
    elif kind == "calibration":
        payload = exp.run_calibration(
            tmp_path, strata=["S1", "S2"], families=2, batches=batches, **common
        )
    else:
        payload = exp.run_tournament(
            tmp_path, stratum="S1", families=2, surfaces=TRIO, batch=batches[0], **common
        )
    new = _files(tmp_path) - before
    cache_prefix = exp.CACHE_NAMESPACES[kind]
    artifact_prefix = "artifacts/" + exp.ARTIFACT_NAMESPACES[kind]
    assert new
    assert all(p.startswith(cache_prefix + "/") or p.startswith(artifact_prefix + "/") for p in new)
    assert f"{cache_prefix}/{exp.SENTINEL_NAME}" in new
    assert not any(frozen in p for p in new for frozen in exp.FROZEN_NAMESPACES)
    assert payload["stage_config"]["namespace"] == kind
    assert payload["stage_config"]["runtime_condition"] == "bare"
    assert payload["artifact"]["relative"].startswith(exp.ARTIFACT_NAMESPACES[kind] + "/")
    assert payload["artifact"]["decision"] == "WRITTEN_NEW"
    assert (tmp_path / "artifacts" / payload["artifact"]["relative"]).is_file()


# --------------------------------------------------------------------------------- smoke


def test_smoke_second_invocation_replays_same_condition_reuse_byte_identically(
    tmp_path: Path,
) -> None:
    batch = _stub(2)[0]
    first = exp.run_smoke(
        tmp_path, solver=_solver(), counter=StubTokenCounter(), budget=CallBudget(100), batch=batch
    )
    assert first["passed"] is True
    assert set(first["checks"]) == {
        "served_digest_matches",
        "grammar_parseable_answers",
        "token_counts_exact",
        "no_solver_errors",
        "cache_files_under_smoke_namespace_only",
        "replay_same_condition_reuse",
        "replay_raw_output_identical",
        "prompt_bytes_match_manifest",
        "rotated_follows_base",
        "artifact_path_isolated",
        "sentinel_present",
    }
    assert first["checks"]["served_digest_matches"] == "NOT_APPLICABLE_NO_SERVED_RECORD"
    assert all(
        value == "PASS" for key, value in first["checks"].items() if key != "served_digest_matches"
    )
    assert first["arms"] == ["GRF_L3_JSON_AST", "GRF_L0_STRUCTURED_ENGLISH"]
    assert len(first["rows"]) == 16  # 2 families x [base, rot] x 2 twins x 2 arms
    assert {row["cache_scope"] for row in first["rows"]} == {"FRESH"}
    assert {row["cache_scope"] for row in first["replay_rows"]} == {"SAME_CONDITION_REUSE"}
    assert first["budget"]["spent"] == 16  # the replay leg is free
    assert first["artifact"]["relative"].endswith("/smoke.json")

    second = exp.run_smoke(
        tmp_path, solver=_solver(), counter=StubTokenCounter(), budget=CallBudget(100), batch=batch
    )
    assert second["passed"] is True
    assert {row["cache_scope"] for row in second["rows"]} == {"SAME_CONDITION_REUSE"}
    assert [r["raw_output"] for r in second["rows"]] == [r["raw_output"] for r in first["rows"]]
    assert [r["prompt_hash"] for r in second["rows"]] == [r["prompt_hash"] for r in first["rows"]]
    assert second["budget"]["spent"] == 0
    assert second["artifact"]["decision"] == "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    assert second["artifact"]["relative"].endswith("/smoke-run2.json")
    assert (tmp_path / "artifacts" / first["artifact"]["relative"]).is_file()


def test_smoke_reports_a_served_digest_mismatch_instead_of_hiding_it(tmp_path: Path) -> None:
    payload = exp.run_smoke(
        tmp_path,
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(100),
        batch=_stub(2)[0],
        served={"digest": "not-the-stub-digest"},
    )
    assert payload["checks"]["served_digest_matches"] == "FAIL"
    assert payload["passed"] is False
    assert payload["manifest"]["served"] == {"digest": "not-the-stub-digest"}


# ------------------------------------------------------------------------------ schedule


def test_schedule_places_each_rotated_twin_immediately_after_its_base_family_major() -> None:
    batch = _stub(3)[0]
    scheduled = exp.schedule_items(batch.items)
    assert len(scheduled) == 12
    for index in range(0, 12, 2):
        base, rotated = scheduled[index], scheduled[index + 1]
        assert base.variant in exp.POSITIVE_VARIANTS
        assert rotated.variant == str(ItemVariant.ORDER_ROTATED)
        assert rotated.task_id == f"{base.task_id}#rot1"
        assert rotated.provenance["rotated_from"] == base.task_id
        assert rotated.provenance["shift"] == 1
        assert rotated.family_id == base.family_id
        assert rotated.options == (base.options[1], base.options[0])
        assert rotated.correct_index == (base.correct_index + 1) % 2
        assert rotated.canonical_state is base.canonical_state
    for family in range(3):
        block = scheduled[4 * family : 4 * family + 4]
        assert len({item.family_id for item in block}) == 1
        assert [item.variant for item in block] == [
            "ORIGINAL",
            "ORDER_ROTATED",
            "COUNTERFACTUAL",
            "ORDER_ROTATED",
        ]
    assert exp.schedule_items(batch.items) == scheduled  # deterministic


def test_schedule_refuses_pre_rotated_duplicate_or_non_positive_items() -> None:
    batch = _stub(1)[0]
    with pytest.raises(HarnessRefusal, match="already order-rotated"):
        exp.schedule_items((*batch.items, rotate_options(batch.items[0], 1)))
    destroyed = dataclasses.replace(
        batch.items[0], task_id="destroyed", variant="DESTROYED_ORIGINAL"
    )
    with pytest.raises(HarnessRefusal, match="non-positive"):
        exp.schedule_items((destroyed,))
    with pytest.raises(HarnessRefusal, match="duplicate"):
        exp.schedule_items((batch.items[0], batch.items[0]))


def test_rows_pair_rotated_with_base_through_pairing_key_and_arms_share_one_order(
    tmp_path: Path,
) -> None:
    batch = _stub(2)[0]
    result = exp.run_arms(
        exp.Stage(exp.StageKind.TOURNAMENT, tmp_path),
        batch,
        exp.founder_roster(TRIO),
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(100),
        label="t",
    )
    orders = []
    for rows in result.rows_by_arm.values():
        assert len(rows) == 8
        for index in range(0, 8, 2):
            base, rotated = rows[index], rows[index + 1]
            assert exp.is_base_row(base) and not exp.is_base_row(rotated)
            assert base["pairing_key"] == base["task_id"]
            assert rotated["pairing_key"] == base["task_id"]
            assert rotated["task_id"] == f"{base['task_id']}#rot1"
        orders.append([row["task_id"] for row in rows])
    assert len(orders) == 3 and all(order == orders[0] for order in orders)
    assert list(result.rows_by_arm) == [founder_genome(s).candidate_id for s in TRIO]


def test_progress_lines_go_to_stderr_every_ten_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exp.run_arms(
        exp.Stage(exp.StageKind.TOURNAMENT, tmp_path),
        _stub(3)[0],
        _control(),
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(100),
        label="probe",
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = [line for line in captured.err.splitlines() if line.startswith("[probe]")]
    assert len(lines) == 2
    assert "rows 10/12" in lines[0] and "elapsed" in lines[0] and "eta" in lines[0]
    assert "rows 12/12" in lines[1]


# ------------------------------------------------------------------------------- metrics


def test_pair_statistics_separate_content_invariance_from_letter_anchoring() -> None:
    rows = [
        # same content under a different letter: invariant, not anchored
        _row("t1", "t1", "ORIGINAL", answer="OPTION_A", content="X"),
        _row("t1#rot1", "t1", "ORDER_ROTATED", answer="OPTION_B", content="X"),
        # same letter, different content: anchored, not invariant
        _row("t2", "t2", "COUNTERFACTUAL", answer="OPTION_A", content="Y"),
        _row("t2#rot1", "t2", "ORDER_ROTATED", answer="OPTION_A", content="Z"),
        # invalid base answer: a pair, but neither invariant nor anchored
        _row("t3", "t3", "ORIGINAL", answer=None, content=None, status="RESPONSE_SCHEMA_ERROR"),
        _row("t3#rot1", "t3", "ORDER_ROTATED", answer="OPTION_B", content="X"),
        # orphan rotated row: no base, not a pair
        _row("t4#rot1", "t4", "ORDER_ROTATED", answer="OPTION_B", content="X"),
        # unscored base (transport failure): its rotated twin has no scored partner
        _row("t5", "t5", "ORIGINAL", answer=None, content=None, status="SOLVER_ERROR"),
        _row("t5#rot1", "t5", "ORDER_ROTATED", answer="OPTION_A", content="X"),
    ]
    assert exp.pair_statistics(rows) == {
        "pairs": 3,
        "invariant_pairs": 1,
        "anchored_pairs": 1,
        "both_valid_pairs": 2,
        "position_invariance": pytest.approx(1 / 3),
        "position_anchoring_rate": pytest.approx(1 / 3),
    }
    assert exp.pair_statistics([])["position_invariance"] is None

    report = exp.arm_report(rows, [0.5] * len(rows))
    assert report["candidate_id"] == "GRF_X"
    assert report["rows_total"] == 9 and report["base_rows"] == 4 and report["rotated_rows"] == 5
    assert report["base_rows_scored"] == 3  # t5 is SOLVER_ERROR: unscored, never dropped silently
    assert report["accuracy_base"] == pytest.approx(2 / 3)
    assert report["accuracy_rotated"] == 1.0
    assert report["solver_error_rows"] == 1
    assert report["valid_response_rate"] == pytest.approx(7 / 8)
    assert report["prompt_tokens"] == {"min": 10, "mean": 10.0, "max": 10}
    assert report["latency_seconds"]["fresh_rows"] == 9
    assert report["pairs"]["pairs"] == 3
    assert report["harness_score"]["candidate_id"] == "GRF_X"
    with pytest.raises(HarnessRefusal):
        exp.arm_report([])


# ------------------------------------------------------------------------------ selector


def test_select_stratum_is_argmin_distance_inside_the_band() -> None:
    accuracies = {"P05": 0.95, "P07": 0.78, "P09": 0.70, "P12": 0.55, "P16": None}
    selection = exp.select_stratum(
        accuracies, band=(0.65, 0.80), target=0.725, ladder_order=tuple(pl.LADDER)
    )
    assert selection["selected"] == "P09"
    assert selection["selected_accuracy"] == 0.70
    assert selection["reason"] == "ARGMIN_ABS_DISTANCE_TO_TARGET"
    assert selection["inside_band"] == ["P07", "P09"]
    assert selection["outside_band"] == ["P05", "P12", "P16"]
    assert selection["band"] == [0.65, 0.80] and selection["target"] == 0.725
    assert [r["stratum"] for r in selection["ranking"]] == ["P09", "P07"]
    assert selection["ranking"][0]["distance"] == pytest.approx(0.025)
    assert selection["ladder_order"] == list(pl.LADDER)
    assert selection["stratum_accuracies"] == accuracies


def test_select_stratum_ties_go_to_the_easier_stratum_independently_of_mapping_order() -> None:
    kwargs: dict[str, Any] = {
        "band": (0.65, 0.80),
        "target": 0.725,
        "ladder_order": ("P05", "P07", "P09"),
    }
    # equal distance, symmetric around the target: the higher accuracy is the easier one
    assert exp.select_stratum({"P07": 0.75, "P09": 0.70}, **kwargs)["selected"] == "P07"
    assert exp.select_stratum({"P09": 0.70, "P07": 0.75}, **kwargs)["selected"] == "P07"
    # equal accuracy: the ladder decides, whatever order the caller iterates in
    assert exp.select_stratum({"P09": 0.75, "P07": 0.75}, **kwargs)["selected"] == "P07"
    assert exp.select_stratum({"P07": 0.75, "P09": 0.75}, **kwargs)["selected"] == "P07"
    # a stratum the ladder does not list ranks after every listed one
    assert exp.select_stratum({"X": 0.75, "P09": 0.75}, **kwargs)["selected"] == "P09"
    # without a ladder order the caller's order is the tie-break
    no_ladder = {"band": (0.65, 0.80), "target": 0.725}
    assert exp.select_stratum({"P09": 0.75, "P07": 0.75}, **no_ladder)["selected"] == "P09"
    # band edges are inclusive
    assert exp.select_stratum({"A": 0.65, "B": 0.80}, **no_ladder)["selected"] == "B"


def test_select_stratum_reports_no_stratum_inside_band_and_validates_the_target() -> None:
    selection = exp.select_stratum(
        {"P05": 0.90, "P07": 0.85, "P09": None}, band=(0.65, 0.80), target=0.725
    )
    assert selection["selected"] is None
    assert selection["reason"] == "NO_STRATUM_INSIDE_BAND"
    assert selection["inside_band"] == []
    assert selection["outside_band"] == ["P05", "P07", "P09"]
    assert "ranking" not in selection
    with pytest.raises(ValueError, match="inside band"):
        exp.select_stratum({"P05": 0.7}, band=(0.65, 0.80), target=0.9)


def test_select_stratum_is_a_pure_function_of_its_inputs() -> None:
    accuracies = {"P05": 0.82, "P07": 0.74, "P09": 0.71, "P12": 0.66}
    kwargs: dict[str, Any] = {
        "band": (0.65, 0.80),
        "target": 0.725,
        "ladder_order": tuple(pl.LADDER),
    }
    first = exp.select_stratum(accuracies, **kwargs)
    second = exp.select_stratum(dict(reversed(list(accuracies.items()))), **kwargs)
    assert first["selected"] == second["selected"] == "P07"
    assert first["ranking"] == second["ranking"]
    assert exp.select_stratum(accuracies, **kwargs) == first


# --------------------------------------------------------------------------- guarded write


def test_guarded_write_never_overwrites_without_a_matching_resume(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    relative = exp.ARTIFACT_NAMESPACES["tournament"] + "/tournament-P05.json"
    identity = {"task_hash": "t" * 64, "roster_hash": "r" * 64, "solver_hash": "s" * 64}
    payload = {"manifest": identity, "n": 1}

    first = exp.guarded_write(store, relative, payload, resume=False)
    assert first["decision"] == "WRITTEN_NEW"
    assert first["relative"] == relative
    assert first["existing_identity"] is None
    original = (store.root / relative).read_bytes()

    second = exp.guarded_write(store, relative, {**payload, "n": 2}, resume=False)
    assert second["decision"] == "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    assert second["relative"] == relative.replace(".json", "-run2.json")
    assert second["existing_identity"] == identity
    assert (store.root / relative).read_bytes() == original
    assert json.loads((store.root / second["relative"]).read_text())["n"] == 2

    third = exp.guarded_write(store, relative, {**payload, "n": 3}, resume=False)
    assert third["relative"] == relative.replace(".json", "-run3.json")

    other = {"manifest": {**identity, "task_hash": "x" * 64}, "n": 4}
    fourth = exp.guarded_write(store, relative, other, resume=True)
    assert fourth["decision"] == "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    assert fourth["relative"] == relative.replace(".json", "-run4.json")
    assert (store.root / relative).read_bytes() == original

    fifth = exp.guarded_write(store, relative, {**payload, "n": 5}, resume=True)
    assert fifth["decision"] == "OVERWRITTEN_RESUME_SAME_IDENTITY"
    assert fifth["relative"] == relative
    assert json.loads((store.root / relative).read_text())["n"] == 5

    sixth = exp.guarded_write(store, relative, {"n": 6}, resume=True)  # no identity: no resume
    assert sixth["decision"] == "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    assert sixth["relative"] == relative.replace(".json", "-run5.json")

    with pytest.raises(exp.FrozenNamespaceRefusal):
        exp.guarded_write(store, "experiments/fitness_v7/x.json", payload, resume=False)
    assert exp.manifest_identity({"manifest": {**identity, "solver_hash": ""}}) is None
    assert exp.manifest_identity({}) is None


# ----------------------------------------------------------------------- cache protection


def test_cache_vanished_when_the_sentinel_disappears_mid_run(tmp_path: Path) -> None:
    batch = exp.stub_batch("S1", families=7, level=1)  # 28 rows on one arm
    stage = exp.Stage(exp.StageKind.TOURNAMENT, tmp_path)
    killer = _SentinelKiller(_solver(), stage.cache_root / exp.SENTINEL_NAME, at=3)
    with pytest.raises(exp.CacheVanished, match="sentinel .* vanished"):
        exp.run_arms(
            stage,
            batch,
            _control(),
            solver=killer,
            counter=StubTokenCounter(),
            budget=CallBudget(1000),
            label="t",
        )
    assert killer.calls == exp.SENTINEL_CHECK_EVERY  # stopped at the first periodic check
    assert killer.calls < 28


def test_cache_vanished_when_the_whole_cache_root_is_removed_mid_run(tmp_path: Path) -> None:
    batch = exp.stub_batch("S1", families=7, level=1)
    stage = exp.Stage(exp.StageKind.TOURNAMENT, tmp_path)
    killer = _SentinelKiller(_solver(), stage.cache_root, at=5, rmtree=True)
    with pytest.raises(exp.CacheVanished, match="vanished"):
        exp.run_arms(
            stage,
            batch,
            _control(),
            solver=killer,
            counter=StubTokenCounter(),
            budget=CallBudget(1000),
            label="t",
        )
    assert killer.calls <= exp.SENTINEL_CHECK_EVERY


def test_cache_vanished_is_also_checked_at_stage_end(tmp_path: Path) -> None:
    batch = exp.stub_batch("S1", families=7, level=1)
    stage = exp.Stage(exp.StageKind.TOURNAMENT, tmp_path)
    killer = _SentinelKiller(_solver(), stage.cache_root / exp.SENTINEL_NAME, at=27)
    with pytest.raises(exp.CacheVanished, match="stage end"):
        exp.run_arms(
            stage,
            batch,
            _control(),
            solver=killer,
            counter=StubTokenCounter(),
            budget=CallBudget(1000),
            label="t",
        )
    assert killer.calls == 28


def test_sentinel_is_created_at_stage_start_and_checked_before_any_row(tmp_path: Path) -> None:
    stage = exp.Stage(exp.StageKind.CALIBRATION, tmp_path)
    assert not stage.cache_root.exists()
    sentinel = exp.ensure_sentinel(stage.cache_root)
    assert sentinel == stage.cache_root / exp.SENTINEL_NAME
    assert "Do not delete" in sentinel.read_text(encoding="utf-8")
    exp.assert_sentinel(stage.cache_root)
    sentinel.unlink()
    with pytest.raises(exp.CacheVanished):
        exp.assert_sentinel(stage.cache_root, context="probe")
    shutil.rmtree(stage.cache_root)
    with pytest.raises(exp.CacheVanished, match="cache root"):
        exp.assert_sentinel(stage.cache_root)


def test_wipe_smoke_deletes_only_the_smoke_cache(tmp_path: Path) -> None:
    smoke = tmp_path / exp.CACHE_NAMESPACES["smoke"]
    other = tmp_path / exp.CACHE_NAMESPACES["tournament"]
    for directory in (smoke, other):
        directory.mkdir(parents=True)
        (directory / "row.json").write_text("{}", encoding="utf-8")
        (directory / exp.SENTINEL_NAME).write_text("x", encoding="utf-8")
    artifact = tmp_path / "artifacts" / exp.ARTIFACT_NAMESPACES["smoke"] / "smoke.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")

    record = exp.wipe_smoke_cache(tmp_path)
    assert record["existed"] is True and record["files_removed"] == 2
    assert record["wiped"].endswith(exp.SMOKE_CACHE_SUFFIX)
    assert not smoke.exists()
    assert (other / "row.json").is_file() and (other / exp.SENTINEL_NAME).is_file()
    assert artifact.is_file()  # the smoke ARTIFACT is not a cache and is never wiped

    again = exp.wipe_smoke_cache(tmp_path)
    assert again["existed"] is False and again["files_removed"] == 0

    smoke.symlink_to(other)
    with pytest.raises(exp.SmokeCacheRefusal, match="symlink"):
        exp.wipe_smoke_cache(tmp_path)
    assert (other / "row.json").is_file()


# ---------------------------------------------------------------------------------- Holm


def test_holm_step_down_over_the_baseline_comparisons() -> None:
    comparisons = {
        "GRF_A": {"status": "COMPARED", "mcnemar_exact_p": 0.01},
        "GRF_B": {"status": "COMPARED", "mcnemar_exact_p": 0.04},
        "GRF_C": {"status": "COMPARED", "mcnemar_exact_p": 0.03},
        "GRF_D": {"status": "NO_COMMON_SET", "n": 0},
    }
    holm = exp.holm_baseline_comparisons(comparisons)
    assert holm["alpha"] == 0.05 and holm["key"] == "mcnemar_exact_p"
    assert holm["family_size"] == 3
    assert holm["not_compared"] == ["GRF_D"]
    decisions = holm["decisions"]
    assert decisions["GRF_A"]["holm_threshold"] == pytest.approx(0.05 / 3)
    assert decisions["GRF_A"]["holm_reject"] is True
    assert decisions["GRF_C"]["holm_threshold"] == pytest.approx(0.05 / 2)
    assert decisions["GRF_C"]["holm_reject"] is False  # 0.03 > 0.025
    assert decisions["GRF_B"]["holm_threshold"] == pytest.approx(0.05)
    assert decisions["GRF_B"]["holm_reject"] is False  # step-down stopped at GRF_C
    assert holm["rejected"] == ["GRF_A"]
    assert "holm_reject" not in comparisons["GRF_A"]  # inputs are not mutated

    all_in = exp.holm_baseline_comparisons(
        {
            "A": {"status": "COMPARED", "mcnemar_exact_p": 0.001},
            "B": {"status": "COMPARED", "mcnemar_exact_p": 0.02},
        }
    )
    assert all_in["rejected"] == ["A", "B"]
    empty = exp.holm_baseline_comparisons({})
    assert empty["family_size"] == 0 and empty["rejected"] == [] and empty["decisions"] == {}


# ------------------------------------------------------------------------------ tournament


def test_tournament_payload_has_all_pairs_holm_and_a_manifest_with_per_arm_prompt_hashes(
    tmp_path: Path,
) -> None:
    batch = _stub(3)[0]
    payload = exp.run_tournament(
        tmp_path,
        stratum="S1",
        families=3,
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        surfaces=TRIO,
        batch=batch,
    )
    arms = ["GRF_L3_JSON_AST", "GRF_L1_CURRENT_HML", "GRF_L5_COMPACT_SYMBOLIC"]
    assert payload["arms"] == arms
    assert payload["baseline_candidate"] == "GRF_L3_JSON_AST"
    assert payload["stratum"] == "S1" and payload["families"] == 3
    assert set(payload["comparisons_vs_baseline"]) == {
        "GRF_L1_CURRENT_HML",
        "GRF_L5_COMPACT_SYMBOLIC",
    }
    assert set(payload["comparisons_all_pairs"]) == {
        "GRF_L1_CURRENT_HML|GRF_L3_JSON_AST",
        "GRF_L1_CURRENT_HML|GRF_L5_COMPACT_SYMBOLIC",
        "GRF_L3_JSON_AST|GRF_L5_COMPACT_SYMBOLIC",
    }
    for comparison in (
        *payload["comparisons_vs_baseline"].values(),
        *payload["comparisons_all_pairs"].values(),
    ):
        assert comparison["status"] == "COMPARED"
        assert comparison["n"] == 6  # base rows only: 3 families x 2 twins
        assert {"mcnemar_exact_p", "ci95", "delta", "n10", "n01"} <= set(comparison)
    assert payload["holm"]["family_size"] == 2
    assert set(payload["holm"]["decisions"]) == set(payload["comparisons_vs_baseline"])
    assert "base rows" in payload["primary_metric"]

    manifest = payload["manifest"]
    assert manifest["experiment_version"] == exp.EXPERIMENT_VERSION
    assert manifest["harness_version"] == HARNESS_VERSION
    assert manifest["environment_version"] == batch.environment_version
    assert manifest["mechanism"] == batch.mechanism
    assert manifest["stratum"] == "S1" and manifest["pool"] == "STUB"
    assert manifest["n_items_positive"] == 6 and manifest["n_rows_per_arm"] == 12
    assert manifest["ladder_params"] == {"stub_level": 1}
    assert manifest["roster"]["candidates"] == arms
    assert manifest["roster_hash"] == exp.roster_hash(TRIO)
    assert manifest["solver"] == {
        "name": "stub-solver",
        "digest": StubSolver().digest,
        "revision": "stub-revision-v1",
    }
    assert manifest["decoding"] == frozen_decoding()
    assert manifest["decoding_hash"] == decoding_hash(frozen_decoding(), response_schema(2))
    assert manifest["guide_policy"] == "SHARED_CONSTANT"
    assert (
        manifest["context"]["num_ctx"] == 32768 and manifest["context"]["max_output_tokens"] == 64
    )
    assert manifest["tokenizer"] == {"id": "stub-token-counter-v1", "exact": True}
    assert len(manifest["task_hash"]) == 64 and len(manifest["solver_hash"]) == 64
    assert len(manifest["tasks"]) == 12
    for task in manifest["tasks"]:
        assert {"task_id", "qualified_task_id", "pairing_key", "state_hash", "variant"} <= set(task)
        assert "question" not in task and "provenance" not in task

    by_task = {item.task_id: item for item in exp.schedule_items(batch.items)}
    assert len(by_task) == 12
    for task_id, item in by_task.items():
        qualified = qualified_task_id(batch.environment_version, batch.mechanism, task_id)
        hashes = manifest["prompt_hashes"][qualified]
        assert set(hashes) == set(arms)
        for genome in exp.founder_roster(TRIO):
            prompt = build_prompt(genome, item, guide_policy=SyntaxGuidePolicy.SHARED_CONSTANT)
            assert hashes[genome.candidate_id] == prompt_bytes_hash(prompt)
    for arm, rows in payload["rows"].items():
        assert len(rows) == 12
        for row in rows:
            assert manifest["prompt_hashes"][row["task_id"]][arm] == row["prompt_hash"]
        report = payload["arm_reports"][arm]
        assert report["base_rows"] == 6 and report["rotated_rows"] == 6
        assert report["pairs"]["pairs"] == 6
        assert 0.0 <= report["accuracy_base"] <= 1.0
        assert report["harness_score"]["candidate_id"] == arm
        assert report["cache_scopes"] == {"FRESH": 12}
    assert len(payload["parity"]) == 12
    assert all(p["checks"]["rendered_bytes_distinct"] == "PASS" for p in payload["parity"])
    assert payload["budget"]["spent"] == 36
    assert (
        payload["artifact"]["relative"]
        == exp.ARTIFACT_NAMESPACES["tournament"] + "/tournament-S1.json"
    )


def test_tournament_refuses_a_roster_without_the_baseline_or_a_foreign_batch(
    tmp_path: Path,
) -> None:
    common: dict[str, Any] = {
        "solver": _solver(),
        "counter": StubTokenCounter(),
        "budget": CallBudget(10),
        "batch": _stub(1)[0],
    }
    with pytest.raises(HarnessRefusal, match="baseline"):
        exp.run_tournament(
            tmp_path, stratum="S1", families=1, surfaces=("L1_CURRENT_HML", "L2_SEXPR"), **common
        )
    with pytest.raises(HarnessRefusal, match="stratum"):
        exp.run_tournament(tmp_path, stratum="S2", families=1, surfaces=TRIO, **common)
    assert not (tmp_path / "artifacts").exists()


def test_budget_is_a_hard_ceiling_and_a_resumed_run_pays_only_for_the_rest(tmp_path: Path) -> None:
    batch = _stub(2)[0]
    with pytest.raises(BudgetExceeded):
        exp.run_tournament(
            tmp_path,
            stratum="S1",
            families=2,
            solver=_solver(),
            counter=StubTokenCounter(),
            budget=CallBudget(3),
            surfaces=("L3_JSON_AST",),
            batch=batch,
        )
    payload = exp.run_tournament(
        tmp_path,
        stratum="S1",
        families=2,
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(100),
        surfaces=("L3_JSON_AST",),
        batch=batch,
        resume=True,
    )
    assert payload["budget"]["spent"] == 5
    assert payload["arm_reports"]["GRF_L3_JSON_AST"]["cache_scopes"] == {
        "FRESH": 5,
        "SAME_CONDITION_REUSE": 3,
    }
    assert payload["comparisons_vs_baseline"] == {} and payload["comparisons_all_pairs"] == {}
    assert payload["holm"]["family_size"] == 0


# ----------------------------------------------------------------------------- calibration


def test_calibration_runs_the_control_arm_only_on_positives_and_records_band_and_target(
    tmp_path: Path,
) -> None:
    batches = _stub(3, ("S1", "S2"))
    payload = exp.run_calibration(
        tmp_path,
        strata=["S1", "S2"],
        families=3,
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        batches=batches,
        band=(0.3, 0.9),
        target=0.6,
    )
    assert payload["control_arm"] == "GRF_L3_JSON_AST"
    assert payload["band"] == [0.3, 0.9] and payload["target"] == 0.6
    assert payload["strata"] == ["S1", "S2"]
    assert list(payload["per_stratum"]) == ["S1", "S2"]
    for stratum, record in payload["per_stratum"].items():
        rows = record["rows"]
        assert len(rows) == 12
        assert {row["candidate_id"] for row in rows} == {"GRF_L3_JSON_AST"}
        assert {row["variant"] for row in rows} == {"ORIGINAL", "COUNTERFACTUAL", "ORDER_ROTATED"}
        arm = record["arm"]
        assert {
            "accuracy_base",
            "accuracy_rotated",
            "pairs",
            "prompt_tokens",
            "latency_seconds",
            "cache_scopes",
            "status_counts",
        } <= set(arm)
        assert arm["base_rows"] == 6 and arm["rotated_rows"] == 6 and arm["pairs"]["pairs"] == 6
        assert (
            arm["prompt_tokens"]["min"]
            <= arm["prompt_tokens"]["mean"]
            <= arm["prompt_tokens"]["max"]
        )
        assert record["manifest"]["stratum"] == stratum
        assert record["manifest"]["roster"]["candidates"] == ["GRF_L3_JSON_AST"]
        assert all(
            p["checks"]["surface_information_identical"] == "NOT_APPLICABLE_SINGLE_ARM"
            for p in record["parity"]
        )
    assert payload["stratum_accuracies"] == {
        s: payload["per_stratum"][s]["arm"]["accuracy_base"] for s in ("S1", "S2")
    }
    selection = payload["selection"]
    assert selection["band"] == [0.3, 0.9] and selection["target"] == 0.6
    assert selection["ladder_order"] == list(pl.LADDER)  # the real ladder is present
    assert selection["selected"] in {"S1", "S2", None}
    assert payload["manifest"]["roster_hash"] == exp.roster_hash(("L3_JSON_AST",))
    assert payload["manifest"]["strata_task_hashes"].keys() == {"S1", "S2"}
    assert payload["budget"]["spent"] == 24
    assert payload["artifact"]["relative"].endswith("/calibration-S1-S2.json")

    with pytest.raises(HarnessRefusal, match="do not match"):
        exp.run_calibration(
            tmp_path,
            strata=["S2", "S1"],
            families=3,
            solver=_solver(),
            counter=StubTokenCounter(),
            budget=CallBudget(10),
            batches=batches,
        )


# ------------------------------------------------------------------------------- ladder


def test_load_batch_uses_the_real_ladder_and_binds_the_batch_to_its_stratum() -> None:
    batch = exp.load_batch("P05", pool="SMOKE", families=2)
    assert batch.environment_version == pl.ENVIRONMENT_VERSION
    assert batch.mechanism == pl.MECHANISM
    assert batch.pool == "SMOKE" and batch.stratum == "P05" and batch.families == 2
    assert [item.variant for item in batch.items] == ["ORIGINAL", "COUNTERFACTUAL"] * 2
    assert all(item.provenance["stratum"] == "P05" for item in batch.items)
    assert batch.excluded_variants == {}
    assert batch.ladder_params == {**pl.LADDER["P05"].to_dict(), "start": 0}
    record = batch.to_dict()
    assert record["n_items_positive"] == 4 and len(record["family_ids"]) == 2
    offset = exp.load_batch("P05", pool="SMOKE", families=1, start=1)
    assert offset.items[0].family_id == batch.items[2].family_id
    assert offset.ladder_params["start"] == 1
    with pytest.raises(ValueError, match="unknown stratum"):
        exp.load_batch("P99", pool="SMOKE", families=1)
    assert exp.ladder_order() == tuple(pl.LADDER)
    explicit = exp.load_batch("P05_EXPLICIT", pool="SMOKE", families=1)
    assert {item.level for item in explicit.items} == {0}
    assert {item.provenance["stratum"] for item in explicit.items} == {"P05_EXPLICIT"}


def test_positive_items_keeps_the_twins_and_counts_everything_else() -> None:
    family = pl.build_family("P05", pl.Pool.SMOKE, 0)
    original, counterfactual = family.items()
    items = (
        original,
        counterfactual,
        family.destroyed_item(0),
        family.destroyed_item(1),
        rotate_options(original, 1),
    )
    kept, excluded = exp.positive_items(items)
    assert [item.variant for item in kept] == ["ORIGINAL", "COUNTERFACTUAL"]
    assert excluded == {
        "DESTROYED_COUNTERFACTUAL": 1,
        "DESTROYED_ORIGINAL": 1,
        "ORDER_ROTATED": 1,
    }


def test_full_founder_roster_passes_parity_on_ladder_items(tmp_path: Path) -> None:
    batch = exp.load_batch("P05", pool="SMOKE", families=1)
    result = exp.run_arms(
        exp.Stage(exp.StageKind.TOURNAMENT, tmp_path, dry_run=True),
        batch,
        exp.founder_roster(),
        solver=_solver(),
        counter=StubTokenCounter(),
        budget=CallBudget(100),
        label="roster",
    )
    assert len(result.parity) == 4
    for report in result.parity:
        assert set(report["prompt_hashes"]) == set(exp.roster_record()["candidates"])
        assert report["checks"]["rendered_bytes_distinct"] == "PASS"
        assert report["checks"]["option_content_and_order_identical"] == "PASS"
    assert list(result.rows_by_arm) == exp.roster_record()["candidates"]


# --------------------------------------------------------------------------------- roster


def test_roster_is_the_founder_five_with_the_json_ast_baseline() -> None:
    assert exp.FOUNDER_SURFACES == (
        "L3_JSON_AST",
        "L0_STRUCTURED_ENGLISH",
        "L1_CURRENT_HML",
        "L2_SEXPR",
        "L5_COMPACT_SYMBOLIC",
    )
    assert exp.BASELINE_SURFACE == "L3_JSON_AST"
    roster = exp.founder_roster()
    assert [g.candidate_id for g in roster] == [
        founder_genome(s).candidate_id for s in exp.FOUNDER_SURFACES
    ]
    assert roster[0].candidate_id == exp.baseline_candidate_id() == "GRF_L3_JSON_AST"
    record = exp.roster_record()
    assert record["baseline_candidate"] == "GRF_L3_JSON_AST"
    assert record["guide_policy"] == "SHARED_CONSTANT"
    assert set(record["genome_hashes"]) == set(record["candidates"])
    assert len(exp.roster_hash()) == 64
    assert exp.roster_hash() == exp.roster_hash(exp.FOUNDER_SURFACES)
    assert exp.roster_hash(("L3_JSON_AST",)) != exp.roster_hash()
    with pytest.raises(ValueError, match="duplicate"):
        exp.founder_roster(("L3_JSON_AST", "L3_JSON_AST"))
    assert exp.GUIDE_POLICY is SyntaxGuidePolicy.SHARED_CONSTANT
    assert exp.CONTEXT_BUDGET.num_ctx == 32768
    assert exp.CONTEXT_BUDGET.max_output_tokens == 64
    assert exp.CONTEXT_BUDGET.prompt_token_limit == 32448
    assert exp.EXPERIMENT_VERSION == "arena-game-r-precondition-founder-v1.0.0"


def test_stage_run_config_pins_frozen_decoding_and_the_shared_guide(tmp_path: Path) -> None:
    stage = exp.Stage(exp.StageKind.TOURNAMENT, tmp_path)
    config = stage.run_config()
    assert config.decoding == frozen_decoding()
    assert config.context == exp.CONTEXT_BUDGET
    assert config.guide_policy is SyntaxGuidePolicy.SHARED_CONSTANT
    assert config.runtime_condition == "bare"
    assert config.experiment_version == exp.EXPERIMENT_VERSION
    assert config.cache_root == tmp_path / exp.CACHE_NAMESPACES["tournament"]
    assert stage.artifact_relpath("x") == exp.ARTIFACT_NAMESPACES["tournament"] + "/x.json"
    dry = exp.Stage(exp.StageKind.TOURNAMENT, tmp_path, dry_run=True)
    assert dry.namespace == "dryrun"
    assert dry.runtime_condition == "dryrun-stub"
    assert dry.cache_root == tmp_path / exp.CACHE_NAMESPACES["dryrun"]
    assert dry.to_dict()["cache_namespace"] == exp.CACHE_NAMESPACES["dryrun"]
    assert "urlopen" not in MODULE_SOURCE and "Request(" not in MODULE_SOURCE


# ------------------------------------------------------------------------------------ CLI


@pytest.mark.parametrize(
    "argv",
    [
        ["--live", "--smoke"],
        ["--confirm-model-calls", "--smoke"],
        ["--live", "--confirm-model-calls", "--dry-run", "--smoke"],
        ["--smoke"],
        ["--live", "--confirm-model-calls"],
        ["--live", "--confirm-model-calls", "--smoke"],  # no --budget
        ["--live", "--confirm-model-calls", "--calibrate", "--budget", "1"],  # no --strata
        ["--live", "--confirm-model-calls", "--tournament", "--budget", "1"],  # no --stratum
        ["--dry-run", "--smoke", "--tournament"],
    ],
)
def test_cli_refuses_incomplete_live_or_ambiguous_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    def never(stage: Any) -> Any:
        raise AssertionError("_live_wiring must not be reached")

    monkeypatch.setattr(exp, "_live_wiring", never)
    with pytest.raises(SystemExit) as info:
        exp.main([*argv, "--root", str(tmp_path)])
    assert info.value.code == 2
    assert _files(tmp_path) == set()


def test_cli_reaches_live_wiring_only_with_both_flags_and_a_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Reached(Exception):
        pass

    seen: list[exp.Stage] = []

    def marker(stage: exp.Stage) -> Any:
        seen.append(stage)
        raise Reached

    monkeypatch.setattr(exp, "_live_wiring", marker)
    with pytest.raises(Reached):
        exp.main(
            ["--live", "--confirm-model-calls", "--smoke", "--budget", "1", "--root", str(tmp_path)]
        )
    assert seen[0].kind is exp.StageKind.SMOKE and seen[0].dry_run is False
    assert _files(tmp_path) == set()


def test_cli_wipe_smoke_alone_touches_only_the_smoke_cache(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    smoke = tmp_path / exp.CACHE_NAMESPACES["smoke"]
    smoke.mkdir(parents=True)
    (smoke / "row.json").write_text("{}", encoding="utf-8")
    assert exp.main(["--wipe-smoke", "--root", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["wipe_smoke"]["files_removed"] == 1
    assert not smoke.exists()


# --------------------------------------------------------------------------------- dry run


def test_dry_run_is_deterministic_and_stays_inside_the_dryrun_namespace(tmp_path: Path) -> None:
    first = exp.run_dry_run(tmp_path / "a", families=2)
    second = exp.run_dry_run(tmp_path / "b", families=2)
    assert _strip(first) == _strip(second)
    assert first["stage"] == "dryrun"
    assert first["smoke"]["passed"] is True
    for stage in ("smoke", "calibration", "tournament"):
        assert first[stage]["stage_config"]["namespace"] == "dryrun"
        assert first[stage]["stage_config"]["runtime_condition"] == "dryrun-stub"
        assert first[stage]["artifact"]["decision"] == "WRITTEN_NEW"
    assert first["calibration"]["strata"] == list(exp.DRY_RUN_STRATA)
    assert first["tournament"]["stratum"] == exp.DRY_RUN_STRATA[0]
    assert first["tournament"]["arms"] == exp.roster_record()["candidates"]
    assert first["tournament"]["manifest"]["environment_version"] == pl.ENVIRONMENT_VERSION
    files = _files(tmp_path / "a")
    cache_prefix = exp.CACHE_NAMESPACES["dryrun"] + "/"
    artifact_prefix = "artifacts/" + exp.ARTIFACT_NAMESPACES["dryrun"] + "/"
    assert files and all(p.startswith(cache_prefix) or p.startswith(artifact_prefix) for p in files)
    # a second dry run on the SAME root replays every row and versions its artifacts
    third = exp.run_dry_run(tmp_path / "a", families=2)
    replayed = [row for rows in third["tournament"]["rows"].values() for row in rows]
    assert replayed and all(row["cache_scope"] == "SAME_CONDITION_REUSE" for row in replayed)
    assert [r["raw_output"] for r in replayed] == [
        r["raw_output"] for rows in first["tournament"]["rows"].values() for r in rows
    ]
    assert third["tournament"]["artifact"]["decision"] == "REFUSED_OVERWRITE_VERSIONED_SIBLING"
    assert third["tournament"]["budget"]["spent"] == 0


def test_cli_dry_run_prints_a_compact_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert exp.main(["--dry-run", "--root", str(tmp_path), "--families", "2"]) == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert set(summary) == {"stage", "smoke", "calibration", "tournament"}
    assert summary["stage"] == "dryrun"
    assert summary["smoke"]["passed"] is True
    assert summary["smoke"]["rows"] == 16
    assert set(summary["calibration"]["per_stratum"]) == set(exp.DRY_RUN_STRATA)
    assert set(summary["tournament"]["arms"]) == set(exp.roster_record()["candidates"])
    for arm in summary["tournament"]["arms"].values():
        assert {
            "accuracy_base",
            "accuracy_rotated",
            "position_invariance",
            "position_anchoring_rate",
        } <= set(arm)
    assert "rows" in captured.err  # progress lines
