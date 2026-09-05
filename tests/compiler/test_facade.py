import pytest

from arena.compiler import CompilationError, canonicalize, parse_state, render_state
from arena.languages.registry import seed_languages
from tests.helpers import sample_state


@pytest.mark.parametrize("language", seed_languages(), ids=lambda item: item.candidate_id)
def test_compiler_facade_preserves_mathematical_identity(language) -> None:
    state = sample_state(metadata=(("runtime", "excluded"),))
    source = render_state(language, state)
    decoded = parse_state(language, source)
    canonical = canonicalize(language, source)
    assert decoded.artifact_hash == state.artifact_hash
    assert canonical.execution_metadata == ()
    assert canonical.mathematical_hash == state.mathematical_hash


def test_compiler_facade_normalizes_parse_error() -> None:
    with pytest.raises(CompilationError, match="SURFACE_PARSE_ERROR"):
        parse_state(seed_languages()[0], "malformed")
