"""Tests for the live Ollama wiring.  **No test here opens a socket.**

Every HTTP call in :mod:`arena.experiments.ollama_live` goes through an injectable transport
(or verifier); the tests substitute fakes and additionally patch ``urlopen`` in every module
that could reach the network so that an accidental live call fails loudly.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from arena.experiments import fitness_v5, game_r_formal_v1, ollama_live
from arena.experiments.game_r_formal_v1 import (
    SCORED_STATUSES,
    CallBudget,
    ContextBudget,
    OllamaSolver,
    ResponseCache,
    RowStatus,
    RunConfig,
    StubEnvironment,
    StubSolver,
    StubSolverPolicy,
    SyntaxGuidePolicy,
    founder_genome,
    run_item,
)
from arena.experiments.ollama_live import (
    FROZEN_SOLVER,
    OLLAMA_ENDPOINT,
    OllamaPreflightTokenCounter,
    frozen_decoding,
    live_solver,
    served_model_record,
)

TEMPLATE_HASH = "a" * 64
OTHER_TEMPLATE_HASH = "b" * 64


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a test attempted a network call")

    monkeypatch.setattr(ollama_live, "urlopen", refuse)
    monkeypatch.setattr(fitness_v5, "urlopen", refuse)
    monkeypatch.setattr(game_r_formal_v1, "urlopen", refuse)


class FakeTransport:
    """Records every call.  Counts one token per whitespace word unless ``reply`` is fixed."""

    def __init__(self, reply: Mapping[str, Any] | None = None, *, version: str = "0.33.2") -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.reply = reply
        self.version = version

    def __call__(self, url: str, payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
        self.calls.append((url, None if payload is None else json.loads(json.dumps(payload))))
        if payload is None:
            return {"version": self.version}
        if self.reply is not None:
            return dict(self.reply)
        return {
            "prompt_eval_count": len(str(payload["prompt"]).split()),
            "eval_count": 1,
            "response": "",
            "done": True,
        }


def _counter(
    tmp_path: Path, transport: FakeTransport, **overrides: Any
) -> OllamaPreflightTokenCounter:
    kwargs: dict[str, Any] = {
        "num_ctx": 32768,
        "cache_dir": tmp_path / "token_counts",
        "template_hash": TEMPLATE_HASH,
        "transport": transport,
    }
    kwargs.update(overrides)
    return OllamaPreflightTokenCounter(FROZEN_SOLVER, **kwargs)


def _served(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": FROZEN_SOLVER["name"],
        "digest": FROZEN_SOLVER["digest"],
        "template": "{{ .Prompt }}",
        "template_hash": TEMPLATE_HASH,
        "template_is_passthrough": True,
        "capabilities": ["completion"],
        "details": {"family": "qwen35"},
    }
    record.update(overrides)
    return record


# ------------------------------------------------------------------------- token counter


def test_count_is_the_reported_prompt_eval_count_from_a_bare_num_predict_1_preflight(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    counter = _counter(tmp_path, transport)
    assert counter.exact is True
    assert counter.count_tokens("alpha beta gamma") == 3
    assert counter.preflight_calls == 1
    assert len(transport.calls) == 1
    url, payload = transport.calls[0]
    assert url == f"{OLLAMA_ENDPOINT}/api/generate"
    assert payload is not None
    assert payload["model"] == FROZEN_SOLVER["name"]
    assert payload["prompt"] == "alpha beta gamma"
    assert payload["raw"] is True
    assert payload["stream"] is False
    assert "format" not in payload
    assert payload["options"] == {
        "num_ctx": 32768,
        "num_predict": 1,
        "temperature": 0.0,
        "seed": 20260905,
    }


def test_count_is_memoised_in_memory_so_the_transport_is_called_once(tmp_path: Path) -> None:
    transport = FakeTransport()
    counter = _counter(tmp_path, transport)
    assert counter.count_tokens("one two") == 2
    assert counter.count_tokens("one two") == 2
    assert len(transport.calls) == 1
    assert counter.preflight_calls == 1
    assert counter.memo_hits == 1
    assert counter.count_tokens("one two three") == 3
    assert len(transport.calls) == 2


def test_on_disk_memo_survives_a_new_instance_without_any_transport_call(tmp_path: Path) -> None:
    first = _counter(tmp_path, FakeTransport())
    assert first.count_tokens("resume me please") == 3
    stored = list((tmp_path / "token_counts").rglob("*.json"))
    assert len(stored) == 1
    record = json.loads(stored[0].read_text(encoding="utf-8"))
    assert record["prompt_eval_count"] == 3
    assert record["tokenizer_id"] == first.tokenizer_id
    assert record["num_ctx"] == 32768
    assert record["digest"] == FROZEN_SOLVER["digest"]

    # A transport that would report a different count proves the disk value is what is used.
    lying = FakeTransport(reply={"prompt_eval_count": 999})
    second = _counter(tmp_path, lying)
    assert second.count_tokens("resume me please") == 3
    assert lying.calls == []
    assert second.preflight_calls == 0
    assert second.disk_hits == 1


def test_disk_memo_is_keyed_by_tokenizer_identity(tmp_path: Path) -> None:
    _counter(tmp_path, FakeTransport()).count_tokens("same text")
    other_template = FakeTransport(reply={"prompt_eval_count": 17})
    counter = _counter(tmp_path, other_template, template_hash=OTHER_TEMPLATE_HASH)
    assert counter.count_tokens("same text") == 17
    assert len(other_template.calls) == 1
    other_ctx = FakeTransport(reply={"prompt_eval_count": 23})
    assert _counter(tmp_path, other_ctx, num_ctx=8192).count_tokens("same text") == 23
    assert len(other_ctx.calls) == 1


@pytest.mark.parametrize("reply", [{"prompt_eval_count": 0}, {}, {"prompt_eval_count": None}])
def test_zero_or_missing_count_is_refused_and_never_cached(
    tmp_path: Path, reply: dict[str, Any]
) -> None:
    counter = _counter(tmp_path, FakeTransport(reply=reply))
    with pytest.raises(RuntimeError, match="refusing to treat a missing or zero count as exact"):
        counter.count_tokens("anything")
    assert not list((tmp_path / "token_counts").rglob("*.json"))
    # Nothing was memoised in memory either: the next call preflights again.
    with pytest.raises(RuntimeError):
        counter.count_tokens("anything")
    assert counter.preflight_calls == 2
    assert counter.memo_hits == 0 and counter.disk_hits == 0


def test_tokenizer_id_embeds_the_digest_and_the_served_template_hash(tmp_path: Path) -> None:
    counter = _counter(tmp_path, FakeTransport())
    assert counter.tokenizer_id == f"ollama-preflight:{FROZEN_SOLVER['digest']}:{TEMPLATE_HASH}"
    other = _counter(tmp_path, FakeTransport(), template_hash=OTHER_TEMPLATE_HASH)
    assert other.tokenizer_id != counter.tokenizer_id
    assert counter.cache_dir != other.cache_dir
    record = counter.to_dict()
    assert record["exact"] is True
    assert record["tokenizer_id"] == counter.tokenizer_id
    assert record["template_hash"] == TEMPLATE_HASH
    assert "prompt_eval_count" in record["method"]


def test_counter_requires_a_template_hash_and_a_digest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template hash"):
        OllamaPreflightTokenCounter(
            FROZEN_SOLVER, num_ctx=32768, cache_dir=tmp_path, transport=FakeTransport()
        )
    from_solver = OllamaPreflightTokenCounter(
        {**FROZEN_SOLVER, "template_hash": TEMPLATE_HASH},
        num_ctx=32768,
        cache_dir=tmp_path,
        transport=FakeTransport(),
    )
    assert from_solver.template_hash == TEMPLATE_HASH
    with pytest.raises(ValueError, match="digest"):
        OllamaPreflightTokenCounter(
            {**FROZEN_SOLVER, "digest": ""},
            num_ctx=32768,
            cache_dir=tmp_path,
            template_hash=TEMPLATE_HASH,
            transport=FakeTransport(),
        )


def test_counter_is_accepted_by_the_harness_as_exact_and_cross_checks_the_solver(
    tmp_path: Path,
) -> None:
    item = StubEnvironment().items(families=1, levels=(1,))[0]
    genome = founder_genome("L3_JSON_AST")
    config = RunConfig(
        experiment_version="test",
        runtime_condition="bare",
        decoding=frozen_decoding(),
        context=ContextBudget(num_ctx=32768, max_output_tokens=64),
        cache_root=tmp_path / "cache",
        guide_policy=SyntaxGuidePolicy.SHARED_CONSTANT,
    )
    transport = FakeTransport()
    counter = _counter(tmp_path, transport)
    row = run_item(
        item,
        genome,
        mechanism="stub",
        environment_version="stub-v0",
        config=config,
        solver=StubSolver(policy=StubSolverPolicy.DETERMINISTIC_MIX),
        counter=counter,
        budget=CallBudget(10),
        cache=ResponseCache(tmp_path / "cache"),
    )
    assert RowStatus(row["status"]) in SCORED_STATUSES
    sent = transport.calls[0][1]
    assert sent is not None
    assert row["prompt_tokens_counted"] == len(str(sent["prompt"]).split())
    assert row["prompt_tokens_reported"] == row["prompt_tokens_counted"]
    assert row["token_count_mismatch"] is False
    # The harness folds the tokenizer id into the cache identity through model_revision, so
    # a template or digest change can never replay a row counted under another tokenizer.
    stored = json.loads(next((tmp_path / "cache").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["identity"]["model_revision"].endswith(f"|{counter.tokenizer_id}")


# ------------------------------------------------------------------------ frozen values


def test_frozen_decoding_equals_v5_runtime_config_minus_engine_think_format() -> None:
    expected = {
        key: value
        for key, value in fitness_v5.RUNTIME_CONFIG.items()
        if key not in {"engine", "think", "format"}
    }
    assert frozen_decoding() == expected
    assert frozen_decoding() == {
        "num_ctx": 32768,
        "temperature": 0.0,
        "seed": 20260905,
        "num_predict": 64,
        "top_k": 64,
        "top_p": 0.95,
    }
    copy = frozen_decoding()
    copy["num_predict"] = 1
    assert frozen_decoding()["num_predict"] == 64


def test_frozen_solver_is_the_v5_qwen_registry_entry() -> None:
    assert fitness_v5.SOLVERS["qwen38-rvn"] == FROZEN_SOLVER
    assert FROZEN_SOLVER["name"] == "qwen38-rvn:latest"
    assert (
        FROZEN_SOLVER["digest"]
        == "25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae"
    )
    assert OLLAMA_ENDPOINT == "http://127.0.0.1:11434"


# --------------------------------------------------------------------- served model record


def test_served_model_record_raises_on_digest_mismatch_before_touching_the_version() -> None:
    transport = FakeTransport()
    with pytest.raises(RuntimeError, match="does not match the frozen solver digest"):
        served_model_record(
            FROZEN_SOLVER, transport=transport, verify=lambda _: _served(digest="0" * 64)
        )
    assert transport.calls == []

    def v5_style_refusal(solver: dict[str, str]) -> dict[str, Any]:
        raise RuntimeError(f"digest mismatch for {solver['name']}")

    with pytest.raises(RuntimeError, match="digest mismatch"):
        served_model_record(FROZEN_SOLVER, transport=transport, verify=v5_style_refusal)
    with pytest.raises(RuntimeError, match="template_hash"):
        served_model_record(
            FROZEN_SOLVER, transport=transport, verify=lambda _: _served(template_hash="")
        )


def test_served_model_record_wraps_the_verified_record_with_the_runtime_version() -> None:
    transport = FakeTransport(version="0.33.2")
    record = served_model_record(FROZEN_SOLVER, transport=transport, verify=lambda _: _served())
    assert transport.calls == [(f"{OLLAMA_ENDPOINT}/api/version", None)]
    assert record["digest"] == FROZEN_SOLVER["digest"]
    assert record["template_hash"] == TEMPLATE_HASH
    assert record["template_is_passthrough"] is True
    assert record["ollama_version"] == "0.33.2"
    assert record["endpoint"] == OLLAMA_ENDPOINT
    assert record["recorded"] == dict(FROZEN_SOLVER)
    assert "absent" in record["tokenize_endpoint"]
    assert "prompt_eval_count" in record["tokenize_endpoint"]


def test_served_model_record_refuses_a_foreign_endpoint() -> None:
    with pytest.raises(ValueError, match="bound to"):
        served_model_record(
            FROZEN_SOLVER,
            endpoint="http://10.0.0.1:11434",
            transport=FakeTransport(),
            verify=lambda _: _served(),
        )


# ------------------------------------------------------------------------------ solver


def test_live_solver_is_the_harness_ollama_solver_bound_to_the_frozen_model() -> None:
    solver = live_solver(FROZEN_SOLVER, revision=TEMPLATE_HASH)
    assert isinstance(solver, OllamaSolver)
    assert solver.name == FROZEN_SOLVER["name"]
    assert solver.digest == FROZEN_SOLVER["digest"]
    assert solver.revision == TEMPLATE_HASH
    assert solver.endpoint == f"{OLLAMA_ENDPOINT}/api/generate"
    assert solver.bare is True
    assert live_solver(FROZEN_SOLVER, revision=TEMPLATE_HASH, bare=False).bare is False
    with pytest.raises(ValueError, match="revision"):
        live_solver(FROZEN_SOLVER, revision="")
