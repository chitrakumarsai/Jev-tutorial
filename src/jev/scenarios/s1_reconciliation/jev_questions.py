"""Jev's questions for S1. Every value question is a Choice over candidates that code found
in the document, plus "none", so an answer is always a verbatim span (or an explicit miss)."""

import re
from dataclasses import dataclass, field
from itertools import combinations

from jev.domain.documents import Document
from jev.extraction.candidates import (
    Candidate,
    find_dates,
    find_integers,
    find_money,
    find_percents,
)
from jev.extraction.invoice_table import InvoiceRow, ParsedInvoice
from jev.providers.jev.types import ChoiceQ, Description, JevRequest, NoulQ, Question

NONE = "none"
NONE_TEXT = "None of these is the requested value."
CONTRACT_PURPOSE = "s1.contract"
_INVOICE_REF = re.compile(r"INV-\d{4}-\d{2}")

LINE_KIND_CRITERIA: dict[str, Description | None] = {
    "line_haul_zone_a": "Line-haul transport charge for Zone A (regional) Loads",
    "line_haul_zone_b": "Line-haul transport charge for Zone B (long haul) Loads",
    "fuel_surcharge": "Fuel surcharge calculated as a percentage of line-haul charges",
    "detention": "Detention: waiting time charged per hour at a site",
    "late_fee": "A late-payment fee for an earlier invoice",
    "other": "Any other kind of charge",
}


@dataclass(frozen=True)
class TermSpec:
    name: str
    kind: str  # "money" | "percent" | "integer"
    question: str
    twin: bool  # also ask with the options reversed (Jev 1.13 option-order check)


TERM_SPECS = (
    TermSpec(
        "zone_a_rate", "money", "Which amount is the line-haul rate per Load for Zone A?", True
    ),
    TermSpec(
        "zone_b_rate", "money", "Which amount is the line-haul rate per Load for Zone B?", True
    ),
    TermSpec("detention_rate", "money", "Which amount is the detention rate per hour?", False),
    TermSpec(
        "discount_threshold",
        "integer",
        "Which number of cumulative Loads in the Contract Year must be exceeded for the volume "
        "discount to apply?",
        True,
    ),
    TermSpec(
        "discount_pct",
        "percent",
        "Which percentage is the volume discount on line-haul charges?",
        True,
    ),
    TermSpec(
        "fuel_cap_pct",
        "percent",
        "Which percentage is the maximum fuel surcharge, as a share of line-haul charges?",
        True,
    ),
    TermSpec(
        "late_fee_pct",
        "percent",
        "Which percentage of an invoice's balance is the late fee?",
        False,
    ),
    TermSpec(
        "late_fee_grace_days",
        "integer",
        "Which number of days after the invoice date may pass before a late fee can be charged?",
        False,
    ),
)
_FINDERS = {"money": find_money, "percent": find_percents, "integer": find_integers}


def _choice(question: str, candidates: list[str]) -> ChoiceQ:
    return ChoiceQ(
        instructions=question, criteria={**{c: None for c in candidates}, NONE: NONE_TEXT}
    )


@dataclass
class QuestionSet:
    """A request plus the candidates behind each Choice, to map answers back to spans."""

    request: JevRequest
    candidates: dict[str, dict[str, Candidate]] = field(default_factory=dict)


def contract_questions(msa: Document, run_id: str) -> QuestionSet:
    by_kind = {kind: finder(msa) for kind, finder in _FINDERS.items()}
    questions: dict[str, Question] = {}
    candidates: dict[str, dict[str, Candidate]] = {}
    for spec in TERM_SPECS:
        cands = by_kind[spec.kind]
        values = [c.value for c in cands]
        question = f"In the `contract`: {spec.question}"
        questions[spec.name] = _choice(question, values)
        candidates[spec.name] = {c.value: c for c in cands}
        if spec.twin:
            questions[f"{spec.name}__rev"] = _choice(question, list(reversed(values)))
    request = JevRequest(
        state={"contract": msa.text}, questions=questions, purpose=CONTRACT_PURPOSE, run_id=run_id
    )
    return QuestionSet(request, candidates)


def _within(row: InvoiceRow, cands: tuple[Candidate, ...]) -> dict[str, Candidate]:
    inside = {}
    for cand in cands:
        spans = tuple(s for s in cand.spans if row.span.start <= s.start and s.end <= row.span.end)
        if spans:
            inside[cand.value] = Candidate(cand.value, spans)
    return inside


def _late_fee_questions(
    doc: Document, invoice: ParsedInvoice, row: InvoiceRow
) -> dict[str, tuple[str, dict[str, Candidate]]]:
    refs = [r for r in _INVOICE_REF.findall(row.description) if r != invoice.number]
    if not refs:
        return {}
    ref_cands = {r: Candidate(r, ()) for r in dict.fromkeys(refs)}
    ref = row.line_ref
    return {
        f"paid_{ref}": (
            f"On line {ref}, which date is when the referenced invoice was paid?",
            _within(row, find_dates(doc)),
        ),
        f"refinv_{ref}": (f"Which invoice is the late fee on line {ref} charged for?", ref_cands),
        f"base_{ref}": (
            f"Which amount is the balance the late fee on line {ref} is charged on?",
            _within(row, find_money(doc)),
        ),
    }


def invoice_questions(doc: Document, invoice: ParsedInvoice, run_id: str) -> QuestionSet:
    questions: dict[str, Question] = {}
    candidates: dict[str, dict[str, Candidate]] = {}
    for row in invoice.rows:
        questions[f"kind_{row.line_ref}"] = ChoiceQ(
            instructions=f"In the `invoice`: what kind of charge is line {row.line_ref}?",
            criteria=LINE_KIND_CRITERIA,
        )
        for key, (text, cands) in _late_fee_questions(doc, invoice, row).items():
            questions[key] = _choice(f"In the `invoice`: {text}", list(cands))
            candidates[key] = cands
    dates = {c.value: c for c in find_dates(doc)}
    questions["invoice_date"] = _choice(
        "In the `invoice`: which date is the invoice date?", list(dates)
    )
    candidates["invoice_date"] = dates
    for a, b in combinations(invoice.rows, 2):
        if (a.description, a.amount) == (b.description, b.amount):
            questions[f"dup_{a.line_ref}_{b.line_ref}"] = NoulQ(
                instructions=f"In the `invoice`: is line {b.line_ref} a second charge for the "
                f"same service already billed on line {a.line_ref}?"
            )
    request = JevRequest(
        state={"invoice": doc.text},
        questions=questions,
        purpose=f"s1.invoice.{doc.doc_id}",
        run_id=run_id,
    )
    return QuestionSet(request, candidates)
