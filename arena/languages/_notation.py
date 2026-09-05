"""Small transparent tree notations used by several seed surfaces."""

from __future__ import annotations

import json
from typing import Any


def sexpr_encode(value: Any) -> str:
    if isinstance(value, dict):
        pairs = " ".join(
            f"({json.dumps(key, ensure_ascii=False)} {sexpr_encode(child)})"
            for key, child in value.items()
        )
        return f"(record{(' ' + pairs) if pairs else ''})"
    if isinstance(value, list):
        children = " ".join(sexpr_encode(child) for child in value)
        return f"(list{(' ' + children) if children else ''})"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class _SExprParser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0
        self.decoder = json.JSONDecoder()

    def parse(self) -> Any:
        value = self._value()
        self._space()
        if self.index != len(self.source):
            raise ValueError(f"trailing input at character {self.index}")
        return value

    def _space(self) -> None:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1

    def _expect(self, token: str) -> None:
        self._space()
        if not self.source.startswith(token, self.index):
            raise ValueError(f"expected {token!r} at character {self.index}")
        self.index += len(token)

    def _identifier(self) -> str:
        self._space()
        start = self.index
        while self.index < len(self.source) and (
            self.source[self.index].isalnum() or self.source[self.index] in "_-"
        ):
            self.index += 1
        if start == self.index:
            raise ValueError(f"expected identifier at character {self.index}")
        return self.source[start : self.index]

    def _json_atom(self) -> Any:
        self._space()
        try:
            value, end = self.decoder.raw_decode(self.source, self.index)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid scalar at character {self.index}") from error
        if isinstance(value, (dict, list)):
            raise ValueError("objects and lists require structural S-expression tags")
        self.index = end
        return value

    def _value(self) -> Any:
        self._space()
        if self.index >= len(self.source):
            raise ValueError("unexpected end of input")
        if self.source[self.index] != "(":
            return self._json_atom()
        self.index += 1
        tag = self._identifier()
        if tag == "list":
            result: list[Any] = []
            while True:
                self._space()
                if self.index >= len(self.source):
                    raise ValueError("unclosed list")
                if self.source[self.index] == ")":
                    self.index += 1
                    return result
                result.append(self._value())
        if tag == "record":
            result_dict: dict[str, Any] = {}
            while True:
                self._space()
                if self.index >= len(self.source):
                    raise ValueError("unclosed record")
                if self.source[self.index] == ")":
                    self.index += 1
                    return result_dict
                self._expect("(")
                key = self._json_atom()
                if not isinstance(key, str):
                    raise ValueError("record keys must be strings")
                if key in result_dict:
                    raise ValueError(f"duplicate record key {key!r}")
                result_dict[key] = self._value()
                self._expect(")")
        raise ValueError(f"unknown S-expression tag {tag!r}")


def sexpr_decode(source: str) -> Any:
    return _SExprParser(source).parse()


def typed_prefix_encode(value: Any) -> str:
    if isinstance(value, dict):
        items = ",".join(
            f"{json.dumps(key, ensure_ascii=False)}:{typed_prefix_encode(child)}"
            for key, child in value.items()
        )
        return f"D({items})"
    if isinstance(value, list):
        return f"L({','.join(typed_prefix_encode(child) for child in value)})"
    if isinstance(value, str):
        return f"S({json.dumps(value, ensure_ascii=False)})"
    if value is None:
        return "Z"
    if isinstance(value, bool):
        return f"B({int(value)})"
    if isinstance(value, int):
        return f"I({value})"
    if isinstance(value, float):
        return f"F({json.dumps(value, allow_nan=False)})"
    raise TypeError(f"unsupported typed-prefix value: {type(value).__name__}")


class _TypedPrefixParser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0
        self.decoder = json.JSONDecoder()

    def parse(self) -> Any:
        value = self._value()
        if self.index != len(self.source):
            raise ValueError(f"trailing input at character {self.index}")
        return value

    def _take(self, token: str) -> None:
        if not self.source.startswith(token, self.index):
            raise ValueError(f"expected {token!r} at character {self.index}")
        self.index += len(token)

    def _json_string(self) -> str:
        try:
            value, end = self.decoder.raw_decode(self.source, self.index)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON string at character {self.index}") from error
        if not isinstance(value, str):
            raise ValueError(f"expected JSON string at character {self.index}")
        self.index = end
        return value

    def _closed_scalar(self, prefix: str) -> str:
        self._take(prefix)
        end = self.source.find(")", self.index)
        if end < 0:
            raise ValueError("unclosed typed scalar")
        token = self.source[self.index : end]
        self.index = end + 1
        return token

    def _value(self) -> Any:
        if self.index >= len(self.source):
            raise ValueError("unexpected end of input")
        if self.source.startswith("D(", self.index):
            self.index += 2
            result: dict[str, Any] = {}
            if self.source.startswith(")", self.index):
                self.index += 1
                return result
            while True:
                key = self._json_string()
                if key in result:
                    raise ValueError(f"duplicate dictionary key {key!r}")
                self._take(":")
                result[key] = self._value()
                if self.source.startswith(")", self.index):
                    self.index += 1
                    return result
                self._take(",")
        if self.source.startswith("L(", self.index):
            self.index += 2
            result_list: list[Any] = []
            if self.source.startswith(")", self.index):
                self.index += 1
                return result_list
            while True:
                result_list.append(self._value())
                if self.source.startswith(")", self.index):
                    self.index += 1
                    return result_list
                self._take(",")
        if self.source.startswith("S(", self.index):
            self.index += 2
            value = self._json_string()
            self._take(")")
            return value
        if self.source.startswith("B(", self.index):
            token = self._closed_scalar("B(")
            if token not in {"0", "1"}:
                raise ValueError("boolean token must be 0 or 1")
            return token == "1"
        if self.source.startswith("I(", self.index):
            token = self._closed_scalar("I(")
            if not token or token in {"+", "-"} or not token.lstrip("-").isdigit():
                raise ValueError("invalid integer token")
            if len(token.lstrip("-")) > 1 and token.lstrip("-").startswith("0"):
                raise ValueError("integer token has a leading zero")
            return int(token)
        if self.source.startswith("F(", self.index):
            token = self._closed_scalar("F(")
            try:
                value = json.loads(token)
            except json.JSONDecodeError as error:
                raise ValueError("invalid float token") from error
            if not isinstance(value, float):
                raise ValueError("float token must contain a JSON float")
            return value
        if self.source.startswith("Z", self.index):
            self.index += 1
            return None
        raise ValueError(f"unknown typed prefix at character {self.index}")


def typed_prefix_decode(source: str) -> Any:
    return _TypedPrefixParser(source).parse()
