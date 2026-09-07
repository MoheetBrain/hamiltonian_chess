"""Offline tests for the V7 instrument.

Nothing here makes a model call.  ``test_dry_run_makes_no_network_call`` proves it by poisoning
both modules' ``urlopen`` for the duration of a full development run.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from arena.canonical.schema import stable_hash
from arena.experiments import fitness_v5 as v5
from arena.experiments import fitness_v7 as v7
from arena.experiments.fitness_v5 import POSITIVE_VARIANTS

PROVENANCE_KEYS = {
    "cache_scope",
    "cache_hit",
    "cache_scopes",
    "cache_scope_totals",
    "fresh_calls_made",
    "latency_seconds",
}


def _strip_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_provenance(v) for k, v in value.items() if k not in PROVENANCE_KEYS}
    if isinstance(value, list):
        return [_strip_provenance(v) for v in value]
    return value


@pytest.fixture(scope="module")
def dev_pool() -> tuple[v5.V5Probe, ...]:
    return v5.build_dev_pool(Path.cwd())


@pytest.fixture(scope="module")
def dry_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("v7-dry")
    payload = v7.run_development(root, v7.STUB_SOLVER, bare=True, dry_run=True)
    return root, payload


# --------------------------------------------------------------- 1. derived frontier target


def test_frontier_target_is_derived_from_the_gate_arithmetic() -> None:
    frontier = v7.derive_frontier()
    assert frontier["destroyed_expected"] == pytest.approx(0.50)
    assert frontier["gap_min"] == pytest.approx(0.20)
    assert frontier["window_low"] == pytest.approx(0.70)
    assert frontier["window_high"] == pytest.approx(0.85)
    assert frontier["frontier_target"] == pytest.approx(0.775)
    # The whole point: the target is the midpoint of the window its own gates define.
    assert frontier["frontier_target"] == pytest.approx(
        (frontier["window_low"] + frontier["window_high"]) / 2
    )


def test_frontier_target_lies_strictly_inside_the_qualifying_window() -> None:
    frontier = v7.derive_frontier()
    assert frontier["window_low"] < frontier["frontier_target"] < frontier["window_high"]
    assert v7.QUALIFICATION_RULE_V7["frontier_target"] == v7.FRONTIER_TARGET
    assert v7.QUALIFICATION_RULE_V7["effective_qualifying_window"] == [
        frontier["window_low"],
        frontier["window_high"],
    ]


@pytest.mark.parametrize("gap_min", [0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
def test_target_moves_automatically_when_gap_min_moves(gap_min: float) -> None:
    frontier = v7.derive_frontier(gap_min=gap_min)
    assert frontier["window_low"] == pytest.approx(0.50 + gap_min)
    assert frontier["frontier_target"] == pytest.approx((0.50 + gap_min + 0.85) / 2)
    # Never again stranded below its own floor, at any gap threshold.
    assert frontier["window_low"] < frontier["frontier_target"] < frontier["window_high"]


def test_raising_gap_min_strictly_raises_the_target() -> None:
    targets = [v7.derive_frontier(gap_min=g)["frontier_target"] for g in (0.10, 0.20, 0.30)]
    assert targets == sorted(targets)
    assert len(set(targets)) == 3


def test_v5s_stranded_constant_is_reproduced_and_is_outside_the_window() -> None:
    """The defect V7 exists to fix, stated as a test rather than as prose."""

    frontier = v7.derive_frontier()
    assert float(v5.QUALIFICATION_RULE["frontier_target"]) == 0.625
    assert not frontier["window_low"] <= 0.625 <= frontier["window_high"]
    assert frontier["window_low"] - 0.625 == pytest.approx(0.075)


def test_an_empty_qualifying_window_is_refused_rather_than_silently_used() -> None:
    with pytest.raises(ValueError, match="empty qualifying window"):
        v7.derive_frontier(gap_min=0.40)


def test_v7_selects_a_qualifiable_level_where_v5_selected_an_unqualifiable_one() -> None:
    ladder = {0: 1.000, 1: 0.833, 2: 0.792, 3: 0.625}
    assert v5.select_frontier_level(ladder)["selected_level"] == 3
    selection = v7.select_frontier_level(ladder)
    assert selection["selected_level"] == 2
    assert selection["candidate_inside_qualifying_window"] is True


def test_selection_ties_go_to_the_lower_level_and_band_edges_void() -> None:
    tie = {0: 1.0, 1: 0.70, 2: 0.85, 3: 0.50}
    assert v7.select_frontier_level(tie)["selected_level"] == 1
    assert v7.select_frontier_level({0: 1.0, 1: 0.95, 2: 0.99})["verdict"] == "VOID_CEILING"
    assert v7.select_frontier_level({0: 1.0, 1: 0.20, 2: 0.10})["verdict"] == "VOID_FLOOR"
    assert v7.select_frontier_level({0: 0.5, 1: 0.8})["verdict"] == "VOID_INSTRUMENT_LIMIT"
    assert v7.select_frontier_level({0: 1.0})["verdict"] == "VOID_INSTRUMENT_LIMIT"


# ----------------------------------------------------------------------- 2. the dead gate


def test_the_dead_destroyed_ceiling_gate_is_removed() -> None:
    assert "negative_target_accuracy_max" in v5.QUALIFICATION_RULE
    assert "negative_target_accuracy_max" not in v7.QUALIFICATION_RULE_V7
    assert v7.QUALIFICATION_RULE_V7["dropped_gate"]["name"] == "negative_target_accuracy_max"


def test_negative_collapse_now_reads_only_the_gap() -> None:
    """Same gap, different destroyed accuracy: V7 cannot distinguish them, by design."""

    audit = {"best_shortcut_accuracy": 0.5, "best_shortcut_feature": "always_first_option"}
    verdicts = set()
    for destroyed in (0.30, 0.50, 0.59, 0.61, 0.70):
        summary = _summary(positive=destroyed + 0.25, destroyed=destroyed)
        verdicts.add(v7.qualify_mechanism(summary, audit, 1.0)["checks"]["negative_collapse"])
    assert verdicts == {"PASS"}
    tight = _summary(positive=0.60, destroyed=0.50)
    assert (
        v7.qualify_mechanism(tight, audit, 1.0)["checks"]["negative_collapse"]
        == "VOID_NEGATIVE_CONTROL"
    )


def _summary(*, positive: float, destroyed: float = 0.5, **overrides: Any) -> dict[str, Any]:
    summary = {
        "positive_accuracy": positive,
        "negative_target_accuracy": destroyed,
        "positive_negative_gap": positive - destroyed,
        "valid_response_rate": 1.0,
        "context_truncated_rows": 0,
        "positive_examples": 24,
        "largest_answer_share": 0.55,
        "position_invariance": 0.90,
    }
    summary.update(overrides)
    return summary


# ------------------------------------------------------------ 3. per-level shortcut audit


def test_shortcut_audit_is_populated_for_every_level_of_every_mechanism(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    table = v7.per_level_shortcut_audit(dev_pool)
    assert set(table) == set(v5.MECHANISMS)
    for mechanism, levels in table.items():
        assert set(levels) == {"0", "1", "2", "3"}, mechanism
        for entry in levels.values():
            assert entry["items"] == 24
            assert entry["best_shortcut_feature"] in entry["scores"]
            assert 0.5 <= entry["best_shortcut_accuracy"] <= 1.0
            assert entry["status"] in {"CLEAN", "LEAKS"}


def test_per_level_audit_reuses_v5s_implementation_verbatim(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    table = v7.per_level_shortcut_audit(dev_pool)
    for mechanism in v5.MECHANISMS:
        for level in range(4):
            cell = [p for p in dev_pool if p.mechanism == mechanism and p.level == level]
            reference = v5.shortcut_audit(tuple(cell))
            entry = table[mechanism][str(level)]
            assert entry["best_shortcut_accuracy"] == reference["worst_score"]
            assert entry["best_shortcut_feature"] == reference["worst_rule"]
            assert entry["scores"] == reference["scores"]


def test_off_frontier_shortcut_exposure_is_real_on_this_probe_bank(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    """V5 measured only the frontier. These are the levels it never looked at."""

    table = v7.per_level_shortcut_audit(dev_pool)["formal_expression_depth"]
    assert table["1"]["best_shortcut_feature"] == "first_mentioned_in_state"
    assert table["1"]["best_shortcut_accuracy"] == pytest.approx(1.0)
    assert table["2"]["best_shortcut_accuracy"] == pytest.approx(0.8333, abs=1e-3)
    assert table["3"]["best_shortcut_accuracy"] == pytest.approx(0.9167, abs=1e-3)
    assert {table[str(level)]["status"] for level in (1, 2, 3)} == {"LEAKS"}


def test_shortcut_audit_costs_no_model_call(
    monkeypatch: pytest.MonkeyPatch, dev_pool: tuple[v5.V5Probe, ...]
) -> None:
    def explode(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the shortcut audit must be a pure probe-bank property")

    monkeypatch.setattr(v7, "urlopen", explode)
    monkeypatch.setattr(v5, "urlopen", explode)
    assert v7.per_level_shortcut_audit(dev_pool)


# ------------------------------------------------------------------ 4. the VOID_SHORTCUT gate


def test_shortcut_margin_gate_boundary() -> None:
    clean = {"best_shortcut_accuracy": 0.60, "best_shortcut_feature": "more_frequent_in_state"}
    exactly = v7.qualify_mechanism(_summary(positive=0.70), clean, 1.0)
    assert exactly["shortcut_margin_observed"] == pytest.approx(0.10)
    assert exactly["checks"]["shortcut_margin"] == "PASS"

    short = v7.qualify_mechanism(_summary(positive=0.6999), clean, 1.0)
    assert short["checks"]["shortcut_margin"] == "VOID_SHORTCUT"
    assert short["qualified"] is False

    inside = v7.qualify_mechanism(_summary(positive=0.75), clean, 1.0)
    assert inside["verdict"] == "QUALIFIED"
    assert inside["qualified"] is True
    assert inside["all_failures"] == []


def test_the_inherited_gap_gate_keeps_v5s_exact_comparison_float_edge_included() -> None:
    """Documented, not repaired: V7 changes only the gates it owns.

    ``0.70 - 0.50 == 0.19999999999999996`` in IEEE-754, so the inherited gap gate makes the
    effective window half-open at its floor.  It is unreachable on real data -- positive
    accuracy is k/24, k/48 or k/72 and none of those is exactly 0.70 -- but the integrator
    should know the edge exists rather than discover it in a run.
    """

    representation_gap = 0.70 - 0.50
    assert representation_gap < float(v5.QUALIFICATION_RULE["positive_negative_gap_min"])
    audit = {"best_shortcut_accuracy": 0.50, "best_shortcut_feature": "always_first_option"}
    at_floor = v7.qualify_mechanism(_summary(positive=0.70, destroyed=0.50), audit, 1.0)
    assert at_floor["checks"]["negative_collapse"] == "VOID_NEGATIVE_CONTROL"
    assert not any(abs(k / n - 0.70) < 1e-12 for n in (24, 48, 72) for k in range(n + 1)), (
        "if a representable accuracy ever equals 0.70 exactly this edge becomes reachable"
    )


def test_the_margin_gate_epsilon_cannot_change_a_real_decision() -> None:
    """0.70 - 0.60 is 0.09999999999999998 in IEEE-754. The tolerance fixes that and nothing else."""

    representation_margin = 0.70 - 0.60  # the artefact this guards against
    assert representation_margin < v7.SHORTCUT_MARGIN
    resolution_floor = 1 / 72  # accuracies are k/24, k/48 or k/72
    assert resolution_floor / 1e6 > v7.GATE_EPSILON
    audit = {"best_shortcut_accuracy": 0.60, "best_shortcut_feature": "always_first_option"}
    # One representable step below the threshold still voids.
    below = v7.qualify_mechanism(_summary(positive=0.70 - resolution_floor), audit, 1.0)
    assert below["checks"]["shortcut_margin"] == "VOID_SHORTCUT"


def test_void_shortcut_fires_when_a_shortcut_beats_the_solver() -> None:
    leaky = {"best_shortcut_accuracy": 0.8333, "best_shortcut_feature": "first_mentioned_in_state"}
    result = v7.qualify_mechanism(_summary(positive=0.7917), leaky, 1.0)
    assert result["shortcut_margin_observed"] < 0
    assert result["verdict"] == "VOID_SHORTCUT"
    assert result["all_failures"] == ["shortcut_absolute", "shortcut_margin"]


def test_absolute_shortcut_gate_still_fires_even_with_a_wide_margin() -> None:
    audit = {"best_shortcut_accuracy": 0.80, "best_shortcut_feature": "more_frequent_in_state"}
    result = v7.qualify_mechanism(_summary(positive=0.95), audit, 1.0)
    assert result["shortcut_margin_observed"] == pytest.approx(0.15)
    assert result["checks"]["shortcut_margin"] == "PASS"
    assert result["checks"]["shortcut_absolute"] == "VOID_SHORTCUT"
    assert result["verdict"] == "VOID_SHORTCUT"


def test_a_solver_that_answers_by_the_shortcut_voids(
    tmp_path: Path, dev_pool: tuple[v5.V5Probe, ...]
) -> None:
    """End to end on the real bank: a shortcut-following solver cannot qualify L1."""

    cell = [p for p in dev_pool if p.mechanism == "formal_expression_depth" and p.level == 1]
    profile = v7.StubProfile(accuracy={}, shortcut_feature="first_mentioned_in_state")
    result = v7.evaluate(
        tmp_path,
        v5.equal_information_genome(),
        cell,
        v7.stub_solver(dev_pool, profile),
        solver=v7.STUB_SOLVER,
        bare=True,
        solver_kind=v7.SolverKind.STUB,
        model_template_hash=stable_hash(""),
        dry_run=True,
    )
    audit = v7.per_level_shortcut_audit(dev_pool)["formal_expression_depth"]["1"]
    assert result["summary"]["positive_accuracy"] == pytest.approx(1.0)
    assert audit["best_shortcut_accuracy"] == pytest.approx(1.0)
    verdict = v7.qualify_mechanism(result["summary"], audit, 1.0)
    assert verdict["shortcut_margin_observed"] == pytest.approx(0.0)
    assert verdict["verdict"] == "VOID_SHORTCUT"


# ------------------------------------------------------------------- 5. cache identity


def _identity(dev_pool: tuple[v5.V5Probe, ...], **kwargs: Any) -> dict[str, Any]:
    probe = dev_pool[0]
    genome = v5.equal_information_genome()
    defaults: dict[str, Any] = {
        "solver": v5.SOLVERS["qwen38-rvn"],
        "bare": True,
        "solver_kind": v7.SolverKind.LIVE,
        "model_template_hash": stable_hash("{{ .Prompt }}"),
    }
    defaults.update(kwargs)
    return v7.cache_identity(genome, probe, v5.build_prompt(genome, probe), **defaults)


CACHE_COMPONENTS = [
    "experiment_version",
    "instrument_version",
    "solver_kind",
    "model_digest",
    "model_template_hash",
    "runtime_condition",
    "runtime_hash",
    "decoding_hash",
    "candidate_id",
    "genome_hash",
    "task_id",
    "probe_hash",
    "prompt_hash",
    "prompt_bytes_sha256",
]


def test_cache_identity_records_every_required_component(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    assert sorted(_identity(dev_pool)) == sorted(CACHE_COMPONENTS)


@pytest.mark.parametrize("component", CACHE_COMPONENTS)
def test_cache_key_is_sensitive_to_every_component(
    component: str, dev_pool: tuple[v5.V5Probe, ...], tmp_path: Path
) -> None:
    base = _identity(dev_pool)
    mutated = {**base, component: f"{base[component]}-mutated"}
    assert stable_hash(mutated) != stable_hash(base)
    assert v7.cache_path(tmp_path, mutated, dry_run=False) != v7.cache_path(
        tmp_path, base, dry_run=False
    )
    assert v7.classify_cache_scope(mutated, base) is v7.CacheScope.CROSS_CONDITION


def test_real_condition_changes_produce_different_cache_identities(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    base = _identity(dev_pool)
    variations = {
        "solver": _identity(dev_pool, solver=v5.SOLVERS["gemma4:12b"]),
        "framing": _identity(dev_pool, bare=False),
        "solver_kind": _identity(dev_pool, solver_kind=v7.SolverKind.STUB),
        "template": _identity(dev_pool, model_template_hash=stable_hash("other")),
        "task": v7.cache_identity(
            v5.equal_information_genome(),
            dev_pool[1],
            v5.build_prompt(v5.equal_information_genome(), dev_pool[1]),
            solver=v5.SOLVERS["qwen38-rvn"],
            bare=True,
            solver_kind=v7.SolverKind.LIVE,
            model_template_hash=stable_hash("{{ .Prompt }}"),
        ),
        "candidate": v7.cache_identity(
            v5.equal_information_genome("L5_COMPACT_SYMBOLIC"),
            dev_pool[0],
            v5.build_prompt(v5.equal_information_genome("L5_COMPACT_SYMBOLIC"), dev_pool[0]),
            solver=v5.SOLVERS["qwen38-rvn"],
            bare=True,
            solver_kind=v7.SolverKind.LIVE,
            model_template_hash=stable_hash("{{ .Prompt }}"),
        ),
    }
    hashes = {name: stable_hash(value) for name, value in variations.items()}
    assert stable_hash(base) not in hashes.values()
    assert len(set(hashes.values())) == len(hashes)


def test_cache_scope_is_fresh_then_same_condition_reuse(
    tmp_path: Path, dev_pool: tuple[v5.V5Probe, ...]
) -> None:
    probe = dev_pool[0]
    genome = v5.equal_information_genome()
    prompt = v5.build_prompt(genome, probe)
    identity = _identity(dev_pool, solver_kind=v7.SolverKind.STUB)
    call = v7.stub_solver(dev_pool)
    _, first = v7.cached_call(tmp_path, identity, probe, prompt, call, dry_run=True)
    _, second = v7.cached_call(tmp_path, identity, probe, prompt, call, dry_run=True)
    assert first is v7.CacheScope.FRESH
    assert second is v7.CacheScope.SAME_CONDITION_REUSE


def test_a_cross_condition_cache_entry_is_refused_not_consumed(
    tmp_path: Path, dev_pool: tuple[v5.V5Probe, ...]
) -> None:
    """CROSS_CONDITION is impossible by construction; if one is forged it must raise."""

    identity = _identity(dev_pool, solver_kind=v7.SolverKind.STUB)
    path = v7.cache_path(tmp_path, identity, dry_run=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    poisoned = {**identity, "model_digest": "a" * 64}
    path.write_text(json.dumps({"identity": poisoned, "result": {"response": '{"choice":"A"}'}}))
    with pytest.raises(v7.CrossConditionCacheError):
        v7.cached_call(
            tmp_path, identity, dev_pool[0], "prompt", v7.stub_solver(dev_pool), dry_run=True
        )


def test_no_row_of_a_dry_run_is_cross_condition(dry_run: tuple[Path, dict[str, Any]]) -> None:
    _, payload = dry_run
    scopes = {row["cache_scope"] for row in payload["rows"]}
    assert v7.CacheScope.CROSS_CONDITION.value not in scopes
    assert scopes <= {v7.CacheScope.FRESH.value, v7.CacheScope.SAME_CONDITION_REUSE.value}
    assert payload["cache_scope_totals"] == {v7.CacheScope.FRESH.value: len(payload["rows"])}


# ---------------------------------------------------- 6. isolation from V5 and Phase 6


@pytest.mark.parametrize("namespace", v7.FROZEN_NAMESPACES)
def test_v7_refuses_every_frozen_namespace(namespace: str) -> None:
    with pytest.raises(ValueError, match="frozen-instrument path"):
        v7.assert_v7_namespace(f"artifacts/cache/{namespace}/abc.json")
    with pytest.raises(ValueError, match="frozen-instrument path"):
        v7.assert_v7_namespace(f"experiments/{namespace}/development/result.json")


def test_v7_paths_are_all_inside_v7_namespaces(tmp_path: Path) -> None:
    paths = [
        v7.CACHE_NAMESPACE,
        v7.DRY_RUN_CACHE_NAMESPACE,
        v7.ARTIFACT_NAMESPACE,
        str(v7.cache_root(tmp_path, dry_run=False)),
        str(v7.cache_root(tmp_path, dry_run=True)),
        v7.development_artifact_path(v5.SOLVERS["qwen38-rvn"], True),
        v7.development_artifact_path(v5.SOLVERS["qwen38-rvn"], False),
        v7.development_artifact_path(v7.STUB_SOLVER, True, dry_run=True),
    ]
    for path in paths:
        assert v7.assert_v7_namespace(path) == str(path).replace("\\", "/")
        assert "fitness_v7" in path


def test_v7_can_never_collide_with_the_frozen_v5_artifact_path() -> None:
    v5_paths = {
        v5.development_artifact_path(v5.SOLVERS["gemma4:12b"], False),
        v5.development_artifact_path(v5.SOLVERS["gemma4:12b"], True),
        v5.development_artifact_path(v5.SOLVERS["qwen38-rvn"], True),
    }
    v7_paths = {
        v7.development_artifact_path(v5.SOLVERS["gemma4:12b"], False),
        v7.development_artifact_path(v5.SOLVERS["qwen38-rvn"], True),
        v7.development_artifact_path(v7.STUB_SOLVER, True, dry_run=True),
    }
    assert v5_paths.isdisjoint(v7_paths)
    for path in v5_paths:
        with pytest.raises(ValueError):
            v7.assert_v7_namespace(path)


def test_v7_runtime_hash_differs_from_every_v5_runtime_hash() -> None:
    v5_hashes = {v5.RUNTIME_CONFIG_HASH, v5.RUNTIME_CONFIG_BARE_HASH}
    v7_hashes = {v7.RUNTIME_CONFIG_V7_HASH, v7.RUNTIME_CONFIG_V7_BARE_HASH}
    assert v5_hashes.isdisjoint(v7_hashes)
    assert len(v7_hashes) == 2


def test_the_decoding_that_reaches_the_wire_is_byte_identical_to_v5() -> None:
    """The runtime hash differs; the decoding does NOT. Both matter."""

    for bare in (False, True):
        config = v5.RUNTIME_CONFIG_BARE if bare else v5.RUNTIME_CONFIG
        expected = {
            key: value
            for key, value in config.items()
            if key not in {"engine", "think", "format", "raw"}
        }
        settings = v7.decoding_settings(bare=bare)
        assert settings["options"] == expected
        assert settings["format"] == v5.RESPONSE_SCHEMA
    assert v7.decoding_settings(bare=False)["options"]["temperature"] == 0.0
    assert v7.decoding_settings(bare=False)["options"]["seed"] == 20260905
    assert v7.decoding_settings(bare=False)["options"]["num_ctx"] == 32768
    assert v7.decoding_settings(bare=False)["options"]["num_predict"] == 64


def test_a_v7_cache_identity_can_never_equal_a_v5_one(
    dev_pool: tuple[v5.V5Probe, ...],
) -> None:
    probe = dev_pool[0]
    genome = v5.equal_information_genome()
    prompt = v5.build_prompt(genome, probe)
    v5_identity = {
        "experiment": v5.EXPERIMENT_VERSION,
        "instrument": v5.INSTRUMENT_VERSION,
        "model_digest": v5.SOLVERS["qwen38-rvn"]["digest"],
        "runtime_hash": v5.RUNTIME_CONFIG_BARE_HASH,
        "genome_hash": genome.genome_hash,
        "probe_hash": probe.derived_hash,
        "prompt_hash": stable_hash(prompt),
    }
    v7_identity = _identity(dev_pool)
    assert stable_hash(v5_identity) != stable_hash(v7_identity)
    assert v7_identity["prompt_hash"] == v5_identity["prompt_hash"]  # same prompt, new namespace


def test_a_dry_run_writes_nothing_outside_v7_namespaces(
    dry_run: tuple[Path, dict[str, Any]],
) -> None:
    root, _ = dry_run
    written = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
    assert written
    for path in written:
        assert "fitness_v7" in path, path
        for namespace in v7.FROZEN_NAMESPACES:
            assert namespace not in path, path


# ------------------------------------------------------------------------ 7. the dry run


def test_dry_run_produces_a_complete_recomputable_artifact(
    dry_run: tuple[Path, dict[str, Any]],
) -> None:
    root, payload = dry_run
    assert payload["mode"] == "DRY_RUN"
    assert payload["solver_kind"] == v7.SolverKind.STUB.value
    assert payload["experiment_version"] == "arena-representation-fitness-v7"
    assert payload["dev_pool_probes"] == 864
    assert len(payload["rows"]) == 864
    stored = json.loads(
        (
            root / "artifacts" / v7.development_artifact_path(v7.STUB_SOLVER, True, dry_run=True)
        ).read_text()
    )
    assert stored["dev_pool_hash"] == payload["dev_pool_hash"]

    for mechanism in v5.MECHANISMS:
        report = payload["mechanisms"][mechanism]
        assert [entry["level"] for entry in report["ladder"]] == [0, 1, 2, 3]
        for entry in report["ladder"]:
            for key in (
                "positive_accuracy",
                "largest_answer_share",
                "answer_entropy_bits",
                "valid_response_rate",
                "destroyed_accuracy",
                "best_shortcut_accuracy",
                "best_shortcut_feature",
            ):
                assert key in entry, (mechanism, entry["level"], key)


def test_dry_run_uses_the_same_probe_bank_as_v5(dry_run: tuple[Path, dict[str, Any]]) -> None:
    """Same DEV pool hash as the frozen V5/Phase-6 runs: the probes did not change."""

    _, payload = dry_run
    assert payload["dev_pool_hash"].startswith("f804e0d9")


def test_the_verdict_is_recomputable_from_the_rows(
    dry_run: tuple[Path, dict[str, Any]], dev_pool: tuple[v5.V5Probe, ...]
) -> None:
    _, payload = dry_run
    audits = v7.per_level_shortcut_audit(dev_pool)
    for mechanism in v5.MECHANISMS:
        report = payload["mechanisms"][mechanism]
        accuracies = {}
        for level in range(4):
            rows = [
                r
                for r in payload["rows"]
                if r["mechanism"] == mechanism
                and r["level"] == level
                and r["variant"] in POSITIVE_VARIANTS
            ]
            accuracies[level] = sum(r["correct"] for r in rows) / len(rows)
        assert v7.select_frontier_level(accuracies) == report["selection"]
        level = report["selection"]["selected_level"]
        if level is None:
            continue
        cell = [r for r in payload["rows"] if r["mechanism"] == mechanism and r["level"] == level]
        recomputed = v7.qualify_mechanism(
            v5.summarize(cell), audits[mechanism][str(level)], payload["q0"]["rate"]
        )
        assert recomputed == report["qualification"]


def test_the_destroyed_control_is_measured_and_is_the_structural_constant(
    dry_run: tuple[Path, dict[str, Any]],
) -> None:
    """V7 measures destroyed at EVERY level, so the theorem is demonstrated, not assumed."""

    _, payload = dry_run
    for mechanism in v5.MECHANISMS:
        for entry in payload["mechanisms"][mechanism]["ladder"]:
            assert entry["destroyed_measured"] is True
            assert entry["destroyed_accuracy"] == pytest.approx(v7.DESTROYED_EXPECTED)
    twins: dict[str, set[str]] = {}
    for row in payload["rows"]:
        if row["truth_kind"] == "NEGATIVE_CONTROL_TARGET":
            twins.setdefault(row["family_id"], set()).add(row["raw_output"])
    assert twins
    assert all(len(outputs) == 1 for outputs in twins.values())


def test_dry_run_exercises_the_void_shortcut_and_qualified_paths(
    dry_run: tuple[Path, dict[str, Any]],
) -> None:
    _, payload = dry_run
    verdicts = {
        mechanism: report["qualification"]["verdict"]
        for mechanism, report in payload["mechanisms"].items()
    }
    assert verdicts["formal_expression_depth"] == "VOID_SHORTCUT"
    assert "QUALIFIED" in set(verdicts.values())


def test_dry_run_makes_no_network_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def explode(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a dry run must never open a socket")

    monkeypatch.setattr(v7, "urlopen", explode)
    monkeypatch.setattr(v5, "urlopen", explode)
    payload = v7.run_development(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True)
    assert payload["mode"] == "DRY_RUN"
    assert payload["served_model"]["note"].startswith("DRY RUN")


def test_dry_run_is_deterministic_and_reuses_its_own_cache(tmp_path: Path) -> None:
    first = v7.run_development(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True)
    second = v7.run_development(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True)
    assert _strip_provenance(first) == _strip_provenance(second)
    assert first["cache_scope_totals"] == {v7.CacheScope.FRESH.value: 864}
    assert second["cache_scope_totals"] == {v7.CacheScope.SAME_CONDITION_REUSE.value: 864}
    assert second["fresh_calls_made"] == 0


def test_status_reads_only_the_v7_artifact(dry_run: tuple[Path, dict[str, Any]]) -> None:
    root, payload = dry_run
    status = v7.experiment_status_v7(root, v7.STUB_SOLVER, bare=True, dry_run=True)
    assert status["experiment_version"] == "arena-representation-fitness-v7"
    assert status["mode"] == "DRY_RUN"
    assert status["sentinel"] in {
        "FITNESS_V7_QUALIFIED",
        "FITNESS_V7_NOT_QUALIFIED",
        "CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT",
    }
    assert status["qualified_mechanisms"] == payload["qualified_mechanisms"]


def test_status_before_any_run(tmp_path: Path) -> None:
    status = v7.experiment_status_v7(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True)
    assert status["sentinel"] == "FITNESS_V7_NOT_RUN"


# ------------------------------------------------------------------- 8. budget and misc


def test_planned_call_count_fits_the_frozen_budget(dev_pool: tuple[v5.V5Probe, ...]) -> None:
    budget = int(v5.MODEL_CALL_BUDGET["development_max"])
    full = v7.planned_call_count(dev_pool, "full")
    positives = v7.planned_call_count(dev_pool, "positives")
    assert full == len(dev_pool) + 8 == 872
    assert positives == 512
    assert full <= budget and positives <= budget


def test_an_over_budget_schedule_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(v7, "planned_call_count", lambda *_args: 10_000)
    with pytest.raises(ValueError, match="against the frozen budget"):
        v7.run_development(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True)


def test_unknown_arm_schedule_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown arm schedule"):
        v7.run_development(tmp_path, v7.STUB_SOLVER, bare=True, dry_run=True, arms="frontier")


def test_answer_entropy_bits() -> None:
    assert v7.answer_entropy_bits([]) == 0.0
    assert v7.answer_entropy_bits([{"parsed_index": None}]) == 0.0
    assert v7.answer_entropy_bits([{"parsed_index": 0}] * 4) == pytest.approx(0.0)
    balanced = [{"parsed_index": 0}] * 12 + [{"parsed_index": 1}] * 12
    assert v7.answer_entropy_bits(balanced) == pytest.approx(1.0)
    skewed = [{"parsed_index": 0}] * 18 + [{"parsed_index": 1}] * 6
    assert v7.answer_entropy_bits(skewed) == pytest.approx(
        -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25))
    )


def test_stub_solver_hits_its_requested_accuracy_exactly(
    dev_pool: tuple[v5.V5Probe, ...], tmp_path: Path
) -> None:
    cell = [p for p in dev_pool if p.mechanism == "transitive_dependency" and p.level == 2]
    profile = v7.StubProfile(accuracy={("transitive_dependency", 2): 0.75})
    result = v7.evaluate(
        tmp_path,
        v5.equal_information_genome(),
        cell,
        v7.stub_solver(dev_pool, profile),
        solver=v7.STUB_SOLVER,
        bare=True,
        solver_kind=v7.SolverKind.STUB,
        model_template_hash=stable_hash(""),
        dry_run=True,
    )
    assert result["summary"]["positive_accuracy"] == pytest.approx(0.75)
    assert result["summary"]["negative_target_accuracy"] == pytest.approx(0.5)


def test_stub_solver_can_drive_the_validity_and_truncation_paths(
    dev_pool: tuple[v5.V5Probe, ...], tmp_path: Path
) -> None:
    cell = [p for p in dev_pool if p.mechanism == "precondition_conjunction" and p.level == 1]
    positives = [p for p in cell if p.variant.value in POSITIVE_VARIANTS]
    profile = v7.StubProfile(
        accuracy={},
        invalid_task_ids=frozenset({positives[0].probe_id}),
        truncated_task_ids=frozenset({positives[1].probe_id}),
    )
    result = v7.evaluate(
        tmp_path,
        v5.equal_information_genome(),
        cell,
        v7.stub_solver(dev_pool, profile),
        solver=v7.STUB_SOLVER,
        bare=True,
        solver_kind=v7.SolverKind.STUB,
        model_template_hash=stable_hash(""),
        dry_run=True,
    )
    causes = {row["cause"] for row in result["rows"]}
    assert "RESPONSE_SCHEMA_ERROR" in causes
    assert "OUTPUT_TRUNCATION" in causes
    assert result["summary"]["valid_response_rate"] < 1.0


def test_v7_inherits_v5s_frozen_variables_unchanged() -> None:
    inherited = (
        "explicit_positive_level",
        "explicit_positive_min",
        "frontier_band",
        "q0_valid_rate_min",
        "valid_response_rate_min",
        "context_truncated_rows_max",
        "positive_negative_gap_min",
        "largest_answer_share_max",
        "min_positives_for_gates",
        "position_invariance_min",
        "shortcut_rule_max",
        "minimum_qualified_mechanisms",
    )
    for key in inherited:
        assert v7.QUALIFICATION_RULE_V7[key] == v5.QUALIFICATION_RULE[key], key
    assert v7.SHORTCUT_MARGIN == 0.10
    assert v7.LADDERS is v5.LADDERS
    assert v7.MECHANISMS is v5.MECHANISMS
    assert v7.RESPONSE_SCHEMA is v5.RESPONSE_SCHEMA


def test_v7_module_never_edits_a_frozen_instrument() -> None:
    """A read-only tripwire: the frozen module's own constants must still be its own."""

    assert v5.QUALIFICATION_RULE["frontier_target"] == 0.625
    assert v5.QUALIFICATION_RULE["negative_target_accuracy_max"] == 0.60
    assert v5.EXPERIMENT_VERSION == "arena-representation-fitness-v5"
