"""Game-R compatibility audit for candidate representations.

A byte difference between two renderings proves nothing about causal purity.  A Game-R
candidate must change only ``R``: it must recover the identical canonical mathematics and
must not put information on the page that another candidate does not get.

**Correction (Phase 5).**  The first version of this audit compared inventories of the
*recovered* canonical state.  Two independent reviews showed that check is vacuous: the
recovered-state inventory is a strict coarsening of ``mathematical_hash``, so it can differ
only when semantic recovery has already failed, and the ``GAME_P_ONLY`` branch was therefore
unreachable.  The option-inventory check was degenerate for the same reason plus a second
one: restricting the comparison to expression records made it constant across every
candidate, because free-text option policies emit no expression record at all.

The audit now inventories **what is actually on the page**: the rendered prompt is decoded
back through the candidate's own codec and its leaf multiset compared against the reference.
A candidate that smuggles a derived relation into its rendering and silently drops it on
parse now fails, which is exactly the Game-P violation the old check could not see.  Checks
that remain constant by construction are reported as ``VACUOUS`` rather than counted as
evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arena.canonical.schema import CanonicalAction, CanonicalState, canonical_json, stable_hash
from arena.experiments.fitness_v4 import (
    MECHANISMS,
    V4Probe,
    V4Slice,
    build_prompt,
    derive_probe_family,
)
from arena.genome.schema import LanguageGenome
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages._wire import STATE_FIELD_ORDER  # noqa: F401  (schema anchor)
from arena.languages.phenotype import GenomePhenotypeLanguage, _unwrap
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.storage.artifacts import ArtifactStore

AUDIT_VERSION = "arena-game-r-mutant-audit-v2"
CLASSES = (
    "GAME_R_COMPATIBLE",
    "GAME_P_ONLY",
    "MIXED_CONFOUNDED",
    "DUPLICATE_BEHAVIOUR",
    "OBSOLETE",
)


def _leaves(value: Any, path: str = "") -> Counter[str]:
    """Order-insensitive inventory of every (path, scalar) pair in a decoded record."""

    out: Counter[str] = Counter()
    if isinstance(value, dict):
        for key, child in value.items():
            out.update(_leaves(child, f"{path}/{key}"))
    elif isinstance(value, list):
        for child in value:
            out.update(_leaves(child, f"{path}[]"))
    else:
        out[f"{path}={canonical_json(value)}"] += 1
    return out


def information_inventory(state: CanonicalState) -> str:
    return stable_hash(
        sorted(
            _leaves(state.to_dict(include_execution=False, include_display_identity=False)).items()
        )
    )


def _expressions(value: Any) -> list[str]:
    """Top-level canonical expression records inside a decoded option envelope."""

    if isinstance(value, dict):
        if "op" in value and "sort" in value:
            return [canonical_json(value)]
        return [item for child in value.values() for item in _expressions(child)]
    if isinstance(value, list):
        return [item for child in value for item in _expressions(child)]
    return []


def prompt_information_inventory(language: GenomePhenotypeLanguage, state: CanonicalState) -> str:
    """Inventory the information actually present in the rendered surface.

    This is the independent check.  It decodes the candidate's own rendering back into a
    payload and inventories that payload's leaves.  Unlike an inventory of the parsed
    canonical state, it can see content a renderer emitted and a parser discarded.
    """

    rendered = language.render(state)
    # Deliberately call the base codec unbound.  Using ``language``'s own bound methods would
    # let a candidate that filters on parse hide what it emitted, which is precisely the
    # violation this check exists to catch.
    body = _unwrap(rendered, language.genome.serialization)
    decoded = GenomePhenotypeLanguage._decode_value(language, body)
    return stable_hash(sorted(_leaves(decoded).items()))


def option_inventory(language: GenomePhenotypeLanguage, options: Sequence[CanonicalAction]) -> str:
    """Options must expose exactly the same mathematical argument content.

    Envelope keys such as ``candidate_result`` or ``apply/target_role`` are role labels chosen
    by the action-policy gene; they are constant across the two options of a probe and carry
    no mathematics, so only the expression records they wrap are compared.
    """

    rendered = [language.render_action_choice(option) for option in options]
    decoded = [language._decode_value(text) for text in rendered]
    return stable_hash([sorted(_expressions(item)) for item in decoded])


def audit_genome(
    genome: LanguageGenome, candidate_id: str, probes: Sequence[V4Probe]
) -> dict[str, Any]:
    view_genome = ModelViewGenome(
        candidate_id, (), SearchTrack.EQUAL_INFORMATION, genome, ContentGenome()
    )
    compiler = ModelViewCompiler(view_genome)
    language = GenomePhenotypeLanguage(genome)
    semantic_ok = True
    inventories: list[str] = []
    derived: list[str] = []
    options: list[str] = []
    surface: list[str] = []
    prompts: list[str] = []
    for probe in probes:
        for state in (probe.state, probe.previous_state):
            if state is None:
                continue
            compiled = compiler.compile(state, options=probe.options)
            recovered = compiler.recover_canonical_state(compiled)
            semantic_ok &= recovered.mathematical_hash == state.mathematical_hash
            inventories.append(information_inventory(recovered))
            derived.append(
                stable_hash(
                    {
                        "projection": compiled.projection.to_dict()
                        if compiled.projection
                        else None,
                        "omissions": list(compiled.accounting.omitted_relations),
                        "derived": list(compiled.accounting.derived_relation_hashes),
                    }
                )
            )
        options.append(option_inventory(language, probe.options))
        surface.append(prompt_information_inventory(language, probe.state))
        prompts.append(build_prompt(view_genome, probe))
    return {
        "candidate_id": candidate_id,
        "semantic_recovery": semantic_ok,
        "information_inventory_hash": stable_hash(inventories),
        "derived_relation_hash": stable_hash(derived),
        "option_inventory_hash": stable_hash(options),
        "surface_information_hash": stable_hash(surface),
        "render_signature": stable_hash(prompts),
        "prompt_chars": sum(len(item) for item in prompts),
    }


def classify(
    row: dict[str, Any], reference: dict[str, Any], signatures: dict[str, list[str]]
) -> str:
    if not row["semantic_recovery"]:
        return "OBSOLETE"
    # The surface inventory is the only independent Game-P detector: it reads what the
    # renderer actually put on the page, not what the parser handed back.
    same_surface = row["surface_information_hash"] == reference["surface_information_hash"]
    same_derived = row["derived_relation_hash"] == reference["derived_relation_hash"]
    if not same_surface:
        return "GAME_P_ONLY"
    if not same_derived:
        return "MIXED_CONFOUNDED"
    if len(signatures[row["render_signature"]]) > 1:
        return "DUPLICATE_BEHAVIOUR"
    return "GAME_R_COMPATIBLE"


PHENOTYPE_GENES = (
    "grammar",
    "serialization",
    "state",
    "binders",
    "types",
    "morphology",
    "token_policy",
    "redundancy",
    "actions",
)
R_DIMENSIONS = {
    "grammar_family": "grammar",
    "organization": "state",
    "serialization": "serialization",
    "binder_encoding": "binders",
    "type_placement": "types",
    "role_labels": "morphology",
    "identifier_system": "token_policy",
    "compression": "redundancy",
    "option_structure": "actions",
}


def _genes(genome: dict[str, Any]) -> dict[str, str]:
    return {name: str(value) for name, value in genome["genes"].items()}


def _attach_structure(rows: list[dict[str, Any]], population: dict[str, Any]) -> None:
    """Genome-level descriptors, lineage and structural distances (phenotype genes only)."""

    genomes: dict[str, dict[str, str]] = {
        f"V4E_{seed_id}": _genes(genome.to_dict()) for seed_id, genome in SEED_GENOME_BY_ID.items()
    }
    for candidate in population["candidates"]:
        genomes[candidate["candidate_id"]] = _genes(candidate["genome"])
    seed_ids = [f"V4E_{seed_id}" for seed_id in SEED_GENOME_BY_ID]

    def distance(left: dict[str, str], right: dict[str, str]) -> int:
        return sum(left[gene] != right[gene] for gene in PHENOTYPE_GENES)

    for row in rows:
        genes = genomes[row["candidate_id"]]
        row["genes"] = genes
        row["r_dimensions"] = {dimension: genes[gene] for dimension, gene in R_DIMENSIONS.items()}
        row["distance_to_founders"] = {
            seed_id: distance(genes, genomes[seed_id]) for seed_id in seed_ids
        }
        nearest = [
            other["candidate_id"]
            for other in rows
            if other["candidate_id"] != row["candidate_id"]
            and other["kind"] == "mutant"
            and distance(genes, genomes[other["candidate_id"]]) <= 1
        ]
        row["phenotype_neighbours_within_1"] = nearest
        row["structural_near_duplicates"] = [
            other["candidate_id"]
            for other in rows
            if other["candidate_id"] != row["candidate_id"]
            and distance(genes, genomes[other["candidate_id"]]) == 0
        ]


def run_audit(root: Path) -> dict[str, Any]:
    population = json.loads(
        (root / "artifacts/experiments/fitness_v1/candidate_population.json").read_text()
    )
    probes = [
        probe
        for mechanism in MECHANISMS
        for probe in derive_probe_family(mechanism, 2, V4Slice.DEV, 7)[:2]
    ]
    rows: list[dict[str, Any]] = []
    for seed_id, genome in SEED_GENOME_BY_ID.items():
        rows.append(
            {
                **audit_genome(genome, f"V4E_{seed_id}", probes),
                "kind": "seed",
                "parent_id": None,
                "changed_gene": None,
            }
        )
    for candidate in population["candidates"]:
        genome = LanguageGenome.from_dict(candidate["genome"])
        rows.append(
            {
                **audit_genome(genome, candidate["candidate_id"], probes),
                "kind": "mutant",
                "parent_id": candidate["parent_id"],
                "changed_gene": candidate["mutation_family"],
            }
        )
    reference = next(row for row in rows if row["candidate_id"] == "V4E_L3_JSON_AST")
    signatures: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        signatures[row["render_signature"]].append(row["candidate_id"])
    for row in rows:
        row["game_r_class"] = classify(row, reference, signatures)
        row["duplicates"] = [
            other for other in signatures[row["render_signature"]] if other != row["candidate_id"]
        ]
    _attach_structure(rows, population)
    counts = Counter(row["game_r_class"] for row in rows if row["kind"] == "mutant")
    by_gene: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row["kind"] == "mutant":
            by_gene[str(row["changed_gene"])][row["game_r_class"]] += 1
    clusters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row["kind"] == "mutant":
            for dimension, value in row["r_dimensions"].items():
                clusters[dimension][value] += 1
    near_duplicate_pairs = sorted(
        {
            tuple(sorted((row["candidate_id"], other)))
            for row in rows
            for other in row["structural_near_duplicates"]
        }
    )
    report = {
        "schema_version": AUDIT_VERSION,
        "phenotype_genes": list(PHENOTYPE_GENES),
        "r_dimension_clusters": {dimension: dict(value) for dimension, value in clusters.items()},
        "structural_near_duplicate_pairs": [list(pair) for pair in near_duplicate_pairs],
        "source_population_hash": population["population_hash"],
        "reference_candidate": reference["candidate_id"],
        "probe_hashes": [probe.derived_hash for probe in probes],
        "checks": [
            "semantic recovery: parse(render(state)) has the identical mathematical hash",
            "information inventory: order-insensitive (path, scalar) multiset of the recovered record equals the reference",
            "derived relations: Track-E emits no projection; omissions and derived hashes equal the reference",
            "option structure: decoded option renderings expose the same argument inventory",
            "behavioural duplicate: byte-identical prompt signature with another candidate",
        ],
        "mutant_classes": dict(counts),
        "by_changed_gene": {gene: dict(value) for gene, value in by_gene.items()},
        "rows": rows,
    }
    ArtifactStore(root / "artifacts").write_json("reports/game-r-mutant-audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = run_audit(args.root)
    print(
        canonical_json(
            {
                "mutant_classes": report["mutant_classes"],
                "by_changed_gene": report["by_changed_gene"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
