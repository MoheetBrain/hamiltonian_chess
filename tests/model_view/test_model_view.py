from __future__ import annotations

import json
from dataclasses import replace

import pytest

from arena.canonical.schema import EvidenceNode
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.genome.seeds import L3_JSON_AST
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import CONTENT_ENUMS, ContentGenome, ModelViewGenome, SearchTrack
from arena.model_view.projection import derive_truth_view
from tests.helpers import sample_state


def model_genome(
    content: ContentGenome | None = None,
    *,
    track: SearchTrack = SearchTrack.CONTENT_PROJECTION,
) -> ModelViewGenome:
    return ModelViewGenome(
        candidate_id="MV_TEST",
        parent_ids=(),
        track=track,
        surface=L3_JSON_AST,
        content=content or ContentGenome(),
    )


def rich_states():
    state = sample_state()
    before = replace(
        state,
        evidence_dependencies=(
            EvidenceNode("e:root", "VERIFIED"),
            EvidenceNode("e:middle", "VERIFIED", ("e:root",)),
            EvidenceNode("e:leaf", "UNKNOWN", ("e:middle",), "z3", "cert"),
        ),
        local_scope=("e:leaf",),
    )
    after = replace(before, terminal_status="ADVANCED", established_facts=(before.goal,))
    return before, after


def test_track_e_is_exactly_recoverable_surface_without_content_projection() -> None:
    state, _ = rich_states()
    compiler = ModelViewCompiler(model_genome(track=SearchTrack.EQUAL_INFORMATION))
    compiled = compiler.compile(state)
    compiler.validate(compiled, state)
    assert compiled.projection is None
    assert "TRUTH-DERIVED" not in compiled.text
    assert compiled.accounting.projection_utf8_bytes == 0


def test_track_c_projection_is_recomputed_and_canonical_truth_is_recovered() -> None:
    raw_before, raw_state = rich_states()
    options = (*raw_state.legal_actions, *raw_state.plausible_invalid_actions)
    before = project_state_for_observation(raw_before, ObservationKind.NEXT_ACTION)
    state = project_state_for_observation(raw_state, ObservationKind.NEXT_ACTION)
    compiler = ModelViewCompiler(model_genome())
    compiled = compiler.compile(state, options=options, previous_state=before)
    compiler.validate(compiled, state, options=options, previous_state=before)
    assert compiler.recover_canonical_state(compiled).mathematical_hash == state.mathematical_hash
    assert compiled.accounting.canonical_state_hash == state.mathematical_hash
    assert compiled.accounting.projection_utf8_bytes > 0
    assert "expected_usefulness" not in json.dumps(compiled.projection.to_dict())


def test_tampered_projection_fails_independent_recomputation() -> None:
    state, _ = rich_states()
    compiler = ModelViewCompiler(model_genome())
    compiled = compiler.compile(state)
    tampered = replace(compiled, text=compiled.text.replace("STATUS_ONLY", "PROOF_EDGE"))
    with pytest.raises(ValueError, match="not independently reproducible"):
        compiler.validate(tampered, state)


@pytest.mark.parametrize("gene_name", sorted(CONTENT_ENUMS))
def test_every_content_axis_has_behaviorally_distinct_values(gene_name: str) -> None:
    before, state = rich_states()
    options = (*state.legal_actions, *state.plausible_invalid_actions)
    enum = CONTENT_ENUMS[gene_name]
    views = []
    for value in enum:
        genome = ContentGenome().with_gene(gene_name, value.value)
        view = derive_truth_view(state, genome, options=options, previous_state=before)
        views.append(json.dumps(view.to_dict(), sort_keys=True))
        assert view.source_state_hash == state.mathematical_hash
    assert len(set(views)) == len(views)


def test_projection_never_reads_hidden_action_pools() -> None:
    state, _ = rich_states()
    observation = project_state_for_observation(state, ObservationKind.NEXT_ACTION)
    view = derive_truth_view(observation, ContentGenome())
    assert not observation.legal_actions
    assert not observation.plausible_invalid_actions
    assert state.legal_actions[0].action_id not in json.dumps(view.to_dict())
