"""Graph/triples seed language with explicit node types and ordered list edges."""

from __future__ import annotations

import re
from typing import Any

from arena.genome.seeds import L6_GRAPH_TRIPLES

from .._json_tools import canonical_json, strict_json_loads
from ..base import CandidateLanguage

_HEADER = "HAMILTONIAN-GRAPH-TRIPLES/0.1"
_NODE_ID = re.compile(r"n(?:0|[1-9][0-9]*)$")


def _scalar_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    raise TypeError(f"unsupported graph scalar {type(value).__name__}")


class GraphTriplesLanguage(CandidateLanguage):
    format_id = "arena-graph-triples-v0.1"
    genome = L6_GRAPH_TRIPLES

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        nodes: list[tuple[str, str, object | None]] = []
        edges: list[tuple[str, str | int, str]] = []

        def visit(value: object) -> str:
            node_id = f"n{len(nodes)}"
            if isinstance(value, dict):
                nodes.append((node_id, "object", None))
                for role, child in value.items():
                    child_id = visit(child)
                    edges.append((node_id, role, child_id))
            elif isinstance(value, list):
                nodes.append((node_id, "list", None))
                for role, child in enumerate(value):
                    child_id = visit(child)
                    edges.append((node_id, role, child_id))
            else:
                nodes.append((node_id, _scalar_kind(value), value))
            return node_id

        root_id = visit(payload)
        lines = [_HEADER, f"ROOT\t{root_id}"]
        for node_id, kind, value in nodes:
            suffix = "" if kind in {"object", "list"} else f"\t{canonical_json(value)}"
            lines.append(f"NODE\t{node_id}\t{kind}{suffix}")
        lines.extend(
            f"EDGE\t{parent}\t{canonical_json(role)}\t{child}" for parent, role, child in edges
        )
        return "\n".join(lines)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        lines = source.splitlines()
        if len(lines) < 3 or lines[0] != _HEADER or lines[1] != "ROOT\tn0":
            raise ValueError("invalid graph-triples header or root")
        nodes: dict[str, tuple[str, object | None]] = {}
        edges: list[tuple[str, str | int, str]] = []
        reading_edges = False
        for line in lines[2:]:
            parts = line.split("\t")
            if parts[0] == "NODE" and not reading_edges:
                if len(parts) not in {3, 4}:
                    raise ValueError("malformed NODE record")
                _, node_id, kind, *encoded = parts
                expected_id = f"n{len(nodes)}"
                if node_id != expected_id or not _NODE_ID.fullmatch(node_id):
                    raise ValueError(f"expected sequential node ID {expected_id!r}")
                if kind in {"object", "list"}:
                    if encoded:
                        raise ValueError(f"container node {node_id} cannot have a scalar")
                    value = None
                elif kind in {"null", "boolean", "string", "integer", "float"}:
                    if len(encoded) != 1:
                        raise ValueError(f"scalar node {node_id} must have one value")
                    value = strict_json_loads(encoded[0])
                    if _scalar_kind(value) != kind:
                        raise ValueError(f"node {node_id} scalar does not match declared type")
                else:
                    raise ValueError(f"unknown node kind {kind!r}")
                nodes[node_id] = (kind, value)
            elif parts[0] == "EDGE":
                reading_edges = True
                if len(parts) != 4:
                    raise ValueError("malformed EDGE record")
                _, parent, encoded_role, child = parts
                role = strict_json_loads(encoded_role)
                if isinstance(role, bool) or not isinstance(role, (str, int)):
                    raise ValueError("edge roles must be strings or integer list positions")
                edges.append((parent, role, child))
            else:
                raise ValueError("NODE records must precede EDGE records")
        if "n0" not in nodes:
            raise ValueError("root node is not defined")

        children: dict[str, list[tuple[str | int, str]]] = {node_id: [] for node_id in nodes}
        incoming = {node_id: 0 for node_id in nodes}
        for parent, role, child in edges:
            if parent not in nodes or child not in nodes:
                raise ValueError("edge references an unknown node")
            children[parent].append((role, child))
            incoming[child] += 1
        if incoming["n0"] or any(
            count != 1 for node_id, count in incoming.items() if node_id != "n0"
        ):
            raise ValueError("encoded state must be one rooted, non-sharing tree")

        visiting: set[str] = set()
        visited: set[str] = set()

        def build(node_id: str) -> object:
            if node_id in visiting:
                raise ValueError("cycle in graph-triples source")
            visiting.add(node_id)
            kind, scalar = nodes[node_id]
            node_edges = children[node_id]
            if kind == "object":
                result: dict[str, object] = {}
                for role, child in node_edges:
                    if not isinstance(role, str) or role in result:
                        raise ValueError("object edges need unique string roles")
                    result[role] = build(child)
                value: object = result
            elif kind == "list":
                positions = [role for role, _ in node_edges]
                if any(isinstance(role, bool) or not isinstance(role, int) for role in positions):
                    raise ValueError("list edges need integer positions")
                if positions != list(range(len(positions))):
                    raise ValueError("list edge positions must be contiguous and ordered")
                value = [build(child) for _, child in node_edges]
            else:
                if node_edges:
                    raise ValueError("scalar nodes cannot have outgoing edges")
                value = scalar
            visiting.remove(node_id)
            visited.add(node_id)
            return value

        root = build("n0")
        if visited != set(nodes):
            raise ValueError("graph-triples source contains unreachable nodes")
        if not isinstance(root, dict):
            raise ValueError("graph-triples root must be an object")
        return root


GRAPH_TRIPLES = GraphTriplesLanguage()

__all__ = ["GRAPH_TRIPLES", "GraphTriplesLanguage"]
