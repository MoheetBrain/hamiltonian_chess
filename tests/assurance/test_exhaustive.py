from arena.assurance.exhaustive import (
    enumerate_directed_graphs,
    enumerate_scalar_expressions,
    run_universe,
)


def test_depth_one_scalar_universe_has_exact_denominator() -> None:
    expressions = enumerate_scalar_expressions(max_depth=1)
    assert len(expressions) == 30
    result = run_universe(
        "scalar-depth-1",
        expressions,
        lambda item: item.content_hash,
        lambda item: item.op in {"integer", "add", "sub", "mul"},
        parameters={"max_depth": "1"},
    )
    assert result.complete
    assert result.exact_denominator == result.enumerated_cases == result.passed_cases == 30


def test_all_three_node_directed_graphs_are_enumerated() -> None:
    graphs = enumerate_directed_graphs(3)
    assert len(graphs) == 64
