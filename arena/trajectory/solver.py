"""The Solver seam of ``M_L``: a rendered proof state in, one Lean 4 tactic out.

Every action in the trajectory bank today carries ``actor=REFERENCE``.  This module is what a
``actor=SOLVER`` action has to come through, and it is deliberately the narrowest possible
object: :meth:`Solver.propose` receives an observation and returns a :class:`TacticProposal`.
The scientific object is ``state -> action``; nothing here asks the model to explain itself, and
nothing here shows the model anything but the rendered goal.

Four commitments, each of them testable:

**The Solver never sees an oracle.**  The prompt is assembled from exactly one key of
``observation.rendered`` (:data:`OBSERVED_FIELD`).  That is an allow-list, not a filter: a
renderer or a provenance record may later attach the reference proof, the remaining tactics or
the theorem's own name to the observation, and none of it can reach the wire, because nothing
but ``goals_pp`` is ever read.  (Leakage *inside* ``goals_pp`` is
:class:`arena.trajectory.arena_v0.LeakageFilter`'s job, not this module's.)

**The output format is frozen and minimal.**  One JSON object, ``{"tactic": "..."}``, enforced
server-side by Ollama's ``format`` grammar (:data:`TACTIC_RESPONSE_SCHEMA`).  The alternative --
a bare tactic string -- was measured on the installed model and rejected: it comes back as
``'\\nring\\n\\n'``, so a bare-string reader needs client-side normalisation whose rules would
have to be frozen anyway, and it leaves a genuine parse failure indistinguishable from a
formatting quirk.  Under the grammar the model *cannot* emit a preamble, a markdown fence or an
explanation, so ``PARSE_FAILURE`` means something real happened.  The only normalisation applied
to the response is ``str.strip``; there is no repair, no fence-stripping and no retry.

**Parse failure is an outcome, not an exception.**  Prose, empty output, a wrong key, a
truncation and a dead transport all return a typed :class:`TacticProposal` with a status and a
``failure_detail``.  The caller decides what a failure costs; this module never decides to try
again.

**Token accounting is mandatory** (manual section 13.1).  ``prompt_tokens`` and
``completion_tokens`` come from the server's own ``prompt_eval_count``/``eval_count`` on the
generating call, and latency is measured around it.  Ollama 0.33.2 has no ``/api/tokenize``
(re-verified 404 on 2026-09-08), so a *pre-send* count -- the only kind a context guard can use
-- comes from :class:`arena.experiments.ollama_live.OllamaPreflightTokenCounter`, imported and
reused rather than re-implemented.

Identity
--------
The model previously used in Phases 6/8 (``qwen38-rvn``, digest ``25eb57cb...``) was deleted from
this machine.  :data:`RECORDED_SOLVER` is a **new** identity for the model that is installed now
and inherits nothing from it: its ``lineage`` is ``UNKNOWN`` and
:data:`INSTALLED_LINEAGE_EVIDENCE` records exactly what could and could not be established.

Nothing in this module reaches the network under test: every HTTP call goes through an injectable
``transport`` callable and :class:`ScriptedSolver` needs no runtime at all.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from arena.canonical.schema import stable_hash
from arena.experiments.ollama_live import (
    OLLAMA_ENDPOINT,
    OllamaPreflightTokenCounter,
    Transport,
    urllib_transport,
)

SOLVER_ADAPTER_VERSION = "trajectory-solver-v0.1.0"

__all__ = [
    "DEFAULT_BUDGET",
    "FROZEN_DECODING",
    "INSTALLED_LINEAGE_EVIDENCE",
    "OBSERVED_FIELD",
    "PROMPT_TEMPLATE",
    "PROMPT_TEMPLATE_ID",
    "PROMPT_TEMPLATE_SHA256",
    "RECORDED_SOLVER",
    "SMOKE_GOALS",
    "SOLVER_ADAPTER_VERSION",
    "TACTIC_RESPONSE_SCHEMA",
    "TACTIC_RESPONSE_SCHEMA_SHA256",
    "WIRE_FLAGS",
    "OllamaTacticSolver",
    "ParseResult",
    "ProposalBudget",
    "ProposalStatus",
    "RenderedObservation",
    "ScriptedSolver",
    "Solver",
    "SolverIdentity",
    "SolverIdentityMismatch",
    "TacticProposal",
    "UnrenderableObservation",
    "build_prompt",
    "identity_from_live",
    "live_smoke",
    "main",
    "observed_state_text",
    "parse_tactic_response",
    "preflight_counter",
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# The frozen prompt
# ---------------------------------------------------------------------------------------------

#: The **only** key of ``observation.rendered`` that is ever read.  Both renderers shipped in
#: ``arena.trajectory.arena_v0`` (``backend-native-v0`` and ``goal-text-v0``) emit it.
OBSERVED_FIELD = "goals_pp"

#: One fixed template, substituted with :meth:`str.replace` and never with :meth:`str.format`:
#: Lean goal text is full of ``{`` and ``}`` (structure instances, set-builders, ``fun x => {x}``)
#: and ``format`` would raise on the state rather than render it.
PROMPT_TEMPLATE = (
    "Lean 4 proof state:\n"
    "{state}\n"
    "\n"
    "Give exactly one Lean 4 tactic to apply to the first goal.\n"
    'Reply with only the JSON object {"tactic": "<tactic>"}.\n'
)
PROMPT_TEMPLATE_ID = "hc-v0.5-tactic-json-v1"
PROMPT_TEMPLATE_SHA256 = _sha256(PROMPT_TEMPLATE)

#: Ollama's ``format`` grammar.  ``additionalProperties: false`` is what makes "a JSON object with
#: the wrong key" a *server-side impossibility* on this runtime and a ``PARSE_FAILURE`` on any
#: other; the parser enforces the same shape independently, so the two never drift apart silently.
TACTIC_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"tactic": {"type": "string"}},
    "required": ["tactic"],
    "additionalProperties": False,
}
TACTIC_RESPONSE_SCHEMA_SHA256 = stable_hash(TACTIC_RESPONSE_SCHEMA)


class UnrenderableObservation(ValueError):
    """The observation carries no goal text.  A wiring bug, not a model outcome."""


@runtime_checkable
class RenderedObservation(Protocol):
    """The structural shape this module needs.

    ``arena.trajectory.arena_v0.ArenaObservation`` satisfies it; stating it structurally keeps
    the Solver from depending on the arena module and lets a test build an observation by hand.
    """

    @property
    def step_index(self) -> int: ...

    @property
    def state_id(self) -> str: ...

    @property
    def rendered(self) -> Mapping[str, Any]: ...


def observed_state_text(observation: RenderedObservation) -> str:
    """The single field of the observation that the model is allowed to see."""

    text = observation.rendered.get(OBSERVED_FIELD)
    if not isinstance(text, str) or not text.strip():
        raise UnrenderableObservation(
            f"observation {observation.state_id!r} has no usable {OBSERVED_FIELD!r}; the Solver "
            "reads that key and nothing else, so it cannot be substituted with another field"
        )
    return text


def build_prompt(state_text: str) -> str:
    """Render the frozen template.  This is the entire prompt; there is no system message."""

    return PROMPT_TEMPLATE.replace("{state}", state_text)


# ---------------------------------------------------------------------------------------------
# Decoding and framing
# ---------------------------------------------------------------------------------------------

#: Greedy, seeded, and fully explicit.  ``top_k``/``top_p``/``min_p``/the penalties are inert at
#: ``temperature=0`` but are pinned anyway so that a change to the model's own ``PARAMETER``
#: defaults cannot silently alter decoding.  ``num_ctx`` is ours (32768); the model's own limit is
#: 262144 and is recorded separately as :attr:`SolverIdentity.context_limit`.
FROZEN_DECODING: dict[str, float | int] = {
    "num_ctx": 32768,
    "num_predict": 128,
    "temperature": 0.0,
    "seed": 20260908,
    "top_k": 20,
    "top_p": 0.95,
    "min_p": 0.0,
    "repeat_penalty": 1.0,
    "presence_penalty": 0.0,
}

#: Wire-level flags, which are *not* ``options`` and so are recorded separately.
#:
#: ``think=False`` is the load-bearing one.  Measured on 2026-09-08 against
#: ``qwen3.6:27b-mlx``: with ``think`` omitted the model spent all 256 permitted tokens on
#: reasoning, returned ``done_reason="length"`` and an **empty** ``response`` -- i.e. every
#: proposal would have been a ``PARSE_FAILURE``.  With ``think=False`` the ``thinking`` field is
#: absent and the answer arrives in 1-14 tokens.
#:
#: ``raw=False`` keeps Ollama's built-in ``qwen3.5`` renderer in the loop.  The legacy Modelfile
#: ``TEMPLATE`` is the pass-through ``{{ .Prompt }}``, but the renderer still applies chat framing
#: (measured: 58 prompt tokens at ``raw=True`` against 70 for the same string at ``raw=False``),
#: and ``think`` is a renderer/parser concern that ``raw=True`` bypasses entirely.
WIRE_FLAGS: dict[str, bool] = {"raw": False, "think": False, "stream": False}


@dataclass(frozen=True, slots=True)
class ProposalBudget:
    """A per-call ceiling.  ``None`` means "use the frozen decoding value"."""

    max_output_tokens: int | None = None
    #: When set *and* a preflight counter is wired, a prompt over this many tokens is refused
    #: before it is sent, as :attr:`ProposalStatus.PROMPT_OVER_BUDGET`.
    max_prompt_tokens: int | None = None
    timeout_seconds: float = 900.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_output_tokens": self.max_output_tokens,
            "max_prompt_tokens": self.max_prompt_tokens,
            "timeout_seconds": self.timeout_seconds,
        }


DEFAULT_BUDGET = ProposalBudget()


# ---------------------------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------------------------

INSTALLED_MODEL_NAME = "qwen3.6:27b-mlx"

#: Verbatim record of what could and could not be established about where this model came from.
#: Distribution provenance is not training lineage, so :attr:`SolverIdentity.lineage` stays
#: ``UNKNOWN``.
INSTALLED_LINEAGE_EVIDENCE = (
    "established: pulled from registry.ollama.ai/library/qwen3.6:27b-mlx (local manifest path); "
    "safetensors format; Apache-2.0 licence text served by /api/show; architecture string "
    "'qwen3_5'. NOT established: training data, base checkpoint, fine-tuning history, or any "
    "relation to the deleted Phase 6/8 solver qwen38-rvn (digest 25eb57cb...), which is "
    "unrecoverable and is NOT assumed to be an ancestor, descendant or sibling of this model."
)


class SolverIdentityMismatch(RuntimeError):
    """The served model is not the recorded one.  Never downgraded to a warning."""


@dataclass(frozen=True, slots=True)
class SolverIdentity:
    """Everything needed to say which policy produced an action, hashable and digestible.

    Split into three groups, because they answer different questions:

    * *served* (``model_name`` .. ``capabilities``) -- what the runtime is serving.  Compared
      against a live ``/api/show`` by :meth:`assert_matches`.
    * *harness* (``prompt_template_id`` .. ``wire_flags``) -- what this adapter does with it.
    * *lineage* -- what is known about where it came from, which is deliberately very little.
    """

    model_name: str
    model_digest: str
    parameter_size: str
    parameter_count: int
    quantization: str
    family: str
    architecture: str
    context_limit: int
    capabilities: tuple[str, ...]
    runtime: str
    runtime_version: str
    #: Ollama 0.33.2's built-in renderer/parser pair, which is what actually frames the prompt.
    renderer: str
    parser: str
    #: The legacy Modelfile ``TEMPLATE`` string.  Pass-through on this model; recorded because a
    #: non-pass-through template would change the bytes the model sees.
    legacy_template: str
    #: How token counts are obtained, in words, because the endpoint that would be obvious is
    #: absent on this runtime.
    tokenizer_id: str
    tokenizer_note: str
    prompt_template_id: str
    prompt_template_sha256: str
    output_format: str
    output_schema_sha256: str
    decoding: tuple[tuple[str, str | int | float | bool], ...]
    wire_flags: tuple[tuple[str, bool], ...]
    lineage: str = "UNKNOWN"
    lineage_evidence: str = ""
    adapter_version: str = SOLVER_ADAPTER_VERSION

    #: Fields that describe the served model rather than this adapter's use of it.
    SERVED_FIELDS = (
        "model_name",
        "model_digest",
        "parameter_size",
        "parameter_count",
        "quantization",
        "family",
        "architecture",
        "context_limit",
        "capabilities",
        "runtime",
        "runtime_version",
        "renderer",
        "parser",
        "legacy_template",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_version": self.adapter_version,
            "architecture": self.architecture,
            "capabilities": list(self.capabilities),
            "context_limit": self.context_limit,
            "decoding": {key: value for key, value in self.decoding},
            "family": self.family,
            "legacy_template": self.legacy_template,
            "lineage": self.lineage,
            "lineage_evidence": self.lineage_evidence,
            "model_digest": self.model_digest,
            "model_name": self.model_name,
            "output_format": self.output_format,
            "output_schema_sha256": self.output_schema_sha256,
            "parameter_count": self.parameter_count,
            "parameter_size": self.parameter_size,
            "parser": self.parser,
            "prompt_template_id": self.prompt_template_id,
            "prompt_template_sha256": self.prompt_template_sha256,
            "quantization": self.quantization,
            "renderer": self.renderer,
            "runtime": self.runtime,
            "runtime_version": self.runtime_version,
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_note": self.tokenizer_note,
            "wire_flags": {key: value for key, value in self.wire_flags},
        }

    @property
    def digest(self) -> str:
        """``sha256`` of the canonical JSON of every field.  Deterministic across processes."""

        return stable_hash(self.to_dict())

    @property
    def solver_id(self) -> str:
        return f"{self.runtime}:{self.model_name}@{self.model_digest[:12]}#{self.digest[:12]}"

    def decoding_options(self) -> dict[str, Any]:
        return {key: value for key, value in self.decoding}

    def missing_fields(self) -> tuple[str, ...]:
        """Identity fields that are empty.  A complete identity has none."""

        empty: list[str] = []
        for key, value in sorted(self.to_dict().items()):
            if value == "" or value == 0 or value == [] or value == {}:
                empty.append(key)
        return tuple(empty)

    def assert_matches(self, served: SolverIdentity) -> None:
        """Raise unless ``served`` agrees on every field describing the model itself."""

        differences = [
            f"{name}: recorded={getattr(self, name)!r} served={getattr(served, name)!r}"
            for name in self.SERVED_FIELDS
            if getattr(self, name) != getattr(served, name)
        ]
        if differences:
            raise SolverIdentityMismatch(
                "the served model does not match the recorded solver identity; refusing to run "
                "(" + "; ".join(differences) + ")"
            )


def _decoding_pairs(
    decoding: Mapping[str, Any],
) -> tuple[tuple[str, str | int | float | bool], ...]:
    return tuple(sorted((str(key), value) for key, value in decoding.items()))


def _wire_pairs(flags: Mapping[str, bool]) -> tuple[tuple[str, bool], ...]:
    return tuple(sorted((str(key), bool(value)) for key, value in flags.items()))


def _tokenizer_note(runtime_version: str) -> str:
    return (
        f"no tokenizer metadata is exposed by /api/show for this safetensors model, and Ollama "
        f"{runtime_version} has no /api/tokenize endpoint (verified 404). Per-call counts are the "
        "server's own prompt_eval_count/eval_count; a pre-send count comes from the repository's "
        "num_predict=1 preflight (arena.experiments.ollama_live.OllamaPreflightTokenCounter), "
        "which is taken at raw=True and therefore excludes the renderer's chat framing."
    )


#: The identity verified against the live runtime on 2026-09-08.  A live
#: :func:`identity_from_live` must equal this on every served field or the run is refused.
RECORDED_SOLVER = SolverIdentity(
    model_name=INSTALLED_MODEL_NAME,
    model_digest="d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7",
    parameter_size="27.8B",
    parameter_count=27781081984,
    quantization="nvfp4",
    family="qwen3_5",
    architecture="qwen3_5",
    context_limit=262144,
    capabilities=("completion", "thinking", "tools", "vision"),
    runtime="ollama",
    runtime_version="0.33.2",
    renderer="qwen3.5",
    parser="qwen3.5",
    legacy_template="{{ .Prompt }}",
    tokenizer_id="ollama-served:d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7",
    tokenizer_note=_tokenizer_note("0.33.2"),
    prompt_template_id=PROMPT_TEMPLATE_ID,
    prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
    output_format="json-object-tactic-v1",
    output_schema_sha256=TACTIC_RESPONSE_SCHEMA_SHA256,
    decoding=_decoding_pairs(FROZEN_DECODING),
    wire_flags=_wire_pairs(WIRE_FLAGS),
    lineage="UNKNOWN",
    lineage_evidence=INSTALLED_LINEAGE_EVIDENCE,
)


def _modelfile_directive(modelfile: str, keyword: str) -> str:
    for line in modelfile.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{keyword} "):
            return stripped[len(keyword) + 1 :].strip()
    return ""


def identity_from_live(
    model_name: str = INSTALLED_MODEL_NAME,
    *,
    endpoint: str = OLLAMA_ENDPOINT,
    transport: Transport | None = None,
) -> SolverIdentity:
    """Build a :class:`SolverIdentity` from ``/api/version``, ``/api/show`` and ``/api/tags``.

    Nothing is inferred: the digest comes from ``/api/tags`` (``/api/show`` does not report one),
    the renderer and parser come from the served Modelfile, and ``lineage`` is left ``UNKNOWN``.
    """

    call = transport or urllib_transport
    base = endpoint.rstrip("/")
    version = str(call(f"{base}/api/version", None).get("version", ""))
    show = call(f"{base}/api/show", {"model": model_name})
    tags = call(f"{base}/api/tags", None)

    digest = ""
    for entry in tags.get("models", []) or []:
        if isinstance(entry, Mapping) and entry.get("model") == model_name:
            digest = str(entry.get("digest", ""))
            break
    if not digest:
        raise SolverIdentityMismatch(
            f"{model_name!r} is not served by {base}; /api/tags lists no such model"
        )

    details = show.get("details") or {}
    info = show.get("model_info") or {}
    architecture = str(info.get("general.architecture", ""))
    modelfile = str(show.get("modelfile", ""))
    context_limit = int(info.get(f"{architecture}.context_length", 0) or 0)
    return SolverIdentity(
        model_name=model_name,
        model_digest=digest,
        parameter_size=str(details.get("parameter_size", "")),
        parameter_count=int(info.get("general.parameter_count", 0) or 0),
        quantization=str(details.get("quantization_level", "")),
        family=str(details.get("family", "")),
        architecture=architecture,
        context_limit=context_limit,
        capabilities=tuple(sorted(str(item) for item in show.get("capabilities", []) or [])),
        runtime="ollama",
        runtime_version=version,
        renderer=_modelfile_directive(modelfile, "RENDERER"),
        parser=_modelfile_directive(modelfile, "PARSER"),
        legacy_template=str(show.get("template", "")),
        tokenizer_id=f"ollama-served:{digest}",
        tokenizer_note=_tokenizer_note(version),
        prompt_template_id=PROMPT_TEMPLATE_ID,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
        output_format="json-object-tactic-v1",
        output_schema_sha256=TACTIC_RESPONSE_SCHEMA_SHA256,
        decoding=_decoding_pairs(FROZEN_DECODING),
        wire_flags=_wire_pairs(WIRE_FLAGS),
        lineage="UNKNOWN",
        lineage_evidence=INSTALLED_LINEAGE_EVIDENCE,
    )


# ---------------------------------------------------------------------------------------------
# The proposal
# ---------------------------------------------------------------------------------------------


class ProposalStatus(StrEnum):
    """Every way a call can end.  Only :attr:`OK` carries a tactic."""

    OK = "OK"
    #: Output arrived and is not a usable tactic: prose, empty, wrong key, wrong type.
    PARSE_FAILURE = "PARSE_FAILURE"
    #: The generation hit ``num_predict`` before finishing.  Kept apart from ``PARSE_FAILURE``
    #: because "we cut it off" and "it emitted garbage" are different findings.
    TRUNCATED = "TRUNCATED"
    #: Refused before sending, on a preflight count.  Costs no generation.
    PROMPT_OVER_BUDGET = "PROMPT_OVER_BUDGET"
    #: The runtime could not be reached, or answered with something that is not JSON.
    TRANSPORT_FAILURE = "TRANSPORT_FAILURE"


@dataclass(frozen=True, slots=True)
class TacticProposal:
    """One ``state -> action`` attempt, with everything needed to audit it."""

    status: ProposalStatus
    tactic: str | None
    raw_output: str
    prompt_sha256: str
    latency_ms: int
    solver_digest: str
    step_index: int
    state_id: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    done_reason: str = ""
    #: Reasoning text the runtime returned anyway.  Recorded so its presence is visible; it is
    #: never parsed and never becomes the action.
    thinking: str = ""
    failure_detail: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def actionable(self) -> bool:
        return self.status is ProposalStatus.OK and bool(self.tactic)

    @property
    def tactic_head(self) -> str:
        stripped = (self.tactic or "").strip()
        if not stripped:
            return ""
        return stripped.split()[0].rstrip(";").rstrip("[")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "tactic": self.tactic,
            "tactic_head": self.tactic_head,
            "raw_output": self.raw_output,
            "prompt_sha256": self.prompt_sha256,
            "latency_ms": self.latency_ms,
            "solver_digest": self.solver_digest,
            "step_index": self.step_index,
            "state_id": self.state_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "done_reason": self.done_reason,
            "thinking_chars": len(self.thinking),
            "failure_detail": self.failure_detail,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True, slots=True)
class ParseResult:
    """``tactic is None`` means the text is not a usable action; ``detail`` says why."""

    tactic: str | None
    detail: str = ""


def parse_tactic_response(text: str) -> ParseResult:
    """Read the frozen ``{"tactic": "..."}`` format.  Strict, and it never repairs.

    The only normalisation is stripping surrounding whitespace from the payload and from the
    tactic itself.  A markdown fence, a preamble, a second key, a non-string value or an empty
    tactic are all failures rather than something to salvage: under the grammar the model cannot
    produce them, so if one appears the assumption that the channel is constrained has broken and
    that is worth seeing.
    """

    payload = text.strip()
    if not payload:
        return ParseResult(None, "empty output")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as error:
        return ParseResult(None, f"not JSON ({error.msg} at char {error.pos})")
    if not isinstance(parsed, dict):
        return ParseResult(None, f"not a JSON object (got {type(parsed).__name__})")
    keys = set(parsed)
    if keys != {"tactic"}:
        return ParseResult(None, f"expected exactly the key 'tactic', got {sorted(keys)}")
    value = parsed["tactic"]
    if not isinstance(value, str):
        return ParseResult(None, f"'tactic' is {type(value).__name__}, not a string")
    tactic = value.strip()
    if not tactic:
        return ParseResult(None, "'tactic' is empty")
    return ParseResult(tactic)


# ---------------------------------------------------------------------------------------------
# The protocol
# ---------------------------------------------------------------------------------------------


@runtime_checkable
class Solver(Protocol):
    """``pi``: the thing under measurement.  One observation in, one proposal out."""

    @property
    def identity(self) -> SolverIdentity: ...

    def propose(
        self, observation: RenderedObservation, *, budget: ProposalBudget = ...
    ) -> TacticProposal: ...


# ---------------------------------------------------------------------------------------------
# The real one
# ---------------------------------------------------------------------------------------------


class OllamaTacticSolver:
    """The live Solver: one ``/api/generate`` call per proposal, grammar-constrained.

    ``transport`` is ``(url, json_payload_or_None) -> parsed JSON`` -- the same signature as
    :data:`arena.experiments.ollama_live.Transport`, so the production transport is that module's
    and a test substitutes a fake.  ``token_counter`` is optional; wiring one turns
    ``budget.max_prompt_tokens`` into a pre-send refusal instead of a wasted generation.
    """

    def __init__(
        self,
        identity: SolverIdentity = RECORDED_SOLVER,
        *,
        endpoint: str = OLLAMA_ENDPOINT,
        transport: Transport | None = None,
        token_counter: OllamaPreflightTokenCounter | None = None,
    ) -> None:
        self._identity = identity
        self.endpoint = endpoint.rstrip("/")
        self._transport: Transport = transport or urllib_transport
        self.token_counter = token_counter
        self.calls = 0

    @property
    def identity(self) -> SolverIdentity:
        return self._identity

    def verify_served(self) -> SolverIdentity:
        """Refuse to run unless the live runtime serves exactly the recorded model."""

        served = identity_from_live(
            self._identity.model_name, endpoint=self.endpoint, transport=self._transport
        )
        self._identity.assert_matches(served)
        return served

    def payload(self, prompt: str, *, budget: ProposalBudget) -> dict[str, Any]:
        options = self._identity.decoding_options()
        if budget.max_output_tokens is not None:
            options["num_predict"] = int(budget.max_output_tokens)
        wire = dict(self._identity.wire_flags)
        return {
            "model": self._identity.model_name,
            "prompt": prompt,
            "stream": bool(wire.get("stream", False)),
            "raw": bool(wire.get("raw", False)),
            "think": bool(wire.get("think", False)),
            "format": dict(TACTIC_RESPONSE_SCHEMA),
            "options": options,
        }

    def propose(
        self, observation: RenderedObservation, *, budget: ProposalBudget = DEFAULT_BUDGET
    ) -> TacticProposal:
        prompt = build_prompt(observed_state_text(observation))
        prompt_sha = _sha256(prompt)
        payload = self.payload(prompt, budget=budget)
        provenance: dict[str, Any] = {
            "adapter_version": SOLVER_ADAPTER_VERSION,
            "endpoint": self.endpoint,
            "prompt_template_id": self._identity.prompt_template_id,
            "prompt_template_sha256": self._identity.prompt_template_sha256,
            "output_format": self._identity.output_format,
            "output_schema_sha256": self._identity.output_schema_sha256,
            "decoding": dict(payload["options"]),
            "wire_flags": {key: payload[key] for key in ("raw", "think", "stream")},
            "budget": budget.to_dict(),
            "observed_field": OBSERVED_FIELD,
            "token_accounting": "ollama server-reported prompt_eval_count/eval_count",
        }
        if budget.max_output_tokens is not None:
            provenance["num_predict_override"] = int(budget.max_output_tokens)

        def failed(
            status: ProposalStatus,
            detail: str,
            *,
            latency_ms: int,
            raw_output: str = "",
            prompt_tokens: int | None = None,
            completion_tokens: int | None = None,
            done_reason: str = "",
            thinking: str = "",
        ) -> TacticProposal:
            return TacticProposal(
                status=status,
                tactic=None,
                raw_output=raw_output,
                prompt_sha256=prompt_sha,
                latency_ms=latency_ms,
                solver_digest=self._identity.digest,
                step_index=int(observation.step_index),
                state_id=str(observation.state_id),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                done_reason=done_reason,
                thinking=thinking,
                failure_detail=detail,
                provenance=provenance,
            )

        if self.token_counter is not None and budget.max_prompt_tokens is not None:
            started = time.perf_counter()
            counted = self.token_counter.count_tokens(prompt)
            elapsed = int((time.perf_counter() - started) * 1000)
            provenance["preflight_prompt_tokens"] = counted
            provenance["preflight_tokenizer_id"] = self.token_counter.tokenizer_id
            if counted > budget.max_prompt_tokens:
                return failed(
                    ProposalStatus.PROMPT_OVER_BUDGET,
                    f"preflight counted {counted} prompt tokens, over the budget of "
                    f"{budget.max_prompt_tokens}; not sent",
                    latency_ms=elapsed,
                    prompt_tokens=counted,
                )

        started = time.perf_counter()
        try:
            raw = self._transport(f"{self.endpoint}/api/generate", payload)
        except Exception as error:  # a dead runtime is an outcome, not a crash
            return failed(
                ProposalStatus.TRANSPORT_FAILURE,
                repr(error),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        latency_ms = int((time.perf_counter() - started) * 1000)
        self.calls += 1

        if not isinstance(raw, Mapping):
            return failed(
                ProposalStatus.TRANSPORT_FAILURE,
                f"/api/generate returned {type(raw).__name__}, not a JSON object",
                latency_ms=latency_ms,
            )
        text = str(raw.get("response", "") or "")
        thinking = str(raw.get("thinking", "") or "")
        done_reason = str(raw.get("done_reason", "") or "")
        prompt_tokens = int(raw.get("prompt_eval_count", 0) or 0) or None
        completion_tokens = int(raw.get("eval_count", 0) or 0) or None
        if thinking:
            provenance["thinking_emitted"] = True
            provenance["thinking_chars"] = len(thinking)

        parsed = parse_tactic_response(text)
        if parsed.tactic is None:
            truncated = done_reason == "length"
            detail = parsed.detail
            if truncated:
                detail = f"{detail}; generation stopped at num_predict (done_reason=length)"
            if thinking and not text:
                detail = (
                    f"{detail}; the runtime returned {len(thinking)} characters of reasoning "
                    "despite think=false and an empty response"
                )
            return failed(
                ProposalStatus.TRUNCATED if truncated else ProposalStatus.PARSE_FAILURE,
                detail,
                latency_ms=latency_ms,
                raw_output=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                done_reason=done_reason,
                thinking=thinking,
            )
        return TacticProposal(
            status=ProposalStatus.OK,
            tactic=parsed.tactic,
            raw_output=text,
            prompt_sha256=prompt_sha,
            latency_ms=latency_ms,
            solver_digest=self._identity.digest,
            step_index=int(observation.step_index),
            state_id=str(observation.state_id),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            done_reason=done_reason,
            thinking=thinking,
            provenance=provenance,
        )


def preflight_counter(
    identity: SolverIdentity = RECORDED_SOLVER,
    *,
    cache_dir: str | Path,
    endpoint: str = OLLAMA_ENDPOINT,
    transport: Transport | None = None,
) -> OllamaPreflightTokenCounter:
    """The repository's exact counter, bound to this identity's template hash.

    Reused by import, never re-implemented: it is the only exact pre-send count available on a
    runtime with no ``/api/tokenize``.
    """

    return OllamaPreflightTokenCounter(
        {"name": identity.model_name, "digest": identity.model_digest},
        num_ctx=int(identity.decoding_options()["num_ctx"]),
        cache_dir=cache_dir,
        endpoint=endpoint,
        template_hash=identity.prompt_template_sha256,
        transport=transport,
        seed=int(identity.decoding_options()["seed"]),
    )


# ---------------------------------------------------------------------------------------------
# The offline one
# ---------------------------------------------------------------------------------------------


class ScriptedSolver:
    """A deterministic, offline Solver: no runtime, no network, no clock-dependent behaviour.

    It is what the arena's own tests drive, and what a control arm uses.  A scripted value of
    ``None`` yields a :attr:`ProposalStatus.PARSE_FAILURE`, so the failure path is exercisable
    without a model.  Token counts are reported as ``None`` rather than estimated: there is no
    tokenizer here, and a plausible-looking surrogate would be worse than an honest absence.
    """

    def __init__(
        self,
        script: Mapping[str, str | None] | None = None,
        *,
        default: str | None = None,
        name: str = "scripted-solver-v0",
    ) -> None:
        self.script: dict[str, str | None] = dict(script or {})
        self.default = default
        self.name = name
        self.calls = 0
        content = stable_hash(
            {"name": name, "script": dict(sorted(self.script.items())), "default": default}
        )
        self._identity = SolverIdentity(
            model_name=name,
            model_digest=content,
            parameter_size="0",
            parameter_count=0,
            quantization="none",
            family="scripted",
            architecture="scripted",
            context_limit=0,
            capabilities=("completion",),
            runtime="scripted",
            runtime_version=SOLVER_ADAPTER_VERSION,
            renderer="none",
            parser="none",
            legacy_template="none",
            tokenizer_id="none",
            tokenizer_note="no tokenizer: this solver emits pre-written strings",
            prompt_template_id=PROMPT_TEMPLATE_ID,
            prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
            output_format="json-object-tactic-v1",
            output_schema_sha256=TACTIC_RESPONSE_SCHEMA_SHA256,
            decoding=(("deterministic", True),),
            wire_flags=(("offline", True),),
            lineage="NOT_A_MODEL",
            lineage_evidence="a fixed lookup table written by the test author",
        )

    @property
    def identity(self) -> SolverIdentity:
        return self._identity

    def propose(
        self, observation: RenderedObservation, *, budget: ProposalBudget = DEFAULT_BUDGET
    ) -> TacticProposal:
        prompt = build_prompt(observed_state_text(observation))
        self.calls += 1
        state_id = str(observation.state_id)
        tactic = self.script.get(state_id, self.default)
        raw = "" if tactic is None else json.dumps({"tactic": tactic})
        parsed = parse_tactic_response(raw)
        provenance = {
            "adapter_version": SOLVER_ADAPTER_VERSION,
            "scripted": True,
            "budget": budget.to_dict(),
            "observed_field": OBSERVED_FIELD,
            "token_accounting": "none (offline scripted solver has no tokenizer)",
        }
        return TacticProposal(
            status=ProposalStatus.OK if parsed.tactic is not None else ProposalStatus.PARSE_FAILURE,
            tactic=parsed.tactic,
            raw_output=raw,
            prompt_sha256=_sha256(prompt),
            latency_ms=0,
            solver_digest=self._identity.digest,
            step_index=int(observation.step_index),
            state_id=state_id,
            prompt_tokens=None,
            completion_tokens=None,
            done_reason="scripted",
            failure_detail=parsed.detail,
            provenance=provenance,
        )


# ---------------------------------------------------------------------------------------------
# Live smoke
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SmokeGoal:
    """A hand-written Lean 4 proof state.  Not drawn from the bank, so nothing is contaminated."""

    state_id: str
    goals_pp: str
    n_goals: int = 1

    @property
    def step_index(self) -> int:
        return 0

    @property
    def rendered(self) -> Mapping[str, Any]:
        return {"renderer_id": "goal-text-v0", "goals_pp": self.goals_pp}


SMOKE_GOALS: tuple[SmokeGoal, ...] = (
    SmokeGoal("smoke-add-comm", "a b : Nat\n⊢ a + b = b + a"),
    SmokeGoal("smoke-refl", "n : Nat\n⊢ n = n"),
    SmokeGoal("smoke-intro", "p q : Prop\n⊢ p → q → p"),
    SmokeGoal("smoke-list-append-nil", "α : Type u_1\nl : List α\n⊢ l ++ [] = l"),
    SmokeGoal(
        "smoke-two-goals",
        "case left\np q : Prop\nhp : p\nhq : q\n⊢ p\n\ncase right\np q : Prop\nhp : p\nhq : q\n⊢ q",
        n_goals=2,
    ),
)


def live_smoke(
    goals: Iterable[SmokeGoal] = SMOKE_GOALS,
    *,
    solver: OllamaTacticSolver | None = None,
    budget: ProposalBudget = DEFAULT_BUDGET,
    max_calls: int = 20,
) -> list[dict[str, Any]]:
    """A handful of real calls, fully logged.  Every call is counted against ``max_calls``."""

    driver = solver or OllamaTacticSolver()
    rows: list[dict[str, Any]] = []
    for goal in goals:
        if len(rows) >= max_calls:
            break
        proposal = driver.propose(goal, budget=budget)
        row = proposal.to_dict()
        row["goals_pp"] = goal.goals_pp
        row["prompt"] = build_prompt(goal.goals_pp)
        rows.append(row)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Live smoke for the HC-V0.5 Solver adapter (makes real model calls)."
    )
    parser.add_argument("--endpoint", default=OLLAMA_ENDPOINT)
    parser.add_argument("--max-calls", type=int, default=20)
    parser.add_argument("--out", type=Path, default=None, help="write one JSON row per call")
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="do not compare the served model against the recorded identity first",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - needs a live runtime
    args = build_parser().parse_args(argv)
    solver = OllamaTacticSolver(endpoint=args.endpoint)
    if not args.skip_verify:
        served = solver.verify_served()
        print(json.dumps({"served_identity": served.to_dict(), "digest": served.digest}, indent=2))
    rows = live_smoke(solver=solver, max_calls=int(args.max_calls))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    ok = sum(1 for row in rows if row["status"] == ProposalStatus.OK.value)
    print(f"\n{ok}/{len(rows)} proposals parsed; solver calls made: {solver.calls}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
