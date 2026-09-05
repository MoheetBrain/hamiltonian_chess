from arena.assurance.properties import PropertyStatus, semantic_property_suite
from arena.verifier.native import NativeVerifier
from tests.helpers import sample_state


def test_native_verifier_survives_declared_semantic_attack_suite() -> None:
    results = semantic_property_suite(sample_state(), NativeVerifier())
    assert len(results) >= 10
    assert all(result.status == PropertyStatus.PASS for result in results), results
