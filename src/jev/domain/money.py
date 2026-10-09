"""Exact money handling. Amounts are `Decimal` in code and strings in JSON; never floats."""

import re
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
# US formatting: optional minus, optional $, digits with comma grouping or none, up to 2 decimals.
_MONEY_RE = re.compile(r"(-)?\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?", re.ASCII)


def cents(amount: Decimal) -> Decimal:
    """Round to whole cents, half away from zero (the convention on the invoices)."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_money(raw: str) -> Decimal:
    """Parse a verbatim amount such as "$1,250.00" into a cent-exact Decimal."""
    match = _MONEY_RE.fullmatch(raw.strip())
    if match is None:
        raise ValueError(f"Not a money amount: {raw!r}")
    sign, whole, fraction = match.groups()
    value = Decimal(f"{whole.replace(',', '')}.{fraction or '0'}")
    return cents(-value if sign else value)


def format_money(amount: Decimal) -> str:
    """Format as on the documents: "$193,750.00", negatives as "-$12.50"."""
    rounded = cents(amount)
    sign = "-" if rounded < 0 else ""
    return f"{sign}${abs(rounded):,.2f}"
