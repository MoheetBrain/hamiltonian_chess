"""Every refusal path of the GPU spend gate.  A gate that can only pass is not a gate."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from arena.training.gpu_authorisation import (
    GPU_AUTHORISATION_ENV_VALUE,
    GPU_AUTHORISATION_ENV_VAR,
    GpuAuthorisation,
    GpuAuthorisationError,
    preregistration_hash,
    require_gpu_authorisation,
)

RUN_LABEL = "route-b-learning-curve"
AUTHORISED_ENV = {GPU_AUTHORISATION_ENV_VAR: GPU_AUTHORISATION_ENV_VALUE}


@pytest.fixture
def prereg(tmp_path: Path) -> Path:
    document = tmp_path / "route_b_preregistration.md"
    document.write_text(
        "# Route B preregistration\n\nFive arms, budgets 16/32/64/128/224, two seeds.\n",
        encoding="utf-8",
    )
    return document


def authorise(prereg: Path, **overrides: object) -> GpuAuthorisation:
    kwargs: dict[str, object] = {
        "authorized": True,
        "preregistration_path": prereg,
        "expected_preregistration_hash": preregistration_hash(prereg),
        "run_label": RUN_LABEL,
        "env": AUTHORISED_ENV,
    }
    kwargs.update(overrides)
    return require_gpu_authorisation(**kwargs)  # type: ignore[arg-type]


def test_all_three_conditions_together_authorise(prereg: Path) -> None:
    record = authorise(prereg)
    assert record.run_label == RUN_LABEL
    assert record.preregistration_sha256 == preregistration_hash(prereg)
    assert record.env_var == GPU_AUTHORISATION_ENV_VAR
    assert record.to_dict()["preregistration_sha256"] == record.preregistration_sha256


def test_preregistration_hash_is_over_the_exact_bytes(prereg: Path) -> None:
    assert preregistration_hash(prereg) == hashlib.sha256(prereg.read_bytes()).hexdigest()


# --- condition 1: the explicit flag -----------------------------------------------------


@pytest.mark.parametrize("flag", [False, None, 0, 1, "yes", "true", "no", [], object()])
def test_anything_but_literal_true_is_refused(prereg: Path, flag: object) -> None:
    with pytest.raises(GpuAuthorisationError, match="authorisation flag is not set"):
        authorise(prereg, authorized=flag)


# --- condition 2: the machine's environment ---------------------------------------------


def test_missing_environment_variable_is_refused(prereg: Path) -> None:
    with pytest.raises(GpuAuthorisationError, match="is not set") as error:
        authorise(prereg, env={})
    assert GPU_AUTHORISATION_ENV_VAR in str(error.value)


@pytest.mark.parametrize("value", ["", "0", "true", "TRUE", "yes", "1 ", " 1", "01"])
def test_any_other_environment_value_is_refused(prereg: Path, value: str) -> None:
    with pytest.raises(GpuAuthorisationError, match="only accepted value"):
        authorise(prereg, env={GPU_AUTHORISATION_ENV_VAR: value})


def test_an_unrelated_variable_does_not_authorise(prereg: Path) -> None:
    with pytest.raises(GpuAuthorisationError):
        authorise(prereg, env={"ARENA_GPU": "1", "CUDA_VISIBLE_DEVICES": "0"})


# --- condition 3: the preregistered design ----------------------------------------------


def test_missing_preregistration_document_is_refused(tmp_path: Path, prereg: Path) -> None:
    with pytest.raises(GpuAuthorisationError, match="does not exist"):
        authorise(prereg, preregistration_path=tmp_path / "absent.md")


def test_a_directory_is_not_a_preregistration(tmp_path: Path, prereg: Path) -> None:
    directory = tmp_path / "prereg_dir"
    directory.mkdir()
    with pytest.raises(GpuAuthorisationError, match="is not a file"):
        authorise(prereg, preregistration_path=directory)


def test_an_empty_document_registers_nothing(tmp_path: Path, prereg: Path) -> None:
    """Even when the caller supplies the *correct* hash of an empty file."""

    empty = tmp_path / "empty.md"
    empty.write_bytes(b"")
    with pytest.raises(GpuAuthorisationError, match="is empty"):
        authorise(
            prereg,
            preregistration_path=empty,
            expected_preregistration_hash=hashlib.sha256(b"").hexdigest(),
        )


@pytest.mark.parametrize(
    "value",
    ["", "   ", "0" * 63, "0" * 65, "g" * 64, "A" * 64, "sha256:" + "0" * 64, "not-a-hash"],
)
def test_a_malformed_expected_hash_is_refused(prereg: Path, value: str) -> None:
    with pytest.raises(GpuAuthorisationError):
        authorise(prereg, expected_preregistration_hash=value)


def test_an_empty_expected_hash_names_the_remedy(prereg: Path) -> None:
    with pytest.raises(GpuAuthorisationError, match="preregistration_hash") as error:
        authorise(prereg, expected_preregistration_hash="")
    assert "empty" in str(error.value)


@pytest.mark.parametrize("value", [None, 0, b"0" * 64, object()])
def test_a_non_string_expected_hash_is_refused(prereg: Path, value: object) -> None:
    with pytest.raises(GpuAuthorisationError, match="64-character lowercase hex"):
        authorise(prereg, expected_preregistration_hash=value)


def test_an_edited_preregistration_no_longer_authorises(prereg: Path) -> None:
    """The interesting failure: authorised, but for a different design than registered."""

    frozen = preregistration_hash(prereg)
    prereg.write_text(
        "# Route B preregistration\n\nFive arms, budgets 16/32/64/128/512, ONE seed.\n",
        encoding="utf-8",
    )
    with pytest.raises(GpuAuthorisationError, match="Either the design changed") as error:
        authorise(prereg, expected_preregistration_hash=frozen)
    assert frozen in str(error.value)
    assert preregistration_hash(prereg) in str(error.value)


def test_reformatting_the_preregistration_counts_as_a_change(prereg: Path) -> None:
    frozen = preregistration_hash(prereg)
    prereg.write_text(prereg.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(GpuAuthorisationError, match="hashes to"):
        authorise(prereg, expected_preregistration_hash=frozen)


def test_a_different_document_with_a_valid_hash_is_refused(tmp_path: Path, prereg: Path) -> None:
    other = tmp_path / "some_other_plan.md"
    other.write_text("A completely different experiment.\n", encoding="utf-8")
    with pytest.raises(GpuAuthorisationError, match="hashes to"):
        authorise(prereg, preregistration_path=other)


# --- housekeeping ------------------------------------------------------------------------


@pytest.mark.parametrize("label", ["", "   ", None, 0])
def test_a_missing_run_label_is_refused(prereg: Path, label: object) -> None:
    with pytest.raises(GpuAuthorisationError, match="run_label is missing"):
        authorise(prereg, run_label=label)


def test_the_run_label_appears_in_every_refusal(prereg: Path) -> None:
    with pytest.raises(GpuAuthorisationError) as error:
        authorise(prereg, authorized=False, run_label="tier-3-sprint")
    assert "tier-3-sprint" in str(error.value)


def test_unreadable_preregistration_is_reported(tmp_path: Path) -> None:
    with pytest.raises(GpuAuthorisationError, match="could not be read"):
        preregistration_hash(tmp_path / "nowhere" / "missing.md")


def test_the_docstring_shows_the_call_site() -> None:
    """The gate is useless if nobody knows where to put it."""

    import arena.training.gpu_authorisation as module

    doc = module.__doc__ or ""
    assert "require_gpu_authorisation(" in doc
    assert "gpu_matched_runner" in doc


def test_the_expected_hash_is_a_parameter_not_a_constant() -> None:
    """A hash baked into this file could be edited alongside the design it certifies."""

    source = Path(
        __import__("arena.training.gpu_authorisation", fromlist=["x"]).__file__ or ""
    ).read_text(encoding="utf-8")
    body = source.split("def require_gpu_authorisation", 1)[1]
    assert "expected_preregistration_hash" in body
    assert not any(
        len(token) == 64 and all(c in "0123456789abcdef" for c in token)
        for token in body.replace('"', " ").replace("'", " ").split()
    )
