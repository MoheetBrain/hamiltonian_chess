"""Enumerate every model the local Ollama runtime serves, with nothing inferred.

Facts come from ``/api/version``, ``/api/tags`` and ``/api/show``.  A shared name prefix is not
recorded as evidence of anything: the pairwise family classification below is decided from the
architecture string, the ``details.family`` field, the declared context length and the digest,
and every pair the runtime cannot settle is left ``UNKNOWN``.
"""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

from arena.experiments.ollama_live import urllib_transport
from arena.trajectory.solver import OLLAMA_ENDPOINT, identity_from_live

OUT = Path("research/phase10/models/out/inventory.json")


def _directive(modelfile: str, keyword: str) -> str:
    for line in modelfile.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{keyword} "):
            return stripped[len(keyword) + 1 :].strip()
    return ""


def collect(endpoint: str = OLLAMA_ENDPOINT) -> dict[str, Any]:
    base = endpoint.rstrip("/")
    version = str(urllib_transport(f"{base}/api/version", None).get("version", ""))
    tags = urllib_transport(f"{base}/api/tags", None)

    models: list[dict[str, Any]] = []
    for entry in sorted(tags.get("models", []) or [], key=lambda e: str(e.get("model", ""))):
        name = str(entry["model"])
        show = urllib_transport(f"{base}/api/show", {"model": name})
        details = show.get("details") or {}
        info = show.get("model_info") or {}
        arch = str(info.get("general.architecture", ""))
        modelfile = str(show.get("modelfile", ""))
        identity = identity_from_live(name, endpoint=endpoint)
        models.append(
            {
                "name": name,
                "digest": str(entry.get("digest", "")),
                "modified_at": str(entry.get("modified_at", "")),
                "size_bytes_on_disk": int(entry.get("size", 0) or 0),
                "format": str(details.get("format", "")),
                # /api/tags and /api/show disagree for the safetensors model; record both.
                "tags_family": str((entry.get("details") or {}).get("family", "")),
                "tags_families": (entry.get("details") or {}).get("families"),
                "tags_parameter_size": str((entry.get("details") or {}).get("parameter_size", "")),
                "show_family": str(details.get("family", "")),
                "show_families": details.get("families"),
                "show_parameter_size": str(details.get("parameter_size", "")),
                "parameter_count": int(info.get("general.parameter_count", 0) or 0),
                "quantization_level": str(details.get("quantization_level", "")),
                "architecture": arch,
                "context_length": int(info.get(f"{arch}.context_length", 0) or 0),
                "embedding_length": int(info.get(f"{arch}.embedding_length", 0) or 0),
                "block_count": int(info.get(f"{arch}.block_count", 0) or 0),
                "head_count": int(info.get(f"{arch}.attention.head_count", 0) or 0),
                "head_count_kv": int(info.get(f"{arch}.attention.head_count_kv", 0) or 0),
                # No installed model reports a vocabulary size (`tokenizer.ggml.tokens` is null
                # on every one of them), so this is recorded as not-reported rather than as 0.
                "vocab_size": "NOT_REPORTED_BY_RUNTIME",
                "tokenizer_model": str(info.get("tokenizer.ggml.model", "")),
                "tokenizer_pre": str(info.get("tokenizer.ggml.pre", "")),
                "general_name": str(info.get("general.name", "")),
                "general_basename": str(info.get("general.basename", "")),
                "general_finetune": str(info.get("general.finetune", "")),
                "general_size_label": str(info.get("general.size_label", "")),
                "general_license": str(info.get("general.license", "")),
                # The only training-provenance field any installed model exposes.  Absent on most.
                "declared_base_model": {
                    "name": str(info.get("general.base_model.0.name", "")),
                    "organization": str(info.get("general.base_model.0.organization", "")),
                    "repo_url": str(info.get("general.base_model.0.repo_url", "")),
                },
                "capabilities": sorted(str(c) for c in show.get("capabilities", []) or []),
                "renderer": _directive(modelfile, "RENDERER"),
                "parser": _directive(modelfile, "PARSER"),
                "legacy_template": str(show.get("template", "")),
                "runtime": "ollama",
                "runtime_version": version,
                "lineage": identity.lineage,
                "lineage_evidence": identity.lineage_evidence,
                "solver_identity_digest": identity.digest,
            }
        )

    return {
        "schema": "hc-v0.6-model-inventory-v1",
        "endpoint": base,
        "runtime": "ollama",
        "runtime_version": version,
        "models": models,
        "pairwise": classify_pairs(models),
    }


def classify_pairs(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify each pair from runtime-reported structure, never from the tag name."""

    out: list[dict[str, Any]] = []
    for left, right in combinations(models, 2):
        same_arch = bool(left["architecture"]) and left["architecture"] == right["architecture"]
        same_family = bool(left["show_family"]) and left["show_family"] == right["show_family"]
        same_tok = (
            bool(left["tokenizer_model"])
            and left["tokenizer_model"] == right["tokenizer_model"]
            and left["tokenizer_pre"] == right["tokenizer_pre"]
        )
        evidence = {
            "architecture": [left["architecture"], right["architecture"]],
            "show_family": [left["show_family"], right["show_family"]],
            "context_length": [left["context_length"], right["context_length"]],
            "tokenizer": [
                f"{left['tokenizer_model']}/{left['tokenizer_pre']}",
                f"{right['tokenizer_model']}/{right['tokenizer_pre']}",
            ],
            "digest": [left["digest"][:12], right["digest"][:12]],
            "parameter_count": [left["parameter_count"], right["parameter_count"]],
            "quantization_level": [left["quantization_level"], right["quantization_level"]],
        }
        if same_arch and same_family:
            relation = "SAME_FAMILY_VARIANT"
            reason = (
                "same general.architecture and same details.family; an ARCHITECTURE-family "
                "statement only. Differences: "
                + ", ".join(
                    part
                    for part in (
                        "parameter count"
                        if left["parameter_count"] != right["parameter_count"]
                        else "",
                        "context length"
                        if left["context_length"] != right["context_length"]
                        else "",
                        "tokenizer metadata encoding" if not same_tok else "",
                        "quantization"
                        if left["quantization_level"] != right["quantization_level"]
                        else "",
                    )
                    if part
                )
                or "none reported"
            )
        elif not same_arch and left["architecture"] and right["architecture"]:
            relation = "DISTINCT_MODEL_FAMILY"
            reason = (
                f"different general.architecture strings ({left['architecture']!r} vs "
                f"{right['architecture']!r}) and different details.family"
            )
        else:
            relation = "UNKNOWN"
            reason = "the runtime does not report enough to decide; name prefix is not evidence"
        out.append(
            {
                "a": left["name"],
                "b": right["name"],
                "relation": relation,
                "reason": reason,
                "evidence": evidence,
                "training_lineage": (
                    "UNKNOWN -- no runtime field records training data, base checkpoint or "
                    "fine-tuning history for both members of this pair"
                ),
            }
        )
    return out


def main() -> int:
    payload = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(payload['models'])} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
