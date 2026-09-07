from dataclasses import replace

from arena.canonical.equivalence import alpha_normalize, expressions_equivalent
from arena.canonical.schema import CanonicalExpression, CanonicalState
from tests.helpers import sample_state, variable


def test_state_roundtrip_and_stable_identity() -> None:
    state = sample_state(metadata=(("runtime", "1.2"),))
    decoded = CanonicalState.from_dict(state.to_dict())
    assert decoded.to_dict() == state.to_dict()
    assert decoded.mathematical_hash == state.mathematical_hash


def test_execution_metadata_does_not_change_mathematical_identity() -> None:
    left = sample_state(metadata=(("runtime", "1.2"),))
    right = sample_state(metadata=(("runtime", "9000"), ("model", "other")))
    assert left.mathematical_hash == right.mathematical_hash
    assert left.artifact_hash != right.artifact_hash


def test_display_state_id_does_not_change_mathematical_identity() -> None:
    state = sample_state()
    renamed = replace(state, state_id="state:presentation-only")
    assert state.mathematical_hash == renamed.mathematical_hash


def test_alpha_equivalent_binders_have_same_normal_form() -> None:
    x = variable("x")
    y = variable("y")
    left = CanonicalExpression("forall", (x, CanonicalExpression("eq", (x, x))))
    right = CanonicalExpression("forall", (y, CanonicalExpression("eq", (y, y))))
    assert expressions_equivalent(left, right)
    assert alpha_normalize(left).to_dict() == alpha_normalize(right).to_dict()


def test_free_variable_is_not_alpha_renamed() -> None:
    x = variable("x")
    y = variable("y")
    left = CanonicalExpression("eq", (x, x))
    right = CanonicalExpression("eq", (y, y))
    assert not expressions_equivalent(left, right)


def test_alpha_normalize_does_not_support_dependent_binder_types() -> None:
    """Pin a known limitation so it cannot be mistaken for a working guarantee.

    ``alpha_normalize`` documents binder nodes as ``(variable, body, ...)`` and normalises
    every argument after the first under the extended environment. If a caller instead puts a
    binder's TYPE at ``args[1]`` -- as a dependent type would -- that type is scoped under the
    binder it belongs to, and two genuinely alpha-equivalent terms normalise differently.

    Nothing in the V1-V5 measurement path uses this function, so this is a latent hazard
    rather than an active defect. It is pinned here, and recorded in docs/CURRENT_STATE.md, so
    that a future generator does not adopt it as an "independent" oracle for dependent types.
    """

    from arena.canonical.equivalence import alpha_normalize

    def var(name: str) -> CanonicalExpression:
        return CanonicalExpression("var", value=name, sort="Term")

    def binder(name: str, second: CanonicalExpression) -> CanonicalExpression:
        return CanonicalExpression("forall", (var(name), second), sort="Prop")

    vec_of_x = CanonicalExpression("apply", (var("Vec"), var("x")), sort="Term")
    shadowed = binder("x", binder("x", vec_of_x))
    renamed = binder("x", binder("y", vec_of_x))

    assert alpha_normalize(shadowed).to_dict() != alpha_normalize(renamed).to_dict()
