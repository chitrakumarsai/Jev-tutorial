from decimal import Decimal

import pytest

from jev.domain.money import cents, decimal_str, format_money, parse_money


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1,250.00", Decimal("1250.00")),
        ("1250", Decimal("1250.00")),
        ("$2,000,000", Decimal("2000000.00")),
        (" $85.00 ", Decimal("85.00")),
        ("-$12.50", Decimal("-12.50")),
    ],
)
def test_parse_money_accepts_us_formats(raw: str, expected: Decimal) -> None:
    assert parse_money(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "$1.2.3", "12,50", "$"])
def test_parse_money_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_money(raw)


def test_cents_rounds_half_up() -> None:
    assert cents(Decimal("2.005")) == Decimal("2.01")
    assert cents(Decimal("2.004")) == Decimal("2.00")
    assert cents(Decimal("-2.005")) == Decimal("-2.01")


def test_format_money_round_trips() -> None:
    assert format_money(Decimal("193750")) == "$193,750.00"
    assert format_money(Decimal("-12.5")) == "-$12.50"
    assert parse_money(format_money(Decimal("98510.71"))) == Decimal("98510.71")


@pytest.mark.parametrize("raw", ["٣", "$１,250.00", "1250.00\n"])
def test_parse_money_accepts_ascii_digits_only(raw: str) -> None:
    if raw.endswith("\n"):
        assert parse_money(raw) == Decimal("1250.00")  # surrounding whitespace is stripped
        return
    with pytest.raises(ValueError):
        parse_money(raw)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("1E+2", "100"), ("98510.71", "98510.71"), ("-12.50", "-12.50"), ("0.00", "0.00")],
)
def test_decimal_str_never_uses_exponent_form(amount: str, expected: str) -> None:
    assert decimal_str(Decimal(amount)) == expected
