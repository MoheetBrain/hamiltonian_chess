"""Fitness V7: V5 with a derived frontier target and a per-level shortcut audit.

V7 is a **strictly stricter** instrument than V5.  It changes exactly two things and inherits
everything else from :mod:`arena.experiments.fitness_v5` by import -- probe bank, mechanisms,
ladders, arms, prompt template, response schema, decoding settings, scoring, validity gates and
the abort clause.  It adds a gate; it removes a degree of freedom; it relaxes nothing.

Change 1 -- the frontier target is DERIVED, not declared
--------------------------------------------------------
V5 minimised ``|accuracy - 0.625|`` (``fitness_v5.py:915-948``, constant at ``:213``) while its
own gates made ``[0.70, 0.85]`` the only region in which a mechanism can qualify.  The reason is
arithmetic, not opinion:

* The destroyed twins are *information-identical* with opposite targets.  The same
  ``CanonicalState`` object and the same ``options`` tuple are passed to both siblings and only
  ``expected_index`` differs (``fitness_v5.py:485-486``, asserted at ``:505-509``), and
  ``build_prompt`` (``:550-565``) never sees ``variant`` or ``expected_index``.  A deterministic
  solver therefore returns one answer to one shared prompt, that answer matches exactly one of
  the two opposite targets, and each twin pair contributes exactly one correct row of two.
  Destroyed accuracy is a **constant at 0.5000**, not a measurement.  Verified 24/24 twin pairs
  in the frozen V5 rows: identical ``prompt_hash`` AND byte-identical ``raw_output``.
* Hence ``positive - destroyed >= gap_min`` reduces to ``positive >= 0.5 + gap_min``, i.e.
  ``positive >= 0.70`` at V5's ``gap_min = 0.20``, and with the ``0.85`` ceiling the qualifying
  window is ``[0.70, 0.85]``.  V5 aimed 0.075 *below* its own floor.
* Provenance: V3 (``fitness_v3.py:56,61``) and V4 (``fitness_v4.py:143,148,152``) used
  ``gap_min = 0.10``, which put 0.625 inside the window ``[0.60, 0.85]``.  V5 raised the gap to
  0.20 and left the target untouched.  One uncoordinated constant edit.

V7 computes the target from the gate arithmetic (:func:`derive_frontier`), so the constants can
never drift apart again: move ``gap_min`` and the aim point moves with it.

**The dead gate is dropped.**  V5's ``negative_target_accuracy <= 0.60`` is unreachable and
carries zero information.  Destroyed accuracy is 0.5000 under determinism and validity, and the
only way it can move is *down*: an unparsed destroyed row scores INCORRECT rather than voiding,
so an invalid twin pushes destroyed accuracy **below** 0.5, never above.  No run can make that
gate fire.  V7 keeps the gap gate (which does the work) and removes the ceiling on destroyed
accuracy entirely.

Change 2 -- the shortcut audit runs at EVERY level, and gates on a margin
------------------------------------------------------------------------
V5 ran :func:`arena.experiments.fitness_v5.shortcut_audit` only at the selected frontier, so a
mechanism's shortcut exposure at every other level was **unmeasured**.  That is not a hypothetical
gap on this probe bank: ``first_mentioned_in_state`` scores **1.000** on ``formal_expression_depth``
L1, **0.8333** at L2 and **0.9167** at L3 (0.8125 pooled over the four-level bank) -- numbers this
module reproduces with zero model calls because the audit is a property of the probe bank, not of
the solver.  A selector fix delivered without a per-level audit would move the aim point onto a
level whose answer is legible from a surface cue and manufacture a qualification.

So V7 additionally requires, **at the selected level**, that the solver beat the best shortcut by
a preregistered margin:

    ``positive_accuracy - best_shortcut_accuracy >= SHORTCUT_MARGIN``  (else ``VOID_SHORTCUT``)

``best_shortcut_accuracy`` is V5's own ``worst_score`` -- the best accuracy achievable by any of
V5's seven rules *or its negation*, because a rule that scores 0.333 is a shortcut that scores
0.667 once inverted.  V5's absolute ``worst_score <= 0.75`` gate is kept as well; both report
``VOID_SHORTCUT``.  No new shortcut features are invented: the rule set is imported from V5.

Known inherited edge, documented rather than repaired
-----------------------------------------------------
``0.70 - 0.50`` is ``0.19999999999999996`` in IEEE-754, so V5's inherited gap gate makes the
effective window **half-open at its floor**: a mechanism sitting at exactly 0.700 would void.
V7 does not touch it, because V7 changes only the gates it owns.  It is unreachable on real
data -- positive accuracy is ``k/24``, ``k/48`` or ``k/72`` and none of those is exactly 0.70 --
and it is asserted as a test rather than left to be discovered in a run.  The one gate V7
introduces carries an explicit :data:`GATE_EPSILON` so the new boundary is not decided by
floating-point representation.

Isolation from V5 and Phase 6
-----------------------------
V7 carries its own experiment version, instrument version, runtime hash, cache namespace and
artifact namespace.  No V5 or Phase-6 row can be reused or overwritten
(:func:`assert_v7_namespace`, and the namespace tests).  The **decoding settings sent on the wire
are byte-identical to V5's** -- the V7 runtime hash differs only by an instrument-namespace tag,
which exists precisely so that identical prompts cannot collide across instrument versions.

Cache identity
--------------
Phase 6 accumulated 61 cache hits against a ``cache hits > 0`` invalidation rule, with no way to
tell a legitimate same-condition resume from a cross-condition replay.  V7 records
:data:`CacheScope` per row.  An entry is reusable only when model digest, model template
(tokenizer/revision proxy), prompt bytes, runtime/framing condition, decoding settings, experiment
version, instrument version, solver kind, task ID and candidate ID **all** match.  The cache path
is the hash of that whole identity and the stored identity is re-checked field by field on read,
so ``CROSS_CONDITION`` is impossible by construction; if one is ever presented it raises
:class:`CrossConditionCacheError` rather than being silently consumed.

Reporting discipline
--------------------
V7 reports; it does not decide.  Every level of every mechanism is measured on every arm, so the
artifact carries accuracy, largest answer share, answer entropy, valid rate, destroyed accuracy
and the per-level best shortcut for L0..L3, plus the raw rows.  A reader can recompute the
verdict from the rows without trusting this module's arithmetic.

**No model call is made by importing or testing this module.**  ``--dry-run`` exercises every
path with a deterministic offline stub solver and writes to its own artifact and cache namespaces.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from arena.canonical.schema import canonical_json, stable_hash
from arena.environments.formal_structural import ENVIRONMENT_VERSION
from arena.experiments.fitness_v5 import (
    CONTEXT_GUARD,
    DEFAULT_SOLVER,
    DEV_FAMILIES,
    LADDERS,
    MECHANISMS,
    MODEL_CALL_BUDGET,
    POSITIVE_VARIANTS,
    PROMOTION_RULE,
    QUALIFICATION_RULE,
    RESPONSE_SCHEMA,
    RUNTIME_CONFIG,
    RUNTIME_CONFIG_BARE,
    SOLVERS,
    V5Probe,
    build_dev_pool,
    build_prompt,
    classify_row,
    equal_information_genome,
    parse_response,
    shortcut_audit,
    summarize,
    verify_served_model,
)
from arena.experiments.fitness_v5 import EXPERIMENT_VERSION as V5_EXPERIMENT_VERSION
from arena.experiments.fitness_v5 import INSTRUMENT_VERSION as V5_INSTRUMENT_VERSION
from arena.model_view.genome import ModelViewGenome
from arena.storage.artifacts import ArtifactStore

EXPERIMENT_VERSION = "arena-representation-fitness-v7"
INSTRUMENT_VERSION = "arena-game-r-derived-frontier-instrument-v7.0.0"

#: Namespaces owned by earlier instruments.  V7 must never read or write inside them.
FROZEN_NAMESPACES: tuple[str, ...] = (
    "fitness_v1",
    "fitness_v2",
    "fitness_v3",
    "fitness_v4",
    "fitness_v5",
    "fitness_v6",
    "model_fitness",
)
CACHE_NAMESPACE = "artifacts/cache/fitness_v7"
DRY_RUN_CACHE_NAMESPACE = "artifacts/cache/fitness_v7_dryrun"
ARTIFACT_NAMESPACE = "experiments/fitness_v7"

#: The decoding settings are V5's, byte for byte.  ``RUNTIME_CONFIG_V7`` adds ONLY an instrument
#: namespace tag, which never reaches the wire: it exists so that an identical prompt under
#: identical decoding cannot collide with a V5 or Phase-6 cache entry.  Asserted in the tests.
RUNTIME_CONFIG_V7: dict[str, Any] = {**RUNTIME_CONFIG, "instrument_namespace": INSTRUMENT_VERSION}
RUNTIME_CONFIG_V7_BARE: dict[str, Any] = {
    **RUNTIME_CONFIG_BARE,
    "instrument_namespace": INSTRUMENT_VERSION,
}
RUNTIME_CONFIG_V7_HASH = stable_hash(RUNTIME_CONFIG_V7)
RUNTIME_CONFIG_V7_BARE_HASH = stable_hash(RUNTIME_CONFIG_V7_BARE)

#: The preregistered shortcut margin.  This is a THRESHOLD, not a tuning knob.  It is set once,
#: before any V7 call, and it is not adjusted to change what passes.  If a mechanism voids on it,
#: that is the instrument working.
SHORTCUT_MARGIN = 0.10

#: Binary floating point makes ``0.70 - 0.60 == 0.09999999999999998``, so a mechanism sitting
#: EXACTLY on the margin would void for a representation artefact rather than for a scientific
#: reason.  The tolerance is 1e-9, seven orders of magnitude below the smallest difference this
#: instrument can even express (accuracies are k/24, k/48 or k/72, so the resolution floor is
#: 1/72 = 0.0139).  It therefore cannot change any decision on real data; it only stops the
#: boundary from being decided by IEEE-754.  It is applied ONLY to the gate V7 introduces --
#: every inherited V5 gate keeps V5's comparison exactly as written.
GATE_EPSILON = 1e-9

#: Destroyed-control accuracy is a theorem about the probe construction, not a measurement.
#: See the module docstring.  It is still MEASURED at every level and the measurement is
#: reported next to this constant, so a violation is visible rather than assumed away.
DESTROYED_EXPECTED = 0.50


class CacheScope(StrEnum):
    """Provenance of a single row's model output."""

    FRESH = "FRESH"
    SAME_CONDITION_REUSE = "SAME_CONDITION_REUSE"
    CROSS_CONDITION = "CROSS_CONDITION"


class CrossConditionCacheError(RuntimeError):
    """A cache entry was presented whose identity differs from the requesting condition."""


class SolverKind(StrEnum):
    LIVE = "LIVE"
    STUB = "STUB"


#: ``(probe, prompt) -> raw ollama-shaped response dict``.  Injecting the solver is what makes
#: the whole instrument testable offline: the live adapter ignores the probe, the stub uses it.
SolverCall = Callable[[V5Probe, str], dict[str, Any]]


# --------------------------------------------------------------- derived frontier arithmetic


def derive_frontier(
    gap_min: float | None = None,
    destroyed_expected: float = DESTROYED_EXPECTED,
    band_high: float | None = None,
    band_low: float | None = None,
) -> dict[str, float]:
    """Derive the qualifying window and the frontier aim point from the gate constants.

    ``window_low  = destroyed_expected + gap_min``  -- the gap gate, with destroyed pinned at its
    structural constant, is exactly a floor on positive accuracy.
    ``window_high = band_high``                     -- the ceiling gate.
    ``frontier_target = (window_low + window_high) / 2``

    The point is that ``frontier_target`` is a *function* of the gate constants.  Raise
    ``gap_min`` and the aim point rises with it; there is no second constant to forget.
    """

    rule = QUALIFICATION_RULE
    gap = float(rule["positive_negative_gap_min"]) if gap_min is None else float(gap_min)
    low_band = float(rule["frontier_band"][0]) if band_low is None else float(band_low)
    high = float(rule["frontier_band"][1]) if band_high is None else float(band_high)
    window_low = float(destroyed_expected) + gap
    window_high = high
    if not window_low < window_high:
        raise ValueError(
            f"empty qualifying window: destroyed {destroyed_expected} + gap {gap} = {window_low} "
            f">= ceiling {window_high}. The instrument cannot qualify anything; fix the gates."
        )
    return {
        "destroyed_expected": float(destroyed_expected),
        "gap_min": gap,
        "band_low": low_band,
        "band_high": high,
        "window_low": window_low,
        "window_high": window_high,
        "frontier_target": (window_low + window_high) / 2.0,
    }


FRONTIER = derive_frontier()
FRONTIER_TARGET = FRONTIER["frontier_target"]

#: V7's rule.  Inherited from V5 except for the two changes and the dropped dead gate.
QUALIFICATION_RULE_V7: dict[str, Any] = {
    **{k: v for k, v in QUALIFICATION_RULE.items() if k != "negative_target_accuracy_max"},
    "frontier_target": FRONTIER_TARGET,
    "frontier_target_derivation": (
        "frontier_target = ((destroyed_expected + positive_negative_gap_min) + frontier_band[1])/2"
    ),
    "frontier_selection": (
        "among levels 1..3 minimise |accuracy - frontier_target|, ties to the lower level"
    ),
    "effective_qualifying_window": [FRONTIER["window_low"], FRONTIER["window_high"]],
    "destroyed_expected": DESTROYED_EXPECTED,
    "dropped_gate": {
        "name": "negative_target_accuracy_max",
        "v5_value": 0.60,
        "reason": (
            "unreachable. Destroyed accuracy is 0.5000 under determinism and validity, and an "
            "invalid parse pushes it BELOW 0.5, never above. The gate cannot fire and carries "
            "no information."
        ),
    },
    "shortcut_margin": SHORTCUT_MARGIN,
    "shortcut_margin_gate_epsilon": GATE_EPSILON,
    "shortcut_gate": (
        "at the selected level, positive_accuracy - best_shortcut_accuracy >= shortcut_margin, "
        "AND best_shortcut_accuracy <= shortcut_rule_max; else VOID_SHORTCUT"
    ),
    "shortcut_audit_scope": "EVERY level L0..L3, reported in full; gated at the selected level",
}


def assert_v7_namespace(path: str | Path) -> str:
    """Refuse any path that belongs to a frozen instrument.

    V7 must be unable to read a V5/Phase-6 artifact or cache entry, and unable to overwrite one.
    This is a hard failure, not a warning: a silent namespace collision is exactly the defect
    Phase 6 could not rule out after the fact.
    """

    text = str(path).replace("\\", "/")
    for namespace in FROZEN_NAMESPACES:
        if namespace in text:
            raise ValueError(
                f"V7 refused a frozen-instrument path: {text!r} contains {namespace!r}. "
                "V7 owns fitness_v7 namespaces only."
            )
    return text


# ------------------------------------------------------------------------- cache identity


def cache_identity(
    genome: ModelViewGenome,
    probe: V5Probe,
    prompt: str,
    *,
    solver: Mapping[str, str],
    bare: bool,
    solver_kind: SolverKind,
    model_template_hash: str,
) -> dict[str, Any]:
    """The full reuse key.  Every component must match for an entry to be reusable."""

    return {
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "solver_kind": solver_kind.value,
        "model_digest": str(solver["digest"]),
        "model_template_hash": model_template_hash,
        "runtime_condition": "bare" if bare else "framed",
        "runtime_hash": RUNTIME_CONFIG_V7_BARE_HASH if bare else RUNTIME_CONFIG_V7_HASH,
        "decoding_hash": stable_hash(decoding_settings(bare=bare)),
        "candidate_id": genome.candidate_id,
        "genome_hash": genome.genome_hash,
        "task_id": probe.probe_id,
        "probe_hash": probe.derived_hash,
        "prompt_hash": stable_hash(prompt),
        "prompt_bytes_sha256": stable_hash(prompt),
    }


def q0_cache_identity(
    case: int,
    prompt: str,
    *,
    solver: Mapping[str, str],
    bare: bool,
    solver_kind: SolverKind,
    model_template_hash: str,
) -> dict[str, Any]:
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "solver_kind": solver_kind.value,
        "model_digest": str(solver["digest"]),
        "model_template_hash": model_template_hash,
        "runtime_condition": "bare" if bare else "framed",
        "runtime_hash": RUNTIME_CONFIG_V7_BARE_HASH if bare else RUNTIME_CONFIG_V7_HASH,
        "decoding_hash": stable_hash(decoding_settings(bare=bare)),
        "kind": "Q0",
        "case": case,
        "prompt_hash": stable_hash(prompt),
    }


def decoding_settings(*, bare: bool) -> dict[str, Any]:
    """Exactly the settings that reach the wire.  Byte-identical to V5's -- asserted in tests."""

    config = RUNTIME_CONFIG_BARE if bare else RUNTIME_CONFIG
    return {
        "options": {
            key: value
            for key, value in config.items()
            if key not in {"engine", "think", "format", "raw"}
        },
        "format": RESPONSE_SCHEMA,
        "raw": bool(bare),
        "think": None if bare else bool(config["think"]),
    }


def cache_root(root: Path, *, dry_run: bool) -> Path:
    namespace = DRY_RUN_CACHE_NAMESPACE if dry_run else CACHE_NAMESPACE
    assert_v7_namespace(namespace)
    return Path(root) / namespace


def cache_path(root: Path, identity: Mapping[str, Any], *, dry_run: bool) -> Path:
    return cache_root(root, dry_run=dry_run) / f"{stable_hash(dict(identity))}.json"


def classify_cache_scope(
    stored_identity: Mapping[str, Any] | None, identity: Mapping[str, Any]
) -> CacheScope:
    """FRESH when nothing was stored; otherwise reuse iff every component matches."""

    if stored_identity is None:
        return CacheScope.FRESH
    if dict(stored_identity) == dict(identity):
        return CacheScope.SAME_CONDITION_REUSE
    return CacheScope.CROSS_CONDITION


def cached_call(
    root: Path,
    identity: Mapping[str, Any],
    probe: V5Probe | None,
    prompt: str,
    solver_call: SolverCall,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], CacheScope]:
    path = cache_path(root, identity, dry_run=dry_run)
    assert_v7_namespace(path)
    if path.exists():
        cached = json.loads(path.read_text())
        scope = classify_cache_scope(cached.get("identity"), identity)
        if scope is CacheScope.CROSS_CONDITION:
            raise CrossConditionCacheError(
                f"cache entry {path} was written under a different condition; refusing to reuse "
                "it. This is impossible by construction (the path IS the identity hash), so a "
                "hit here means the cache was tampered with or a hash collided."
            )
        if not isinstance(cached.get("result"), dict):
            raise ValueError(f"invalid V7 cache record: {path}")
        return dict(cached["result"]), scope
    started = time.monotonic()
    try:
        raw = solver_call(probe, prompt) if probe is not None else solver_call(_Q0_PROBE, prompt)
    except Exception as error:  # pragma: no cover - network/runtime failure path
        raw = {
            "response": "",
            "error": repr(error),
            "prompt_eval_count": 0,
            "eval_count": 0,
            "total_duration_ns": int((time.monotonic() - started) * 1e9),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json({"identity": dict(identity), "result": raw}), encoding="utf-8")
    return raw, CacheScope.FRESH


# ------------------------------------------------------------------------------- solvers


def _call_ollama_v7(model: str, prompt: str, *, bare: bool = False) -> dict[str, Any]:
    """Verbatim copy of ``arena.experiments.fitness_v5._call_ollama`` (fitness_v5.py:583-611).

    Copied rather than imported because it is a private helper of a frozen instrument, which may
    not be edited or refactored.  It deliberately reads V5's frozen ``RUNTIME_CONFIG`` /
    ``RUNTIME_CONFIG_BARE`` and ``RESPONSE_SCHEMA``, so the bytes on the wire cannot drift from
    V5's.  ``tests/experiments/test_fitness_v7.py`` asserts the payload equality.
    """

    config = RUNTIME_CONFIG_BARE if bare else RUNTIME_CONFIG
    options = {
        key: value
        for key, value in config.items()
        if key not in {"engine", "think", "format", "raw"}
    }
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": options,
    }
    if bare:
        payload["raw"] = True
    else:
        payload["think"] = config["think"]
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=900) as response:  # noqa: S310 - fixed local service
        raw = json.loads(response.read().decode())
    return {
        "response": str(raw.get("response", "")),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "done_reason": str(raw.get("done_reason", "")),
        "total_duration_ns": int(raw.get("total_duration", 0)),
    }


def ollama_solver(solver: Mapping[str, str], *, bare: bool) -> SolverCall:
    """The live path.  Never invoked by the tests, by ``--dry-run`` or by import."""

    def call(_probe: V5Probe, prompt: str) -> dict[str, Any]:
        return _call_ollama_v7(str(solver["name"]), prompt, bare=bare)

    return call


STUB_SOLVER_DIGEST = "0" * 64
STUB_SOLVER: dict[str, str] = {
    "name": "stub://deterministic-offline",
    "digest": STUB_SOLVER_DIGEST,
    "family": "stub",
    "parameter_size": "0B",
    "quantization": "none",
}


@dataclass(frozen=True, slots=True)
class StubProfile:
    """A preregistered offline behaviour, used only to exercise code paths.

    ``accuracy`` is per ``(mechanism, level)`` on the POSITIVE arms.  Destroyed arms always get a
    single deterministic answer to the shared prompt, which is what makes destroyed accuracy come
    out at the structural 0.5000 -- the dry run therefore *demonstrates* the theorem rather than
    assuming it.  ``invalid_task_ids`` and ``truncated_task_ids`` exercise the validity and
    output-truncation paths.
    """

    accuracy: Mapping[tuple[str, int], float]
    default_accuracy: float = 0.75
    invalid_task_ids: frozenset[str] = frozenset()
    truncated_task_ids: frozenset[str] = frozenset()
    shortcut_feature: str | None = None


#: A SYNTHETIC staircase, chosen only so that ``--dry-run`` walks every branch: the explicit arm
#: passes, a frontier is selected inside the band, the gap/share/invariance gates are evaluated,
#: one mechanism voids on the new shortcut margin and two qualify.  These numbers are made up.
#: They are not a prediction, not a replay of any recorded run, and carry no empirical content.
DEFAULT_STUB_PROFILE = StubProfile(
    accuracy={
        (mechanism, level): value
        for mechanism in MECHANISMS
        for level, value in ((0, 1.00), (1, 0.875), (2, 0.792), (3, 0.625))
    },
    default_accuracy=0.75,
)


def stub_solver(
    probes: Sequence[V5Probe], profile: StubProfile = DEFAULT_STUB_PROFILE
) -> SolverCall:
    """A deterministic solver that makes no network call of any kind.

    Correctness is assigned by a stable rank within each ``(mechanism, level, variant-class)``
    cell, so the realised accuracy hits the requested value exactly and reproduces byte for byte
    across processes.  Destroyed twins share one prompt, so they share one answer.
    """

    positives: dict[tuple[str, int], list[str]] = defaultdict(list)
    for probe in probes:
        if probe.variant.value in POSITIVE_VARIANTS:
            positives[(probe.mechanism, probe.level)].append(probe.probe_id)
    correct_ids: set[str] = set()
    for cell, ids in positives.items():
        ordered = sorted(ids, key=lambda pid: stable_hash(pid))
        target = float(profile.accuracy.get(cell, profile.default_accuracy))
        take = int(round(target * len(ordered)))
        correct_ids.update(ordered[:take])

    def answer_index(probe: V5Probe, prompt: str) -> int:
        if probe.truth_kind == "NEGATIVE_CONTROL_TARGET":
            # One answer to the one shared prompt: the destroyed pair cannot both be right.
            return int(stable_hash(prompt)[0], 16) % 2
        if profile.shortcut_feature is not None:
            return _shortcut_index(probe, profile.shortcut_feature)
        # Swapped arms mirror their base probe's decision, which is what position invariance
        # is defined to measure, so they are always "hit".
        positive = probe.variant.value in POSITIVE_VARIANTS
        hit = (probe.probe_id in correct_ids) if positive else True
        return probe.expected_index if hit else 1 - probe.expected_index

    def call(probe: V5Probe, prompt: str) -> dict[str, Any]:
        if probe.probe_id in profile.truncated_task_ids:
            return {
                "response": '{"choice": ',
                "prompt_eval_count": len(prompt) // 4,
                "eval_count": int(RUNTIME_CONFIG["num_predict"]),
                "done_reason": "length",
                "total_duration_ns": 0,
            }
        if probe.probe_id in profile.invalid_task_ids:
            return {
                "response": "I think the answer is A.",
                "prompt_eval_count": len(prompt) // 4,
                "eval_count": 7,
                "done_reason": "stop",
                "total_duration_ns": 0,
            }
        choice = "A" if answer_index(probe, prompt) == 0 else "B"
        return {
            "response": json.dumps({"choice": choice}),
            "prompt_eval_count": len(prompt) // 4,
            "eval_count": 8,
            "done_reason": "stop",
            "total_duration_ns": 0,
        }

    return call


def _shortcut_index(probe: V5Probe, feature: str) -> int:
    """Answer a probe by one of V5's own shortcut rules, for the VOID_SHORTCUT path."""

    names = (str(probe.options[0].arguments[0].value), str(probe.options[1].arguments[0].value))
    text = canonical_json(probe.state.to_dict(include_display_identity=False))
    if feature == "always_first_option":
        return 0
    if feature == "always_second_option":
        return 1
    if feature == "first_mentioned_in_state":
        return 0 if text.find(f'"{names[0]}"') <= text.find(f'"{names[1]}"') else 1
    if feature == "more_frequent_in_state":
        return 0 if text.count(f'"{names[0]}"') >= text.count(f'"{names[1]}"') else 1
    raise ValueError(f"unknown shortcut feature for the stub solver: {feature!r}")


#: A placeholder probe used only so the Q0 format check can share the cached-call path.
class _Q0Placeholder:
    probe_id = "probe:q0"
    truth_kind = "FORMAT_CHECK"
    mechanism = "q0"
    level = -1

    class _Variant:
        value = "Q0"

    variant = _Variant()


_Q0_PROBE: Any = _Q0Placeholder()


# ------------------------------------------------------------------- per-level shortcut audit


def per_level_shortcut_audit(
    probes: Iterable[V5Probe],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Run V5's shortcut audit on EVERY (mechanism, level) cell.

    This costs zero model calls: the audit is a property of the probe bank.  ``worst_score`` is
    reported as ``best_shortcut_accuracy`` because it already accounts for rule inversion -- a
    rule at 0.333 is a shortcut at 0.667 for anyone willing to negate it.
    """

    cells: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for probe in probes:
        cells[(probe.mechanism, probe.level)].append(probe)
    table: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for (mechanism, level), cell in sorted(cells.items()):
        audit = shortcut_audit(tuple(cell))
        table[mechanism][str(level)] = {
            "level": level,
            "items": audit.get("items", 0),
            "best_shortcut_accuracy": float(audit.get("worst_score", 1.0)),
            "best_shortcut_feature": audit.get("worst_rule"),
            "status": audit.get("status"),
            "answer_share_index_0": audit.get("answer_share_index_0"),
            "scores": audit.get("scores", {}),
        }
    return dict(table)


def answer_entropy_bits(rows: Sequence[Mapping[str, Any]]) -> float:
    """Shannon entropy (bits) of the parsed answer distribution over the given rows."""

    counts = Counter(r["parsed_index"] for r in rows if r["parsed_index"] is not None)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c)


# ------------------------------------------------------------------ selection and gating


def select_frontier_level(level_accuracies: Mapping[int, float]) -> dict[str, Any]:
    """V5's selector (``fitness_v5.py:915-948``) with the DERIVED target."""

    rule = QUALIFICATION_RULE_V7
    explicit = float(level_accuracies.get(0, 0.0))
    base = {
        "frontier_target": FRONTIER_TARGET,
        "qualifying_window": [FRONTIER["window_low"], FRONTIER["window_high"]],
        "explicit_positive_accuracy": explicit,
    }
    if explicit < float(rule["explicit_positive_min"]):
        return {**base, "selected_level": None, "verdict": "VOID_INSTRUMENT_LIMIT"}
    candidates = [(lvl, acc) for lvl, acc in sorted(level_accuracies.items()) if lvl >= 1]
    if not candidates:
        return {**base, "selected_level": None, "verdict": "VOID_INSTRUMENT_LIMIT"}
    level, accuracy = min(candidates, key=lambda item: (abs(item[1] - FRONTIER_TARGET), item[0]))
    low, high = float(rule["frontier_band"][0]), float(rule["frontier_band"][1])
    verdict = (
        "VOID_CEILING"
        if accuracy > high
        else "VOID_FLOOR"
        if accuracy < low
        else "FRONTIER_SELECTED"
    )
    return {
        **base,
        "selected_level": level if verdict == "FRONTIER_SELECTED" else None,
        "candidate_level": level,
        "candidate_accuracy": accuracy,
        "distance_to_target": abs(accuracy - FRONTIER_TARGET),
        "candidate_inside_qualifying_window": (
            FRONTIER["window_low"] <= accuracy <= FRONTIER["window_high"]
        ),
        "verdict": verdict,
    }


def qualify_mechanism(
    summary: Mapping[str, Any], audit: Mapping[str, Any], q0_rate: float
) -> dict[str, Any]:
    """V5's gate set, minus the dead destroyed ceiling, plus the shortcut margin.

    The check ORDER is V5's, so ``verdict`` stays comparable across instrument versions, but
    ``all_failures`` is reported too: V7 does not hide a second failure behind the first.
    """

    rule = QUALIFICATION_RULE_V7
    positive = float(summary["positive_accuracy"])
    best_shortcut = float(audit.get("best_shortcut_accuracy", 1.0))
    margin = positive - best_shortcut
    checks = {
        "q0": "PASS" if q0_rate >= float(rule["q0_valid_rate_min"]) else "VOID_VALIDITY",
        "valid_response": "PASS"
        if summary["valid_response_rate"] >= float(rule["valid_response_rate_min"])
        else "VOID_VALIDITY",
        "context": "PASS"
        if summary["context_truncated_rows"] <= int(rule["context_truncated_rows_max"])
        else "VOID_CONTEXT",
        "sample_size": "PASS"
        if summary["positive_examples"] >= int(rule["min_positives_for_gates"])
        else "VOID_VALIDITY",
        # The dead `destroyed <= 0.60` conjunct is GONE. Only the gap gate remains, and with
        # destroyed pinned at 0.5000 it is exactly `positive >= window_low`.
        "negative_collapse": "PASS"
        if summary["positive_negative_gap"] >= float(rule["positive_negative_gap_min"])
        else "VOID_NEGATIVE_CONTROL",
        "answer_share": "PASS"
        if summary["largest_answer_share"] <= float(rule["largest_answer_share_max"])
        else "VOID_POSITION_SHARE",
        "position_invariance": "PASS"
        if summary["position_invariance"] >= float(rule["position_invariance_min"])
        else "VOID_POSITION",
        "shortcut_absolute": "PASS"
        if best_shortcut <= float(rule["shortcut_rule_max"])
        else "VOID_SHORTCUT",
        "shortcut_margin": "PASS"
        if margin >= float(rule["shortcut_margin"]) - GATE_EPSILON
        else "VOID_SHORTCUT",
    }
    failures = [code for code in checks.values() if code != "PASS"]
    return {
        "checks": checks,
        "shortcut_margin_observed": margin,
        "shortcut_margin_required": float(rule["shortcut_margin"]),
        "best_shortcut_accuracy": best_shortcut,
        "best_shortcut_feature": audit.get("best_shortcut_feature"),
        "positive_accuracy": positive,
        "qualified": not failures,
        "verdict": failures[0] if failures else "QUALIFIED",
        "all_failures": sorted({name for name, code in checks.items() if code != "PASS"}),
    }


# ---------------------------------------------------------------------------- evaluation


def evaluate(
    root: Path,
    genome: ModelViewGenome,
    probes: Sequence[V5Probe],
    solver_call: SolverCall,
    *,
    solver: Mapping[str, str],
    bare: bool,
    solver_kind: SolverKind,
    model_template_hash: str,
    dry_run: bool,
) -> dict[str, Any]:
    """V5's :func:`~arena.experiments.fitness_v5.evaluate` with V7 cache identity and scope."""

    rows: list[dict[str, Any]] = []
    for probe in probes:
        prompt = build_prompt(genome, probe)
        identity = cache_identity(
            genome,
            probe,
            prompt,
            solver=solver,
            bare=bare,
            solver_kind=solver_kind,
            model_template_hash=model_template_hash,
        )
        raw, scope = cached_call(root, identity, probe, prompt, solver_call, dry_run=dry_run)
        if scope is CacheScope.CROSS_CONDITION:  # pragma: no cover - cached_call raises first
            raise CrossConditionCacheError(probe.probe_id)
        parsed = parse_response(raw["response"])
        cause = classify_row(raw, prompt, probe, parsed)
        selected_hash = (
            probe.options[parsed].arguments[0].content_hash if parsed is not None else None
        )
        expected_hash = probe.options[probe.expected_index].arguments[0].content_hash
        rows.append(
            {
                **identity,
                "probe_id": probe.probe_id,
                "family_id": probe.family_id,
                "mechanism": probe.mechanism,
                "level": probe.level,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind,
                "expected_index": probe.expected_index,
                "parsed_index": parsed,
                "selected_hash": selected_hash,
                "expected_hash": expected_hash,
                "correct": selected_hash == expected_hash,
                "cause": cause,
                "prompt_chars": len(prompt),
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "done_reason": raw.get("done_reason", ""),
                "raw_output": raw["response"],
                "cache_hit": scope is not CacheScope.FRESH,
                "cache_scope": scope.value,
                "latency_seconds": raw.get("total_duration_ns", 0) / 1e9,
                "error": raw.get("error"),
            }
        )
    return {
        "candidate_id": genome.candidate_id,
        "summary": summarize(rows),
        "rows": rows,
        "calls": sum(r["cache_scope"] == CacheScope.FRESH.value for r in rows),
        "cache_hits": sum(r["cache_hit"] for r in rows),
        "cache_scopes": dict(Counter(r["cache_scope"] for r in rows)),
    }


def q0_check(
    root: Path,
    solver_call: SolverCall,
    *,
    solver: Mapping[str, str],
    bare: bool,
    solver_kind: SolverKind,
    model_template_hash: str,
    dry_run: bool,
) -> dict[str, Any]:
    """V5's format-check probe, verbatim (``fitness_v5.py:986-1010``), on the V7 cache."""

    rows = []
    for index in range(8):
        expected = "A" if index % 2 == 0 else "B"
        prompt = f'Format check only. Answer with {{"choice":"{expected}"}}.\nANSWER:'
        identity = q0_cache_identity(
            index,
            prompt,
            solver=solver,
            bare=bare,
            solver_kind=solver_kind,
            model_template_hash=model_template_hash,
        )
        raw, scope = cached_call(root, identity, None, prompt, solver_call, dry_run=dry_run)
        parsed = parse_response(raw["response"])
        rows.append(
            {
                **identity,
                "expected": expected,
                "parsed": parsed,
                "correct": parsed == (0 if expected == "A" else 1),
                "raw_output": raw["response"],
                "cache_scope": scope.value,
            }
        )
    return {"rate": sum(r["correct"] for r in rows) / len(rows), "rows": rows}


def _wrap_q0(inner: SolverCall) -> SolverCall:
    """Let a stub solver also answer the Q0 format-check prompts, which carry no probe."""

    def call(probe: V5Probe, prompt: str) -> dict[str, Any]:
        if getattr(probe, "truth_kind", "") == "FORMAT_CHECK":
            choice = "B" if '"choice":"B"' in prompt else "A"
            return {
                "response": json.dumps({"choice": choice}),
                "prompt_eval_count": len(prompt) // 4,
                "eval_count": 8,
                "done_reason": "stop",
                "total_duration_ns": 0,
            }
        return inner(probe, prompt)

    return call


# ------------------------------------------------------------------------------- the run


def _log(message: str) -> None:
    print(f"[fitness_v7 {time.strftime('%H:%M:%S')}] {message}", flush=True)


def development_artifact_path(
    solver: Mapping[str, str], bare: bool = False, *, dry_run: bool = False
) -> str:
    key = str(solver["name"]).replace(":", "_").replace("/", "_")
    suffix = "-bare" if bare else "-framed"
    prefix = "dryrun-" if dry_run else "result-"
    path = f"{ARTIFACT_NAMESPACE}/development/{prefix}{key}{suffix}.json"
    return assert_v7_namespace(path)


def planned_call_count(probes: Sequence[V5Probe], arms: str) -> int:
    """Model calls a cold V7 development run will make, Q0 included."""

    if arms == "full":
        return len(probes) + 8
    positives = sum(p.variant.value in POSITIVE_VARIANTS for p in probes)
    per_level_families = DEV_FAMILIES * 6
    return positives + per_level_families * len(MECHANISMS) + 8


def run_development(
    root: Path,
    solver: Mapping[str, str] = DEFAULT_SOLVER,
    bare: bool = True,
    *,
    dry_run: bool = False,
    arms: str = "full",
    stub_profile: StubProfile = DEFAULT_STUB_PROFILE,
) -> dict[str, Any]:
    """Measure every arm at every level, then select and gate from the collected rows.

    Selection and qualification are pure functions of ``rows``: nothing is measured *because* a
    level was selected, so no gate can be reached by a second, differently-scheduled call.
    """

    if arms not in {"full", "positives"}:
        raise ValueError(f"unknown arm schedule {arms!r}; expected 'full' or 'positives'")
    solver_kind = SolverKind.STUB if dry_run else SolverKind.LIVE
    control = equal_information_genome()
    all_probes = build_dev_pool(root)

    if dry_run:
        served = {
            "name": str(solver["name"]),
            "digest": str(solver["digest"]),
            "template": "",
            "template_hash": stable_hash(""),
            "template_is_passthrough": True,
            "capabilities": [],
            "details": {},
            "note": "DRY RUN: no network call was made; nothing was verified against a live model",
        }
        solver_call: SolverCall = _wrap_q0(stub_solver(all_probes, stub_profile))
    else:
        served = verify_served_model(dict(solver))
        _log(
            f"solver {solver['name']} digest verified; "
            f"template passthrough={served['template_is_passthrough']}"
        )
        solver_call = ollama_solver(solver, bare=bare)
    template_hash = str(served["template_hash"])

    planned = planned_call_count(all_probes, arms)
    budget = int(MODEL_CALL_BUDGET["development_max"])
    if planned > budget:
        raise ValueError(
            f"V7 development schedule needs {planned} calls against the frozen budget of {budget}. "
            "Refusing to start rather than silently overrunning it."
        )
    _log(f"planned model calls (cold cache): {planned} / budget {budget}; arms={arms}")

    q0 = q0_check(
        root,
        solver_call,
        solver=solver,
        bare=bare,
        solver_kind=solver_kind,
        model_template_hash=template_hash,
        dry_run=dry_run,
    )
    _log(f"Q0 valid rate {q0['rate']:.3f}")

    by_cell: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for probe in all_probes:
        by_cell[(probe.mechanism, probe.level)].append(probe)

    audits = per_level_shortcut_audit(all_probes)
    all_rows: list[dict[str, Any]] = []
    mechanism_reports: dict[str, Any] = {}
    selected: dict[str, int] = {}

    for mechanism in MECHANISMS:
        ladder: list[dict[str, Any]] = []
        summaries: dict[int, dict[str, Any]] = {}
        accuracies: dict[int, float] = {}
        for level in range(len(LADDERS[mechanism])):
            cell = by_cell[(mechanism, level)]
            if not cell:
                continue
            measured = (
                cell
                if arms == "full"
                else [p for p in cell if p.variant.value in POSITIVE_VARIANTS]
            )
            result = evaluate(
                root,
                control,
                measured,
                solver_call,
                solver=solver,
                bare=bare,
                solver_kind=solver_kind,
                model_template_hash=template_hash,
                dry_run=dry_run,
            )
            all_rows.extend(result["rows"])
            summary = result["summary"]
            summaries[level] = summary
            accuracies[level] = float(summary["positive_accuracy"])
            audit = audits[mechanism][str(level)]
            positives = [r for r in result["rows"] if r["variant"] in POSITIVE_VARIANTS]
            ladder.append(
                {
                    "level": level,
                    "parameters": dict(LADDERS[mechanism][level]),
                    "positive_accuracy": accuracies[level],
                    "largest_answer_share": summary["largest_answer_share"],
                    "answer_entropy_bits": answer_entropy_bits(positives),
                    "valid_response_rate": summary["valid_response_rate"],
                    "destroyed_accuracy": summary["negative_target_accuracy"],
                    "destroyed_measured": arms == "full",
                    "destroyed_expected": DESTROYED_EXPECTED,
                    "positive_negative_gap": summary["positive_negative_gap"],
                    "position_invariance": summary["position_invariance"],
                    "best_shortcut_accuracy": audit["best_shortcut_accuracy"],
                    "best_shortcut_feature": audit["best_shortcut_feature"],
                    "shortcut_status": audit["status"],
                    "shortcut_margin_at_this_level": (
                        accuracies[level] - float(audit["best_shortcut_accuracy"])
                    ),
                    "inside_qualifying_window": (
                        FRONTIER["window_low"] <= accuracies[level] <= FRONTIER["window_high"]
                    ),
                    "positive_examples": summary["positive_examples"],
                    "cache_scopes": dict(Counter(r["cache_scope"] for r in result["rows"])),
                }
            )
            _log(
                f"{mechanism} L{level} acc {accuracies[level]:.3f} "
                f"share {summary['largest_answer_share']:.2f} "
                f"H {answer_entropy_bits(positives):.2f} "
                f"destroyed {summary['negative_target_accuracy']:.3f} "
                f"shortcut {audit['best_shortcut_feature']} {audit['best_shortcut_accuracy']:.3f}"
            )

        selection = select_frontier_level(accuracies)
        report: dict[str, Any] = {
            "ladder": ladder,
            "shortcut_audit_by_level": audits.get(mechanism, {}),
            "selection": selection,
        }
        level = selection["selected_level"]
        if level is not None and arms == "positives":
            # The `positives` schedule measures only positive arms on the ladder, so the gated
            # level needs its remaining arms before the gap and invariance gates can be read.
            full = by_cell[(mechanism, int(level))]
            result = evaluate(
                root,
                control,
                full,
                solver_call,
                solver=solver,
                bare=bare,
                solver_kind=solver_kind,
                model_template_hash=template_hash,
                dry_run=dry_run,
            )
            all_rows.extend(r for r in result["rows"] if r["variant"] not in POSITIVE_VARIANTS)
            summaries[int(level)] = result["summary"]
        if level is not None:
            level = int(level)
            qualification = qualify_mechanism(
                summaries[level], audits[mechanism][str(level)], q0["rate"]
            )
            report.update(
                {
                    "selected_level": level,
                    "full_family_summary": summaries[level],
                    "shortcut_audit": audits[mechanism][str(level)],
                    "qualification": qualification,
                }
            )
            _log(f"{mechanism} L{level} qualification: {qualification['verdict']}")
            if qualification["qualified"]:
                selected[mechanism] = level
        else:
            report.update(
                {
                    "selected_level": None,
                    "qualification": {"qualified": False, "verdict": selection["verdict"]},
                }
            )
            _log(f"{mechanism} {selection['verdict']}")
        mechanism_reports[mechanism] = report

    cache_scopes = dict(Counter(r["cache_scope"] for r in all_rows))
    if cache_scopes.get(CacheScope.CROSS_CONDITION.value):  # pragma: no cover - unreachable
        raise CrossConditionCacheError("V7 produced a CROSS_CONDITION row; the run is invalid")

    payload: dict[str, Any] = {
        "schema_version": "arena-fitness-v7-development-v1",
        "mode": "DRY_RUN" if dry_run else "LIVE",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "environment_version": ENVIRONMENT_VERSION,
        "inherits_from": {
            "experiment_version": V5_EXPERIMENT_VERSION,
            "instrument_version": V5_INSTRUMENT_VERSION,
            "unchanged": [
                "probe bank",
                "mechanisms",
                "ladders",
                "arms",
                "prompt template",
                "response schema",
                "decoding settings",
                "num_ctx / temperature / seed",
                "scoring",
                "validity gates",
                "n per cell",
                "abort clause",
            ],
            "changed": [
                "frontier_target is derived from the gate arithmetic, not declared",
                "the dead destroyed <= 0.60 gate is removed",
                "the shortcut audit runs at every level and gates on SHORTCUT_MARGIN",
                "cache identity records cache_scope; namespaces are V7-only",
            ],
        },
        "control_candidate": control.candidate_id,
        "model": dict(solver),
        "solver_kind": solver_kind.value,
        "served_model": served,
        "runtime": RUNTIME_CONFIG_V7_BARE if bare else RUNTIME_CONFIG_V7,
        "runtime_config_hash": RUNTIME_CONFIG_V7_BARE_HASH if bare else RUNTIME_CONFIG_V7_HASH,
        "decoding_settings": decoding_settings(bare=bare),
        "prompt_condition": "bare" if bare else "framed",
        "response_schema": RESPONSE_SCHEMA,
        "context_guard": CONTEXT_GUARD,
        "frontier": FRONTIER,
        "qualification_rule": QUALIFICATION_RULE_V7,
        "promotion_rule": PROMOTION_RULE,
        "shortcut_margin": SHORTCUT_MARGIN,
        "ladders": {k: [dict(p) for p in v] for k, v in LADDERS.items()},
        "arm_schedule": arms,
        "planned_model_calls": planned,
        "model_call_budget": budget,
        "q0": q0,
        "dev_pool_hash": stable_hash([p.to_dict() for p in all_probes]),
        "dev_pool_probes": len(all_probes),
        "shortcut_audit_by_level": audits,
        "mechanisms": mechanism_reports,
        "qualified_mechanisms": sorted(selected),
        "selected_levels": selected,
        "instrument_qualified": len(selected)
        >= int(QUALIFICATION_RULE_V7["minimum_qualified_mechanisms"]),
        "cache_scope_totals": cache_scopes,
        "fresh_calls_made": cache_scopes.get(CacheScope.FRESH.value, 0),
        "rows": all_rows,
    }
    path = development_artifact_path(solver, bare, dry_run=dry_run)
    ArtifactStore(Path(root) / "artifacts").write_json(path, payload)
    return payload


def experiment_status_v7(
    root: Path,
    solver: Mapping[str, str] = DEFAULT_SOLVER,
    bare: bool = True,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    path = Path(root) / "artifacts" / development_artifact_path(solver, bare, dry_run=dry_run)
    if not path.exists():
        return {"experiment_version": EXPERIMENT_VERSION, "sentinel": "FITNESS_V7_NOT_RUN"}
    development = json.loads(path.read_text())
    qualified = bool(development["instrument_qualified"])
    explicit_passes = sum(
        1
        for report in development["mechanisms"].values()
        if float(report["selection"]["explicit_positive_accuracy"])
        >= float(QUALIFICATION_RULE_V7["explicit_positive_min"])
    )
    # V5's abort clause, inherited unchanged (docs/FITNESS_V5_SPEC.md section 9).
    aborted = not qualified and explicit_passes >= int(
        QUALIFICATION_RULE_V7["minimum_qualified_mechanisms"]
    )
    if qualified:
        sentinel = "FITNESS_V7_QUALIFIED"
    elif aborted:
        sentinel = "CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT"
    else:
        sentinel = "FITNESS_V7_NOT_QUALIFIED"
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "mode": development.get("mode"),
        "solver": development["model"]["name"],
        "sentinel": sentinel,
        "qualified_mechanisms": development["qualified_mechanisms"],
        "selected_levels": development["selected_levels"],
        "explicit_positive_arms_passing": explicit_passes,
        "abort_clause_triggered": aborted,
        "founder_tournament_authorized": qualified,
        "cache_scope_totals": development.get("cache_scope_totals", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fitness V7 development runner")
    parser.add_argument("command", choices=("materialize", "audit", "develop", "status", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--solver", choices=tuple(SOLVERS), default="qwen38-rvn")
    parser.add_argument("--framed", action="store_true", help="apply the model renderer (not bare)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run end to end with a deterministic offline stub solver; makes NO model call",
    )
    parser.add_argument("--arms", choices=("full", "positives"), default="full")
    args = parser.parse_args()
    bare = not args.framed
    solver: Mapping[str, str] = STUB_SOLVER if args.dry_run else SOLVERS[args.solver]
    if args.command == "materialize":
        probes = build_dev_pool(args.root)
        print(
            canonical_json(
                {
                    "probes": len(probes),
                    "families": len(probes) // 6,
                    "dev_pool_hash": stable_hash([p.to_dict() for p in probes]),
                    "planned_model_calls": planned_call_count(probes, args.arms),
                    "frontier": FRONTIER,
                }
            )
        )
    elif args.command == "audit":
        probes = build_dev_pool(args.root)
        print(canonical_json(per_level_shortcut_audit(probes)))
    elif args.command == "verify":
        print(canonical_json(verify_served_model(dict(SOLVERS[args.solver]))))
    elif args.command == "develop":
        result = run_development(args.root, solver, bare, dry_run=args.dry_run, arms=args.arms)
        print(
            canonical_json(
                {
                    k: result[k]
                    for k in (
                        "mode",
                        "qualified_mechanisms",
                        "selected_levels",
                        "instrument_qualified",
                        "cache_scope_totals",
                    )
                }
            )
        )
    else:
        print(canonical_json(experiment_status_v7(args.root, solver, bare, dry_run=args.dry_run)))
    return 0


__all__ = [
    "ARTIFACT_NAMESPACE",
    "CACHE_NAMESPACE",
    "DESTROYED_EXPECTED",
    "DRY_RUN_CACHE_NAMESPACE",
    "EXPERIMENT_VERSION",
    "FRONTIER",
    "FRONTIER_TARGET",
    "FROZEN_NAMESPACES",
    "GATE_EPSILON",
    "INSTRUMENT_VERSION",
    "QUALIFICATION_RULE_V7",
    "RUNTIME_CONFIG_V7",
    "RUNTIME_CONFIG_V7_BARE",
    "RUNTIME_CONFIG_V7_BARE_HASH",
    "RUNTIME_CONFIG_V7_HASH",
    "SHORTCUT_MARGIN",
    "STUB_SOLVER",
    "CacheScope",
    "CrossConditionCacheError",
    "SolverKind",
    "StubProfile",
    "answer_entropy_bits",
    "assert_v7_namespace",
    "cache_identity",
    "cache_path",
    "cache_root",
    "cached_call",
    "classify_cache_scope",
    "decoding_settings",
    "derive_frontier",
    "development_artifact_path",
    "evaluate",
    "experiment_status_v7",
    "ollama_solver",
    "per_level_shortcut_audit",
    "planned_call_count",
    "q0_cache_identity",
    "q0_check",
    "qualify_mechanism",
    "run_development",
    "select_frontier_level",
    "stub_solver",
]


if __name__ == "__main__":
    raise SystemExit(main())
