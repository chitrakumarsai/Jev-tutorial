"""Code finds candidate values verbatim; Jev later decides what they mean."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from jev.extraction.candidates import find_dates, find_integers, find_money, find_percents
from jev.extraction.invoice_table import parse_invoice
from jev.extraction.text import find_quote
from jev.scenarios.s1_reconciliation.documents import load_s1_documents

DOCS = load_s1_documents(Path(__file__).resolve().parents[2] / "data")
MSA = DOCS.get("msa")


def values(cands: tuple) -> list[str]:  # type: ignore[type-arg]
    return [c.value for c in cands]


def test_money_candidates_over_find_including_distractors() -> None:
    found = values(find_money(MSA))

    assert {"$1,250.00", "$1,480.00", "$85.00"} <= set(found)
    assert {"$500.00", "$2,000,000"} <= set(found)  # distractors are candidates too
    assert len(found) == len(set(found))  # deduplicated


def test_candidate_spans_point_at_the_exact_text() -> None:
    cand = next(c for c in find_money(MSA) if c.value == "$1,250.00")
    span = cand.spans[0]

    assert MSA.text[span.start : span.end] == "$1,250.00"
    assert span.doc_id == "msa"


def test_percent_and_integer_candidates() -> None:
    assert {"5%", "18%", "1.5%"} <= set(values(find_percents(MSA)))
    ints = set(values(find_integers(MSA)))
    assert {"1,000", "30", "90", "250"} <= ints
    assert "18" not in ints  # part of a percentage
    assert "1,250" not in ints  # part of a money amount


def test_date_candidates_are_parsed_by_code() -> None:
    invoice = DOCS.get("inv-2026-05")
    found = {c.value: c for c in find_dates(invoice)}

    assert {"31 May 2026", "31 March 2026", "11 May 2026"} <= set(found)
    assert found["11 May 2026"].as_date() == date(2026, 5, 11)


def test_invoice_rows_are_parsed_verbatim() -> None:
    invoice = parse_invoice(DOCS.get("inv-2026-10"))

    assert invoice.number == "INV-2026-10"
    refs = [row.line_ref for row in invoice.rows]
    assert refs == ["L1", "L2", "L3", "L4", "L5"]
    l1 = invoice.rows[0]
    assert (l1.quantity, l1.unit_price, l1.amount) == (
        155,
        Decimal("1250.00"),
        Decimal("193750.00"),
    )
    assert invoice.rows[2].stated_percent == Decimal("16.0")
    assert (
        invoice.rows[3].description == invoice.rows[4].description == "Detention, DC-South, 6 hours"
    )
    assert invoice.total_due == Decimal("303026.00")
    assert DOCS.get("inv-2026-10").text[l1.span.start : l1.span.end].startswith("| L1 |")


def test_every_bundled_invoice_parses_and_totals_add_up() -> None:
    for doc in DOCS.documents[1:]:
        invoice = parse_invoice(doc)
        assert sum(r.amount for r in invoice.rows) == invoice.total_due, doc.doc_id


def test_unparseable_invoice_is_rejected() -> None:
    from jev.domain.documents import Document

    with pytest.raises(ValueError, match="invoice number"):
        parse_invoice(Document(doc_id="x", text="no table here"))


def test_find_quote_tolerates_whitespace_but_not_paraphrase() -> None:
    span = find_quote(DOCS, "may not exceed   18% of line-haul\ncharges")

    assert span is not None and span.doc_id == "msa"
    assert "may not exceed 18%" in MSA.text[span.start : span.end]
    assert find_quote(DOCS, "may not go above 18%") is None
    assert find_quote(DOCS, "") is None
