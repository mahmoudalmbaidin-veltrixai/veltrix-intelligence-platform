"""Small deterministic formula language; no Python/JavaScript evaluation is used."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from vip_api.core.errors import ApplicationError

_TOKEN = re.compile(
    r'\s*(?:(?P<number>\d+(?:\.\d+)?)|(?P<string>"(?:[^"\\]|\\.)*")|(?P<field>\[[A-Za-z_][A-Za-z0-9_]{0,127}\])|(?P<op><=|>=|!=|==|[()+\-*/,<>])|(?P<name>[A-Za-z_][A-Za-z0-9_]*))'
)
FUNCTION_CATALOG = (
    {
        "name": "abs",
        "category": "Math",
        "signature": "abs(number)",
        "description": "Returns the absolute numeric value.",
        "example": "abs([variance])",
    },
    {
        "name": "ceil",
        "category": "Math",
        "signature": "ceil(number)",
        "description": "Rounds a number up to the nearest integer.",
        "example": "ceil([quantity])",
    },
    {
        "name": "floor",
        "category": "Math",
        "signature": "floor(number)",
        "description": "Rounds a number down to the nearest integer.",
        "example": "floor([quantity])",
    },
    {
        "name": "round",
        "category": "Math",
        "signature": "round(number, digits)",
        "description": "Rounds a number to the requested decimal places.",
        "example": "round([gross_profit] / [net_revenue] * 100, 2)",
    },
    {
        "name": "coalesce",
        "category": "Logical",
        "signature": "coalesce(value, ...)",
        "description": "Returns the first non-null value.",
        "example": 'coalesce([customer_name], "Unknown")',
    },
    {
        "name": "concat",
        "category": "Text",
        "signature": "concat(value, ...)",
        "description": "Concatenates values as text.",
        "example": 'concat([country], " - ", [city])',
    },
    {
        "name": "lower",
        "category": "Text",
        "signature": "lower(text)",
        "description": "Converts text to lowercase.",
        "example": "lower([email])",
    },
    {
        "name": "upper",
        "category": "Text",
        "signature": "upper(text)",
        "description": "Converts text to uppercase.",
        "example": "upper([region])",
    },
)
_FUNCTIONS = frozenset(str(item["name"]) for item in FUNCTION_CATALOG)


@dataclass(frozen=True, slots=True)
class Expr:
    kind: str
    value: object
    children: tuple[Expr, ...] = ()


def _tokens(source: str) -> list[tuple[str, str]]:
    if not 1 <= len(source) <= 4096:
        raise ValueError("Formula length must be between 1 and 4096 characters")
    result: list[tuple[str, str]] = []
    position = 0
    while position < len(source):
        match = _TOKEN.match(source, position)
        if match is None:
            raise ValueError(f"Unsupported token at character {position + 1}")
        kind = match.lastgroup
        assert kind is not None
        result.append((kind, match.group(kind)))
        position = match.end()
        if len(result) > 512:
            raise ValueError("Formula is too complex")
    result.append(("eof", ""))
    return result


class Parser:
    def __init__(self, source: str) -> None:
        self.items = _tokens(source)
        self.index = 0
        self.depth = 0

    def parse(self) -> Expr:
        expression = self._comparison()
        if self._peek()[0] != "eof":
            raise ValueError("Unexpected formula content")
        return expression

    def _peek(self) -> tuple[str, str]:
        return self.items[self.index]

    def _take(self) -> tuple[str, str]:
        value = self._peek()
        self.index += 1
        return value

    def _comparison(self) -> Expr:
        left = self._sum()
        while self._peek()[1] in {"==", "!=", "<", "<=", ">", ">="}:
            operator = self._take()[1]
            left = Expr("binary", operator, (left, self._sum()))
        return left

    def _sum(self) -> Expr:
        left = self._product()
        while self._peek()[1] in {"+", "-"}:
            operator = self._take()[1]
            left = Expr("binary", operator, (left, self._product()))
        return left

    def _product(self) -> Expr:
        left = self._unary()
        while self._peek()[1] in {"*", "/"}:
            operator = self._take()[1]
            left = Expr("binary", operator, (left, self._unary()))
        return left

    def _unary(self) -> Expr:
        if self._peek()[1] in {"+", "-"}:
            return Expr("unary", self._take()[1], (self._unary(),))
        return self._primary()

    def _primary(self) -> Expr:
        kind, value = self._take()
        if kind == "number":
            return Expr("literal", Decimal(value))
        if kind == "string":
            return Expr("literal", bytes(value[1:-1], "utf-8").decode("unicode_escape"))
        if kind == "field":
            return Expr("field", value[1:-1])
        if kind == "name":
            lowered = value.lower()
            if lowered in {"true", "false", "null"}:
                return Expr("literal", {"true": True, "false": False, "null": None}[lowered])
            if lowered not in _FUNCTIONS or self._peek()[1] != "(":
                raise ValueError(f"Function '{value}' is not allowed")
            self._take()
            self.depth += 1
            if self.depth > 20:
                raise ValueError("Formula nesting is too deep")
            arguments: list[Expr] = []
            if self._peek()[1] != ")":
                while True:
                    arguments.append(self._comparison())
                    if len(arguments) > 20:
                        raise ValueError("Function has too many arguments")
                    if self._peek()[1] != ",":
                        break
                    self._take()
            if self._take()[1] != ")":
                raise ValueError("Expected closing parenthesis")
            self.depth -= 1
            return Expr("call", lowered, tuple(arguments))
        if value == "(":
            result = self._comparison()
            if self._take()[1] != ")":
                raise ValueError("Expected closing parenthesis")
            return result
        raise ValueError("Expected a literal, field, or approved function")


def parse_formula(source: str, available_fields: set[str] | None = None) -> Expr:
    try:
        expression = Parser(source).parse()
    except (ValueError, InvalidOperation) as exc:
        raise ApplicationError(code="INVALID_FORMULA", message=str(exc), status_code=422) from exc
    if available_fields is not None:
        unknown = referenced_fields(expression) - available_fields
        if unknown:
            raise ApplicationError(
                code="UNKNOWN_FORMULA_FIELD",
                message=f"Unknown field: {sorted(unknown)[0]}",
                status_code=422,
            )
    return expression


def referenced_fields(expression: Expr) -> set[str]:
    result = {str(expression.value)} if expression.kind == "field" else set()
    for child in expression.children:
        result.update(referenced_fields(child))
    return result


def referenced_functions(expression: Expr) -> set[str]:
    result = {str(expression.value)} if expression.kind == "call" else set()
    for child in expression.children:
        result.update(referenced_functions(child))
    return result


def evaluate(expression: Expr, row: dict[str, object]) -> object:
    if expression.kind == "literal":
        return expression.value
    if expression.kind == "field":
        return row.get(str(expression.value))
    values = [evaluate(child, row) for child in expression.children]
    if expression.kind == "unary":
        value = Decimal(str(values[0] or 0))
        return value if expression.value == "+" else -value
    if expression.kind == "binary":
        left, right = values
        op = str(expression.value)
        if op in {"==", "!="}:
            return left == right if op == "==" else left != right
        if op in {"<", "<=", ">", ">="}:
            numeric = (int, float, Decimal)
            if isinstance(left, numeric) and isinstance(right, numeric):
                number_left, number_right = Decimal(str(left)), Decimal(str(right))
                if op == "<":
                    return number_left < number_right
                if op == "<=":
                    return number_left <= number_right
                if op == ">":
                    return number_left > number_right
                return number_left >= number_right
            if isinstance(left, str) and isinstance(right, str):
                if op == "<":
                    return left < right
                if op == "<=":
                    return left <= right
                if op == ">":
                    return left > right
                return left >= right
            return False
        if op == "+" and (isinstance(left, str) or isinstance(right, str)):
            return f"{left or ''}{right or ''}"
        a, b = Decimal(str(left or 0)), Decimal(str(right or 0))
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        return a / b
    name = str(expression.value)
    if name == "coalesce":
        return next((value for value in values if value is not None), None)
    if name == "concat":
        return "".join(str(value or "") for value in values)
    if name == "lower":
        return str(values[0] or "").lower()
    if name == "upper":
        return str(values[0] or "").upper()
    number = Decimal(str(values[0] or 0))
    if name == "abs":
        return abs(number)
    if name == "round":
        return round(number, int(str(values[1])) if len(values) > 1 else 0)
    if name == "floor":
        return int(number // 1)
    if name == "ceil":
        return int(-(-number // 1))
    raise RuntimeError("Unreachable formula function")
