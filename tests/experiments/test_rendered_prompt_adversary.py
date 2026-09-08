"""Tests for the rendered-prompt adversary family.

Everything here is offline and deterministic.  The adversary module is only ever handed the
rendered prompt string; the canonical machinery is imported *here*, in the test, to build those
strings, and one test asserts by AST scan that the adversary module never imports it.
"""

from __future__ import annotations

import ast
import itertools
import json
import math
import random
from collections.abc import Sequence
from pathlib import Path

import pytest

from arena.environments.precondition_ladder import Pool, build_pool
from arena.experiments import rendered_prompt_adversary as rpa
from arena.experiments.game_r_formal_v1 import (
    StubEnvironment,
    SyntaxGuidePolicy,
    build_prompt,
    founder_genome,
)
from arena.genome.seeds import SEED_GENOME_BY_ID

MODULE_PATH = Path(rpa.__file__)

BANNED_IMPORT_PREFIXES = (
    "arena.canonical",
    "arena.environments",
    "arena.experiments.fitness_v4",
    "arena.experiments.fitness_v5",
    "arena.experiments.fitness_v7",
    "arena.model_view",
    "arena.languages",
)
BANNED_NONDETERMINISM_MODULES = ("time", "uuid", "secrets", "os")


# ------------------------------------------------------------------------------ builders


def _envelope(
    question: str, state: str, options: Sequence[str], *, guide: str | None = None
) -> str:
    """The literal envelope of ``game_r_formal_v1._assemble``; ``test_real_prompt_round_trips``
    proves the two agree byte for byte."""

    labels = rpa.option_labels(len(options))
    header = (
        f'Answer with exactly one JSON object, for example {{"answer":"{labels[0]}"}}.\n'
        f"The only valid values are: {', '.join(labels)}.\n"
        "Read identifiers exactly. Do not choose by option position.\n"
    )
    guide_block = "" if guide is None else f"GUIDE:\n{guide}\n"
    rendered = "\n".join(f"{label}: {text}" for label, text in zip(labels, options, strict=True))
    return (
        f"{header}{guide_block}QUESTION: {question}\nCURRENT STATE:\n{state}\n"
        f"OPTIONS:\n{rendered}\nANSWER:"
    )


def _example(
    prompt: str, correct: int, family: str, task: str, *, arm: str = "ARM", n: int = 2
) -> rpa.Example:
    return rpa.Example(
        prompt=prompt,
        n_options=n,
        correct_index=correct,
        family_id=family,
        arm_id=arm,
        task_id=task,
    )


def _leak_examples(start: int, count: int, *, arm: str = "ARM", seed: int = 1) -> list[rpa.Example]:
    """Planted leak: the correct option always has the longer text.  Mention order and count in
    the state are randomised so that only length-type rules can be perfect."""

    rng = random.Random(seed + start)
    out: list[rpa.Example] = []
    for family in range(start, start + count):
        short, long_ = f"id{family:03d}a", f"identifier{family:03d}bbb"
        for k in range(2):
            correct = (family + k) % 2
            options = ["", ""]
            options[correct], options[1 - correct] = long_, short
            mentions = [short] * rng.randrange(1, 4) + [long_] * rng.randrange(1, 4)
            rng.shuffle(mentions)
            state = "\n".join(f"(fact {token} {rng.randrange(100)})" for token in mentions)
            out.append(
                _example(
                    _envelope("which?", state, options),
                    correct,
                    f"leak:F{family:03d}",
                    f"leak:F{family:03d}:{k}",
                    arm=arm,
                )
            )
    return out


def _balanced_twins(start: int, count: int, *, arm: str = "ARM") -> list[rpa.Example]:
    """Same state, same options, flipped truth: nothing on the surface can separate the twins."""

    out: list[rpa.Example] = []
    for family in range(start, start + count):
        a, b = f"answer:{family:04d}a", f"answer:{family:04d}b"
        state = f"(objects {a} {b})\n(assumptions p{family})\n(requires {a} p{family})\n(requires {b} q{family})"
        for k in range(2):
            out.append(
                _example(
                    _envelope("which?", state, [a, b]),
                    k,
                    f"twin:F{family:03d}",
                    f"twin:F{family:03d}:{k}",
                    arm=arm,
                )
            )
    return out


def _noise_examples(families: int, *, seed: int) -> list[rpa.Example]:
    """Live rules, no signal: random identifiers, random mentions, balanced labels per family."""

    rng = random.Random(seed)
    out: list[rpa.Example] = []
    for family in range(families):
        for k in range(2):
            ids = [f"tok{rng.randrange(10**6):06d}{'y' * rng.randrange(1, 7)}" for _ in range(2)]
            mentions = [ids[0]] * rng.randrange(1, 4) + [ids[1]] * rng.randrange(1, 4)
            rng.shuffle(mentions)
            state = "\n".join(f"(fact ({token}) [{rng.randrange(100)}])" for token in mentions)
            out.append(
                _example(
                    _envelope("which?", state, ids),
                    k,
                    f"noise:F{family:03d}",
                    f"noise:F{family:03d}:{k}",
                )
            )
    return out


def _stub_examples(surface: str, *, families: int, levels: Sequence[int]) -> list[rpa.Example]:
    genome = founder_genome(surface)
    return [
        _example(
            build_prompt(genome, item),
            item.correct_index,
            item.family_id,
            item.task_id,
            arm=surface,
            n=len(item.options),
        )
        for item in StubEnvironment().items(families=families, levels=levels)
    ]


def _precondition_twins(
    surface: str, pool: Pool, families: int, *, stratum: str = "P05"
) -> list[rpa.Example]:
    """ORIGINAL / COUNTERFACTUAL twins of the precondition ladder, rendered on ``surface``.

    The pool name enters every family id, so DEV and SHORTCUT_EVAL families are disjoint by
    construction; the adversary only ever sees the rendered string."""

    genome = founder_genome(surface)
    return [
        _example(
            build_prompt(genome, item),
            item.correct_index,
            item.family_id,
            item.task_id,
            arm=surface,
            n=len(item.options),
        )
        for item in build_pool(stratum, pool, families)
    ]


# --------------------------------------------------------------- 1. envelope parsing (C1)


def test_real_prompt_round_trips_on_every_founder_surface() -> None:
    item = StubEnvironment().items(families=1, levels=(0,))[0]
    for surface in SEED_GENOME_BY_ID:
        prompt = build_prompt(founder_genome(surface), item)
        view = rpa.extract_surface(prompt, 2)
        assert view.question == item.question
        assert view.candidate_tokens == (("c0_0_0",), ("c0_0_1",))
        rebuilt = (
            view.header
            + rpa.QUESTION_MARKER
            + view.question
            + rpa.STATE_MARKER
            + view.state_text
            + rpa.OPTIONS_MARKER
            + "\n".join(
                f"{label}: {text}"
                for label, text in zip(rpa.option_labels(2), view.option_texts, strict=True)
            )
            + rpa.ANSWER_MARKER
        )
        assert rebuilt == prompt, surface


def test_guide_block_lands_in_the_header() -> None:
    item = StubEnvironment().items(families=1, levels=(0,))[0]
    prompt = build_prompt(
        founder_genome("L2_SEXPR"), item, guide_policy=SyntaxGuidePolicy.SHARED_CONSTANT
    )
    view = rpa.extract_surface(prompt, 2)
    assert "GUIDE:\n" in view.header
    assert view.question == item.question


def test_envelope_parse_n4_with_literal_options_word_and_multiline_options() -> None:
    options = [
        "alpha OPTIONS",
        'beta\nOPTIONS: nested\n{\n  "x": 1\n}',
        "gamma: OPTION_B is a decoy",
        "delta",
    ]
    state = "line one has OPTIONS: inside\nOPTIONS:\nline three"
    prompt = _envelope("pick", state, options, guide="shared guide text")
    view = rpa.extract_surface(prompt, 4)
    assert view.option_texts == tuple(options)
    assert view.state_text == state
    assert view.question == "pick"
    # the header is everything before the "\nQUESTION: " marker, so it has no trailing newline
    assert view.header.endswith("GUIDE:\nshared guide text")
    assert view.n_options == 4
    # no token is common to every option, so each keeps its own identifiers; the envelope
    # stoplist strips OPTIONS / OPTION_B even when a trailing colon is glued to the word.
    assert view.candidate_tokens[0] == ("alpha",)
    assert view.candidate_tokens[1] == ("nested", "beta")
    assert view.candidate_tokens[2] == ("decoy", "gamma")
    assert view.candidate_tokens[3] == ("delta",)


def test_envelope_rejects_missing_markers_and_wrong_option_count() -> None:
    good = _envelope("q", "state", ["a1a", "b2b"])
    with pytest.raises(ValueError):
        rpa.extract_surface(good.replace("QUESTION: ", "QUESTON: "), 2)
    with pytest.raises(ValueError):
        rpa.extract_surface(good.replace("\nCURRENT STATE:\n", "\nSTATE:\n"), 2)
    with pytest.raises(ValueError):
        rpa.extract_surface(good[: -len("\nANSWER:")], 2)
    with pytest.raises(ValueError):
        rpa.extract_surface(good, 3)
    with pytest.raises(ValueError):
        rpa.extract_surface(good, 1)
    with pytest.raises(ValueError):
        rpa.extract_surface(good, 27)
    assert rpa.extract_surface(_envelope("q", "s", ["x"] * 26), 26).n_options == 26


# ------------------------------------------------------------- 2. boundary rule (AST scan)


def test_adversary_module_never_imports_canonical_machinery_or_nondeterminism() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            imported.extend(f"{module}.{alias.name}" for alias in node.names)
    for name in imported:
        for banned in BANNED_IMPORT_PREFIXES:
            assert not name.startswith(banned), f"{name} crosses the boundary rule"
        assert name.split(".")[0] not in BANNED_NONDETERMINISM_MODULES, name
    assert not any(name.startswith("arena.") for name in imported), imported


# --------------------------------------------------------------------- 3. the rule family


def test_every_feature_has_both_polarities_and_every_position_has_a_constant_rule() -> None:
    for name in rpa.FEATURE_NAMES:
        assert f"{name}:+" in rpa.RULES
        assert f"{name}:-" in rpa.RULES
    for k in range(rpa.MAX_OPTIONS):
        assert f"always_option_{k}" in rpa.RULES
    assert len(rpa.RULES) == 2 * len(rpa.FEATURES) + rpa.MAX_OPTIONS
    assert len(set(rpa.RULES)) == len(rpa.RULES)
    required = {
        "option_text_length",
        "option_token_count",
        "candidate_first_mention_pos",
        "candidate_last_mention_pos",
        "candidate_mention_count",
        "candidate_mention_spread",
        "candidate_lexical_rank",
        "candidate_digit_sum",
        "candidate_id_length",
        "first_mention_line_index",
        "mention_bracket_depth",
        "window_ngram_overlap",
        "window_punctuation_density",
        "candidate_prefix_shared",
        "candidate_suffix_shared",
        "gzip_delta",
        "position_of_option_in_prompt",
        "state_text_length",
    }
    assert required <= set(rpa.FEATURE_NAMES)


def test_ties_abstain_and_are_never_broken_by_position() -> None:
    view = rpa.extract_surface(
        _envelope("q", "state mentions same twice: same same", ["same", "same"]), 2
    )
    predictions = rpa.rule_predictions(view)
    assert all(
        prediction is None
        for rule, prediction in predictions.items()
        if rule not in rpa.POSITIONAL_RULES
    )
    assert predictions["always_option_0"] == 0
    assert predictions["always_option_1"] == 1
    assert predictions["always_option_2"] is None  # beyond n_options: abstain, never clamp
    assert view.candidate_tokens == ((), ())

    # three options, two identical and shorter: the "shorter" rule ties between them and must
    # abstain rather than pick the first of the pair.
    view3 = rpa.extract_surface(
        _envelope("q", "state", ["same", "same", "a-much-longer-option"]), 3
    )
    predictions3 = rpa.rule_predictions(view3)
    assert predictions3["option_text_length:-"] is None
    assert predictions3["option_text_length:+"] == 2
    # and a global feature abstains everywhere by construction
    assert predictions3["state_text_length:+"] is None
    assert predictions3["state_text_length:-"] is None


def test_old_rule_ideas_are_reproduced_on_the_rendered_string() -> None:
    state = "(holds bbb222)\n(requires aaa111 bbb222)\n(note aaa111)\n(note aaa111)"
    view = rpa.extract_surface(_envelope("q", state, ["aaa111", "bbb222"]), 2)
    predictions = rpa.rule_predictions(view)
    assert predictions["candidate_first_mention_pos:-"] == 1  # first_mentioned_in_state
    assert predictions["candidate_last_mention_pos:+"] == 0  # last_mentioned_in_state
    assert predictions["candidate_mention_count:+"] == 0  # more_frequent_in_state
    assert predictions["candidate_lexical_rank:-"] == 0  # alphabetically_first
    assert predictions["candidate_digit_sum:+"] == 1
    assert predictions["always_option_0"] == 0 and predictions["always_option_1"] == 1


# --------------------------------------------------------------- 4. exact statistics (C3e)


def test_clopper_pearson_known_values() -> None:
    assert rpa.clopper_pearson(0, 10) == pytest.approx((0.0, 0.3085), abs=5e-4)
    assert rpa.clopper_pearson(10, 10) == pytest.approx((0.6915, 1.0), abs=5e-4)
    assert rpa.clopper_pearson(5, 10) == pytest.approx((0.187, 0.813), abs=1e-3)
    assert rpa.clopper_pearson(0, 0) == (0.0, 1.0)
    lower, upper = rpa.clopper_pearson(50, 100, 0.05 / 64)
    assert lower < 0.398 and upper > 0.602  # the Bonferroni-adjusted interval is wider
    with pytest.raises(ValueError):
        rpa.clopper_pearson(11, 10)


def test_binomial_tails_match_exact_sums() -> None:
    def exact_upper(k: int, n: int, p: float) -> float:
        return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))

    for k, n, p in [(7, 10, 0.5), (1, 10, 0.3), (10, 10, 0.9), (30, 50, 0.5), (3, 12, 0.25)]:
        assert rpa.binomial_upper_tail(k, n, p) == pytest.approx(exact_upper(k, n, p), rel=1e-9)
        assert rpa.binomial_lower_tail(k - 1, n, p) == pytest.approx(
            1 - exact_upper(k, n, p), rel=1e-9
        )
    probabilities = [0.5, 0.25, 0.5, 0.25]
    manual = 0.0
    for bits in itertools.product([0, 1], repeat=4):
        if sum(bits) >= 3:
            manual += math.prod(p if b else 1 - p for b, p in zip(bits, probabilities, strict=True))
    assert rpa.poisson_binomial_upper_tail(3, probabilities) == pytest.approx(manual)
    assert rpa.poisson_binomial_upper_tail(7, [0.5] * 10) == pytest.approx(exact_upper(7, 10, 0.5))


def test_bonferroni_and_holm_arithmetic_on_a_toy_table() -> None:
    assert rpa.bonferroni_alpha(0.05, 64) == pytest.approx(0.05 / 64)
    assert rpa.holm_adjust([0.01, 0.04, 0.03, 0.5]) == pytest.approx([0.04, 0.09, 0.09, 0.5])
    assert rpa.holm_adjust([0.2, 0.9]) == pytest.approx([0.4, 0.9])
    assert rpa.holm_adjust([0.6, 0.7]) == [1.0, 1.0]
    with pytest.raises(ValueError):
        rpa.bonferroni_alpha(0.05, 0)


def test_permutation_null_exceeds_chance_for_small_n_and_shrinks_with_n() -> None:
    small = rpa.evaluate_rules(_noise_examples(4, seed=3), permutations=400, bootstrap_samples=50)
    large = rpa.evaluate_rules(_noise_examples(160, seed=3), permutations=400, bootstrap_samples=50)
    assert small.n_examples == 8 and large.n_examples == 320
    assert small.null_expected_max > 0.5
    assert large.null_expected_max > 0.5
    assert large.null_expected_max < small.null_expected_max
    assert large.null_expected_max < 0.62
    assert small.null_sd_max > 0.0
    assert 0.0 <= large.null_p_value <= 1.0
    assert set(large.null_quantiles) == {"q50", "q90", "q95", "q99"}
    # the report carries the whole family, ranked, with exact intervals on the decided subset
    assert large.n_rules == len(rpa.RULES)
    assert [stats.rule for stats in large.rules] == sorted(
        (stats.rule for stats in large.rules),
        key=lambda rule: (-large.stats(rule).accuracy, -large.stats(rule).decided_n, rule),
    )
    assert large.bonferroni_alpha == pytest.approx(0.05 / len(rpa.RULES))
    best = large.stats(large.best_rule)
    assert (
        large.bonferroni_lower
        <= best.cp_lower
        <= best.accuracy
        <= best.cp_upper
        <= large.bonferroni_upper
    )


def test_clustered_bootstrap_is_seeded_and_reproducible() -> None:
    examples = _noise_examples(12, seed=5)
    first = rpa.evaluate_rules(examples, seed=11, permutations=100, bootstrap_samples=200)
    second = rpa.evaluate_rules(examples, seed=11, permutations=100, bootstrap_samples=200)
    assert first.to_dict() == second.to_dict()
    other = rpa.evaluate_rules(examples, seed=12, permutations=100, bootstrap_samples=200)
    assert [s.accuracy for s in other.rules] == [s.accuracy for s in first.rules]
    assert any(s.clustered_se > 0 for s in first.rules)
    assert any(
        a.clustered_se != b.clustered_se for a, b in zip(first.rules, other.rules, strict=True)
    )


# --------------------------------------------------- 5. develop / freeze / evaluate split


def test_planted_leak_is_selected_on_dev_and_detected_on_disjoint_eval() -> None:
    dev, evaluation = _leak_examples(0, 30), _leak_examples(30, 30, arm="L3_JSON_AST")
    frozen = rpa.develop_and_freeze(dev, top_k=3, permutations=200, bootstrap_samples=100)
    dev_table = {row["rule"]: row for row in frozen.dev_report["rules"]}
    assert set(dev_table) == set(rpa.RULES)  # the whole DEV table is recorded
    assert dev_table["option_text_length:+"]["accuracy"] == 1.0
    assert dev_table["option_text_length:-"]["accuracy"] == 0.0
    assert dev_table["candidate_first_mention_pos:-"]["accuracy"] < 1.0  # mention order is noise
    assert dev_table["always_option_0"]["accuracy"] == 0.5  # balanced within every family
    # several length-type rules are perfect on DEV and tie; ranking is by accuracy, then by the
    # number of decided items, then by name, so the top-k is deterministic but not "the" rule
    assert len(frozen.selected_rules) == 3
    assert all(dev_table[rule]["accuracy"] == 1.0 for rule in frozen.selected_rules)
    assert frozen.dev_report["best_accuracy"] == 1.0
    assert frozen.dev_report["bonferroni_lower"] > 0.5
    assert [model.kind for model in frozen.models] == ["logistic", "tree"]

    result = rpa.evaluate_frozen(frozen, evaluation)
    assert result.n_adversaries == 5
    arm = result.arm("L3_JSON_AST")
    assert arm.n_families == 30 and arm.n_examples == 60
    assert arm.best_accuracy == 1.0
    assert arm.significant and arm.best_holm_p < 1e-6
    assert arm.best_bonferroni_lower > 0.5
    for rule in frozen.selected_rules:
        assert arm.stats(rule).accuracy == 1.0 and arm.stats(rule).cp_lower > 0.5, rule
    assert arm.stats("model:logistic:difference").accuracy == 1.0
    assert arm.stats("model:tree:difference").accuracy == 1.0
    for stats in arm.adversaries:
        assert stats.abstain_rate == 0.0 and stats.chance == pytest.approx(0.5)

    with pytest.raises(ValueError, match="used in development"):
        rpa.evaluate_frozen(frozen, dev)


def test_balanced_twins_have_no_significant_adversary_and_are_pinned() -> None:
    frozen = rpa.develop_and_freeze(
        _balanced_twins(0, 12), top_k=3, permutations=200, bootstrap_samples=100
    )
    arm = rpa.evaluate_frozen(frozen, _balanced_twins(12, 24)).arms[0]
    assert not arm.significant
    assert arm.best_accuracy == pytest.approx(0.5)
    assert arm.best_holm_p == 1.0
    assert arm.best_bonferroni_upper >= 0.5
    for stats in arm.adversaries:
        assert stats.accuracy == pytest.approx(0.5), stats.name
        assert stats.chance is None if stats.decided_n == 0 else stats.chance == 0.5
    # an adversary that decides nothing has no chance level; the payload stays JSON-clean
    payload = arm.to_dict()
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload
    report = rpa.twin_invariance_report(_balanced_twins(12, 24))
    assert report["n_twin_pairs"] == 24 and report["flipped_truth_fraction"] == 1.0
    for name in rpa.FEATURE_NAMES:
        assert report["features"][name]["identical_fraction"] == 1.0
        assert report["features"][name]["pinned"] is True
        assert report["features"][name]["identical_pair_accuracy"] == {"+": 0.5, "-": 0.5}


#: The only features that read the *whole* state text (which differs between ladder twins in
#: the held-premise block); everything else is a function of the shared option texts and the
#: candidate mentions, which the ladder pins by construction.
WHOLE_STATE_FEATURES = {"window_ngram_overlap", "gzip_delta"}


def test_precondition_twins_pin_every_candidate_mention_feature_on_the_rendered_prompt() -> None:
    surface, other = "L5_COMPACT_SYMBOLIC", "L3_JSON_AST"
    dev = _precondition_twins(surface, Pool.DEV, 12)
    evaluation = _precondition_twins(surface, Pool.SHORTCUT_EVAL, 12) + _precondition_twins(
        other, Pool.SHORTCUT_EVAL, 12
    )
    assert len(dev) == 24 and len(evaluation) == 48
    assert {example.family_id for example in dev}.isdisjoint(
        {example.family_id for example in evaluation}
    )
    # the adversary sees the answer identifiers as candidates and nothing else about the task
    view = rpa.extract_surface(evaluation[0].prompt, 2)
    assert all(
        len(tokens) == 1 and tokens[0].startswith("answer:") for tokens in view.candidate_tokens
    )

    for arm_examples in (evaluation[:24], evaluation[24:]):
        report = rpa.twin_invariance_report(arm_examples)
        assert report["n_twin_pairs"] == 12 and report["flipped_truth_fraction"] == 1.0
        for name in rpa.CANDIDATE_MENTION_FEATURES:
            assert report["features"][name]["identical_fraction"] == 1.0, name
            assert report["features"][name]["pinned"] is True, name
            assert report["features"][name]["identical_pair_accuracy"] == {"+": 0.5, "-": 0.5}, name
        for name in ("option_text_length", "candidate_lexical_rank", "candidate_digit_sum"):
            assert report["features"][name]["identical_fraction"] == 1.0, name
        moving = {
            name for name, row in report["features"].items() if row["identical_fraction"] < 1.0
        }
        assert moving <= WHOLE_STATE_FEATURES, moving

    frozen = rpa.develop_and_freeze(dev, top_k=3, permutations=200, bootstrap_samples=100)
    result = rpa.evaluate_frozen(frozen, evaluation)
    assert [arm.arm_id for arm in result.arms] == sorted([surface, other])
    for arm in result.arms:
        assert arm.n_families == 12 and arm.n_examples == 24 and arm.n_adversaries == 5
        assert not arm.significant, arm.arm_id
        assert arm.best_holm_p >= 0.05, arm.arm_id
        assert arm.best_bonferroni_lower < 0.5, arm.arm_id
        for rule in frozen.selected_rules:
            if rule.split(":")[0] not in WHOLE_STATE_FEATURES:
                assert arm.stats(rule).accuracy == pytest.approx(0.5), (arm.arm_id, rule)


def test_stub_rotated_twins_hold_every_positional_rule_at_exact_chance() -> None:
    examples = _stub_examples("L3_JSON_AST", families=6, levels=(0, 1))
    report = rpa.evaluate_rules(examples, permutations=100, bootstrap_samples=50)
    for rule in rpa.POSITIONAL_RULES:
        stats = report.stats(rule)
        assert stats.accuracy == pytest.approx(0.5), rule
    twins = rpa.twin_invariance_report(examples)
    assert twins["n_twin_pairs"] == 12
    # rotation reverses the option order, so content features reverse rather than repeat
    assert twins["features"]["candidate_lexical_rank"]["reversed_fraction"] == 1.0
    assert twins["features"]["candidate_lexical_rank"]["identical_fraction"] == 0.0


def test_frozen_json_round_trip_preserves_hash_and_rejects_tampering() -> None:
    frozen = rpa.develop_and_freeze(
        _leak_examples(0, 8), top_k=2, permutations=50, bootstrap_samples=20
    )
    text = rpa.to_json(frozen)
    restored = rpa.from_json(text)
    assert restored.content_hash == frozen.content_hash
    assert rpa.to_json(restored) == text
    assert restored == frozen
    payload = json.loads(text)
    payload["selected_rules"][0] = "always_option_1"
    with pytest.raises(ValueError, match="content hash"):
        rpa.from_json(json.dumps(payload))
    # a frozen object whose hash does not cover its payload is refused everywhere
    forged = rpa.FrozenAdversaries(**{**frozen.__dict__, "content_hash": "0" * 64})
    with pytest.raises(ValueError):
        rpa.to_json(forged)
    with pytest.raises(ValueError):
        rpa.evaluate_frozen(forged, _leak_examples(8, 2))


# ------------------------------------------------------------------- 6. shallow models


def test_shallow_models_on_both_backends_and_tie_abstention() -> None:
    dev, evaluation = _leak_examples(0, 20), _leak_examples(20, 10)
    numpy_model = rpa.fit_shallow_model(dev, backend="numpy")
    assert numpy_model.backend == "numpy" and numpy_model.mode == "difference"
    assert rpa.evaluate_model(numpy_model, evaluation)["accuracy"] == 1.0
    sklearn_model = rpa.fit_shallow_model(dev, backend="sklearn")
    assert sklearn_model.backend == "sklearn"
    assert rpa.evaluate_model(sklearn_model, evaluation)["accuracy"] == 1.0
    tree = rpa.fit_shallow_model(dev, kind="tree")
    assert tree.params["max_depth"] == 3
    assert rpa.evaluate_model(tree, evaluation)["accuracy"] == 1.0
    tied = rpa.extract_surface(_envelope("q", "state", ["same", "same"]), 2)
    for model in (numpy_model, sklearn_model, tree):
        assert model.predict(tied) is None
        # the design excludes position, so identical options give identical rows and a tie
        assert model.feature_names == rpa.MODEL_FEATURE_NAMES
        assert not set(model.feature_names) & rpa.POSITIONAL_FEATURES
    scored = rpa.evaluate_model(
        tree, [_example(_envelope("q", "state", ["same", "same"]), 0, "f", "t")]
    )
    assert scored["abstain_rate"] == 1.0 and scored["accuracy"] == 0.5
    with pytest.raises(ValueError):
        rpa.fit_shallow_model(dev, kind="tree", backend="numpy")
    tampered = {**numpy_model.to_dict(), "feature_names": list(rpa.FEATURE_NAMES)}
    with pytest.raises(ValueError, match="position"):
        rpa.ShallowModel.from_dict(tampered)


def test_one_vs_rest_mode_for_four_options() -> None:
    rng = random.Random(9)
    examples: list[rpa.Example] = []
    for family in range(16):
        for k in range(2):
            correct = rng.randrange(4)
            options = [f"opt{family:02d}{k}{i}" for i in range(4)]
            options[correct] = options[correct] + "-longer-text"
            examples.append(
                _example(
                    _envelope("q", "state", options),
                    correct,
                    f"four:F{family:02d}",
                    f"four:F{family:02d}:{k}",
                    n=4,
                )
            )
    dev, evaluation = examples[:16], examples[16:]
    model = rpa.fit_shallow_model(dev)
    assert model.mode == "one_vs_rest"
    assert rpa.evaluate_model(model, evaluation)["accuracy"] == 1.0
    frozen = rpa.develop_and_freeze(dev, top_k=2, permutations=50, bootstrap_samples=20)
    dev_table = {row["rule"]: row for row in frozen.dev_report["rules"]}
    assert dev_table["option_text_length:+"]["accuracy"] == 1.0
    assert all(dev_table[rule]["accuracy"] == 1.0 for rule in frozen.selected_rules)
    arm = rpa.evaluate_frozen(frozen, evaluation).arms[0]
    for rule in frozen.selected_rules:
        assert arm.stats(rule).accuracy == 1.0, rule
        assert arm.stats(rule).chance == pytest.approx(0.25), rule
    assert arm.stats("model:logistic:one_vs_rest").accuracy == 1.0
    assert arm.significant and arm.best_bonferroni_lower > 0.25


def test_evaluate_frozen_reports_every_arm_separately() -> None:
    frozen = rpa.develop_and_freeze(
        _leak_examples(0, 8), top_k=2, permutations=50, bootstrap_samples=20
    )
    evaluation = _leak_examples(8, 6, arm="B_ARM") + _leak_examples(14, 6, arm="A_ARM")
    result = rpa.evaluate_frozen(frozen, evaluation)
    assert [arm.arm_id for arm in result.arms] == ["A_ARM", "B_ARM"]
    assert all(arm.n_adversaries == result.n_adversaries == 4 for arm in result.arms)
    assert result.frozen_hash == frozen.content_hash
    payload = result.to_dict()
    assert json.loads(json.dumps(payload)) == payload
