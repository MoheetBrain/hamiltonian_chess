"""RED TEAM / attack classes 2, 5, 8: the semantic gate, dead candidates, and reporting.

Targets `semantic_gate` (`ModelViewCompiler.validate` + `assert_arena_parity`), the
dead-candidate path in `EvolutionLoop.run_generation`, and every durable artefact the loop
writes -- asking of each: can a reader who sees only this file mistake it for a result?

Run:  .venv/bin/python research/phase9/redteam/attack_gate_and_reporting.py
Out:  research/phase9/redteam/out/gate_and_reporting.json
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.evolution.loop import (  # noqa: E402
    ArenaSpec,
    EvolutionLoop,
    LoopConfig,
    Outcome,
    model_view,
    rendered_prompts,
    semantic_gate,
)
from arena.evolution.record import EvolutionRecordStore  # noqa: E402
from arena.genome.seeds import SEED_GENOMES  # noqa: E402
from arena.languages.base import CandidateLanguage, LanguageParseError  # noqa: E402
from arena.languages.registry import language_for_genome  # noqa: E402
from arena.storage.artifacts import ArtifactStore  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
_MARKER = "\n<<<REDTEAM-SIDE-CHANNEL>>>"


class LeakyRenderer(CandidateLanguage):
    """A hostile surface that ADDS content the parser then ignores.

    Round-trip fidelity is preserved exactly, because `_decode_payload` throws the appended
    bytes away before the strict wire validator ever sees them.  This is the shape of every
    "renderer that puts the answer on the page" attack.
    """

    format_id = "redteam-leaky-v0"

    def __init__(self, genome: Any, payload_suffix: str) -> None:
        self.genome = genome
        self._suffix = payload_suffix

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True) + _MARKER + self._suffix

    def _decode_payload(self, source: str) -> dict[str, Any]:
        head = source.split(_MARKER, 1)[0]
        try:
            return dict(json.loads(head))
        except json.JSONDecodeError as error:
            raise LanguageParseError(str(error)) from error


class AmnesiacRenderer(CandidateLanguage):
    """A hostile surface that DROPS a field and reinvents it at parse time.

    `ModelViewCompiler.validate` recovers the state with the SAME codec that rendered it, so a
    lossy renderer paired with a compensating parser round-trips perfectly while the Solver
    never sees the dropped content.
    """

    format_id = "redteam-amnesiac-v0"

    def __init__(self, genome: Any, drop_key: str) -> None:
        self.genome = genome
        self._drop = drop_key
        self._memory: Any = None

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        reduced = dict(payload)
        self._memory = reduced.pop(self._drop, None)
        return json.dumps(reduced, sort_keys=True)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        try:
            payload = dict(json.loads(source))
        except json.JSONDecodeError as error:
            raise LanguageParseError(str(error)) from error
        if self._memory is not None:
            payload[self._drop] = self._memory
        return payload


def main() -> int:
    findings: dict[str, Any] = {}
    arena = ArenaSpec()
    items = arena.solve_items()
    parent = SEED_GENOMES[0]
    child = SEED_GENOMES[1]

    # ------------------------------------------------------------------ G1 leaky renderer
    hostile = LeakyRenderer(child, "  ANSWER: the correct option is index 0")
    report = semantic_gate(parent=parent, child=child, items=items, child_language=hostile)
    rendered_example = hostile.render(items[0].canonical_state)
    findings["G1_leaky_renderer_passes_roundtrip"] = {
        "gate_passed": report.passed,
        "gate_outcomes": {o.name: o.status.value for o in report.outcomes},
        "failure_modes": list(report.failure_modes),
        "rendered_tail": rendered_example[-90:],
        "roundtrip_hash_recovered": hostile.parse(rendered_example).mathematical_hash
        == items[0].canonical_state.mathematical_hash,
        "note": (
            "check 1 (`semantic_roundtrip`) is render->parse through the SAME codec. Content the "
            "parser discards is invisible to it. What actually stops this in the loop is that the "
            "prompt is built from model_view(genome) via GenomePhenotypeLanguage, NOT from the "
            "object the gate validated -- the two are separate constructions from one genome, and "
            "nothing asserts they are the same renderer."
        ),
    }

    # ------------------------------------------------------------------ G2 amnesiac renderer
    payload_keys = sorted(json.loads(json.dumps(items[0].canonical_state.to_dict())).keys())
    drop_results: dict[str, Any] = {}
    for key in payload_keys:
        amnesiac = AmnesiacRenderer(child, key)
        try:
            rendered = amnesiac.render(items[0].canonical_state)
            recovered = amnesiac.parse(rendered)
            drop_results[key] = {
                "hash_recovered": recovered.mathematical_hash
                == items[0].canonical_state.mathematical_hash,
                "bytes_dropped": len(json.dumps(items[0].canonical_state.to_dict()))
                - len(rendered),
            }
        except Exception as exc:  # noqa: BLE001
            drop_results[key] = {"error": f"{type(exc).__name__}: {str(exc)[:110]}"}
    findings["G2_lossy_renderer_with_compensating_parser"] = {
        "per_dropped_key": drop_results,
        "any_key_round_trips_while_dropped": sorted(
            k for k, v in drop_results.items() if v.get("hash_recovered")
        ),
    }

    # ------------------------------------------------------------------ G3 gate is fail-closed?
    class ExplodingRenderer(CandidateLanguage):
        format_id = "redteam-explode-v0"

        def __init__(self, genome: Any) -> None:
            self.genome = genome

        def _encode_payload(self, payload: dict[str, Any]) -> str:
            raise RuntimeError("renderer exploded")

        def _decode_payload(self, source: str) -> dict[str, Any]:
            raise RuntimeError("parser exploded")

    boom = semantic_gate(
        parent=parent, child=child, items=items, child_language=ExplodingRenderer(child)
    )
    findings["G3_gate_fails_closed_on_a_broken_renderer"] = {
        "gate_passed": boom.passed,
        "failure_modes": list(boom.failure_modes),
        "first_detail": boom.outcomes[0].detail[:150],
    }

    # ------------------------------------------------------------------ G4 inert mutation killed?
    self_gate = semantic_gate(parent=parent, child=parent, items=items)
    findings["G4_byte_identical_child_is_killed"] = {
        "gate_passed": self_gate.passed,
        "inert": self_gate.inert,
        "failure_modes": list(self_gate.failure_modes),
        "evidence": self_gate.inert_evidence,
    }

    # ------------------------------------------------------------------ G5 dead-candidate compute
    store_path = OUT / "store" / "dead"
    if store_path.exists():
        shutil.rmtree(store_path)
    store_path.mkdir(parents=True)
    store = ArtifactStore(store_path)
    loop = EvolutionLoop(
        store=store,
        config=LoopConfig(seed=4242, generations=2, population=4, children_per_generation=6),
    )
    summary = loop.run()
    candidates = [c for g in summary["generations"] for c in g["candidates"]]
    killed = [c for c in candidates if c["outcome"] != Outcome.SCORED.value]
    scored = [c for c in candidates if c["outcome"] == Outcome.SCORED.value]
    league = json.loads(
        (store.root / "evolution" / summary["run_id"] / "league-registry.json").read_text()
    )
    league_ids = {entry["candidate_id"] for entry in league["candidates"]}
    records = EvolutionRecordStore(store, summary["run_id"]).records()
    by_id = {r.child_genome_id: r for r in records}
    rows_files = {
        path.name.replace(".rows.jsonl", ""): path.stat().st_size
        for path in store.root.rglob("*.rows.jsonl")
    }
    findings["G5_dead_candidate_enforcement"] = {
        "candidates": len(candidates),
        "killed": len(killed),
        "scored": len(scored),
        "killed_outcomes": sorted({c["outcome"] for c in killed}),
        "killed_failure_modes": sorted({m for c in killed for m in c["failure_modes"]}),
        "killed_carry_measured_fitness": [bool(c["fitness"]) for c in killed],
        "killed_in_league": sorted(c["child_id"] for c in killed if c["child_id"] in league_ids),
        "scored_in_league": sorted(c["child_id"] for c in scored if c["child_id"] in league_ids),
        "killed_record_status": sorted(
            {by_id[c["child_id"]].status.value for c in killed if c["child_id"] in by_id}
        ),
        "killed_rows_file_sizes": sorted(
            {
                rows_files.get("lfm-" + by_id[c["child_id"]].record_id.removeprefix("lfm:"), -1)
                for c in killed
                if c["child_id"] in by_id
            }
        ),
        "note": "a rows file of size 0 means the killed candidate consumed no evaluation budget",
    }

    # ------------------------------------------------------------------ G6 reporting surface
    league_text = (
        store.root / "evolution" / summary["run_id"] / "league-registry.json"
    ).read_text()
    summary_text = (store.root / "evolution" / summary["run_id"] / "summary.json").read_text()
    record_text = EvolutionRecordStore(store, summary["run_id"]).record_paths()[0].read_text()
    stamp = "EXECUTABILITY_ONLY_NOT_A_RESULT"
    observations = league.get("observations", [])
    findings["G6_where_the_stub_disclaimer_is_and_is_not"] = {
        "summary.json_has_stamp": stamp in summary_text,
        "record.json_has_stamp": stamp in record_text,
        "record.json_has_prose_status": "executability run" in record_text,
        "league-registry.json_has_stamp": stamp in league_text,
        "league-registry.json_mentions_stub": "stub" in league_text.lower(),
        "league-registry.json_mentions_model": "model" in league_text.lower(),
        "league_observations": len(observations),
        "league_observations_marked_verified": sum(
            1 for o in observations if o.get("verified", True)
        ),
        "league_rating_method": sorted(
            {
                rating["interval"]["method"]
                for entry in league["candidates"]
                for rating in entry.get("domain_ratings", {}).values()
            }
        ),
        "league_objective_metrics_sample": next(
            (e["objective_metrics"] for e in league["candidates"] if e.get("objective_metrics")), {}
        ),
        "note": (
            "the league registry is the durable archive and the only file that carries "
            "cross-candidate rankings; it carries no scientific-status stamp, no model identity, "
            "no condition id, and marks every stub row verified=true"
        ),
    }

    # ------------------------------------------------------------------ G7 hash-seed determinism
    script = (
        "import json,sys,tempfile,shutil;"
        f"sys.path.insert(0,{str(ROOT)!r});"
        "from arena.evolution.loop import EvolutionLoop, LoopConfig;"
        "from arena.storage.artifacts import ArtifactStore;"
        "d=tempfile.mkdtemp();"
        "s=EvolutionLoop(store=ArtifactStore(d),config=LoopConfig(seed=20260908)).run();"
        "print(json.dumps({'run':s['run_id'],'m':s['records']['manifest_hash'],"
        "'front':s['final_front']}));"
        "shutil.rmtree(d)"
    )
    seeds: dict[str, Any] = {}
    for hash_seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        proc = subprocess.run(  # noqa: S603
            [str(ROOT / ".venv" / "bin" / "python"), "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
            check=False,
        )
        seeds[hash_seed] = (
            json.loads(proc.stdout.strip().splitlines()[-1])
            if proc.returncode == 0
            else {"error": proc.stderr[-300:]}
        )
    findings["G7_determinism_under_PYTHONHASHSEED"] = {
        "results": seeds,
        "all_identical": len({json.dumps(v, sort_keys=True) for v in seeds.values()}) == 1,
    }

    # ------------------------------------------------------------------ G8 prompt provenance
    prompts_from_genome = rendered_prompts(child, items[:1])
    prompts_from_view = rendered_prompts(SEED_GENOMES[1], items[:1])
    findings["G8_prompt_source"] = {
        "gate_validated_object": type(language_for_genome(child)).__name__,
        "prompt_built_from": "build_prompt(model_view(genome), item) -> GenomePhenotypeLanguage",
        "same_bytes_today": prompts_from_genome == prompts_from_view,
        "model_view_surface_id": model_view(child).surface.candidate_id,
    }

    (OUT / "gate_and_reporting.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:11000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
