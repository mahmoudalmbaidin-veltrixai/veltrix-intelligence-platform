"""Coverage for the expanded formula function library (Batches 1-3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from vip_api.pipelines.formula import FUNCTION_CATALOG, evaluate, parse_formula

pytestmark = pytest.mark.unit


def _run(expression: str, row: dict[str, object] | None = None) -> object:
    return evaluate(parse_formula(expression), row or {})


def test_catalog_is_expanded_and_well_formed() -> None:
    names = [str(item["name"]) for item in FUNCTION_CATALOG]
    assert len(names) == 58
    assert len(names) == len(set(names)), "duplicate function names"
    for item in FUNCTION_CATALOG:
        assert item["signature"] and item["description"] and item["example"]
    # the original eight remain
    for original in ("abs", "ceil", "floor", "round", "coalesce", "concat", "lower", "upper"):
        assert original in names


def test_math_functions() -> None:
    assert _run("mod(10, 3)") == 1
    assert _run("pow(2, 10)") == Decimal("1024.0")
    assert _run("sqrt(81)") == Decimal("9")
    assert _run("sign(-4)") == -1
    assert _run("trunc(4.9)") == 4
    assert _run("clamp(150, 0, 100)") == Decimal("100")
    assert _run("min(5, 2, 9)") == Decimal("2")
    assert _run("max(5, 2, 9)") == Decimal("9")
    assert _run("round(log10(1000), 4)") == Decimal("3.0000")


def test_math_domain_errors_return_null_not_crash() -> None:
    assert _run("sqrt(-1)") is None
    assert _run("ln(0)") is None
    assert _run("mod(10, 0)") is None  # division by zero -> null, never raises


def test_text_functions() -> None:
    row: dict[str, object] = {
        "name": "  Ada Lovelace ",
        "sku": "US-1234",
        "email": "a@b.com",
    }
    assert _run("length(trim([name]))", row) == 12
    assert _run("left([sku], 2)", row) == "US"
    assert _run("right([sku], 4)", row) == "1234"
    assert _run("substring([sku], 3, 4)", row) == "1234"
    assert _run('replace([sku], "-", "")', row) == "US1234"
    assert _run('contains([email], "@")', row) is True
    assert _run('startswith([sku], "US")', row) is True
    assert _run('padleft("7", 3, "0")', row) == "007"
    assert _run("upper(trim([name]))", row) == "ADA LOVELACE"


def test_logical_null_and_conversion() -> None:
    assert _run('if(5 >= 3, "hi", "lo")') == "hi"
    assert _run("isnull([missing])") is True
    assert _run("isempty([missing])") is True
    assert _run("ifnull([missing], 99)") == Decimal("99")
    assert _run("isnumber(tonumber([amt]))", {"amt": "42.5"}) is True
    assert _run("tonumber([amt]) * 2", {"amt": "42.5"}) == Decimal("85.0")
    assert _run("toint([amt])", {"amt": "42.9"}) == 42
    assert _run('tobool("yes")') is True
    assert _run('tobool("no")') is False


def test_if_short_circuits_and_guards_division() -> None:
    # The untaken branch (a divide-by-zero) must never be evaluated.
    assert _run("if([d] != 0, [n] / [d], -1)", {"n": 10, "d": 0}) == Decimal("-1")
    assert _run("if([d] != 0, [n] / [d], -1)", {"n": 10, "d": 2}) == Decimal("5")


def test_existing_behaviour_preserved() -> None:
    assert evaluate(parse_formula("round([revenue] * 1.15, 2) >= 100"), {"revenue": 100}) is True
    assert evaluate(parse_formula("coalesce([revenue], 0) * 2"), {"revenue": 21}) == 42


# --- Batch 4: logical operators, IF keyword form, membership ---


def test_and_or_not_operators() -> None:
    row: dict[str, object] = {"a": 5, "b": 0}
    assert _run("[a] > 0 and [b] == 0", row) is True
    assert _run("[a] > 10 or [b] == 0", row) is True
    assert _run("not [b] > 0", row) is True
    assert _run("[a] > 10 and [b] == 0", row) is False


def test_and_or_short_circuit() -> None:
    # right side would divide by zero; 'and' must not evaluate it when left is false
    assert _run("[d] != 0 and [n] / [d] > 1", {"n": 10, "d": 0}) is False
    assert _run("[d] == 0 or [n] / [d] > 1", {"n": 10, "d": 0}) is True


def test_if_keyword_form_with_elseif() -> None:
    assert (
        _run('if [a] > 10 then "big" elseif [a] > 3 then "mid" else "small" endif', {"a": 5})
        == "mid"
    )
    assert _run('if [a] > 10 then "big" else "small" endif', {"a": 1}) == "small"
    # both the keyword form and the function form coexist
    assert _run('if([a] > 3, "fn", "no")', {"a": 5}) == "fn"


def test_in_membership() -> None:
    assert _run('in([status], "active", "trial")', {"status": "trial"}) is True
    assert _run('in([status], "active")', {"status": "trial"}) is False


# --- Batch 5: date & time ---


def test_date_extraction() -> None:
    row: dict[str, object] = {"ts": "2024-03-15T10:30:00"}
    assert _run("year([ts])", row) == 2024
    assert _run("month([ts])", row) == 3
    assert _run("day([ts])", row) == 15
    assert _run("hour([ts])", row) == 10
    assert _run("minute([ts])", row) == 30
    assert _run("year([missing])", {}) is None


def test_date_arithmetic_and_formatting() -> None:
    row: dict[str, object] = {"start": "2024-01-01", "end": "2024-01-11"}
    assert _run('datediff([start], [end], "days")', row) == 10
    assert _run('dateformat(dateadd([start], 7, "days"), "%Y-%m-%d")', row) == "2024-01-08"
    assert _run('dateformat(dateparse("03/15/2024", "%m/%d/%Y"), "%Y-%m-%d")', {}) == "2024-03-15"


def test_now_and_today_are_available() -> None:
    from datetime import date as _date
    from datetime import datetime as _datetime

    assert isinstance(_run("now()"), _datetime)
    assert isinstance(_run("today()"), _date)
