"""Parse the invoice line table. Every value is copied verbatim from its row."""

import re
from dataclasses import dataclass
from decimal import Decimal

from jev.domain.documents import Document
from jev.domain.findings import SpanRef
from jev.domain.money import parse_money

_NUMBER_RE = re.compile(r"^# Invoice (INV-\d{4}-\d{2})\s*$", re.M)
_TOTAL_RE = re.compile(r"\*\*Total due: (\$[\d,]+\.\d{2})\*\*")
_ROW_RE = re.compile(r"^\| (L\d+) \| (.+?) \| (.*?) \| (.*?) \| (\$[\d,]+\.\d{2}) \|$", re.M)
_QTY_RE = re.compile(r"\d+", re.ASCII)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)%", re.ASCII)


@dataclass(frozen=True)
class InvoiceRow:
    line_ref: str
    description: str
    quantity: int | None
    unit_price: Decimal | None
    amount: Decimal
    stated_percent: Decimal | None  # e.g. the surcharge rate written in the description
    span: SpanRef


@dataclass(frozen=True)
class ParsedInvoice:
    doc_id: str
    number: str
    rows: tuple[InvoiceRow, ...]
    total_due: Decimal


def _row(document: Document, match: re.Match[str]) -> InvoiceRow:
    ref, description, qty, unit, amount = match.groups()
    qty_match = _QTY_RE.search(qty)
    percents = _PCT_RE.findall(description)
    return InvoiceRow(
        line_ref=ref,
        description=description.strip(),
        quantity=int(qty_match.group()) if qty_match else None,
        unit_price=parse_money(unit) if unit.strip() else None,
        amount=parse_money(amount),
        stated_percent=Decimal(percents[0]) if len(percents) == 1 else None,
        span=SpanRef(
            doc_id=document.doc_id, start=match.start(), end=match.end(), text=match.group()
        ),
    )


def parse_invoice(document: Document) -> ParsedInvoice:
    number = _NUMBER_RE.search(document.text)
    total = _TOTAL_RE.search(document.text)
    if number is None or total is None:
        raise ValueError(f"{document.doc_id}: no invoice number or total found")
    return ParsedInvoice(
        doc_id=document.doc_id,
        number=number.group(1),
        rows=tuple(_row(document, m) for m in _ROW_RE.finditer(document.text)),
        total_due=parse_money(total.group(1)),
    )
