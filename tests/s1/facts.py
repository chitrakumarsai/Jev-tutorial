"""Hand-built S1 facts for testing the reconciler without Jev (what a perfect reader would say)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from jev.extraction.invoice_table import ParsedInvoice, parse_invoice
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s1_reconciliation.terms import (
    ContractTerms,
    InvoiceFacts,
    LateFeeFact,
    LineFact,
    LineKind,
)

DATA = Path(__file__).resolve().parents[2] / "data"
DOCS = load_s1_documents(DATA)

TRUE_TERMS = ContractTerms(
    zone_a_rate=Decimal("1250.00"),
    zone_b_rate=Decimal("1480.00"),
    detention_rate=Decimal("85.00"),
    discount_threshold=1000,
    discount_pct=Decimal("5"),
    fuel_cap_pct=Decimal("18"),
    late_fee_pct=Decimal("1.5"),
    late_fee_grace_days=30,
)


def kind_of(description: str) -> LineKind:
    if description.startswith("Line-haul, Zone A"):
        return "line_haul_zone_a"
    if description.startswith("Line-haul, Zone B"):
        return "line_haul_zone_b"
    if description.startswith("Fuel surcharge"):
        return "fuel_surcharge"
    if description.startswith("Detention"):
        return "detention"
    if description.startswith("Late fee"):
        return "late_fee"
    return "other"


def invoice_date(invoice: ParsedInvoice) -> date:
    month = int(invoice.number[-2:])
    return (
        date(2026, month, 28)
        if month == 2
        else date(2026, month, 30 if month in (4, 6, 9, 11) else 31)
    )


def true_facts() -> list[InvoiceFacts]:
    facts = []
    for document in DOCS.documents[1:]:
        invoice = parse_invoice(document)
        late = ()
        if invoice.number == "INV-2026-05":
            late = (LateFeeFact("L5", "INV-2026-03", date(2026, 5, 11), Decimal("271672.00")),)
        facts.append(
            InvoiceFacts(
                invoice=invoice,
                invoice_date=invoice_date(invoice),
                lines=tuple(LineFact(row, kind_of(row.description)) for row in invoice.rows),
                duplicate_of={"L5": "L4"} if invoice.number == "INV-2026-10" else {},
                late_fees=late,
            )
        )
    return facts
