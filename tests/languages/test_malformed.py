import json

import pytest

from arena.languages import GRAPH_TRIPLES, JSON_AST, STRUCTURED_ENGLISH, LanguageParseError


def test_json_ast_rejects_unknown_and_missing_state_fields(representative_state) -> None:
    envelope = json.loads(JSON_AST.render(representative_state))
    del envelope["state"]["goal"]
    with pytest.raises(LanguageParseError, match="missing"):
        JSON_AST.parse(json.dumps(envelope))

    envelope = json.loads(JSON_AST.render(representative_state))
    envelope["state"]["private_answer"] = 42
    with pytest.raises(LanguageParseError, match="unknown"):
        JSON_AST.parse(json.dumps(envelope))


def test_json_ast_rejects_duplicate_keys(representative_state) -> None:
    source = JSON_AST.render(representative_state)
    malformed = source.replace('"candidate":', '"candidate":"wrong","candidate":', 1)
    with pytest.raises(LanguageParseError, match="duplicate"):
        JSON_AST.parse(malformed)


def test_duplicate_semantic_ids_are_rejected(representative_state) -> None:
    envelope = json.loads(JSON_AST.render(representative_state))
    envelope["state"]["objects"].append(envelope["state"]["objects"][0])
    with pytest.raises(LanguageParseError, match="duplicate object_id"):
        JSON_AST.parse(json.dumps(envelope))


def test_structured_english_rejects_reordered_roles(representative_state) -> None:
    lines = STRUCTURED_ENGLISH.render(representative_state).splitlines()
    lines[1], lines[2] = lines[2], lines[1]
    with pytest.raises(LanguageParseError, match="expected field label"):
        STRUCTURED_ENGLISH.parse("\n".join(lines))


def test_graph_rejects_dangling_edges(representative_state) -> None:
    source = GRAPH_TRIPLES.render(representative_state)
    lines = source.splitlines()
    edge_index = next(index for index, line in enumerate(lines) if line.startswith("EDGE\t"))
    parts = lines[edge_index].split("\t")
    parts[-1] = "n999999"
    lines[edge_index] = "\t".join(parts)
    with pytest.raises(LanguageParseError, match="unknown node"):
        GRAPH_TRIPLES.parse("\n".join(lines))
