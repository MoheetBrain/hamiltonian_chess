"""Fail-closed spend gate for GPU work.  No GPU, no model, no network in this module.

``arena/training/gpu_matched_runner.py`` refuses to run without CUDA, which stops it on a
laptop but does nothing on a rented GPU box: there, a bare invocation starts spending
immediately, on whatever design happened to be in the working tree.  A CUDA check is a
capability check, not an authorisation check.

This gate is the authorisation check.  It requires three independent things, and refuses
unless all three agree:

1. **An explicit in-process flag** -- someone wrote the intent into the invocation.
2. **An environment variable** -- the machine itself is marked as authorised to spend, so a
   script copied onto an unauthorised box does not run there.
3. **A preregistration document whose content hash matches an expected hash supplied by the
   caller** -- the design being run is the design that was written down beforehand.  The
   expected hash is a *parameter*, never a constant in this file: a hash baked into the
   source could be edited in the same commit that changes the design, which would make the
   check ceremonial rather than binding.

Requirements 1 and 2 stop an accidental run.  Requirement 3 stops the more interesting
failure: a run that was authorised, but of a different experiment than the one preregistered.

Every ambiguity fails closed.  A missing variable, an empty file, a blank expected hash and a
malformed expected hash are all refusals, never passes, because "we could not tell" must
never be spelled the same way as "yes".

Call site to add at the top of ``gpu_matched_runner.main()``, before any CUDA work::

    require_gpu_authorisation(
        authorized=args.i_authorize_gpu_spend,
        preregistration_path=args.preregistration,
        expected_preregistration_hash=args.preregistration_sha256,
        run_label="route-b-learning-curve",
    )

The runner is deliberately not modified here; wiring it up is a separate, reviewed change.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GPU_AUTHORISATION_SCHEMA_VERSION = "arena-gpu-authorisation-v1.0.0"

#: The machine-level switch.  Named so it cannot be confused with a debug or dry-run toggle.
GPU_AUTHORISATION_ENV_VAR = "ARENA_GPU_SPEND_AUTHORIZED"

#: The only accepted value.  Any other value -- including "true", "yes" or "0" -- is refused,
#: so a half-remembered spelling cannot accidentally authorise spending.
GPU_AUTHORISATION_ENV_VALUE = "1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class GpuAuthorisationError(RuntimeError):
    """GPU work was requested without complete, matching authorisation."""


@dataclass(frozen=True, slots=True)
class GpuAuthorisation:
    """Evidence that a specific preregistered design was authorised on this machine."""

    run_label: str
    preregistration_path: str
    preregistration_sha256: str
    env_var: str
    schema_version: str = GPU_AUTHORISATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_label": self.run_label,
            "preregistration_path": self.preregistration_path,
            "preregistration_sha256": self.preregistration_sha256,
            "env_var": self.env_var,
        }


def preregistration_hash(path: Path | str) -> str:
    """SHA-256 of the preregistration document's exact bytes.

    Bytes, not parsed content: a preregistration is a human commitment, and reformatting it
    is a change to that commitment as far as this gate is concerned.
    """

    document = Path(path)
    try:
        payload = document.read_bytes()
    except OSError as error:
        raise GpuAuthorisationError(
            f"preregistration document could not be read: {document}: {error}"
        ) from error
    return hashlib.sha256(payload).hexdigest()


def require_gpu_authorisation(
    *,
    authorized: bool,
    preregistration_path: Path | str,
    expected_preregistration_hash: str,
    run_label: str,
    env: Mapping[str, str] | None = None,
) -> GpuAuthorisation:
    """Raise unless flag, environment and preregistration all authorise this exact design.

    Returns a record suitable for writing into the run's artefact, so the authorisation that
    permitted the spend is stored alongside the results rather than remembered.
    """

    environment = os.environ if env is None else env

    if not isinstance(run_label, str) or not run_label.strip():
        raise GpuAuthorisationError(
            "GPU work refused: run_label is missing. Pass a short label naming the run, "
            "e.g. run_label='route-b-learning-curve', so the spend is attributable."
        )

    # `is not True` rather than falsiness: a truthy string such as "no" must not authorise.
    if authorized is not True:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: the explicit authorisation flag is not set "
            f"(got {authorized!r}, required literal True). Pass authorized=True only from an "
            f"invocation that a human deliberately wrote, e.g. --i-authorize-gpu-spend."
        )

    if GPU_AUTHORISATION_ENV_VAR not in environment:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: environment variable "
            f"{GPU_AUTHORISATION_ENV_VAR} is not set. Set "
            f"{GPU_AUTHORISATION_ENV_VAR}={GPU_AUTHORISATION_ENV_VALUE} on the machine that "
            f"is authorised to spend, so this script cannot spend anywhere else."
        )
    observed_env = environment[GPU_AUTHORISATION_ENV_VAR]
    if observed_env != GPU_AUTHORISATION_ENV_VALUE:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: {GPU_AUTHORISATION_ENV_VAR} is "
            f"{observed_env!r}, and the only accepted value is "
            f"{GPU_AUTHORISATION_ENV_VALUE!r}. Nothing else is treated as consent."
        )

    if not isinstance(expected_preregistration_hash, str):
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: expected_preregistration_hash must be a "
            f"64-character lowercase hex SHA-256, got {type(expected_preregistration_hash).__name__}."
        )
    expected = expected_preregistration_hash.strip()
    if not expected:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: expected_preregistration_hash is empty. "
            f"An unspecified expected hash cannot certify anything; compute it with "
            f"preregistration_hash(<document>) and record it in the invocation."
        )
    if not _SHA256_RE.fullmatch(expected):
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: expected_preregistration_hash "
            f"{expected!r} is not a 64-character lowercase hex SHA-256."
        )

    document = Path(preregistration_path)
    if not document.exists():
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: preregistration document {document} does "
            f"not exist. An unregistered design may not be run; write the preregistration "
            f"first and point --preregistration at it."
        )
    if not document.is_file():
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: preregistration path {document} is not a "
            f"file. Point --preregistration at the preregistration document itself."
        )
    observed = preregistration_hash(document)
    if not document.stat().st_size:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: preregistration document {document} is "
            f"empty. An empty document registers no design."
        )
    if observed != expected:
        raise GpuAuthorisationError(
            f"GPU work refused for {run_label!r}: preregistration {document} hashes to "
            f"{observed}, but the invocation expected {expected}. Either the design changed "
            f"after it was registered, or the wrong document was supplied. Re-register the "
            f"design deliberately; do not update the expected hash to match."
        )

    return GpuAuthorisation(
        run_label=run_label,
        preregistration_path=str(document),
        preregistration_sha256=observed,
        env_var=GPU_AUTHORISATION_ENV_VAR,
    )


__all__ = [
    "GPU_AUTHORISATION_ENV_VALUE",
    "GPU_AUTHORISATION_ENV_VAR",
    "GPU_AUTHORISATION_SCHEMA_VERSION",
    "GpuAuthorisation",
    "GpuAuthorisationError",
    "preregistration_hash",
    "require_gpu_authorisation",
]
