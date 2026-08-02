"""Small deterministic formula language; no Python/JavaScript evaluation is used."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
    # --- Batch 1: Math & Number ---
    {
        "name": "mod",
        "category": "Math",
        "signature": "mod(number, divisor)",
        "description": "Remainder after division (null if the divisor is 0).",
        "example": "mod([row_id], 10)",
    },
    {
        "name": "pow",
        "category": "Math",
        "signature": "pow(base, exponent)",
        "description": "Raises a base to the power of an exponent.",
        "example": "pow([side], 2)",
    },
    {
        "name": "sqrt",
        "category": "Math",
        "signature": "sqrt(number)",
        "description": "Square root (null for negative numbers).",
        "example": "sqrt([area])",
    },
    {
        "name": "exp",
        "category": "Math",
        "signature": "exp(number)",
        "description": "Returns e raised to the given power.",
        "example": "exp([rate])",
    },
    {
        "name": "ln",
        "category": "Math",
        "signature": "ln(number)",
        "description": "Natural logarithm (null for values <= 0).",
        "example": "ln([value])",
    },
    {
        "name": "log",
        "category": "Math",
        "signature": "log(number, base)",
        "description": "Logarithm of a number in the given base (default 10).",
        "example": "log([value], 2)",
    },
    {
        "name": "log10",
        "category": "Math",
        "signature": "log10(number)",
        "description": "Base-10 logarithm (null for values <= 0).",
        "example": "log10([value])",
    },
    {
        "name": "min",
        "category": "Math",
        "signature": "min(number, ...)",
        "description": "Smallest of the given numbers.",
        "example": "min([a], [b], 0)",
    },
    {
        "name": "max",
        "category": "Math",
        "signature": "max(number, ...)",
        "description": "Largest of the given numbers.",
        "example": "max([a], [b], 0)",
    },
    {
        "name": "sign",
        "category": "Math",
        "signature": "sign(number)",
        "description": "Returns -1, 0, or 1 for the sign of a number.",
        "example": "sign([variance])",
    },
    {
        "name": "trunc",
        "category": "Math",
        "signature": "trunc(number)",
        "description": "Truncates toward zero (drops the fractional part).",
        "example": "trunc([amount])",
    },
    {
        "name": "clamp",
        "category": "Math",
        "signature": "clamp(number, min, max)",
        "description": "Constrains a number to the range [min, max].",
        "example": "clamp([score], 0, 100)",
    },
    # --- Batch 2: Text / String ---
    {
        "name": "length",
        "category": "Text",
        "signature": "length(text)",
        "description": "Number of characters in the text.",
        "example": "length([name])",
    },
    {
        "name": "trim",
        "category": "Text",
        "signature": "trim(text)",
        "description": "Removes leading and trailing whitespace.",
        "example": "trim([name])",
    },
    {
        "name": "ltrim",
        "category": "Text",
        "signature": "ltrim(text)",
        "description": "Removes leading whitespace.",
        "example": "ltrim([code])",
    },
    {
        "name": "rtrim",
        "category": "Text",
        "signature": "rtrim(text)",
        "description": "Removes trailing whitespace.",
        "example": "rtrim([code])",
    },
    {
        "name": "left",
        "category": "Text",
        "signature": "left(text, count)",
        "description": "First N characters of the text.",
        "example": "left([sku], 3)",
    },
    {
        "name": "right",
        "category": "Text",
        "signature": "right(text, count)",
        "description": "Last N characters of the text.",
        "example": "right([sku], 4)",
    },
    {
        "name": "substring",
        "category": "Text",
        "signature": "substring(text, start, length)",
        "description": "Substring from a 0-based start position (length optional).",
        "example": "substring([code], 2, 4)",
    },
    {
        "name": "replace",
        "category": "Text",
        "signature": "replace(text, find, replacement)",
        "description": "Replaces every occurrence of a substring.",
        "example": 'replace([phone], "-", "")',
    },
    {
        "name": "contains",
        "category": "Text",
        "signature": "contains(text, search)",
        "description": "True if the text contains the search value.",
        "example": 'contains([email], "@")',
    },
    {
        "name": "startswith",
        "category": "Text",
        "signature": "startswith(text, prefix)",
        "description": "True if the text starts with the prefix.",
        "example": 'startswith([sku], "US-")',
    },
    {
        "name": "endswith",
        "category": "Text",
        "signature": "endswith(text, suffix)",
        "description": "True if the text ends with the suffix.",
        "example": 'endswith([filename], ".csv")',
    },
    {
        "name": "indexof",
        "category": "Text",
        "signature": "indexof(text, search)",
        "description": "0-based position of the search value, or -1 if absent.",
        "example": 'indexof([email], "@")',
    },
    {
        "name": "padleft",
        "category": "Text",
        "signature": "padleft(text, width, pad)",
        "description": "Pads text on the left to a fixed width (default space).",
        "example": 'padleft([id], 6, "0")',
    },
    {
        "name": "padright",
        "category": "Text",
        "signature": "padright(text, width, pad)",
        "description": "Pads text on the right to a fixed width (default space).",
        "example": 'padright([code], 6, " ")',
    },
    {
        "name": "title",
        "category": "Text",
        "signature": "title(text)",
        "description": "Converts text to Title Case.",
        "example": "title([name])",
    },
    {
        "name": "reverse",
        "category": "Text",
        "signature": "reverse(text)",
        "description": "Reverses the characters in the text.",
        "example": "reverse([code])",
    },
    # --- Batch 3: Logical, Null & Conversion ---
    {
        "name": "if",
        "category": "Logical",
        "signature": "if(condition, when_true, when_false)",
        "description": "Returns one value when the condition is true, another when false.",
        "example": 'if([score] >= 50, "pass", "fail")',
    },
    {
        "name": "isnull",
        "category": "Logical",
        "signature": "isnull(value)",
        "description": "True if the value is null.",
        "example": "isnull([email])",
    },
    {
        "name": "isempty",
        "category": "Logical",
        "signature": "isempty(value)",
        "description": "True if the value is null or an empty string.",
        "example": "isempty([note])",
    },
    {
        "name": "isnumber",
        "category": "Logical",
        "signature": "isnumber(value)",
        "description": "True if the value is numeric.",
        "example": "isnumber([amount])",
    },
    {
        "name": "istext",
        "category": "Logical",
        "signature": "istext(value)",
        "description": "True if the value is text.",
        "example": "istext([code])",
    },
    {
        "name": "ifnull",
        "category": "Logical",
        "signature": "ifnull(value, fallback)",
        "description": "Returns the value, or the fallback when it is null.",
        "example": "ifnull([discount], 0)",
    },
    {
        "name": "tonumber",
        "category": "Conversion",
        "signature": "tonumber(value)",
        "description": "Converts a value to a number (null if not numeric).",
        "example": "tonumber([amount_text])",
    },
    {
        "name": "tostring",
        "category": "Conversion",
        "signature": "tostring(value)",
        "description": "Converts a value to text.",
        "example": "tostring([row_id])",
    },
    {
        "name": "toint",
        "category": "Conversion",
        "signature": "toint(value)",
        "description": "Converts a value to an integer, truncating decimals.",
        "example": "toint([price])",
    },
    {
        "name": "tobool",
        "category": "Conversion",
        "signature": "tobool(value)",
        "description": "Converts a value to true or false.",
        "example": "tobool([flag])",
    },
    # --- Batch 4: Membership (and/or/not and IF..THEN..ENDIF are operators) ---
    {
        "name": "in",
        "category": "Logical",
        "signature": "in(value, option, ...)",
        "description": "True if the value equals one of the following options.",
        "example": 'in([status], "active", "trial")',
    },
    # --- Batch 5: Date & Time ---
    {
        "name": "now",
        "category": "Date",
        "signature": "now()",
        "description": "Current UTC date and time.",
        "example": "now()",
    },
    {
        "name": "today",
        "category": "Date",
        "signature": "today()",
        "description": "Current UTC date (no time component).",
        "example": "today()",
    },
    {
        "name": "year",
        "category": "Date",
        "signature": "year(date)",
        "description": "Four-digit year of a date.",
        "example": "year([created_at])",
    },
    {
        "name": "month",
        "category": "Date",
        "signature": "month(date)",
        "description": "Month number (1-12) of a date.",
        "example": "month([created_at])",
    },
    {
        "name": "day",
        "category": "Date",
        "signature": "day(date)",
        "description": "Day of the month (1-31) of a date.",
        "example": "day([created_at])",
    },
    {
        "name": "hour",
        "category": "Date",
        "signature": "hour(date)",
        "description": "Hour (0-23) of a timestamp.",
        "example": "hour([created_at])",
    },
    {
        "name": "minute",
        "category": "Date",
        "signature": "minute(date)",
        "description": "Minute (0-59) of a timestamp.",
        "example": "minute([created_at])",
    },
    {
        "name": "datediff",
        "category": "Date",
        "signature": "datediff(start, end, unit)",
        "description": "Whole units from start to end (days, hours, minutes, seconds).",
        "example": 'datediff([opened_at], [closed_at], "days")',
    },
    {
        "name": "dateadd",
        "category": "Date",
        "signature": "dateadd(date, amount, unit)",
        "description": "Adds an amount of units to a date (days, hours, minutes, seconds, weeks).",
        "example": 'dateadd([start_date], 7, "days")',
    },
    {
        "name": "dateformat",
        "category": "Date",
        "signature": "dateformat(date, pattern)",
        "description": "Formats a date to text using a strftime pattern.",
        "example": 'dateformat([created_at], "%Y-%m-%d")',
    },
    {
        "name": "dateparse",
        "category": "Date",
        "signature": "dateparse(text, pattern)",
        "description": "Parses text into a date using a strftime pattern.",
        "example": 'dateparse([raw_date], "%m/%d/%Y")',
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
        expression = self._expression()
        if self._peek()[0] != "eof":
            raise ValueError("Unexpected formula content")
        return expression

    def _peek(self) -> tuple[str, str]:
        return self.items[self.index]

    def _take(self) -> tuple[str, str]:
        value = self._peek()
        self.index += 1
        return value

    def _keyword(self) -> str | None:
        kind, value = self._peek()
        return value.lower() if kind == "name" else None

    def _expect_keyword(self, keyword: str) -> None:
        if self._keyword() != keyword:
            raise ValueError(f"Expected {keyword.upper()}")
        self._take()

    def _expression(self) -> Expr:
        left = self._and()
        while self._keyword() == "or":
            self._take()
            left = Expr("binary", "or", (left, self._and()))
        return left

    def _and(self) -> Expr:
        left = self._not()
        while self._keyword() == "and":
            self._take()
            left = Expr("binary", "and", (left, self._not()))
        return left

    def _not(self) -> Expr:
        if self._keyword() == "not":
            self._take()
            return Expr("unary", "not", (self._not(),))
        return self._comparison()

    def _if_keyword(self) -> Expr:
        # 'if' already consumed; parse IF <cond> THEN <expr> [ELSEIF..] [ELSE <expr>] ENDIF
        branches: list[tuple[Expr, Expr]] = []
        condition = self._expression()
        self._expect_keyword("then")
        branches.append((condition, self._expression()))
        else_branch: Expr | None = None
        while True:
            keyword = self._keyword()
            if keyword == "elseif":
                self._take()
                cond = self._expression()
                self._expect_keyword("then")
                branches.append((cond, self._expression()))
            elif keyword == "else":
                self._take()
                else_branch = self._expression()
                self._expect_keyword("endif")
                break
            elif keyword == "endif":
                self._take()
                break
            else:
                raise ValueError("Expected ELSEIF, ELSE, or ENDIF")
        # Desugar into nested if(cond, then, rest) calls (reuses short-circuit eval).
        result: Expr = else_branch if else_branch is not None else Expr("literal", None)
        for cond, branch in reversed(branches):
            result = Expr("call", "if", (cond, branch, result))
        return result

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
            if lowered == "if" and self._peek()[1] != "(":
                return self._if_keyword()
            if lowered not in _FUNCTIONS or self._peek()[1] != "(":
                raise ValueError(f"Function '{value}' is not allowed")
            self._take()
            self.depth += 1
            if self.depth > 20:
                raise ValueError("Formula nesting is too deep")
            arguments: list[Expr] = []
            if self._peek()[1] != ")":
                while True:
                    arguments.append(self._expression())
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
            result = self._expression()
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


def _to_decimal(value: object) -> Decimal | None:
    """Best-effort numeric coercion; returns None when the value is not numeric."""
    if value is None:
        return None
    if isinstance(value, bool):
        return Decimal(1) if value else Decimal(0)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _truthy(value: object) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return bool(value)


def _evaluate_binary(op: str, left: object, right: object) -> object:
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


def _text_function(name: str, values: list[object]) -> object:
    text = _to_text(values[0]) if values else ""

    def _int_arg(index: int, default: int = 0) -> int:
        candidate = _to_decimal(values[index]) if len(values) > index else None
        return int(candidate) if candidate is not None else default

    if name == "length":
        return len(text)
    if name == "trim":
        return text.strip()
    if name == "ltrim":
        return text.lstrip()
    if name == "rtrim":
        return text.rstrip()
    if name == "title":
        return text.title()
    if name == "reverse":
        return text[::-1]
    if name == "left":
        return text[: max(_int_arg(1), 0)]
    if name == "right":
        count = _int_arg(1)
        return text[-count:] if count > 0 else ""
    if name == "substring":
        start = max(_int_arg(1), 0)
        if len(values) > 2:
            return text[start : start + max(_int_arg(2), 0)]
        return text[start:]
    if name == "replace":
        find = _to_text(values[1]) if len(values) > 1 else ""
        replacement = _to_text(values[2]) if len(values) > 2 else ""
        return text if find == "" else text.replace(find, replacement)
    if name == "contains":
        return (_to_text(values[1]) if len(values) > 1 else "") in text
    if name == "startswith":
        return text.startswith(_to_text(values[1]) if len(values) > 1 else "")
    if name == "endswith":
        return text.endswith(_to_text(values[1]) if len(values) > 1 else "")
    if name == "indexof":
        return text.find(_to_text(values[1]) if len(values) > 1 else "")
    if name in {"padleft", "padright"}:
        width = _int_arg(1)
        pad = (_to_text(values[2])[:1] or " ") if len(values) > 2 else " "
        return text.rjust(width, pad) if name == "padleft" else text.ljust(width, pad)
    raise RuntimeError("Unreachable formula function")


def _value_function(name: str, values: list[object]) -> object:
    value = values[0] if values else None
    if name == "isnull":
        return value is None
    if name == "isempty":
        return value is None or (isinstance(value, str) and value == "")
    if name == "isnumber":
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    if name == "istext":
        return isinstance(value, str)
    if name == "tostring":
        return None if value is None else _to_text(value)
    if name == "tonumber":
        return _to_decimal(value)
    if name == "toint":
        number = _to_decimal(value)
        return None if number is None else int(number)
    if name == "tobool":
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            return value != 0
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y", "t"}:
            return True
        if text in {"false", "0", "no", "n", "f", ""}:
            return False
        return None
    raise RuntimeError("Unreachable formula function")


def _math_function(name: str, values: list[object]) -> object:
    if name in {"min", "max"}:
        numbers = [value for value in (_to_decimal(item) for item in values) if value is not None]
        if not numbers:
            return None
        return min(numbers) if name == "min" else max(numbers)

    number = _to_decimal(values[0]) if values else None
    if name == "round":
        if number is None:
            return None
        digits = _to_decimal(values[1]) if len(values) > 1 else None
        return round(number, int(digits) if digits is not None else 0)
    if number is None:
        return None
    if name == "abs":
        return abs(number)
    if name == "floor":
        return int(number // 1)
    if name == "ceil":
        return int(-(-number // 1))
    if name == "sign":
        return 0 if number == 0 else (1 if number > 0 else -1)
    if name == "trunc":
        return int(number)
    if name == "mod":
        divisor = _to_decimal(values[1]) if len(values) > 1 else None
        return None if not divisor else number % divisor
    if name == "clamp":
        low = _to_decimal(values[1]) if len(values) > 1 else None
        high = _to_decimal(values[2]) if len(values) > 2 else None
        if low is None or high is None:
            return None
        return min(max(number, low), high)
    if name == "sqrt":
        return None if number < 0 else number.sqrt()
    if name == "pow":
        exponent = _to_decimal(values[1]) if len(values) > 1 else Decimal(0)
        try:
            return Decimal(str(math.pow(float(number), float(exponent or 0))))
        except (ValueError, OverflowError):
            return None
    if name == "exp":
        try:
            return Decimal(str(math.exp(float(number))))
        except OverflowError:
            return None
    if name == "ln":
        return None if number <= 0 else Decimal(str(math.log(float(number))))
    if name == "log10":
        return None if number <= 0 else Decimal(str(math.log10(float(number))))
    if name == "log":
        if number <= 0:
            return None
        base = _to_decimal(values[1]) if len(values) > 1 else Decimal(10)
        if base is None or base <= 0 or base == 1:
            return None
        return Decimal(str(math.log(float(number), float(base))))
    raise RuntimeError("Unreachable formula function")


_TEXT_FUNCTIONS = frozenset(
    {
        "length",
        "trim",
        "ltrim",
        "rtrim",
        "left",
        "right",
        "substring",
        "replace",
        "contains",
        "startswith",
        "endswith",
        "indexof",
        "padleft",
        "padright",
        "title",
        "reverse",
    }
)
_VALUE_FUNCTIONS = frozenset(
    {"isnull", "isempty", "isnumber", "istext", "tonumber", "tostring", "toint", "tobool"}
)
_DATE_FUNCTIONS = frozenset(
    {
        "now",
        "today",
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "datediff",
        "dateadd",
        "dateformat",
        "dateparse",
    }
)
_DATE_UNIT_SECONDS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
    "days": 86400,
    "weeks": 604800,
}


def _to_datetime(value: object) -> datetime | None:
    """Best-effort coercion of a cell value into a datetime; None when not a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
    return None


def _date_function(name: str, values: list[object]) -> object:
    if name == "now":
        return datetime.now(UTC)
    if name == "today":
        return datetime.now(UTC).date()

    moment = _to_datetime(values[0]) if values else None

    if name in {"year", "month", "day", "hour", "minute"}:
        return None if moment is None else int(getattr(moment, name))
    if name == "dateformat":
        pattern = _to_text(values[1]) if len(values) > 1 else "%Y-%m-%d"
        return None if moment is None else moment.strftime(pattern)
    if name == "dateparse":
        text = _to_text(values[0]) if values else ""
        pattern = _to_text(values[1]) if len(values) > 1 else "%Y-%m-%d"
        try:
            return datetime.strptime(text, pattern)
        except (ValueError, TypeError):
            return None
    if name == "datediff":
        start = _to_datetime(values[0]) if values else None
        end = _to_datetime(values[1]) if len(values) > 1 else None
        if start is None or end is None:
            return None
        unit = (_to_text(values[2]).lower() if len(values) > 2 else "days") or "days"
        seconds = _DATE_UNIT_SECONDS.get(unit)
        if seconds is None:
            return None
        return int((end - start).total_seconds() // seconds)
    if name == "dateadd":
        if moment is None:
            return None
        amount = _to_decimal(values[1]) if len(values) > 1 else None
        unit = (_to_text(values[2]).lower() if len(values) > 2 else "days") or "days"
        seconds = _DATE_UNIT_SECONDS.get(unit)
        if amount is None or seconds is None:
            return None
        return moment + timedelta(seconds=int(amount) * seconds)
    raise RuntimeError("Unreachable formula function")


def evaluate(expression: Expr, row: dict[str, object]) -> object:
    kind = expression.kind
    if kind == "literal":
        return expression.value
    if kind == "field":
        return row.get(str(expression.value))
    if kind == "unary":
        if expression.value == "not":
            return not _truthy(evaluate(expression.children[0], row))
        inner = _to_decimal(evaluate(expression.children[0], row)) or Decimal(0)
        return inner if expression.value == "+" else -inner
    if kind == "binary":
        op = str(expression.value)
        # Logical operators short-circuit and always yield a boolean.
        if op == "and":
            return _truthy(evaluate(expression.children[0], row)) and _truthy(
                evaluate(expression.children[1], row)
            )
        if op == "or":
            return _truthy(evaluate(expression.children[0], row)) or _truthy(
                evaluate(expression.children[1], row)
            )
        return _evaluate_binary(
            op,
            evaluate(expression.children[0], row),
            evaluate(expression.children[1], row),
        )

    name = str(expression.value)
    children = expression.children

    # Short-circuit functions: evaluate only the arguments actually needed so a
    # guarded branch (e.g. if([d] != 0, [n] / [d], 0)) never triggers an unused error.
    if name == "if":
        if _truthy(evaluate(children[0], row)) if children else False:
            return evaluate(children[1], row) if len(children) > 1 else None
        return evaluate(children[2], row) if len(children) > 2 else None
    if name == "coalesce":
        for child in children:
            value = evaluate(child, row)
            if value is not None:
                return value
        return None
    if name == "ifnull":
        primary = evaluate(children[0], row) if children else None
        if primary is not None:
            return primary
        return evaluate(children[1], row) if len(children) > 1 else None

    values = [evaluate(child, row) for child in children]
    if name == "concat":
        return "".join(str(value or "") for value in values)
    if name == "lower":
        return str(values[0] or "").lower()
    if name == "upper":
        return str(values[0] or "").upper()
    if name == "in":
        return any(values[0] == option for option in values[1:])
    if name in _TEXT_FUNCTIONS:
        return _text_function(name, values)
    if name in _VALUE_FUNCTIONS:
        return _value_function(name, values)
    if name in _DATE_FUNCTIONS:
        return _date_function(name, values)
    return _math_function(name, values)
