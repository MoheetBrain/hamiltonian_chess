"""Live Ollama wiring for the Game-R founder-parity harness (Phase 8).

:mod:`arena.experiments.game_r_formal_v1` refuses to send any prompt without an **exact**
:class:`~arena.experiments.game_r_formal_v1.TokenCounter`.  Ollama 0.33.2 has no
``/api/tokenize`` endpoint (verified 404), so the only exact count available is the one the
server itself reports: the V5 precedent (``fitness_v5.CONTEXT_GUARD``) is a ``num_predict=1``
preflight at the production ``num_ctx`` reading ``prompt_eval_count``.  Ollama reports the
*full* ``prompt_eval_count`` even when the prefix is KV-cached, and a call whose prompt shares
a long prefix with the previous call costs about 2 s instead of about 15 s, so
preflight-then-generate on the same prompt is nearly free.

Nothing in this module is executed by its tests against a network: every HTTP call goes
through an injectable ``transport`` callable, and the tests substitute a fake.  The digest
check is the frozen :func:`arena.experiments.fitness_v5.verify_served_model`, imported and
reused rather than re-implemented.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from arena.experiments.fitness_v5 import verify_served_model
from arena.experiments.game_r_formal_v1 import OllamaSolver

OLLAMA_ENDPOINT = "http://127.0.0.1:11434"

#: The Phase-8 Solver, frozen by name AND digest.  The cache identity keys on the digest while
#: the HTTP call uses the name; :func:`served_model_record` is what keeps them linked.
FROZEN_SOLVER: dict[str, str] = {
    "name": "qwen38-rvn:latest",
    "digest": "25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae",
    "family": "qwen35",
    "parameter_size": "27.3B",
    "quantization": "Q4_K_M",
}

#: V5/V7's frozen decoding values, byte for byte.  These are the ONLY keys that reach the wire
#: as ``options``; ``engine``/``think``/``format`` are harness concerns (the format is the
#: harness's own response schema).  Asserted equal to ``fitness_v5.RUNTIME_CONFIG`` minus
#: those keys in the test module.
_FROZEN_DECODING: dict[str, Any] = {
    "num_ctx": 32768,
    "temperature": 0.0,
    "seed": 20260905,
    "num_predict": 64,
    "top_k": 64,
    "top_p": 0.95,
}

#: ``(url, json_payload_or_None) -> parsed JSON``.  ``None`` means a GET.
Transport = Callable[[str, Mapping[str, Any] | None], Mapping[str, Any]]
#: ``solver -> served record``; the production value is ``fitness_v5.verify_served_model``.
Verifier = Callable[[dict[str, str]], dict[str, Any]]


def frozen_decoding() -> dict[str, Any]:
    """A fresh copy of the frozen decoding options."""

    return dict(_FROZEN_DECODING)


def urllib_transport(
    url: str, payload: Mapping[str, Any] | None, *, timeout_seconds: float = 900.0
) -> Mapping[str, Any]:
    """The production transport.  Never invoked by the tests."""

    data = None if payload is None else json.dumps(dict(payload)).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="GET" if data is None else "POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - local service
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{url} returned a non-object JSON payload")
    return parsed


def served_model_record(
    solver: Mapping[str, str],
    *,
    endpoint: str = OLLAMA_ENDPOINT,
    transport: Transport | None = None,
    verify: Verifier | None = None,
) -> dict[str, Any]:
    """Verify the served model against ``solver`` and record the runtime version.

    Thin wrapper around the frozen :func:`fitness_v5.verify_served_model`, which raises
    ``RuntimeError`` on a digest mismatch (or an unserved model).  The digest is re-checked
    here as well, so a substituted ``verify`` (tests) cannot hand back a foreign model.  The
    frozen verifier is bound to the local endpoint, so a different ``endpoint`` is refused
    rather than silently ignored.
    """

    if endpoint.rstrip("/") != OLLAMA_ENDPOINT:
        raise ValueError(
            f"verify_served_model is bound to {OLLAMA_ENDPOINT}; cannot verify {endpoint!r}"
        )
    record = (verify or verify_served_model)(dict(solver))
    if str(record.get("digest", "")) != str(solver["digest"]):
        raise RuntimeError(
            f"served digest {record.get('digest')!r} does not match the frozen solver digest "
            f"{solver['digest']!r}; refusing to run"
        )
    if not str(record.get("template_hash", "")):
        raise RuntimeError("served model record carries no template_hash; refusing to run")
    version = (transport or urllib_transport)(f"{endpoint}/api/version", None)
    return {
        **record,
        "recorded": {key: str(solver.get(key, "")) for key in FROZEN_SOLVER},
        "ollama_version": str(version.get("version", "")),
        "endpoint": endpoint,
        "tokenize_endpoint": (
            "absent (/api/tokenize returned 404 on Ollama 0.33.2); exact counts come from a "
            "num_predict=1 preflight reading prompt_eval_count"
        ),
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class OllamaPreflightTokenCounter:
    """An exact :class:`TokenCounter` backed by a ``num_predict=1`` preflight.

    ``count_tokens`` POSTs ``/api/generate`` with the production ``num_ctx``, ``raw=True`` and
    ``num_predict=1`` and returns ``prompt_eval_count`` verbatim.  A zero or missing count is a
    hard error, never a guess.  Counts are memoised by ``sha256(text)`` in memory AND on disk
    under ``cache_dir`` (namespaced by ``tokenizer_id``), so a resumed run never re-counts and a
    template or digest change can never read a stale count.
    """

    exact: bool = True

    def __init__(
        self,
        solver: Mapping[str, str],
        *,
        num_ctx: int,
        cache_dir: str | Path,
        endpoint: str = OLLAMA_ENDPOINT,
        template_hash: str = "",
        transport: Transport | None = None,
        seed: int = int(_FROZEN_DECODING["seed"]),
        timeout_seconds: float = 900.0,
    ) -> None:
        self.model = str(solver["name"])
        self.digest = str(solver["digest"])
        resolved_template = template_hash or str(solver.get("template_hash", ""))
        if not resolved_template:
            raise ValueError(
                "a preflight counter must be bound to the served template hash "
                "(pass template_hash= from served_model_record)"
            )
        if not self.digest:
            raise ValueError("a preflight counter must be bound to a solver digest")
        self.template_hash = resolved_template
        self.tokenizer_id = f"ollama-preflight:{self.digest}:{self.template_hash}"
        self.num_ctx = int(num_ctx)
        self.seed = int(seed)
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.cache_dir = Path(cache_dir) / _sha256(self.tokenizer_id)[:16]
        self._transport: Transport = transport or self._default_transport
        self._memo: dict[str, int] = {}
        self.preflight_calls = 0
        self.memo_hits = 0
        self.disk_hits = 0

    def _default_transport(
        self, url: str, payload: Mapping[str, Any] | None
    ) -> Mapping[str, Any]:  # pragma: no cover - requires a live local runtime
        return urllib_transport(url, payload, timeout_seconds=self.timeout_seconds)

    def preflight_payload(self, text: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt": text,
            "raw": True,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": 1,
                "temperature": 0.0,
                "seed": self.seed,
            },
        }

    def _disk_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _load_disk(self, key: str) -> int | None:
        path = self._disk_path(key)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict):
            return None
        if record.get("tokenizer_id") != self.tokenizer_id or record.get("num_ctx") != self.num_ctx:
            return None
        count = record.get("prompt_eval_count")
        if not isinstance(count, int) or count <= 0:
            return None
        return count

    def _store_disk(self, key: str, count: int) -> None:
        path = self._disk_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "sha256": key,
            "prompt_eval_count": count,
            "tokenizer_id": self.tokenizer_id,
            "model": self.model,
            "digest": self.digest,
            "num_ctx": self.num_ctx,
        }
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def count_tokens(self, text: str) -> int:
        key = _sha256(text)
        memoised = self._memo.get(key)
        if memoised is not None:
            self.memo_hits += 1
            return memoised
        stored = self._load_disk(key)
        if stored is not None:
            self.disk_hits += 1
            self._memo[key] = stored
            return stored
        raw = self._transport(f"{self.endpoint}/api/generate", self.preflight_payload(text))
        self.preflight_calls += 1
        reported = raw.get("prompt_eval_count")
        if reported is None or not isinstance(reported, int | float) or int(reported) <= 0:
            raise RuntimeError(
                f"preflight for {self.model} returned prompt_eval_count={reported!r}; refusing "
                "to treat a missing or zero count as exact"
            )
        count = int(reported)
        self._memo[key] = count
        self._store_disk(key, count)
        return count

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokenizer_id": self.tokenizer_id,
            "exact": self.exact,
            "method": "ollama num_predict=1 preflight at production num_ctx; prompt_eval_count",
            "model": self.model,
            "digest": self.digest,
            "template_hash": self.template_hash,
            "num_ctx": self.num_ctx,
            "cache_dir": str(self.cache_dir),
            "preflight_calls": self.preflight_calls,
            "memo_hits": self.memo_hits,
            "disk_hits": self.disk_hits,
        }


def live_solver(
    solver: Mapping[str, str],
    *,
    revision: str,
    bare: bool = True,
    endpoint: str = OLLAMA_ENDPOINT,
    timeout_seconds: int = 900,
) -> OllamaSolver:
    """Construct the harness's :class:`OllamaSolver` for the frozen solver.

    ``revision`` should be the served template hash: the harness folds
    ``f"{solver.revision}|{counter.tokenizer_id}"`` into the cache identity, so a template
    change invalidates every cached row instead of silently replaying it.
    """

    if not revision:
        raise ValueError("live_solver needs a non-empty revision (the served template hash)")
    return OllamaSolver(
        name=str(solver["name"]),
        digest=str(solver["digest"]),
        revision=revision,
        endpoint=f"{endpoint.rstrip('/')}/api/generate",
        bare=bare,
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "FROZEN_SOLVER",
    "OLLAMA_ENDPOINT",
    "OllamaPreflightTokenCounter",
    "Transport",
    "Verifier",
    "frozen_decoding",
    "live_solver",
    "served_model_record",
    "urllib_transport",
]
