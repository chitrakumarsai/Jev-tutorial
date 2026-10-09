"""Facts the reconciler works from. On the Jev side they come from Jev's typed judgments over
candidates that code found; in tests they are written by hand."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

from jev.extraction.invoice_table import InvoiceRow, ParsedInvoice

LineKind = Literal[
    "line_haul_zone_a", "line_haul_zone_b", "fuel_surcharge", "detention", "late_fee", "other"
]


@dataclass(frozen=True)
class ContractTerms:
    zone_a_rate: Decimal
    zone_b_rate: Decimal
    detention_rate: Decimal
    discount_threshold: int
    discount_pct: Decimal
    fuel_cap_pct: Decimal
    late_fee_pct: Decimal
    late_fee_grace_days: int


@dataclass(frozen=True)
class LineFact:
    row: InvoiceRow
    kind: LineKind


@dataclass(frozen=True)
class LateFeeFact:
    line_ref: str
    referenced_invoice: str  # e.g. "INV-2026-03"
    paid_on: date
    base: Decimal  # the balance the fee is charged on


@dataclass(frozen=True)
class InvoiceFacts:
    invoice: ParsedInvoice
    invoice_date: date
    lines: tuple[LineFact, ...]
    duplicate_of: Mapping[str, str] = field(default_factory=dict)  # line_ref -> earlier line_ref
    late_fees: tuple[LateFeeFact, ...] = ()

    def of_kind(self, *kinds: LineKind) -> list[LineFact]:
        return [line for line in self.lines if line.kind in kinds]


@dataclass(frozen=True)
class ReconFinding:
    kind: str
    doc_id: str
    line_refs: tuple[str, ...]
    billed: Decimal
    expected: Decimal

    @property
    def line_ref(self) -> str:
        return "+".join(self.line_refs)

    @property
    def variance(self) -> Decimal:
        return self.billed - self.expected
