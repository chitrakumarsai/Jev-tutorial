"""S1 reconciliation in pure Decimal code: every calculation and date comparison lives here,
never in the model (ADR 0001)."""

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal

from jev.domain.money import cents
from jev.scenarios.s1_reconciliation.terms import (
    ContractTerms,
    InvoiceFacts,
    LineFact,
    ReconFinding,
)

_HUNDRED = Decimal(100)


def _finding(
    kind: str, facts: InvoiceFacts, refs: Sequence[str], billed: Decimal, expected: Decimal
) -> ReconFinding:
    return ReconFinding(kind, facts.invoice.doc_id, tuple(refs), cents(billed), cents(expected))


def _rate_mismatches(terms: ContractTerms, facts: InvoiceFacts) -> list[ReconFinding]:
    rates = {
        "line_haul_zone_a": terms.zone_a_rate,
        "line_haul_zone_b": terms.zone_b_rate,
        "detention": terms.detention_rate,
    }
    out = []
    for line in facts.lines:
        rate, row = rates.get(line.kind), line.row
        if rate is None or row.quantity is None or line.row.line_ref in facts.duplicate_of:
            continue
        if row.amount != rate * row.quantity:
            out.append(
                _finding("rate_mismatch", facts, [row.line_ref], row.amount, rate * row.quantity)
            )
    return out


def _line_haul(
    terms: ContractTerms, facts: InvoiceFacts, discounted: bool
) -> tuple[Decimal, list[ReconFinding]]:
    """Returns the line-haul base the surcharge should use, plus any discount finding."""
    lines = facts.of_kind("line_haul_zone_a", "line_haul_zone_b")
    billed = sum((line.row.amount for line in lines), Decimal("0"))
    if not discounted or not lines:
        return billed, []
    expected = cents(billed * (1 - terms.discount_pct / _HUNDRED))
    if billed == expected:
        return expected, []
    refs = [line.row.line_ref for line in lines]
    return expected, [_finding("discount_not_applied", facts, refs, billed, expected)]


def _surcharge(terms: ContractTerms, facts: InvoiceFacts, base: Decimal) -> list[ReconFinding]:
    out = []
    for line in facts.of_kind("fuel_surcharge"):
        rate = line.row.stated_percent
        if rate is None:
            continue  # can't verify without a stated rate; never guess
        ref = line.row.line_ref
        if rate > terms.fuel_cap_pct:
            expected = cents(base * terms.fuel_cap_pct / _HUNDRED)
            out.append(_finding("surcharge_over_cap", facts, [ref], line.row.amount, expected))
            continue
        expected = cents(base * rate / _HUNDRED)
        if line.row.amount != expected:
            out.append(
                _finding("surcharge_on_undiscounted_base", facts, [ref], line.row.amount, expected)
            )
    return out


def _duplicates(facts: InvoiceFacts) -> list[ReconFinding]:
    by_ref = {line.row.line_ref: line for line in facts.lines}
    return [
        _finding("duplicate_line", facts, [ref], by_ref[ref].row.amount, Decimal("0"))
        for ref in facts.duplicate_of
        if ref in by_ref
    ]


def _late_fees(
    terms: ContractTerms, facts: InvoiceFacts, dates: Mapping[str, date]
) -> list[ReconFinding]:
    by_ref: dict[str, LineFact] = {line.row.line_ref: line for line in facts.lines}
    out = []
    for fee in facts.late_fees:
        line, invoiced_on = by_ref.get(fee.line_ref), dates.get(fee.referenced_invoice)
        if line is None or invoiced_on is None:
            continue
        days_late = (fee.paid_on - invoiced_on).days
        allowed = days_late > terms.late_fee_grace_days
        expected = cents(fee.base * terms.late_fee_pct / _HUNDRED) if allowed else Decimal("0")
        if line.row.amount != expected:
            out.append(
                _finding("late_fee_incorrect", facts, [fee.line_ref], line.row.amount, expected)
            )
    return out


def reconcile(terms: ContractTerms, invoices: Sequence[InvoiceFacts]) -> tuple[ReconFinding, ...]:
    ordered = sorted(invoices, key=lambda facts: facts.invoice_date)
    dates = {f.invoice.number: f.invoice_date for f in ordered}
    findings: list[ReconFinding] = []
    cumulative, crossed = 0, False
    for facts in ordered:
        # The discount starts with the invoice *after* the month the threshold is crossed (MSA 4.2).
        base, discount = _line_haul(terms, facts, discounted=crossed)
        findings += discount + _surcharge(terms, facts, base) + _duplicates(facts)
        findings += _rate_mismatches(terms, facts) + _late_fees(terms, facts, dates)
        loads = facts.of_kind("line_haul_zone_a", "line_haul_zone_b")
        cumulative += sum(line.row.quantity or 0 for line in loads)
        crossed = crossed or cumulative > terms.discount_threshold
    return tuple(findings)
