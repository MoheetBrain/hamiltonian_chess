"""Solver requests that enforce the communication-bottleneck boundary."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from arena.canonical.schema import stable_hash


@dataclass(frozen=True)
class SolverRequest:
    task_id: str
    task_kind: str
    candidate_id: str
    message: str
    response_schema: str
    option_ids: tuple[str, ...] = ()

    def prompt(self) -> str:
        options = "\nOPTIONS:\n" + "\n".join(self.option_ids) if self.option_ids else ""
        return (
            "You are a mathematical state solver. You can see only the candidate message. "
            "Do not invent hidden state. Return only the requested JSON value.\n"
            f"TASK_KIND: {self.task_kind}\n"
            f"RESPONSE_SCHEMA: {self.response_schema}{options}\n"
            f"MESSAGE:\n{self.message}"
        )


@dataclass(frozen=True)
class SolverResponse:
    task_id: str
    candidate_id: str
    model_id: str
    output: str
    latency_seconds: float
    prompt_hash: str
    config_hash: str
    error: str | None = None


class OllamaSolver:
    """Minimal deterministic Ollama adapter with complete configuration provenance."""

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def solve(
        self,
        request: SolverRequest,
        *,
        seed: int = 0,
        temperature: float = 0.0,
        num_predict: int = 512,
        timeout: float = 120.0,
    ) -> SolverResponse:
        prompt = request.prompt()
        options: dict[str, Any] = {
            "seed": seed,
            "temperature": temperature,
            "num_predict": num_predict,
        }
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }
        started = time.monotonic()
        error: str | None = None
        output = ""
        try:
            http_request = Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(http_request, timeout=timeout) as response:  # noqa: S310
                result = json.loads(response.read().decode("utf-8"))
            output = str(result.get("response", ""))
        except Exception as exception:  # External model boundary; preserve the failure.
            error = repr(exception)
        return SolverResponse(
            task_id=request.task_id,
            candidate_id=request.candidate_id,
            model_id=self.model,
            output=output,
            latency_seconds=time.monotonic() - started,
            prompt_hash=stable_hash(prompt),
            config_hash=stable_hash(options),
            error=error,
        )
