from arena.genome.seeds import L1_CURRENT_HML
from arena.genome.validation import validate_genome
from arena.players.architect import Architect


def test_architect_is_deterministic_and_proposes_valid_neighbours() -> None:
    first = Architect().propose(L1_CURRENT_HML, count=12, seed=42)
    second = Architect().propose(L1_CURRENT_HML, count=12, seed=42)
    assert [item.genome.candidate_hash for item in first] == [
        item.genome.candidate_hash for item in second
    ]
    assert len(first) == 12
    assert all(validate_genome(item.genome).valid for item in first)
    assert all(item.genome.parent_ids == (L1_CURRENT_HML.candidate_id,) for item in first)
